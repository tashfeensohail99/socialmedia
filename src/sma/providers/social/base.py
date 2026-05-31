"""Social poster protocol — uniform interface across IG, FB, YouTube, TikTok."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Protocol, runtime_checkable

Platform = Literal["instagram", "facebook", "youtube", "tiktok"]


@dataclass
class PostResult:
    success: bool
    platform: Platform
    external_post_id: str | None = None
    url: str | None = None
    error: str | None = None
    raw_response: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class SocialPoster(Protocol):
    """Implementations: instagram, facebook, youtube, tiktok."""

    platform: Platform

    def post_video(
        self,
        video_path: Path,
        caption: str,
        hashtags: list[str],
        thumbnail_path: Path | None = None,
        is_short: bool = True,
    ) -> PostResult: ...
