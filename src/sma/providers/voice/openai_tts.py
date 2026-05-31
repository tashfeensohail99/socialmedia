"""OpenAI TTS provider — cheaper alternative to ElevenLabs (~$15/1M chars vs $180)."""

from __future__ import annotations

from pathlib import Path

from loguru import logger
from openai import APIConnectionError, APIError, OpenAI, RateLimitError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from sma.providers.voice.base import VoiceResult
from sma.usage import pricing
from sma.usage.events import UsageEvent
from sma.usage.recorder import record

_DEFAULT_MODEL = "tts-1"
# Built-in voice IDs supported by OpenAI TTS.
SUPPORTED_VOICES = {"alloy", "echo", "fable", "onyx", "nova", "shimmer"}


class OpenAITTSVoice:
    name = "openai_tts"

    def __init__(self, api_key: str) -> None:
        if not api_key:
            raise ValueError("OpenAI API key required for TTS")
        self._client = OpenAI(api_key=api_key)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=1, max=8),
        retry=retry_if_exception_type((RateLimitError, APIConnectionError, APIError)),
        reraise=True,
    )
    def synthesize(
        self,
        text: str,
        voice_id: str,
        output_path: Path,
        model: str | None = None,
        previous_text: str | None = None,  # OpenAI TTS has no prosody-context API; ignored.
        next_text: str | None = None,
    ) -> VoiceResult:
        used_model = model or _DEFAULT_MODEL
        if voice_id not in SUPPORTED_VOICES:
            logger.warning(f"OpenAI TTS voice {voice_id!r} not in {SUPPORTED_VOICES}; using 'nova'")
            voice_id = "nova"

        output_path.parent.mkdir(parents=True, exist_ok=True)

        with self._client.audio.speech.with_streaming_response.create(
            model=used_model,
            voice=voice_id,
            input=text,
            response_format="mp3",
        ) as resp:
            resp.stream_to_file(str(output_path))

        chars = len(text)
        cost = pricing.cost_for_units("openai", used_model, chars)
        duration_sec = chars / 15.0

        record(
            UsageEvent(
                provider="openai",
                model=used_model,
                operation="tts",
                units=chars,
                cost_usd=cost,
                metadata={"voice_id": voice_id, "output": str(output_path)},
            )
        )

        return VoiceResult(
            path=output_path,
            duration_sec=duration_sec,
            chars=chars,
            cost_usd=cost,
            provider=self.name,
            voice_id=voice_id,
        )
