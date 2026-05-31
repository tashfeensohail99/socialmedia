"""Whop membership webhook handler.

Whop sends signed POSTs to /api/webhooks/whop when subscription state changes.
The most important events for SaaS lifecycle:

  - membership.went_valid     → user just paid / trial started → CREATE tenant + send magic link
  - membership.went_invalid   → mark PAST_DUE (Whop reports failed payments this way)
  - membership.cancelled      → mark CANCELLED (user clicked cancel)
  - membership.expired        → mark CANCELLED (subscription ran out)

Signature verification: Whop signs the raw body with HMAC-SHA256 using
WHOP_WEBHOOK_SECRET. The header is `Whop-Signature`. We validate before
parsing the JSON.

See: https://docs.whop.com/webhooks
"""

from __future__ import annotations

import hashlib
import hmac
import os
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request, status
from loguru import logger
from sqlalchemy import select

from sma.db.models.tenant import (
    SubscriptionStatus,
    Tenant,
    whop_status_to_subscription_status,
)
from sma.db.models.user import User, UserRole
from sma.db.session import get_session_factory
from sma.web.auth.magic import issue_magic_link_token
from sma.web.auth.passwords import hash_password
from sma.web.email.sender import send_email
from sma.web.email.templates import (
    magic_link_signup,
    subscription_cancelled,
)

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


def _frontend_base_url() -> str:
    return os.environ.get("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")


# ─── Signature verification ────────────────────────────────────


def _verify_signature(raw_body: bytes, signature_header: str | None) -> None:
    """Whop sends HMAC-SHA256 of the raw request body, hex-encoded."""
    secret = os.environ.get("WHOP_WEBHOOK_SECRET", "").strip()
    if not secret:
        # In dev you can leave this blank and we accept all requests. In prod this
        # MUST be set or the webhook is wide open.
        if os.environ.get("DEPLOYMENT_MODE", "").lower() == "multi_tenant":
            raise HTTPException(
                status_code=500,
                detail="WHOP_WEBHOOK_SECRET not configured — refusing to accept webhooks in production",
            )
        logger.warning("WHOP_WEBHOOK_SECRET not set; accepting webhook without signature verification")
        return
    if not signature_header:
        raise HTTPException(status_code=401, detail="missing Whop-Signature header")
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature_header.strip()):
        raise HTTPException(status_code=401, detail="invalid Whop signature")


# ─── Helpers ──────────────────────────────────────────────────


def _parse_expires_at(value) -> datetime | None:
    """Whop sends ISO strings or unix timestamps. Accept both."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _upsert_tenant_from_membership(membership: dict) -> tuple[Tenant, User, bool]:
    """Create or update the Tenant + User for this Whop membership.

    Returns (tenant, user, is_new) — `is_new` tells the caller whether to
    send the welcome magic-link email.
    """
    membership_id = str(membership.get("id") or "")
    whop_user = membership.get("user") or {}
    whop_user_id = str(whop_user.get("id") or "")
    email = (whop_user.get("email") or "").strip().lower()
    product_id = str((membership.get("product") or {}).get("id") or "") or None
    whop_status = membership.get("status")
    expires_at = _parse_expires_at(membership.get("expires_at"))

    if not membership_id or not whop_user_id or not email:
        raise HTTPException(
            status_code=400,
            detail=f"Whop payload missing required fields (membership_id, user.id, user.email)",
        )

    mapped_status = whop_status_to_subscription_status(whop_status)
    SessionLocal = get_session_factory()
    is_new = False
    with SessionLocal() as session:
        tenant = session.execute(
            select(Tenant)
            .where(Tenant.whop_membership_id == membership_id)
            .execution_options(skip_tenant_filter=True)
        ).scalar_one_or_none()

        if tenant is None:
            is_new = True
            tenant = Tenant(
                name=f"{email.split('@')[0]}'s workspace",
                subscription_status=mapped_status,
                whop_user_id=whop_user_id,
                whop_membership_id=membership_id,
                whop_product_id=product_id,
                whop_status_raw=whop_status,
                whop_expires_at=expires_at,
            )
            session.add(tenant)
            session.flush()
        else:
            tenant.subscription_status = mapped_status
            tenant.whop_status_raw = whop_status
            tenant.whop_expires_at = expires_at
            if product_id:
                tenant.whop_product_id = product_id

        # Find or create the admin user.
        user = session.execute(
            select(User)
            .where(User.email == email)
            .execution_options(skip_tenant_filter=True)
        ).scalar_one_or_none()
        if user is None:
            # A random password — the user authenticates via magic link, not password.
            # We still set a hash so the password column is never null.
            import secrets

            user = User(
                tenant_id=tenant.id,
                email=email,
                password_hash=hash_password(secrets.token_urlsafe(32)),
                role=UserRole.ADMIN.value,
                email_verified=True,
            )
            session.add(user)
        elif user.tenant_id != tenant.id:
            # Edge case: same email re-subscribed under a different tenant.
            # Keep them tied to the most recent tenant.
            user.tenant_id = tenant.id

        session.commit()
        session.refresh(tenant)
        session.refresh(user)

    return tenant, user, is_new


# ─── Route ────────────────────────────────────────────────────


@router.post("/whop", status_code=status.HTTP_200_OK)
async def whop_webhook(request: Request) -> dict:
    raw_body = await request.body()
    _verify_signature(raw_body, request.headers.get("Whop-Signature"))

    import json
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"bad JSON: {e}") from e

    event = payload.get("event") or payload.get("action") or ""
    data = payload.get("data") or {}

    logger.info(f"Whop webhook received: event={event!r}, membership_id={(data or {}).get('id')}")

    if event in {"membership.went_valid", "membership.created", "membership_went_valid"}:
        tenant, user, is_new = _upsert_tenant_from_membership(data)
        if is_new or tenant.subscription_status in {
            SubscriptionStatus.TRIALING.value,
            SubscriptionStatus.ACTIVE.value,
        }:
            magic = issue_magic_link_token(user_id=user.id, tenant_id=tenant.id)
            magic_url = f"{_frontend_base_url()}/auth/magic?token={magic}"
            rendered = magic_link_signup(magic_url, workspace_name=tenant.name)
            send_email(to=user.email, subject=rendered.subject, text=rendered.text, html=rendered.html)
        return {"ok": True, "tenant_id": tenant.id, "is_new": is_new}

    if event in {"membership.went_invalid", "membership_went_invalid"}:
        _mark_membership_status(data, SubscriptionStatus.PAST_DUE.value)
        return {"ok": True}

    if event in {"membership.cancelled", "membership_cancelled", "membership.expired", "membership_expired"}:
        tenant = _mark_membership_status(data, SubscriptionStatus.CANCELLED.value)
        # Notify the user — only if we have an email and they had been active.
        if tenant is not None:
            SessionLocal = get_session_factory()
            with SessionLocal() as s:
                user = s.execute(
                    select(User)
                    .where(User.tenant_id == tenant.id)
                    .execution_options(skip_tenant_filter=True)
                ).scalar_one_or_none()
            if user is not None:
                rendered = subscription_cancelled()
                send_email(to=user.email, subject=rendered.subject, text=rendered.text)
        return {"ok": True}

    # Other events (payment.created, etc.) — accept but don't act on them yet.
    logger.info(f"Whop webhook event {event!r} acknowledged (no handler wired)")
    return {"ok": True, "handled": False}


def _mark_membership_status(membership: dict, new_status: str) -> Tenant | None:
    membership_id = str(membership.get("id") or "")
    if not membership_id:
        return None
    SessionLocal = get_session_factory()
    with SessionLocal() as session:
        tenant = session.execute(
            select(Tenant)
            .where(Tenant.whop_membership_id == membership_id)
            .execution_options(skip_tenant_filter=True)
        ).scalar_one_or_none()
        if tenant is None:
            logger.warning(f"Whop webhook: no tenant for membership {membership_id}")
            return None
        tenant.subscription_status = new_status
        tenant.whop_status_raw = membership.get("status")
        tenant.whop_expires_at = _parse_expires_at(membership.get("expires_at"))
        session.commit()
        session.refresh(tenant)
        return tenant
