"""Usage event schema. Records every external API call's cost for the cost dashboard."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class UsageEvent:
    """One row per external API call. Powers the per-tenant cost dashboard.

    In Phase 1 these are appended to data/usage/events.jsonl.
    In Phase 2 they're inserted into the `usage_events` Postgres table.
    """

    provider: str           # "openai" | "elevenlabs" | "nano_banana" | ...
    model: str              # "gpt-4o-mini" | "eleven_turbo_v2" | ...
    operation: str          # "complete" | "synthesize" | "generate" | ...

    tokens_in: int = 0
    tokens_out: int = 0
    units: int = 0          # for non-token providers (chars, seconds, images)

    cost_usd: float = 0.0

    tenant_id: int = 1      # always 1 in single-tenant mode
    post_id: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["timestamp"] = self.timestamp.isoformat()
        return d
