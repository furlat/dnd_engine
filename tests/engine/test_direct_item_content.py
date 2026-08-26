"""Direct authored item construction without recipes or content registries."""

from uuid import uuid4

import pytest

from dnd.content.items.authored_item_builders import (
    DIRECT_ACOLYTE_GEAR_BUILDERS,
    build_acolyte_gear,
    build_authored_item,
)
from dnd.content.items.authored_item_definitions import (
    ACOLYTE_GEAR_DEFINITIONS,
    AUTHORED_WEAPON_DEFINITIONS,
    AUTHORED_WEARABLE_DEFINITIONS,
    STATIC_BLOCKER_DEFINITIONS,
)
from dnd.content.items.item_loadouts import ACOLYTE_STARTING_LOADOUT
from dnd.core.base_block import BaseBlock
from dnd.types.items import ItemKind
from dnd.runtime_reset import reset_engine_runtime


def test_acolyte_gear_has_one_cold_definition_and_direct_builder_per_id() -> None:
    assert set(ACOLYTE_GEAR_DEFINITIONS) == set(DIRECT_ACOLYTE_GEAR_BUILDERS)
    assert tuple(entry.item_id for entry in ACOLYTE_STARTING_LOADOUT) == (
        "gear.holy_symbol",
        "gear.prayer_book",
        "gear.incense",
        "gear.vestments",
        "gear.common_clothes",
    )


def test_acolyte_loadout_builds_without_content_refs_or_renderer_fields() -> None:
    owner_uuid = uuid4()
    items = [
        build_acolyte_gear(
            entry.item_id,
            owner_uuid,
            stack_count=entry.quantity,
        )
        for entry in ACOLYTE_STARTING_LOADOUT
    ]
    try:
        assert [item.get_semantic_key() for item in items] == [
            entry.item_id for entry in ACOLYTE_STARTING_LOADOUT
        ]
        assert all(item.content_ref is None for item in items)
        assert all(
            "visual_item_name" not in item.model_dump()
            and "visual_variant_id" not in item.model_dump()
            for item in items
        )
        incense = next(item for item in items if item.semantic_key == "gear.incense")
        assert incense.stack_count == 5
        assert incense.max_stack == 20
    finally:
        for item in items:
            BaseBlock.unregister(item.uuid)


def test_direct_builder_rejects_invalid_authored_stack_quantity() -> None:
    with pytest.raises(ValueError, match="between 1 and 1"):
        build_acolyte_gear("gear.holy_symbol", uuid4(), stack_count=2)


def test_direct_item_state_is_game_data_without_renderer_or_content_fields() -> None:
    item = build_acolyte_gear("gear.incense", uuid4(), stack_count=5)
    try:
        state = item.to_item_state()
        payload = state.model_dump(mode="json")

        assert state.item_kind is ItemKind.ITEM
        assert state.semantic_key == "gear.incense"
        assert state.stack_count == 5
        assert state.max_stack == 20
        assert state.tags == ("acolyte", "incense", "religious")
        assert "content_ref" not in payload
        assert "visual_item_name" not in payload
        assert "visual_variant_id" not in payload
        assert "equipped_visual_policy" not in payload
    finally:
        BaseBlock.unregister(item.uuid)


def test_every_cold_weapon_and_wearable_definition_builds_directly() -> None:
    """The direct definition maps and construction dispatch cannot drift."""
    definition_ids = (
        *AUTHORED_WEAPON_DEFINITIONS,
        *AUTHORED_WEARABLE_DEFINITIONS,
        *STATIC_BLOCKER_DEFINITIONS,
    )
    reset_engine_runtime()
    try:
        built = tuple(
            build_authored_item(item_id, uuid4())
            for item_id in definition_ids
        )
        assert tuple(item.get_semantic_key() for item in built) == definition_ids
        assert all(item.content_ref is None for item in built)
        assert all(
            "visual_item_name" not in item.model_dump()
            and "visual_variant_id" not in item.model_dump()
            for item in built
        )
    finally:
        reset_engine_runtime()


@pytest.mark.parametrize(
    ("item_id", "expected_behavior_ids"),
    (
        (
            "consumable.weapon_coat.concentration_fire",
            ("action.item.weapon_coat.concentration_fire.apply",),
        ),
        (
            "consumable.weapon_coat.timed_fire",
            ("action.item.weapon_coat.timed_fire.apply",),
        ),
        (
            "environment.arcane_device",
            ("action.environment.arcane_device.activate",),
        ),
        ("environment.arcane_machine_gun", ("spell.magic_missile",)),
        (
            "environment.campfire",
            (
                "action.environment.campfire.rest",
                "action.environment.campfire.cook",
            ),
        ),
        (
            "environment.spell_object.heroes_feast",
            ("action.environment.heroes_feast.eat",),
        ),
        ("gear.field_kit", ("action.item.field_kit.deploy",)),
        ("spell_item.scroll_fire_bolt", ("spell.fire_bolt",)),
        ("spell_item.scroll_mage_armor", ("spell.mage_armor",)),
    ),
)
def test_behavior_bearing_items_build_with_direct_semantic_ownership(
    item_id: str,
    expected_behavior_ids: tuple[str, ...],
) -> None:
    reset_engine_runtime()
    user_uuid = uuid4()
    try:
        item = build_authored_item(item_id, user_uuid)
        actions = item.get_use_actions(user_uuid)
        assert item.get_semantic_key() == item_id
        assert item.content_ref is None
        assert tuple(action.behavior_id for action in actions) == (
            expected_behavior_ids
        )
        assert all(action.provided_by_id == item_id for action in actions)
        assert all(action.origin_root_id == item_id for action in actions)
    finally:
        reset_engine_runtime()


@pytest.mark.parametrize(
    "item_id",
    ("weapon.assassin_dagger", "weapon.double_bladed_sword"),
)
def test_remaining_authored_weapons_build_without_presentation_state(
    item_id: str,
) -> None:
    reset_engine_runtime()
    try:
        item = build_authored_item(item_id, uuid4())
        assert item.get_semantic_key() == item_id
        assert item.content_ref is None
        payload = item.model_dump()
        assert "visual_item_name" not in payload
        assert "visual_variant_id" not in payload
    finally:
        reset_engine_runtime()
