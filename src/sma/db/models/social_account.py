"""SocialAccount — OAuth tokens for a connected social platform.

Mode A: customer connects their own Meta/Google/TikTok/LinkedIn apps and
saves the tokens here.
Mode B: master OAuth apps owned by the platform operator; each tenant connects
through them and saves their per-account tokens here.

The encrypted_oauth_blob stores {access_token, refresh_token, scopes, ...}
encrypted with Fernet (same MASTER_KEY as credentials).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, LargeBinary, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from sma.db.base import Base, TenantOwned


class SocialAccount(Base, TenantOwned):
    __tablename__ = "social_accounts"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "platform", "account_handle",
            name="uq_social_account_tenant_platform_handle",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    platform: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    # instagram | facebook | youtube | tiktok | linkedin
    account_handle: Mapped[str] = mapped_column(String(255), nullable=False)
    # IG username, FB page name, YT channel title, TikTok username, LinkedIn org/person name

    encrypted_oauth_blob: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    refresh_token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    # active | expired | revoked
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
