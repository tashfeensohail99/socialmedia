"""Voice (TTS) provider protocol."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable


@dataclass
class VoiceResult:
    path: Path
    duration_sec: float
    chars: int
    cost_usd: float
    provider: str
    voice_id: str


@runtime_checkable
class VoiceProvider(Protocol):
    """Implementations: elevenlabs, openai_tts."""

    name: str

    def synthesize(
        self,
        text: str,
        voice_id: str,
        output_path: Path,
        model: str | None = None,
        previous_text: str | None = None,
        next_text: str | None = None,
    ) -> VoiceResult:
        """Synthesize speech for `text` to `output_path`.

        `previous_text` and `next_text` give the engine prosody context when
        synthesizing in chunks (e.g. per-beat). Providers that don't support
        them should accept and ignore them.
        """
        ...
