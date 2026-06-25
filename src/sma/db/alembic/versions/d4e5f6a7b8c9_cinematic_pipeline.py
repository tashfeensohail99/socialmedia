"""add cinematic Seedance pipeline columns

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-06-23 22:30:00.000000

Adds Tier-A cinematic (HeyGen Seedance 2.0 / cinematic_avatar) support on top of
the existing talking-head pipeline. Two table changes:

niches: gains cinematic_* configuration columns. cinematic_enabled defaults to
        FALSE so existing niches keep their current behavior unchanged.

posts:  gains pipeline_kind column to disambiguate which pipeline produced the
        post (slideshow / talking_head / cinematic). Existing rows backfill via
        avatar_id heuristic: avatar_id IS NOT NULL → 'talking_head', else
        'slideshow'. New cinematic posts will be tagged 'cinematic' so the
        per-3-day cadence gate can find the most-recent one cheaply.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "niches",
        sa.Column("cinematic_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "niches",
        sa.Column("cinematic_interval_days", sa.Integer(), nullable=False, server_default="3"),
    )
    op.add_column(
        "niches",
        sa.Column("cinematic_prompt_style", sa.String(64), nullable=False, server_default="immigration_office"),
    )
    op.add_column(
        "niches",
        sa.Column("cinematic_min_wallet_usd", sa.Float(), nullable=False, server_default="15.0"),
    )
    op.add_column(
        "niches",
        sa.Column("cinematic_duration_sec", sa.Integer(), nullable=False, server_default="8"),
    )
    op.add_column(
        "niches",
        sa.Column("cinematic_resolution", sa.String(8), nullable=False, server_default="720p"),
    )
    op.add_column(
        "posts",
        sa.Column("pipeline_kind", sa.String(16), nullable=False, server_default="slideshow"),
    )
    op.create_index("ix_posts_pipeline_kind", "posts", ["pipeline_kind"])
    # Backfill: any existing post with an avatar_id was the talking-head path.
    op.execute(
        "UPDATE posts SET pipeline_kind = 'talking_head' WHERE avatar_id IS NOT NULL"
    )


def downgrade() -> None:
    op.drop_index("ix_posts_pipeline_kind", table_name="posts")
    op.drop_column("posts", "pipeline_kind")
    op.drop_column("niches", "cinematic_resolution")
    op.drop_column("niches", "cinematic_duration_sec")
    op.drop_column("niches", "cinematic_min_wallet_usd")
    op.drop_column("niches", "cinematic_prompt_style")
    op.drop_column("niches", "cinematic_interval_days")
    op.drop_column("niches", "cinematic_enabled")
