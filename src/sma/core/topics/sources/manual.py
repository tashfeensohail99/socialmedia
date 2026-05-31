"""Manual topic source — user-provided list.

Useful for batch-importing topics or when the user knows exactly what they
want covered (e.g. an editorial calendar).
"""

from __future__ import annotations

from sma.core.niche.config import NicheConfig
from sma.core.topics.base import Topic
from sma.providers.llm.base import LLMProvider


class ManualTopicSource:
    kind = "manual"

    def __init__(self, topics: list[dict[str, str]]) -> None:
        """Each dict: {"title": str, "content": str (optional)}."""
        self._raw = topics

    def discover(
        self,
        niche: NicheConfig,
        llm: LLMProvider,
        recent_topic_titles: list[str] | None = None,
    ) -> list[Topic]:
        return [
            Topic(
                title=item["title"],
                content=item.get("content", ""),
                source=self.kind,
            )
            for item in self._raw
            if item.get("title")
        ]
