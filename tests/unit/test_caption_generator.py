"""Hashtag cleanup logic (no LLM calls)."""

from __future__ import annotations

from sma.core.content.caption_generator import _clean_tags


def test_clean_lowercases_and_strips_symbols() -> None:
    assert _clean_tags(["#Fitness", "WORKOUT!", "  health  "]) == ["fitness", "workout", "health"]


def test_clean_dedupes() -> None:
    assert _clean_tags(["fit", "Fit", "FIT", "different"]) == ["fit", "different"]


def test_clean_drops_too_short_too_long() -> None:
    out = _clean_tags(["a", "ok", "x" * 50, "valid"])
    assert "a" not in out
    assert "valid" in out
    assert "ok" in out
    assert "x" * 50 not in out


def test_clean_handles_non_string_input() -> None:
    out = _clean_tags(["fit", 123, None, "valid"])  # type: ignore[list-item]
    assert "fit" in out
    assert "valid" in out
