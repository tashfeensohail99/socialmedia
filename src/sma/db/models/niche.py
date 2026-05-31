"""Niche model — the personality + provider config for a content stream.

One tenant can have multiple niches (e.g. one Instagram channel + one YouTube
channel under the same tenant umbrella).

Fields mirror sma.core.niche.config.NicheConfig 1:1 so we can map between
them in either direction (DB → engine input, engine input → DB).
"""

from __future__ import annotations

from sqlalchemy import JSON, Boolean, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from sma.db.base import Base, TenantOwned


class Niche(Base, TenantOwned):
    __tablename__ = "niches"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    target_audience: Mapped[str] = mapped_column(Text, nullable=False)
    tone: Mapped[str] = mapped_column(String(255), nullable=False, default="friendly, informative")
    language: Mapped[str] = mapped_column(String(8), nullable=False, default="en")

    content_pillars: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    forbidden_topics: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    cta: Mapped[str] = mapped_column(Text, nullable=False, default="")
    hashtag_seeds: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    # Output preferences
    video_length_default: Mapped[str] = mapped_column(String(16), nullable=False, default="short")
    image_aspect_default: Mapped[str] = mapped_column(String(8), nullable=False, default="9:16")
    image_count_short: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    image_count_long: Mapped[int] = mapped_column(Integer, nullable=False, default=20)

    # Provider selection
    llm_provider: Mapped[str] = mapped_column(String(32), nullable=False, default="openai")
    llm_model: Mapped[str] = mapped_column(String(64), nullable=False, default="gpt-4o-mini")

    image_provider: Mapped[str] = mapped_column(String(32), nullable=False, default="pexels")

    voice_provider: Mapped[str] = mapped_column(String(32), nullable=False, default="elevenlabs")
    voice_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    voice_model: Mapped[str | None] = mapped_column(String(64), nullable=True)

    music_provider: Mapped[str] = mapped_column(String(32), nullable=False, default="elevenlabs")
    music_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    topic_score_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=7.0)
