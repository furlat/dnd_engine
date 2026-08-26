"""Move/Swim/Fly and forced-displacement elevation rules."""

from uuid import UUID, uuid4

from dnd.actions.standard import (
    Move,
    MovementEvent,
    Shove,
)
from dnd.actions.operations import execute_available_action, get_available_actions
from dnd.core.events.action_events import (
    ShoveEvent,
)
from dnd.types.world import MovementMode
from dnd.core.events.events_registry import (
    Event,
    EventHandler,
    EventPhase,
    EventQueue,
    EventType,
    Trigger,
)
from dnd.core.events.world_events import (
    ForcedMovementEvent,
)
from dnd.core.gridmap import get_map
from dnd.core.world_edges import ElevationSurfaceKind, SlopeAxis
from dnd.entities.entity import Entity
from tests.engine.test_combat_actions import reset_core_action_state, strong_entity


def _mover() -> Entity:
    reset_core_action_state()
    mover = strong_entity("Mover", (0, 0), "heroes")
    Entity.materialize_all_navigation(max_distance=20)
    return mover


def _set_elevation(
    position: tuple[int, int],
    height: int,
    kind: ElevationSurfaceKind = ElevationSurfaceKind.ORDINARY,
    axis: SlopeAxis | None = None,
) -> None:
    get_map().set_tile_elevation(
        position,
        height=height,
        surface_kind=kind,
        slope_axis=axis,
    )


def test_walking_height_change_requires_both_matching_progressive_endpoints() -> None:
    _mover()
    grid = get_map()
    _set_elevation((0, 0), 0, ElevationSurfaceKind.STAIRS, SlopeAxis.EAST_WEST)
    _set_elevation((1, 0), 1, ElevationSurfaceKind.STAIRS, SlopeAxis.EAST_WEST)

    assert grid.can_transition((0, 0), (1, 0), movement_mode=MovementMode.WALKING)
    assert grid.can_transition((1, 0), (0, 0), movement_mode=MovementMode.WALKING)

    _set_elevation((1, 0), 1, ElevationSurfaceKind.RAMP, SlopeAxis.EAST_WEST)
    assert not grid.can_transition((0, 0), (1, 0), movement_mode=MovementMode.WALKING)
    _set_elevation((1, 0), 1, ElevationSurfaceKind.STAIRS, SlopeAxis.NORTH_SOUTH)
    assert not grid.can_transition((0, 0), (1, 0), movement_mode=MovementMode.WALKING)


def test_cliffs_block_walk_swim_burrow_and_forced_displacement_but_not_fly() -> None:
    mover = _mover()
    grid = get_map()
    _set_elevation((1, 0), 2)

    for mode in (
        MovementMode.WALKING,
        MovementMode.SWIMMING,
        MovementMode.BURROWING,
    ):
        assert not grid.can_transition((0, 0), (1, 0), mover.uuid, mode)
    assert grid.can_transition((0, 0), (1, 0), mover.uuid, MovementMode.FLYING)
    assert Shove.calculate_final_position((0, 0), (1, 0), 5, mover.uuid)[:3] == (
        (0, 0),
        0,
        True,
    )


def test_forced_movement_revalidates_each_leg_after_effect_topology_change() -> None:
    """A Shove cannot cross a cliff created during its accepted EFFECT."""
    reset_core_action_state()
    shover = strong_entity("Shove Source", (0, 0), "heroes", strength=18)
    target = strong_entity("Shove Target", (1, 0), "heroes", strength=10)
    Entity.materialize_all_navigation(max_distance=20)

    def raise_destination(event: Event, _source_uuid: UUID) -> Event:
        if type(event) is ForcedMovementEvent:
            _set_elevation((2, 0), 2)
        return event

    handler = EventHandler(
        name="Raise forced-movement destination",
        source_entity_uuid=uuid4(),
        trigger_conditions=[Trigger(
            event_type=EventType.FORCED_MOVEMENT,
            event_phase=EventPhase.EFFECT,
            event_target_entity_uuid=target.uuid,
        )],
        event_processor=raise_destination,
    )
    EventQueue.add_event_handler(handler)
    try:
        result = Shove(
            source_entity_uuid=shover.uuid,
            target_entity_uuid=target.uuid,
        ).apply()
    finally:
        EventQueue.remove_event_handler(handler)

    assert type(result) is ShoveEvent
    assert result.phase is EventPhase.COMPLETION
    assert result.push_distance == 0
    assert result.end_position == (1, 0)
    assert target.position == (1, 0)
    forced_completions = [
        event
        for event in EventQueue.get_events_by_type(EventType.FORCED_MOVEMENT)
        if type(event) is ForcedMovementEvent
        and event.phase is EventPhase.COMPLETION
    ]
    assert len(forced_completions) == 1
    assert forced_completions[0].end_position == (1, 0)
    assert forced_completions[0].actual_distance == 0
    assert forced_completions[0].blocked_by_obstacle is True


def test_diagonal_plateau_needs_one_height_legal_cardinal_bridge() -> None:
    _mover()
    grid = get_map()
    _set_elevation((0, 0), 1)
    _set_elevation((1, 1), 1)

    assert not grid.can_transition((0, 0), (1, 1), movement_mode=MovementMode.WALKING)
    _set_elevation((1, 0), 1)
    assert grid.can_transition((0, 0), (1, 1), movement_mode=MovementMode.WALKING)

    _set_elevation((1, 1), 2)
    assert not grid.can_transition((0, 0), (1, 1), movement_mode=MovementMode.WALKING)
    assert grid.can_transition((0, 0), (1, 1), movement_mode=MovementMode.FLYING)


def test_walking_like_diagonal_cannot_change_endpoint_elevation() -> None:
    mover = _mover()
    grid = get_map()
    _set_elevation((0, 0), 0, ElevationSurfaceKind.STAIRS, SlopeAxis.EAST_WEST)
    _set_elevation((1, 0), 1, ElevationSurfaceKind.STAIRS, SlopeAxis.EAST_WEST)
    _set_elevation((1, 1), 1, ElevationSurfaceKind.STAIRS, SlopeAxis.EAST_WEST)

    assert grid.can_transition((0, 0), (1, 0), mover.uuid, MovementMode.WALKING)
    assert grid.can_transition((1, 0), (1, 1), mover.uuid, MovementMode.WALKING)
    for mode in (
        MovementMode.WALKING,
        MovementMode.SWIMMING,
        MovementMode.BURROWING,
    ):
        assert not grid.can_transition((0, 0), (1, 1), mover.uuid, mode)
    assert grid.can_transition((0, 0), (1, 1), mover.uuid, MovementMode.FLYING)


def test_fly_path_and_move_settlement_use_one_support_distance_cost() -> None:
    mover = _mover()
    grid = get_map()
    _set_elevation((1, 0), 2)
    Entity.materialize_all_navigation(max_distance=20)

    distances, paths = grid.compute_paths(
        mover.position,
        requesting_entity_uuid=mover.uuid,
        movement_mode=MovementMode.FLYING,
        subjective=True,
    )
    assert distances[(1, 0)] == 2
    assert paths[(1, 0)] == [(0, 0), (1, 0)]

    result = Move(
        source_entity_uuid=mover.uuid,
        end_position=(1, 0),
        movement_mode=MovementMode.FLYING,
    ).apply()

    assert isinstance(result, MovementEvent)
    assert result.phase is EventPhase.COMPLETION
    assert mover.position == (1, 0)
    assert mover.action_economy.movement.normalized_score == 20
    assert [cost.cost for cost in result.costs if cost.cost_type == "movement"] == [10]
    assert result.combat_log is not None
    assert result.combat_log.data["movement_type"] == "move"
    assert result.combat_log.data["distance_feet"] == 10


def test_flying_discovery_uses_directed_edge_costs_and_affordability() -> None:
    mover = _mover()
    grid = get_map()
    _set_elevation((1, 0), 2)
    _set_elevation((2, 1), 2)
    mover.register_action(Move(
        source_entity_uuid=mover.uuid,
        movement_mode=MovementMode.FLYING,
        template=True,
    ))
    mover.action_economy.consume("movement", 20)
    assert mover.action_economy.movement.normalized_score == 10
    Entity.materialize_all_navigation(max_distance=20)
    available = get_available_actions(mover, legal_only=True)
    move_info = next(
        action for action in available.position_actions
        if action.template_name == "Move"
        and action.execution_template is not None
        and action.execution_template.movement_mode is MovementMode.FLYING
    )
    adjacent = next(target for target in move_info.valid_targets if target.position == (1, 0))
    assert adjacent.path_cost == 10
    assert all(target.position != (2, 1) for target in move_info.valid_targets)

    result = execute_available_action(mover, move_info, adjacent)
    assert isinstance(result, MovementEvent)
    assert result.phase is EventPhase.COMPLETION
    assert mover.position == adjacent.position


def test_progressive_walking_cost_uses_destination_terrain_not_vertical_distance() -> None:
    mover = _mover()
    _set_elevation((0, 0), 0, ElevationSurfaceKind.RAMP, SlopeAxis.EAST_WEST)
    _set_elevation((1, 0), 1, ElevationSurfaceKind.RAMP, SlopeAxis.EAST_WEST)
    Entity.materialize_all_navigation(max_distance=20)

    result = Move(
        source_entity_uuid=mover.uuid,
        end_position=(1, 0),
        movement_mode=MovementMode.WALKING,
    ).apply()

    assert isinstance(result, MovementEvent)
    assert result.phase is EventPhase.COMPLETION
    assert mover.position == (1, 0)
    assert mover.action_economy.movement.normalized_score == 25
    assert [cost.cost for cost in result.costs if cost.cost_type == "movement"] == [5]
