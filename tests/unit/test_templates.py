"""Jinja2 template rendering — verify all templates accept their expected context."""

from __future__ import annotations

from sma.core.niche.config import NicheConfig
from sma.core.templates import render
from sma.core.topics.base import Topic


def _niche() -> NicheConfig:
    return NicheConfig(
        name="Test Niche",
        description="A niche for testing.",
        target_audience="Test users",
        tone="friendly, neutral",
        content_pillars=["pillar one", "pillar two"],
        forbidden_topics=["forbidden one"],
        cta="CTA goes here",
        hashtag_seeds=["test", "demo"],
        voice_id="v1",
    )


def _topic() -> Topic:
    return Topic(title="A test topic", content="Some context here.", source="test")


def test_topic_scoring_renders() -> None:
    out = render("topic_scoring.j2", niche=_niche(), topic=_topic())
    assert "Test Niche" in out
    assert "pillar one" in out
    assert "forbidden one" in out


def test_story_analysis_short_renders() -> None:
    out = render("story_analysis.j2", niche=_niche(), topic=_topic(), video_length="short")
    assert "SHORT-VIDEO CONSTRAINTS" in out
    assert "narrative_script" in out


def test_story_analysis_long_renders() -> None:
    out = render("story_analysis.j2", niche=_niche(), topic=_topic(), video_length="long")
    # "long" mode now means horizontal 16:9 for YouTube long-form
    assert "LONG-FORMAT VIDEO CONSTRAINTS" in out
    assert "16:9" in out
    assert "YouTube" in out


def test_caption_renders() -> None:
    out = render("caption.j2", niche=_niche(), topic=_topic(), narrative_script="hello world")
    assert "CTA goes here" in out


def test_hashtags_renders() -> None:
    out = render("hashtags.j2", niche=_niche(), topic=_topic(), caption="hi")
    assert "#test" in out
    assert "#demo" in out


def test_image_scene_stock_mode() -> None:
    from sma.core.content.story_analyzer import StoryBeat

    beat = StoryBeat(order=1, scene_description="a sunny morning", voiceover_segment="hi", duration_sec=3.0)
    out = render(
        "image_scene.j2",
        niche=_niche(),
        topic=_topic(),
        beat=beat,
        total_beats=5,
        for_stock_search=True,
    )
    assert "search queries" in out


def test_image_scene_ai_mode() -> None:
    from sma.core.content.story_analyzer import StoryBeat

    beat = StoryBeat(order=1, scene_description="a sunny morning", voiceover_segment="hi", duration_sec=3.0)
    out = render(
        "image_scene.j2",
        niche=_niche(),
        topic=_topic(),
        beat=beat,
        total_beats=5,
        for_stock_search=False,
    )
    assert "Photorealistic" in out
    # AI mode should NOT include the JSON-output instruction the stock branch uses.
    assert '"queries"' not in out
    assert "Output strictly as JSON" not in out


def test_thumbnail_renders() -> None:
    out = render("thumbnail_prompt.j2", niche=_niche(), topic=_topic(), hook_text="big hook")
    assert "9:16" in out


def test_music_renders() -> None:
    out = render("music_prompt.j2", niche=_niche(), topic=_topic(), mood_hint="upbeat")
    assert "instrumental" in out.lower() or "INSTRUMENTAL" in out


def test_ai_topic_generation_renders() -> None:
    out = render(
        "ai_topic_generation.j2",
        niche=_niche(),
        count=5,
        recent_topics=["recent A", "recent B"],
    )
    assert "5 fresh" in out
    assert "recent A" in out
