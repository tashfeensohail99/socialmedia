"""Schedule + PostingAttempt models.

A `Schedule` says "post N should go live at time T to platforms [a, b, c]".
The worker polls this table every minute and dispatches posting attempts.
Each `PostingAttempt` is one platform's outcome — success, failure, rate limit,
or retry-pending.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sma.db.base import Base, TenantOwned


class ScheduleStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    CANCELLED = "cancelled"


class AttemptStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    RATE_LIMITED = "rate_limited"
    RETRY_PENDING = "retry_pending"


class Schedule(Base, TenantOwned):
    __tablename__ = "schedules"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    post_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True
    )

    scheduled_for_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    platforms_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=ScheduleStatus.PENDING.value, index=True
    )
    attempts_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    attempts: Mapped[list["PostingAttempt"]] = relationship(
        back_populates="schedule", cascade="all, delete-orphan"
    )


class PostingAttempt(Base, TenantOwned):
    """One outcome of posting to one platform for one schedule.

    `schedule_id` is nullable so we can also record "post-now" attempts
    (operator triggered immediate posts that bypass the schedule entirely).
    """

    __tablename__ = "posting_attempts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    schedule_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("schedules.id", ondelete="CASCADE"), nullable=True, index=True
    )
    post_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=True, index=True
    )

    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    attempted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    external_post_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    response_log: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    error: Mapped[str] = mapped_column(Text, nullable=False, default="")

    schedule: Mapped[Schedule] = relationship(back_populates="attempts")
