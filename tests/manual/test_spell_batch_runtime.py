"""Selected spell delivery retains native geometry, pushes and observed lifetime."""

import pytest

from dnd.actions import SpellEvent
from dnd.actions_functional import execute_available_action, get_available_actions, register_spell
from dnd.blocks.sensory import capture_senses_snapshot
from dnd.core.base_object import PASSIVE_EVENT_REPLAY
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import EventPhase, EventQueue, ForcedMovementEvent, SensoryUpdateEvent
from dnd.core.gridmap import get_map
from dnd.core.presentation_geometry import LinePresentationGeometry
from dnd.controller import HumanController
from dnd.encounter import Encounter
from dnd.entity import Entity
from dnd.runtime_reset import reset_engine_runtime
from dnd.spells.conjuration import PoisonSpray, Web
from dnd.spells.evocation import (
    BurningHands, GustOfWind, GustOfWindZone, SacredFlame, ShockingGrasp, Thunderwave,
)
from dnd.types.senses import reduce_senses_snapshot
from tests.manual.test_131_inventory_use_actions_legacy_contract import (
    create_caster, create_target, force_save, reset_item_arena,
)


@pytest.mark.parametrize("spell_type, identity", (
    (SacredFlame, "spell.sacred_flame"), (ShockingGrasp, "spell.shocking_grasp"),
    (PoisonSpray, "spell.poison_spray"), (BurningHands, "spell.burning_hands"),
    (Thunderwave, "spell.thunderwave"), (GustOfWind, "spell.gust_of_wind"), (Web, "spell.web"),
))
def test_selected_spells_are_discoverable_through_the_initialized_catalog(spell_type, identity) -> None:
    reset_item_arena()
    caster = create_caster((4, 5))
    create_target((5, 5))
    register_spell(caster, spell_type)
    Entity.update_all_entities_senses()
    rows = [row for row in get_available_actions(caster).all_actions if row.behavior_id == identity]
    assert rows and any(row.valid_targets for row in rows)


@pytest.mark.parametrize("spell_type, ability, steps", (
    (Thunderwave, "constitution", 2), (GustOfWind, "strength", 3),
))
@pytest.mark.parametrize("diagonal", (False, True))
@pytest.mark.parametrize("blocked", (False, True))
def test_push_distance_reports_admitted_steps_and_preserves_blocked_endpoint(spell_type, ability, steps,
                                                                           diagonal, blocked) -> None:
    reset_item_arena(30, 30)
    caster = create_caster((5, 5))
    start = (6, 6 if diagonal else 5)
    direction = (1, int(diagonal))
    target = create_target(start)
    force_save(target, ability, succeeds=False)
    if blocked:
        obstacle = (start[0] + steps * direction[0], start[1] + steps * direction[1])
        get_map().set_tile(*obstacle, walking_cost=0, blocks_propagation=True,
                           blocks_optics=True, name="Push blocker")
    Entity.update_all_entities_senses(max_distance=150)
    with fixed_dice_faces(*([4] * 20)):
        result = spell_type(source_entity_uuid=caster.uuid,
                            end_position=(15, 15 if diagonal else 5)).apply()
    assert isinstance(result, SpellEvent) and not result.canceled
    pushes = [event for _, event in EventQueue.iter_events_since(0)
              if isinstance(event, ForcedMovementEvent) and event.phase is EventPhase.COMPLETION]
    assert len(pushes) == 1
    actual_steps = steps - int(blocked)
    expected = (start[0] + direction[0] * actual_steps, start[1] + direction[1] * actual_steps)
    assert target.position == expected and pushes[0].end_position == expected
    assert pushes[0].actual_distance == actual_steps * 5
    assert pushes[0].intended_distance == steps * 5 and pushes[0].blocked_by_obstacle is blocked


@pytest.mark.parametrize("spell_type, ability", (
    (BurningHands, "dexterity"), (Thunderwave, "constitution"), (GustOfWind, "strength"),
))
def test_area_result_records_the_footprint_that_selected_its_actual_recipients(spell_type, ability) -> None:
    reset_item_arena(30, 20)
    caster = create_caster((5, 10))
    target = create_target((6, 10))
    blocked = create_target((9, 10))
    force_save(target, ability, succeeds=True)
    get_map().set_tile(7, 10, walking_cost=0, blocks_propagation=True,
                       blocks_optics=True, name="Area blocker")
    Entity.update_all_entities_senses(max_distance=150)
    with fixed_dice_faces(*([4] * 20)):
        result = spell_type(source_entity_uuid=caster.uuid, end_position=(15, 10)).apply()
    assert isinstance(result, SpellEvent) and not result.canceled
    assert result.resolved_area_positions is not None
    assert target.position in result.resolved_area_positions
    assert blocked.position not in result.resolved_area_positions
    applications = [event for _, event in EventQueue.iter_events_since(0)
                    if isinstance(event, SpellEvent) and event.phase is EventPhase.COMPLETION
                    and event.parent_lineage == result.lineage_uuid]
    assert {event.target_entity_uuid for event in applications} == {target.uuid}
    if spell_type is GustOfWind:
        zone = next(zone for zone in get_map().get_spatial_conditions() if isinstance(zone, GustOfWindZone))
        assert set(result.resolved_area_positions) == zone.affected_positions


def test_oblique_gust_initial_and_persistent_footprints_share_the_selected_direction() -> None:
    reset_item_arena(30, 30)
    caster = create_caster((5, 5))
    target = create_target((14, 9))
    force_save(target, "strength", succeeds=True)
    Entity.update_all_entities_senses(max_distance=150)
    with fixed_dice_faces(4):
        result = GustOfWind(source_entity_uuid=caster.uuid, end_position=(15, 9)).apply()
    assert isinstance(result, SpellEvent) and not result.canceled and result.total_targets == 1
    zone = next(zone for zone in get_map().get_spatial_conditions() if isinstance(zone, GustOfWindZone))
    assert zone.zone_direction == (10, 4)
    assert target.position in zone.affected_positions
    assert set(result.resolved_area_positions or ()) == zone.affected_positions
    observation = caster.senses.spatial_effects[zone.uuid]
    assert observation.area_geometry == result.area_geometry


def test_persistent_gust_keeps_its_caster_at_origin_through_a_real_turn_cycle() -> None:
    reset_item_arena(15, 15)
    caster = create_caster((3, 5))
    target = create_target((4, 5))
    register_spell(caster, GustOfWind)
    Entity.update_all_entities_senses()
    encounter = Encounter(name="Persistent wind", source_entity_uuid=caster.uuid)
    for actor in (caster, target):
        encounter.add_combatant(actor, HumanController(source_entity_uuid=actor.uuid))
    with fixed_dice_faces(20, 10):
        encounter.start_encounter()
    encounter.start_turn()
    assert encounter.get_current_entity() is caster
    choice = next((action, position) for action in get_available_actions(caster).all_actions
                  if action.behavior_id == "spell.gust_of_wind"
                  for position in action.valid_targets if position.position == (4, 5))
    with fixed_dice_faces(1):
        result = execute_available_action(caster, *choice)
    assert isinstance(result, SpellEvent) and not result.canceled
    assert caster.position == (3, 5) and target.position == (7, 5)
    zone = next(zone for zone in get_map().get_spatial_conditions() if isinstance(zone, GustOfWindZone))
    with fixed_dice_faces(1, 1):
        encounter.next_turn()
        encounter.next_turn()
    assert encounter.get_current_entity() is caster
    assert caster.position == zone.position == (3, 5) and target.position == (10, 5)
    assert not zone.is_hazardous_for(caster.uuid) and zone.is_hazardous_for(target.uuid)
    push_targets = {event.target_entity_uuid for _, event in EventQueue.iter_events_since(0)
                    if isinstance(event, ForcedMovementEvent) and event.phase is EventPhase.COMPLETION}
    assert push_targets == {target.uuid}
    drop = next((action, recipient) for action in get_available_actions(caster).all_actions
                if action.behavior_id == "action.drop_concentration" for recipient in action.valid_targets)
    result = execute_available_action(caster, *drop)
    assert result is not None and not result.canceled
    assert not get_map().get_spatial_conditions() and "Concentrating" not in caster.active_conditions


@pytest.mark.parametrize("remove_while_hidden", (False, True))
def test_gust_observation_origin_disclosure_and_removal_replay_without_native_world(remove_while_hidden) -> None:
    reset_item_arena(40, 25)
    caster = create_caster((5, 10))
    observer = create_target((14, 13))
    Entity.update_all_entities_senses(max_distance=5)
    initial = capture_senses_snapshot(observer.senses)
    identity = observer.uuid
    cursor = EventQueue.event_cursor()
    checkpoints = []

    def checkpoint():
        checkpoints.append((EventQueue.event_cursor(), capture_senses_snapshot(observer.senses)))

    result = GustOfWind(source_entity_uuid=caster.uuid, end_position=(17, 10)).apply()
    assert result is not None and not result.canceled
    zone = next(zone for zone in get_map().get_spatial_conditions() if isinstance(zone, GustOfWindZone))
    edge = observer.senses.spatial_effects[zone.uuid]
    assert edge.anchor_position is None and edge.area_geometry is None
    assert set(edge.positions) < zone.affected_positions
    checkpoint()
    Entity.update_entity_position(observer, (6, 13))
    seen = observer.senses.spatial_effects[zone.uuid]
    assert seen.anchor_position == (5, 10)
    assert seen.area_geometry == LinePresentationGeometry(
        origin=(5, 10), direction=(12, 0), length_feet=60, width_feet=10)
    checkpoint()
    Entity.update_entity_position(observer, (30, 13))
    assert observer.senses.spatial_effects[zone.uuid] == seen
    checkpoint()
    if remove_while_hidden:
        assert caster.remove_condition("Concentrating")
        assert observer.senses.spatial_effects[zone.uuid] == seen
        checkpoint()
    Entity.update_entity_position(observer, (6, 13))
    if not remove_while_hidden:
        assert caster.remove_condition("Concentrating")
    retained = observer.senses.spatial_effects.get(zone.uuid)
    assert retained is None or set(retained.positions).isdisjoint(observer.senses.visible)
    checkpoint()
    # Previously observed but still hidden cells retain their last known state.
    # Seeing the complete former area establishes that every part is gone.
    Entity.update_all_entities_senses(max_distance=150)
    assert zone.uuid not in observer.senses.spatial_effects
    checkpoint()
    packets = [(index, event.model_dump_json()) for index, event in EventQueue.iter_events_since(cursor)
               if isinstance(event, SensoryUpdateEvent) and event.observer_uuid == identity
               and event.phase is EventPhase.COMPLETION]
    reset_engine_runtime()
    restored = initial
    pending = iter(packets)
    current = next(pending, None)
    for end, expected in checkpoints:
        while current is not None and current[0] < end:
            event = SensoryUpdateEvent.model_validate_json(current[1], context=PASSIVE_EVENT_REPLAY)
            restored = reduce_senses_snapshot(identity, restored, event)
            current = next(pending, None)
        assert restored.spatial_effects == expected.spatial_effects
    assert current is None and EventQueue.event_cursor() == 0 and not Entity.get_all_entities()
