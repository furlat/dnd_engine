"""A Fireball contacts structures once and expands only after native destruction."""

from uuid import uuid4

import pytest

from dnd.actions import SpellEvent
from dnd.blocks.base_item import BaseItem
from dnd.content.items.environment_item_builders import build_authored_door
from dnd.content.items.window_builders import place_window
from dnd.core.creature_types import DamageType
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import (
    AreaReachEvent, EventHandler, EventPhase, EventQueue, EventType,
    ItemDestructionEvent, TakeDamageEvent, Trigger,
)
from dnd.core.gridmap import get_map
from dnd.core.item_types import ItemDestructionProfile, ItemIntegrity
from dnd.entity import Entity
from dnd.runtime_reset import reset_engine_runtime
from dnd.spells.abjuration import GlobeOfInvulnerability
from dnd.spells.evocation import Fireball
from dnd.types.world import CardinalDirection
from tests.manual.spell_regression_support import (
    create_spell_regression_actor, reset_spell_regression_arena,
)


@pytest.fixture(autouse=True)
def arena():
    reset_spell_regression_arena(12, 1)
    yield
    reset_engine_runtime()


def caster(position=(0, 0)):
    return create_spell_regression_actor("Caster", position, "heroes", spell_slots={3: 1})


def door(x, *, hp=4, immune=False):
    item = build_authored_door("environment.door.desert_c7", hit_points=hp)
    if immune:
        item.health = BaseItem.create_item_health(item.uuid, hp, immunities=[DamageType.FIRE])
    item.place_on_grid((x, 0), boundary_direction=CardinalDirection.WEST)
    return item


def cast(source, target=(1, 0)):
    Entity.update_all_entities_senses(max_distance=120)
    cursor = EventQueue.event_cursor()
    with fixed_dice_faces(*([1] * 200)):
        result = Fireball(source_entity_uuid=source.uuid, end_position=target).apply()
    assert isinstance(result, SpellEvent)
    events = tuple(event for _, event in EventQueue.iter_events_since(cursor))
    return result, events


def completed(events, event_type):
    return [event for event in events if isinstance(event, event_type)
            and event.phase is EventPhase.COMPLETION]


@pytest.mark.parametrize("reverse_registration", [False, True])
def test_serial_doors_reach_later_victim_once_without_restarting_radius(reverse_registration):
    source = caster()
    near = create_spell_regression_actor("Near", (2, 0), "enemies")
    doors = {x: door(x) for x in ((5, 3) if reverse_registration else (3, 5))}
    first, second = doors[3], doors[5]
    far = create_spell_regression_actor("Far", (5, 0), "enemies")
    outside = create_spell_regression_actor("Outside", (7, 0), "enemies")
    before = near.get_hp(), far.get_hp(), outside.get_hp()
    result, events = cast(source)
    assert not result.canceled
    assert first.integrity is second.integrity is ItemIntegrity.DESTROYED
    assert (near.get_hp(), far.get_hp(), outside.get_hp()) == (before[0]-8, before[1]-8, before[2])
    assert set(result.resolved_area_positions or ()) == {(x, 0) for x in range(6)}
    damage = completed(events, TakeDamageEvent)
    assert len([event for event in damage if event.target_entity_uuid == near.uuid]) == 1
    assert len([event for event in damage if event.target_entity_uuid == far.uuid]) == 1
    stages = completed(events, AreaReachEvent)
    assert [stage.stage_index for stage in stages] == [0, 1, 2]
    assert [set(stage.newly_reached_positions) for stage in stages] == [
        {(0, 0), (1, 0), (2, 0)}, {(3, 0), (4, 0)}, {(5, 0)}]
    breaks = {event.target_entity_uuid: event for event in completed(events, ItemDestructionEvent)}
    assert stages[0].prerequisite_destruction_lineages == ()
    assert stages[1].prerequisite_destruction_lineages == (breaks[first.uuid].lineage_uuid,)
    assert stages[2].prerequisite_destruction_lineages == (breaks[second.uuid].lineage_uuid,)
    assert stages[1].previous_reach_lineage_uuid == stages[0].lineage_uuid
    applications = [event for event in completed(events, SpellEvent) if event.application_id is not None]
    far_application, = [event for event in applications if event.target_entity_uuid == far.uuid]
    assert far_application.parent_lineage == stages[2].lineage_uuid
    assert source.action_economy.spell_slot_3.normalized_score == 0
    assert source.action_economy.actions.normalized_score == 0


@pytest.mark.parametrize("hp,immune,remaining", [(100, False, 92), (4, True, 4)])
def test_surviving_or_immune_barrier_is_not_repeatedly_damaged(hp, immune, remaining):
    source = caster()
    blocker = door(3, hp=hp, immune=immune)
    target = create_spell_regression_actor("Sheltered", (4, 0), "enemies")
    before = target.get_hp()
    result, events = cast(source)
    assert not result.canceled and blocker.get_hp() == remaining
    assert target.get_hp() == before
    assert len(completed(events, AreaReachEvent)) == 1
    assert len([event for event in completed(events, TakeDamageEvent)
                if event.target_entity_uuid == blocker.uuid]) == 1
    assert (4, 0) not in (result.resolved_area_positions or ())


def test_parallel_surviving_provider_still_blocks_after_neighbor_breaks():
    source = caster()
    broken = door(3)
    survivor = build_authored_door("environment.door.desert_c7", hit_points=100)
    survivor.place_on_grid((2, 0), boundary_direction=CardinalDirection.EAST)
    target = create_spell_regression_actor("Sheltered", (4, 0), "enemies")
    before = target.get_hp()
    result, events = cast(source)
    assert not result.canceled and broken.integrity is ItemIntegrity.DESTROYED
    assert survivor.get_hp() == 92 and target.get_hp() == before
    assert (3, 0) not in (result.resolved_area_positions or ())
    assert len(completed(events, ItemDestructionEvent)) == 1


def test_parent_destruction_cascades_without_second_insert_application():
    source = caster()
    assembly = place_window("environment.window.fantasy_g9", (3, 0), CardinalDirection.WEST)
    assembly.wall.health = BaseItem.create_item_health(assembly.wall.uuid, 4)
    assert assembly.insert is not None
    result, events = cast(source)
    assert not result.canceled
    breaks = completed(events, ItemDestructionEvent)
    assert {event.target_entity_uuid for event in breaks} == {assembly.wall.uuid, assembly.insert.uuid}
    assert len(breaks) == 2
    assert not any(event.target_entity_uuid == assembly.insert.uuid
        for event in completed(events, TakeDamageEvent))


@pytest.mark.parametrize("inside", [False, True])
def test_globe_protects_objects_by_cast_source_without_stopping_geometric_reach(inside):
    source = caster((6 if inside else 0, 0))
    owner = create_spell_regression_actor("Globe", (4, 0), "heroes", spell_slots={6: 1})
    guarded = BaseItem(source_entity_uuid=uuid4(), item_id="test.protected_prop",
        is_targetable=True, health=BaseItem.create_item_health(owner.uuid, 30),
        destruction_profile=ItemDestructionProfile(name="Debris"))
    guarded.place_on_grid((4, 0))
    outside = create_spell_regression_actor("Outside", (7, 0), "enemies")
    Entity.update_all_entities_senses(max_distance=120)
    globe = GlobeOfInvulnerability(source_entity_uuid=owner.uuid).apply()
    assert globe is not None and not globe.canceled
    before = guarded.get_hp(), outside.get_hp()
    result, events = cast(source, target=(4, 0))
    assert not result.canceled
    assert guarded.get_hp() == before[0] - (8 if inside else 0)
    assert outside.get_hp() == before[1] - 8
    if not inside:
        canceled, = [event for event in events if isinstance(event, SpellEvent)
            and event.target_entity_uuid == guarded.uuid and event.phase is EventPhase.CANCEL]
        assert canceled.suppressions
        assert (4, 0) not in (result.resolved_area_positions or ())


def test_canceled_second_stage_keeps_first_damage_without_applying_future_region():
    source = caster()
    broken = door(3)
    target = create_spell_regression_actor("Sheltered", (4, 0), "enemies")
    before = target.get_hp()

    def cancel_later(event, _source):
        if isinstance(event, AreaReachEvent) and event.stage_index == 1:
            return event.cancel(status_message="Interrupt expansion")
        return event

    EventQueue.add_event_handler(EventHandler(name="Interrupt second area stage",
        source_entity_uuid=source.uuid,
        trigger_conditions=[Trigger(event_type=EventType.AREA_REACHED, event_phase=EventPhase.EXECUTION)],
        event_processor=cancel_later))
    result, events = cast(source)
    assert result.canceled and broken.integrity is ItemIntegrity.DESTROYED
    assert target.get_hp() == before
    assert len(completed(events, AreaReachEvent)) == 1
    assert source.action_economy.spell_slot_3.normalized_score == 0
