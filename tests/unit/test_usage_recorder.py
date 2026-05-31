"""Usage recorder — JSONL sink, thread-safe append."""

from __future__ import annotations

import json
from pathlib import Path

from sma.usage.events import UsageEvent
from sma.usage.recorder import JsonlSink, NullSink, record, set_sink


def test_jsonl_sink_writes_one_line(tmp_path: Path) -> None:
    sink = JsonlSink(tmp_path / "events.jsonl")
    sink.write(UsageEvent(provider="x", model="m", operation="op", tokens_in=10, cost_usd=0.001))
    sink.write(UsageEvent(provider="x", model="m", operation="op", tokens_in=20, cost_usd=0.002))
    lines = (tmp_path / "events.jsonl").read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 2
    parsed = [json.loads(ln) for ln in lines]
    assert parsed[0]["tokens_in"] == 10
    assert parsed[1]["cost_usd"] == 0.002


def test_jsonl_creates_parent_dir(tmp_path: Path) -> None:
    sink = JsonlSink(tmp_path / "deep" / "nested" / "events.jsonl")
    sink.write(UsageEvent(provider="x", model="m", operation="op"))
    assert (tmp_path / "deep" / "nested" / "events.jsonl").exists()


def test_record_uses_active_sink() -> None:
    captured: list[UsageEvent] = []

    class _Capture:
        def write(self, e: UsageEvent) -> None:
            captured.append(e)

    set_sink(_Capture())
    try:
        record(UsageEvent(provider="x", model="m", operation="op"))
        assert len(captured) == 1
        assert captured[0].provider == "x"
    finally:
        set_sink(NullSink())  # don't pollute later tests


def test_event_to_dict_serializes_timestamp() -> None:
    ev = UsageEvent(provider="x", model="m", operation="op")
    d = ev.to_dict()
    assert isinstance(d["timestamp"], str)
    assert d["provider"] == "x"
