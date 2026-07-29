"""Canonical serialization and secret-digest helpers."""

from __future__ import annotations

import hashlib
import hmac
from datetime import UTC, datetime

from server.canonical_json import canonical_json


def utc_now() -> datetime:
    """Return the current timezone-aware UTC time."""

    return datetime.now(UTC)


def datetime_to_text(value: datetime) -> str:
    """Serialize a datetime as normalized UTC text.

    Args:
        value: Timezone-aware datetime to serialize.

    Returns:
        ISO-8601 UTC timestamp ending in ``Z``.

    Raises:
        ValueError: If ``value`` is timezone-naive.
    """

    if value.tzinfo is None:
        raise ValueError("Directory timestamps must be timezone-aware")
    normalized = value.astimezone(UTC)
    return normalized.isoformat(timespec="microseconds").replace("+00:00", "Z")


def canonical_digest(value: object) -> str:
    """Return the SHA-256 digest of canonical JSON for ``value``."""

    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def hash_capability(secret: str, pepper: bytes) -> str:
    """Hash a high-entropy capability using a server-held HMAC pepper.

    Args:
        secret: Plaintext capability returned to a client exactly once.
        pepper: Server-held key that is never stored beside the digest.

    Returns:
        Lowercase SHA-256 HMAC digest.

    Raises:
        ValueError: If the secret or pepper is empty.
    """

    if not secret:
        raise ValueError("Capability secret cannot be empty")
    if not pepper:
        raise ValueError("Capability pepper cannot be empty")
    return hmac.new(pepper, secret.encode("utf-8"), hashlib.sha256).hexdigest()
