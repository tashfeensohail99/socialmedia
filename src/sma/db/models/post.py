"""Post + MediaAsset models.

A `Post` is one generated unit of content (caption + video + thumbnail + metadata).
`MediaAsset` rows reference the individual files (image scenes, voiceover, music,
final video, thumbnail).
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sma.db.base import Base, TenantOwned


class PostStatus(str, Enum):
    QUEUED = "queued"          # waiting for the worker to process
    GENERATING = "generating"  # pipeline running now
    READY = "ready"            # video + caption ready, not yet scheduled/posted
    SCHEDULED = "scheduled"    # has a Schedule row pointing at it
    POSTED = "posted"          # at least one platform successfully posted
    FAILED = "failed"          # pipeline crashed; see error_log


class Post(Base, TenantOwned):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    niche_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("niches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    topic_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("topics.id", ondelete="SET NULL"), nullable=True
    )

    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=PostStatus.QUEUED.value, index=True
    )
    video_length: Mapped[str] = mapped_column(String(16), nullable=False, default="short")
    video_format: Mapped[str] = mapped_column(
        String(32), nullable=False, default="vertical_9_16"
    )  # vertical_9_16 | horizontal_16_9

    # Generated content
    caption: Mapped[str] = mapped_column(Text, nullable=False, default="")
    hashtags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    narrative_script: Mapped[str] = mapped_column(Text, nullable=False, default="")
    hook_text: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    story_beats_json: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)

    # Provider snapshot (what was used when this post was generated)
    llm_model: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    image_provider: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    voice_provider: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    music_provider: Mapped[str | None] = mapped_column(String(32), nullable=True)

    duration_sec: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    image_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    media_cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_log: Mapped[str] = mapped_column(Text, nullable=False, default="")

    assets: Mapped[list["MediaAsset"]] = relationship(
        back_populates="post", cascade="all, delete-orphan"
    )


class MediaAsset(Base, TenantOwned):
    """One media file (image / voiceover / music / video / thumbnail)."""

    __tablename__ = "media_assets"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    post_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True
    )

    kind: Mapped[str] = mapped_column(String(16), nullable=False)  # image/voiceover/music/video/thumbnail
    path_or_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)

    post: Mapped[Post] = relationship(back_populates="assets")
