"""Current boundary occupancy and contact follow native placement/removal.

Boundary: public GridMap contact and Tile-side queries. A native window is
placed and removed; returned membership sets remain detached query values.
"""

import pytest

from dnd.core.events import EventQueue
from dnd.core.gridmap import get_map
from dnd.types.physical_access import ContactPassage, PhysicalAccess
from dnd.types.world import CardinalDirection
from tests.engine.test_window_attack_access import arena, barrier, combatants


@pytest.mark.parametrize("policy,allowed", [
    (ContactPassage.CLEAR, True),
    (ContactPassage.BLOCKED, False),
    (ContactPassage.HAND_AND_LIGHT_WEAPONS, False),
])
def test_current_boundary_presence_preserves_contact_and_detached_queries(arena, policy, allowed):
    source, target, _ = combatants(arena, "greataxe")
    grid = get_map()
    position, direction = source.position, CardinalDirection.EAST
    assert not grid.has_boundary_objects_at(position, direction)
    assert not grid.has_boundary_objects_at((-5, -5), direction)
    assert grid.can_reach_between(position, target.position, PhysicalAccess.WEAPON, source.uuid)
    frame = barrier(policy)
    cursor = EventQueue.event_cursor()
    assert grid.has_boundary_objects_at(position, direction)
    assert grid.has_boundary_objects_at(position, direction, 0)
    assert grid.has_boundary_objects_at(position, direction, 1)
    assert not grid.has_boundary_objects_at(position, direction, 2)
    snapshot = grid.get_boundary_objects_at(position, direction)
    assert snapshot == {frame.uuid}
    snapshot.clear()
    assert grid.has_boundary_objects_at(position, direction)
    assert grid.can_reach_between(position, target.position, PhysicalAccess.WEAPON, source.uuid) is allowed
    assert EventQueue.event_cursor() == cursor
    assert grid.remove_object(frame.uuid)
    assert not grid.has_boundary_objects_at(position, direction)
    assert grid.can_reach_between(position, target.position, PhysicalAccess.WEAPON, source.uuid)
