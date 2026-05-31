"""ElevenLabs Music provider. Generates instrumental background tracks from a prompt."""

from __future__ import annotations

from pathlib import Path

from elevenlabs.client import ElevenLabs
from elevenlabs.core.api_error import ApiError
from loguru import logger
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from sma.providers.music.base import MusicResult
from sma.usage import pricing
from sma.usage.events import UsageEvent
from sma.usage.recorder import record


class MusicNotAvailableError(RuntimeError):
    """Raised when the music API is unreachable for non-retryable reasons
    (e.g. free-tier accounts on ElevenLabs)."""


_DEFAULT_MODEL = "music-v1"
_MAX_DURATION_SEC = 20.0  # ElevenLabs Music API current limit


def _is_retryable(exc: BaseException) -> bool:
    """Don't retry on payment_required (402) or other client errors."""
    if isinstance(exc, ApiError):
        return exc.status_code not in {400, 401, 402, 403, 404}
    return True


class ElevenLabsMusic:
    name = "elevenlabs"

    def __init__(self, api_key: str) -> None:
        if not api_key:
            raise ValueError("ElevenLabs API key required")
        self._client = ElevenLabs(api_key=api_key)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=1, max=10),
        retry=retry_if_exception(_is_retryable),
        reraise=True,
    )
    def generate(
        self,
        prompt: str,
        duration_sec: float,
        output_path: Path,
        model: str | None = None,
    ) -> MusicResult:
        used_model = model or _DEFAULT_MODEL
        clamped = min(duration_sec, _MAX_DURATION_SEC)
        if clamped < duration_sec:
            logger.warning(
                f"Requested {duration_sec:.1f}s music; ElevenLabs limit is {_MAX_DURATION_SEC}s. "
                "The video assembler should loop this track to cover the full voiceover."
            )

        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            track = self._client.music.compose(
                prompt=prompt,
                music_length_ms=int(clamped * 1000),
            )
            with output_path.open("wb") as f:
                for chunk in track:
                    if chunk:
                        f.write(chunk)
        except ApiError as e:
            if e.status_code == 402:
                body = getattr(e, "body", None) or {}
                detail = body.get("detail", {}) if isinstance(body, dict) else {}
                msg = (
                    detail.get("message")
                    if isinstance(detail, dict)
                    else "ElevenLabs Music API requires a paid plan."
                )
                raise MusicNotAvailableError(
                    f"ElevenLabs music unavailable: {msg} "
                    "Set music_enabled: false in your niche YAML, or upgrade your plan."
                ) from e
            raise

        cost = pricing.cost_for_units(self.name, used_model, max(1, int(clamped / 60)))

        record(
            UsageEvent(
                provider=self.name,
                model=used_model,
                operation="compose",
                units=int(clamped),
                cost_usd=cost,
                metadata={"prompt": prompt[:200], "duration_sec": clamped},
            )
        )

        return MusicResult(
            path=output_path,
            duration_sec=clamped,
            cost_usd=cost,
            provider=self.name,
            prompt=prompt,
        )
