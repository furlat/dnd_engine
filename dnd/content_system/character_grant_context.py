"""Shared cold-composition context for trusted built-in grant appliers."""

from dataclasses import dataclass
from uuid import UUID

from dnd.content_system.character_build_validation import CharacterBuildPreview
from dnd.content_system.runtime import ContentSystemRuntime
from dnd.entity import Entity


@dataclass(frozen=True, slots=True)
class BuiltinCharacterGrantContext:
    """Cold composition inputs available to trusted built-in appliers."""

    entity: Entity
    character_id: UUID
    preview: CharacterBuildPreview
    runtime: ContentSystemRuntime


__all__ = ["BuiltinCharacterGrantContext"]
