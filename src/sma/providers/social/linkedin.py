"""LinkedIn poster — UGC video posting via the Posts API.

LinkedIn video upload is a 3-step dance:
  1. POST /rest/videos?action=initializeUpload  → upload URLs + asset urn
  2. PUT chunks to each upload URL              → returns ETags
  3. POST /rest/videos?action=finalizeUpload    → finalize with ETags
  4. POST /rest/posts with the video asset urn  → actually publish

Requires an OAuth access_token with `w_member_social` (post as member) or
`w_organization_social` (post as company page) scope. The author URN is either
`urn:li:person:{member_id}` for members or `urn:li:organization:{org_id}` for
company pages.

Long-format friendly: LinkedIn accepts 16:9 horizontal video up to 10 minutes
on member feeds, up to 30 minutes on company pages.

Phase 1 status: working end-to-end for member posts when access_token + author_urn
are supplied. Token acquisition (3-legged OAuth) is the customer's responsibility
in Mode A; in Mode B (SaaS) you'll wire the master OAuth flow in Phase 5.
"""

from __future__ import annotations

import math
from pathlib import Path

import httpx
from loguru import logger
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from sma.providers.social.base import PostResult

_API_BASE = "https://api.linkedin.com/rest"
_API_VERSION = "202504"  # LinkedIn versioned API header
_HEADERS_BASE = {
    "LinkedIn-Version": _API_VERSION,
    "X-Restli-Protocol-Version": "2.0.0",
}


class LinkedInPoster:
    platform = "linkedin"

    def __init__(self, access_token: str, author_urn: str) -> None:
        if not access_token or not author_urn:
            raise ValueError("LinkedIn requires access_token and author_urn")
        if not author_urn.startswith(("urn:li:person:", "urn:li:organization:")):
            raise ValueError(
                "LinkedIn author_urn must look like 'urn:li:person:<id>' "
                "or 'urn:li:organization:<id>'"
            )
        self._token = access_token
        self._author = author_urn

    def post_video(
        self,
        video_path: Path,
        caption: str,
        hashtags: list[str],
        thumbnail_path: Path | None = None,
        is_short: bool = True,  # LinkedIn doesn't have a "shorts" notion; param ignored
    ) -> PostResult:
        full_caption = self._compose(caption, hashtags)
        try:
            file_size = video_path.stat().st_size
            init = self._init_upload(file_size)
            video_urn = init["video"]
            upload_instructions = init["uploadInstructions"]

            etags = self._upload_chunks(video_path, upload_instructions)
            self._finalize_upload(video_urn, etags)
            post_urn = self._create_post(video_urn, full_caption)

            # LinkedIn doesn't return a public URL per post — only an activity URN.
            # The post is visible on the author's profile feed.
            return PostResult(
                success=True,
                platform=self.platform,
                external_post_id=post_urn,
                url=None,
            )
        except (httpx.HTTPError, RuntimeError, KeyError) as e:
            logger.error(f"LinkedIn post failed: {e}")
            return PostResult(success=False, platform=self.platform, error=str(e))

    # ─── upload steps ──────────────────────────────────────────────

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=2, max=10),
        retry=retry_if_exception_type(httpx.HTTPError),
        reraise=True,
    )
    def _init_upload(self, file_size: int) -> dict:
        payload = {
            "initializeUploadRequest": {
                "owner": self._author,
                "fileSizeBytes": file_size,
                "uploadCaptions": False,
                "uploadThumbnail": False,
            }
        }
        with httpx.Client(timeout=30.0) as client:
            r = client.post(
                f"{_API_BASE}/videos?action=initializeUpload",
                headers={**_HEADERS_BASE, "Authorization": f"Bearer {self._token}"},
                json=payload,
            )
            r.raise_for_status()
            data = r.json().get("value", {})
            if "video" not in data or "uploadInstructions" not in data:
                raise RuntimeError(f"LinkedIn init missing fields: {r.text[:300]}")
            return data

    def _upload_chunks(self, video_path: Path, instructions: list[dict]) -> list[str]:
        """Upload each declared chunk via PUT to its signed URL. Collect ETags."""
        etags: list[str] = []
        with video_path.open("rb") as f, httpx.Client(timeout=300.0) as client:
            for chunk_info in instructions:
                upload_url = chunk_info["uploadUrl"]
                first = int(chunk_info.get("firstByte", 0))
                last = int(chunk_info.get("lastByte", 0))
                length = last - first + 1
                f.seek(first)
                payload = f.read(length)
                r = client.put(upload_url, content=payload)
                if r.status_code not in (200, 201, 206):
                    raise RuntimeError(
                        f"LinkedIn chunk upload failed: {r.status_code} {r.text[:200]}"
                    )
                etag = r.headers.get("etag") or r.headers.get("ETag")
                if not etag:
                    raise RuntimeError("LinkedIn chunk response missing ETag header")
                etags.append(etag)
        return etags

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=2, max=10),
        retry=retry_if_exception_type(httpx.HTTPError),
        reraise=True,
    )
    def _finalize_upload(self, video_urn: str, etags: list[str]) -> None:
        payload = {
            "finalizeUploadRequest": {
                "video": video_urn,
                "uploadToken": "",
                "uploadedPartIds": etags,
            }
        }
        with httpx.Client(timeout=60.0) as client:
            r = client.post(
                f"{_API_BASE}/videos?action=finalizeUpload",
                headers={**_HEADERS_BASE, "Authorization": f"Bearer {self._token}"},
                json=payload,
            )
            r.raise_for_status()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=2, max=10),
        retry=retry_if_exception_type(httpx.HTTPError),
        reraise=True,
    )
    def _create_post(self, video_urn: str, caption: str) -> str:
        payload = {
            "author": self._author,
            "commentary": caption[:3000],  # LinkedIn caption limit
            "visibility": "PUBLIC",
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": [],
            },
            "content": {"media": {"id": video_urn}},
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False,
        }
        with httpx.Client(timeout=30.0) as client:
            r = client.post(
                f"{_API_BASE}/posts",
                headers={**_HEADERS_BASE, "Authorization": f"Bearer {self._token}"},
                json=payload,
            )
            r.raise_for_status()
            # The post URN is in the x-restli-id header.
            post_urn = r.headers.get("x-restli-id") or r.json().get("id", "")
            return post_urn

    @staticmethod
    def _compose(caption: str, hashtags: list[str]) -> str:
        tags = " ".join(f"#{t}" for t in hashtags)
        return f"{caption.rstrip()}\n\n{tags}".strip()
