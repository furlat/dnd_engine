"""Exact controlled-item and privacy-safe presentation transport contracts."""

from __future__ import annotations

from collections.abc import Iterator
import json
from uuid import uuid4

import pytest
from pydantic import ValidationError

from dnd.blocks.base_item import BaseItem
from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.content_system.item_bindings import (
    ITEM_RUNTIME_BINDINGS,
    ItemRuntimeOrigin,
)
from dnd.content_system.item_materialization import materialize_item
from dnd.core.equipment_types import WeaponSlot
from dnd.entity import Entity, EntityConfig
from dnd.items.authored_variant_presets import (
    NEURODRAGON_AUTHORED_ITEM_RECIPE_PRESETS,
)
from dnd.items.weapons import GREATAXE_RECIPE
from dnd.runtime_reset import reset_engine_runtime
from server.content_catalog import (
    ContentCatalogResponse,
    build_public_content_catalog,
    safe_content_presentation_ref,
)
from server.player_replication.world_projection import (
    _project_floor_object,
    build_entity_visual_loadout,
)
from server.player_replication_contract import (
    SubjectiveFloorObject,
    VisualEquipmentLayer,
    VisualLoadoutSlot,
)
from server.world_projection import project_item_summary


def _dagger_preset():
    return next(
        preset
        for preset in NEURODRAGON_AUTHORED_ITEM_RECIPE_PRESETS
        if preset.recipe.ref.content_id == "weapon.dagger"
    )


@pytest.fixture(autouse=True)
def _reset_runtime() -> Iterator[None]:
    reset_engine_runtime(grid_size=(4, 4))
    yield
    reset_engine_runtime()


def test_controlled_item_summary_carries_exact_definition_and_recipe_identity() -> None:
    """Controlled inventory can join a preset without receiving recipe parameters."""
    preset = _dagger_preset()
    item = materialize_item(
        preset.recipe,
        uuid4(),
        origin=ItemRuntimeOrigin.STARTER,
    )

    summary = project_item_summary(item)

    assert summary.content_ref.model_dump(mode="json") == (
        preset.recipe.ref.model_dump(mode="json")
    )
    assert summary.recipe_ref.recipe_digest == preset.recipe.recipe_digest
    assert summary.recipe_ref.preset_ref is not None
    assert summary.recipe_ref.preset_ref.model_dump(mode="json") == (
        preset.ref.model_dump(mode="json")
    )
    encoded = summary.model_dump(mode="json")
    assert "parameters" not in encoded
    assert encoded["recipe_ref"] == {
        "recipe_digest": preset.recipe.recipe_digest,
        "preset_ref": preset.ref.model_dump(mode="json"),
    }


def test_unbound_item_cannot_enter_the_controlled_item_surface() -> None:
    """A Python class/name is not an acceptable reconstruction identity."""
    item = BaseItem(source_entity_uuid=uuid4(), name="Unbound")

    with pytest.raises(KeyError, match="is not bound"):
        project_item_summary(item)


def test_catalog_deduplicates_and_authenticates_safe_presentations() -> None:
    """Safe rows contain presentation only and participate in catalog integrity."""
    catalog = build_public_content_catalog(bootstrap_content_system())
    refs = [row.ref.presentation_contract_hash for row in catalog.safe_presentations]

    assert refs == sorted(refs)
    assert len(refs) == len(set(refs))
    assert all(
        row.ref == safe_content_presentation_ref(row.presentation)
        for row in catalog.safe_presentations
    )
    assert all(
        set(row.model_dump(mode="json")) == {"ref", "presentation"}
        for row in catalog.safe_presentations
    )

    payload = json.loads(catalog.model_dump_json())
    payload["safe_presentations"][0]["presentation"]["icon_key"] = "tampered"
    with pytest.raises(ValidationError, match="safe presentation|catalog_digest"):
        ContentCatalogResponse.model_validate(payload)


def test_visible_loadout_uses_only_the_safe_catalog_presentation_identity() -> None:
    """Enemy-visible layers never expose definition, recipe, or preset identity."""
    preset = _dagger_preset()
    entity = Entity.create(
        source_entity_uuid=uuid4(),
        name="Visible actor",
        config=EntityConfig(position=(1, 1)),
    )
    item = materialize_item(
        preset.recipe,
        entity.uuid,
        origin=ItemRuntimeOrigin.STARTER,
    )
    assert entity.loot_item(item)
    assert entity.equip_item(item.uuid, WeaponSlot.MELEE_MAIN)

    loadout = build_entity_visual_loadout(entity)

    layer = next(
        row
        for row in loadout.layers
        if row.slot is VisualLoadoutSlot.WEAPON_MELEE_MAIN
    )
    assert layer.safe_presentation_ref == (
        safe_content_presentation_ref(preset.descriptor.presentation)
    )
    assert "content_ref" not in VisualEquipmentLayer.model_fields
    assert "recipe_ref" not in VisualEquipmentLayer.model_fields
    assert "preset_ref" not in VisualEquipmentLayer.model_fields


def test_base_equipment_safe_presentation_is_renderer_complete() -> None:
    """A non-preset starter weapon must render through its authenticated row."""
    entity = Entity.create(
        source_entity_uuid=uuid4(),
        name="Base weapon actor",
        config=EntityConfig(position=(1, 1)),
    )
    item = materialize_item(
        GREATAXE_RECIPE,
        entity.uuid,
        origin=ItemRuntimeOrigin.STARTER,
    )
    assert ITEM_RUNTIME_BINDINGS.require(item.uuid).recipe_preset_ref is None
    assert entity.loot_item(item)
    assert entity.equip_item(item.uuid, WeaponSlot.MELEE_MAIN)

    layer = next(
        row
        for row in build_entity_visual_loadout(entity).layers
        if row.slot is VisualLoadoutSlot.WEAPON_MELEE_MAIN
    )
    catalog = build_public_content_catalog(bootstrap_content_system())
    [safe_row] = [
        row
        for row in catalog.safe_presentations
        if row.ref == layer.safe_presentation_ref
    ]

    assert safe_row.presentation.sprite_key == "Melee14"
    assert safe_row.presentation.tint_rgb == 0x8899AA
    assert [
        row.model_dump(mode="json")
        for row in safe_row.presentation.equipment_sprites
        if row.equipment_slot is VisualLoadoutSlot.WEAPON_MELEE_MAIN
    ] == [
        {
            "equipment_slot": "weapon_melee_main",
            "render_layer": "weapon",
            "sprite_key": "Melee14",
            "tint_rgb": 0x8899AA,
        },
    ]


def test_bound_floor_item_uses_only_its_safe_catalog_presentation_identity() -> None:
    """A visible floor instance authenticates visuals without exposing mechanics."""
    preset = _dagger_preset()
    observer_uuid = uuid4()
    item = materialize_item(
        preset.recipe,
        observer_uuid,
        origin=ItemRuntimeOrigin.STARTER,
    )

    projected = _project_floor_object(
        item.uuid,
        (1, 2),
        requesting_entity_uuid=observer_uuid,
    )

    assert projected is not None
    assert projected.safe_presentation_ref == (
        safe_content_presentation_ref(preset.descriptor.presentation)
    )
    catalog = build_public_content_catalog(bootstrap_content_system())
    assert [
        row.presentation
        for row in catalog.safe_presentations
        if row.ref == projected.safe_presentation_ref
    ] == [preset.descriptor.presentation]
    assert "content_ref" not in SubjectiveFloorObject.model_fields
    assert "recipe_ref" not in SubjectiveFloorObject.model_fields
    assert "preset_ref" not in SubjectiveFloorObject.model_fields


def test_unbound_floor_object_cannot_fall_back_to_name_or_python_class() -> None:
    """The subjective surface refuses objects outside the content registry."""
    observer_uuid = uuid4()
    item = BaseItem(
        source_entity_uuid=observer_uuid,
        name="Unbound floor object",
        visual_item_name="PlausibleButUnauthenticated",
    )

    with pytest.raises(KeyError, match="is not bound"):
        _project_floor_object(
            item.uuid,
            (1, 2),
            requesting_entity_uuid=observer_uuid,
        )
