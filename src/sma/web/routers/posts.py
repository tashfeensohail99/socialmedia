"""Posts router — list/get/delete only.

Posts are CREATED by the pipeline (action endpoint elsewhere). This router
is the read-side: lets users browse what's been generated, inspect details,
and delete failed/unwanted posts.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from sma.db.models.post import Post
from sma.db.session import get_db_session
from sma.web.auth.dependencies import CurrentUser
from sma.web.schemas.common import Page, PageMeta
from sma.web.schemas.post import PostRead

router = APIRouter(prefix="/api/posts", tags=["posts"])


@router.get("", response_model=Page[PostRead])
def list_posts(
    user: CurrentUser,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    status_filter: str | None = Query(None, alias="status"),
    niche_id: int | None = Query(None),
    video_format: str | None = Query(None),
) -> Page[PostRead]:
    with get_db_session() as session:
        stmt = select(Post)
        if status_filter:
            stmt = stmt.where(Post.status == status_filter)
        if niche_id is not None:
            stmt = stmt.where(Post.niche_id == niche_id)
        if video_format:
            stmt = stmt.where(Post.video_format == video_format)
        total = session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        rows = session.scalars(
            stmt.order_by(Post.id.desc()).limit(limit).offset(offset)
        ).all()
        return Page[PostRead](
            items=[PostRead.model_validate(r) for r in rows],
            meta=PageMeta(total=total, limit=limit, offset=offset),
        )


@router.get("/{post_id}", response_model=PostRead)
def get_post(post_id: int, user: CurrentUser) -> PostRead:
    with get_db_session() as session:
        row = session.get(Post, post_id)
        if row is None or row.tenant_id != user.tenant_id:
            raise HTTPException(status_code=404, detail="post not found")
        return PostRead.model_validate(row)


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_post(post_id: int, user: CurrentUser) -> None:
    """Delete a post + its media assets + any schedules. Cascade is configured on the FKs."""
    with get_db_session() as session:
        row = session.get(Post, post_id)
        if row is None or row.tenant_id != user.tenant_id:
            raise HTTPException(status_code=404, detail="post not found")
        session.delete(row)
