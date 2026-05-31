"""DALL-E / gpt-image-1 image provider. Paid OpenAI image generation."""

from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path

from loguru import logger
from openai import APIConnectionError, APIError, OpenAI, RateLimitError
from PIL import Image
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from sma.providers.image.base import AspectRatio, ImageResult
from sma.usage import pricing
from sma.usage.events import UsageEvent
from sma.usage.recorder import record


def _size_for(aspect: AspectRatio) -> str:
    # gpt-image-1 supports 1024x1024, 1024x1536, 1536x1024
    return {
        "9:16": "1024x1536",
        "4:5": "1024x1536",
        "1:1": "1024x1024",
        "16:9": "1536x1024",
    }[aspect]


class DalleProvider:
    name = "dalle"
    is_free = False

    def __init__(self, api_key: str, model: str = "gpt-image-1") -> None:
        if not api_key:
            raise ValueError("OpenAI API key required for DALL-E")
        self._client = OpenAI(api_key=api_key)
        self._model = model

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=1, max=10),
        retry=retry_if_exception_type((RateLimitError, APIConnectionError, APIError)),
        reraise=True,
    )
    def _generate_one(self, prompt: str, size: str) -> bytes:
        resp = self._client.images.generate(
            model=self._model,
            prompt=prompt,
            n=1,
            size=size,
        )
        b64 = resp.data[0].b64_json
        if not b64:
            raise RuntimeError("DALL-E returned no image data")
        return base64.b64decode(b64)

    def generate(
        self,
        prompts: list[str],
        aspect_ratio: AspectRatio,
        output_dir: Path,
        count: int | None = None,
    ) -> ImageResult:
        output_dir.mkdir(parents=True, exist_ok=True)
        targets = prompts if count is None else (prompts * (count // len(prompts) + 1))[:count]
        size = _size_for(aspect_ratio)

        out_paths: list[Path] = []
        for idx, prompt in enumerate(targets):
            try:
                data = self._generate_one(prompt, size)
                img = Image.open(BytesIO(data)).convert("RGB")
                out = output_dir / f"dalle_{idx:03d}.jpg"
                img.save(out, "JPEG", quality=92)
                out_paths.append(out)
            except Exception as e:
                logger.error(f"DALL-E failed on prompt {idx} ({prompt[:60]}...): {e}")
                continue

        cost = pricing.cost_for_units("openai", self._model, len(out_paths))
        record(
            UsageEvent(
                provider="openai",
                model=self._model,
                operation="image_generate",
                units=len(out_paths),
                cost_usd=cost,
                metadata={"prompt_count": len(targets), "succeeded": len(out_paths)},
            )
        )

        return ImageResult(
            paths=out_paths,
            cost_usd=cost,
            provider=self.name,
            metadata={"aspect": aspect_ratio, "size": size, "model": self._model},
        )
