"""Pack-owned named recipes for the complete supported item visual inventory."""

from __future__ import annotations

from types import MappingProxyType

from dnd.core.content.descriptors import (
    ContentDescriptorSpec,
    ContentPresentation,
    EquipmentSpritePresentation,
)
from dnd.core.content.provenance import (
    ContentFidelity,
    ContentProvenance,
    ContentProvenanceRelation,
    ContentReviewStatus,
)
from dnd.core.content.recipe_presets import ContentRecipePreset
from dnd.core.content.recipes import ContentRecipe
from dnd.core.content.registration import ContentDeclaration
from dnd.items.armors import (
    NEURODRAGON_ARMOR_DECLARATIONS,
    SRD_ARMOR_DECLARATIONS,
)
from dnd.items.authored_variant_inventory import (
    AUTHORED_ITEM_VARIANT_CATEGORIES,
    AuthoredItemVariantCategory,
    AuthoredItemVariantInventoryRow,
    primary_authored_item_equipment_layer,
)
from dnd.items.weapons import (
    ARCANE_STAFF_RECIPE,
    ASSASSIN_DAGGER_RECIPE,
    NEURODRAGON_WEAPON_DECLARATIONS,
    SRD_WEAPON_DECLARATIONS,
)


_DECLARATIONS_BY_IDENTITY = MappingProxyType({
    declaration.ref.identity_key: declaration
    for declaration in (
        *NEURODRAGON_ARMOR_DECLARATIONS,
        *NEURODRAGON_WEAPON_DECLARATIONS,
        *SRD_ARMOR_DECLARATIONS,
        *SRD_WEAPON_DECLARATIONS,
    )
})
_FIXED_RECIPES_BY_VISUAL_VARIANT_ID = MappingProxyType({
    "10000004": ASSASSIN_DAGGER_RECIPE,
    "1000000f": ARCANE_STAFF_RECIPE,
})


def _variant_provenance(
    category: AuthoredItemVariantCategory,
    row: AuthoredItemVariantInventoryRow,
) -> ContentProvenance:
    return ContentProvenance(
        primary_source_id="neurodragon.original_b2b3930",
        source_anchor=(
            "NeuroClient authored item visual inventory "
            f"{category.base_category}/{row.source_visual_variant_id}: "
            f"{row.display_name}"
        ),
        relation=ContentProvenanceRelation.ORIGINAL_CONTENT,
        fidelity=ContentFidelity.COMPLETE,
        review_status=ContentReviewStatus.REVIEWED,
        notes=(
            "Presentation-only named recipe; mechanics remain owned by the "
            "exact related item factory."
        ),
    )


def _variant_recipe(
    declaration: ContentDeclaration,
    row: AuthoredItemVariantInventoryRow,
) -> ContentRecipe:
    fixed = _FIXED_RECIPES_BY_VISUAL_VARIANT_ID.get(
        str(row.visual_variant_id),
    )
    if fixed is not None:
        if fixed.ref != declaration.ref:
            raise ValueError(
                f"fixed authored recipe target mismatch for {row.inventory_id}",
            )
        return fixed
    construction = declaration.construction
    if construction is None:
        raise ValueError(
            f"authored item target is not constructible: {row.inventory_id}",
        )
    required_parameters = {"display_name", "visual_variant_id"}
    if not required_parameters.issubset(
        construction.parameter_model.model_fields,
    ):
        raise ValueError(
            "authored item target lacks typed presentation parameters: "
            f"{declaration.ref.identity_key}",
        )
    return ContentRecipe.create(
        ref=declaration.ref,
        parameters={
            "display_name": row.display_name,
            "visual_variant_id": row.visual_variant_id,
        },
    )


def _build_variant_preset(
    category: AuthoredItemVariantCategory,
    row: AuthoredItemVariantInventoryRow,
) -> ContentRecipePreset:
    target_identity = row.mechanical_factory_identity
    if target_identity is None or row.preset_id is None:
        raise ValueError(f"unsupported row entered preset build: {row.inventory_id}")
    declaration = _DECLARATIONS_BY_IDENTITY.get(target_identity)
    if declaration is None:
        raise ValueError(
            f"authored item target is not installed: {target_identity}",
        )
    descriptor = declaration.descriptor
    description = row.notes or (
        f"A NeuroDragon-authored presentation variant of "
        f"{category.base_category}."
    )
    primary_layer = primary_authored_item_equipment_layer(category, row)
    equipment_sprites = {
        (
            equipment_sprite.equipment_slot,
            equipment_sprite.render_layer,
        ): equipment_sprite
        for equipment_sprite in descriptor.presentation.equipment_sprites
        if equipment_sprite.equipment_slot is not category.equipment_slot
    }
    equipment_sprites.update(
        {
            (category.equipment_slot, layer.render_layer): (
                EquipmentSpritePresentation(
                    equipment_slot=category.equipment_slot,
                    render_layer=layer.render_layer,
                    sprite_key=layer.sprite_key,
                    tint_rgb=layer.tint_rgb,
                )
            )
            for layer in row.equipment_layers
        },
    )
    presentation = ContentPresentation.model_validate(
        {
            **descriptor.presentation.model_dump(mode="python"),
            "sprite_key": primary_layer.sprite_key,
            "tint_rgb": primary_layer.tint_rgb,
            "visual_variant_key": row.visual_variant_id,
            "equipment_sprites": tuple(equipment_sprites.values()),
        },
    )
    return ContentRecipePreset.create(
        pack_id="content.neurodragon",
        preset_id=row.preset_id,
        preset_version=1,
        recipe=_variant_recipe(declaration, row),
        descriptor=ContentDescriptorSpec(
            display_name=row.display_name,
            description=description,
            tags=tuple((*descriptor.tags, *row.tags, "variant")),
            visibility=descriptor.visibility,
            presentation=presentation,
            ordering=descriptor.ordering.model_copy(
                update={
                    "sort_order": (
                        descriptor.ordering.sort_order * 100_000
                        + category.source_order * 1_000
                        + row.source_order
                    ),
                },
            ),
            related_content_refs=(declaration.ref,),
        ),
        provenance=_variant_provenance(category, row),
    )


_authored_presets: list[ContentRecipePreset] = []
for _category in AUTHORED_ITEM_VARIANT_CATEGORIES:
    if _category.classification != "supported_existing_factory":
        continue
    for _row in _category.variants:
        _authored_presets.append(
            _build_variant_preset(_category, _row),
        )

NEURODRAGON_AUTHORED_ITEM_RECIPE_PRESETS = tuple(
    _authored_presets,
)
CONTENT_RECIPE_PRESETS = NEURODRAGON_AUTHORED_ITEM_RECIPE_PRESETS
AUTHORED_ITEM_RECIPE_PRESETS_BY_PRESET_ID = MappingProxyType({
    preset.ref.preset_id: preset
    for preset in NEURODRAGON_AUTHORED_ITEM_RECIPE_PRESETS
})
AUTHORED_ITEM_RECIPE_PRESETS_BY_PRESENTATION_KEY = MappingProxyType({
    (
        str(preset.descriptor.presentation.sprite_key),
        str(preset.descriptor.presentation.visual_variant_key),
    ): preset
    for preset in NEURODRAGON_AUTHORED_ITEM_RECIPE_PRESETS
})
