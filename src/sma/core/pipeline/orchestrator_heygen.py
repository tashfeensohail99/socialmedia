"""HeyGen Avatar IV talking-head pipeline.

A drop-in alternative to `orchestrator.run_pipeline` for niches whose
avatar_mode='talking_head'. Returns the same PipelineResult dataclass so the
db_runner + posting code paths work unchanged.

Differences from the slideshow pipeline:
  - No scene images, no slideshow assembler, no separate voiceover synth.
  - Script (from analyze_story) is sent to HeyGen; HeyGen returns a finished
    talking-head MP4 with burned-in captions and a matching SRT.
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
    video_path = video_dir / "final.mp4"
    aspect = "16:9" if length == "long" else "9:16"
    hg = provider.generate_talking_head(
        script=plan.narrative_script,
        voice_id=heygen_voice_id,
        avatar_id=avatar_id,
        output_path=video_path,
        aspect=aspect,
    )

    thumbnail_path = post_dir / "thumbnail.jpg"
    try:
        _extract_thumbnail(hg.video_path, thumbnail_path)
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
