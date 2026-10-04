"""Approved weather/solar rules through native casts, movement and clocks."""
from uuid import uuid4
from typing import TypeVar

import pytest

from dnd.actions import SpellEvent
from dnd.conditions import Blinded, Concentrating, Prone
from dnd.core.creature_types import CreatureType, DamageType
from dnd.core.effect_types import EffectOrigin
from dnd.core.modifiers import AdvantageStatus, ResistanceModifier, ResistanceStatus
from dnd.spatial.area_conditions import SpatialCondition
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import (
    DamageAppliedEvent, Event, EventPhase, EventQueue, EventType, RoundEndEvent, SavingThrowEvent,
)
from dnd.content.items.environment_item_builders import build_standing_torch
from dnd.core.base_block import LightLevel
from dnd.core.gridmap import get_map
from dnd.entity import Entity
from dnd.encounter import Encounter
from dnd.items.environment import DirectionalWall
from dnd.monsters.traits import register_sunlight_sensitivity
from dnd.types.world import CardinalDirection, WorldEdgeChannel
from dnd.runtime_reset import reset_engine_runtime
from dnd.spells.conjuration import DarknessZone, FogCloudZone, SleetStorm
from dnd.spells.abjuration import register_counterspell_reaction
from dnd.spells.evocation import IceStorm, Sunbeam, SunbeamEffect, Sunburst
from tests.manual.spell_regression_support import (
    create_spell_regression_actor, force_save_result, reset_spell_regression_arena,
)


@pytest.fixture
def scene():
    reset_spell_regression_arena(35, 12)
    caster = create_spell_regression_actor("Caster", (2, 5), "heroes",
        spell_slots={3: 3, 4: 2, 5: 1, 6: 2, 8: 2})
    target = create_spell_regression_actor("Recipient", (14, 5), "enemies")
    force_save_result(target, "dexterity", succeeds=False)
    force_save_result(target, "constitution", succeeds=False)
    Entity.update_all_entities_senses(max_distance=300)
    yield caster, target
    reset_engine_runtime()


def cast(spell_type, caster, destination, **values):
    with fixed_dice_faces(*([2] * 200)):
        result = spell_type(source_entity_uuid=caster.uuid, end_position=destination, **values).apply()
    assert isinstance(result, SpellEvent)
    return result


_Event = TypeVar("_Event", bound=Event)


def completed(cursor: int, event_type: type[_Event]) -> list[_Event]:
    return [event for _, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, event_type) and event.phase is EventPhase.COMPLETION]


def zone_named(name):
    return next(zone for zone in get_map().get_spatial_conditions()
                if isinstance(zone, SpatialCondition) and zone.name == name)


def boundary(event_type):
    assert event_type is EventType.ROUND_END
    return Encounter(source_entity_uuid=uuid4())._fire_round_end()


@pytest.mark.parametrize("slot, damage", [(4, 12), (5, 14)])
def test_ice_storm_range_mixed_damage_and_next_source_turn_end(scene, slot, damage):
    caster, target = scene
    Entity.update_entity_position(target, (20, 5))
    Entity.update_all_entities_senses(max_distance=300)
    before = target.get_normal_hp()
    result = cast(IceStorm, caster, target.position, cast_at_level=slot)
    assert not result.canceled and before - target.get_normal_hp() == damage
    terrain = zone_named("Ice Storm Terrain")
    target.on_turn_end()
    caster.on_turn_end()
    assert terrain.applied
    caster.on_turn_start()
    assert terrain.applied
    caster.on_turn_end()
    assert not terrain.applied


def test_ice_storm_empty_area_and_source_absence_fallback(scene):
    caster, _ = scene
    result = cast(IceStorm, caster, (28, 5))
    assert not result.canceled
    terrain = zone_named("Ice Storm Terrain")
    caster._detach_from_world()
    assert terrain.applied
    boundary(EventType.ROUND_END)
    assert not terrain.applied


def test_sleet_affects_allies_and_prone_creatures_and_ends_after_ten_rounds(scene):
    caster, target = scene
    target.faction = caster.faction
    target.add_condition(Prone(source_entity_uuid=target.uuid, target_entity_uuid=target.uuid))
    assert not cast(SleetStorm, caster, target.position).canceled
    storm = zone_named("Sleet Storm Zone")
    cursor = EventQueue.event_cursor()
    with fixed_dice_faces(*([2] * 100)):
        target.on_turn_start()
    saves = completed(cursor, SavingThrowEvent)
    assert len(saves) == 1 and saves[0].ability_name == "dexterity"
    assert saves[0].source_entity_uuid == caster.uuid
    assert not completed(cursor, DamageAppliedEvent)
    assert storm.duration.duration == 10
    for _ in range(9):
        storm.progress_spatial_duration()
    assert storm.applied
    storm.progress_spatial_duration()
    assert not storm.applied


def test_sleet_disrupts_concentration_against_spell_dc_even_when_already_prone(scene):
    caster, target = scene
    target.add_condition(Prone(source_entity_uuid=target.uuid, target_entity_uuid=target.uuid))
    target.add_condition(Concentrating(source_entity_uuid=target.uuid, target_entity_uuid=target.uuid))
    assert not cast(SleetStorm, caster, target.position).canceled
    cursor = EventQueue.event_cursor()
    with fixed_dice_faces(*([2] * 100)):
        target.on_turn_start()
    saves = completed(cursor, SavingThrowEvent)
    assert [event.ability_name for event in saves] == ["dexterity", "constitution"]
    assert all(event.get_dc() == caster.spell_save_dc() for event in saves)
    assert "Concentrating" not in target.active_conditions


def test_sunbeam_initial_is_one_cast_with_paid_repeat_and_next_caster_blind_expiry(scene):
    caster, target = scene
    Entity.update_entity_position(target, (10, 5))
    Entity.update_all_entities_senses(max_distance=300)
    before = target.get_normal_hp()
    cursor = EventQueue.event_cursor()
    initial = cast(Sunbeam, caster, (14, 5))
    assert not initial.canceled and before - target.get_normal_hp() == 12
    assert "Blinded" in target.active_conditions
    spells = completed(cursor, SpellEvent)
    assert all(event.event_type is EventType.CAST_SPELL for event in spells)
    assert all(event.lineage_uuid == initial.lineage_uuid or event.parent_lineage == initial.lineage_uuid
               for event in spells)
    assert caster.action_economy.actions.normalized_score == 0
    assert caster.action_economy.spell_slot_6.normalized_score == 1
    repeat = caster.get_action_template("Sunbeam Strike")
    assert repeat is not None
    target.on_turn_start()
    assert "Blinded" in target.active_conditions
    caster.on_turn_start()
    assert "Blinded" not in target.active_conditions
    with fixed_dice_faces(*([2] * 200)):
        activated = repeat.instantiate(end_position=(14, 5)).apply()
    assert isinstance(activated, SpellEvent) and not activated.canceled
    assert activated.event_type is EventType.BASE_ACTION
    assert activated.lineage_uuid != initial.lineage_uuid
    assert activated.get_effect_origin() == initial.get_effect_origin()
    assert caster.action_economy.actions.normalized_score == 0
    assert caster.action_economy.spell_slot_6.normalized_score == 1
    caster.remove_condition("Concentrating")
    assert caster.get_action_template("Sunbeam Strike") is None


def test_sunbeam_light_moves_and_ends_with_exact_owner(scene):
    caster, _ = scene
    assert not cast(Sunbeam, caster, (2, 10)).canceled
    assert get_map().is_sunlit((2, 5)) and get_map().is_sunlit((13, 5))
    assert not get_map().is_sunlit((16, 5))
    Entity.update_entity_position(caster, (8, 5))
    assert get_map().is_sunlit((19, 5))
    for _ in range(10):
        caster.on_turn_start()
    assert caster.get_action_template("Sunbeam Strike") is None
    assert not get_map().is_sunlit((8, 5))


@pytest.mark.parametrize("creature_type", [CreatureType.UNDEAD, CreatureType.OOZE])
def test_sunbeam_disadvantages_undead_and_oozes(scene, creature_type):
    caster, target = scene
    target.creature_type = creature_type
    Entity.update_entity_position(target, (10, 5))
    Entity.update_all_entities_senses(max_distance=300)
    cursor = EventQueue.event_cursor()
    assert not cast(Sunbeam, caster, (14, 5)).canceled
    saves = completed(cursor, SavingThrowEvent)
    assert len(saves) == 1 and saves[0].dice_roll is not None
    assert saves[0].dice_roll.advantage_status is AdvantageStatus.DISADVANTAGE


def test_sunburst_blindness_retains_prior_blindness_and_source_independent_lifetime(scene):
    caster, target = scene
    original = Blinded(source_entity_uuid=target.uuid, target_entity_uuid=target.uuid)
    target.add_condition(original)
    assert not cast(Sunburst, caster, target.position).canceled
    caster._detach_from_world()
    with fixed_dice_faces(*([2] * 100)):
        target.on_turn_end()
    assert "Sunburst Blindness" in target.active_conditions
    for _ in range(10):
        target.on_turn_start()
    assert "Sunburst Blindness" not in target.active_conditions
    assert target.active_conditions["Blinded"].uuid == original.uuid


def test_empty_sunburst_dispels_spell_darkness_without_removing_other_areas(scene):
    caster, target = scene
    Entity.update_entity_position(target, (32, 5))
    darkness = DarknessZone(source_entity_uuid=caster.uuid, position=(20, 5),
        effect_origin=EffectOrigin.spell(source_id="darkness", source_event_lineage_uuid=str(uuid4()),
            source_position=caster.position, base_spell_level=2, effective_spell_level=2))
    parent = Event(source_entity_uuid=caster.uuid, event_type=EventType.CAST_SPELL)
    darkness.activate(parent_event=parent)
    fog = FogCloudZone(source_entity_uuid=caster.uuid, position=(20, 5))
    fog.activate(parent_event=parent)
    Entity.update_all_entities_senses(max_distance=300)
    result = cast(Sunburst, caster, (15, 5))
    assert not result.canceled
    assert not darkness.applied
    assert fog.applied


def test_round_boundary_publishes_once_and_ticks_world_duration_once(scene):
    caster, target = scene
    assert not cast(SleetStorm, caster, target.position).canceled
    storm = zone_named("Sleet Storm Zone")
    encounter = Encounter(source_entity_uuid=caster.uuid)
    cursor = EventQueue.event_cursor()
    encounter._advance_round()
    boundaries = completed(cursor, RoundEndEvent)
    assert len(boundaries) == 1
    phases = [event.phase for _, event in EventQueue.iter_events_since(cursor)
              if isinstance(event, RoundEndEvent)]
    assert phases == [EventPhase.DECLARATION, EventPhase.EXECUTION, EventPhase.EFFECT, EventPhase.COMPLETION]
    assert storm.duration.duration == 9 and encounter.round_number == 1


def test_sleet_entry_fence_does_not_skip_turn_start_and_douses_flames(scene):
    caster, target = scene
    torch = build_standing_torch()
    torch.place_on_grid((14, 6))
    assert torch.light() is not None and torch.is_lit
    Entity.update_entity_position(target, (25, 5))
    Entity.update_all_entities_senses(max_distance=300)
    assert not cast(SleetStorm, caster, (14, 5)).canceled
    assert not torch.is_lit
    cursor = EventQueue.event_cursor()
    turn = EventQueue.begin_turn_execution()
    try:
        with fixed_dice_faces(*([2] * 100)):
            Entity.update_entity_position(target, (14, 5))
            Entity.update_entity_position(target, (25, 5))
            Entity.update_entity_position(target, (14, 5))
            target.on_turn_start()
    finally:
        EventQueue.end_turn_execution(turn)
    saves = completed(cursor, SavingThrowEvent)
    assert len(saves) == 2 and all(save.ability_name == "dexterity" for save in saves)
    storm = zone_named("Sleet Storm Zone")
    caster.remove_condition("Concentrating")
    assert not storm.applied


def test_sunbeam_blindness_survives_concentration_loss_until_missing_source_round(scene):
    caster, target = scene
    Entity.update_entity_position(target, (10, 5))
    Entity.update_all_entities_senses(max_distance=300)
    assert not cast(Sunbeam, caster, (14, 5)).canceled
    caster.remove_condition("Concentrating")
    assert "Blinded" in target.active_conditions
    caster._detach_from_world()
    target.on_turn_start()
    assert "Blinded" in target.active_conditions
    boundary(EventType.ROUND_END)
    assert "Sunbeam Blindness" not in target.active_conditions
    assert "Blinded" not in target.active_conditions


def test_sunlight_contribution_gate_retains_identity_and_authored_toggle(scene):
    caster, _ = scene
    grid = get_map()
    grid.set_tile_base_light(caster.position, LightLevel.DARKNESS)
    assert not cast(Sunbeam, caster, (2, 10)).canceled
    owner = caster.active_conditions["Sunbeam"]
    assert isinstance(owner, SunbeamEffect) and owner.light_source_uuid is not None
    identity = owner.light_source_uuid
    tile = grid.get_tile(*caster.position)
    assert tile is not None and tile.resolved_light_level is LightLevel.BRIGHT_LIGHT
    first, second = uuid4(), uuid4()
    owner.set_suppression(first, True)
    owner.set_suppression(second, True)
    grid.refresh_contribution_lights()
    assert not grid.is_sunlit(caster.position) and tile.resolved_light_level is LightLevel.DARKNESS
    assert grid.get_light_source_position(identity) == caster.position
    owner.set_suppression(first, False)
    grid.refresh_contribution_lights()
    assert not grid.is_sunlit(caster.position)
    owner.set_suppression(second, False)
    grid.refresh_contribution_lights()
    assert grid.is_sunlit(caster.position) and owner.light_source_uuid == identity
    grid.toggle_light_source(identity, False)
    owner.set_suppression(first, True)
    grid.refresh_contribution_lights()
    owner.set_suppression(first, False)
    grid.refresh_contribution_lights()
    assert not grid.is_sunlit(caster.position)
    grid.toggle_light_source(identity, True)
    assert grid.is_sunlit(caster.position)
    SunbeamEffect.unregister(owner.uuid)
    grid.refresh_contribution_lights()
    assert not grid.is_sunlit(caster.position) and tile.resolved_light_level is LightLevel.DARKNESS


def test_sunlight_uses_occlusion_and_existing_sensitivity_consumers(scene):
    caster, target = scene
    Entity.update_entity_position(target, (4, 5))
    register_sunlight_sensitivity(target)
    assert not cast(Sunbeam, caster, (2, 10)).canceled
    assert target.attack_bonus().advantage is AdvantageStatus.DISADVANTAGE
    assert target.skill_bonus(None, "perception").advantage is AdvantageStatus.DISADVANTAGE
    wall = DirectionalWall(source_entity_uuid=caster.uuid, item_id="test.sunlight_wall",
        blocked_channels=(WorldEdgeChannel.OPTICAL,))
    wall.place_on_grid((3, 5), boundary_direction=CardinalDirection.EAST)
    assert not get_map().is_sunlit(target.position)
    assert target.attack_bonus().advantage is not AdvantageStatus.DISADVANTAGE
    assert target.skill_bonus(None, "perception").advantage is not AdvantageStatus.DISADVANTAGE


def test_sunburst_success_halves_damage_and_repeat_save_survives_source_absence(scene):
    caster, target = scene
    before = target.get_normal_hp()
    assert not cast(Sunburst, caster, target.position).canceled
    assert before - target.get_normal_hp() == 24
    target.saving_throws.get_saving_throw("constitution").bonus.self_static.remove_all_modifiers()
    force_save_result(target, "constitution", succeeds=True)
    caster._detach_from_world()
    with fixed_dice_faces(*([2] * 100)):
        target.on_turn_end()
    assert "Sunburst Blindness" not in target.active_conditions and "Blinded" not in target.active_conditions


@pytest.mark.parametrize("spell, destination, damage", [(Sunbeam, (14, 5), 6), (Sunburst, (14, 5), 12)])
def test_solar_success_halves_damage_without_blindness(scene, spell, destination, damage):
    caster, target = scene
    Entity.update_entity_position(target, (10, 5))
    Entity.update_all_entities_senses(max_distance=300)
    target.saving_throws.get_saving_throw("constitution").bonus.self_static.remove_all_modifiers()
    force_save_result(target, "constitution", succeeds=True)
    before = target.get_normal_hp()
    assert not cast(spell, caster, destination).canceled
    assert before - target.get_normal_hp() == damage and "Blinded" not in target.active_conditions


def test_ice_storm_mixed_resistance_and_source_death_preserve_terrain_until_round(scene):
    caster, target = scene
    target.health.damage_reduction.self_static.add_resistance_modifier(ResistanceModifier(
        source_entity_uuid=target.uuid, target_entity_uuid=target.uuid, name="Cold immunity",
        value=ResistanceStatus.IMMUNITY, damage_type=DamageType.COLD))
    before = target.get_normal_hp()
    assert not cast(IceStorm, caster, target.position).canceled
    assert before - target.get_normal_hp() == 4
    terrain = zone_named("Ice Storm Terrain")
    caster.receive_instant_death(target.uuid)
    assert terrain.applied
    boundary(EventType.ROUND_END)
    assert not terrain.applied


@pytest.mark.parametrize("repeat", [False, True])
def test_counterspell_intercepts_sunbeam_cast_but_not_retained_activation(scene, repeat):
    caster, target = scene
    if repeat:
        assert not cast(Sunbeam, caster, (14, 5)).canceled
        caster.on_turn_start()
    abjurer = create_spell_regression_actor("Abjurer", (6, 6), "enemies", spell_slots={6: 1})
    register_counterspell_reaction(abjurer)
    Entity.update_all_entities_senses(max_distance=300)
    before = target.get_normal_hp()
    if repeat:
        template = caster.get_action_template("Sunbeam Strike")
        assert template is not None
        with fixed_dice_faces(*([2] * 100)):
            result = template.instantiate(end_position=(14, 5)).apply()
        assert result is not None and not result.canceled
        assert target.get_normal_hp() == before - 12
        assert abjurer.action_economy.spell_slot_6.normalized_score == 1
    else:
        result = cast(Sunbeam, caster, (14, 5))
        assert result.canceled and target.get_normal_hp() == before
        assert "Sunbeam" not in caster.active_conditions
        assert not get_map().is_sunlit(caster.position)
        assert caster.get_action_template("Sunbeam Strike") is None
        assert abjurer.action_economy.spell_slot_6.normalized_score == 0
