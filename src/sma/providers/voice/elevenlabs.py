"""ElevenLabs TTS provider. Premium voice quality, ~$0.18/1k chars on Turbo v2."""

from __future__ import annotations

from pathlib import Path

from elevenlabs.client import ElevenLabs
from elevenlabs.core.api_error import ApiError
from loguru import logger
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from sma.providers.voice.base import VoiceResult
from sma.usage import pricing
from sma.usage.events import UsageEvent
from sma.usage.recorder import record

_DEFAULT_MODEL = "eleven_turbo_v2_5"


class VoiceNotAvailableError(RuntimeError):
    """Raised for non-retryable voice failures (e.g. free-tier locked voices)."""


def _voice_is_retryable(exc: BaseException) -> bool:
    """Don't retry 4xx — those are deterministic and waste credits."""
    if isinstance(exc, VoiceNotAvailableError):
        return False
    if isinstance(exc, ApiError):
        return exc.status_code not in {400, 401, 402, 403, 404}
    return True


class ElevenLabsVoice:
    name = "elevenlabs"

    def __init__(self, api_key: str) -> None:
        if not api_key:
            raise ValueError("ElevenLabs API key required")
        self._client = ElevenLabs(api_key=api_key)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=1, max=8),
        retry=retry_if_exception(_voice_is_retryable),
        reraise=True,
    )
    def synthesize(
        self,
        text: str,
        voice_id: str,
        output_path: Path,
        model: str | None = None,
        previous_text: str | None = None,
        next_text: str | None = None,
    ) -> VoiceResult:
        used_model = model or _DEFAULT_MODEL
        output_path.parent.mkdir(parents=True, exist_ok=True)

        convert_kwargs: dict = {
            "voice_id": voice_id,
            "model_id": used_model,
            "text": text,
            "output_format": "mp3_44100_128",
        }
        # previous_text / next_text help ElevenLabs maintain prosody across
        # consecutive chunks when we synthesize per-beat.
        if previous_text:
            convert_kwargs["previous_text"] = previous_text
        if next_text:
            convert_kwargs["next_text"] = next_text

        try:
            audio_iter = self._client.text_to_speech.convert(**convert_kwargs)
            with output_path.open("wb") as f:
                for chunk in audio_iter:
                    if chunk:
                        f.write(chunk)
        except ApiError as e:
            if e.status_code in {401, 402, 403}:
                body = getattr(e, "body", None) or {}
                detail = body.get("detail", {}) if isinstance(body, dict) else {}
                msg = (
                    detail.get("message")
                    if isinstance(detail, dict)
                    else "ElevenLabs rejected this request."
                )
                raise VoiceNotAvailableError(
                    f"ElevenLabs voice {voice_id!r} unavailable: {msg} "
                    "(Tip: in ElevenLabs, open the voice in 'Voice Library' and click "
                    "'Add to Voices'. Or switch voice_id in your niche YAML to one you own.)"
                ) from e
            raise

        chars = len(text)
        # Pricing key in pricing.yaml is a normalized version (turbo_v2 covers v2/v2.5).
        pricing_model = "eleven_turbo_v2" if "turbo" in used_model else "eleven_multilingual_v2"
        cost = pricing.cost_for_units(self.name, pricing_model, chars)

        # Rough duration estimate (mp3 from elevenlabs ~150 wpm ≈ 5 chars/sec).
        duration_sec = chars / 15.0

        record(
            UsageEvent(
                provider=self.name,
                model=used_model,
                operation="synthesize",
                units=chars,
                cost_usd=cost,
                metadata={"voice_id": voice_id, "output": str(output_path)},
            )
        )
        logger.debug(f"ElevenLabs {used_model}: {chars} chars → {output_path.name} (${cost:.4f})")

        return VoiceResult(
            path=output_path,
            duration_sec=duration_sec,
            chars=chars,
            cost_usd=cost,
            provider=self.name,
            voice_id=voice_id,
        )
