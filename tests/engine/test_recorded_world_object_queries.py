"""Native recorded placement changes preserve local object query membership."""

import json
from uuid import uuid4

import pytest

from dnd.blocks.base_item import WorldItem
from dnd.core.events import EventPhase, EventQueue
from dnd.core.gridmap import get_map
from dnd.player.event_record import decode_event, encode_event
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.types.materials import Material
from dnd.types.world import CardinalDirection, WorldEdgeChannel
from dnd.types.world_placement import (
    BoundaryStructure, BoundaryStructureKind, WorldPlacementKind, WorldPlacementSpec,
)
from dnd.world_facts import WorldFacts, apply_world_fact, copy_world_facts, world_objects_at


@pytest.fixture(autouse=True)
def fresh_runtime():
    reset_engine_runtime()
    yield
    reset_engine_runtime()


def fold_recorded(world, cursor=0):
    """Feed completed native events through their detached recording contract."""
    for _, native in EventQueue.iter_events_since(cursor):
        if native.phase is EventPhase.COMPLETION and not native.canceled:
            event = decode_event(json.loads(json.dumps(encode_event(native))))
            apply_world_fact(world, event)
    return EventQueue.event_cursor()


def boundary(*, zero_band=False):
    return WorldItem(source_entity_uuid=uuid4(), item_id="test.recorded.boundary",
        world_placement_spec=WorldPlacementSpec(kind=WorldPlacementKind.BOUNDARY,
            occupies_bands=False, vertical_extent_steps=1),
        removed_local_bands=((0, 0, 0),) if zero_band else (),
        boundary_structure=BoundaryStructure(structure=BoundaryStructureKind.WALL,
            material=Material.STONE, blocked_channels=(WorldEdgeChannel.OPTICAL,)))


@pytest.mark.parametrize("direction,opposite", [
    (CardinalDirection.NORTH, (-2, -2)),
    (CardinalDirection.SOUTH, (-2, -4)),
    (CardinalDirection.WEST, (-3, -3)),
    (CardinalDirection.EAST, (-1, -3)),
])
@pytest.mark.parametrize("zero_band", [False, True])
def test_boundary_queries_include_unsupported_incident_neighbor(direction, opposite, zero_band):
    anchor = (-2, -3)
    get_map().set_tile(*anchor)
    wall = boundary(zero_band=zero_band)
    wall.place_on_grid(anchor, boundary_direction=direction)
    world = WorldFacts()
    cursor = fold_recorded(world)

    assert opposite not in world.tiles
    assert world_objects_at(world, {opposite}) == {wall.uuid}
    assert world_objects_at(world, {anchor}) == (set() if zero_band else {wall.uuid})
    assert world_objects_at(world, {anchor, opposite}) == {wall.uuid}
    assert world_objects_at(world, {(5, 5)}) == set()
    assert get_map().remove_object(wall.uuid)
    fold_recorded(world, cursor)
    assert world_objects_at(world, {anchor, opposite}) == set()


def test_native_relocation_face_change_and_removal_leave_detached_query_results():
    grid = get_map()
    grid.create_rectangle(-2, -2, 6, 5)
    wall = boundary()
    wall.place_on_grid((-1, 0), boundary_direction=CardinalDirection.EAST)
    center = WorldItem(source_entity_uuid=uuid4(), item_id="test.recorded.footprint",
        world_placement_spec=WorldPlacementSpec(kind=WorldPlacementKind.CENTER,
            occupies_bands=False, vertical_extent_steps=1, footprint_offsets=((0, 0), (1, 0))))
    center.place_on_grid((0, 0))
    world = WorldFacts()
    cursor = fold_recorded(world)
    before = copy_world_facts(world)
    assert world_objects_at(world, {(0, 0), (1, 0)}) == {wall.uuid, center.uuid}

    grid.move_object(wall.uuid, (-1, 0), boundary_direction=CardinalDirection.NORTH)
    cursor = fold_recorded(world, cursor)
    assert world_objects_at(world, {(0, 0)}) == {center.uuid}
    assert world_objects_at(world, {(-1, 1)}) == {wall.uuid}

    grid.move_object(wall.uuid, (2, 1), boundary_direction=CardinalDirection.WEST)
    grid.move_object(center.uuid, (1, -1))
    cursor = fold_recorded(world, cursor)
    assert world_objects_at(world, {(-1, 0), (-1, 1), (0, 0), (1, 0)}) == set()
    assert world_objects_at(world, {(2, 1), (1, 1)}) == {wall.uuid}
    assert world_objects_at(world, {(1, -1), (2, -1)}) == {center.uuid}

    assert grid.remove_object(wall.uuid)
    assert grid.remove_object(center.uuid)
    fold_recorded(world, cursor)
    assert world_objects_at(world, set(grid.get_all_tiles())) == set()
    assert world_objects_at(before, {(-1, 0), (0, 0), (1, 0)}) == {wall.uuid, center.uuid}
    assert world_objects_at(before, {(-1, 1), (2, 1), (1, 1)}) == set()


def test_new_recorded_world_replaces_old_incident_membership():
    grid = get_map()
    grid.set_tile(-1, -1)
    wall = boundary(zero_band=True)
    wall.place_on_grid((-1, -1), boundary_direction=CardinalDirection.WEST)
    world = WorldFacts()
    fold_recorded(world)
    before = copy_world_facts(world)
    assert world_objects_at(world, {(-2, -1)}) == {wall.uuid}

    reset_engine_runtime()
    build_battlefield("battlefield.open_floor_bright")
    fold_recorded(world)
    assert world_objects_at(world, {(-2, -1)}) == set()
    assert world_objects_at(before, {(-2, -1)}) == {wall.uuid}
