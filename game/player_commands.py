"""Plain player intents shared by UI selection and the native command boundary."""

from dataclasses import dataclass
from uuid import UUID

from dnd.core.equipment_types import EquipmentSlot


class CommandRejected(ValueError):
    """An explicitly inadmissible user choice, not a runtime failure."""


@dataclass(frozen=True, slots=True)
class ActionSelection:
    action_index: int
    target_indices: tuple[int, ...]
    extra_target_positions: tuple[tuple[int, int], ...] = ()


@dataclass(frozen=True, slots=True)
class EndTurn:
    pass


@dataclass(frozen=True, slots=True)
class EquipItem:
    item_uuid: UUID
    slot: EquipmentSlot


@dataclass(frozen=True, slots=True)
class UnequipItem:
    slot: EquipmentSlot


@dataclass(frozen=True, slots=True)
class ToggleHandler:
    handler_uuid: UUID
    enabled: bool
