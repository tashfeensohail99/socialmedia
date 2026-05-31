"""Current-user info — `/api/me`. Useful for the frontend to confirm a JWT works
and read user/tenant details for the navbar."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from sma.db.models.tenant import Tenant
from sma.db.models.user import User
from sma.db.session import get_db_session
from sma.web.auth.dependencies import CurrentUser
from sma.web.auth.passwords import hash_password, verify_password

router = APIRouter(prefix="/api/me", tags=["me"])


class MeResponse(BaseModel):
    user_id: int
    tenant_id: int
    email: str
    role: str
    tenant_name: str
    subscription_status: str
    daily_short_videos: int
    daily_long_videos: int


@router.get("", response_model=MeResponse)
def me(user: CurrentUser) -> MeResponse:
    with get_db_session() as session:
        u = session.execute(
            select(User).where(User.id == user.user_id)
            .execution_options(skip_tenant_filter=True)
        ).scalar_one_or_none()
        t = session.execute(
            select(Tenant).where(Tenant.id == user.tenant_id)
            .execution_options(skip_tenant_filter=True)
        ).scalar_one_or_none()
        if u is None or t is None:
            raise HTTPException(status_code=404, detail="user not found")
        return MeResponse(
            user_id=u.id,
            tenant_id=t.id,
            email=u.email,
            role=u.role,
            tenant_name=t.name,
            subscription_status=t.subscription_status,
            daily_short_videos=t.daily_short_videos,
            daily_long_videos=t.daily_long_videos,
        )


class ConfigUpdate(BaseModel):
    daily_short_videos: int = Field(..., ge=0, le=50)
    daily_long_videos: int = Field(..., ge=0, le=20)


@router.patch("/config", response_model=MeResponse)
def update_config(payload: ConfigUpdate, user: CurrentUser) -> MeResponse:
    """Update daily video generation limits for this tenant."""
    with get_db_session() as session:
        t = session.execute(
            select(Tenant).where(Tenant.id == user.tenant_id)
            .execution_options(skip_tenant_filter=True)
        ).scalar_one_or_none()
        if t is None:
            raise HTTPException(status_code=404, detail="tenant not found")
        t.daily_short_videos = payload.daily_short_videos
        t.daily_long_videos = payload.daily_long_videos

    # Re-read for the response.
    with get_db_session() as session:
        u = session.execute(
            select(User).where(User.id == user.user_id)
            .execution_options(skip_tenant_filter=True)
        ).scalar_one_or_none()
        t = session.execute(
            select(Tenant).where(Tenant.id == user.tenant_id)
            .execution_options(skip_tenant_filter=True)
        ).scalar_one_or_none()
        return MeResponse(
            user_id=u.id,
            tenant_id=t.id,
            email=u.email,
            role=u.role,
            tenant_name=t.name,
            subscription_status=t.subscription_status,
            daily_short_videos=t.daily_short_videos,
            daily_long_videos=t.daily_long_videos,
        )


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8)


class MessageResponse(BaseModel):
    message: str


@router.post("/change-password", response_model=MessageResponse)
def change_password(payload: ChangePasswordRequest, user: CurrentUser) -> MessageResponse:
    """Change the current user's password."""
    with get_db_session() as session:
        u = session.execute(
            select(User).where(User.id == user.user_id)
            .execution_options(skip_tenant_filter=True)
        ).scalar_one_or_none()
        if u is None:
            raise HTTPException(status_code=404, detail="user not found")
        if not verify_password(payload.current_password, u.password_hash):
            raise HTTPException(status_code=400, detail="current password is incorrect")
        u.password_hash = hash_password(payload.new_password)
    return MessageResponse(message="password updated")
