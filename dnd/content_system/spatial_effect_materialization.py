"""Canonical spatial-effect materialization against the installed registry."""

from __future__ import annotations

from typing import TypeVar, overload
from uuid import UUID

from dnd.content_system.runtime import (
    SERVER_CONTENT_SYSTEM_RUNTIME,
    ContentSystemRuntime,
)
from dnd.content_system.spatial_effect_registry_materialization import (
    materialize_spatial_effect_from_registry,
)
from dnd.core.content.recipes import ContentRecipe
from dnd.core.content.registration import ContentDeclaration
from dnd.spatial_effects import SpatialEffect


_SpatialEffectT = TypeVar("_SpatialEffectT", bound=SpatialEffect)


def resolve_spatial_effect_recipe(
    recipe: ContentRecipe,
    *,
    runtime: ContentSystemRuntime = SERVER_CONTENT_SYSTEM_RUNTIME,
) -> ContentDeclaration:
    """Resolve one exact spatial-effect recipe through the sole registry."""
    recipe.verify_integrity()
    declaration = runtime.require().registry.resolve_factory(recipe.ref)
    if declaration.spatial_effect_definition is None:
        raise TypeError(
            f"Spatial-effect factory {recipe.ref.identity_key} has no "
            "spatial-effect definition",
        )
    return declaration


@overload
def materialize_spatial_effect(
    recipe: ContentRecipe,
    source_entity_uuid: UUID,
    *,
    position: tuple[int, int],
    faction: str | None,
    expected_type: type[_SpatialEffectT],
    anchor_uuid: UUID | None = None,
    runtime: ContentSystemRuntime = SERVER_CONTENT_SYSTEM_RUNTIME,
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
    runtime: ContentSystemRuntime = SERVER_CONTENT_SYSTEM_RUNTIME,
) -> SpatialEffect: ...


def materialize_spatial_effect(
    recipe: ContentRecipe,
    source_entity_uuid: UUID,
    *,
    position: tuple[int, int],
    faction: str | None,
    anchor_uuid: UUID | None = None,
    expected_type: type[_SpatialEffectT] | None = None,
    runtime: ContentSystemRuntime = SERVER_CONTENT_SYSTEM_RUNTIME,
) -> SpatialEffect | _SpatialEffectT:
    """Construct and authenticate one persistent spatial phenomenon."""
    loaded = runtime.require()
    result = materialize_spatial_effect_from_registry(
        recipe,
        source_entity_uuid,
        position=position,
        faction=faction,
        registry=loaded.registry,
        anchor_uuid=anchor_uuid,
        expected_type=expected_type,
    )
    runtime.record_external_materialization()
    return result


__all__ = [
    "materialize_spatial_effect",
    "materialize_spatial_effect_from_registry",
    "resolve_spatial_effect_recipe",
]
