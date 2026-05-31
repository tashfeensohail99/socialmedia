"""YouTube Shorts uploader. OAuth via google-auth; refresh tokens stored per account."""

from __future__ import annotations

from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from loguru import logger

from sma.providers.social.base import PostResult

YOUTUBE_UPLOAD_SCOPE = "https://www.googleapis.com/auth/youtube.upload"


class YouTubePoster:
    platform = "youtube"

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        refresh_token: str,
    ) -> None:
        if not all([client_id, client_secret, refresh_token]):
            raise ValueError("YouTube requires client_id, client_secret, refresh_token")
        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            client_id=client_id,
            client_secret=client_secret,
            token_uri="https://oauth2.googleapis.com/token",
            scopes=[YOUTUBE_UPLOAD_SCOPE],
        )
        creds.refresh(Request())
        self._service = build("youtube", "v3", credentials=creds, cache_discovery=False)

    def post_video(
        self,
        video_path: Path,
        caption: str,
        hashtags: list[str],
        thumbnail_path: Path | None = None,
        is_short: bool = True,
    ) -> PostResult:
        title = self._title_from_caption(caption)
        description = self._compose_description(caption, hashtags, is_short)
        tags = hashtags[:30]

        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": tags,
                "categoryId": "22",  # People & Blogs (safe default)
            },
            "status": {
                "privacyStatus": "public",
                "selfDeclaredMadeForKids": False,
            },
        }
        media = MediaFileUpload(str(video_path), mimetype="video/mp4", resumable=True)

        try:
            request = self._service.videos().insert(
                part="snippet,status", body=body, media_body=media
            )
            response = None
            while response is None:
                _, response = request.next_chunk()
            video_id = response["id"]

            if thumbnail_path is not None and thumbnail_path.exists():
                try:
                    self._service.thumbnails().set(
                        videoId=video_id,
                        media_body=MediaFileUpload(str(thumbnail_path), mimetype="image/jpeg"),
                    ).execute()
                except HttpError as e:
                    logger.warning(f"YouTube thumbnail upload failed (non-fatal): {e}")

            return PostResult(
                success=True,
                platform=self.platform,
                external_post_id=video_id,
                url=f"https://www.youtube.com/shorts/{video_id}" if is_short else f"https://www.youtube.com/watch?v={video_id}",
                raw_response=response,
            )
        except HttpError as e:
            logger.error(f"YouTube upload failed: {e}")
            return PostResult(success=False, platform=self.platform, error=str(e))

    @staticmethod
    def _title_from_caption(caption: str) -> str:
        first_line = caption.strip().split("\n", 1)[0]
        return first_line[:95] + ("…" if len(first_line) > 95 else "")

    @staticmethod
    def _compose_description(caption: str, hashtags: list[str], is_short: bool) -> str:
        # The literal "#Shorts" hashtag in the description is the YT signal for Shorts.
        tags = " ".join(f"#{t}" for t in hashtags[:15])
        suffix = "\n\n#Shorts" if is_short else ""
        return f"{caption.rstrip()}\n\n{tags}{suffix}".strip()
