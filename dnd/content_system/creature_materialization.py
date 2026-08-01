"""Canonical runtime adapter for creature recipes."""

from __future__ import annotations

from typing import TypeVar, overload
from uuid import UUID

from dnd.content_system.creature_bindings import (
    CREATURE_RUNTIME_BINDINGS,
    CreatureRuntimeBinding,
    CreatureRuntimeBindingRegistry,
)
from dnd.content_system.runtime import (
    SERVER_CONTENT_SYSTEM_RUNTIME,
    ContentSystemRuntime,
)
from dnd.core.content.identities import ContentDefinitionKind, ContentRef
from dnd.core.content.materialization import (
    CreatureBuildContext,
    CreatureDeploymentRole,
    CreaturePossessionMode,
)
from dnd.core.content.recipes import ContentRecipe
from dnd.core.content.registration import ContentDeclaration
from dnd.entity import Entity


_EntityT = TypeVar("_EntityT", bound=Entity)


def resolve_creature_recipe(
    recipe: ContentRecipe,
    *,
    runtime: ContentSystemRuntime = SERVER_CONTENT_SYSTEM_RUNTIME,
) -> ContentDeclaration:
    """Resolve one exact creature recipe through the sole process registry."""
    recipe.verify_integrity()
    if recipe.ref.definition_kind != ContentDefinitionKind.CREATURE:
        raise TypeError(
            f"Creature materialization requires a creature recipe; got "
            f"{recipe.ref.definition_kind.value}",
        )
    return runtime.require().registry.resolve_factory(recipe.ref)


@overload
def materialize_creature(
    recipe: ContentRecipe,
    *,
    runtime_entity_uuid: UUID,
    display_name: str,
    faction: str | None,
    position: tuple[int, int],
    deployment_role: CreatureDeploymentRole,
    possession_mode: CreaturePossessionMode,
    expected_type: type[_EntityT],
    entity_content_ref: ContentRef | None = None,
    binding_registry: CreatureRuntimeBindingRegistry = CREATURE_RUNTIME_BINDINGS,
    runtime: ContentSystemRuntime = SERVER_CONTENT_SYSTEM_RUNTIME,
) -> _EntityT: ...


@overload
def materialize_creature(
    recipe: ContentRecipe,
    *,
    runtime_entity_uuid: UUID,
    display_name: str,
    faction: str | None,
    position: tuple[int, int],
    deployment_role: CreatureDeploymentRole,
    possession_mode: CreaturePossessionMode,
    expected_type: None = None,
    entity_content_ref: ContentRef | None = None,
    binding_registry: CreatureRuntimeBindingRegistry = CREATURE_RUNTIME_BINDINGS,
    runtime: ContentSystemRuntime = SERVER_CONTENT_SYSTEM_RUNTIME,
) -> Entity: ...


def materialize_creature(
    recipe: ContentRecipe,
    *,
    runtime_entity_uuid: UUID,
    display_name: str,
    faction: str | None,
    position: tuple[int, int],
    deployment_role: CreatureDeploymentRole,
    possession_mode: CreaturePossessionMode,
    expected_type: type[_EntityT] | None = None,
    entity_content_ref: ContentRef | None = None,
    binding_registry: CreatureRuntimeBindingRegistry = CREATURE_RUNTIME_BINDINGS,
    runtime: ContentSystemRuntime = SERVER_CONTENT_SYSTEM_RUNTIME,
) -> Entity | _EntityT:
    """Construct and identity-check one creature through the frozen registry."""
    resolve_creature_recipe(recipe, runtime=runtime)
    context = CreatureBuildContext(
        runtime_entity_uuid=runtime_entity_uuid,
        requested_ref=entity_content_ref or recipe.ref,
        display_name=display_name,
        faction=faction,
        position=position,
        deployment_role=deployment_role,
        possession_mode=possession_mode,
    )
    result = runtime.materialize(recipe, context)
    if not isinstance(result, Entity):
        raise TypeError(
            f"Creature factory {recipe.ref.identity_key} returned "
            f"{type(result).__module__}.{type(result).__name__}",
        )
    if (
        result.uuid != context.runtime_entity_uuid
        or result.source_entity_uuid != context.runtime_entity_uuid
    ):
        raise ValueError(
            f"Creature factory {recipe.ref.identity_key} did not preserve its "
            "exact runtime entity/source UUID",
        )
    expected_content_ref = entity_content_ref or recipe.ref
    if result.content_ref != expected_content_ref:
        raise ValueError(
            f"Creature factory {recipe.ref.identity_key} did not bind its exact "
            "content reference; expected runtime identity "
            f"{expected_content_ref.identity_key}",
        )
    if expected_type is not None and not isinstance(result, expected_type):
        raise TypeError(
            f"Creature factory {recipe.ref.identity_key} returned "
            f"{type(result).__module__}.{type(result).__name__}; expected "
            f"{expected_type.__module__}.{expected_type.__name__}",
        )
    binding_registry.bind(
        CreatureRuntimeBinding(
            runtime_entity_uuid=result.uuid,
            recipe=recipe,
            content_set_digest=runtime.require().content_set_digest,
            deployment_role=deployment_role,
            possession_mode=possession_mode,
        ),
    )
    return result
