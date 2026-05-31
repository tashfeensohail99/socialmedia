"""Worker job: refresh OAuth tokens nearing expiry.

Runs hourly. For each SocialAccount with refresh_token_expires_at < now + 24h,
attempts a refresh against the platform's OAuth endpoint, re-encrypts and
saves the new tokens, updates expiry.

For Phase 2 this is a SCAFFOLD with provider-specific stubs; full refresh
logic per platform comes online as each OAuth callback ships. Tokens that
can't be refreshed (e.g. revoked) get marked status='expired' so the operator
sees them in the UI and can re-connect.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx
from loguru import logger
from sqlalchemy import select

from sma.db.crypto import decrypt_blob, encrypt_blob
from sma.db.models.social_account import SocialAccount
from sma.db.session import get_session_factory, tenant_scope


def refresh_due_tokens() -> None:
    """Top-level entry point — APScheduler calls this hourly."""
    SessionLocal = get_session_factory()
    threshold = datetime.now(timezone.utc) + timedelta(hours=24)

    with SessionLocal() as session:
        due = session.execute(
            select(SocialAccount)
            .where(
                SocialAccount.status == "active",
                SocialAccount.refresh_token_expires_at.isnot(None),
                SocialAccount.refresh_token_expires_at < threshold,
            )
            .execution_options(skip_tenant_filter=True)
        ).scalars().all()
        targets = [(a.id, a.tenant_id, a.platform) for a in due]

    if not targets:
        return
    logger.info(f"refresh_tokens: {len(targets)} accounts due for refresh")

    for acct_id, tenant_id, platform in targets:
        with tenant_scope(tenant_id):
            try:
                _refresh_one(acct_id, platform)
            except Exception as e:
                logger.error(f"refresh failed for account {acct_id} ({platform}): {e}")


def _refresh_one(acct_id: int, platform: str) -> None:
    SessionLocal = get_session_factory()
    with SessionLocal() as session:
        acct = session.get(SocialAccount, acct_id)
        if acct is None:
            return
        try:
            token = decrypt_blob(acct.encrypted_oauth_blob)
        except Exception as e:
            logger.error(f"account {acct_id}: decrypt failed: {e}")
            acct.status = "expired"
            session.commit()
            return

    new_token: dict | None = None
    new_expiry: datetime | None = None

    try:
        if platform == "facebook" or platform == "instagram":
            new_token, new_expiry = _refresh_meta(token)
        elif platform == "youtube":
            new_token, new_expiry = _refresh_google(token)
        elif platform == "tiktok":
            new_token, new_expiry = _refresh_tiktok(token)
        elif platform == "linkedin":
            # LinkedIn member tokens don't have a refresh_token — re-auth is required.
            new_token, new_expiry = None, None
        else:
            logger.warning(f"unknown platform {platform!r} for refresh")
            return
    except httpx.HTTPError as e:
        logger.warning(f"account {acct_id} refresh HTTP error: {e}")
        return

    with SessionLocal() as session:
        acct = session.get(SocialAccount, acct_id)
        if acct is None:
            return
        if new_token is None:
            # Mark expired so the user re-connects via OAuth.
            acct.status = "expired"
        else:
            # Merge: keep static fields (client_id, page_id, etc.) and update the access_token.
            merged = {**token, **new_token}
            acct.encrypted_oauth_blob = encrypt_blob(merged)
            acct.refresh_token_expires_at = new_expiry
        session.commit()


# ─── Provider-specific refresh helpers ─────────────────────────


def _refresh_meta(token: dict) -> tuple[dict | None, datetime | None]:
    """Meta page tokens last 60 days; long-lived user tokens can extend them.

    Stub: returns (None, None) so the account gets marked expired and the user
    re-connects. Full impl: GET /oauth/access_token?grant_type=fb_exchange_token...
    """
    return None, None


def _refresh_google(token: dict) -> tuple[dict | None, datetime | None]:
    """Use Google's refresh_token grant to mint a new access_token."""
    refresh_token = token.get("refresh_token")
    client_id = token.get("client_id")
    client_secret = token.get("client_secret")
    if not (refresh_token and client_id and client_secret):
        return None, None
    with httpx.Client(timeout=30.0) as client:
        r = client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
        r.raise_for_status()
        data = r.json()
    new_token = {"access_token": data["access_token"]}
    expires_in = int(data.get("expires_in", 3600))
    new_expiry = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    return new_token, new_expiry


def _refresh_tiktok(token: dict) -> tuple[dict | None, datetime | None]:
    """TikTok refresh_token grant."""
    refresh_token = token.get("refresh_token")
    client_key = token.get("client_key")
    client_secret = token.get("client_secret")
    if not (refresh_token and client_key and client_secret):
        return None, None
    with httpx.Client(timeout=30.0) as client:
        r = client.post(
            "https://open.tiktokapis.com/v2/oauth/token/",
            data={
                "client_key": client_key,
                "client_secret": client_secret,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        r.raise_for_status()
        data = r.json()
    new_token = {
        "access_token": data["access_token"],
        "refresh_token": data.get("refresh_token", refresh_token),
    }
    expires_in = int(data.get("expires_in", 86400))
    new_expiry = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    return new_token, new_expiry
