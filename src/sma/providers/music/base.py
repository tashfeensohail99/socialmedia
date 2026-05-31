"""Music provider protocol — generates background music tracks for videos."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable


@dataclass
class MusicResult:
    path: Path
    duration_sec: float
    cost_usd: float
    provider: str
    prompt: str


@runtime_checkable
class MusicProvider(Protocol):
    """Implementations: elevenlabs (more added later — Suno, AudioCraft)."""

    name: str

    def generate(
        self,
        prompt: str,
        duration_sec: float,
        output_path: Path,
        model: str | None = None,
    ) -> MusicResult: ...
