"""Pexels stock image provider. Free with a dev API key."""

from __future__ import annotations

from pathlib import Path

import httpx
from loguru import logger
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from sma.providers.image.base import AspectRatio, ImageResult
from sma.usage.events import UsageEvent
from sma.usage.recorder import record

_API_BASE = "https://api.pexels.com/v1"


def _orientation_for(aspect: AspectRatio) -> str:
    return {"9:16": "portrait", "4:5": "portrait", "1:1": "square", "16:9": "landscape"}[aspect]


class PexelsProvider:
    name = "pexels"
    is_free = True

    def __init__(self, api_key: str, timeout: float = 30.0) -> None:
        if not api_key:
            raise ValueError("Pexels API key required")
        self._client = httpx.Client(
            base_url=_API_BASE,
            headers={"Authorization": api_key},
            timeout=timeout,
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=1, max=10),
        retry=retry_if_exception_type((httpx.HTTPError,)),
        reraise=True,
    )
    def _search(self, query: str, orientation: str) -> dict:
        resp = self._client.get(
            "/search",
            params={"query": query, "orientation": orientation, "per_page": 5},
        )
        resp.raise_for_status()
        return resp.json()

    def generate(
        self,
        prompts: list[str],
        aspect_ratio: AspectRatio,
        output_dir: Path,
        count: int | None = None,
    ) -> ImageResult:
        output_dir.mkdir(parents=True, exist_ok=True)
        orientation = _orientation_for(aspect_ratio)
        targets = prompts if count is None else (prompts * (count // len(prompts) + 1))[:count]

        downloaded: list[Path] = []
        sources: list[str] = []

        for idx, query in enumerate(targets):
            try:
                data = self._search(query, orientation)
                photos = data.get("photos", [])
                if not photos:
                    logger.warning(f"Pexels returned no results for query: {query!r}")
                    continue
                # Prefer the largest available; fall back through 'large' / 'original'
                photo = photos[0]
                src = photo["src"].get("large2x") or photo["src"].get("large") or photo["src"]["original"]
                out = output_dir / f"pexels_{idx:03d}_{photo['id']}.jpg"
                self._download(src, out)
                downloaded.append(out)
                sources.append(src)
            except httpx.HTTPError as e:
                logger.error(f"Pexels error for {query!r}: {e}")
                continue

        record(
            UsageEvent(
                provider=self.name,
                model="stock",
                operation="search_download",
                units=len(downloaded),
                cost_usd=0.0,
                metadata={"queries": targets[: len(downloaded)]},
            )
        )

        return ImageResult(
            paths=downloaded,
            cost_usd=0.0,
            provider=self.name,
            metadata={"sources": sources, "orientation": orientation},
        )

    def _download(self, url: str, dest: Path) -> None:
        with self._client.stream("GET", url) as r:
            r.raise_for_status()
            with dest.open("wb") as f:
                for chunk in r.iter_bytes():
                    f.write(chunk)

    def close(self) -> None:
        self._client.close()
