"""Tutorial tests for the grid, tiles, movement costs, and spatial events."""
from dnd.types.materials import Material, TileSurface

from uuid import uuid4

from dnd.content.items.environment_item_builders import build_directional_wall
from dnd.types.world import MovementMode
from dnd.types.world import CardinalDirection, WorldEdgeChannel
from dnd.core.base_tiles import Tile, difficult_terrain_factory
from dnd.core.events.events_registry import (
    EventPhase,
    EventQueue,
    EventType,
)
from dnd.core.events.world_events import (
    ForcedMovementEvent,
    SpatialChangeEvent,
    StepMovementEvent,
)
from dnd.core.gridmap import get_map
from dnd.entities.entity import Entity, EntityConfig
from dnd.runtime_reset import reset_engine_runtime
from tests.engine.support import create_test_entity


def reset_world_state() -> None:
    """Clear global state touched by these world-model examples."""
    reset_engine_runtime()


def test_first_world_example_prints_visible_corridor_costs(capsys) -> None:
    """One corridor prints bounds, terrain costs, route cost, and path."""
    reset_world_state()

    grid = get_map()
    grid.create_rectangle(0, 0, 5, 1, name="Stone Floor", surface=TileSurface(base_material=Material.STONE))
    difficult_tile = difficult_terrain_factory((2, 0))
    grid.set_tile(2, 0, tile=difficult_tile, fire_event=False)

    distances, paths = grid.compute_paths(
        (0, 0),
        movement_mode=MovementMode.WALKING,
    )
    easy_distances, _ = grid.compute_paths(
        (0, 0),
        movement_mode=MovementMode.WALKING,
        ignore_difficult_terrain=True,
    )
    path_text = " -> ".join(str(position) for position in paths[(4, 0)])
    readout_lines = [
        f"tile count: {grid.tile_count()}",
        f"bounds: {grid.bounds}",
        f"middle tile: {grid.get_tile(2, 0).name}",
        f"walking cost at middle: {difficult_tile.get_movement_cost(MovementMode.WALKING)}",
        f"flying cost at middle: {difficult_tile.get_movement_cost(MovementMode.FLYING)}",
        f"walking route cost: {distances[(4, 0)]}",
        f"ignore-terrain route cost: {easy_distances[(4, 0)]}",
        f"path: {path_text}",
    ]

    print("\n".join(readout_lines))

    expected_lines = [
        "tile count: 5",
        "bounds: (0, 0, 4, 0)",
        "middle tile: Difficult Terrain",
        "walking cost at middle: 2",
        "flying cost at middle: 1",
        "walking route cost: 5",
        "ignore-terrain route cost: 4",
        "path: (0, 0) -> (1, 0) -> (2, 0) -> (3, 0) -> (4, 0)",
    ]
    assert readout_lines == expected_lines
    assert grid.get_tile_by_uuid(difficult_tile.uuid) is difficult_tile
    assert capsys.readouterr().out.splitlines() == expected_lines


def test_grid_tiles_have_bounds_lookup_and_movement_costs(capsys) -> None:
    """GridMap stores tiles by position and uses tile costs for pathfinding."""
    reset_world_state()
    grid = get_map()

    grid.create_rectangle(0, 0, 5, 1, name="Stone Floor", surface=TileSurface(base_material=Material.STONE))
    difficult_tile = difficult_terrain_factory((2, 0))
    grid.set_tile(2, 0, tile=difficult_tile, fire_event=False)

    assert grid.tile_count() == 5
    assert grid.bounds == (0, 0, 4, 0)
    assert grid.get_tile(0, 0).name == "Stone Floor"
    assert grid.get_tile(2, 0) is difficult_tile
    assert grid.get_tile_by_uuid(difficult_tile.uuid) is difficult_tile

    assert difficult_tile.get_movement_cost(MovementMode.WALKING) == 2
    assert difficult_tile.get_movement_cost(MovementMode.FLYING) == 1

    distances, paths = grid.compute_paths((0, 0), movement_mode=MovementMode.WALKING)
    assert distances[(4, 0)] == 5
    assert paths[(4, 0)] == [(0, 0), (1, 0), (2, 0), (3, 0), (4, 0)]

    easier_distances, _ = grid.compute_paths(
        (0, 0),
        movement_mode=MovementMode.WALKING,
        ignore_difficult_terrain=True,
    )
    assert easier_distances[(4, 0)] == 4
    path_text = " -> ".join(str(position) for position in paths[(4, 0)])

    terrain_lines = [
        f"tile count: {grid.tile_count()}",
        f"bounds: {grid.bounds}",
        f"start tile: {grid.get_tile(0, 0).name}",
        f"middle tile lookup: {grid.get_tile(2, 0) is difficult_tile}",
        f"walking cost at middle: {difficult_tile.get_movement_cost(MovementMode.WALKING)}",
        f"flying cost at middle: {difficult_tile.get_movement_cost(MovementMode.FLYING)}",
        f"walking route cost: {distances[(4, 0)]}",
        f"ignore-terrain route cost: {easier_distances[(4, 0)]}",
        f"path: {path_text}",
    ]

    print("\n".join(terrain_lines))

    expected_terrain_lines = [
        "tile count: 5",
        "bounds: (0, 0, 4, 0)",
        "start tile: Stone Floor",
        "middle tile lookup: True",
        "walking cost at middle: 2",
        "flying cost at middle: 1",
        "walking route cost: 5",
        "ignore-terrain route cost: 4",
        "path: (0, 0) -> (1, 0) -> (2, 0) -> (3, 0) -> (4, 0)",
    ]
    assert terrain_lines == expected_terrain_lines
    assert capsys.readouterr().out.splitlines() == expected_terrain_lines


def test_directional_border_blocks_transition_and_emits_tile_change(capsys) -> None:
    """Directional tile borders can block movement between adjacent cells."""
    reset_world_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 2, 1, surface=TileSurface(base_material=Material.STONE))

    before_passable = grid.can_transition(
        (0, 0),
        (1, 0),
        movement_mode=MovementMode.WALKING,
    )
    assert before_passable

    wall = build_directional_wall(
        display_name="Tutorial East Wall",
        blocked_channels=(WorldEdgeChannel.MOVEMENT,),
    )
    event_cursor = EventQueue.event_cursor()
    placement = grid.place_object(
        wall.uuid,
        (0, 0),
        boundary_direction=CardinalDirection.EAST,
    )
    after_passable = grid.can_transition(
        (0, 0),
        (1, 0),
        movement_mode=MovementMode.WALKING,
    )

    assert not after_passable

    tile_change_completions = [
        event
        for _, event in EventQueue.iter_events_since(event_cursor)
        if event.event_type is EventType.SPATIAL_OBJECT_PLACED
        if event.phase == EventPhase.COMPLETION
    ]
    assert len(tile_change_completions) == 1
    placement_event = tile_change_completions[0]
    assert placement_event.object_uuid == wall.uuid
    assert placement_event.placement == placement
    assert placement_event.placement.boundary_direction is CardinalDirection.EAST
    assert placement_event.object_boundary_structure is not None
    assert placement_event.object_boundary_structure.blocked_channels == (
        WorldEdgeChannel.MOVEMENT,
    )

    border_lines = [
        f"transition before border: {before_passable}",
        "object placed: True",
        f"transition after border: {after_passable}",
        f"object-placement completions: {len(tile_change_completions)}",
        f"placed position: {placement_event.position}",
        f"boundary direction: {placement_event.placement.boundary_direction.value}",
        f"channels: {[channel.value for channel in placement_event.object_boundary_structure.blocked_channels]}",
    ]

    print("\n".join(border_lines))

    expected_border_lines = [
        "transition before border: True",
        "object placed: True",
        "transition after border: False",
        "object-placement completions: 1",
        "placed position: (0, 0)",
        "boundary direction: east",
        "channels: ['movement']",
    ]
    assert border_lines == expected_border_lines
    assert capsys.readouterr().out.splitlines() == expected_border_lines


def test_entity_position_index_and_spatial_events_follow_grid_moves(capsys) -> None:
    """GridMap tracks entity positions and emits enter/leave spatial events."""
    reset_world_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 3, 1, surface=TileSurface(base_material=Material.STONE))
    actor = create_test_entity(
        name="World model actor",
        config=EntityConfig(position=(0, 0), faction="heroes"),
    )
    actor_id = actor.uuid

    assert grid.get_entity_position(actor_id) == (0, 0)
    assert grid.get_entities_at((0, 0)) == {actor_id}
    initial_position = grid.get_entity_position(actor_id)
    initial_cell_count = len(grid.get_entities_at((0, 0)))

    step_event = StepMovementEvent(
        source_entity_uuid=actor_id,
        from_position=(0, 0),
        to_position=(1, 0),
        path_index=1,
        total_path_length=2,
        phase=EventPhase.EFFECT,
    )
    Entity.update_entity_position(actor, (1, 0), parent_event=step_event.uuid)

    assert grid.get_entity_position(actor_id) == (1, 0)
    assert grid.get_entities_at((0, 0)) == set()
    assert grid.get_entities_at((1, 0)) == {actor_id}
    final_position = grid.get_entity_position(actor_id)
    old_cell_count = len(grid.get_entities_at((0, 0)))
    new_cell_count = len(grid.get_entities_at((1, 0)))

    left_completions = [
        event
        for event in EventQueue.get_events_by_type(EventType.SPATIAL_ENTITY_LEFT)
        if event.phase == EventPhase.COMPLETION
    ]
    entered_completions = [
        event
        for event in EventQueue.get_events_by_type(EventType.SPATIAL_ENTITY_ENTERED)
        if event.phase == EventPhase.COMPLETION
    ]

    movement_left = left_completions[-1]
    movement_entered = entered_completions[-1]

    assert movement_left.position == (0, 0)
    assert movement_left.old_position == (1, 0)
    assert movement_left.parent_lineage == step_event.lineage_uuid

    assert movement_entered.position == (1, 0)
    assert movement_entered.old_position == (0, 0)
    assert movement_entered.parent_lineage == step_event.lineage_uuid

    movement_lines = [
        f"initial position: {initial_position}",
        f"initial cell count: {initial_cell_count}",
        f"final position: {final_position}",
        f"old cell count after move: {old_cell_count}",
        f"new cell count after move: {new_cell_count}",
        f"left event: position={movement_left.position}, old={movement_left.old_position}",
        f"entered event: position={movement_entered.position}, old={movement_entered.old_position}",
        (
            "spatial parent lineage matches step: "
            f"{movement_entered.parent_lineage == step_event.lineage_uuid}"
        ),
    ]

    print("\n".join(movement_lines))

    expected_movement_lines = [
        "initial position: (0, 0)",
        "initial cell count: 1",
        "final position: (1, 0)",
        "old cell count after move: 0",
        "new cell count after move: 1",
        "left event: position=(0, 0), old=(1, 0)",
        "entered event: position=(1, 0), old=(0, 0)",
        "spatial parent lineage matches step: True",
    ]
    assert movement_lines == expected_movement_lines
    assert capsys.readouterr().out.splitlines() == expected_movement_lines


def test_forced_movement_is_a_distinct_event_that_can_parent_spatial_updates(capsys) -> None:
    """Forced displacement is distinct from voluntary step movement."""
    reset_world_state()
    grid = get_map()
    grid.create_rectangle(0, 0, 5, 1, surface=TileSurface(base_material=Material.STONE))
    shover_id = uuid4()
    target = create_test_entity(
        name="Forced movement target",
        config=EntityConfig(position=(1, 0), faction="neutral"),
    )
    target_id = target.uuid

    forced_event = ForcedMovementEvent(
        source_entity_uuid=shover_id,
        target_entity_uuid=target_id,
        start_position=(1, 0),
        end_position=(3, 0),
        direction=(1, 0),
        intended_distance=10,
        actual_distance=10,
        cause="tutorial shove",
        phase=EventPhase.EFFECT,
    )
    Entity.update_entity_position(target, (3, 0), parent_event=forced_event.uuid)

    assert forced_event.event_type == EventType.FORCED_MOVEMENT
    assert grid.get_entity_position(target_id) == (3, 0)
    forced_log = forced_event.generate_combat_log()
    assert "(1, 0) \u2192 (3, 0)" in forced_log.verbose

    forced_entered = [
        event
        for event in EventQueue.get_events_by_type(EventType.SPATIAL_ENTITY_ENTERED)
        if event.phase == EventPhase.COMPLETION and event.position == (3, 0)
    ][-1]

    assert forced_entered.old_position == (1, 0)
    assert forced_entered.parent_lineage == forced_event.lineage_uuid

    forced_lines = [
        f"forced event type: {forced_event.event_type.value}",
        f"target final position: {grid.get_entity_position(target_id)}",
        f"forced distance: {forced_event.actual_distance}",
        f"spatial entered position: {forced_entered.position}",
        f"spatial entered old position: {forced_entered.old_position}",
        (
            "spatial parent lineage matches forced movement: "
            f"{forced_entered.parent_lineage == forced_event.lineage_uuid}"
        ),
    ]

    print("\n".join(forced_lines))

    expected_forced_lines = [
        "forced event type: forced_movement",
        "target final position: (3, 0)",
        "forced distance: 10",
        "spatial entered position: (3, 0)",
        "spatial entered old position: (1, 0)",
        "spatial parent lineage matches forced movement: True",
    ]
    assert forced_lines == expected_forced_lines
    assert capsys.readouterr().out.splitlines() == expected_forced_lines


def test_batch_tile_creation_does_not_emit_tile_change_events(capsys) -> None:
    """Rectangular map creation populates tiles without noisy per-tile events."""
    reset_world_state()
    grid = get_map()

    grid.create_rectangle(0, 0, 3, 2, surface=TileSurface(base_material=Material.STONE))

    assert grid.tile_count() == 6
    assert EventQueue.get_events_by_type(EventType.SPATIAL_TILE_CHANGED) == []
    setup_tile_changes = EventQueue.get_events_by_type(EventType.SPATIAL_TILE_CHANGED)

    grid.set_tile(
        1,
        1,
        surface=TileSurface(base_material=Material.STONE),
        walking_cost=0,
        blocks_optics=True,
        blocks_propagation=True,
        name="Wall",
    )

    tile_change_completions = [
        event
        for event in EventQueue.get_events_by_type(EventType.SPATIAL_TILE_CHANGED)
        if event.phase == EventPhase.COMPLETION
    ]
    assert len(tile_change_completions) == 1
    assert tile_change_completions[0].position == (1, 1)
    changed_tile = grid.get_tile(1, 1)

    batch_lines = [
        f"tile count after rectangle: {grid.tile_count()}",
        f"tile-change events during rectangle: {len(setup_tile_changes)}",
        f"tile-change completions after edit: {len(tile_change_completions)}",
        f"changed tile position: {tile_change_completions[0].position}",
        f"changed tile name: {changed_tile.name}",
        f"changed tile walking cost: {changed_tile.get_movement_cost(MovementMode.WALKING)}",
    ]

    print("\n".join(batch_lines))

    expected_batch_lines = [
        "tile count after rectangle: 6",
        "tile-change events during rectangle: 0",
        "tile-change completions after edit: 1",
        "changed tile position: (1, 1)",
        "changed tile name: Wall",
        "changed tile walking cost: 0",
    ]
    assert batch_lines == expected_batch_lines
    assert capsys.readouterr().out.splitlines() == expected_batch_lines
