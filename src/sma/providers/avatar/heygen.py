"""HeyGen Avatar IV (Photo Avatar) talking-head provider.

Submits {script, voice_id, avatar_id} to HeyGen's /v2/video/generate using the
`talking_photo` character type (works with Photo Avatar IV trained groups),
polls until the video is ready, downloads the MP4 + burned-in captions.

Cost: read from wallet delta when possible (most accurate); otherwise estimate
at $0.05/sec which is the published Photo Avatar IV rate.

Auth: HEYGEN_API_KEY env var. Worker + backend both have it set.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path

import httpx
from loguru import logger

HEYGEN_BASE = "https://api.heygen.com"
POLL_INTERVAL_SEC = 10
POLL_TIMEOUT_SEC = 900  # 15 min — Photo Avatar IV usually finishes in 2–5 min
EST_COST_PER_SEC = 0.05


class HeyGenError(RuntimeError):
    pass


@dataclass
class HeyGenResult:
    video_path: Path
    srt_path: Path | None
    duration_sec: float
    cost_usd: float
    avatar_id: str
    video_id: str


class HeyGenAvatarProvider:
    name = "heygen"

    def __init__(self, api_key: str | None = None) -> None:
        self._key = api_key or os.environ.get("HEYGEN_API_KEY")
        if not self._key:
            raise HeyGenError("HEYGEN_API_KEY env var not set")
        self._h_json = {"X-Api-Key": self._key, "Content-Type": "application/json"}
        self._h_key = {"X-Api-Key": self._key}

    def _wallet_balance(self) -> float | None:
        try:
            r = httpx.get(f"{HEYGEN_BASE}/v1/user/me", headers=self._h_key, timeout=15)
            r.raise_for_status()
            return float(r.json()["data"]["wallet"]["remaining_balance"])
        except Exception as e:
            logger.warning(f"HeyGen wallet check failed: {e}")
            return None

    def generate_talking_head(
        self,
        *,
        script: str,
        voice_id: str,
        avatar_id: str,
        output_path: Path,
        aspect: str = "9:16",
        background_color: str = "#000000",
        talking_style: str = "stable",
    ) -> HeyGenResult:
        if not script.strip():
            raise HeyGenError("script is empty")
        if not voice_id:
            raise HeyGenError("voice_id is empty")
        if not avatar_id:
            raise HeyGenError("avatar_id is empty")

        wallet_before = self._wallet_balance()

        if aspect == "9:16":
            width, height = 720, 1280
        elif aspect == "16:9":
            width, height = 1280, 720
        else:
            width, height = 720, 1280

        payload = {
            "video_inputs": [
                {
                    "character": {
                        "type": "talking_photo",
                        "talking_photo_id": avatar_id,
                        # 'stable' dampens facial-expression intensity during
                        # speech — our trained avatars have smiles baked into
                        # their source photos, so the default ('expressive')
                        # over-animates the smile.
                        "talking_style": talking_style,
                    },
                    "voice": {
                        "type": "text",
                        "input_text": script,
                        "voice_id": voice_id,
                    },
                    "background": {"type": "color", "value": background_color},
                }
            ],
            "dimension": {"width": width, "height": height},
            "caption": True,
        }

        logger.info(
            f"HeyGen submit: avatar={avatar_id} voice={voice_id} "
            f"script_chars={len(script)} aspect={aspect}"
        )
        r = httpx.post(
            f"{HEYGEN_BASE}/v2/video/generate",
            headers=self._h_json,
            json=payload,
            timeout=60,
        )
        if r.status_code != 200:
            raise HeyGenError(
                f"HeyGen submit HTTP {r.status_code}: {r.text[:500]}"
            )
        body = r.json()
        if body.get("error"):
            raise HeyGenError(f"HeyGen submit error: {body['error']}")
        video_id = body["data"]["video_id"]
        logger.info(f"HeyGen video_id={video_id} — polling…")

        status_data: dict = {}
        deadline = time.time() + POLL_TIMEOUT_SEC
        while time.time() < deadline:
            time.sleep(POLL_INTERVAL_SEC)
            try:
                pr = httpx.get(
                    f"{HEYGEN_BASE}/v1/video_status.get",
                    headers=self._h_key,
                    params={"video_id": video_id},
                    timeout=15,
                )
                pr.raise_for_status()
                status_data = pr.json().get("data", {}) or {}
            except Exception as e:
                logger.warning(f"HeyGen poll error (will retry): {e}")
                continue

            status = status_data.get("status")
            if status == "completed":
                break
            if status == "failed":
                raise HeyGenError(
                    f"HeyGen generation failed: {status_data.get('error')}"
                )
            logger.debug(f"HeyGen {video_id}: status={status}")
        else:
            raise HeyGenError(f"HeyGen polling timed out after {POLL_TIMEOUT_SEC}s")

        video_url = status_data.get("video_url")
        if not video_url:
            raise HeyGenError(f"HeyGen completed but no video_url: {status_data}")
        duration = float(status_data.get("duration") or 0.0)
        caption_url = status_data.get("caption_url")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        self._download(video_url, output_path)

        srt_path: Path | None = None
        if caption_url:
            srt_candidate = output_path.with_suffix(".srt")
            try:
                self._download(caption_url, srt_candidate)
                srt_path = srt_candidate
            except Exception as e:
                logger.warning(f"HeyGen caption download failed (non-fatal): {e}")

        cost = duration * EST_COST_PER_SEC
        if wallet_before is not None:
            wallet_after = self._wallet_balance()
            if wallet_after is not None:
                cost = round(max(0.0, wallet_before - wallet_after), 4)

        logger.info(
            f"HeyGen done: {output_path.name} ({duration:.1f}s, ${cost:.4f})"
        )
        return HeyGenResult(
            video_path=output_path,
            srt_path=srt_path,
            duration_sec=duration,
            cost_usd=cost,
            avatar_id=avatar_id,
            video_id=video_id,
        )

    @staticmethod
    def _download(url: str, dst: Path, *, attempts: int = 4) -> None:
        # files2.heygen.ai occasionally drops the connection mid-transfer.
        # Retry the whole download a few times before giving up.
        last_err: Exception | None = None
        for i in range(attempts):
            try:
                with httpx.stream(
                    "GET",
                    url,
                    headers={"User-Agent": "Mozilla/5.0 (sma-heygen-fetch/1.0)"},
                    timeout=300,
                    follow_redirects=True,
                ) as r:
                    r.raise_for_status()
                    with dst.open("wb") as f:
                        for chunk in r.iter_bytes(chunk_size=64 * 1024):
                            if chunk:
                                f.write(chunk)
                return
            except Exception as e:
                last_err = e
                logger.warning(f"HeyGen download attempt {i + 1} failed: {e}")
                time.sleep(3 + i * 2)
        raise HeyGenError(
            f"HeyGen download failed after {attempts} attempts: {last_err}"
        )
