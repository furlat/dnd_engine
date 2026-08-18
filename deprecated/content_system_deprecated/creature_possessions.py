"""Exact authored possession grants shared by creature declarations and factories."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from dnd.blocks.base_item import BaseItem, EquippableItem
from dnd.content_system.item_bindings import (
    ITEM_RUNTIME_BINDINGS,
    ItemRuntimeBindingRegistry,
    ItemRuntimeOrigin,
)
from dnd.content_system.item_materialization import materialize_item
from dnd.content_system.runtime import (
    SERVER_CONTENT_SYSTEM_RUNTIME,
    ContentSystemRuntime,
)
from dnd.core.content.dependencies import (
    ContentDependency,
    ContentDependencyPhase,
    ContentDependencyRelation,
)
from dnd.core.content.materialization import CreaturePossessionMode
from dnd.core.content.recipes import ContentRecipe
from dnd.core.equipment_types import EquipmentSlot
from dnd.entities.entity import Entity


class CreaturePossessionDisposition(str, Enum):
    """How one exact authored recipe belongs to a creature."""

    INTRINSIC = "intrinsic"
    EQUIPPED = "equipped"
    INVENTORY = "inventory"


@dataclass(frozen=True, slots=True)
class CreaturePossessionGrant:
    """One immutable recipe placement used by dependency and runtime paths."""

    recipe: ContentRecipe
    disposition: CreaturePossessionDisposition
    equipment_slot: EquipmentSlot | None = None

    def __post_init__(self) -> None:
        self.recipe.verify_integrity()
        requires_slot = self.disposition in {
            CreaturePossessionDisposition.INTRINSIC,
            CreaturePossessionDisposition.EQUIPPED,
        }
        if requires_slot != (self.equipment_slot is not None):
            raise ValueError(
                f"{self.disposition.value} possession requires "
                f"equipment_slot={requires_slot}",
            )

    @property
    def origin(self) -> ItemRuntimeOrigin:
        """Return the exact runtime provenance implied by the disposition."""
        if self.disposition is CreaturePossessionDisposition.INTRINSIC:
            return ItemRuntimeOrigin.INTRINSIC
        return ItemRuntimeOrigin.STARTER

    def applies_to(self, mode: CreaturePossessionMode) -> bool:
        """Return whether the grant exists in one deployment possession mode."""
        return (
            self.disposition is CreaturePossessionDisposition.INTRINSIC
            or mode is CreaturePossessionMode.INCLUDE_DEFAULT_POSSESSIONS
        )


def creature_possession_dependencies(
    grants: Iterable[CreaturePossessionGrant],
) -> tuple[ContentDependency, ...]:
    """Derive the exact construction dependency closure from authored grants."""
    relations: dict[
        str,
        tuple[ContentDependencyRelation, ContentRecipe],
    ] = {}
    for grant in grants:
        relation = (
            ContentDependencyRelation.CREATES_ITEM
            if grant.disposition is CreaturePossessionDisposition.INVENTORY
            else ContentDependencyRelation.EQUIPS_ITEM
        )
        identity_key = grant.recipe.ref.identity_key
        existing = relations.get(identity_key)
        if (
            existing is None
            or relation is ContentDependencyRelation.EQUIPS_ITEM
        ):
            relations[identity_key] = (relation, grant.recipe)
    return tuple(
        ContentDependency(
            relation=relation,
            target_ref=recipe.ref,
            phase=ContentDependencyPhase.CONSTRUCTION,
            notes="Exact creature-owned possession grant.",
        )
        for _, (relation, recipe) in sorted(relations.items())
    )


def _validate_materialized_grants(
    entity: Entity,
    rows: tuple[tuple[CreaturePossessionGrant, BaseItem], ...],
) -> None:
    """Reject incompatible authored placement before attaching any item."""
    claimed_slots: set[EquipmentSlot] = set()
    for grant, item in rows:
        slot = grant.equipment_slot
        if slot is None:
            if not entity.inventory.can_add(item):
                raise ValueError(
                    f"{entity.name!r} inventory rejects creature possession "
                    f"{grant.recipe.ref.identity_key!r}",
                )
            continue
        if not isinstance(item, EquippableItem):
            raise TypeError(
                f"Creature possession {grant.recipe.ref.identity_key!r} "
                "is not equippable",
            )
        if slot not in item.compatible_equipment_slots():
            raise ValueError(
                f"Creature possession {grant.recipe.ref.identity_key!r} "
                f"cannot occupy {slot.value!r}",
            )
        footprint = item.occupied_equipment_slots(slot)
        conflicts = footprint & claimed_slots
        if conflicts:
            raise ValueError(
                f"Creature possession {grant.recipe.ref.identity_key!r} "
                f"duplicates authored slots "
                f"{sorted(conflict.value for conflict in conflicts)!r}",
            )
        for occupied_slot in footprint:
            if entity.equipment.get_item_by_slot(occupied_slot) is not None:
                raise ValueError(
                    f"Creature possession {grant.recipe.ref.identity_key!r} "
                    f"would replace occupied {occupied_slot.value!r}",
                )
        claimed_slots.update(footprint)


def _discard_provisional_items(
    entity: Entity,
    rows: Iterable[tuple[CreaturePossessionGrant, BaseItem]],
    *,
    binding_registry: ItemRuntimeBindingRegistry,
) -> None:
    """Remove provisional construction items after a failed authored grant."""
    for grant, item in reversed(tuple(rows)):
        slot = grant.equipment_slot
        if slot is not None and entity.equipment.get_item_by_slot(slot) is item:
            entity.equipment.unequip(slot)
        if entity.inventory.items.get(item.uuid) is item:
            entity.inventory.remove_item(item.uuid)
        binding_registry.discard(item.uuid)
        item.destroy()


def apply_creature_possessions(
    entity: Entity,
    grants: Iterable[CreaturePossessionGrant],
    *,
    possession_mode: CreaturePossessionMode,
    binding_registry: ItemRuntimeBindingRegistry = ITEM_RUNTIME_BINDINGS,
    runtime: ContentSystemRuntime = SERVER_CONTENT_SYSTEM_RUNTIME,
) -> tuple[BaseItem, ...]:
    """Materialize and attach one already-authored exact possession tuple."""
    selected = tuple(
        grant for grant in grants if grant.applies_to(possession_mode)
    )
    rows: list[tuple[CreaturePossessionGrant, BaseItem]] = []
    applied: list[tuple[CreaturePossessionGrant, BaseItem]] = []
    try:
        for grant in selected:
            rows.append((
                grant,
                materialize_item(
                    grant.recipe,
                    entity.uuid,
                    origin=grant.origin,
                    binding_registry=binding_registry,
                    runtime=runtime,
                ),
            ))
        materialized = tuple(rows)
        _validate_materialized_grants(entity, materialized)
        for grant, item in materialized:
            slot = grant.equipment_slot
            if slot is None:
                if not entity.loot_item(item):
                    raise ValueError(
                        f"{entity.name!r} rejected inventory possession "
                        f"{grant.recipe.ref.identity_key!r}",
                    )
            else:
                if not isinstance(item, EquippableItem):
                    raise TypeError(
                        f"Creature possession "
                        f"{grant.recipe.ref.identity_key!r} is not equippable",
                    )
                if not entity.equipment.equip(item, slot):
                    raise ValueError(
                        f"{entity.name!r} rejected equipped possession "
                        f"{grant.recipe.ref.identity_key!r}",
                    )
            applied.append((grant, item))
    except Exception:
        _discard_provisional_items(
            entity,
            rows,
            binding_registry=binding_registry,
        )
        raise
    return tuple(item for _, item in applied)


__all__ = [
    "CreaturePossessionDisposition",
    "CreaturePossessionGrant",
    "apply_creature_possessions",
    "creature_possession_dependencies",
]
