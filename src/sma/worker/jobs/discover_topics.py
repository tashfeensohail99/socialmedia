"""Worker job: run all enabled topic sources for every tenant on a schedule.

Iterates `topic_sources` rows where enabled=True; for each one, invokes the
configured source (AI / RSS / manual / news), scores results via LLM, inserts
new Topic rows skipping duplicates.

Runs as a single in-process APScheduler job. Each tenant's work is wrapped in
its own `tenant_scope(tenant_id)` block so the auto-tenant-filter applies.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from loguru import logger
from sqlalchemy import select

from sma.core.pipeline.factory_db import build_context_for_niche
from sma.core.topics.scorer import score_and_filter
from sma.core.topics.sources.ai_generated import AIGeneratedTopicSource
from sma.core.topics.sources.manual import ManualTopicSource
from sma.core.topics.sources.news import NewsTopicSource
from sma.core.topics.sources.rss import RSSTopicSource
from sma.db.models.topic import Topic as TopicRow, TopicSource, TopicStatus
from sma.db.session import get_session_factory, tenant_scope


def _source_for(kind: str, config: dict, default_language: str):
    if kind == "ai_generated":
        return AIGeneratedTopicSource(count=int(config.get("count", 8)))
    if kind == "manual":
        return ManualTopicSource(topics=config.get("topics", []))
    if kind == "rss":
        return RSSTopicSource(
            feed_urls=list(config.get("feed_urls", [])),
            items_per_feed=int(config.get("items_per_feed", 10)),
        )
    if kind == "news":
        api_key = config.get("api_key", "")
        if not api_key:
            raise ValueError("news topic source requires 'api_key' in config_json")
        return NewsTopicSource(
            api_key=api_key,
            max_results=int(config.get("max_results", 20)),
            language=config.get("language", default_language),
        )
    raise ValueError(f"unknown topic source kind {kind!r}")


def discover_topics_for_all_tenants() -> None:
    """Top-level entry point — APScheduler calls this on an interval."""
    SessionLocal = get_session_factory()
    # Pull every enabled source across all tenants (we'll re-scope per tenant below).
    with SessionLocal() as session:
        sources = session.execute(
            select(TopicSource).where(TopicSource.enabled.is_(True))
            .execution_options(skip_tenant_filter=True)
        ).scalars().all()
        tasks = [(s.tenant_id, s.id, s.niche_id, s.kind, dict(s.config_json or {})) for s in sources]

    logger.info(f"discover_topics: {len(tasks)} enabled sources across all tenants")

    for tenant_id, src_id, niche_id, kind, config in tasks:
        with tenant_scope(tenant_id):
            try:
                _run_one_source(src_id, niche_id, kind, config, tenant_id)
            except Exception as e:
                logger.error(f"tenant {tenant_id} source {src_id} ({kind}) failed: {e}")


def _run_one_source(src_id: int, niche_id: int, kind: str, config: dict, tenant_id: int) -> None:
    ctx, niche_row = build_context_for_niche(niche_id)
    # Use ctx.niche.language (a plain value) rather than niche_row.language — the
    # ORM row is detached once build_context_for_niche's session closed, so
    # touching its attributes raises DetachedInstanceError.
    source_obj = _source_for(kind, config, ctx.niche.language)
    candidates = source_obj.discover(ctx.niche, ctx.llm)
    if not candidates:
        logger.info(f"source {src_id} returned no candidates")
        return
    scored = score_and_filter(candidates, ctx.niche, ctx.llm)

    inserted = 0
    SessionLocal = get_session_factory()
    with SessionLocal() as session:
        # Pre-load existing hashes for this tenant to dedup.
        existing_hashes = {
            row[0]
            for row in session.execute(
                select(TopicRow.content_hash).where(TopicRow.tenant_id == tenant_id)
                .execution_options(skip_tenant_filter=True)
            ).all()
        }
        for t in scored:
            chash = hashlib.sha256(f"{t.title}\n{t.content}".encode()).hexdigest()[:32]
            if chash in existing_hashes:
                continue
            session.add(
                TopicRow(
                    tenant_id=tenant_id,
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
        # Stamp last_run_at
        src = session.get(TopicSource, src_id)
        if src is not None:
            src.last_run_at = datetime.now(timezone.utc)
        session.commit()
    logger.info(f"source {src_id}: kept {len(scored)} above threshold, inserted {inserted} new topics")
