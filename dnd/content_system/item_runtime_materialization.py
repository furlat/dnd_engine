"""Item materialization against an already-installed frozen content runtime."""

from __future__ import annotations

from typing import TypeVar, overload
from uuid import UUID

from dnd.blocks.base_item import BaseItem, UsableItem
from dnd.content_system.item_bindings import (
    ITEM_RUNTIME_BINDINGS,
    ItemRuntimeBinding,
    ItemRuntimeBindingRegistry,
    ItemRuntimeOrigin,
)
from dnd.content_system.runtime import (
    SERVER_CONTENT_SYSTEM_RUNTIME,
    ContentSystemRuntime,
)
from dnd.core.content.materialization import ItemBuildContext
from dnd.core.content.recipes import ContentRecipe
from dnd.core.content.registration import ContentDeclaration
from dnd.core.content.runtime import has_direct_behavior_declaration


_ItemT = TypeVar("_ItemT", bound=BaseItem)


def resolve_installed_item_recipe(
    recipe: ContentRecipe,
    *,
    runtime: ContentSystemRuntime = SERVER_CONTENT_SYSTEM_RUNTIME,
) -> ContentDeclaration:
    """Resolve one exact item recipe without owning process bootstrap."""
    recipe.verify_integrity()
    return runtime.require().registry.resolve_factory(recipe.ref)


@overload
def materialize_item_from_installed_runtime(
    recipe: ContentRecipe,
    source_entity_uuid: UUID,
    *,
    origin: ItemRuntimeOrigin,
    expected_type: type[_ItemT],
    character_item_id: UUID | None = None,
    binding_registry: ItemRuntimeBindingRegistry = ITEM_RUNTIME_BINDINGS,
    runtime: ContentSystemRuntime = SERVER_CONTENT_SYSTEM_RUNTIME,
) -> _ItemT: ...


@overload
def materialize_item_from_installed_runtime(
    recipe: ContentRecipe,
    source_entity_uuid: UUID,
    *,
    origin: ItemRuntimeOrigin,
    expected_type: None = None,
    character_item_id: UUID | None = None,
    binding_registry: ItemRuntimeBindingRegistry = ITEM_RUNTIME_BINDINGS,
    runtime: ContentSystemRuntime = SERVER_CONTENT_SYSTEM_RUNTIME,
) -> BaseItem: ...


def materialize_item_from_installed_runtime(
    recipe: ContentRecipe,
    source_entity_uuid: UUID,
    *,
    origin: ItemRuntimeOrigin,
    expected_type: type[_ItemT] | None = None,
    character_item_id: UUID | None = None,
    binding_registry: ItemRuntimeBindingRegistry = ITEM_RUNTIME_BINDINGS,
    runtime: ContentSystemRuntime = SERVER_CONTENT_SYSTEM_RUNTIME,
) -> BaseItem | _ItemT:
    """Construct and bind an item without importing startup composition."""
    loaded = runtime.require()
    declaration = resolve_installed_item_recipe(recipe, runtime=runtime)
    definition = declaration.item_definition
    if definition is None:
        raise TypeError(
            f"Item factory {recipe.ref.identity_key} has no item definition",
        )
    binding_registry.validate_origin(
        definition,
        origin,
        character_item_id,
    )
    context = ItemBuildContext(
        source_entity_uuid=source_entity_uuid,
        requested_ref=recipe.ref,
    )
    result = runtime.materialize(recipe, context)
    if not isinstance(result, BaseItem):
        raise TypeError(
            f"Item factory {recipe.ref.identity_key} returned "
            f"{type(result).__module__}.{type(result).__name__}",
        )
    if result.content_ref != recipe.ref:
        raise ValueError(
            f"Item factory {recipe.ref.identity_key} did not bind its exact "
            "content reference",
        )
    if expected_type is not None and not isinstance(result, expected_type):
        raise TypeError(
            f"Item factory {recipe.ref.identity_key} returned "
            f"{type(result).__module__}.{type(result).__name__}; expected "
            f"{expected_type.__module__}.{expected_type.__name__}",
        )
    if isinstance(result, UsableItem):
        for template in result.use_action_templates:
            if not has_direct_behavior_declaration(template):
                continue
            runtime.bind_child(
                template,
                provider=result,
                runtime_owner_uuid=result.uuid,
            )
    if result.stack_id is not None:
        result.stack_id = recipe.recipe_digest
    preset = loaded.registry.find_recipe_preset(recipe)
    binding_registry.bind(
        ItemRuntimeBinding(
            runtime_item_uuid=result.uuid,
            recipe=recipe,
            content_set_digest=loaded.content_set_digest,
            origin=origin,
            recipe_preset_ref=preset.ref if preset is not None else None,
            character_item_id=character_item_id,
        ),
        definition,
    )
    return result
