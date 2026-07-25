"""Dependency-neutral deterministic JSON serialization for server artifacts."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import UUID

from pydantic import BaseModel


def _json_ready(value: Any) -> Any:
    """Convert supported typed values into canonical JSON-compatible data."""

    if isinstance(value, BaseModel):
        # Pydantic's JSON-mode serializer has already traversed the complete
        # model graph and converted nested models, UUIDs, datetimes, enums, and
        # paths to JSON primitives. Walking that often-large replay graph a
        # second time is pure duplicate work.
        return value.model_dump(mode="json", by_alias=True, exclude_none=False)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError("Canonical JSON timestamps must be timezone-aware")
        normalized = value.astimezone(UTC)
        return normalized.isoformat(timespec="microseconds").replace("+00:00", "Z")
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
    """Serialize a supported value into compact deterministic JSON text."""

    return json.dumps(
        _json_ready(value),
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def canonical_json_bytes(value: Any) -> bytes:
    """Serialize a supported value into deterministic UTF-8 JSON bytes."""

    return canonical_json(value).encode("utf-8")
