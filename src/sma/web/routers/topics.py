"""Topics: list/get, plus manual create + reject/promote actions."""

from __future__ import annotations

import hashlib

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from sma.db.models.topic import Topic, TopicStatus
from sma.db.session import get_db_session
from sma.web.auth.dependencies import CurrentUser
from sma.web.schemas.common import MessageResponse, Page, PageMeta
from sma.web.schemas.topic import TopicCreate, TopicRead

router = APIRouter(prefix="/api/topics", tags=["topics"])


@router.get("", response_model=Page[TopicRead])
def list_topics(
    user: CurrentUser,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    status_filter: str | None = Query(None, alias="status"),
    min_score: float | None = Query(None),
) -> Page[TopicRead]:
    with get_db_session() as session:
        stmt = select(Topic)
        if status_filter:
            stmt = stmt.where(Topic.status == status_filter)
        if min_score is not None:
            stmt = stmt.where(Topic.score >= min_score)
        total = session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        rows = session.scalars(
            stmt.order_by(Topic.score.desc().nulls_last(), Topic.id.desc())
            .limit(limit)
            .offset(offset)
        ).all()
        return Page[TopicRead](
            items=[TopicRead.model_validate(r) for r in rows],
            meta=PageMeta(total=total, limit=limit, offset=offset),
        )


@router.post("", response_model=TopicRead, status_code=status.HTTP_201_CREATED)
def create_topic(payload: TopicCreate, user: CurrentUser) -> TopicRead:
    """Add a topic manually (skips discovery)."""
    content_hash = hashlib.sha256(f"{payload.title}\n{payload.content}".encode()).hexdigest()[:32]
    with get_db_session() as session:
        row = Topic(
            tenant_id=user.tenant_id,
            source_id=None,
            content_hash=content_hash,
            title=payload.title,
            content=payload.content,
            metadata_json=payload.metadata_json,
            status=TopicStatus.DISCOVERED.value,
        )
        session.add(row)
        session.flush()
        session.refresh(row)
        return TopicRead.model_validate(row)


@router.get("/{topic_id}", response_model=TopicRead)
def get_topic(topic_id: int, user: CurrentUser) -> TopicRead:
    with get_db_session() as session:
        row = session.get(Topic, topic_id)
        if row is None or row.tenant_id != user.tenant_id:
            raise HTTPException(status_code=404, detail="topic not found")
        return TopicRead.model_validate(row)


@router.post("/{topic_id}/reject", response_model=MessageResponse)
def reject_topic(topic_id: int, user: CurrentUser) -> MessageResponse:
    """Mark a topic as REJECTED so the worker won't pick it up."""
    with get_db_session() as session:
        row = session.get(Topic, topic_id)
        if row is None or row.tenant_id != user.tenant_id:
            raise HTTPException(status_code=404, detail="topic not found")
        row.status = TopicStatus.REJECTED.value
        return MessageResponse(message=f"topic {topic_id} rejected")


@router.post("/{topic_id}/promote", response_model=MessageResponse)
def promote_topic(topic_id: int, user: CurrentUser) -> MessageResponse:
    """Force a topic into SCORED status with a 10.0 score so it's first in line."""
    with get_db_session() as session:
        row = session.get(Topic, topic_id)
        if row is None or row.tenant_id != user.tenant_id:
            raise HTTPException(status_code=404, detail="topic not found")
        row.status = TopicStatus.SCORED.value
        row.score = 10.0
        return MessageResponse(message=f"topic {topic_id} promoted")


@router.delete("/{topic_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_topic(topic_id: int, user: CurrentUser) -> None:
    with get_db_session() as session:
        row = session.get(Topic, topic_id)
        if row is None or row.tenant_id != user.tenant_id:
            raise HTTPException(status_code=404, detail="topic not found")
        session.delete(row)
