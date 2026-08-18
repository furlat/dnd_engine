"""Resolve authored item loadouts into entity-owned placement operations."""

from uuid import UUID

from dnd.content.items.authored_item_builders import (
    build_acolyte_gear,
    build_authored_item,
)
from dnd.content.items.item_loadouts import (
    BACKGROUND_ITEM_LOADOUTS,
    CLASS_STARTING_LOADOUTS,
    ItemLoadoutEntry,
)
from dnd.entities.creature_transforms import EntityTransform
from dnd.entities.entity_creation import initial_item_transform
from dnd.entities.entity_progression import ResolvedLevelStep
from dnd.types.creatures import Background


def resolve_background_item_transforms(
    owner_uuid: UUID,
    background: Background,
) -> tuple[EntityTransform, ...]:
    """Build a background's holdings as silent initial-item operations."""
    loadout = BACKGROUND_ITEM_LOADOUTS.get(background, ())
    return tuple(
        initial_item_transform(
            transform_id=(
                f"background.{background.value}.holding.{index}.{entry.item_id}"
            ),
            item=build_acolyte_gear(
                entry.item_id,
                owner_uuid,
                stack_count=entry.quantity,
            ),
        )
        for index, entry in enumerate(loadout)
    )


def resolve_item_loadout_transforms(
    owner_uuid: UUID,
    *,
    transform_prefix: str,
    entries: tuple[ItemLoadoutEntry, ...],
) -> tuple[EntityTransform, ...]:
    """Build one cold loadout into silent, exactly slotted item operations."""
    items = []
    try:
        for entry in entries:
            items.append(build_authored_item(
                entry.item_id,
                owner_uuid,
                quantity=entry.quantity,
            ))
    except Exception:
        for item in items:
            item.unregister(item.uuid)
        raise
    return tuple(
        initial_item_transform(
            transform_id=f"{transform_prefix}.{index}.{entry.item_id}",
            item=item,
            equipment_slot=entry.equipment_slot,
        )
        for index, (entry, item) in enumerate(zip(entries, items, strict=True))
    )


def resolve_class_starting_item_transforms(
    owner_uuid: UUID,
    initial_levels: tuple[ResolvedLevelStep, ...],
) -> tuple[EntityTransform, ...]:
    """Resolve the first-class equipment selection from applied level data."""
    selected_ids = tuple(
        value
        for step in initial_levels
        for choice in step.level.choices
        if choice.choice_id.endswith(".first_class.starting_equipment")
        for value in choice.values
    )
    if len(selected_ids) > 1:
        raise ValueError("an entity build can select only one first-class loadout")
    if not selected_ids:
        return ()
    selected_id = selected_ids[0]
    try:
        entries = CLASS_STARTING_LOADOUTS[selected_id]
    except KeyError as exc:
        raise KeyError(f"unknown class starting loadout {selected_id!r}") from exc
    return resolve_item_loadout_transforms(
        owner_uuid,
        transform_prefix=f"class.starting_loadout.{selected_id}",
        entries=entries,
    )


__all__ = [
    "resolve_background_item_transforms",
    "resolve_class_starting_item_transforms",
    "resolve_item_loadout_transforms",
]
