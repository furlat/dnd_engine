"""Central spatial registry for tiles, entities, objects, light, and paths."""

import math
import time
from typing import Any, Dict, List, Optional, Tuple, Set, DefaultDict, cast
from uuid import UUID, uuid4
from collections import OrderedDict, defaultdict

from pydantic import BaseModel, Field

from dnd.core.geometry import circle_positions, supercover_line, supercover_line_offsets
from dnd.core.shadowcast import compute_fov
from dnd.core.dijkstra import breadth_first_paths, dijkstra
from dnd.core.base_block import BaseBlock, MovementMode, LightLevel
from dnd.core.base_tiles import Tile
from dnd.core.events import Event, SpatialChangeEvent, SpatialChangeType, EventPhase, EventQueue, EventType, SensesUpdateHint
from dnd.action_timing import action_timing_enabled, record_action_elapsed, record_action_timing

DIRECTIONS: Tuple[str, ...] = ("north", "south", "east", "west")
DIRECTIONAL_CHANNELS: Tuple[str, ...] = ("movement", "vision", "light", "propagation")


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

    The map owns tile storage, entity/object position indexes, event-backed
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

        self._entities_by_position: DefaultDict[Tuple[int, int], Set[UUID]] = defaultdict(set)
        self._entity_positions: Dict[UUID, Tuple[int, int]] = {}

        self._object_positions: Dict[UUID, Tuple[int, int]] = {}
        self._objects_by_position: DefaultDict[Tuple[int, int], Set[UUID]] = defaultdict(set)

        self._cell_subscribers: DefaultDict[Tuple[int, int], Set[UUID]] = defaultdict(set)
        self._entity_subscriptions: DefaultDict[UUID, Set[Tuple[int, int]]] = defaultdict(set)

        self._light_sources: Dict[UUID, LightSourceData] = {}
        self._block_light_suppressions: DefaultDict[UUID, Set[str]] = defaultdict(set)

        self._events_enabled: bool = True
        self._pending_events: List['SpatialChangeEvent'] = []

        self._light_callback_registered: bool = False
        self._blocking_callback_registered: bool = False
        self._spatial_revision: int = 0
        self._vision_revision: int = 0
        self._movement_revision: int = 0
        self._occupancy_revision: int = 0
        self._light_revision: int = 0
        self._light_geometry_revision: int = 0
        self._propagation_revision: int = 0
        self._fov_cache: Dict[
            Tuple[Tuple[int, int], Optional[float], bool, int],
            List[Tuple[int, int]],
        ] = {}
        self._propagation_fov_cache: Dict[
            Tuple[Tuple[int, int], Optional[float]],
            Tuple[Tuple[int, int], ...],
        ] = {}
        self._barrier_positions_cache: Optional[frozenset[Tuple[int, int]]] = None
        self._directional_blockers_cache: Dict[str, bool] = {}
        self._directional_channel_equivalence_cache: Dict[
            Tuple[str, str],
            bool,
        ] = {}
        self._directional_transition_cache: Dict[
            Tuple[str, int, bool],
            Dict[Tuple[Tuple[int, int], Tuple[int, int]], bool],
        ] = {}
        self._directional_blocking_cache: Dict[
            Tuple[str, int, bool],
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

        current_event = current_event.phase_to(EventPhase.COMPLETION)
        current_event = cast(SpatialChangeEvent, EventQueue.register(current_event))

        return current_event

    def enable_events(self) -> None:
        """Enable event firing and flush pending events through full lifecycle."""
        self._events_enabled = True
        pending = self._pending_events.copy()
        self._pending_events.clear()
        for event in pending:
            self._fire_spatial_event(event)

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
    def vision_revision(self) -> int:
        """Return the current vision-topology revision."""
        return self._vision_revision

    @property
    def movement_revision(self) -> int:
        """Return the current movement-topology revision."""
        return self._movement_revision

    @property
    def propagation_revision(self) -> int:
        """Return the current physical-propagation topology revision."""
        return self._propagation_revision

    def invalidate_spatial_caches(self, channels: Set[str]) -> None:
        """Invalidate spatial query caches after authoritative topology changes.

        Args:
            channels: Changed spatial channels: movement, vision, light, or
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
        if "vision" in channels:
            self._vision_revision += 1
            self._fov_cache.clear()
        if "movement" in channels:
            self._movement_revision += 1
            self._path_cache.clear()
        if "light" in channels or "illumination" in channels:
            self._light_revision += 1
        if "light" in channels:
            self._light_geometry_revision += 1
        if "propagation" in channels:
            self._propagation_revision += 1
            self._propagation_fov_cache.clear()
            self._propagation_filter_cache.clear()
            self._barrier_positions_cache = None
            self._propagation_transition_cache.clear()
            self._propagation_blocking_cache.clear()
        if channels & set(DIRECTIONAL_CHANNELS):
            self._directional_channel_equivalence_cache.clear()
        if "vision" in channels or "light" in channels:
            self._directional_transition_cache.clear()
            self._directional_blocking_cache.clear()
        for channel in channels & set(DIRECTIONAL_CHANNELS):
            self._directional_blockers_cache.pop(channel, None)

    def _bump_all_spatial_revisions(self) -> None:
        """Advance every spatial channel revision and clear query caches."""
        self._bump_spatial_revisions({"movement", "vision", "light", "propagation"})

    def _observer_can_pierce_magical_darkness(self, observer_uuid: Optional[UUID]) -> bool:
        """Return the observer capability that affects magical-darkness FOV."""
        if observer_uuid is None:
            return False
        observer = BaseBlock.get(observer_uuid)
        return observer is not None and observer.can_pierce_magical_darkness()

    def _path_requester_perception_signature(
        self,
        requester_uuid: Optional[UUID],
        subjective: bool,
    ) -> Tuple[Any, ...]:
        """Return subjective observer state that can change path blockers."""
        if requester_uuid is None or not subjective:
            return ()
        requester = BaseBlock.get(requester_uuid)
        if requester is None:
            return ()
        return (
            requester.get_passive_perception(),
            requester.can_bypass_invisibility(),
            requester.can_pierce_magical_darkness(),
            tuple(
                sorted(
                    (mode.sense_type.value, mode.range_feet)
                    for mode in requester.get_sense_modes()
                )
            ),
        )

    def set_tile(self, x: int, y: int, walkable: bool = True, visible: bool = True,
                 name: str = "Floor", sprite_name: Optional[str] = None,
                 fire_event: bool = True, tile: Optional[Tile] = None) -> Tile:
        """Set or replace a tile at a position.

        If tile parameter is provided, uses that tile directly (updating its position if needed).
        Otherwise creates a new Tile object with the given parameters.
        Returns the stored tile.
        """
        position = (x, y)
        old_tile = self._tiles.get(position)
        old_directional = self._directional_block_map(position)

        if old_tile:
            self._tiles_by_uuid.pop(old_tile.uuid, None)

        if tile is not None:
            tile.position = position
        else:
            tile = Tile.create(
                position=position,
                walkable=walkable,
                visible=visible,
                name=name,
                sprite_name=sprite_name
            )
        self._tiles[position] = tile
        self._tiles_by_uuid[tile.uuid] = position
        self._bounds_dirty = True
        self.recompute_tile_directional_blocking(position)
        new_directional = self._directional_block_map(position)
        directional_metadata = self._directional_metadata_from_delta(position, old_directional, new_directional)
        revision_channels: Set[str] = set()
        if old_tile is None:
            revision_channels.update({"movement", "vision", "light", "propagation"})
        else:
            if old_tile.walkable != tile.walkable:
                revision_channels.add("movement")
            if old_tile.visible != tile.visible:
                revision_channels.update({"vision", "propagation"})
            old_magical = old_tile.resolved_light_level == LightLevel.MAGICAL_DARKNESS
            new_magical = tile.resolved_light_level == LightLevel.MAGICAL_DARKNESS
            if old_magical != new_magical:
                revision_channels.update({"vision", "light"})
        self._bump_spatial_revisions(revision_channels)

        if fire_event and self._events_enabled:
            old_walkable = old_tile.walkable if old_tile else None
            old_visible = old_tile.visible if old_tile else None
            tile_walkable = tile.walkable
            tile_visible = tile.visible
            scalar_walk_changed = old_tile is None or old_walkable != tile_walkable
            scalar_visible_changed = old_tile is None or old_visible != tile_visible
            directional_channels = set(directional_metadata.get("directional_channels") or [])
            if scalar_walk_changed or scalar_visible_changed or directional_channels:
                hint = SensesUpdateHint(
                    requires_fov=scalar_visible_changed or "vision" in directional_channels,
                    requires_paths=scalar_walk_changed or "movement" in directional_channels,
                    directional_positions={position} if directional_channels else None,
                    directional_neighbors={
                        neighbor
                        for direction in (directional_metadata.get("directional_directions") or [])
                        for neighbor in self._neighbor_for_direction(position, direction)
                    } or None,
                    directional_channels_changed=directional_channels or None,
                    requires_light_recompute="light" in directional_channels,
                    requires_propagation_recompute="propagation" in directional_channels,
                )
                event = SpatialChangeEvent.tile_changed(
                    position, tile_walkable, tile_visible,
                    senses_hint=hint,
                    **directional_metadata,
                )
                self._fire_spatial_event(event)

        return tile

    def set_tile_directional_border(self, position: Tuple[int, int], channel: str,
                                    direction: str, passable: bool,
                                    parent_event: Optional[UUID] = None,
                                    fire_event: bool = True) -> bool:
        """Set an intrinsic tile-owned directional border and emit tile change metadata.

        Args:
            channel: movement, vision, light, or propagation.
            direction: north, south, east, or west relative to this tile.
            passable: True allows crossing; False blocks crossing.

        Returns True when the stored value changed.
        """
        if channel not in DIRECTIONAL_CHANNELS:
            raise ValueError(f"Unsupported directional channel: {channel}")
        if direction not in DIRECTIONS:
            raise ValueError(f"Unsupported direction: {direction}")

        tile = self._tiles.get(position)
        if tile is None:
            return False

        if not tile.set_intrinsic_border(channel, direction, passable):
            return False
        self._bump_spatial_revisions({channel})
        state = self._directional_block_map(position)
        metadata = {
            "directional_position": position,
            "directional_directions": [direction],
            "directional_channels": [channel],
            "directional_blocks_movement": state["movement"],
            "directional_blocks_vision": state["vision"],
            "directional_blocks_light": state["light"],
            "directional_blocks_propagation": state["propagation"],
        }

        if fire_event and self._events_enabled:
            hint = SensesUpdateHint(
                requires_fov=channel == "vision",
                requires_paths=channel == "movement",
                directional_positions={position},
                directional_neighbors={neighbor for neighbor in self._neighbor_for_direction(position, direction)},
                directional_channels_changed={channel},
                requires_light_recompute=channel == "light",
                requires_propagation_recompute=channel == "propagation",
            )
            event = SpatialChangeEvent.tile_changed(
                position, tile.walkable, tile.visible,
                senses_hint=hint,
                parent_event=parent_event,
                **metadata,
            )
            self._fire_spatial_event(event)
        return True

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
            was_blocking_vision = not tile.visible
            was_blocking_walking = not tile.walkable
            self._tiles_by_uuid.pop(tile.uuid, None)
            del self._tiles[position]
            self._bounds_dirty = True
            self._bump_all_spatial_revisions()

            if fire_event and self._events_enabled:
                hint = SensesUpdateHint(
                    requires_fov=was_blocking_vision,
                    requires_paths=was_blocking_walking,
                )
                event = SpatialChangeEvent(
                    source_entity_uuid=uuid4(),
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
        """Return whether tile or placed-object hazards affect an entity."""
        tile = self.get_tile(x, y)
        if tile is not None and tile.is_hazardous_for(entity_uuid):
            return True

        for obj_uuid in self._objects_by_position.get((x, y), set()):
            obj = BaseBlock.get(obj_uuid)
            if obj is not None and obj.is_hazardous_for(entity_uuid):
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

        for entity_uuid in self._entities_by_position.get((x, y), set()):
            block = BaseBlock.get(entity_uuid)
            if block is not None and block.blocks_walking(requesting_entity_uuid, mode):
                if subjective and not block.is_perceivable_by(requesting_entity_uuid):
                    continue
                return False

        for obj_uuid in self._objects_by_position.get((x, y), set()):
            block = BaseBlock.get(obj_uuid)
            if block is not None and block.blocks_walking(requesting_entity_uuid, mode):
                if subjective and not block.is_perceivable_by(requesting_entity_uuid):
                    continue
                return False

        if not walk_in_danger:
            if self.is_position_hazardous_for(x, y, requesting_entity_uuid):
                return False

        if collision_blocked and (x, y) in collision_blocked:
            return False

        return True

    def is_visible(self, x: int, y: int) -> bool:
        """Check if position allows vision (has tile and tile allows vision)."""
        tile = self._tiles.get((x, y))
        return tile is not None and not tile.blocks_vision()

    def is_blocking(self, x: int, y: int, requesting_entity_uuid: Optional[UUID] = None) -> bool:
        """Return whether a tile or placed object blocks line of sight."""
        tile = self._tiles.get((x, y))
        if tile is None or tile.blocks_vision(requesting_entity_uuid):
            return True
        for obj_uuid in self._objects_by_position.get((x, y), set()):
            block = BaseBlock.get(obj_uuid)
            if block is not None and block.blocks_vision(requesting_entity_uuid):
                return True
        return False

    def _block_blocks_direction(self, block: BaseBlock, channel: str, direction: str,
                                requester_uuid: Optional[UUID] = None,
                                movement_mode: MovementMode = MovementMode.WALKING,
                                subjective: bool = False) -> bool:
        if channel == "movement":
            return block.blocks_directional_movement(direction, requester_uuid, movement_mode, subjective)
        if channel == "vision":
            return block.blocks_directional_vision(direction, requester_uuid, subjective)
        if channel == "light":
            return block.blocks_directional_light(direction, requester_uuid, subjective)
        if channel == "propagation":
            return block.blocks_directional_propagation(direction, requester_uuid, subjective)
        return False

    def _directional_block_map(self, position: Tuple[int, int]) -> Dict[str, Dict[str, bool]]:
        tile = self._tiles.get(position)
        result: Dict[str, Dict[str, bool]] = {
            channel: {direction: False for direction in DIRECTIONS}
            for channel in DIRECTIONAL_CHANNELS
        }
        if tile is None:
            return result
        for channel in DIRECTIONAL_CHANNELS:
            for direction in DIRECTIONS:
                result[channel][direction] = not tile.allows_direction(direction, channel)
        return result

    def get_subjective_directional_block_map(
        self,
        position: Tuple[int, int],
        requesting_entity_uuid: UUID,
        movement_mode: MovementMode = MovementMode.WALKING,
    ) -> Dict[str, Dict[str, bool]]:
        """Return intrinsic plus perceivable directional blockers for one observer.

        The tile's cached derived borders are objective.  Subjective transports
        must instead rebuild the derived contribution from blocks the requesting
        observer can actually perceive, or hidden directional blockers leak.
        """
        if BaseBlock.get(requesting_entity_uuid) is None:
            raise ValueError("subjective directional projection requires a known observer")
        tile = self._tiles.get(position)
        result: Dict[str, Dict[str, bool]] = {
            channel: {direction: False for direction in DIRECTIONS}
            for channel in DIRECTIONAL_CHANNELS
        }
        if tile is None:
            return result

        for channel in DIRECTIONAL_CHANNELS:
            for direction in DIRECTIONS:
                result[channel][direction] = not tile.allows_direction(
                    direction,
                    channel,
                    include_derived=False,
                )

        block_uuids = set(self._objects_by_position.get(position, set()))
        block_uuids.update(self._entities_by_position.get(position, set()))
        for block_uuid in block_uuids:
            block = BaseBlock.get(block_uuid)
            if block is None or not block.is_perceivable_by(requesting_entity_uuid):
                continue
            for channel in DIRECTIONAL_CHANNELS:
                for direction in DIRECTIONS:
                    if self._block_blocks_direction(
                        block,
                        channel,
                        direction,
                        requesting_entity_uuid,
                        movement_mode,
                        subjective=True,
                    ):
                        result[channel][direction] = True
        return result

    def _directional_metadata_from_delta(self, position: Tuple[int, int],
                                         old: Dict[str, Dict[str, bool]],
                                         new: Dict[str, Dict[str, bool]]) -> Dict[str, Any]:
        empty: Dict[str, Any] = {
            "directional_position": None,
            "directional_directions": None,
            "directional_channels": None,
            "directional_blocks_movement": None,
            "directional_blocks_vision": None,
            "directional_blocks_light": None,
            "directional_blocks_propagation": None,
        }
        changed_channels = [
            channel for channel in DIRECTIONAL_CHANNELS
            if any(old[channel][direction] != new[channel][direction] for direction in DIRECTIONS)
        ]
        changed_directions = [
            direction for direction in DIRECTIONS
            if any(old[channel][direction] != new[channel][direction] for channel in DIRECTIONAL_CHANNELS)
        ]
        if not changed_channels:
            return empty
        return {
            "directional_position": position,
            "directional_directions": changed_directions,
            "directional_channels": changed_channels,
            "directional_blocks_movement": new["movement"],
            "directional_blocks_vision": new["vision"],
            "directional_blocks_light": new["light"],
            "directional_blocks_propagation": new["propagation"],
        }

    def recompute_tile_directional_blocking(self, position: Tuple[int, int]) -> Dict[str, Any]:
        """Refresh object/entity-derived tile directional state for one tile.

        The stored state is objective/default. Subjective pathing still re-derives
        from the live blocks so imperceivable directional blockers do not leak.
        """
        empty: Dict[str, Any] = {
            "directional_position": None,
            "directional_directions": None,
            "directional_channels": None,
            "directional_blocks_movement": None,
            "directional_blocks_vision": None,
            "directional_blocks_light": None,
            "directional_blocks_propagation": None,
        }
        tile = self._tiles.get(position)
        if tile is None:
            return empty

        old = self._directional_block_map(position)

        for channel in DIRECTIONAL_CHANNELS:
            for direction in DIRECTIONS:
                tile.set_object_border(channel, direction, True)

        block_uuids = set(self._objects_by_position.get(position, set()))
        block_uuids.update(self._entities_by_position.get(position, set()))
        for block_uuid in block_uuids:
            block = BaseBlock.get(block_uuid)
            if block is None:
                continue
            for channel in DIRECTIONAL_CHANNELS:
                for direction in DIRECTIONS:
                    if self._block_blocks_direction(block, channel, direction):
                        tile.set_object_border(channel, direction, False)

        new = self._directional_block_map(position)
        metadata = self._directional_metadata_from_delta(position, old, new)
        changed_channels = set(metadata.get("directional_channels") or [])
        self._bump_spatial_revisions(changed_channels)
        return metadata

    def _tile_allows_transition_side(self, tile_pos: Tuple[int, int], other_pos: Tuple[int, int],
                                     channel: str,
                                     requester_uuid: Optional[UUID] = None,
                                     movement_mode: MovementMode = MovementMode.WALKING,
                                     subjective: bool = False) -> bool:
        tile = self._tiles.get(tile_pos)
        if tile is None:
            return False

        directions = tile.directions_toward(other_pos)
        if not directions:
            return True

        if not subjective:
            return tile.allows_directions(directions, channel)

        open_directions = {direction: tile.allows_direction(direction, channel, include_derived=False)
                           for direction in directions}
        block_uuids = set(self._objects_by_position.get(tile_pos, set()))
        block_uuids.update(self._entities_by_position.get(tile_pos, set()))
        for block_uuid in block_uuids:
            block = BaseBlock.get(block_uuid)
            if block is None:
                continue
            if not block.is_perceivable_by(requester_uuid):
                continue
            for direction in directions:
                if self._block_blocks_direction(block, channel, direction, requester_uuid,
                                                movement_mode, subjective=True):
                    open_directions[direction] = False

        return all(open_directions.values())

    def _cached_tile_allows_transition_side(
        self,
        tile_pos: Tuple[int, int],
        other_pos: Tuple[int, int],
        channel: str,
        requester_uuid: Optional[UUID],
        movement_mode: MovementMode,
        subjective: bool,
        side_cache: Optional[
            Dict[Tuple[Tuple[int, int], Tuple[int, int]], bool]
        ],
    ) -> bool:
        """Return one directional-side result through an optional query cache."""
        key = (tile_pos, other_pos)
        if side_cache is not None:
            cached = side_cache.get(key)
            if cached is not None:
                return cached
        result = self._tile_allows_transition_side(
            tile_pos,
            other_pos,
            channel,
            requester_uuid,
            movement_mode,
            subjective,
        )
        if side_cache is not None:
            side_cache[key] = result
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
        return not self.is_blocking(position[0], position[1], requester_uuid)

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
        return (
            self._cached_tile_allows_transition_side(
                from_pos, to_pos, channel,
                requester_uuid, movement_mode, subjective, side_cache,
            )
            and self._cached_tile_allows_transition_side(
                to_pos, from_pos, channel,
                requester_uuid, movement_mode, subjective, side_cache,
            )
        )

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
                self._cardinal_transition_sides_allow(
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
        if not self._cached_tile_allows_transition_side(
            from_pos, to_pos, "movement",
            requesting_entity_uuid, movement_mode, subjective, side_cache,
        ):
            return False
        if not self._cached_tile_allows_transition_side(
            to_pos, from_pos, "movement",
            requesting_entity_uuid, movement_mode, subjective, side_cache,
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

    def can_see_transition(self, from_pos: Tuple[int, int], to_pos: Tuple[int, int],
                           observer_uuid: Optional[UUID] = None,
                           subjective: bool = False) -> bool:
        if abs(to_pos[0] - from_pos[0]) == 1 and abs(to_pos[1] - from_pos[1]) == 1:
            return self._diagonal_transition_allows(from_pos, to_pos, "vision", observer_uuid, subjective=subjective)
        return (
            self._tile_allows_transition_side(from_pos, to_pos, "vision", observer_uuid, subjective=subjective)
            and self._tile_allows_transition_side(to_pos, from_pos, "vision", observer_uuid, subjective=subjective)
        )

    def can_light_transition(self, from_pos: Tuple[int, int], to_pos: Tuple[int, int],
                             observer_uuid: Optional[UUID] = None,
                             subjective: bool = False) -> bool:
        if abs(to_pos[0] - from_pos[0]) == 1 and abs(to_pos[1] - from_pos[1]) == 1:
            return self._diagonal_transition_allows(from_pos, to_pos, "light", observer_uuid, subjective=subjective)
        return (
            self._tile_allows_transition_side(from_pos, to_pos, "light", observer_uuid, subjective=subjective)
            and self._tile_allows_transition_side(to_pos, from_pos, "light", observer_uuid, subjective=subjective)
        )

    def can_propagate_transition(self, from_pos: Tuple[int, int], to_pos: Tuple[int, int],
                                 requester_uuid: Optional[UUID] = None,
                                 subjective: bool = False) -> bool:
        if abs(to_pos[0] - from_pos[0]) == 1 and abs(to_pos[1] - from_pos[1]) == 1:
            return self._diagonal_transition_allows(from_pos, to_pos, "propagation", requester_uuid, subjective=subjective)
        return (
            self._tile_allows_transition_side(from_pos, to_pos, "propagation", requester_uuid, subjective=subjective)
            and self._tile_allows_transition_side(to_pos, from_pos, "propagation", requester_uuid, subjective=subjective)
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

        for entity_uuid in self._entities_by_position.get(position, set()):
            block = BaseBlock.get(entity_uuid)
            if block is not None and block.blocks_walking(requesting_entity_uuid, mode):
                return block.name

        for obj_uuid in self._objects_by_position.get(position, set()):
            block = BaseBlock.get(obj_uuid)
            if block is not None and block.blocks_walking(requesting_entity_uuid, mode):
                return block.name

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

    def create_rectangle(self, x: int, y: int, width: int, height: int,
                         walkable: bool = True, visible: bool = True,
                         name: str = "Floor", sprite_name: Optional[str] = None) -> None:
        """Create a rectangular area of tiles (batch operation, no events during)."""
        self.disable_events()
        try:
            for tx in range(x, x + width):
                for ty in range(y, y + height):
                    old_tile = self._tiles.get((tx, ty))
                    if old_tile:
                        self._tiles_by_uuid.pop(old_tile.uuid, None)

                    tile = Tile.create(
                        position=(tx, ty),
                        walkable=walkable,
                        visible=visible,
                        name=name,
                        sprite_name=sprite_name
                    )
                    self._tiles[(tx, ty)] = tile
                    self._tiles_by_uuid[tile.uuid] = (tx, ty)
            self._bounds_dirty = True
        finally:
            self._bump_all_spatial_revisions()
            self.enable_events()

    def register_entity(self, entity_uuid: UUID, position: Tuple[int, int],
                         parent_event: Optional[UUID] = None) -> None:
        """Register an entity at a position."""
        old_pos = self._entity_positions.get(entity_uuid)
        if old_pos is not None:
            self._entities_by_position[old_pos].discard(entity_uuid)
            self.invalidate_occupancy_paths()
            old_directional_metadata = self.recompute_tile_directional_blocking(old_pos)
            if self._events_enabled:
                event = SpatialChangeEvent.entity_left(
                    old_pos, entity_uuid, position, parent_event=parent_event,
                    **old_directional_metadata,
                )
                self._fire_spatial_event(event)

        self._entity_positions[entity_uuid] = position
        self._entities_by_position[position].add(entity_uuid)
        self.invalidate_occupancy_paths()
        new_directional_metadata = self.recompute_tile_directional_blocking(position)

        if self._events_enabled:
            event = SpatialChangeEvent.entity_entered(
                position, entity_uuid, old_pos, parent_event=parent_event,
                **new_directional_metadata,
            )
            self._fire_spatial_event(event)

    def move_entity(
        self,
        entity_uuid: UUID,
        new_position: Tuple[int, int],
        parent_event: Optional[UUID] = None
    ) -> None:
        """Move an entity to a new position and fire spatial events.

        Args:
            entity_uuid: UUID of the entity to move
            new_position: New grid position
            parent_event: Optional parent event UUID for lineage (e.g., StepMovementEvent)
        """
        old_position = self._entity_positions.get(entity_uuid)

        if old_position is not None:
            started = time.perf_counter()
            self._entities_by_position[old_position].discard(entity_uuid)
            self.invalidate_occupancy_paths()
            record_action_timing("grid.move_entity.discard_old_position_ms", started)
            started = time.perf_counter()
            old_directional_metadata = self.recompute_tile_directional_blocking(old_position)
            record_action_timing("grid.move_entity.recompute_old_directional_ms", started)

            if self._events_enabled:
                started = time.perf_counter()
                event = SpatialChangeEvent.entity_left(
                    old_position, entity_uuid, new_position, parent_event=parent_event,
                    **old_directional_metadata,
                )
                self._fire_spatial_event(event)
                record_action_timing("grid.move_entity.fire_entity_left_ms", started)

        started = time.perf_counter()
        self._entity_positions[entity_uuid] = new_position
        self._entities_by_position[new_position].add(entity_uuid)
        self.invalidate_occupancy_paths()
        record_action_timing("grid.move_entity.store_new_position_ms", started)
        started = time.perf_counter()
        new_directional_metadata = self.recompute_tile_directional_blocking(new_position)
        record_action_timing("grid.move_entity.recompute_new_directional_ms", started)

        if self._events_enabled:
            started = time.perf_counter()
            event = SpatialChangeEvent.entity_entered(
                new_position, entity_uuid, old_position, parent_event=parent_event,
                **new_directional_metadata,
            )
            self._fire_spatial_event(event)
            record_action_timing("grid.move_entity.fire_entity_entered_ms", started)

    def get_entity_position(self, entity_uuid: UUID) -> Optional[Tuple[int, int]]:
        """Get an entity's position."""
        return self._entity_positions.get(entity_uuid)

    def get_entities_at(self, position: Tuple[int, int]) -> Set[UUID]:
        """Get all entity UUIDs at a position."""
        return self._entities_by_position.get(position, set()).copy()

    def get_all_object_positions(self) -> Dict[UUID, Tuple[int, int]]:
        """Get all placed object positions."""
        return self._object_positions.copy()

    def place_object(self, object_uuid: UUID, position: Tuple[int, int],
                      parent_event: Optional[UUID] = None) -> None:
        """Place an object on the grid at a position."""
        old_position = self._object_positions.get(object_uuid)
        if old_position is not None and old_position != position:
            self.remove_object(object_uuid, parent_event=parent_event, clear_object_location=False)

        self._object_positions[object_uuid] = position
        self._objects_by_position[position].add(object_uuid)
        directional_metadata = self.recompute_tile_directional_blocking(position)
        obj = BaseBlock.get(object_uuid)
        blocks_vision = obj.blocks_vision() if obj else False
        blocks_walking = obj.blocks_walking() if obj else False
        revision_channels: Set[str] = set()
        if blocks_vision:
            revision_channels.update({"vision", "propagation"})
        if blocks_walking:
            revision_channels.add("movement")
        self._bump_spatial_revisions(revision_channels)
        if self._events_enabled:
            obj_name = obj.name if obj else None
            obj_map_char = obj.get_map_char() if obj else None
            self._fire_spatial_event(SpatialChangeEvent.object_placed(
                position, object_uuid,
                parent_event=parent_event,
                blocks_vision=blocks_vision,
                blocks_walking=blocks_walking,
                object_name=obj_name,
                object_map_char=obj_map_char,
                **directional_metadata,
            ))

    def remove_object(self, object_uuid: UUID,
                       parent_event: Optional[UUID] = None,
                       clear_object_location: bool = True) -> None:
        """Remove an object from the grid."""
        obj = BaseBlock.get(object_uuid)
        blocks_vision = obj.blocks_vision() if obj else False
        blocks_walking = obj.blocks_walking() if obj else False
        position = self._object_positions.pop(object_uuid, None)
        if position is not None:
            self._objects_by_position[position].discard(object_uuid)
            if obj is not None:
                obj.on_grid_object_removed(position, clear_location=clear_object_location)
            directional_metadata = self.recompute_tile_directional_blocking(position)
            revision_channels: Set[str] = set()
            if blocks_vision:
                revision_channels.update({"vision", "propagation"})
            if blocks_walking:
                revision_channels.add("movement")
            self._bump_spatial_revisions(revision_channels)
            if self._events_enabled:
                self._fire_spatial_event(SpatialChangeEvent.object_removed(
                    position, object_uuid,
                    parent_event=parent_event,
                    blocks_vision=blocks_vision,
                    blocks_walking=blocks_walking,
                    **directional_metadata,
                ))

    def get_objects_at(self, position: Tuple[int, int]) -> Set[UUID]:
        """Get all object UUIDs at a position."""
        return set(self._objects_by_position.get(position, set()))

    def get_object_position(self, object_uuid: UUID) -> Optional[Tuple[int, int]]:
        """Get an object's grid position, or None if not placed."""
        return self._object_positions.get(object_uuid)

    def get_objects_with_conditions(self) -> List[BaseBlock]:
        """Get placed objects with active conditions (for environment step).

        Returns BaseBlock (not BaseItem) — GridMap stays type-unaware.
        """
        result: List[BaseBlock] = []
        for obj_uuid in self._object_positions:
            block = BaseBlock.get(obj_uuid)
            if block is not None and block.active_conditions:
                result.append(block)
        return result

    def _has_directional_blockers(self, channel: str) -> bool:
        cached = self._directional_blockers_cache.get(channel)
        if cached is not None:
            return cached
        for tile in self._tiles.values():
            for direction in DIRECTIONS:
                if not tile.allows_direction(direction, channel):
                    self._directional_blockers_cache[channel] = True
                    return True
        self._directional_blockers_cache[channel] = False
        return False

    def _directional_channels_equivalent(
        self,
        first_channel: str,
        second_channel: str,
    ) -> bool:
        """Return whether two directional channels have identical topology.

        Args:
            first_channel: First directional propagation channel.
            second_channel: Second directional propagation channel.

        Returns:
            Whether every tile exposes the same directional borders for both.
        """
        key = (
            min(first_channel, second_channel),
            max(first_channel, second_channel),
        )
        cached = self._directional_channel_equivalence_cache.get(key)
        if cached is not None:
            return cached
        equivalent = all(
            tile.allows_direction(direction, first_channel)
            == tile.allows_direction(direction, second_channel)
            for tile in self._tiles.values()
            for direction in DIRECTIONS
        )
        self._directional_channel_equivalence_cache[key] = equivalent
        return equivalent

    def _transition_clear(self, start: Tuple[int, int], end: Tuple[int, int],
                          channel: str,
                          observer_uuid: Optional[UUID] = None) -> bool:
        path = supercover_line(start, end)
        if not path:
            return False
        for index in range(1, len(path)):
            prev = path[index - 1]
            current = path[index]
            if channel == "vision":
                if not self.can_see_transition(prev, current, observer_uuid):
                    return False
                blocks_cell = self.is_blocking(current[0], current[1], observer_uuid)
            elif channel == "light":
                if not self.can_light_transition(prev, current, observer_uuid):
                    return False
                blocks_cell = self.is_blocking(current[0], current[1], observer_uuid)
            else:
                if not self.can_propagate_transition(prev, current, observer_uuid):
                    return False
                blocks_cell = self.is_blocking_propagation(current[0], current[1])

            if index < len(path) - 1 and blocks_cell:
                return False
        return True

    def raycast_clear(self, start: Tuple[int, int], end: Tuple[int, int],
                      channel: str = "vision",
                      observer_uuid: Optional[UUID] = None) -> bool:
        """Public transition-aware line check for vision/light/propagation."""
        return self._transition_clear(start, end, channel, observer_uuid)

    def _compute_directional_fov(self, origin: Tuple[int, int], max_distance: Optional[float],
                                 channel: str,
                                 observer_uuid: Optional[UUID] = None) -> List[Tuple[int, int]]:
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
        elif channel in {"vision", "light"}:
            revision = (
                self._vision_revision
                if channel == "vision"
                else self._light_geometry_revision
            )
            cache_key = (
                channel,
                revision,
                self._observer_can_pierce_magical_darkness(observer_uuid),
            )
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
            if channel == "vision":
                allowed = self.can_see_transition(prev, current, observer_uuid)
            elif channel == "light":
                allowed = self.can_light_transition(prev, current, observer_uuid)
            else:
                allowed = self.can_propagate_transition(prev, current, observer_uuid)
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
            if channel in {"vision", "light"}:
                blocked = self.is_blocking(position[0], position[1], observer_uuid)
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

    def compute_fov(self, origin: Tuple[int, int], max_distance: Optional[float] = None,
                    observer_uuid: Optional[UUID] = None) -> List[Tuple[int, int]]:
        """
        Compute field of view from a position using shadowcasting.

        Args:
            origin: Position to compute FOV from
            max_distance: Maximum view distance
            observer_uuid: If provided, magical darkness is checked per-observer

        Returns list of visible positions.
        """
        timing = action_timing_enabled()
        cache_started = time.perf_counter() if timing else 0.0
        cache_key = (
            origin,
            max_distance,
            self._observer_can_pierce_magical_darkness(observer_uuid),
            self._vision_revision,
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
                    cached_pierces_darkness,
                    cached_revision,
                ), positions in tuple(self._fov_cache.items())
                if cached_origin == origin
                and cached_pierces_darkness == cache_key[2]
                and cached_revision == self._vision_revision
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
            blocked = self.is_blocking(x, y, requesting_entity_uuid=observer_uuid)
            blocking_cache[position] = blocked
            return blocked

        if self._has_directional_blockers("vision"):
            visible_positions = self._compute_directional_fov(origin, max_distance, "vision", observer_uuid)
            self._fov_cache[cache_key] = list(visible_positions)
            return list(visible_positions)

        compute_fov(origin, is_blocking_for, mark_visible, max_distance)
        self._fov_cache[cache_key] = list(visible_positions)
        return list(visible_positions)

    def compute_light_fov(self, origin: Tuple[int, int], max_distance: Optional[float] = None) -> List[Tuple[int, int]]:
        """Compute light reach using light directional borders and current cell blockers."""
        if self._has_directional_blockers("light"):
            if self._directional_channels_equivalent("vision", "light"):
                return self.compute_fov(origin, max_distance)
            return self._compute_directional_fov(origin, max_distance, "light")
        visible_positions: List[Tuple[int, int]] = []

        def mark_visible(x: int, y: int) -> None:
            visible_positions.append((x, y))

        def is_blocking_for(x: int, y: int) -> bool:
            return self.is_blocking(x, y)

        compute_fov(origin, is_blocking_for, mark_visible, max_distance)
        return visible_positions

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

        self._ensure_light_callback()

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
                if tile.remove_light_modifier(source.uuid, fire_event=False):
                    changed_positions.append(pos)
            elif new_level is not None:
                if tile.add_illumination(source.uuid, new_level, fire_event=False):
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
                if tile.add_illumination(source.uuid, level, fire_event=False):
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
                if tile.remove_light_modifier(source.uuid, fire_event=False):
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
        senses consume the same authoritative batch exactly once. Magical
        darkness changes request a full field-of-view refresh.

        Args:
            changed_positions: Tiles whose resolved light level changed.
            parent_event: Optional causal parent event UUID.
            requires_fov: Whether the light delta changes vision geometry.
        """
        if not changed_positions:
            return
        channels = {"illumination"}
        if requires_fov:
            channels.update({"vision", "light"})
        self._bump_spatial_revisions(channels)

        has_magical_darkness = requires_fov
        for pos in changed_positions:
            tile = self._tiles.get(pos)
            if tile and tile.resolved_light_level == LightLevel.MAGICAL_DARKNESS:
                has_magical_darkness = True
                break

        batch_hint = SensesUpdateHint(
            requires_fov=has_magical_darkness,
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

    def _ensure_light_callback(self) -> None:
        """Register the movement callback for light source tracking (once)."""
        if self._light_callback_registered:
            return
        self._light_callback_registered = True
        EventQueue.add_on_event_callback(
            self._on_light_movement_event,
            event_types={EventType.SPATIAL_ENTITY_ENTERED},
            phases={EventPhase.COMPLETION},
        )
        self._ensure_blocking_callback()

    def _on_light_movement_event(self, event: Event) -> None:
        """Move light sources when their anchor entity moves."""
        if event.event_type != EventType.SPATIAL_ENTITY_ENTERED:
            return
        if event.phase != EventPhase.COMPLETION:
            return
        if not isinstance(event, SpatialChangeEvent) or event.entity_uuid is None:
            return
        entity_uuid = event.entity_uuid
        new_pos = event.position
        anchor = BaseBlock.get(entity_uuid)
        if anchor is None:
            return
        for light_uuid in anchor.get_attached_light_sources():
            if light_uuid in self._light_sources:
                self.move_light_source(light_uuid, new_pos, parent_event=event.parent_event)

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
        self.recompute_lights_at_position(event.position, parent_event=event.uuid)

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
                    continue

                tile = self._tiles.get(pos)
                if tile is None:
                    continue

                if old_level is not None and new_level is None:
                    if tile.remove_light_modifier(source.uuid, fire_event=False):
                        changed_positions.append(pos)
                elif new_level is not None:
                    if tile.add_illumination(source.uuid, new_level, fire_event=False):
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

        Unlike is_blocking(), this ignores magical darkness — AoE spreads
        through darkness but not through walls/closed doors."""
        tile = self._tiles.get((x, y))
        if tile is None or not tile.visible:
            return True
        for obj_uuid in self._objects_by_position.get((x, y), set()):
            block = BaseBlock.get(obj_uuid)
            if block is not None and block.blocks_vision():
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
            if not tile.visible:
                barriers.add(pos)
            elif any(not tile.allows_direction(direction, "propagation") for direction in DIRECTIONS):
                barriers.add(pos)
        for pos, obj_uuids in self._objects_by_position.items():
            for obj_uuid in obj_uuids:
                block = BaseBlock.get(obj_uuid)
                if block is not None and block.blocks_vision():
                    barriers.add(pos)
        self._barrier_positions_cache = frozenset(barriers)
        return set(barriers)

    def clear(self) -> None:
        """Clear all tiles, entity positions, object positions, subscriptions, and light sources."""
        registered_objects = tuple(self._object_positions.items())
        for object_uuid, position in registered_objects:
            obj = BaseBlock.get(object_uuid)
            if obj is not None:
                obj.on_grid_object_removed(position, clear_location=True)
        self._tiles.clear()
        self._tiles_by_uuid.clear()
        self._entities_by_position.clear()
        self._entity_positions.clear()
        self._object_positions.clear()
        self._objects_by_position.clear()
        self._cell_subscribers.clear()
        self._entity_subscriptions.clear()
        self._light_sources.clear()
        self._block_light_suppressions.clear()
        self._pending_events.clear()
        self._bounds_dirty = True
        self._spatial_revision = 0
        self._vision_revision = 0
        self._movement_revision = 0
        self._light_revision = 0
        self._light_geometry_revision = 0
        self._propagation_revision = 0
        self._fov_cache.clear()
        self._propagation_fov_cache.clear()
        self._propagation_filter_cache.clear()
        self._barrier_positions_cache = None
        self._directional_blockers_cache.clear()
        self._directional_channel_equivalence_cache.clear()
        self._directional_transition_cache.clear()
        self._directional_blocking_cache.clear()
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
