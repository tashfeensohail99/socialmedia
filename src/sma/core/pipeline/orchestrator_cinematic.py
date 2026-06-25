"""HeyGen Seedance 2.0 cinematic ad pipeline (Tier A).

Produces a silent B-roll clip (4-15s) of a trained avatar inside a scene
described by a visual prompt. The /v3/videos cinematic_avatar endpoint takes
NO script and NO voice — it's pure visual. The brand is communicated via the
hardcoded Tashfeen CTA badge burned in at the end.

Pipeline:
  1. analyze_story (reused)  → narrative_script gives us the topic angle
  2. Build a visual prompt from niche.cinematic_prompt_style + the topic
  3. Pick avatar from niche.avatar_library_ids (round-robin by post_id)
  4. HeyGen /v3/videos cinematic_avatar (~$7, ~5-10 min)
  5. Apply Tashfeen CTA (3s capped at 40% of duration for short clips)
  6. Thumbnail = first frame
  7. Caption + hashtags (reused — slightly off-style for an ad but acceptable)

Returns the same PipelineResult dataclass so db_runner persistence works
unchanged.
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
from sma.core.media.video.cta_overlay import apply_brand_cta
from sma.core.niche.config import VideoLength
from sma.core.pipeline.context import PipelineContext
from sma.core.pipeline.orchestrator import PipelineResult
from sma.core.pipeline.orchestrator_heygen import _extract_thumbnail, _pick_avatar
from sma.core.topics.base import Topic
from sma.providers.avatar.heygen import HeyGenAvatarProvider

# Visual-prompt presets — each key is what niche.cinematic_prompt_style stores.
# These prefixes get prepended to the topic angle to produce the final prompt
# that Seedance 2.0 renders.
_STYLE_PROMPTS: dict[str, str] = {
    "immigration_office": (
        "Cinematic shot inside a modern, sunlit immigration consultancy office. "
        "Documentary style, handheld camera, shallow depth of field. "
        "The professional consultant is reviewing paperwork at a clean desk "
        "with a laptop, passport, and visa documents visible. "
        "Warm golden window light, calm confident energy."
    ),
    "hopeful_documentary": (
        "Cinematic documentary-style scene, warm natural lighting, "
        "shallow depth of field, handheld 50mm lens. "
        "Hopeful, confident, professional energy."
    ),
    "verite_street": (
        "Verité street-style shot, natural daylight, candid handheld camera, "
        "shallow focus, urban setting in the background."
    ),
    "golden_hour": (
        "Golden-hour cinematic shot, warm orange backlight, dreamy depth of field, "
        "slow movement, hopeful tone."
    ),
}


def _build_cinematic_prompt(style_key: str, topic: Topic, niche_name: str) -> str:
    prefix = _STYLE_PROMPTS.get(style_key, _STYLE_PROMPTS["hopeful_documentary"])
    # Strip the topic to a short visual angle hint — Seedance handles long
    # prompts (10000 char cap) but stays on-style better with a concise scene.
    title = (topic.title or "").strip()[:200]
    return (
        f"{prefix} "
        f"The scene visually evokes the topic: \"{title}\". "
        f"Brand context: {niche_name}. No on-screen text, no captions."
    )


def run_pipeline_cinematic(
    topic: Topic,
    ctx: PipelineContext,
    output_root: Path,
    *,
    avatar_library_ids: list[str],
    cinematic_prompt_style: str = "immigration_office",
    cinematic_duration_sec: int = 8,
    cinematic_resolution: str = "720p",
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
        f"▶ Cinematic pipeline start: post={pid} niche={ctx.niche.name!r} "
        f"dur={cinematic_duration_sec}s res={cinematic_resolution}"
    )

    # 1. Story analysis — gives us a narrative angle to feed into the visual prompt.
    plan: StoryPlan = analyze_story(topic, ctx.niche, ctx.llm, video_length=length)

    # 2. Visual prompt
    prompt = _build_cinematic_prompt(
        style_key=cinematic_prompt_style,
        topic=topic,
        niche_name=ctx.niche.name,
    )

    # 3. Avatar
    avatar_id = _pick_avatar(list(avatar_library_ids), pid)
    logger.info(f"Cinematic avatar chosen: {avatar_id}")

    # 4. HeyGen Seedance 2.0 render
    provider = HeyGenAvatarProvider()
    raw_video_path = video_dir / "cinematic_raw.mp4"
    hg = provider.generate_cinematic(
        prompt=prompt,
        avatar_id=avatar_id,
        output_path=raw_video_path,
        duration_sec=cinematic_duration_sec,
        resolution=cinematic_resolution,
        aspect="9:16",
        title=f"{ctx.niche.name[:80]} — {topic.title[:40]}",
    )

    # 5. CTA — short clip needs a short CTA. apply_brand_cta caps the badge
    # at 40% of duration anyway, but pass 3s explicitly so an 8s clip gets
    # a 3s CTA (not the default 5s which would be capped to 3.2s).
    video_path = apply_brand_cta(
        src_video=hg.video_path,
        duration_sec=hg.duration_sec,
        cta_png=output_root / "_cta_tashfeen.png",
        cta_seconds=3.0,
    )

    # 6. Thumbnail
    thumbnail_path = post_dir / "thumbnail.jpg"
    try:
        _extract_thumbnail(video_path, thumbnail_path)
    except Exception as e:
        logger.warning(f"cinematic thumbnail extract failed (non-fatal): {e}")

    # 7. Caption + hashtags
    caption_result = generate_caption_and_hashtags(
        topic=topic,
        niche=ctx.niche,
        narrative_script=plan.narrative_script,
        llm=ctx.llm,
    )

    metadata: dict[str, Any] = {
        "post_id": pid,
        "tenant_id": ctx.tenant_id,
        "video_format": "vertical_9_16",
        "pipeline_kind": "cinematic",
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
        "image_provider": "heygen_cinematic",
        "voice_provider": None,  # silent v1 — no narration
        "voice_id": None,
        "music_provider": None,
        "llm_model": ctx.niche.llm_model,
        "media_cost_usd": hg.cost_usd,
        "avatar_id": avatar_id,
        "avatar_cost_usd": hg.cost_usd,
        "heygen_video_id": hg.video_id,
        "cinematic_prompt": prompt,
        "cinematic_resolution": cinematic_resolution,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "ready",
    }
    (post_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    logger.info(
        f"✔ Cinematic pipeline done: post={pid} video={video_path.name} "
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
