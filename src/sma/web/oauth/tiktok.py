"""TikTok OAuth — for Content Posting API.

TikTok requires PKCE (S256). Customer must:
  1. Register a TikTok app at developers.tiktok.com
  2. Add the Content Posting API product
  3. Add our callback URL to the redirect URIs allowlist
  4. Set TIKTOK_CLIENT_KEY + TIKTOK_CLIENT_SECRET in .env

Note: TikTok apps start in "unaudited" mode with limited functionality;
production requires app review for the `video.publish` scope. We assume the
operator has done that work.
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
    frontend_redirect,
    issue_state,
    pkce_challenge,
    upsert_social_account,
)

router = APIRouter(prefix="/api/oauth/tiktok", tags=["oauth"])

_AUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"
_TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
_USER_INFO_URL = "https://open.tiktokapis.com/v2/user/info/"

_SCOPES = [
    "user.info.basic",
    "video.publish",
    "video.upload",
]


@router.get("/connect")
def connect_tiktok(
    user: OAuthConnectUser, redirect_after: str | None = Query(None)
) -> RedirectResponse:
    creds = get_oauth_app_creds(user.tenant_id, "tiktok", "TIKTOK", "CLIENT_KEY", "CLIENT_SECRET")
    state, verifier = issue_state(user.tenant_id, "tiktok", redirect_after, with_pkce=True)
    challenge = pkce_challenge(verifier)  # type: ignore[arg-type]
    params = {
        "client_key": creds["client_key"],
        "response_type": "code",
        "scope": ",".join(_SCOPES),
        "redirect_uri": callback_url("tiktok"),
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    return RedirectResponse(url=f"{_AUTH_URL}?{urlencode(params)}", status_code=302)


@router.get("/callback")
def callback_tiktok(
    code: str = Query(None),
    state: str = Query(...),
    error: str | None = Query(None),
    error_description: str | None = Query(None),
) -> RedirectResponse:
    if error:
        return RedirectResponse(
            url=frontend_redirect("tiktok", False, error_description or error), status_code=302
        )
    if not code:
        return RedirectResponse(url=frontend_redirect("tiktok", False, "no code"), status_code=302)
    state_row = consume_state(state, "tiktok")
    tenant_id = state_row.tenant_id
    creds = get_oauth_app_creds(tenant_id, "tiktok", "TIKTOK", "CLIENT_KEY", "CLIENT_SECRET")

    with httpx.Client(timeout=30.0) as client:
        r = client.post(
            _TOKEN_URL,
            data={
                "client_key": creds["client_key"],
                "client_secret": creds["client_secret"],
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": callback_url("tiktok"),
                "code_verifier": state_row.code_verifier or "",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        r.raise_for_status()
        token_data = r.json()
        access_token = token_data["access_token"]
        refresh_token = token_data.get("refresh_token", "")
        expires_in = int(token_data.get("expires_in", 86400))
        open_id = token_data.get("open_id", "")

        # Fetch a friendly handle (username) via user/info
        username = "tiktok_user"
        try:
            r = client.get(
                _USER_INFO_URL,
                params={"fields": "open_id,union_id,display_name"},
                headers={"Authorization": f"Bearer {access_token}"},
            )
            r.raise_for_status()
            display = r.json().get("data", {}).get("user", {}).get("display_name", "")
            if display:
                username = display
        except httpx.HTTPError:
            pass

    expiry = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    upsert_social_account(
        tenant_id=tenant_id,
        platform="tiktok",
        account_handle=username,
        token_payload={
            "client_key": creds["client_key"],
            "client_secret": creds["client_secret"],
            "access_token": access_token,
            "refresh_token": refresh_token,
            "open_id": open_id,
        },
        refresh_expires_at=expiry,
    )
    return RedirectResponse(url=frontend_redirect("tiktok", True), status_code=302)
