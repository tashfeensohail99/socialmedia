"""Caption + hashtag generator. Two LLM calls: one for caption, one for hashtags."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from loguru import logger

from sma.core.niche.config import NicheConfig
from sma.core.templates import render
from sma.core.topics.base import Topic
from sma.providers.llm.base import LLMProvider


@dataclass
class CaptionResult:
    caption: str
    hashtags: list[str]


_TAG_RE = re.compile(r"^[a-z0-9]{2,40}$")


def _clean_tags(raw: list[str]) -> list[str]:
    """Lowercase, strip non-alphanumeric, dedupe, drop too-short / too-long."""
    cleaned: list[str] = []
    seen: set[str] = set()
    for t in raw:
        t = re.sub(r"[^a-zA-Z0-9]", "", str(t)).lower()
        if not _TAG_RE.match(t) or t in seen:
            continue
        seen.add(t)
        cleaned.append(t)
    return cleaned


def generate_caption(
    topic: Topic,
    niche: NicheConfig,
    narrative_script: str,
    llm: LLMProvider,
) -> str:
    prompt = render("caption.j2", niche=niche, topic=topic, narrative_script=narrative_script)
    resp = llm.complete(
        system="You write social-media captions in the brand's voice.",
        user=prompt,
        model=niche.llm_model,
        temperature=0.7,
    )
    return resp.text.strip()


def generate_hashtags(
    topic: Topic,
    niche: NicheConfig,
    caption: str,
    llm: LLMProvider,
) -> list[str]:
    prompt = render("hashtags.j2", niche=niche, topic=topic, caption=caption)
    resp = llm.complete(
        system="You select social-media hashtags. Return only valid JSON.",
        user=prompt,
        model=niche.llm_model,
        temperature=0.5,
        json_mode=True,
    )
    try:
        data = json.loads(resp.text)
        raw = data.get("hashtags", [])
    except json.JSONDecodeError as e:
        logger.warning(f"Hashtag JSON parse failed: {e}; falling back to seeds")
        raw = niche.hashtag_seeds

    tags = _clean_tags(raw)
    # Always ensure niche seeds are present so brand consistency holds.
    for seed in niche.hashtag_seeds:
        s = seed.lower().strip("#")
        if _TAG_RE.match(s) and s not in tags:
            tags.append(s)
    return tags[:30]


def generate_caption_and_hashtags(
    topic: Topic,
    niche: NicheConfig,
    narrative_script: str,
    llm: LLMProvider,
) -> CaptionResult:
    caption = generate_caption(topic, niche, narrative_script, llm)
    tags = generate_hashtags(topic, niche, caption, llm)
    return CaptionResult(caption=caption, hashtags=tags)
