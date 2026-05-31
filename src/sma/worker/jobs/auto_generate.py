"""Worker job: auto-generate + schedule videos from discovered topics.

This is the missing link that makes the system fully autonomous:

    discover_topics  →  [auto_generate]  →  process_schedules
       (finds)            (this job)           (posts)

For every tenant, every run:
  1. Read the tenant's daily limits (daily_short_videos, daily_long_videos).
  2. Count how many auto-generated posts already exist *today* (UTC) per length.
  3. For the remaining quota, pick the highest-scored unused Topics.
  4. Run the pipeline to build each video (Post + MediaAssets).
  5. Auto-create a Schedule row (scheduled_for = now) targeting the tenant's
     connected platforms that are valid for the video format — so
     process_schedules picks it up on its next 60s tick and posts it.

Idempotent-ish: the per-day count caps generation, so re-runs within the same
day won't exceed the limit. Spreads posts across the day by only generating a
fraction per run (so a limit of 4 doesn't fire all 4 at 00:00).
"""

from __future__ import annotations

from datetime import datetime, timezone

from loguru import logger
from sqlalchemy import func, select

from sma.core.pipeline.db_runner import PipelineRunError, run_pipeline_for_db
from sma.db.models.niche import Niche as NicheRow
from sma.db.models.post import Post, PostStatus
from sma.db.models.schedule import Schedule, ScheduleStatus
from sma.db.models.social_account import SocialAccount
from sma.db.models.tenant import Tenant
from sma.db.models.topic import Topic as TopicRow, TopicStatus
from sma.db.session import get_session_factory, tenant_scope
from sma.providers.registry import platforms_for_format

# Where generated media is written (matches the actions router).
from pathlib import Path

_OUTPUT_ROOT = Path("data/posts_db")

# How many posts to generate per run, at most, per (tenant, length). Keeps a
# daily limit of e.g. 6 from all firing in one tick — spreads them out over the
# day's 30-min discovery cadence.
_MAX_PER_RUN = 1


def auto_generate_for_all_tenants() -> None:
    """Top-level entry point — APScheduler calls this on an interval."""
    SessionLocal = get_session_factory()
    with SessionLocal() as session:
        tenants = session.execute(
            select(Tenant).execution_options(skip_tenant_filter=True)
        ).scalars().all()
        tenant_rows = [
            (t.id, t.daily_short_videos, t.daily_long_videos) for t in tenants
        ]

    for tenant_id, daily_short, daily_long in tenant_rows:
        with tenant_scope(tenant_id):
            try:
                _auto_generate_for_tenant(tenant_id, daily_short, daily_long)
            except Exception as e:
                logger.error(f"auto_generate: tenant {tenant_id} failed: {e}")


def _count_today(session, tenant_id: int, video_length: str) -> int:
    """How many posts of this length were generated today (UTC) for this tenant."""
    now = datetime.now(timezone.utc)
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return (
        session.execute(
            select(func.count())
            .select_from(Post)
            .where(
                Post.tenant_id == tenant_id,
                Post.video_length == video_length,
                Post.generated_at >= start_of_day,
                Post.status.in_(
                    [PostStatus.READY.value, PostStatus.SCHEDULED.value, PostStatus.POSTED.value]
                ),
            )
            .execution_options(skip_tenant_filter=True)
        ).scalar()
        or 0
    )


def _minutes_since_last_post(session, tenant_id: int, video_length: str) -> float | None:
    """Minutes since the most recent generated post of this length, or None if never."""
    last = session.execute(
        select(func.max(Post.generated_at))
        .where(
            Post.tenant_id == tenant_id,
            Post.video_length == video_length,
            Post.generated_at.isnot(None),
            Post.status.in_(
                [PostStatus.READY.value, PostStatus.SCHEDULED.value, PostStatus.POSTED.value]
            ),
        )
        .execution_options(skip_tenant_filter=True)
    ).scalar()
    if last is None:
        return None
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - last).total_seconds() / 60.0


def _auto_generate_for_tenant(tenant_id: int, daily_short: int, daily_long: int) -> None:
    SessionLocal = get_session_factory()

    # Resolve the tenant's first niche (single-niche assumption for autonomy).
    with SessionLocal() as session:
        niche = session.execute(
            select(NicheRow).order_by(NicheRow.id.asc()).limit(1)
        ).scalar_one_or_none()
        if niche is None:
            logger.debug(f"tenant {tenant_id}: no niche configured — skipping auto-generate")
            return
        niche_id = niche.id

        # Today's counts per length.
        short_today = _count_today(session, tenant_id, "short")
        long_today = _count_today(session, tenant_id, "long")
        short_gap = _minutes_since_last_post(session, tenant_id, "short")
        long_gap = _minutes_since_last_post(session, tenant_id, "long")

        # Which connected platforms are available?
        active_platforms = {
            row[0]
            for row in session.execute(
                select(SocialAccount.platform).where(SocialAccount.status == "active")
            ).all()
        }

    if not active_platforms:
        logger.info(
            f"tenant {tenant_id}: no connected social accounts — generating but not scheduling"
        )

    # Spread posts evenly across the day. With daily_short=3 that's one every
    # ~8h. We allow a small head-start (90% of the slot) so clock jitter doesn't
    # push a post past midnight and waste the daily quota.
    def _slot_minutes(per_day: int) -> float:
        return (24 * 60) / per_day * 0.9 if per_day > 0 else 0.0

    # Build a work plan: (length, remaining quota), honoring spacing.
    plan: list[tuple[str, int]] = []
    short_remaining = max(0, daily_short - short_today)
    long_remaining = max(0, daily_long - long_today)

    if short_remaining > 0:
        slot = _slot_minutes(daily_short)
        if short_gap is None or short_gap >= slot:
            plan.append(("short", _MAX_PER_RUN))
        else:
            logger.debug(
                f"tenant {tenant_id}: short post spacing not met "
                f"({short_gap:.0f}/{slot:.0f} min) — waiting"
            )
    if long_remaining > 0:
        slot = _slot_minutes(daily_long)
        if long_gap is None or long_gap >= slot:
            plan.append(("long", _MAX_PER_RUN))
        else:
            logger.debug(
                f"tenant {tenant_id}: long post spacing not met "
                f"({long_gap:.0f}/{slot:.0f} min) — waiting"
            )

    if not plan:
        logger.debug(
            f"tenant {tenant_id}: nothing to do "
            f"(short {short_today}/{daily_short}, long {long_today}/{daily_long})"
        )
        return

    for video_length, n_to_make in plan:
        for _ in range(n_to_make):
            topic_id = _next_topic_id(tenant_id)
            if topic_id is None:
                logger.info(
                    f"tenant {tenant_id}: no unused scored topics for {video_length} video"
                )
                break
            _generate_and_schedule(
                tenant_id, niche_id, topic_id, video_length, active_platforms
            )


def _next_topic_id(tenant_id: int) -> int | None:
    """Highest-scored SCORED topic not yet used, for this tenant."""
    SessionLocal = get_session_factory()
    with SessionLocal() as session:
        row = session.execute(
            select(TopicRow.id)
            .where(TopicRow.status == TopicStatus.SCORED.value)
            .order_by(TopicRow.score.desc().nulls_last(), TopicRow.id.asc())
            .limit(1)
        ).scalar_one_or_none()
        return row


def _generate_and_schedule(
    tenant_id: int,
    niche_id: int,
    topic_id: int,
    video_length: str,
    active_platforms: set[str],
) -> None:
    logger.info(
        f"tenant {tenant_id}: auto-generating {video_length} video from topic {topic_id}"
    )
    try:
        post = run_pipeline_for_db(
            niche_id=niche_id,
            topic_id=topic_id,
            output_root=_OUTPUT_ROOT,
            video_length=video_length,
        )
    except (PipelineRunError, ValueError) as e:
        logger.error(f"tenant {tenant_id}: pipeline failed for topic {topic_id}: {e}")
        return

    post_id = post.id
    post_format = post.video_format

    # Pick platforms valid for this format AND connected by the tenant.
    valid_for_format = platforms_for_format(video_length)
    target_platforms = sorted(active_platforms & valid_for_format)
    if not target_platforms:
        logger.info(
            f"tenant {tenant_id}: post {post_id} generated but no connected platform "
            f"supports {video_length} format — leaving as READY for manual posting"
        )
        return

    # Schedule immediately (now) — process_schedules will dispatch on next tick.
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
        p = session.get(Post, post_id)
        if p is not None:
            p.status = PostStatus.SCHEDULED.value
        session.commit()

    logger.info(
        f"tenant {tenant_id}: post {post_id} scheduled to {target_platforms}"
    )
