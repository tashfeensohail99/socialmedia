"""Run the Phase 1 pipeline AND persist the resulting Post + MediaAssets to DB.

Compared to `pipeline.orchestrator.run_pipeline` (which writes JSON to disk),
this wraps the same engine but:
  - Reads niche + credentials from Postgres via `factory_db.build_context_for_niche`
  - Creates a Post row BEFORE running so progress can be observed (status=GENERATING)
  - Updates the Post row to READY when done, or FAILED on error
  - Inserts MediaAsset rows for each generated file
  - If `topic_id` is provided, links the Post to the Topic and marks the Topic USED
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger
from sqlalchemy import select

from sma.core.pipeline.factory_db import build_context_for_niche
from sma.core.pipeline.orchestrator import PipelineResult, run_pipeline
from sma.core.pipeline.orchestrator_heygen import run_pipeline_heygen_talking_head
from sma.core.topics.base import Topic as EngineTopic
from sma.db.models.post import MediaAsset, Post, PostStatus
from sma.db.models.topic import Topic as TopicRow, TopicStatus
from sma.db.session import get_db_session, require_current_tenant


class PipelineRunError(RuntimeError):
    pass


def run_pipeline_for_db(
    niche_id: int,
    topic_id: int | None,
    output_root: Path,
    *,
    video_length: str | None = None,
    manual_topic_title: str | None = None,
    manual_topic_content: str = "",
) -> Post:
    """Run the pipeline + persist the Post.

    Exactly one of {topic_id, manual_topic_title} must be provided. The function
    creates a Post row with status=GENERATING, runs the engine, then transitions
    to READY (or FAILED) and inserts MediaAsset rows.

    Returns the persisted Post (with id, status, all metadata fields).
    """
    if not topic_id and not manual_topic_title:
        raise ValueError("Provide either topic_id or manual_topic_title")
    if topic_id and manual_topic_title:
        raise ValueError("Provide topic_id OR manual_topic_title, not both")

    tenant_id = require_current_tenant()

    # 1) Resolve the engine Topic + DB Topic row
    engine_topic: EngineTopic
    topic_row: TopicRow | None = None
    if topic_id is not None:
        with get_db_session() as session:
            topic_row = session.get(TopicRow, topic_id)
            if topic_row is None or topic_row.tenant_id != tenant_id:
                raise PipelineRunError(f"topic {topic_id} not found in tenant {tenant_id}")
            engine_topic = EngineTopic(
                title=topic_row.title,
                content=topic_row.content,
                source=str(topic_row.source_id) if topic_row.source_id else "manual",
                score=topic_row.score,
                metadata=dict(topic_row.metadata_json or {}),
            )
    else:
        engine_topic = EngineTopic(
            title=manual_topic_title or "",
            content=manual_topic_content,
            source="manual_api",
        )

    # 2) Build the PipelineContext from DB-stored niche + credentials
    ctx, niche_row = build_context_for_niche(niche_id)
    # Use ctx.niche.* (plain values) not niche_row.* — the ORM row is detached
    # once build_context_for_niche's session closed.
    length = video_length or ctx.niche.video_length_default

    # 3) Insert a Post row with GENERATING status so the UI can poll it.
    with get_db_session() as session:
        post = Post(
            tenant_id=tenant_id,
            niche_id=niche_id,
            topic_id=topic_id,
            status=PostStatus.GENERATING.value,
            video_length=length,
            video_format="horizontal_16_9" if length == "long" else "vertical_9_16",
        )
        session.add(post)
        session.flush()
        post_id_db = post.id
        post_dir_name = f"post_{post_id_db:06d}"

    # 4) Run the engine (writes media to disk under output_root/{post_dir_name}/)
    avatar_mode = getattr(niche_row, "avatar_mode", "off") or "off"
    try:
        if avatar_mode == "talking_head":
            logger.info(f"Routing post {post_id_db} through HeyGen talking-head pipeline")
            result: PipelineResult = run_pipeline_heygen_talking_head(
                topic=engine_topic,
                ctx=ctx,
                output_root=output_root,
                avatar_library_ids=list(niche_row.avatar_library_ids or []),
                heygen_voice_id=niche_row.heygen_voice_id or "",
                video_length=length,  # type: ignore[arg-type]
                post_id=post_dir_name.replace("post_", ""),
            )
        else:
            result = run_pipeline(
                topic=engine_topic,
                ctx=ctx,
                output_root=output_root,
                video_length=length,  # type: ignore[arg-type]
                post_id=post_dir_name.replace("post_", ""),  # so on-disk dir matches our id
            )
    except Exception as e:
        logger.error(f"Pipeline failed for post {post_id_db}: {e}")
        with get_db_session() as session:
            failed = session.get(Post, post_id_db)
            if failed is not None:
                failed.status = PostStatus.FAILED.value
                failed.error_log = str(e)[:5000]
                failed.generated_at = datetime.now(timezone.utc)
        raise PipelineRunError(f"pipeline failed: {e}") from e

    # 5) Persist outputs: update Post fields + create MediaAssets + mark Topic used
    with get_db_session() as session:
        post = session.get(Post, post_id_db)  # type: ignore[assignment]
        assert post is not None
        post.status = PostStatus.READY.value
        post.caption = result.caption
        post.hashtags = result.hashtags
        post.duration_sec = result.duration_sec
        post.image_count = result.image_count
        post.media_cost_usd = result.cost_usd
        post.llm_model = ctx.niche.llm_model
        post.image_provider = ctx.niche.image_provider
        post.voice_provider = ctx.niche.voice_provider
        post.music_provider = ctx.niche.music_provider if ctx.niche.music_enabled else None
        post.generated_at = datetime.now(timezone.utc)

        # Pull story_beats + narrative + hook from the on-disk metadata.json that
        # the engine writes (single source of truth, avoids signature changes upstream).
        try:
            import json
            meta_path = result.output_dir / "metadata.json"
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            post.narrative_script = meta.get("narrative_script", "")
            post.hook_text = meta.get("hook_text", "")
            post.story_beats_json = meta.get("story_beats", [])
            # Populated only on the HeyGen talking-head path.
            if meta.get("avatar_id"):
                post.avatar_id = meta.get("avatar_id")
                post.avatar_cost_usd = meta.get("avatar_cost_usd")
        except Exception as e:
            logger.warning(f"Could not read engine metadata.json: {e}")

        # MediaAsset rows
        asset_paths = {
            "video": result.video_path,
            "thumbnail": result.thumbnail_path,
        }
        # Pick up audio + image assets that the engine writes alongside.
        audio_dir = result.output_dir / "audio"
        images_dir = result.output_dir / "images"
        if audio_dir.exists():
            for p in audio_dir.iterdir():
                if p.is_file():
                    kind = "voiceover" if "voice" in p.name else ("music" if "music" in p.name else "audio")
                    asset_paths[f"{kind}_{p.name}"] = p
        if images_dir.exists():
            for p in sorted(images_dir.iterdir()):
                if p.is_file():
                    asset_paths[f"image_{p.name}"] = p

        for kind, path in asset_paths.items():
            base_kind = (
                "video" if kind == "video"
                else "thumbnail" if kind == "thumbnail"
                else "voiceover" if kind.startswith("voiceover")
                else "music" if kind.startswith("music")
                else "image" if kind.startswith("image")
                else "other"
            )
            session.add(
                MediaAsset(
                    tenant_id=tenant_id,
                    post_id=post_id_db,
                    kind=base_kind,
                    path_or_url=str(path.resolve()),
                )
            )

        # Mark the topic USED if we were driven by one
        if topic_id is not None:
            t = session.get(TopicRow, topic_id)
            if t is not None:
                t.status = TopicStatus.USED.value
                t.used_for_post_id = post_id_db

        session.commit()
        session.refresh(post)
        # Detach with all attributes loaded so callers can read post.* after this
        # session closes (avoids DetachedInstanceError in worker / auto_generate).
        session.expunge(post)
        return post
