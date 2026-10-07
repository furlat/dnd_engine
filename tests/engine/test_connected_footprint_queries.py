"""Connected footprints retain exact reach across shared topology queries."""

from uuid import uuid4

import pytest

from dnd.blocks.base_item import BaseItem
from dnd.core.aoe import Sphere
from dnd.core.events import EventQueue
from dnd.items.environment import DirectionalDoor
from dnd.runtime_reset import reset_engine_runtime
from dnd.types.world import CardinalDirection


@pytest.fixture(autouse=True)
def corridor():
    reset_engine_runtime(grid_size=(7, 1))
    yield
    reset_engine_runtime()


def footprint(origin, radius_feet):
    cursor = EventQueue.event_cursor()
    shape = Sphere(source_entity_uuid=uuid4(), target=origin,
        radius_feet=radius_feet, propagation="connected")
    positions = shape.compute_objective(origin).affected_positions
    assert EventQueue.event_cursor() == cursor
    return positions


def test_connected_queries_follow_door_changes_without_extending_each_footprint():
    door = DirectionalDoor(source_entity_uuid=uuid4(),
        item_id="test.connected.door", is_open=True)
    door.place_on_grid((2, 0), boundary_direction=CardinalDirection.EAST)

    def check(opened):
        assert footprint((1, 0), 20) == {(x, 0) for x in range(6 if opened else 3)}
        assert footprint((3, 0), 10) == {(x, 0) for x in range(1 if opened else 3, 6)}

    check(True)
    door.close()
    check(False)
    door.open()
    check(True)
    door.close()
    check(False)
    door.destroy()
    check(True)


def test_connected_queries_reach_solid_surface_and_allow_a_solid_origin():
    wall = BaseItem(source_entity_uuid=uuid4(), item_id="test.connected.solid",
        is_pickable=False, blocks_propagation_field=True)
    wall.place_on_grid((2, 0))

    assert footprint((0, 0), 20) == {(0, 0), (1, 0), (2, 0)}
    assert footprint((2, 0), 10) == {(x, 0) for x in range(5)}
    assert footprint((4, 0), 20) == {(x, 0) for x in range(2, 7)}
