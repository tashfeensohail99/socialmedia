"""Per-tenant prompt template overrides.

Default templates ship as files in `templates/` and are used when no DB row
exists for a tenant+slug combination. The admin panel lets a tenant override
any default template by inserting a row here.
"""

from __future__ import annotations

from sqlalchemy import Boolean, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from sma.db.base import Base, TenantOwned


class PromptTemplate(Base, TenantOwned):
    __tablename__ = "prompt_templates"
    __table_args__ = (
        UniqueConstraint("tenant_id", "slug", name="uq_prompt_template_tenant_slug"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(64), nullable=False)  # story_analysis | caption | etc
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
