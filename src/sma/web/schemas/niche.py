"""Pydantic schemas for the Niche resource."""

from __future__ import annotations

from pydantic import BaseModel, Field

from sma.web.schemas.common import TimestampedRead


class _NicheBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    description: str
    target_audience: str
    tone: str = "friendly, informative"
    language: str = "en"

    content_pillars: list[str] = Field(default_factory=list)
    forbidden_topics: list[str] = Field(default_factory=list)
    cta: str = ""
    hashtag_seeds: list[str] = Field(default_factory=list)

    video_length_default: str = "short"  # short | long
    image_aspect_default: str = "9:16"
    image_count_short: int = 10
    image_count_long: int = 20

    llm_provider: str = "openai"
    llm_model: str = "gpt-4o-mini"
    image_provider: str = "pexels"
    voice_provider: str = "elevenlabs"
    voice_id: str = ""
    voice_model: str | None = None
    music_provider: str = "elevenlabs"
    music_enabled: bool = True

    topic_score_threshold: float = 7.0


class NicheCreate(_NicheBase):
    """Payload for POST /api/niches."""


class NicheUpdate(BaseModel):
    """All fields optional — only updates what's provided."""

    name: str | None = None
    description: str | None = None
    target_audience: str | None = None
    tone: str | None = None
    language: str | None = None

    content_pillars: list[str] | None = None
    forbidden_topics: list[str] | None = None
    cta: str | None = None
    hashtag_seeds: list[str] | None = None

    video_length_default: str | None = None
    image_aspect_default: str | None = None
    image_count_short: int | None = None
    image_count_long: int | None = None

    llm_provider: str | None = None
    llm_model: str | None = None
    image_provider: str | None = None
    voice_provider: str | None = None
    voice_id: str | None = None
    voice_model: str | None = None
    music_provider: str | None = None
    music_enabled: bool | None = None

    topic_score_threshold: float | None = None


class NicheRead(_NicheBase, TimestampedRead):
    """Returned by GET /api/niches and GET /api/niches/:id."""

    id: int
    tenant_id: int
