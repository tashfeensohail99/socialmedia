"""SocialAccount routes — read/list/delete.

OAuth flow handles creation; users connect via /api/oauth/{platform}/connect.
This router never returns the encrypted token blob.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select

from sma.db.crypto import decrypt_blob, encrypt_blob
from sma.db.models.credentials import Credentials
from sma.db.models.social_account import SocialAccount
from sma.db.session import get_db_session
from sma.web.auth.dependencies import CurrentUser
from sma.web.schemas.common import MessageResponse, Page, PageMeta
from sma.web.schemas.social_account import SocialAccountRead

router = APIRouter(prefix="/api/social-accounts", tags=["social-accounts"])

# Which credential fields each platform's OAuth app needs, and a short hint
# for the UI on where to create the app + which redirect URI to register.
OAUTH_APP_SPECS: dict[str, dict] = {
    "youtube": {
        "label": "YouTube (Google)",
        "fields": ["client_id", "client_secret"],
        "console_url": "https://console.cloud.google.com/apis/credentials",
        "instructions": (
            "Create a Google Cloud project, enable 'YouTube Data API v3', configure the "
            "OAuth consent screen (External, add yourself as a Test user), then create an "
            "OAuth client ID of type 'Web application'."
        ),
    },
    "meta": {
        "label": "Facebook + Instagram (Meta)",
        "fields": ["app_id", "app_secret"],
        "console_url": "https://developers.facebook.com/apps",
        "instructions": (
            "Create a Meta app, add the 'Facebook Login' product, and add the redirect URI "
            "below under Valid OAuth Redirect URIs."
        ),
    },
    "tiktok": {
        "label": "TikTok",
        "fields": ["client_key", "client_secret"],
        "console_url": "https://developers.tiktok.com/apps",
        "instructions": (
            "Create a TikTok app, enable Content Posting API, and add the redirect URI below."
        ),
    },
    "linkedin": {
        "label": "LinkedIn",
        "fields": ["client_id", "client_secret"],
        "console_url": "https://www.linkedin.com/developers/apps",
        "instructions": (
            "Create a LinkedIn app, request the Share on LinkedIn / w_member_social product, "
            "and add the redirect URI below under Authorized redirect URLs."
        ),
    },
}


@router.get("", response_model=Page[SocialAccountRead])
def list_accounts(
    user: CurrentUser,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    platform: str | None = Query(None),
) -> Page[SocialAccountRead]:
    with get_db_session() as session:
        stmt = select(SocialAccount)
        if platform:
            stmt = stmt.where(SocialAccount.platform == platform)
        total = session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        rows = session.scalars(
            stmt.order_by(SocialAccount.id.desc()).limit(limit).offset(offset)
        ).all()
        return Page[SocialAccountRead](
            items=[SocialAccountRead.model_validate(r) for r in rows],
            meta=PageMeta(total=total, limit=limit, offset=offset),
        )


@router.get("/{acct_id}", response_model=SocialAccountRead)
def get_account(acct_id: int, user: CurrentUser) -> SocialAccountRead:
    with get_db_session() as session:
        row = session.get(SocialAccount, acct_id)
        if row is None or row.tenant_id != user.tenant_id:
            raise HTTPException(status_code=404, detail="social account not found")
        return SocialAccountRead.model_validate(row)


@router.delete("/{acct_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(acct_id: int, user: CurrentUser) -> None:
    """Disconnect — deletes the stored OAuth tokens. User can re-connect via OAuth."""
    with get_db_session() as session:
        row = session.get(SocialAccount, acct_id)
        if row is None or row.tenant_id != user.tenant_id:
            raise HTTPException(status_code=404, detail="social account not found")
        session.delete(row)


# ─── OAuth app credentials (Client ID / Secret) — set via the UI ──────────────


class OAuthAppStatus(BaseModel):
    platform: str
    label: str
    configured: bool
    fields: list[str]
    console_url: str
    instructions: str
    redirect_uri: str


class OAuthAppSave(BaseModel):
    # Generic: the UI sends the fields relevant to the platform.
    client_id: str | None = None
    client_secret: str | None = None
    app_id: str | None = None
    app_secret: str | None = None
    client_key: str | None = None


def _backend_base_url() -> str:
    import os
    return os.environ.get("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")


@router.get("/oauth-apps/status", response_model=list[OAuthAppStatus])
def oauth_apps_status(user: CurrentUser) -> list[OAuthAppStatus]:
    """List each platform's OAuth-app config status (whether Client ID/Secret are saved)."""
    base = _backend_base_url()
    out: list[OAuthAppStatus] = []
    with get_db_session() as session:
        rows = {
            r.provider_name: r
            for r in session.query(Credentials)
            .filter(Credentials.provider_kind == "oauth_app")
            .all()
        }
        for platform, spec in OAUTH_APP_SPECS.items():
            configured = False
            row = rows.get(platform)
            if row is not None:
                try:
                    blob = decrypt_blob(row.encrypted_blob)
                    configured = all(blob.get(f) for f in spec["fields"])
                except Exception:
                    configured = False
            # meta/youtube/linkedin/tiktok all callback under /api/oauth/<platform>/callback
            out.append(
                OAuthAppStatus(
                    platform=platform,
                    label=spec["label"],
                    configured=configured,
                    fields=spec["fields"],
                    console_url=spec["console_url"],
                    instructions=spec["instructions"],
                    redirect_uri=f"{base}/api/oauth/{platform}/callback",
                )
            )
    return out


@router.put("/oauth-apps/{platform}", response_model=MessageResponse)
def save_oauth_app(platform: str, payload: OAuthAppSave, user: CurrentUser) -> MessageResponse:
    """Save (encrypted) the OAuth app Client ID/Secret for a platform."""
    spec = OAUTH_APP_SPECS.get(platform)
    if spec is None:
        raise HTTPException(status_code=404, detail=f"unknown platform {platform!r}")

    data = payload.model_dump(exclude_none=True)
    blob = {f: data.get(f, "").strip() for f in spec["fields"]}
    missing = [f for f in spec["fields"] if not blob.get(f)]
    if missing:
        raise HTTPException(status_code=400, detail=f"missing fields: {missing}")

    with get_db_session() as session:
        existing = session.execute(
            select(Credentials).where(
                Credentials.provider_kind == "oauth_app",
                Credentials.provider_name == platform,
                Credentials.label == "default",
            )
        ).scalar_one_or_none()
        if existing is None:
            session.add(
                Credentials(
                    tenant_id=user.tenant_id,
                    provider_kind="oauth_app",
                    provider_name=platform,
                    label="default",
                    encrypted_blob=encrypt_blob(blob),
                )
            )
        else:
            existing.encrypted_blob = encrypt_blob(blob)
    return MessageResponse(message=f"{spec['label']} app credentials saved")
