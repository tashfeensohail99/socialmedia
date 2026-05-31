"""PromptTemplates — per-tenant overrides of default templates.

Default templates live in `templates/*.j2` on disk. A tenant can override any
of them by inserting a row here with the same slug; the engine reads DB-backed
templates first (when present), falling back to disk defaults otherwise.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from sma.db.models.prompt_template import PromptTemplate
from sma.db.session import get_db_session
from sma.web.auth.dependencies import CurrentUser
from sma.web.schemas.common import MessageResponse, Page, PageMeta
from sma.web.schemas.rules_and_templates import PromptTemplateRead, PromptTemplateUpsert

router = APIRouter(prefix="/api/prompt-templates", tags=["prompt-templates"])

_TEMPLATES_ROOT = Path(__file__).resolve().parents[4] / "templates"


@router.get("", response_model=Page[PromptTemplateRead])
def list_templates(
    user: CurrentUser,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> Page[PromptTemplateRead]:
    with get_db_session() as session:
        total = session.scalar(select(func.count(PromptTemplate.id))) or 0
        rows = session.scalars(
            select(PromptTemplate).order_by(PromptTemplate.slug.asc()).limit(limit).offset(offset)
        ).all()
        return Page[PromptTemplateRead](
            items=[PromptTemplateRead.model_validate(r) for r in rows],
            meta=PageMeta(total=total, limit=limit, offset=offset),
        )


@router.get("/{slug}/default", response_model=MessageResponse)
def get_default_body(slug: str, user: CurrentUser) -> MessageResponse:
    """Return the on-disk default template body for `slug` (for the 'reset to default' button)."""
    safe = slug.replace("/", "_").replace("\\", "_")
    candidate = _TEMPLATES_ROOT / f"{safe}.j2"
    if not candidate.exists():
        raise HTTPException(status_code=404, detail=f"no default template named {slug!r}")
    return MessageResponse(message=candidate.read_text(encoding="utf-8"))


@router.put("/{slug}", response_model=PromptTemplateRead)
def upsert_template(
    slug: str, payload: PromptTemplateUpsert, user: CurrentUser
) -> PromptTemplateRead:
    """Insert or replace a tenant override at this slug."""
    if payload.slug != slug:
        raise HTTPException(status_code=400, detail="slug in path must match payload.slug")
    with get_db_session() as session:
        existing = session.execute(
            select(PromptTemplate).where(PromptTemplate.slug == slug)
        ).scalar_one_or_none()
        if existing is None:
            row = PromptTemplate(
                tenant_id=user.tenant_id,
                slug=slug,
                body=payload.body,
                is_default=False,
            )
            session.add(row)
        else:
            row = existing
            row.body = payload.body
        session.flush()
        session.refresh(row)
        return PromptTemplateRead.model_validate(row)


@router.delete("/{slug}", status_code=status.HTTP_204_NO_CONTENT)
def delete_template(slug: str, user: CurrentUser) -> None:
    """Remove the tenant override — engine falls back to the on-disk default."""
    with get_db_session() as session:
        row = session.execute(
            select(PromptTemplate).where(PromptTemplate.slug == slug)
        ).scalar_one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail=f"no override for slug {slug!r}")
        session.delete(row)
