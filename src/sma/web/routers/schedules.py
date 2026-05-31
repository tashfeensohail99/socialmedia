"""Schedules CRUD + cancel.

A Schedule says "post N should go to platforms [...] at time T". The worker
polls this table every minute and dispatches posting attempts.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from sma.db.models.post import Post
from sma.db.models.schedule import Schedule, ScheduleStatus
from sma.db.session import get_db_session
from sma.providers.registry import platforms_for_format
from sma.web.auth.dependencies import CurrentUser
from sma.web.schemas.common import MessageResponse, Page, PageMeta
from sma.web.schemas.post import ScheduleCreate, ScheduleRead, ScheduleUpdate

router = APIRouter(prefix="/api/schedules", tags=["schedules"])


@router.get("", response_model=Page[ScheduleRead])
def list_schedules(
    user: CurrentUser,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    status_filter: str | None = Query(None, alias="status"),
) -> Page[ScheduleRead]:
    with get_db_session() as session:
        stmt = select(Schedule)
        if status_filter:
            stmt = stmt.where(Schedule.status == status_filter)
        total = session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        rows = session.scalars(
            stmt.order_by(Schedule.scheduled_for_utc.asc()).limit(limit).offset(offset)
        ).all()
        return Page[ScheduleRead](
            items=[ScheduleRead.model_validate(r) for r in rows],
            meta=PageMeta(total=total, limit=limit, offset=offset),
        )


@router.post("", response_model=ScheduleRead, status_code=status.HTTP_201_CREATED)
def create_schedule(payload: ScheduleCreate, user: CurrentUser) -> ScheduleRead:
    with get_db_session() as session:
        post = session.get(Post, payload.post_id)
        if post is None or post.tenant_id != user.tenant_id:
            raise HTTPException(status_code=404, detail="post not found")

        # Reject platforms that don't match the post's video format.
        valid_platforms = platforms_for_format(post.video_length)
        invalid = [p for p in payload.platforms if p not in valid_platforms]
        if invalid:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"platforms {invalid} are not valid for a {post.video_length} "
                    f"video (allowed: {sorted(valid_platforms)})"
                ),
            )

        row = Schedule(
            tenant_id=user.tenant_id,
            post_id=payload.post_id,
            scheduled_for_utc=payload.scheduled_for_utc,
            platforms_json=payload.platforms,
            status=ScheduleStatus.PENDING.value,
        )
        session.add(row)
        session.flush()
        session.refresh(row)
        return ScheduleRead.model_validate(row)


@router.patch("/{sched_id}", response_model=ScheduleRead)
def update_schedule(
    sched_id: int, payload: ScheduleUpdate, user: CurrentUser
) -> ScheduleRead:
    with get_db_session() as session:
        row = session.get(Schedule, sched_id)
        if row is None or row.tenant_id != user.tenant_id:
            raise HTTPException(status_code=404, detail="schedule not found")
        if payload.scheduled_for_utc is not None:
            row.scheduled_for_utc = payload.scheduled_for_utc
        if payload.platforms is not None:
            row.platforms_json = payload.platforms
        if payload.status is not None:
            row.status = payload.status
        session.flush()
        session.refresh(row)
        return ScheduleRead.model_validate(row)


@router.post("/{sched_id}/cancel", response_model=MessageResponse)
def cancel_schedule(sched_id: int, user: CurrentUser) -> MessageResponse:
    with get_db_session() as session:
        row = session.get(Schedule, sched_id)
        if row is None or row.tenant_id != user.tenant_id:
            raise HTTPException(status_code=404, detail="schedule not found")
        row.status = ScheduleStatus.CANCELLED.value
        return MessageResponse(message=f"schedule {sched_id} cancelled")


@router.delete("/{sched_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_schedule(sched_id: int, user: CurrentUser) -> None:
    with get_db_session() as session:
        row = session.get(Schedule, sched_id)
        if row is None or row.tenant_id != user.tenant_id:
            raise HTTPException(status_code=404, detail="schedule not found")
        session.delete(row)
