"""TopicSource CRUD — one tenant can have many sources per niche."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from sma.db.models.niche import Niche
from sma.db.models.topic import TopicSource
from sma.db.session import get_db_session
from sma.web.auth.dependencies import CurrentUser
from sma.web.schemas.common import Page, PageMeta
from sma.web.schemas.topic import TopicSourceCreate, TopicSourceRead, TopicSourceUpdate

router = APIRouter(prefix="/api/topic-sources", tags=["topic-sources"])


@router.get("", response_model=Page[TopicSourceRead])
def list_sources(
    user: CurrentUser,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    niche_id: int | None = Query(None),
) -> Page[TopicSourceRead]:
    with get_db_session() as session:
        stmt = select(TopicSource)
        if niche_id is not None:
            stmt = stmt.where(TopicSource.niche_id == niche_id)
        total = session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        rows = session.scalars(
            stmt.order_by(TopicSource.id.desc()).limit(limit).offset(offset)
        ).all()
        return Page[TopicSourceRead](
            items=[TopicSourceRead.model_validate(r) for r in rows],
            meta=PageMeta(total=total, limit=limit, offset=offset),
        )


@router.post("", response_model=TopicSourceRead, status_code=status.HTTP_201_CREATED)
def create_source(payload: TopicSourceCreate, user: CurrentUser) -> TopicSourceRead:
    with get_db_session() as session:
        # Verify the niche belongs to this tenant.
        niche = session.get(Niche, payload.niche_id)
        if niche is None or niche.tenant_id != user.tenant_id:
            raise HTTPException(status_code=404, detail="niche not found")
        row = TopicSource(
            tenant_id=user.tenant_id,
            niche_id=payload.niche_id,
            kind=payload.kind,
            config_json=payload.config_json,
            enabled=payload.enabled,
        )
        session.add(row)
        session.flush()
        session.refresh(row)
        return TopicSourceRead.model_validate(row)


@router.patch("/{src_id}", response_model=TopicSourceRead)
def update_source(
    src_id: int, payload: TopicSourceUpdate, user: CurrentUser
) -> TopicSourceRead:
    with get_db_session() as session:
        row = session.get(TopicSource, src_id)
        if row is None or row.tenant_id != user.tenant_id:
            raise HTTPException(status_code=404, detail="topic source not found")
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(row, field, value)
        session.flush()
        session.refresh(row)
        return TopicSourceRead.model_validate(row)


@router.delete("/{src_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_source(src_id: int, user: CurrentUser) -> None:
    with get_db_session() as session:
        row = session.get(TopicSource, src_id)
        if row is None or row.tenant_id != user.tenant_id:
            raise HTTPException(status_code=404, detail="topic source not found")
        session.delete(row)
