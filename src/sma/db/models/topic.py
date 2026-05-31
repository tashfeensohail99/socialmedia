"""Topic + TopicSource models.

A `TopicSource` is the config for one discovery method (AI-generated, RSS,
news, manual). The worker calls each enabled source on a schedule, producing
`Topic` rows that are then scored and (if they pass threshold) turned into
`Post` rows.
"""

from __future__ import annotations

from enum import Enum

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from sma.db.base import Base, TenantOwned


class TopicStatus(str, Enum):
    DISCOVERED = "discovered"  # just pulled in, not scored yet
    SCORED = "scored"          # scored, may or may not be above threshold
    REJECTED = "rejected"      # scored below threshold or violated forbidden topics
    USED = "used"              # successfully turned into a Post


class TopicSource(Base, TenantOwned):
    """Configuration row for one topic source (one tenant can have many)."""

    __tablename__ = "topic_sources"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    niche_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("niches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)  # ai_generated/rss/news/manual
    config_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_run_at: Mapped["DateTime | None"] = mapped_column(DateTime(timezone=True), nullable=True)


class Topic(Base, TenantOwned):
    """A candidate topic discovered by a TopicSource."""

    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("topic_sources.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Stable hash from sma.core.topics.base.Topic.id (for dedup)
    content_hash: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    title: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    score_reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    suggested_angle: Mapped[str] = mapped_column(Text, nullable=False, default="")

    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=TopicStatus.DISCOVERED.value, index=True
    )
    used_for_post_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("posts.id", ondelete="SET NULL"), nullable=True
    )
