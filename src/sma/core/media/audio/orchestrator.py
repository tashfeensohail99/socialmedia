"""Audio orchestrator: voiceover (chunked for long videos) + music + mix."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from loguru import logger

from sma.core.content.story_analyzer import StoryBeat
from sma.core.niche.config import NicheConfig
from sma.core.templates import render
from sma.core.topics.base import Topic
from sma.providers.llm.base import LLMProvider
from sma.providers.music.base import MusicProvider
from sma.providers.voice.base import VoiceProvider, VoiceResult

# ElevenLabs hard cap per request — split longer scripts into chunks.
_VOICE_CHUNK_CHARS = 4500
_MUSIC_VOLUME = 0.18  # background music level relative to voiceover (1.0)


@dataclass
class AudioBundle:
    voiceover_path: Path
    music_path: Path | None
    mixed_path: Path
    voiceover: VoiceResult
    duration_sec: float


def synthesize_voiceover(
    text: str,
    niche: NicheConfig,
    voice: VoiceProvider,
    output_path: Path,
) -> VoiceResult:
    """Single-shot for short text; chunked + concatenated via ffmpeg for long text."""
    if len(text) <= _VOICE_CHUNK_CHARS:
        return voice.synthesize(
            text=text, voice_id=niche.voice_id, output_path=output_path, model=niche.voice_model
        )

    # Chunk on sentence boundaries.
    chunks = _chunk_text(text, _VOICE_CHUNK_CHARS)
    logger.info(f"Voiceover script is {len(text)} chars; synthesizing {len(chunks)} chunks")

    chunk_paths: list[Path] = []
    total_chars = 0
    total_cost = 0.0
    output_path.parent.mkdir(parents=True, exist_ok=True)
    for i, chunk in enumerate(chunks):
        chunk_path = output_path.with_name(f"{output_path.stem}_part{i:02d}.mp3")
        result = voice.synthesize(
            text=chunk, voice_id=niche.voice_id, output_path=chunk_path, model=niche.voice_model
        )
        chunk_paths.append(chunk_path)
        total_chars += result.chars
        total_cost += result.cost_usd

    _ffmpeg_concat(chunk_paths, output_path)
    for p in chunk_paths:
        p.unlink(missing_ok=True)

    return VoiceResult(
        path=output_path,
        duration_sec=total_chars / 15.0,
        chars=total_chars,
        cost_usd=total_cost,
        provider=voice.name,
        voice_id=niche.voice_id,
    )


def generate_background_music(
    topic: Topic,
    niche: NicheConfig,
    duration_sec: float,
    music: MusicProvider,
    llm: LLMProvider,
    output_path: Path,
    mood_hint: str | None = None,
) -> Path | None:
    """Generates a music prompt via LLM (for generative providers), then calls
    the music provider. Local/bundled providers ignore the prompt, so we skip
    the LLM call entirely for them to save cost + latency."""
    if not niche.music_enabled:
        return None
    provider_name = getattr(music, "name", "")
    if provider_name == "local":
        music_prompt = ""  # bundled tracks don't use a prompt
    else:
        prompt_template = render(
            "music_prompt.j2", niche=niche, topic=topic, mood_hint=mood_hint or ""
        )
        resp = llm.complete(
            system="You write music-generation prompts. Be specific about genre, tempo, instruments.",
            user=prompt_template,
            model=niche.llm_model,
            temperature=0.7,
        )
        music_prompt = resp.text.strip()
    try:
        result = music.generate(
            prompt=music_prompt, duration_sec=duration_sec, output_path=output_path
        )
    except Exception as e:
        # Music is non-essential — log and continue without it so the pipeline still
        # produces a video. Common cause: free-tier accounts on paid music APIs (402).
        logger.warning(
            f"Music generation failed; continuing without background music. "
            f"Reason: {e}"
        )
        return None
    return result.path


def mix_voice_and_music(
    voiceover_path: Path,
    music_path: Path | None,
    output_path: Path,
    music_volume: float = _MUSIC_VOLUME,
) -> Path:
    """ffmpeg mix: voiceover at full volume + music looped to match + ducked."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if music_path is None or not music_path.exists():
        # No music — just copy the voiceover as the final mix.
        _ffmpeg_copy_audio(voiceover_path, output_path)
        return output_path

    # filter:
    #   [0:a] = voiceover (passthrough)
    #   [1:a] = music, looped via stream_loop -1, trimmed to voiceover duration, volume-scaled
    cmd = [
        "ffmpeg", "-y",
        "-i", str(voiceover_path),
        "-stream_loop", "-1", "-i", str(music_path),
        "-filter_complex",
        f"[1:a]volume={music_volume}[bg];"
        "[0:a][bg]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[a]",
        "-map", "[a]",
        "-c:a", "libmp3lame", "-b:a", "192k",
        str(output_path),
    ]
    _run(cmd)
    return output_path


def synthesize_voiceover_per_beat(
    beats: list[StoryBeat],
    niche: NicheConfig,
    voice: VoiceProvider,
    output_dir: Path,
) -> tuple[VoiceResult, list[float]]:
    """Synthesize each beat's voiceover_segment as its own audio clip, concat them
    into a single voiceover.mp3, and return the actual measured duration of each
    beat.

    This is the fix for caption/voice desync: we no longer trust the LLM's
    estimated `beat.duration_sec` — we measure the real audio.

    Returns:
        (combined_voice_result, per_beat_actual_durations_seconds)
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    final_path = output_dir / "voiceover.mp3"

    chunk_paths: list[Path] = []
    real_durations: list[float] = []
    total_chars = 0
    total_cost = 0.0

    for i, beat in enumerate(beats):
        prev_text = beats[i - 1].voiceover_segment if i > 0 else None
        next_text = beats[i + 1].voiceover_segment if i < len(beats) - 1 else None

        chunk_path = output_dir / f"_voiceover_beat{i:02d}.mp3"
        result = voice.synthesize(
            text=beat.voiceover_segment,
            voice_id=niche.voice_id,
            output_path=chunk_path,
            model=niche.voice_model,
            previous_text=prev_text,
            next_text=next_text,
        )
        chunk_paths.append(chunk_path)
        total_chars += result.chars
        total_cost += result.cost_usd

        # Measure the ACTUAL duration of the synthesized audio — this is the
        # number that drives both image holds and caption timing.
        measured = _probe_audio_duration(chunk_path)
        real_durations.append(measured)
        logger.debug(
            f"Beat {i}: {result.chars} chars synthesized in {measured:.2f}s "
            f"(LLM estimate was {beat.duration_sec:.2f}s)"
        )

    _ffmpeg_concat(chunk_paths, final_path)
    for p in chunk_paths:
        p.unlink(missing_ok=True)

    combined_duration = sum(real_durations)

    return (
        VoiceResult(
            path=final_path,
            duration_sec=combined_duration,
            chars=total_chars,
            cost_usd=total_cost,
            provider=voice.name,
            voice_id=niche.voice_id,
        ),
        real_durations,
    )


def build_audio_bundle(
    topic: Topic,
    niche: NicheConfig,
    voice: VoiceProvider,
    music: MusicProvider | None,
    llm: LLMProvider,
    output_dir: Path,
    *,
    beats: list[StoryBeat] | None = None,
    text: str | None = None,
) -> AudioBundle:
    """Build voiceover + music + mix.

    When `beats` is provided (preferred), each beat is synthesized separately
    and the beats' `duration_sec` is MUTATED IN PLACE with the real measured
    audio duration. The video assembler then uses these real durations so
    captions and images stay perfectly in sync with the voiceover.

    When only `text` is given (backwards-compat), falls back to single-shot
    synthesis with LLM-estimated timing (the old, drift-prone behavior).
    """
    if beats is None and text is None:
        raise ValueError("build_audio_bundle requires either `beats` or `text`")

    output_dir.mkdir(parents=True, exist_ok=True)
    vo_path = output_dir / "voiceover.mp3"
    music_path = output_dir / "music.mp3"
    mixed_path = output_dir / "audio_mixed.mp3"

    if beats:
        vo, real_durations = synthesize_voiceover_per_beat(beats, niche, voice, output_dir)
        # Mutate beat durations IN PLACE so downstream (video assembler) uses real timing.
        for beat, real_dur in zip(beats, real_durations):
            beat.duration_sec = real_dur
    else:
        vo = synthesize_voiceover(text or "", niche, voice, vo_path)

    music_file: Path | None = None
    if music is not None and niche.music_enabled:
        music_file = generate_background_music(
            topic=topic,
            niche=niche,
            duration_sec=vo.duration_sec,
            music=music,
            llm=llm,
            output_path=music_path,
        )

    mix_voice_and_music(vo.path, music_file, mixed_path)
    return AudioBundle(
        voiceover_path=vo.path,
        music_path=music_file,
        mixed_path=mixed_path,
        voiceover=vo,
        duration_sec=vo.duration_sec,
    )


def _probe_audio_duration(path: Path) -> float:
    """Get the actual duration of an audio file in seconds via ffprobe."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "json",
        str(path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        logger.error(f"ffprobe failed for {path}: {proc.stderr[-300:]}")
        raise RuntimeError(f"Could not probe duration for {path}")
    data = json.loads(proc.stdout)
    return float(data["format"]["duration"])


# ─── helpers ──────────────────────────────────────────────────


def _chunk_text(text: str, max_chars: int) -> list[str]:
    """Split on sentence boundaries; never breaks a sentence."""
    import re
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    chunks: list[str] = []
    cur = ""
    for s in sentences:
        if len(cur) + len(s) + 1 <= max_chars:
            cur = (cur + " " + s).strip()
        else:
            if cur:
                chunks.append(cur)
            cur = s
    if cur:
        chunks.append(cur)
    return chunks


def _ffmpeg_concat(parts: list[Path], output: Path) -> None:
    list_file = output.with_suffix(".txt")
    list_file.write_text(
        "".join(f"file '{p.resolve().as_posix()}'\n" for p in parts), encoding="utf-8"
    )
    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(list_file), "-c", "copy", str(output),
    ]
    _run(cmd)
    list_file.unlink(missing_ok=True)


def _ffmpeg_copy_audio(src: Path, dst: Path) -> None:
    cmd = ["ffmpeg", "-y", "-i", str(src), "-c", "copy", str(dst)]
    _run(cmd)


def _run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        logger.error(f"ffmpeg failed ({proc.returncode}): {proc.stderr[-500:]}")
        raise RuntimeError(f"ffmpeg failed: {' '.join(cmd[:6])}...")
