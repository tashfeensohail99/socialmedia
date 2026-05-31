"""tenant_daily_video_limits

Revision ID: a1b2c3d4e5f6
Revises: f038ded5c50d
Create Date: 2026-05-29 00:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "f038ded5c50d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("tenants", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("daily_short_videos", sa.Integer(), nullable=False, server_default="3")
        )
        batch_op.add_column(
            sa.Column("daily_long_videos", sa.Integer(), nullable=False, server_default="0")
        )


def downgrade() -> None:
    with op.batch_alter_table("tenants", schema=None) as batch_op:
        batch_op.drop_column("daily_long_videos")
        batch_op.drop_column("daily_short_videos")
