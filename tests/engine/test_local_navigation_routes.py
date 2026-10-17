"""Bounded movement choices depend on local terrain, not distant islands."""

from uuid import uuid4

import pytest

from dnd.core.aoe import Sphere
from dnd.core.base_block import MovementMode
from dnd.actions import Move
from dnd.blocks.base_item import BaseItem
from dnd.core.base_conditions import BaseCondition
from dnd.core.condition_types import HazardFilter
from dnd.core.events import EventPhase, EventQueue, StepMovementEvent
from dnd.core.base_tiles import difficult_terrain_factory
from dnd.core.gridmap import get_map
from dnd.items.environment import DirectionalWall
from dnd.runtime_reset import reset_engine_runtime
from dnd.reactions import add_opportunity_attack_handler
from dnd.types.world import CardinalDirection, WorldEdgeChannel
from tests.engine.test_grid_pathfinding import EntryCleanupZone, create_skeleton, reset_grid_state


def test_distant_rough_island_does_not_change_bounded_route_or_cost():
    reset_engine_runtime()
    try:
        grid = get_map()
        grid.create_rectangle(0, 0, 7, 7)
        for position, direction in (
            ((2, 4), 'north'), ((2, 1), 'south'), ((2, 0), 'south'),
            ((4, 0), 'south'), ((4, 0), 'east'), ((6, 3), 'south'),
            ((2, 5), 'south'), ((0, 2), 'north'), ((3, 5), 'south'),
            ((1, 2), 'west'), ((3, 0), 'north'), ((1, 4), 'south'),
        ):
            wall = DirectionalWall(item_id='test.local_navigation.wall',
                source_entity_uuid=uuid4(), blocked_channels=(WorldEdgeChannel.MOVEMENT,))
            wall.place_on_grid(position, boundary_direction=CardinalDirection(direction))
        before = grid.compute_paths((3, 3), max_distance=3)
        assert before[0][(2, 6)] == 3

        grid.set_tile(1000, 1000, tile=difficult_terrain_factory((1000, 1000)))
        after = grid.compute_paths((3, 3), max_distance=3)
        assert after == before
        assert all(grid.can_transition(source, target)
            for path in after[1].values() for source, target in zip(path, path[1:]))
    finally:
        reset_engine_runtime()


@pytest.mark.parametrize('budget', [-1, 0, 1, 2, 3, 4, None])
def test_budget_box_keeps_weighted_boundary_costs_and_negative_coordinates(budget):
    reset_engine_runtime()
    try:
        grid = get_map()
        grid.create_rectangle(-3, -2, 5, 1)
        grid.set_tile(-1, -2, tile=difficult_terrain_factory((-1, -2)))
        grid.remove_tile(1, -2)
        distances, paths = grid.compute_paths((-3, -2), max_distance=budget)
        expected = {(-3, -2): 0, (-2, -2): 1, (-1, -2): 3, (0, -2): 4}
        expected = {position: cost for position, cost in expected.items()
            if position == (-3, -2) or budget is None or cost <= budget}
        assert distances == expected
        assert set(paths) == set(expected)
        for position, path in paths.items():
            assert sum(grid.movement_cell_cost_units(step, MovementMode.WALKING)
                       for step in path[1:]) == distances[position]
    finally:
        reset_engine_runtime()


def test_local_fractional_expenditure_keeps_existing_distance_and_path_values():
    reset_engine_runtime()
    try:
        grid = get_map()
        grid.create_rectangle(-2, 0, 5, 1)
        zone = EntryCleanupZone(source_entity_uuid=uuid4(), position=(-1, 0),
            area=Sphere(radius_feet=0), adds_difficult_terrain=False,
            movement_expenditure_extra=0.5)
        assert zone.activate(parent_event=None) is not None
        assert grid.movement_cell_cost_units((-1, 0), MovementMode.WALKING) == 1.5
        reference_distances, reference_paths = grid.compute_paths((-2, 0))
        distances, paths = grid.compute_paths((-2, 0), max_distance=3)
        assert distances == {position: cost for position, cost in reference_distances.items()
                             if cost <= 3}
        assert paths == {position: reference_paths[position] for position in distances}
        # Keep the existing fractional solver boundary; this locality change
        # must not silently reinterpret stored distances or charged movement.
        assert distances[(0, 0)] == 2
        assert sum(grid.movement_cell_cost_units(step, MovementMode.WALKING)
                   for step in paths[(0, 0)][1:]) == 2.5
    finally:
        reset_engine_runtime()


@pytest.mark.parametrize('obstacle,straight', [
    ('none', True), ('old_path_hazard', True), ('hidden_hazard', True),
    ('visible_hazard', False), ('rough', False), ('blocked', False), ('reactor', False),
])
def test_native_route_prefers_fewer_turns_without_extra_cost_or_known_risk(obstacle, straight):
    reset_grid_state(width=7, height=5)
    try:
        grid = get_map()
        actor = create_skeleton(name='Walker', position=(3, 3), faction='heroes')
        for position in ((5, 3), (4, 2)) if obstacle == 'blocked' else ((5, 3),):
            item = BaseItem(item_id='test.local_navigation.boulder',
                source_entity_uuid=actor.uuid, blocks_movement=True, is_pickable=False)
            item.place_on_grid(position)
        if obstacle in ('old_path_hazard', 'hidden_hazard', 'visible_hazard'):
            position = (4, 3) if obstacle == 'old_path_hazard' else (4, 2)
            tile = grid.get_tile(*position)
            tile.add_condition(BaseCondition(name='Route hazard',
                source_entity_uuid=uuid4(), target_entity_uuid=tile.uuid,
                hazard_filter=HazardFilter.ALL,
                condition_stealth_dc=100 if obstacle == 'hidden_hazard' else None))
        if obstacle == 'rough':
            grid.set_tile(4, 2, tile=difficult_terrain_factory((4, 2)))
        if obstacle == 'reactor':
            reactor = create_skeleton(name='Known hostile', position=(3, 1), faction='monsters')
            add_opportunity_attack_handler(reactor)
            reactor.update_entity_senses(max_distance=8)
        actor.update_entity_senses(max_distance=8)
        expected = [(3, 3), (4, 2) if straight else (4, 3), (5, 2), (6, 2)]
        if obstacle == 'blocked':
            expected = [(3, 3), (4, 3), (5, 4), (6, 3), (6, 2)]
        expected_cost = (len(expected) - 1) * 5
        assert actor.senses.paths[(6, 2)] == expected
        assert actor.senses.path_costs[(6, 2)] == expected_cost
        row = next(row for row in actor.get_available_actions().position_actions
                   if row.template_name == 'Move')
        target = next(target for target in row.valid_targets if target.position == (6, 2))
        assert target.path == expected
        assert not target.is_path_hazardous
        assert not target.opportunity_attack_exposures
        cursor = EventQueue.event_cursor()
        before = actor.action_economy.movement_remaining()
        result = Move(source_entity_uuid=actor.uuid, end_position=(6, 2), prefer_safe=False).apply()
        assert result is not None and not result.canceled
        steps = [event for _, event in EventQueue.iter_events_since(cursor)
                 if isinstance(event, StepMovementEvent) and event.phase is EventPhase.COMPLETION
                 and event.source_entity_uuid == actor.uuid]
        assert [(step.from_position, step.to_position) for step in steps] == list(zip(expected, expected[1:]))
        assert actor.position == (6, 2)
        assert actor.action_economy.movement_remaining() == before - expected_cost
    finally:
        reset_engine_runtime()


def test_fractional_walking_route_is_not_reselected_for_fewer_turns():
    reset_grid_state(width=7, height=7)
    try:
        grid = get_map()
        actor = create_skeleton(name='Fractional walker', position=(3, 3), faction='heroes')
        for position in ((0, 0), (0, 2), (5, 6), (6, 1), (6, 6)):
            item = BaseItem(item_id='test.local_navigation.boulder',
                source_entity_uuid=actor.uuid, blocks_movement=True, is_pickable=False)
            item.place_on_grid(position)
        zone = EntryCleanupZone(source_entity_uuid=actor.uuid, position=(3, 3),
            area=Sphere(radius_feet=30), adds_difficult_terrain=False,
            movement_expenditure_extra=0.01, hazard_filter=HazardFilter.NON_SOURCE)
        assert zone.activate(parent_event=None) is not None
        actor.update_entity_senses(max_distance=8)
        _, reference = grid.compute_paths(actor.position, 6,
            requesting_entity_uuid=actor.uuid, subjective=True)
        destination = (0, 4)
        alternative = [(3, 3), (2, 4), (1, 4), destination]
        assert reference[destination] != alternative
        assert all(grid.can_transition(source, target, actor.uuid)
                   for source, target in zip(alternative, alternative[1:]))
        assert all(grid.movement_cell_cost_units(step, MovementMode.WALKING) == 1.01
                   for step in alternative[1:])
        row = next(row for row in actor.get_available_actions().position_actions
                   if row.template_name == 'Move')
        target = next(target for target in row.valid_targets if target.position == destination)
        assert actor.senses.paths[destination] == reference[destination]
        assert target.path == reference[destination]
        assert target.path_cost == 15
    finally:
        reset_engine_runtime()
