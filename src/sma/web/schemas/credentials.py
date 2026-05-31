"""Pydantic schemas for the Credentials resource.

Security: the encrypted_blob is NEVER returned by any API endpoint. Reads
return only a masked preview of the underlying key (e.g. 'sk-...XYZ').
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from sma.web.schemas.common import TimestampedRead


class CredentialsCreate(BaseModel):
    provider_kind: str = Field(..., description="llm | image | voice | music | social")
    provider_name: str = Field(..., description="openai | pexels | elevenlabs | ...")
    label: str = Field(default="default", max_length=64)
    payload: dict[str, str] = Field(
        ...,
        description=(
            "Dict of secret fields, e.g. {'api_key': 'sk-...'} for OpenAI. "
            "Stored encrypted; never returned."
        ),
    )


class CredentialsUpdate(BaseModel):
    """Rotate the secret payload OR change the label."""

    label: str | None = None
    payload: dict[str, str] | None = None


class CredentialsRead(TimestampedRead):
    id: int
    tenant_id: int
    provider_kind: str
    provider_name: str
    label: str
    # Masked summary of the stored secret — never the actual key.
    secret_preview: str = Field(
        ..., description="Last 4 chars of api_key prefixed with '...' for visual confirmation"
    )


class CredentialsTestResult(BaseModel):
    ok: bool
    message: str
    provider: str
    detail: dict[str, str] = Field(default_factory=dict)
