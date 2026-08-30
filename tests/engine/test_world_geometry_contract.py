"""Public cold geometry and directed-elevation contracts."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from dnd.core.base_block import BaseBlock
from dnd.core.base_tiles import Tile
from dnd.core.events import (
    Event,
    EventHandler,
    EventPhase,
    EventQueue,
    EventType,
    SpatialChangeEvent,
    TileElevationChangeEvent,
    Trigger,
)
from dnd.core.gridmap import GridMap
from dnd.core.world_edges import (
    AdjacentEdgeKey,
    ElevationSurfaceKind,
    SlopeAxis,
    contradictory_progressive_elevation_edge,
    progressive_elevation_transition,
)
from dnd.types.materials import Material, SurfaceLayer, TileSurface
from dnd.types.world import CardinalDirection, MovementMode
from dnd.types.world_placement import (
    BoundaryStructure,
    BoundaryStructureKind,
    WorldObjectPlacement,
    WorldPlacementKind,
    WorldPlacementSpec,
)
from dnd.types.world import WorldEdgeChannel
from dnd.items.environment import DirectionalDoor
from tests.engine.support import reset_combat_state


class OccupyingBoundaryBlock(BaseBlock):
    """Small public provider used to prove exact Tile-side placement."""

    def get_world_placement_spec(self) -> WorldPlacementSpec:
        return WorldPlacementSpec(
            kind=WorldPlacementKind.BOUNDARY,
            occupies_bands=True,
            vertical_extent_steps=2,
        )


class StructuralBoundaryBlock(OccupyingBoundaryBlock):
    """Boundary provider with explicit current structural channels."""

    blocked_channels: tuple[WorldEdgeChannel, ...] = ()

    def get_boundary_structure(self) -> BoundaryStructure:
        return BoundaryStructure(
            structure=BoundaryStructureKind.WALL,
            material=Material.STONE,
            blocked_channels=self.blocked_channels,
        )


def _two_tile_grid() -> GridMap:
    reset_combat_state()
    grid = GridMap.get_instance()
    for position in ((0, 0), (1, 0)):
        grid.set_tile(
            *position,
            tile=Tile.create(
                position,
                surface=TileSurface(base_material=Material.STONE),
            ),
        )
    return grid


def test_surface_round_trip_preserves_ordered_repeated_layers() -> None:
    surface = TileSurface(
        base_material=Material.STONE,
        layers=(
            SurfaceLayer(material=Material.WOOD, description="boards"),
            SurfaceLayer(material=Material.WOOD, description="debris"),
        ),
    )

    assert TileSurface.model_validate_json(surface.model_dump_json()) == surface
    assert [layer.description for layer in surface.layers] == [
        "boards",
        "debris",
    ]


def test_world_placement_is_strict_and_keeps_side_separate_from_facing() -> None:
    placement = WorldObjectPlacement(
        object_uuid=uuid4(),
        tile_uuid=uuid4(),
        position=(2, 3),
        kind=WorldPlacementKind.BOUNDARY,
        occupies_bands=True,
        boundary_direction=CardinalDirection.EAST,
        base_height_steps=1,
        top_height_steps=3,
    )

    assert placement.boundary_direction is CardinalDirection.EAST
    assert placement.orientation is None
    assert WorldObjectPlacement.model_validate_json(
        placement.model_dump_json()
    ) == placement

    with pytest.raises(ValidationError):
        WorldObjectPlacement.model_validate(
            {
                **placement.model_dump(),
                "base_height_steps": True,
            }
        )


def test_adjacent_edge_identity_is_canonical_but_transition_is_directed() -> None:
    assert AdjacentEdgeKey.between((1, 2), (2, 2)) == AdjacentEdgeKey.between(
        (2, 2),
        (1, 2),
    )
    with pytest.raises(ValueError):
        AdjacentEdgeKey.between((1, 1), (2, 2))
    with pytest.raises(TypeError):
        AdjacentEdgeKey.between((True, 1), (1, 1))


def test_progressive_elevation_requires_matching_both_endpoint_surfaces() -> None:
    assert progressive_elevation_transition(
        0,
        ElevationSurfaceKind.RAMP,
        SlopeAxis.EAST_WEST,
        1,
        ElevationSurfaceKind.RAMP,
        SlopeAxis.EAST_WEST,
        SlopeAxis.EAST_WEST,
    )
    assert not progressive_elevation_transition(
        0,
        ElevationSurfaceKind.RAMP,
        SlopeAxis.EAST_WEST,
        1,
        ElevationSurfaceKind.ORDINARY,
        None,
        SlopeAxis.EAST_WEST,
    )
    assert contradictory_progressive_elevation_edge(
        {
            (0, 0): (
                0,
                ElevationSurfaceKind.RAMP,
                SlopeAxis.EAST_WEST,
            ),
            (1, 0): (1, ElevationSurfaceKind.ORDINARY, None),
        }
    ) == ((0, 0), (1, 0))


def test_tile_stores_one_strict_surface_elevation_and_four_costs() -> None:
    surface = TileSurface(base_material=Material.EARTH)
    tile = Tile.create(
        (4, 5),
        surface=surface,
        walking_cost=2,
        flying_cost=1,
        swimming_cost=0,
        burrowing_cost=3,
        height=-2,
        elevation_surface_kind=ElevationSurfaceKind.STAIRS,
        slope_axis=SlopeAxis.NORTH_SOUTH,
    )

    assert tile.surface == surface
    assert tile.height == -2
    assert tile.walking_cost.normalized_score == 2
    assert tile.flying_cost.normalized_score == 1
    assert tile.swimming_cost.normalized_score == 0
    assert tile.burrowing_cost.normalized_score == 3
    tile_dump = tile.model_dump()
    assert "walkable" not in tile_dump
    assert not {
        "border_north",
        "border_south",
        "border_east",
        "border_west",
        "object_movement_border_north",
        "object_movement_border_south",
        "object_movement_border_east",
        "object_movement_border_west",
    } & tile_dump.keys()

    with pytest.raises((TypeError, ValidationError)):
        Tile.create((0, 0), surface=surface, height=True)
    with pytest.raises((ValueError, ValidationError)):
        Tile.create((0, 0), surface=surface, walking_cost=True)
    with pytest.raises((ValueError, ValidationError)):
        Tile.create((0, 0), surface=surface, flying_cost=-1)
    with pytest.raises((ValueError, ValidationError)):
        Tile.create(
            (0, 0),
            surface=surface,
            height=1,
            elevation_surface_kind=ElevationSurfaceKind.RAMP,
        )


def test_tile_replacement_publishes_complete_cost_after_values() -> None:
    grid = _two_tile_grid()
    cursor = EventQueue.event_cursor()
    replacement = Tile.create(
        (1, 0),
        surface=TileSurface(base_material=Material.WATER),
        walking_cost=0,
        flying_cost=1,
        swimming_cost=1,
        burrowing_cost=0,
    )

    grid.set_tile(1, 0, tile=replacement)

    completion = next(
        event
        for _, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, SpatialChangeEvent)
        and event.event_type is EventType.SPATIAL_TILE_CHANGED
        and event.phase is EventPhase.COMPLETION
        and event.position == (1, 0)
    )
    assert (
        completion.tile_walking_cost,
        completion.tile_flying_cost,
        completion.tile_swimming_cost,
        completion.tile_burrowing_cost,
    ) == (0, 1, 1, 0)
    assert "tile_walkable" not in completion.model_dump()
    with pytest.raises(ValidationError):
        SpatialChangeEvent.tile_changed(
            (0, 0),
            tile_walking_cost=True,
        )


def test_movement_edge_cost_uses_destination_policy_and_flying_height() -> None:
    grid = _two_tile_grid()
    grid.set_tile_elevation(
        (1, 0),
        height=2,
        surface_kind=ElevationSurfaceKind.ORDINARY,
        slope_axis=None,
    )

    assert grid.get_support_elevation_feet((0, 0)) == 0
    assert grid.get_support_elevation_feet((1, 0)) == 10
    assert grid.movement_edge_cost_units(
        (0, 0),
        (1, 0),
        MovementMode.FLYING,
    ) == 2
    assert grid.movement_edge_cost_units(
        (1, 0),
        (0, 0),
        MovementMode.FLYING,
    ) == 2
    with pytest.raises(ValueError, match="both support Tiles"):
        grid.movement_edge_cost_units(
            (0, 0),
            (2, 0),
            MovementMode.FLYING,
        )


def test_adjacent_tile_sides_are_independent_placement_volumes() -> None:
    grid = _two_tile_grid()
    exit_wall = OccupyingBoundaryBlock(
        name="Exit wall",
        source_entity_uuid=uuid4(),
    )
    entry_wall = OccupyingBoundaryBlock(
        name="Entry wall",
        source_entity_uuid=uuid4(),
    )
    collision = OccupyingBoundaryBlock(
        name="Same-side collision",
        source_entity_uuid=uuid4(),
    )

    exit_placement = grid.place_object(
        exit_wall.uuid,
        (0, 0),
        boundary_direction=CardinalDirection.EAST,
        base_height_steps=0,
    )
    entry_placement = grid.place_object(
        entry_wall.uuid,
        (1, 0),
        boundary_direction=CardinalDirection.WEST,
        base_height_steps=0,
    )

    assert exit_placement.orientation is None
    assert entry_placement.orientation is None
    assert grid.get_boundary_objects_at(
        (0, 0), CardinalDirection.EAST
    ) == {exit_wall.uuid}
    assert grid.get_boundary_objects_at(
        (1, 0), CardinalDirection.WEST
    ) == {entry_wall.uuid}

    oriented = grid.orient_object(
        entry_wall.uuid,
        CardinalDirection.NORTH,
    )
    assert oriented.orientation is CardinalDirection.NORTH
    assert oriented.position == entry_placement.position
    assert oriented.boundary_direction is entry_placement.boundary_direction
    assert set(grid.iter_object_placements()) == {exit_placement, oriented}

    with pytest.raises(ValueError, match="collides"):
        grid.place_object(
            collision.uuid,
            (0, 0),
            boundary_direction=CardinalDirection.EAST,
            base_height_steps=1,
        )
    assert grid.get_object_placement(collision.uuid) is None

    moved = grid.move_object(
        exit_wall.uuid,
        (0, 0),
        boundary_direction=CardinalDirection.NORTH,
        base_height_steps=0,
    )
    assert moved.boundary_direction is CardinalDirection.NORTH
    assert grid.get_boundary_objects_at(
        (0, 0), CardinalDirection.EAST
    ) == set()
    assert grid.get_boundary_objects_at(
        (1, 0), CardinalDirection.WEST
    ) == {entry_wall.uuid}

    assert grid.remove_object(exit_wall.uuid)
    assert grid.get_boundary_objects_at(
        (1, 0), CardinalDirection.WEST
    ) == {entry_wall.uuid}

    completed = [
        event
        for _, event in EventQueue.iter_events_since(0)
        if event.phase is EventPhase.COMPLETION
        and event.object_uuid in {exit_wall.uuid, entry_wall.uuid}
    ]
    assert any(event.placement == exit_placement for event in completed)
    assert any(event.placement == entry_placement for event in completed)
    assert any(
        event.previous_placement == entry_placement
        and event.placement == oriented
        for event in completed
    )
    assert any(event.previous_placement == moved for event in completed)


def test_canceled_placement_leaves_no_reverse_or_tile_membership() -> None:
    grid = _two_tile_grid()
    wall = OccupyingBoundaryBlock(
        name="Rejected wall",
        source_entity_uuid=uuid4(),
    )

    def reject_placement(event: Event, _source_uuid) -> Event:
        return event.cancel("placement rejected")

    handler = EventHandler(
        name="Reject placement",
        source_entity_uuid=uuid4(),
        trigger_conditions=[
            Trigger(
                event_type=EventType.SPATIAL_OBJECT_PLACED,
                event_phase=EventPhase.DECLARATION,
            ),
        ],
        event_processor=reject_placement,
    )
    EventQueue.add_event_handler(handler)
    try:
        with pytest.raises(ValueError, match="canceled"):
            grid.place_object(
                wall.uuid,
                (0, 0),
                boundary_direction=CardinalDirection.EAST,
                base_height_steps=0,
            )
    finally:
        EventQueue.remove_event_handler(handler)

    assert grid.get_object_placement(wall.uuid) is None
    assert grid.get_boundary_objects_at(
        (0, 0), CardinalDirection.EAST
    ) == set()


def test_world_edge_is_ordered_and_keeps_both_incident_side_layers() -> None:
    grid = _two_tile_grid()
    exit_wall = StructuralBoundaryBlock(
        name="Movement wall",
        source_entity_uuid=uuid4(),
        blocked_channels=(WorldEdgeChannel.MOVEMENT,),
    )
    entry_wall = StructuralBoundaryBlock(
        name="Open wall provider",
        source_entity_uuid=uuid4(),
        blocked_channels=(),
    )
    grid.place_object(
        exit_wall.uuid,
        (0, 0),
        boundary_direction=CardinalDirection.EAST,
        base_height_steps=0,
    )
    grid.place_object(
        entry_wall.uuid,
        (1, 0),
        boundary_direction=CardinalDirection.WEST,
        base_height_steps=0,
    )

    forward = grid.get_world_edge((0, 0), (1, 0))
    reverse = grid.get_world_edge((1, 0), (0, 0))

    assert forward.key == reverse.key
    assert forward.source_position == reverse.destination_position
    assert forward.destination_position == reverse.source_position
    assert forward.exit_direction is CardinalDirection.EAST
    assert forward.entry_direction is CardinalDirection.WEST
    assert forward.exit_contributions == reverse.entry_contributions
    assert forward.entry_contributions == reverse.exit_contributions
    assert forward.exit_contributions[0].provider_uuid == exit_wall.uuid
    assert forward.exit_contributions[0].blocked_channels == (
        WorldEdgeChannel.MOVEMENT,
    )
    assert forward.entry_contributions[0].provider_uuid == entry_wall.uuid
    assert forward.entry_contributions[0].blocked_channels == ()


def test_directional_door_changes_structure_without_replacing_placement() -> None:
    grid = _two_tile_grid()
    door = DirectionalDoor(
        source_entity_uuid=uuid4(),
        blocked_channels=(
            WorldEdgeChannel.MOVEMENT,
            WorldEdgeChannel.OPTICAL,
            WorldEdgeChannel.PROPAGATION,
        ),
    )
    door.place_on_grid(
        (0, 0),
        boundary_direction=CardinalDirection.EAST,
    )
    placement = grid.get_object_placement(door.uuid)
    assert placement is not None
    assert not grid.can_transition((0, 0), (1, 0))
    assert not grid.can_transition((1, 0), (0, 0))
    assert not grid.can_optical_transition((0, 0), (1, 0))
    assert not grid.can_propagate_transition((0, 0), (1, 0))
    assert not {
        "blocks_movement_north",
        "blocks_movement_south",
        "blocks_movement_east",
        "blocks_movement_west",
    } & door.model_dump().keys()
    with pytest.raises(ValueError, match="placed boundary structures"):
        grid.set_tile_directional_border(
            (0, 0),
            "movement",
            "east",
            False,
        )
    assert not hasattr(door, "set_directional_blocking")

    cursor = EventQueue.event_cursor()
    movement_revision = grid.movement_revision
    optical_revision = grid.optical_revision
    propagation_revision = grid.propagation_revision
    door.open()

    assert grid.get_object_placement(door.uuid) == placement
    assert grid.can_transition((0, 0), (1, 0))
    assert grid.can_transition((1, 0), (0, 0))
    assert grid.can_optical_transition((0, 0), (1, 0))
    assert grid.can_propagate_transition((0, 0), (1, 0))
    assert grid.movement_revision == movement_revision + 1
    assert grid.optical_revision == optical_revision + 1
    assert grid.propagation_revision == propagation_revision + 1
    edge = grid.get_world_edge((0, 0), (1, 0))
    assert len(edge.exit_contributions) == 1
    assert edge.exit_contributions[0].provider_uuid == door.uuid
    assert edge.exit_contributions[0].blocked_channels == ()

    completion = next(
        event
        for _, event in EventQueue.iter_events_since(cursor)
        if event.event_type is EventType.SPATIAL_OBJECT_CHANGED
        and event.phase is EventPhase.COMPLETION
        and event.object_uuid == door.uuid
    )
    assert completion.placement == placement
    assert completion.previous_placement == placement
    assert completion.object_is_open is True
    assert completion.object_boundary_structure == door.get_boundary_structure()
    assert completion.directional_position == (0, 0)
    assert completion.directional_directions == ["east"]
    assert completion.directional_channels == [
        "movement",
        "optical",
        "propagation",
    ]
    assert completion.senses_hint is not None
    assert completion.senses_hint.requires_fov
    assert completion.senses_hint.requires_light_recompute
    assert completion.senses_hint.requires_propagation_recompute

    door.close()
    assert grid.get_object_placement(door.uuid) == placement
    assert not grid.can_transition((0, 0), (1, 0))


def test_walking_uses_both_side_layers_and_progressive_support_rules() -> None:
    grid = _two_tile_grid()
    high_wall = StructuralBoundaryBlock(
        name="High movement wall",
        source_entity_uuid=uuid4(),
        blocked_channels=(WorldEdgeChannel.MOVEMENT,),
    )
    grid.place_object(
        high_wall.uuid,
        (1, 0),
        boundary_direction=CardinalDirection.WEST,
        base_height_steps=2,
    )

    assert grid.can_transition((0, 0), (1, 0))
    grid.move_object(
        high_wall.uuid,
        (1, 0),
        boundary_direction=CardinalDirection.WEST,
        base_height_steps=0,
    )
    assert not grid.can_transition((0, 0), (1, 0))

    grid.remove_object(high_wall.uuid)
    destination = grid.get_tile(1, 0)
    assert destination is not None
    destination.height = 1
    assert not grid.can_transition((0, 0), (1, 0))
    assert grid.can_transition(
        (0, 0),
        (1, 0),
        movement_mode=MovementMode.FLYING,
    )

    source = grid.get_tile(0, 0)
    assert source is not None
    source.elevation_surface_kind = ElevationSurfaceKind.RAMP
    source.slope_axis = SlopeAxis.EAST_WEST
    destination.elevation_surface_kind = ElevationSurfaceKind.RAMP
    destination.slope_axis = SlopeAxis.EAST_WEST
    assert grid.can_transition((0, 0), (1, 0))


def test_tile_elevation_change_commits_before_typed_completion() -> None:
    grid = _two_tile_grid()
    tile = grid.get_tile(1, 0)
    assert tile is not None

    assert grid.set_tile_elevation(
        (1, 0),
        height=1,
        surface_kind=ElevationSurfaceKind.RAMP,
        slope_axis=SlopeAxis.EAST_WEST,
    )

    completions = [
        event
        for _, event in EventQueue.iter_events_since(0)
        if isinstance(event, TileElevationChangeEvent)
        and event.phase is EventPhase.COMPLETION
    ]
    assert len(completions) == 1
    assert completions[0].tile_uuid == tile.uuid
    assert completions[0].old_height_steps == 0
    assert completions[0].new_height_steps == 1
    assert tile.height == 1


def test_canceled_tile_elevation_change_preserves_support_tuple() -> None:
    grid = _two_tile_grid()
    tile = grid.get_tile(1, 0)
    assert tile is not None

    def reject_elevation(event: Event, _source_uuid) -> Event:
        return event.cancel("elevation rejected")

    handler = EventHandler(
        name="Reject elevation",
        source_entity_uuid=uuid4(),
        trigger_conditions=[
            Trigger(
                event_type=EventType.SPATIAL_TILE_CHANGED,
                event_phase=EventPhase.DECLARATION,
            ),
        ],
        event_processor=reject_elevation,
    )
    EventQueue.add_event_handler(handler)
    try:
        assert not grid.set_tile_elevation(
            (1, 0),
            height=1,
            surface_kind=ElevationSurfaceKind.RAMP,
            slope_axis=SlopeAxis.EAST_WEST,
        )
    finally:
        EventQueue.remove_event_handler(handler)

    assert (
        tile.height,
        tile.elevation_surface_kind,
        tile.slope_axis,
    ) == (0, ElevationSurfaceKind.ORDINARY, None)
