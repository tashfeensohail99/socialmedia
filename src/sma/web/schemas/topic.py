"""Pydantic schemas for Topics + TopicSources."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from sma.web.schemas.common import TimestampedRead


# ─── Topic sources ─────────────────────────────────────────────


class TopicSourceCreate(BaseModel):
    niche_id: int
    kind: str = Field(..., description="ai_generated | manual | rss | news")
    config_json: dict = Field(default_factory=dict)
    enabled: bool = True


class TopicSourceUpdate(BaseModel):
    kind: str | None = None
    config_json: dict | None = None
    enabled: bool | None = None


class TopicSourceRead(TimestampedRead):
    id: int
    tenant_id: int
    niche_id: int
    kind: str
    config_json: dict
    enabled: bool
    last_run_at: datetime | None = None


# ─── Topics ────────────────────────────────────────────────────


class TopicRead(TimestampedRead):
    id: int
    tenant_id: int
    source_id: int | None = None
    content_hash: str
    title: str
    content: str
    metadata_json: dict
    score: float | None = None
    score_reason: str = ""
    suggested_angle: str = ""
    status: str
    used_for_post_id: int | None = None


class TopicCreate(BaseModel):
    """Manual topic — bypasses discovery sources."""

    title: str
    content: str = ""
    metadata_json: dict = Field(default_factory=dict)
