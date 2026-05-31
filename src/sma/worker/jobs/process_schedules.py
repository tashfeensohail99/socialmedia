"""Worker job: dispatch pending Schedules whose time has arrived.

Polled every 60s by APScheduler. For each due Schedule:
  1. Mark IN_PROGRESS to claim it (avoids double-processing on race).
  2. Load the post + media assets.
  3. For each platform: build the SocialPoster from the tenant's stored OAuth
     token, attempt the post, record a PostingAttempt row.
  4. If at least one platform succeeded, mark the Post POSTED and the Schedule DONE.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from loguru import logger
from sqlalchemy import select

from sma.db.crypto import decrypt_blob
from sma.db.models.post import MediaAsset, Post, PostStatus
from sma.db.models.schedule import (
    AttemptStatus,
    PostingAttempt,
    Schedule,
    ScheduleStatus,
)
from sma.db.models.social_account import SocialAccount
from sma.db.session import get_session_factory, tenant_scope
from sma.providers.registry import get_provider


def process_due_schedules() -> None:
    """Top-level entry point — APScheduler calls this every 60s."""
    SessionLocal = get_session_factory()
    now = datetime.now(timezone.utc)

    with SessionLocal() as session:
        # Find PENDING schedules whose time has come. Cross-tenant query (operator-level).
        due = session.execute(
            select(Schedule)
            .where(
                Schedule.status == ScheduleStatus.PENDING.value,
                Schedule.scheduled_for_utc <= now,
            )
            .execution_options(skip_tenant_filter=True)
            .order_by(Schedule.scheduled_for_utc.asc())
            .limit(50)  # batch cap per tick
        ).scalars().all()
        if not due:
            return
        schedule_ids = [(s.id, s.tenant_id) for s in due]

    logger.info(f"process_schedules: {len(schedule_ids)} due")
    for sched_id, tenant_id in schedule_ids:
        with tenant_scope(tenant_id):
            try:
                _dispatch_schedule(sched_id, tenant_id)
            except Exception as e:
                logger.error(f"schedule {sched_id} dispatch failed: {e}")


def _dispatch_schedule(sched_id: int, tenant_id: int) -> None:
    SessionLocal = get_session_factory()
    # 1) Claim the schedule.
    with SessionLocal() as session:
        sched = session.get(Schedule, sched_id)
        if sched is None or sched.status != ScheduleStatus.PENDING.value:
            return  # already claimed by another tick or cancelled
        sched.status = ScheduleStatus.IN_PROGRESS.value
        sched.attempts_count = sched.attempts_count + 1
        session.commit()
        post_id = sched.post_id
        platforms = list(sched.platforms_json or [])

    # 2) Load post + assets
    with SessionLocal() as session:
        post = session.get(Post, post_id)
        if post is None:
            logger.error(f"schedule {sched_id}: post {post_id} not found")
            _mark_schedule_done(sched_id)
            return
        video_asset = (
            session.query(MediaAsset)
            .filter(MediaAsset.post_id == post_id, MediaAsset.kind == "video")
            .first()
        )
        thumb_asset = (
            session.query(MediaAsset)
            .filter(MediaAsset.post_id == post_id, MediaAsset.kind == "thumbnail")
            .first()
        )
        caption = post.caption
        hashtags = list(post.hashtags or [])
        is_short = post.video_format == "vertical_9_16"
        if video_asset is None:
            logger.error(f"schedule {sched_id}: post {post_id} has no video asset")
            _mark_schedule_done(sched_id)
            return
        video_path = Path(video_asset.path_or_url)
        thumb_path = Path(thumb_asset.path_or_url) if thumb_asset else None

    any_success = False
    for platform in platforms:
        try:
            poster = _build_poster(tenant_id, platform)
            if poster is None:
                continue
            result = poster.post_video(
                video_path=video_path,
                caption=caption,
                hashtags=hashtags,
                thumbnail_path=thumb_path,
                is_short=is_short,
            )
            with SessionLocal() as session:
                session.add(
                    PostingAttempt(
                        tenant_id=tenant_id,
                        schedule_id=sched_id,
                        post_id=post_id,
                        platform=platform,
                        attempted_at=datetime.now(timezone.utc),
                        status=(
                            AttemptStatus.SUCCESS.value
                            if result.success
                            else AttemptStatus.FAILED.value
                        ),
                        external_post_id=result.external_post_id,
                        response_log=result.raw_response or {},
                        error=result.error or "",
                    )
                )
                session.commit()
            if result.success:
                any_success = True
        except Exception as e:
            logger.error(f"schedule {sched_id} platform {platform} threw: {e}")
            with SessionLocal() as session:
                session.add(
                    PostingAttempt(
                        tenant_id=tenant_id,
                        schedule_id=sched_id,
                        post_id=post_id,
                        platform=platform,
                        attempted_at=datetime.now(timezone.utc),
                        status=AttemptStatus.FAILED.value,
                        error=str(e),
                        response_log={},
                    )
                )
                session.commit()

    # 4) Update post + schedule status
    with SessionLocal() as session:
        p = session.get(Post, post_id)
        if p is not None and any_success:
            p.status = PostStatus.POSTED.value
        s = session.get(Schedule, sched_id)
        if s is not None:
            s.status = ScheduleStatus.DONE.value
        session.commit()


def _mark_schedule_done(sched_id: int) -> None:
    SessionLocal = get_session_factory()
    with SessionLocal() as session:
        s = session.get(Schedule, sched_id)
        if s is not None:
            s.status = ScheduleStatus.DONE.value
            session.commit()


def _build_poster(tenant_id: int, platform: str):
    """Return a SocialPoster for this platform using the tenant's stored OAuth token."""
    SessionLocal = get_session_factory()
    with SessionLocal() as session:
        acct = (
            session.query(SocialAccount)
            .filter(
                SocialAccount.platform == platform,
                SocialAccount.status == "active",
            )
            .order_by(SocialAccount.last_used_at.desc().nulls_last())
            .first()
        )
        if acct is None:
            logger.warning(f"tenant {tenant_id} has no active {platform} account; skipping")
            return None
        token_data = decrypt_blob(acct.encrypted_oauth_blob)

    if platform == "facebook":
        return get_provider("social", "facebook",
                            page_token=token_data.get("page_token", token_data.get("access_token", "")),
                            page_id=token_data["page_id"])
    if platform == "youtube":
        return get_provider("social", "youtube",
                            client_id=token_data["client_id"],
                            client_secret=token_data["client_secret"],
                            refresh_token=token_data["refresh_token"])
    if platform == "tiktok":
        return get_provider("social", "tiktok",
                            access_token=token_data["access_token"])
    if platform == "linkedin":
        return get_provider("social", "linkedin",
                            access_token=token_data["access_token"],
                            author_urn=token_data["author_urn"])
    if platform == "instagram":
        # Instagram needs a media uploader (R2/S3 etc.). Worker skips IG until Phase 4 wires it.
        logger.warning(f"Instagram posting skipped — media uploader not configured")
        return None
    logger.warning(f"unknown platform {platform!r}")
    return None
