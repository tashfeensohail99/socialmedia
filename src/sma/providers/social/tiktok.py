"""TikTok poster — Content Posting API.

Uses the FILE_UPLOAD path (chunked) so we don't need a public URL like Instagram does.
Flow:
  1. POST /v2/post/publish/video/init/   → upload_url + publish_id
  2. PUT chunks to upload_url             → returns 201 when complete
  3. POLL /v2/post/publish/status/fetch/  → wait for "PUBLISH_COMPLETE"

Requires an OAuth access_token with `video.publish` and `video.upload` scopes.
"""

from __future__ import annotations

import math
import time
from pathlib import Path

import httpx
from loguru import logger
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from sma.providers.social.base import PostResult

_API_BASE = "https://open.tiktokapis.com"
# TikTok requires chunks between 5 MB and 64 MB (last chunk can be smaller).
_CHUNK_SIZE = 10 * 1024 * 1024  # 10 MB


class TikTokPoster:
    platform = "tiktok"

    def __init__(self, access_token: str, privacy_level: str = "PUBLIC_TO_EVERYONE") -> None:
        if not access_token:
            raise ValueError("TikTok access_token required")
        self._token = access_token
        # Other valid: SELF_ONLY, MUTUAL_FOLLOW_FRIENDS, FOLLOWER_OF_CREATOR
        self._privacy = privacy_level

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
            video_size = video_path.stat().st_size
            chunk_size = min(_CHUNK_SIZE, video_size)
            chunk_count = math.ceil(video_size / chunk_size)

            init = self._init_upload(
                title=full_caption,
                video_size=video_size,
                chunk_size=chunk_size,
                total_chunks=chunk_count,
            )
            upload_url = init["upload_url"]
            publish_id = init["publish_id"]

            self._upload_chunks(video_path, upload_url, video_size, chunk_size, chunk_count)
            final = self._poll_status(publish_id)

            video_id = final.get("publicaly_available_post_id") or publish_id
            return PostResult(
                success=True,
                platform=self.platform,
                external_post_id=video_id,
                url=None,  # TikTok doesn't return a stable URL via this API
                raw_response=final,
            )
        except (httpx.HTTPError, RuntimeError) as e:
            logger.error(f"TikTok post failed: {e}")
            return PostResult(success=False, platform=self.platform, error=str(e))

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=2, max=10),
        retry=retry_if_exception_type(httpx.HTTPError),
        reraise=True,
    )
    def _init_upload(
        self, *, title: str, video_size: int, chunk_size: int, total_chunks: int
    ) -> dict:
        payload = {
            "post_info": {
                "title": title[:2200],  # TikTok caption length limit
                "privacy_level": self._privacy,
                "disable_duet": False,
                "disable_comment": False,
                "disable_stitch": False,
                "video_cover_timestamp_ms": 1000,
            },
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": video_size,
                "chunk_size": chunk_size,
                "total_chunk_count": total_chunks,
            },
        }
        with httpx.Client(timeout=30.0) as client:
            r = client.post(
                f"{_API_BASE}/v2/post/publish/video/init/",
                headers={
                    "Authorization": f"Bearer {self._token}",
                    "Content-Type": "application/json; charset=UTF-8",
                },
                json=payload,
            )
            r.raise_for_status()
            data = r.json().get("data", {})
            if not data.get("upload_url") or not data.get("publish_id"):
                raise RuntimeError(f"TikTok init returned no upload info: {r.text}")
            return data

    def _upload_chunks(
        self,
        video_path: Path,
        upload_url: str,
        video_size: int,
        chunk_size: int,
        total_chunks: int,
    ) -> None:
        with httpx.Client(timeout=300.0) as client, video_path.open("rb") as f:
            for chunk_idx in range(total_chunks):
                start = chunk_idx * chunk_size
                end = min(start + chunk_size, video_size) - 1
                f.seek(start)
                chunk_data = f.read(end - start + 1)
                headers = {
                    "Content-Type": "video/mp4",
                    "Content-Length": str(len(chunk_data)),
                    "Content-Range": f"bytes {start}-{end}/{video_size}",
                }
                r = client.put(upload_url, content=chunk_data, headers=headers)
                if r.status_code not in (200, 201, 206):
                    raise RuntimeError(
                        f"TikTok chunk {chunk_idx} upload failed: {r.status_code} {r.text[:200]}"
                    )

    def _poll_status(self, publish_id: str, timeout_sec: float = 300.0) -> dict:
        deadline = time.monotonic() + timeout_sec
        while time.monotonic() < deadline:
            with httpx.Client(timeout=15.0) as client:
                r = client.post(
                    f"{_API_BASE}/v2/post/publish/status/fetch/",
                    headers={
                        "Authorization": f"Bearer {self._token}",
                        "Content-Type": "application/json; charset=UTF-8",
                    },
                    json={"publish_id": publish_id},
                )
                r.raise_for_status()
                data = r.json().get("data", {})
                status = data.get("status")
                if status == "PUBLISH_COMPLETE":
                    return data
                if status in {"FAILED", "EXPIRED"}:
                    raise RuntimeError(f"TikTok publish failed: {data}")
            time.sleep(5)
        raise TimeoutError(f"TikTok publish did not complete within {timeout_sec}s")

    @staticmethod
    def _compose(caption: str, hashtags: list[str]) -> str:
        tags = " ".join(f"#{t}" for t in hashtags)
        return f"{caption.rstrip()}\n\n{tags}".strip()
