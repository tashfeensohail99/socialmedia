"""add per-avatar voice mapping

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-06-25 19:35:00.000000

Adds niches.avatar_voice_map — a JSON object mapping look_id -> voice_id so
each avatar in the rotation can speak with its own correct voice (e.g.
Thompson, who is male, no longer gets Ramisa's female voice). niche.heygen_voice_id
remains as the fallback for any avatar not present in the map.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "niches",
        sa.Column("avatar_voice_map", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("niches", "avatar_voice_map")
