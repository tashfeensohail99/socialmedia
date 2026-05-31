"""AI-generated topic source — the default for SaaS.

Asks the LLM to generate fresh topic ideas tailored to the niche. Zero external
dependencies beyond an LLM key. Perfect for users who don't want to set up RSS
feeds or news APIs.
"""

from __future__ import annotations

import json

from loguru import logger

from sma.core.niche.config import NicheConfig
from sma.core.templates import render
from sma.core.topics.base import Topic
from sma.providers.llm.base import LLMProvider


class AIGeneratedTopicSource:
    kind = "ai_generated"

    def __init__(self, count: int = 10) -> None:
        self.count = count

    def discover(
        self,
        niche: NicheConfig,
        llm: LLMProvider,
        recent_topic_titles: list[str] | None = None,
    ) -> list[Topic]:
        prompt = render(
            "ai_topic_generation.j2",
            niche=niche,
            count=self.count,
            recent_topics=recent_topic_titles or [],
        )
        resp = llm.complete(
            system="You generate distinct, hook-driven content topics. Return only valid JSON.",
            user=prompt,
            model=niche.llm_model,
            temperature=0.9,
            json_mode=True,
        )

        try:
            data = json.loads(resp.text)
            raw_topics = data.get("topics", [])
        except json.JSONDecodeError as e:
            logger.error(f"AI topic generation returned invalid JSON: {e}\n{resp.text[:500]}")
            return []

        topics = []
        for item in raw_topics:
            if not isinstance(item, dict) or "title" not in item:
                continue
            topics.append(
                Topic(
                    title=item["title"],
                    content=item.get("content", ""),
                    source=self.kind,
                )
            )
        logger.info(f"AI generated {len(topics)} topics for niche {niche.name!r}")
        return topics
