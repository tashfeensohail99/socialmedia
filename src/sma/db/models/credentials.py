"""Encrypted API credentials per tenant.

Each row stores ONE credential (an API key, or a more complex blob for OAuth
clients). The value is encrypted at rest with Fernet using the master key from
the MASTER_KEY env var; decrypted only at job runtime.

Examples:
  (tenant=1, kind="llm",   name="openai",     label="default") → {"api_key": "sk-..."}
  (tenant=1, kind="image", name="pexels",     label="default") → {"api_key": "..."}
  (tenant=1, kind="voice", name="elevenlabs", label="default") → {"api_key": "..."}
"""

from __future__ import annotations

from sqlalchemy import LargeBinary, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from sma.db.base import Base, TenantOwned


class Credentials(Base, TenantOwned):
    """Encrypted credential blob, scoped to (tenant, provider_kind, provider_name, label)."""

    __tablename__ = "credentials"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "provider_kind", "provider_name", "label",
            name="uq_credentials_tenant_provider_label",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    provider_kind: Mapped[str] = mapped_column(String(32), nullable=False)  # llm/image/voice/...
    provider_name: Mapped[str] = mapped_column(String(64), nullable=False)  # openai/pexels/...
    label: Mapped[str] = mapped_column(String(64), nullable=False, default="default")

    # Fernet-encrypted JSON blob. The decrypted form is a dict like
    # {"api_key": "sk-..."} or {"client_id": "...", "client_secret": "..."}.
    encrypted_blob: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
