"""Central spatial registry for tiles, entities, objects, light, and paths."""

import math
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple, Set, DefaultDict
from uuid import UUID, uuid4
from collections import OrderedDict, defaultdict

from pydantic import BaseModel, Field

from dnd.core.elevation import support_distance_feet
from dnd.core.geometry import circle_positions, supercover_line, supercover_line_offsets
from dnd.core.dijkstra import dijkstra
from dnd.core.base_block import BaseBlock
from dnd.core.base_conditions import BaseCondition
from dnd.types.world import CardinalDirection, MovementMode, LightLevel
from dnd.types.materials import TileSurface
from dnd.core.base_tiles import (
    Tile,
    TileObjectBand,
    validate_elevation_surface_tuple,
)
from dnd.core.events.events_registry import (
    Event,
    EventPhase,
    EventQueue,
    EventType,
)
from dnd.core.events.world_events import (
    SpatialChangeEvent,
    SpatialChangeType,
    SensesUpdateHint,
    TileElevationChangeEvent,
    TraversalConnectorChangeEvent,
)
from dnd.types.spatial_effects import SpatialEffectLayer, SpatialEffectOccupancyPolicy
from dnd.core.world_edges import (
    AdjacentEdgeKey,
    ElevationSurfaceKind,
    SlopeAxis,
    WorldEdgeStructuralContribution,
    WorldEdgeView,
    progressive_elevation_transition,
    transition_axis,
)
from dnd.types.world import WorldEdgeChannel
from dnd.types.world_placement import (
    BoundaryStructure,
    BoundaryStructureKind,
    WorldObjectPlacement,
    WorldPlacementKind,
)
from dnd.types.senses import OpticalObscurement
from dnd.core.positioning import PositionCommitError, PositionPublicationError
from dnd.core.traversal_connectors import (
    TraversalConnector,
    TraversalConnectorChangeOperation,
    TraversalConnectorDefinition,
    TraversalConnectorEndpoint,
)

DIRECTIONS: Tuple[CardinalDirection, ...] = tuple(CardinalDirection)
ENTITY_WORLD_PRESENCE_LIGHT_SUPPRESSION_TOKEN = "entity.world_presence.absent"


@dataclass(frozen=True, slots=True)
class GridEntityMembershipReceipt:
    """Exact committed Tile-membership transition awaiting publication."""

    entity_uuid: UUID
    old_position: Optional[Tuple[int, int]]
    new_position: Optional[Tuple[int, int]]


@dataclass(frozen=True, slots=True)
class GridMapOperationDiagnostics:
    """Read-only counters for one measured GridMap operation."""

    operation: str
    tiles_inspected: int = 0
    bands_inspected: int = 0
    bands_replaced: int = 0
    placement_iterator_rows_visited: int = 0
    path_edge_queries: int = 0


class LightSourceData(BaseModel):
    """Tracks a light source and its affected tiles."""

    uuid: UUID = Field(default_factory=uuid4, description="Light source identity.")
    position: Tuple[int, int] = Field(description="Current position of the light source")
    very_bright_radius_feet: int = Field(default=0, description="Radius of very bright light in feet (innermost zone)")
    bright_radius_feet: int = Field(description="Radius of bright light in feet (extends beyond very bright)")
    dim_radius_feet: int = Field(description="Radius of dim light in feet (extends beyond bright)")
    anchor_uuid: Optional[UUID] = Field(default=None, description="BaseBlock this light is attached to (follows its movement)")
    affected_tiles: Dict[Tuple[int, int], LightLevel] = Field(default_factory=dict, description="pos -> level applied")
    is_active: bool = Field(default=True, description="Whether this light currently illuminates tiles.")


class GridMap:
    """Singleton-like manager for grid state and spatial queries.

    The map owns tile storage, entity/object spatial membership, event-backed
    spatial changes, cell subscriptions, light sources, FOV, and pathfinding.
    """

    _instance: Optional['GridMap'] = None

    def __init__(self):
        self._tiles: Dict[Tuple[int, int], Tile] = {}
        self._tiles_by_uuid: Dict[UUID, Tuple[int, int]] = {}

        self._min_x: int = 0
        self._max_x: int = 0
        self._min_y: int = 0
        self._max_y: int = 0
        self._bounds_dirty: bool = True

        self._object_placements: Dict[UUID, WorldObjectPlacement] = {}
        self._last_operation_diagnostics = GridMapOperationDiagnostics("none")

        self._spatial_conditions: Dict[UUID, BaseCondition] = {}
        self._spatial_condition_positions: Dict[
            UUID,
            Set[Tuple[int, int]],
        ] = {}
        self._spatial_condition_layers: Dict[
            UUID,
            SpatialEffectLayer,
        ] = {}

        self._cell_subscribers: DefaultDict[Tuple[int, int], Set[UUID]] = defaultdict(set)
        self._entity_subscriptions: DefaultDict[UUID, Set[Tuple[int, int]]] = defaultdict(set)

        self._light_sources: Dict[UUID, LightSourceData] = {}
        self._block_light_suppressions: DefaultDict[UUID, Set[str]] = defaultdict(set)

        self._connectors_by_uuid: Dict[UUID, TraversalConnector] = {}
        self._connector_uuid_by_authored_id: Dict[str, UUID] = {}
        self._connector_uuids_by_endpoint: DefaultDict[
            Tuple[int, int], List[UUID]
        ] = defaultdict(list)
        self._connector_revision: int = 0

        self._events_enabled: bool = True
        self._pending_events: List['SpatialChangeEvent'] = []
        self._pending_committed_events: List['SpatialChangeEvent'] = []

        self._blocking_callback_registered: bool = False
        self._spatial_revision: int = 0
        self._optical_revision: int = 0
        self._movement_revision: int = 0
        self._occupancy_revision: int = 0
        self._light_revision: int = 0
        self._propagation_revision: int = 0
        self._fov_cache: Dict[
            Tuple[Tuple[int, int], Optional[float], int],
            List[Tuple[int, int]],
        ] = {}
        self._propagation_fov_cache: Dict[
            Tuple[Tuple[int, int], Optional[float]],
            Tuple[Tuple[int, int], ...],
        ] = {}
        self._propagation_transition_cache: Dict[
            Tuple[Tuple[int, int], Tuple[int, int]],
            bool,
        ] = {}
        self._propagation_blocking_cache: Dict[Tuple[int, int], bool] = {}
        self._propagation_filter_cache: OrderedDict[
            Tuple[
                Tuple[int, int],
                Optional[float],
                Tuple[Tuple[int, int], ...],
            ],
            Tuple[Tuple[int, int], ...],
        ] = OrderedDict()
        self._path_cache: OrderedDict[
            Tuple[Any, ...],
            Tuple[
                Dict[Tuple[int, int], int],
                Dict[Tuple[int, int], Tuple[Tuple[int, int], ...]],
            ],
        ] = OrderedDict()
        EventQueue.add_on_event_callback(
            self._on_perceivability_changed,
            event_types={EventType.SPATIAL_PERCEIVABILITY_CHANGED},
            phases={EventPhase.DECLARATION},
        )

    @classmethod
    def get_instance(cls) -> 'GridMap':
        """Get the singleton GridMap instance."""
        if cls._instance is None:
            cls._instance = GridMap()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset the GridMap (for testing)."""
        cls._instance = None

    def _fire_spatial_event(self, event: 'SpatialChangeEvent') -> Optional['SpatialChangeEvent']:
        """Fire a spatial change event through the full phase lifecycle.

        Progresses: DECLARATION -> EXECUTION -> EFFECT -> COMPLETION

        Returns `None` if event was cancelled, otherwise returns completed event.
        If events are disabled (batch mode), queues for later and returns None.
        """
        if not self._events_enabled:
            self._pending_events.append(event)
            return None

        return EventQueue.publish_lifecycle(event)

    def _fire_committed_spatial_event(
        self,
        event: 'SpatialChangeEvent',
    ) -> Optional['SpatialChangeEvent']:
        """Publish a non-vetoable observation fact for an existing commit."""
        if not self._events_enabled:
            self._pending_committed_events.append(event)
            return None
        current = EventQueue.publish_preflighted(event)
        execution = current.phase_to(EventPhase.EXECUTION)
        effect = execution.phase_to(EventPhase.EFFECT)
        return effect.phase_to(EventPhase.COMPLETION, use_register=True)

    def enable_events(self, *, flush_pending: bool = True) -> None:
        """Enable events and either publish or discard buffered bootstrap facts."""
        self._events_enabled = True
        pending = self._pending_events.copy()
        pending_committed = self._pending_committed_events.copy()
        self._pending_events.clear()
        self._pending_committed_events.clear()
        if not flush_pending:
            return
        for event in pending:
            self._fire_spatial_event(event)
        for event in pending_committed:
            self._fire_committed_spatial_event(event)

    def disable_events(self) -> None:
        """Disable event firing (for batch operations)."""
        self._events_enabled = False

    def get_subscribers_at(self, position: Tuple[int, int]) -> Set[UUID]:
        """Get all entity UUIDs subscribed to a cell."""
        return self._cell_subscribers.get(position, set()).copy()

    def get_subscribers_for_cells(self, cells: Set[Tuple[int, int]]) -> Set[UUID]:
        """Return the union of subscribers for a batch of cells."""
        subscribers: Set[UUID] = set()
        for cell in cells:
            subscribers.update(self._cell_subscribers.get(cell, set()))
        return subscribers

    def subscribe_to_cells(self, entity_uuid: UUID, cells: Set[Tuple[int, int]]) -> None:
        """Subscribe an entity to a set of cells.

        Replaces any existing subscriptions for this entity.
        Typically called after updating entity senses with the visible cells.
        """
        old_cells = self._entity_subscriptions.get(entity_uuid, set())

        for cell in old_cells - cells:
            self._cell_subscribers[cell].discard(entity_uuid)

        for cell in cells - old_cells:
            self._cell_subscribers[cell].add(entity_uuid)

        self._entity_subscriptions[entity_uuid] = cells.copy()

    def unsubscribe_entity(self, entity_uuid: UUID) -> None:
        """Remove all subscriptions for an entity."""
        cells = self._entity_subscriptions.pop(entity_uuid, set())
        for cell in cells:
            self._cell_subscribers[cell].discard(entity_uuid)

    def get_entity_subscriptions(self, entity_uuid: UUID) -> Set[Tuple[int, int]]:
        """Get all cells an entity is subscribed to."""
        return self._entity_subscriptions.get(entity_uuid, set()).copy()

    @property
    def optical_revision(self) -> int:
        """Return the current physical-optical topology revision."""
        return self._optical_revision

    @property
    def movement_revision(self) -> int:
        """Return the current movement-topology revision."""
        return self._movement_revision

    @property
    def occupancy_revision(self) -> int:
        """Return the authoritative Entity-membership revision."""
        return self._occupancy_revision

    @property
    def propagation_revision(self) -> int:
        """Return the current physical-propagation topology revision."""
        return self._propagation_revision

    @property
    def connector_revision(self) -> int:
        """Return the connector/action-discovery topology revision."""
        return self._connector_revision

    def invalidate_spatial_caches(self, channels: Set[str]) -> None:
        """Invalidate spatial query caches after authoritative topology changes.

        Args:
            channels: Changed spatial channels: movement, optical, illumination, or
                propagation.
        """
        self._bump_spatial_revisions(channels)

    def invalidate_occupancy_paths(self) -> None:
        """Invalidate cached paths after entity blocking state changes."""
        self._occupancy_revision += 1
        self._path_cache.clear()

    def _on_perceivability_changed(self, event: Event) -> None:
        """Invalidate subjective occupancy paths when a blocker can appear or vanish.

        Perceivability is observer-relative, so a Hidden or Invisible transition
        can change which occupied cells a subjective path query may traverse
        even though authoritative occupancy did not move. The map consumes the
        spatial fact emitted by the block rather than making lower-level blocks
        import the spatial registry.
        """
        if (
            event.event_type == EventType.SPATIAL_PERCEIVABILITY_CHANGED
            and event.phase == EventPhase.DECLARATION
        ):
            self.invalidate_occupancy_paths()

    def _bump_spatial_revisions(self, channels: Set[str]) -> None:
        """Advance channel revisions and clear dependent query caches."""
        if not channels:
            return
        self._spatial_revision += 1
        if "optical" in channels:
            self._optical_revision += 1
            self._fov_cache.clear()
        if "movement" in channels:
            self._movement_revision += 1
            self._path_cache.clear()
        if "illumination" in channels:
            self._light_revision += 1
        if "propagation" in channels:
            self._propagation_revision += 1
            self._propagation_fov_cache.clear()
            self._propagation_filter_cache.clear()
            self._propagation_transition_cache.clear()
            self._propagation_blocking_cache.clear()
    def _bump_all_spatial_revisions(self) -> None:
        """Advance every spatial channel revision and clear query caches."""
        self._bump_spatial_revisions({"movement", "optical", "propagation"})

    def _assert_tile_replacement_allowed(
        self,
        position: Tuple[int, int],
        tile: Optional[Tile],
    ) -> None:
        """Reject replacement while any Phase-2-owned support is live."""
        if tile is None:
            return
        if self.get_entities_at(position):
            raise ValueError("cannot replace a Tile with entity occupancy")
        if self.get_objects_at(position):
            raise ValueError("cannot replace a Tile with object bands")
        if tile.active_conditions:
            raise ValueError("cannot replace a Tile with direct conditions")
        if tile.get_spatial_condition_uuids():
            raise ValueError("cannot replace a Tile while spatial conditions cover it")
        if self._connector_uuids_by_endpoint.get(position):
            raise ValueError("cannot replace a support Tile with a connector endpoint")
        if tile._illuminations or tile._illumination_caps:
            raise ValueError("cannot replace a Tile with live illumination contributions")

    def _path_requester_perception_signature(
        self,
        requester_uuid: Optional[UUID],
        subjective: bool,
    ) -> Tuple[Any, ...]:
        """Return subjective observer state that can change path blockers."""
        if requester_uuid is None or not subjective:
            return ()
        requester = BaseBlock.get(requester_uuid)
        if requester is None or requester.get_senses() is None:
            return ()
        senses = requester.get_senses()
        assert senses is not None
        return (
            tuple(sorted(senses.entities, key=str)),
            tuple(sorted(senses.objects, key=str)),
        )

    @staticmethod
    def _tile_movement_costs(tile: Tile) -> Tuple[int, int, int, int]:
        """Return the complete effective traversal-cost tuple for one Tile."""
        return (
            tile.get_movement_cost(MovementMode.WALKING),
            tile.get_movement_cost(MovementMode.FLYING),
            tile.get_movement_cost(MovementMode.SWIMMING),
            tile.get_movement_cost(MovementMode.BURROWING),
        )

    def set_tile(
        self,
        x: int,
        y: int,
        surface: Optional[TileSurface] = None,
        walking_cost: int = 1,
        flying_cost: int = 1,
        swimming_cost: int = 0,
        burrowing_cost: int = 0,
        blocks_optics: bool = False,
        blocks_propagation: bool = False,
                 name: str = "Floor",
                 fire_event: bool = True, tile: Optional[Tile] = None,
                 height: int = 0,
                 elevation_surface_kind: ElevationSurfaceKind = ElevationSurfaceKind.ORDINARY,
                 slope_axis: Optional[SlopeAxis] = None) -> Tile:
        """Set or replace a tile at a position.

        If tile parameter is provided, uses that tile directly (updating its position if needed).
        Otherwise creates a new Tile object with the given parameters.
        Returns the stored tile.
        """
        if type(x) is not int or type(y) is not int:
            raise ValueError("tile position must be an exact tuple[int, int]")
        validate_elevation_surface_tuple(
            height if tile is None else tile.height,
            (
                elevation_surface_kind
                if tile is None
                else tile.elevation_surface_kind
            ),
            slope_axis if tile is None else tile.slope_axis,
        )
        position = (x, y)
        old_tile = self._tiles.get(position)
        if (
            old_tile is not None
            and tile is not old_tile
        ):
            self._assert_tile_replacement_allowed(position, old_tile)
        old_elevation_tuple = (
            (
                old_tile.height,
                old_tile.elevation_surface_kind,
                old_tile.slope_axis,
            )
            if old_tile is not None
            else None
        )

        if tile is not None:
            if BaseBlock.get(tile.uuid) is not tile:
                raise ValueError(
                    "tile UUID must resolve to the exact global Tile object"
                )
            indexed_position = self._tiles_by_uuid.get(tile.uuid)
            if indexed_position is not None and (
                indexed_position != position
                or self._tiles.get(indexed_position) is not tile
            ):
                raise ValueError(
                    "cannot install a live Tile or UUID at a second position"
                )
            tile.position = position
        else:
            if surface is None:
                raise ValueError("new Tiles require an explicit semantic surface")
            tile = Tile.create(
                position=position,
                surface=surface,
                walking_cost=walking_cost,
                flying_cost=flying_cost,
                swimming_cost=swimming_cost,
                burrowing_cost=burrowing_cost,
                blocks_optics=blocks_optics,
                blocks_propagation=blocks_propagation,
                name=name,
                height=height,
                elevation_surface_kind=elevation_surface_kind,
                slope_axis=slope_axis,
            )
        if old_tile:
            self._tiles_by_uuid.pop(old_tile.uuid, None)
        self._tiles[position] = tile
        self._tiles_by_uuid[tile.uuid] = position
        self._bounds_dirty = True
        revision_channels: Set[str] = set()
        if old_tile is None:
            revision_channels.update({"movement", "optical", "propagation"})
        else:
            if self._tile_movement_costs(old_tile) != self._tile_movement_costs(tile):
                revision_channels.add("movement")
            if (
                old_tile.height,
                old_tile.elevation_surface_kind,
                old_tile.slope_axis,
            ) != (
                tile.height,
                tile.elevation_surface_kind,
                tile.slope_axis,
            ):
                revision_channels.add("movement")
            if old_tile.blocks_optics != tile.blocks_optics:
                revision_channels.add("optical")
            if (
                old_tile.blocks_propagation_field
                != tile.blocks_propagation_field
            ):
                revision_channels.add("propagation")
            if old_tile.resolved_light_level != tile.resolved_light_level:
                revision_channels.add("illumination")
        self._bump_spatial_revisions(revision_channels)

        if fire_event:
            old_blocks_optics = old_tile.blocks_optics if old_tile else None
            old_blocks_propagation = (
                old_tile.blocks_propagation_field if old_tile else None
            )
            tile_blocks_optics = tile.blocks_optics
            tile_blocks_propagation = tile.blocks_propagation_field
            scalar_movement_changed = (
                old_tile is None
                or self._tile_movement_costs(old_tile)
                != self._tile_movement_costs(tile)
            )
            scalar_optics_changed = (
                old_tile is None or old_blocks_optics != tile_blocks_optics
            )
            scalar_propagation_changed = (
                old_tile is None
                or old_blocks_propagation != tile_blocks_propagation
            )
            scalar_elevation_changed = old_elevation_tuple != (
                tile.height,
                tile.elevation_surface_kind,
                tile.slope_axis,
            )
            if (
                scalar_movement_changed
                or scalar_optics_changed
                or scalar_propagation_changed
                or scalar_elevation_changed
            ):
                hint = SensesUpdateHint(
                    requires_fov=scalar_optics_changed,
                    requires_paths=(
                        scalar_movement_changed
                        or scalar_elevation_changed
                    ),
                    requires_light_recompute=scalar_optics_changed,
                    requires_propagation_recompute=scalar_propagation_changed,
                )
                event = SpatialChangeEvent.tile_changed(
                    position,
                    tile_walking_cost=tile.get_movement_cost(MovementMode.WALKING),
                    tile_flying_cost=tile.get_movement_cost(MovementMode.FLYING),
                    tile_swimming_cost=tile.get_movement_cost(MovementMode.SWIMMING),
                    tile_burrowing_cost=tile.get_movement_cost(MovementMode.BURROWING),
                    tile_blocks_optics=tile_blocks_optics,
                    tile_blocks_propagation=tile_blocks_propagation,
                    tile_surface=tile.surface,
                    senses_hint=hint,
                )
                self._fire_committed_spatial_event(event)

        return tile

    def replace_tile_surface(
        self,
        position: Tuple[int, int],
        surface: TileSurface,
        *,
        parent_event: Optional[UUID] = None,
    ) -> bool:
        """Replace one Tile's semantic surface in place and publish its fact."""
        if not isinstance(surface, TileSurface):
            raise TypeError("surface must be a TileSurface")
        tile = self._tiles.get(position)
        if tile is None:
            raise ValueError(f"cannot replace surface on missing tile {position}")
        if tile.surface == surface:
            return False

        tile.surface = surface
        event = SpatialChangeEvent.tile_changed(
            position,
            tile_blocks_optics=tile.blocks_optics,
            tile_blocks_propagation=tile.blocks_propagation_field,
            tile_surface=surface,
            senses_hint=SensesUpdateHint(),
            parent_event=parent_event,
        )
        self._fire_committed_spatial_event(event)
        return True

    def set_tile_elevation(
        self,
        position: Tuple[int, int],
        *,
        height: int,
        surface_kind: ElevationSurfaceKind,
        slope_axis: Optional[SlopeAxis],
        parent_event: Optional[UUID] = None,
    ) -> bool:
        """Validate, publish, and commit one exact support-tuple mutation."""
        validate_elevation_surface_tuple(height, surface_kind, slope_axis)
        tile = self._tiles.get(position)
        if tile is None:
            raise ValueError(f"cannot set elevation on missing tile {position}")
        if (
            tile.height == height
            and tile.elevation_surface_kind is surface_kind
            and tile.slope_axis is slope_axis
        ):
            return False
        if height != tile.height and self._connector_uuids_by_endpoint.get(position):
            raise ValueError(
                "cannot change support height while a traversal connector is anchored"
            )
        if height != tile.height:
            support_dependent_placements = tuple(
                placement
                for placement in self._object_placements.values()
                if (
                    placement.position == position
                    and placement.kind is WorldPlacementKind.CENTER
                )
            )
            if support_dependent_placements:
                raise ValueError(
                    "cannot change support height while center object placements are anchored",
                )
        original_tile_tuple = (
            tile.height,
            tile.elevation_surface_kind,
            tile.slope_axis,
        )
        original_connector_uuids = tuple(
            self._connector_uuids_by_endpoint.get(position, ())
        )

        declaration = TileElevationChangeEvent(
            source_entity_uuid=tile.uuid,
            target_entity_uuid=tile.uuid,
            position=position,
            tile_uuid=tile.uuid,
            old_height_steps=tile.height,
            new_height_steps=height,
            old_surface_kind=tile.elevation_surface_kind,
            new_surface_kind=surface_kind,
            old_slope_axis=tile.slope_axis,
            new_slope_axis=slope_axis,
            parent_event=parent_event,
            phase=EventPhase.DECLARATION,
            use_register=False,
        )
        accepted = EventQueue.publish_declaration(declaration)
        if accepted.canceled:
            return False
        for phase in (EventPhase.EXECUTION, EventPhase.EFFECT):
            accepted = accepted.phase_to(phase)
            if accepted.canceled:
                return False
        if type(accepted) is not TileElevationChangeEvent:
            raise TypeError("tile elevation lifecycle changed event family")

        if (
            self._tiles.get(position) is not tile
            or BaseBlock.get(tile.uuid) is not tile
            or self._tiles_by_uuid.get(tile.uuid) != position
            or self.get_tile_by_uuid(tile.uuid) is not tile
            or (
                tile.height,
                tile.elevation_surface_kind,
                tile.slope_axis,
            ) != original_tile_tuple
            or tuple(self._connector_uuids_by_endpoint.get(position, ()))
            != original_connector_uuids
        ):
            accepted.cancel(
                status_message=(
                    "Tile support changed before the elevation mutation committed"
                )
            )
            return False

        tile.height = height
        tile.elevation_surface_kind = surface_kind
        tile.slope_axis = slope_axis
        self._bump_spatial_revisions({"movement"})
        accepted.phase_to(EventPhase.COMPLETION)
        return True

    def get_world_edge(
        self,
        source: Tuple[int, int],
        destination: Tuple[int, int],
    ) -> WorldEdgeView:
        """Derive one ordered edge view from exact endpoint-owned layers."""
        view, _ = self._derive_world_edge(source, destination)
        return view

    def get_boundary_route_layers(
        self,
        source: Tuple[int, int],
        direction: CardinalDirection,
        channel: WorldEdgeChannel,
    ) -> Tuple[Tuple[UUID, ...], Tuple[UUID, ...]]:
        """Return the deterministic reached boundary layers for one route step."""
        if source not in self._tiles:
            raise ValueError("boundary route source must have a supporting Tile")
        if type(direction) is not CardinalDirection:
            raise TypeError("boundary route direction must be a CardinalDirection")
        if channel not in {
            WorldEdgeChannel.OPTICAL,
            WorldEdgeChannel.PROPAGATION,
        }:
            raise ValueError("boundary route channel must be OPTICAL or PROPAGATION")

        exit_layer = tuple(sorted(
            self.get_boundary_objects_at(source, direction),
            key=str,
        ))
        destination = self._directional_neighbor(source, direction)
        if destination not in self._tiles:
            return exit_layer, ()

        view, _closed_door_provider_uuids = self._derive_world_edge(
            source,
            destination,
        )
        if not self._edge_layer_allows(
            view.exit_contributions,
            channel,
            source_height=view.source_height_steps,
            destination_height=view.destination_height_steps,
            movement_mode=MovementMode.WALKING,
            treat_closed_doors_as_interactable=False,
            ignorable_provider_uuids=frozenset(),
        ):
            return exit_layer, ()
        entry_layer = tuple(sorted(
            self.get_boundary_objects_at(
                destination,
                self._opposite_direction(direction),
            ),
            key=str,
        ))
        return exit_layer, entry_layer

    def _derive_world_edge(
        self,
        source: Tuple[int, int],
        destination: Tuple[int, int],
        *,
        structure_overrides: Optional[Dict[UUID, Optional[BoundaryStructure]]] = None,
    ) -> tuple[WorldEdgeView, frozenset[UUID]]:
        """Derive an edge and transient closed-door facts for one evaluation."""
        self._begin_operation_diagnostics("get_world_edge")
        key = AdjacentEdgeKey.between(source, destination)
        source_tile = self._tiles.get(source)
        destination_tile = self._tiles.get(destination)
        if source_tile is None or destination_tile is None:
            raise ValueError("world-edge endpoints must both have supporting tiles")

        dx = destination[0] - source[0]
        dy = destination[1] - source[1]
        if (dx, dy) == (1, 0):
            exit_direction = CardinalDirection.EAST
        elif (dx, dy) == (-1, 0):
            exit_direction = CardinalDirection.WEST
        elif (dx, dy) == (0, 1):
            exit_direction = CardinalDirection.NORTH
        elif (dx, dy) == (0, -1):
            exit_direction = CardinalDirection.SOUTH
        else:
            raise ValueError("world-edge endpoints must be cardinally adjacent")
        entry_direction = self._opposite_direction(exit_direction)
        bands_inspected = 0
        provider_rows_visited = 0
        closed_door_provider_uuids: set[UUID] = set()

        def layer_contributions(
            tile: Tile,
            direction: CardinalDirection,
        ) -> tuple[WorldEdgeStructuralContribution, ...]:
            nonlocal bands_inspected, provider_rows_visited
            contributions: Dict[UUID, WorldEdgeStructuralContribution] = {}
            provider_uuids: Set[UUID] = set()
            boundary_bands = tuple(
                tile._boundary_object_bands.get(direction, {}).values()
            )
            bands_inspected += len(boundary_bands)
            for band in boundary_bands:
                provider_uuids.update(band.object_uuids)

            for provider_uuid in sorted(provider_uuids, key=str):
                provider_rows_visited += 1
                provider = BaseBlock.get(provider_uuid)
                placement = self.get_object_placement(provider_uuid)
                if provider is None or placement is None:
                    continue
                if (
                    placement.kind is not WorldPlacementKind.BOUNDARY
                    or placement.boundary_direction is not direction
                ):
                    continue
                if (
                    structure_overrides is not None
                    and provider_uuid in structure_overrides
                ):
                    structure = structure_overrides[provider_uuid]
                else:
                    structure = provider.get_boundary_structure()
                    if structure_overrides is not None:
                        structure_overrides[provider_uuid] = structure
                if structure is None:
                    continue
                if (
                    structure.structure is BoundaryStructureKind.DOOR
                    and provider.get_spatial_open_state() is False
                ):
                    closed_door_provider_uuids.add(provider_uuid)
                contributions[provider_uuid] = WorldEdgeStructuralContribution(
                    provider_uuid=provider_uuid,
                    base_height_steps=placement.base_height_steps,
                    top_height_steps=placement.top_height_steps,
                    blocked_channels=structure.blocked_channels,
                )
            return tuple(contributions[uuid] for uuid in sorted(contributions, key=str))

        exit_contributions = layer_contributions(source_tile, exit_direction)
        entry_contributions = layer_contributions(destination_tile, entry_direction)
        self._finish_operation_diagnostics(
            "get_world_edge",
            tiles_inspected=2,
            bands_inspected=bands_inspected,
            placement_iterator_rows_visited=provider_rows_visited,
        )
        return WorldEdgeView(
            key=key,
            source_position=source,
            destination_position=destination,
            source_tile_uuid=source_tile.uuid,
            destination_tile_uuid=destination_tile.uuid,
            source_height_steps=source_tile.height,
            destination_height_steps=destination_tile.height,
            elevation_delta_steps=destination_tile.height - source_tile.height,
            source_surface_kind=source_tile.elevation_surface_kind,
            destination_surface_kind=destination_tile.elevation_surface_kind,
            source_slope_axis=source_tile.slope_axis,
            destination_slope_axis=destination_tile.slope_axis,
            exit_direction=exit_direction,
            entry_direction=entry_direction,
            exit_contributions=exit_contributions,
            entry_contributions=entry_contributions,
        ), frozenset(closed_door_provider_uuids)

    def remove_tile(self, x: int, y: int, fire_event: bool = True) -> None:
        """Remove a tile at the given position."""
        position = (x, y)
        if position in self._tiles:
            tile = self._tiles[position]
            self._assert_tile_replacement_allowed(position, tile)
            self._tiles_by_uuid.pop(tile.uuid, None)
            del self._tiles[position]
            self._bounds_dirty = True
            self._bump_all_spatial_revisions()

            if fire_event and self._events_enabled:
                hint = SensesUpdateHint(
                    requires_fov=True,
                    requires_paths=True,
                )
                event = SpatialChangeEvent(
                    source_entity_uuid=uuid4(),
                    change_type=SpatialChangeType.TILE_REMOVED,
                    position=position,
                    senses_hint=hint,
                    phase=EventPhase.DECLARATION,
                    use_register=False,
                )
                self._fire_committed_spatial_event(event)

    def get_tile(self, x: int, y: int) -> Optional[Tile]:
        """Get tile at position, or None if no tile exists."""
        return self._tiles.get((x, y))

    def get_support_elevation_feet(self, position: Tuple[int, int]) -> int:
        """Return one existing tile's authoritative support elevation."""
        tile = self._tiles.get(position)
        if tile is None:
            raise ValueError(f"missing support tile at {position}")
        return tile.height * 5

    def get_tile_by_uuid(self, tile_uuid: UUID) -> Optional[Tile]:
        """Get tile by UUID, or None if not found."""
        position = self._tiles_by_uuid.get(tile_uuid)
        if position:
            return self._tiles.get(position)
        return None

    def _build_connector(
        self,
        definition: TraversalConnectorDefinition,
        *,
        connector_uuid: Optional[UUID] = None,
        revision: int = 1,
    ) -> TraversalConnector:
        """Resolve one authored connector against its exact live supports."""
        endpoints: List[TraversalConnectorEndpoint] = []
        for position in definition.endpoint_positions:
            tile = self._tiles.get(position)
            if tile is None:
                raise ValueError(
                    f"connector endpoint has no support tile at {position}"
                )
            endpoints.append(TraversalConnectorEndpoint(
                position=position,
                support_tile_uuid=tile.uuid,
                elevation_feet=tile.height * 5,
            ))
        return TraversalConnector.create(
            definition,
            (endpoints[0], endpoints[1]),
            connector_uuid=connector_uuid,
            revision=revision,
        )

    def _publish_connector_change(
        self,
        operation: TraversalConnectorChangeOperation,
        *,
        connector_uuid: UUID,
        authored_id: str,
        old_connector: Optional[TraversalConnector],
        new_connector: Optional[TraversalConnector],
        parent_event: Optional[UUID],
    ) -> Optional[TraversalConnectorChangeEvent]:
        """Publish the cancelable precommit boundary for one connector edit."""
        declaration = TraversalConnectorChangeEvent(
            source_entity_uuid=connector_uuid,
            operation=operation,
            connector_uuid=connector_uuid,
            authored_id=authored_id,
            old_connector=old_connector,
            new_connector=new_connector,
            parent_event=parent_event,
            phase=EventPhase.DECLARATION,
            use_register=False,
        )
        accepted = EventQueue.publish_declaration(declaration)
        if accepted.canceled:
            return None
        for phase in (EventPhase.EXECUTION, EventPhase.EFFECT):
            accepted = accepted.phase_to(phase)
            if accepted.canceled:
                return None
        if type(accepted) is not TraversalConnectorChangeEvent:
            raise TypeError("connector lifecycle changed event family")
        return accepted

    def _index_connector(self, connector: TraversalConnector) -> None:
        """Install one already validated connector into all exact indexes."""
        self._connectors_by_uuid[connector.uuid] = connector
        self._connector_uuid_by_authored_id[connector.authored_id] = connector.uuid
        for endpoint in connector.endpoints:
            values = self._connector_uuids_by_endpoint[endpoint.position]
            if connector.uuid not in values:
                values.append(connector.uuid)
            values.sort(key=lambda connector_uuid: (
                self._connectors_by_uuid[connector_uuid].authored_id,
                str(connector_uuid),
            ))

    def _unindex_connector(self, connector: TraversalConnector) -> None:
        """Remove one connector from every index without publishing events."""
        self._connectors_by_uuid.pop(connector.uuid, None)
        if self._connector_uuid_by_authored_id.get(connector.authored_id) == connector.uuid:
            self._connector_uuid_by_authored_id.pop(connector.authored_id, None)
        for endpoint in connector.endpoints:
            values = self._connector_uuids_by_endpoint.get(endpoint.position)
            if values is None:
                continue
            self._connector_uuids_by_endpoint[endpoint.position] = [
                value for value in values if value != connector.uuid
            ]
            if not self._connector_uuids_by_endpoint[endpoint.position]:
                self._connector_uuids_by_endpoint.pop(endpoint.position, None)

    def connector_supports_are_current(
        self,
        connector: TraversalConnector,
    ) -> bool:
        """Return whether both frozen support anchors still match the map."""
        return all(
            (tile := self._tiles.get(endpoint.position)) is not None
            and tile.uuid == endpoint.support_tile_uuid
            and tile.position == endpoint.position
            and BaseBlock.get(tile.uuid) is tile
            and self._tiles_by_uuid.get(tile.uuid) == endpoint.position
            and self.get_tile_by_uuid(tile.uuid) is tile
            and tile.height * 5 == endpoint.elevation_feet
            for endpoint in connector.endpoints
        )

    @staticmethod
    def _cancel_stale_connector_change(
        effect: TraversalConnectorChangeEvent,
    ) -> None:
        """Close an accepted lifecycle whose frozen supports changed in-handler."""
        effect.cancel(
            status_message=(
                "Connector support changed before the connector mutation committed"
            )
        )

    def register_connector(
        self,
        definition: TraversalConnectorDefinition,
        *,
        connector_uuid: Optional[UUID] = None,
        parent_event: Optional[UUID] = None,
    ) -> Optional[TraversalConnector]:
        """Register one authored connector after its accepted change lifecycle."""
        if definition.authored_id in self._connector_uuid_by_authored_id:
            raise ValueError(f"duplicate connector authored_id {definition.authored_id}")
        connector = self._build_connector(
            definition,
            connector_uuid=connector_uuid,
        )
        if connector.uuid in self._connectors_by_uuid:
            raise ValueError(f"duplicate connector UUID {connector.uuid}")
        if not self._events_enabled:
            if not self.connector_supports_are_current(connector):
                raise ValueError("connector supports changed before initial registration")
            self._index_connector(connector)
            self._connector_revision += 1
            return connector
        effect = self._publish_connector_change(
            TraversalConnectorChangeOperation.REGISTER,
            connector_uuid=connector.uuid,
            authored_id=connector.authored_id,
            old_connector=None,
            new_connector=connector,
            parent_event=parent_event,
        )
        if effect is None:
            return None
        if (
            connector.uuid in self._connectors_by_uuid
            or connector.authored_id in self._connector_uuid_by_authored_id
            or not self.connector_supports_are_current(connector)
        ):
            self._cancel_stale_connector_change(effect)
            return None
        self._index_connector(connector)
        self._connector_revision += 1
        effect.phase_to(EventPhase.COMPLETION)
        return connector

    def replace_connector(
        self,
        connector_uuid: UUID,
        definition: TraversalConnectorDefinition,
        *,
        parent_event: Optional[UUID] = None,
    ) -> Optional[TraversalConnector]:
        """Replace authored mechanics while preserving runtime identity."""
        old = self._connectors_by_uuid.get(connector_uuid)
        if old is None:
            raise ValueError(f"unknown connector {connector_uuid}")
        if definition.authored_id != old.authored_id:
            raise ValueError("connector replacement must preserve authored_id")
        replacement = self._build_connector(
            definition,
            connector_uuid=connector_uuid,
            revision=old.revision + 1,
        )
        effect = self._publish_connector_change(
            TraversalConnectorChangeOperation.REPLACE,
            connector_uuid=connector_uuid,
            authored_id=old.authored_id,
            old_connector=old,
            new_connector=replacement,
            parent_event=parent_event,
        )
        if effect is None:
            return None
        if (
            self._connectors_by_uuid.get(connector_uuid) is not old
            or self._connector_uuid_by_authored_id.get(old.authored_id)
            != connector_uuid
            or not self.connector_supports_are_current(replacement)
        ):
            self._cancel_stale_connector_change(effect)
            return None
        self._unindex_connector(old)
        self._index_connector(replacement)
        self._connector_revision += 1
        effect.phase_to(EventPhase.COMPLETION)
        return replacement

    def set_connector_enabled(
        self,
        connector_uuid: UUID,
        enabled: bool,
        *,
        parent_event: Optional[UUID] = None,
    ) -> Optional[TraversalConnector]:
        """Enable or disable one connector through the same guarded lifecycle."""
        if type(enabled) is not bool:
            raise TypeError("enabled must be an exact bool")
        old = self._connectors_by_uuid.get(connector_uuid)
        if old is None:
            raise ValueError(f"unknown connector {connector_uuid}")
        if old.enabled is enabled:
            return old
        definition = old.definition().model_copy(update={"enabled": enabled})
        replacement = self._build_connector(
            definition,
            connector_uuid=connector_uuid,
            revision=old.revision + 1,
        )
        operation = (
            TraversalConnectorChangeOperation.ENABLE
            if enabled
            else TraversalConnectorChangeOperation.DISABLE
        )
        effect = self._publish_connector_change(
            operation,
            connector_uuid=connector_uuid,
            authored_id=old.authored_id,
            old_connector=old,
            new_connector=replacement,
            parent_event=parent_event,
        )
        if effect is None:
            return None
        if (
            self._connectors_by_uuid.get(connector_uuid) is not old
            or self._connector_uuid_by_authored_id.get(old.authored_id)
            != connector_uuid
            or not self.connector_supports_are_current(replacement)
        ):
            self._cancel_stale_connector_change(effect)
            return None
        self._unindex_connector(old)
        self._index_connector(replacement)
        self._connector_revision += 1
        effect.phase_to(EventPhase.COMPLETION)
        return replacement

    def remove_connector(
        self,
        connector_uuid: UUID,
        *,
        parent_event: Optional[UUID] = None,
    ) -> bool:
        """Remove one connector atomically after accepted precommit phases."""
        old = self._connectors_by_uuid.get(connector_uuid)
        if old is None:
            return False
        effect = self._publish_connector_change(
            TraversalConnectorChangeOperation.REMOVE,
            connector_uuid=connector_uuid,
            authored_id=old.authored_id,
            old_connector=old,
            new_connector=None,
            parent_event=parent_event,
        )
        if effect is None:
            return False
        if (
            self._connectors_by_uuid.get(connector_uuid) is not old
            or self._connector_uuid_by_authored_id.get(old.authored_id)
            != connector_uuid
        ):
            self._cancel_stale_connector_change(effect)
            return False
        self._unindex_connector(old)
        self._connector_revision += 1
        effect.phase_to(EventPhase.COMPLETION)
        return True

    def get_connector(self, connector_uuid: UUID) -> Optional[TraversalConnector]:
        """Return one live connector by encounter-local identity."""
        return self._connectors_by_uuid.get(connector_uuid)

    def get_connector_by_authored_id(
        self,
        authored_id: str,
    ) -> Optional[TraversalConnector]:
        """Return one connector by stable map-authored identity."""
        connector_uuid = self._connector_uuid_by_authored_id.get(authored_id)
        return (
            self._connectors_by_uuid.get(connector_uuid)
            if connector_uuid is not None
            else None
        )

    def get_connectors_at(
        self,
        position: Tuple[int, int],
    ) -> Tuple[TraversalConnector, ...]:
        """Return deterministic endpoint-indexed connector facts."""
        return tuple(
            self._connectors_by_uuid[connector_uuid]
            for connector_uuid in self._connector_uuids_by_endpoint.get(position, ())
            if connector_uuid in self._connectors_by_uuid
        )

    def get_all_connectors(self) -> Tuple[TraversalConnector, ...]:
        """Return all connectors in stable authored/runtime identity order."""
        return tuple(sorted(
            self._connectors_by_uuid.values(),
            key=lambda connector: (connector.authored_id, str(connector.uuid)),
        ))

    def has_tile(self, x: int, y: int) -> bool:
        """Check if a tile exists at position."""
        return (x, y) in self._tiles

    def is_walkable(self, x: int, y: int, mode: MovementMode = MovementMode.WALKING) -> bool:
        """
        Check if position is walkable based on tile movement cost.

        Uses the new movement cost system - a tile is walkable if its
        movement cost for the given mode is > 0.

        Does NOT consider entity occupancy - use is_walkable_for() for that.
        """
        tile = self._tiles.get((x, y))
        if tile is None:
            return False
        return not tile.blocks_walking(mode=mode)

    def is_position_hazardous_for(self, x: int, y: int,
                                  entity_uuid: Optional[UUID] = None) -> bool:
        """Return whether tile, object, or spatial-effect hazards affect an entity."""
        tile = self.get_tile(x, y)
        if tile is not None and tile.is_hazardous_for(entity_uuid):
            return True

        for obj_uuid in self.get_center_objects_at((x, y)):
            obj = BaseBlock.get(obj_uuid)
            if obj is not None and obj.is_hazardous_for(entity_uuid):
                return True

        for condition in self.get_spatial_conditions_at((x, y)):
            if condition.is_hazardous_for(entity_uuid):
                return True

        return False

    def has_any_hazards(self) -> bool:
        """Return whether any indexed world block currently declares a hazard."""
        for tile in self.get_tiles_with_conditions():
            if any(
                condition.hazard_filter is not None
                for condition in tile.get_conditions().values()
            ):
                return True
        for obj in self.get_objects_with_conditions():
            if any(condition.hazard_filter is not None for condition in obj.active_conditions.values()):
                return True
        for condition in self.get_spatial_conditions():
            if condition.hazard_filter is not None:
                return True
        return False

    def set_spatial_condition_positions(
        self,
        *,
        condition: BaseCondition,
        layer: SpatialEffectLayer,
        occupancy_policy: SpatialEffectOccupancyPolicy,
        positions: Set[Tuple[int, int]],
    ) -> None:
        """Commit one independent condition's complete Tile footprint."""
        normalized = set(positions)
        self.validate_spatial_condition_positions(
            condition=condition,
            layer=layer,
            occupancy_policy=occupancy_policy,
            positions=normalized,
        )

        previous_layer = self._spatial_condition_layers.get(condition.uuid)
        previous_positions = self._spatial_condition_positions.get(
            condition.uuid,
            set(),
        )
        if previous_layer is not None:
            for position in previous_positions - normalized:
                tile = self._tiles.get(position)
                if tile is not None:
                    tile.remove_spatial_condition_reference(
                        condition.uuid,
                        previous_layer,
                    )
            if previous_layer is not layer:
                for position in previous_positions & normalized:
                    tile = self._tiles[position]
                    tile.remove_spatial_condition_reference(
                        condition.uuid,
                        previous_layer,
                    )

        self._spatial_conditions[condition.uuid] = condition
        self._spatial_condition_layers[condition.uuid] = layer
        self._spatial_condition_positions[condition.uuid] = normalized
        for position in normalized:
            self._tiles[position].add_spatial_condition_reference(
                condition.uuid,
                layer,
            )

    def validate_spatial_condition_positions(
        self,
        *,
        condition: BaseCondition,
        layer: SpatialEffectLayer,
        occupancy_policy: SpatialEffectOccupancyPolicy,
        positions: Set[Tuple[int, int]],
    ) -> None:
        """Validate one complete footprint without mutating map indexes."""
        normalized = set(positions)
        if any(position not in self._tiles for position in normalized):
            raise ValueError(
                "Spatial condition positions must identify existing tiles",
            )

        existing = self._spatial_conditions.get(condition.uuid)
        if existing is not None and existing is not condition:
            raise ValueError(
                f"Spatial condition UUID {condition.uuid} is already active",
            )

        if occupancy_policy is SpatialEffectOccupancyPolicy.EXCLUSIVE_TRANSFORMING:
            for position in normalized:
                occupants = self._tiles[position].get_spatial_condition_uuids(
                    layer,
                ) - {condition.uuid}
                if occupants:
                    raise ValueError(
                        f"{layer.value} cell {position} already has a condition",
                    )

    def remove_spatial_condition(self, condition_uuid: UUID) -> None:
        """Remove one independent condition from GridMap and every Tile."""
        layer = self._spatial_condition_layers.pop(condition_uuid, None)
        positions = self._spatial_condition_positions.pop(
            condition_uuid,
            set(),
        )
        if layer is not None:
            for position in positions:
                tile = self._tiles.get(position)
                if tile is not None:
                    tile.remove_spatial_condition_reference(
                        condition_uuid,
                        layer,
                    )
        self._spatial_conditions.pop(condition_uuid, None)

    def get_spatial_condition_positions(
        self,
        condition_uuid: UUID,
    ) -> Set[Tuple[int, int]]:
        """Return the authoritative footprint indexed for one condition."""
        return set(self._spatial_condition_positions.get(condition_uuid, set()))

    def has_spatial_condition(self, condition_uuid: UUID) -> bool:
        """Return whether the exact condition UUID is active on this map."""
        return condition_uuid in self._spatial_conditions

    def get_spatial_condition(
        self,
        condition_uuid: UUID,
    ) -> Optional[BaseCondition]:
        """Return the exact active independent condition, if present."""
        return self._spatial_conditions.get(condition_uuid)

    def get_spatial_condition_uuids_at(
        self,
        position: Tuple[int, int],
        *,
        layer: Optional[SpatialEffectLayer] = None,
    ) -> Set[UUID]:
        """Return active independent condition UUIDs affecting one Tile."""
        tile = self._tiles.get(position)
        if tile is None:
            return set()
        return tile.get_spatial_condition_uuids(layer)

    def get_spatial_conditions_at(
        self,
        position: Tuple[int, int],
        *,
        layer: Optional[SpatialEffectLayer] = None,
    ) -> List[BaseCondition]:
        """Resolve active independent conditions affecting one Tile."""
        conditions: List[BaseCondition] = []
        for condition_uuid in sorted(
            self.get_spatial_condition_uuids_at(position, layer=layer),
            key=str,
        ):
            condition = self._spatial_conditions.get(condition_uuid)
            if not isinstance(condition, BaseCondition):
                raise RuntimeError(
                    "Tile references a spatial condition missing from GridMap: "
                    f"{condition_uuid}",
                )
            conditions.append(condition)
        return conditions

    def get_spatial_conditions(self) -> List[BaseCondition]:
        """Return every active independent spatial condition once."""
        return [
            self._spatial_conditions[condition_uuid]
            for condition_uuid in sorted(self._spatial_conditions, key=str)
        ]

    def get_optical_obscurements_at(
        self,
        position: Tuple[int, int],
    ) -> Tuple[OpticalObscurement, ...]:
        """Return active optical contributions affecting one Tile."""
        return tuple(
            obscurement
            for condition in self.get_spatial_conditions_at(position)
            if (
                obscurement := condition.get_optical_obscurement_at(position)
            ) is not None
        )

    def is_walkable_for(self, x: int, y: int, requesting_entity_uuid: Optional[UUID] = None,
                        mode: MovementMode = MovementMode.WALKING,
                        walk_in_danger: bool = True,
                        subjective: bool = False,
                        collision_blocked: Optional[Set[Tuple[int, int]]] = None) -> bool:
        """Check whether a position is walkable for a specific entity.

        Considers:
        1. Tile must exist and be walkable for the given movement mode
        2. Position must not be occupied by another blocking entity
        3. If walk_in_danger=False, hazardous positions are treated as unwalkable

        Uses polymorphic dispatch: BaseBlock.get(uuid).blocks_walking() routes
        to Entity, Tile, or future item overrides. GridMap stays type-unaware.
        """
        if not self.is_walkable(x, y, mode):
            return False

        for entity_uuid in self.get_entities_at((x, y)):
            block = BaseBlock.get(entity_uuid)
            if block is not None and block.blocks_walking(requesting_entity_uuid, mode):
                if subjective and requesting_entity_uuid is not None:
                    requester = BaseBlock.get(requesting_entity_uuid)
                    senses = requester.get_senses() if requester is not None else None
                    if senses is not None and entity_uuid not in senses.entities:
                        continue
                return False

        for obj_uuid in self.get_center_objects_at((x, y)):
            block = BaseBlock.get(obj_uuid)
            if block is not None and block.blocks_walking(requesting_entity_uuid, mode):
                if subjective and requesting_entity_uuid is not None:
                    requester = BaseBlock.get(requesting_entity_uuid)
                    senses = requester.get_senses() if requester is not None else None
                    if senses is not None and obj_uuid not in senses.objects:
                        continue
                return False

        for condition in self.get_spatial_conditions_at((x, y)):
            if condition.blocks_walking_at(
                (x, y),
                requesting_entity_uuid,
                mode,
            ):
                if (
                    subjective
                    and not condition.is_hazard_perceived_by(requesting_entity_uuid)
                ):
                    continue
                return False

        if not walk_in_danger:
            if self.is_position_hazardous_for(x, y, requesting_entity_uuid):
                return False

        if collision_blocked and (x, y) in collision_blocked:
            return False

        return True

    def allows_optics(self, x: int, y: int) -> bool:
        """Return whether an existing Tile intrinsically transmits optics."""
        tile = self._tiles.get((x, y))
        return (
            tile is not None
            and not tile.blocks_optics
            and not any(
                condition.blocks_physical_optics_at((x, y))
                for condition in self.get_spatial_conditions_at((x, y))
            )
        )

    def is_blocking_optics(self, x: int, y: int) -> bool:
        """Return whether a Tile or center object blocks ordinary optics."""
        tile = self._tiles.get((x, y))
        if tile is None or tile.blocks_optics:
            return True
        for obj_uuid in self.get_center_objects_at((x, y)):
            block = BaseBlock.get(obj_uuid)
            if block is not None and block.blocks_optics_at_center():
                return True
        if any(
            condition.blocks_physical_optics_at((x, y))
            for condition in self.get_spatial_conditions_at((x, y))
        ):
            return True
        return False

    def _edge_contribution_allows(
        self,
        contribution: WorldEdgeStructuralContribution,
        channel: WorldEdgeChannel,
        *,
        source_height: int,
        destination_height: int,
        movement_mode: MovementMode,
        treat_closed_doors_as_interactable: bool,
        ignorable_provider_uuids: frozenset[UUID],
        visible_provider_uuids: Optional[frozenset[UUID]] = None,
    ) -> bool:
        """Evaluate one contribution under the canonical channel policy."""
        if (
            channel is WorldEdgeChannel.MOVEMENT
            and visible_provider_uuids is not None
            and contribution.provider_uuid not in visible_provider_uuids
        ):
            return True
        if (
            treat_closed_doors_as_interactable
            and contribution.provider_uuid in ignorable_provider_uuids
        ):
            return True
        if channel not in contribution.blocked_channels:
            return True
        if channel is not WorldEdgeChannel.MOVEMENT:
            return False
        if movement_mode is not MovementMode.WALKING:
            return False
        lower = min(source_height, destination_height)
        upper = max(source_height, destination_height) + 1
        return not (
            contribution.base_height_steps < upper
            and contribution.top_height_steps > lower
        )

    def _edge_layer_allows(
        self,
        contributions: Tuple[WorldEdgeStructuralContribution, ...],
        channel: WorldEdgeChannel,
        *,
        source_height: int,
        destination_height: int,
        movement_mode: MovementMode,
        treat_closed_doors_as_interactable: bool,
        ignorable_provider_uuids: frozenset[UUID],
        visible_provider_uuids: Optional[frozenset[UUID]] = None,
    ) -> bool:
        """Evaluate one ordered layer with the canonical contribution policy."""
        return all(
            self._edge_contribution_allows(
                contribution,
                channel,
                source_height=source_height,
                destination_height=destination_height,
                movement_mode=movement_mode,
                treat_closed_doors_as_interactable=treat_closed_doors_as_interactable,
                ignorable_provider_uuids=ignorable_provider_uuids,
                visible_provider_uuids=visible_provider_uuids,
            )
            for contribution in contributions
        )

    def _edge_channel_allows(
        self,
        view: WorldEdgeView,
        channel: WorldEdgeChannel,
        *,
        source_height: Optional[int] = None,
        destination_height: Optional[int] = None,
        movement_mode: MovementMode = MovementMode.WALKING,
        treat_closed_doors_as_interactable: bool = False,
        ignorable_provider_uuids: frozenset[UUID] = frozenset(),
        visible_provider_uuids: Optional[frozenset[UUID]] = None,
    ) -> bool:
        """Evaluate both ordered endpoint layers for one channel."""
        source_height = view.source_height_steps if source_height is None else source_height
        destination_height = view.destination_height_steps if destination_height is None else destination_height

        return (
            self._edge_layer_allows(
                view.exit_contributions,
                channel,
                source_height=source_height,
                destination_height=destination_height,
                movement_mode=movement_mode,
                treat_closed_doors_as_interactable=treat_closed_doors_as_interactable,
                ignorable_provider_uuids=ignorable_provider_uuids,
                visible_provider_uuids=visible_provider_uuids,
            )
            and self._edge_layer_allows(
                view.entry_contributions,
                channel,
                source_height=source_height,
                destination_height=destination_height,
                movement_mode=movement_mode,
                treat_closed_doors_as_interactable=treat_closed_doors_as_interactable,
                ignorable_provider_uuids=ignorable_provider_uuids,
                visible_provider_uuids=visible_provider_uuids,
            )
        )

    def _remembered_transition_allows(self, from_pos: Tuple[int, int], to_pos: Tuple[int, int],
                                      blocked: Optional[Set[Tuple[Tuple[int, int], str]]]) -> bool:
        if not blocked:
            return True
        tile = self._tiles.get(from_pos)
        if tile is None:
            return False
        directions = tile.directions_toward(to_pos)
        if not directions:
            return True
        return all((from_pos, direction) not in blocked for direction in directions)

    def _transition_cell_allows(self, position: Tuple[int, int], channel: str,
                                requester_uuid: Optional[UUID] = None,
                                movement_mode: MovementMode = MovementMode.WALKING,
                                walk_in_danger: bool = True,
                                subjective: bool = False,
                                collision_blocked: Optional[Set[Tuple[int, int]]] = None,
                                movement_cell_cache: Optional[Dict[Tuple[int, int], bool]] = None) -> bool:
        if channel == "movement":
            if movement_cell_cache is not None:
                cached = movement_cell_cache.get(position)
                if cached is not None:
                    return cached
            if requester_uuid is None:
                result = self.is_walkable(position[0], position[1], movement_mode)
            else:
                result = self.is_walkable_for(
                    position[0], position[1], requester_uuid, movement_mode,
                    walk_in_danger, subjective, collision_blocked,
                )
            if movement_cell_cache is not None:
                movement_cell_cache[position] = result
            return result
        if channel == "propagation":
            return not self.is_blocking_propagation(position[0], position[1])
        return not self.is_blocking_optics(position[0], position[1])

    def _cardinal_transition_sides_allow(self, from_pos: Tuple[int, int], to_pos: Tuple[int, int],
                                         channel: str,
                                         requester_uuid: Optional[UUID] = None,
                                         movement_mode: MovementMode = MovementMode.WALKING,
                                         subjective: bool = False,
                                         directional_collision_blocked: Optional[Set[Tuple[Tuple[int, int], str]]] = None,
                                         side_cache: Optional[Dict[Tuple[Tuple[int, int], Tuple[int, int]], bool]] = None,
                                         treat_closed_doors_as_interactable: bool = False) -> bool:
        dx = abs(to_pos[0] - from_pos[0])
        dy = abs(to_pos[1] - from_pos[1])
        if dx + dy != 1:
            return False
        if from_pos not in self._tiles or to_pos not in self._tiles:
            return False
        if channel == "movement" and not self._remembered_transition_allows(from_pos, to_pos, directional_collision_blocked):
            return False
        key = (from_pos, to_pos)
        if side_cache is not None:
            cached = side_cache.get(key)
            if cached is not None:
                return cached
        view, ignorable_provider_uuids = self._derive_world_edge(from_pos, to_pos)
        visible_provider_uuids: Optional[frozenset[UUID]] = None
        if subjective and channel == WorldEdgeChannel.MOVEMENT.value and requester_uuid is not None:
            requester = BaseBlock.get(requester_uuid)
            senses = requester.get_senses() if requester is not None else None
            if senses is not None:
                visible_provider_uuids = frozenset(senses.objects)
        result = self._edge_channel_allows(
            view,
            WorldEdgeChannel(channel),
            source_height=self._tiles[from_pos].height,
            destination_height=self._tiles[to_pos].height,
            movement_mode=movement_mode,
            treat_closed_doors_as_interactable=treat_closed_doors_as_interactable,
            ignorable_provider_uuids=ignorable_provider_uuids,
            visible_provider_uuids=visible_provider_uuids,
        )
        if side_cache is not None:
            side_cache[key] = result
        return result

    def _elevation_transition_allows(
        self,
        from_pos: Tuple[int, int],
        to_pos: Tuple[int, int],
        movement_mode: MovementMode,
    ) -> bool:
        """Return whether one cardinal leg is legal for its movement mode."""
        from_tile = self._tiles.get(from_pos)
        to_tile = self._tiles.get(to_pos)
        if from_tile is None or to_tile is None:
            return False
        if from_tile.height == to_tile.height:
            return True
        if movement_mode is MovementMode.FLYING:
            return True
        if movement_mode is not MovementMode.WALKING:
            return False
        return progressive_elevation_transition(
            from_tile.height,
            from_tile.elevation_surface_kind,
            from_tile.slope_axis,
            to_tile.height,
            to_tile.elevation_surface_kind,
            to_tile.slope_axis,
            transition_axis(from_pos, to_pos),
        )

    def movement_edge_cost_units(
        self,
        from_pos: Tuple[int, int],
        to_pos: Tuple[int, int],
        movement_mode: MovementMode,
        *,
        ignore_difficult_terrain: bool = False,
    ) -> float:
        """Return the exact destination-policy cost for one admitted edge."""
        from_tile = self._tiles.get(from_pos)
        to_tile = self._tiles.get(to_pos)
        if from_tile is None or to_tile is None:
            raise ValueError("movement edge cost requires both support tiles")
        terrain_multiplier = to_tile.get_movement_cost(movement_mode)
        if movement_mode is MovementMode.WALKING and ignore_difficult_terrain:
            terrain_multiplier = min(terrain_multiplier, 1.0)
        if movement_mode is not MovementMode.FLYING:
            return terrain_multiplier
        base_leg_feet = support_distance_feet(
            from_pos,
            from_tile.height * 5,
            to_pos,
            to_tile.height * 5,
        )
        return (base_leg_feet / 5) * terrain_multiplier

    def _diagonal_transition_allows(self, from_pos: Tuple[int, int], to_pos: Tuple[int, int],
                                    channel: str,
                                    requester_uuid: Optional[UUID] = None,
                                    movement_mode: MovementMode = MovementMode.WALKING,
                                    walk_in_danger: bool = True,
                                    subjective: bool = False,
                                    collision_blocked: Optional[Set[Tuple[int, int]]] = None,
                                    directional_collision_blocked: Optional[Set[Tuple[Tuple[int, int], str]]] = None,
                                    side_cache: Optional[Dict[Tuple[Tuple[int, int], Tuple[int, int]], bool]] = None,
                                    movement_cell_cache: Optional[Dict[Tuple[int, int], bool]] = None,
                                    treat_closed_doors_as_interactable: bool = False) -> bool:
        dx = to_pos[0] - from_pos[0]
        dy = to_pos[1] - from_pos[1]
        if abs(dx) != 1 or abs(dy) != 1:
            return False
        if channel == "movement" and movement_mode is not MovementMode.FLYING:
            from_tile = self._tiles.get(from_pos)
            to_tile = self._tiles.get(to_pos)
            if (
                from_tile is None
                or to_tile is None
                or from_tile.height != to_tile.height
            ):
                return False

        bridges = ((from_pos[0] + dx, from_pos[1]), (from_pos[0], from_pos[1] + dy))
        for bridge in bridges:
            if bridge not in self._tiles:
                continue
            if not self._transition_cell_allows(
                bridge, channel, requester_uuid, movement_mode,
                walk_in_danger, subjective, collision_blocked,
                movement_cell_cache,
            ):
                continue
            if (
                (
                    channel != "movement"
                    or (
                        self._elevation_transition_allows(
                            from_pos,
                            bridge,
                            movement_mode,
                        )
                        and self._elevation_transition_allows(
                            bridge,
                            to_pos,
                            movement_mode,
                        )
                    )
                )
                and self._cardinal_transition_sides_allow(
                    from_pos, bridge, channel, requester_uuid, movement_mode,
                    subjective, directional_collision_blocked, side_cache,
                    treat_closed_doors_as_interactable,
                )
                and self._cardinal_transition_sides_allow(
                    bridge, to_pos, channel, requester_uuid, movement_mode,
                    subjective, directional_collision_blocked, side_cache,
                    treat_closed_doors_as_interactable,
                )
            ):
                return True
        return False

    def can_transition(self, from_pos: Tuple[int, int], to_pos: Tuple[int, int],
                       requesting_entity_uuid: Optional[UUID] = None,
                       movement_mode: MovementMode = MovementMode.WALKING,
                       walk_in_danger: bool = True,
                       subjective: bool = False,
                       collision_blocked: Optional[Set[Tuple[int, int]]] = None,
                       directional_collision_blocked: Optional[Set[Tuple[Tuple[int, int], str]]] = None,
                       side_cache: Optional[Dict[Tuple[Tuple[int, int], Tuple[int, int]], bool]] = None,
                       movement_cell_cache: Optional[Dict[Tuple[int, int], bool]] = None,
                       treat_closed_doors_as_interactable: bool = False) -> bool:
        """Return whether movement can cross from one adjacent tile to another."""
        if from_pos == to_pos:
            return True
        if max(abs(to_pos[0] - from_pos[0]), abs(to_pos[1] - from_pos[1])) > 1:
            return False
        if from_pos not in self._tiles or to_pos not in self._tiles:
            return False
        if abs(to_pos[0] - from_pos[0]) == 1 and abs(to_pos[1] - from_pos[1]) == 1:
            if not self._diagonal_transition_allows(
                from_pos, to_pos, "movement", requesting_entity_uuid, movement_mode,
                walk_in_danger, subjective, collision_blocked,
                directional_collision_blocked, side_cache,
                movement_cell_cache,
                treat_closed_doors_as_interactable,
            ):
                return False
            return self._transition_cell_allows(
                to_pos,
                "movement",
                requesting_entity_uuid,
                movement_mode,
                walk_in_danger,
                subjective,
                collision_blocked,
                movement_cell_cache,
            )
        if not self._remembered_transition_allows(from_pos, to_pos, directional_collision_blocked):
            return False
        if not self._cardinal_transition_sides_allow(
            from_pos,
            to_pos,
            "movement",
            requesting_entity_uuid,
            movement_mode,
            subjective,
            directional_collision_blocked,
            side_cache,
            treat_closed_doors_as_interactable,
        ):
            return False
        return self._transition_cell_allows(
            to_pos,
            "movement",
            requesting_entity_uuid,
            movement_mode,
            walk_in_danger,
            subjective,
            collision_blocked,
            movement_cell_cache,
        ) and self._elevation_transition_allows(
            from_pos,
            to_pos,
            movement_mode,
        )

    def can_optical_transition(
        self,
        from_pos: Tuple[int, int],
        to_pos: Tuple[int, int],
    ) -> bool:
        """Return whether ordinary optics can cross one adjacent transition."""
        if abs(to_pos[0] - from_pos[0]) == 1 and abs(to_pos[1] - from_pos[1]) == 1:
            return self._diagonal_transition_allows(
                from_pos,
                to_pos,
                "optical",
            )
        return self._cardinal_transition_sides_allow(from_pos, to_pos, "optical")

    def can_propagate_transition(self, from_pos: Tuple[int, int], to_pos: Tuple[int, int],
                                 requester_uuid: Optional[UUID] = None,
                                 subjective: bool = False) -> bool:
        if abs(to_pos[0] - from_pos[0]) == 1 and abs(to_pos[1] - from_pos[1]) == 1:
            return self._diagonal_transition_allows(from_pos, to_pos, "propagation", requester_uuid, subjective=subjective)
        return self._cardinal_transition_sides_allow(
            from_pos,
            to_pos,
            "propagation",
            requester_uuid=requester_uuid,
            subjective=subjective,
        )

    def identify_blocker_at(
        self,
        position: Tuple[int, int],
        requesting_entity_uuid: Optional[UUID] = None,
        mode: MovementMode = MovementMode.WALKING,
        *,
        source_position: Optional[Tuple[int, int]] = None,
    ) -> Optional[str]:
        """Return one public blocker identity, or ``None`` when admissible.

        With ``source_position`` this performs the complete adjacent transition
        decision once, including ordered boundary identity. Without it, the
        query retains its existing destination-cell blocker contract.
        """
        if source_position is not None:
            delta_x = position[0] - source_position[0]
            delta_y = position[1] - source_position[1]
            if abs(delta_x) <= 1 and abs(delta_y) <= 1 and (delta_x or delta_y):
                if (
                    source_position not in self._tiles
                    or position not in self._tiles
                ):
                    return "edge of map"
                if abs(delta_x) == 1 and abs(delta_y) == 1:
                    if self._diagonal_transition_allows(
                        source_position,
                        position,
                        WorldEdgeChannel.MOVEMENT.value,
                        requesting_entity_uuid,
                        mode,
                    ) and self._transition_cell_allows(
                        position,
                        WorldEdgeChannel.MOVEMENT.value,
                        requesting_entity_uuid,
                        mode,
                    ):
                        return None
                else:
                    view, ignorable_provider_uuids = self._derive_world_edge(
                        source_position,
                        position,
                    )
                    source_tile = self._tiles[source_position]
                    destination_tile = self._tiles[position]
                    for contribution in (
                        *view.exit_contributions,
                        *view.entry_contributions,
                    ):
                        if self._edge_contribution_allows(
                            contribution,
                            WorldEdgeChannel.MOVEMENT,
                            source_height=source_tile.height,
                            destination_height=destination_tile.height,
                            movement_mode=mode,
                            treat_closed_doors_as_interactable=False,
                            ignorable_provider_uuids=ignorable_provider_uuids,
                        ):
                            continue
                        provider = BaseBlock.get(contribution.provider_uuid)
                        return provider.name if provider is not None else "obstacle"
                    if self._transition_cell_allows(
                        position,
                        WorldEdgeChannel.MOVEMENT.value,
                        requesting_entity_uuid,
                        mode,
                    ) and self._elevation_transition_allows(
                        source_position,
                        position,
                        mode,
                    ):
                        return None

        tile = self._tiles.get(position)
        if tile is None:
            return "edge of map"
        if tile.blocks_walking(mode=mode):
            return tile.name

        for entity_uuid in self.get_entities_at(position):
            block = BaseBlock.get(entity_uuid)
            if block is not None and block.blocks_walking(requesting_entity_uuid, mode):
                return block.name

        for obj_uuid in self.get_center_objects_at(position):
            block = BaseBlock.get(obj_uuid)
            if block is not None and block.blocks_walking(requesting_entity_uuid, mode):
                return block.name

        for condition in self.get_spatial_conditions_at(position):
            if condition.blocks_walking_at(
                position,
                requesting_entity_uuid,
                mode,
            ):
                return condition.name

        return "obstacle"

    def _update_bounds(self) -> None:
        """Recalculate grid bounds from tiles."""
        if not self._tiles:
            self._min_x = self._max_x = 0
            self._min_y = self._max_y = 0
        else:
            positions = list(self._tiles.keys())
            self._min_x = min(p[0] for p in positions)
            self._max_x = max(p[0] for p in positions)
            self._min_y = min(p[1] for p in positions)
            self._max_y = max(p[1] for p in positions)
        self._bounds_dirty = False

    @property
    def width(self) -> int:
        """Grid width (max_x - min_x + 1)."""
        if self._bounds_dirty:
            self._update_bounds()
        return self._max_x - self._min_x + 1 if self._tiles else 0

    @property
    def height(self) -> int:
        """Grid height (max_y - min_y + 1)."""
        if self._bounds_dirty:
            self._update_bounds()
        return self._max_y - self._min_y + 1 if self._tiles else 0

    @property
    def bounds(self) -> Tuple[int, int, int, int]:
        """Grid bounds as (min_x, min_y, max_x, max_y)."""
        if self._bounds_dirty:
            self._update_bounds()
        return (self._min_x, self._min_y, self._max_x, self._max_y)

    @property
    def size(self) -> Tuple[int, int]:
        """Grid size as (width, height)."""
        return (self.width, self.height)

    def create_rectangle(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        surface: TileSurface,
        walking_cost: int = 1,
        flying_cost: int = 1,
        swimming_cost: int = 0,
        burrowing_cost: int = 0,
        blocks_optics: bool = False,
        blocks_propagation: bool = False,
        name: str = "Floor",
    ) -> None:
        """Create a rectangular area of tiles (batch operation, no events during)."""
        positions = {
            (tx, ty)
            for tx in range(x, x + width)
            for ty in range(y, y + height)
        }
        for position in positions:
            self._assert_tile_replacement_allowed(
                position,
                self._tiles.get(position),
            )
        events_were_enabled = self._events_enabled
        self.disable_events()
        try:
            for tx in range(x, x + width):
                for ty in range(y, y + height):
                    old_tile = self._tiles.get((tx, ty))
                    if old_tile:
                        self._tiles_by_uuid.pop(old_tile.uuid, None)

                    tile = Tile.create(
                        position=(tx, ty),
                        surface=surface,
                        walking_cost=walking_cost,
                        flying_cost=flying_cost,
                        swimming_cost=swimming_cost,
                        burrowing_cost=burrowing_cost,
                        blocks_optics=blocks_optics,
                        blocks_propagation=blocks_propagation,
                        name=name
                    )
                    self._tiles[(tx, ty)] = tile
                    self._tiles_by_uuid[tile.uuid] = (tx, ty)
            self._bounds_dirty = True
        finally:
            self._bump_all_spatial_revisions()
            if events_were_enabled:
                self.enable_events()

    @staticmethod
    def _validate_entity_position(
        position: Optional[Tuple[int, int]],
        *,
        allow_none: bool = True,
    ) -> None:
        """Require one exact objective coordinate at the Tile boundary."""
        if position is None:
            if allow_none:
                return
            raise ValueError("entity position cannot be None")
        if (
            type(position) is not tuple
            or len(position) != 2
            or any(type(component) is not int for component in position)
        ):
            raise ValueError("entity position must be an exact tuple[int, int]")

    def _commit_entity_membership(
        self,
        entity_uuid: UUID,
        expected_old_position: Optional[Tuple[int, int]],
        new_position: Optional[Tuple[int, int]],
    ) -> GridEntityMembershipReceipt:
        """Atomically replace the one Entity UUID membership row."""
        if not self._events_enabled:
            raise PositionCommitError(
                ValueError("Entity occupancy requires enabled GridMap events"),
            )
        self._validate_entity_position(expected_old_position)
        self._validate_entity_position(new_position)
        block = BaseBlock.get(entity_uuid)
        if block is None:
            raise PositionCommitError(
                ValueError(f"entity identity {entity_uuid} is not registered"),
            )
        block_position = block.get_position()
        if new_position is not None and block_position != new_position:
            raise PositionCommitError(
                ValueError("Entity objective position does not match destination"),
            )
        if expected_old_position is not None and block_position not in {
            expected_old_position,
            new_position,
        }:
            raise PositionCommitError(
                ValueError("Entity objective position does not match transition"),
            )

        old_tile = (
            self._tiles.get(expected_old_position)
            if expected_old_position is not None
            else None
        )
        new_tile = (
            self._tiles.get(new_position)
            if new_position is not None
            else None
        )
        if expected_old_position is not None and old_tile is None:
            raise PositionCommitError(ValueError("source Tile does not exist"))
        if new_position is not None and new_tile is None:
            raise PositionCommitError(ValueError("destination Tile does not exist"))
        if (
            expected_old_position is not None
            and old_tile is not None
            and entity_uuid not in old_tile.get_entity_uuids()
        ):
            raise PositionCommitError(
                ValueError("source Tile does not contain the Entity UUID"),
            )
        if (
            new_tile is not None
            and new_position != expected_old_position
            and entity_uuid in new_tile.get_entity_uuids()
        ):
            raise PositionCommitError(
                ValueError("destination Tile already contains the Entity UUID"),
            )

        if expected_old_position == new_position:
            return GridEntityMembershipReceipt(
                entity_uuid=entity_uuid,
                old_position=expected_old_position,
                new_position=new_position,
            )

        old_members = old_tile.get_entity_uuids() if old_tile is not None else None
        new_members = new_tile.get_entity_uuids() if new_tile is not None else None
        try:
            if old_tile is not None and old_members is not None:
                old_members.discard(entity_uuid)
                old_tile._replace_entity_uuids(old_members)
            if new_tile is not None and new_members is not None:
                new_members.add(entity_uuid)
                new_tile._replace_entity_uuids(new_members)
            self.invalidate_occupancy_paths()
        except BaseException as exc:
            if old_tile is not None and old_members is not None:
                old_tile._replace_entity_uuids(old_members | {entity_uuid})
            if new_tile is not None and new_members is not None:
                new_tile._replace_entity_uuids(new_members - {entity_uuid})
            raise PositionCommitError(exc) from exc

        return GridEntityMembershipReceipt(
            entity_uuid=entity_uuid,
            old_position=expected_old_position,
            new_position=new_position,
        )

    def _publish_entity_membership(
        self,
        receipt: GridEntityMembershipReceipt,
        *,
        parent_event: Optional[UUID] = None,
    ) -> None:
        """Publish facts for an already committed Entity membership row."""
        block = BaseBlock.get(receipt.entity_uuid)
        if block is None:
            raise ValueError("membership receipt identity no longer exists")
        if receipt.new_position is not None:
            tile = self._tiles.get(receipt.new_position)
            if tile is None or receipt.entity_uuid not in tile.get_entity_uuids():
                raise ValueError("membership receipt destination is not committed")
        if receipt.old_position is not None and receipt.old_position == receipt.new_position:
            raise ValueError("membership receipt cannot publish a no-op")
        if receipt.old_position is not None:
            event = SpatialChangeEvent.entity_left(
                receipt.old_position,
                receipt.entity_uuid,
                receipt.new_position,
                parent_event=parent_event,
            )
            self._fire_committed_spatial_event(event)
        if receipt.new_position is not None:
            event = SpatialChangeEvent.entity_entered(
                receipt.new_position,
                receipt.entity_uuid,
                receipt.old_position,
                parent_event=parent_event,
            )
            self._fire_committed_spatial_event(event)

    def get_entity_position(self, entity_uuid: UUID) -> Optional[Tuple[int, int]]:
        """Return a neutral block coordinate only for a present Tile member."""
        block = BaseBlock.get(entity_uuid)
        if block is None:
            return None
        position = block.get_position()
        self._validate_entity_position(position, allow_none=False)
        tile = self._tiles.get(position)
        if tile is None or entity_uuid not in tile.get_entity_uuids():
            return None
        return position

    def get_entities_at(self, position: Tuple[int, int]) -> Set[UUID]:
        """Return a defensive UUID snapshot from one authoritative Tile."""
        self._validate_entity_position(position, allow_none=False)
        tile = self._tiles.get(position)
        if tile is None:
            return set()
        entity_uuids = tile.get_entity_uuids()
        for entity_uuid in entity_uuids:
            block = BaseBlock.get(entity_uuid)
            if block is None or block.get_position() != position:
                raise RuntimeError(
                    f"Tile membership {entity_uuid} does not match {position}",
                )
        return entity_uuids

    @property
    def last_operation_diagnostics(self) -> GridMapOperationDiagnostics:
        """Return the immutable counters from the most recent measured query."""
        return self._last_operation_diagnostics

    def _begin_operation_diagnostics(self, operation: str) -> None:
        self._last_operation_diagnostics = GridMapOperationDiagnostics(operation)

    def _finish_operation_diagnostics(
        self,
        operation: str,
        *,
        tiles_inspected: int = 0,
        bands_inspected: int = 0,
        bands_replaced: int = 0,
        placement_iterator_rows_visited: int = 0,
        path_edge_queries: int = 0,
    ) -> None:
        self._last_operation_diagnostics = GridMapOperationDiagnostics(
            operation=operation,
            tiles_inspected=tiles_inspected,
            bands_inspected=bands_inspected,
            bands_replaced=bands_replaced,
            placement_iterator_rows_visited=placement_iterator_rows_visited,
            path_edge_queries=path_edge_queries,
        )

    @staticmethod
    def _opposite_direction(direction: CardinalDirection) -> CardinalDirection:
        return {
            CardinalDirection.NORTH: CardinalDirection.SOUTH,
            CardinalDirection.SOUTH: CardinalDirection.NORTH,
            CardinalDirection.EAST: CardinalDirection.WEST,
            CardinalDirection.WEST: CardinalDirection.EAST,
        }[direction]

    @staticmethod
    def _directional_neighbor(
        position: Tuple[int, int],
        direction: CardinalDirection,
    ) -> Tuple[int, int]:
        """Return the one adjacent cell on an authored boundary side."""
        offsets = {
            CardinalDirection.NORTH: (0, 1),
            CardinalDirection.SOUTH: (0, -1),
            CardinalDirection.EAST: (1, 0),
            CardinalDirection.WEST: (-1, 0),
        }
        dx, dy = offsets[direction]
        return position[0] + dx, position[1] + dy

    def _capture_boundary_views(
        self,
        placements: Iterable[WorldObjectPlacement],
        *,
        structure_overrides: Optional[Dict[UUID, Optional[BoundaryStructure]]] = None,
    ) -> tuple[
        Dict[Tuple[Tuple[int, int], Tuple[int, int]], WorldEdgeView],
        Set[Tuple[int, int]],
        Set[Tuple[int, int]],
    ]:
        """Capture only live ordered edges incident to the supplied side owners."""
        views: Dict[
            Tuple[Tuple[int, int], Tuple[int, int]],
            WorldEdgeView,
        ] = {}
        owners: Set[Tuple[int, int]] = set()
        endpoints: Set[Tuple[int, int]] = set()
        for placement in placements:
            if (
                placement.kind is not WorldPlacementKind.BOUNDARY
                or placement.boundary_direction is None
            ):
                continue
            owner = placement.position
            owners.add(owner)
            endpoints.add(owner)
            neighbor = self._directional_neighbor(
                owner,
                placement.boundary_direction,
            )
            if neighbor not in self._tiles:
                continue
            endpoints.add(neighbor)
            views[(owner, neighbor)] = self._derive_world_edge(
                owner,
                neighbor,
                structure_overrides=structure_overrides,
            )[0]
        return views, owners, endpoints

    def _boundary_answer(
        self,
        view: WorldEdgeView,
    ) -> tuple[bool, bool, bool, bool]:
        """Return optical, propagation, walking, and nonwalking edge answers."""
        return (
            self._edge_channel_allows(view, WorldEdgeChannel.OPTICAL),
            self._edge_channel_allows(view, WorldEdgeChannel.PROPAGATION),
            self._edge_channel_allows(
                view,
                WorldEdgeChannel.MOVEMENT,
                movement_mode=MovementMode.WALKING,
            ),
            self._edge_channel_allows(
                view,
                WorldEdgeChannel.MOVEMENT,
                movement_mode=MovementMode.FLYING,
            ),
        )

    def _aggregate_boundary_changes(
        self,
        before_views: Mapping[
            Tuple[Tuple[int, int], Tuple[int, int]],
            WorldEdgeView,
        ],
        after_views: Mapping[
            Tuple[Tuple[int, int], Tuple[int, int]],
            WorldEdgeView,
        ],
    ) -> Set[str]:
        """Compare one bounded before/after side set without retaining a signature."""
        changed: Set[str] = set()
        open_answer = (True, True, True, True)
        for edge in set(before_views) | set(after_views):
            before = before_views.get(edge)
            after = after_views.get(edge)
            before_answer = open_answer if before is None else self._boundary_answer(before)
            after_answer = open_answer if after is None else self._boundary_answer(after)
            if before_answer[0] != after_answer[0]:
                changed.add(WorldEdgeChannel.OPTICAL.value)
            if before_answer[1] != after_answer[1]:
                changed.add(WorldEdgeChannel.PROPAGATION.value)
            if before_answer[2] != after_answer[2] or before_answer[3] != after_answer[3]:
                changed.add(WorldEdgeChannel.MOVEMENT.value)
        return changed

    def _object_senses_hint(
        self,
        object_uuid: UUID,
        position: Tuple[int, int],
        *,
        changed_channels: Set[str],
        owners: Set[Tuple[int, int]],
        endpoints: Set[Tuple[int, int]],
        placed: bool = False,
        removed: bool = False,
    ) -> SensesUpdateHint:
        """Build bounded endpoint evidence and aggregate-only channel flags."""
        endpoint_positions = set(endpoints)
        if "optical" in changed_channels and not endpoint_positions:
            endpoint_positions.add(position)
        return SensesUpdateHint(
            requires_fov="optical" in changed_channels,
            requires_paths="movement" in changed_channels,
            object_placed=(object_uuid, position) if placed else None,
            object_removed=(object_uuid, position) if removed else None,
            light_changed_positions=(
                endpoint_positions if "optical" in changed_channels else None
            ),
            directional_positions=set(owners) or None,
            directional_neighbors=(endpoint_positions - owners) or None,
            directional_channels_changed=(
                set(changed_channels) or None
            ),
            requires_light_recompute="optical" in changed_channels,
            requires_propagation_recompute="propagation" in changed_channels,
        )

    def _placement_band_heights(
        self,
        placement: WorldObjectPlacement,
    ) -> range:
        return range(placement.base_height_steps, placement.top_height_steps)

    def _placement_work_counts(
        self,
        placements: Iterable[WorldObjectPlacement],
    ) -> Tuple[int, int]:
        """Count only local Tiles and bands touched by placement admission."""
        tiles: set[Tuple[int, int]] = set()
        bands: set[Tuple[Tuple[int, int], Optional[CardinalDirection], int]] = set()
        for placement in placements:
            tiles.add(placement.position)
            bands.update(self._placement_band_keys(placement))
        return len(tiles), len(bands)

    def _resolve_object_placement(
        self,
        object_uuid: UUID,
        position: Tuple[int, int],
        boundary_direction: Optional[CardinalDirection] = None,
        orientation: Optional[CardinalDirection] = None,
        base_height_steps: Optional[int] = None,
    ) -> WorldObjectPlacement:
        """Resolve a provider-owned placement capability against one Tile."""
        if (
            type(position) is not tuple
            or len(position) != 2
            or any(type(value) is not int for value in position)
        ):
            raise TypeError("object placement position must be a pair of exact integers")
        tile = self._tiles.get(position)
        if tile is None:
            raise ValueError(f"cannot place object on missing tile {position}")
        obj = BaseBlock.get(object_uuid)
        if obj is None:
            raise ValueError(f"cannot place unknown object {object_uuid}")
        spec = obj.get_world_placement_spec()
        if base_height_steps is not None and type(base_height_steps) is not int:
            raise TypeError("base_height_steps must be an exact integer number of steps")
        if boundary_direction is not None and type(boundary_direction) is not CardinalDirection:
            raise TypeError("boundary_direction must be a CardinalDirection or None")
        if orientation is not None and type(orientation) is not CardinalDirection:
            raise TypeError("orientation must be a CardinalDirection or None")
        if spec.kind is WorldPlacementKind.BOUNDARY:
            if boundary_direction is None:
                raise ValueError("boundary placements require a boundary_direction")
            committed_orientation = orientation
        else:
            if boundary_direction is not None:
                raise ValueError("center placements cannot define boundary_direction")
            committed_orientation = orientation
        base_height = tile.height if base_height_steps is None else base_height_steps
        if spec.kind is WorldPlacementKind.CENTER and base_height != tile.height:
            raise ValueError("center placements must begin at the Tile support height")
        return WorldObjectPlacement(
            object_uuid=object_uuid,
            tile_uuid=tile.uuid,
            position=position,
            kind=spec.kind,
            occupies_bands=spec.occupies_bands,
            boundary_direction=boundary_direction,
            base_height_steps=base_height,
            top_height_steps=base_height + spec.vertical_extent_steps,
            orientation=committed_orientation,
        )

    def _placement_band_snapshots(
        self,
        placement: WorldObjectPlacement,
    ) -> Tuple[Tuple[Tile, CardinalDirection | None, int, TileObjectBand], ...]:
        tile = self._tiles[placement.position]
        if placement.kind is WorldPlacementKind.CENTER:
            return tuple(
                (tile, None, height, tile._center_object_bands.get(height, TileObjectBand()))
                for height in self._placement_band_heights(placement)
            )
        assert placement.boundary_direction is not None
        return tuple(
            (
                tile,
                placement.boundary_direction,
                height,
                tile._boundary_object_bands.get(placement.boundary_direction, {}).get(
                    height,
                    TileObjectBand(),
                ),
            )
            for height in self._placement_band_heights(placement)
        )

    def _validate_placement_collision(
        self,
        placement: WorldObjectPlacement,
        *,
        staged_occupants: Optional[
            Mapping[Tuple[Tuple[int, int], Optional[CardinalDirection], int], UUID]
        ] = None,
    ) -> None:
        """Check all occupied center or boundary bands before mutation."""
        if not placement.occupies_bands:
            return
        for _tile, direction, height, band in self._placement_band_snapshots(placement):
            key = (placement.position, direction, height)
            incumbent = band.occupant_uuid
            if staged_occupants is not None and key in staged_occupants:
                incumbent = staged_occupants[key]
            if incumbent not in (None, placement.object_uuid):
                raise ValueError(
                    f"placement band is occupied by {incumbent}",
                )

    def validate_object_placement(
        self,
        object_uuid: UUID,
        position: Tuple[int, int],
        boundary_direction: Optional[CardinalDirection] = None,
        orientation: Optional[CardinalDirection] = None,
        base_height_steps: Optional[int] = None,
    ) -> WorldObjectPlacement:
        """Resolve and validate a placement without mutating GridMap state."""
        placement = self._resolve_object_placement(
            object_uuid,
            position,
            boundary_direction,
            orientation,
            base_height_steps,
        )
        self._validate_placement_collision(placement)
        return placement

    def validate_object_placement_batch(
        self,
        object_uuids: Iterable[UUID],
        position: Tuple[int, int],
    ) -> Tuple[WorldObjectPlacement, ...]:
        """Return jointly admissible immutable placements without mutation.

        The local staged occupants reuse the same collision authority as normal
        placement admission. They exist only for this pure preflight and are
        discarded with the returned candidates.
        """
        candidates: list[WorldObjectPlacement] = []
        seen_object_uuids: set[UUID] = set()
        staged_occupants: Dict[
            Tuple[Tuple[int, int], Optional[CardinalDirection], int], UUID
        ] = {}
        for object_uuid in object_uuids:
            if object_uuid in seen_object_uuids:
                raise ValueError(
                    f"placement batch contains duplicate object {object_uuid}",
                )
            seen_object_uuids.add(object_uuid)
            candidate = self._resolve_object_placement(object_uuid, position)
            self._validate_placement_collision(
                candidate,
                staged_occupants=staged_occupants,
            )
            if candidate.occupies_bands:
                for key in self._placement_band_keys(candidate):
                    staged_occupants[key] = candidate.object_uuid
            candidates.append(candidate)
        return tuple(candidates)

    def _replace_placement_bands(
        self,
        placement: WorldObjectPlacement,
        *,
        add: bool,
    ) -> int:
        tile = self._tiles[placement.position]
        replacements = 0
        for _tile, direction, height, old_band in self._placement_band_snapshots(placement):
            object_uuids = set(old_band.object_uuids)
            if add:
                object_uuids.add(placement.object_uuid)
            else:
                object_uuids.discard(placement.object_uuid)
            occupant_uuid = old_band.occupant_uuid
            if placement.occupies_bands:
                occupant_uuid = placement.object_uuid if add else None
            new_band = TileObjectBand(
                object_uuids=frozenset(object_uuids),
                occupant_uuid=occupant_uuid,
            )
            if new_band == old_band:
                continue
            if direction is None:
                tile._replace_center_object_band(
                    height,
                    new_band if new_band.object_uuids else None,
                )
            else:
                tile._replace_boundary_object_band(
                    direction,
                    height,
                    new_band if new_band.object_uuids else None,
                )
            replacements += 1
        return replacements

    def _placement_band_keys(
        self,
        placement: WorldObjectPlacement,
    ) -> Tuple[Tuple[Tuple[int, int], Optional[CardinalDirection], int], ...]:
        """Return the authoritative Tile-band keys for one placement row."""
        return tuple(
            (
                placement.position,
                placement.boundary_direction
                if placement.kind is WorldPlacementKind.BOUNDARY
                else None,
                height,
            )
            for height in self._placement_band_heights(placement)
        )

    def _snapshot_object_mutation(
        self,
        placements: Iterable[WorldObjectPlacement],
    ) -> Dict[
        Tuple[Tuple[int, int], Optional[CardinalDirection], int],
        Tuple[Tile, Optional[CardinalDirection], int, Optional[TileObjectBand]],
    ]:
        """Capture only the immutable bands a command may touch."""
        band_snapshots: Dict[
            Tuple[Tuple[int, int], Optional[CardinalDirection], int],
            Tuple[Tile, Optional[CardinalDirection], int, Optional[TileObjectBand]],
        ] = {}
        for placement in placements:
            tile = self._tiles[placement.position]
            for position, direction, height in self._placement_band_keys(placement):
                if direction is None:
                    band = tile._center_object_bands.get(height)
                else:
                    band = tile._boundary_object_bands.get(direction, {}).get(height)
                band_snapshots.setdefault(
                    (position, direction, height),
                    (tile, direction, height, band),
                )
        return band_snapshots

    def _restore_object_mutation(
        self,
        object_uuid: UUID,
        previous: Optional[WorldObjectPlacement],
        band_snapshots: Mapping[
            Tuple[Tuple[int, int], Optional[CardinalDirection], int],
            Tuple[Tile, Optional[CardinalDirection], int, Optional[TileObjectBand]],
        ],
    ) -> None:
        """Restore a failed placement command and invalidate dependent caches."""
        for _key, (tile, direction, height, band) in band_snapshots.items():
            if direction is None:
                tile._replace_center_object_band(height, band)
            else:
                tile._replace_boundary_object_band(direction, height, band)
        if previous is None:
            self._object_placements.pop(object_uuid, None)
        else:
            self._object_placements[object_uuid] = previous
        self.invalidate_spatial_caches({"movement", "optical", "propagation"})

    def get_object_placement(self, object_uuid: UUID) -> Optional[WorldObjectPlacement]:
        """Return the immutable committed placement for one object."""
        return self._object_placements.get(object_uuid)

    def get_all_object_placements(self) -> Tuple[WorldObjectPlacement, ...]:
        """Return immutable placement rows in deterministic UUID order."""
        self._begin_operation_diagnostics("get_all_object_placements")
        placements = tuple(
            self._object_placements[object_uuid]
            for object_uuid in sorted(self._object_placements, key=str)
        )
        self._finish_operation_diagnostics(
            "get_all_object_placements",
            placement_iterator_rows_visited=len(placements),
        )
        return placements

    def rebuild_object_placements(
        self,
        serialized_placements: Iterable[WorldObjectPlacement | Mapping[str, object]],
    ) -> Tuple[WorldObjectPlacement, ...]:
        """Atomically rebuild Tile bands and reverse placements from cold values."""
        self._begin_operation_diagnostics("rebuild_object_placements")
        values: list[WorldObjectPlacement] = []
        seen_object_uuids: set[UUID] = set()
        provider_structures: Dict[UUID, Optional[BoundaryStructure]] = {}
        for raw_value in serialized_placements:
            placement = (
                raw_value
                if isinstance(raw_value, WorldObjectPlacement)
                else WorldObjectPlacement.model_validate(raw_value, strict=True)
            )
            if placement.object_uuid in seen_object_uuids:
                raise ValueError(
                    f"serialized object placements contain duplicate object {placement.object_uuid}",
                )
            seen_object_uuids.add(placement.object_uuid)
            tile = self._tiles.get(placement.position)
            if tile is None or tile.uuid != placement.tile_uuid:
                raise ValueError(
                    f"serialized placement {placement.object_uuid} does not identify its exact Tile",
                )
            provider = BaseBlock.get(placement.object_uuid)
            if provider is None:
                raise ValueError(
                    f"serialized placement {placement.object_uuid} has no registered provider",
                )
            spec = provider.get_world_placement_spec()
            # Resolve structural after-values only for boundary placements
            # before touching any live bands; center mechanics never enter an
            # ordered edge layer.
            if placement.kind is WorldPlacementKind.BOUNDARY:
                provider_structures[placement.object_uuid] = (
                    provider.get_boundary_structure()
                )
            if placement.kind is not spec.kind:
                raise ValueError("serialized placement kind differs from provider policy")
            if placement.occupies_bands is not spec.occupies_bands:
                raise ValueError("serialized placement occupancy differs from provider policy")
            if placement.top_height_steps - placement.base_height_steps != spec.vertical_extent_steps:
                raise ValueError("serialized placement extent differs from provider policy")
            if placement.kind is WorldPlacementKind.CENTER:
                if placement.boundary_direction is not None:
                    raise ValueError("serialized center placement defines a boundary side")
                if placement.base_height_steps != tile.height:
                    raise ValueError("serialized center placement is not support-relative")
            elif placement.boundary_direction is None:
                raise ValueError("serialized boundary placement is missing its boundary side")
            values.append(placement)

        staged_members: Dict[
            Tuple[Tuple[int, int], Optional[CardinalDirection], int],
            set[UUID],
        ] = {}
        staged_occupants: Dict[
            Tuple[Tuple[int, int], Optional[CardinalDirection], int],
            UUID,
        ] = {}

        def admit_band(
            placement: WorldObjectPlacement,
            position: Tuple[int, int],
            height: int,
            direction: Optional[CardinalDirection],
        ) -> None:
            key = (position, direction, height)
            members = staged_members.setdefault(key, set())
            occupants = staged_occupants
            members.add(placement.object_uuid)
            if placement.occupies_bands:
                incumbent = occupants.get(key)
                if incumbent is not None and incumbent != placement.object_uuid:
                    raise ValueError("serialized placement has an occupying band collision")
                occupants[key] = placement.object_uuid

        for placement in values:
            direction = placement.boundary_direction
            for height in self._placement_band_heights(placement):
                admit_band(placement, placement.position, height, direction)

        staged_bands: Dict[
            Tuple[Tuple[int, int], Optional[CardinalDirection], int],
            TileObjectBand,
        ] = {}
        for key, members in staged_members.items():
            staged_bands[key] = TileObjectBand(
                object_uuids=frozenset(members),
                occupant_uuid=staged_occupants.get(key),
            )

        new_placements = {placement.object_uuid: placement for placement in values}
        old_placements = dict(self._object_placements)
        for placement in old_placements.values():
            if placement.object_uuid in provider_structures:
                continue
            provider = BaseBlock.get(placement.object_uuid)
            if provider is None:
                raise ValueError(
                    f"live placement {placement.object_uuid} has no registered provider",
                )
            if placement.kind is WorldPlacementKind.BOUNDARY:
                provider_structures[placement.object_uuid] = (
                    provider.get_boundary_structure()
                )
        old_band_keys = {
            key
            for placement in old_placements.values()
            for key in self._placement_band_keys(placement)
        }
        new_band_keys = set(staged_bands)
        affected_band_keys = old_band_keys | new_band_keys
        affected_positions = {
            position
            for position, _direction, _height in affected_band_keys
        }
        changed_uuids = {
            object_uuid
            for object_uuid in set(old_placements) | set(new_placements)
            if old_placements.get(object_uuid) != new_placements.get(object_uuid)
        }
        topology_placements = tuple(
            placement
            for object_uuid, placement in old_placements.items()
            if object_uuid in changed_uuids
        ) + tuple(
            placement
            for object_uuid, placement in new_placements.items()
            if object_uuid in changed_uuids
        )
        before_boundary_views, _before_boundary_owners, before_boundary_endpoints = (
            self._capture_boundary_views(
                topology_placements,
                structure_overrides=provider_structures,
            )
        )
        optical_positions: set[Tuple[int, int]] = set()
        revision_channels: set[str] = set()
        for object_uuid in changed_uuids:
            provider = BaseBlock.get(object_uuid)
            if provider is None:
                continue
            old = old_placements.get(object_uuid)
            new = new_placements.get(object_uuid)
            positions = {
                placement.position
                for placement in (old, new)
                if placement is not None
            }
            if not any(
                placement is not None
                and placement.kind is WorldPlacementKind.CENTER
                for placement in (old, new)
            ):
                continue
            blocks_walking = provider.blocks_walking()
            blocks_propagation = provider.blocks_propagation()
            blocks_optics = provider.blocks_optics_at_center()
            # Resolve center provider mechanics before mutation; these values
            # are reused for center revision and light decisions below.
            if blocks_walking:
                revision_channels.add("movement")
            if blocks_propagation:
                revision_channels.add("propagation")
            if blocks_optics:
                revision_channels.add("optical")
                optical_positions.update(positions)

        band_snapshots: Dict[
            Tuple[Tuple[int, int], Optional[CardinalDirection], int],
            Optional[TileObjectBand],
        ] = {}
        for key in affected_band_keys:
            position, direction, height = key
            tile = self._tiles[position]
            if direction is None:
                band = tile._center_object_bands.get(height)
            else:
                band = tile._boundary_object_bands.get(direction, {}).get(height)
            band_snapshots[key] = band

        revision_names = (
            "_spatial_revision",
            "_optical_revision",
            "_movement_revision",
            "_light_revision",
            "_propagation_revision",
        )
        revision_snapshots = {
            name: getattr(self, name)
            for name in revision_names
        }
        light_source_snapshots: Dict[UUID, Dict[Tuple[int, int], LightLevel]] = {}
        light_tile_snapshots: Dict[
            Tuple[int, int],
            Tuple[Dict[UUID, LightLevel], Dict[UUID, LightLevel]],
        ] = {}
        events_enabled = self._events_enabled
        pending_event_count = len(self._pending_events)
        pending_committed_event_count = len(self._pending_committed_events)

        def restore_rebuild_state() -> None:
            for key, band in band_snapshots.items():
                position, direction, height = key
                tile = self._tiles[position]
                if direction is None:
                    tile._replace_center_object_band(height, band)
                else:
                    tile._replace_boundary_object_band(direction, height, band)
            self._object_placements = old_placements
            for name, value in revision_snapshots.items():
                setattr(self, name, value)
            self._fov_cache.clear()
            self._path_cache.clear()
            self._propagation_fov_cache.clear()
            self._propagation_transition_cache.clear()
            self._propagation_blocking_cache.clear()
            self._propagation_filter_cache.clear()
            for source_uuid, affected in light_source_snapshots.items():
                source = self._light_sources.get(source_uuid)
                if source is not None:
                    source.affected_tiles = dict(affected)
            for position, (illuminations, caps) in light_tile_snapshots.items():
                tile = self._tiles[position]
                tile._illuminations = dict(illuminations)
                tile._illumination_caps = dict(caps)

        self._events_enabled = False
        try:
            # The old reverse map is the removal authority. Only its old rows
            # and the staged new rows are touched; distant Tiles remain alone.
            bands_replaced = 0
            for key in affected_band_keys:
                position, direction, height = key
                tile = self._tiles[position]
                old_band = band_snapshots[key]
                band = staged_bands.get(key)
                if old_band == band:
                    continue
                if direction is None:
                    tile._replace_center_object_band(height, band)
                else:
                    tile._replace_boundary_object_band(direction, height, band)
                bands_replaced += 1
            self._object_placements = new_placements
            after_boundary_views, after_boundary_owners, after_boundary_endpoints = (
                self._capture_boundary_views(
                    topology_placements,
                    structure_overrides=provider_structures,
                )
            )
            boundary_channels = self._aggregate_boundary_changes(
                before_boundary_views,
                after_boundary_views,
            )
            revision_channels.update(boundary_channels)
            if WorldEdgeChannel.OPTICAL.value in boundary_channels:
                optical_positions.update(
                    before_boundary_endpoints | after_boundary_endpoints
                )
            self._bump_spatial_revisions(revision_channels)
            if optical_positions:
                for source_uuid, source in self._light_sources.items():
                    if not self._is_light_effectively_active(source):
                        continue
                    total_radius_tiles = (
                        source.bright_radius_feet + source.dim_radius_feet
                    ) / 5
                    if not any(
                        math.sqrt(
                            (position[0] - source.position[0]) ** 2
                            + (position[1] - source.position[1]) ** 2
                        ) <= total_radius_tiles
                        for position in optical_positions
                    ):
                        continue
                    light_source_snapshots[source_uuid] = dict(source.affected_tiles)
                    possible_positions = set(source.affected_tiles)
                    radius_tiles = max(
                        (source.bright_radius_feet + source.dim_radius_feet) // 5,
                        1,
                    )
                    possible_positions.update(
                        position
                        for position in circle_positions(source.position, radius_tiles)
                        if position in self._tiles
                    )
                    for position in possible_positions:
                        tile = self._tiles.get(position)
                        if tile is None:
                            continue
                        light_tile_snapshots[position] = (
                            dict(tile._illuminations),
                            dict(tile._illumination_caps),
                        )
            self.recompute_lights_at_positions(optical_positions)

            live_bands: Dict[
                Tuple[Tuple[int, int], Optional[CardinalDirection], int],
                TileObjectBand,
            ] = {}
            for key in affected_band_keys:
                position, direction, height = key
                tile = self._tiles[position]
                band = (
                    tile._center_object_bands.get(height)
                    if direction is None
                    else tile._boundary_object_bands.get(direction, {}).get(height)
                )
                if band is not None:
                    live_bands[key] = band
            self._assert_object_placement_bijection(
                new_placements,
                live_bands,
            )
            self._last_operation_diagnostics = GridMapOperationDiagnostics(
                operation="rebuild_object_placements",
                tiles_inspected=len(affected_positions),
                bands_inspected=len(affected_band_keys),
                bands_replaced=bands_replaced,
                placement_iterator_rows_visited=len(values),
            )
            return tuple(
                self._object_placements[uuid]
                for uuid in sorted(self._object_placements, key=str)
            )
        except Exception:
            restore_rebuild_state()
            self._last_operation_diagnostics = GridMapOperationDiagnostics(
                operation="rebuild_object_placements",
            )
            raise
        finally:
            self._events_enabled = events_enabled
            del self._pending_events[pending_event_count:]
            del self._pending_committed_events[pending_committed_event_count:]

    def _assert_object_placement_bijection(
        self,
        placements: Mapping[UUID, WorldObjectPlacement],
        bands: Mapping[
            Tuple[Tuple[int, int], Optional[CardinalDirection], int],
            TileObjectBand,
        ],
    ) -> None:
        """Prove every affected live band UUID has one placement."""
        forward_members: Dict[UUID, int] = defaultdict(int)
        for band in bands.values():
            for object_uuid in band.object_uuids:
                forward_members[object_uuid] += 1
        for object_uuid, placement in placements.items():
            expected_keys = self._placement_band_keys(placement)
            expected = len(expected_keys)
            for key in expected_keys:
                band = bands.get(key)
                if band is None or object_uuid not in band.object_uuids:
                    raise ValueError("rebuilt placement bands are not bijective with placements")
                if placement.occupies_bands and band.occupant_uuid != object_uuid:
                    raise ValueError("rebuilt occupying bands have the wrong occupant")
            if forward_members.get(object_uuid, 0) != expected:
                raise ValueError("rebuilt placement bands are not bijective with placements")
        extra = set(forward_members).difference(placements)
        if extra:
            raise ValueError("rebuilt bands contain an unplaced object")

    def get_object_position(self, object_uuid: UUID) -> Optional[Tuple[int, int]]:
        """Return an object's committed grid position, or None if unplaced."""
        placement = self.get_object_placement(object_uuid)
        return placement.position if placement is not None else None

    def get_center_objects_at(
        self,
        position: Tuple[int, int],
        height: Optional[int] = None,
    ) -> Set[UUID]:
        """Return object UUIDs indexed in center bands at one Tile."""
        self._begin_operation_diagnostics("get_center_objects_at")
        tile = self._tiles.get(position)
        if tile is None:
            self._finish_operation_diagnostics("get_center_objects_at", tiles_inspected=1)
            return set()
        bands = (
            ((height, tile._center_object_bands.get(height, TileObjectBand())),)
            if height is not None
            else tuple(tile._center_object_bands.items())
        )
        result = {
            object_uuid
            for _band_height, band in bands
            for object_uuid in band.object_uuids
        }
        self._finish_operation_diagnostics(
            "get_center_objects_at",
            tiles_inspected=1,
            bands_inspected=len(bands),
        )
        return result

    def get_boundary_objects_at(
        self,
        position: Tuple[int, int],
        direction: CardinalDirection,
        height: Optional[int] = None,
    ) -> Set[UUID]:
        """Return object UUIDs indexed on one Tile-relative boundary."""
        self._begin_operation_diagnostics("get_boundary_objects_at")
        tile = self._tiles.get(position)
        if tile is None:
            self._finish_operation_diagnostics("get_boundary_objects_at", tiles_inspected=1)
            return set()
        direction_bands = tile._boundary_object_bands.get(direction, {})
        bands = (
            ((height, direction_bands.get(height, TileObjectBand())),)
            if height is not None
            else tuple(direction_bands.items())
        )
        result = {
            object_uuid
            for _band_height, band in bands
            for object_uuid in band.object_uuids
        }
        self._finish_operation_diagnostics(
            "get_boundary_objects_at",
            tiles_inspected=1,
            bands_inspected=len(bands),
        )
        return result

    def get_objects_at(self, position: Tuple[int, int]) -> Set[UUID]:
        """Return all center and boundary object UUIDs anchored at a Tile."""
        self._begin_operation_diagnostics("get_objects_at")
        tile = self._tiles.get(position)
        if tile is None:
            self._finish_operation_diagnostics("get_objects_at", tiles_inspected=1)
            return set()
        result = {
            object_uuid
            for band in tile._center_object_bands.values()
            for object_uuid in band.object_uuids
        }
        result.update(
            object_uuid
            for direction_bands in tile._boundary_object_bands.values()
            for band in direction_bands.values()
            for object_uuid in band.object_uuids
        )
        self._finish_operation_diagnostics(
            "get_objects_at",
            tiles_inspected=1,
            bands_inspected=(
                len(tile._center_object_bands)
                + sum(len(bands) for bands in tile._boundary_object_bands.values())
            ),
        )
        return result

    def _emit_object_state_event(
        self,
        object_uuid: UUID,
        placement: WorldObjectPlacement,
        *,
        object_name: Optional[str],
        blocks_optics: bool,
        blocks_propagation: bool,
        blocks_walking: bool,
        previous_placement: Optional[WorldObjectPlacement] = None,
        parent_event: Optional[UUID] = None,
        object_boundary_structure: Optional[BoundaryStructure] = None,
        revision_channels: Set[str],
        senses_hint: SensesUpdateHint,
    ) -> None:
        self._bump_spatial_revisions(revision_channels)
        if self._events_enabled:
            self._fire_spatial_event(SpatialChangeEvent.object_placed(
                placement.position,
                object_uuid,
                parent_event=parent_event,
                blocks_optics=blocks_optics,
                blocks_propagation=blocks_propagation,
                blocks_walking=blocks_walking,
                object_name=object_name,
                placement=placement,
                previous_placement=previous_placement,
                object_boundary_structure=object_boundary_structure,
                senses_hint=senses_hint,
            ))

    def place_object(
        self,
        object_uuid: UUID,
        position: Tuple[int, int],
        *,
        boundary_direction: Optional[CardinalDirection] = None,
        base_height_steps: Optional[int] = None,
        orientation: Optional[CardinalDirection] = None,
        parent_event: Optional[UUID] = None,
    ) -> WorldObjectPlacement:
        """Atomically admit an unplaced object at one resolved placement."""
        self._begin_operation_diagnostics("place_object")
        current = self.get_object_placement(object_uuid)
        candidate = self.validate_object_placement(
            object_uuid,
            position,
            boundary_direction=boundary_direction,
            orientation=orientation,
            base_height_steps=base_height_steps,
        )
        tiles_inspected, bands_inspected = self._placement_work_counts((candidate,))
        if current is not None:
            if current == candidate:
                self._finish_operation_diagnostics(
                    "place_object",
                    tiles_inspected=tiles_inspected,
                    bands_inspected=bands_inspected,
                )
                return current
            raise ValueError(
                f"object {object_uuid} is already placed; use move_object or orient_object",
            )
        obj = BaseBlock.get(object_uuid)
        object_boundary_structure = None
        structure_overrides: Dict[UUID, Optional[BoundaryStructure]] = {}
        if candidate.kind is WorldPlacementKind.BOUNDARY and obj is not None:
            object_boundary_structure = obj.get_boundary_structure()
            structure_overrides[object_uuid] = object_boundary_structure
        blocks_optics = obj.blocks_optics_at_center() if obj else False
        blocks_propagation = obj.blocks_propagation() if obj else False
        blocks_walking = obj.blocks_walking() if obj else False
        object_name = obj.name if obj else None
        before_views, before_owners, before_endpoints = self._capture_boundary_views(
            (candidate,),
            structure_overrides=structure_overrides,
        )
        band_snapshots = self._snapshot_object_mutation((candidate,))
        try:
            replacements = self._replace_placement_bands(candidate, add=True)
            self._object_placements[object_uuid] = candidate
        except Exception:
            self._restore_object_mutation(
                object_uuid,
                None,
                band_snapshots,
            )
            raise
        try:
            after_views, after_owners, after_endpoints = self._capture_boundary_views(
                (candidate,),
                structure_overrides=structure_overrides,
            )
        except Exception:
            self._restore_object_mutation(
                object_uuid,
                None,
                band_snapshots,
            )
            raise
        revision_channels = self._aggregate_boundary_changes(
            before_views,
            after_views,
        )
        if candidate.kind is WorldPlacementKind.CENTER:
            revision_channels.update({
                channel
                for channel, blocked in (
                    (WorldEdgeChannel.OPTICAL.value, blocks_optics),
                    (WorldEdgeChannel.PROPAGATION.value, blocks_propagation),
                    (WorldEdgeChannel.MOVEMENT.value, blocks_walking),
                )
                if blocked
            })
        senses_hint = self._object_senses_hint(
            object_uuid,
            candidate.position,
            changed_channels=revision_channels,
            owners=before_owners | after_owners,
            endpoints=before_endpoints | after_endpoints,
            placed=True,
        )
        self._last_operation_diagnostics = GridMapOperationDiagnostics(
            operation="place_object",
            tiles_inspected=tiles_inspected,
            bands_inspected=bands_inspected,
            bands_replaced=replacements,
        )
        self._emit_object_state_event(
            object_uuid,
            candidate,
            object_name=object_name,
            blocks_optics=blocks_optics,
            blocks_propagation=blocks_propagation,
            blocks_walking=blocks_walking,
            parent_event=parent_event,
            object_boundary_structure=object_boundary_structure,
            revision_channels=revision_channels,
            senses_hint=senses_hint,
        )
        self._last_operation_diagnostics = GridMapOperationDiagnostics(
            operation="place_object",
            tiles_inspected=tiles_inspected,
            bands_inspected=bands_inspected,
            bands_replaced=replacements,
        )
        return candidate

    def move_object(
        self,
        object_uuid: UUID,
        position: Tuple[int, int],
        *,
        boundary_direction: Optional[CardinalDirection] = None,
        base_height_steps: Optional[int] = None,
        orientation: Optional[CardinalDirection] = None,
        parent_event: Optional[UUID] = None,
    ) -> WorldObjectPlacement:
        """Atomically move one committed object with departure then arrival facts."""
        self._begin_operation_diagnostics("move_object")
        if not self._events_enabled:
            raise RuntimeError(
                "move_object requires enabled spatial event publication"
            )
        previous = self.get_object_placement(object_uuid)
        if previous is None:
            raise ValueError(f"object {object_uuid} is not placed")
        candidate = self.validate_object_placement(
            object_uuid,
            position,
            boundary_direction=boundary_direction,
            orientation=orientation,
            base_height_steps=base_height_steps,
        )
        tiles_inspected, bands_inspected = self._placement_work_counts(
            (previous, candidate),
        )
        if candidate == previous:
            self._finish_operation_diagnostics(
                "move_object",
                tiles_inspected=tiles_inspected,
                bands_inspected=bands_inspected,
            )
            return previous
        obj = BaseBlock.get(object_uuid)
        object_boundary_structure = None
        structure_overrides: Dict[UUID, Optional[BoundaryStructure]] = {}
        if (
            (previous.kind is WorldPlacementKind.BOUNDARY
             or candidate.kind is WorldPlacementKind.BOUNDARY)
            and obj is not None
        ):
            object_boundary_structure = obj.get_boundary_structure()
            structure_overrides[object_uuid] = object_boundary_structure
        blocks_optics = obj.blocks_optics_at_center() if obj else False
        blocks_propagation = obj.blocks_propagation() if obj else False
        blocks_walking = obj.blocks_walking() if obj else False
        object_name = obj.name if obj else None
        before_views, before_owners, before_endpoints = self._capture_boundary_views(
            (previous, candidate),
            structure_overrides=structure_overrides,
        )
        band_snapshots = self._snapshot_object_mutation(
            (previous, candidate),
        )
        try:
            old_replacements = self._replace_placement_bands(previous, add=False)
            self._object_placements.pop(object_uuid, None)
        except Exception:
            self._restore_object_mutation(
                object_uuid,
                previous,
                band_snapshots,
            )
            raise
        try:
            absent_views, absent_owners, absent_endpoints = self._capture_boundary_views(
                (previous, candidate),
                structure_overrides=structure_overrides,
            )
        except Exception:
            self._restore_object_mutation(
                object_uuid,
                previous,
                band_snapshots,
            )
            raise
        departure_channels = self._aggregate_boundary_changes(
            before_views,
            absent_views,
        )
        if previous.kind is WorldPlacementKind.CENTER:
            departure_channels.update({
                channel
                for channel, blocked in (
                    (WorldEdgeChannel.OPTICAL.value, blocks_optics),
                    (WorldEdgeChannel.PROPAGATION.value, blocks_propagation),
                    (WorldEdgeChannel.MOVEMENT.value, blocks_walking),
                )
                if blocked
            })
        departure_hint = self._object_senses_hint(
            object_uuid,
            previous.position,
            changed_channels=departure_channels,
            owners=before_owners | absent_owners,
            endpoints=before_endpoints | absent_endpoints,
            removed=True,
        )
        self._bump_spatial_revisions(departure_channels)
        self._last_operation_diagnostics = GridMapOperationDiagnostics(
            operation="move_object",
            tiles_inspected=tiles_inspected,
            bands_inspected=bands_inspected,
            bands_replaced=old_replacements,
        )
        self._fire_spatial_event(SpatialChangeEvent.object_removed(
            previous.position,
            object_uuid,
            parent_event=parent_event,
            blocks_optics=blocks_optics,
            blocks_propagation=blocks_propagation,
            blocks_walking=blocks_walking,
            previous_placement=previous,
            new_position=candidate.position,
            object_boundary_structure=None,
            senses_hint=departure_hint,
        ))

        new_replacements = self._replace_placement_bands(candidate, add=True)
        self._object_placements[object_uuid] = candidate
        after_views, after_owners, after_endpoints = self._capture_boundary_views(
            (previous, candidate),
            structure_overrides=structure_overrides,
        )
        arrival_channels = self._aggregate_boundary_changes(
            absent_views,
            after_views,
        )
        if candidate.kind is WorldPlacementKind.CENTER:
            arrival_channels.update({
                channel
                for channel, blocked in (
                    (WorldEdgeChannel.OPTICAL.value, blocks_optics),
                    (WorldEdgeChannel.PROPAGATION.value, blocks_propagation),
                    (WorldEdgeChannel.MOVEMENT.value, blocks_walking),
                )
                if blocked
            })
        arrival_hint = self._object_senses_hint(
            object_uuid,
            candidate.position,
            changed_channels=arrival_channels,
            owners=absent_owners | after_owners,
            endpoints=absent_endpoints | after_endpoints,
            placed=True,
        )
        self._bump_spatial_revisions(arrival_channels)
        self._fire_spatial_event(SpatialChangeEvent.object_placed(
            candidate.position,
            object_uuid,
            parent_event=parent_event,
            blocks_optics=blocks_optics,
            blocks_propagation=blocks_propagation,
            blocks_walking=blocks_walking,
            object_name=object_name,
            placement=candidate,
            previous_placement=previous,
            object_boundary_structure=object_boundary_structure,
            senses_hint=arrival_hint,
        ))
        self._last_operation_diagnostics = GridMapOperationDiagnostics(
            operation="move_object",
            tiles_inspected=tiles_inspected,
            bands_inspected=bands_inspected,
            bands_replaced=old_replacements + new_replacements,
        )
        return candidate

    def orient_object(
        self,
        object_uuid: UUID,
        orientation: Optional[CardinalDirection],
        *,
        parent_event: Optional[UUID] = None,
    ) -> WorldObjectPlacement:
        """Atomically change one object's orientation in place."""
        self._begin_operation_diagnostics("orient_object")
        previous = self.get_object_placement(object_uuid)
        if previous is None:
            raise ValueError(f"object {object_uuid} is not placed")
        candidate = self._resolve_object_placement(
            object_uuid,
            previous.position,
            previous.boundary_direction,
            orientation,
            previous.base_height_steps,
        )
        self._validate_placement_collision(candidate)
        tiles_inspected, bands_inspected = self._placement_work_counts((candidate,))
        if candidate == previous:
            self._finish_operation_diagnostics(
                "orient_object",
                tiles_inspected=tiles_inspected,
                bands_inspected=bands_inspected,
            )
            return previous
        obj = BaseBlock.get(object_uuid)
        object_boundary_structure = None
        structure_overrides: Dict[UUID, Optional[BoundaryStructure]] = {}
        if previous.kind is WorldPlacementKind.BOUNDARY and obj is not None:
            object_boundary_structure = obj.get_boundary_structure()
            structure_overrides[object_uuid] = object_boundary_structure
        blocks_optics = obj.blocks_optics_at_center() if obj else False
        blocks_propagation = obj.blocks_propagation() if obj else False
        blocks_walking = obj.blocks_walking() if obj else False
        object_name = obj.name if obj else None
        before_views, before_owners, before_endpoints = self._capture_boundary_views(
            (previous,),
            structure_overrides=structure_overrides,
        )
        band_snapshots = self._snapshot_object_mutation((previous,))
        try:
            self._object_placements[object_uuid] = candidate
        except Exception:
            self._restore_object_mutation(
                object_uuid,
                previous,
                band_snapshots,
            )
            raise
        try:
            after_views, after_owners, after_endpoints = self._capture_boundary_views(
                (candidate,),
                structure_overrides=structure_overrides,
            )
        except Exception:
            self._restore_object_mutation(
                object_uuid,
                previous,
                band_snapshots,
            )
            raise
        senses_hint = self._object_senses_hint(
            object_uuid,
            candidate.position,
            changed_channels=self._aggregate_boundary_changes(
                before_views,
                after_views,
            ),
            owners=before_owners | after_owners,
            endpoints=before_endpoints | after_endpoints,
        )
        if self._events_enabled:
            self._fire_spatial_event(SpatialChangeEvent.object_changed(
                candidate.position,
                object_uuid,
                parent_event=parent_event,
                placement=candidate,
                previous_placement=previous,
                object_name=object_name,
                object_blocks_movement=blocks_walking,
                object_blocks_optics=blocks_optics,
                object_blocks_propagation=blocks_propagation,
                object_boundary_structure=object_boundary_structure,
                senses_hint=senses_hint,
            ))
        self._finish_operation_diagnostics(
            "orient_object",
            tiles_inspected=tiles_inspected,
            bands_inspected=bands_inspected,
        )
        return candidate

    def remove_object(
        self,
        object_uuid: UUID,
        parent_event: Optional[UUID] = None,
    ) -> None:
        """Terminally remove one committed placement and publish its prior fact."""
        self._begin_operation_diagnostics("remove_object")
        previous = self._object_placements.get(object_uuid)
        if previous is None:
            self._finish_operation_diagnostics("remove_object")
            return
        obj = BaseBlock.get(object_uuid)
        object_boundary_structure = None
        structure_overrides: Dict[UUID, Optional[BoundaryStructure]] = {}
        if previous.kind is WorldPlacementKind.BOUNDARY and obj is not None:
            object_boundary_structure = obj.get_boundary_structure()
            structure_overrides[object_uuid] = object_boundary_structure
        before_views, before_owners, before_endpoints = self._capture_boundary_views(
            (previous,),
            structure_overrides=structure_overrides,
        )
        band_snapshots = self._snapshot_object_mutation((previous,))
        self._object_placements.pop(object_uuid, None)
        replacements = self._replace_placement_bands(previous, add=False)
        try:
            after_views, after_owners, after_endpoints = self._capture_boundary_views(
                (previous,),
                structure_overrides=structure_overrides,
            )
        except Exception:
            self._restore_object_mutation(
                object_uuid,
                previous,
                band_snapshots,
            )
            raise
        blocks_optics = obj.blocks_optics_at_center() if obj else False
        blocks_propagation = obj.blocks_propagation() if obj else False
        blocks_walking = obj.blocks_walking() if obj else False
        revision_channels = self._aggregate_boundary_changes(
            before_views,
            after_views,
        )
        if previous.kind is WorldPlacementKind.CENTER:
            revision_channels.update({
                channel
                for channel, blocked in (
                    (WorldEdgeChannel.OPTICAL.value, blocks_optics),
                    (WorldEdgeChannel.PROPAGATION.value, blocks_propagation),
                    (WorldEdgeChannel.MOVEMENT.value, blocks_walking),
                )
                if blocked
            })
        self._bump_spatial_revisions(revision_channels)
        senses_hint = self._object_senses_hint(
            object_uuid,
            previous.position,
            changed_channels=revision_channels,
            owners=before_owners | after_owners,
            endpoints=before_endpoints | after_endpoints,
            removed=True,
        )
        if obj is not None:
            obj.on_grid_object_removed(previous.position, parent_event=parent_event)
        self._last_operation_diagnostics = GridMapOperationDiagnostics(
            operation="remove_object",
            tiles_inspected=1,
            bands_inspected=len(self._placement_band_keys(previous)),
            bands_replaced=replacements,
        )
        if self._events_enabled:
            self._fire_spatial_event(SpatialChangeEvent.object_removed(
                previous.position,
                object_uuid,
                parent_event=parent_event,
                blocks_optics=blocks_optics,
                blocks_propagation=blocks_propagation,
                blocks_walking=blocks_walking,
                previous_placement=previous,
                object_boundary_structure=None,
                senses_hint=senses_hint,
            ))
        self._last_operation_diagnostics = GridMapOperationDiagnostics(
            operation="remove_object",
            tiles_inspected=1,
            bands_inspected=len(self._placement_band_keys(previous)),
            bands_replaced=replacements,
        )

    def update_object_boundary_structure(
        self,
        object_uuid: UUID,
        structure: BoundaryStructure,
        *,
        previous_structure: Optional[BoundaryStructure] = None,
        parent_event: Optional[UUID] = None,
    ) -> None:
        """Publish one committed current-structure change without band mutation."""
        placement = self._object_placements.get(object_uuid)
        if placement is None:
            return
        provider = BaseBlock.get(object_uuid)
        if provider is None or placement.kind is not WorldPlacementKind.BOUNDARY:
            raise ValueError("boundary structure requires a placed boundary provider")
        structure_overrides: Dict[UUID, Optional[BoundaryStructure]] = {
            object_uuid: previous_structure,
        }
        before_views, before_owners, before_endpoints = self._capture_boundary_views(
            (placement,),
            structure_overrides=structure_overrides,
        )
        structure_overrides[object_uuid] = structure
        after_views, after_owners, after_endpoints = self._capture_boundary_views(
            (placement,),
            structure_overrides=structure_overrides,
        )
        changed_channel_names = self._aggregate_boundary_changes(
            before_views,
            after_views,
        )
        self._bump_spatial_revisions(changed_channel_names)
        senses_hint = self._object_senses_hint(
            object_uuid,
            placement.position,
            changed_channels=changed_channel_names,
            owners=before_owners | after_owners,
            endpoints=before_endpoints | after_endpoints,
        )
        if self._events_enabled:
            self._fire_spatial_event(
                SpatialChangeEvent.object_changed(
                    placement.position,
                    object_uuid,
                    parent_event=parent_event,
                    placement=placement,
                    previous_placement=placement,
                    object_name=provider.name,
                    blocks_walking_changed=WorldEdgeChannel.MOVEMENT.value in changed_channel_names,
                    blocks_optics_changed=WorldEdgeChannel.OPTICAL.value in changed_channel_names,
                    blocks_propagation_changed=WorldEdgeChannel.PROPAGATION.value in changed_channel_names,
                    object_blocks_movement=provider.blocks_walking(),
                    object_blocks_optics=provider.blocks_optics_at_center(),
                    object_blocks_propagation=provider.blocks_propagation(),
                    object_is_open=provider.get_spatial_open_state(),
                    object_boundary_structure=structure,
                    senses_hint=senses_hint,
                )
            )

    def get_objects_with_conditions(self) -> List[BaseBlock]:
        """Get placed objects with active conditions (for environment step)."""
        result: List[BaseBlock] = []
        for placement in self.get_all_object_placements():
            block = BaseBlock.get(placement.object_uuid)
            if block is not None and block.active_conditions:
                result.append(block)
        return result

    def _transition_clear(self, start: Tuple[int, int], end: Tuple[int, int],
                          channel: str,
                          requester_uuid: Optional[UUID] = None) -> bool:
        path = supercover_line(start, end)
        if not path:
            return False
        for index in range(1, len(path)):
            prev = path[index - 1]
            current = path[index]
            if channel == "optical":
                if not self.can_optical_transition(prev, current):
                    return False
                blocks_cell = self.is_blocking_optics(current[0], current[1])
            else:
                if not self.can_propagate_transition(prev, current, requester_uuid):
                    return False
                blocks_cell = self.is_blocking_propagation(current[0], current[1])

            if index < len(path) - 1 and blocks_cell:
                return False
        return True

    def raycast_clear(self, start: Tuple[int, int], end: Tuple[int, int],
                      channel: str = "optical",
                      requester_uuid: Optional[UUID] = None) -> bool:
        """Public transition-aware line check for optics or propagation."""
        if channel not in {"optical", "propagation"}:
            raise ValueError(f"Unsupported raycast channel: {channel}")
        return self._transition_clear(start, end, channel, requester_uuid)

    def get_optical_obscurements_on_route(
        self,
        start: Tuple[int, int],
        end: Tuple[int, int],
    ) -> Set[OpticalObscurement]:
        """Return conditional optical obscurements intersecting one clear ray."""
        obscurements: Set[OpticalObscurement] = set()
        for position in supercover_line(start, end):
            obscurements.update(self.get_optical_obscurements_at(position))
        return obscurements

    def _compute_directional_fov(self, origin: Tuple[int, int], max_distance: Optional[float],
                                 channel: str,
                                 requester_uuid: Optional[UUID] = None) -> List[Tuple[int, int]]:
        if origin not in self._tiles:
            return []
        if self._bounds_dirty:
            self._update_bounds()

        radius = max_distance if max_distance is not None else max(self.width, self.height)
        radius_squared = radius * radius if max_distance is not None else None
        visible_positions: List[Tuple[int, int]] = []
        min_x = max(self._min_x, math.floor(origin[0] - radius))
        max_x = min(self._max_x, math.ceil(origin[0] + radius))
        min_y = max(self._min_y, math.floor(origin[1] - radius))
        max_y = min(self._max_y, math.ceil(origin[1] + radius))

        line_cache: Dict[Tuple[int, int], Tuple[Tuple[int, int], ...]] = {}
        transition_cache: Dict[Tuple[Tuple[int, int], Tuple[int, int]], bool] = {}
        blocking_cache: Dict[Tuple[int, int], bool] = {}
        def get_line_offsets(end: Tuple[int, int]) -> Tuple[Tuple[int, int], ...]:
            key = (end[0] - origin[0], end[1] - origin[1])
            cached = line_cache.get(key)
            if cached is not None:
                return cached
            path = supercover_line_offsets(key)
            line_cache[key] = path
            return path

        def transition_allows(prev: Tuple[int, int], current: Tuple[int, int]) -> bool:
            key = (prev, current)
            cached = transition_cache.get(key)
            if cached is not None:
                return cached
            if channel == "optical":
                allowed = self.can_optical_transition(prev, current)
            else:
                allowed = self.can_propagate_transition(prev, current, requester_uuid)
            transition_cache[key] = allowed
            return allowed

        def blocks_cell(position: Tuple[int, int]) -> bool:
            cached = blocking_cache.get(position)
            if cached is not None:
                return cached
            if channel == "optical":
                blocked = self.is_blocking_optics(position[0], position[1])
            else:
                blocked = self.is_blocking_propagation(position[0], position[1])
            blocking_cache[position] = blocked
            return blocked

        def transition_clear(start: Tuple[int, int], end: Tuple[int, int]) -> bool:
            path = get_line_offsets(end)
            if not path:
                return False
            origin_x, origin_y = start
            prev = start
            for index in range(1, len(path)):
                offset_x, offset_y = path[index]
                current = (origin_x + offset_x, origin_y + offset_y)
                if not transition_allows(prev, current):
                    return False
                if index < len(path) - 1 and blocks_cell(current):
                    return False
                prev = current
            return True

        for x in range(min_x, max_x + 1):
            for y in range(min_y, max_y + 1):
                pos = (x, y)
                if pos not in self._tiles:
                    continue
                if max_distance is not None:
                    dx = x - origin[0]
                    dy = y - origin[1]
                    if radius_squared is not None and dx * dx + dy * dy > radius_squared:
                        continue
                if pos == origin or transition_clear(origin, pos):
                    visible_positions.append(pos)
        return visible_positions

    def compute_fov(
        self,
        origin: Tuple[int, int],
        max_distance: Optional[float] = None,
    ) -> List[Tuple[int, int]]:
        """
        Compute field of view from a position using shadowcasting.

        Args:
            origin: Position to compute FOV from
            max_distance: Maximum view distance
        Returns list of visible positions.
        """
        cache_key = (
            origin,
            max_distance,
            self._optical_revision,
        )
        cached = self._fov_cache.get(cache_key)
        if cached is not None:
            return list(cached)
        if max_distance is not None:
            supersets = [
                (cached_distance, positions)
                for (
                    cached_origin,
                    cached_distance,
                    cached_revision,
                ), positions in tuple(self._fov_cache.items())
                if cached_origin == origin
                and cached_revision == self._optical_revision
                and (cached_distance is None or cached_distance >= max_distance)
            ]
            if supersets:
                _, superset = min(
                    supersets,
                    key=lambda item: math.inf if item[0] is None else item[0],
                )
                radius_squared = max_distance * max_distance
                cached = [
                    position
                    for position in superset
                    if (
                        (position[0] - origin[0]) ** 2
                        + (position[1] - origin[1]) ** 2
                    ) <= radius_squared
                ]
                self._fov_cache[cache_key] = list(cached)
                return list(cached)

        visible_positions = self._compute_directional_fov(origin, max_distance, "optical")
        self._fov_cache[cache_key] = list(visible_positions)
        return list(visible_positions)

    def compute_paths(self, start: Tuple[int, int], max_distance: Optional[int] = None,
                      requesting_entity_uuid: Optional[UUID] = None,
                      movement_mode: MovementMode = MovementMode.WALKING,
                      walk_in_danger: bool = True,
                      subjective: bool = False,
                      collision_blocked: Optional[Set[Tuple[int, int]]] = None,
                      directional_collision_blocked: Optional[Set[Tuple[Tuple[int, int], str]]] = None,
                      ignore_difficult_terrain: bool = False
                      ) -> Tuple[Dict[Tuple[int, int], int], Dict[Tuple[int, int], List[Tuple[int, int]]]]:
        """Compute all reachable positions and paths from start using Dijkstra.

        Args:
            start: Starting position.
            max_distance: Maximum distance to compute paths for, in movement cost units.
            requesting_entity_uuid: If provided, treats cells occupied by OTHER entities as blocked.
                The requesting entity's own position is always walkable.
            movement_mode: Movement mode used for terrain costs.
            walk_in_danger: Whether hazardous positions remain walkable.
            subjective: Whether imperceivable blockers are ignored.
            collision_blocked: Positions remembered as blocked by collision.
            directional_collision_blocked: Directional transitions remembered as blocked by collision.
            ignore_difficult_terrain: Whether costs above base movement are capped at 1.

        Returns:
            `(distances, paths)` where distances account for terrain costs.
        """
        self._begin_operation_diagnostics("compute_paths")
        path_edge_consultations: Set[
            Tuple[Tuple[int, int], Tuple[int, int]]
        ] = set()
        if self._bounds_dirty:
            self._update_bounds()

        cache_key = (
            start,
            max_distance,
            requesting_entity_uuid,
            movement_mode,
            walk_in_danger,
            subjective,
            self._movement_revision,
            self._occupancy_revision,
            ignore_difficult_terrain,
            self._path_requester_perception_signature(requesting_entity_uuid, subjective),
            tuple(sorted(collision_blocked or ())),
            tuple(sorted(directional_collision_blocked or ())),
            self._min_x,
            self._min_y,
            self._max_x,
            self._max_y,
        )
        cached = self._path_cache.get(cache_key)
        if cached is not None:
            self._path_cache.move_to_end(cache_key)
            cached_distances, cached_paths = cached
            self._finish_operation_diagnostics(
                "compute_paths",
                path_edge_queries=0,
            )
            return (
                dict(cached_distances),
                {position: list(path) for position, path in cached_paths.items()},
            )

        grid_width = self.width
        grid_height = self.height
        transition_side_cache: Dict[
            Tuple[Tuple[int, int], Tuple[int, int]],
            bool,
        ] = {}

        if requesting_entity_uuid is not None:
            def raw_walkable_check(x: int, y: int) -> bool:
                return self.is_walkable_for(x, y, requesting_entity_uuid, movement_mode,
                                            walk_in_danger, subjective, collision_blocked)
        else:
            def raw_walkable_check(x: int, y: int) -> bool:
                return self.is_walkable(x, y, movement_mode)

        def raw_get_edge_cost(
            from_pos: Tuple[int, int],
            to_pos: Tuple[int, int],
        ) -> float:
            return self.movement_edge_cost_units(
                from_pos,
                to_pos,
                movement_mode,
                ignore_difficult_terrain=ignore_difficult_terrain,
            )

        def raw_can_enter_tile(from_pos: Tuple[int, int], to_pos: Tuple[int, int]) -> bool:
            return self.can_transition(
                from_pos, to_pos, requesting_entity_uuid, movement_mode,
                walk_in_danger, subjective, collision_blocked,
                directional_collision_blocked=directional_collision_blocked,
                side_cache=transition_side_cache,
                movement_cell_cache=walkable_cache,
            )

        walkable_cache: Dict[Tuple[int, int], bool] = {}
        edge_cost_cache: Dict[
            Tuple[Tuple[int, int], Tuple[int, int]],
            float,
        ] = {}
        transition_cache: Dict[Tuple[Tuple[int, int], Tuple[int, int]], bool] = {}

        def cached_walkable_check(x: int, y: int) -> bool:
            key = (x, y)
            cached = walkable_cache.get(key)
            if cached is not None:
                return cached
            value = raw_walkable_check(x, y)
            walkable_cache[key] = value
            return value

        def cached_get_edge_cost(
            from_pos: Tuple[int, int],
            to_pos: Tuple[int, int],
        ) -> float:
            key = (from_pos, to_pos)
            cached = edge_cost_cache.get(key)
            if cached is not None:
                return cached
            path_edge_consultations.add(key)
            value = raw_get_edge_cost(from_pos, to_pos)
            edge_cost_cache[key] = value
            return value

        def cached_can_enter_tile(from_pos: Tuple[int, int], to_pos: Tuple[int, int]) -> bool:
            key = (from_pos, to_pos)
            cached = transition_cache.get(key)
            if cached is not None:
                return cached
            path_edge_consultations.add(key)
            value = raw_can_enter_tile(from_pos, to_pos)
            transition_cache[key] = value
            return value

        walkable_check = cached_walkable_check
        get_edge_cost = cached_get_edge_cost
        can_enter_tile = cached_can_enter_tile

        start_tile = self.get_tile(*start)
        if (
            start_tile is None
            or start_tile.get_movement_cost(movement_mode) <= 0
        ):
            sentinel_result = ({start: 0}, {start: [start]})
            self._path_cache[cache_key] = (
                dict(sentinel_result[0]),
                {
                    position: tuple(path)
                    for position, path in sentinel_result[1].items()
                },
            )
            if len(self._path_cache) > 128:
                self._path_cache.popitem(last=False)
            self._finish_operation_diagnostics(
                "compute_paths",
                path_edge_queries=len(path_edge_consultations),
            )
            return sentinel_result

        result = dijkstra(
            start,
            walkable_check,
            grid_width,
            grid_height,
            diagonal=True,
            max_distance=max_distance,
            edge_cost_func=get_edge_cost,
            can_enter=can_enter_tile,
            min_x=self._min_x,
            min_y=self._min_y,
        )
        distances, paths = result
        self._path_cache[cache_key] = (
            dict(distances),
            {position: tuple(path) for position, path in paths.items()},
        )
        if len(self._path_cache) > 128:
            self._path_cache.popitem(last=False)
        self._finish_operation_diagnostics(
            "compute_paths",
            path_edge_queries=len(path_edge_consultations),
        )
        return result

    def get_path(self, start: Tuple[int, int], end: Tuple[int, int],
                 max_distance: Optional[int] = None,
                 requesting_entity_uuid: Optional[UUID] = None) -> Optional[List[Tuple[int, int]]]:
        """Get path from start to end, or None if no path exists."""
        _, paths = self.compute_paths(start, max_distance, requesting_entity_uuid)
        return paths.get(end)

    def get_distance(self, start: Tuple[int, int], end: Tuple[int, int],
                     requesting_entity_uuid: Optional[UUID] = None) -> Optional[int]:
        """Get walking distance from start to end, or None if unreachable."""
        distances, _ = self.compute_paths(start, requesting_entity_uuid=requesting_entity_uuid)
        return distances.get(end)

    def set_tile_base_light(
        self,
        position: Tuple[int, int],
        level: LightLevel,
        *,
        parent_event: Optional[UUID] = None,
    ) -> bool:
        """Set one Tile's objective base illumination through GridMap authority."""
        tile = self._tiles.get(position)
        if tile is None:
            raise ValueError(f"cannot set light on missing tile {position}")
        old_level = tile.resolved_light_level
        tile.default_light = level
        if tile.resolved_light_level == old_level:
            return False
        self._fire_light_batch_events([position], parent_event=parent_event)
        return True

    def apply_tile_light_modifier(
        self,
        source_uuid: UUID,
        positions: Set[Tuple[int, int]],
        level: LightLevel,
        *,
        cap: bool,
    ) -> Tuple[Set[Tuple[int, int]], Set[Tuple[int, int]]]:
        """Install one source-owned contribution without publishing its fact."""
        changed_positions: Set[Tuple[int, int]] = set()
        applied_positions: Set[Tuple[int, int]] = set()
        for position in positions:
            tile = self._tiles.get(position)
            if tile is None:
                continue
            applied_positions.add(position)
            changed = (
                tile._add_illumination_cap(source_uuid, level)
                if cap
                else tile._add_illumination(source_uuid, level)
            )
            if changed:
                changed_positions.add(position)
        return applied_positions, changed_positions

    def remove_tile_light_modifier(
        self,
        source_uuid: UUID,
        positions: Set[Tuple[int, int]],
    ) -> Tuple[Set[Tuple[int, int]], Set[Tuple[int, int]]]:
        """Remove one source-owned contribution without publishing its fact."""
        changed_positions: Set[Tuple[int, int]] = set()
        removed_positions: Set[Tuple[int, int]] = set()
        for position in positions:
            tile = self._tiles.get(position)
            if tile is None:
                continue
            removed_positions.add(position)
            if tile._remove_light_modifier(source_uuid):
                changed_positions.add(position)
        return removed_positions, changed_positions

    def publish_light_changes(
        self,
        changed_positions: Set[Tuple[int, int]],
        *,
        parent_event: Optional[UUID] = None,
    ) -> None:
        """Publish one objective light fact after its complete domain commit."""
        self._fire_light_batch_events(
            sorted(changed_positions),
            parent_event=parent_event,
        )

    def add_light_source(self, position: Tuple[int, int], bright_radius_feet: int,
                         dim_radius_feet: int, anchor_uuid: Optional[UUID] = None,
                         very_bright_radius_feet: int = 0,
                         parent_event: Optional[UUID] = None) -> UUID:
        """Add a light source at a position.

        Computes illuminated area via FOV from position.
        Very bright radius -> VERY_BRIGHT, bright annulus -> BRIGHT_LIGHT, dim annulus -> DIM_LIGHT.

        Args:
            position: Center of the light source
            bright_radius_feet: Radius of bright light in feet
            dim_radius_feet: Radius of dim light in feet (total radius = bright + dim)
            anchor_uuid: If set, light follows this BaseBlock's movement
            very_bright_radius_feet: Radius of very bright light in feet (innermost zone)

        Returns:
            UUID of the light source
        """
        source = LightSourceData(
            position=position,
            very_bright_radius_feet=very_bright_radius_feet,
            bright_radius_feet=bright_radius_feet,
            dim_radius_feet=dim_radius_feet,
            anchor_uuid=anchor_uuid
        )
        self._light_sources[source.uuid] = source

        if anchor_uuid:
            anchor = BaseBlock.get(anchor_uuid)
            if anchor:
                anchor.attach_light_source(source.uuid)

        if self._is_light_effectively_active(source):
            self._apply_light_source(source, parent_event=parent_event)

        self._ensure_light_pre_completion_callback()
        self._ensure_blocking_callback()

        return source.uuid

    def remove_light_source(self, light_uuid: UUID,
                            parent_event: Optional[UUID] = None) -> None:
        """Remove a light source and clean up tile modifiers."""
        source = self._light_sources.pop(light_uuid, None)
        if source is None:
            return

        self._remove_light_source_tiles(source, parent_event=parent_event)

        if source.anchor_uuid:
            anchor = BaseBlock.get(source.anchor_uuid)
            if anchor:
                anchor.detach_light_source(light_uuid)

    def cleanup_block_light_sources(
        self,
        block_uuid: UUID,
        parent_event: Optional[UUID] = None,
    ) -> None:
        """Permanently remove all light sources attached to a destroyed block."""
        block = BaseBlock.get(block_uuid)
        if block is None:
            return
        for light_uuid in block.get_attached_light_sources():
            self.remove_light_source(light_uuid, parent_event=parent_event)
        self._block_light_suppressions.pop(block_uuid, None)

    def _is_light_effectively_active(self, source: LightSourceData) -> bool:
        """Return desired activation after anchor-owned suppressions."""
        return bool(
            source.is_active
            and (
                source.anchor_uuid is None
                or not self._block_light_suppressions.get(source.anchor_uuid)
            )
        )

    def set_block_light_suppressed(
        self,
        block_uuid: UUID,
        token: str,
        suppressed: bool,
        parent_event: Optional[UUID] = None,
    ) -> None:
        """Add or remove one owner's reversible suppression of anchored lights.

        Suppressions compose by token. Illumination changes only when the first
        token is added or the last token is removed, so independent rules never
        restore light that another rule still suppresses.
        """
        tokens = self._block_light_suppressions[block_uuid]
        was_suppressed = bool(tokens)
        if suppressed:
            tokens.add(token)
        else:
            tokens.discard(token)
            if not tokens:
                self._block_light_suppressions.pop(block_uuid, None)
        is_suppressed = bool(self._block_light_suppressions.get(block_uuid))
        if was_suppressed == is_suppressed:
            return

        block = BaseBlock.get(block_uuid)
        if block is None:
            return
        for light_uuid in block.get_attached_light_sources():
            source = self._light_sources.get(light_uuid)
            if source is None or not source.is_active:
                continue
            if is_suppressed:
                self._remove_light_source_tiles(source, parent_event=parent_event)
            else:
                self._apply_light_source(source, parent_event=parent_event)

    def move_light_source(self, light_uuid: UUID, new_position: Tuple[int, int],
                          parent_event: Optional[UUID] = None) -> None:
        """Move a light source to a new position using delta computation.

        Only touches tiles that actually change — tiles in the overlap area
        with the same light level are left untouched (no events fired).
        For a 1-tile move, this typically touches ~10% of affected tiles.
        """
        source = self._light_sources.get(light_uuid)
        if source is None:
            return

        if not self._is_light_effectively_active(source):
            source.position = new_position
            source.affected_tiles.clear()
            return

        old_affected = dict(source.affected_tiles)
        new_affected = self._compute_light_tiles(source, new_position)

        changed_positions: List[Tuple[int, int]] = []
        all_positions = set(old_affected) | set(new_affected)
        for pos in all_positions:
            old_level = old_affected.get(pos)
            new_level = new_affected.get(pos)
            if old_level == new_level:
                continue

            tile = self._tiles.get(pos)
            if tile is None:
                continue

            if old_level is not None and new_level is None:
                if tile._remove_light_modifier(source.uuid):
                    changed_positions.append(pos)
            elif new_level is not None:
                if tile._add_illumination(source.uuid, new_level):
                    changed_positions.append(pos)

        source.position = new_position
        source.affected_tiles = new_affected

        self._fire_light_batch_events(changed_positions, parent_event=parent_event)

    def toggle_light_source(
        self,
        light_uuid: UUID,
        active: bool,
        parent_event: Optional[UUID] = None,
    ) -> None:
        """Toggle a light source on/off without destroying it."""
        source = self._light_sources.get(light_uuid)
        if source is None:
            return
        if source.is_active == active:
            return

        source.is_active = active
        if self._is_light_effectively_active(source):
            self._apply_light_source(source, parent_event=parent_event)
        else:
            self._remove_light_source_tiles(source, parent_event=parent_event)

    def _compute_light_tiles(self, source: LightSourceData,
                             position: Optional[Tuple[int, int]] = None) -> Dict[Tuple[int, int], LightLevel]:
        """Compute which tiles a light source would affect and at what level.

        Pure computation — does NOT modify any tiles.
        Uses FOV from position so light doesn't go through walls.
        """
        pos = position or source.position
        total_radius_feet = source.bright_radius_feet + source.dim_radius_feet
        total_radius_tiles = max(total_radius_feet // 5, 1)
        bright_radius_tiles = max(source.bright_radius_feet // 5, 1)
        very_bright_radius_tiles = source.very_bright_radius_feet / 5 if source.very_bright_radius_feet > 0 else 0

        visible_positions = self.compute_fov(pos, total_radius_tiles)
        result: Dict[Tuple[int, int], LightLevel] = {}
        for tile_pos in visible_positions:
            if tile_pos not in self._tiles:
                continue
            dx = tile_pos[0] - pos[0]
            dy = tile_pos[1] - pos[1]
            dist_tiles = math.sqrt(dx * dx + dy * dy)
            if very_bright_radius_tiles > 0 and dist_tiles <= very_bright_radius_tiles:
                result[tile_pos] = LightLevel.VERY_BRIGHT
            elif dist_tiles <= bright_radius_tiles:
                result[tile_pos] = LightLevel.BRIGHT_LIGHT
            else:
                result[tile_pos] = LightLevel.DIM_LIGHT
        return result

    def _apply_light_source(self, source: LightSourceData,
                            parent_event: Optional[UUID] = None) -> None:
        """Compute and apply illumination from a light source to tiles.
        Suppresses per-tile events and fires a single senses update after."""
        if not self._is_light_effectively_active(source):
            return
        source.affected_tiles = self._compute_light_tiles(source)
        changed_positions: List[Tuple[int, int]] = []
        for pos, level in source.affected_tiles.items():
            tile = self._tiles.get(pos)
            if tile is not None:
                if tile._add_illumination(source.uuid, level):
                    changed_positions.append(pos)
        self._fire_light_batch_events(changed_positions, parent_event=parent_event)

    def _remove_light_source_tiles(self, source: LightSourceData,
                                   parent_event: Optional[UUID] = None) -> None:
        """Remove illumination from all tiles affected by this light source.
        Suppresses per-tile events and fires a single senses update after."""
        changed_positions: List[Tuple[int, int]] = []
        for pos in source.affected_tiles:
            tile = self._tiles.get(pos)
            if tile:
                if tile._remove_light_modifier(source.uuid):
                    changed_positions.append(pos)
        source.affected_tiles.clear()
        self._fire_light_batch_events(changed_positions, parent_event=parent_event)

    def _fire_light_batch_events(
        self,
        changed_positions: List[Tuple[int, int]],
        parent_event: Optional[UUID] = None,
        requires_fov: bool = False,
    ) -> None:
        """Publish one complete event for an atomic light-field delta.

        The event carries every changed position so rule handlers and observer
        senses consume the same authoritative batch exactly once.

        Args:
            changed_positions: Tiles whose resolved light level changed.
            parent_event: Optional causal parent event UUID.
            requires_fov: Whether the light delta changes vision geometry.
        """
        if not changed_positions:
            return
        channels = {"illumination"}
        if requires_fov:
            channels.add("optical")
        self._bump_spatial_revisions(channels)

        batch_hint = SensesUpdateHint(
            requires_fov=requires_fov,
            light_changed_positions=set(changed_positions),
        )
        representative_position = min(changed_positions)
        representative_tile = self._tiles.get(representative_position)
        if representative_tile is None:
            return
        level_map = {
            f"{position[0]},{position[1]}": tile.resolved_light_level.value
            for position in sorted(set(changed_positions))
            if (tile := self._tiles.get(position)) is not None
        }
        event = SpatialChangeEvent.light_changed(
            representative_position,
            representative_tile.uuid,
            senses_hint=batch_hint,
            parent_event=parent_event,
            new_light_level=representative_tile.resolved_light_level.value,
            light_level_map=level_map,
        )
        self._fire_spatial_event(event)

    def _ensure_light_pre_completion_callback(self) -> None:
        """Install carried-light settlement before indexed sensory reduction."""
        EventQueue.add_pre_completion_callback(
            self._move_attached_lights_before_entry_completion,
        )

    def _move_attached_lights_before_entry_completion(self, event: Event) -> None:
        """Settle attached illumination at the existing anchor-entry boundary."""
        if not isinstance(event, SpatialChangeEvent):
            return
        if (
            event.event_type is EventType.SPATIAL_ENTITY_LEFT
            and event.old_position is None
            and event.entity_uuid is not None
        ):
            self.set_block_light_suppressed(
                event.entity_uuid,
                ENTITY_WORLD_PRESENCE_LIGHT_SUPPRESSION_TOKEN,
                True,
                parent_event=event.uuid,
            )
            return
        if event.event_type is EventType.SPATIAL_ENTITY_ENTERED:
            anchor_uuid = event.entity_uuid
        elif event.event_type is EventType.SPATIAL_OBJECT_PLACED:
            anchor_uuid = event.object_uuid
        else:
            return
        if anchor_uuid is None:
            return
        anchor = BaseBlock.get(anchor_uuid)
        if anchor is None:
            return
        for light_uuid in anchor.get_attached_light_sources():
            source = self._light_sources.get(light_uuid)
            if source is not None and source.position != event.position:
                self.move_light_source(
                    light_uuid,
                    event.position,
                    parent_event=event.uuid,
                )
        if event.event_type is EventType.SPATIAL_ENTITY_ENTERED:
            self.set_block_light_suppressed(
                anchor_uuid,
                ENTITY_WORLD_PRESENCE_LIGHT_SUPPRESSION_TOKEN,
                False,
                parent_event=event.uuid,
            )

    def _ensure_blocking_callback(self) -> None:
        """Register vision-blocking callback for light recomputation (once)."""
        if self._blocking_callback_registered:
            return
        self._blocking_callback_registered = True
        EventQueue.add_on_event_callback(
            self._on_vision_blocking_changed,
            event_types={
                EventType.SPATIAL_ENTITY_ENTERED,
                EventType.SPATIAL_ENTITY_LEFT,
                EventType.SPATIAL_TILE_CHANGED,
                EventType.SPATIAL_OBJECT_PLACED,
                EventType.SPATIAL_OBJECT_REMOVED,
                EventType.SPATIAL_PERCEIVABILITY_CHANGED,
                EventType.SPATIAL_OBJECT_CHANGED,
            },
            phases={EventPhase.DECLARATION},
        )

    def _on_vision_blocking_changed(self, event: Event) -> None:
        """Recompute lights when vision-blocking geometry changes.

        Reacts to ANY spatial event with requires_fov=True (the unified signal
        that vision geometry changed). Fires at DECLARATION so light propagates
        before senses evaluate.

        Excludes SPATIAL_LIGHT_CHANGED to prevent recursion.
        """
        if event.phase != EventPhase.DECLARATION:
            return
        if event.event_type == EventType.SPATIAL_LIGHT_CHANGED:
            return
        if not isinstance(event, SpatialChangeEvent):
            return
        hint = event.senses_hint
        if hint is None or not (hint.requires_fov or hint.requires_light_recompute):
            return
        positions = set(hint.light_changed_positions or ())
        if not positions:
            positions.add(event.position)
        self.recompute_lights_at_positions(positions, parent_event=event.uuid)

    def recompute_lights_at_position(self, position: Tuple[int, int],
                                     parent_event: Optional[UUID] = None) -> None:
        """Recompute light sources affected by a blocking change at position.

        When blocking geometry changes (door open/close, wall destruction),
        light sources within range of the changed position must recompute
        their illumination. Uses the same delta pattern as move_light_source()
        — only tiles that actually change are touched.

        Uses a distance check (position within light's max radius) rather than
        affected_tiles membership, since geometry changes may have previously
        removed the position from affected_tiles (e.g. remove_tile + set_tile).
        """
        self.recompute_lights_at_positions({position}, parent_event=parent_event)

    def recompute_lights_at_positions(
        self,
        positions: Set[Tuple[int, int]],
        *,
        parent_event: Optional[UUID] = None,
    ) -> None:
        """Recompute each relevant active light source once for a position set."""
        if not positions:
            return
        for source in self._light_sources.values():
            if not self._is_light_effectively_active(source):
                continue
            total_radius_tiles = (source.bright_radius_feet + source.dim_radius_feet) / 5
            if not any(
                math.sqrt(
                    (position[0] - source.position[0]) ** 2
                    + (position[1] - source.position[1]) ** 2
                ) <= total_radius_tiles
                for position in positions
            ):
                continue

            old_affected = dict(source.affected_tiles)
            new_affected = self._compute_light_tiles(source)

            changed_positions: List[Tuple[int, int]] = []
            all_positions = set(old_affected) | set(new_affected)
            for pos in all_positions:
                old_level = old_affected.get(pos)
                new_level = new_affected.get(pos)
                if old_level == new_level:
                    continue

                tile = self._tiles.get(pos)
                if tile is None:
                    continue

                if old_level is not None and new_level is None:
                    if tile._remove_light_modifier(source.uuid):
                        changed_positions.append(pos)
                elif new_level is not None:
                    if tile._add_illumination(source.uuid, new_level):
                        changed_positions.append(pos)

            source.affected_tiles = new_affected
            self._fire_light_batch_events(changed_positions, parent_event=parent_event)

    def get_positions_near_entities(
        self, entity_positions: Set[Tuple[int, int]], radius: int
    ) -> Set[Tuple[int, int]]:
        """Union of all positions within radius tiles of any entity position.

        Used by AoE prefilter to skip shape computation at positions that
        can't possibly hit any entity.
        """
        candidates: Set[Tuple[int, int]] = set()
        for ent_pos in entity_positions:
            candidates |= circle_positions(ent_pos, radius)
        return candidates

    def is_blocking_propagation(self, x: int, y: int) -> bool:
        """Return whether a Tile or center object blocks physical propagation."""
        tile = self._tiles.get((x, y))
        if tile is None or tile.blocks_propagation():
            return True
        for obj_uuid in self.get_center_objects_at((x, y)):
            block = BaseBlock.get(obj_uuid)
            if block is not None and block.blocks_propagation():
                return True
        return False

    def compute_propagation_fov(self, origin: Tuple[int, int],
                                max_distance: Optional[float] = None) -> List[Tuple[int, int]]:
        """Compute FOV for AoE propagation (physical barriers only).

        This is independent of optical opacity and objective illumination."""
        cache_key = (origin, max_distance)
        cached = self._propagation_fov_cache.get(cache_key)
        if cached is not None:
            return list(cached)
        visible_positions: List[Tuple[int, int]] = []

        visible_positions = self._compute_directional_fov(origin, max_distance, "propagation")

        self._propagation_fov_cache[cache_key] = tuple(visible_positions)
        return list(visible_positions)

    def filter_propagation_positions(
        self,
        origin: Tuple[int, int],
        positions: Set[Tuple[int, int]],
        max_distance: Optional[float] = None,
    ) -> Set[Tuple[int, int]]:
        """Filter a known footprint through physical propagation blockers.

        This uses the same transition and blocking rules as
        `compute_propagation_fov()`, but it tests only the supplied positions.
        AoE previews already know their geometric footprint, so this avoids
        scanning a full square FOV around every possible origin.

        Args:
            origin: AoE propagation origin.
            positions: Candidate footprint positions to filter.
            max_distance: Optional radial bound matching full FOV behavior.

        Returns:
            Candidate positions that physical propagation can reach.
        """
        if origin not in self._tiles:
            return set()

        cache_key = (origin, max_distance, tuple(sorted(positions)))
        cached_positions = self._propagation_filter_cache.get(cache_key)
        if cached_positions is not None:
            self._propagation_filter_cache.move_to_end(cache_key)
            return set(cached_positions)

        radius_squared = max_distance * max_distance if max_distance is not None else None
        transition_cache = self._propagation_transition_cache
        blocking_cache = self._propagation_blocking_cache
        line_cache: Dict[Tuple[int, int], Tuple[Tuple[int, int], ...]] = {}

        def get_line_offsets(end: Tuple[int, int]) -> Tuple[Tuple[int, int], ...]:
            key = (end[0] - origin[0], end[1] - origin[1])
            cached = line_cache.get(key)
            if cached is not None:
                return cached
            path = supercover_line_offsets(key)
            line_cache[key] = path
            return path

        def transition_allows(prev: Tuple[int, int], current: Tuple[int, int]) -> bool:
            key = (prev, current)
            cached = transition_cache.get(key)
            if cached is not None:
                return cached
            allowed = self.can_propagate_transition(prev, current, None)
            transition_cache[key] = allowed
            return allowed

        def blocks_cell(position: Tuple[int, int]) -> bool:
            cached = blocking_cache.get(position)
            if cached is not None:
                return cached
            blocked = self.is_blocking_propagation(position[0], position[1])
            blocking_cache[position] = blocked
            return blocked

        def transition_clear(end: Tuple[int, int]) -> bool:
            path = get_line_offsets(end)
            if not path:
                return False
            origin_x, origin_y = origin
            prev = origin
            for index in range(1, len(path)):
                offset_x, offset_y = path[index]
                current = (origin_x + offset_x, origin_y + offset_y)
                if not transition_allows(prev, current):
                    return False
                if index < len(path) - 1 and blocks_cell(current):
                    return False
                prev = current
            return True

        visible_positions: Set[Tuple[int, int]] = set()
        for position in positions:
            if position not in self._tiles:
                continue
            if radius_squared is not None:
                dx = position[0] - origin[0]
                dy = position[1] - origin[1]
                if dx * dx + dy * dy > radius_squared:
                    continue
            if position == origin or transition_clear(position):
                visible_positions.add(position)

        self._propagation_filter_cache[cache_key] = tuple(sorted(visible_positions))
        if len(self._propagation_filter_cache) > 256:
            self._propagation_filter_cache.popitem(last=False)
        return visible_positions

    def get_barrier_positions(
        self,
        footprint: Iterable[Tuple[int, int]],
    ) -> Set[Tuple[int, int]]:
        """Return bounded positions needing ordered propagation evaluation.

        Center blockers are tested directly. Boundary blockers are discovered
        only across the four edges incident to each supplied footprint
        position; the caller still performs the authoritative ordered
        propagation evaluation for the resulting bounded candidate set.
        """
        positions = set(footprint)
        barriers: Set[Tuple[int, int]] = set()
        for position in positions:
            if self.is_blocking_propagation(position[0], position[1]):
                barriers.add(position)
                continue
            for neighbor in (
                (position[0] - 1, position[1]),
                (position[0] + 1, position[1]),
                (position[0], position[1] - 1),
                (position[0], position[1] + 1),
            ):
                if neighbor in self._tiles and not self.can_propagate_transition(
                    position,
                    neighbor,
                ):
                    barriers.add(position)
                    break
        return barriers

    def clear(self) -> None:
        """Clear all tiles, entity membership, object placements, and light sources."""
        if any(tile.get_entity_uuids() for tile in self._tiles.values()):
            raise ValueError("cannot clear a map while entities are deployed")
        if self._spatial_conditions:
            raise ValueError(
                "cannot clear a map while spatial conditions are active",
            )
        if any(tile.active_conditions for tile in self._tiles.values()):
            raise ValueError("cannot clear a map while direct Tile conditions are active")
        for light_uuid in tuple(self._light_sources):
            self.remove_light_source(light_uuid)
        registered_objects = tuple(self._object_placements.values())
        for placement in registered_objects:
            object_uuid = placement.object_uuid
            obj = BaseBlock.get(object_uuid)
            if obj is not None:
                obj.on_grid_object_removed(placement.position)
        self._tiles.clear()
        self._tiles_by_uuid.clear()
        self._object_placements.clear()
        self._spatial_conditions.clear()
        self._spatial_condition_positions.clear()
        self._spatial_condition_layers.clear()
        self._cell_subscribers.clear()
        self._entity_subscriptions.clear()
        self._light_sources.clear()
        self._block_light_suppressions.clear()
        self._connectors_by_uuid.clear()
        self._connector_uuid_by_authored_id.clear()
        self._connector_uuids_by_endpoint.clear()
        self._connector_revision = 0
        self._pending_events.clear()
        self._pending_committed_events.clear()
        self._bounds_dirty = True
        self._spatial_revision = 0
        self._optical_revision = 0
        self._movement_revision = 0
        self._light_revision = 0
        self._propagation_revision = 0
        self._fov_cache.clear()
        self._propagation_fov_cache.clear()
        self._propagation_filter_cache.clear()
        self._propagation_transition_cache.clear()
        self._propagation_blocking_cache.clear()

    def get_all_tiles(self) -> Dict[Tuple[int, int], Tile]:
        """Get all tiles (for serialization/debugging)."""
        return self._tiles.copy()

    def get_tiles_with_conditions(self) -> List[Tile]:
        """Get tiles with active conditions (for environment step)."""
        return [tile for tile in self._tiles.values() if tile.active_conditions]

    def tile_count(self) -> int:
        """Get number of tiles."""
        return len(self._tiles)

def get_map() -> GridMap:
    """Get the global GridMap instance."""
    return GridMap.get_instance()


def reset_map() -> None:
    """Reset the global GridMap (for testing)."""
    GridMap.reset()
