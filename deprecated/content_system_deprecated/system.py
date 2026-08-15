"""Immutable identity and registry for the trusted built-in content set."""

from __future__ import annotations

from dataclasses import dataclass

from dnd.core.content.registry import FrozenContentRegistry


@dataclass(frozen=True, slots=True)
class LoadedContentSystem:
    """One validated built-in registry and its process identity."""

    registry: FrozenContentRegistry
    built_in_artifact_digest: str
    content_set_digest: str


__all__ = ["LoadedContentSystem"]
