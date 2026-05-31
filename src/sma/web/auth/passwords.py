"""Password hashing using bcrypt directly (not via passlib).

passlib is unmaintained and has a known break against bcrypt 4.x; we use the
bcrypt library directly. bcrypt has a hard 72-byte input limit, so we SHA-256
the password first to get a fixed-length 32-byte input regardless of how long
the user's password is.
"""

from __future__ import annotations

import hashlib

import bcrypt


def _prehash(plain: str) -> bytes:
    """SHA-256 the password to a fixed 32-byte digest. Bypasses bcrypt's 72-byte limit
    without weakening security (SHA-256 is collision-resistant for this purpose)."""
    return hashlib.sha256(plain.encode("utf-8")).digest()


def hash_password(plain: str) -> str:
    hashed = bcrypt.hashpw(_prehash(plain), bcrypt.gensalt(rounds=12))
    return hashed.decode("ascii")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_prehash(plain), hashed.encode("ascii"))
    except (ValueError, TypeError):
        return False
