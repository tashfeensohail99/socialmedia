"""OAuthState — short-lived row tracking an in-flight OAuth handshake.

When a user clicks "Connect Instagram" we:
  1. Generate a random `state` token + (for TikTok) a PKCE verifier
  2. Insert an OAuthState row tying state → (tenant_id, platform)
  3. Redirect the user to the platform's authorize URL with the state
  4. Platform redirects back to our callback with state + code
  5. We look up the state in the DB to recover tenant_id + verify CSRF
  6. Exchange code → token, save SocialAccount, delete the state row

Stale rows older than ~30 min are cleaned up periodically.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from sma.db.base import Base


class OAuthState(Base):
    """NOT TenantOwned — written before auth is complete, has its own tenant_id col."""

    __tablename__ = "oauth_states"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    state: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    tenant_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    # PKCE verifier (TikTok requires PKCE; others ignore).
    code_verifier: Mapped[str | None] = mapped_column(String(128), nullable=True)

    redirect_after: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
