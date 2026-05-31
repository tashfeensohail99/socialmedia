"""JWT issuance + validation.

Tokens carry: sub (user_id), tenant_id, role, iat, exp.
Signed with the JWT_SECRET env var (HS256). Short-lived (24h default).
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

_ALGO = "HS256"
_TOKEN_TTL_HOURS = 24


class JWTConfigurationError(RuntimeError):
    pass


class InvalidToken(Exception):
    pass


def _secret() -> str:
    s = os.environ.get("JWT_SECRET", "").strip()
    if not s:
        raise JWTConfigurationError(
            "JWT_SECRET env var is required. Generate one with `openssl rand -hex 32`."
        )
    return s


def issue_token(*, user_id: int, tenant_id: int, role: str, ttl_hours: int | None = None) -> str:
    """Create a signed JWT for the given user."""
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "tenant_id": tenant_id,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=ttl_hours or _TOKEN_TTL_HOURS)).timestamp()),
    }
    return jwt.encode(payload, _secret(), algorithm=_ALGO)


def decode_token(token: str) -> dict[str, Any]:
    """Verify + decode a JWT. Raises InvalidToken on any failure."""
    try:
        return jwt.decode(token, _secret(), algorithms=[_ALGO])
    except jwt.InvalidTokenError as e:
        raise InvalidToken(str(e)) from e
