"""Registry-scoped spatial-effect construction shared by runtime services."""

from __future__ import annotations

from typing import TypeVar, overload
from uuid import UUID

from dnd.core.content.materialization import SpatialEffectBuildContext
from dnd.core.content.recipes import ContentRecipe
from dnd.core.content.registry import FrozenContentRegistry
from dnd.core.spatial_effect_types import SpatialEffectAnchorKind
from dnd.spatial_effects import SpatialEffect


_SpatialEffectT = TypeVar("_SpatialEffectT", bound=SpatialEffect)


@overload
def materialize_spatial_effect_from_registry(
    recipe: ContentRecipe,
    source_entity_uuid: UUID,
    *,
    position: tuple[int, int],
    faction: str | None,
    registry: FrozenContentRegistry,
    expected_type: type[_SpatialEffectT],
    anchor_uuid: UUID | None = None,
) -> _SpatialEffectT: ...


@overload
def materialize_spatial_effect_from_registry(
    recipe: ContentRecipe,
    source_entity_uuid: UUID,
    *,
    position: tuple[int, int],
    faction: str | None,
    registry: FrozenContentRegistry,
    anchor_uuid: UUID | None = None,
    expected_type: None = None,
) -> SpatialEffect: ...


def materialize_spatial_effect_from_registry(
    recipe: ContentRecipe,
    source_entity_uuid: UUID,
    *,
    position: tuple[int, int],
    faction: str | None,
    registry: FrozenContentRegistry,
    anchor_uuid: UUID | None = None,
    expected_type: type[_SpatialEffectT] | None = None,
) -> SpatialEffect | _SpatialEffectT:
    """Construct through a supplied frozen registry and authenticate the result."""
    recipe.verify_integrity()
    declaration = registry.resolve_factory(recipe.ref)
    definition = declaration.spatial_effect_definition
    if definition is None:
        raise TypeError(
            f"Spatial-effect factory {recipe.ref.identity_key} has no "
            "spatial-effect definition",
        )
    anchor_kind = definition.anchor_kind
    if anchor_kind is SpatialEffectAnchorKind.ENTITY:
        resolved_anchor_uuid = anchor_uuid or source_entity_uuid
    elif anchor_kind is SpatialEffectAnchorKind.WORLD_OBJECT:
        if anchor_uuid is None:
            raise ValueError(
                f"Spatial-effect factory {recipe.ref.identity_key} requires "
                "an explicit world-object anchor",
            )
        resolved_anchor_uuid = anchor_uuid
    else:
        if anchor_uuid is not None:
            raise ValueError(
                f"Spatial-effect factory {recipe.ref.identity_key} does not "
                "accept an attached anchor",
            )
        resolved_anchor_uuid = None
    context = SpatialEffectBuildContext(
        source_entity_uuid=source_entity_uuid,
        requested_ref=recipe.ref,
        position=position,
        faction=faction,
        anchor_kind=anchor_kind,
        anchor_uuid=resolved_anchor_uuid,
    )
    result = registry.materialize(recipe, context)
    if not isinstance(result, SpatialEffect):
        raise TypeError(
            f"Spatial-effect factory {recipe.ref.identity_key} returned "
            f"{type(result).__module__}.{type(result).__name__}",
        )
    if result.content_ref != recipe.ref:
        raise ValueError(
            f"Spatial-effect factory {recipe.ref.identity_key} did not bind "
            "its exact content reference",
        )
    if result.layer is not definition.layer:
        raise ValueError(
            f"Spatial-effect factory {recipe.ref.identity_key} returned layer "
            f"{result.layer.value}; expected {definition.layer.value}",
        )
    if result.occupancy_policy is not definition.occupancy_policy:
        raise ValueError(
            f"Spatial-effect factory {recipe.ref.identity_key} returned "
            f"occupancy {result.occupancy_policy.value}; expected "
            f"{definition.occupancy_policy.value}",
        )
    result.blocking_policy = definition.blocking_policy
    if (
        result.anchor_kind is not definition.anchor_kind
        or result.anchor_uuid != resolved_anchor_uuid
    ):
        raise ValueError(
            f"Spatial-effect factory {recipe.ref.identity_key} returned an "
            "anchor that differs from its authored build context",
        )
    result.trigger_kinds = definition.trigger_kinds
    result.first_per_turn_trigger_kinds = (
        definition.first_per_turn_trigger_kinds
    )
    if expected_type is not None and not isinstance(result, expected_type):
        raise TypeError(
            f"Spatial-effect factory {recipe.ref.identity_key} returned "
            f"{type(result).__module__}.{type(result).__name__}; expected "
            f"{expected_type.__module__}.{expected_type.__name__}",
        )
    return result


__all__ = ["materialize_spatial_effect_from_registry"]
