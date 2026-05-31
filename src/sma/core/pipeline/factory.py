"""Factory: turns a NicheConfig + Settings into an instantiated PipelineContext."""

from __future__ import annotations

from sma.config import Settings
from sma.core.niche.config import NicheConfig
from sma.core.pipeline.context import PipelineContext
from sma.providers.image.base import ImageProvider
from sma.providers.llm.base import LLMProvider
from sma.providers.music.base import MusicProvider
from sma.providers.registry import get_provider
from sma.providers.voice.base import VoiceProvider


# Maps each provider's name to the credentials it needs from Settings.
def _llm_creds(name: str, s: Settings) -> dict:
    return {
        "openai": {"api_key": s.openai_api_key},
        "anthropic": {"api_key": s.anthropic_api_key},
        "gemini": {"api_key": s.gemini_api_key},
    }[name]


def _image_creds(name: str, s: Settings) -> dict:
    return {
        "pexels": {"api_key": s.pexels_api_key},
        "unsplash": {"access_key": s.unsplash_access_key},
        "nano_banana": {"api_key": s.gemini_api_key},
        "dalle": {"api_key": s.openai_api_key},
    }[name]


def _voice_creds(name: str, s: Settings) -> dict:
    return {
        "elevenlabs": {"api_key": s.elevenlabs_api_key},
        "openai_tts": {"api_key": s.openai_api_key},
    }[name]


def _music_creds(name: str, s: Settings) -> dict:
    return {
        "elevenlabs": {"api_key": s.elevenlabs_api_key},
    }[name]


def build_context(niche: NicheConfig, settings: Settings, tenant_id: int = 1) -> PipelineContext:
    llm: LLMProvider = get_provider("llm", niche.llm_provider, **_llm_creds(niche.llm_provider, settings))
    image: ImageProvider = get_provider(
        "image", niche.image_provider, **_image_creds(niche.image_provider, settings)
    )
    voice: VoiceProvider = get_provider(
        "voice", niche.voice_provider, **_voice_creds(niche.voice_provider, settings)
    )
    music: MusicProvider | None = None
    if niche.music_enabled:
        music = get_provider(
            "music", niche.music_provider, **_music_creds(niche.music_provider, settings)
        )
    return PipelineContext(
        niche=niche,
        llm=llm,
        image=image,
        voice=voice,
        music=music,
        tenant_id=tenant_id,
    )
