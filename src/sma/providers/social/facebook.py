"""Facebook Page poster — Graph API videos endpoint. Direct upload, no public URL needed."""

from __future__ import annotations

from pathlib import Path

import httpx
from loguru import logger
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from sma.providers.social.base import PostResult


class FacebookPoster:
    platform = "facebook"

    def __init__(
        self,
        page_token: str,
        page_id: str,
        graph_version: str = "v21.0",
    ) -> None:
        if not page_token or not page_id:
            raise ValueError("Facebook requires page_token and page_id")
        self._token = page_token
        self._page_id = page_id
        self._base = f"https://graph.facebook.com/{graph_version}"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=2, max=15),
        retry=retry_if_exception_type(httpx.HTTPError),
        reraise=True,
    )
    def post_video(
        self,
        video_path: Path,
        caption: str,
        hashtags: list[str],
        thumbnail_path: Path | None = None,
        is_short: bool = True,
    ) -> PostResult:
        full_caption = self._compose(caption, hashtags)
        try:
            with httpx.Client(timeout=300.0) as client, video_path.open("rb") as f:
                files = {"source": (video_path.name, f, "video/mp4")}
                data = {"description": full_caption, "access_token": self._token}
                r = client.post(f"{self._base}/{self._page_id}/videos", data=data, files=files)
                r.raise_for_status()
                resp_json = r.json()
                video_id = resp_json.get("id")
                return PostResult(
                    success=True,
                    platform=self.platform,
                    external_post_id=video_id,
                    url=f"https://www.facebook.com/{self._page_id}/videos/{video_id}",
                    raw_response=resp_json,
                )
        except httpx.HTTPError as e:
            logger.error(f"Facebook post failed: {e}")
            return PostResult(success=False, platform=self.platform, error=str(e))

    @staticmethod
    def _compose(caption: str, hashtags: list[str]) -> str:
        tags = " ".join(f"#{t}" for t in hashtags)
        return f"{caption.rstrip()}\n\n{tags}".strip()
