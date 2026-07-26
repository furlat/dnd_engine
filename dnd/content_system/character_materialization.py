"""Deployment-time reconstruction of one durable character revision pair."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from dnd.blocks.base_item import EquippableItem, UsableItem
from dnd.content_system.creature_materialization import materialize_creature
from dnd.content_system.item_bindings import ItemRuntimeOrigin
from dnd.content_system.item_runtime_materialization import (
    materialize_item_from_installed_runtime,
)
from dnd.content_system.runtime import (
    SERVER_CONTENT_SYSTEM_RUNTIME,
    ContentSystemRuntime,
)
from dnd.core.content.durable_characters import (
    CharacterDefinitionRevision,
    CharacterHoldingsRevision,
    CharacterItemV1,
)
from dnd.core.content.materialization import (
    CreatureDeploymentRole,
    CreaturePossessionMode,
)
from dnd.entity import Entity


@dataclass(frozen=True, slots=True)
class MaterializedCharacter:
    """Runtime actor plus exact persistent-item to runtime-item lineage."""

    entity: Entity
    item_lineage: tuple[tuple[UUID, UUID], ...]


def _restore_item_state(item: object, durable_item: CharacterItemV1) -> None:
    """Restore authored durable state before the item enters owner containers."""

    if durable_item.durable_augmentations:
        raise ValueError(
            "Durable item augmentations require an installed augmentation "
            "materializer",
        )
    if not hasattr(item, "stack_count") or not hasattr(item, "max_stack"):
        raise TypeError("Character item factory returned no stackable item surface")
    stack_id = getattr(item, "stack_id", None)
    max_stack = getattr(item, "max_stack")
    if stack_id is None and durable_item.quantity != 1:
        raise ValueError("Non-stackable durable items must have quantity one")
    if durable_item.quantity > max_stack:
        raise ValueError(
            f"Durable quantity {durable_item.quantity} exceeds max stack "
            f"{max_stack}",
        )
    setattr(item, "stack_count", durable_item.quantity)

    if durable_item.remaining_charges is not None:
        if not isinstance(item, UsableItem):
            raise TypeError("remaining_charges requires a usable item")
        if (
            item.max_charges >= 0
            and durable_item.remaining_charges > item.max_charges
        ):
            raise ValueError(
                "remaining_charges exceeds the authored per-item maximum",
            )
        item.charges = durable_item.remaining_charges

    if durable_item.durability_damage is not None:
        health = getattr(item, "health", None)
        if health is None:
            raise TypeError("durability_damage requires a breakable item")
        maximum = health.get_max_hit_dices_points(0)
        if durable_item.durability_damage >= maximum:
            raise ValueError(
                "Destroyed items cannot enter durable character holdings",
            )
        health.damage_taken = durable_item.durability_damage


def materialize_character(
    *,
    definition: CharacterDefinitionRevision,
    holdings: CharacterHoldingsRevision,
    runtime_entity_uuid: UUID | None,
    display_name: str,
    faction: str | None,
    position: tuple[int, int],
    deployment_role: CreatureDeploymentRole,
    runtime: ContentSystemRuntime = SERVER_CONTENT_SYSTEM_RUNTIME,
) -> MaterializedCharacter:
    """Build structural creature state, then hydrate exact persisted possessions."""

    definition.verify_integrity()
    holdings.verify_integrity()
    if definition.character_id != holdings.character_id:
        raise ValueError(
            "Character definition and holdings belong to different characters",
        )
    loaded = runtime.require()
    if definition.content_set_digest != loaded.content_set_digest:
        raise ValueError(
            "Character definition content set differs from this worker",
        )

    entity = materialize_creature(
        definition.creature_recipe,
        runtime_entity_uuid=runtime_entity_uuid or uuid4(),
        display_name=display_name,
        faction=faction,
        position=position,
        deployment_role=deployment_role,
        possession_mode=(
            CreaturePossessionMode.STRUCTURE_AND_INTRINSICS_ONLY
        ),
        runtime=runtime,
    )

    lineage: list[tuple[UUID, UUID]] = []
    for durable_item in holdings.items:
        item = materialize_item_from_installed_runtime(
            durable_item.recipe,
            entity.uuid,
            origin=ItemRuntimeOrigin.PERSISTED,
            character_item_id=durable_item.character_item_id,
            runtime=runtime,
        )
        _restore_item_state(item, durable_item)
        if not entity.loot_item(item):
            raise ValueError(
                f"Character inventory rejected "
                f"{durable_item.recipe.ref.identity_key}",
            )
        if durable_item.equipped_slot is not None:
            if not isinstance(item, EquippableItem):
                raise TypeError(
                    "equipped_slot requires an equippable item definition",
                )
            if not entity.equip_item(item.uuid, durable_item.equipped_slot):
                raise ValueError(
                    f"Character equipment rejected "
                    f"{durable_item.recipe.ref.identity_key} in "
                    f"{durable_item.equipped_slot.value}",
                )
        lineage.append((durable_item.character_item_id, item.uuid))

    return MaterializedCharacter(
        entity=entity,
        item_lineage=tuple(lineage),
    )


__all__ = [
    "MaterializedCharacter",
    "materialize_character",
]
