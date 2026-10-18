"""Plain player intents shared by UI selection and the native command boundary."""

from dataclasses import dataclass
from typing import Annotated, ClassVar
from pydantic import ConfigDict, Field
from uuid import UUID

from dnd.core.equipment_types import EquipmentSlot
from dnd.types.character_progression import PreparedSpellSelection


class CommandRejected(ValueError):
    """An explicitly inadmissible user choice, not a runtime failure."""


@dataclass(frozen=True, slots=True)
class ActionSelection:
    __pydantic_config__: ClassVar[ConfigDict] = ConfigDict(extra="forbid")
    action_index: Annotated[int, Field(strict=True, ge=0)]
    target_indices: tuple[Annotated[int, Field(strict=True, ge=0)], ...]
    extra_target_positions: tuple[tuple[Annotated[int, Field(strict=True)], Annotated[int, Field(strict=True)]], ...] = ()
    prefer_safe: Annotated[bool, Field(strict=True)] = True
    # One of the row's cast_levels; omitted casts at the row's level (plan D17).
    cast_at_level: Annotated[int, Field(strict=True, ge=0, le=9)] | None = None


@dataclass(frozen=True, slots=True)
class EndTurn:
    __pydantic_config__: ClassVar[ConfigDict] = ConfigDict(extra="forbid")
    pass


@dataclass(frozen=True, slots=True)
class EquipItem:
    __pydantic_config__: ClassVar[ConfigDict] = ConfigDict(extra="forbid")
    item_uuid: UUID
    slot: EquipmentSlot


@dataclass(frozen=True, slots=True)
class UnequipItem:
    __pydantic_config__: ClassVar[ConfigDict] = ConfigDict(extra="forbid")
    slot: EquipmentSlot


@dataclass(frozen=True, slots=True)
class ToggleHandler:
    __pydantic_config__: ClassVar[ConfigDict] = ConfigDict(extra="forbid")
    handler_uuid: UUID
    enabled: Annotated[bool, Field(strict=True)]


@dataclass(frozen=True, slots=True)
class PrepareSpells:
    __pydantic_config__: ClassVar[ConfigDict] = ConfigDict(extra="forbid")
    selection: PreparedSpellSelection
