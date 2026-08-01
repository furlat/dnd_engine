"""Canonical serialization primitives for authenticated content values."""

from __future__ import annotations

import hashlib
import json


def canonical_content_json_bytes(value: object) -> bytes:
    """Serialize one JSON-compatible content value deterministically."""
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def canonical_content_sha256(value: object) -> str:
    """Return the SHA-256 of one canonical content JSON value."""
    return hashlib.sha256(canonical_content_json_bytes(value)).hexdigest()
