"""Jinja2 prompt template loader.

Resolution order for `render(name, ...)`:
  1. DB override in the prompt_templates table for the CURRENT tenant (Phase 2)
  2. On-disk template at templates/{name} (the default)

The DB lookup only runs when a tenant context is set; otherwise we go straight
to disk. This keeps the CLI (which doesn't have a tenant context) working
identically to before Phase 2.
"""

from __future__ import annotations

from functools import cache
from pathlib import Path
from typing import Any

from jinja2 import DictLoader, Environment, FileSystemLoader, StrictUndefined
from loguru import logger

_TEMPLATES_DIR = Path(__file__).resolve().parents[3] / "templates"


@cache
def _disk_env() -> Environment:
    """Fallback environment that reads only from disk."""
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=False,
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )


def _try_db_override(template_name: str) -> str | None:
    """Return the DB override body for this template+tenant, or None if there is none."""
    # Strip .j2 suffix from name to match the slug stored in DB.
    slug = template_name[:-3] if template_name.endswith(".j2") else template_name

    # Lazy import to avoid pulling SQLAlchemy into CLI startup when no DB is configured.
    try:
        from sqlalchemy import select

        from sma.db.models.prompt_template import PromptTemplate
        from sma.db.session import get_current_tenant, get_session_factory
    except Exception:
        return None

    if get_current_tenant() is None:
        return None

    try:
        SessionLocal = get_session_factory()
        with SessionLocal() as session:
            row = session.execute(
                select(PromptTemplate).where(PromptTemplate.slug == slug)
            ).scalar_one_or_none()
            return row.body if row is not None else None
    except Exception as e:
        # DB unreachable / migrations not applied — silently fall back to disk.
        logger.debug(f"Template DB lookup failed for {slug!r} ({e}); falling back to disk")
        return None


def render(template_name: str, **context: Any) -> str:
    """Render a Jinja2 template, preferring tenant DB override over the on-disk default."""
    override_body = _try_db_override(template_name)
    if override_body is not None:
        # Build a one-shot env from the override body so it picks up the same filters/options.
        env = Environment(
            loader=DictLoader({template_name: override_body}),
            autoescape=False,
            undefined=StrictUndefined,
            trim_blocks=True,
            lstrip_blocks=True,
        )
        return env.get_template(template_name).render(**context)

    return _disk_env().get_template(template_name).render(**context)
