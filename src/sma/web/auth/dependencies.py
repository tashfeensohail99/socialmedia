"""FastAPI auth dependencies — extract user from JWT, set tenant context, etc.

Use `CurrentUser` in any protected route signature; it both validates the JWT
AND sets the tenant ContextVar so all DB queries auto-scope correctly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from sma.db.session import set_current_tenant
from sma.web.auth.jwt import InvalidToken, decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


@dataclass
class AuthedUser:
    user_id: int
    tenant_id: int
    role: str


def get_current_user(
    token: Annotated[str | None, Depends(oauth2_scheme)],
) -> AuthedUser:
    """Validate the bearer JWT, set the tenant context, return the user info."""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing or malformed Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = decode_token(token)
    except InvalidToken as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"invalid token: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e

    user_id = int(payload["sub"])
    tenant_id = int(payload["tenant_id"])
    role = str(payload["role"])

    # Critical: set tenant context for the rest of this request.
    # Every DB query through the session will auto-filter by this tenant.
    set_current_tenant(tenant_id)

    return AuthedUser(user_id=user_id, tenant_id=tenant_id, role=role)


CurrentUser = Annotated[AuthedUser, Depends(get_current_user)]


def require_operator(user: CurrentUser) -> AuthedUser:
    """Guard for operator-only routes (Mode B SaaS dashboard)."""
    if user.role != "operator":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="operator-only endpoint",
        )
    return user


CurrentOperator = Annotated[AuthedUser, Depends(require_operator)]
