"""Google OAuth — for YouTube upload + channel access.

Standard Google OAuth 2.0 with refresh tokens. The customer must:
  1. Create a project at console.cloud.google.com
  2. Enable YouTube Data API v3
  3. Configure OAuth consent (External, can stay in Testing mode for dev)
  4. Create OAuth client ID (Web app), add our callback URL
  5. Set GOOGLE_CLIENT_ID + GOOGLE_CLIENT_SECRET in .env

`access_type=offline` + `prompt=consent` is REQUIRED to get a refresh_token
(Google only returns it on first consent unless we force it).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse

from sma.web.oauth.common import (
    OAuthConnectUser,
    callback_url,
    consume_state,
    frontend_redirect,
    get_oauth_app_creds,
    issue_state,
    upsert_social_account,
)

router = APIRouter(prefix="/api/oauth/youtube", tags=["oauth"])

_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN_URL = "https://oauth2.googleapis.com/token"
_YT_CHANNEL_URL = "https://www.googleapis.com/youtube/v3/channels"

_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]


@router.get("/connect")
def connect_youtube(
    user: OAuthConnectUser, redirect_after: str | None = Query(None)
) -> RedirectResponse:
    creds = get_oauth_app_creds(user.tenant_id, "youtube", "GOOGLE", "CLIENT_ID", "CLIENT_SECRET")
    state, _ = issue_state(user.tenant_id, "youtube", redirect_after)
    params = {
        "client_id": creds["client_id"],
        "redirect_uri": callback_url("youtube"),
        "state": state,
        "response_type": "code",
        "scope": " ".join(_SCOPES),
        "access_type": "offline",
        "prompt": "consent",  # force consent so we always get a refresh_token
        "include_granted_scopes": "true",
    }
    return RedirectResponse(url=f"{_AUTH_URL}?{urlencode(params)}", status_code=302)


@router.get("/callback")
def callback_youtube(
    code: str = Query(None),
    state: str = Query(...),
    error: str | None = Query(None),
) -> RedirectResponse:
    if error:
        return RedirectResponse(url=frontend_redirect("youtube", False, error), status_code=302)
    if not code:
        return RedirectResponse(url=frontend_redirect("youtube", False, "no code"), status_code=302)
    state_row = consume_state(state, "youtube")
    tenant_id = state_row.tenant_id
    creds = get_oauth_app_creds(tenant_id, "youtube", "GOOGLE", "CLIENT_ID", "CLIENT_SECRET")

    with httpx.Client(timeout=30.0) as client:
        r = client.post(_TOKEN_URL, data={
            "client_id": creds["client_id"],
            "client_secret": creds["client_secret"],
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": callback_url("youtube"),
        })
        r.raise_for_status()
        token_data = r.json()
        refresh_token = token_data.get("refresh_token")
        access_token = token_data["access_token"]
        expires_in = int(token_data.get("expires_in", 3600))

        if not refresh_token:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Google did not return a refresh_token. This usually means the "
                    "account has already been connected once. Visit "
                    "https://myaccount.google.com/permissions and remove this app, "
                    "then try again."
                ),
            )

        # Fetch channel title for a friendly account_handle
        r = client.get(
            _YT_CHANNEL_URL,
            params={"part": "snippet", "mine": "true"},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        r.raise_for_status()
        items = r.json().get("items", [])
        channel_title = items[0]["snippet"]["title"] if items else "YouTube Channel"

    expiry = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    upsert_social_account(
        tenant_id=tenant_id,
        platform="youtube",
        account_handle=channel_title,
        token_payload={
            "client_id": creds["client_id"],
            "client_secret": creds["client_secret"],
            "refresh_token": refresh_token,
            "access_token": access_token,
        },
        refresh_expires_at=expiry,
    )
    return RedirectResponse(url=frontend_redirect("youtube", True), status_code=302)
