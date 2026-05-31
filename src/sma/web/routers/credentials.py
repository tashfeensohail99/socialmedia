"""Credentials CRUD — encrypted BYOK keys per provider.

Security:
- Plaintext payload is accepted only on POST/PATCH; never returned by any GET.
- Reads expose a masked preview (last 4 chars) for visual confirmation.
- The test endpoint pings the real provider with a tiny request to verify the key works.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from sma.db.crypto import decrypt_blob, encrypt_blob
from sma.db.models.credentials import Credentials
from sma.db.session import get_db_session
from sma.providers.registry import UnknownProvider, get_provider
from sma.web.auth.dependencies import CurrentUser
from sma.web.schemas.common import Page, PageMeta
from sma.web.schemas.credentials import (
    CredentialsCreate,
    CredentialsRead,
    CredentialsTestResult,
    CredentialsUpdate,
)

router = APIRouter(prefix="/api/credentials", tags=["credentials"])


def _to_read(row: Credentials) -> CredentialsRead:
    """Build a CredentialsRead with a masked secret preview (never leaks the key)."""
    try:
        payload = decrypt_blob(row.encrypted_blob)
    except Exception:
        payload = {}
    # Find the most likely secret field and show only its last 4 chars.
    secret_value = ""
    for k in ("api_key", "access_key", "client_secret", "page_token", "access_token", "secret"):
        if k in payload and isinstance(payload[k], str):
            secret_value = payload[k]
            break
    preview = (
        f"...{secret_value[-4:]}" if len(secret_value) >= 4
        else ("[set]" if secret_value else "[unset]")
    )
    return CredentialsRead(
        id=row.id,
        tenant_id=row.tenant_id,
        provider_kind=row.provider_kind,
        provider_name=row.provider_name,
        label=row.label,
        secret_preview=preview,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get("", response_model=Page[CredentialsRead])
def list_credentials(
    user: CurrentUser,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    provider_kind: str | None = Query(None),
) -> Page[CredentialsRead]:
    with get_db_session() as session:
        stmt = select(Credentials)
        if provider_kind:
            stmt = stmt.where(Credentials.provider_kind == provider_kind)
        total = session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        rows = session.scalars(
            stmt.order_by(Credentials.id.desc()).limit(limit).offset(offset)
        ).all()
        return Page[CredentialsRead](
            items=[_to_read(r) for r in rows],
            meta=PageMeta(total=total, limit=limit, offset=offset),
        )


@router.post("", response_model=CredentialsRead, status_code=status.HTTP_201_CREATED)
def create_credentials(payload: CredentialsCreate, user: CurrentUser) -> CredentialsRead:
    if not payload.payload:
        raise HTTPException(status_code=400, detail="payload must contain at least one secret field")
    with get_db_session() as session:
        # Upsert behavior: (tenant, kind, name, label) is unique.
        existing = session.execute(
            select(Credentials).where(
                Credentials.provider_kind == payload.provider_kind,
                Credentials.provider_name == payload.provider_name,
                Credentials.label == payload.label,
            )
        ).scalar_one_or_none()
        if existing is not None:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"credentials for {payload.provider_kind}/{payload.provider_name} "
                    f"label={payload.label!r} already exist — PATCH them instead"
                ),
            )
        row = Credentials(
            tenant_id=user.tenant_id,
            provider_kind=payload.provider_kind,
            provider_name=payload.provider_name,
            label=payload.label,
            encrypted_blob=encrypt_blob(payload.payload),
        )
        session.add(row)
        session.flush()
        session.refresh(row)
        return _to_read(row)


@router.patch("/{cred_id}", response_model=CredentialsRead)
def update_credentials(
    cred_id: int, payload: CredentialsUpdate, user: CurrentUser
) -> CredentialsRead:
    with get_db_session() as session:
        row = session.get(Credentials, cred_id)
        if row is None or row.tenant_id != user.tenant_id:
            raise HTTPException(status_code=404, detail="credentials not found")
        if payload.label is not None:
            row.label = payload.label
        if payload.payload is not None:
            row.encrypted_blob = encrypt_blob(payload.payload)
        session.flush()
        session.refresh(row)
        return _to_read(row)


@router.delete("/{cred_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_credentials(cred_id: int, user: CurrentUser) -> None:
    with get_db_session() as session:
        row = session.get(Credentials, cred_id)
        if row is None or row.tenant_id != user.tenant_id:
            raise HTTPException(status_code=404, detail="credentials not found")
        session.delete(row)


@router.post("/{cred_id}/test", response_model=CredentialsTestResult)
def test_credentials(cred_id: int, user: CurrentUser) -> CredentialsTestResult:
    """Smoke-test the credentials against the actual provider.

    Currently supports `llm` and `image` kinds. Others return a generic OK if the
    payload decrypts cleanly (we can't test e.g. social tokens without performing
    a real post).
    """
    with get_db_session() as session:
        row = session.get(Credentials, cred_id)
        if row is None or row.tenant_id != user.tenant_id:
            raise HTTPException(status_code=404, detail="credentials not found")
        # Capture plain values INSIDE the session — the ORM row becomes detached
        # once the session closes, so reading row.* afterwards raises
        # DetachedInstanceError. Pull everything we need into locals now.
        provider_kind = row.provider_kind
        provider_name = row.provider_name
        try:
            payload = decrypt_blob(row.encrypted_blob)
        except Exception as e:
            return CredentialsTestResult(
                ok=False, message=f"decrypt failed: {e}", provider=provider_name
            )

    try:
        if provider_kind == "llm":
            provider = get_provider(provider_kind, provider_name, **payload)
            resp = provider.complete(
                system="You are a test responder.",
                user="Reply with the single word: ok",
                model="gpt-4o-mini" if provider_name == "openai" else provider_name,
                temperature=0,
            )
            return CredentialsTestResult(
                ok=True, message="LLM responded", provider=provider_name,
                detail={"response": resp.text[:80]},
            )
        if provider_kind == "image":
            from pathlib import Path

            provider = get_provider(provider_kind, provider_name, **payload)
            tmp = Path("data") / "creds_test"
            tmp.mkdir(parents=True, exist_ok=True)
            result = provider.generate(
                prompts=["sunrise over mountains"], aspect_ratio="9:16", output_dir=tmp, count=1
            )
            ok = bool(result.paths)
            return CredentialsTestResult(
                ok=ok,
                message="image generated" if ok else "no image returned",
                provider=provider_name,
                detail={"path": str(result.paths[0]) if result.paths else ""},
            )
        # For voice/music/social we accept "decrypted OK" as a pass for now.
        return CredentialsTestResult(
            ok=True,
            message=f"decrypted successfully (no live test for kind {provider_kind!r})",
            provider=provider_name,
        )
    except UnknownProvider as e:
        return CredentialsTestResult(ok=False, message=str(e), provider=provider_name)
    except Exception as e:
        return CredentialsTestResult(ok=False, message=str(e), provider=provider_name)
