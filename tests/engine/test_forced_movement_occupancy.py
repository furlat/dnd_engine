"""Forced ground movement stops before physical creature occupancy."""

import pytest

from dnd.actions import Shove, commit_forced_movement
from dnd.content.items.environment_item_builders import build_directional_wall
from dnd.core.creature_types import DamageType
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import EventPhase, ForcedMovementEvent
from dnd.entity import Entity
from dnd.runtime_reset import reset_engine_runtime
from dnd.types.world import CardinalDirection
from tests.manual.spell_regression_support import create_spell_regression_actor


@pytest.fixture
def scene():
    reset_engine_runtime(grid_size=(9, 5))
    pusher = create_spell_regression_actor("Pusher", (2, 2), "heroes", strength=18)
    target = create_spell_regression_actor("Pushed", (3, 2), "heroes")
    yield pusher, target
    reset_engine_runtime()


def shove(pusher, target):
    Entity.update_all_entities_senses(max_distance=100)
    with fixed_dice_faces(*([2] * 64)):
        result = Shove(source_entity_uuid=pusher.uuid, target_entity_uuid=target.uuid).apply()
    assert result is not None and not result.canceled
    return result


@pytest.mark.parametrize("direct", [False, True], ids=["shove", "direct-commit"])
@pytest.mark.parametrize("faction", ["heroes", "enemies"])
@pytest.mark.parametrize("blocker_position", [(4, 2), (5, 2)], ids=["intermediate", "endpoint"])
def test_forced_steps_stop_before_a_blocking_creature(scene, direct, faction, blocker_position):
    pusher, target = scene
    if direct:
        planned_end, planned_distance, _, _ = Shove.calculate_final_position(
            target.position, (1, 0), 10, target.uuid,
        )
        assert planned_end == (5, 2) and planned_distance == 10
    blocker = create_spell_regression_actor("Blocker", blocker_position, faction)
    expected_end = (blocker_position[0] - 1, 2)
    expected_distance = (expected_end[0] - target.position[0]) * 5
    if direct:
        event = ForcedMovementEvent(
            source_entity_uuid=pusher.uuid, target_entity_uuid=target.uuid,
            start_position=target.position, end_position=planned_end, direction=(1, 0),
            intended_distance=10, actual_distance=planned_distance, cause="occupancy regression",
            phase=EventPhase.DECLARATION,
        ).phase_to(EventPhase.EXECUTION).phase_to(EventPhase.EFFECT)
        result = commit_forced_movement(target, event, parent_event=event)
        assert not result.canceled
        assert result.actual_distance == expected_distance
        assert result.end_position == expected_end
        assert result.blocked_by_obstacle
    else:
        result = shove(pusher, target)
        assert result.push_distance == expected_distance
        assert result.end_position == expected_end
    assert target.position == expected_end
    assert target.can_end_movement_at(target.position)
    assert blocker.position == blocker_position


@pytest.mark.parametrize("exception", ["dead", "nonblocking"])
def test_nonblocking_creatures_do_not_stop_the_push(scene, exception):
    pusher, target = scene
    occupant = create_spell_regression_actor("Nonblocking occupant", (4, 2), "heroes")
    if exception == "dead":
        occupant.receive_damage(10000, DamageType.FORCE, pusher.uuid)
    else:
        occupant.non_blocking = True
    result = shove(pusher, target)
    assert target.position == (5, 2)
    assert result.push_distance == 10


@pytest.mark.parametrize("side,expected_end", [
    (CardinalDirection.EAST, (4, 2)),
    (CardinalDirection.WEST, (3, 2)),
])
def test_a_boundary_wall_blocks_crossing_its_edge_not_occupying_its_tile(scene, side, expected_end):
    pusher, target = scene
    wall = build_directional_wall()
    wall.place_on_grid((4, 2), boundary_direction=side)
    result = shove(pusher, target)
    assert target.position == expected_end
    assert result.push_distance == (expected_end[0] - 3) * 5
