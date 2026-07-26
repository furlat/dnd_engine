"""Canonical runtime adapter for item recipes."""

from __future__ import annotations

from typing import TypeVar, overload
from uuid import UUID

from dnd.blocks.base_item import BaseItem
from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.item_bindings import (
    ITEM_RUNTIME_BINDINGS,
    ItemRuntimeBindingRegistry,
    ItemRuntimeOrigin,
)
from dnd.content_system.item_runtime_materialization import (
    materialize_item_from_installed_runtime,
    resolve_installed_item_recipe,
)
from dnd.content_system.runtime import (
    SERVER_CONTENT_SYSTEM_RUNTIME,
    ContentSystemRuntime,
)
from dnd.core.content.recipes import ContentRecipe
from dnd.core.content.registration import ContentDeclaration


_ItemT = TypeVar("_ItemT", bound=BaseItem)


def _ensure_content_system(
    runtime: ContentSystemRuntime,
) -> None:
    if runtime.is_installed:
        return
    runtime.install(bootstrap_content_system())


def resolve_item_recipe(
    recipe: ContentRecipe,
    *,
    runtime: ContentSystemRuntime = SERVER_CONTENT_SYSTEM_RUNTIME,
) -> ContentDeclaration:
    """Resolve one exact item recipe through the sole process registry."""
    _ensure_content_system(runtime)
    return resolve_installed_item_recipe(recipe, runtime=runtime)


@overload
def materialize_item(
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
def materialize_item(
    recipe: ContentRecipe,
    source_entity_uuid: UUID,
    *,
    origin: ItemRuntimeOrigin,
    expected_type: None = None,
    character_item_id: UUID | None = None,
    binding_registry: ItemRuntimeBindingRegistry = ITEM_RUNTIME_BINDINGS,
    runtime: ContentSystemRuntime = SERVER_CONTENT_SYSTEM_RUNTIME,
) -> BaseItem: ...


def materialize_item(
    recipe: ContentRecipe,
    source_entity_uuid: UUID,
    *,
    origin: ItemRuntimeOrigin,
    expected_type: type[_ItemT] | None = None,
    character_item_id: UUID | None = None,
    binding_registry: ItemRuntimeBindingRegistry = ITEM_RUNTIME_BINDINGS,
    runtime: ContentSystemRuntime = SERVER_CONTENT_SYSTEM_RUNTIME,
) -> BaseItem | _ItemT:
    """Construct and identity-check one item through the frozen registry."""
    _ensure_content_system(runtime)
    return materialize_item_from_installed_runtime(
        recipe,
        source_entity_uuid,
        origin=origin,
        expected_type=expected_type,
        character_item_id=character_item_id,
        binding_registry=binding_registry,
        runtime=runtime,
    )
