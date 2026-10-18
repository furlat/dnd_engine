"""Grid query answers after local writes equal a world that never answered before (plan P5).

The map keeps sight, propagation and path answers and drops only the ones a
write can change. Each case answers every query, applies one write, and
compares all answers with a world built directly in the resulting state, whose
answers are therefore computed from nothing.
"""

from dataclasses import dataclass
from typing import Callable, Dict, FrozenSet, List, Sequence, Tuple
from uuid import uuid4

from dnd.blocks.base_item import BaseItem
from dnd.core.gridmap import get_map
from dnd.core.base_tiles import tile_light_contributions
from dnd.entity import Entity
from dnd.items.environment import DirectionalWall
from dnd.types.world import CardinalDirection, WorldEdgeChannel
from tests.engine.test_grid_pathfinding import create_skeleton, reset_grid_state
from tests.engine.support import search_tables

Cell = Tuple[int, int]
WIDTH, HEIGHT = 24, 16
ORIGINS: Tuple[Cell, ...] = ((3, 3), (12, 8), (20, 12))
LIGHT: Cell = (11, 7)
ALL_CHANNELS = (WorldEdgeChannel.MOVEMENT, WorldEdgeChannel.OPTICAL, WorldEdgeChannel.PROPAGATION)


@dataclass(frozen=True)
class WorldState:
    """What differs between steps: pillars, wall tiles, a door, the walker's cell, a bystander's allegiance."""

    pillars: FrozenSet[Cell] = frozenset()
    walls: FrozenSet[Cell] = frozenset()
    door: bool = False
    walker: Cell = (8, 8)
    # The walker passes an ally's cell but not an enemy's.
    bystander: str = "heroes"


@dataclass(frozen=True)
class CacheCase:
    name: str
    # A permanent optical boundary far from every query keeps the directional solver on.
    directional: bool
    states: Sequence[WorldState]


def pillar(position: Cell) -> None:
    BaseItem(item_id='test.cache.pillar', source_entity_uuid=uuid4(), name="Pillar", is_pickable=False,
             blocks_optics_field=True, blocks_propagation_field=True, blocks_movement=True).place_on_grid(position)


def door() -> DirectionalWall:
    wall = DirectionalWall(item_id='test.cache.door', source_entity_uuid=uuid4(), name="Door",
                           blocked_channels=ALL_CHANNELS)
    wall.place_on_grid((12, 9), boundary_direction=CardinalDirection.EAST)
    return wall


def wall_tile(position: Cell) -> None:
    get_map().set_tile(*position, blocks_optics=True, blocks_propagation=True, walking_cost=0,
                       flying_cost=0, name="Wall")


def answers(walker: Entity) -> Dict[str, object]:
    grid = get_map()
    result: Dict[str, object] = {}
    for origin in ORIGINS:
        for radius in (6, None):
            result[f"fov {origin} {radius}"] = sorted(grid.compute_fov(origin, radius))
            result[f"propagation {origin} {radius}"] = sorted(grid.compute_propagation_fov(origin, radius))
        for distance in (8, None):
            distances, paths = search_tables(grid.compute_paths(origin, distance, requesting_entity_uuid=walker.uuid))
            result[f"paths {origin} {distance}"] = (distances, paths)
    result["lit"] = sorted(position for position, tile in grid.get_all_tiles().items()
                           if tile_light_contributions(tile)[0])
    return result


def build_world(case: CacheCase, state: WorldState) -> Tuple[Entity, Callable[[WorldState], None]]:
    """A world in ``state``; returns its walker and the write that moves it to another state."""
    reset_grid_state(width=WIDTH, height=HEIGHT)
    if case.directional:
        DirectionalWall(item_id='test.cache.far_wall', source_entity_uuid=uuid4(), name="Far Wall",
                        blocked_channels=(WorldEdgeChannel.OPTICAL,)).place_on_grid(
                            (0, 15), boundary_direction=CardinalDirection.SOUTH)
    walker = create_skeleton(name="Walker", position=state.walker, faction="heroes")
    bystander = create_skeleton(name="Bystander", position=(4, 3), faction=state.bystander)
    for position in state.pillars:
        pillar(position)
    for position in state.walls:
        wall_tile(position)
    doors: List[DirectionalWall] = [door()] if state.door else []
    get_map().add_light_source(LIGHT, 20, 20)
    current = [state]

    def write(target: WorldState) -> None:
        before = current[0]
        grid = get_map()
        for position in target.pillars - before.pillars:
            pillar(position)
        for position in before.pillars - target.pillars:
            grid.remove_object(next(iter(grid.get_center_objects_at(position))))
        for position in target.walls - before.walls:
            wall_tile(position)
        for position in before.walls - target.walls:
            grid.set_tile(*position)
        if target.door and not before.door:
            doors.append(door())
        if before.door and not target.door:
            grid.remove_object(doors.pop().uuid)
        if target.walker != before.walker:
            Entity.update_entity_position(walker, target.walker)
        if target.bystander != before.bystander:
            bystander.set_faction(target.bystander)
        current[0] = target

    return walker, write


def check(case: CacheCase) -> None:
    walker, write = build_world(case, case.states[0])
    answers(walker)
    observed: List[Dict[str, object]] = []
    for state in case.states[1:]:
        write(state)
        observed.append(answers(walker))
    for index, state in enumerate(case.states[1:]):
        cold_walker, _ = build_world(case, state)
        expected = answers(cold_walker)
        stale = [key for key in expected if observed[index][key] != expected[key]]
        assert not stale, (case.name, index + 1, state, stale[:6])


NEAR, EDGE, FAR = (6, 3), (19, 15), (18, 3)
STATES = (
    WorldState(),
    WorldState(pillars=frozenset({NEAR})),
    WorldState(pillars=frozenset({NEAR, EDGE})),
    WorldState(pillars=frozenset({NEAR, EDGE}), walls=frozenset({(10, 8)})),
    WorldState(pillars=frozenset({NEAR, EDGE}), walls=frozenset({(10, 8)}), door=True),
    WorldState(pillars=frozenset({NEAR, EDGE}), walls=frozenset({(10, 8)}), door=True, walker=(14, 8)),
    WorldState(pillars=frozenset({EDGE, FAR}), walls=frozenset({(10, 8)}), door=True, walker=(14, 8)),
    WorldState(pillars=frozenset({EDGE, FAR}), walls=frozenset({(10, 8)}), walker=(14, 8)),
    WorldState(pillars=frozenset({FAR}), walker=(14, 8)),
    WorldState(pillars=frozenset({FAR}), walker=(14, 8), bystander="monsters"),
    WorldState(pillars=frozenset({FAR}), walker=(14, 8)),
)


def test_cached_grid_answers_equal_a_world_that_never_answered() -> None:
    for case in (
        # The door is the only optical boundary: placing and removing it switches solvers.
        CacheCase("shadowcast, solver switch", directional=False, states=STATES),
        CacheCase("directional solver", directional=True, states=STATES),
    ):
        check(case)
