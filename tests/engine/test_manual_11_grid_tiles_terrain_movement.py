"""Focused checks for grid, tiles, terrain, and movement."""
from dnd.types.materials import Material, TileSurface

from typing import Optional
from uuid import uuid4

from dnd.actions.standard import (
    Move,
    Shove,
)
from dnd.content.items.environment_item_builders import build_directional_wall
from dnd.core.events.action_events import (
    ShoveEvent,
)
from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig
from dnd.blocks.action_economy import ActionEconomyConfig
from dnd.core.base_block import BaseBlock
from dnd.types.world import CardinalDirection, MovementMode, WorldEdgeChannel
from dnd.core.base_object import BaseObject
from dnd.core.base_tiles import difficult_terrain_factory, floor_factory, water_factory
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
    SpatialChangeEvent,
    StepMovementEvent,
)
from dnd.core.gridmap import get_map
from dnd.core.modifiers import NumericalModifier
from dnd.core.values import BaseValue
from dnd.entities.entity import Entity, EntityConfig
from tests.engine.support import create_test_entity, reset_combat_state


def reset_world_state(width: int = 8, height: int = 8) -> None:
    """Clear global state and create a rectangular floor arena."""
    reset_combat_state()
    BaseObject._registry.clear()
    BaseValue._registry.clear()
    BaseBlock._registry.clear()
    get_map().create_rectangle(0, 0, width, height, surface=TileSurface(base_material=Material.STONE))


def create_world_actor(
    name: str,
    position: tuple[int, int],
    faction: Optional[str],
    strength: int = 14,
) -> Entity:
    """Create an actor with stable movement and Strength for world examples."""
    actor_id = uuid4()
    return create_test_entity(
        source_id=actor_id,
        name=name,
        config=EntityConfig(
            ability_scores=AbilityScoresConfig(
                strength=AbilityConfig(ability_score=strength),
                dexterity=AbilityConfig(ability_score=14),
                constitution=AbilityConfig(ability_score=12),
                intelligence=AbilityConfig(ability_score=10),
                wisdom=AbilityConfig(ability_score=12),
                charisma=AbilityConfig(ability_score=10),
            ),
            action_economy=ActionEconomyConfig(movement=30),
            proficiency_bonus=2,
            position=position,
            faction=faction,
        ),
        entity_kind_id="test.world_actor",
    )


def test_tiles_are_blocks_and_costs_define_passability() -> None:
    """Tiles are grid-owned blocks whose movement costs define passability."""
    reset_world_state(width=4, height=1)
    grid = get_map()

    floor = grid.set_tile(0, 0, tile=floor_factory((0, 0)))
    water = grid.set_tile(1, 0, tile=water_factory((1, 0)))
    difficult = grid.set_tile(2, 0, tile=difficult_terrain_factory((2, 0)))

    assert grid.get_tile(0, 0) is floor
    assert grid.get_tile_by_uuid(floor.uuid) is floor
    assert floor.get_movement_cost(MovementMode.WALKING) == 1
    assert floor.get_movement_cost(MovementMode.FLYING) == 1
    assert floor.get_movement_cost(MovementMode.SWIMMING) == 0

    assert water.get_movement_cost(MovementMode.WALKING) == 0
    assert water.get_movement_cost(MovementMode.SWIMMING) == 1
    assert not grid.is_walkable(1, 0, MovementMode.WALKING)
    assert grid.is_walkable(1, 0, MovementMode.SWIMMING)

    assert difficult.get_movement_cost(MovementMode.WALKING) == 2
    assert grid.is_walkable(2, 0, MovementMode.WALKING)


def test_paths_price_destination_tiles_and_directional_borders() -> None:
    """Dijkstra path costs come from entered tiles and crossing rules."""
    reset_world_state(width=5, height=1)
    grid = get_map()
    difficult_tile = grid.get_tile(2, 0)
    assert difficult_tile is not None
    difficult_tile.walking_cost.self_static.add_value_modifier(
        NumericalModifier.create(
            source_entity_uuid=difficult_tile.uuid,
            name="Mud",
            value=1,
        )
    )

    distances, paths = grid.compute_paths((0, 0), movement_mode=MovementMode.WALKING)

    assert distances[(1, 0)] == 1
    assert distances[(2, 0)] == 3
    assert distances[(4, 0)] == 5
    assert paths[(4, 0)] == [(0, 0), (1, 0), (2, 0), (3, 0), (4, 0)]

    wall = build_directional_wall(
        blocked_channels=(WorldEdgeChannel.MOVEMENT,),
    )
    grid.place_object(
        wall.uuid,
        (1, 0),
        boundary_direction=CardinalDirection.EAST,
    )
    blocked_distances, blocked_paths = grid.compute_paths(
        (0, 0),
        movement_mode=MovementMode.WALKING,
    )

    assert not grid.can_transition((1, 0), (2, 0))
    assert (2, 0) not in blocked_distances
    assert (4, 0) not in blocked_paths


def test_entity_position_updates_class_registry_grid_registry_and_spatial_events() -> None:
    """Entity movement keeps entity indexes, grid indexes, and spatial events together."""
    reset_world_state(width=4, height=4)
    grid = get_map()
    hero = create_world_actor("Hero", (1, 1), "heroes")
    cursor = EventQueue.event_cursor()

    Entity.update_entity_position(hero, (2, 2))

    events = [event for _, event in EventQueue.iter_events_since(cursor)]
    entered_positions = [
        event.position
        for event in events
        if isinstance(event, SpatialChangeEvent)
        and event.event_type == EventType.SPATIAL_ENTITY_ENTERED
        and event.phase == EventPhase.EFFECT
        and event.entity_uuid == hero.uuid
    ]

    assert hero.position == (2, 2)
    assert hero.senses.position == (2, 2)
    assert hero.uuid not in get_map().get_entities_at((1, 1))
    assert hero.uuid in get_map().get_entities_at((2, 2))
    assert hero.uuid not in grid.get_entities_at((1, 1))
    assert hero.uuid in grid.get_entities_at((2, 2))
    assert entered_positions == [(2, 2)]


def test_voluntary_move_walks_cell_by_cell_and_spends_movement() -> None:
    """The Move action emits step movement and spends movement per entered cell."""
    reset_world_state(width=5, height=1)
    hero = create_world_actor("Hero", (0, 0), "heroes")
    Entity.materialize_all_navigation(max_distance=20)
    cursor = EventQueue.event_cursor()
    movement_before = hero.action_economy.movement.normalized_score

    event = Move(source_entity_uuid=hero.uuid, end_position=(3, 0)).apply()

    events = [event for _, event in EventQueue.iter_events_since(cursor)]
    step_events = [
        event
        for event in events
        if isinstance(event, StepMovementEvent)
        and event.phase == EventPhase.EFFECT
    ]

    assert event is not None
    assert not event.canceled
    assert hero.position == (3, 0)
    assert hero.action_economy.movement.normalized_score == movement_before - 15
    assert [(step.from_position, step.to_position) for step in step_events] == [
        ((0, 0), (1, 0)),
        ((1, 0), (2, 0)),
        ((2, 0), (3, 0)),
    ]


def test_forced_movement_uses_forced_event_spatial_entries_and_no_step_events() -> None:
    """Shove displacement uses forced movement, spatial entries, and no movement budget."""
    reset_world_state(width=7, height=1)
    shover = create_world_actor("Shove Tutor", (0, 0), "heroes", strength=18)
    target = create_world_actor("Practice Ally", (1, 0), "heroes", strength=10)
    Entity.materialize_all_navigation(max_distance=20)
    cursor = EventQueue.event_cursor()
    target_movement_before = target.action_economy.movement.normalized_score

    shove_event = Shove(
        source_entity_uuid=shover.uuid,
        target_entity_uuid=target.uuid,
    ).apply()

    events = [event for _, event in EventQueue.iter_events_since(cursor)]
    forced_completions = [
        event
        for event in events
        if isinstance(event, ForcedMovementEvent)
        and event.phase == EventPhase.COMPLETION
    ]
    entered_positions = [
        event.position
        for event in events
        if isinstance(event, SpatialChangeEvent)
        and event.event_type == EventType.SPATIAL_ENTITY_ENTERED
        and event.phase == EventPhase.EFFECT
        and event.entity_uuid == target.uuid
    ]

    assert isinstance(shove_event, ShoveEvent)
    assert shove_event.push_distance == 10
    assert shove_event.end_position == (3, 0)
    assert target.position == (3, 0)
    assert target.action_economy.movement.normalized_score == target_movement_before

    assert len(forced_completions) == 1
    assert forced_completions[0].event_type == EventType.FORCED_MOVEMENT
    assert forced_completions[0].actual_distance == 10
    assert not any(event.event_type == EventType.STEP_MOVEMENT for event in events)
    assert entered_positions == [(2, 0), (3, 0)]


def test_step_handlers_see_voluntary_movement_not_forced_movement() -> None:
    """Step-movement reactions attach to voluntary movement, not forced displacement."""
    reset_world_state(width=5, height=1)
    hero = create_world_actor("Hero", (0, 0), "heroes")
    seen_steps: list[tuple[tuple[int, int], tuple[int, int]]] = []

    def record_step(event: Event, _source_uuid) -> Event:
        assert isinstance(event, StepMovementEvent)
        seen_steps.append((event.from_position, event.to_position))
        return event

    hero.add_event_handler(
        EventHandler(
            name="Tutorial Step Recorder",
            source_entity_uuid=hero.uuid,
            trigger_conditions=[
                Trigger(
                    name="Record Step Movement",
                    event_type=EventType.STEP_MOVEMENT,
                    event_phase=EventPhase.EFFECT,
                )
            ],
            event_processor=record_step,
        )
    )
    Entity.materialize_all_navigation(max_distance=20)

    Move(source_entity_uuid=hero.uuid, end_position=(2, 0)).apply()

    assert seen_steps == [((0, 0), (1, 0)), ((1, 0), (2, 0))]

    reset_world_state(width=7, height=1)
    shover = create_world_actor("Shove Tutor", (0, 0), "heroes", strength=18)
    target = create_world_actor("Practice Ally", (1, 0), "heroes")
    forced_steps: list[tuple[tuple[int, int], tuple[int, int]]] = []

    def record_forced_step(event: Event, _source_uuid) -> Event:
        assert isinstance(event, StepMovementEvent)
        forced_steps.append((event.from_position, event.to_position))
        return event

    shover.add_event_handler(
        EventHandler(
            name="Forced Movement Step Recorder",
            source_entity_uuid=shover.uuid,
            trigger_conditions=[
                Trigger(
                    name="Record Forced Step Movement",
                    event_type=EventType.STEP_MOVEMENT,
                    event_phase=EventPhase.EFFECT,
                )
            ],
            event_processor=record_forced_step,
        )
    )
    Entity.materialize_all_navigation(max_distance=20)

    Shove(source_entity_uuid=shover.uuid, target_entity_uuid=target.uuid).apply()

    assert target.position == (3, 0)
    assert forced_steps == []
