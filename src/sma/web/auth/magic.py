"""Magic-link login.

Flow:
  1. Whop webhook → we create the tenant + user → we generate a short-lived
     "magic" JWT (type=magic_link) for that user.
  2. Email a URL containing the JWT to the user's billing email:
       https://summitautomates.com/auth/magic?token=<JWT>
  3. User clicks. Frontend page POSTs the JWT to /api/auth/magic-login.
  4. Backend validates the JWT (sig, exp, type=magic_link), looks up the user,
     issues a normal session JWT, returns it. Frontend stores it in
     localStorage and redirects to /dashboard.

The magic-link token is stateless — its single-use property comes from a short
expiry (30 minutes) and the fact that it must contain a user_id that exists in
our DB. We don't track used tokens; reusing a not-yet-expired link is a
trade-off we accept for not having a token table.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt as _jwt

from sma.web.auth.jwt import _ALGO, InvalidToken, _secret

_MAGIC_TYPE = "magic_link"
_MAGIC_TTL_MINUTES = 30


def issue_magic_link_token(*, user_id: int, tenant_id: int) -> str:
    """Mint a short-lived single-purpose JWT for magic-link login."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "tenant_id": tenant_id,
        "type": _MAGIC_TYPE,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=_MAGIC_TTL_MINUTES)).timestamp()),
    }
    return _jwt.encode(payload, _secret(), algorithm=_ALGO)


def decode_magic_link_token(token: str) -> tuple[int, int]:
    """Verify + decode a magic-link JWT. Returns (user_id, tenant_id). Raises on any
    failure (bad sig, expired, wrong type)."""
    try:
        payload = _jwt.decode(token, _secret(), algorithms=[_ALGO])
    except _jwt.InvalidTokenError as e:
        raise InvalidToken(f"magic link invalid: {e}") from e
    if payload.get("type") != _MAGIC_TYPE:
        raise InvalidToken("magic link wrong token type")
    return int(payload["sub"]), int(payload["tenant_id"])
