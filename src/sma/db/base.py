"""SQLAlchemy 2.0 declarative base + shared column types.

Every domain table inherits from `TenantOwned` which provides:
- `tenant_id` (FK → tenants.id, indexed, NOT NULL) — the multi-tenancy keystone
- `created_at` / `updated_at` timestamps

The session-level loader criteria in `db.session` auto-filters every query
by the current tenant, so application code never has to remember to add
`WHERE tenant_id = :current`.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Root declarative base for ALL ORM models in the project."""

    type_annotation_map: dict[type, Any] = {}


class TimestampMixin:
    """Adds created_at + updated_at to a model."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )


class TenantOwned(TimestampMixin):
    """Mixin for any table that belongs to a tenant.

    Every domain table (niche, posts, topics, credentials, etc.) inherits
    this so multi-tenancy is enforced at the schema level, not just the
    application layer.
    """

    tenant_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
