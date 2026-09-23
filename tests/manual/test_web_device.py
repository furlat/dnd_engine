"""Web device commands and observed zone lifetime use native events end to end."""

import pytest

from dnd.actions import SpellEvent
from dnd.actions_functional import execute_use_action
from dnd.blocks.sensory import capture_senses_snapshot
from dnd.content.items.environment_item_builders import build_arcane_machine_gun
from dnd.core.base_actions import AvailableTarget, TargetType
from dnd.core.base_object import PASSIVE_EVENT_REPLAY
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import EventPhase, EventQueue, SensoryUpdateEvent
from dnd.core.gridmap import get_map
from dnd.core.presentation_geometry import CubePresentationGeometry
from dnd.entity import Entity
from dnd.runtime_reset import reset_engine_runtime
from dnd.spells.conjuration import Web, WebZone
from dnd.types.senses import reduce_senses_snapshot
from dnd.types.world import MovementMode
from tests.manual.test_131_inventory_use_actions_legacy_contract import (
    create_caster, create_target, force_save, item_action, reset_item_arena,
)


def test_device_web_creates_one_zone_at_emitter_range_and_concentration_removes_it() -> None:
    reset_item_arena()
    caster = create_caster((4, 10))
    target = create_target((6, 10))
    outside_sector = create_target((6, 11))
    for actor in (target, outside_sector):
        force_save(actor, "dexterity", succeeds=False)
    grant = Web(source_entity_uuid=caster.uuid, template=True, cast_origin="source_item",
                alt_range=5, target_sector_degrees=45)
    device = build_arcane_machine_gun(caster.uuid, spell_templates=[grant], charges=2)
    device.place_on_grid((5, 10))
    Entity.update_all_entities_senses()
    info = item_action(caster, device.uuid, "Web")
    assert info.target_type is TargetType.POSITION
    assert outside_sector.position not in {row.position for row in info.valid_targets}
    selected = next(row for row in info.valid_targets if row.position == target.position)
    assert selected.distance == 5 and caster.senses.get_feet_distance(target.position) == 10
    hp_before = target.get_hp(), outside_sector.get_hp()
    slots_before = caster.action_economy.spell_slot_2.normalized_score
    cursor = EventQueue.event_cursor()
    with fixed_dice_faces(10, 10):
        result = execute_use_action(caster, device.uuid, info.template_name, selected)
    assert isinstance(result, SpellEvent) and not result.canceled
    assert result.phase is EventPhase.COMPLETION and result.behavior_id == "spell.web"
    assert result.source_entity_uuid == caster.uuid and result.source_position == caster.position
    assert result.source_item_uuid == device.uuid and result.cast_origin == "source_item"
    assert result.range_ft == 5 and result.aoe_position == target.position
    zones = [zone for zone in get_map().get_spatial_conditions() if isinstance(zone, WebZone)]
    assert len(zones) == 1
    zone = zones[0]
    assert result.resolved_area_positions == tuple(sorted(zone.affected_positions))
    assert result.area_geometry == CubePresentationGeometry(origin=zone.position, size_feet=20, centered=True)
    assert target.position in zone.affected_positions and outside_sector.position in zone.affected_positions
    assert (target.get_hp(), outside_sector.get_hp()) == hp_before
    assert all("Restrained" in actor.active_conditions for actor in (target, outside_sector))
    assert caster.action_economy.actions.normalized_score == 0 and device.charges == 1
    assert caster.action_economy.spell_slot_2.normalized_score == slots_before
    spell_completions = [event for _, event in EventQueue.iter_events_since(cursor)
                         if isinstance(event, SpellEvent) and event.phase is EventPhase.COMPLETION]
    assert [event.uuid for event in spell_completions] == [result.uuid]
    observed = caster.senses.spatial_effects[zone.uuid]
    assert observed.trap_state is None and observed.content_ref == zone.content_ref
    tile = get_map().get_tile(*target.position)
    assert tile is not None and tile.get_movement_cost(MovementMode.WALKING) == 2
    assert "Concentrating" not in caster.active_conditions
    assert device.remove_condition("Concentrating")
    assert zone.uuid not in caster.senses.spatial_effects
    assert get_map().get_spatial_condition(zone.uuid) is None
    assert all("Restrained" not in actor.active_conditions for actor in (target, outside_sector))
    assert tile.get_movement_cost(MovementMode.WALKING) == 1


@pytest.mark.parametrize("position, reason", (((5, 14), "firing sector"), ((14, 10), "out of range")))
def test_device_web_rejects_invalid_center_without_spending_or_creating_zone(position, reason) -> None:
    reset_item_arena()
    caster = create_caster((4, 10))
    grant = Web(source_entity_uuid=caster.uuid, template=True, cast_origin="source_item",
                alt_range=20, target_sector_degrees=45)
    device = build_arcane_machine_gun(caster.uuid, spell_templates=[grant], charges=1)
    device.place_on_grid((5, 10))
    Entity.update_all_entities_senses()
    template = device.get_use_actions(caster.uuid)[0]
    slots_before = caster.action_economy.spell_slot_2.normalized_score
    result = execute_use_action(caster, device.uuid, template.get_discovery_template_name(),
                                AvailableTarget(index=0, position=position))
    assert result is not None and result.canceled and reason in (result.status_message or "")
    assert device.charges == 1 and caster.action_economy.actions.normalized_score == 1
    assert caster.action_economy.spell_slot_2.normalized_score == slots_before
    assert not any(isinstance(zone, WebZone) for zone in get_map().get_spatial_conditions())


@pytest.mark.parametrize("remove_while_hidden", (False, True))
def test_web_observation_retains_only_seen_cells_and_replays_leave_reacquire_remove(remove_while_hidden) -> None:
    reset_item_arena(width=40, height=25)
    caster = create_caster((4, 10))
    observer = create_target((12, 13), name="Observer")
    Entity.update_all_entities_senses(max_distance=5)
    observer_uuid = observer.uuid
    initial = capture_senses_snapshot(observer.senses)
    cursor = EventQueue.event_cursor()
    checkpoints = []

    def checkpoint() -> None:
        checkpoints.append((EventQueue.event_cursor(), capture_senses_snapshot(observer.senses)))

    result = Web(source_entity_uuid=caster.uuid, end_position=(8, 10)).apply()
    assert result is not None and not result.canceled
    zone = next(zone for zone in get_map().get_spatial_conditions() if isinstance(zone, WebZone))
    observed = observer.senses.spatial_effects[zone.uuid]
    assert observed.trap_state is None
    assert set(observed.positions) == zone.affected_positions.intersection(observer.senses.visible)
    assert set(observed.positions) < zone.affected_positions
    checkpoint()
    Entity.update_entity_position(observer, (30, 13))
    assert not zone.affected_positions.intersection(observer.senses.visible)
    assert observer.senses.spatial_effects[zone.uuid] == observed
    checkpoint()
    if remove_while_hidden:
        assert caster.remove_condition("Concentrating")
        assert observer.senses.spatial_effects[zone.uuid] == observed
        checkpoint()
    Entity.update_entity_position(observer, (12, 13))
    if remove_while_hidden:
        assert zone.uuid not in observer.senses.spatial_effects
    else:
        assert observer.senses.spatial_effects[zone.uuid] == observed
    checkpoint()
    if not remove_while_hidden:
        assert caster.remove_condition("Concentrating")
        assert zone.uuid not in observer.senses.spatial_effects
        checkpoint()
    packets = [(index, event.model_dump_json()) for index, event in EventQueue.iter_events_since(cursor)
               if isinstance(event, SensoryUpdateEvent) and event.observer_uuid == observer_uuid
               and event.phase is EventPhase.COMPLETION]
    reset_engine_runtime()
    restored = initial
    next_packet = 0
    for end_cursor, expected in checkpoints:
        while next_packet < len(packets) and packets[next_packet][0] < end_cursor:
            event = SensoryUpdateEvent.model_validate_json(packets[next_packet][1], context=PASSIVE_EVENT_REPLAY)
            restored = reduce_senses_snapshot(observer_uuid, restored, event)
            next_packet += 1
        assert restored.position == expected.position
        assert restored.visible == expected.visible
        assert restored.spatial_effects == expected.spatial_effects
    assert next_packet == len(packets)
    assert EventQueue.event_cursor() == 0 and not Entity.get_all_entities()
