"""Pydantic schemas for PostingRules + PromptTemplates + Usage summary."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from sma.web.schemas.common import TimestampedRead


# ─── Posting rules ────────────────────────────────────────────


class PostingRuleCreate(BaseModel):
    name: str = Field(..., max_length=64)
    type: str = Field(..., description="peak_hours | spacing | platform_priority | quiet_hours")
    params_json: dict = Field(default_factory=dict)
    enabled: bool = True


class PostingRuleUpdate(BaseModel):
    name: str | None = None
    type: str | None = None
    params_json: dict | None = None
    enabled: bool | None = None


class PostingRuleRead(TimestampedRead):
    id: int
    tenant_id: int
    name: str
    type: str
    params_json: dict
    enabled: bool


# ─── Prompt templates ────────────────────────────────────────


class PromptTemplateUpsert(BaseModel):
    """Insert or replace a tenant override for the template at `slug`."""

    slug: str = Field(..., description="story_analysis | caption | hashtags | etc.")
    body: str


class PromptTemplateRead(TimestampedRead):
    id: int
    tenant_id: int
    slug: str
    body: str
    is_default: bool


# ─── Usage summary ───────────────────────────────────────────


class UsageByProviderModel(BaseModel):
    provider: str
    model: str
    calls: int
    tokens_in: int
    tokens_out: int
    units: int
    cost_usd: float


class UsageSummary(BaseModel):
    month: str  # "2026-05"
    total_events: int
    total_cost_usd: float
    by_provider_model: list[UsageByProviderModel]
    starting_at: datetime
    ending_at: datetime
