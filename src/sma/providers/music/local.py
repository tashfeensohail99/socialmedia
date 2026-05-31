"""Local background-music provider.

Instead of calling a paid music-generation API (ElevenLabs Music, blocked on
free tier / cloud IPs), this provider serves a track bundled with the app from
`assets/music/`. The audio mixer loops + trims it to match the voiceover length,
so a short track still covers a long video.

Selection is deterministic-per-call but varied across posts: we pick a track by
hashing the output path's parent (the post dir), so each post gets a stable but
rotating choice across the available tracks.
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from loguru import logger

from sma.providers.music.base import MusicResult

def _candidate_dirs() -> list[Path]:
    """Possible locations of the bundled music assets.

    Layout is <repo>/src/sma/providers/music/local.py with assets at
    <repo>/assets/music. From this file that's parents[4]/assets/music. We also
    try the CWD-relative path (Docker runs with CWD=/app) and a couple of
    fallbacks so it works in dev + container regardless of how it's launched.
    """
    here = Path(__file__).resolve()
    cands: list[Path | None] = [
        here.parents[4] / "assets" / "music" if len(here.parents) > 4 else None,
        Path("assets/music"),
        here.parents[3] / "assets" / "music" if len(here.parents) > 3 else None,
        here.parents[5] / "assets" / "music" if len(here.parents) > 5 else None,
    ]
    return [c for c in cands if c is not None]


class LocalMusicProvider:
    name = "local"

    def __init__(self, **_ignore: object) -> None:
        # No credentials needed. Accept/ignore any kwargs so the registry can
        # pass tenant creds uniformly.
        self._tracks: list[Path] = []
        for d in _candidate_dirs():
            if d.is_dir():
                self._tracks = sorted(p for p in d.glob("*.mp3") if p.is_file())
                if self._tracks:
                    logger.debug(f"LocalMusicProvider: {len(self._tracks)} tracks in {d}")
                    break
        if not self._tracks:
            logger.warning("LocalMusicProvider: no bundled tracks found in assets/music")

    def generate(
        self,
        prompt: str,
        duration_sec: float,
        output_path: Path,
        model: str | None = None,
    ) -> MusicResult:
        if not self._tracks:
            raise FileNotFoundError(
                "No bundled music tracks available (assets/music/*.mp3 missing)"
            )

        # Pick a track that varies per post but is stable for a given output dir.
        key = str(output_path.parent)
        idx = int(hashlib.sha256(key.encode()).hexdigest(), 16) % len(self._tracks)
        track = self._tracks[idx]

        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(track, output_path)
        logger.info(f"LocalMusicProvider: using {track.name} for {output_path.parent.name}")

        return MusicResult(
            path=output_path,
            duration_sec=duration_sec,
            cost_usd=0.0,
            provider=self.name,
            prompt=f"(local track: {track.name})",
        )
