from typing import Dict, Optional, List, Self, Tuple, Set, DefaultDict, TYPE_CHECKING, Callable
from uuid import UUID
from pydantic import Field


from enum import Enum

import math
from collections import defaultdict

from dnd.core.base_block import BaseBlock
from dnd.core.gridmap import get_map
from dnd.core.events import ( EventType, SpatialChangeType)

if TYPE_CHECKING:
    from dnd.core.events import Event

class SensesType(str, Enum):
    BLINDSIGHT = "Blindsight"
    DARKVISION = "Darkvision"
    TREMORSENSE = "Tremorsense"
    TRUESIGHT = "Truesight"

class Senses(BaseBlock):
    """ A block that contains the senses of a creature"""
    entities : Dict[UUID,Tuple[int,int]] = Field(default_factory=dict)
    visible: Dict[Tuple[int,int],bool] = Field(default_factory=dict)
    walkable: Dict[Tuple[int,int],bool] = Field(default_factory=dict)
    paths: DefaultDict[Tuple[int,int],List[Tuple[int,int]]] = Field(default_factory=lambda: defaultdict(list))
    extra_senses: List[SensesType] = Field(default_factory=list)
    seen: Set[Tuple[int,int]] = Field(default_factory=set, description="A list of positions that the entity has seen")



    def add_entity(self,entity_uuid: UUID,position: Tuple[int,int]):
        """ add an entity to the senses"""
        self.entities[entity_uuid] = position

    def get_distance(self,position: Tuple[int,int]) -> int:
        """ get the euclidean distance between the position and the position of the senses"""
        return int(math.sqrt((self.position[0] - position[0])**2 + (self.position[1] - position[1])**2))
    
    def get_feet_distance(self,position: Tuple[int,int]) -> int:
        """ get the euclidean distance in feet between the position and the position of the senses and then multiply by 5 to obtain the distance in feet"""
        return self.get_distance(position) * 5
    
    def get_path_to_entity(self,entity_uuid: UUID, max_path_length: Optional[int] = None) -> List[Tuple[int,int]]:
        """ Get the path to the entity"""
        if entity_uuid not in self.entities:
            return []
        path = self.paths.get(self.entities[entity_uuid],[])
        if max_path_length is None or len(path) <= max_path_length:
            return path
        else:
            return []
    
    def update_seen(self, visible: Dict[Tuple[int,int],bool]):
        """ update the seen list"""
        visible_positions = set([key for key,value in visible.items() if value])
        self.seen.update(visible_positions)

    
    def update_senses(self,  entities: Dict[UUID,Tuple[int,int]], visible: Dict[Tuple[int,int],bool], walkable: Dict[Tuple[int,int],bool],paths: DefaultDict[Tuple[int,int],List[Tuple[int,int]]]):
        #sets all to empty dicts
        self.entities = {}
        self.visible = {}
        self.walkable = {}
        self.paths = defaultdict(list)
        #sets all to the new values
        self.entities = entities
        self.visible = visible
        self.update_seen(visible)
        self.walkable = walkable
        self.paths = paths

    def get_threathened_positions(self) -> List[Tuple[int,int]]:
        """
        Get all neighboring positions that this entity threatens (for opportunity attacks).

        A position is threatened if it's:
        1. Adjacent to this entity (including diagonals)
        2. Visible to this entity
        3. On a walkable tile (regardless of occupancy - an occupied cell is still threatened)

        Note: Uses tile walkability (self.walkable), not paths, because paths exclude
        occupied cells but an enemy standing in a cell is still threatened.
        """
        position = self.position
        neighbors = set([
            (position[0] + 1, position[1]),
            (position[0] - 1, position[1]),
            (position[0], position[1] + 1),
            (position[0], position[1] - 1),
            (position[0] + 1, position[1] + 1),
            (position[0] - 1, position[1] - 1),
            (position[0] + 1, position[1] - 1),
            (position[0] - 1, position[1] + 1),
        ])
        visible_set = set(self.visible.keys())
        walkable_set = set(pos for pos, is_walkable in self.walkable.items() if is_walkable)
        return list(neighbors & visible_set & walkable_set)
        

    @classmethod
    def create(cls,source_entity_uuid: UUID,name: str = "Senses", source_entity_name: Optional[str] = None, target_entity_uuid: Optional[UUID] = None, target_entity_name: Optional[str] = None, position: Tuple[int,int] = (0,0)) -> Self:
        return cls(source_entity_uuid=source_entity_uuid, name=name, source_entity_name=source_entity_name, target_entity_uuid=target_entity_uuid, target_entity_name=target_entity_name, position=position)

    def create_spatial_callback(
        self,
        owner_uuid: UUID,
        update_senses_func: Optional[Callable[[], None]] = None,
        update_visibility_func: Optional[Callable[[], None]] = None
    ) -> "SpatialSensesCallback":
        """Create a callback that updates senses when spatial events fire.

        Uses closure to access the senses instance without importing Entity.
        The callback fires on SPATIAL events and triggers appropriate updates:
        - During movement (is_moving=True): visibility-only update
        - Otherwise: full senses update (visibility + paths)

        This uses the passive callback system (EventQueue._on_event_callbacks)
        instead of EventHandlers because spatial events fire at COMPLETION phase
        and we don't need to modify them, just react to them.

        Args:
            owner_uuid: UUID of the entity that owns this Senses block
            update_senses_func: Optional callable to trigger full senses update
                (visibility + paths). Used when not moving.
            update_visibility_func: Optional callable to trigger visibility-only
                update. Used during movement for efficiency.

        Returns:
            SpatialSensesCallback that should be registered with EventQueue
        """
        return SpatialSensesCallback(
            self, owner_uuid, update_senses_func, update_visibility_func
        )


class SpatialSensesCallback:
    """Callback that updates senses when spatial events fire.

    This is registered with EventQueue.add_on_event_callback() and fires
    for ALL events. It filters to events that affect senses and triggers
    appropriate updates:
    - Entity movement: recompute paths (entities block movement)
    - Tile changes: recompute FOV + paths (tiles block vision and movement)
    - Entity death: recompute paths (dead bodies no longer block movement)

    When the owner entity is moving (is_moving=True), only visibility is updated
    per step for efficiency. Full path recomputation happens at movement end.

    Using callbacks instead of EventHandlers because:
    - Spatial events fire at COMPLETION phase
    - EventHandlers don't fire for COMPLETION events (by design)
    - Callbacks fire for ALL events and can't modify them (perfect for reactive senses)
    """

    # Spatial event types we care about
    SPATIAL_EVENTS = (
        EventType.SPATIAL_ENTITY_ENTERED,
        EventType.SPATIAL_ENTITY_LEFT,
        EventType.SPATIAL_TILE_CHANGED,
    )

    def __init__(
        self,
        senses: Senses,
        owner_uuid: UUID,
        update_senses_func: Optional[Callable[[], None]] = None,
        update_visibility_func: Optional[Callable[[], None]] = None
    ):
        self.senses = senses
        self.owner_uuid = owner_uuid
        self.update_senses_func = update_senses_func
        self.update_visibility_func = update_visibility_func

    def __call__(self, event: "Event") -> None:
        """Process any event, filtering to events that affect our senses."""
        # Handle DEATH events - dead entity no longer blocks paths
        if event.event_type == EventType.DEATH:
            self._handle_death_event(event)
            return

        # Handle spatial events
        if event.event_type not in self.SPATIAL_EVENTS:
            return

        # Get position from event
        position = getattr(event, 'position', None)
        if position is None:
            return

        # Handle self-movement events (we moved to a new cell)
        entity_uuid = getattr(event, 'entity_uuid', None)
        if entity_uuid == self.owner_uuid:
            # Get entity to check is_moving flag
            from dnd.entity import Entity
            entity = Entity.get(self.owner_uuid)
            if entity:
                if entity.is_moving:
                    # During movement: visibility-only update per step
                    # Paths are recomputed once at end of Move._apply()
                    if self.update_visibility_func:
                        self.update_visibility_func()
                else:
                    # Not moving (e.g., teleport, forced movement): full update
                    if self.update_senses_func:
                        self.update_senses_func()
            return

        # Check if owner is subscribed to the affected cell
        grid = get_map()
        subscribers = grid.get_subscribers_at(position)
        if self.owner_uuid not in subscribers:
            return  # Not watching this cell, ignore

        # Trigger senses update (other entity moved in our FOV)
        if self.update_senses_func is not None:
            # Full senses update - recalculates FOV, paths, and entities
            # This is the proper behavior for real-time updates
            self.update_senses_func()
        else:
            # Fallback: incremental entity dict update only (legacy behavior)
            # This only tracks "who is where" without recalculating paths
            change_type = getattr(event, 'change_type', None)
            if change_type == SpatialChangeType.ENTITY_ENTERED:
                if entity_uuid is not None:
                    self.senses.entities[entity_uuid] = position
            elif change_type == SpatialChangeType.ENTITY_LEFT:
                if entity_uuid is not None:
                    self.senses.entities.pop(entity_uuid, None)

    def _handle_death_event(self, event: "Event") -> None:
        """Handle entity death - dead entities no longer block paths."""
        # Get the dead entity's UUID
        dead_uuid = getattr(event, 'entity_uuid', None)
        if dead_uuid is None:
            return

        # Ignore if WE died
        if dead_uuid == self.owner_uuid:
            return

        # Check if the dead entity was in our visible entities
        # If so, we need to recalculate paths (dead body no longer blocks)
        if dead_uuid in self.senses.entities:
            if self.update_senses_func is not None:
                self.update_senses_func()
            else:
                # Fallback: just remove from entities dict
                self.senses.entities.pop(dead_uuid, None)
    
