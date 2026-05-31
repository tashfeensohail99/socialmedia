"""RSS topic source — pulls items from a list of feeds the user provides."""

from __future__ import annotations

import feedparser
from loguru import logger

from sma.core.niche.config import NicheConfig
from sma.core.topics.base import Topic
from sma.providers.llm.base import LLMProvider


class RSSTopicSource:
    kind = "rss"

    def __init__(self, feed_urls: list[str], items_per_feed: int = 10) -> None:
        self.feed_urls = feed_urls
        self.items_per_feed = items_per_feed

    def discover(
        self,
        niche: NicheConfig,
        llm: LLMProvider,
        recent_topic_titles: list[str] | None = None,
    ) -> list[Topic]:
        topics: list[Topic] = []
        for url in self.feed_urls:
            try:
                parsed = feedparser.parse(url)
            except Exception as e:
                logger.error(f"Failed to fetch RSS feed {url}: {e}")
                continue

            for entry in parsed.entries[: self.items_per_feed]:
                title = getattr(entry, "title", "").strip()
                if not title:
                    continue
                summary = getattr(entry, "summary", "") or getattr(entry, "description", "")
                topics.append(
                    Topic(
                        title=title,
                        content=summary,
                        source=self.kind,
                        metadata={
                            "feed_url": url,
                            "link": getattr(entry, "link", ""),
                            "published": getattr(entry, "published", ""),
                        },
                    )
                )

        logger.info(f"RSS source pulled {len(topics)} items from {len(self.feed_urls)} feed(s)")
        return topics
