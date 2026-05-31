"""Image provider protocol — covers both stock libraries (free) and AI generators (paid)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Protocol, runtime_checkable

AspectRatio = Literal["9:16", "1:1", "16:9", "4:5"]


@dataclass
class ImageResult:
    paths: list[Path]
    cost_usd: float       # 0.0 for stock libraries
    provider: str
    metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class ImageProvider(Protocol):
    """Implementations: pexels, unsplash (free) | nano_banana, dalle (paid)."""

    name: str
    is_free: bool

    def generate(
        self,
        prompts: list[str],
        aspect_ratio: AspectRatio,
        output_dir: Path,
        count: int | None = None,
    ) -> ImageResult:
        """Returns one image per prompt (count overrides len(prompts) when provider supports it).

        For stock libraries, prompts are search keywords. For AI generators they're scene descriptions.
        """
        ...
