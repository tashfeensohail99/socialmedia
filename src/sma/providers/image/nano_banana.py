"""Nano Banana image provider — Google's gemini-2.5-flash-image model.

Default paid image generator. ~$0.039/image.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from google import genai
from loguru import logger
from PIL import Image
from tenacity import retry, stop_after_attempt, wait_exponential

from sma.providers.image.base import AspectRatio, ImageResult
from sma.usage import pricing
from sma.usage.events import UsageEvent
from sma.usage.recorder import record

_MODEL = "gemini-2.5-flash-image"


def _aspect_hint(aspect: AspectRatio) -> str:
    return {
        "9:16": "Vertical 9:16 portrait composition.",
        "4:5": "Vertical 4:5 portrait composition.",
        "1:1": "Square 1:1 composition.",
        "16:9": "Horizontal 16:9 widescreen composition.",
    }[aspect]


class NanoBananaProvider:
    name = "nano_banana"
    is_free = False

    def __init__(self, api_key: str) -> None:
        if not api_key:
            raise ValueError("Gemini API key required for Nano Banana")
        self._client = genai.Client(api_key=api_key)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10), reraise=True)
    def _generate_one(self, prompt: str) -> bytes:
        response = self._client.models.generate_content(
            model=_MODEL,
            contents=prompt,
        )
        # The response contains parts; image bytes are in inline_data.data.
        for candidate in response.candidates or []:
            for part in candidate.content.parts or []:
                inline = getattr(part, "inline_data", None)
                if inline and inline.data:
                    return inline.data  # bytes
        raise RuntimeError(f"Nano Banana returned no image for prompt: {prompt[:80]}...")

    def generate(
        self,
        prompts: list[str],
        aspect_ratio: AspectRatio,
        output_dir: Path,
        count: int | None = None,
    ) -> ImageResult:
        output_dir.mkdir(parents=True, exist_ok=True)
        targets = prompts if count is None else (prompts * (count // len(prompts) + 1))[:count]
        aspect_hint = _aspect_hint(aspect_ratio)

        out_paths: list[Path] = []
        for idx, prompt in enumerate(targets):
            full_prompt = f"{prompt}\n\n{aspect_hint}"
            try:
                data = self._generate_one(full_prompt)
                # Normalize to JPEG so downstream video assembly is consistent.
                img = Image.open(BytesIO(data)).convert("RGB")
                out = output_dir / f"nano_banana_{idx:03d}.jpg"
                img.save(out, "JPEG", quality=92)
                out_paths.append(out)
            except Exception as e:
                logger.error(f"Nano Banana failed on prompt {idx} ({prompt[:60]}...): {e}")
                continue

        cost = pricing.cost_for_units(self.name, _MODEL, len(out_paths))
        record(
            UsageEvent(
                provider=self.name,
                model=_MODEL,
                operation="generate",
                units=len(out_paths),
                cost_usd=cost,
                metadata={"prompt_count": len(targets), "succeeded": len(out_paths)},
            )
        )

        return ImageResult(
            paths=out_paths,
            cost_usd=cost,
            provider=self.name,
            metadata={"aspect": aspect_ratio, "model": _MODEL},
        )
