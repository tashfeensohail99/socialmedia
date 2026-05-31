"""Subscription gate — blocks protected API routes when the current tenant's
subscription is cancelled / expired / past_due.

In Mode A (single_tenant) this is a no-op: tenants have status='none' which is
always allowed.

In Mode B (multi_tenant):
  - `none`        → no subscription, blocked (shouldn't happen for real tenants)
  - `trialing`    → allowed
  - `active`      → allowed
  - `past_due`    → blocked, frontend shows "update your payment" splash
  - `cancelled`   → blocked, frontend shows "resubscribe" splash

The gate is bypassed for a small set of routes a cancelled user still needs:
auth, billing, /api/me (so the splash UI can render the user's email).
"""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select

from sma.config import DeploymentMode, get_settings
from sma.db.models.tenant import ACTIVE_STATUSES, Tenant
from sma.db.session import get_session_factory
from sma.web.auth.dependencies import CurrentUser


def require_active_subscription(user: CurrentUser) -> CurrentUser:
    """FastAPI dependency. Blocks the request if subscription is not active.

    Use as a router-level dependency on every "real product" route — the
    subscription state is checked in DB on every request (sub-millisecond).

    Routes that should remain accessible even when cancelled (so the user can
    re-subscribe) don't use this dependency.
    """
    settings = get_settings()
    if settings.deployment_mode != DeploymentMode.MULTI_TENANT:
        # Mode A — always allowed.
        return user

    SessionLocal = get_session_factory()
    with SessionLocal() as session:
        tenant = session.execute(
            select(Tenant)
            .where(Tenant.id == user.tenant_id)
            .execution_options(skip_tenant_filter=True)
        ).scalar_one_or_none()

    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="tenant not found",
        )
    if tenant.subscription_status not in ACTIVE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"subscription_inactive:{tenant.subscription_status}",
        )
    return user
