"""default 3 shorts 0 long, bump existing single-tenant rows

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-05-31 00:00:00.000000

Changes the server-side default for daily video limits to 3 short / 0 long,
and updates any existing tenant rows that still carry the previous default
(1 short / 1 long) so the deployed single-tenant workspace gets the new
sensible default without manual intervention.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # New server-side defaults for future inserts.
    with op.batch_alter_table("tenants", schema=None) as batch_op:
        batch_op.alter_column("daily_short_videos", server_default="3")
        batch_op.alter_column("daily_long_videos", server_default="0")

    # Bump existing rows that still hold the previous default (1/1) to the
    # new default. Rows a user has already customized to other values are left
    # untouched (we only touch the exact old-default pair).
    op.execute(
        "UPDATE tenants SET daily_short_videos = 3, daily_long_videos = 0 "
        "WHERE daily_short_videos = 1 AND daily_long_videos = 1"
    )


def downgrade() -> None:
    with op.batch_alter_table("tenants", schema=None) as batch_op:
        batch_op.alter_column("daily_short_videos", server_default="1")
        batch_op.alter_column("daily_long_videos", server_default="1")
