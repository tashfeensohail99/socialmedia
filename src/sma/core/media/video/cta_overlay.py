"""Tashfeen Immigration Solutions CTA overlay — burned in on every short.

Used by both pipelines (HeyGen talking-head and Pexels slideshow) so every
short ends with the same brand badge regardless of how the video was made.

The CTA banner is a PIL-rendered PNG cached at output_root/_cta_tashfeen.png
on first use. ffmpeg upscales the source video to 1080×1920 (YouTube Shorts
sweet spot) and overlays the badge at y=1480 (~77% from top — below the
speaker's face, above HeyGen's burned-in captions) for the last _CTA_SECONDS.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from loguru import logger

# Hardcoded brand — applies to every short, regardless of pipeline.
CTA_BRAND = "Tashfeen Immigration Solutions"
CTA_PHONE = "+92 335 0001111"
CTA_SECONDS = 5  # show CTA for the last N seconds
FINAL_W = 1080
FINAL_H = 1920
CTA_Y = 1480


def render_cta_png(out_path: Path) -> None:
    """Render the Tashfeen CTA banner once. Cached on disk — subsequent calls no-op."""
    if out_path.exists():
        return
    out_path.parent.mkdir(parents=True, exist_ok=True)
    from PIL import Image, ImageDraw, ImageFont

    font_candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVu-Sans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "C:/Windows/Fonts/impact.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
    ]
    font_path = next((p for p in font_candidates if Path(p).exists()), None)
    if font_path is None:
        raise RuntimeError(f"No CTA font found. Tried: {font_candidates}")

    font_brand = ImageFont.truetype(font_path, 70)
    font_phone = ImageFont.truetype(font_path, 95)

    tmp = Image.new("RGBA", (1, 1))
    d = ImageDraw.Draw(tmp)
    b1 = d.textbbox((0, 0), CTA_BRAND, font=font_brand)
    b2 = d.textbbox((0, 0), CTA_PHONE, font=font_phone)
    w1, h1 = b1[2] - b1[0], b1[3] - b1[1]
    w2, h2 = b2[2] - b2[0], b2[3] - b2[1]

    pad_x, pad_y, gap = 50, 30, 12
    bw = max(w1, w2) + 2 * pad_x
    bh = h1 + h2 + 2 * pad_y + gap

    img = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
    dr = ImageDraw.Draw(img)
    dr.rounded_rectangle([0, 0, bw, bh], radius=22, fill=(0, 0, 0, 220))

    tx1 = (bw - w1) // 2 - b1[0]
    ty1 = pad_y - b1[1]
    dr.text((tx1 + 3, ty1 + 3), CTA_BRAND, fill=(0, 0, 0, 220), font=font_brand)
    dr.text((tx1, ty1), CTA_BRAND, fill=(255, 255, 255, 255), font=font_brand)

    tx2 = (bw - w2) // 2 - b2[0]
    ty2 = pad_y + h1 + gap - b2[1]
    dr.text((tx2 + 3, ty2 + 3), CTA_PHONE, fill=(0, 0, 0, 220), font=font_phone)
    dr.text((tx2, ty2), CTA_PHONE, fill=(255, 200, 0, 255), font=font_phone)

    img.save(out_path, "PNG")
    logger.info(f"Rendered CTA banner: {bw}x{bh} -> {out_path}")


def add_cta_overlay(
    src_video: Path,
    cta_png: Path,
    duration_sec: float,
    output_path: Path,
) -> None:
    """Scale src to 1080×1920 and overlay the CTA on the last CTA_SECONDS."""
    cta_start = max(0.0, duration_sec - CTA_SECONDS)
    cta_end = duration_sec
    filter_complex = (
        f"[0:v]scale={FINAL_W}:{FINAL_H}:force_original_aspect_ratio=increase,"
        f"crop={FINAL_W}:{FINAL_H},setsar=1[base];"
        f"[base][1:v]overlay=x=(W-w)/2:y={CTA_Y}:"
        f"enable='between(t,{cta_start:.2f},{cta_end:.2f})'[vout]"
    )
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "warning",
        "-i", str(src_video),
        "-i", str(cta_png),
        "-filter_complex", filter_complex,
        "-map", "[vout]", "-map", "0:a?",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-pix_fmt", "yuv420p", "-r", "30",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        str(output_path),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg CTA overlay failed: {r.stderr[-600:]}")


def apply_brand_cta(
    src_video: Path,
    duration_sec: float,
    cta_png: Path,
) -> Path:
    """One-shot helper: render CTA PNG if needed, overlay onto src, return the
    new video path (sibling of src named ``final.mp4`` / ``...with_cta.mp4``).

    Returns the original src_video path on any failure so the post still ships.
    """
    try:
        render_cta_png(cta_png)
        # Write to src_video.parent / "final_with_cta.mp4" so the original
        # raw is preserved (useful for debugging visual issues).
        out = src_video.parent / "final_with_cta.mp4"
        add_cta_overlay(
            src_video=src_video,
            cta_png=cta_png,
            duration_sec=duration_sec,
            output_path=out,
        )
        return out
    except Exception as e:
        logger.error(f"CTA overlay failed (keeping raw video): {e}")
        return src_video
