"""Simultaneous groups settle observers once, exactly as a cold recompute would (plan §5.2-5.4)."""

from collections import Counter
from contextlib import contextmanager

from dnd.action_timing import reset_action_count_recorder, set_action_count_recorder
from dnd.blocks.sensory import capture_senses_snapshot, spatial_senses_system
from dnd.core.base_block import LightLevel
from dnd.core.content.identities import ContentDefinitionKind, ContentRef
from dnd.core.events import Event, EventPhase, EventQueue, EventType
from dnd.core.gridmap import get_map
from dnd.entity import Entity
from dnd.spatial.area_conditions import AreaCondition
from dnd.spatial.gas_traps import GasCloud, GasCloudSpec, materialize_gas_vent
from dnd.spatial.triggers import materialize_pressure_plate
from dnd.types.controls import ActivationLink
from dnd.types.event_facts import GroupEntryKind
from dnd.types.senses import OpticalObscurement
from dnd.core.condition_types import HazardFilter
from dnd.types.spatial_effects import SpatialEffectAnchorKind, SpatialEffectLayer, SpatialEffectOccupancyPolicy
from tests.engine.test_senses_light_stealth import create_skeleton, reset_senses_state


def _cause(source_uuid) -> Event:
    return Event(name="Group test cause", event_type=EventType.BASE_ACTION, phase=EventPhase.EFFECT,
        source_entity_uuid=source_uuid)


def _zone(source_uuid, name: str, cells: set[tuple[int, int]]) -> AreaCondition:
    return AreaCondition(name=name, source_entity_uuid=source_uuid, content_ref=ContentRef(
            pack_id="test.groups", definition_kind=ContentDefinitionKind.CONDITION,
            content_id=f"condition.groups.{name.lower().replace(' ', '_')}", content_version=1,
            definition_contract_hash="0" * 64),
        position=min(cells), affected_positions=set(cells), layer=SpatialEffectLayer.GROUND_SURFACE,
        occupancy_policy=SpatialEffectOccupancyPolicy.OVERLAPPING, adds_difficult_terrain=True)


@contextmanager
def _counting():
    counts: Counter[str] = Counter()
    token = set_action_count_recorder(lambda name, value: counts.update({name: value}))
    try:
        yield counts
    finally:
        reset_action_count_recorder(token)


def _observation(observer: Entity) -> dict:
    snapshot = capture_senses_snapshot(observer.senses)
    return {"visible": snapshot.visible, "entities": snapshot.entities, "objects": snapshot.objects,
        "hazardous_cells": snapshot.hazardous_cells, "light": snapshot.effective_light_levels,
        "light_sources": snapshot.light_sources}


def assert_matches_cold_recompute(*observers: Entity) -> None:
    """The correctness oracle: a forced full recompute must not change any settled observation."""
    for observer in observers:
        settled = _observation(observer)
        spatial_senses_system.recompute_observer(observer.uuid)
        assert _observation(observer) == settled, observer.name


def _world():
    reset_senses_state(width=10, height=3, default_light=LightLevel.DARKNESS)
    observers = [create_skeleton(name=f"Observer {index}", position=(index * 3, 1), darkvision=True)
        for index in range(3)]
    for observer in observers:
        observer.materialize_navigation(max_distance=5)
    # A standing zone fixes the propagation solver choice for the whole test (PD1a removes the flip).
    _zone(observers[0].uuid, "Standing", {(9, 2)}).activate(parent_event=_cause(observers[0].uuid))
    return observers


def _changes(source: Entity) -> None:
    """Several objective changes of one logical instant: terrain, light, a wall."""
    grid = get_map()
    _zone(source.uuid, "Mud A", {(1, 0), (2, 0)}).activate(parent_event=_cause(source.uuid))
    _zone(source.uuid, "Mud B", {(5, 0), (6, 0)}).activate(parent_event=_cause(source.uuid))
    grid.add_light_source((4, 1), bright_radius_feet=10, dim_radius_feet=5)
    grid.set_tile(4, 0, blocks_optics=True, blocks_propagation=True, default_light=LightLevel.DARKNESS)


def test_a_group_settles_each_affected_observer_once_and_matches_a_cold_recompute() -> None:
    observers = _world()
    cursor = EventQueue.event_cursor()
    with _counting() as counts:
        with EventQueue.group(GroupEntryKind.AREA_APPLICATION):
            _changes(observers[0])
            assert counts["sensory.observer_settled"] == 0
    assert counts["sensory.observer_settled"] <= len(observers)
    light_facts = [event for _, event in EventQueue.iter_events_since(cursor)
        if event.event_type in (EventType.SPATIAL_LIGHT_CHANGED, EventType.SPATIAL_LIGHT_SOURCES_CHANGED)
        and event.phase is EventPhase.COMPLETION]
    assert len(light_facts) == 1
    assert_matches_cold_recompute(*observers)


def test_nested_entries_join_the_open_group_and_settle_at_the_outermost_close() -> None:
    observers = _world()
    with _counting() as counts:
        with EventQueue.group(GroupEntryKind.AREA_APPLICATION):
            with EventQueue.group(GroupEntryKind.ZONE_INSTALL):
                _changes(observers[0])
            assert counts["sensory.observer_settled"] == 0
    assert counts["sensory.observer_settled"] <= len(observers)
    assert_matches_cold_recompute(*observers)


def test_the_same_changes_outside_a_group_settle_per_fact_and_agree() -> None:
    """Grouping changes the number of passes, never the settled observation."""
    observers = _world()
    with _counting() as counts:
        _changes(observers[0])
    assert counts["sensory.observer_settled"] > len(observers)
    assert_matches_cold_recompute(*observers)


def test_a_plate_released_gas_cloud_settles_observers_as_a_cold_recompute_would() -> None:
    """Plate pulse → vent → cloud is one instant (plan §5.2 trap/plate entry)."""
    reset_senses_state(width=10, height=3)
    observers = [create_skeleton(name=f"Observer {index}", position=(index * 3, 0), darkvision=True)
        for index in range(3)]
    traveler = create_skeleton(name="Traveler", position=(4, 2), darkvision=True)
    vent = materialize_gas_vent((7, 2), gas=GasCloudSpec(radius_feet=5, optical_obscurement=OpticalObscurement.HEAVY))
    materialize_pressure_plate({(5, 2)}, ActivationLink(target_condition_uuid=vent.uuid))
    Entity.update_all_entities_senses()
    turn = EventQueue.begin_turn_execution()
    try:
        Entity.update_entity_position(traveler, (5, 2), parent_event=_cause(traveler.uuid).uuid)
        assert any(isinstance(condition, GasCloud) for condition in get_map().get_spatial_conditions())
    finally:
        EventQueue.end_turn_execution(turn)
    assert_matches_cold_recompute(*observers, traveler)


def test_an_anchored_zone_following_each_step_settles_as_a_cold_recompute_would() -> None:
    """The zone moves inside the step, before the step's own contacts settle (plan §5.1 P-e)."""
    reset_senses_state(width=10, height=3)
    observers = [create_skeleton(name=f"Observer {index}", position=(index * 4, 0), darkvision=True)
        for index in range(3)]
    walker = create_skeleton(name="Walker", position=(1, 2), darkvision=True)
    zone = AreaCondition(name="Following Mud", source_entity_uuid=walker.uuid, content_ref=ContentRef(
            pack_id="test.groups", definition_kind=ContentDefinitionKind.CONDITION,
            content_id="condition.groups.following_mud", content_version=1, definition_contract_hash="0" * 64),
        position=(1, 2), affected_positions={(1, 2), (2, 2)}, layer=SpatialEffectLayer.FIELD,
        occupancy_policy=SpatialEffectOccupancyPolicy.OVERLAPPING, adds_difficult_terrain=True,
        hazard_filter=HazardFilter.ALL, anchor_kind=SpatialEffectAnchorKind.ENTITY, anchor_uuid=walker.uuid)
    zone.activate(parent_event=_cause(walker.uuid))
    Entity.update_all_entities_senses()
    for x in range(2, 6):
        Entity.update_entity_position(walker, (x, 2), parent_event=_cause(walker.uuid).uuid)
        assert zone.position == (x, 2)
        assert_matches_cold_recompute(*observers, walker)
