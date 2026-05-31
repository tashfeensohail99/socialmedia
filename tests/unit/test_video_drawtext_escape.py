"""drawtext escaping + caption wrapping — both must keep text inside the safe area."""

from __future__ import annotations

from sma.core.media.video.assembler import (
    _escape_drawtext,
    _truncate_for_caption,
    _wrap_to_lines,
)


def test_escapes_single_quotes() -> None:
    assert _escape_drawtext("don't") == "don\\'t"


def test_escapes_colons() -> None:
    assert _escape_drawtext("ratio 9:16") == "ratio 9\\:16"


def test_escapes_backslashes() -> None:
    assert _escape_drawtext("path\\file") == "path\\\\file"


def test_escapes_percents() -> None:
    assert _escape_drawtext("100% great") == "100\\% great"


def test_truncate_keeps_short_text() -> None:
    assert _truncate_for_caption("hello", max_chars=90) == "hello"


def test_truncate_long_with_ellipsis() -> None:
    out = _truncate_for_caption("x" * 200, max_chars=90)
    assert out.endswith("…")
    assert len(out) == 90


# ─── caption wrapping (the fix for "subtitles overflow the bottom") ─────


def test_wrap_short_text_returns_single_line() -> None:
    assert _wrap_to_lines("Hello world", max_chars_per_line=32, max_lines=3) == ["Hello world"]


def test_wrap_empty_returns_empty_list() -> None:
    assert _wrap_to_lines("   ", max_chars_per_line=32, max_lines=3) == []


def test_wrap_breaks_on_word_boundary() -> None:
    text = "In just five minutes, you can do these desk-friendly stretches"
    lines = _wrap_to_lines(text, max_chars_per_line=32, max_lines=3)
    assert len(lines) >= 2
    # No line exceeds the max
    for line in lines:
        assert len(line) <= 32
    # No mid-word breaks
    for line in lines:
        assert not line.startswith(" ")
        assert not line.endswith(" ")


def test_wrap_truncates_overflow_with_ellipsis() -> None:
    long_text = "word " * 100  # way too long for 2 lines of 20
    lines = _wrap_to_lines(long_text, max_chars_per_line=20, max_lines=2)
    assert len(lines) == 2
    assert lines[-1].endswith("…")


def test_wrap_replaces_newlines_with_spaces() -> None:
    lines = _wrap_to_lines("hello\nworld", max_chars_per_line=32, max_lines=3)
    assert lines == ["hello world"]


def test_escape_strips_newlines_to_spaces() -> None:
    # We render multi-line captions by emitting one drawtext per line, not by
    # encoding line breaks in the text value. Stray newlines become spaces so
    # they don't leak into ffmpeg as malformed escapes.
    out = _escape_drawtext("line1\nline2")
    assert out == "line1 line2"


def test_escape_handles_special_chars_with_stray_newline() -> None:
    out = _escape_drawtext("It's 9:16\nfine")
    assert out == "It\\'s 9\\:16 fine"
