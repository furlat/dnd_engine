"""Exact coverage for the backend-owned authored item visual inventory."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from dnd.core.content.descriptors import (
    ContentPresentation,
    EquipmentSpritePresentation,
)
from dnd.core.equipment_types import EquipmentRenderLayer, VisualLoadoutSlot
from dnd.items.authored_variant_inventory import (
    AUTHORED_ITEM_VARIANT_CATEGORIES,
    AUTHORED_ITEM_VARIANT_LEDGER,
    AUTHORED_ITEM_VARIANT_ROWS,
    SUPPORTED_AUTHORED_ITEM_VARIANT_ROWS,
    primary_authored_item_equipment_layer,
)


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
