"""Direct one-process construction of built-in spatial conditions."""

from __future__ import annotations

from typing import Mapping, TypeVar
from uuid import UUID

from dnd.content.spatial_effect_recipes import (
    BURNING_WEB_FIRE_RECIPE,
    BUILT_IN_SPATIAL_EFFECT_DECLARATIONS,
    ELECTRIFIED_WATER_RECIPE,
    FIRE_SURFACE_RECIPE,
    ICE_SURFACE_RECIPE,
    STEAM_CLOUD_RECIPE,
)
from dnd.core.base_conditions import Duration
from dnd.core.content.recipes import ContentRecipe
from dnd.core.events.world_events import SpatialEffectInteractionEvent
from dnd.spatial.area_conditions import SpatialCondition
from dnd.spatial.environmental_conditions import (
    ElectrifiedWater,
    FireSurface,
    IceSurface,
    SteamCloud,
)
from dnd.spatial.transitions import apply_spatial_interaction
from dnd.types.conditions import DurationType
from dnd.types.spatial_effects import SpatialEffectAnchorKind


_SpatialConditionT = TypeVar("_SpatialConditionT", bound=SpatialCondition)

_DECLARATIONS_BY_IDENTITY = {
    declaration.ref.identity_key: declaration
    for declaration in BUILT_IN_SPATIAL_EFFECT_DECLARATIONS
}


def _build_transition_replacement(
    recipe: ContentRecipe,
    replaced: SpatialCondition,
    event: SpatialEffectInteractionEvent,
    positions: set[tuple[int, int]],
) -> SpatialCondition:
    """Construct one exact environmental replacement condition."""
    duration_rounds = event.duration_rounds
    condition_fields: dict[str, object] = {
        "affected_positions": set(positions),
    }
    if recipe.ref == FIRE_SURFACE_RECIPE.ref:
        condition_type: type[SpatialCondition] = FireSurface
        condition_fields["duration"] = Duration(
            duration=duration_rounds or 3,
            duration_type=DurationType.ROUNDS,
        )
    elif recipe.ref == STEAM_CLOUD_RECIPE.ref:
        condition_type = SteamCloud
        condition_fields["duration"] = Duration(
            duration=duration_rounds or 2,
            duration_type=DurationType.ROUNDS,
        )
    elif recipe.ref == ICE_SURFACE_RECIPE.ref:
        condition_type = IceSurface
    elif recipe.ref == ELECTRIFIED_WATER_RECIPE.ref:
        condition_type = ElectrifiedWater
        condition_fields["duration"] = Duration(
            duration=duration_rounds or 3,
            duration_type=DurationType.ROUNDS,
        )
    elif recipe.ref == BURNING_WEB_FIRE_RECIPE.ref:
        condition_type = FireSurface
        condition_fields.update({
            "name": "Burning Web Fire",
            "description": (
                "Burning webs deal 2d4 fire to creatures starting their turn "
                "in the affected cube before expiring."
            ),
            "duration": Duration(
                duration=1,
                duration_type=DurationType.ROUNDS,
            ),
        })
    else:
        raise KeyError(
            f"No direct replacement condition for {recipe.ref.identity_key}",
        )
    return materialize_spatial_condition(
        recipe,
        event.source_entity_uuid,
        position=min(positions),
        faction=replaced.faction,
        condition_type=condition_type,
        condition_fields=condition_fields,
    )


def materialize_spatial_condition(
    recipe: ContentRecipe,
    source_entity_uuid: UUID,
    *,
    position: tuple[int, int],
    faction: str | None,
    condition_type: type[_SpatialConditionT],
    anchor_uuid: UUID | None = None,
    condition_fields: Mapping[str, object] | None = None,
) -> _SpatialConditionT:
    """Validate authored metadata and construct the final runtime condition."""
    recipe.verify_integrity()
    declaration = _DECLARATIONS_BY_IDENTITY.get(recipe.ref.identity_key)
    if declaration is None or declaration.ref != recipe.ref:
        raise KeyError(
            f"Unknown built-in spatial recipe {recipe.ref.identity_key}",
        )
    definition = declaration.spatial_effect_definition
    construction = declaration.construction
    if definition is None or construction is not None:
        raise TypeError(
            f"Spatial declaration {recipe.ref.identity_key} must be "
            "metadata-only",
        )
    if recipe.parameters:
        raise ValueError(
            f"Spatial recipe {recipe.ref.identity_key} does not accept "
            "construction parameters",
        )

    if definition.anchor_kind is SpatialEffectAnchorKind.ENTITY:
        resolved_anchor_uuid = anchor_uuid or source_entity_uuid
    elif definition.anchor_kind is SpatialEffectAnchorKind.WORLD_OBJECT:
        if anchor_uuid is None:
            raise ValueError(
                f"Spatial recipe {recipe.ref.identity_key} requires an "
                "explicit world-object anchor",
            )
        resolved_anchor_uuid = anchor_uuid
    else:
        if anchor_uuid is not None:
            raise ValueError(
                f"Spatial recipe {recipe.ref.identity_key} does not accept "
                "an attached anchor",
            )
        resolved_anchor_uuid = None

    values: dict[str, object] = {
        "source_entity_uuid": source_entity_uuid,
        "content_ref": recipe.ref,
        "behavior_id": recipe.ref.content_id,
        "position": position,
        "faction": faction,
        "anchor_kind": definition.anchor_kind,
        "anchor_uuid": resolved_anchor_uuid,
        "layer": definition.layer,
        "occupancy_policy": definition.occupancy_policy,
        "blocking_policy": definition.blocking_policy,
        "trigger_kinds": definition.trigger_kinds,
        "first_per_turn_trigger_kinds": (
            definition.first_per_turn_trigger_kinds
        ),
    }
    if condition_fields is not None:
        forbidden = set(condition_fields) & set(values)
        if forbidden:
            raise ValueError(
                "Condition-specific fields cannot replace authored spatial "
                f"metadata: {sorted(forbidden)}",
            )
        values.update(condition_fields)

    condition = condition_type.model_validate(values)
    if condition.content_ref != recipe.ref:
        raise ValueError("Constructed condition lost its exact content identity")
    if condition.layer is not definition.layer:
        raise ValueError("Constructed condition changed its authored layer")
    if condition.occupancy_policy is not definition.occupancy_policy:
        raise ValueError("Constructed condition changed its occupancy policy")
    if definition.transitions:
        condition.bind_interactions(
            definition.transitions,
            _build_transition_replacement,
            apply_spatial_interaction,
        )
    return condition


__all__ = ["materialize_spatial_condition"]
