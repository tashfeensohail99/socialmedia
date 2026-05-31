"""Video assembler. Slideshow vertical video with crossfades + caption overlays.

ffmpeg-based for speed and determinism. The output is 1080x1920 H.264 MP4
with embedded mixed audio (voiceover + ducked music).
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from loguru import logger

from sma.core.content.story_analyzer import StoryBeat

# Output format
_W, _H = 1080, 1920
_FPS = 30
_CROSSFADE_SEC = 0.4

# Caption style (drawtext)
_CAPTION_FONT_SIZE = 48
_CAPTION_BOX_OPACITY = 0.6
_CAPTION_MAX_CHARS_PER_LINE = 32  # tuned for fontsize=48 in a bold font at 1080px wide
_CAPTION_MAX_LINES = 3            # → max ~96 chars on screen; longer gets truncated
_CAPTION_LINE_SPACING = 10        # extra px between wrapped lines
_CAPTION_BOTTOM_MARGIN = 220      # px above the bottom edge — leaves room for IG/TikTok UI


@dataclass
class VideoResult:
    path: Path
    duration_sec: float
    width: int = _W
    height: int = _H
    fps: int = _FPS


def assemble_video(
    images: list[Path],
    beats: list[StoryBeat],
    audio_path: Path,
    output_path: Path,
    *,
    hook_text: str = "",
    show_captions: bool = True,
) -> VideoResult:
    """Build a vertical slideshow video.

    Each beat's image is shown for `beat.duration_sec` seconds, with a short
    crossfade between consecutive beats. Captions (the voiceover_segment text)
    are overlaid as drawtext during the corresponding beat.
    """
    if len(images) != len(beats):
        logger.warning(
            f"Image count ({len(images)}) != beat count ({len(beats)}); "
            "trimming to the shorter list"
        )
    pairs = list(zip(images, beats))
    if not pairs:
        raise ValueError("No images/beats provided to assemble video")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Build the ffmpeg command in 3 stages:
    # 1) Per-image input streams scaled+padded to 1080x1920
    # 2) xfade chain to crossfade between scenes
    # 3) Caption drawtext overlays + audio mixin

    inputs: list[str] = []
    filter_parts: list[str] = []
    timeline_offset = 0.0
    last_label = None

    for idx, (img, beat) in enumerate(pairs):
        dur = max(0.5, beat.duration_sec)
        # Hold the image as a video stream of `dur` seconds
        inputs += ["-loop", "1", "-t", f"{dur:.3f}", "-i", str(img)]
        scale = (
            f"[{idx}:v]scale={_W}:{_H}:force_original_aspect_ratio=increase,"
            f"crop={_W}:{_H},setsar=1,fps={_FPS}[v{idx}]"
        )
        filter_parts.append(scale)

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

    # Optional captions overlay — write each caption line to a small text file
    # and have drawtext read it via textfile=. This sidesteps ALL of ffmpeg's
    # filter-string escaping rules, which break on apostrophes, colons, and
    # other punctuation in long-form LLM output.
    final_label = last_label
    captions_dir: Path | None = None
    if show_captions:
        captions_dir = output_path.parent / "_captions"
        captions_dir.mkdir(parents=True, exist_ok=True)
        final_label = "vcap"
        captions_filter = _build_captions_filter(
            beats, last_label, final_label, hook_text, captions_dir
        )
        filter_parts.append(captions_filter)

    # Audio input (last)
    audio_idx = len(pairs)
    inputs += ["-i", str(audio_path)]

    filter_complex = ";".join(filter_parts)

    cmd = [
        "ffmpeg", "-y",
        *inputs,
        "-filter_complex", filter_complex,
        "-map", f"[{final_label}]",
        "-map", f"{audio_idx}:a",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "medium", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        "-shortest",
        str(output_path),
    ]
    _run(cmd)
    return VideoResult(path=output_path, duration_sec=timeline_offset)


def _build_captions_filter(
    beats: list[StoryBeat],
    in_label: str,
    out_label: str,
    hook_text: str,
    captions_dir: Path,
) -> str:
    """Build the drawtext filter chain for captions + hook overlay.

    Strategy:
    1. Wrap each beat's voiceover into multiple short lines.
    2. Write each line to a tiny .txt file under `captions_dir`.
    3. Emit one drawtext per line stacked vertically, using `textfile=<path>`
       so ffmpeg reads raw bytes from disk and we never have to escape
       apostrophes, colons, or other punctuation inside the filter graph.

    Per-line drawtext (rather than one per beat) gives us per-line centering
    for free and avoids the multi-line `\n` escaping rabbit hole.
    """
    parts: list[str] = []
    cur_label = in_label
    t = 0.0
    # Effective per-line vertical step: fontsize + line spacing + 2x box padding.
    line_step = _CAPTION_FONT_SIZE + _CAPTION_LINE_SPACING + 24

    for beat_idx, beat in enumerate(beats):
        end = t + max(0.5, beat.duration_sec)
        wrapped = _wrap_to_lines(
            beat.voiceover_segment,
            max_chars_per_line=_CAPTION_MAX_CHARS_PER_LINE,
            max_lines=_CAPTION_MAX_LINES,
        )
        if not wrapped:
            t = end
            continue

        n_lines = len(wrapped)
        top_y_for_block = _H - _CAPTION_BOTTOM_MARGIN - (line_step * n_lines)

        for line_idx, line_text in enumerate(wrapped):
            txt_path = captions_dir / f"cap_{beat_idx:03d}_{line_idx}.txt"
            txt_path.write_text(line_text, encoding="utf-8")
            new_label = f"cap{beat_idx}_{line_idx}"
            line_y = top_y_for_block + (line_idx * line_step)
            parts.append(
                f"[{cur_label}]drawtext="
                f"textfile={_filter_path(txt_path)}:"
                f"fontcolor=white:"
                f"fontsize={_CAPTION_FONT_SIZE}:"
                f"box=1:boxcolor=black@{_CAPTION_BOX_OPACITY}:boxborderw=14:"
                f"x=(w-text_w)/2:y={line_y}:"
                f"enable='between(t,{t:.3f},{end:.3f})'"
                f"[{new_label}]"
            )
            cur_label = new_label
        t = end

    # Hook text overlay during the first 3 seconds.
    if hook_text:
        hook_lines = _wrap_to_lines(hook_text, max_chars_per_line=20, max_lines=2)
        hook_line_step = 64 + 14 + 28
        hook_top_y = 180
        for line_idx, line_text in enumerate(hook_lines):
            txt_path = captions_dir / f"hook_{line_idx}.txt"
            txt_path.write_text(line_text, encoding="utf-8")
            new_label = f"hook_{line_idx}"
            parts.append(
                f"[{cur_label}]drawtext="
                f"textfile={_filter_path(txt_path)}:"
                f"fontcolor=white:fontsize=64:"
                f"box=1:boxcolor=black@0.65:boxborderw=20:"
                f"x=(w-text_w)/2:y={hook_top_y + line_idx * hook_line_step}:"
                f"enable='between(t,0,3)'"
                f"[{new_label}]"
            )
            cur_label = new_label

    parts.append(f"[{cur_label}]null[{out_label}]")
    return ";".join(parts)


def _filter_path(path: Path) -> str:
    """Format a filesystem path so ffmpeg's filter parser accepts it.

    On Windows, backslashes and the drive-letter colon would otherwise be
    interpreted as escape chars / option separators. Forward-slashes are
    universally accepted, and we wrap in single quotes to allow spaces.
    """
    return "'" + str(path).replace("\\", "/").replace(":", "\\:") + "'"


def _wrap_to_lines(text: str, max_chars_per_line: int, max_lines: int) -> list[str]:
    """Word-wrap text into at most `max_lines` lines, each at most `max_chars_per_line`.

    If the text doesn't fit, the last line is truncated with an ellipsis.
    Returns an empty list for empty/whitespace input.
    """
    text = text.strip().replace("\n", " ")
    if not text:
        return []
    words = text.split()
    lines: list[str] = []
    cur = ""
    for w in words:
        candidate = (cur + " " + w).strip() if cur else w
        if len(candidate) <= max_chars_per_line:
            cur = candidate
        else:
            if cur:
                lines.append(cur)
            cur = w
            if len(lines) >= max_lines:
                break
    if cur and len(lines) < max_lines:
        lines.append(cur)

    # If we ran out of room, ellipsize the last line and signal overflow.
    if len(lines) == max_lines:
        consumed_chars = sum(len(line) for line in lines) + (len(lines) - 1)
        if consumed_chars < len(text):
            last = lines[-1]
            if len(last) > max_chars_per_line - 1:
                last = last[: max_chars_per_line - 1]
            lines[-1] = last.rstrip() + "…"
    return lines


def _truncate_for_caption(text: str, max_chars: int = 90) -> str:
    """Legacy single-line truncator (kept for tests). Prefer _wrap_to_lines."""
    text = text.strip().replace("\n", " ")
    return text if len(text) <= max_chars else text[: max_chars - 1] + "…"


def _escape_drawtext(text: str) -> str:
    """ffmpeg drawtext requires escaping single quotes, colons, backslashes, and percents.

    We no longer try to encode line breaks here — multi-line captions are rendered
    by emitting one drawtext node per line in _build_captions_filter, which is far
    more reliable than fighting ffmpeg's filter-arg escaping rules.
    """
    return (
        text.replace("\\", "\\\\")
        .replace(":", "\\:")
        .replace("'", "\\'")
        .replace("%", "\\%")
        .replace("\n", " ")  # any stray newline becomes a space — never reaches ffmpeg
    )


def _run(cmd: list[str]) -> None:
    logger.debug(f"ffmpeg: {' '.join(cmd[:8])}... ({len(cmd)} args)")
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        # Dump the full command + stderr to a file so we can debug complex filter
        # graph failures (otherwise the stderr cap loses what we need).
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
            logger.error(f"ffmpeg failed ({proc.returncode}) — full dump at {dump}")
        except Exception:
            pass
        logger.error(f"ffmpeg stderr (tail):\n{proc.stderr[-2000:]}")
        raise RuntimeError("ffmpeg video assembly failed")
