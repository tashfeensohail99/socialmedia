"""PostingRule — per-tenant scheduling rules (peak hours, quiet hours, spacing).

Each row encodes one rule. The scheduler reads them when deciding when a
newly-ready post should be scheduled.

Examples:
  type="peak_hours", params={"timezone": "Asia/Karachi", "hours": [18, 20, 21]}
  type="spacing",    params={"min_gap_minutes": 90}
  type="quiet_hours", params={"start": 1, "end": 7}
"""

from __future__ import annotations

from sqlalchemy import JSON, Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from sma.db.base import Base, TenantOwned


class PostingRule(Base, TenantOwned):
    __tablename__ = "posting_rules"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    # peak_hours | spacing | platform_priority | quiet_hours

    params_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
