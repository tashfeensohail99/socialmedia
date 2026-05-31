"""Topic abstraction. A Topic is the input to the content pipeline."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol, runtime_checkable

from sma.core.niche.config import NicheConfig
from sma.providers.llm.base import LLMProvider


@dataclass
class Topic:
    title: str
    content: str
    source: str  # which TopicSource produced it ("ai_generated", "rss", ...)
    score: float | None = None
    score_reason: str = ""
    suggested_angle: str = ""
    discovered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def id(self) -> str:
        """Stable hash for de-duplication. Title+content body."""
        h = hashlib.sha256(f"{self.title}\n{self.content}".encode()).hexdigest()
        return h[:16]

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["discovered_at"] = self.discovered_at.isoformat()
        d["id"] = self.id
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Topic:
        d = dict(d)  # copy
        d.pop("id", None)
        if isinstance(d.get("discovered_at"), str):
            d["discovered_at"] = datetime.fromisoformat(d["discovered_at"])
        return cls(**d)


@runtime_checkable
class TopicSource(Protocol):
    """Discovers candidate topics for a given niche."""

    kind: str  # "ai_generated" | "manual" | "rss" | "news"

    def discover(
        self,
        niche: NicheConfig,
        llm: LLMProvider,
        recent_topic_titles: list[str] | None = None,
    ) -> list[Topic]: ...


def dump_topics(topics: list[Topic], path) -> None:
    """Persist topics to a JSONL file (Phase 1 storage)."""
    from pathlib import Path
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        for t in topics:
            f.write(json.dumps(t.to_dict(), separators=(",", ":")) + "\n")
