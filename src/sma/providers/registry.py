"""Central provider registry. Looks up provider classes by (kind, name) and instantiates them."""

from __future__ import annotations

from typing import Any, Literal

ProviderKind = Literal["llm", "image", "voice", "music", "social"]


# Lazy import map. Keys are (kind, name); values are dotted paths to classes.
# Lazy because (a) optional deps shouldn't crash unrelated imports, and
# (b) it lets us add providers without touching this dict.
_PROVIDER_PATHS: dict[ProviderKind, dict[str, str]] = {
    "llm": {
        "openai": "sma.providers.llm.openai:OpenAIProvider",
        "anthropic": "sma.providers.llm.anthropic:AnthropicProvider",
        "gemini": "sma.providers.llm.gemini:GeminiProvider",
    },
    "image": {
        "pexels": "sma.providers.image.pexels:PexelsProvider",
        "unsplash": "sma.providers.image.unsplash:UnsplashProvider",
        "nano_banana": "sma.providers.image.nano_banana:NanoBananaProvider",
        "dalle": "sma.providers.image.dalle:DalleProvider",
    },
    "voice": {
        "elevenlabs": "sma.providers.voice.elevenlabs:ElevenLabsVoice",
        "openai_tts": "sma.providers.voice.openai_tts:OpenAITTSVoice",
    },
    "music": {
        "elevenlabs": "sma.providers.music.elevenlabs:ElevenLabsMusic",
        "local": "sma.providers.music.local:LocalMusicProvider",
    },
    "social": {
        "instagram": "sma.providers.social.instagram:InstagramPoster",
        "facebook": "sma.providers.social.facebook:FacebookPoster",
        "youtube": "sma.providers.social.youtube:YouTubePoster",
        "tiktok": "sma.providers.social.tiktok:TikTokPoster",
        "linkedin": "sma.providers.social.linkedin:LinkedInPoster",
    },
}


# Image providers tagged free vs paid. Used by SaaS UI to default new tenants
# to free providers so they don't see surprise image bills.
FREE_IMAGE_PROVIDERS = {"pexels", "unsplash"}

# Which social platforms accept which video formats. The pipeline + UI use
# this to avoid posting horizontal long-form to TikTok or vertical Reels to
# LinkedIn (where it would look terrible).
SHORT_PLATFORMS = {"instagram", "facebook", "tiktok", "youtube"}  # vertical 9:16
LONG_PLATFORMS = {"youtube", "facebook", "linkedin"}              # horizontal 16:9


def platforms_for_format(video_length: str) -> set[str]:
    return LONG_PLATFORMS if video_length == "long" else SHORT_PLATFORMS


class UnknownProvider(Exception):
    pass


def _import_class(dotted: str) -> type[Any]:
    module_path, _, class_name = dotted.partition(":")
    module = __import__(module_path, fromlist=[class_name])
    return getattr(module, class_name)


def get_provider(kind: ProviderKind, name: str, **credentials: Any) -> Any:
    """Instantiate a provider. Credentials passed as keyword args to the constructor."""
    try:
        dotted = _PROVIDER_PATHS[kind][name]
    except KeyError as e:
        raise UnknownProvider(f"No {kind} provider registered as {name!r}") from e
    cls = _import_class(dotted)
    return cls(**credentials)


def list_providers(kind: ProviderKind, free_only: bool = False) -> list[str]:
    """Names of providers registered for a kind. Used by admin panel dropdowns."""
    names = list(_PROVIDER_PATHS.get(kind, {}).keys())
    if free_only and kind == "image":
        names = [n for n in names if n in FREE_IMAGE_PROVIDERS]
    return names
