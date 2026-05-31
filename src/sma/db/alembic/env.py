"""Alembic environment.

Resolves the DB URL dynamically (env var or SQLite dev fallback) and imports
all ORM models so `--autogenerate` sees every table.
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Make sure src/ is on sys.path so `import sma.db.models` works.
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]  # …/social-media-automation
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# Trigger registration of all tables.
import sma.db.models  # noqa: F401
from sma.db.base import Base
from sma.db.session import _build_database_url

config = context.config

# Inject the dynamic DB URL into Alembic's config so it doesn't have to live in alembic.ini.
config.set_main_option("sqlalchemy.url", _build_database_url())

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # SQLite needs render_as_batch for ALTER TABLE compatibility
        render_as_batch=(url or "").startswith("sqlite"),
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        is_sqlite = connection.engine.url.get_backend_name() == "sqlite"
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=is_sqlite,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
