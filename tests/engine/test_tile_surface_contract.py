"""Public contracts for semantic Tile surfaces and cold placement values."""

from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from dnd.core.base_tiles import (
    Tile,
    dark_floor_factory,
    difficult_terrain_factory,
    floor_factory,
    wall_factory,
    water_factory,
)
from dnd.core.base_conditions import BaseCondition
from dnd.core.geometry import circle_positions
from dnd.core.world_edges import ElevationSurfaceKind
from dnd.blocks.base_item import BaseItem
from dnd.content.spatial_effect_materialization import materialize_spatial_condition
from dnd.content.spatial_effect_recipes import OIL_SURFACE_RECIPE
from dnd.spatial.environmental_conditions import OilSurface
from dnd.spatial.area_conditions import SpatialCondition
from dnd.core.events.events_registry import Event, EventPhase, EventQueue, EventType
from dnd.core.events.item_events import ItemLocationStateEvent
from dnd.core.events.world_events import (
    SpatialChangeEvent,
    SpatialChangeType,
    WorldInitializedEvent,
    WorldObjectState,
)
from dnd.core.gridmap import get_map
from dnd.items.environment import CliffFace, DirectionalDoor, DirectionalWall
from dnd.items.torches import WallTorch
from dnd.types.materials import Material, SurfaceLayer, TileSurface
from dnd.types.items import ItemLocation
from dnd.types.spatial_effects import (
    SpatialEffectAnchorKind,
    SpatialEffectLayer,
    SpatialEffectOccupancyPolicy,
)
from dnd.types.world import (
    CardinalDirection,
    LightLevel,
    MovementMode,
    WorldEdgeChannel,
)
from dnd.types.world_placement import (
    BoundaryStructure,
    BoundaryStructureKind,
    WorldObjectPlacement,
    WorldPlacementKind,
    WorldPlacementSpec,
)
from tests.engine.support import reset_combat_state


class CenterOccupant(BaseItem):
    """Test provider with a two-step exclusive center footprint."""

    def get_world_placement_spec(self) -> WorldPlacementSpec:
        return WorldPlacementSpec(
            kind=WorldPlacementKind.CENTER,
            occupies_bands=True,
            vertical_extent_steps=2,
        )


class CenterStructuralProvider(CenterOccupant):
    """Center provider whose neutral structure must never enter an edge."""

    boundary_structure_calls: int = 0

    def get_boundary_structure(self) -> BoundaryStructure:
        self.boundary_structure_calls += 1
        return BoundaryStructure(
            structure=BoundaryStructureKind.WALL,
            material=Material.STONE,
            blocked_channels=tuple(WorldEdgeChannel),
        )


class BoundaryOccupant(BaseItem):
    """Test provider with a one-step exclusive cardinal boundary footprint."""

    def get_world_placement_spec(self) -> WorldPlacementSpec:
        return WorldPlacementSpec(
            kind=WorldPlacementKind.BOUNDARY,
            occupies_bands=True,
            vertical_extent_steps=1,
        )


class BoundaryAttachment(BaseItem):
    """Nonoccupying provider that shares one exact boundary side."""

    boundary_structure_calls: int = 0

    def get_world_placement_spec(self) -> WorldPlacementSpec:
        return WorldPlacementSpec(
            kind=WorldPlacementKind.BOUNDARY,
            occupies_bands=False,
            vertical_extent_steps=1,
        )

    def get_boundary_structure(self) -> None:
        self.boundary_structure_calls += 1
        return None


class AnchoredLifecycleCondition(SpatialCondition):
    """Non-light condition used to observe public object-anchor relocation."""

    def resolve_condition_footprint(self) -> set[tuple[int, int]]:
        return set(self.affected_positions)

    def relocate_anchor(
        self,
        position: tuple[int, int],
        *,
        parent_event: Event,
    ) -> None:
        del parent_event
        grid = get_map()
        grid.set_spatial_condition_positions(
            condition=self,
            layer=self.layer,
            occupancy_policy=self.occupancy_policy,
            positions={position},
        )
        self.position = position
        self.affected_positions = {position}


class StructuralBoundaryOccupant(BoundaryOccupant):
    """Boundary provider whose exact semantic state appears in edge views."""

    def get_boundary_structure(self) -> BoundaryStructure:
        """Expose the exact public structural after-value."""
        return BoundaryStructure(
            structure=BoundaryStructureKind.WALL,
            material=Material.STONE,
            blocked_channels=(
                WorldEdgeChannel.MOVEMENT,
                WorldEdgeChannel.OPTICAL,
            ),
        )


class TwoBandStructuralBoundaryOccupant(StructuralBoundaryOccupant):
    """Structural boundary provider with an exact two-band footprint."""

    def get_world_placement_spec(self) -> WorldPlacementSpec:
        return WorldPlacementSpec(
            kind=WorldPlacementKind.BOUNDARY,
            occupies_bands=True,
            vertical_extent_steps=2,
        )


class ThrowingDirectionalItem(BaseItem):
    """Provider used to prove command rollback around directional recomputation."""

    raise_on_directional: bool = False

    def get_world_placement_spec(self) -> WorldPlacementSpec:
        return WorldPlacementSpec(
            kind=WorldPlacementKind.BOUNDARY,
            occupies_bands=True,
            vertical_extent_steps=1,
        )

    def get_boundary_structure(self) -> BoundaryStructure | None:
        if self.raise_on_directional:
            raise RuntimeError("directional provider failure")
        return None


class ThrowingBoundaryItem(ThrowingDirectionalItem):
    """Throwing provider with an independently selected boundary side."""

    def get_world_placement_spec(self) -> WorldPlacementSpec:
        return WorldPlacementSpec(
            kind=WorldPlacementKind.BOUNDARY,
            occupies_bands=True,
            vertical_extent_steps=1,
        )


class ThrowingRebuildDirectionalItem(BaseItem):
    """Provider that fails during canonical rebuild recomputation."""

    raise_on_directional: bool = False

    def get_world_placement_spec(self) -> WorldPlacementSpec:
        return WorldPlacementSpec(
            kind=WorldPlacementKind.BOUNDARY,
            occupies_bands=True,
            vertical_extent_steps=1,
        )

    def get_boundary_structure(self) -> BoundaryStructure | None:
        if self.raise_on_directional:
            raise RuntimeError("rebuild directional provider failure")
        return None


class ThrowingCenterMechanic(BaseItem):
    """Provider whose center blocking query fails before command mutation."""

    raise_on_center_mechanic: bool = False

    def blocks_optics_at_center(self) -> bool:
        if self.raise_on_center_mechanic:
            raise RuntimeError("center mechanic provider failure")
        return False


class ThrowingRemovalItem(BaseItem):
    """Provider used to prove terminal-hook exceptions keep current diagnostics."""

    def on_grid_object_removed(self, position, parent_event=None) -> None:
        raise RuntimeError("terminal removal hook failure")


class OpticalCenterBlocker(BaseItem):
    """Test provider that blocks center optics without directional borders."""

    def blocks_optics_at_center(self) -> bool:
        return True


def test_cliff_and_wall_torch_use_exact_boundary_height_contracts() -> None:
    """Concrete boundary objects retain independent side, height, and channels."""
    reset_combat_state()
    grid = get_map()
    grid.create_rectangle(
        0,
        0,
        2,
        1,
        surface=TileSurface(base_material=Material.STONE),
    )
    grid.set_tile_elevation(
        (0, 0),
        height=2,
        surface_kind=ElevationSurfaceKind.ORDINARY,
        slope_axis=None,
    )
    grid.set_tile_elevation(
        (1, 0),
        height=2,
        surface_kind=ElevationSurfaceKind.ORDINARY,
        slope_axis=None,
    )

    cliff = CliffFace(source_entity_uuid=uuid4(), semantic_key="test.cliff")
    torch = WallTorch(source_entity_uuid=uuid4(), semantic_key="test.torch")
    wall = DirectionalWall(
        source_entity_uuid=uuid4(),
        semantic_key="test.wall",
    )

    grid.place_object(
        cliff.uuid,
        (1, 0),
        boundary_direction=CardinalDirection.WEST,
        base_height_steps=0,
    )
    torch.mount(
        (1, 0),
        boundary_direction=CardinalDirection.WEST,
        base_height_steps=1,
        orientation=CardinalDirection.EAST,
        lit=False,
    )
    cliff_placement = grid.get_object_placement(cliff.uuid)
    torch_placement = grid.get_object_placement(torch.uuid)
    assert cliff_placement is not None
    assert torch_placement is not None
    assert cliff_placement.kind is WorldPlacementKind.BOUNDARY
    assert cliff_placement.occupies_bands is True
    assert (cliff_placement.boundary_direction, cliff_placement.base_height_steps) == (
        CardinalDirection.WEST,
        0,
    )
    assert cliff_placement.top_height_steps == 2
    assert torch_placement.occupies_bands is False
    assert (torch_placement.boundary_direction, torch_placement.base_height_steps) == (
        CardinalDirection.WEST,
        1,
    )
    assert torch_placement.orientation is CardinalDirection.EAST
    assert set(grid.get_boundary_objects_at((1, 0), CardinalDirection.WEST)) == {
        cliff.uuid,
        torch.uuid,
    }

    cliff_edge = grid.get_world_edge((0, 0), (1, 0))
    assert {row.provider_uuid for row in cliff_edge.entry_contributions} == {cliff.uuid}
    assert all(row.provider_uuid != torch.uuid for row in cliff_edge.entry_contributions)
    assert cliff.get_boundary_structure().structure is BoundaryStructureKind.CLIFF
    assert cliff.get_boundary_structure().material is Material.STONE
    assert cliff.get_boundary_structure().blocked_channels == (
        WorldEdgeChannel.MOVEMENT,
    )
    assert grid.can_transition(
        (0, 0),
        (1, 0),
        movement_mode=MovementMode.WALKING,
    )
    assert not grid.can_transition(
        (0, 0),
        (1, 0),
        movement_mode=MovementMode.FLYING,
    )
    assert grid.can_optical_transition((0, 0), (1, 0))
    assert grid.can_propagate_transition((0, 0), (1, 0))
    wall_before = grid.place_object(
        wall.uuid,
        (0, 0),
        boundary_direction=CardinalDirection.EAST,
        base_height_steps=0,
        orientation=CardinalDirection.WEST,
    )
    edge = grid.get_world_edge((0, 0), (1, 0))
    assert {row.provider_uuid for row in edge.exit_contributions} == {wall.uuid}
    assert {row.provider_uuid for row in edge.entry_contributions} == {cliff.uuid}
    assert wall_before.base_height_steps == 0
    assert wall_before.top_height_steps == 2
    assert wall_before.boundary_direction is CardinalDirection.EAST
    assert wall_before.orientation is CardinalDirection.WEST
    assert grid.can_transition(
        (0, 0),
        (1, 0),
        movement_mode=MovementMode.WALKING,
    )

    wall_after = grid.move_object(
        wall.uuid,
        (0, 0),
        boundary_direction=CardinalDirection.EAST,
        base_height_steps=2,
        orientation=CardinalDirection.WEST,
    )
    assert wall_after.object_uuid == wall_before.object_uuid == wall.uuid
    assert wall_after.boundary_direction is CardinalDirection.EAST
    assert wall_after.base_height_steps == 2
    assert wall_after.top_height_steps == 4
    assert wall_after.orientation is CardinalDirection.WEST
    assert wall_after.occupies_bands is True
    assert wall.get_boundary_structure().structure is BoundaryStructureKind.WALL
    assert wall.get_boundary_structure().blocked_channels == tuple(WorldEdgeChannel)
    assert grid.get_object_placement(cliff.uuid) == cliff_placement
    assert grid.get_object_placement(torch.uuid) == torch_placement
    moved_edge = grid.get_world_edge((0, 0), (1, 0))
    assert {row.provider_uuid for row in moved_edge.entry_contributions} == {cliff.uuid}
    assert not grid.can_transition(
        (0, 0),
        (1, 0),
        movement_mode=MovementMode.WALKING,
    )


def test_surface_values_round_trip_strictly_and_preserve_order() -> None:
    """Surface composition is immutable, ordered, and deterministic on the wire."""
    surface = TileSurface(
        base_material=Material.EARTH,
        layers=(
            SurfaceLayer(material=Material.VEGETATION, description="grass"),
            SurfaceLayer(material=Material.VEGETATION, description="moss"),
        ),
        description="overgrown ground",
    )

    restored = TileSurface.model_validate_json(surface.model_dump_json())

    assert restored == surface
    assert restored.layers[0].description == "grass"
    assert restored.layers[1].description == "moss"
    with pytest.raises(ValidationError):
        TileSurface(base_material=Material.STONE, extra_field="nope")


@pytest.mark.parametrize("value", [True, 1.0, "1"])
def test_world_placement_rejects_coerced_coordinates_and_heights(value: object) -> None:
    """Persisted placement integers reject bools, floats, and strings."""
    with pytest.raises(ValidationError):
        WorldObjectPlacement(
            object_uuid=uuid4(),
            tile_uuid=uuid4(),
            position=(value, 0),
            kind=WorldPlacementKind.CENTER,
            occupies_bands=False,
            base_height_steps=0,
            top_height_steps=1,
        )

    with pytest.raises(ValidationError):
        WorldObjectPlacement(
            object_uuid=uuid4(),
            tile_uuid=uuid4(),
            position=(0, 0),
            kind=WorldPlacementKind.CENTER,
            occupies_bands=False,
            base_height_steps=value,
            top_height_steps=1,
        )


def test_active_tile_factories_have_explicit_semantic_surfaces() -> None:
    """Factories use authored meaning, independently of sprite names."""
    assert floor_factory((0, 0)).surface == TileSurface(base_material=Material.STONE)
    assert dark_floor_factory((0, 0)).surface == TileSurface(base_material=Material.STONE)
    assert wall_factory((0, 0)).surface == TileSurface(base_material=Material.STONE)
    assert water_factory((0, 0)).surface == TileSurface(base_material=Material.WATER)
    assert difficult_terrain_factory((0, 0)).surface == TileSurface(
        base_material=Material.EARTH,
    )


def test_surface_replacement_preserves_tile_identity_light_and_fact_round_trip() -> None:
    """GridMap replaces only the semantic surface and publishes its after-value."""
    reset_combat_state()
    grid = get_map()
    grid.disable_events()
    grid.create_rectangle(
        0,
        0,
        2,
        1,
        surface=TileSurface(base_material=Material.STONE),
    )
    grid.enable_events(flush_pending=False)
    tile = grid.get_tile(0, 0)
    assert tile is not None
    original_uuid = tile.uuid
    original_light = tile.resolved_light_level
    original_costs = (
        tile.get_movement_cost(MovementMode.WALKING),
        tile.get_movement_cost(MovementMode.FLYING),
        tile.get_movement_cost(MovementMode.SWIMMING),
        tile.get_movement_cost(MovementMode.BURROWING),
    )
    original_movement_revision = grid.movement_revision
    replacement = TileSurface(
        base_material=Material.EARTH,
        layers=(SurfaceLayer(material=Material.VEGETATION),),
    )

    assert grid.replace_tile_surface((0, 0), replacement) is True

    assert tile.uuid == original_uuid
    assert tile.surface == replacement
    assert tile.resolved_light_level is original_light
    assert (
        tile.get_movement_cost(MovementMode.WALKING),
        tile.get_movement_cost(MovementMode.FLYING),
        tile.get_movement_cost(MovementMode.SWIMMING),
        tile.get_movement_cost(MovementMode.BURROWING),
    ) == original_costs
    assert grid.movement_revision == original_movement_revision
    completed = [
        event
        for event in EventQueue.get_events_by_type(EventType.SPATIAL_TILE_CHANGED)
        if isinstance(event, SpatialChangeEvent)
        and event.phase is EventPhase.COMPLETION
        and event.position == (0, 0)
    ]
    assert completed
    assert completed[-1].tile_surface == replacement
    assert TileSurface.model_validate_json(
        completed[-1].tile_surface.model_dump_json()
    ) == replacement


def test_surface_change_does_not_copy_temporary_illumination_into_surface() -> None:
    """Objective light remains independent from semantic surface composition."""
    reset_combat_state()
    grid = get_map()
    grid.disable_events()
    grid.create_rectangle(
        0,
        0,
        1,
        1,
        surface=TileSurface(base_material=Material.STONE),
    )
    grid.enable_events(flush_pending=False)
    grid.set_tile_base_light((0, 0), LightLevel.DARKNESS)
    tile = grid.get_tile(0, 0)
    assert tile is not None

    grid.replace_tile_surface(
        (0, 0),
        TileSurface(base_material=Material.STONE, description="dark floor"),
    )

    assert tile.surface.description == "dark floor"
    assert tile.resolved_light_level.value == 0


def test_gridmap_commits_center_bands_and_rejects_exclusive_overlap() -> None:
    """Placement admission is band-aware while public queries stay immutable."""
    reset_combat_state()
    grid = get_map()
    grid.disable_events()
    grid.create_rectangle(
        0,
        0,
        2,
        1,
        surface=TileSurface(base_material=Material.STONE),
    )
    grid.enable_events(flush_pending=False)
    first = CenterOccupant(source_entity_uuid=uuid4(), name="First")
    second = CenterOccupant(source_entity_uuid=uuid4(), name="Second")

    grid.place_object(first.uuid, (0, 0))
    assert grid.get_center_objects_at((0, 0), height=0) == {first.uuid}
    assert grid.get_center_objects_at((0, 0), height=1) == {first.uuid}
    assert grid.get_tile(0, 0).get_center_object_bands()[0][1].object_uuids == {first.uuid}
    with pytest.raises(ValueError, match="occupied"):
        grid.place_object(second.uuid, (0, 0))
    assert grid.get_object_placement(second.uuid) is None

    cursor = EventQueue.event_cursor()
    grid.move_object(first.uuid, (1, 0))
    assert grid.last_operation_diagnostics.operation == "move_object"
    assert grid.last_operation_diagnostics.bands_replaced >= 4
    changes = [
        event
        for _index, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, SpatialChangeEvent)
        and event.phase is EventPhase.COMPLETION
        and event.object_uuid == first.uuid
    ]
    departure = next(event for event in changes if event.change_type.value == "object_removed")
    arrival = next(event for event in changes if event.change_type.value == "object_placed")
    assert departure.previous_placement is not None
    assert departure.placement is None
    assert departure.old_position == (1, 0)
    assert arrival.previous_placement == departure.previous_placement
    assert arrival.placement == grid.get_object_placement(first.uuid)
    assert grid.get_objects_at((0, 0)) == set()
    assert grid.get_objects_at((1, 0)) == {first.uuid}


def test_object_event_matrix_carries_exact_before_and_after_placements() -> None:
    """Place, move, orient, and remove expose the frozen lifecycle matrix."""
    reset_combat_state()
    grid = get_map()
    grid.disable_events()
    grid.create_rectangle(0, 0, 3, 1, surface=TileSurface(base_material=Material.STONE))
    for position in grid.get_all_tiles():
        grid.set_tile_base_light(position, LightLevel.DARKNESS)
    grid.enable_events(flush_pending=False)
    item = CenterOccupant(source_entity_uuid=uuid4(), name="Event matrix item")

    cursor = EventQueue.event_cursor()
    placed = grid.place_object(item.uuid, (0, 0))
    placement_events = [
        event
        for _index, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, SpatialChangeEvent)
        and event.phase is EventPhase.COMPLETION
        and event.object_uuid == item.uuid
    ]
    assert len(placement_events) == 1
    assert placement_events[0].change_type is SpatialChangeType.OBJECT_PLACED
    assert placement_events[0].placement == placed
    assert placement_events[0].previous_placement is None
    assert placement_events[0].old_position is None

    cursor = EventQueue.event_cursor()
    moved = grid.move_object(item.uuid, (1, 0))
    move_events = [
        event
        for _index, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, SpatialChangeEvent)
        and event.phase is EventPhase.COMPLETION
        and event.object_uuid == item.uuid
    ]
    assert [event.change_type for event in move_events] == [
        SpatialChangeType.OBJECT_REMOVED,
        SpatialChangeType.OBJECT_PLACED,
    ]
    departure, arrival = move_events
    assert departure.previous_placement == placed
    assert departure.placement is None
    assert departure.old_position == moved.position
    assert arrival.previous_placement == placed
    assert arrival.placement == moved
    assert arrival.old_position == placed.position

    cursor = EventQueue.event_cursor()
    oriented = grid.orient_object(item.uuid, CardinalDirection.SOUTH)
    orientation_events = [
        event
        for _index, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, SpatialChangeEvent)
        and event.phase is EventPhase.COMPLETION
        and event.object_uuid == item.uuid
    ]
    assert len(orientation_events) == 1
    assert orientation_events[0].change_type is SpatialChangeType.OBJECT_CHANGED
    assert orientation_events[0].placement == oriented
    assert orientation_events[0].previous_placement == moved
    assert orientation_events[0].old_position == oriented.position

    cursor = EventQueue.event_cursor()
    grid.remove_object(item.uuid)
    removal_events = [
        event
        for _index, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, SpatialChangeEvent)
        and event.phase is EventPhase.COMPLETION
        and event.object_uuid == item.uuid
    ]
    assert len(removal_events) == 1
    assert removal_events[0].change_type is SpatialChangeType.OBJECT_REMOVED
    assert removal_events[0].previous_placement == oriented
    assert removal_events[0].placement is None


def test_boundary_bands_are_exact_side_queries_and_independent_collisions() -> None:
    """Opposing Tile sides admit independent occupants at the same height."""
    reset_combat_state()
    grid = get_map()
    grid.disable_events()
    grid.create_rectangle(
        0,
        0,
        2,
        1,
        surface=TileSurface(base_material=Material.STONE),
    )
    grid.enable_events(flush_pending=False)
    first = TwoBandStructuralBoundaryOccupant(
        source_entity_uuid=uuid4(),
        name="First boundary",
    )
    second = TwoBandStructuralBoundaryOccupant(
        source_entity_uuid=uuid4(),
        name="Second boundary",
    )
    attachment = BoundaryAttachment(
        source_entity_uuid=uuid4(),
        name="Boundary attachment",
    )
    center_provider = CenterStructuralProvider(
        source_entity_uuid=uuid4(),
        name="Center structure must stay off-edge",
    )
    nonstructural = BoundaryAttachment(
        source_entity_uuid=uuid4(),
        name="Nonstructural outer attachment",
    )

    grid.place_object(center_provider.uuid, (0, 0))
    nonstructural_placement = grid.place_object(
        nonstructural.uuid,
        (1, 0),
        boundary_direction=CardinalDirection.EAST,
    )
    assert center_provider.boundary_structure_calls == 0
    assert nonstructural.boundary_structure_calls == 1

    cursor = EventQueue.event_cursor()
    first_placement = grid.place_object(
        first.uuid,
        (0, 0),
        boundary_direction=CardinalDirection.EAST,
        orientation=CardinalDirection.NORTH,
    )
    grid.place_object(
        attachment.uuid,
        (0, 0),
        boundary_direction=CardinalDirection.EAST,
    )
    grid.place_object(
        second.uuid,
        (1, 0),
        boundary_direction=CardinalDirection.WEST,
    )
    assert grid.get_boundary_objects_at(
        (0, 0), CardinalDirection.EAST, height=0,
    ) == {first.uuid, attachment.uuid}
    assert grid.get_boundary_objects_at(
        (0, 0), CardinalDirection.EAST, height=1,
    ) == {first.uuid}
    assert grid.get_boundary_objects_at(
        (1, 0), CardinalDirection.WEST, height=0,
    ) == {second.uuid}
    assert grid.get_boundary_objects_at(
        (1, 0), CardinalDirection.WEST, height=1,
    ) == {second.uuid}
    second_placement = grid.get_object_placement(second.uuid)
    assert second_placement is not None
    placement_rows = {
        placement.object_uuid: placement
        for placement in grid.get_all_object_placements()
    }
    assert placement_rows[first.uuid].boundary_direction is CardinalDirection.EAST
    assert placement_rows[second.uuid].boundary_direction is CardinalDirection.WEST
    assert placement_rows[first.uuid].position == (0, 0)
    assert placement_rows[second.uuid].position == (1, 0)
    assert placement_rows[first.uuid].base_height_steps == 0
    assert placement_rows[first.uuid].top_height_steps == 2
    assert placement_rows[second.uuid].base_height_steps == 0
    assert placement_rows[second.uuid].top_height_steps == 2

    forward = grid.get_world_edge((0, 0), (1, 0))
    reverse = grid.get_world_edge((1, 0), (0, 0))
    assert {
        contribution.provider_uuid for contribution in forward.exit_contributions
    } == {first.uuid}
    assert {
        contribution.provider_uuid for contribution in forward.entry_contributions
    } == {second.uuid}
    assert {
        contribution.provider_uuid for contribution in reverse.exit_contributions
    } == {second.uuid}
    assert {
        contribution.provider_uuid for contribution in reverse.entry_contributions
    } == {first.uuid}
    assert center_provider.uuid in grid.get_center_objects_at((0, 0))
    assert first.uuid not in grid.get_center_objects_at((0, 0))
    assert all(
        center_provider.uuid != contribution.provider_uuid
        for contribution in forward.exit_contributions + forward.entry_contributions
    )

    def assert_second_is_unchanged() -> None:
        assert grid.get_object_placement(second.uuid) == second_placement
        assert grid.get_boundary_objects_at(
            (1, 0), CardinalDirection.WEST, height=0,
        ) == {second.uuid}
        assert grid.get_boundary_objects_at(
            (1, 0), CardinalDirection.WEST, height=1,
        ) == {second.uuid}

    completed = [
        event
        for _index, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, SpatialChangeEvent)
        and event.phase is EventPhase.COMPLETION
        and event.change_type is SpatialChangeType.OBJECT_PLACED
    ]
    assert {event.object_uuid for event in completed} == {
        first.uuid,
        attachment.uuid,
        second.uuid,
    }
    completed_by_uuid = {event.object_uuid: event for event in completed}
    assert completed_by_uuid[first.uuid].placement == first_placement
    assert completed_by_uuid[second.uuid].placement == second_placement
    assert completed_by_uuid[first.uuid].placement is not None
    assert completed_by_uuid[second.uuid].placement is not None
    assert completed_by_uuid[first.uuid].placement.boundary_direction is CardinalDirection.EAST
    assert completed_by_uuid[second.uuid].placement.boundary_direction is CardinalDirection.WEST
    assert completed_by_uuid[first.uuid].placement.base_height_steps == 0
    assert completed_by_uuid[first.uuid].placement.top_height_steps == 2
    assert completed_by_uuid[second.uuid].placement.base_height_steps == 0
    assert completed_by_uuid[second.uuid].placement.top_height_steps == 2
    attachment_hint = completed_by_uuid[attachment.uuid].senses_hint
    assert attachment_hint is not None
    assert attachment_hint.directional_positions == {(0, 0)}
    assert attachment_hint.directional_neighbors == {(1, 0)}
    assert attachment_hint.directional_channels_changed is None

    third = BoundaryOccupant(
        source_entity_uuid=uuid4(),
        name="Same-side collision",
    )
    collision_cursor = EventQueue.event_cursor()
    with pytest.raises(ValueError, match="placement band is occupied"):
        grid.place_object(
            third.uuid,
            (0, 0),
            boundary_direction=CardinalDirection.EAST,
            base_height_steps=1,
        )
    assert grid.get_object_placement(third.uuid) is None
    assert [
        event
        for _index, event in EventQueue.iter_events_since(collision_cursor)
        if isinstance(event, SpatialChangeEvent)
        and event.phase is EventPhase.COMPLETION
        and event.object_uuid == third.uuid
    ] == []

    mutation_cursor = EventQueue.event_cursor()
    grid.orient_object(first.uuid, CardinalDirection.SOUTH)
    assert_second_is_unchanged()
    grid.move_object(
        first.uuid,
        (0, 0),
        boundary_direction=CardinalDirection.WEST,
        orientation=CardinalDirection.EAST,
    )
    assert_second_is_unchanged()
    grid.remove_object(first.uuid)
    assert_second_is_unchanged()
    assert [
        event
        for _index, event in EventQueue.iter_events_since(mutation_cursor)
        if isinstance(event, SpatialChangeEvent)
        and event.phase is EventPhase.COMPLETION
        and event.object_uuid == second.uuid
    ] == []

    grid.remove_object(second.uuid)
    grid.remove_object(nonstructural.uuid)
    grid.remove_object(center_provider.uuid)
    nonstructural.boundary_structure_calls = 0
    grid.rebuild_object_placements([second_placement, nonstructural_placement])
    assert nonstructural.boundary_structure_calls == 1
    assert center_provider.boundary_structure_calls == 0


def test_boundary_side_and_orientation_are_independent_and_orient_in_place() -> None:
    """Orientation changes preserve the independently selected boundary side."""
    reset_combat_state()
    grid = get_map()
    grid.disable_events()
    grid.create_rectangle(0, 0, 2, 1, surface=TileSurface(base_material=Material.STONE))
    grid.enable_events(flush_pending=False)
    boundary = BoundaryOccupant(source_entity_uuid=uuid4(), name="Independent boundary")

    committed = grid.place_object(
        boundary.uuid,
        (0, 0),
        boundary_direction=CardinalDirection.EAST,
        orientation=CardinalDirection.NORTH,
    )
    assert committed.boundary_direction is CardinalDirection.EAST
    assert committed.orientation is CardinalDirection.NORTH

    cursor = EventQueue.event_cursor()
    oriented = grid.orient_object(boundary.uuid, CardinalDirection.SOUTH)

    assert oriented.boundary_direction is CardinalDirection.EAST
    assert oriented.orientation is CardinalDirection.SOUTH
    assert grid.get_boundary_objects_at((0, 0), CardinalDirection.EAST) == {boundary.uuid}
    assert grid.get_boundary_objects_at((0, 0), CardinalDirection.WEST) == set()
    changes = [
        event
        for _index, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, SpatialChangeEvent)
        and event.phase is EventPhase.COMPLETION
        and event.object_uuid == boundary.uuid
    ]
    assert len(changes) == 1
    assert changes[0].change_type is SpatialChangeType.OBJECT_CHANGED
    assert changes[0].previous_placement is not None
    assert changes[0].placement == oriented
    assert changes[0].previous_placement.boundary_direction is CardinalDirection.EAST


def test_same_xy_door_open_and_orient_preserve_anchor_placement() -> None:
    """Opening and orienting a door change mechanics, never its XY anchor/side."""
    reset_combat_state()
    grid = get_map()
    grid.disable_events()
    grid.create_rectangle(0, 0, 2, 1, surface=TileSurface(base_material=Material.STONE))
    grid.enable_events(flush_pending=False)
    door = DirectionalDoor(source_entity_uuid=uuid4())

    placed = grid.place_object(
        door.uuid,
        (0, 0),
        boundary_direction=CardinalDirection.EAST,
        orientation=CardinalDirection.NORTH,
    )
    door.open()
    opened = grid.get_object_placement(door.uuid)
    assert opened == placed
    assert grid.get_boundary_objects_at((0, 0), CardinalDirection.EAST) == {door.uuid}
    assert grid.can_transition((0, 0), (1, 0))

    oriented = grid.orient_object(door.uuid, CardinalDirection.SOUTH)
    assert oriented.position == placed.position == (0, 0)
    assert oriented.boundary_direction is CardinalDirection.EAST
    assert oriented.orientation is CardinalDirection.SOUTH
    assert grid.get_object_placement(door.uuid) == oriented
    assert grid.get_boundary_objects_at((0, 0), CardinalDirection.EAST) == {door.uuid}


def test_boundary_lifecycle_emits_exact_structure_facts_for_move_orient_remove() -> None:
    """Boundary relocation and terminal facts retain exact current/previous values."""
    reset_combat_state()
    grid = get_map()
    grid.disable_events()
    grid.create_rectangle(0, 0, 16, 1, surface=TileSurface(base_material=Material.STONE))
    for position in grid.get_all_tiles():
        grid.set_tile_base_light(position, LightLevel.DARKNESS)
    grid.enable_events(flush_pending=False)
    wall = DirectionalWall(
        source_entity_uuid=uuid4(),
    )
    structure = wall.get_boundary_structure()
    parent = Event(
        source_entity_uuid=wall.source_entity_uuid,
        event_type=EventType.BASE_ACTION,
        phase=EventPhase.COMPLETION,
        use_register=False,
    )

    cursor = EventQueue.event_cursor()
    placed = grid.place_object(
        wall.uuid,
        (0, 0),
        boundary_direction=CardinalDirection.EAST,
        parent_event=parent.uuid,
    )
    placement_events = [
        event
        for _index, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, SpatialChangeEvent)
        and event.phase is EventPhase.COMPLETION
        and event.object_uuid == wall.uuid
    ]
    assert [event.change_type for event in placement_events] == [
        SpatialChangeType.OBJECT_PLACED,
    ]
    assert placement_events[0].placement == placed
    assert placement_events[0].previous_placement is None
    assert placement_events[0].object_boundary_structure == structure

    light_uuid = grid.add_light_source(
        (0, 0),
        bright_radius_feet=20,
        dim_radius_feet=0,
        very_bright_radius_feet=1,
        anchor_uuid=wall.uuid,
        parent_event=parent.uuid,
    )
    assert light_uuid in wall.get_attached_light_sources()
    grid.add_light_source(
        (12, 0),
        bright_radius_feet=20,
        dim_radius_feet=0,
        parent_event=parent.uuid,
    )
    condition = AnchoredLifecycleCondition(
        source_entity_uuid=wall.source_entity_uuid,
        content_ref=OIL_SURFACE_RECIPE.ref,
        behavior_id=OIL_SURFACE_RECIPE.ref.content_id,
        position=(0, 0),
        affected_positions={(0, 0)},
        layer=SpatialEffectLayer.FIELD,
        occupancy_policy=SpatialEffectOccupancyPolicy.OVERLAPPING,
        anchor_kind=SpatialEffectAnchorKind.WORLD_OBJECT,
        anchor_uuid=wall.uuid,
    )
    condition.activate(parent_event=parent)

    before_move_revisions = (
        grid.movement_revision,
        grid.optical_revision,
        grid.propagation_revision,
    )
    old_tile = grid.get_tile(0, 0)
    shadow_tile = grid.get_tile(1, 0)
    new_tile = grid.get_tile(12, 0)
    far_shadow_tile = grid.get_tile(13, 0)
    assert (
        old_tile is not None
        and shadow_tile is not None
        and new_tile is not None
        and far_shadow_tile is not None
    )
    before_move_light = (
        old_tile.resolved_light_level,
        shadow_tile.resolved_light_level,
        new_tile.resolved_light_level,
        far_shadow_tile.resolved_light_level,
    )
    assert before_move_light == (
        LightLevel.VERY_BRIGHT,
        LightLevel.DARKNESS,
        LightLevel.BRIGHT_LIGHT,
        LightLevel.BRIGHT_LIGHT,
    )
    cursor = EventQueue.event_cursor()
    moved = grid.move_object(
        wall.uuid,
        (12, 0),
        boundary_direction=CardinalDirection.EAST,
        parent_event=parent.uuid,
    )
    move_events = [
        event
        for _index, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, SpatialChangeEvent)
        and event.object_uuid == wall.uuid
    ]
    assert [
        (event.change_type, event.phase)
        for event in move_events
    ] == [
        (change_type, phase)
        for change_type in (
            SpatialChangeType.OBJECT_REMOVED,
            SpatialChangeType.OBJECT_PLACED,
        )
        for phase in (
            EventPhase.DECLARATION,
            EventPhase.EXECUTION,
            EventPhase.EFFECT,
            EventPhase.COMPLETION,
        )
    ]
    assert all(event.parent_event == parent.uuid for event in move_events)
    departure = next(
        event
        for event in move_events
        if event.change_type is SpatialChangeType.OBJECT_REMOVED
        and event.phase is EventPhase.COMPLETION
    )
    arrival = next(
        event
        for event in move_events
        if event.change_type is SpatialChangeType.OBJECT_PLACED
        and event.phase is EventPhase.COMPLETION
    )
    assert departure.placement is None
    assert departure.object_boundary_structure is None
    assert departure.previous_placement == placed
    assert departure.old_position == moved.position
    assert arrival.placement == moved
    assert arrival.object_boundary_structure == structure
    assert arrival.previous_placement == placed
    assert departure.parent_event == parent.uuid
    assert arrival.parent_event == parent.uuid
    assert [
        event.phase
        for event in move_events
        if event.change_type is SpatialChangeType.OBJECT_REMOVED
    ] == [
        EventPhase.DECLARATION,
        EventPhase.EXECUTION,
        EventPhase.EFFECT,
        EventPhase.COMPLETION,
    ]
    assert [
        event.phase
        for event in move_events
        if event.change_type is SpatialChangeType.OBJECT_PLACED
    ] == [
        EventPhase.DECLARATION,
        EventPhase.EXECUTION,
        EventPhase.EFFECT,
        EventPhase.COMPLETION,
    ]
    light_facts = [
        event
        for _index, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, SpatialChangeEvent)
        and event.event_type is EventType.SPATIAL_LIGHT_CHANGED
        and event.phase is EventPhase.COMPLETION
    ]
    assert any(
        event.light_level_map is not None
        and event.light_level_map.get("1,0") == LightLevel.BRIGHT_LIGHT.value
        for event in light_facts
    )
    assert any(
        event.light_level_map is not None
        and event.light_level_map.get("1,0") == LightLevel.DARKNESS.value
        and event.light_level_map.get("12,0") == LightLevel.VERY_BRIGHT.value
        for event in light_facts
    )
    assert any(
        event.light_level_map is not None
        and event.light_level_map.get("13,0") == LightLevel.DARKNESS.value
        for event in light_facts
    )
    assert (
        grid.movement_revision,
        grid.optical_revision,
        grid.propagation_revision,
    ) == tuple(revision + 2 for revision in before_move_revisions)
    assert grid.get_object_placement(wall.uuid) == moved
    assert grid.get_boundary_objects_at(
        (0, 0), CardinalDirection.EAST,
    ) == set()
    assert grid.get_boundary_objects_at(
        (12, 0), CardinalDirection.EAST,
    ) == {wall.uuid}
    assert (
        grid.movement_revision,
        grid.optical_revision,
        grid.propagation_revision,
    ) == tuple(revision + 2 for revision in before_move_revisions)

    cursor = EventQueue.event_cursor()
    oriented = grid.orient_object(wall.uuid, CardinalDirection.SOUTH)
    orientation_events = [
        event
        for _index, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, SpatialChangeEvent)
        and event.phase is EventPhase.COMPLETION
        and event.object_uuid == wall.uuid
    ]
    assert [event.change_type for event in orientation_events] == [
        SpatialChangeType.OBJECT_CHANGED,
    ]
    assert orientation_events[0].placement == oriented
    assert orientation_events[0].previous_placement == moved
    assert orientation_events[0].object_boundary_structure == structure

    cursor = EventQueue.event_cursor()
    grid.remove_object(wall.uuid)
    removal_events = [
        event
        for _index, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, SpatialChangeEvent)
        and event.phase is EventPhase.COMPLETION
        and event.object_uuid == wall.uuid
    ]
    assert [event.change_type for event in removal_events] == [
        SpatialChangeType.OBJECT_REMOVED,
    ]
    assert removal_events[0].placement is None
    assert removal_events[0].object_boundary_structure is None
    assert removal_events[0].previous_placement == oriented


def test_move_object_rejects_while_events_are_disabled_without_mutation() -> None:
    """Runtime relocation requires lifecycle publication and remains untouched on rejection."""
    reset_combat_state()
    grid = get_map()
    grid.disable_events()
    grid.create_rectangle(0, 0, 2, 1, surface=TileSurface(base_material=Material.STONE))
    grid.enable_events(flush_pending=False)
    item = CenterOccupant(source_entity_uuid=uuid4(), name="Events-required mover")
    placed = grid.place_object(item.uuid, (0, 0))
    grid.add_light_source(
        (0, 0),
        bright_radius_feet=5,
        dim_radius_feet=0,
        anchor_uuid=item.uuid,
    )
    before_revisions = (
        grid.movement_revision,
        grid.optical_revision,
        grid.propagation_revision,
    )
    before_cursor = EventQueue.event_cursor()
    before_placements = grid.get_all_object_placements()
    before_objects = (
        grid.get_center_objects_at((0, 0)),
        grid.get_center_objects_at((1, 0)),
    )
    before_light = tuple(
        (
            position,
            grid.get_tile(*position).resolved_light_level,
        )
        for position in sorted(grid.get_all_tiles())
    )

    grid.disable_events()
    with pytest.raises(RuntimeError, match="requires enabled spatial event publication"):
        grid.move_object(item.uuid, (1, 0))

    assert grid.get_object_placement(item.uuid) == placed
    assert grid.get_all_object_placements() == before_placements
    assert (
        grid.get_center_objects_at((0, 0)),
        grid.get_center_objects_at((1, 0)),
    ) == before_objects
    assert tuple(
        (
            position,
            grid.get_tile(*position).resolved_light_level,
        )
        for position in sorted(grid.get_all_tiles())
    ) == before_light
    assert (
        grid.movement_revision,
        grid.optical_revision,
        grid.propagation_revision,
    ) == before_revisions
    assert list(EventQueue.iter_events_since(before_cursor)) == []
    grid.enable_events(flush_pending=False)


def test_boundary_move_into_a_live_incident_edge_invalidates_aggregate_channels() -> None:
    """A move from an outer side compares the newly live ordered edge exactly."""
    reset_combat_state()
    grid = get_map()
    grid.disable_events()
    grid.create_rectangle(0, 0, 2, 1, surface=TileSurface(base_material=Material.STONE))
    grid.enable_events(flush_pending=False)
    wall = DirectionalWall(
        source_entity_uuid=uuid4(),
    )
    grid.place_object(
        wall.uuid,
        (0, 0),
        boundary_direction=CardinalDirection.WEST,
    )
    assert grid.can_transition((1, 0), (0, 0))
    revisions_before = (
        grid.movement_revision,
        grid.optical_revision,
        grid.propagation_revision,
    )

    grid.move_object(
        wall.uuid,
        (1, 0),
        boundary_direction=CardinalDirection.WEST,
    )

    assert not grid.can_transition((1, 0), (0, 0))
    assert (
        grid.movement_revision,
        grid.optical_revision,
        grid.propagation_revision,
    ) == tuple(revision + 1 for revision in revisions_before)


def test_nonoccupying_center_objects_coexist_with_an_occupying_object() -> None:
    """Attachments share a center without weakening occupying collision rules."""
    reset_combat_state()
    grid = get_map()
    grid.disable_events()
    grid.create_rectangle(0, 0, 1, 1, surface=TileSurface(base_material=Material.STONE))
    grid.enable_events(flush_pending=False)
    occupant = CenterOccupant(source_entity_uuid=uuid4(), name="Occupying object")
    attachment = BaseItem(source_entity_uuid=uuid4(), name="Nonoccupying attachment")

    grid.place_object(occupant.uuid, (0, 0))
    grid.place_object(attachment.uuid, (0, 0))

    assert grid.get_center_objects_at((0, 0), height=0) == {
        occupant.uuid,
        attachment.uuid,
    }
    assert grid.get_objects_at((0, 0)) == {occupant.uuid, attachment.uuid}


def test_center_support_height_is_required_but_boundary_base_is_independent() -> None:
    """Support mutation rejects center placements while preserving boundary policy."""
    reset_combat_state()
    grid = get_map()
    grid.disable_events()
    grid.create_rectangle(0, 0, 2, 1, surface=TileSurface(base_material=Material.STONE))
    grid.enable_events(flush_pending=False)
    center = CenterOccupant(source_entity_uuid=uuid4(), name="Support center")
    boundary = BoundaryOccupant(source_entity_uuid=uuid4(), name="Independent boundary")
    grid.place_object(center.uuid, (0, 0))
    grid.remove_object(center.uuid)
    grid.place_object(
        boundary.uuid,
        (0, 0),
        boundary_direction=CardinalDirection.EAST,
        base_height_steps=3,
    )
    assert grid.set_tile_elevation(
        (0, 0),
        height=1,
        surface_kind=grid.get_tile(0, 0).elevation_surface_kind,
        slope_axis=grid.get_tile(0, 0).slope_axis,
    ) is True
    assert grid.get_object_placement(boundary.uuid).base_height_steps == 3

    center = CenterOccupant(source_entity_uuid=uuid4(), name="Support center 2")
    grid.place_object(center.uuid, (1, 0))
    with pytest.raises(ValueError, match="center object placements"):
        grid.set_tile_elevation(
            (1, 0),
            height=1,
            surface_kind=grid.get_tile(1, 0).elevation_surface_kind,
            slope_axis=grid.get_tile(1, 0).slope_axis,
        )


def test_rejected_move_leaves_authority_and_events_unchanged() -> None:
    """Destination collision is rejected before origin mutation or success facts."""
    reset_combat_state()
    grid = get_map()
    grid.disable_events()
    grid.create_rectangle(0, 0, 2, 1, surface=TileSurface(base_material=Material.STONE))
    grid.enable_events(flush_pending=False)
    first = CenterOccupant(source_entity_uuid=uuid4(), name="First")
    second = CenterOccupant(source_entity_uuid=uuid4(), name="Second")
    grid.place_object(first.uuid, (0, 0))
    grid.place_object(second.uuid, (1, 0))
    before = grid.get_object_placement(first.uuid)
    cursor = EventQueue.event_cursor()

    with pytest.raises(ValueError, match="occupied"):
        grid.move_object(first.uuid, (1, 0))

    assert grid.get_object_placement(first.uuid) == before
    assert grid.get_objects_at((0, 0)) == {first.uuid}
    assert grid.get_objects_at((1, 0)) == {second.uuid}
    assert list(EventQueue.iter_events_since(cursor)) == []


def test_surface_replacement_preserves_direct_spatial_conditions_and_reference_fold() -> None:
    """Surface facts replace only surface data and retain independent owners."""
    reset_combat_state()
    grid = get_map()
    grid.disable_events()
    grid.create_rectangle(0, 0, 1, 1, surface=TileSurface(base_material=Material.STONE))
    grid.enable_events(flush_pending=False)
    tile = grid.get_tile(0, 0)
    assert tile is not None
    direct = BaseCondition(
        source_entity_uuid=uuid4(),
        name="Direct test condition",
        behavior_id="condition.surface_direct",
    )
    assert tile.add_condition(direct) is not None
    spatial = materialize_spatial_condition(
        OIL_SURFACE_RECIPE,
        uuid4(),
        position=(0, 0),
        faction="test",
        condition_type=OilSurface,
        condition_fields={"affected_positions": {(0, 0)}},
    )
    spatial.activate(parent_event=None)
    replacement = TileSurface(
        base_material=Material.EARTH,
        layers=(SurfaceLayer(material=Material.VEGETATION),),
    )

    assert grid.replace_tile_surface((0, 0), replacement) is True
    assert tile.surface == replacement
    assert direct.uuid in tile.get_conditions()
    assert spatial.uuid in tile.get_conditions()

    completed = [
        event
        for event in EventQueue.get_events_by_type(EventType.SPATIAL_TILE_CHANGED)
        if isinstance(event, SpatialChangeEvent)
        and event.phase is EventPhase.COMPLETION
        and event.position == (0, 0)
    ]
    folded_surface = TileSurface.model_validate_json(
        completed[-1].tile_surface.model_dump_json()
    )
    assert {"surface": folded_surface}["surface"] == replacement


def test_world_object_placement_identity_mismatch_is_rejected_by_all_public_models() -> None:
    """Item, world-snapshot, and spatial-event contracts reject wrong UUIDs."""
    item = BaseItem(source_entity_uuid=uuid4(), name="Identity item")
    wrong_uuid = uuid4()
    placement = WorldObjectPlacement(
        object_uuid=wrong_uuid,
        tile_uuid=uuid4(),
        position=(0, 0),
        kind=WorldPlacementKind.CENTER,
        occupies_bands=False,
        base_height_steps=0,
        top_height_steps=1,
    )
    with pytest.raises(ValidationError, match="object_uuid"):
        ItemLocationStateEvent(
            source_entity_uuid=uuid4(),
            item_state=item.to_item_state(),
            location=ItemLocation.FLOOR,
            world_placement=placement,
            phase=EventPhase.COMPLETION,
            use_register=False,
        )
    with pytest.raises(ValidationError, match="object_uuid"):
        WorldObjectState(placement=placement, item=item.to_item_state())
    with pytest.raises(ValidationError, match="object_uuid"):
        SpatialChangeEvent(
            source_entity_uuid=uuid4(),
            event_type=EventType.SPATIAL_OBJECT_PLACED,
            change_type=SpatialChangeType.OBJECT_PLACED,
            position=(0, 0),
            object_uuid=item.uuid,
            placement=placement,
            phase=EventPhase.COMPLETION,
            use_register=False,
        )


def test_serialized_placement_rebuild_is_bijective_and_rejects_ambiguity() -> None:
    """Cold placement values rebuild both authorities or leave them untouched."""
    reset_combat_state()
    grid = get_map()
    grid.disable_events()
    grid.create_rectangle(0, 0, 2, 1, surface=TileSurface(base_material=Material.STONE))
    grid.enable_events(flush_pending=False)
    center = CenterOccupant(source_entity_uuid=uuid4(), name="Rebuilt center")
    boundary = BoundaryOccupant(source_entity_uuid=uuid4(), name="Rebuilt boundary")
    center_placement = grid.place_object(center.uuid, (0, 0))
    boundary_placement = grid.place_object(
        boundary.uuid,
        (0, 0),
        boundary_direction=CardinalDirection.EAST,
        orientation=CardinalDirection.NORTH,
    )
    normal_anchor_objects = grid.get_objects_at((0, 0))
    normal_neighbor_objects = grid.get_objects_at((1, 0))
    normal_anchor_boundary = grid.get_boundary_objects_at(
        (0, 0), CardinalDirection.EAST,
    )
    grid.remove_object(center.uuid)
    grid.remove_object(boundary.uuid)

    successful_rebuild_cursor = EventQueue.event_cursor()
    restored = grid.rebuild_object_placements([
        WorldObjectPlacement.model_validate_json(center_placement.model_dump_json()),
        WorldObjectPlacement.model_validate_json(boundary_placement.model_dump_json()),
    ])
    assert list(EventQueue.iter_events_since(successful_rebuild_cursor)) == []
    assert restored == tuple(
        sorted(
            (center_placement, boundary_placement),
            key=lambda placement: str(placement.object_uuid),
        )
    )
    assert grid.get_objects_at((0, 0)) == normal_anchor_objects
    assert grid.get_objects_at((1, 0)) == normal_neighbor_objects
    assert grid.get_boundary_objects_at(
        (0, 0), CardinalDirection.EAST,
    ) == normal_anchor_boundary

    before = tuple(grid.get_all_object_placements())
    with pytest.raises(ValueError, match="duplicate"):
        grid.rebuild_object_placements([center_placement, center_placement])
    assert tuple(grid.get_all_object_placements()) == before

    bad_tile = center_placement.model_copy(update={"tile_uuid": uuid4()})
    with pytest.raises(ValueError, match="exact Tile"):
        grid.rebuild_object_placements([bad_tile, boundary_placement])
    assert tuple(grid.get_all_object_placements()) == before

    opposite = BoundaryOccupant(source_entity_uuid=uuid4(), name="Independent side")
    bad_opposite = WorldObjectPlacement(
        object_uuid=opposite.uuid,
        tile_uuid=grid.get_tile(1, 0).uuid,
        position=(1, 0),
        kind=WorldPlacementKind.BOUNDARY,
        occupies_bands=True,
        boundary_direction=CardinalDirection.WEST,
        base_height_steps=0,
        top_height_steps=1,
        orientation=CardinalDirection.WEST,
    )
    restored_with_opposite = grid.rebuild_object_placements([
        center_placement,
        boundary_placement,
        bad_opposite,
    ])
    assert restored_with_opposite == tuple(
        sorted(
            (center_placement, boundary_placement, bad_opposite),
            key=lambda placement: str(placement.object_uuid),
        )
    )
    assert grid.get_boundary_objects_at(
        (1, 0), CardinalDirection.WEST,
    ) == {opposite.uuid}

    same_side = BoundaryOccupant(source_entity_uuid=uuid4(), name="Same-side rebuild")
    bad_same_side = WorldObjectPlacement(
        object_uuid=same_side.uuid,
        tile_uuid=grid.get_tile(0, 0).uuid,
        position=(0, 0),
        kind=WorldPlacementKind.BOUNDARY,
        occupies_bands=True,
        boundary_direction=CardinalDirection.EAST,
        base_height_steps=0,
        top_height_steps=1,
        orientation=CardinalDirection.EAST,
    )
    light_uuid = grid.add_light_source((0, 0), 5, 5)
    try:
        before_failed_rebuild = tuple(grid.get_all_object_placements())
        side_i_before = grid.get_boundary_objects_at(
            (0, 0), CardinalDirection.EAST,
        )
        side_j_before = grid.get_boundary_objects_at(
            (1, 0), CardinalDirection.WEST,
        )
        revisions_before = (
            grid.movement_revision,
            grid.optical_revision,
            grid.propagation_revision,
        )
        light_positions = ((0, 0), (1, 0))
        light_before = tuple(
            grid.get_tile(*position).resolved_light_level
            for position in light_positions
        )
        rejection_cursor = EventQueue.event_cursor()

        with pytest.raises(ValueError, match="occupying band collision"):
            grid.rebuild_object_placements([
                center_placement,
                boundary_placement,
                bad_opposite,
                bad_same_side,
            ])

        failed_diagnostics = grid.last_operation_diagnostics
        assert tuple(grid.get_all_object_placements()) == before_failed_rebuild
        assert grid.get_boundary_objects_at(
            (0, 0), CardinalDirection.EAST,
        ) == side_i_before
        assert grid.get_boundary_objects_at(
            (1, 0), CardinalDirection.WEST,
        ) == side_j_before
        assert (
            grid.movement_revision,
            grid.optical_revision,
            grid.propagation_revision,
        ) == revisions_before
        assert tuple(
            grid.get_tile(*position).resolved_light_level
            for position in light_positions
        ) == light_before
        assert list(EventQueue.iter_events_since(rejection_cursor)) == []
        assert failed_diagnostics.operation == "rebuild_object_placements"
        assert failed_diagnostics.bands_replaced == 0
    finally:
        grid.remove_light_source(light_uuid)


def test_world_initialized_round_trip_rebuilds_opposing_boundary_placements() -> None:
    """Public world facts round-trip two independent exact side placements."""
    reset_combat_state()
    grid = get_map()
    grid.disable_events()
    grid.create_rectangle(
        0,
        0,
        2,
        1,
        surface=TileSurface(base_material=Material.STONE),
    )
    grid.enable_events(flush_pending=False)
    first = StructuralBoundaryOccupant(
        source_entity_uuid=uuid4(),
        name="World fact east",
    )
    second = StructuralBoundaryOccupant(
        source_entity_uuid=uuid4(),
        name="World fact west",
    )
    first_placement = grid.place_object(
        first.uuid,
        (0, 0),
        boundary_direction=CardinalDirection.EAST,
        base_height_steps=2,
    )
    second_placement = grid.place_object(
        second.uuid,
        (1, 0),
        boundary_direction=CardinalDirection.WEST,
        base_height_steps=2,
    )
    forward_before = grid.get_world_edge((0, 0), (1, 0))
    reverse_before = grid.get_world_edge((1, 0), (0, 0))
    first_state = first.to_item_state()
    second_state = second.to_item_state()

    world_event = WorldInitializedEvent(
        source_entity_uuid=uuid4(),
        source_entity_name="World",
        phase=EventPhase.COMPLETION,
        use_register=False,
        battlefield_id="test.opposing.boundaries",
        battlefield_name="Opposing boundaries",
        bounds=grid.bounds,
        width=grid.width,
        height=grid.height,
        tiles=(),
        objects=(
            WorldObjectState(placement=first_placement, item=first_state),
            WorldObjectState(placement=second_placement, item=second_state),
        ),
        connectors=(),
    )
    restored_event = WorldInitializedEvent.model_validate_json(
        world_event.model_dump_json()
    )
    assert tuple(row.item for row in restored_event.objects) == (
        first_state,
        second_state,
    )

    grid.remove_object(first.uuid)
    grid.remove_object(second.uuid)
    restored = grid.rebuild_object_placements(
        [row.placement for row in restored_event.objects]
    )

    assert restored == tuple(
        sorted(
            (first_placement, second_placement),
            key=lambda placement: str(placement.object_uuid),
        )
    )
    assert grid.get_boundary_objects_at(
        (0, 0), CardinalDirection.EAST,
    ) == {first.uuid}
    assert grid.get_boundary_objects_at(
        (1, 0), CardinalDirection.WEST,
    ) == {second.uuid}
    assert grid.get_world_edge((0, 0), (1, 0)) == forward_before
    assert grid.get_world_edge((1, 0), (0, 0)) == reverse_before


def test_placement_diagnostics_and_timing_are_local_to_used_space() -> None:
    """Structured placement work does not scale with distant unused Tiles."""
    def measure(size: int) -> object:
        reset_combat_state()
        grid = get_map()
        grid.disable_events()
        grid.create_rectangle(0, 0, size, size, surface=TileSurface(base_material=Material.STONE))
        grid.enable_events(flush_pending=False)
        diagnostics = None
        for _index in range(5):
            item = CenterOccupant(source_entity_uuid=uuid4(), name="Locality probe")
            grid.place_object(item.uuid, (0, 0))
            diagnostics = grid.last_operation_diagnostics
            grid.remove_object(item.uuid)
        assert diagnostics is not None
        return diagnostics

    small_diag = measure(2)
    large_diag = measure(40)
    assert (small_diag.tiles_inspected, small_diag.bands_inspected) == (
        large_diag.tiles_inspected,
        large_diag.bands_inspected,
    )
    assert small_diag.placement_iterator_rows_visited == 0
    assert large_diag.placement_iterator_rows_visited == 0


def test_boundary_placement_diagnostics_count_only_owner_and_local_bands() -> None:
    """Boundary admission work excludes adjacent and distant Tiles."""
    def measure(width: int, height: int):
        reset_combat_state()
        grid = get_map()
        grid.disable_events()
        grid.create_rectangle(
            0,
            0,
            width,
            height,
            surface=TileSurface(base_material=Material.STONE),
        )
        grid.enable_events(flush_pending=False)
        boundary = BoundaryOccupant(
            source_entity_uuid=uuid4(),
            name="Boundary locality probe",
        )
        grid.place_object(
            boundary.uuid,
            (0, 0),
            boundary_direction=CardinalDirection.EAST,
        )
        return grid.last_operation_diagnostics

    without_neighbor = measure(1, 1)
    with_neighbor = measure(2, 1)
    with_distant_tiles = measure(40, 40)

    for diagnostics in (without_neighbor, with_neighbor, with_distant_tiles):
        assert diagnostics.operation == "place_object"
        assert diagnostics.tiles_inspected == 1
        assert diagnostics.bands_inspected == 1
        assert diagnostics.placement_iterator_rows_visited == 0
    assert (with_neighbor.tiles_inspected, with_neighbor.bands_inspected) == (
        without_neighbor.tiles_inspected,
        without_neighbor.bands_inspected,
    )
    assert (with_distant_tiles.tiles_inspected, with_distant_tiles.bands_inspected) == (
        without_neighbor.tiles_inspected,
        without_neighbor.bands_inspected,
    )


def test_rebuild_diagnostics_ignore_distant_unused_tiles() -> None:
    """Non-optical rebuild locality ignores primed distant caches and lights."""
    def rebuild(size: int):
        reset_combat_state()
        grid = get_map()
        grid.disable_events()
        grid.create_rectangle(0, 0, size, size, surface=TileSurface(base_material=Material.STONE))
        distant_source_position = (size - 2, size - 2)
        light_uuid = grid.add_light_source(distant_source_position, 10, 10)
        distant_positions = circle_positions(distant_source_position, 4)
        before_light = {
            position: grid.get_tile(*position).resolved_light_level
            for position in distant_positions
            if grid.get_tile(*position) is not None
        }
        grid.compute_fov(distant_source_position, 2)
        grid.compute_paths(distant_source_position, max_distance=2)
        grid.compute_propagation_fov(distant_source_position, 2)
        grid.enable_events(flush_pending=False)
        item = CenterOccupant(source_entity_uuid=uuid4(), name="Rebuild locality")
        placement = grid.place_object(item.uuid, (0, 0))
        grid.remove_object(item.uuid)
        grid.rebuild_object_placements([placement])
        after_light = {
            position: grid.get_tile(*position).resolved_light_level
            for position in distant_positions
            if grid.get_tile(*position) is not None
        }
        assert after_light == before_light
        grid.remove_light_source(light_uuid)
        return grid.last_operation_diagnostics

    small = rebuild(2)
    large = rebuild(40)
    assert (small.tiles_inspected, small.bands_inspected) == (
        large.tiles_inspected,
        large.bands_inspected,
    )
    assert small.placement_iterator_rows_visited == 1
    assert large.placement_iterator_rows_visited == 1


def test_identical_place_replay_is_a_public_noop() -> None:
    """Replaying one committed placement returns it without bands or facts."""
    reset_combat_state()
    grid = get_map()
    grid.disable_events()
    grid.create_rectangle(0, 0, 1, 1, surface=TileSurface(base_material=Material.STONE))
    grid.enable_events(flush_pending=False)
    item = CenterOccupant(source_entity_uuid=uuid4(), name="Replay item")

    committed = grid.place_object(item.uuid, (0, 0))
    before_band = grid.get_tile(0, 0).get_center_object_bands()
    cursor = EventQueue.event_cursor()
    replay = grid.place_object(item.uuid, (0, 0))

    assert replay is committed
    assert grid.get_tile(0, 0).get_center_object_bands() == before_band
    assert [
        event for _index, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, SpatialChangeEvent)
        and event.object_uuid == item.uuid
    ] == []


def test_phase_one_public_values_expose_strict_json_schemas() -> None:
    """The serialized Phase-1 values publish their complete field contracts."""
    surface_properties = TileSurface.model_json_schema()["properties"]
    layer_properties = SurfaceLayer.model_json_schema()["properties"]
    placement_properties = WorldObjectPlacement.model_json_schema()["properties"]

    assert {"base_material", "layers", "description"} <= set(surface_properties)
    assert {"material", "description"} <= set(layer_properties)
    assert {
        "object_uuid",
        "tile_uuid",
        "position",
        "kind",
        "occupies_bands",
        "boundary_direction",
        "base_height_steps",
        "top_height_steps",
        "orientation",
    } <= set(placement_properties)


def test_slice_6_3_renderer_fields_are_absent_and_rejected() -> None:
    """Renderer fields are deleted from the public Tile and BaseItem contracts."""
    tile_properties = set(Tile.model_fields)
    item_properties = set(BaseItem.model_fields)
    retired_tile_fields = {"sprite_name", "walkable"}
    retired_item_fields = {
        "map_char",
        "visual_item_name",
        "visual_variant_id",
        "walkable",
        "position",
    }

    assert retired_tile_fields.isdisjoint(tile_properties)
    assert retired_item_fields.isdisjoint(item_properties)

    tile = floor_factory((0, 0))
    tile_payload = tile.model_dump(mode="python")
    assert retired_tile_fields.isdisjoint(tile_payload)
    item = BaseItem(source_entity_uuid=uuid4())
    item_payload = item.model_dump(mode="python")
    assert retired_item_fields.isdisjoint(item_payload)
    computed_view_fields = {
        "contextual_immunity_names",
        "values_dict_uuid_name",
        "values_dict_name_uuid",
        "blocks_dict_uuid_name",
        "blocks_dict_name_uuid",
    }
    clean_tile_payload = {
        key: value
        for key, value in tile_payload.items()
        if key not in computed_view_fields
    }
    clean_item_payload = {
        key: value
        for key, value in item_payload.items()
        if key not in computed_view_fields
    }
    assert Tile.model_validate(clean_tile_payload).uuid == tile.uuid
    assert BaseItem.model_validate(clean_item_payload).uuid == item.uuid

    for field_name, value in (
        ("sprite_name", "floor.png"),
        ("walkable", True),
    ):
        with pytest.raises(ValidationError):
            Tile.model_validate({**clean_tile_payload, field_name: value})
    for field_name, value in (
        ("map_char", "@"),
        ("visual_item_name", "Floor"),
        ("visual_variant_id", "floor"),
        ("walkable", True),
        ("position", (0, 0)),
    ):
        with pytest.raises(ValidationError):
            BaseItem.model_validate({**clean_item_payload, field_name: value})
        with pytest.raises(ValidationError):
            BaseItem(
                source_entity_uuid=uuid4(),
                **{field_name: value},
            )

    assert not hasattr(BaseItem, "get_map_char")
    assert not hasattr(Tile, "get_map_char")
    with pytest.raises(TypeError):
        Tile.create(
            (0, 0),
            surface=TileSurface(base_material=Material.STONE),
            sprite_name="floor.png",
        )
    grid = get_map()
    with pytest.raises(TypeError):
        grid.set_tile(
            0,
            0,
            surface=TileSurface(base_material=Material.STONE),
            sprite_name="floor.png",
        )
    with pytest.raises(TypeError):
        grid.create_rectangle(
            0,
            0,
            1,
            1,
            surface=TileSurface(base_material=Material.STONE),
            sprite_name="floor.png",
        )


def test_surface_replacement_preserves_live_source_owned_light_contribution_and_cap() -> None:
    """Surface replacement does not discard active source modifiers or caps."""
    reset_combat_state()
    grid = get_map()
    grid.disable_events()
    grid.create_rectangle(0, 0, 1, 1, surface=TileSurface(base_material=Material.STONE))
    grid.set_tile_base_light((0, 0), LightLevel.DARKNESS)
    grid.enable_events(flush_pending=False)
    source_uuid = uuid4()
    cap_uuid = uuid4()
    grid.apply_tile_light_modifier(
        source_uuid,
        {(0, 0)},
        LightLevel.VERY_BRIGHT,
        cap=False,
    )
    grid.apply_tile_light_modifier(
        cap_uuid,
        {(0, 0)},
        LightLevel.BRIGHT_LIGHT,
        cap=True,
    )
    assert grid.get_tile(0, 0).resolved_light_level is LightLevel.BRIGHT_LIGHT

    grid.replace_tile_surface(
        (0, 0),
        TileSurface(base_material=Material.EARTH),
    )

    assert grid.get_tile(0, 0).resolved_light_level is LightLevel.BRIGHT_LIGHT
    grid.remove_tile_light_modifier(source_uuid, {(0, 0)})
    grid.remove_tile_light_modifier(cap_uuid, {(0, 0)})
    assert grid.get_tile(0, 0).resolved_light_level is LightLevel.DARKNESS


def test_rebuild_restores_directional_blocking_and_light_shadow() -> None:
    """A cold rebuild restores directional and optical mechanics locally."""
    reset_combat_state()
    grid = get_map()
    grid.disable_events()
    grid.create_rectangle(0, 0, 3, 1, surface=TileSurface(base_material=Material.STONE))
    for position in grid.get_all_tiles():
        grid.set_tile_base_light(position, LightLevel.DARKNESS)
    grid.enable_events(flush_pending=False)

    wall = DirectionalWall(
        source_entity_uuid=uuid4(),
    )
    wall_placement = grid.place_object(
        wall.uuid,
        (0, 0),
        boundary_direction=CardinalDirection.EAST,
    )
    assert grid.can_transition((0, 0), (1, 0)) is False
    light_uuid = grid.add_light_source((0, 0), 15, 0)
    shadowed = grid.get_tile(2, 0).resolved_light_level
    assert shadowed is LightLevel.DARKNESS
    grid.remove_object(wall.uuid)
    assert grid.can_transition((0, 0), (1, 0)) is True
    assert grid.get_tile(2, 0).resolved_light_level is not shadowed

    movement_revision = grid.movement_revision
    grid.rebuild_object_placements([wall_placement])
    assert grid.movement_revision == movement_revision + 1
    assert grid.can_transition((0, 0), (1, 0)) is False
    assert grid.get_tile(2, 0).resolved_light_level is shadowed
    grid.remove_light_source(light_uuid)


def test_rebuild_light_failure_restores_bounded_light_state_after_directional_settlement() -> None:
    """A later light failure restores an earlier light's affected field exactly."""
    reset_combat_state()
    grid = get_map()
    grid.disable_events()
    grid.create_rectangle(0, 0, 7, 2, surface=TileSurface(base_material=Material.STONE))

    wall = DirectionalWall(
        source_entity_uuid=uuid4(),
    )
    wall_placement = grid.place_object(
        wall.uuid,
        (2, 1),
        boundary_direction=CardinalDirection.EAST,
    )
    provider = ThrowingCenterMechanic(
        source_entity_uuid=uuid4(),
        name="Far optical provider",
    )
    provider_placement = grid.place_object(provider.uuid, (4, 1))
    grid.remove_object(wall.uuid)

    first_light_uuid = grid.add_light_source((1, 1), 15, 0)
    second_light_uuid = grid.add_light_source((3, 1), 15, 0)
    grid.remove_light_source(second_light_uuid)
    first_light_field = {
        position: tile.resolved_light_level
        for position, tile in grid.get_all_tiles().items()
    }
    second_light_uuid = grid.add_light_source((3, 1), 15, 0)
    grid.enable_events(flush_pending=False)

    before_placements = tuple(grid.get_all_object_placements())
    before_objects = grid.get_objects_at((2, 1))
    before_directional = (
        grid.can_transition((2, 1), (3, 1)),
        grid.can_optical_transition((2, 1), (3, 1)),
        grid.can_propagate_transition((2, 1), (3, 1)),
    )
    before_revisions = (
        grid.optical_revision,
        grid.movement_revision,
        grid.propagation_revision,
    )
    provider.raise_on_center_mechanic = True
    cursor = EventQueue.event_cursor()

    with pytest.raises(RuntimeError, match="center mechanic provider"):
        grid.rebuild_object_placements([wall_placement, provider_placement])

    assert tuple(grid.get_all_object_placements()) == before_placements
    assert grid.get_objects_at((2, 1)) == before_objects
    assert (
        grid.can_transition((2, 1), (3, 1)),
        grid.can_optical_transition((2, 1), (3, 1)),
        grid.can_propagate_transition((2, 1), (3, 1)),
    ) == before_directional
    assert (
        grid.optical_revision,
        grid.movement_revision,
        grid.propagation_revision,
    ) == before_revisions
    assert list(EventQueue.iter_events_since(cursor)) == []

    grid.remove_light_source(second_light_uuid)
    assert {
        position: tile.resolved_light_level
        for position, tile in grid.get_all_tiles().items()
    } == first_light_field
    grid.remove_light_source(first_light_uuid)


def test_rebuild_invalidates_primed_fov_for_a_center_optical_blocker() -> None:
    """Center optical changes advance the existing FOV cache revision."""
    reset_combat_state()
    grid = get_map()
    grid.disable_events()
    grid.create_rectangle(0, 0, 3, 1, surface=TileSurface(base_material=Material.STONE))
    grid.enable_events(flush_pending=False)
    blocker = OpticalCenterBlocker(source_entity_uuid=uuid4(), name="FOV blocker")

    assert (2, 0) in grid.compute_fov((0, 0), 3)
    placement = grid.place_object(blocker.uuid, (1, 0))
    assert (2, 0) not in grid.compute_fov((0, 0), 3)
    grid.remove_object(blocker.uuid)
    assert (2, 0) in grid.compute_fov((0, 0), 3)

    optical_revision = grid.optical_revision
    grid.rebuild_object_placements([placement])
    assert grid.optical_revision == optical_revision + 1
    assert (2, 0) not in grid.compute_fov((0, 0), 3)


def test_malformed_rebuild_preserves_authority_mechanics_and_diagnostics() -> None:
    """Malformed cold values fail before changing bands, mechanics, or counters."""
    reset_combat_state()
    grid = get_map()
    grid.disable_events()
    grid.create_rectangle(0, 0, 2, 1, surface=TileSurface(base_material=Material.STONE))
    grid.enable_events(flush_pending=False)
    item = CenterOccupant(source_entity_uuid=uuid4(), name="Stable rebuild")
    placement = grid.place_object(item.uuid, (0, 0))
    before = (
        grid.get_all_object_placements(),
        grid.get_objects_at((0, 0)),
        grid.can_transition((0, 0), (1, 0)),
    )
    bad = placement.model_copy(update={"tile_uuid": uuid4()})

    with pytest.raises(ValueError, match="exact Tile"):
        grid.rebuild_object_placements([bad])

    assert (
        grid.get_all_object_placements(),
        grid.get_objects_at((0, 0)),
        grid.can_transition((0, 0), (1, 0)),
    ) == before


def test_rebuild_provider_failure_restores_live_state_and_current_diagnostics() -> None:
    """A directional settlement failure restores the exact prior local state."""
    reset_combat_state()
    grid = get_map()
    grid.disable_events()
    grid.create_rectangle(0, 0, 2, 1, surface=TileSurface(base_material=Material.STONE))
    grid.enable_events(flush_pending=False)
    item = ThrowingRebuildDirectionalItem(
        source_entity_uuid=uuid4(),
        name="Rebuild throw",
    )
    placement = grid.place_object(
        item.uuid,
        (0, 0),
        boundary_direction=CardinalDirection.EAST,
    )
    grid.remove_object(item.uuid)
    before_revisions = (
        grid.optical_revision,
        grid.movement_revision,
        grid.propagation_revision,
    )
    before_directional = (
        grid.can_transition((0, 0), (1, 0)),
        grid.can_optical_transition((0, 0), (1, 0)),
        grid.can_propagate_transition((0, 0), (1, 0)),
    )
    before_bands = grid.get_objects_at((0, 0))
    item.raise_on_directional = True
    cursor = EventQueue.event_cursor()

    with pytest.raises(RuntimeError, match="rebuild directional provider"):
        grid.rebuild_object_placements([placement])

    diagnostics = grid.last_operation_diagnostics
    assert grid.get_object_placement(item.uuid) is None
    assert grid.get_objects_at((0, 0)) == before_bands
    assert (
        grid.can_transition((0, 0), (1, 0)),
        grid.can_optical_transition((0, 0), (1, 0)),
        grid.can_propagate_transition((0, 0), (1, 0)),
    ) == before_directional
    assert (
        grid.optical_revision,
        grid.movement_revision,
        grid.propagation_revision,
    ) == before_revisions
    assert list(EventQueue.iter_events_since(cursor)) == []
    assert diagnostics.operation == "rebuild_object_placements"
    assert diagnostics.bands_replaced == 0


def test_object_commands_restore_bands_borders_and_events_when_provider_throws() -> None:
    """Place, move, and orient roll back before publishing on provider failure."""
    reset_combat_state()
    grid = get_map()
    grid.disable_events()
    grid.create_rectangle(0, 0, 3, 1, surface=TileSurface(base_material=Material.STONE))
    grid.enable_events(flush_pending=False)

    placing = ThrowingDirectionalItem(source_entity_uuid=uuid4(), name="Place throw")
    placing.raise_on_directional = True
    cursor = EventQueue.event_cursor()
    with pytest.raises(RuntimeError, match="directional provider"):
        grid.place_object(
            placing.uuid,
            (0, 0),
            boundary_direction=CardinalDirection.EAST,
        )
    assert grid.get_object_placement(placing.uuid) is None
    assert grid.get_objects_at((0, 0)) == set()
    assert list(EventQueue.iter_events_since(cursor)) == []

    moving = ThrowingDirectionalItem(source_entity_uuid=uuid4(), name="Move throw")
    grid.place_object(
        moving.uuid,
        (0, 0),
        boundary_direction=CardinalDirection.EAST,
    )
    before_placement = grid.get_object_placement(moving.uuid)
    before_objects = grid.get_objects_at((0, 0))
    moving.raise_on_directional = True
    cursor = EventQueue.event_cursor()
    with pytest.raises(RuntimeError, match="directional provider"):
        grid.move_object(
            moving.uuid,
            (1, 0),
            boundary_direction=CardinalDirection.EAST,
        )
    assert grid.get_object_placement(moving.uuid) == before_placement
    assert grid.get_objects_at((0, 0)) == before_objects
    assert grid.get_objects_at((1, 0)) == set()
    assert list(EventQueue.iter_events_since(cursor)) == []

    boundary = ThrowingBoundaryItem(source_entity_uuid=uuid4(), name="Orient throw")
    grid.place_object(
        boundary.uuid,
        (2, 0),
        boundary_direction=CardinalDirection.WEST,
        orientation=CardinalDirection.NORTH,
    )
    before_placement = grid.get_object_placement(boundary.uuid)
    before_boundary = grid.get_boundary_objects_at((2, 0), CardinalDirection.WEST)
    boundary.raise_on_directional = True
    cursor = EventQueue.event_cursor()
    with pytest.raises(RuntimeError, match="directional provider"):
        grid.orient_object(boundary.uuid, CardinalDirection.SOUTH)
    assert grid.get_object_placement(boundary.uuid) == before_placement
    assert grid.get_boundary_objects_at((2, 0), CardinalDirection.WEST) == before_boundary
    assert grid.get_boundary_objects_at((2, 0), CardinalDirection.SOUTH) == set()
    assert list(EventQueue.iter_events_since(cursor)) == []
    boundary.raise_on_directional = False

    placing_center = ThrowingCenterMechanic(
        source_entity_uuid=uuid4(),
        name="Center place throw",
        raise_on_center_mechanic=True,
    )
    cursor = EventQueue.event_cursor()
    with pytest.raises(RuntimeError, match="center mechanic provider"):
        grid.place_object(placing_center.uuid, (1, 0))
    assert grid.get_object_placement(placing_center.uuid) is None
    assert grid.get_objects_at((1, 0)) == set()
    assert list(EventQueue.iter_events_since(cursor)) == []

    moving_center = ThrowingCenterMechanic(
        source_entity_uuid=uuid4(),
        name="Center move throw",
    )
    grid.place_object(moving_center.uuid, (1, 0))
    before_placement = grid.get_object_placement(moving_center.uuid)
    moving_center.raise_on_center_mechanic = True
    cursor = EventQueue.event_cursor()
    with pytest.raises(RuntimeError, match="center mechanic provider"):
        grid.move_object(moving_center.uuid, (2, 0))
    assert grid.get_object_placement(moving_center.uuid) == before_placement
    assert grid.get_objects_at((1, 0)) == {moving_center.uuid}
    assert grid.get_objects_at((2, 0)) == {boundary.uuid}
    assert list(EventQueue.iter_events_since(cursor)) == []

    orient_center = ThrowingCenterMechanic(
        source_entity_uuid=uuid4(),
        name="Center orient throw",
    )
    grid.place_object(orient_center.uuid, (2, 0))
    before_placement = grid.get_object_placement(orient_center.uuid)
    orient_center.raise_on_center_mechanic = True
    cursor = EventQueue.event_cursor()
    with pytest.raises(RuntimeError, match="center mechanic provider"):
        grid.orient_object(orient_center.uuid, CardinalDirection.SOUTH)
    assert grid.get_object_placement(orient_center.uuid) == before_placement
    assert grid.get_objects_at((2, 0)) == {orient_center.uuid, boundary.uuid}
    assert list(EventQueue.iter_events_since(cursor)) == []


def test_remove_diagnostics_reset_for_success_and_absent_noop() -> None:
    """Terminal diagnostics describe the current call, including an absent no-op."""
    reset_combat_state()
    grid = get_map()
    grid.disable_events()
    grid.create_rectangle(0, 0, 1, 1, surface=TileSurface(base_material=Material.STONE))
    grid.enable_events(flush_pending=False)
    item = CenterOccupant(source_entity_uuid=uuid4(), name="Diagnostics")
    grid.place_object(item.uuid, (0, 0))
    grid.remove_object(item.uuid)
    success = grid.last_operation_diagnostics
    grid.remove_object(item.uuid)
    absent = grid.last_operation_diagnostics

    assert success.operation == "remove_object"
    assert success.bands_replaced > 0
    assert absent == type(success)(operation="remove_object")


def test_remove_hook_failure_keeps_terminal_diagnostics_after_authority_removal() -> None:
    """Terminal hook failure does not retain an earlier operation snapshot."""
    reset_combat_state()
    grid = get_map()
    grid.disable_events()
    grid.create_rectangle(0, 0, 1, 1, surface=TileSurface(base_material=Material.STONE))
    grid.enable_events(flush_pending=False)
    item = ThrowingRemovalItem(source_entity_uuid=uuid4(), name="Removal throw")
    grid.place_object(item.uuid, (0, 0))
    cursor = EventQueue.event_cursor()

    with pytest.raises(RuntimeError, match="terminal removal hook failure"):
        grid.remove_object(item.uuid)

    diagnostics = grid.last_operation_diagnostics
    assert grid.get_object_placement(item.uuid) is None
    assert grid.get_objects_at((0, 0)) == set()
    assert list(EventQueue.iter_events_since(cursor)) == []
    assert diagnostics.operation == "remove_object"
