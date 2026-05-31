"""Pricing table loader. Computes USD cost from token counts or unit counts."""

from __future__ import annotations

from functools import cache
from importlib.resources import files
from typing import Any

import yaml


class UnknownPricing(Exception):
    """Raised when a provider/model has no pricing entry. Cost is recorded as 0."""


@cache
def _load_pricing() -> dict[str, Any]:
    pricing_text = files("sma.usage").joinpath("pricing.yaml").read_text(encoding="utf-8")
    return yaml.safe_load(pricing_text) or {}


def cost_for_tokens(provider: str, model: str, tokens_in: int, tokens_out: int) -> float:
    """Compute USD cost for an LLM call."""
    entry = _entry(provider, model)
    if entry is None or "input_per_1m" not in entry:
        return 0.0
    return (
        tokens_in * entry["input_per_1m"] / 1_000_000
        + tokens_out * entry["output_per_1m"] / 1_000_000
    )


def cost_for_units(provider: str, model: str, units: int) -> float:
    """Compute USD cost for a non-token call (chars for TTS, images for image gen)."""
    entry = _entry(provider, model)
    if entry is None or "per_unit_cost" not in entry:
        return 0.0
    return units * entry["per_unit_cost"]


def _entry(provider: str, model: str) -> dict[str, Any] | None:
    table = _load_pricing()
    return table.get(provider, {}).get(model)
