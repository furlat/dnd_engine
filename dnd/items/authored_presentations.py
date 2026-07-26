"""Cold bindings from the reviewed item-visual ledger into item descriptors."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from pydantic import BaseModel

from dnd.core.content.dependencies import ContentDependency
from dnd.core.content.descriptors import (
    ContentDescriptorSpec,
    ContentPresentation,
    EquipmentSpritePresentation,
)
from dnd.core.content.item_definitions import ItemDefinition
from dnd.core.content.provenance import ContentProvenance
from dnd.core.content.registration import item_factory
from dnd.items.authored_variant_inventory import (
    AUTHORED_ITEM_VARIANT_CATEGORIES,
    primary_authored_item_equipment_layer,
)


_Factory = TypeVar("_Factory", bound=Callable[..., object])


def bind_authored_item_presentation(
    *,
    factory_identity: str,
    descriptor: ContentDescriptorSpec,
) -> ContentDescriptorSpec:
    """Apply the exact reviewed base and per-slot sprite facts, if authored."""
    bindings = tuple(
        (category, binding)
        for category in AUTHORED_ITEM_VARIANT_CATEGORIES
        for binding in category.factory_presentation_bindings
        if binding.factory_identity == factory_identity
    )
    if not bindings:
        return descriptor
    owners = tuple(
        category
        for category, binding in bindings
        if binding.root_presentation_owner
    )
    if len(owners) != 1:
        raise ValueError(
            "authored item factory requires exactly one root presentation "
            f"owner: {factory_identity}",
        )
    slots = [binding.equipment_slot for _, binding in bindings]
    if len(slots) != len(set(slots)):
        raise ValueError(
            "authored item factory has conflicting equipment slot bindings: "
            f"{factory_identity}",
        )
    owner = owners[0]
    owner_primary_layer = primary_authored_item_equipment_layer(
        owner,
        owner.base_presentation,
    )
    equipment_sprites = tuple(
        EquipmentSpritePresentation(
            equipment_slot=binding.equipment_slot,
            render_layer=layer.render_layer,
            sprite_key=layer.sprite_key,
            tint_rgb=layer.tint_rgb,
        )
        for category, binding in bindings
        for layer in category.base_presentation.equipment_layers
    )
    presentation = ContentPresentation.model_validate(
        {
            **descriptor.presentation.model_dump(mode="python"),
            "sprite_key": owner_primary_layer.sprite_key,
            "tint_rgb": owner_primary_layer.tint_rgb,
            "equipment_sprites": equipment_sprites,
        },
    )
    return ContentDescriptorSpec.model_validate(
        {
            **descriptor.model_dump(mode="python"),
            "presentation": presentation,
        },
    )


def authored_item_factory(
    *,
    pack_id: str,
    content_id: str,
    version: int,
    parameters: type[BaseModel],
    descriptor: ContentDescriptorSpec,
    provenance: ContentProvenance,
    item_definition: ItemDefinition,
    dependencies: tuple[ContentDependency, ...] = (),
) -> Callable[[_Factory], _Factory]:
    """Declare an item factory with any reviewed equipment presentation bound."""
    factory_identity = f"{pack_id}:item:{content_id}@{version}"
    return item_factory(
        pack_id=pack_id,
        content_id=content_id,
        version=version,
        parameters=parameters,
        descriptor=bind_authored_item_presentation(
            factory_identity=factory_identity,
            descriptor=descriptor,
        ),
        provenance=provenance,
        item_definition=item_definition,
        dependencies=dependencies,
    )
