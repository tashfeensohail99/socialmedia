"""Cinematic (HeyGen Seedance 2.0) cron — one ad every cinematic_interval_days.

Runs every 6 hours. For each tenant whose niche has cinematic_enabled=True,
checks whether the most-recent cinematic post is older than
niche.cinematic_interval_days. If yes (and the HeyGen wallet clears the
niche's cinematic_min_wallet_usd gate), generates one Seedance ad via the
existing run_pipeline_for_db with pipeline_kind='cinematic'.

Cadence + wallet are the only gates — daily quota and short-post spacing
(which apply to talking-head/slideshow) do NOT apply to cinematic.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from loguru import logger
from sqlalchemy import select

from sma.core.pipeline.db_runner import PipelineRunError, run_pipeline_for_db
from sma.db.models.niche import Niche as NicheRow
from sma.db.models.post import PipelineKind, Post
from sma.db.models.schedule import Schedule, ScheduleStatus
from sma.db.models.social_account import SocialAccount
from sma.db.session import get_session_factory, tenant_scope
from sma.providers.registry import platforms_for_format
from sma.worker.jobs.auto_generate import _next_topic_id

_OUTPUT_ROOT = Path("/app/data/posts_db") if Path("/app").exists() else Path("data/posts_db")


def auto_generate_cinematic_for_all_tenants() -> None:
    """Top-level scheduler entry — checks every tenant for cinematic eligibility."""
    SessionLocal = get_session_factory()
    with SessionLocal() as session:
        tenant_ids = [
            row[0]
            for row in session.execute(
                select(NicheRow.tenant_id).distinct().where(NicheRow.cinematic_enabled == True)  # noqa: E712
            ).all()
        ]
    if not tenant_ids:
        logger.debug("auto_generate_cinematic: no tenants with cinematic_enabled=True")
        return
    logger.info(f"auto_generate_cinematic: {len(tenant_ids)} tenant(s) eligible")
    for tid in tenant_ids:
        with tenant_scope(tid):
            try:
                _maybe_generate_cinematic_for_tenant(tid)
            except Exception as e:
                logger.error(f"tenant {tid}: cinematic generation crashed: {e}")


def _maybe_generate_cinematic_for_tenant(tenant_id: int) -> None:
    SessionLocal = get_session_factory()
    with SessionLocal() as session:
        niche = session.execute(
            select(NicheRow)
            .where(NicheRow.tenant_id == tenant_id, NicheRow.cinematic_enabled == True)  # noqa: E712
            .order_by(NicheRow.id.asc())
            .limit(1)
        ).scalar_one_or_none()
        if niche is None:
            return
        niche_id = niche.id
        interval_days = int(niche.cinematic_interval_days or 3)

        # Cadence check: how long since the last cinematic post for this tenant?
        # We count GENERATING/READY/SCHEDULED/POSTED to prevent double-fire
        # when a render is mid-flight on overlapping ticks.
        last_cinematic = session.execute(
            select(Post.created_at)
            .where(
                Post.tenant_id == tenant_id,
                Post.pipeline_kind == PipelineKind.CINEMATIC.value,
            )
            .order_by(Post.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        now = datetime.now(timezone.utc)
        if last_cinematic is not None:
            age = now - last_cinematic
            if age < timedelta(days=interval_days):
                logger.debug(
                    f"tenant {tenant_id}: last cinematic was {age} ago "
                    f"(< {interval_days}d) — skipping"
                )
                return

        # Active social platforms
        active_platforms = {
            row[0]
            for row in session.execute(
                select(SocialAccount.platform).where(SocialAccount.status == "active")
            ).all()
        }

    # Topic
    topic_id = _next_topic_id(tenant_id)
    if topic_id is None:
        logger.info(f"tenant {tenant_id}: no scored topics for cinematic — skipping")
        return

    logger.info(f"tenant {tenant_id}: firing CINEMATIC from topic {topic_id}")
    try:
        post = run_pipeline_for_db(
            niche_id=niche_id,
            topic_id=topic_id,
            output_root=_OUTPUT_ROOT,
            video_length="short",
            pipeline_kind=PipelineKind.CINEMATIC.value,
        )
    except (PipelineRunError, ValueError) as e:
        logger.error(f"tenant {tenant_id}: cinematic pipeline failed: {e}")
        return

    # NOTE: if the wallet-gate downgraded this run to slideshow, post.pipeline_kind
    # will be 'slideshow' — that's still a valid post, just not cinematic. Either
    # way we schedule it for posting.
    post_id = post.id
    post_format = post.video_format

    valid_for_format = platforms_for_format("short")
    target_platforms = sorted(active_platforms & valid_for_format)
    if not target_platforms:
        logger.info(
            f"tenant {tenant_id}: cinematic post {post_id} generated but no "
            f"connected short platforms — leaving as READY for manual posting"
        )
        return

    SessionLocal = get_session_factory()
    with SessionLocal() as session:
        session.add(
            Schedule(
                tenant_id=tenant_id,
                post_id=post_id,
                scheduled_for_utc=datetime.now(timezone.utc),
                platforms_json=target_platforms,
                status=ScheduleStatus.PENDING.value,
            )
        )
        from sma.db.models.post import PostStatus as _PostStatus
        p = session.get(Post, post_id)
        if p is not None:
            p.status = _PostStatus.SCHEDULED.value
        session.commit()

    logger.info(
        f"tenant {tenant_id}: cinematic post {post_id} (kind={post.pipeline_kind}) "
        f"scheduled to {target_platforms}"
    )
