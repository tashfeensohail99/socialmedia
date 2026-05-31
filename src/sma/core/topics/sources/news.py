"""News topic source — generalized version of the original tourism news fetcher.

Uses NewsData.io (or NewsCatcher) to pull articles matching the niche's content
pillars. Keywords are derived from the niche, not hardcoded.
"""

from __future__ import annotations

import httpx
from loguru import logger
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from sma.core.niche.config import NicheConfig
from sma.core.topics.base import Topic
from sma.providers.llm.base import LLMProvider

_NEWSDATA_BASE = "https://newsdata.io/api/1/news"


class NewsTopicSource:
    kind = "news"

    def __init__(
        self,
        api_key: str,
        provider: str = "newsdata",
        max_results: int = 20,
        language: str = "en",
    ) -> None:
        if not api_key:
            raise ValueError("News API key required")
        if provider != "newsdata":
            raise NotImplementedError("Only newsdata.io supported in Phase 1")
        self.api_key = api_key
        self.provider = provider
        self.max_results = max_results
        self.language = language

    def _build_query(self, niche: NicheConfig) -> str:
        # Use the first 3-5 content pillars as OR'd keywords.
        # Strip out any explanatory parens to keep query terse.
        terms: list[str] = []
        for pillar in niche.content_pillars[:5]:
            cleaned = pillar.split("(")[0].strip().strip(",")
            # Take first 1-3 significant words
            words = [w for w in cleaned.split() if len(w) > 3][:3]
            if words:
                terms.append(" ".join(words))
        if not terms:
            terms = [niche.name]
        return " OR ".join(f'"{t}"' for t in terms)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=2, max=15),
        retry=retry_if_exception_type((httpx.HTTPError,)),
        reraise=True,
    )
    def _fetch(self, query: str) -> list[dict]:
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(
                _NEWSDATA_BASE,
                params={
                    "apikey": self.api_key,
                    "q": query,
                    "language": self.language,
                    "size": min(self.max_results, 50),
                },
            )
            resp.raise_for_status()
            return resp.json().get("results", [])

    def discover(
        self,
        niche: NicheConfig,
        llm: LLMProvider,
        recent_topic_titles: list[str] | None = None,
    ) -> list[Topic]:
        query = self._build_query(niche)
        logger.info(f"News query for niche {niche.name!r}: {query}")
        try:
            articles = self._fetch(query)
        except httpx.HTTPError as e:
            logger.error(f"News API request failed: {e}")
            return []

        topics: list[Topic] = []
        for art in articles[: self.max_results]:
            title = (art.get("title") or "").strip()
            if not title:
                continue
            content = art.get("description") or art.get("content") or ""
            topics.append(
                Topic(
                    title=title,
                    content=content,
                    source=self.kind,
                    metadata={
                        "article_id": art.get("article_id"),
                        "link": art.get("link"),
                        "source_id": art.get("source_id"),
                        "pubDate": art.get("pubDate"),
                    },
                )
            )
        logger.info(f"News source returned {len(topics)} articles")
        return topics
