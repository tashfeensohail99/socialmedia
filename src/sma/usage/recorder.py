"""Records UsageEvents to a sink. Phase 1 = JSONL file. Phase 2 = Postgres."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Protocol

from loguru import logger

from sma.config import get_settings
from sma.usage.events import UsageEvent


class UsageSink(Protocol):
    def write(self, event: UsageEvent) -> None: ...


class JsonlSink:
    """Append-only JSONL file sink. Thread-safe via a lock."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, event: UsageEvent) -> None:
        line = json.dumps(event.to_dict(), separators=(",", ":"))
        with self._lock, self.path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")


class NullSink:
    def write(self, event: UsageEvent) -> None:  # pragma: no cover
        pass


class DbSink:
    """Inserts UsageEvent rows into Postgres. Used when a tenant context is active.

    Falls back to JsonlSink (via the recorder) on any DB error so we never
    break a pipeline run because of usage tracking.
    """

    def write(self, event: UsageEvent) -> None:
        # Lazy import — keep recorder.py importable without SQLAlchemy if the
        # caller never uses the DB sink.
        from sma.db.models.usage_event import UsageEvent as UsageEventRow
        from sma.db.session import get_current_tenant, get_session_factory

        tenant_id = get_current_tenant()
        if tenant_id is None:
            # No tenant context → can't write to a tenant-scoped table.
            raise RuntimeError("no tenant context — DbSink cannot insert without it")

        # The dataclass post_id is a string (Phase 1 used hash-based ids); DB column
        # is integer. Convert when possible; leave as None otherwise.
        post_id_int: int | None = None
        if event.post_id is not None:
            try:
                post_id_int = int(event.post_id)
            except (ValueError, TypeError):
                post_id_int = None

        row = UsageEventRow(
            tenant_id=tenant_id,
            provider=event.provider,
            model=event.model,
            operation=event.operation,
            tokens_in=event.tokens_in,
            tokens_out=event.tokens_out,
            units=event.units,
            cost_usd=event.cost_usd,
            post_id=post_id_int,
            occurred_at=event.timestamp,
            metadata_json=event.metadata,
        )
        SessionLocal = get_session_factory()
        with SessionLocal() as session:
            session.add(row)
            session.commit()


_sink: UsageSink | None = None
_jsonl_fallback: UsageSink | None = None


def get_sink() -> UsageSink:
    """Default sink. JSONL on disk; can be overridden via set_sink() (used by tests)."""
    global _sink
    if _sink is None:
        _sink = JsonlSink(get_settings().usage_log_path)
    return _sink


def _get_jsonl_fallback() -> UsageSink:
    global _jsonl_fallback
    if _jsonl_fallback is None:
        _jsonl_fallback = JsonlSink(get_settings().usage_log_path)
    return _jsonl_fallback


def set_sink(sink: UsageSink) -> None:
    """Override the default sink (used by tests)."""
    global _sink
    _sink = sink


def record(event: UsageEvent) -> None:
    """Persist a usage event.

    Resolution:
      1. If a tenant context is active → try DB sink first, fall back to JSONL on error
      2. Otherwise → JSONL sink (CLI / unauthenticated paths)
    """
    try:
        # Lazy import the tenant ContextVar so this module stays usable
        # without SQLAlchemy installed.
        try:
            from sma.db.session import get_current_tenant as _get_tenant
            tenant_id = _get_tenant()
        except Exception:
            tenant_id = None

        if tenant_id is not None:
            try:
                DbSink().write(event)
                return
            except Exception as db_err:
                logger.warning(f"DbSink failed ({db_err}); falling back to JSONL")
                _get_jsonl_fallback().write(event)
                return

        get_sink().write(event)
    except Exception as e:  # never let usage tracking break a pipeline run
        logger.warning(f"Failed to record usage event: {e}")
