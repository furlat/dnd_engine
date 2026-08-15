"""Direct one-process materialization of built-in spatial-effect recipes."""

from __future__ import annotations

from typing import TypeVar, overload
from uuid import UUID

from dnd.content.spatial_effect_recipes import (
    BUILT_IN_SPATIAL_EFFECT_DECLARATIONS,
)
from dnd.core.content.materialization import SpatialEffectBuildContext
from dnd.core.content.recipes import ContentRecipe
from dnd.spatial.effect_base import SpatialEffect
from dnd.types.spatial_effects import SpatialEffectAnchorKind


_SpatialEffectT = TypeVar("_SpatialEffectT", bound=SpatialEffect)

_DECLARATIONS_BY_IDENTITY = {
    declaration.ref.identity_key: declaration
    for declaration in BUILT_IN_SPATIAL_EFFECT_DECLARATIONS
}


@overload
def materialize_spatial_effect(
    recipe: ContentRecipe,
    source_entity_uuid: UUID,
    *,
    position: tuple[int, int],
    faction: str | None,
    expected_type: type[_SpatialEffectT],
    anchor_uuid: UUID | None = None,
) -> _SpatialEffectT: ...


@overload
def materialize_spatial_effect(
    recipe: ContentRecipe,
    source_entity_uuid: UUID,
    *,
    position: tuple[int, int],
    faction: str | None,
    anchor_uuid: UUID | None = None,
    expected_type: None = None,
) -> SpatialEffect: ...


def materialize_spatial_effect(
    recipe: ContentRecipe,
    source_entity_uuid: UUID,
    *,
    position: tuple[int, int],
    faction: str | None,
    anchor_uuid: UUID | None = None,
    expected_type: type[_SpatialEffectT] | None = None,
) -> SpatialEffect | _SpatialEffectT:
    """Validate and construct one built-in spatial phenomenon directly."""
    recipe.verify_integrity()
    declaration = _DECLARATIONS_BY_IDENTITY.get(recipe.ref.identity_key)
    if declaration is None or declaration.ref != recipe.ref:
        raise KeyError(
            f"Unknown built-in spatial-effect recipe {recipe.ref.identity_key}",
        )
    definition = declaration.spatial_effect_definition
    construction = declaration.construction
    if definition is None or construction is None:
        raise TypeError(
            f"Spatial-effect declaration {recipe.ref.identity_key} is not constructible",
        )

    if definition.anchor_kind is SpatialEffectAnchorKind.ENTITY:
        resolved_anchor_uuid = anchor_uuid or source_entity_uuid
    elif definition.anchor_kind is SpatialEffectAnchorKind.WORLD_OBJECT:
        if anchor_uuid is None:
            raise ValueError(
                f"Spatial-effect recipe {recipe.ref.identity_key} requires "
                "an explicit world-object anchor",
            )
        resolved_anchor_uuid = anchor_uuid
    else:
        if anchor_uuid is not None:
            raise ValueError(
                f"Spatial-effect recipe {recipe.ref.identity_key} does not "
                "accept an attached anchor",
            )
        resolved_anchor_uuid = None

    context = SpatialEffectBuildContext(
        source_entity_uuid=source_entity_uuid,
        requested_ref=recipe.ref,
        position=position,
        faction=faction,
        anchor_kind=definition.anchor_kind,
        anchor_uuid=resolved_anchor_uuid,
    )
    parameters = construction.parameter_model.model_validate(recipe.parameters)
    result = construction.factory(context, parameters)
    if not isinstance(result, SpatialEffect):
        raise TypeError(
            f"Spatial-effect recipe {recipe.ref.identity_key} returned "
            f"{type(result).__module__}.{type(result).__name__}",
        )
    if result.content_ref != recipe.ref:
        raise ValueError(
            f"Spatial-effect recipe {recipe.ref.identity_key} did not bind "
            "its exact content reference",
        )
    if result.layer is not definition.layer:
        raise ValueError(
            f"Spatial-effect recipe {recipe.ref.identity_key} returned layer "
            f"{result.layer.value}; expected {definition.layer.value}",
        )
    if result.occupancy_policy is not definition.occupancy_policy:
        raise ValueError(
            f"Spatial-effect recipe {recipe.ref.identity_key} returned occupancy "
            f"{result.occupancy_policy.value}; expected "
            f"{definition.occupancy_policy.value}",
        )
    if (
        result.anchor_kind is not definition.anchor_kind
        or result.anchor_uuid != resolved_anchor_uuid
    ):
        raise ValueError(
            f"Spatial-effect recipe {recipe.ref.identity_key} returned "
            "an anchor that differs from its build context",
        )

    result.blocking_policy = definition.blocking_policy
    result.trigger_kinds = definition.trigger_kinds
    result.first_per_turn_trigger_kinds = definition.first_per_turn_trigger_kinds
    if expected_type is not None and not isinstance(result, expected_type):
        raise TypeError(
            f"Spatial-effect recipe {recipe.ref.identity_key} returned "
            f"{type(result).__module__}.{type(result).__name__}; expected "
            f"{expected_type.__module__}.{expected_type.__name__}",
        )
    return result
