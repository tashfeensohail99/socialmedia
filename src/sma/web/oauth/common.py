"""Shared OAuth helpers.

Used by Meta / YouTube / TikTok / LinkedIn routers. Each platform has its own
wire format but the high-level flow is identical:

    /api/oauth/<platform>/connect  → 302 redirect to platform's authorize URL
    /api/oauth/<platform>/callback → exchanges code → token, saves SocialAccount

This module owns state-token generation, PKCE, lookup, and the post-callback
SocialAccount upsert path that all platforms converge on.
"""

from __future__ import annotations

import base64
import hashlib
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Query
from loguru import logger
from sqlalchemy import select

from sma.db.crypto import encrypt_blob
from sma.db.models.oauth_state import OAuthState
from sma.db.models.social_account import SocialAccount
from sma.db.session import get_session_factory, set_current_tenant
from sma.web.auth.jwt import InvalidToken, decode_token


@dataclass
class OAuthUser:
    user_id: int
    tenant_id: int
    role: str


def oauth_connect_user(
    token: Annotated[str | None, Query()] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> OAuthUser:
    """Resolve the user for an OAuth /connect redirect.

    Browser navigations to /connect can't send an Authorization header, so we
    also accept the JWT as a ?token= query param. The frontend appends it.
    """
    # Prefer the header if present (e.g. programmatic calls), else the query param.
    raw = None
    if authorization and authorization.lower().startswith("bearer "):
        raw = authorization[7:].strip()
    if not raw:
        raw = token
    if not raw:
        raise HTTPException(status_code=401, detail="missing token (pass ?token=<jwt>)")
    try:
        payload = decode_token(raw)
    except InvalidToken as e:
        raise HTTPException(status_code=401, detail=f"invalid token: {e}") from e

    tenant_id = int(payload["tenant_id"])
    set_current_tenant(tenant_id)
    return OAuthUser(
        user_id=int(payload["sub"]),
        tenant_id=tenant_id,
        role=str(payload["role"]),
    )


OAuthConnectUser = Annotated[OAuthUser, Depends(oauth_connect_user)]


def get_base_url() -> str:
    """Public base URL of the FastAPI service. OAuth callbacks live under this."""
    return os.environ.get("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")


def callback_url(platform: str) -> str:
    return f"{get_base_url()}/api/oauth/{platform}/callback"


def frontend_base_url() -> str:
    """Public URL of the Next.js frontend, for post-OAuth redirects back to the UI."""
    return os.environ.get(
        "FRONTEND_BASE_URL",
        os.environ.get("NEXT_PUBLIC_API_URL", "http://localhost:3100"),
    ).rstrip("/")


def frontend_redirect(platform: str, ok: bool, detail: str = "") -> str:
    """Build a URL back to the frontend /socials page with a status query."""
    from urllib.parse import urlencode

    q = {"connected": platform if ok else "", "error": "" if ok else (detail or "failed")}
    return f"{frontend_base_url()}/socials?{urlencode(q)}"


# ─── State + PKCE ──────────────────────────────────────────────


def issue_state(tenant_id: int, platform: str, redirect_after: str | None = None,
                with_pkce: bool = False) -> tuple[str, str | None]:
    """Generate a random state token, persist it, return (state, code_verifier_or_None)."""
    state = secrets.token_urlsafe(32)
    code_verifier = secrets.token_urlsafe(64) if with_pkce else None

    SessionLocal = get_session_factory()
    with SessionLocal() as session:
        session.add(
            OAuthState(
                state=state,
                tenant_id=tenant_id,
                platform=platform,
                code_verifier=code_verifier,
                redirect_after=redirect_after,
                created_at=datetime.now(timezone.utc),
            )
        )
        session.commit()
    return state, code_verifier


def consume_state(state: str, expected_platform: str) -> OAuthState:
    """Look up + delete the state row; verify platform; raise 400 on any mismatch."""
    SessionLocal = get_session_factory()
    with SessionLocal() as session:
        row = session.execute(
            select(OAuthState).where(OAuthState.state == state)
        ).scalar_one_or_none()
        if row is None:
            raise HTTPException(status_code=400, detail="invalid or expired OAuth state")
        # Expire states older than 30 minutes.
        if datetime.now(timezone.utc) - row.created_at > timedelta(minutes=30):
            session.delete(row)
            session.commit()
            raise HTTPException(status_code=400, detail="OAuth state expired; please retry")
        if row.platform != expected_platform:
            raise HTTPException(status_code=400, detail="OAuth state platform mismatch")
        # Snapshot before delete so caller can use the values.
        captured = OAuthState(
            id=row.id,
            state=row.state,
            tenant_id=row.tenant_id,
            platform=row.platform,
            code_verifier=row.code_verifier,
            redirect_after=row.redirect_after,
            created_at=row.created_at,
        )
        session.delete(row)
        session.commit()
        return captured


def pkce_challenge(code_verifier: str) -> str:
    """S256 code challenge for OAuth PKCE."""
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


# ─── Save the SocialAccount after a successful exchange ────────


def upsert_social_account(
    tenant_id: int,
    platform: str,
    account_handle: str,
    token_payload: dict,
    refresh_expires_at: datetime | None,
) -> int:
    """Insert or update a SocialAccount for (tenant, platform, account_handle).

    Returns the row id. token_payload is encrypted with Fernet before storage.
    """
    SessionLocal = get_session_factory()
    with SessionLocal() as session:
        existing = session.execute(
            select(SocialAccount).where(
                SocialAccount.tenant_id == tenant_id,
                SocialAccount.platform == platform,
                SocialAccount.account_handle == account_handle,
            ).execution_options(skip_tenant_filter=True)
        ).scalar_one_or_none()
        encrypted = encrypt_blob(token_payload)
        if existing is None:
            row = SocialAccount(
                tenant_id=tenant_id,
                platform=platform,
                account_handle=account_handle,
                encrypted_oauth_blob=encrypted,
                refresh_token_expires_at=refresh_expires_at,
                status="active",
            )
            session.add(row)
            session.flush()
            row_id = row.id
        else:
            existing.encrypted_oauth_blob = encrypted
            existing.refresh_token_expires_at = refresh_expires_at
            existing.status = "active"
            row_id = existing.id
        session.commit()
        return row_id


def env_creds(prefix: str, *names: str) -> dict[str, str]:
    """Read OAuth client creds from env vars (e.g. META_APP_ID, META_APP_SECRET).

    Returns a dict { name.lower(): value }. Raises HTTPException(503) if any
    required var is missing (so the operator sees a clear setup error).
    """
    creds: dict[str, str] = {}
    missing: list[str] = []
    for name in names:
        full = f"{prefix}_{name}"
        val = os.environ.get(full, "").strip()
        if not val:
            missing.append(full)
        creds[name.lower()] = val
    if missing:
        raise HTTPException(
            status_code=503,
            detail=(
                f"{prefix} OAuth not configured — missing env vars: {missing}. "
                f"Set them in .env and restart."
            ),
        )
    return creds


# ─── Per-tenant OAuth app credentials (entered via the UI) ─────
#
# Each platform's OAuth *app* (client id/secret) is stored encrypted in the
# Credentials table under provider_kind="oauth_app", provider_name=<platform>.
# This lets each tenant bring their own OAuth app through the frontend instead
# of the operator setting env vars. We fall back to env vars if no DB row.

# (platform, payload-keys we expect, friendly env prefix for fallback)
_OAUTH_APP_KEYS: dict[str, tuple[str, str]] = {
    "youtube": ("client_id", "client_secret"),
    "meta": ("app_id", "app_secret"),
    "tiktok": ("client_key", "client_secret"),
    "linkedin": ("client_id", "client_secret"),
}


def get_oauth_app_creds(tenant_id: int, platform: str, env_prefix: str, *env_names: str) -> dict[str, str]:
    """Return the OAuth app credentials for a platform.

    Resolution order:
      1. Per-tenant row in Credentials (provider_kind='oauth_app', name=platform)
      2. Environment variables (operator-wide fallback)

    Raises HTTPException(503) with a UI-friendly message if neither is set.
    """
    from sma.db.crypto import decrypt_blob
    from sma.db.models.credentials import Credentials

    keys = _OAUTH_APP_KEYS.get(platform, env_names and tuple(n.lower() for n in env_names) or ())

    SessionLocal = get_session_factory()
    with SessionLocal() as session:
        row = session.execute(
            select(Credentials).where(
                Credentials.provider_kind == "oauth_app",
                Credentials.provider_name == platform,
            ).execution_options(skip_tenant_filter=True).where(
                Credentials.tenant_id == tenant_id
            )
        ).scalar_one_or_none()
        if row is not None:
            blob = decrypt_blob(row.encrypted_blob)
            if all(blob.get(k) for k in keys):
                return {k: str(blob[k]) for k in keys}

    # Fall back to env vars.
    creds: dict[str, str] = {}
    missing: list[str] = []
    for i, name in enumerate(env_names):
        val = os.environ.get(f"{env_prefix}_{name}", "").strip()
        key = keys[i] if i < len(keys) else name.lower()
        if not val:
            missing.append(name)
        creds[key] = val
    if missing:
        raise HTTPException(
            status_code=503,
            detail=(
                f"{platform} is not configured yet. Add your {platform} app "
                f"Client ID and Secret on the Social Accounts page first."
            ),
        )
    return creds
