"""DEPRECATED — kept as a shim for backwards compat.

The pipeline now routes long-format requests to `cinematic_assembler` (horizontal
16:9 with Ken Burns) instead of this module. Importers should switch to:

    from sma.core.media.video.cinematic_assembler import assemble_cinematic_video
"""

from __future__ import annotations

from pathlib import Path

from sma.core.content.story_analyzer import StoryBeat
from sma.core.media.video.cinematic_assembler import (
    CinematicVideoResult,
    assemble_cinematic_video,
)


def assemble_long_video(
    images: list[Path],
    beats: list[StoryBeat],
    audio_path: Path,
    output_path: Path,
    *,
    hook_text: str = "",  # ignored — long-format has no burnt captions
    show_captions: bool = True,  # ignored — same
) -> CinematicVideoResult:
    """Shim that forwards to the cinematic (16:9 horizontal) assembler."""
    return assemble_cinematic_video(
        images=images,
        beats=beats,
        audio_path=audio_path,
        output_path=output_path,
    )
