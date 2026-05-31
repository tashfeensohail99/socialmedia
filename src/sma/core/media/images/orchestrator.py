"""Image generation orchestrator.

Turns a list of StoryBeats into actual image files on disk by:
1. Asking the LLM to write a per-scene image prompt (or stock-search query) for each beat
2. Calling the configured ImageProvider with those prompts
3. Normalizing all results to the niche's preferred aspect ratio (1080x1920 for 9:16)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from loguru import logger
from PIL import Image

from sma.core.content.story_analyzer import StoryBeat
from sma.core.niche.config import NicheConfig
from sma.core.templates import render
from sma.core.topics.base import Topic
from sma.providers.image.base import AspectRatio, ImageProvider, ImageResult
from sma.providers.llm.base import LLMProvider

# Target dimensions per aspect ratio. The video assembler expects these.
_TARGET_DIMS: dict[str, tuple[int, int]] = {
    "9:16": (1080, 1920),
    "4:5": (1080, 1350),
    "1:1": (1080, 1080),
    "16:9": (1920, 1080),
}


@dataclass
class GeneratedImages:
    images: list[Path]   # one per beat (may be shorter if a provider failed silently)
    prompts: list[str]
    cost_usd: float
    aspect_ratio: AspectRatio
    provider: str


def build_image_prompts(
    beats: list[StoryBeat],
    topic: Topic,
    niche: NicheConfig,
    llm: LLMProvider,
    *,
    for_stock_search: bool,
) -> list[str]:
    """Asks the LLM for one prompt per beat. For stock providers, returns a search query."""
    prompts: list[str] = []
    total = len(beats)
    for beat in beats:
        rendered = render(
            "image_scene.j2",
            niche=niche,
            topic=topic,
            beat=beat,
            total_beats=total,
            for_stock_search=for_stock_search,
        )
        resp = llm.complete(
            system="You write image-generation prompts or stock-search queries. Be precise.",
            user=rendered,
            model=niche.llm_model,
            temperature=0.8,
            json_mode=for_stock_search,
        )
        if for_stock_search:
            try:
                data = json.loads(resp.text)
                queries = data.get("queries", [])
                # Use the first query as the primary; the provider can decide whether to retry.
                prompts.append(queries[0] if queries else beat.scene_description)
            except (json.JSONDecodeError, IndexError) as e:
                logger.warning(f"Stock-query JSON parse failed for beat {beat.order}: {e}")
                prompts.append(beat.scene_description)
        else:
            prompts.append(resp.text.strip())
    return prompts


def generate_scene_images(
    beats: list[StoryBeat],
    topic: Topic,
    niche: NicheConfig,
    llm: LLMProvider,
    image_provider: ImageProvider,
    output_dir: Path,
    aspect_override: AspectRatio | None = None,
) -> GeneratedImages:
    aspect: AspectRatio = aspect_override or niche.image_aspect_default  # type: ignore[assignment]
    output_dir.mkdir(parents=True, exist_ok=True)

    prompts = build_image_prompts(
        beats, topic, niche, llm, for_stock_search=image_provider.is_free
    )

    raw_result: ImageResult = image_provider.generate(
        prompts=prompts,
        aspect_ratio=aspect,
        output_dir=output_dir,
    )

    normalized = _normalize_all(raw_result.paths, aspect)

    return GeneratedImages(
        images=normalized,
        prompts=prompts,
        cost_usd=raw_result.cost_usd,
        aspect_ratio=aspect,
        provider=image_provider.name,
    )


def _normalize_all(paths: list[Path], aspect: AspectRatio) -> list[Path]:
    """Resize/crop every image to the target dimensions for the aspect ratio."""
    target = _TARGET_DIMS[aspect]
    out: list[Path] = []
    for p in paths:
        try:
            normalized = _normalize_one(p, target)
            out.append(normalized)
        except Exception as e:
            logger.error(f"Failed to normalize {p.name}: {e}")
    return out


def _normalize_one(path: Path, target: tuple[int, int]) -> Path:
    """Center-crop and resize an image to exact target dimensions, in-place."""
    tw, th = target
    target_aspect = tw / th
    with Image.open(path) as img:
        img = img.convert("RGB")
        w, h = img.size
        src_aspect = w / h
        # Crop to target aspect
        if src_aspect > target_aspect:
            new_w = int(h * target_aspect)
            left = (w - new_w) // 2
            img = img.crop((left, 0, left + new_w, h))
        elif src_aspect < target_aspect:
            new_h = int(w / target_aspect)
            top = (h - new_h) // 2
            img = img.crop((0, top, w, top + new_h))
        img = img.resize((tw, th), Image.Resampling.LANCZOS)
        img.save(path, "JPEG", quality=92)
    return path
