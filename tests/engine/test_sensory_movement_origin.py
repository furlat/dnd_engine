"""Every emitted movement observation uses its committed observer position."""

from dataclasses import replace

import pytest

from dnd.blocks.sensory import capture_senses_snapshot
from dnd.conditions import Invisible
from dnd.core.base_block import LightLevel, SenseMode, SensesType
from dnd.core.events import Event, EventPhase, EventQueue, EventType, SpatialChangeEvent
from dnd.core.gridmap import get_map
from dnd.entity import Entity
from dnd.items.environment import DirectionalDoor
from dnd.types.world import CardinalDirection
from dnd.player.event_record import decode_event, encode_event
from dnd.spatial.environmental_conditions import SpikeTrap
from dnd.spells.conjuration import DarknessZone, FogCloudZone
from dnd.types.senses import OpticalObscurement
from dnd.types.senses import reduce_senses_snapshot
from tests.engine.test_senses_light_stealth import create_skeleton, reset_senses_state
from tests.engine.test_sensory_initial_replay import sensory_since


@pytest.mark.parametrize("sense", [SensesType.DARKVISION, SensesType.TRUESIGHT])
@pytest.mark.parametrize("attached_light", [False, True])
def test_movement_range_is_correct_at_every_sensory_completion(sense, attached_light):
    # The target crosses the 15-foot sense boundary, outside the small torch's
    # reach. Truesight separately tests bypassing an invisible creature on an
    # otherwise visible tile. No explicit refresh follows either movement.
    reset_senses_state(width=7, height=1, default_light=(
        LightLevel.DARKNESS if sense is SensesType.DARKVISION else LightLevel.DIM_LIGHT))
    mover = create_skeleton(name="Moving observer", position=(0, 0), darkvision=False)
    target = create_skeleton(name="Range boundary target", position=(4, 0), darkvision=False)
    if sense is SensesType.TRUESIGHT:
        target.add_condition(Invisible(source_entity_uuid=target.uuid, target_entity_uuid=target.uuid))
    mover.senses.sense_modes = [SenseMode(sense_type=sense, range_feet=15)]
    if attached_light:
        get_map().add_light_source(mover.position, bright_radius_feet=5,
            dim_radius_feet=10, anchor_uuid=mover.uuid)
    mover.update_entity_senses(max_distance=6)
    target_id = target.uuid
    initial_contact = target_id in mover.senses.entities
    assert not initial_contact

    replayed = None
    for event in sensory_since(mover.uuid):
        replayed = reduce_senses_snapshot(mover.uuid, replayed, decode_event(encode_event(event)))
    assert replayed is not None
    for destination, expected_contact in [((1, 0), True), ((0, 0), False)]:
        cursor = EventQueue.event_cursor()
        Entity.update_entity_position(mover, destination)
        observations = sensory_since(mover.uuid, cursor)
        assert observations
        for event in observations:
            replayed = reduce_senses_snapshot(mover.uuid, replayed, decode_event(encode_event(event)))
            if replayed.position == destination:
                present = target_id in replayed.entities
                assert present == expected_contact, (
                    "A committed sensory prefix measured range from the previous cell",
                    event.update_reason, destination, replayed.entities)
                if sense is SensesType.DARKVISION:
                    assert (target.position in replayed.visible) == expected_contact
            assert event.cause_event_uuid == event.parent_event
            assert EventQueue.get_event_by_uuid(event.cause_event_uuid) is not None
        assert replayed.position == destination
        final_contact = target_id in mover.senses.entities
        assert final_contact == expected_contact
        assert mover.senses._paths_dirty
        assert replace(replayed, paths_dirty=False) == replace(
            capture_senses_snapshot(mover.senses), paths_dirty=False)
        light_completions = [event for _, event in EventQueue.iter_events_since(cursor)
            if isinstance(event, SpatialChangeEvent)
            and event.event_type is EventType.SPATIAL_LIGHT_CHANGED
            and event.phase is EventPhase.COMPLETION]
        assert len(light_completions) == int(attached_light)
        if attached_light:
            assert any(EventQueue.get_event_by_uuid(event.cause_event_uuid).event_type
                is EventType.SPATIAL_LIGHT_CHANGED for event in observations)
        # The public full refresh is a reference for retained-field reuse. It
        # may materialize navigation but must not correct perception or emit
        # another sensory delta after the committed movement boundary.
        refresh_cursor = EventQueue.event_cursor()
        mover.update_entity_senses(max_distance=6)
        refreshed = capture_senses_snapshot(mover.senses)
        assert replace(replayed, paths_dirty=False) == replace(refreshed, paths_dirty=False)
        assert sensory_since(mover.uuid, refresh_cursor) == ()


def test_moving_light_and_explicit_obscurement_with_nonoptical_trap():
    reset_senses_state(width=9, height=2, default_light=LightLevel.DARKNESS)
    observer = create_skeleton(name="Observer", position=(0, 1), darkvision=False)
    carrier = create_skeleton(name="Carrier", position=(1, 1), darkvision=False)
    target = create_skeleton(name="Target", position=(5, 1), darkvision=False)
    trap = SpikeTrap(source_entity_uuid=observer.uuid, position=(8, 0), affected_positions={(8, 0)})
    trap.activate(parent_event=None)
    grid = get_map()
    grid.add_light_source(carrier.position, bright_radius_feet=5,
        dim_radius_feet=10, anchor_uuid=carrier.uuid)
    assert target.uuid not in observer.senses.entities

    for destination, visible in (((2, 1), True), ((1, 1), False), ((2, 1), True)):
        cursor = EventQueue.event_cursor()
        Entity.update_entity_position(carrier, destination)
        assert (target.uuid in observer.senses.entities) is visible
        updates = sensory_since(observer.uuid, cursor)
        assert updates
        assert any(EventQueue.get_event_by_uuid(event.cause_event_uuid).event_type
            is EventType.SPATIAL_LIGHT_CHANGED for event in updates)
    grid.apply_optical_obscurement(trap.uuid, {(3, 1)}, OpticalObscurement.HEAVY)
    assert target.uuid not in observer.senses.entities
    grid.remove_optical_obscurement(trap.uuid)
    assert target.uuid in observer.senses.entities
    assert grid.has_spatial_condition(trap.uuid)


def test_partial_fog_footprint_still_blocks_and_removal_restores_sight():
    reset_senses_state(width=8, height=3)
    observer = create_skeleton(name="Observer", position=(0, 1), darkvision=False)
    target = create_skeleton(name="Target", position=(6, 1), darkvision=False)
    fog = FogCloudZone(source_entity_uuid=observer.uuid, position=(3, 1),
        affected_positions={(3, 1), (4, 1)})
    fog.activate(parent_event=None)
    assert target.uuid not in observer.senses.entities
    cause = Event(source_entity_uuid=observer.uuid, event_type=EventType.BASE_ACTION,
                  phase=EventPhase.EFFECT)
    fog.change_footprint({(4, 1)}, parent_event=cause)
    assert target.uuid not in observer.senses.entities
    fog.change_footprint({(4, 0)}, parent_event=cause)
    assert target.uuid in observer.senses.entities
    fog.change_footprint({(3, 1)}, parent_event=cause)
    assert target.uuid not in observer.senses.entities
    fog.deactivate()
    assert target.uuid in observer.senses.entities


@pytest.mark.parametrize("sense", [None, SensesType.DARKVISION, SensesType.BLINDSIGHT])
@pytest.mark.parametrize("volume", [None, FogCloudZone, DarknessZone])
def test_stationary_light_observations_match_refresh_and_cold_replay(sense, volume):
    """Changing torch light preserves each observed field, including cloud surfaces."""
    reset_senses_state(width=12, height=3, default_light=LightLevel.DARKNESS)
    observer = create_skeleton(name="Stationary observer", position=(0, 1), darkvision=False)
    carrier = create_skeleton(name="Light carrier", position=(5, 1), darkvision=False)
    create_skeleton(name="Far contact", position=(8, 1), darkvision=False)
    if sense is not None:
        observer.senses.sense_modes = [SenseMode(sense_type=sense, range_feet=50)]
    if volume is not None:
        volume(source_entity_uuid=observer.uuid, position=(3, 1),
            affected_positions={(3, 1), (4, 1)}).activate(parent_event=None)
    get_map().add_light_source(carrier.position, bright_radius_feet=5,
        dim_radius_feet=10, anchor_uuid=carrier.uuid)
    observer.update_entity_senses(max_distance=10)

    replayed = None
    for event in sensory_since(observer.uuid):
        replayed = reduce_senses_snapshot(observer.uuid, replayed, decode_event(encode_event(event)))
    historical = capture_senses_snapshot(observer.senses)
    historical_replay = replayed
    assert replayed is not None
    for destination in ((6, 1), (7, 1), (6, 1), (5, 1)):
        cursor = EventQueue.event_cursor()
        Entity.update_entity_position(carrier, destination)
        for event in sensory_since(observer.uuid, cursor):
            replayed = reduce_senses_snapshot(observer.uuid, replayed, decode_event(encode_event(event)))
        actual = capture_senses_snapshot(observer.senses)
        assert replace(replayed, paths_dirty=False) == replace(actual, paths_dirty=False)
        refresh_cursor = EventQueue.event_cursor()
        observer.update_entity_senses(max_distance=10)
        assert replace(actual, paths_dirty=False) == replace(
            capture_senses_snapshot(observer.senses), paths_dirty=False)
        assert sensory_since(observer.uuid, refresh_cursor) == ()
        assert replace(historical_replay, paths_dirty=False) == replace(historical, paths_dirty=False)


def test_opening_door_reveals_settled_light_at_the_existing_causal_boundary():
    """Light changes behind a closed face do not grant premature observations."""
    reset_senses_state(width=6, height=1, default_light=LightLevel.DARKNESS)
    grid = get_map()
    observer = create_skeleton(name="Door observer", position=(0, 0), darkvision=False)
    door = DirectionalDoor(source_entity_uuid=observer.uuid, item_id="test.directional_door")
    door.place_on_grid((1, 0), boundary_direction=CardinalDirection.EAST)
    # The first source only newly reaches cells behind the door. The second
    # strengthens those same cells before the door's committed observation.
    grid.add_light_source((0, 0), bright_radius_feet=5, dim_radius_feet=20)
    grid.add_light_source((0, 0), bright_radius_feet=20, dim_radius_feet=5)
    before = capture_senses_snapshot(observer.senses)
    assert (2, 0) not in before.visible
    cursor = EventQueue.event_cursor()
    door.open()
    replayed = before
    observations = sensory_since(observer.uuid, cursor)
    assert observations
    for event in observations:
        replayed = reduce_senses_snapshot(observer.uuid, replayed, decode_event(encode_event(event)))
        if (2, 0) in replayed.visible:
            assert replayed.effective_light_levels[(2, 0)] is LightLevel.BRIGHT_LIGHT
        cause = EventQueue.get_event_by_uuid(event.cause_event_uuid)
        assert cause is not None
        assert cause.event_type is EventType.SPATIAL_OBJECT_CHANGED
    assert (2, 0) in replayed.visible
    assert replace(replayed, paths_dirty=False) == replace(capture_senses_snapshot(observer.senses), paths_dirty=False)
