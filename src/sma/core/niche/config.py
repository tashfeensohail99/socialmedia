"""NicheConfig — the single object that drives every prompt and provider choice.

In Phase 1 it's loaded from a YAML file. In Phase 2 it's loaded per-tenant from Postgres.
The pipeline never reaches into globals — niche flows in via the PipelineContext.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

VideoLength = Literal["short", "long"]


class NicheConfig(BaseModel):
    """Configures the personality, audience, and provider preferences for a single niche."""

    # ─── Identity ──────────────────────────────────────────────
    name: str = Field(..., description="Short label, e.g. 'Daily Fitness Tips'")
    description: str = Field(..., description="Multi-paragraph context for the LLM")
    target_audience: str = Field(..., description="Who the content is for")
    tone: str = Field("friendly, informative", description="Voice / style instruction")
    language: str = "en"

    # ─── Content guidance ──────────────────────────────────────
    content_pillars: list[str] = Field(default_factory=list)
    forbidden_topics: list[str] = Field(default_factory=list)
    cta: str = ""
    hashtag_seeds: list[str] = Field(default_factory=list)

    # ─── Output preferences ────────────────────────────────────
    video_length_default: VideoLength = "short"

    # ─── Provider selection ────────────────────────────────────
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o-mini"

    image_provider: str = "pexels"  # safe free default
    image_aspect_default: str = "9:16"
    image_count_short: int = 10
    image_count_long: int = 20

    voice_provider: str = "elevenlabs"
    voice_id: str = ""  # required to be set by user; no sensible default
    voice_model: str | None = None

    music_provider: str = "elevenlabs"
    music_enabled: bool = True

    # ─── Scoring ───────────────────────────────────────────────
    topic_score_threshold: float = 7.0
