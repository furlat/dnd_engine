"""Exact coverage for the backend-owned authored item visual inventory."""

from __future__ import annotations

import ast
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

import dnd.items.apparel_presets as apparel_preset_module
import dnd.items.authored_variant_presets as authored_preset_module
from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.item_bindings import ItemRuntimeOrigin
from dnd.content_system.item_materialization import materialize_item
from dnd.core.content.descriptors import (
    ContentPresentation,
    EquipmentSpritePresentation,
)
from dnd.core.content.recipe_presets import (
    scan_module_content_recipe_presets,
)
from dnd.core.equipment_types import EquipmentRenderLayer, VisualLoadoutSlot
from dnd.items.authored_variant_inventory import (
    AUTHORED_ITEM_VARIANT_CATEGORIES,
    AUTHORED_ITEM_VARIANT_LEDGER,
    AUTHORED_ITEM_VARIANT_ROWS,
    SUPPORTED_AUTHORED_ITEM_VARIANT_ROWS,
    UNSUPPORTED_AUTHORED_ITEM_VARIANT_ROWS,
    primary_authored_item_equipment_layer,
)
from dnd.items.authored_variant_presets import (
    AUTHORED_ITEM_RECIPE_PRESETS_BY_PRESENTATION_KEY,
    AUTHORED_ITEM_RECIPE_PRESETS_BY_PRESET_ID,
    NEURODRAGON_AUTHORED_ITEM_RECIPE_PRESETS,
)
from server.content_catalog import build_public_content_catalog


def _equipment_sprite_map(
    presentation: ContentPresentation,
) -> dict[VisualLoadoutSlot, str]:
    primary_layers = {
        VisualLoadoutSlot.WEAPON_MELEE_MAIN: EquipmentRenderLayer.WEAPON,
        VisualLoadoutSlot.WEAPON_MELEE_OFF: EquipmentRenderLayer.OFFHAND,
        VisualLoadoutSlot.WEAPON_RANGED_MAIN: EquipmentRenderLayer.WEAPON,
        VisualLoadoutSlot.WEAPON_RANGED_OFF: EquipmentRenderLayer.OFFHAND,
        VisualLoadoutSlot.HELMET: EquipmentRenderLayer.HELMET,
        VisualLoadoutSlot.BODY_ARMOR: EquipmentRenderLayer.CHEST,
        VisualLoadoutSlot.GAUNTLETS: EquipmentRenderLayer.HANDS,
        VisualLoadoutSlot.BOOTS: EquipmentRenderLayer.SHOES,
    }
    return {
        row.equipment_slot: row.sprite_key
        for row in presentation.equipment_sprites
        if row.render_layer is primary_layers.get(row.equipment_slot)
    }


def test_backend_ledger_authenticates_the_exact_reviewed_source_snapshot() -> None:
    ledger = AUTHORED_ITEM_VARIANT_LEDGER

    assert ledger.schema_version == 3
    assert ledger.source.repository == "NeuroClient"
    assert ledger.source.repository_relative_path == (
        "app/src/render/data/defaultItemVisualMap.json"
    )
    assert ledger.source.sha256 == (
        "3adaea5f6717fd8fc19198176ebe2cd32211681d6c522163a998697aca83a27a"
    )
    assert ledger.source.source_base_category_count == 77
    assert ledger.authored_category_count == 77
    assert ledger.authored_variant_count == 205
    assert ledger.inventory_digest == (
        "304c44499560b4165582235c1442a9171a215bb99438023044f684c5b534e018"
    )


def test_every_authored_row_is_supported_or_explicitly_unsupported() -> None:
    supported_categories = tuple(
        category
        for category in AUTHORED_ITEM_VARIANT_CATEGORIES
        if category.classification == "supported_existing_factory"
    )
    unsupported_categories = tuple(
        category
        for category in AUTHORED_ITEM_VARIANT_CATEGORIES
        if category.classification == "unsupported_missing_factory"
    )
    expected_supported_rows = tuple(
        row
        for category in supported_categories
        for row in category.variants
    )
    expected_unsupported_rows = tuple(
        row
        for category in unsupported_categories
        for row in category.variants
    )

    assert len(supported_categories) == 76
    assert tuple(
        category.base_category
        for category in unsupported_categories
    ) == ("Rusty Blade",)
    assert all(
        isinstance(category.equipment_slot, VisualLoadoutSlot)
        for category in AUTHORED_ITEM_VARIANT_CATEGORIES
    )
    assert tuple(
        category.source_order
        for category in AUTHORED_ITEM_VARIANT_CATEGORIES
    ) == tuple(range(77))
    assert SUPPORTED_AUTHORED_ITEM_VARIANT_ROWS == expected_supported_rows
    assert UNSUPPORTED_AUTHORED_ITEM_VARIANT_ROWS == expected_unsupported_rows
    assert (
        {
            row.inventory_id
            for row in SUPPORTED_AUTHORED_ITEM_VARIANT_ROWS
        }
        | {
            row.inventory_id
            for row in UNSUPPORTED_AUTHORED_ITEM_VARIANT_ROWS
        }
        == {
            row.inventory_id
            for row in AUTHORED_ITEM_VARIANT_ROWS
        }
    )
    assert {
        row.inventory_id
        for row in SUPPORTED_AUTHORED_ITEM_VARIANT_ROWS
    }.isdisjoint(
        row.inventory_id
        for row in UNSUPPORTED_AUTHORED_ITEM_VARIANT_ROWS
    )
    assert UNSUPPORTED_AUTHORED_ITEM_VARIANT_ROWS == ()
    assert all(
        category.unsupported_reason
        for category in unsupported_categories
    )
    assert all(
        row.preset_id is None
        and row.visual_variant_id is None
        and row.mechanical_factory_identity is None
        for row in UNSUPPORTED_AUTHORED_ITEM_VARIANT_ROWS
    )


def test_supported_roots_have_one_owner_and_complete_slot_presentations() -> None:
    loaded = bootstrap_content_system()
    bindings_by_identity = {
        identity: tuple(
            (category, binding)
            for category in AUTHORED_ITEM_VARIANT_CATEGORIES
            for binding in category.factory_presentation_bindings
            if binding.factory_identity == identity
        )
        for identity in {
            binding.factory_identity
            for category in AUTHORED_ITEM_VARIANT_CATEGORIES
            for binding in category.factory_presentation_bindings
        }
    }

    assert len(bindings_by_identity) == 78
    assert sum(map(len, bindings_by_identity.values())) == 87
    for identity, category_bindings in bindings_by_identity.items():
        owners = tuple(
            category
            for category, binding in category_bindings
            if binding.root_presentation_owner
        )
        assert len(owners) == 1, identity
        [owner] = owners
        expected_sprites = {
            binding.equipment_slot: (
                primary_authored_item_equipment_layer(
                    category,
                    category.base_presentation,
                ).sprite_key
            )
            for category, binding in category_bindings
        }
        assert len(expected_sprites) == len(category_bindings), identity

        declaration = loaded.registry.declarations[identity]
        presentation = declaration.descriptor.presentation
        owner_primary_layer = primary_authored_item_equipment_layer(
            owner,
            owner.base_presentation,
        )
        assert presentation.sprite_key == (
            owner_primary_layer.sprite_key
        ), identity
        assert presentation.tint_rgb == (
            owner_primary_layer.tint_rgb
        ), identity
        assert _equipment_sprite_map(presentation) == expected_sprites, identity
        assert all(
            isinstance(row.equipment_slot, VisualLoadoutSlot)
            and isinstance(row.render_layer, EquipmentRenderLayer)
            for row in presentation.equipment_sprites
        )


def test_every_preset_overrides_only_its_category_equipment_sprite() -> None:
    loaded = bootstrap_content_system()

    for category in AUTHORED_ITEM_VARIANT_CATEGORIES:
        if category.classification != "supported_existing_factory":
            continue
        for row in category.variants:
            assert row.preset_id is not None
            assert row.mechanical_factory_identity is not None
            preset = AUTHORED_ITEM_RECIPE_PRESETS_BY_PRESET_ID[
                row.preset_id
            ]
            root = loaded.registry.declarations[
                row.mechanical_factory_identity
            ].descriptor.presentation
            expected_sprites = _equipment_sprite_map(root)
            expected_sprites[category.equipment_slot] = (
                primary_authored_item_equipment_layer(
                    category,
                    row,
                ).sprite_key
            )

            presentation = preset.descriptor.presentation
            primary_layer = primary_authored_item_equipment_layer(category, row)
            assert presentation.sprite_key == primary_layer.sprite_key
            assert presentation.tint_rgb == primary_layer.tint_rgb
            assert _equipment_sprite_map(presentation) == expected_sprites
            assert {
                (
                    equipment_sprite.render_layer,
                    equipment_sprite.sprite_key,
                    equipment_sprite.tint_rgb,
                )
                for equipment_sprite in presentation.equipment_sprites
                if equipment_sprite.equipment_slot is category.equipment_slot
            } == {
                (
                    equipment_layer.render_layer,
                    equipment_layer.sprite_key,
                    equipment_layer.tint_rgb,
                )
                for equipment_layer in row.equipment_layers
            }


def test_dagger_root_and_variants_preserve_main_and_offhand_sprites() -> None:
    dagger_identity = "content.srd_5_1_cc:item:weapon.dagger@1"
    [main_category] = [
        category
        for category in AUTHORED_ITEM_VARIANT_CATEGORIES
        if category.base_category == "Dagger"
    ]
    [offhand_category] = [
        category
        for category in AUTHORED_ITEM_VARIANT_CATEGORIES
        if category.base_category == "Off-hand Dagger"
    ]

    assert main_category.mechanical_factory_identity == dagger_identity
    assert main_category.equipment_slot is (
        VisualLoadoutSlot.WEAPON_MELEE_MAIN
    )
    [main_binding] = [
        binding
        for binding in main_category.factory_presentation_bindings
        if binding.factory_identity == dagger_identity
    ]
    assert main_binding.root_presentation_owner
    assert primary_authored_item_equipment_layer(
        main_category,
        main_category.base_presentation,
    ).sprite_key == "Melee1"
    assert offhand_category.mechanical_factory_identity == dagger_identity
    assert offhand_category.equipment_slot is (
        VisualLoadoutSlot.WEAPON_MELEE_OFF
    )
    [offhand_binding] = [
        binding
        for binding in offhand_category.factory_presentation_bindings
        if binding.factory_identity == dagger_identity
    ]
    assert not offhand_binding.root_presentation_owner
    assert primary_authored_item_equipment_layer(
        offhand_category,
        offhand_category.base_presentation,
    ).sprite_key == "Offhand2"

    dagger_root = (
        bootstrap_content_system()
        .registry
        .declarations[dagger_identity]
        .descriptor
        .presentation
    )
    assert dagger_root.sprite_key == "Melee1"
    assert _equipment_sprite_map(dagger_root) == {
        VisualLoadoutSlot.WEAPON_MELEE_MAIN: "Melee1",
        VisualLoadoutSlot.WEAPON_MELEE_OFF: "Offhand2",
    }

    main_row = next(
        row
        for row in main_category.variants
        if row.mechanical_factory_identity == dagger_identity
    )
    offhand_row = offhand_category.variants[0]
    assert main_row.preset_id is not None
    assert offhand_row.preset_id is not None
    main_preset = AUTHORED_ITEM_RECIPE_PRESETS_BY_PRESET_ID[
        main_row.preset_id
    ]
    offhand_preset = AUTHORED_ITEM_RECIPE_PRESETS_BY_PRESET_ID[
        offhand_row.preset_id
    ]

    assert _equipment_sprite_map(
        main_preset.descriptor.presentation,
    ) == {
        VisualLoadoutSlot.WEAPON_MELEE_MAIN: (
            primary_authored_item_equipment_layer(
                main_category,
                main_row,
            ).sprite_key
        ),
        VisualLoadoutSlot.WEAPON_MELEE_OFF: "Offhand2",
    }
    assert _equipment_sprite_map(
        offhand_preset.descriptor.presentation,
    ) == {
        VisualLoadoutSlot.WEAPON_MELEE_MAIN: "Melee1",
        VisualLoadoutSlot.WEAPON_MELEE_OFF: (
            primary_authored_item_equipment_layer(
                offhand_category,
                offhand_row,
            ).sprite_key
        ),
    }


def test_alias_bindings_close_special_and_creature_equipment_slots() -> None:
    loaded = bootstrap_content_system()
    expected = {
        (
            "content.neurodragon:item:weapon.assassin_dagger@1",
            VisualLoadoutSlot.WEAPON_MELEE_OFF,
        ): "Offhand2",
        (
            "content.neurodragon:item:weapon.circus.rusty_dagger@1",
            VisualLoadoutSlot.WEAPON_MELEE_OFF,
        ): "Offhand2",
        (
            "content.neurodragon:item:weapon.circus.flaming_scimitar@1",
            VisualLoadoutSlot.WEAPON_MELEE_OFF,
        ): "Offhand1",
        (
            "content.srd_5_1_cc:item:weapon.creature.kobold_sling@1",
            VisualLoadoutSlot.WEAPON_RANGED_MAIN,
        ): "Ranged5",
        (
            "content.srd_5_1_cc:item:weapon.creature.spy_hand_crossbow@1",
            VisualLoadoutSlot.WEAPON_RANGED_MAIN,
        ): "Ranged2",
        (
            "content.srd_5_1_cc:item:"
            "weapon.creature.bandit_captain_thrown_dagger@1",
            VisualLoadoutSlot.WEAPON_RANGED_MAIN,
        ): "Melee1",
        (
            "content.srd_5_1_cc:item:weapon.creature.thrown_javelin@1",
            VisualLoadoutSlot.WEAPON_RANGED_MAIN,
        ): "Melee24",
        (
            "content.srd_5_1_cc:item:"
            "weapon.creature.bugbear_morningstar@1",
            VisualLoadoutSlot.WEAPON_MELEE_MAIN,
        ): "Melee12",
        (
            "content.srd_5_1_cc:item:weapon.creature.ogre_greatclub@1",
            VisualLoadoutSlot.WEAPON_MELEE_MAIN,
        ): "Melee10",
        (
            "content.srd_5_1_cc:item:"
            "weapon.creature.ogre_thrown_javelin@1",
            VisualLoadoutSlot.WEAPON_RANGED_MAIN,
        ): "Melee24",
        (
            "content.srd_5_1_cc:item:"
            "weapon.creature.ogre_zombie_morningstar@1",
            VisualLoadoutSlot.WEAPON_MELEE_MAIN,
        ): "Melee12",
    }

    actual = {}
    for identity, slot in expected:
        presentation = (
            loaded.registry.declarations[identity].descriptor.presentation
        )
        actual[(identity, slot)] = _equipment_sprite_map(presentation)[slot]

    assert actual == expected
    shield_presentation = (
        loaded.registry.declarations[
            "content.srd_5_1_cc:item:shield.shield@1"
        ].descriptor.presentation
    )
    assert _equipment_sprite_map(shield_presentation) == {
        VisualLoadoutSlot.WEAPON_MELEE_OFF: "Shield5",
    }


def test_source_id_collision_is_evidence_only_and_runtime_ids_are_unique() -> None:
    expected_collision_groups = (
        AUTHORED_ITEM_VARIANT_LEDGER
        .inventory
        .source_visual_variant_id_collisions
    )
    assert expected_collision_groups == {
        "h0000017": (
            "item_visual.cloth_hood.h0000017",
            "item_visual.monster_helm.h0000017",
        ),
    }
    inventory_ids = [row.inventory_id for row in AUTHORED_ITEM_VARIANT_ROWS]
    supported_presentation_keys = [
        (
            primary_authored_item_equipment_layer(category, row).sprite_key,
            row.visual_variant_id,
        )
        for category in AUTHORED_ITEM_VARIANT_CATEGORIES
        if category.classification == "supported_existing_factory"
        for row in category.variants
    ]
    source_groups = {
        source_id: tuple(
            row.inventory_id
            for row in AUTHORED_ITEM_VARIANT_ROWS
            if row.source_visual_variant_id == source_id
        )
        for source_id in {
            row.source_visual_variant_id
            for row in AUTHORED_ITEM_VARIANT_ROWS
        }
    }
    runtime_visual_groups = {
        visual_id: tuple(
            row.inventory_id
            for row in SUPPORTED_AUTHORED_ITEM_VARIANT_ROWS
            if row.visual_variant_id == visual_id
        )
        for visual_id in {
            row.visual_variant_id
            for row in SUPPORTED_AUTHORED_ITEM_VARIANT_ROWS
        }
    }

    assert len(inventory_ids) == len(set(inventory_ids))
    assert {
        source_id: inventory_group
        for source_id, inventory_group in source_groups.items()
        if len(inventory_group) > 1
    } == expected_collision_groups
    assert {
        visual_id: inventory_group
        for visual_id, inventory_group in runtime_visual_groups.items()
        if len(inventory_group) > 1
    } == expected_collision_groups
    assert len(supported_presentation_keys) == len(
        set(supported_presentation_keys),
    )


def test_supported_rows_have_one_unique_pack_owned_preset_and_recipe() -> None:
    presets = NEURODRAGON_AUTHORED_ITEM_RECIPE_PRESETS
    preset_ids = [preset.ref.identity_key for preset in presets]
    recipe_digests = [preset.recipe.recipe_digest for preset in presets]
    rows_by_presentation_key = {
        (
            primary_authored_item_equipment_layer(category, row).sprite_key,
            str(row.visual_variant_id),
        ): row
        for category in AUTHORED_ITEM_VARIANT_CATEGORIES
        if category.classification == "supported_existing_factory"
        for row in category.variants
    }
    expected_preset_content_ids = tuple(
        str(row.preset_id)
        for row in SUPPORTED_AUTHORED_ITEM_VARIANT_ROWS
    )
    expected_preset_refs_by_presentation_key = {
        presentation_key: str(row.preset_id)
        for presentation_key, row in rows_by_presentation_key.items()
    }
    actual_preset_refs_by_presentation_key = {
        presentation_key: preset.ref.preset_id
        for presentation_key, preset in (
            AUTHORED_ITEM_RECIPE_PRESETS_BY_PRESENTATION_KEY.items()
        )
    }

    assert tuple(preset.ref.preset_id for preset in presets) == (
        expected_preset_content_ids
    )
    assert len(preset_ids) == len(set(preset_ids))
    assert len(recipe_digests) == len(set(recipe_digests))
    assert actual_preset_refs_by_presentation_key == (
        expected_preset_refs_by_presentation_key
    )
    assert tuple(AUTHORED_ITEM_RECIPE_PRESETS_BY_PRESET_ID) == (
        expected_preset_content_ids
    )
    assert {
        preset.ref.identity_key
        for preset in AUTHORED_ITEM_RECIPE_PRESETS_BY_PRESENTATION_KEY.values()
    } == set(preset_ids)
    assert {
        preset.ref.identity_key
        for preset in AUTHORED_ITEM_RECIPE_PRESETS_BY_PRESET_ID.values()
    } == set(preset_ids)

    for presentation_key, preset in (
        AUTHORED_ITEM_RECIPE_PRESETS_BY_PRESENTATION_KEY.items()
    ):
        row = rows_by_presentation_key[presentation_key]
        assert preset.ref.pack_id == "content.neurodragon"
        assert preset.ref.preset_id == row.preset_id
        assert preset.recipe.ref.identity_key == (
            row.mechanical_factory_identity
        )
        assert preset.descriptor.display_name == row.display_name
        assert preset.descriptor.presentation.sprite_key == presentation_key[0]
        assert (
            preset.descriptor.presentation.visual_variant_key
            == row.visual_variant_id
        )
        assert preset.descriptor.presentation.tint_rgb == next(
            layer.tint_rgb
            for category in AUTHORED_ITEM_VARIANT_CATEGORIES
            if row in category.variants
            for layer in row.equipment_layers
            if layer.render_layer is category.primary_render_layer
        )


def test_all_rows_use_one_builder_and_one_explicit_pack_export() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    authored_path = (
        repository_root / "dnd" / "items" / "authored_variant_presets.py"
    )
    apparel_path = (
        repository_root / "dnd" / "items" / "apparel_presets.py"
    )

    authored_tree = ast.parse(authored_path.read_text(encoding="utf-8"))
    apparel_tree = ast.parse(apparel_path.read_text(encoding="utf-8"))
    authored_build_calls = [
        node
        for node in ast.walk(authored_tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "ContentRecipePreset"
        and node.func.attr == "create"
    ]
    apparel_build_calls = [
        node
        for node in ast.walk(apparel_tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id in {"ContentRecipe", "ContentRecipePreset"}
        and node.func.attr == "create"
    ]

    assert len(authored_build_calls) == 1
    assert apparel_build_calls == []
    exported = scan_module_content_recipe_presets(authored_preset_module)
    exported_refs = tuple(preset.ref.identity_key for preset in exported)
    expected_exported_refs = tuple(
        preset.ref.identity_key
        for preset in NEURODRAGON_AUTHORED_ITEM_RECIPE_PRESETS
    )
    assert len(exported_refs) == len(set(exported_refs))
    assert set(exported_refs) == set(expected_exported_refs)
    assert scan_module_content_recipe_presets(apparel_preset_module) == ()
    assert all(
        preset.provenance.notes
        == (
            "Presentation-only named recipe; mechanics remain owned by the "
            "exact related item factory."
        )
        for preset in NEURODRAGON_AUTHORED_ITEM_RECIPE_PRESETS
    )


def test_every_supported_recipe_materializes_exact_authored_presentation() -> None:
    for preset in NEURODRAGON_AUTHORED_ITEM_RECIPE_PRESETS:
        item = materialize_item(
            preset.recipe,
            uuid4(),
            origin=ItemRuntimeOrigin.STARTER,
        )
        assert item.content_ref == preset.recipe.ref
        assert item.name == preset.descriptor.display_name
        assert item.visual_variant_id == (
            preset.descriptor.presentation.visual_variant_key
        )


def test_registry_and_catalog_publish_all_and_only_supported_rows() -> None:
    loaded = bootstrap_content_system()
    catalog = build_public_content_catalog(loaded)
    expected_preset_ids = {
        preset.ref.identity_key
        for preset in NEURODRAGON_AUTHORED_ITEM_RECIPE_PRESETS
    }

    assert set(loaded.registry.recipe_presets) == expected_preset_ids
    assert {
        preset.ref.identity_key
        for preset in catalog.presets
    } == expected_preset_ids
    assert {
        preset.presentation.visual_variant_key
        for preset in catalog.presets
    } == {
        row.visual_variant_id
        for row in SUPPORTED_AUTHORED_ITEM_VARIANT_ROWS
    }
    assert all(preset.presentation.tint_rgb is not None for preset in catalog.presets)


def test_tint_rgb_is_a_closed_24_bit_catalog_contract() -> None:
    assert ContentPresentation(tint_rgb=0).tint_rgb == 0
    assert ContentPresentation(tint_rgb=0xFFFFFF).tint_rgb == 0xFFFFFF
    tint_schema = ContentPresentation.model_json_schema()["properties"][
        "tint_rgb"
    ]["anyOf"][0]
    assert tint_schema["minimum"] == 0
    assert tint_schema["maximum"] == 0xFFFFFF

    with pytest.raises(ValidationError, match="greater than or equal to 0"):
        ContentPresentation(tint_rgb=-1)
    with pytest.raises(ValidationError, match="less than or equal to 16777215"):
        ContentPresentation(tint_rgb=0x1000000)


def test_equipment_sprite_rows_are_closed_slot_layer_tint_facts() -> None:
    presentation = ContentPresentation(
        equipment_sprites=(
            EquipmentSpritePresentation(
                equipment_slot=VisualLoadoutSlot.BODY_ARMOR,
                render_layer=EquipmentRenderLayer.LEGS,
                sprite_key="Legs9",
                tint_rgb=0x6B4646,
            ),
            EquipmentSpritePresentation(
                equipment_slot=VisualLoadoutSlot.BODY_ARMOR,
                render_layer=EquipmentRenderLayer.CHEST,
                sprite_key="Chest6",
                tint_rgb=0x5C2A4E,
            ),
        ),
    )

    assert [
        row.render_layer
        for row in presentation.equipment_sprites
    ] == [EquipmentRenderLayer.CHEST, EquipmentRenderLayer.LEGS]
    with pytest.raises(ValidationError, match="slot/layer pairs"):
        ContentPresentation(
            equipment_sprites=(
                presentation.equipment_sprites[0],
                presentation.equipment_sprites[0],
            ),
        )
    with pytest.raises(ValidationError, match="equipment_slot|Extra inputs"):
        EquipmentSpritePresentation.model_validate({
            "slot": "body_armor",
            "render_layer": "chest",
            "sprite_key": "Chest6",
            "tint_rgb": 0x5C2A4E,
        })
    with pytest.raises(ValidationError, match="tint_rgb"):
        EquipmentSpritePresentation.model_validate({
            "equipment_slot": "body_armor",
            "render_layer": "chest",
            "sprite_key": "Chest6",
        })


def test_pit_fighter_costume_preset_carries_exact_compound_actor_layers() -> None:
    """The authenticated preset must not rely on a Chest6 reverse lookup."""
    [category] = [
        row
        for row in AUTHORED_ITEM_VARIANT_CATEGORIES
        if row.base_category == "Costume"
    ]
    [variant] = [
        row
        for row in category.variants
        if row.source_visual_variant_id == "85000004"
    ]
    assert variant.preset_id == "apparel.costume.pit_fighter_wrap"
    assert variant.model_dump(mode="json")["equipment_layers"] == [
        {
            "render_layer": "chest",
            "sprite_key": "Chest6",
            "tint_rgb": 6040078,
        },
        {
            "render_layer": "legs",
            "sprite_key": "Legs9",
            "tint_rgb": 7029286,
        },
    ]

    preset = AUTHORED_ITEM_RECIPE_PRESETS_BY_PRESET_ID[
        "apparel.costume.pit_fighter_wrap"
    ]
    assert [
        row.model_dump(mode="json")
        for row in preset.descriptor.presentation.equipment_sprites
        if row.model_dump(mode="json").get("equipment_slot") == "body_armor"
    ] == [
        {
            "equipment_slot": "body_armor",
            "render_layer": "chest",
            "sprite_key": "Chest6",
            "tint_rgb": 6040078,
        },
        {
            "equipment_slot": "body_armor",
            "render_layer": "legs",
            "sprite_key": "Legs9",
            "tint_rgb": 7029286,
        },
    ]


def test_authored_body_armor_layers_preserve_base_belt_and_variant_tints() -> None:
    """Compound armor rows are fully resolved at import, including inheritance."""
    [category] = [
        row
        for row in AUTHORED_ITEM_VARIANT_CATEGORIES
        if row.base_category == "Traveler's Clothes"
    ]
    [variant] = [
        row
        for row in category.variants
        if row.source_visual_variant_id == "84000001"
    ]

    assert category.base_presentation.model_dump(mode="json")[
        "equipment_layers"
    ] == [
        {
            "render_layer": "belt",
            "sprite_key": "Belt1",
            "tint_rgb": 6040078,
        },
        {
            "render_layer": "chest",
            "sprite_key": "Chest3",
            "tint_rgb": 9127187,
        },
        {
            "render_layer": "legs",
            "sprite_key": "Legs4",
            "tint_rgb": 6042391,
        },
    ]
    assert variant.model_dump(mode="json")["equipment_layers"] == [
        {
            "render_layer": "belt",
            "sprite_key": "Belt1",
            "tint_rgb": 6040078,
        },
        {
            "render_layer": "chest",
            "sprite_key": "Chest3",
            "tint_rgb": 4491332,
        },
        {
            "render_layer": "legs",
            "sprite_key": "Legs4",
            "tint_rgb": 6042391,
        },
    ]
