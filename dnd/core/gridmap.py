"""
GridMap - Centralized spatial data management for the D&D engine.

Manages:
- Tile grid (stores Tile objects which can have conditions)
- Spatial queries (walkable, visible, entities at position)
- FOV and pathfinding (with occupancy awareness)
- Entity position registry
- Cell subscriptions for spatial events
"""

import math
from typing import Dict, List, Optional, Tuple, Set, DefaultDict, cast
from uuid import UUID, uuid4
from collections import defaultdict

from pydantic import BaseModel, Field

from dnd.core.geometry import circle_positions
from dnd.core.shadowcast import compute_fov
from dnd.core.dijkstra import dijkstra
from dnd.core.base_block import BaseBlock, MovementMode, LightLevel
from dnd.core.base_tiles import Tile
from dnd.core.events import Event, SpatialChangeEvent, SpatialChangeType, EventPhase, EventQueue, EventType, SensesUpdateHint


class LightSourceData(BaseModel):
    """Tracks a light source and its affected tiles."""
    uuid: UUID = Field(default_factory=uuid4)
    position: Tuple[int, int] = Field(description="Current position of the light source")
    very_bright_radius_feet: int = Field(default=0, description="Radius of very bright light in feet (innermost zone)")
    bright_radius_feet: int = Field(description="Radius of bright light in feet (extends beyond very bright)")
    dim_radius_feet: int = Field(description="Radius of dim light in feet (extends beyond bright)")
    anchor_uuid: Optional[UUID] = Field(default=None, description="BaseBlock this light is attached to (follows its movement)")
    affected_tiles: Dict[Tuple[int, int], LightLevel] = Field(default_factory=dict, description="pos -> level applied")
    is_active: bool = Field(default=True)


class GridMap:
    """
    Singleton-like manager for spatial data.

    Holds the tile grid, entity positions, and provides efficient spatial queries.
    All spatial operations should go through this class.

    Subscription System:
    - Entities subscribe to cells they can see
    - When something changes at a cell, SpatialChangeEvents are fired
    - Subscribed entities receive these events via their EventHandlers
    """

    _instance: Optional['GridMap'] = None

    def __init__(self):
        # Tile storage - now stores actual Tile objects (BaseBlock with conditions)
        self._tiles: Dict[Tuple[int, int], Tile] = {}
        # UUID -> position lookup for tiles
        self._tiles_by_uuid: Dict[UUID, Tuple[int, int]] = {}

        # Cached grid bounds (updated on tile add/remove)
        self._min_x: int = 0
        self._max_x: int = 0
        self._min_y: int = 0
        self._max_y: int = 0
        self._bounds_dirty: bool = True

        # Entity position tracking
        self._entities_by_position: DefaultDict[Tuple[int, int], Set[UUID]] = defaultdict(set)
        self._entity_positions: Dict[UUID, Tuple[int, int]] = {}

        # Object position tracking (items on the grid)
        self._object_positions: Dict[UUID, Tuple[int, int]] = {}
        self._objects_by_position: DefaultDict[Tuple[int, int], Set[UUID]] = defaultdict(set)

        # Cell subscription system
        # cell -> set of entity UUIDs subscribed to that cell
        self._cell_subscribers: DefaultDict[Tuple[int, int], Set[UUID]] = defaultdict(set)
        # entity -> set of cells it's subscribed to
        self._entity_subscriptions: DefaultDict[UUID, Set[Tuple[int, int]]] = defaultdict(set)

        # Light source tracking
        self._light_sources: Dict[UUID, LightSourceData] = {}

        # Event firing enabled flag (can be disabled during batch operations)
        self._events_enabled: bool = True

        # Pending events (when events are disabled, queue them here)
        self._pending_events: List['SpatialChangeEvent'] = []

        # Callback for light source movement (registered once)
        self._light_callback_registered: bool = False

        # Callback for vision-blocking changes (registered once)
        self._blocking_callback_registered: bool = False

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

    # =========================================================================
    # Event Firing
    # =========================================================================

    def _fire_spatial_event(self, event: 'SpatialChangeEvent') -> Optional['SpatialChangeEvent']:
        """
        Fire a spatial change event through full phase lifecycle.

        Progresses: DECLARATION -> EXECUTION -> EFFECT -> COMPLETION

        Returns None if event was cancelled, otherwise returns completed event.
        If events are disabled (batch mode), queues for later and returns None.
        """
        if not self._events_enabled:
            self._pending_events.append(event)
            return None

        # Register at DECLARATION phase - handlers can react/cancel
        current_event = cast(SpatialChangeEvent, EventQueue.register(event))
        if current_event.canceled:
            return None

        # Progress to EXECUTION
        current_event = current_event.phase_to(EventPhase.EXECUTION)
        current_event = cast(SpatialChangeEvent, EventQueue.register(current_event))
        if current_event.canceled:
            return None

        # Progress to EFFECT - this is where damage/saves/conditions happen
        current_event = current_event.phase_to(EventPhase.EFFECT)
        current_event = cast(SpatialChangeEvent, EventQueue.register(current_event))
        if current_event.canceled:
            return None

        # Progress to COMPLETION. Pre-completion lifecycle systems, including
        # sensory updates, run during phase_to(COMPLETION) before metadata is
        # finalized.
        current_event = current_event.phase_to(EventPhase.COMPLETION)
        current_event = cast(SpatialChangeEvent, EventQueue.register(current_event))

        return current_event

    def enable_events(self) -> None:
        """Enable event firing and flush pending events through full lifecycle."""
        self._events_enabled = True
        # Fire all pending events through full lifecycle
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

    # =========================================================================
    # Cell Subscriptions
    # =========================================================================

    def subscribe_to_cells(self, entity_uuid: UUID, cells: Set[Tuple[int, int]]) -> None:
        """
        Subscribe an entity to a set of cells.

        Replaces any existing subscriptions for this entity.
        Typically called after updating entity senses with the visible cells.
        """
        # Get current subscriptions
        old_cells = self._entity_subscriptions.get(entity_uuid, set())

        # Remove from cells we're no longer watching
        for cell in old_cells - cells:
            self._cell_subscribers[cell].discard(entity_uuid)

        # Add to new cells
        for cell in cells - old_cells:
            self._cell_subscribers[cell].add(entity_uuid)

        # Update entity's subscription set
        self._entity_subscriptions[entity_uuid] = cells.copy()

    def unsubscribe_entity(self, entity_uuid: UUID) -> None:
        """Remove all subscriptions for an entity."""
        cells = self._entity_subscriptions.pop(entity_uuid, set())
        for cell in cells:
            self._cell_subscribers[cell].discard(entity_uuid)

    def get_entity_subscriptions(self, entity_uuid: UUID) -> Set[Tuple[int, int]]:
        """Get all cells an entity is subscribed to."""
        return self._entity_subscriptions.get(entity_uuid, set()).copy()

    # =========================================================================
    # Tile Management
    # =========================================================================

    def set_tile(self, x: int, y: int, walkable: bool = True, visible: bool = True,
                 name: str = "Floor", sprite_name: Optional[str] = None,
                 fire_event: bool = True, tile: Optional[Tile] = None) -> Tile:
        """
        Set a tile at the given position.

        If tile parameter is provided, uses that tile directly (updating its position if needed).
        Otherwise creates a new Tile object with the given parameters.
        Returns the stored tile.
        """
        position = (x, y)
        old_tile = self._tiles.get(position)

        # Remove old tile from UUID lookup if exists
        if old_tile:
            self._tiles_by_uuid.pop(old_tile.uuid, None)

        # Use provided tile or create new one
        if tile is not None:
            # Update tile position if needed
            tile.position = position
        else:
            # Create new Tile object
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

        # Fire tile changed event if properties actually changed
        if fire_event and self._events_enabled:
            old_walkable = old_tile.walkable if old_tile else None
            old_visible = old_tile.visible if old_tile else None
            tile_walkable = tile.walkable
            tile_visible = tile.visible
            if old_tile is None or old_walkable != tile_walkable or old_visible != tile_visible:
                event = SpatialChangeEvent.tile_changed(position, tile_walkable, tile_visible)
                self._fire_spatial_event(event)

        return tile

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
        """Check if position is hazardous for a specific entity.
        Checks tile conditions AND object conditions at position (not entities)."""
        tile = self.get_tile(x, y)
        if tile is not None and tile.is_hazardous_for(entity_uuid):
            return True

        # Check objects on tile (items placed on grid — e.g., bear traps, caltrops)
        for obj_uuid in self._objects_by_position.get((x, y), set()):
            obj = BaseBlock.get(obj_uuid)
            if obj is not None and obj.is_hazardous_for(entity_uuid):
                return True

        return False

    def is_position_hazardous(self, x: int, y: int) -> bool:
        """Non-entity-aware hazard check. True if ANY hazard condition exists."""
        return self.is_position_hazardous_for(x, y, entity_uuid=None)

    def is_walkable_for(self, x: int, y: int, requesting_entity_uuid: Optional[UUID] = None,
                        mode: MovementMode = MovementMode.WALKING,
                        walk_in_danger: bool = True,
                        subjective: bool = False,
                        collision_blocked: Optional[Set[Tuple[int, int]]] = None) -> bool:
        """
        Check if position is walkable for a specific entity.

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

        # Check objects at this position (e.g., large boulder blocks walking)
        for obj_uuid in self._objects_by_position.get((x, y), set()):
            block = BaseBlock.get(obj_uuid)
            if block is not None and block.blocks_walking(requesting_entity_uuid, mode):
                if subjective and not block.is_perceivable_by(requesting_entity_uuid):
                    continue
                return False

        # Hazard avoidance when walk_in_danger=False
        if not walk_in_danger:
            if self.is_position_hazardous_for(x, y, requesting_entity_uuid):
                return False

        # Positions remembered as blocked from previous collisions
        if collision_blocked and (x, y) in collision_blocked:
            return False

        return True

    def is_visible(self, x: int, y: int) -> bool:
        """Check if position allows vision (has tile and tile allows vision)."""
        tile = self._tiles.get((x, y))
        return tile is not None and not tile.blocks_vision()

    def is_blocking(self, x: int, y: int, requesting_entity_uuid: Optional[UUID] = None) -> bool:
        """Check if position blocks line of sight (tile or object).
        Magical darkness blocks vision unless observer has TRUESIGHT/DEVILS_SIGHT."""
        tile = self._tiles.get((x, y))
        if tile is None or tile.blocks_vision(requesting_entity_uuid):
            return True
        # Check objects that block vision (e.g., barricade)
        for obj_uuid in self._objects_by_position.get((x, y), set()):
            block = BaseBlock.get(obj_uuid)
            if block is not None and block.blocks_vision(requesting_entity_uuid):
                return True
        return False

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

    # =========================================================================
    # Grid Bounds (cached)
    # =========================================================================

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

    # =========================================================================
    # Grid Creation Helpers
    # =========================================================================

    def create_rectangle(self, x: int, y: int, width: int, height: int,
                         walkable: bool = True, visible: bool = True,
                         name: str = "Floor", sprite_name: Optional[str] = None) -> None:
        """Create a rectangular area of tiles (batch operation, no events during)."""
        self.disable_events()
        try:
            for tx in range(x, x + width):
                for ty in range(y, y + height):
                    # Remove old tile from UUID lookup if exists
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
            self.enable_events()

    def create_room(self, x: int, y: int, width: int, height: int,
                    floor_name: str = "Floor", wall_name: str = "Wall") -> None:
        """Create a room with floor tiles surrounded by wall tiles."""
        self.disable_events()
        try:
            def _set_tile(pos: Tuple[int, int], tile: Tile) -> None:
                old_tile = self._tiles.get(pos)
                if old_tile:
                    self._tiles_by_uuid.pop(old_tile.uuid, None)
                self._tiles[pos] = tile
                self._tiles_by_uuid[tile.uuid] = pos

            # Walls
            for tx in range(x, x + width):
                _set_tile((tx, y), Tile.create((tx, y), walkable=False, visible=False, name=wall_name))
                _set_tile((tx, y + height - 1), Tile.create((tx, y + height - 1), walkable=False, visible=False, name=wall_name))
            for ty in range(y, y + height):
                _set_tile((x, ty), Tile.create((x, ty), walkable=False, visible=False, name=wall_name))
                _set_tile((x + width - 1, ty), Tile.create((x + width - 1, ty), walkable=False, visible=False, name=wall_name))
            # Floor
            for tx in range(x + 1, x + width - 1):
                for ty in range(y + 1, y + height - 1):
                    _set_tile((tx, ty), Tile.create((tx, ty), walkable=True, visible=True, name=floor_name))
            self._bounds_dirty = True
        finally:
            self.enable_events()

    # =========================================================================
    # Entity Position Management
    # =========================================================================

    def register_entity(self, entity_uuid: UUID, position: Tuple[int, int],
                         parent_event: Optional[UUID] = None) -> None:
        """Register an entity at a position."""
        # Remove from old position if exists
        old_pos = self._entity_positions.get(entity_uuid)
        if old_pos is not None:
            self._entities_by_position[old_pos].discard(entity_uuid)
            # Fire entity left event
            if self._events_enabled:
                event = SpatialChangeEvent.entity_left(old_pos, entity_uuid, position, parent_event=parent_event)
                self._fire_spatial_event(event)

        # Add to new position
        self._entity_positions[entity_uuid] = position
        self._entities_by_position[position].add(entity_uuid)

        # Fire entity entered event
        if self._events_enabled:
            event = SpatialChangeEvent.entity_entered(position, entity_uuid, old_pos, parent_event=parent_event)
            self._fire_spatial_event(event)

    def unregister_entity(self, entity_uuid: UUID,
                           parent_event: Optional[UUID] = None) -> None:
        """Remove an entity from position tracking and subscriptions."""
        if entity_uuid in self._entity_positions:
            pos = self._entity_positions[entity_uuid]
            self._entities_by_position[pos].discard(entity_uuid)

            # Fire entity left event
            if self._events_enabled:
                event = SpatialChangeEvent.entity_left(pos, entity_uuid, parent_event=parent_event)
                self._fire_spatial_event(event)

            del self._entity_positions[entity_uuid]

        # Also remove subscriptions
        self.unsubscribe_entity(entity_uuid)

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

        # Update position tracking
        if old_position is not None:
            self._entities_by_position[old_position].discard(entity_uuid)

            # Fire entity left event for old position
            if self._events_enabled:
                event = SpatialChangeEvent.entity_left(old_position, entity_uuid, new_position, parent_event=parent_event)
                self._fire_spatial_event(event)

        self._entity_positions[entity_uuid] = new_position
        self._entities_by_position[new_position].add(entity_uuid)

        # Fire entity entered event for new position
        if self._events_enabled:
            event = SpatialChangeEvent.entity_entered(new_position, entity_uuid, old_position, parent_event=parent_event)
            self._fire_spatial_event(event)

    def get_entity_position(self, entity_uuid: UUID) -> Optional[Tuple[int, int]]:
        """Get an entity's position."""
        return self._entity_positions.get(entity_uuid)

    def get_entities_at(self, position: Tuple[int, int]) -> Set[UUID]:
        """Get all entity UUIDs at a position."""
        return self._entities_by_position.get(position, set()).copy()

    def get_all_entity_positions(self) -> Dict[UUID, Tuple[int, int]]:
        """Get all entity positions."""
        return self._entity_positions.copy()

    # =========================================================================
    # Object Position Management
    # =========================================================================

    def place_object(self, object_uuid: UUID, position: Tuple[int, int],
                      parent_event: Optional[UUID] = None) -> None:
        """Place an object on the grid at a position."""
        self._object_positions[object_uuid] = position
        self._objects_by_position[position].add(object_uuid)
        if self._events_enabled:
            # Check object blocking properties for hint
            obj = BaseBlock.get(object_uuid)
            blocks_vision = obj.blocks_vision() if obj else False
            blocks_walking = obj.blocks_walking() if obj else False
            obj_name = getattr(obj, 'name', None)
            obj_map_char = getattr(obj, 'map_char', None)
            self._fire_spatial_event(SpatialChangeEvent.object_placed(
                position, object_uuid,
                parent_event=parent_event,
                blocks_vision=blocks_vision,
                blocks_walking=blocks_walking,
                object_name=obj_name,
                object_map_char=obj_map_char,
            ))

    def remove_object(self, object_uuid: UUID,
                       parent_event: Optional[UUID] = None) -> None:
        """Remove an object from the grid."""
        # Check blocking properties BEFORE removing (for hint)
        obj = BaseBlock.get(object_uuid)
        blocks_vision = obj.blocks_vision() if obj else False
        blocks_walking = obj.blocks_walking() if obj else False
        position = self._object_positions.pop(object_uuid, None)
        if position is not None:
            self._objects_by_position[position].discard(object_uuid)
            if self._events_enabled:
                self._fire_spatial_event(SpatialChangeEvent.object_removed(
                    position, object_uuid,
                    parent_event=parent_event,
                    blocks_vision=blocks_vision,
                    blocks_walking=blocks_walking,
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

    # =========================================================================
    # FOV and Pathfinding
    # =========================================================================

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
        visible_positions: List[Tuple[int, int]] = []

        def mark_visible(x: int, y: int) -> None:
            visible_positions.append((x, y))

        def is_blocking_for(x: int, y: int) -> bool:
            return self.is_blocking(x, y, requesting_entity_uuid=observer_uuid)

        compute_fov(origin, is_blocking_for, mark_visible, max_distance)
        return visible_positions

    def compute_paths(self, start: Tuple[int, int], max_distance: Optional[int] = None,
                      requesting_entity_uuid: Optional[UUID] = None,
                      movement_mode: MovementMode = MovementMode.WALKING,
                      walk_in_danger: bool = True,
                      subjective: bool = False,
                      collision_blocked: Optional[Set[Tuple[int, int]]] = None,
                      ignore_difficult_terrain: bool = False
                      ) -> Tuple[Dict[Tuple[int, int], int], Dict[Tuple[int, int], List[Tuple[int, int]]]]:
        """
        Compute all reachable positions and paths from start using Dijkstra.

        Args:
            start: Starting position
            max_distance: Maximum distance to compute paths for (in movement cost units)
            requesting_entity_uuid: If provided, treats cells occupied by OTHER entities as blocked.
                                    The requesting entity's own position is always walkable.
            movement_mode: The movement mode to use for pathfinding (affects terrain costs)
            walk_in_danger: If False, hazardous positions are treated as unwalkable

        Returns (distances_dict, paths_dict) where distances account for terrain costs.
        """
        if self._bounds_dirty:
            self._update_bounds()

        # Use actual grid bounds for dijkstra
        # Add padding to handle positions outside current bounds
        grid_width = self._max_x + 2
        grid_height = self._max_y + 2

        # Choose walkability function based on whether we're checking occupancy
        if requesting_entity_uuid is not None:
            def walkable_check(x: int, y: int) -> bool:
                return self.is_walkable_for(x, y, requesting_entity_uuid, movement_mode,
                                            walk_in_danger, subjective, collision_blocked)
        else:
            def walkable_check(x: int, y: int) -> bool:
                return self.is_walkable(x, y, movement_mode)

        # Get tile cost for movement mode
        def get_tile_cost(x: int, y: int) -> float:
            tile = self.get_tile(x, y)
            if not tile:
                return 0  # No tile = impassable
            cost = tile.get_movement_cost(movement_mode)
            if ignore_difficult_terrain:
                return min(cost, 1.0)  # Cap at base cost
            return cost

        # Check if entry is allowed from a direction (border check)
        def can_enter_tile(from_pos: Tuple[int, int], to_pos: Tuple[int, int]) -> bool:
            tile = self.get_tile(*to_pos)
            if not tile:
                return False
            return tile.can_enter_from(from_pos)

        return dijkstra(
            start,
            walkable_check,
            grid_width,
            grid_height,
            diagonal=True,
            max_distance=max_distance,
            cost_func=get_tile_cost,
            can_enter=can_enter_tile
        )

    def get_visible_entities(self, origin: Tuple[int, int], max_distance: Optional[float] = None
                             ) -> Dict[UUID, Tuple[int, int]]:
        """Get all entities visible from origin position."""
        visible_positions = self.compute_fov(origin, max_distance)
        result: Dict[UUID, Tuple[int, int]] = {}

        for pos in visible_positions:
            for entity_uuid in self._entities_by_position.get(pos, set()):
                result[entity_uuid] = pos

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

    # =========================================================================
    # Light Source Management
    # =========================================================================

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

        # Attach to anchor if provided
        if anchor_uuid:
            anchor = BaseBlock.get(anchor_uuid)
            if anchor:
                anchor.attach_light_source(source.uuid)

        # Apply illumination to tiles
        self._apply_light_source(source, parent_event=parent_event)

        # Register movement callback if not already done
        self._ensure_light_callback()

        return source.uuid

    def remove_light_source(self, light_uuid: UUID,
                            parent_event: Optional[UUID] = None) -> None:
        """Remove a light source and clean up tile modifiers."""
        source = self._light_sources.pop(light_uuid, None)
        if source is None:
            return

        # Remove tile illumination
        self._remove_light_source_tiles(source, parent_event=parent_event)

        # Detach from anchor
        if source.anchor_uuid:
            anchor = BaseBlock.get(source.anchor_uuid)
            if anchor:
                anchor.detach_light_source(light_uuid)

    def cleanup_block_light_sources(self, block_uuid: UUID) -> None:
        """Remove all light sources attached to a block (entity or item).
        Called on entity death and item destruction."""
        block = BaseBlock.get(block_uuid)
        if block is None:
            return
        for light_uuid in block.get_attached_light_sources():
            self.remove_light_source(light_uuid)

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

        old_affected = dict(source.affected_tiles)

        # Compute new affected tiles at new position
        new_affected = self._compute_light_tiles(source, new_position)

        # Delta: only modify tiles that actually change
        changed_positions: List[Tuple[int, int]] = []
        all_positions = set(old_affected) | set(new_affected)
        for pos in all_positions:
            old_level = old_affected.get(pos)
            new_level = new_affected.get(pos)
            if old_level == new_level:
                continue  # No change for this tile — skip entirely

            tile = self._tiles.get(pos)
            if tile is None:
                continue

            if old_level is not None and new_level is None:
                # Tile leaving light range — remove illumination
                if tile.remove_light_modifier(source.uuid, fire_event=False):
                    changed_positions.append(pos)
            elif new_level is not None:
                # Tile entering range or level changed — add/update illumination
                if tile.add_illumination(source.uuid, new_level, fire_event=False):
                    changed_positions.append(pos)

        # Update source state
        source.position = new_position
        source.affected_tiles = new_affected

        # Fire events for changed tiles
        self._fire_light_batch_events(changed_positions, parent_event=parent_event)

    def toggle_light_source(self, light_uuid: UUID, active: bool) -> None:
        """Toggle a light source on/off without destroying it."""
        source = self._light_sources.get(light_uuid)
        if source is None:
            return
        if source.is_active == active:
            return

        if active:
            source.is_active = True
            self._apply_light_source(source)
        else:
            self._remove_light_source_tiles(source)
            source.is_active = False

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

    def _fire_light_batch_events(self, changed_positions: List[Tuple[int, int]],
                                  parent_event: Optional[UUID] = None) -> None:
        """Fire efficient events after a batch light change.

        Two-tier approach:
        1. Positions with entities: fire full SPATIAL_LIGHT_CHANGED event lifecycle
           (needed for Hidden reveal handler at EFFECT phase). Very rare.
        2. Single COMPLETION event at one representative position to trigger
           senses re-evaluation via batch hint with ALL changed positions.

        The Tier 2 event carries a SensesUpdateHint with light_changed_positions
        containing all changed positions. If any position has magical darkness,
        requires_fov is set to True.
        """
        if not changed_positions:
            return

        # Detect magical darkness for requires_fov
        has_magical_darkness = False
        for pos in changed_positions:
            tile = self._tiles.get(pos)
            if tile and tile.resolved_light_level == LightLevel.MAGICAL_DARKNESS:
                has_magical_darkness = True
                break

        # Build batch hint with all changed positions
        batch_hint = SensesUpdateHint(
            requires_fov=has_magical_darkness,
            light_changed_positions=set(changed_positions),
        )

        # Tier 1: Full lifecycle for positions with entities (Hidden reveal handler)
        handled_positions: Set[Tuple[int, int]] = set()
        for pos in changed_positions:
            entity_uuids = self._entities_by_position.get(pos, set())
            if entity_uuids:
                handled_positions.add(pos)
                tile = self._tiles.get(pos)
                if tile:
                    # Per-position hint for individual entity events
                    per_pos_hint = SensesUpdateHint(
                        requires_fov=has_magical_darkness,
                        light_changed_positions={pos},
                    )
                    event = SpatialChangeEvent.light_changed(pos, tile.uuid, senses_hint=per_pos_hint,
                                                                   new_light_level=tile.resolved_light_level.value)
                    event.parent_event = parent_event
                    self._fire_spatial_event(event)

        # Tier 2: Single COMPLETION event for senses refresh
        # Pick any unhandled position, or first position if all handled
        senses_pos = None
        for pos in changed_positions:
            if pos not in handled_positions:
                senses_pos = pos
                break
        if senses_pos is None and changed_positions:
            senses_pos = changed_positions[0]
        if senses_pos is not None:
            tile = self._tiles.get(senses_pos)
            if tile:
                # Build per-position light level map for client reducer
                level_map: Dict[str, int] = {}
                for pos in changed_positions:
                    t = self._tiles.get(pos)
                    if t:
                        level_map[f"{pos[0]},{pos[1]}"] = t.resolved_light_level.value
                event = SpatialChangeEvent.light_changed(senses_pos, tile.uuid, senses_hint=batch_hint,
                                                               new_light_level=tile.resolved_light_level.value,
                                                               light_level_map=level_map)
                event.parent_event = parent_event
                current_event = EventQueue.register(event)
                if current_event.canceled:
                    return
                current_event = current_event.phase_to(EventPhase.COMPLETION)
                EventQueue.register(current_event)

    def _ensure_light_callback(self) -> None:
        """Register the movement callback for light source tracking (once)."""
        if self._light_callback_registered:
            return
        self._light_callback_registered = True
        EventQueue.add_on_event_callback(self._on_light_movement_event)
        self._ensure_blocking_callback()

    def _on_light_movement_event(self, event: Event) -> None:
        """Move light sources when their anchor entity moves."""
        if event.event_type != EventType.SPATIAL_ENTITY_ENTERED:
            return
        # Only fire once per event lifecycle (at COMPLETION)
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
        EventQueue.add_on_event_callback(self._on_vision_blocking_changed)

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
            return  # Prevent recursion
        if not isinstance(event, SpatialChangeEvent):
            return
        hint = event.senses_hint
        if hint is None or not hint.requires_fov:
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
            if not source.is_active:
                continue
            # Check if position is within the light's maximum range
            total_radius_tiles = (source.bright_radius_feet + source.dim_radius_feet) / 5
            dx = position[0] - source.position[0]
            dy = position[1] - source.position[1]
            if math.sqrt(dx * dx + dy * dy) > total_radius_tiles:
                continue

            # Save old, recompute new at same position
            old_affected = dict(source.affected_tiles)
            new_affected = self._compute_light_tiles(source)

            # Delta: only modify tiles that actually change
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

    # =========================================================================
    # AoE Prefilter
    # =========================================================================

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

    # =========================================================================
    # AoE Propagation (physical barriers only, ignores magical darkness)
    # =========================================================================

    def is_blocking_propagation(self, x: int, y: int) -> bool:
        """Check if position blocks AoE propagation (physical barriers only).

        Unlike is_blocking(), this ignores magical darkness — AoE spreads
        through darkness but not through walls/closed doors."""
        tile = self._tiles.get((x, y))
        if tile is None or not tile.visible:  # Wall or out-of-bounds
            return True
        for obj_uuid in self._objects_by_position.get((x, y), set()):
            block = BaseBlock.get(obj_uuid)
            if block is not None and block.blocks_vision():  # Closed door, barricade
                return True
        return False

    def compute_propagation_fov(self, origin: Tuple[int, int],
                                max_distance: Optional[float] = None) -> List[Tuple[int, int]]:
        """Compute FOV for AoE propagation (physical barriers only).

        Unlike compute_fov(), ignores magical darkness — AoE spreads through
        darkness but not through walls/closed doors."""
        visible_positions: List[Tuple[int, int]] = []

        def mark_visible(x: int, y: int) -> None:
            visible_positions.append((x, y))

        def is_blocking_for(x: int, y: int) -> bool:
            return self.is_blocking_propagation(x, y)

        compute_fov(origin, is_blocking_for, mark_visible, max_distance)
        return visible_positions

    def get_barrier_positions(self) -> Set[Tuple[int, int]]:
        """Return all positions that block AoE propagation.

        Used for fast-path: if geometric_shape & barrier_positions is empty,
        skip shadowcast entirely."""
        barriers: Set[Tuple[int, int]] = set()
        for pos, tile in self._tiles.items():
            if not tile.visible:  # Wall
                barriers.add(pos)
        for pos, obj_uuids in self._objects_by_position.items():
            for obj_uuid in obj_uuids:
                block = BaseBlock.get(obj_uuid)
                if block is not None and block.blocks_vision():
                    barriers.add(pos)
        return barriers

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def clear(self) -> None:
        """Clear all tiles, entity positions, object positions, subscriptions, and light sources."""
        self._tiles.clear()
        self._tiles_by_uuid.clear()
        self._entities_by_position.clear()
        self._entity_positions.clear()
        self._object_positions.clear()
        self._objects_by_position.clear()
        self._cell_subscribers.clear()
        self._entity_subscriptions.clear()
        self._light_sources.clear()
        self._pending_events.clear()
        self._bounds_dirty = True

    def get_all_tiles(self) -> Dict[Tuple[int, int], Tile]:
        """Get all tiles (for serialization/debugging)."""
        return self._tiles.copy()

    def get_tiles_with_conditions(self) -> List[Tile]:
        """Get tiles with active conditions (for environment step)."""
        return [tile for tile in self._tiles.values() if tile.active_conditions]

    def tile_count(self) -> int:
        """Get number of tiles."""
        return len(self._tiles)

    def entity_count(self) -> int:
        """Get number of registered entities."""
        return len(self._entity_positions)

    def subscription_count(self) -> int:
        """Get total number of cell subscriptions."""
        return sum(len(subs) for subs in self._cell_subscribers.values())


# =========================================================================
# Module-level convenience functions
# =========================================================================

def get_map() -> GridMap:
    """Get the global GridMap instance."""
    return GridMap.get_instance()


def reset_map() -> None:
    """Reset the global GridMap (for testing)."""
    GridMap.reset()
