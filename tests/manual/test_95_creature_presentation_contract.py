"""Creature presentation and equipment visual-contract tests."""

import pytest

from dnd.blocks.base_item import EquippedVisualPolicy
from dnd.core.base_block import BaseBlock
from dnd.core.base_conditions import BaseCondition, SpellProtectionRegistry
from dnd.core.base_object import BaseObject
from dnd.core.events import EventQueue
from dnd.core.gridmap import GridMap, get_map
from dnd.core.modifiers import CreatureType, Size
from dnd.core.values import BaseValue
from dnd.entity import Entity
from dnd.monsters.bestiary import create_goblin, create_skeleton
from dnd.monsters.srd_roster import create_srd_monster, list_srd_monster_specs
from server.api_models import APIEntitySummary, APIEquipmentOverview


VISUAL_SCALE_BY_SIZE = {
    Size.TINY: 0.68,
    Size.SMALL: 0.82,
    Size.MEDIUM: 1.0,
    Size.LARGE: 1.28,
    Size.HUGE: 1.55,
    Size.GARGANTUAN: 2.0,
}
DIRECT_VISUAL_ALIASES = {
    "Sling": "Sling",
    "Hand Crossbow": "Light Crossbow",
    "Thrown Dagger": "Dagger",
    "Thrown Javelin": "Javelin",
    "Morningstar": "Morningstar",
    "Greatclub": "Club",
}
BODY_DRIVEN_ITEMS = {"Natural Armor", "Bite", "Claws", "Slam"}


@pytest.fixture(autouse=True)
def reset_presentation_state() -> None:
    """Clear engine registries before each presentation test."""
    _reset_state()


def _reset_state() -> None:
    """Create an isolated map for monster factories."""
    EventQueue.reset()
    EventQueue.set_combat_log_callback(None)
    SpellProtectionRegistry.reset()
    BaseObject._registry.clear()
    BaseBlock._registry.clear()
    BaseCondition._registry.clear()
    BaseValue._registry.clear()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()
    GridMap.reset()
    get_map().create_rectangle(0, 0, 20, 20)


def test_preset_goblin_and_skeleton_keep_layered_presentation() -> None:
    """Equipment-driven humanoids and existing skeleton art stay layered."""
    goblin = create_goblin(position=(2, 2), faction="monsters")
    skeleton = create_skeleton(position=(4, 2), faction="monsters")

    goblin_api = APIEntitySummary.create(goblin)
    skeleton_api = APIEntitySummary.create(skeleton)

    assert goblin_api.creature_type == CreatureType.HUMANOID.value
    assert goblin_api.size == Size.SMALL.value
    assert goblin_api.appearance.presentation_kind == "layered"
    assert goblin_api.appearance.visual_scale == pytest.approx(0.82)
    assert skeleton_api.creature_type == CreatureType.UNDEAD.value
    assert skeleton_api.appearance.presentation_kind == "layered"
    assert skeleton_api.appearance.body_category == "NakedBody2"


def test_srd_roster_uses_explicit_type_driven_presentation() -> None:
    """SRD factories select presentation from typed creature data, not names."""
    for spec in list_srd_monster_specs():
        _reset_state()
        entity = create_srd_monster(spec.monster_id, position=(2, 2), faction="monsters")
        summary = APIEntitySummary.create(entity)
        expected_kind = "layered" if entity.creature_type == CreatureType.HUMANOID else "placeholder"

        assert summary.creature_type == entity.creature_type.value
        assert summary.size == entity.size.value
        assert summary.appearance.presentation_kind == expected_kind
        assert summary.appearance.visual_scale == pytest.approx(VISUAL_SCALE_BY_SIZE[entity.size])
        if expected_kind == "placeholder":
            assert summary.appearance.placeholder_tint == 0x36FF62


def test_srd_equipment_exposes_a_complete_visual_contract() -> None:
    """Every equipped SRD item is either visibly keyed or explicitly body-driven."""
    observed_aliases: dict[str, str] = {}
    observed_body_items: set[str] = set()

    for spec in list_srd_monster_specs():
        _reset_state()
        entity = create_srd_monster(spec.monster_id, position=(2, 2), faction="monsters")
        overview = APIEquipmentOverview.create(entity)

        for slot in overview.slots:
            item = slot.item
            if item is None:
                continue
            assert item.visual_item_name
            if item.name in DIRECT_VISUAL_ALIASES:
                assert item.equipped_visual_policy == EquippedVisualPolicy.VISIBLE.value
                observed_aliases[item.name] = item.visual_item_name
            if item.name in BODY_DRIVEN_ITEMS:
                assert item.equipped_visual_policy == EquippedVisualPolicy.HIDDEN.value
                observed_body_items.add(item.name)

    assert observed_aliases == DIRECT_VISUAL_ALIASES
    assert observed_body_items == BODY_DRIVEN_ITEMS
