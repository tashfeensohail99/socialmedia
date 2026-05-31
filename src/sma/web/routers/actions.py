"""Action endpoints — kick off pipeline runs and post-now operations.

Sync execution for v1 (the request blocks until the pipeline finishes).
A future enhancement is to enqueue the work and return immediately, polling via
GET /api/posts/:id; but for Mode A's single-tenant single-operator model the
sync UX is fine and far simpler to operate.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from sma.core.pipeline.db_runner import PipelineRunError, run_pipeline_for_db
from sma.db.crypto import decrypt_blob
from sma.db.models.post import Post, PostStatus
from sma.db.models.schedule import (
    AttemptStatus,
    PostingAttempt,
    Schedule,
    ScheduleStatus,
)
from sma.db.models.social_account import SocialAccount
from sma.db.session import get_db_session
from sma.providers.registry import get_provider, platforms_for_format
from sma.web.auth.dependencies import CurrentUser
from sma.web.schemas.common import MessageResponse
from sma.web.schemas.post import PostRead

router = APIRouter(prefix="/api", tags=["actions"])

# Where the engine writes media files.
_OUTPUT_ROOT = Path("data/posts_db")


# ─── Run pipeline ─────────────────────────────────────────────────────


class RunPipelineRequest(BaseModel):
    niche_id: int
    topic_id: int | None = None
    manual_topic_title: str | None = None
    manual_topic_content: str = ""
    video_length: str | None = Field(None, description="short | long; overrides niche default")


@router.post(
    "/posts/run",
    response_model=PostRead,
    status_code=status.HTTP_201_CREATED,
    summary="Run the pipeline end-to-end for a niche + topic, returns the created Post.",
)
def run_pipeline_action(payload: RunPipelineRequest, user: CurrentUser) -> PostRead:
    try:
        post = run_pipeline_for_db(
            niche_id=payload.niche_id,
            topic_id=payload.topic_id,
            output_root=_OUTPUT_ROOT,
            video_length=payload.video_length,
            manual_topic_title=payload.manual_topic_title,
            manual_topic_content=payload.manual_topic_content,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except PipelineRunError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    # Re-read from a fresh session so the response includes all updated fields.
    with get_db_session() as session:
        fresh = session.get(Post, post.id)
        if fresh is None or fresh.tenant_id != user.tenant_id:
            raise HTTPException(status_code=500, detail="post vanished after creation")
        return PostRead.model_validate(fresh)


# ─── Regenerate ───────────────────────────────────────────────────────


@router.post(
    "/posts/{post_id}/regenerate",
    response_model=PostRead,
    summary="Re-run the pipeline for an existing post (uses the same topic/niche).",
)
def regenerate_post(post_id: int, user: CurrentUser) -> PostRead:
    with get_db_session() as session:
        existing = session.get(Post, post_id)
        if existing is None or existing.tenant_id != user.tenant_id:
            raise HTTPException(status_code=404, detail="post not found")
        niche_id = existing.niche_id
        topic_id = existing.topic_id
        length = existing.video_length

    try:
        post = run_pipeline_for_db(
            niche_id=niche_id,
            topic_id=topic_id,
            output_root=_OUTPUT_ROOT,
            video_length=length,
            manual_topic_title=("re-run" if topic_id is None else None),
        )
    except PipelineRunError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    with get_db_session() as session:
        fresh = session.get(Post, post.id)
        if fresh is None or fresh.tenant_id != user.tenant_id:
            raise HTTPException(status_code=500, detail="post vanished")
        return PostRead.model_validate(fresh)


# ─── Post now ─────────────────────────────────────────────────────────


class PostNowRequest(BaseModel):
    platforms: list[str] = Field(
        ..., min_length=1,
        description="Subset of {instagram, facebook, youtube, tiktok, linkedin}",
    )


class PostNowResult(BaseModel):
    platform: str
    success: bool
    external_post_id: str | None = None
    url: str | None = None
    error: str | None = None


class PostNowResponse(BaseModel):
    post_id: int
    attempts: list[PostNowResult]


@router.post(
    "/posts/{post_id}/post-now",
    response_model=PostNowResponse,
    summary="Post immediately to the named platforms, bypassing the schedule.",
)
def post_now(post_id: int, payload: PostNowRequest, user: CurrentUser) -> PostNowResponse:
    with get_db_session() as session:
        post = session.get(Post, post_id)
        if post is None or post.tenant_id != user.tenant_id:
            raise HTTPException(status_code=404, detail="post not found")
        if post.status != PostStatus.READY.value:
            raise HTTPException(
                status_code=409,
                detail=f"post status is {post.status!r} — must be 'ready' to post",
            )

        # Validate platform compatibility with the post's video format
        valid = platforms_for_format(post.video_length)
        invalid = [p for p in payload.platforms if p not in valid]
        if invalid:
            raise HTTPException(
                status_code=400,
                detail=f"platforms {invalid} not valid for {post.video_length} video (allowed: {sorted(valid)})",
            )

        # Resolve the post's media files
        from sma.db.models.post import MediaAsset

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
        if video_asset is None:
            raise HTTPException(status_code=500, detail="no video asset on this post")
        video_path = Path(video_asset.path_or_url)
        thumb_path = Path(thumb_asset.path_or_url) if thumb_asset else None
        caption = post.caption
        hashtags = list(post.hashtags or [])
        is_short = post.video_format == "vertical_9_16"
        tenant_id = post.tenant_id

    # Build posters per platform from stored SocialAccount tokens.
    attempts: list[PostNowResult] = []
    for platform in payload.platforms:
        try:
            poster = _build_poster_for_platform(platform)
            result = poster.post_video(
                video_path=video_path,
                caption=caption,
                hashtags=hashtags,
                thumbnail_path=thumb_path,
                is_short=is_short,
            )
            attempts.append(
                PostNowResult(
                    platform=platform,
                    success=result.success,
                    external_post_id=result.external_post_id,
                    url=result.url,
                    error=result.error,
                )
            )
            # Persist the attempt + flip post status if any platform succeeded.
            with get_db_session() as session:
                session.add(
                    PostingAttempt(
                        tenant_id=tenant_id,
                        schedule_id=None,  # post-now has no schedule
                        post_id=post_id,
                        platform=platform,
                        attempted_at=datetime.now(timezone.utc),
                        status=(
                            AttemptStatus.SUCCESS.value if result.success
                            else AttemptStatus.FAILED.value
                        ),
                        external_post_id=result.external_post_id,
                        response_log=result.raw_response or {},
                        error=result.error or "",
                    )
                )
                if result.success:
                    p = session.get(Post, post_id)
                    if p is not None:
                        p.status = PostStatus.POSTED.value
        except HTTPException:
            raise
        except Exception as e:
            attempts.append(
                PostNowResult(platform=platform, success=False, error=str(e))
            )

    return PostNowResponse(post_id=post_id, attempts=attempts)


def _build_poster_for_platform(platform: str):
    """Construct a SocialPoster for the platform using the active tenant's stored OAuth token."""
    with get_db_session() as session:
        acct = (
            session.query(SocialAccount)
            .filter(
                SocialAccount.platform == platform, SocialAccount.status == "active"
            )
            .order_by(SocialAccount.last_used_at.desc().nulls_last())
            .first()
        )
        if acct is None:
            raise HTTPException(
                status_code=412,
                detail=f"no connected {platform} account — connect one via /api/oauth/{platform}/connect",
            )
        token_data = decrypt_blob(acct.encrypted_oauth_blob)

    if platform == "instagram":
        # Instagram needs a MediaUploader (public URL provider). For Phase 2 we
        # bail out cleanly with a 501 — Phase 4 will wire R2/S3 uploaders.
        raise HTTPException(
            status_code=501,
            detail=(
                "Instagram posting requires a configured media uploader (R2/S3). "
                "Configure one before using post-now for IG."
            ),
        )
    if platform == "facebook":
        return get_provider(
            "social", "facebook",
            page_token=token_data.get("page_token", token_data.get("access_token", "")),
            page_id=token_data["page_id"],
        )
    if platform == "youtube":
        return get_provider(
            "social", "youtube",
            client_id=token_data["client_id"],
            client_secret=token_data["client_secret"],
            refresh_token=token_data["refresh_token"],
        )
    if platform == "tiktok":
        return get_provider(
            "social", "tiktok",
            access_token=token_data["access_token"],
        )
    if platform == "linkedin":
        return get_provider(
            "social", "linkedin",
            access_token=token_data["access_token"],
            author_urn=token_data["author_urn"],
        )
    raise HTTPException(status_code=400, detail=f"unknown platform {platform!r}")


# ─── Topic source discovery trigger ──────────────────────────────────


@router.post(
    "/topic-sources/{src_id}/run-now",
    response_model=MessageResponse,
    summary="Manually trigger a topic source to discover topics now.",
)
def run_topic_source_now(src_id: int, user: CurrentUser) -> MessageResponse:
    """Synchronous discovery for a single source. Inserts new Topic rows.

    Skips topics whose content_hash already exists for this tenant (dedup).
    """
    from sqlalchemy import select as _select

    import hashlib

    from sma.core.niche.config import NicheConfig
    from sma.core.pipeline.factory_db import build_context_for_niche
    from sma.core.topics.scorer import score_and_filter
    from sma.core.topics.sources.ai_generated import AIGeneratedTopicSource
    from sma.core.topics.sources.manual import ManualTopicSource
    from sma.core.topics.sources.news import NewsTopicSource
    from sma.core.topics.sources.rss import RSSTopicSource
    from sma.db.models.topic import Topic as TopicRow, TopicSource, TopicStatus

    with get_db_session() as session:
        src = session.get(TopicSource, src_id)
        if src is None or src.tenant_id != user.tenant_id:
            raise HTTPException(status_code=404, detail="topic source not found")
        niche_id = src.niche_id
        kind = src.kind
        config = dict(src.config_json or {})

    # Build a context so we have the LLM for AI-generation / scoring.
    ctx, niche_row = build_context_for_niche(niche_id)

    # Instantiate the matching source.
    if kind == "ai_generated":
        source_obj = AIGeneratedTopicSource(count=int(config.get("count", 8)))
    elif kind == "manual":
        source_obj = ManualTopicSource(topics=config.get("topics", []))
    elif kind == "rss":
        source_obj = RSSTopicSource(
            feed_urls=list(config.get("feed_urls", [])),
            items_per_feed=int(config.get("items_per_feed", 10)),
        )
    elif kind == "news":
        api_key = config.get("api_key", "")
        if not api_key:
            raise HTTPException(
                status_code=400, detail="news topic source requires 'api_key' in config_json"
            )
        source_obj = NewsTopicSource(
            api_key=api_key,
            max_results=int(config.get("max_results", 20)),
            language=config.get("language", ctx.niche.language),
        )
    else:
        raise HTTPException(status_code=400, detail=f"unknown topic source kind {kind!r}")

    candidates = source_obj.discover(ctx.niche, ctx.llm)
    scored = score_and_filter(candidates, ctx.niche, ctx.llm)

    # Persist new topics, skipping duplicates.
    inserted = 0
    with get_db_session() as session:
        existing_hashes = {
            row[0]
            for row in session.execute(
                _select(TopicRow.content_hash)
            ).all()
        }
        for t in scored:
            chash = hashlib.sha256(f"{t.title}\n{t.content}".encode()).hexdigest()[:32]
            if chash in existing_hashes:
                continue
            session.add(
                TopicRow(
                    tenant_id=user.tenant_id,
                    source_id=src_id,
                    content_hash=chash,
                    title=t.title,
                    content=t.content,
                    metadata_json=dict(t.metadata or {}),
                    score=t.score,
                    score_reason=t.score_reason,
                    suggested_angle=t.suggested_angle,
                    status=TopicStatus.SCORED.value,
                )
            )
            inserted += 1

        # Update last_run_at.
        src = session.get(TopicSource, src_id)
        if src is not None:
            src.last_run_at = datetime.now(timezone.utc)

    return MessageResponse(
        message=f"discovered {len(candidates)} candidates, kept {len(scored)} above threshold, inserted {inserted} new topics"
    )


# ─── Mark schedule done ──────────────────────────────────────────────


@router.post(
    "/automation/run-now",
    response_model=MessageResponse,
    summary="Run the full autonomous cycle once now: discover topics → generate videos → schedule.",
)
def run_automation_now(user: CurrentUser) -> MessageResponse:
    """Kick the whole pipeline synchronously for THIS tenant.

    Useful for first-time setup and testing instead of waiting for the worker's
    timed cycle. Steps:
      1. Run every enabled topic source (discover + score new Topics).
      2. Auto-generate videos from the best unused topics, up to the daily limit.
      3. Auto-schedule each generated post to connected platforms.
    """
    from sma.db.models.tenant import Tenant
    from sma.db.models.topic import TopicSource as TopicSourceModel
    from sma.db.session import tenant_scope
    from sma.worker.jobs.auto_generate import _auto_generate_for_tenant
    from sma.worker.jobs.discover_topics import _run_one_source

    tenant_id = user.tenant_id

    # The worker helpers below read the tenant ContextVar (via require_current_tenant).
    # This sync endpoint may run on a threadpool worker where the dependency-set
    # ContextVar doesn't propagate, so wrap the whole cycle in an explicit
    # tenant_scope to guarantee the context is set on THIS thread.
    with tenant_scope(tenant_id):
        # Step 1: discovery for every enabled source in this tenant.
        discovered_sources = 0
        with get_db_session() as session:
            srcs = (
                session.query(TopicSourceModel)
                .filter(TopicSourceModel.enabled.is_(True))
                .all()
            )
            src_plan = [(s.id, s.niche_id, s.kind, dict(s.config_json or {})) for s in srcs]

        for src_id, niche_id, kind, config in src_plan:
            try:
                _run_one_source(src_id, niche_id, kind, config, tenant_id)
                discovered_sources += 1
            except Exception as e:
                raise HTTPException(
                    status_code=500, detail=f"topic discovery failed for source {src_id}: {e}"
                ) from e

        # Step 2 + 3: generate + schedule, honoring the tenant's daily limits.
        with get_db_session() as session:
            tenant = session.get(Tenant, tenant_id)
            daily_short = tenant.daily_short_videos if tenant else 1
            daily_long = tenant.daily_long_videos if tenant else 0

        try:
            _auto_generate_for_tenant(tenant_id, daily_short, daily_long)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"auto-generate failed: {e}") from e

    return MessageResponse(
        message=(
            f"Automation cycle complete: ran {discovered_sources} topic source(s), "
            f"then generated + scheduled up to {daily_short} short / {daily_long} long video(s). "
            f"Check the Posts page."
        )
    )


@router.post(
    "/schedules/{sched_id}/mark-done",
    response_model=MessageResponse,
    summary="Manually mark a schedule as DONE (operator override).",
)
def mark_schedule_done(sched_id: int, user: CurrentUser) -> MessageResponse:
    with get_db_session() as session:
        row = session.get(Schedule, sched_id)
        if row is None or row.tenant_id != user.tenant_id:
            raise HTTPException(status_code=404, detail="schedule not found")
        row.status = ScheduleStatus.DONE.value
    return MessageResponse(message=f"schedule {sched_id} marked done")
