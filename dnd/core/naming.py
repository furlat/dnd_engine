"""Shared naming helpers for stable API identifiers."""

import re


def normalize_spell_id(name: str) -> str:
    """Convert a spell display name into a stable snake_case catalog id."""
    normalized = name.strip().lower()
    normalized = normalized.replace("&", " and ")
    normalized = re.sub(r"['`]", "", normalized)
    normalized = re.sub(r"[^a-z0-9]+", "_", normalized)
    return normalized.strip("_")
