"""Pure exact composition of background-owned starting possessions."""

from __future__ import annotations

from collections.abc import Iterable
from uuid import UUID, uuid5

from dnd.core.content.durable_characters import (
    BackgroundDefinition,
    CharacterItemV2,
)
from dnd.core.content.identities import ContentRef
from dnd.core.content.registry import FrozenContentRegistry
from dnd.core.content.starting_equipment import (
    StartingEquipmentPackageDefinition,
)
from dnd.core.equipment_types import EquipmentSlot


def background_starting_holdings(
    *,
    character_id: UUID,
    background_ref: ContentRef,
    registry: FrozenContentRegistry,
    occupied_slots: Iterable[EquipmentSlot] = (),
) -> tuple[CharacterItemV2, ...]:
    """Create the exact revision-one item rows owned by one background."""

    background = registry.resolve_typed_definition(
        background_ref,
        BackgroundDefinition,
    )
    package_ref = background.starting_holdings_package_ref
    if package_ref is None:
        return ()
    package = registry.resolve_typed_definition(
        package_ref,
        StartingEquipmentPackageDefinition,
    )
    occupied = set(occupied_slots)
    items: list[CharacterItemV2] = []
    for entry_index, entry in enumerate(package.entries):
        equipped_slot = entry.equipped_slot
        if equipped_slot in occupied:
            equipped_slot = None
        if equipped_slot is not None:
            occupied.add(equipped_slot)
        items.append(CharacterItemV2.create(
            character_item_id=uuid5(
                character_id,
                (
                    "dnd-engine:background-possession:v2:"
                    f"{background_ref.identity_key}:"
                    f"{package_ref.identity_key}:"
                    f"{entry_index}:{entry.item_id}:"
                    f"{equipped_slot}"
                ),
            ),
            item_id=entry.item_id,
            quantity=entry.quantity,
            equipped_slot=equipped_slot,
        ))
    return tuple(items)


__all__ = ["background_starting_holdings"]
