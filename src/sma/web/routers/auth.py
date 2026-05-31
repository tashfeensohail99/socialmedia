"""Auth routes: login + (Mode B) signup."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select

from sma.config import DeploymentMode, get_settings
from sma.db.models.tenant import SubscriptionStatus, Tenant
from sma.db.models.user import User, UserRole
from sma.db.session import get_db_session, get_session_factory
from sma.web.auth.jwt import InvalidToken, issue_token
from sma.web.auth.magic import decode_magic_link_token
from sma.web.auth.passwords import hash_password, verify_password

# Length of the self-serve free trial granted at signup (before any payment).
SELF_SERVE_TRIAL_DAYS = 7

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    tenant_id: int
    role: str


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest) -> TokenResponse:
    """Verify password, issue JWT."""
    email = payload.email.strip().lower()
    SessionLocal = get_session_factory()
    with SessionLocal() as session:
        user = session.execute(
            select(User).where(User.email == email).execution_options(skip_tenant_filter=True)
        ).scalar_one_or_none()
        if user is None or not verify_password(payload.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="invalid email or password",
            )
        token = issue_token(user_id=user.id, tenant_id=user.tenant_id, role=user.role)
        return TokenResponse(
            access_token=token,
            user_id=user.id,
            tenant_id=user.tenant_id,
            role=user.role,
        )


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    workspace_name: str = Field(default="", max_length=128)


class MagicLoginRequest(BaseModel):
    token: str


@router.post("/magic-login", response_model=TokenResponse)
def magic_login(payload: MagicLoginRequest) -> TokenResponse:
    """Exchange a magic-link JWT (from email) for a long-lived session JWT.

    This is how SaaS buyers sign in for the first time after subscribing
    on Whop. They click the link in the welcome email which carries them
    to /auth/magic on the frontend; the frontend POSTs the token here.
    """
    try:
        user_id, tenant_id = decode_magic_link_token(payload.token)
    except InvalidToken as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    SessionLocal = get_session_factory()
    with SessionLocal() as session:
        user = session.execute(
            select(User).where(User.id == user_id).execution_options(skip_tenant_filter=True)
        ).scalar_one_or_none()
        if user is None or user.tenant_id != tenant_id:
            raise HTTPException(status_code=400, detail="magic link no longer valid")
        token = issue_token(user_id=user.id, tenant_id=user.tenant_id, role=user.role)
        return TokenResponse(
            access_token=token,
            user_id=user.id,
            tenant_id=user.tenant_id,
            role=user.role,
        )


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def signup(payload: SignupRequest) -> TokenResponse:
    """Mode B only — create a new tenant + admin user, issue JWT immediately.

    In Mode A this endpoint is disabled by the app router setup.
    """
    settings = get_settings()
    if settings.deployment_mode != DeploymentMode.MULTI_TENANT:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="signup is disabled in single-tenant deploys",
        )
    email = payload.email.strip().lower()
    SessionLocal = get_session_factory()
    with SessionLocal() as session:
        existing = session.execute(
            select(User).where(User.email == email).execution_options(skip_tenant_filter=True)
        ).scalar_one_or_none()
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="email already in use",
            )
        tenant = Tenant(
            name=payload.workspace_name.strip() or f"{email.split('@')[0]}'s workspace",
            subscription_status=SubscriptionStatus.TRIALING.value,
            trial_ends_at=datetime.now(timezone.utc) + timedelta(days=SELF_SERVE_TRIAL_DAYS),
        )
        session.add(tenant)
        session.flush()  # populate tenant.id
        user = User(
            tenant_id=tenant.id,
            email=email,
            password_hash=hash_password(payload.password),
            role=UserRole.ADMIN.value,
            email_verified=False,
        )
        session.add(user)
        session.commit()
        token = issue_token(user_id=user.id, tenant_id=tenant.id, role=user.role)
        return TokenResponse(
            access_token=token, user_id=user.id, tenant_id=tenant.id, role=user.role
        )
