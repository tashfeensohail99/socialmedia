"""User model. One admin per tenant in Mode A; one signup → one user in Mode B."""

from __future__ import annotations

from enum import Enum

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sma.db.base import Base, TimestampMixin
from sma.db.models.tenant import Tenant


class UserRole(str, Enum):
    ADMIN = "admin"      # Tenant owner — full access to their tenant
    MEMBER = "member"    # Reserved for future team feature
    OPERATOR = "operator"  # Mode B only — the platform operator (you), can see all tenants


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )

    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default=UserRole.ADMIN.value)
    email_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    tenant: Mapped[Tenant] = relationship(back_populates="users")
