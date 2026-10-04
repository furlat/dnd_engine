"""Continual Flame follows one real item through ordinary item commands."""
import pytest
from uuid import uuid4

from dnd.actions import SpellEvent
from dnd.actions_functional import execute_action
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.core.base_actions import TargetType
from dnd.core.base_conditions import ConditionApplicationEvent
from dnd.core.events import EventPhase, EventQueue
from dnd.core.base_block import BaseBlock
from dnd.core.equipment_types import WeaponSlot
from dnd.core.gridmap import get_map
from dnd.spells.evocation import ContinualFlame
from dnd.types.world import LightLevel
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from tests.engine.test_roster_support_spells import actor, cast


@pytest.fixture
def game():
    grid = reset_engine_runtime()
    grid.create_rectangle(0, 0, 14, 3, default_light=LightLevel.DARKNESS)
    result = Game()
    yield result
    result.close()
    reset_engine_runtime()


def level(position):
    tile = get_map().get_tile(*position)
    assert tile is not None
    return tile.resolved_light_level


@pytest.mark.parametrize("location", ["inventory", "equipment", "floor"])
def test_continual_flame_selects_existing_item_and_publishes_heatless_membership(game, location):
    caster = actor(game)
    item = build_authored_item("weapon.club", caster.uuid)
    if location == "floor":
        item.place_on_grid((3, 2))
    else:
        assert caster.loot_item(item)
        if location == "equipment":
            assert caster.equip_item(item.uuid, WeaponSlot.MELEE_MAIN)
    result = cast(ContinualFlame, caster, item)
    assert result.target_entity_uuid == item.uuid
    assert BaseBlock.get(item.uuid) is item
    effect, = item.to_item_presentation_state().item_effects
    assert effect.damage_type is None and effect.contribution_uuid is None
    assert effect.applied_source_event_cursor is not None
    assert item.is_exposed_flame() is False
    assert item.douse_exposed_flame() is False
    assert level(item.get_position()) is (LightLevel.DARKNESS if location == "inventory" else LightLevel.BRIGHT_LIGHT)
    assert isinstance(result, SpellEvent) and result.target_type is TargetType.OBJECT
    completions = [event for _, event in EventQueue.iter_events_since(0)
        if isinstance(event, ConditionApplicationEvent) and event.phase is EventPhase.COMPLETION
        and event.target_entity_uuid == item.uuid]
    recorded = completions[-1].resulting_item
    assert recorded is not None and recorded.item_uuid == item.uuid
    captured_effect, = recorded.item_effects
    assert captured_effect.effect_uuid == effect.effect_uuid
    assert captured_effect.behavior_id == effect.behavior_id
    assert captured_effect.damage_type is None and captured_effect.contribution_uuid is None
    assert not get_map().get_spatial_conditions()
    if location == "floor":
        assert level((7, 2)) is LightLevel.BRIGHT_LIGHT
        assert level((8, 2)) is LightLevel.DIM_LIGHT
        assert level((11, 2)) is LightLevel.DIM_LIGHT
        assert level((12, 2)) is LightLevel.DARKNESS


def test_continual_flame_cover_carry_drop_loot_and_destruction_keep_one_item(game):
    caster = actor(game)
    looter = actor(game, "Looter", (4, 2))
    item = build_authored_item("weapon.club", caster.uuid)
    assert caster.loot_item(item)
    cast(ContinualFlame, caster, item)
    condition = item.active_conditions["Continual Flame"]
    assert caster.equip_item(item.uuid, WeaponSlot.MELEE_MAIN)
    assert level(caster.position) is LightLevel.BRIGHT_LIGHT
    caster.move((12, 2))
    assert level((2, 2)) is LightLevel.DARKNESS
    assert level(caster.position) is LightLevel.BRIGHT_LIGHT
    assert caster.unequip_item(WeaponSlot.MELEE_MAIN) is item
    assert level(caster.position) is LightLevel.DARKNESS
    assert item.active_conditions["Continual Flame"] is condition
    caster.move((3, 2))
    assert caster.drop_item(item.uuid, (4, 2)) is item
    assert level((4, 2)) is LightLevel.BRIGHT_LIGHT
    assert looter.loot_item(item)
    assert level((4, 2)) is LightLevel.DARKNESS
    assert looter.equip_item(item.uuid, WeaponSlot.MELEE_MAIN)
    assert level(looter.position) is LightLevel.BRIGHT_LIGHT
    assert item.uuid not in caster.inventory.items
    assert item.active_conditions["Continual Flame"] is condition
    item.destroy()
    assert not condition.applied
    assert level(looter.position) is LightLevel.DARKNESS


def test_continual_flame_rejects_unreachable_floor_item_before_payment(game):
    caster = actor(game)
    item = build_authored_item("weapon.club", caster.uuid)
    item.place_on_grid((8, 2))
    result = ContinualFlame(source_entity_uuid=caster.uuid, target_entity_uuid=item.uuid, alt_skip_slot=True).apply()
    assert result is not None and result.canceled
    assert caster.action_economy.actions.normalized_score == 1
    assert not item.to_item_presentation_state().item_effects


def test_continual_flame_discovery_includes_own_gear_without_exposing_another_inventory(game):
    get_map().add_light_source((2, 2), 40, 0)
    caster = actor(game)
    other = actor(game, "Other", (3, 2))
    own = build_authored_item("weapon.club", caster.uuid)
    hidden = build_authored_item("weapon.club", other.uuid)
    floor = build_authored_item("weapon.club", caster.uuid)
    assert caster.loot_item(own)
    assert other.loot_item(hidden)
    floor.place_on_grid((3, 2))
    caster.register_action(ContinualFlame(source_entity_uuid=caster.uuid, template=True, alt_skip_slot=True))
    actions = [info for info in caster.get_available_actions().all_actions if info.display_name == "Continual Flame"]
    action, = actions
    identities = {target.target_uuid for target in action.valid_targets}
    assert own.uuid in identities and floor.uuid in identities and hidden.uuid not in identities
    selected = next(target for target in action.valid_targets if target.target_uuid == own.uuid)
    result = execute_action(caster, action.template_name, selected)
    assert result is not None and not result.canceled
    assert own.to_item_presentation_state().item_effects


def test_continual_flame_suppression_resumes_same_retained_light(game):
    caster = actor(game)
    item = build_authored_item("weapon.club", caster.uuid)
    item.place_on_grid((3, 2))
    cast(ContinualFlame, caster, item)
    condition = item.active_conditions["Continual Flame"]
    light, = item.get_attached_light_sources()
    provider = uuid4()
    condition.set_suppression(provider, True)
    get_map().refresh_contribution_lights()
    assert level((3, 2)) is LightLevel.DARKNESS
    assert item.get_attached_light_sources() == {light}
    assert item.to_item_presentation_state().item_effects[0].suppression_provider_uuids == (provider,)
    condition.set_suppression(provider, False)
    get_map().refresh_contribution_lights()
    assert level((3, 2)) is LightLevel.BRIGHT_LIGHT
    assert item.get_attached_light_sources() == {light}

