"""add avatar_mode + heygen fields to niches and posts

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-06-22 18:00:00.000000

Adds HeyGen Avatar IV talking-head support. When niches.avatar_mode='talking_head'
the pipeline routes through HeyGen instead of the slideshow path; otherwise the
slideshow path runs as before (default 'off').

niches.avatar_library_ids is a JSON array of trained HeyGen avatar/group IDs the
niche rotates through; one is chosen per post. niches.heygen_voice_id is the
HeyGen voice used for the talking-head synthesis.

posts.avatar_id + posts.avatar_cost_usd capture which avatar a particular post
used and what HeyGen charged for it (for per-post unit economics).
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "niches",
        sa.Column("avatar_mode", sa.String(16), nullable=False, server_default="off"),
    )
    op.add_column(
        "niches",
        sa.Column("avatar_library_ids", sa.JSON(), nullable=True),
    )
    op.add_column(
        "niches",
        sa.Column("heygen_voice_id", sa.String(64), nullable=True),
    )
    op.add_column(
        "posts",
        sa.Column("avatar_id", sa.String(128), nullable=True),
    )
    op.add_column(
        "posts",
        sa.Column("avatar_cost_usd", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("posts", "avatar_cost_usd")
    op.drop_column("posts", "avatar_id")
    op.drop_column("niches", "heygen_voice_id")
    op.drop_column("niches", "avatar_library_ids")
    op.drop_column("niches", "avatar_mode")
