"""HeyGen Avatar IV talking-head pipeline.

A drop-in alternative to `orchestrator.run_pipeline` for niches whose
avatar_mode='talking_head'. Returns the same PipelineResult dataclass so the
db_runner + posting code paths work unchanged.

Differences from the slideshow pipeline:
  - No scene images, no slideshow assembler, no separate voiceover synth.
  - Script (from analyze_story) is sent to HeyGen; HeyGen returns a finished
    talking-head MP4 with burned-in captions and a matching SRT.
  - Final video is upscaled to 1080×1920 and a brand CTA is burned in over
    the last `_CTA_SECONDS` seconds (Tashfeen Immigration Solutions + phone).
  - Thumbnail = first frame of the HeyGen MP4 (no separate image gen).
  - Cost = HeyGen wallet delta (also persisted as Post.avatar_cost_usd).
"""
from __future__ import annotations

import json
import subprocess
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger

from sma.core.content.caption_generator import generate_caption_and_hashtags
from sma.core.content.story_analyzer import StoryPlan, analyze_story
from sma.core.niche.config import VideoLength
from sma.core.pipeline.context import PipelineContext
from sma.core.pipeline.orchestrator import PipelineResult
from sma.core.topics.base import Topic
from sma.providers.avatar.heygen import HeyGenAvatarProvider

# CTA — hardcoded for every talking-head video. Brand line in white, phone
# line in orange to draw the eye. Positioned at y=1480 of a 1080×1920 frame
# (~77% from top) so the avatar's face above remains uncovered.
_CTA_BRAND = "Tashfeen Immigration Solutions"
_CTA_PHONE = "+92 335 0001111"
_CTA_SECONDS = 5  # show CTA for the last N seconds of the video
_FINAL_W = 1080
_FINAL_H = 1920
_CTA_Y = 1480


def _pick_avatar(avatar_ids: list[str], post_id: str) -> str:
    if not avatar_ids:
        raise ValueError(
            "avatar_library_ids is empty — populate niches.avatar_library_ids"
        )
    # Deterministic by post_id so the same post always uses the same avatar
    # on retry, but spread across the library across posts.
    digits = "".join(c for c in post_id if c.isdigit())
    idx = (int(digits) if digits else 0) % len(avatar_ids)
    return avatar_ids[idx]


def _extract_thumbnail(video_path: Path, output_path: Path) -> None:
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(video_path),
        "-vframes", "1",
        "-q:v", "2",
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg thumbnail extract failed: {result.stderr[:400]}")


def _render_cta_png(out_path: Path) -> None:
    """Render the Tashfeen CTA banner once. Cached on disk — subsequent calls no-op."""
    if out_path.exists():
        return
    out_path.parent.mkdir(parents=True, exist_ok=True)
    from PIL import Image, ImageDraw, ImageFont

    # Find an Impact-equivalent font that exists in the container (Debian-slim
    # ships fonts-dejavu-core per the Dockerfile). Fall back through a few paths.
    font_candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVu-Sans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "C:/Windows/Fonts/impact.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
    ]
    font_path = next((p for p in font_candidates if Path(p).exists()), None)
    if font_path is None:
        raise RuntimeError(
            f"No CTA font found. Tried: {font_candidates}"
        )

    font_brand = ImageFont.truetype(font_path, 70)
    font_phone = ImageFont.truetype(font_path, 95)

    tmp = Image.new("RGBA", (1, 1))
    d = ImageDraw.Draw(tmp)
    b1 = d.textbbox((0, 0), _CTA_BRAND, font=font_brand)
    b2 = d.textbbox((0, 0), _CTA_PHONE, font=font_phone)
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
    dr.text((tx1 + 3, ty1 + 3), _CTA_BRAND, fill=(0, 0, 0, 220), font=font_brand)
    dr.text((tx1, ty1), _CTA_BRAND, fill=(255, 255, 255, 255), font=font_brand)

    tx2 = (bw - w2) // 2 - b2[0]
    ty2 = pad_y + h1 + gap - b2[1]
    dr.text((tx2 + 3, ty2 + 3), _CTA_PHONE, fill=(0, 0, 0, 220), font=font_phone)
    dr.text((tx2, ty2), _CTA_PHONE, fill=(255, 200, 0, 255), font=font_phone)

    img.save(out_path, "PNG")
    logger.info(f"Rendered CTA banner: {bw}x{bh} -> {out_path}")


def _add_cta_overlay(
    src_video: Path,
    cta_png: Path,
    duration_sec: float,
    output_path: Path,
) -> None:
    """Scale src to 1080×1920 and overlay the CTA on the last _CTA_SECONDS."""
    cta_start = max(0.0, duration_sec - _CTA_SECONDS)
    cta_end = duration_sec
    filter_complex = (
        f"[0:v]scale={_FINAL_W}:{_FINAL_H}:force_original_aspect_ratio=increase,"
        f"crop={_FINAL_W}:{_FINAL_H},setsar=1[base];"
        f"[base][1:v]overlay=x=(W-w)/2:y={_CTA_Y}:"
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


def run_pipeline_heygen_talking_head(
    topic: Topic,
    ctx: PipelineContext,
    output_root: Path,
    *,
    avatar_library_ids: list[str],
    heygen_voice_id: str,
    video_length: VideoLength | None = None,
    post_id: str | None = None,
) -> PipelineResult:
    pid = post_id or topic.id
    post_dir = output_root / f"post_{pid}"
    post_dir.mkdir(parents=True, exist_ok=True)
    video_dir = post_dir / "video"
    video_dir.mkdir(parents=True, exist_ok=True)
    length = video_length or ctx.niche.video_length_default

    logger.info(
        f"▶ HeyGen pipeline start: post={pid} niche={ctx.niche.name!r} length={length}"
    )

    plan: StoryPlan = analyze_story(topic, ctx.niche, ctx.llm, video_length=length)

    avatar_id = _pick_avatar(list(avatar_library_ids), pid)
    logger.info(f"HeyGen avatar chosen: {avatar_id}")

    provider = HeyGenAvatarProvider()
    raw_video_path = video_dir / "heygen_raw.mp4"
    aspect = "16:9" if length == "long" else "9:16"
    hg = provider.generate_talking_head(
        script=plan.narrative_script,
        voice_id=heygen_voice_id,
        avatar_id=avatar_id,
        output_path=raw_video_path,
        aspect=aspect,
    )

    # Post-process: upscale to 1080×1920 and burn in the Tashfeen CTA on
    # the last _CTA_SECONDS. This is a hardcoded brand rule for every video.
    video_path = video_dir / "final.mp4"
    if length == "short":
        cta_png = output_root / "_cta_tashfeen.png"
        try:
            _render_cta_png(cta_png)
            _add_cta_overlay(
                src_video=hg.video_path,
                cta_png=cta_png,
                duration_sec=hg.duration_sec,
                output_path=video_path,
            )
            logger.info(f"CTA overlay applied: {video_path.name}")
        except Exception as e:
            # CTA failure is non-fatal — fall back to the raw HeyGen video so
            # the post still goes out. The brand is still mentioned in the audio.
            logger.error(f"CTA overlay failed (using raw HeyGen video): {e}")
            video_path = raw_video_path
    else:
        # Long-form (horizontal 16:9) skips the vertical CTA layout.
        video_path = raw_video_path

    thumbnail_path = post_dir / "thumbnail.jpg"
    try:
        _extract_thumbnail(video_path, thumbnail_path)
    except Exception as e:
        logger.warning(f"thumbnail extract failed (non-fatal): {e}")

    caption_result = generate_caption_and_hashtags(
        topic=topic,
        niche=ctx.niche,
        narrative_script=plan.narrative_script,
        llm=ctx.llm,
    )

    metadata: dict[str, Any] = {
        "post_id": pid,
        "tenant_id": ctx.tenant_id,
        "video_format": "horizontal_16_9" if length == "long" else "vertical_9_16",
        "niche": ctx.niche.name,
        "topic": topic.to_dict(),
        "video_length": length,
        "video_path": str(video_path.relative_to(post_dir)),
        "thumbnail_path": (
            str(thumbnail_path.relative_to(post_dir)) if thumbnail_path.exists() else ""
        ),
        "caption": caption_result.caption,
        "hashtags": caption_result.hashtags,
        "narrative_script": plan.narrative_script,
        "hook_text": plan.hook_text,
        "story_beats": [asdict(b) for b in plan.story_beats],
        "duration_sec": hg.duration_sec,
        "image_count": 0,
        "image_provider": "heygen_avatar",
        "voice_provider": "heygen_voice",
        "voice_id": heygen_voice_id,
        "music_provider": None,
        "llm_model": ctx.niche.llm_model,
        "media_cost_usd": hg.cost_usd,
        "avatar_id": avatar_id,
        "avatar_cost_usd": hg.cost_usd,
        "heygen_video_id": hg.video_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "ready",
    }
    (post_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    logger.info(
        f"✔ HeyGen pipeline done: post={pid} video={video_path.name} "
        f"({hg.duration_sec:.1f}s, ${hg.cost_usd:.4f})"
    )

    return PipelineResult(
        post_id=pid,
        output_dir=post_dir,
        video_path=video_path,
        thumbnail_path=thumbnail_path if thumbnail_path.exists() else video_path,
        caption=caption_result.caption,
        hashtags=caption_result.hashtags,
        duration_sec=hg.duration_sec,
        image_count=0,
        cost_usd=hg.cost_usd,
    )
