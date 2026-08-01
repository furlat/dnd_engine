"""Directory-owned clocks and capability hashing."""

from __future__ import annotations

import hashlib
import hmac
from datetime import UTC, datetime


def utc_now() -> datetime:
    """Return the current timezone-aware UTC time."""

    return datetime.now(UTC)


def hash_capability(secret: str, pepper: bytes) -> str:
    """Hash one high-entropy capability with the server-held HMAC pepper."""

    if not secret:
        raise ValueError("Capability secret cannot be empty")
    if not pepper:
        raise ValueError("Capability pepper cannot be empty")
    return hmac.new(
        pepper,
        secret.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
