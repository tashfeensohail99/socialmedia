"""Meta OAuth — covers Facebook Pages + Instagram Business.

Both platforms use the Facebook Login dialog. After the user grants access we:
  1. Exchange the code for a short-lived USER access token.
  2. Exchange that for a long-lived USER token (~60 days).
  3. List the user's Pages → for each Page, store the Page token (never expires
     while the long-lived USER token is alive) as a SocialAccount.
  4. If a Page has an Instagram Business account attached, also store an
     `instagram` SocialAccount pointing at the same Page token + IG user id.

Required scopes:
  - pages_show_list, pages_read_engagement
  - pages_manage_posts                  (FB post)
  - instagram_basic, instagram_content_publish  (IG post)
  - business_management                 (some accounts need this)

The customer must create a Meta App at developers.facebook.com and put
META_APP_ID + META_APP_SECRET in their env.
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
    get_oauth_app_creds,
    issue_state,
    upsert_social_account,
)

router = APIRouter(prefix="/api/oauth/meta", tags=["oauth"])

_AUTH_URL = "https://www.facebook.com/v21.0/dialog/oauth"
_TOKEN_URL = "https://graph.facebook.com/v21.0/oauth/access_token"
_GRAPH = "https://graph.facebook.com/v21.0"

_SCOPES = [
    "pages_show_list",
    "pages_read_engagement",
    "pages_manage_posts",
    "instagram_basic",
    "instagram_content_publish",
    "business_management",
]


@router.get("/connect")
def connect_meta(user: OAuthConnectUser, redirect_after: str | None = Query(None)) -> RedirectResponse:
    """Kick off the Meta OAuth flow."""
    creds = get_oauth_app_creds(user.tenant_id, "meta", "META", "APP_ID", "APP_SECRET")
    state, _ = issue_state(user.tenant_id, "meta", redirect_after)
    params = {
        "client_id": creds["app_id"],
        "redirect_uri": callback_url("meta"),
        "state": state,
        "response_type": "code",
        "scope": ",".join(_SCOPES),
    }
    return RedirectResponse(url=f"{_AUTH_URL}?{urlencode(params)}", status_code=302)


@router.get("/callback")
def callback_meta(
    code: str = Query(...),
    state: str = Query(...),
    error: str | None = Query(None),
) -> dict:
    if error:
        raise HTTPException(status_code=400, detail=f"Meta returned error: {error}")
    state_row = consume_state(state, "meta")
    tenant_id = state_row.tenant_id
    creds = get_oauth_app_creds(tenant_id, "meta", "META", "APP_ID", "APP_SECRET")

    with httpx.Client(timeout=30.0) as client:
        # 1. Short-lived user token
        r = client.get(_TOKEN_URL, params={
            "client_id": creds["app_id"],
            "client_secret": creds["app_secret"],
            "redirect_uri": callback_url("meta"),
            "code": code,
        })
        r.raise_for_status()
        short_token = r.json()["access_token"]

        # 2. Long-lived user token (~60 days)
        r = client.get(_TOKEN_URL, params={
            "grant_type": "fb_exchange_token",
            "client_id": creds["app_id"],
            "client_secret": creds["app_secret"],
            "fb_exchange_token": short_token,
        })
        r.raise_for_status()
        long_data = r.json()
        long_token = long_data["access_token"]
        expires_in = int(long_data.get("expires_in", 60 * 24 * 3600))
        long_expiry = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

        # 3. List Pages the user manages → save FB + IG accounts
        r = client.get(
            f"{_GRAPH}/me/accounts",
            params={"access_token": long_token, "fields": "id,name,access_token,instagram_business_account"},
        )
        r.raise_for_status()
        pages = r.json().get("data", [])

    saved_fb = 0
    saved_ig = 0
    for page in pages:
        page_id = page["id"]
        page_name = page["name"]
        page_token = page["access_token"]

        # Facebook Page
        upsert_social_account(
            tenant_id=tenant_id,
            platform="facebook",
            account_handle=page_name,
            token_payload={
                "page_id": page_id,
                "page_token": page_token,
                "user_token": long_token,  # for refresh
                "app_id": creds["app_id"],
                "app_secret": creds["app_secret"],
            },
            refresh_expires_at=long_expiry,
        )
        saved_fb += 1

        # Instagram Business account (if attached)
        ig = page.get("instagram_business_account")
        if ig and ig.get("id"):
            # Fetch IG username for a friendly handle
            ig_username = "instagram"
            try:
                with httpx.Client(timeout=15.0) as client:
                    r = client.get(
                        f"{_GRAPH}/{ig['id']}",
                        params={"fields": "username", "access_token": page_token},
                    )
                    r.raise_for_status()
                    ig_username = r.json().get("username", ig_username)
            except httpx.HTTPError:
                pass
            upsert_social_account(
                tenant_id=tenant_id,
                platform="instagram",
                account_handle=f"@{ig_username}",
                token_payload={
                    "ig_user_id": ig["id"],
                    "page_id": page_id,
                    "page_token": page_token,
                    "app_id": creds["app_id"],
                    "app_secret": creds["app_secret"],
                },
                refresh_expires_at=long_expiry,
            )
            saved_ig += 1

    return {
        "ok": True,
        "facebook_pages_connected": saved_fb,
        "instagram_accounts_connected": saved_ig,
        "expires_at": long_expiry.isoformat(),
        "redirect_after": state_row.redirect_after,
    }
