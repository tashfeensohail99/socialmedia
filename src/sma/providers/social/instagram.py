"""Instagram poster — Graph API. Requires a public URL for the video file.

The MediaUploader abstraction lets the customer plug in R2 / S3 / Dropbox /
their own server. In Phase 1 you can use the LocalMediaUploader if your
backend is reachable from the public internet; otherwise configure R2.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Protocol

import httpx
from loguru import logger
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from sma.providers.social.base import PostResult


class MediaUploader(Protocol):
    """Returns a public HTTPS URL for a local file."""

    def upload(self, file_path: Path) -> str: ...


class InstagramPoster:
    platform = "instagram"

    def __init__(
        self,
        page_token: str,
        ig_user_id: str,
        media_uploader: MediaUploader,
        graph_version: str = "v21.0",
    ) -> None:
        if not page_token or not ig_user_id:
            raise ValueError("Instagram requires page_token and ig_user_id")
        self._token = page_token
        self._user_id = ig_user_id
        self._uploader = media_uploader
        self._base = f"https://graph.facebook.com/{graph_version}"

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
            video_url = self._uploader.upload(video_path)
            container_id = self._create_container(video_url, full_caption, is_short)
            self._wait_for_ready(container_id)
            media_id = self._publish_container(container_id)
            return PostResult(
                success=True,
                platform=self.platform,
                external_post_id=media_id,
                url=f"https://www.instagram.com/reel/{media_id}/",
            )
        except httpx.HTTPError as e:
            return PostResult(success=False, platform=self.platform, error=str(e))
        except Exception as e:
            return PostResult(success=False, platform=self.platform, error=str(e))

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=2, max=10),
        retry=retry_if_exception_type(httpx.HTTPError),
        reraise=True,
    )
    def _create_container(self, video_url: str, caption: str, is_short: bool) -> str:
        params = {
            "media_type": "REELS" if is_short else "VIDEO",
            "video_url": video_url,
            "caption": caption,
            "access_token": self._token,
        }
        with httpx.Client(timeout=60.0) as client:
            r = client.post(f"{self._base}/{self._user_id}/media", params=params)
            r.raise_for_status()
            return r.json()["id"]

    def _wait_for_ready(self, container_id: str, timeout_sec: float = 180.0) -> None:
        """Instagram async-processes the upload; poll until status_code=FINISHED."""
        deadline = time.monotonic() + timeout_sec
        while time.monotonic() < deadline:
            with httpx.Client(timeout=15.0) as client:
                r = client.get(
                    f"{self._base}/{container_id}",
                    params={"fields": "status_code", "access_token": self._token},
                )
                r.raise_for_status()
                status = r.json().get("status_code")
                if status == "FINISHED":
                    return
                if status == "ERROR":
                    raise RuntimeError(f"Instagram processing failed for container {container_id}")
            time.sleep(5)
        raise TimeoutError(f"Instagram container {container_id} not ready after {timeout_sec}s")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=2, max=10),
        retry=retry_if_exception_type(httpx.HTTPError),
        reraise=True,
    )
    def _publish_container(self, container_id: str) -> str:
        with httpx.Client(timeout=30.0) as client:
            r = client.post(
                f"{self._base}/{self._user_id}/media_publish",
                params={"creation_id": container_id, "access_token": self._token},
            )
            r.raise_for_status()
            return r.json()["id"]

    @staticmethod
    def _compose(caption: str, hashtags: list[str]) -> str:
        tags = " ".join(f"#{t}" for t in hashtags)
        return f"{caption.rstrip()}\n\n{tags}".strip()
