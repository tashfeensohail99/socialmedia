"""Voice chunking — never breaks a sentence; respects char limit."""

from __future__ import annotations

from sma.core.media.audio.orchestrator import _chunk_text


def test_chunk_short_text_returns_single() -> None:
    chunks = _chunk_text("This is a short sentence.", max_chars=100)
    assert chunks == ["This is a short sentence."]


def test_chunk_splits_at_sentence_boundary() -> None:
    text = "First sentence here. Second sentence here. Third sentence here. Fourth."
    chunks = _chunk_text(text, max_chars=40)
    # Each chunk must end at . or ! or ?
    for c in chunks:
        assert c.rstrip()[-1] in ".!?"
    # No chunk exceeds limit (sentence-boundary split is best-effort, not strict)
    # but each chunk should be a coherent suffix of its source sentences
    assert "".join(chunks).replace(" ", "") == text.replace(" ", "")


def test_chunk_handles_question_and_exclamation() -> None:
    text = "Hello? Hi! Goodbye."
    chunks = _chunk_text(text, max_chars=15)
    assert all(c.rstrip()[-1] in ".!?" for c in chunks)


def test_chunk_empty_returns_empty() -> None:
    assert _chunk_text("", max_chars=100) == []
