"""Provider registry — lookup and discovery."""

from __future__ import annotations

import pytest

from sma.providers.registry import (
    FREE_IMAGE_PROVIDERS,
    UnknownProvider,
    get_provider,
    list_providers,
)


def test_list_providers_for_each_kind() -> None:
    assert "openai" in list_providers("llm")
    assert "pexels" in list_providers("image")
    assert "elevenlabs" in list_providers("voice")
    assert "elevenlabs" in list_providers("music")
    assert "tiktok" in list_providers("social")


def test_free_image_filter() -> None:
    free_only = list_providers("image", free_only=True)
    assert "pexels" in free_only
    assert "unsplash" in free_only
    assert "nano_banana" not in free_only
    assert "dalle" not in free_only
    assert FREE_IMAGE_PROVIDERS == {"pexels", "unsplash"}


def test_unknown_provider_raises() -> None:
    with pytest.raises(UnknownProvider):
        get_provider("llm", "no_such_provider", api_key="x")


def test_constructor_arg_validation() -> None:
    # OpenAIProvider raises ValueError when api_key is missing.
    with pytest.raises(ValueError):
        get_provider("llm", "openai", api_key="")


def test_anthropic_stub_instantiates_but_complete_raises() -> None:
    p = get_provider("llm", "anthropic", api_key="dummy")
    with pytest.raises(NotImplementedError):
        p.complete(system="s", user="u", model="claude")
