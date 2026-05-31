"""Cinematic 16:9 horizontal video assembler for long-format (YouTube main feed).

Differences vs the vertical short-video assembler:
- Output is 1920x1080 (16:9 horizontal), not 1080x1920 vertical
- Each scene gets a slow Ken Burns zoom (zoompan filter) — typical 8-15s holds
- NO burnt-in captions — long-form viewers prefer YouTube's auto-captions
- Slower crossfades (0.8s vs 0.4s) for a more cinematic feel
- Audio is the per-beat synthesized voice (same as short flow)
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from loguru import logger

from sma.core.content.story_analyzer import StoryBeat

# 16:9 horizontal — standard YouTube long-form
_W, _H = 1920, 1080
_FPS = 30
_CROSSFADE_SEC = 0.8                  # slower, more cinematic transition
_KEN_BURNS_ZOOM_RATE = 0.0008         # zoom-in rate per frame; gentle
_KEN_BURNS_MAX_ZOOM = 1.25            # ~25% zoom over the scene


@dataclass
class CinematicVideoResult:
    path: Path
    duration_sec: float
    width: int = _W
    height: int = _H
    fps: int = _FPS


def assemble_cinematic_video(
    images: list[Path],
    beats: list[StoryBeat],
    audio_path: Path,
    output_path: Path,
) -> CinematicVideoResult:
    """Build a horizontal 16:9 cinematic video from images + beats + audio.

    Each beat's image gets a slow Ken Burns zoom for `beat.duration_sec`.
    No on-screen captions — YouTube auto-CC handles that for long-form.
    """
    if len(images) != len(beats):
        logger.warning(
            f"Image count ({len(images)}) != beat count ({len(beats)}); "
            "trimming to the shorter list"
        )
    pairs = list(zip(images, beats))
    if not pairs:
        raise ValueError("No images/beats provided to assemble cinematic video")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    inputs: list[str] = []
    filter_parts: list[str] = []
    timeline_offset = 0.0
    last_label: str | None = None

    for idx, (img, beat) in enumerate(pairs):
        dur = max(1.0, beat.duration_sec)
        n_frames = max(_FPS, int(dur * _FPS))  # at least 1s worth of frames

        inputs += ["-loop", "1", "-t", f"{dur:.3f}", "-i", str(img)]

        # 1) Scale up to a large canvas (zoompan needs headroom or it gets jittery).
        # 2) Run zoompan: slow zoom-in from 1.0 to ~1.25, centered.
        # 3) Final size = 1920x1080.
        # The large intermediate scale eliminates the famous zoompan "jitter" artifact.
        scale_pre = 4  # render input at 4x output size first
        prep = (
            f"[{idx}:v]"
            f"scale={_W * scale_pre}:{_H * scale_pre}:"
            f"force_original_aspect_ratio=increase,"
            f"crop={_W * scale_pre}:{_H * scale_pre},"
            f"setsar=1,fps={_FPS}"
            f"[scaled{idx}]"
        )
        filter_parts.append(prep)

        zoompan = (
            f"[scaled{idx}]"
            f"zoompan="
            f"z='min(zoom+{_KEN_BURNS_ZOOM_RATE},{_KEN_BURNS_MAX_ZOOM})':"
            f"x='iw/2-(iw/zoom/2)':"
            f"y='ih/2-(ih/zoom/2)':"
            f"d={n_frames}:s={_W}x{_H}:fps={_FPS}"
            f"[v{idx}]"
        )
        filter_parts.append(zoompan)

        if last_label is None:
            last_label = f"v{idx}"
            timeline_offset = dur
        else:
            xfade_offset = max(0.0, timeline_offset - _CROSSFADE_SEC)
            new_label = f"x{idx}"
            filter_parts.append(
                f"[{last_label}][v{idx}]xfade=transition=fade:"
                f"duration={_CROSSFADE_SEC}:offset={xfade_offset:.3f}[{new_label}]"
            )
            last_label = new_label
            timeline_offset += dur - _CROSSFADE_SEC

    # Audio input goes last; final video label is whatever the chain ended on.
    audio_idx = len(pairs)
    inputs += ["-i", str(audio_path)]

    filter_complex = ";".join(filter_parts)

    cmd = [
        "ffmpeg", "-y",
        *inputs,
        "-filter_complex", filter_complex,
        "-map", f"[{last_label}]",
        "-map", f"{audio_idx}:a",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-preset", "medium",
        "-crf", "20",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        "-shortest",
        str(output_path),
    ]
    _run(cmd)
    return CinematicVideoResult(path=output_path, duration_sec=timeline_offset)


def _run(cmd: list[str]) -> None:
    logger.debug(f"ffmpeg (cinematic): {' '.join(cmd[:8])}... ({len(cmd)} args)")
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        from pathlib import Path as _P
        dump = _P("data/ffmpeg_last_fail.txt")
        try:
            dump.parent.mkdir(parents=True, exist_ok=True)
            dump.write_text(
                "=== STDERR ===\n" + proc.stderr +
                "\n\n=== ARGS ===\n" + "\n".join(repr(a) for a in cmd) +
                "\n\n=== FILTER ===\n" + (
                    cmd[cmd.index("-filter_complex") + 1] if "-filter_complex" in cmd else "(none)"
                ),
                encoding="utf-8",
            )
            logger.error(f"ffmpeg failed ({proc.returncode}) — dump at {dump}")
        except Exception:
            pass
        logger.error(f"ffmpeg stderr (tail):\n{proc.stderr[-2000:]}")
        raise RuntimeError("cinematic video assembly failed")
