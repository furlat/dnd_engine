"""
GridMap - Centralized spatial data management for the D&D engine.

Manages:
- Tile grid with cached dimensions
- Spatial queries (walkable, visible, entities at position)
- FOV and pathfinding
- Entity position registry
- Cell subscriptions for spatial events
"""

from typing import Dict, List, Optional, Tuple, Set, DefaultDict
from uuid import UUID, uuid4
from collections import defaultdict
from pydantic import BaseModel, ConfigDict

from dnd.core.shadowcast import compute_fov
from dnd.core.dijkstra import dijkstra


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
        # Tile storage
        self._tiles: Dict[Tuple[int, int], 'TileData'] = {}

        # Cached grid bounds (updated on tile add/remove)
        self._min_x: int = 0
        self._max_x: int = 0
        self._min_y: int = 0
        self._max_y: int = 0
        self._bounds_dirty: bool = True

        # Entity position tracking
        self._entities_by_position: DefaultDict[Tuple[int, int], Set[UUID]] = defaultdict(set)
        self._entity_positions: Dict[UUID, Tuple[int, int]] = {}

        # Cell subscription system
        # cell -> set of entity UUIDs subscribed to that cell
        self._cell_subscribers: DefaultDict[Tuple[int, int], Set[UUID]] = defaultdict(set)
        # entity -> set of cells it's subscribed to
        self._entity_subscriptions: DefaultDict[UUID, Set[Tuple[int, int]]] = defaultdict(set)

        # Event firing enabled flag (can be disabled during batch operations)
        self._events_enabled: bool = True

        # Pending events (when events are disabled, queue them here)
        self._pending_events: List['SpatialChangeEvent'] = []

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

    def _fire_spatial_event(self, event: 'SpatialChangeEvent') -> None:
        """
        Fire a spatial change event.

        If events are enabled, fires immediately.
        If disabled (batch mode), queues for later.
        """
        if self._events_enabled:
            # Event is already registered with EventQueue in its __init__
            # The event system will handle notifying subscribers
            pass
        else:
            self._pending_events.append(event)

    def enable_events(self) -> None:
        """Enable event firing and flush pending events."""
        self._events_enabled = True
        # Flush pending events
        for event in self._pending_events:
            pass  # Events were already registered, just clear the queue
        self._pending_events.clear()

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
                 fire_event: bool = True) -> None:
        """Set a tile at the given position."""
        position = (x, y)
        old_tile = self._tiles.get(position)

        self._tiles[position] = TileData(
            walkable=walkable,
            visible=visible,
            name=name,
            sprite_name=sprite_name
        )
        self._bounds_dirty = True

        # Fire tile changed event if properties actually changed
        if fire_event and self._events_enabled:
            if old_tile is None or old_tile.walkable != walkable or old_tile.visible != visible:
                from dnd.core.events import SpatialChangeEvent
                event = SpatialChangeEvent.tile_changed(position, walkable, visible)
                self._fire_spatial_event(event)

    def remove_tile(self, x: int, y: int, fire_event: bool = True) -> None:
        """Remove a tile at the given position."""
        position = (x, y)
        if position in self._tiles:
            del self._tiles[position]
            self._bounds_dirty = True

            if fire_event and self._events_enabled:
                from dnd.core.events import SpatialChangeEvent, SpatialChangeType
                event = SpatialChangeEvent(
                    source_entity_uuid=uuid4(),
                    change_type=SpatialChangeType.TILE_REMOVED,
                    position=position
                )
                self._fire_spatial_event(event)

    def get_tile(self, x: int, y: int) -> Optional['TileData']:
        """Get tile data at position, or None if no tile exists."""
        return self._tiles.get((x, y))

    def has_tile(self, x: int, y: int) -> bool:
        """Check if a tile exists at position."""
        return (x, y) in self._tiles

    def is_walkable(self, x: int, y: int) -> bool:
        """Check if position is walkable (has tile and tile is walkable)."""
        tile = self._tiles.get((x, y))
        return tile is not None and tile.walkable

    def is_visible(self, x: int, y: int) -> bool:
        """Check if position allows vision (has tile and tile allows vision)."""
        tile = self._tiles.get((x, y))
        return tile is not None and tile.visible

    def is_blocking(self, x: int, y: int) -> bool:
        """Check if position blocks line of sight."""
        tile = self._tiles.get((x, y))
        return tile is None or not tile.visible

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
                    self._tiles[(tx, ty)] = TileData(
                        walkable=walkable, visible=visible,
                        name=name, sprite_name=sprite_name
                    )
            self._bounds_dirty = True
        finally:
            self.enable_events()

    def create_room(self, x: int, y: int, width: int, height: int,
                    floor_name: str = "Floor", wall_name: str = "Wall") -> None:
        """Create a room with floor tiles surrounded by wall tiles."""
        self.disable_events()
        try:
            # Walls
            for tx in range(x, x + width):
                self._tiles[(tx, y)] = TileData(walkable=False, visible=False, name=wall_name)
                self._tiles[(tx, y + height - 1)] = TileData(walkable=False, visible=False, name=wall_name)
            for ty in range(y, y + height):
                self._tiles[(x, ty)] = TileData(walkable=False, visible=False, name=wall_name)
                self._tiles[(x + width - 1, ty)] = TileData(walkable=False, visible=False, name=wall_name)
            # Floor
            for tx in range(x + 1, x + width - 1):
                for ty in range(y + 1, y + height - 1):
                    self._tiles[(tx, ty)] = TileData(walkable=True, visible=True, name=floor_name)
            self._bounds_dirty = True
        finally:
            self.enable_events()

    # =========================================================================
    # Entity Position Management
    # =========================================================================

    def register_entity(self, entity_uuid: UUID, position: Tuple[int, int]) -> None:
        """Register an entity at a position."""
        # Remove from old position if exists
        old_pos = self._entity_positions.get(entity_uuid)
        if old_pos is not None:
            self._entities_by_position[old_pos].discard(entity_uuid)
            # Fire entity left event
            if self._events_enabled:
                from dnd.core.events import SpatialChangeEvent
                event = SpatialChangeEvent.entity_left(old_pos, entity_uuid, position)
                self._fire_spatial_event(event)

        # Add to new position
        self._entity_positions[entity_uuid] = position
        self._entities_by_position[position].add(entity_uuid)

        # Fire entity entered event
        if self._events_enabled:
            from dnd.core.events import SpatialChangeEvent
            event = SpatialChangeEvent.entity_entered(position, entity_uuid, old_pos)
            self._fire_spatial_event(event)

    def unregister_entity(self, entity_uuid: UUID) -> None:
        """Remove an entity from position tracking and subscriptions."""
        if entity_uuid in self._entity_positions:
            pos = self._entity_positions[entity_uuid]
            self._entities_by_position[pos].discard(entity_uuid)

            # Fire entity left event
            if self._events_enabled:
                from dnd.core.events import SpatialChangeEvent
                event = SpatialChangeEvent.entity_left(pos, entity_uuid)
                self._fire_spatial_event(event)

            del self._entity_positions[entity_uuid]

        # Also remove subscriptions
        self.unsubscribe_entity(entity_uuid)

    def move_entity(self, entity_uuid: UUID, new_position: Tuple[int, int]) -> None:
        """Move an entity to a new position and fire spatial events."""
        old_position = self._entity_positions.get(entity_uuid)

        # Update position tracking
        if old_position is not None:
            self._entities_by_position[old_position].discard(entity_uuid)

            # Fire entity left event for old position
            if self._events_enabled:
                from dnd.core.events import SpatialChangeEvent
                event = SpatialChangeEvent.entity_left(old_position, entity_uuid, new_position)
                self._fire_spatial_event(event)

        self._entity_positions[entity_uuid] = new_position
        self._entities_by_position[new_position].add(entity_uuid)

        # Fire entity entered event for new position
        if self._events_enabled:
            from dnd.core.events import SpatialChangeEvent
            event = SpatialChangeEvent.entity_entered(new_position, entity_uuid, old_position)
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
    # FOV and Pathfinding
    # =========================================================================

    def compute_fov(self, origin: Tuple[int, int], max_distance: Optional[float] = None) -> List[Tuple[int, int]]:
        """
        Compute field of view from a position using shadowcasting.

        Returns list of visible positions.
        """
        visible_positions: List[Tuple[int, int]] = []

        def mark_visible(x: int, y: int) -> None:
            visible_positions.append((x, y))

        compute_fov(origin, self.is_blocking, mark_visible, max_distance)
        return visible_positions

    def compute_paths(self, start: Tuple[int, int], max_distance: Optional[int] = None
                      ) -> Tuple[Dict[Tuple[int, int], int], Dict[Tuple[int, int], List[Tuple[int, int]]]]:
        """
        Compute all reachable positions and paths from start using Dijkstra.

        Returns (distances_dict, paths_dict).
        """
        if self._bounds_dirty:
            self._update_bounds()

        # Use actual grid bounds for dijkstra
        # Add padding to handle positions outside current bounds
        grid_width = self._max_x + 2
        grid_height = self._max_y + 2

        return dijkstra(
            start,
            lambda x, y: self.is_walkable(x, y),
            grid_width,
            grid_height,
            diagonal=True,
            max_distance=max_distance
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
                 max_distance: Optional[int] = None) -> Optional[List[Tuple[int, int]]]:
        """Get path from start to end, or None if no path exists."""
        distances, paths = self.compute_paths(start, max_distance)
        return paths.get(end)

    def get_distance(self, start: Tuple[int, int], end: Tuple[int, int]) -> Optional[int]:
        """Get walking distance from start to end, or None if unreachable."""
        distances, _ = self.compute_paths(start)
        return distances.get(end)

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def clear(self) -> None:
        """Clear all tiles, entity positions, and subscriptions."""
        self._tiles.clear()
        self._entities_by_position.clear()
        self._entity_positions.clear()
        self._cell_subscribers.clear()
        self._entity_subscriptions.clear()
        self._pending_events.clear()
        self._bounds_dirty = True

    def get_all_tiles(self) -> Dict[Tuple[int, int], 'TileData']:
        """Get all tiles (for serialization/debugging)."""
        return self._tiles.copy()

    def tile_count(self) -> int:
        """Get number of tiles."""
        return len(self._tiles)

    def entity_count(self) -> int:
        """Get number of registered entities."""
        return len(self._entity_positions)

    def subscription_count(self) -> int:
        """Get total number of cell subscriptions."""
        return sum(len(subs) for subs in self._cell_subscribers.values())


class TileData(BaseModel):
    """Lightweight tile data (no UUID, just properties)."""
    model_config = ConfigDict(frozen=True)

    walkable: bool = True
    visible: bool = True
    name: str = "Floor"
    sprite_name: Optional[str] = None


# =========================================================================
# Module-level convenience functions
# =========================================================================

def get_map() -> GridMap:
    """Get the global GridMap instance."""
    return GridMap.get_instance()


def reset_map() -> None:
    """Reset the global GridMap (for testing)."""
    GridMap.reset()
