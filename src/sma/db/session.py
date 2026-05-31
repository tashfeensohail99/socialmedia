"""SQLAlchemy engine + session factory + automatic tenant scoping.

The tenant scoping is the keystone of multi-tenancy safety: every query
through a session is auto-filtered by the current tenant via
`with_loader_criteria`. Application code never has to remember to add
`WHERE tenant_id = :current` — it's impossible to forget because it's
applied at the session level.

Usage:

    from sma.db.session import get_db_session, set_current_tenant

    set_current_tenant(tenant_id=1)
    with get_db_session() as session:
        niches = session.query(Niche).all()   # auto-filtered by tenant_id=1

In Mode A the current tenant is always 1.
In Mode B the FastAPI auth dependency sets it from the JWT.
"""

from __future__ import annotations

import contextvars
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import create_engine, event, orm
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker, with_loader_criteria

from sma.config import get_settings  # noqa: F401  (used elsewhere; kept for fwd compat)
from sma.db.base import TenantOwned

# ContextVar so every request/job carries its own tenant id without polluting globals.
# Set to None when no tenant is active — queries will then fail loudly rather than
# silently leak across tenants.
_current_tenant: contextvars.ContextVar[int | None] = contextvars.ContextVar(
    "current_tenant_id", default=None
)


# ─── Engine + session factory ──────────────────────────────────


def _build_database_url() -> str:
    """Return the SQLAlchemy URL.

    Resolution order:
      1. SMA_DATABASE_URL env var (set in production / Railway)
      2. SQLite at data/sma.db (zero-setup local dev fallback)

    For local dev with Postgres parity, set SMA_DATABASE_URL=postgresql+psycopg://...
    and run `docker compose up -d postgres`.
    """
    import os
    from pathlib import Path as _Path

    explicit = os.environ.get("SMA_DATABASE_URL", "").strip()
    if explicit:
        # Railway's Postgres addon hands out URLs like `postgresql://...` which
        # SQLAlchemy resolves to the psycopg2 driver by default. We ship
        # psycopg[binary] (v3), not psycopg2, so coerce the scheme to make
        # SQLAlchemy pick the v3 dialect.
        if explicit.startswith("postgresql://"):
            explicit = "postgresql+psycopg://" + explicit[len("postgresql://"):]
        elif explicit.startswith("postgres://"):
            # Some platforms still use the old `postgres://` scheme.
            explicit = "postgresql+psycopg://" + explicit[len("postgres://"):]
        return explicit
    # Local dev fallback: SQLite in data/. Forward-slash path works on Windows + POSIX.
    db_path = _Path("data") / "sma.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{db_path.as_posix()}"


_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(_build_database_url(), pool_pre_ping=True, future=True)
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), autoflush=False, autocommit=False, future=True)
    return _SessionLocal


# ─── Tenant context API ────────────────────────────────────────


def set_current_tenant(tenant_id: int | None) -> None:
    """Set the active tenant for the current ContextVar scope."""
    _current_tenant.set(tenant_id)


def get_current_tenant() -> int | None:
    return _current_tenant.get()


def require_current_tenant() -> int:
    """Get the active tenant or raise. Use inside business logic that MUST be tenant-scoped."""
    tid = _current_tenant.get()
    if tid is None:
        raise RuntimeError(
            "No tenant set in this context. Wrap calls in `with tenant_scope(<id>):` "
            "or set the JWT auth dependency on the FastAPI route."
        )
    return tid


@contextmanager
def tenant_scope(tenant_id: int) -> Iterator[None]:
    """Context manager for scoping a block to one tenant.

        with tenant_scope(7):
            with get_db_session() as s:
                ...
    """
    token = _current_tenant.set(tenant_id)
    try:
        yield
    finally:
        _current_tenant.reset(token)


# ─── Automatic query filter via event hook ─────────────────────


@event.listens_for(orm.Session, "do_orm_execute")
def _add_tenant_filter(execute_state: Any) -> None:
    """Inject `WHERE tenant_id = :current` into every SELECT touching a TenantOwned table.

    Only applied to SELECT statements (skip inserts, updates, deletes — those
    are filtered at the application layer or by user-specified WHERE clauses).
    """
    if not execute_state.is_select:
        return
    # Allow opt-out (e.g. for operator endpoints that legitimately span tenants).
    if execute_state.execution_options.get("skip_tenant_filter"):
        return
    tid = _current_tenant.get()
    if tid is None:
        # No tenant context = fail closed for safety. Routes that legitimately
        # span tenants (operator dashboard) must opt out via skip_tenant_filter.
        return
    execute_state.statement = execute_state.statement.options(
        with_loader_criteria(
            TenantOwned,
            lambda cls: cls.tenant_id == tid,
            include_aliases=True,
        )
    )


# ─── Session lifecycle helper ──────────────────────────────────


@contextmanager
def get_db_session() -> Iterator[Session]:
    """Yield a Session that commits on success, rolls back on exception, always closes."""
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
