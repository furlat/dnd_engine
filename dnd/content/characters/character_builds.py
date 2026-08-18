"""Direct character composition through the universal entity transaction."""

from collections.abc import Callable
from typing import Optional
from uuid import UUID

from dnd.actions.operations import standard_actions_transform
from dnd.content.characters.origin_content import (
    resolve_origin_level_transforms,
    resolve_origin_transforms,
)
from dnd.content.characters.class_level_content import resolve_initial_level_steps
from dnd.content.characters.premade_builds import PREMADE_CHARACTER_DEFINITIONS
from dnd.content.characters.player_body import create_player_body
from dnd.content.items.item_placement import (
    resolve_background_item_transforms,
    resolve_class_starting_item_transforms,
    resolve_item_loadout_transforms,
)
from dnd.entities.creature_transforms import EntityTransform
from dnd.entities.entity import Entity
from dnd.entities.entity_creation import compose_entity
from dnd.entities.entity_progression import ResolvedLevelStep
from dnd.types.creatures import Background, Species, SpeciesVariant
from dnd.types.progression import AppliedOriginState


def _body_semantics_transform(
    premade_id: str,
    semantics: tuple[tuple[str, str], ...],
) -> EntityTransform:
    """Install renderer-independent body facts with an exact inverse."""
    def apply(entity: Entity):
        previous = dict(entity.appearance.semantic_properties)
        entity.appearance.semantic_properties = dict(semantics)
        return lambda: setattr(
            entity.appearance,
            "semantic_properties",
            previous,
        )

    return EntityTransform(f"{premade_id}.body_semantics", apply)


def create_character(
    entity_uuid: UUID,
    *,
    name: str,
    species: Species,
    background: Background,
    origin_state: AppliedOriginState,
    species_variant: Optional[SpeciesVariant] = None,
    description: Optional[str] = None,
    faction: Optional[str] = None,
    initial_levels: tuple[ResolvedLevelStep, ...] = (),
    additional_transforms: tuple[EntityTransform, ...] = (),
    validate: Optional[Callable[[Entity], None]] = None,
) -> Entity:
    """Create one committed character from resolved authored operations."""
    entity = create_player_body(
        entity_uuid,
        name=name,
        description=description,
        faction=faction,
    )
    try:
        origin_transforms = resolve_origin_transforms(
            species=species,
            species_variant=species_variant,
            background=background,
            state=origin_state,
        )
        holding_transforms = resolve_background_item_transforms(
            entity.uuid,
            background,
        )
        class_item_transforms = resolve_class_starting_item_transforms(
            entity.uuid,
            initial_levels,
        )
        level_steps = tuple(
            ResolvedLevelStep(
                level=step.level,
                transforms=(
                    *step.transforms,
                    *resolve_origin_level_transforms(
                        species,
                        species_variant,
                        step.level.character_level,
                    ),
                ),
            )
            for step in initial_levels
        )
        compose_entity(
            entity,
            transforms=(
                *holding_transforms,
                *class_item_transforms,
                *additional_transforms,
                standard_actions_transform("character.standard_actions"),
                *origin_transforms,
            ),
            applied_origin_state=origin_state,
            initial_levels=level_steps,
            validate=validate,
        )
    except Exception:
        if Entity.get(entity.uuid) is entity:
            entity.discard_unpublished_runtime()
        raise
    return entity


def create_premade_character(
    premade_id: str,
    entity_uuid: UUID,
    *,
    name: Optional[str] = None,
    faction: Optional[str] = None,
) -> Entity:
    """Create any authored premade through the ordinary character path."""
    try:
        definition = PREMADE_CHARACTER_DEFINITIONS[premade_id]
    except KeyError as exc:
        raise KeyError(f"unknown premade character {premade_id!r}") from exc
    initial_levels = resolve_initial_level_steps(
        definition.origin_state,
        definition.level_requests,
    )
    supplemental_items = resolve_item_loadout_transforms(
        entity_uuid,
        transform_prefix=f"premade.{premade_id}.holding",
        entries=definition.supplemental_loadout,
    )
    return create_character(
        entity_uuid,
        name=name or definition.display_name,
        species=definition.species,
        background=definition.background,
        origin_state=definition.origin_state,
        faction=faction,
        initial_levels=initial_levels,
        additional_transforms=(
            _body_semantics_transform(premade_id, definition.body_semantics),
            *supplemental_items,
        ),
    )


__all__ = ["create_character", "create_premade_character"]
