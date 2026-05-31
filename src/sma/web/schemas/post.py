"""Pydantic schemas for Posts + Schedules + PostingAttempts."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from sma.web.schemas.common import TimestampedRead


# ─── Posts ────────────────────────────────────────────────────


class PostRead(TimestampedRead):
    id: int
    tenant_id: int
    niche_id: int
    topic_id: int | None = None
    status: str
    video_length: str
    video_format: str

    caption: str
    hashtags: list[str]
    narrative_script: str
    hook_text: str
    story_beats_json: list[dict]

    llm_model: str
    image_provider: str
    voice_provider: str
    music_provider: str | None = None

    duration_sec: float
    image_count: int
    media_cost_usd: float

    generated_at: datetime | None = None
    error_log: str = ""


# ─── Schedules ────────────────────────────────────────────────


class ScheduleCreate(BaseModel):
    post_id: int
    scheduled_for_utc: datetime
    platforms: list[str] = Field(..., min_length=1)


class ScheduleUpdate(BaseModel):
    scheduled_for_utc: datetime | None = None
    platforms: list[str] | None = None
    status: str | None = None


class ScheduleRead(TimestampedRead):
    id: int
    tenant_id: int
    post_id: int
    scheduled_for_utc: datetime
    platforms: list[str] = Field(..., alias="platforms_json")
    status: str
    attempts_count: int


# ─── Posting attempts (read-only) ─────────────────────────────


class PostingAttemptRead(TimestampedRead):
    id: int
    tenant_id: int
    schedule_id: int
    platform: str
    attempted_at: datetime
    status: str
    external_post_id: str | None = None
    response_log: dict
    error: str = ""
