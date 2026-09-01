"""Exact authored possession grants shared by creature declarations and factories."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from dnd.actions_functional import update_weapon_templates
from dnd.blocks.base_item import BaseItem
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.core.content.identities import validate_namespaced_id
from dnd.core.content.materialization import CreaturePossessionMode
from dnd.core.equipment_types import EquipmentSlot
from dnd.entity import Entity


class CreaturePossessionDisposition(str, Enum):
    """How one exact authored recipe belongs to a creature."""

    INTRINSIC = "intrinsic"
    EQUIPPED = "equipped"
    INVENTORY = "inventory"


@dataclass(frozen=True, slots=True)
class CreaturePossessionGrant:
    """One immutable direct item placement owned by a creature definition."""

    item_id: str
    disposition: CreaturePossessionDisposition
    equipment_slot: EquipmentSlot | None = None

    def __post_init__(self) -> None:
        validate_namespaced_id(self.item_id, "item_id")
        requires_slot = self.disposition in {
            CreaturePossessionDisposition.INTRINSIC,
            CreaturePossessionDisposition.EQUIPPED,
        }
        if requires_slot != (self.equipment_slot is not None):
            raise ValueError(
                f"{self.disposition.value} possession requires "
                f"equipment_slot={requires_slot}",
            )

    def applies_to(self, mode: CreaturePossessionMode) -> bool:
        """Return whether the grant exists in one deployment possession mode."""
        return (
            self.disposition is CreaturePossessionDisposition.INTRINSIC
            or mode is CreaturePossessionMode.INCLUDE_DEFAULT_POSSESSIONS
        )

def apply_creature_possessions(
    entity: Entity,
    grants: Iterable[CreaturePossessionGrant],
    *,
    possession_mode: CreaturePossessionMode,
) -> tuple[BaseItem, ...]:
    """Build and silently install one creature-owned possession tuple."""
    selected = tuple(
        grant for grant in grants if grant.applies_to(possession_mode)
    )
    try:
        rows = tuple(
            (
                build_authored_item(grant.item_id, entity.uuid),
                grant.equipment_slot,
            )
            for grant in selected
        )
    except BaseException:
        entity.discard_uncommitted()
        raise
    entity.install_initial_items(rows)
    if rows:
        update_weapon_templates(entity)
    return tuple(item for item, _ in rows)


__all__ = [
    "CreaturePossessionDisposition",
    "CreaturePossessionGrant",
    "apply_creature_possessions",
]
