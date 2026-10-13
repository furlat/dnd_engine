"""Moving ordinary sight preserves every committed light observation."""

from dataclasses import replace
from uuid import uuid4

import pytest

from dnd.blocks.sensory import capture_senses_snapshot
from dnd.core.base_block import LightLevel
from dnd.core.events import EventQueue
from dnd.core.gridmap import get_map
from dnd.entity import Entity
from dnd.items.environment import DirectionalWall
from dnd.player.event_record import decode_event, encode_event
from dnd.types.senses import OpticalObscurement, SenseMode, SensesType, reduce_senses_snapshot
from dnd.types.world import CardinalDirection, WorldEdgeChannel
from tests.engine.test_senses_light_stealth import create_skeleton, reset_senses_state
from tests.engine.test_sensory_initial_replay import sensory_since


@pytest.mark.parametrize("obscured", [False, True])
def test_moving_torch_observations_equal_public_full_refresh(obscured):
    reset_senses_state(width=10, height=3, default_light=LightLevel.DARKNESS)
    grid = get_map()
    mover = create_skeleton(name="Ordinary observer", position=(2, 1), darkvision=False)
    target = create_skeleton(name="Light frontier", position=(5, 1), darkvision=False)
    if obscured:
        grid.apply_optical_obscurement(uuid4(), {(0, 1)}, OpticalObscurement.HEAVY)
    grid.add_light_source(mover.position, bright_radius_feet=5,
        dim_radius_feet=5, anchor_uuid=mover.uuid)
    mover.update_entity_senses(max_distance=3)
    replayed = capture_senses_snapshot(mover.senses)
    assert target.uuid not in replayed.entities
    assert target.position not in replayed.visible

    for destinations, expected_contact in ((((3, 1), (4, 1)), True), (((3, 1), (2, 1)), False)):
        cursor = EventQueue.event_cursor()
        for destination in destinations:
            Entity.update_entity_position(mover, destination)
        updates = sensory_since(mover.uuid, cursor)
        assert updates
        for event in updates:
            replayed = reduce_senses_snapshot(mover.uuid, replayed, decode_event(encode_event(event)))
        current = capture_senses_snapshot(mover.senses)
        assert replayed == current
        assert (target.uuid in current.entities) is expected_contact
        assert (target.position in current.visible) is expected_contact

        # Explicit public refresh resolves the complete native field. It may
        # materialize navigation, but must not correct the committed perception.
        refresh_cursor = EventQueue.event_cursor()
        mover.update_entity_senses(max_distance=3)
        refreshed = capture_senses_snapshot(mover.senses)
        assert replace(current, paths_dirty=False) == replace(refreshed, paths_dirty=False)
        assert sensory_since(mover.uuid, refresh_cursor) == ()
        replayed = refreshed


@pytest.mark.parametrize('nonvisual', (False, True))
def test_moving_light_preserves_incident_contacts_across_boundary_coverage(nonvisual):
    reset_senses_state(width=18, height=4, default_light=LightLevel.DARKNESS)
    grid = get_map()
    mover = create_skeleton(name='Boundary observer', position=(2, 1), darkvision=False)
    if nonvisual:
        mover.senses.sense_modes = [SenseMode(sense_type=SensesType.BLINDSIGHT, range_feet=15)]
    # Opposite owners contribute to the same route with different channels.
    # Shift coverage past both, retain one, then return from a disjoint field.
    for x, side, channel in ((1, CardinalDirection.EAST, WorldEdgeChannel.OPTICAL),
                            (2, CardinalDirection.WEST, WorldEdgeChannel.PROPAGATION),
                            (5, CardinalDirection.WEST, WorldEdgeChannel.OPTICAL),
                            (12, CardinalDirection.EAST, WorldEdgeChannel.PROPAGATION)):
        wall = DirectionalWall(source_entity_uuid=mover.uuid, item_id='test.moving_incident_wall',
            blocked_channels=(channel,))
        wall.place_on_grid((x, 2), boundary_direction=side)
    grid.add_light_source(mover.position, bright_radius_feet=10,
        dim_radius_feet=5, anchor_uuid=mover.uuid)
    mover.update_entity_senses(max_distance=3)
    replayed = capture_senses_snapshot(mover.senses)
    prior = []
    for destination in ((3, 1), (4, 1), (5, 1), (6, 1), (13, 1), (12, 1), (11, 1), (4, 1)):
        saved = capture_senses_snapshot(mover.senses)
        prior.append((saved, replace(saved, objects=dict(saved.objects))))
        cursor = EventQueue.event_cursor()
        Entity.update_entity_position(mover, destination)
        updates = sensory_since(mover.uuid, cursor)
        assert updates
        for event in updates:
            replayed = reduce_senses_snapshot(mover.uuid, replayed, decode_event(encode_event(event)))
        current = capture_senses_snapshot(mover.senses)
        assert replace(replayed, paths_dirty=False) == replace(current, paths_dirty=False)
        refresh_cursor = EventQueue.event_cursor()
        mover.update_entity_senses(max_distance=3)
        refreshed = capture_senses_snapshot(mover.senses)
        assert replace(current, paths_dirty=False) == replace(refreshed, paths_dirty=False)
        assert sensory_since(mover.uuid, refresh_cursor) == ()
        assert all(snapshot == frozen for snapshot, frozen in prior)
        replayed = refreshed
