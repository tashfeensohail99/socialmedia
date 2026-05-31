"""Tenant model — the root of multi-tenancy.

In Mode A (single_tenant) there's exactly one row, id=1.
In Mode B (multi_tenant) one row per subscriber, linked to a Whop membership.

Every other domain table has a `tenant_id` FK pointing here.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sma.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from sma.db.models.user import User


class SubscriptionStatus(str, Enum):
    """Maps to Whop's membership status with two added states."""

    NONE = "none"            # Mode A — no billing
    TRIALING = "trialing"    # Mode B — Whop status `trialing`
    ACTIVE = "active"        # Mode B — Whop status `valid`
    PAST_DUE = "past_due"    # Mode B — Whop status `past_due`
    CANCELLED = "cancelled"  # Mode B — Whop status `canceled` / `expired`


ACTIVE_STATUSES = {SubscriptionStatus.NONE.value, SubscriptionStatus.TRIALING.value, SubscriptionStatus.ACTIVE.value}
"""Statuses that grant access to the product."""


def whop_status_to_subscription_status(whop_status: str | None) -> str:
    """Map a Whop membership.status string to our SubscriptionStatus enum value."""
    if not whop_status:
        return SubscriptionStatus.CANCELLED.value
    s = whop_status.lower()
    if s in {"valid", "active"}:
        return SubscriptionStatus.ACTIVE.value
    if s in {"trialing", "trial"}:
        return SubscriptionStatus.TRIALING.value
    if s in {"past_due", "unpaid"}:
        return SubscriptionStatus.PAST_DUE.value
    # canceled / expired / drafted / completed / anything else
    return SubscriptionStatus.CANCELLED.value


class Tenant(Base, TimestampMixin):
    """One tenant = one customer's isolated workspace."""

    __tablename__ = "tenants"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)

    subscription_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=SubscriptionStatus.NONE.value
    )
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Whop linkage (Mode B only — null in Mode A).
    # `whop_user_id` identifies the BUYER (Whop's user, stable across subscriptions).
    # `whop_membership_id` identifies the SUBSCRIPTION row (one buyer can in theory have
    # multiple memberships on different products).
    # `whop_product_id` lets us recognize tier when we add multi-tier pricing later.
    whop_user_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    whop_membership_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, unique=True, index=True
    )
    whop_product_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    whop_status_raw: Mapped[str | None] = mapped_column(String(32), nullable=True)
    whop_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Daily generation limits (user-configurable via /api/me/config)
    daily_short_videos: Mapped[int] = mapped_column(default=3, nullable=False)
    daily_long_videos: Mapped[int] = mapped_column(default=0, nullable=False)

    # Relationships
    users: Mapped[list["User"]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan"
    )
