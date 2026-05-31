"""Thumbnail generator. Picks one image and overlays the hook text.

Two modes:
- AI mode (paid image provider): generates a fresh thumbnail with `thumbnail_prompt.j2`
- Stock mode (free): reuses the first scene image and overlays text
"""

from __future__ import annotations

from pathlib import Path

from loguru import logger
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from sma.core.niche.config import NicheConfig
from sma.core.templates import render
from sma.core.topics.base import Topic
from sma.providers.image.base import ImageProvider
from sma.providers.llm.base import LLMProvider


def generate_thumbnail(
    topic: Topic,
    niche: NicheConfig,
    hook_text: str,
    llm: LLMProvider,
    image_provider: ImageProvider,
    output_path: Path,
    fallback_image: Path | None = None,
    aspect_ratio: str = "9:16",
) -> Path:
    """Generate a thumbnail for the post.

    aspect_ratio:
        "9:16" → 1080x1920 vertical (Reels/Shorts/TikTok)
        "16:9" → 1920x1080 horizontal (YouTube long-form)
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    target_size = (1080, 1920) if aspect_ratio == "9:16" else (1920, 1080)

    if image_provider.is_free and fallback_image is not None:
        # Free providers: skip the second AI call, reuse a scene image.
        base = Image.open(fallback_image).convert("RGB")
    else:
        prompt = render("thumbnail_prompt.j2", niche=niche, topic=topic, hook_text=hook_text)
        resp = llm.complete(
            system="You write image-generation prompts. Be vivid and specific.",
            user=prompt,
            model=niche.llm_model,
            temperature=0.8,
        )
        result = image_provider.generate(
            prompts=[resp.text.strip()],
            aspect_ratio=aspect_ratio,  # type: ignore[arg-type]
            output_dir=output_path.parent,
            count=1,
        )
        if not result.paths:
            if fallback_image is None:
                raise RuntimeError("Thumbnail generation failed and no fallback image provided")
            logger.warning("AI thumbnail failed; falling back to first scene image")
            base = Image.open(fallback_image).convert("RGB")
        else:
            base = Image.open(result.paths[0]).convert("RGB")

    base = _ensure_size(base, target_size)
    composed = _overlay_hook_text(base, hook_text)
    composed.save(output_path, "JPEG", quality=94)
    return output_path


def _ensure_size(img: Image.Image, target: tuple[int, int]) -> Image.Image:
    if img.size == target:
        return img
    return img.resize(target, Image.Resampling.LANCZOS)


def _overlay_hook_text(base: Image.Image, text: str) -> Image.Image:
    """Multi-layer text overlay: shadow + stroke + fill, top-third placement."""
    if not text:
        return base
    img = base.copy()
    W, H = img.size
    # Darken top third for readability
    top = Image.new("RGBA", (W, H // 3), (0, 0, 0, 110))
    img = Image.alpha_composite(img.convert("RGBA"), _paste_at(top, (0, 0), (W, H))).convert("RGB")

    draw = ImageDraw.Draw(img)
    font = _load_bold_font(int(H * 0.06))

    # Wrap to ~16 chars/line
    lines = _wrap(text, 16)
    line_h = int(H * 0.075)
    total_h = line_h * len(lines)
    y = int(H * 0.04)

    for line in lines:
        text_w = draw.textlength(line, font=font)
        x = (W - text_w) // 2
        # Stroke (black) + fill (white)
        draw.text((x, y), line, font=font, fill="white", stroke_width=4, stroke_fill="black")
        y += line_h

    return img


def _paste_at(layer: Image.Image, pos: tuple[int, int], canvas_size: tuple[int, int]) -> Image.Image:
    canvas = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    canvas.paste(layer, pos)
    return canvas


def _wrap(text: str, max_chars: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    cur = ""
    for w in words:
        candidate = f"{cur} {w}".strip()
        if len(candidate) <= max_chars:
            cur = candidate
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _load_bold_font(size: int) -> ImageFont.ImageFont:
    # Try common locations; fall back to default.
    candidates = [
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/segoeuib.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for c in candidates:
        try:
            return ImageFont.truetype(c, size)
        except OSError:
            continue
    return ImageFont.load_default()
