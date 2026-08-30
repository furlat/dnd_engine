"""Central spatial registry for tiles, entities, objects, light, and paths."""

import math
import time
from typing import Any, Dict, List, Optional, Tuple, Set, DefaultDict, cast
from uuid import UUID, uuid4
from collections import OrderedDict, defaultdict

from pydantic import BaseModel, Field

from dnd.core.geometry import circle_positions, supercover_line, supercover_line_offsets
from dnd.core.elevation import support_distance_feet
from dnd.core.shadowcast import compute_fov
from dnd.core.dijkstra import breadth_first_paths, dijkstra
from dnd.core.base_block import BaseBlock, MovementMode, LightLevel
from dnd.core.base_conditions import BaseCondition
from dnd.core.positioning import PositionCommitError
from dnd.core.base_tiles import (
    Tile,
    TileObjectBand,
    validate_elevation_surface_tuple,
)
from dnd.core.events import Event, SpatialChangeEvent, SpatialChangeType, EventPhase, EventQueue, EventType, SensesUpdateHint, TileElevationChangeEvent, TraversalConnectorChangeEvent
from dnd.core.traversal_connectors import (
    TraversalConnector,
    TraversalConnectorChangeOperation,
    TraversalConnectorDefinition,
    TraversalConnectorEndpoint,
)
from dnd.core.world_edges import (
    AdjacentEdgeKey,
    ElevationSurfaceKind,
    SlopeAxis,
    WorldEdgeStructuralContribution,
    WorldEdgeView,
    progressive_elevation_transition,
    transition_axis,
)
from dnd.types.world import CardinalDirection, WorldEdgeChannel
from dnd.types.senses import OpticalObscurement
from dnd.types.spatial_effects import (
    SpatialEffectLayer,
    SpatialEffectOccupancyPolicy,
)
from dnd.types.world_placement import (
    BoundaryStructure,
    WorldObjectPlacement,
    WorldPlacementKind,
)
from dnd.action_timing import action_timing_enabled, record_action_elapsed, record_action_timing

DIRECTIONS: Tuple[str, ...] = ("north", "south", "east", "west")
DIRECTIONAL_CHANNELS: Tuple[str, ...] = (
    "movement",
    "optical",
    "propagation",
)
ENTITY_WORLD_PRESENCE_LIGHT_SUPPRESSION_TOKEN = "entity.world_presence.absent"


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

    The map owns Tile storage, Tile-backed occupancy, object placement, event-backed
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
        self._spatial_conditions: Dict[UUID, BaseCondition] = {}
        self._spatial_condition_positions: Dict[
            UUID,
            Set[Tuple[int, int]],
        ] = {}
        self._spatial_condition_layers: Dict[
            UUID,
            SpatialEffectLayer,
        ] = {}
        self._connectors_by_uuid: Dict[UUID, TraversalConnector] = {}
        self._connector_uuid_by_authored_id: Dict[str, UUID] = {}
        self._connector_uuids_by_endpoint: DefaultDict[
            Tuple[int, int],
            List[UUID],
        ] = defaultdict(list)

        self._cell_subscribers: DefaultDict[Tuple[int, int], Set[UUID]] = defaultdict(set)
        self._entity_subscriptions: DefaultDict[UUID, Set[Tuple[int, int]]] = defaultdict(set)

        self._light_sources: Dict[UUID, LightSourceData] = {}
        self._block_light_suppressions: DefaultDict[UUID, Set[str]] = defaultdict(set)
        self._optical_obscurements_by_position: DefaultDict[
            Tuple[int, int], Dict[UUID, OpticalObscurement]
        ] = defaultdict(dict)
        self._optical_obscurement_positions_by_source: Dict[
            UUID, Set[Tuple[int, int]]
        ] = {}

        self._events_enabled: bool = True
        self._pending_events: List['SpatialChangeEvent'] = []
        self._pending_committed_events: List['SpatialChangeEvent'] = []

        self._spatial_revision: int = 0
        self._optical_revision: int = 0
        self._movement_revision: int = 0
        self._connector_revision: int = 0
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
        self._barrier_positions_cache: Optional[frozenset[Tuple[int, int]]] = None
        self._directional_blockers_cache: Dict[str, bool] = {}
        self._directional_transition_cache: Dict[
            Tuple[str, int],
            Dict[Tuple[Tuple[int, int], Tuple[int, int]], bool],
        ] = {}
        self._directional_blocking_cache: Dict[
            Tuple[str, int],
            Dict[Tuple[int, int], bool],
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

        current_event = cast(SpatialChangeEvent, EventQueue.register(event))
        if current_event.canceled:
            return None

        current_event = current_event.phase_to(EventPhase.EXECUTION)
        current_event = cast(SpatialChangeEvent, EventQueue.register(current_event))
        if current_event.canceled:
            return None

        current_event = current_event.phase_to(EventPhase.EFFECT)
        current_event = cast(SpatialChangeEvent, EventQueue.register(current_event))
        if current_event.canceled:
            return None

        self._recompute_lights_before_spatial_completion(current_event)

        current_event = current_event.phase_to(EventPhase.COMPLETION)
        current_event = cast(SpatialChangeEvent, EventQueue.register(current_event))

        return current_event

    def _fire_committed_spatial_event(
        self,
        event: 'SpatialChangeEvent',
    ) -> Optional['SpatialChangeEvent']:
        """Publish one non-vetoable fact for already committed spatial state."""
        if not self._events_enabled:
            self._pending_committed_events.append(event)
            return None
        current_event = cast(
            SpatialChangeEvent,
            EventQueue.publish_preflighted(event),
        )
        current_event = cast(
            SpatialChangeEvent,
            current_event.phase_to(EventPhase.EXECUTION),
        )
        current_event = cast(
            SpatialChangeEvent,
            current_event.phase_to(EventPhase.EFFECT),
        )
        self._settle_entity_presence_before_completion(current_event)
        return cast(
            SpatialChangeEvent,
            current_event.phase_to(EventPhase.COMPLETION),
        )

    def enable_events(self, *, flush_pending: bool = True) -> None:
        """Enable firing, optionally discarding buffered construction noise."""
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
        """Return the shared ordinary-light/ordinary-sight topology revision."""
        return self._optical_revision

    @property
    def occupancy_revision(self) -> int:
        """Return the current authoritative Entity-membership revision."""
        return self._occupancy_revision

    @property
    def movement_revision(self) -> int:
        """Return the current movement-topology revision."""
        return self._movement_revision

    @property
    def connector_revision(self) -> int:
        """Return the current connector-topology revision."""
        return self._connector_revision

    @property
    def propagation_revision(self) -> int:
        """Return the current physical-propagation topology revision."""
        return self._propagation_revision

    def invalidate_spatial_caches(self, channels: Set[str]) -> None:
        """Invalidate spatial query caches after authoritative topology changes.

        Args:
            channels: Changed spatial channels: movement, optical,
                illumination, or propagation.
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
            self._barrier_positions_cache = None
            self._propagation_transition_cache.clear()
            self._propagation_blocking_cache.clear()
        if "optical" in channels:
            self._directional_transition_cache.clear()
            self._directional_blocking_cache.clear()
        for channel in channels & set(DIRECTIONAL_CHANNELS):
            self._directional_blockers_cache.pop(channel, None)

    def _bump_all_spatial_revisions(self) -> None:
        """Advance every spatial channel revision and clear query caches."""
        self._bump_spatial_revisions(
            {"movement", "optical", "illumination", "propagation"}
        )

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
        """Return all four effective intrinsic traversal after-values."""
        return tuple(
            tile.get_movement_cost(mode)
            for mode in MovementMode
        )

    def set_tile(
        self,
        x: int,
        y: int,
        *,
        blocks_optics: bool = False,
        blocks_propagation: bool = False,
        name: str = "Floor",
        sprite_name: Optional[str] = None,
        walking_cost: int = 1,
        flying_cost: int = 1,
        swimming_cost: int = 0,
        burrowing_cost: int = 0,
        default_light: LightLevel = LightLevel.BRIGHT_LIGHT,
        fire_event: bool = True,
        tile: Optional[Tile] = None,
    ) -> Tile:
        """Set or replace a tile at a position.

        If tile parameter is provided, uses that tile directly (updating its position if needed).
        Otherwise creates a new Tile object with the given parameters.
        Returns the stored tile.
        """
        position = (x, y)
        old_tile = self._tiles.get(position)
        if (
            old_tile is not None
            and tile is not old_tile
            and old_tile.get_entity_uuids()
        ):
            raise ValueError(
                f"cannot replace Tile {position} while entity occupancy is present"
            )
        if (
            old_tile is not None
            and tile is not old_tile
            and old_tile.get_spatial_condition_uuids()
        ):
            raise ValueError(
                f"cannot replace Tile {position} while spatial conditions cover it"
            )
        old_costs = self._tile_movement_costs(old_tile) if old_tile else None
        old_light = old_tile.resolved_light_level if old_tile else None
        if tile is None:
            new_costs = (
                walking_cost,
                flying_cost,
                swimming_cost,
                burrowing_cost,
            )
            new_blocks_optics = blocks_optics
            new_blocks_propagation = blocks_propagation
            new_light = default_light
        else:
            new_costs = self._tile_movement_costs(tile)
            new_blocks_optics = tile.blocks_optics
            new_blocks_propagation = tile.blocks_propagation_field
            new_light = tile.resolved_light_level

        movement_changed = old_costs is None or old_costs != new_costs
        optics_changed = (
            old_tile is None
            or old_tile.blocks_optics != new_blocks_optics
        )
        propagation_changed = (
            old_tile is None
            or old_tile.blocks_propagation_field != new_blocks_propagation
        )
        illumination_changed = old_light is None or old_light != new_light
        topology_changed = movement_changed or optics_changed or propagation_changed

        effect: Optional[Event] = None
        if fire_event and self._events_enabled and topology_changed:
            hint = SensesUpdateHint(
                requires_fov=optics_changed,
                requires_paths=movement_changed,
                light_changed_positions=(
                    {position} if illumination_changed else None
                ),
                requires_light_recompute=optics_changed,
                requires_propagation_recompute=propagation_changed,
            )
            declaration = SpatialChangeEvent.tile_changed(
                position,
                tile_walking_cost=new_costs[0],
                tile_flying_cost=new_costs[1],
                tile_swimming_cost=new_costs[2],
                tile_burrowing_cost=new_costs[3],
                tile_blocks_optics=new_blocks_optics,
                tile_blocks_propagation=new_blocks_propagation,
                new_light_level=new_light.value,
                senses_hint=hint,
            )
            effect = self._accept_event_effect(declaration)
            if effect is None:
                raise ValueError("tile change was canceled")

        if tile is None:
            tile = Tile.create(
                position=position,
                blocks_optics=blocks_optics,
                blocks_propagation=blocks_propagation,
                name=name,
                sprite_name=sprite_name,
                walking_cost=walking_cost,
                flying_cost=flying_cost,
                swimming_cost=swimming_cost,
                burrowing_cost=burrowing_cost,
                default_light=default_light,
            )
        else:
            tile.position = position
        if old_tile is not None:
            self._tiles_by_uuid.pop(old_tile.uuid, None)
            if old_tile is not tile:
                BaseBlock.unregister(old_tile.uuid)
        self._tiles[position] = tile
        self._tiles_by_uuid[tile.uuid] = position
        self._bounds_dirty = True

        revision_channels: Set[str] = set()
        if movement_changed:
            revision_channels.add("movement")
        if optics_changed:
            revision_channels.add("optical")
        if propagation_changed:
            revision_channels.add("propagation")
        if illumination_changed:
            revision_channels.add("illumination")
        self._bump_spatial_revisions(revision_channels)

        if effect is not None:
            self._complete_event_effect(effect)
        elif (
            fire_event
            and self._events_enabled
            and old_light is not None
            and old_light != tile.resolved_light_level
        ):
            self._fire_light_batch_events([position])

        return tile

    def set_tile_directional_border(self, *args: Any, **kwargs: Any) -> bool:
        """Reject retired scalar side state; place a boundary structure instead."""
        raise ValueError(
            "Directional boundaries require placed boundary structures"
        )

    def _neighbor_for_direction(self, position: Tuple[int, int], direction: str) -> List[Tuple[int, int]]:
        delta = {
            "north": (0, 1),
            "south": (0, -1),
            "east": (1, 0),
            "west": (-1, 0),
        }.get(direction)
        if delta is None:
            return []
        return [(position[0] + delta[0], position[1] + delta[1])]

    def remove_tile(self, x: int, y: int, fire_event: bool = True) -> None:
        """Remove a tile at the given position."""
        position = (x, y)
        if position in self._tiles:
            tile = self._tiles[position]
            if tile.get_entity_uuids():
                raise ValueError(
                    f"cannot remove Tile {position} while entity occupancy is present"
                )
            if tile.get_spatial_condition_uuids():
                raise ValueError(
                    f"cannot remove Tile {position} while spatial conditions cover it"
                )
            self._tiles_by_uuid.pop(tile.uuid, None)
            BaseBlock.unregister(tile.uuid)
            del self._tiles[position]
            self._bounds_dirty = True
            self._bump_all_spatial_revisions()

            if fire_event and self._events_enabled:
                hint = SensesUpdateHint(
                    requires_fov=True,
                    requires_light_recompute=True,
                    requires_paths=True,
                    requires_propagation_recompute=True,
                )
                event = SpatialChangeEvent(
                    source_entity_uuid=uuid4(),
                    event_type=EventType.SPATIAL_TILE_CHANGED,
                    change_type=SpatialChangeType.TILE_REMOVED,
                    position=position,
                    senses_hint=hint,
                )
                self._fire_spatial_event(event)

    def get_tile(self, x: int, y: int) -> Optional[Tile]:
        """Get tile at position, or None if no tile exists."""
        return self._tiles.get((x, y))

    def get_tile_by_uuid(self, tile_uuid: UUID) -> Optional[Tile]:
        """Get tile by UUID, or None if not found."""
        position = self._tiles_by_uuid.get(tile_uuid)
        if position:
            return self._tiles.get(position)
        return None

    def get_support_elevation_feet(
        self,
        position: Tuple[int, int],
    ) -> int:
        """Return the exact support elevation at one live Tile position."""
        tile = self._tiles.get(position)
        if tile is None:
            raise ValueError(f"support Tile not found at {position}")
        return tile.height * 5

    def _build_connector(
        self,
        definition: TraversalConnectorDefinition,
        *,
        connector_uuid: Optional[UUID] = None,
        revision: int = 1,
    ) -> TraversalConnector:
        """Resolve authored connector endpoints against exact live supports."""
        endpoints: List[TraversalConnectorEndpoint] = []
        for position in definition.endpoint_positions:
            tile = self._tiles.get(position)
            if tile is None:
                raise ValueError(
                    f"connector endpoint has no support Tile at {position}"
                )
            endpoints.append(
                TraversalConnectorEndpoint(
                    position=position,
                    support_tile_uuid=tile.uuid,
                    elevation_feet=tile.height * 5,
                )
            )
        return TraversalConnector.create(
            definition,
            (endpoints[0], endpoints[1]),
            connector_uuid=connector_uuid,
            revision=revision,
        )

    def connector_supports_are_current(
        self,
        connector: TraversalConnector,
    ) -> bool:
        """Return whether both frozen support anchors still match the map."""
        return all(
            (tile := self._tiles.get(endpoint.position)) is not None
            and tile.uuid == endpoint.support_tile_uuid
            and tile.height * 5 == endpoint.elevation_feet
            and self._tiles_by_uuid.get(tile.uuid) == endpoint.position
            for endpoint in connector.endpoints
        )

    def _index_connector(self, connector: TraversalConnector) -> None:
        self._connectors_by_uuid[connector.uuid] = connector
        self._connector_uuid_by_authored_id[
            connector.authored_id
        ] = connector.uuid
        for endpoint in connector.endpoints:
            indexed = self._connector_uuids_by_endpoint[endpoint.position]
            if connector.uuid not in indexed:
                indexed.append(connector.uuid)
            indexed.sort(
                key=lambda connector_uuid: (
                    self._connectors_by_uuid[connector_uuid].authored_id,
                    str(connector_uuid),
                )
            )

    def _unindex_connector(self, connector: TraversalConnector) -> None:
        self._connectors_by_uuid.pop(connector.uuid, None)
        if (
            self._connector_uuid_by_authored_id.get(connector.authored_id)
            == connector.uuid
        ):
            self._connector_uuid_by_authored_id.pop(
                connector.authored_id,
                None,
            )
        for endpoint in connector.endpoints:
            indexed = self._connector_uuids_by_endpoint.get(endpoint.position)
            if indexed is None:
                continue
            remaining = [
                connector_uuid
                for connector_uuid in indexed
                if connector_uuid != connector.uuid
            ]
            if remaining:
                self._connector_uuids_by_endpoint[
                    endpoint.position
                ] = remaining
            else:
                self._connector_uuids_by_endpoint.pop(endpoint.position, None)

    def _connector_change_effect(
        self,
        operation: TraversalConnectorChangeOperation,
        *,
        connector_uuid: UUID,
        authored_id: str,
        old_connector: Optional[TraversalConnector],
        new_connector: Optional[TraversalConnector],
        parent_event: Optional[UUID],
    ) -> Optional[TraversalConnectorChangeEvent]:
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
        accepted = self._accept_event_effect(declaration)
        return cast(Optional[TraversalConnectorChangeEvent], accepted)

    def register_connector(
        self,
        definition: TraversalConnectorDefinition,
        *,
        connector_uuid: Optional[UUID] = None,
        parent_event: Optional[UUID] = None,
    ) -> Optional[TraversalConnector]:
        """Register one unique authored connector after event acceptance."""
        if definition.authored_id in self._connector_uuid_by_authored_id:
            raise ValueError(
                f"duplicate connector authored_id {definition.authored_id}"
            )
        connector = self._build_connector(
            definition,
            connector_uuid=connector_uuid,
        )
        if connector.uuid in self._connectors_by_uuid:
            raise ValueError(f"duplicate connector UUID {connector.uuid}")
        effect = (
            self._connector_change_effect(
                TraversalConnectorChangeOperation.REGISTER,
                connector_uuid=connector.uuid,
                authored_id=connector.authored_id,
                old_connector=None,
                new_connector=connector,
                parent_event=parent_event,
            )
            if self._events_enabled
            else None
        )
        if self._events_enabled and effect is None:
            return None
        if not self.connector_supports_are_current(connector):
            if effect is not None:
                effect.cancel("Connector supports changed before commit")
            return None
        self._index_connector(connector)
        self._connector_revision += 1
        if effect is not None:
            self._complete_event_effect(effect)
        return connector

    def replace_connector(
        self,
        connector_uuid: UUID,
        definition: TraversalConnectorDefinition,
        *,
        parent_event: Optional[UUID] = None,
    ) -> Optional[TraversalConnector]:
        """Replace connector mechanics while preserving runtime identity."""
        previous = self._connectors_by_uuid.get(connector_uuid)
        if previous is None:
            raise ValueError(f"unknown connector {connector_uuid}")
        if definition.authored_id != previous.authored_id:
            raise ValueError("connector replacement must preserve authored_id")
        replacement = self._build_connector(
            definition,
            connector_uuid=connector_uuid,
            revision=previous.revision + 1,
        )
        effect = self._connector_change_effect(
            TraversalConnectorChangeOperation.REPLACE,
            connector_uuid=connector_uuid,
            authored_id=previous.authored_id,
            old_connector=previous,
            new_connector=replacement,
            parent_event=parent_event,
        )
        if effect is None:
            return None
        if (
            self._connectors_by_uuid.get(connector_uuid) is not previous
            or not self.connector_supports_are_current(replacement)
        ):
            effect.cancel("Connector changed before replacement commit")
            return None
        self._unindex_connector(previous)
        self._index_connector(replacement)
        self._connector_revision += 1
        self._complete_event_effect(effect)
        return replacement

    def set_connector_enabled(
        self,
        connector_uuid: UUID,
        enabled: bool,
        *,
        parent_event: Optional[UUID] = None,
    ) -> Optional[TraversalConnector]:
        """Enable or disable one connector through its replacement boundary."""
        if type(enabled) is not bool:
            raise TypeError("enabled must be an exact bool")
        previous = self._connectors_by_uuid.get(connector_uuid)
        if previous is None:
            raise ValueError(f"unknown connector {connector_uuid}")
        if previous.enabled is enabled:
            return previous
        definition = previous.definition().model_copy(
            update={"enabled": enabled}
        )
        operation = (
            TraversalConnectorChangeOperation.ENABLE
            if enabled
            else TraversalConnectorChangeOperation.DISABLE
        )
        replacement = self._build_connector(
            definition,
            connector_uuid=connector_uuid,
            revision=previous.revision + 1,
        )
        effect = self._connector_change_effect(
            operation,
            connector_uuid=connector_uuid,
            authored_id=previous.authored_id,
            old_connector=previous,
            new_connector=replacement,
            parent_event=parent_event,
        )
        if effect is None:
            return None
        if (
            self._connectors_by_uuid.get(connector_uuid) is not previous
            or not self.connector_supports_are_current(replacement)
        ):
            effect.cancel("Connector changed before state commit")
            return None
        self._unindex_connector(previous)
        self._index_connector(replacement)
        self._connector_revision += 1
        self._complete_event_effect(effect)
        return replacement

    def remove_connector(
        self,
        connector_uuid: UUID,
        *,
        parent_event: Optional[UUID] = None,
    ) -> bool:
        """Remove one connector after its accepted typed lifecycle."""
        previous = self._connectors_by_uuid.get(connector_uuid)
        if previous is None:
            return False
        effect = self._connector_change_effect(
            TraversalConnectorChangeOperation.REMOVE,
            connector_uuid=connector_uuid,
            authored_id=previous.authored_id,
            old_connector=previous,
            new_connector=None,
            parent_event=parent_event,
        )
        if effect is None:
            return False
        if self._connectors_by_uuid.get(connector_uuid) is not previous:
            effect.cancel("Connector changed before removal commit")
            return False
        self._unindex_connector(previous)
        self._connector_revision += 1
        self._complete_event_effect(effect)
        return True

    def get_connector(
        self,
        connector_uuid: UUID,
    ) -> Optional[TraversalConnector]:
        return self._connectors_by_uuid.get(connector_uuid)

    def get_connector_by_authored_id(
        self,
        authored_id: str,
    ) -> Optional[TraversalConnector]:
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
        return tuple(
            self._connectors_by_uuid[connector_uuid]
            for connector_uuid in self._connector_uuids_by_endpoint.get(
                position,
                (),
            )
            if connector_uuid in self._connectors_by_uuid
        )

    def get_all_connectors(self) -> Tuple[TraversalConnector, ...]:
        return tuple(
            sorted(
                self._connectors_by_uuid.values(),
                key=lambda connector: (
                    connector.authored_id,
                    str(connector.uuid),
                ),
            )
        )

    def set_tile_elevation(
        self,
        position: Tuple[int, int],
        *,
        height: int,
        surface_kind: ElevationSurfaceKind,
        slope_axis: Optional[SlopeAxis],
        parent_event: Optional[UUID] = None,
    ) -> bool:
        """Commit one validated support tuple through its typed lifecycle."""
        validate_elevation_surface_tuple(height, surface_kind, slope_axis)
        tile = self._tiles.get(position)
        if tile is None:
            raise ValueError(f"cannot set elevation on missing Tile {position}")
        previous = (
            tile.height,
            tile.elevation_surface_kind,
            tile.slope_axis,
        )
        candidate = (height, surface_kind, slope_axis)
        if previous == candidate:
            return False
        if height != tile.height and any(
            placement.position == position
            and placement.kind is WorldPlacementKind.CENTER
            for placement in self._object_placements.values()
        ):
            raise ValueError(
                "cannot change support height while center objects are placed"
            )
        if height != tile.height and self._connector_uuids_by_endpoint.get(
            position
        ):
            raise ValueError(
                "cannot change support height while a connector is anchored"
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
        effect = (
            self._accept_event_effect(declaration)
            if self._events_enabled
            else None
        )
        if self._events_enabled and effect is None:
            return False
        if (
            self._tiles.get(position) is not tile
            or self._tiles_by_uuid.get(tile.uuid) != position
            or (
                tile.height,
                tile.elevation_surface_kind,
                tile.slope_axis,
            )
            != previous
        ):
            if effect is not None:
                effect.cancel(
                    "Tile support changed before elevation could commit"
                )
            return False
        tile.height = height
        tile.elevation_surface_kind = surface_kind
        tile.slope_axis = slope_axis
        self._bump_spatial_revisions({"movement"})
        if effect is not None:
            self._complete_event_effect(effect)
        return True

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
                self._tiles[position].remove_spatial_condition_reference(
                    condition.uuid,
                    previous_layer,
                )
            if previous_layer is not layer:
                for position in previous_positions & normalized:
                    self._tiles[position].remove_spatial_condition_reference(
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

    def publish_tile_mechanics_changed(
        self,
        position: Tuple[int, int],
        *,
        source_entity_uuid: UUID,
        parent_event: Optional[UUID] = None,
    ) -> Optional[SpatialChangeEvent]:
        """Publish one committed complete traversal tuple for a Tile."""
        tile = self._tiles.get(position)
        if tile is None:
            raise ValueError(f"tile mechanics position is absent: {position}")
        return self._fire_committed_spatial_event(
            SpatialChangeEvent.tile_changed(
                position,
                tile_walking_cost=tile.get_movement_cost(MovementMode.WALKING),
                tile_flying_cost=tile.get_movement_cost(MovementMode.FLYING),
                tile_swimming_cost=tile.get_movement_cost(MovementMode.SWIMMING),
                tile_burrowing_cost=tile.get_movement_cost(MovementMode.BURROWING),
                source_entity_uuid=source_entity_uuid,
                parent_event=parent_event,
                senses_hint=SensesUpdateHint(requires_paths=True),
            ),
        )

    def validate_spatial_condition_positions(
        self,
        *,
        condition: BaseCondition,
        layer: SpatialEffectLayer,
        occupancy_policy: SpatialEffectOccupancyPolicy,
        positions: Set[Tuple[int, int]],
    ) -> None:
        """Validate a complete independent footprint without mutation."""
        normalized = set(positions)
        if not normalized:
            raise ValueError("Spatial condition footprint cannot be empty")
        if any(position not in self._tiles for position in normalized):
            raise ValueError(
                "Spatial condition positions must identify existing tiles"
            )
        existing = self._spatial_conditions.get(condition.uuid)
        if existing is not None and existing is not condition:
            raise ValueError(
                f"Spatial condition UUID {condition.uuid} is already active"
            )
        if occupancy_policy is SpatialEffectOccupancyPolicy.EXCLUSIVE_TRANSFORMING:
            for position in normalized:
                occupants = self._tiles[position].get_spatial_condition_uuids(
                    layer,
                ) - {condition.uuid}
                if occupants:
                    raise ValueError(
                        f"{layer.value} cell {position} already has a condition"
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
        """Return the authoritative footprint for one condition."""
        return set(self._spatial_condition_positions.get(condition_uuid, set()))

    def has_spatial_condition(self, condition_uuid: UUID) -> bool:
        """Return whether the exact condition is active on this map."""
        return condition_uuid in self._spatial_conditions

    def get_spatial_condition(
        self,
        condition_uuid: UUID,
    ) -> Optional[BaseCondition]:
        """Return one exact active independent condition."""
        return self._spatial_conditions.get(condition_uuid)

    def get_spatial_condition_uuids_at(
        self,
        position: Tuple[int, int],
        *,
        layer: Optional[SpatialEffectLayer] = None,
    ) -> Set[UUID]:
        """Return active independent-condition UUIDs at one Tile."""
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
        """Resolve active independent conditions at one Tile."""
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
        """Return every active independent condition once."""
        return [
            self._spatial_conditions[condition_uuid]
            for condition_uuid in sorted(self._spatial_conditions, key=str)
        ]

    def is_position_hazardous_for(self, x: int, y: int,
                                  entity_uuid: Optional[UUID] = None) -> bool:
        """Return whether tile or placed-object hazards affect an entity."""
        tile = self.get_tile(x, y)
        if tile is not None and tile.is_hazardous_for(entity_uuid):
            return True

        for obj_uuid in self.get_objects_at((x, y)):
            obj = BaseBlock.get(obj_uuid)
            if obj is not None and obj.is_hazardous_for(entity_uuid):
                return True

        for condition in self.get_spatial_conditions_at((x, y)):
            if condition.is_hazardous_for(entity_uuid):
                return True

        return False

    def has_any_hazards(self) -> bool:
        """Return whether any tile or placed object currently declares a hazard."""
        for tile in self.get_tiles_with_conditions():
            if any(condition.hazard_filter is not None for condition in tile.active_conditions.values()):
                return True
        for obj in self.get_objects_with_conditions():
            if any(condition.hazard_filter is not None for condition in obj.active_conditions.values()):
                return True
        for condition in self.get_spatial_conditions():
            if condition.hazard_filter is not None:
                return True
        return False

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
                return False

        if not walk_in_danger:
            if self.is_position_hazardous_for(x, y, requesting_entity_uuid):
                return False

        if collision_blocked and (x, y) in collision_blocked:
            return False

        return True

    def is_blocking_optics(self, x: int, y: int) -> bool:
        """Return whether a Tile center blocks ordinary light and sight."""
        tile = self._tiles.get((x, y))
        if tile is None or tile.blocks_optics_at_center():
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

    def get_directional_block_map(self, position: Tuple[int, int]) -> Dict[str, Dict[str, bool]]:
        """Derive canonical side blockers from live ordered world edges."""
        result: Dict[str, Dict[str, bool]] = {
            channel: {direction: False for direction in DIRECTIONS}
            for channel in DIRECTIONAL_CHANNELS
        }
        if position not in self._tiles:
            return result
        deltas = {
            "north": (0, 1),
            "south": (0, -1),
            "east": (1, 0),
            "west": (-1, 0),
        }
        for direction, delta in deltas.items():
            neighbor = (position[0] + delta[0], position[1] + delta[1])
            if neighbor not in self._tiles:
                for channel in DIRECTIONAL_CHANNELS:
                    result[channel][direction] = True
                continue
            edge = self.get_world_edge(position, neighbor)
            for channel in WorldEdgeChannel:
                result[channel.value][direction] = not (
                    self._world_edge_channel_allows(edge, channel)
                )
        return result

    def get_subjective_directional_block_map(
        self,
        position: Tuple[int, int],
        requesting_entity_uuid: UUID,
        movement_mode: MovementMode = MovementMode.WALKING,
    ) -> Dict[str, Dict[str, bool]]:
        """Derive observer-known movement sides and physical optical sides."""
        if BaseBlock.get(requesting_entity_uuid) is None:
            raise ValueError("subjective directional projection requires a known observer")
        result = self.get_directional_block_map(position)
        deltas = {
            "north": (0, 1),
            "south": (0, -1),
            "east": (1, 0),
            "west": (-1, 0),
        }
        for direction, delta in deltas.items():
            neighbor = (position[0] + delta[0], position[1] + delta[1])
            if neighbor not in self._tiles:
                continue
            result["movement"][direction] = not self._world_edge_channel_allows(
                self.get_world_edge(position, neighbor),
                WorldEdgeChannel.MOVEMENT,
                movement_mode=movement_mode,
                requester_uuid=requesting_entity_uuid,
                subjective=True,
            )
        return result

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
        if channel == "optical":
            return not self.is_blocking_optics(position[0], position[1])
        raise ValueError(f"Unsupported transition channel: {channel}")

    def _cardinal_transition_sides_allow(self, from_pos: Tuple[int, int], to_pos: Tuple[int, int],
                                         channel: str,
                                         requester_uuid: Optional[UUID] = None,
                                         movement_mode: MovementMode = MovementMode.WALKING,
                                         subjective: bool = False,
                                         directional_collision_blocked: Optional[Set[Tuple[Tuple[int, int], str]]] = None,
                                         side_cache: Optional[Dict[Tuple[Tuple[int, int], Tuple[int, int]], bool]] = None) -> bool:
        dx = abs(to_pos[0] - from_pos[0])
        dy = abs(to_pos[1] - from_pos[1])
        if dx + dy != 1:
            return False
        if from_pos not in self._tiles or to_pos not in self._tiles:
            return False
        if channel == "movement" and not self._remembered_transition_allows(from_pos, to_pos, directional_collision_blocked):
            return False
        try:
            world_channel = WorldEdgeChannel(channel)
        except ValueError as exc:
            raise ValueError(f"Unsupported world-edge channel: {channel}") from exc
        key = (from_pos, to_pos)
        if side_cache is not None and key in side_cache:
            return side_cache[key]
        result = self._world_edge_channel_allows(
            self.get_world_edge(from_pos, to_pos),
            world_channel,
            movement_mode=movement_mode,
            requester_uuid=requester_uuid,
            subjective=subjective,
        )
        if side_cache is not None:
            side_cache[key] = result
        return result

    @staticmethod
    def _world_edge_contribution_allows(
        contribution: WorldEdgeStructuralContribution,
        channel: WorldEdgeChannel,
        *,
        source_height: int,
        destination_height: int,
        movement_mode: MovementMode,
    ) -> bool:
        """Reduce one structural contribution for the requested channel."""
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

    def _world_edge_channel_allows(
        self,
        edge: WorldEdgeView,
        channel: WorldEdgeChannel,
        *,
        movement_mode: MovementMode = MovementMode.WALKING,
        requester_uuid: Optional[UUID] = None,
        subjective: bool = False,
    ) -> bool:
        """Require both ordered Tile-side layers to transmit one channel."""
        for contribution in (*edge.exit_contributions, *edge.entry_contributions):
            if (
                channel is WorldEdgeChannel.MOVEMENT
                and subjective
                and requester_uuid is not None
            ):
                requester = BaseBlock.get(requester_uuid)
                senses = requester.get_senses() if requester is not None else None
                if senses is not None and contribution.provider_uuid not in senses.objects:
                    continue
            if not self._world_edge_contribution_allows(
                contribution,
                channel,
                source_height=edge.source_height_steps,
                destination_height=edge.destination_height_steps,
                movement_mode=movement_mode,
            ):
                return False
        return True

    def _elevation_transition_allows(
        self,
        from_pos: Tuple[int, int],
        to_pos: Tuple[int, int],
        movement_mode: MovementMode,
    ) -> bool:
        """Apply the 2D support-height rule to one cardinal movement leg."""
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
        """Return the destination-policy cost for one admitted movement edge."""
        from_tile = self._tiles.get(from_pos)
        to_tile = self._tiles.get(to_pos)
        if from_tile is None or to_tile is None:
            raise ValueError("movement edge cost requires both support Tiles")
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
                                    movement_cell_cache: Optional[Dict[Tuple[int, int], bool]] = None) -> bool:
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
                )
                and self._cardinal_transition_sides_allow(
                    bridge, to_pos, channel, requester_uuid, movement_mode,
                    subjective, directional_collision_blocked, side_cache,
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
                       movement_cell_cache: Optional[Dict[Tuple[int, int], bool]] = None) -> bool:
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
        """Return whether ordinary light and sight cross one adjacent edge."""
        if abs(to_pos[0] - from_pos[0]) == 1 and abs(to_pos[1] - from_pos[1]) == 1:
            return self._diagonal_transition_allows(
                from_pos,
                to_pos,
                "optical",
            )
        return self._cardinal_transition_sides_allow(
            from_pos,
            to_pos,
            "optical",
        )

    def can_propagate_transition(self, from_pos: Tuple[int, int], to_pos: Tuple[int, int],
                                 requester_uuid: Optional[UUID] = None,
                                 subjective: bool = False) -> bool:
        if abs(to_pos[0] - from_pos[0]) == 1 and abs(to_pos[1] - from_pos[1]) == 1:
            return self._diagonal_transition_allows(from_pos, to_pos, "propagation", requester_uuid, subjective=subjective)
        return self._cardinal_transition_sides_allow(
            from_pos,
            to_pos,
            "propagation",
            requester_uuid,
            subjective=subjective,
        )

    def identify_blocker_at(self, position: Tuple[int, int],
                            requesting_entity_uuid: Optional[UUID] = None,
                            mode: MovementMode = MovementMode.WALKING) -> str:
        """Identify what's blocking movement at a position.

        Call this after is_walkable_for() returned False to get a descriptive
        name for the blocker. Checks in the same order as is_walkable_for():
        1. Tile itself (missing = "edge of map", blocks_walking = tile.name)
        2. Entity at position
        3. Object at position
        4. Fallback: "obstacle"
        """
        tile = self._tiles.get(position)
        if tile is None:
            return "edge of map"
        if tile.blocks_walking(mode=mode):
            return tile.name

        for entity_uuid in self.get_entities_at(position):
            block = BaseBlock.get(entity_uuid)
            if block is not None and block.blocks_walking(requesting_entity_uuid, mode):
                return block.name

        for obj_uuid in self.get_objects_at(position):
            block = BaseBlock.get(obj_uuid)
            if block is not None and block.blocks_walking(requesting_entity_uuid, mode):
                return block.name

        for condition in self.get_spatial_conditions_at(position):
            if condition.blocks_walking_at(
                position,
                requesting_entity_uuid,
                mode,
            ):
                return condition.name or "spatial condition"

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
        *,
        blocks_optics: bool = False,
        blocks_propagation: bool = False,
        name: str = "Floor",
        sprite_name: Optional[str] = None,
        walking_cost: int = 1,
        flying_cost: int = 1,
        swimming_cost: int = 0,
        burrowing_cost: int = 0,
        default_light: LightLevel = LightLevel.BRIGHT_LIGHT,
    ) -> None:
        """Create a rectangular area of tiles (batch operation, no events during)."""
        positions = {
            (tx, ty)
            for tx in range(x, x + width)
            for ty in range(y, y + height)
        }
        for position in positions:
            old_tile = self._tiles.get(position)
            if old_tile is not None and old_tile.get_entity_uuids():
                raise ValueError(
                    f"cannot replace Tile {position} while entity occupancy is present"
                )
        events_were_enabled = self._events_enabled
        self.disable_events()
        try:
            for tx in range(x, x + width):
                for ty in range(y, y + height):
                    old_tile = self._tiles.get((tx, ty))
                    if old_tile:
                        self._tiles_by_uuid.pop(old_tile.uuid, None)
                        BaseBlock.unregister(old_tile.uuid)

                    tile = Tile.create(
                        position=(tx, ty),
                        blocks_optics=blocks_optics,
                        blocks_propagation=blocks_propagation,
                        name=name,
                        sprite_name=sprite_name,
                        walking_cost=walking_cost,
                        flying_cost=flying_cost,
                        swimming_cost=swimming_cost,
                        burrowing_cost=burrowing_cost,
                        default_light=default_light,
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
    ) -> None:
        """Atomically replace one Entity UUID across authoritative Tiles."""
        if not self._events_enabled:
            raise PositionCommitError(
                ValueError("Entity occupancy requires enabled GridMap events")
            )
        try:
            self._validate_entity_position(expected_old_position)
            self._validate_entity_position(new_position)
        except ValueError as exc:
            raise PositionCommitError(exc) from exc
        block = BaseBlock.get(entity_uuid)
        if block is None:
            raise PositionCommitError(
                ValueError(f"entity identity {entity_uuid} is not registered")
            )
        if new_position is not None and block.get_position() != new_position:
            raise PositionCommitError(
                ValueError("Entity objective position does not match destination")
            )
        if expected_old_position is not None and block.get_position() not in {
            expected_old_position,
            new_position,
        }:
            raise PositionCommitError(
                ValueError("Entity objective position does not match transition")
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
            old_tile is not None
            and entity_uuid not in old_tile.get_entity_uuids()
        ):
            raise PositionCommitError(
                ValueError("source Tile does not contain the Entity UUID")
            )
        if (
            new_tile is not None
            and new_position != expected_old_position
            and entity_uuid in new_tile.get_entity_uuids()
        ):
            raise PositionCommitError(
                ValueError("destination Tile already contains the Entity UUID")
            )
        if expected_old_position == new_position:
            return

        old_members = old_tile.get_entity_uuids() if old_tile is not None else None
        new_members = new_tile.get_entity_uuids() if new_tile is not None else None
        try:
            if old_tile is not None and old_members is not None:
                old_tile._replace_entity_uuids(old_members - {entity_uuid})
            if new_tile is not None and new_members is not None:
                new_tile._replace_entity_uuids(new_members | {entity_uuid})
            self.invalidate_occupancy_paths()
        except BaseException as exc:
            if old_tile is not None and old_members is not None:
                old_tile._replace_entity_uuids(old_members)
            if new_tile is not None and new_members is not None:
                new_tile._replace_entity_uuids(new_members)
            raise PositionCommitError(exc) from exc

    def _publish_entity_membership(
        self,
        entity_uuid: UUID,
        old_position: Optional[Tuple[int, int]],
        new_position: Optional[Tuple[int, int]],
        *,
        parent_event: Optional[UUID] = None,
    ) -> None:
        """Publish LEFT then ENTERED for one already committed membership."""
        if old_position == new_position:
            return
        if old_position is not None:
            old_tile = self._tiles.get(old_position)
            if (
                old_tile is not None
                and entity_uuid in old_tile.get_entity_uuids()
            ):
                raise ValueError("source membership is still committed")
        if new_position is not None:
            tile = self._tiles.get(new_position)
            if tile is None or entity_uuid not in tile.get_entity_uuids():
                raise ValueError("destination membership is not committed")
        if old_position is not None:
            self._fire_committed_spatial_event(
                SpatialChangeEvent.entity_left(
                    old_position,
                    entity_uuid,
                    new_position,
                    parent_event=parent_event,
                )
            )
        if new_position is not None:
            self._fire_committed_spatial_event(
                SpatialChangeEvent.entity_entered(
                    new_position,
                    entity_uuid,
                    old_position,
                    parent_event=parent_event,
                )
            )

    def get_entity_position(self, entity_uuid: UUID) -> Optional[Tuple[int, int]]:
        """Return a coordinate only for a present Tile member."""
        block = BaseBlock.get(entity_uuid)
        if block is None:
            return None
        position = block.get_position()
        try:
            self._validate_entity_position(position, allow_none=False)
        except ValueError:
            return None
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
                    f"Tile membership {entity_uuid} does not match {position}"
                )
        return entity_uuids

    def get_all_object_positions(self) -> Dict[UUID, Tuple[int, int]]:
        """Return a derived UUID-to-position snapshot."""
        return {
            object_uuid: placement.position
            for object_uuid, placement in self._object_placements.items()
        }

    def _object_placement_candidate(
        self,
        object_uuid: UUID,
        position: Tuple[int, int],
        *,
        boundary_direction: Optional[CardinalDirection] = None,
        base_height_steps: Optional[int] = None,
        orientation: Optional[CardinalDirection] = None,
    ) -> WorldObjectPlacement:
        """Build and validate one complete placement candidate."""
        if (
            type(position) is not tuple
            or len(position) != 2
            or any(type(value) is not int for value in position)
        ):
            raise TypeError("object position must be an exact two-integer tuple")
        tile = self._tiles.get(position)
        if tile is None:
            raise ValueError(f"cannot place object on missing Tile {position}")
        obj = BaseBlock.get(object_uuid)
        if obj is None:
            raise ValueError(f"cannot place missing object {object_uuid}")
        spec = obj.get_world_placement_spec()
        if spec.kind is WorldPlacementKind.CENTER:
            if boundary_direction is not None:
                raise ValueError(
                    "center placement cannot define boundary_direction"
                )
        elif boundary_direction is None:
            raise ValueError("boundary placement requires boundary_direction")
        if base_height_steps is None:
            base_height_steps = tile.height
        if type(base_height_steps) is not int:
            raise TypeError("base_height_steps must be an exact integer")
        candidate = WorldObjectPlacement(
            object_uuid=object_uuid,
            tile_uuid=tile.uuid,
            position=position,
            kind=spec.kind,
            occupies_bands=spec.occupies_bands,
            boundary_direction=boundary_direction,
            base_height_steps=base_height_steps,
            top_height_steps=base_height_steps + spec.vertical_extent_steps,
            orientation=orientation,
        )
        self._validate_placement_collision(candidate)
        return candidate

    def _placement_band(
        self,
        tile: Tile,
        placement: WorldObjectPlacement,
        height: int,
    ) -> Optional[TileObjectBand]:
        """Return one exact local band used by a placement."""
        if placement.kind is WorldPlacementKind.CENTER:
            return dict(tile.get_center_object_bands()).get(height)
        assert placement.boundary_direction is not None
        return dict(
            tile.get_boundary_object_bands(placement.boundary_direction)
        ).get(height)

    def _validate_placement_collision(
        self,
        placement: WorldObjectPlacement,
    ) -> None:
        """Reject only occupied bands on the exact owner Tile and side."""
        tile = self._tiles.get(placement.position)
        if tile is None or tile.uuid != placement.tile_uuid:
            raise ValueError("placement support Tile is no longer current")
        for height in range(
            placement.base_height_steps,
            placement.top_height_steps,
        ):
            band = self._placement_band(tile, placement, height)
            if (
                placement.occupies_bands
                and band is not None
                and band.occupant_uuid not in (None, placement.object_uuid)
            ):
                raise ValueError(
                    "object placement collides with an occupied local band"
                )

    def validate_object_placement(
        self,
        object_uuid: UUID,
        position: Tuple[int, int],
        *,
        boundary_direction: Optional[CardinalDirection] = None,
        base_height_steps: Optional[int] = None,
        orientation: Optional[CardinalDirection] = None,
    ) -> WorldObjectPlacement:
        """Return the exact candidate accepted by the commit path."""
        return self._object_placement_candidate(
            object_uuid,
            position,
            boundary_direction=boundary_direction,
            base_height_steps=base_height_steps,
            orientation=orientation,
        )

    def _replace_placement_bands(
        self,
        placement: WorldObjectPlacement,
        *,
        add: bool,
    ) -> None:
        """Replace every immutable local band touched by one placement."""
        tile = self._tiles[placement.position]
        for height in range(
            placement.base_height_steps,
            placement.top_height_steps,
        ):
            old = self._placement_band(tile, placement, height)
            object_uuids = set(old.object_uuids if old is not None else ())
            occupant_uuid = old.occupant_uuid if old is not None else None
            if add:
                object_uuids.add(placement.object_uuid)
                if placement.occupies_bands:
                    occupant_uuid = placement.object_uuid
            else:
                object_uuids.discard(placement.object_uuid)
                if occupant_uuid == placement.object_uuid:
                    occupant_uuid = None
            band = (
                TileObjectBand(
                    object_uuids=frozenset(object_uuids),
                    occupant_uuid=occupant_uuid,
                )
                if object_uuids or occupant_uuid is not None
                else None
            )
            if placement.kind is WorldPlacementKind.CENTER:
                tile._replace_center_object_band(height, band)
            else:
                assert placement.boundary_direction is not None
                tile._replace_boundary_object_band(
                    placement.boundary_direction,
                    height,
                    band,
                )

    def _accept_event_effect(
        self,
        declaration: Event,
    ) -> Optional[Event]:
        """Publish vetoable phases and return the accepted owner effect."""
        current = EventQueue.register(declaration)
        if current.canceled:
            return None
        current = EventQueue.register(
            current.phase_to(EventPhase.EXECUTION)
        )
        if current.canceled:
            return None
        current = EventQueue.register(current.phase_to(EventPhase.EFFECT))
        return None if current.canceled else current

    def _complete_event_effect(
        self,
        effect: Event,
    ) -> Event:
        """Publish completion after the owning GridMap state is committed."""
        self._recompute_lights_before_spatial_completion(effect)
        completion_updates: Dict[str, Any] = {}
        if (
            isinstance(effect, SpatialChangeEvent)
            and effect.change_type is SpatialChangeType.TILE_CHANGED
            and (tile := self._tiles.get(effect.position)) is not None
        ):
            completion_updates["new_light_level"] = (
                tile.resolved_light_level.value
            )
        return EventQueue.register(
            effect.phase_to(
                EventPhase.COMPLETION,
                **completion_updates,
            )
        )

    def _recompute_lights_before_spatial_completion(self, effect: Event) -> None:
        """Publish committed optical light deltas before their parent freezes."""
        if not isinstance(effect, SpatialChangeEvent):
            return
        if effect.event_type == EventType.SPATIAL_LIGHT_CHANGED:
            return
        hint = effect.senses_hint
        if hint is None or not hint.requires_light_recompute:
            return
        self.recompute_lights_at_position(
            effect.position,
            parent_event=effect.uuid,
        )

    @staticmethod
    def _boundary_revision_channels(
        channels: Tuple[WorldEdgeChannel, ...],
    ) -> Set[str]:
        """Map structural channels onto current spatial cache domains."""
        revisions: Set[str] = set()
        if WorldEdgeChannel.MOVEMENT in channels:
            revisions.add("movement")
        if WorldEdgeChannel.OPTICAL in channels:
            revisions.add("optical")
        if WorldEdgeChannel.PROPAGATION in channels:
            revisions.add("propagation")
        return revisions

    def _object_revision_channels(self, obj: BaseBlock) -> Set[str]:
        channels: Set[str] = set()
        if obj.blocks_optics_at_center():
            channels.add("optical")
        if obj.blocks_propagation():
            channels.add("propagation")
        if obj.blocks_walking():
            channels.add("movement")
        structure = obj.get_boundary_structure()
        if structure is not None:
            channels.update(
                self._boundary_revision_channels(structure.blocked_channels)
            )
        return channels

    def _boundary_event_metadata(
        self,
        placement: WorldObjectPlacement,
        structure: Optional[BoundaryStructure],
    ) -> Dict[str, Any]:
        """Return exact legacy hint fields derived from one boundary fact."""
        if (
            placement.kind is not WorldPlacementKind.BOUNDARY
            or placement.boundary_direction is None
            or structure is None
        ):
            return {}
        return {
            "directional_position": placement.position,
            "directional_directions": [
                placement.boundary_direction.value
            ],
            "directional_channels": sorted(
                self._boundary_revision_channels(
                    structure.blocked_channels
                )
            ),
        }

    def place_object(
        self,
        object_uuid: UUID,
        position: Tuple[int, int],
        parent_event: Optional[UUID] = None,
        *,
        boundary_direction: Optional[CardinalDirection] = None,
        base_height_steps: Optional[int] = None,
        orientation: Optional[CardinalDirection] = None,
    ) -> WorldObjectPlacement:
        """Commit the first exact placement of one registered object."""
        candidate = self._object_placement_candidate(
            object_uuid,
            position,
            boundary_direction=boundary_direction,
            base_height_steps=base_height_steps,
            orientation=orientation,
        )
        old = self._object_placements.get(object_uuid)
        if old is not None:
            if old == candidate:
                return old
            raise ValueError("object is already placed; use move_object")
        obj = BaseBlock.get(object_uuid)
        assert obj is not None
        structure = obj.get_boundary_structure()
        declaration = SpatialChangeEvent.object_placed(
            position,
            object_uuid,
            candidate,
            parent_event=parent_event,
            blocks_optics=obj.blocks_optics_at_center(),
            blocks_propagation=obj.blocks_propagation(),
            blocks_walking=obj.blocks_walking(),
            object_name=obj.name,
            object_map_char=obj.get_map_char(),
            object_boundary_structure=structure,
            **self._boundary_event_metadata(candidate, structure),
        )
        effect = (
            self._accept_event_effect(declaration)
            if self._events_enabled
            else None
        )
        if self._events_enabled and effect is None:
            raise ValueError("object placement was canceled")
        self._replace_placement_bands(candidate, add=True)
        self._object_placements[object_uuid] = candidate
        self._bump_spatial_revisions(self._object_revision_channels(obj))
        if effect is not None:
            self._complete_event_effect(effect)
        return candidate

    def move_object(
        self,
        object_uuid: UUID,
        position: Tuple[int, int],
        parent_event: Optional[UUID] = None,
        *,
        boundary_direction: Optional[CardinalDirection] = None,
        base_height_steps: Optional[int] = None,
        orientation: Optional[CardinalDirection] = None,
    ) -> WorldObjectPlacement:
        """Atomically replace one existing exact placement."""
        previous = self._object_placements.get(object_uuid)
        if previous is None:
            raise ValueError("object is not placed; use place_object")
        candidate = self._object_placement_candidate(
            object_uuid,
            position,
            boundary_direction=boundary_direction,
            base_height_steps=base_height_steps,
            orientation=orientation,
        )
        if candidate == previous:
            return previous
        obj = BaseBlock.get(object_uuid)
        assert obj is not None
        structure = obj.get_boundary_structure()
        departure = SpatialChangeEvent.object_removed(
            previous.position,
            object_uuid,
            previous,
            parent_event=parent_event,
            blocks_optics=obj.blocks_optics_at_center(),
            blocks_propagation=obj.blocks_propagation(),
            blocks_walking=obj.blocks_walking(),
            object_boundary_structure=structure,
            **self._boundary_event_metadata(previous, structure),
        ).with_updates(old_position=candidate.position)
        arrival = SpatialChangeEvent.object_placed(
            candidate.position,
            object_uuid,
            candidate,
            previous_placement=previous,
            parent_event=parent_event,
            blocks_optics=obj.blocks_optics_at_center(),
            blocks_propagation=obj.blocks_propagation(),
            blocks_walking=obj.blocks_walking(),
            object_name=obj.name,
            object_map_char=obj.get_map_char(),
            object_boundary_structure=structure,
            **self._boundary_event_metadata(candidate, structure),
        ).with_updates(old_position=previous.position)
        departure_effect = (
            self._accept_event_effect(departure)
            if self._events_enabled
            else None
        )
        if self._events_enabled and departure_effect is None:
            raise ValueError("object relocation departure was canceled")
        arrival_effect = (
            self._accept_event_effect(arrival)
            if self._events_enabled
            else None
        )
        if self._events_enabled and arrival_effect is None:
            raise ValueError("object relocation arrival was canceled")
        self._replace_placement_bands(previous, add=False)
        self._replace_placement_bands(candidate, add=True)
        self._object_placements[object_uuid] = candidate
        self._bump_spatial_revisions(self._object_revision_channels(obj))
        if departure_effect is not None:
            self._complete_event_effect(departure_effect)
        if arrival_effect is not None:
            self._complete_event_effect(arrival_effect)
        return candidate

    def orient_object(
        self,
        object_uuid: UUID,
        orientation: Optional[CardinalDirection],
        parent_event: Optional[UUID] = None,
    ) -> WorldObjectPlacement:
        """Change only one placed object's independent facing fact."""
        previous = self._object_placements.get(object_uuid)
        if previous is None:
            raise ValueError("object is not placed")
        candidate = self._object_placement_candidate(
            object_uuid,
            previous.position,
            boundary_direction=previous.boundary_direction,
            base_height_steps=previous.base_height_steps,
            orientation=orientation,
        )
        if candidate == previous:
            return previous
        obj = BaseBlock.get(object_uuid)
        if obj is None:
            raise ValueError(f"placed object {object_uuid} is not registered")
        declaration = SpatialChangeEvent.object_changed(
            previous.position,
            object_uuid,
            placement=candidate,
            previous_placement=previous,
            parent_event=parent_event,
            object_name=obj.name,
            object_map_char=obj.get_map_char(),
            object_blocks_movement=obj.blocks_walking(),
            object_blocks_optics=obj.blocks_optics_at_center(),
            object_blocks_propagation=obj.blocks_propagation(),
        )
        effect = (
            self._accept_event_effect(declaration)
            if self._events_enabled
            else None
        )
        if self._events_enabled and effect is None:
            raise ValueError("object orientation change was canceled")
        self._object_placements[object_uuid] = candidate
        if effect is not None:
            self._complete_event_effect(effect)
        return candidate

    def remove_object(
        self,
        object_uuid: UUID,
        parent_event: Optional[UUID] = None,
        clear_object_location: bool = True,
    ) -> bool:
        """Terminally remove one exact placement."""
        previous = self._object_placements.get(object_uuid)
        if previous is None:
            return False
        obj = BaseBlock.get(object_uuid)
        if obj is None:
            raise ValueError(f"placed object {object_uuid} is not registered")
        declaration = SpatialChangeEvent.object_removed(
            previous.position,
            object_uuid,
            previous,
            parent_event=parent_event,
            blocks_optics=obj.blocks_optics_at_center(),
            blocks_propagation=obj.blocks_propagation(),
            blocks_walking=obj.blocks_walking(),
            object_boundary_structure=obj.get_boundary_structure(),
            **self._boundary_event_metadata(
                previous,
                obj.get_boundary_structure(),
            ),
        )
        effect = (
            self._accept_event_effect(declaration)
            if self._events_enabled
            else None
        )
        if self._events_enabled and effect is None:
            return False
        self._replace_placement_bands(previous, add=False)
        del self._object_placements[object_uuid]
        obj.on_grid_object_removed(
            previous.position,
            clear_location=clear_object_location,
        )
        self._bump_spatial_revisions(self._object_revision_channels(obj))
        if effect is not None:
            self._complete_event_effect(effect)
        return True

    def update_object_boundary_structure(
        self,
        object_uuid: UUID,
        structure: BoundaryStructure,
        *,
        previous_structure: Optional[BoundaryStructure] = None,
        parent_event: Optional[UUID] = None,
    ) -> None:
        """Publish one committed boundary-structure change in place."""
        placement = self._object_placements.get(object_uuid)
        if placement is None:
            return
        provider = BaseBlock.get(object_uuid)
        if (
            provider is None
            or placement.kind is not WorldPlacementKind.BOUNDARY
        ):
            raise ValueError(
                "boundary structure requires a placed boundary provider"
            )
        if previous_structure is None:
            raise ValueError(
                "a placed boundary structure change requires its previous value"
            )
        if provider.get_boundary_structure() != structure:
            raise ValueError(
                "boundary structure must match the provider's current state"
            )
        changed_world_channels = tuple(
            channel
            for channel in WorldEdgeChannel
            if (
                (channel in previous_structure.blocked_channels)
                != (channel in structure.blocked_channels)
            )
        )
        changed_channels = self._boundary_revision_channels(
            changed_world_channels
        )
        self._bump_spatial_revisions(changed_channels)
        if not self._events_enabled:
            return
        assert placement.boundary_direction is not None
        self._fire_spatial_event(
            SpatialChangeEvent.object_changed(
                placement.position,
                object_uuid,
                blocks_optics_changed="optical" in changed_channels,
                blocks_propagation_changed="propagation" in changed_channels,
                blocks_walking_changed="movement" in changed_channels,
                placement=placement,
                previous_placement=placement,
                parent_event=parent_event,
                object_name=provider.name,
                object_map_char=provider.get_map_char(),
                object_blocks_movement=provider.blocks_walking(),
                object_blocks_optics=provider.blocks_optics_at_center(),
                object_blocks_propagation=provider.blocks_propagation(),
                object_is_open=provider.get_spatial_open_state(),
                object_boundary_structure=structure,
                directional_position=placement.position,
                directional_directions=[placement.boundary_direction.value],
                directional_channels=sorted(changed_channels),
            )
        )

    def get_objects_at(self, position: Tuple[int, int]) -> Set[UUID]:
        """Return objects from the exact Tile's local center and side bands."""
        tile = self._tiles.get(position)
        if tile is None:
            return set()
        object_uuids: Set[UUID] = set()
        for _, band in tile.get_center_object_bands():
            object_uuids.update(band.object_uuids)
        for direction in CardinalDirection:
            for _, band in tile.get_boundary_object_bands(direction):
                object_uuids.update(band.object_uuids)
        return object_uuids

    def get_center_objects_at(
        self,
        position: Tuple[int, int],
        height: Optional[int] = None,
    ) -> Set[UUID]:
        """Return exact center-band members on one Tile."""
        tile = self._tiles.get(position)
        if tile is None:
            return set()
        bands = tile.get_center_object_bands()
        if height is not None:
            band = dict(bands).get(height)
            return set(band.object_uuids) if band is not None else set()
        return {
            object_uuid
            for _, band in bands
            for object_uuid in band.object_uuids
        }

    def get_boundary_objects_at(
        self,
        position: Tuple[int, int],
        direction: CardinalDirection,
        height: Optional[int] = None,
    ) -> Set[UUID]:
        """Return exact side-band members on one owner Tile."""
        tile = self._tiles.get(position)
        if tile is None:
            return set()
        bands = tile.get_boundary_object_bands(direction)
        if height is not None:
            band = dict(bands).get(height)
            return set(band.object_uuids) if band is not None else set()
        return {
            object_uuid
            for _, band in bands
            for object_uuid in band.object_uuids
        }

    def get_object_placement(
        self,
        object_uuid: UUID,
    ) -> Optional[WorldObjectPlacement]:
        """Return one immutable exact placement, if present."""
        return self._object_placements.get(object_uuid)

    def iter_object_placements(self) -> Tuple[WorldObjectPlacement, ...]:
        """Return a deterministic immutable snapshot of all placements."""
        return tuple(
            self._object_placements[object_uuid]
            for object_uuid in sorted(self._object_placements, key=str)
        )

    def get_object_position(self, object_uuid: UUID) -> Optional[Tuple[int, int]]:
        """Get an object's grid position, or None if not placed."""
        placement = self._object_placements.get(object_uuid)
        return placement.position if placement is not None else None

    @staticmethod
    def _opposite_direction(
        direction: CardinalDirection,
    ) -> CardinalDirection:
        """Return the opposite member of the one canonical direction enum."""
        return {
            CardinalDirection.NORTH: CardinalDirection.SOUTH,
            CardinalDirection.SOUTH: CardinalDirection.NORTH,
            CardinalDirection.EAST: CardinalDirection.WEST,
            CardinalDirection.WEST: CardinalDirection.EAST,
        }[direction]

    @staticmethod
    def _transition_direction(
        source: Tuple[int, int],
        destination: Tuple[int, int],
    ) -> CardinalDirection:
        """Return the source-owned side crossed by one cardinal transition."""
        delta = (
            destination[0] - source[0],
            destination[1] - source[1],
        )
        try:
            return {
                (0, 1): CardinalDirection.NORTH,
                (0, -1): CardinalDirection.SOUTH,
                (1, 0): CardinalDirection.EAST,
                (-1, 0): CardinalDirection.WEST,
            }[delta]
        except KeyError as error:
            raise ValueError(
                "world-edge endpoints must be cardinally adjacent"
            ) from error

    def _boundary_contributions(
        self,
        position: Tuple[int, int],
        direction: CardinalDirection,
    ) -> Tuple[WorldEdgeStructuralContribution, ...]:
        """Derive one exact owner-Tile side layer from placed providers."""
        contributions: List[WorldEdgeStructuralContribution] = []
        for provider_uuid in sorted(
            self.get_boundary_objects_at(position, direction),
            key=str,
        ):
            provider = BaseBlock.get(provider_uuid)
            placement = self._object_placements.get(provider_uuid)
            if provider is None or placement is None:
                continue
            if (
                placement.kind is not WorldPlacementKind.BOUNDARY
                or placement.position != position
                or placement.boundary_direction is not direction
            ):
                continue
            structure = provider.get_boundary_structure()
            if structure is None:
                continue
            contributions.append(
                WorldEdgeStructuralContribution(
                    provider_uuid=provider_uuid,
                    base_height_steps=placement.base_height_steps,
                    top_height_steps=placement.top_height_steps,
                    blocked_channels=structure.blocked_channels,
                )
            )
        return tuple(contributions)

    def get_world_edge(
        self,
        source: Tuple[int, int],
        destination: Tuple[int, int],
    ) -> WorldEdgeView:
        """Derive one ordered edge from the two incident Tile-side layers."""
        key = AdjacentEdgeKey.between(source, destination)
        source_tile = self._tiles.get(source)
        destination_tile = self._tiles.get(destination)
        if source_tile is None or destination_tile is None:
            raise ValueError(
                "world-edge endpoints must both have supporting Tiles"
            )
        exit_direction = self._transition_direction(source, destination)
        entry_direction = self._opposite_direction(exit_direction)
        return WorldEdgeView(
            key=key,
            source_position=source,
            destination_position=destination,
            source_tile_uuid=source_tile.uuid,
            destination_tile_uuid=destination_tile.uuid,
            source_height_steps=source_tile.height,
            destination_height_steps=destination_tile.height,
            elevation_delta_steps=(
                destination_tile.height - source_tile.height
            ),
            source_surface_kind=source_tile.elevation_surface_kind,
            destination_surface_kind=destination_tile.elevation_surface_kind,
            source_slope_axis=source_tile.slope_axis,
            destination_slope_axis=destination_tile.slope_axis,
            exit_direction=exit_direction,
            entry_direction=entry_direction,
            exit_contributions=self._boundary_contributions(
                source,
                exit_direction,
            ),
            entry_contributions=self._boundary_contributions(
                destination,
                entry_direction,
            ),
        )

    def get_boundary_route_layers(
        self,
        source: Tuple[int, int],
        direction: CardinalDirection,
        channel: WorldEdgeChannel,
    ) -> Tuple[Tuple[UUID, ...], Tuple[UUID, ...]]:
        """Return boundary objects reached from one perceivable endpoint."""
        if source not in self._tiles:
            raise ValueError("boundary route source must have a supporting Tile")
        if type(direction) is not CardinalDirection:
            raise TypeError("boundary route direction must be a CardinalDirection")
        if channel not in {
            WorldEdgeChannel.OPTICAL,
            WorldEdgeChannel.PROPAGATION,
        }:
            raise ValueError("boundary route channel must be optical or propagation")
        exit_layer = tuple(sorted(
            self.get_boundary_objects_at(source, direction),
            key=str,
        ))
        delta = {
            CardinalDirection.NORTH: (0, 1),
            CardinalDirection.SOUTH: (0, -1),
            CardinalDirection.EAST: (1, 0),
            CardinalDirection.WEST: (-1, 0),
        }[direction]
        destination = (source[0] + delta[0], source[1] + delta[1])
        if destination not in self._tiles:
            return exit_layer, ()
        edge = self.get_world_edge(source, destination)
        if not all(
            self._world_edge_contribution_allows(
                contribution,
                channel,
                source_height=edge.source_height_steps,
                destination_height=edge.destination_height_steps,
                movement_mode=MovementMode.WALKING,
            )
            for contribution in edge.exit_contributions
        ):
            return exit_layer, ()
        return exit_layer, tuple(sorted(
            self.get_boundary_objects_at(
                destination,
                self._opposite_direction(direction),
            ),
            key=str,
        ))

    def get_objects_with_conditions(self) -> List[BaseBlock]:
        """Get placed objects with active conditions (for environment step).

        Returns BaseBlock (not BaseItem) — GridMap stays type-unaware.
        """
        result: List[BaseBlock] = []
        for obj_uuid in self._object_placements:
            block = BaseBlock.get(obj_uuid)
            if block is not None and block.active_conditions:
                result.append(block)
        return result

    def _has_directional_blockers(self, channel: str) -> bool:
        """Return whether any placed boundary blocks the canonical channel."""
        cached = self._directional_blockers_cache.get(channel)
        if cached is not None:
            return cached
        world_channel = WorldEdgeChannel(channel)
        for object_uuid, placement in self._object_placements.items():
            if placement.kind is not WorldPlacementKind.BOUNDARY:
                continue
            provider = BaseBlock.get(object_uuid)
            structure = (
                provider.get_boundary_structure()
                if provider is not None
                else None
            )
            if (
                structure is not None
                and world_channel in structure.blocked_channels
            ):
                self._directional_blockers_cache[channel] = True
                return True
        self._directional_blockers_cache[channel] = False
        return False

    def _transition_clear(
        self,
        start: Tuple[int, int],
        end: Tuple[int, int],
        channel: str,
    ) -> bool:
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
            elif channel == "propagation":
                if not self.can_propagate_transition(prev, current):
                    return False
                blocks_cell = self.is_blocking_propagation(current[0], current[1])
            else:
                raise ValueError(f"Unsupported raycast channel: {channel}")

            if index < len(path) - 1 and blocks_cell:
                return False
        return True

    def raycast_clear(
        self,
        start: Tuple[int, int],
        end: Tuple[int, int],
        channel: str = "optical",
    ) -> bool:
        """Public transition-aware line check for physical topology."""
        return self._transition_clear(start, end, channel)

    def _compute_directional_fov(
        self,
        origin: Tuple[int, int],
        max_distance: Optional[float],
        channel: str,
    ) -> List[Tuple[int, int]]:
        timing = action_timing_enabled()
        total_started = time.perf_counter() if timing else 0.0
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
        if channel == "propagation":
            transition_cache = self._propagation_transition_cache
            blocking_cache = self._propagation_blocking_cache
        elif channel == "optical":
            cache_key = (channel, self._optical_revision)
            transition_cache = self._directional_transition_cache.setdefault(
                cache_key,
                {},
            )
            blocking_cache = self._directional_blocking_cache.setdefault(
                cache_key,
                {},
            )
        else:
            transition_cache: Dict[Tuple[Tuple[int, int], Tuple[int, int]], bool] = {}
            blocking_cache: Dict[Tuple[int, int], bool] = {}
        line_seconds = 0.0
        transition_seconds = 0.0
        blocking_seconds = 0.0

        def get_line_offsets(end: Tuple[int, int]) -> Tuple[Tuple[int, int], ...]:
            nonlocal line_seconds
            key = (end[0] - origin[0], end[1] - origin[1])
            cached = line_cache.get(key)
            if cached is not None:
                return cached
            started = time.perf_counter() if timing else 0.0
            path = supercover_line_offsets(key)
            if timing:
                line_seconds += time.perf_counter() - started
            line_cache[key] = path
            return path

        def transition_allows(prev: Tuple[int, int], current: Tuple[int, int]) -> bool:
            nonlocal transition_seconds
            key = (prev, current)
            cached = transition_cache.get(key)
            if cached is not None:
                return cached
            started = time.perf_counter() if timing else 0.0
            if channel == "optical":
                allowed = self.can_optical_transition(prev, current)
            else:
                allowed = self.can_propagate_transition(prev, current)
            if timing:
                transition_seconds += time.perf_counter() - started
            transition_cache[key] = allowed
            return allowed

        def blocks_cell(position: Tuple[int, int]) -> bool:
            nonlocal blocking_seconds
            cached = blocking_cache.get(position)
            if cached is not None:
                return cached
            started = time.perf_counter() if timing else 0.0
            if channel == "optical":
                blocked = self.is_blocking_optics(position[0], position[1])
            else:
                blocked = self.is_blocking_propagation(position[0], position[1])
            if timing:
                blocking_seconds += time.perf_counter() - started
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
        if timing:
            record_action_elapsed("grid.directional_fov.supercover_line_ms", line_seconds)
            record_action_elapsed("grid.directional_fov.transition_checks_ms", transition_seconds)
            record_action_elapsed("grid.directional_fov.blocking_checks_ms", blocking_seconds)
            record_action_timing("grid.directional_fov.total_ms", total_started)
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
        timing = action_timing_enabled()
        cache_started = time.perf_counter() if timing else 0.0
        cache_key = (
            origin,
            max_distance,
            self._optical_revision,
        )
        cached = self._fov_cache.get(cache_key)
        if cached is not None:
            if timing:
                record_action_timing("grid.compute_fov.cache_hit_ms", cache_started)
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
                if timing:
                    record_action_timing("grid.compute_fov.cache_hit_ms", cache_started)
                return list(cached)
        if timing:
            record_action_timing("grid.compute_fov.cache_miss_ms", cache_started)

        visible_positions: List[Tuple[int, int]] = []
        blocking_cache: Dict[Tuple[int, int], bool] = {}

        def mark_visible(x: int, y: int) -> None:
            visible_positions.append((x, y))

        def is_blocking_for(x: int, y: int) -> bool:
            position = (x, y)
            cached = blocking_cache.get(position)
            if cached is not None:
                return cached
            blocked = self.is_blocking_optics(x, y)
            blocking_cache[position] = blocked
            return blocked

        if self._has_directional_blockers("optical"):
            visible_positions = self._compute_directional_fov(
                origin,
                max_distance,
                "optical",
            )
            self._fov_cache[cache_key] = list(visible_positions)
            return list(visible_positions)

        compute_fov(origin, is_blocking_for, mark_visible, max_distance)
        self._fov_cache[cache_key] = list(visible_positions)
        return list(visible_positions)

    def compute_light_fov(self, origin: Tuple[int, int], max_distance: Optional[float] = None) -> List[Tuple[int, int]]:
        """Compute ordinary light reach through the shared optical topology."""
        return self.compute_fov(origin, max_distance)

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
        if self._bounds_dirty:
            self._update_bounds()

        timing = action_timing_enabled()
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
        cache_started = time.perf_counter() if timing else 0.0
        cached = self._path_cache.get(cache_key)
        if cached is not None:
            self._path_cache.move_to_end(cache_key)
            if timing:
                record_action_timing("grid.compute_paths.cache_hit_ms", cache_started)
            cached_distances, cached_paths = cached
            return (
                dict(cached_distances),
                {position: list(path) for position, path in cached_paths.items()},
            )
        if timing:
            record_action_timing("grid.compute_paths.cache_miss_ms", cache_started)

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

        def raw_get_tile_cost(x: int, y: int) -> float:
            tile = self.get_tile(x, y)
            if not tile:
                return 0
            cost = tile.get_movement_cost(movement_mode)
            if ignore_difficult_terrain:
                return min(cost, 1.0)
            return cost

        def unit_movement_costs() -> bool:
            for tile in self._tiles.values():
                cost = tile.get_movement_cost(movement_mode)
                if ignore_difficult_terrain:
                    cost = min(cost, 1.0)
                if cost != 1:
                    return False
            return True

        def raw_can_enter_tile(from_pos: Tuple[int, int], to_pos: Tuple[int, int]) -> bool:
            return self.can_transition(
                from_pos, to_pos, requesting_entity_uuid, movement_mode,
                walk_in_danger, subjective, collision_blocked,
                directional_collision_blocked=directional_collision_blocked,
                side_cache=transition_side_cache,
                movement_cell_cache=walkable_cache,
            )

        walkable_cache: Dict[Tuple[int, int], bool] = {}
        tile_cost_cache: Dict[Tuple[int, int], float] = {}
        transition_cache: Dict[Tuple[Tuple[int, int], Tuple[int, int]], bool] = {}

        def cached_walkable_check(x: int, y: int) -> bool:
            key = (x, y)
            cached = walkable_cache.get(key)
            if cached is not None:
                return cached
            value = raw_walkable_check(x, y)
            walkable_cache[key] = value
            return value

        def cached_get_tile_cost(x: int, y: int) -> float:
            key = (x, y)
            cached = tile_cost_cache.get(key)
            if cached is not None:
                return cached
            value = raw_get_tile_cost(x, y)
            tile_cost_cache[key] = value
            return value

        def cached_can_enter_tile(from_pos: Tuple[int, int], to_pos: Tuple[int, int]) -> bool:
            key = (from_pos, to_pos)
            cached = transition_cache.get(key)
            if cached is not None:
                return cached
            value = raw_can_enter_tile(from_pos, to_pos)
            transition_cache[key] = value
            return value

        walkable_elapsed = 0.0
        tile_cost_elapsed = 0.0
        can_enter_elapsed = 0.0

        if timing:
            def walkable_check(x: int, y: int) -> bool:
                nonlocal walkable_elapsed
                started = time.perf_counter()
                try:
                    return cached_walkable_check(x, y)
                finally:
                    walkable_elapsed += time.perf_counter() - started

            def get_tile_cost(x: int, y: int) -> float:
                nonlocal tile_cost_elapsed
                started = time.perf_counter()
                try:
                    return cached_get_tile_cost(x, y)
                finally:
                    tile_cost_elapsed += time.perf_counter() - started

            def can_enter_tile(from_pos: Tuple[int, int], to_pos: Tuple[int, int]) -> bool:
                nonlocal can_enter_elapsed
                started = time.perf_counter()
                try:
                    return cached_can_enter_tile(from_pos, to_pos)
                finally:
                    can_enter_elapsed += time.perf_counter() - started
        else:
            walkable_check = cached_walkable_check
            get_tile_cost = cached_get_tile_cost
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
            return sentinel_result

        started = time.perf_counter() if timing else 0.0
        use_unit_pathfinder = unit_movement_costs()
        if use_unit_pathfinder:
            result = breadth_first_paths(
                start,
                walkable_check,
                grid_width,
                grid_height,
                diagonal=True,
                max_distance=max_distance,
                can_enter=can_enter_tile,
                min_x=self._min_x,
                min_y=self._min_y,
            )
        else:
            result = dijkstra(
                start,
                walkable_check,
                grid_width,
                grid_height,
                diagonal=True,
                max_distance=max_distance,
                cost_func=get_tile_cost,
                can_enter=can_enter_tile,
                min_x=self._min_x,
                min_y=self._min_y,
            )
        if timing:
            if use_unit_pathfinder:
                record_action_timing("grid.compute_paths.bfs_total_ms", started)
            record_action_timing("grid.compute_paths.dijkstra_total_ms", started)
            record_action_elapsed("grid.compute_paths.walkable_checks_ms", walkable_elapsed)
            record_action_elapsed("grid.compute_paths.tile_cost_ms", tile_cost_elapsed)
            record_action_elapsed("grid.compute_paths.can_enter_ms", can_enter_elapsed)
        distances, paths = result
        self._path_cache[cache_key] = (
            dict(distances),
            {position: tuple(path) for position, path in paths.items()},
        )
        if len(self._path_cache) > 128:
            self._path_cache.popitem(last=False)
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
        parent_event: Optional[UUID] = None,
    ) -> bool:
        """Set one Tile's objective ambient light through map ownership."""
        tile = self._tiles.get(position)
        if tile is None:
            raise ValueError(f"light Tile not found at {position}")
        old = tile.resolved_light_level
        tile.default_light = level
        if tile.resolved_light_level == old:
            return False
        self._fire_light_batch_events([position], parent_event=parent_event)
        return True

    def apply_light_modifier(
        self,
        source_uuid: UUID,
        positions: Set[Tuple[int, int]],
        level: LightLevel,
        *,
        cap: bool = False,
        parent_event: Optional[UUID] = None,
    ) -> Set[Tuple[int, int]]:
        """Apply one source-owned illumination or cap to existing Tiles."""
        changed: Set[Tuple[int, int]] = set()
        for position in positions:
            tile = self._tiles.get(position)
            if tile is None:
                continue
            did_change = (
                tile._add_illumination_cap(source_uuid, level)
                if cap
                else tile._add_illumination(source_uuid, level)
            )
            if did_change:
                changed.add(position)
        self._fire_light_batch_events(
            list(changed),
            parent_event=parent_event,
        )
        return changed

    def remove_light_modifier(
        self,
        source_uuid: UUID,
        positions: Set[Tuple[int, int]],
        parent_event: Optional[UUID] = None,
    ) -> Set[Tuple[int, int]]:
        """Remove one source-owned illumination fact from existing Tiles."""
        changed: Set[Tuple[int, int]] = set()
        for position in positions:
            tile = self._tiles.get(position)
            if tile is not None and tile._remove_light_modifier(source_uuid):
                changed.add(position)
        self._fire_light_batch_events(
            list(changed),
            parent_event=parent_event,
        )
        return changed

    def apply_optical_obscurement(
        self,
        source_uuid: UUID,
        positions: Set[Tuple[int, int]],
        obscurement: OpticalObscurement,
        *,
        parent_event: Optional[UUID] = None,
    ) -> Set[Tuple[int, int]]:
        """Install one source-owned conditional optical contribution."""
        normalized = {
            position for position in positions if position in self._tiles
        }
        previous = set(self._optical_obscurement_positions_by_source.get(
            source_uuid,
            set(),
        ))
        changed = {
            position
            for position in normalized
            if self._optical_obscurements_by_position[position].get(source_uuid)
            != obscurement
        }
        for position in normalized:
            self._optical_obscurements_by_position[position][source_uuid] = obscurement
        owned = previous | normalized
        if owned:
            self._optical_obscurement_positions_by_source[source_uuid] = owned
        if changed:
            self._publish_optical_obscurement_change(
                source_uuid,
                changed,
                parent_event,
            )
        return changed

    def remove_optical_obscurement(
        self,
        source_uuid: UUID,
        *,
        positions: Optional[Set[Tuple[int, int]]] = None,
        parent_event: Optional[UUID] = None,
    ) -> Set[Tuple[int, int]]:
        """Remove all or part of one source-owned optical contribution."""
        owned = set(self._optical_obscurement_positions_by_source.get(source_uuid, set()))
        removed = owned if positions is None else owned & positions
        for position in removed:
            contributions = self._optical_obscurements_by_position.get(position)
            if contributions is not None:
                contributions.pop(source_uuid, None)
                if not contributions:
                    self._optical_obscurements_by_position.pop(position, None)
        retained = owned - removed
        if retained:
            self._optical_obscurement_positions_by_source[source_uuid] = retained
        else:
            self._optical_obscurement_positions_by_source.pop(source_uuid, None)
        if removed:
            self._publish_optical_obscurement_change(
                source_uuid,
                removed,
                parent_event,
            )
        return removed

    def get_optical_obscurements_at(
        self,
        position: Tuple[int, int],
    ) -> Set[OpticalObscurement]:
        """Return conditional optical facts currently covering one Tile."""
        result = set(
            self._optical_obscurements_by_position.get(position, {}).values()
        )
        result.update(
            obscurement
            for condition in self.get_spatial_conditions_at(position)
            if (
                obscurement := condition.get_optical_obscurement_at(position)
            ) is not None
        )
        return result

    def get_optical_obscurements_on_route(
        self,
        start: Tuple[int, int],
        end: Tuple[int, int],
    ) -> Set[OpticalObscurement]:
        """Return conditional optical facts intersecting one optical ray."""
        result: Set[OpticalObscurement] = set()
        for position in supercover_line(start, end):
            result.update(self.get_optical_obscurements_at(position))
        return result

    def _publish_optical_obscurement_change(
        self,
        source_uuid: UUID,
        positions: Set[Tuple[int, int]],
        parent_event: Optional[UUID],
    ) -> None:
        """Publish one committed batch fact for a conditional optical change."""
        live = {position for position in positions if position in self._tiles}
        if not live:
            return
        self._bump_spatial_revisions({"optical"})
        representative = min(live)
        event = SpatialChangeEvent.tile_changed(
            representative,
            source_entity_uuid=source_uuid,
            senses_hint=SensesUpdateHint(
                requires_fov=True,
                directional_positions=live,
            ),
            parent_event=parent_event,
        )
        self._fire_committed_spatial_event(event)

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

        return source.uuid

    def get_light_source_position(
        self,
        light_uuid: UUID,
    ) -> Optional[Tuple[int, int]]:
        """Return the objective coordinate of one existing light source."""
        source = self._light_sources.get(light_uuid)
        return source.position if source is not None else None

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

    def cleanup_block_light_sources(self, block_uuid: UUID) -> None:
        """Permanently remove all light sources attached to a destroyed block."""
        block = BaseBlock.get(block_uuid)
        if block is None:
            return
        for light_uuid in block.get_attached_light_sources():
            self.remove_light_source(light_uuid)
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

        timing = action_timing_enabled()
        started = time.perf_counter() if timing else 0.0
        old_affected = dict(source.affected_tiles)
        new_affected = self._compute_light_tiles(source, new_position)
        if timing:
            record_action_timing("grid.move_light_source.compute_tiles_ms", started)

        started = time.perf_counter() if timing else 0.0
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
        if timing:
            record_action_timing("grid.move_light_source.apply_delta_ms", started)

        source.position = new_position
        source.affected_tiles = new_affected

        started = time.perf_counter() if timing else 0.0
        self._fire_light_batch_events(changed_positions, parent_event=parent_event)
        if timing:
            record_action_timing("grid.move_light_source.publish_batch_ms", started)

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

        visible_positions = self.compute_light_fov(pos, total_radius_tiles)
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
    ) -> None:
        """Publish one complete event for an atomic light-field delta.

        The event carries every changed position so rule handlers and observer
        senses consume the same authoritative batch exactly once.

        Args:
            changed_positions: Tiles whose resolved light level changed.
            parent_event: Optional causal parent event UUID.
        """
        if not changed_positions:
            return
        self._bump_spatial_revisions({"illumination"})

        batch_hint = SensesUpdateHint(
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

    def _settle_entity_presence_before_completion(
        self,
        effect: SpatialChangeEvent,
    ) -> None:
        """Settle anchored light inside its direct occupancy cause."""
        entity_uuid = effect.entity_uuid
        if entity_uuid is None:
            return
        if effect.event_type is EventType.SPATIAL_ENTITY_LEFT:
            if effect.old_position is None:
                self.set_block_light_suppressed(
                    entity_uuid,
                    ENTITY_WORLD_PRESENCE_LIGHT_SUPPRESSION_TOKEN,
                    True,
                    parent_event=effect.uuid,
                )
            return
        if effect.event_type is not EventType.SPATIAL_ENTITY_ENTERED:
            return
        anchor = BaseBlock.get(entity_uuid)
        if anchor is not None:
            for light_uuid in anchor.get_attached_light_sources():
                if light_uuid in self._light_sources:
                    self.move_light_source(
                        light_uuid,
                        effect.position,
                        parent_event=effect.uuid,
                    )
        self.set_block_light_suppressed(
            entity_uuid,
            ENTITY_WORLD_PRESENCE_LIGHT_SUPPRESSION_TOKEN,
            False,
            parent_event=effect.uuid,
        )

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
        for source in self._light_sources.values():
            if not self._is_light_effectively_active(source):
                continue
            total_radius_tiles = (source.bright_radius_feet + source.dim_radius_feet) / 5
            dx = position[0] - source.position[0]
            dy = position[1] - source.position[1]
            if math.sqrt(dx * dx + dy * dy) > total_radius_tiles:
                continue

            old_affected = dict(source.affected_tiles)
            new_affected = self._compute_light_tiles(source)

            changed_positions: List[Tuple[int, int]] = []
            all_positions = set(old_affected) | set(new_affected)
            for pos in all_positions:
                old_level = old_affected.get(pos)
                new_level = new_affected.get(pos)
                if old_level == new_level:
                    tile = self._tiles.get(pos)
                    if (
                        tile is not None
                        and new_level is not None
                        and tile._add_illumination(source.uuid, new_level)
                    ):
                        changed_positions.append(pos)
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
        """Check if position blocks AoE propagation (physical barriers only).

        Propagation is independent from optical opacity.
        """
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

        Unlike compute_fov(), ignores magical darkness — AoE spreads through
        darkness but not through walls/closed doors."""
        cache_started = time.perf_counter()
        cache_key = (origin, max_distance)
        cached = self._propagation_fov_cache.get(cache_key)
        if cached is not None:
            record_action_timing("grid.compute_propagation_fov.cache_hit_ms", cache_started)
            return list(cached)
        record_action_timing("grid.compute_propagation_fov.cache_miss_ms", cache_started)
        visible_positions: List[Tuple[int, int]] = []

        def mark_visible(x: int, y: int) -> None:
            visible_positions.append((x, y))

        def is_blocking_for(x: int, y: int) -> bool:
            return self.is_blocking_propagation(x, y)

        if self._has_directional_blockers("propagation"):
            visible_positions = self._compute_directional_fov(origin, max_distance, "propagation")
        else:
            compute_fov(origin, is_blocking_for, mark_visible, max_distance)

        visible_positions = [
            position for position in visible_positions
            if position in self._tiles
        ]

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
        timing = action_timing_enabled()
        total_started = time.perf_counter() if timing else 0.0
        if origin not in self._tiles:
            return set()

        cache_started = time.perf_counter() if timing else 0.0
        cache_key = (origin, max_distance, tuple(sorted(positions)))
        cached_positions = self._propagation_filter_cache.get(cache_key)
        if cached_positions is not None:
            self._propagation_filter_cache.move_to_end(cache_key)
            if timing:
                record_action_timing("grid.filter_propagation_positions.cache_hit_ms", cache_started)
                record_action_timing("grid.filter_propagation_positions.total_ms", total_started)
            return set(cached_positions)
        if timing:
            record_action_timing("grid.filter_propagation_positions.cache_miss_ms", cache_started)

        radius_squared = max_distance * max_distance if max_distance is not None else None
        transition_cache = self._propagation_transition_cache
        blocking_cache = self._propagation_blocking_cache
        line_cache: Dict[Tuple[int, int], Tuple[Tuple[int, int], ...]] = {}
        line_seconds = 0.0
        transition_seconds = 0.0
        blocking_seconds = 0.0

        def get_line_offsets(end: Tuple[int, int]) -> Tuple[Tuple[int, int], ...]:
            nonlocal line_seconds
            key = (end[0] - origin[0], end[1] - origin[1])
            cached = line_cache.get(key)
            if cached is not None:
                return cached
            started = time.perf_counter() if timing else 0.0
            path = supercover_line_offsets(key)
            if timing:
                line_seconds += time.perf_counter() - started
            line_cache[key] = path
            return path

        def transition_allows(prev: Tuple[int, int], current: Tuple[int, int]) -> bool:
            nonlocal transition_seconds
            key = (prev, current)
            cached = transition_cache.get(key)
            if cached is not None:
                return cached
            started = time.perf_counter() if timing else 0.0
            allowed = self.can_propagate_transition(prev, current, None)
            if timing:
                transition_seconds += time.perf_counter() - started
            transition_cache[key] = allowed
            return allowed

        def blocks_cell(position: Tuple[int, int]) -> bool:
            nonlocal blocking_seconds
            cached = blocking_cache.get(position)
            if cached is not None:
                return cached
            started = time.perf_counter() if timing else 0.0
            blocked = self.is_blocking_propagation(position[0], position[1])
            if timing:
                blocking_seconds += time.perf_counter() - started
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

        if timing:
            record_action_elapsed("grid.filter_propagation_positions.supercover_line_ms", line_seconds)
            record_action_elapsed("grid.filter_propagation_positions.transition_checks_ms", transition_seconds)
            record_action_elapsed("grid.filter_propagation_positions.blocking_checks_ms", blocking_seconds)
            record_action_timing("grid.filter_propagation_positions.total_ms", total_started)
        self._propagation_filter_cache[cache_key] = tuple(sorted(visible_positions))
        if len(self._propagation_filter_cache) > 256:
            self._propagation_filter_cache.popitem(last=False)
        return visible_positions

    def get_barrier_positions(self) -> Set[Tuple[int, int]]:
        """Return all positions that block AoE propagation.

        Used for fast-path: if geometric_shape & barrier_positions is empty,
        skip shadowcast entirely."""
        cache_started = time.perf_counter()
        if self._barrier_positions_cache is not None:
            record_action_timing("grid.get_barrier_positions.cache_hit_ms", cache_started)
            return set(self._barrier_positions_cache)
        record_action_timing("grid.get_barrier_positions.cache_miss_ms", cache_started)
        barriers: Set[Tuple[int, int]] = set()
        for pos, tile in self._tiles.items():
            if tile.blocks_propagation():
                barriers.add(pos)
        for obj_uuid, placement in self._object_placements.items():
            block = BaseBlock.get(obj_uuid)
            structure = (
                block.get_boundary_structure()
                if block is not None
                else None
            )
            if (
                block is not None
                and (
                    block.blocks_propagation()
                    or (
                        structure is not None
                        and WorldEdgeChannel.PROPAGATION
                        in structure.blocked_channels
                    )
                )
            ):
                barriers.add(placement.position)
        self._barrier_positions_cache = frozenset(barriers)
        return set(barriers)

    def clear(self) -> None:
        """Clear all tiles, entity positions, object positions, subscriptions, and light sources."""
        if any(tile.get_entity_uuids() for tile in self._tiles.values()):
            raise ValueError("cannot clear GridMap while entities are deployed")
        if self._spatial_conditions:
            raise ValueError(
                "cannot clear GridMap while spatial conditions are active"
            )
        registered_objects = tuple(self._object_placements.items())
        for object_uuid, placement in registered_objects:
            obj = BaseBlock.get(object_uuid)
            if obj is not None:
                obj.on_grid_object_removed(
                    placement.position,
                    clear_location=True,
                )
        for tile in tuple(self._tiles.values()):
            BaseBlock.unregister(tile.uuid)
        self._tiles.clear()
        self._tiles_by_uuid.clear()
        self._object_placements.clear()
        self._spatial_conditions.clear()
        self._spatial_condition_positions.clear()
        self._spatial_condition_layers.clear()
        self._connectors_by_uuid.clear()
        self._connector_uuid_by_authored_id.clear()
        self._connector_uuids_by_endpoint.clear()
        self._cell_subscribers.clear()
        self._entity_subscriptions.clear()
        self._light_sources.clear()
        self._block_light_suppressions.clear()
        self._optical_obscurements_by_position.clear()
        self._optical_obscurement_positions_by_source.clear()
        self._pending_events.clear()
        self._pending_committed_events.clear()
        self._bounds_dirty = True
        self._spatial_revision = 0
        self._optical_revision = 0
        self._movement_revision = 0
        self._connector_revision = 0
        self._light_revision = 0
        self._propagation_revision = 0
        self._fov_cache.clear()
        self._propagation_fov_cache.clear()
        self._propagation_filter_cache.clear()
        self._barrier_positions_cache = None
        self._directional_blockers_cache.clear()
        self._directional_transition_cache.clear()
        self._directional_blocking_cache.clear()
        self._propagation_transition_cache.clear()
        self._propagation_blocking_cache.clear()

    def get_all_tiles(self) -> Dict[Tuple[int, int], Tile]:
        """Get all tiles (for serialization/debugging)."""
        return self._tiles.copy()

    def get_tiles_with_conditions(self) -> List[Tile]:
        """Get tiles with active conditions (for environment step)."""
        return [
            tile
            for tile in self._tiles.values()
            if tile.get_conditions()
        ]

    def tile_count(self) -> int:
        """Get number of tiles."""
        return len(self._tiles)

def get_map() -> GridMap:
    """Get the global GridMap instance."""
    return GridMap.get_instance()


def reset_map() -> None:
    """Reset the global GridMap (for testing)."""
    GridMap.reset()
