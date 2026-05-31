"""Top-level pipeline orchestrator. Topic → finished post directory.

Orchestrates: story analysis → image gen → audio gen → video assembly → thumbnail
→ caption + hashtags → metadata save.

Atomic: writes everything into output_dir, only marks the post 'ready' after
the full pipeline succeeds.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger

from sma.core.content.caption_generator import generate_caption_and_hashtags
from sma.core.content.story_analyzer import StoryPlan, analyze_story
from sma.core.media.audio.orchestrator import build_audio_bundle
from sma.core.media.images.orchestrator import generate_scene_images
from sma.core.media.images.thumbnail import generate_thumbnail
from sma.core.media.video.assembler import assemble_video
from sma.core.media.video.cinematic_assembler import assemble_cinematic_video
from sma.core.niche.config import VideoLength
from sma.core.pipeline.context import PipelineContext
from sma.core.topics.base import Topic


@dataclass
class PipelineResult:
    post_id: str
    output_dir: Path
    video_path: Path
    thumbnail_path: Path
    caption: str
    hashtags: list[str]
    duration_sec: float
    image_count: int
    cost_usd: float


def run_pipeline(
    topic: Topic,
    ctx: PipelineContext,
    output_root: Path,
    *,
    video_length: VideoLength | None = None,
    post_id: str | None = None,
) -> PipelineResult:
    """Generate a complete post for one topic.

    Args:
        topic:        The topic to cover (with title + content).
        ctx:          Pre-built PipelineContext (niche + providers).
        output_root:  Directory under which to create this post's folder.
        video_length: "short" or "long"; if None, falls back to niche default.
        post_id:      Optional explicit ID. If None, derived from topic.id.
    """
    pid = post_id or topic.id
    post_dir = output_root / f"post_{pid}"
    post_dir.mkdir(parents=True, exist_ok=True)
    images_dir = post_dir / "images"
    audio_dir = post_dir / "audio"
    video_dir = post_dir / "video"
    length = video_length or ctx.niche.video_length_default

    logger.info(f"▶ Pipeline start: post={pid} niche={ctx.niche.name!r} length={length}")

    # 1. Story analysis
    plan: StoryPlan = analyze_story(topic, ctx.niche, ctx.llm, video_length=length)

    # 2. Scene images
    # Aspect is derived from the video format: long-format = horizontal 16:9
    # (YouTube/LinkedIn/FB main feed), short = whatever the niche prefers (default 9:16).
    aspect_for_run = "16:9" if length == "long" else None  # None → use niche default
    images = generate_scene_images(
        beats=plan.story_beats,
        topic=topic,
        niche=ctx.niche,
        llm=ctx.llm,
        image_provider=ctx.image,
        output_dir=images_dir,
        aspect_override=aspect_for_run,
    )
    if not images.images:
        raise RuntimeError("Image generation produced zero images; aborting pipeline")

    # If image count came back short, trim beats to match (assembler requires equal counts).
    beats_for_video = plan.story_beats[: len(images.images)]

    # 3. Audio (voiceover + music + mix)
    # Passing `beats` (not `text`) triggers per-beat synthesis. The audio
    # orchestrator MUTATES beats_for_video[i].duration_sec in place with the
    # real measured audio duration, so the video assembler downstream stays
    # in sync with the voiceover.
    audio = build_audio_bundle(
        beats=beats_for_video,
        topic=topic,
        niche=ctx.niche,
        voice=ctx.voice,
        music=ctx.music,
        llm=ctx.llm,
        output_dir=audio_dir,
    )

    # 4. Video assembly
    # long  → cinematic 16:9 horizontal (Ken Burns, no captions, slow xfades) for YouTube/LinkedIn/FB
    # short → vertical 9:16 slideshow with captions for Reels/Shorts/TikTok
    video_dir.mkdir(parents=True, exist_ok=True)
    video_path = video_dir / "final.mp4"
    if length == "long":
        cine_result = assemble_cinematic_video(
            images=images.images,
            beats=beats_for_video,
            audio_path=audio.mixed_path,
            output_path=video_path,
        )
        video_duration = cine_result.duration_sec
    else:
        video_result = assemble_video(
            images=images.images,
            beats=beats_for_video,
            audio_path=audio.mixed_path,
            output_path=video_path,
            hook_text=plan.hook_text,
        )
        video_duration = video_result.duration_sec

    # 5. Thumbnail
    thumbnail_path = post_dir / "thumbnail.jpg"
    generate_thumbnail(
        topic=topic,
        niche=ctx.niche,
        hook_text=plan.hook_text,
        llm=ctx.llm,
        image_provider=ctx.image,
        output_path=thumbnail_path,
        fallback_image=images.images[0],
        aspect_ratio="16:9" if length == "long" else "9:16",
    )

    # 6. Caption + hashtags
    caption_result = generate_caption_and_hashtags(
        topic=topic,
        niche=ctx.niche,
        narrative_script=plan.narrative_script,
        llm=ctx.llm,
    )

    # 7. Save metadata
    cost_usd = images.cost_usd + audio.voiceover.cost_usd
    metadata: dict[str, Any] = {
        "post_id": pid,
        "tenant_id": ctx.tenant_id,
        "video_format": "horizontal_16_9" if length == "long" else "vertical_9_16",
        "niche": ctx.niche.name,
        "topic": topic.to_dict(),
        "video_length": length,
        "video_path": str(video_path.relative_to(post_dir)),
        "thumbnail_path": str(thumbnail_path.relative_to(post_dir)),
        "caption": caption_result.caption,
        "hashtags": caption_result.hashtags,
        "narrative_script": plan.narrative_script,
        "hook_text": plan.hook_text,
        "story_beats": [asdict(b) for b in plan.story_beats],
        "duration_sec": video_duration,
        "image_count": len(images.images),
        "image_provider": images.provider,
        "voice_provider": ctx.voice.name,
        "voice_id": ctx.niche.voice_id,
        "music_provider": ctx.music.name if ctx.music else None,
        "llm_model": ctx.niche.llm_model,
        "media_cost_usd": cost_usd,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "ready",
    }
    (post_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    logger.info(
        f"✔ Pipeline done: post={pid} video={video_path.name} "
        f"({video_duration:.1f}s, ${cost_usd:.4f})"
    )

    return PipelineResult(
        post_id=pid,
        output_dir=post_dir,
        video_path=video_path,
        thumbnail_path=thumbnail_path,
        caption=caption_result.caption,
        hashtags=caption_result.hashtags,
        duration_sec=video_duration,
        image_count=len(images.images),
        cost_usd=cost_usd,
    )
