"""Pricing table calculations."""

from __future__ import annotations

import pytest

from sma.usage import pricing


def test_token_cost_known_model() -> None:
    # gpt-4o-mini = $0.15/1M in, $0.60/1M out
    cost = pricing.cost_for_tokens("openai", "gpt-4o-mini", tokens_in=1_000_000, tokens_out=0)
    assert cost == pytest.approx(0.15)
    cost = pricing.cost_for_tokens("openai", "gpt-4o-mini", tokens_in=0, tokens_out=1_000_000)
    assert cost == pytest.approx(0.60)


def test_token_cost_unknown_returns_zero() -> None:
    assert pricing.cost_for_tokens("openai", "no-such-model", 100, 100) == 0.0
    assert pricing.cost_for_tokens("nobody", "nothing", 100, 100) == 0.0


def test_unit_cost_per_image() -> None:
    # nano_banana = $0.039/image
    assert pricing.cost_for_units("nano_banana", "gemini-2.5-flash-image", 10) == pytest.approx(0.39)


def test_unit_cost_per_char_tts() -> None:
    # tts-1 = $0.000015/char → 1000 chars = $0.015
    assert pricing.cost_for_units("openai", "tts-1", 1000) == pytest.approx(0.015)


def test_free_provider_zero_cost() -> None:
    assert pricing.cost_for_units("pexels", "stock", 100) == 0.0
