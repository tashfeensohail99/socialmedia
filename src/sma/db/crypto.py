"""Fernet-based encryption for credentials + OAuth tokens at rest.

Master key comes from the MASTER_KEY env var. Encrypted blobs are stored in
Postgres `credentials.encrypted_blob` and `social_accounts.encrypted_oauth_blob`.

Why Fernet (not raw AES)?
- Bundles AES-128-CBC + HMAC-SHA256 + IV + timestamp in one easy-to-rotate token
- Standard, well-audited Python lib (cryptography.fernet)
- Tokens are url-safe base64; easy to debug, easy to migrate

Key rotation (Phase 3+): use MultiFernet — accepts a list of keys, encrypts with
the first, can decrypt with any. Add the new key to the front, re-encrypt all
rows in a background job, remove the old key.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from loguru import logger


class MissingMasterKey(RuntimeError):
    """MASTER_KEY env var not set or invalid."""


class InvalidEncryptedBlob(RuntimeError):
    """Blob couldn't be decrypted — wrong key, corrupted data, or tampering."""


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    import os

    key = os.environ.get("MASTER_KEY", "").strip()
    if not key:
        raise MissingMasterKey(
            "MASTER_KEY env var is required. Generate one with:\n"
            "  python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"\n"
            "Then set it in your .env (single-tenant deploy) or Railway env vars."
        )
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except (ValueError, TypeError) as e:
        raise MissingMasterKey(f"MASTER_KEY is not a valid Fernet key: {e}") from e


def encrypt_blob(payload: dict[str, Any]) -> bytes:
    """Serialize payload as JSON, encrypt with Fernet, return bytes."""
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return _fernet().encrypt(raw)


def decrypt_blob(token: bytes) -> dict[str, Any]:
    """Decrypt a Fernet token back to a dict. Raises InvalidEncryptedBlob on tampering."""
    try:
        raw = _fernet().decrypt(token)
    except InvalidToken as e:
        logger.error("Failed to decrypt blob — wrong MASTER_KEY or corrupted/tampered data")
        raise InvalidEncryptedBlob("blob could not be decrypted") from e
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise InvalidEncryptedBlob("decrypted payload is not a JSON object")
    return data


def generate_master_key() -> str:
    """Generate a fresh Fernet key. Used by setup wizards / CLI."""
    return Fernet.generate_key().decode()
