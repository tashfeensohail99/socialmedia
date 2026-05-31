"""Loads NicheConfig from a YAML file (Phase 1) or DB row (Phase 2)."""

from __future__ import annotations

from pathlib import Path

import yaml

from sma.core.niche.config import NicheConfig


def load_from_yaml(path: Path | str) -> NicheConfig:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"Niche YAML at {path} must be a mapping at top level")
    return NicheConfig(**raw)
