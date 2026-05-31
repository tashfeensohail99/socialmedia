"""PostingRules CRUD — peak hours / quiet hours / spacing / platform priority."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from sma.db.models.posting_rule import PostingRule
from sma.db.session import get_db_session
from sma.web.auth.dependencies import CurrentUser
from sma.web.schemas.common import Page, PageMeta
from sma.web.schemas.rules_and_templates import (
    PostingRuleCreate,
    PostingRuleRead,
    PostingRuleUpdate,
)

router = APIRouter(prefix="/api/posting-rules", tags=["posting-rules"])

_VALID_TYPES = {"peak_hours", "spacing", "platform_priority", "quiet_hours"}


@router.get("", response_model=Page[PostingRuleRead])
def list_rules(
    user: CurrentUser,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> Page[PostingRuleRead]:
    with get_db_session() as session:
        total = session.scalar(select(func.count(PostingRule.id))) or 0
        rows = session.scalars(
            select(PostingRule).order_by(PostingRule.id.desc()).limit(limit).offset(offset)
        ).all()
        return Page[PostingRuleRead](
            items=[PostingRuleRead.model_validate(r) for r in rows],
            meta=PageMeta(total=total, limit=limit, offset=offset),
        )


@router.post("", response_model=PostingRuleRead, status_code=status.HTTP_201_CREATED)
def create_rule(payload: PostingRuleCreate, user: CurrentUser) -> PostingRuleRead:
    if payload.type not in _VALID_TYPES:
        raise HTTPException(
            status_code=400, detail=f"type must be one of {sorted(_VALID_TYPES)}"
        )
    with get_db_session() as session:
        row = PostingRule(tenant_id=user.tenant_id, **payload.model_dump())
        session.add(row)
        session.flush()
        session.refresh(row)
        return PostingRuleRead.model_validate(row)


@router.patch("/{rule_id}", response_model=PostingRuleRead)
def update_rule(
    rule_id: int, payload: PostingRuleUpdate, user: CurrentUser
) -> PostingRuleRead:
    if payload.type is not None and payload.type not in _VALID_TYPES:
        raise HTTPException(
            status_code=400, detail=f"type must be one of {sorted(_VALID_TYPES)}"
        )
    with get_db_session() as session:
        row = session.get(PostingRule, rule_id)
        if row is None or row.tenant_id != user.tenant_id:
            raise HTTPException(status_code=404, detail="posting rule not found")
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(row, field, value)
        session.flush()
        session.refresh(row)
        return PostingRuleRead.model_validate(row)


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rule(rule_id: int, user: CurrentUser) -> None:
    with get_db_session() as session:
        row = session.get(PostingRule, rule_id)
        if row is None or row.tenant_id != user.tenant_id:
            raise HTTPException(status_code=404, detail="posting rule not found")
        session.delete(row)
