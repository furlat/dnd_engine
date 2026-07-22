"""Canonical serialization and secret-digest helpers."""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import UUID

from pydantic import BaseModel


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


def _json_ready(value: Any) -> Any:
    """Convert supported values into canonical JSON-compatible data."""

    if isinstance(value, BaseModel):
        return _json_ready(value.model_dump(mode="json", by_alias=True, exclude_none=False))
    if isinstance(value, datetime):
        return datetime_to_text(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Enum):
        return _json_ready(value.value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"Unsupported canonical JSON value: {type(value).__name__}")


def canonical_json(value: Any) -> str:
    """Serialize a supported value into deterministic canonical JSON.

    Args:
        value: Pydantic model or JSON-compatible value.

    Returns:
        Compact UTF-8 JSON with sorted keys.
    """

    return json.dumps(
        _json_ready(value),
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def canonical_digest(value: Any) -> str:
    """Return the SHA-256 digest of canonical JSON for ``value``."""

    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def text_digest(value: str) -> str:
    """Return the SHA-256 digest of exact UTF-8 text."""

    return hashlib.sha256(value.encode("utf-8")).hexdigest()


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
