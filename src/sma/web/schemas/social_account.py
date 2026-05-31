"""Pydantic schemas for the SocialAccount resource.

Creation goes through the OAuth flow (not a CRUD POST). The router only
exposes list/get/delete — and crucially never returns the encrypted token blob.
"""

from __future__ import annotations

from datetime import datetime

from sma.web.schemas.common import TimestampedRead


class SocialAccountRead(TimestampedRead):
    id: int
    tenant_id: int
    platform: str
    account_handle: str
    status: str
    last_used_at: datetime | None = None
    refresh_token_expires_at: datetime | None = None
