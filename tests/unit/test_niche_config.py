"""NicheConfig validation + YAML loading."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from sma.core.niche.config import NicheConfig
from sma.core.niche.loader import load_from_yaml

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


@pytest.mark.parametrize("filename", ["fitness_niche.yaml", "recipes_niche.yaml", "crypto_niche.yaml"])
def test_example_niches_load(filename: str) -> None:
    cfg = load_from_yaml(EXAMPLES / filename)
    assert cfg.name
    assert cfg.description
    assert cfg.target_audience
    assert cfg.content_pillars
    assert cfg.llm_provider in {"openai", "anthropic", "gemini"}
    assert cfg.image_provider in {"pexels", "unsplash", "nano_banana", "dalle"}
    assert cfg.video_length_default in {"short", "long"}


def test_niche_requires_required_fields() -> None:
    with pytest.raises(ValidationError):
        NicheConfig.model_validate({"name": "x"})  # missing description, audience


def test_niche_yaml_must_be_mapping(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("- just\n- a list\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_from_yaml(bad)


def test_niche_round_trips_through_yaml(tmp_path: Path) -> None:
    src = NicheConfig(
        name="Test",
        description="d",
        target_audience="a",
        content_pillars=["one", "two"],
        voice_id="v1",
    )
    p = tmp_path / "out.yaml"
    p.write_text(yaml.safe_dump(src.model_dump()), encoding="utf-8")
    loaded = load_from_yaml(p)
    assert loaded.name == src.name
    assert loaded.content_pillars == src.content_pillars
