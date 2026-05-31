"""Topic dataclass — id stability and JSON round-trip."""

from __future__ import annotations

from sma.core.topics.base import Topic


def test_id_is_stable_for_same_content() -> None:
    a = Topic(title="Same Title", content="Same content body", source="x")
    b = Topic(title="Same Title", content="Same content body", source="y")
    assert a.id == b.id  # source doesn't affect ID


def test_id_changes_when_content_changes() -> None:
    a = Topic(title="Same", content="A", source="x")
    b = Topic(title="Same", content="B", source="x")
    assert a.id != b.id


def test_round_trip_preserves_fields() -> None:
    src = Topic(
        title="t",
        content="c",
        source="s",
        score=8.5,
        score_reason="why",
        suggested_angle="angle",
        metadata={"k": "v"},
    )
    restored = Topic.from_dict(src.to_dict())
    assert restored.title == src.title
    assert restored.score == src.score
    assert restored.metadata == {"k": "v"}
    assert restored.id == src.id
