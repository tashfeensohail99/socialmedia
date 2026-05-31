"""`sma migrate-from-json` — import legacy Phase 1 outputs into Postgres.

Walks `data/posts/post_*/metadata.json` files and creates Post + MediaAsset rows.
Also imports `data/usage/events.jsonl` into the `usage_events` table.

Everything goes to tenant_id=1 (the default workspace).

Idempotent on the post side: if a Post already exists with the same on-disk
post_id, it's skipped. Usage events are de-duplicated by their (timestamp,
provider, model, operation) tuple.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import typer
from loguru import logger
from sqlalchemy import select

from sma.db.models.post import MediaAsset, Post, PostStatus
from sma.db.models.tenant import SubscriptionStatus, Tenant
from sma.db.models.usage_event import UsageEvent as UsageEventRow
from sma.db.session import get_session_factory, tenant_scope


def _ensure_default_tenant() -> int:
    """Create tenant id=1 if it doesn't exist. Returns the tenant id."""
    SessionLocal = get_session_factory()
    with SessionLocal() as session:
        t = session.get(Tenant, 1)
        if t is None:
            t = Tenant(
                id=1,
                name="Default Workspace (imported)",
                subscription_status=SubscriptionStatus.NONE.value,
            )
            session.add(t)
            session.commit()
        return 1


def _import_post(post_dir: Path, tenant_id: int) -> bool:
    """Import a single post directory. Returns True if a new row was created."""
    meta_path = post_dir / "metadata.json"
    if not meta_path.exists():
        logger.warning(f"Skipping {post_dir}: no metadata.json")
        return False

    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        logger.error(f"Bad JSON in {meta_path}: {e}")
        return False

    SessionLocal = get_session_factory()
    with SessionLocal() as session:
        # Check for an existing Post with the same on-disk id (stored in error_log
        # tag for traceability) — keeps the import idempotent on re-runs.
        legacy_id = meta.get("post_id", post_dir.name)
        existing = session.execute(
            select(Post).where(Post.error_log == f"imported_from:{legacy_id}")
        ).scalar_one_or_none()
        if existing is not None:
            return False

        # The legacy data didn't track a niche_id — default to 0 (the import
        # script creates a placeholder niche if none exists).
        niche_id = meta.get("niche_id", 0)
        if niche_id == 0:
            from sma.db.models.niche import Niche

            placeholder = session.execute(
                select(Niche).where(Niche.name == "Imported (legacy)")
            ).scalar_one_or_none()
            if placeholder is None:
                placeholder = Niche(
                    tenant_id=tenant_id,
                    name="Imported (legacy)",
                    description=meta.get("niche", "Imported from Phase 1 JSON output."),
                    target_audience="legacy import",
                    tone="(legacy)",
                    voice_id="",
                )
                session.add(placeholder)
                session.flush()
            niche_id = placeholder.id

        generated_at = None
        gen_at_raw = meta.get("generated_at")
        if isinstance(gen_at_raw, str):
            try:
                generated_at = datetime.fromisoformat(gen_at_raw.replace("Z", "+00:00"))
            except ValueError:
                pass

        post = Post(
            tenant_id=tenant_id,
            niche_id=niche_id,
            topic_id=None,
            status=PostStatus.READY.value,
            video_length=meta.get("video_length", "short"),
            video_format=meta.get("video_format", "vertical_9_16"),
            caption=meta.get("caption", ""),
            hashtags=list(meta.get("hashtags", [])),
            narrative_script=meta.get("narrative_script", ""),
            hook_text=meta.get("hook_text", ""),
            story_beats_json=list(meta.get("story_beats", [])),
            llm_model=meta.get("llm_model", ""),
            image_provider=meta.get("image_provider", ""),
            voice_provider=meta.get("voice_provider", ""),
            music_provider=meta.get("music_provider"),
            duration_sec=float(meta.get("duration_sec", 0.0)),
            image_count=int(meta.get("image_count", 0)),
            media_cost_usd=float(meta.get("media_cost_usd", 0.0)),
            generated_at=generated_at,
            error_log=f"imported_from:{legacy_id}",
        )
        session.add(post)
        session.flush()

        # MediaAssets: video + thumbnail + per-file under audio/ and images/
        for asset_kind, rel in (
            ("video", meta.get("video_path", "video/final.mp4")),
            ("thumbnail", meta.get("thumbnail_path", "thumbnail.jpg")),
        ):
            asset_path = post_dir / rel
            if asset_path.exists():
                session.add(
                    MediaAsset(
                        tenant_id=tenant_id,
                        post_id=post.id,
                        kind=asset_kind,
                        path_or_url=str(asset_path.resolve()),
                    )
                )

        audio_dir = post_dir / "audio"
        if audio_dir.exists():
            for f in audio_dir.iterdir():
                if not f.is_file():
                    continue
                kind = (
                    "voiceover" if "voice" in f.name
                    else "music" if "music" in f.name
                    else "audio"
                )
                session.add(
                    MediaAsset(
                        tenant_id=tenant_id, post_id=post.id, kind=kind,
                        path_or_url=str(f.resolve()),
                    )
                )

        images_dir = post_dir / "images"
        if images_dir.exists():
            for f in sorted(images_dir.iterdir()):
                if f.is_file():
                    session.add(
                        MediaAsset(
                            tenant_id=tenant_id, post_id=post.id, kind="image",
                            path_or_url=str(f.resolve()),
                        )
                    )

        session.commit()
        return True


def _import_usage(jsonl_path: Path, tenant_id: int) -> tuple[int, int]:
    """Import the usage events JSONL. Returns (imported, skipped)."""
    if not jsonl_path.exists():
        logger.info(f"No usage file at {jsonl_path}; skipping")
        return 0, 0

    SessionLocal = get_session_factory()
    imported = 0
    skipped = 0

    # Build a set of (timestamp, provider, model, operation) already in the DB
    # for dedup. For large imports a real bulk-insert + ON CONFLICT would scale
    # better; this is fine for tens of thousands of events.
    with SessionLocal() as session:
        existing_keys: set[tuple] = {
            (e.occurred_at.isoformat(), e.provider, e.model, e.operation)
            for e in session.scalars(
                select(UsageEventRow).where(UsageEventRow.tenant_id == tenant_id)
            ).all()
        }

    rows_to_insert: list[UsageEventRow] = []
    with jsonl_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts_str = e.get("timestamp", "")
            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            except ValueError:
                continue
            key = (ts.isoformat(), e.get("provider", ""), e.get("model", ""), e.get("operation", ""))
            if key in existing_keys:
                skipped += 1
                continue
            existing_keys.add(key)
            rows_to_insert.append(
                UsageEventRow(
                    tenant_id=tenant_id,
                    provider=e.get("provider", ""),
                    model=e.get("model", ""),
                    operation=e.get("operation", ""),
                    tokens_in=int(e.get("tokens_in", 0) or 0),
                    tokens_out=int(e.get("tokens_out", 0) or 0),
                    units=int(e.get("units", 0) or 0),
                    cost_usd=float(e.get("cost_usd", 0.0) or 0.0),
                    post_id=None,
                    occurred_at=ts,
                    metadata_json=dict(e.get("metadata", {})),
                )
            )
            imported += 1

    if rows_to_insert:
        with SessionLocal() as session:
            session.add_all(rows_to_insert)
            session.commit()
    return imported, skipped


def cmd_migrate_from_json(
    posts_root: Path = typer.Option(Path("data/posts"), help="Directory containing post_* dirs"),
    usage_jsonl: Path = typer.Option(Path("data/usage/events.jsonl"), help="JSONL with usage events"),
    smoke_root: Path = typer.Option(Path("data/smoke"), help="Optional: also import smoke-test posts"),
) -> None:
    """Import legacy JSON posts + usage events into Postgres (as tenant_id=1)."""
    tenant_id = _ensure_default_tenant()

    # Posts can be imported without a tenant context (we set tenant_id explicitly).
    new_posts = 0
    total_dirs = 0
    for root in (posts_root, smoke_root):
        if not root.exists():
            continue
        for child in sorted(root.iterdir()):
            if not child.is_dir() or not child.name.startswith("post_"):
                continue
            total_dirs += 1
            if _import_post(child, tenant_id):
                new_posts += 1

    # Usage events
    imported, skipped = _import_usage(usage_jsonl, tenant_id)

    typer.echo(
        f"\n✓ Migration complete (tenant_id={tenant_id}):\n"
        f"  posts:        {new_posts} new / {total_dirs} dirs scanned\n"
        f"  usage events: {imported} imported, {skipped} skipped (already present)"
    )
