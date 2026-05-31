"""LinkedIn OAuth — for member posting via the Posts API.

The customer must:
  1. Create an app at developer.linkedin.com
  2. Request the 'Sign In with LinkedIn using OpenID Connect' product
  3. Request the 'Share on LinkedIn' product (needs w_member_social)
  4. Add our callback URL
  5. Set LINKEDIN_CLIENT_ID + LINKEDIN_CLIENT_SECRET in .env

LinkedIn member access tokens last 60 days and there's no refresh token —
re-auth is required after expiry. Phase 5 (Mode B) needs to handle this UX.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse

from sma.web.oauth.common import (
    OAuthConnectUser,
    get_oauth_app_creds,
    callback_url,
    consume_state,
    issue_state,
    upsert_social_account,
)

router = APIRouter(prefix="/api/oauth/linkedin", tags=["oauth"])

_AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
_TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
_USERINFO_URL = "https://api.linkedin.com/v2/userinfo"

_SCOPES = [
    "openid",
    "profile",
    "email",
    "w_member_social",
]


@router.get("/connect")
def connect_linkedin(
    user: OAuthConnectUser, redirect_after: str | None = Query(None)
) -> RedirectResponse:
    creds = get_oauth_app_creds(user.tenant_id, "linkedin", "LINKEDIN", "CLIENT_ID", "CLIENT_SECRET")
    state, _ = issue_state(user.tenant_id, "linkedin", redirect_after)
    params = {
        "response_type": "code",
        "client_id": creds["client_id"],
        "redirect_uri": callback_url("linkedin"),
        "state": state,
        "scope": " ".join(_SCOPES),
    }
    return RedirectResponse(url=f"{_AUTH_URL}?{urlencode(params)}", status_code=302)


@router.get("/callback")
def callback_linkedin(
    code: str = Query(...),
    state: str = Query(...),
    error: str | None = Query(None),
    error_description: str | None = Query(None),
) -> dict:
    if error:
        raise HTTPException(
            status_code=400, detail=f"LinkedIn error: {error} — {error_description or ''}"
        )
    state_row = consume_state(state, "linkedin")
    tenant_id = state_row.tenant_id
    creds = get_oauth_app_creds(tenant_id, "linkedin", "LINKEDIN", "CLIENT_ID", "CLIENT_SECRET")

    with httpx.Client(timeout=30.0) as client:
        r = client.post(
            _TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": callback_url("linkedin"),
                "client_id": creds["client_id"],
                "client_secret": creds["client_secret"],
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        r.raise_for_status()
        token_data = r.json()
        access_token = token_data["access_token"]
        expires_in = int(token_data.get("expires_in", 60 * 24 * 3600))

        # Fetch the member's URN — required for the Posts API.
        r = client.get(_USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"})
        r.raise_for_status()
        userinfo = r.json()
        # OIDC userinfo returns 'sub' = member id (numeric or hash)
        sub = userinfo["sub"]
        author_urn = f"urn:li:person:{sub}"
        name = userinfo.get("name", "LinkedIn member")

    expiry = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    upsert_social_account(
        tenant_id=tenant_id,
        platform="linkedin",
        account_handle=name,
        token_payload={
            "access_token": access_token,
            "author_urn": author_urn,
            "client_id": creds["client_id"],
            "client_secret": creds["client_secret"],
        },
        refresh_expires_at=expiry,
    )
    return {
        "ok": True,
        "name": name,
        "author_urn": author_urn,
        "expires_at": expiry.isoformat(),
        "redirect_after": state_row.redirect_after,
    }
