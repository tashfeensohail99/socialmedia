"""Health + version endpoints. No auth required."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from sma import __version__
from sma.config import get_settings
from sma.db.session import get_session_factory

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    version: str
    deployment_mode: str
    db_ok: bool


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Liveness probe. Tests DB connectivity too so Railway / Render get a real signal."""
    settings = get_settings()
    db_ok = True
    try:
        SessionLocal = get_session_factory()
        with SessionLocal() as session:
            session.execute(text("SELECT 1"))
    except Exception:
        db_ok = False
    return HealthResponse(
        status="ok" if db_ok else "degraded",
        version=__version__,
        deployment_mode=settings.deployment_mode.value,
        db_ok=db_ok,
    )
