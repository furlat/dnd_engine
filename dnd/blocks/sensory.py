from typing import Dict, Optional, List, Self, Tuple, Set, DefaultDict, Callable
from uuid import UUID
from pydantic import Field, PrivateAttr

import math
from collections import defaultdict

from dnd.core.base_block import BaseBlock
from dnd.core.gridmap import get_map
from dnd.core.events import Event, EventType, EventPhase, SensesUpdateHint, SpatialChangeEvent, DeathEvent, EventQueue
from dnd.core.base_block import SensesType, SenseMode, LightLevel
from dnd.core.combat_log import CombatLogEntry, CombatLogEntryType, EntitySpottedLogData, HazardDetectedLogData


class Senses(BaseBlock):
    """ A block that contains the senses of a creature"""
    entities : Dict[UUID,Tuple[int,int]] = Field(default_factory=dict)
    objects: Dict[UUID,Tuple[int,int]] = Field(default_factory=dict, description="Visible objects by UUID → position")
    visible: Dict[Tuple[int,int],bool] = Field(default_factory=dict)
    walkable: Dict[Tuple[int,int],bool] = Field(default_factory=dict)
    paths: DefaultDict[Tuple[int,int],List[Tuple[int,int]]] = Field(default_factory=lambda: defaultdict(list))
    safe_paths: Dict[Tuple[int,int],List[Tuple[int,int]]] = Field(default_factory=dict, description="Paths avoiding hazardous tiles (empty if no hazards)")
    sense_modes: List[SenseMode] = Field(default_factory=list, description="Special sense modes (Darkvision, Blindsight, etc.) with ranges")
    seen: Set[Tuple[int,int]] = Field(default_factory=set, description="A list of positions that the entity has seen")
    _paths_dirty: bool = PrivateAttr(default=False)
    _last_passive_perception: int = PrivateAttr(default=0)
    _last_sense_modes_hash: int = PrivateAttr(default=0)

    def compute_sense_modes_hash(self) -> int:
        """Hash of current sense modes for quick change detection."""
        return hash(tuple(sorted(
            (sm.sense_type.value, sm.range_feet) for sm in self.sense_modes
        )))

    def snapshot_perception(self, passive_perception: int) -> None:
        """Store current perception state for change detection."""
        self._last_passive_perception = passive_perception
        self._last_sense_modes_hash = self.compute_sense_modes_hash()

    def has_sense(self, sense_type: SensesType) -> bool:
        """Check if entity has a sense type (any range)."""
        return any(sm.sense_type == sense_type for sm in self.sense_modes)

    def has_sense_in_range(self, sense_type: SensesType, distance_feet: int) -> bool:
        """Check if a sense type covers a specific distance."""
        for sm in self.sense_modes:
            if sm.sense_type == sense_type:
                return sm.range_feet == 0 or distance_feet <= sm.range_feet
        return False

    def get_sense_range(self, sense_type: SensesType) -> int:
        """Returns range in feet. -1 = not present, 0 = unlimited."""
        for sm in self.sense_modes:
            if sm.sense_type == sense_type:
                return sm.range_feet
        return -1

    def get_sense_modes(self) -> List[SenseMode]:
        """Return this block's sense modes. Override of BaseBlock.get_sense_modes()."""
        return self.sense_modes

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


    def update_senses(self, entities: Dict[UUID,Tuple[int,int]], visible: Dict[Tuple[int,int],bool], walkable: Dict[Tuple[int,int],bool], paths: DefaultDict[Tuple[int,int],List[Tuple[int,int]]], objects: Optional[Dict[UUID,Tuple[int,int]]] = None):
        #sets all to empty dicts
        self.entities = {}
        self.objects = {}
        self.visible = {}
        self.walkable = {}
        self.paths = defaultdict(list)
        #sets all to the new values
        self.entities = entities
        self.objects = objects if objects is not None else {}
        self.visible = visible
        self.update_seen(visible)
        self.walkable = walkable
        self.paths = paths
        self._paths_dirty = False

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
        - Self-movement: visibility-only update per step + mark paths dirty
        - Other changes: apply incremental hint (no Dijkstra)
        - Dijkstra runs only at turn start and movement end (explicit calls)

        This uses the passive callback system (EventQueue._on_event_callbacks)
        instead of EventHandlers because spatial events fire at COMPLETION phase
        and we don't need to modify them, just react to them.

        Args:
            owner_uuid: UUID of the entity that owns this Senses block
            update_senses_func: Optional callable to trigger full senses update
                (visibility + paths). Not called from callbacks — only stored
                for potential explicit use.
            update_visibility_func: Optional callable to trigger visibility-only
                update (FOV + entity filter, no Dijkstra).

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
    targeted incremental updates using SensesUpdateHint carried by each event.

    Key design principle: Callbacks NEVER run Dijkstra (update_senses_func).
    All paths go through update_visibility_func (FOV only, no paths) plus
    _paths_dirty flag. Full Dijkstra only happens at:
    - Turn start (Encounter.start_turn → update_entity_senses)
    - Movement end (Move._apply finally → update_entity_senses)

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
        EventType.SPATIAL_OBJECT_PLACED,
        EventType.SPATIAL_OBJECT_REMOVED,
        EventType.SPATIAL_OBJECT_CHANGED,
        EventType.SPATIAL_PERCEIVABILITY_CHANGED,
        EventType.SPATIAL_LIGHT_CHANGED,
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

    def __call__(self, event: Event) -> None:
        """Process any event, filtering to events that affect our senses.

        NEVER calls update_senses_func (no Dijkstra). All paths through
        the callback use only update_visibility_func + _paths_dirty.
        """
        # Handle DEATH events - dead entity no longer blocks paths
        if event.event_type == EventType.DEATH:
            self._handle_death_event(event)
            return

        # Handle condition changes on self → check perception capabilities update
        if event.event_type in (EventType.CONDITION_APPLICATION, EventType.CONDITION_REMOVAL):
            if event.phase == EventPhase.COMPLETION:
                if event.target_entity_uuid == self.owner_uuid:
                    self._handle_own_perception_change()
            return

        # Handle spatial events only
        if event.event_type not in self.SPATIAL_EVENTS:
            return

        # Only process at COMPLETION phase (one update per event lifecycle)
        if event.phase != EventPhase.COMPLETION:
            return

        # Spatial events are always SpatialChangeEvent
        if not isinstance(event, SpatialChangeEvent):
            return

        position = event.position
        entity_uuid = event.entity_uuid

        # Skip self-perceivability events (our own hiding doesn't affect our own senses)
        if entity_uuid == self.owner_uuid and event.event_type == EventType.SPATIAL_PERCEIVABILITY_CHANGED:
            return

        # Self-movement events: visibility-only + paths dirty
        # Uniform for walking, teleport, and forced movement (no is_moving flag)
        if entity_uuid == self.owner_uuid and event.event_type in (
            EventType.SPATIAL_ENTITY_ENTERED, EventType.SPATIAL_ENTITY_LEFT
        ):
            if self.update_visibility_func:
                self.update_visibility_func()
            self.senses._paths_dirty = True
            return

        # For all other events: use hint if available
        hint = event.senses_hint
        if hint is not None:
            self._apply_hint(hint, event)
        else:
            # Fallback for events without hints: check subscription, visibility-only + paths dirty
            grid = get_map()
            subscribers = grid.get_subscribers_at(position)
            if self.owner_uuid not in subscribers:
                return
            if self.update_visibility_func:
                self.update_visibility_func()
            self.senses._paths_dirty = True

    def _apply_hint(self, hint: SensesUpdateHint, _event: Event) -> None:
        """Apply targeted update based on event hint.

        NEVER calls update_senses_func — no Dijkstra.
        All path changes set _paths_dirty for deferred recomputation at turn start.
        """
        grid = get_map()

        # FOV change (magical darkness, wall, door vision blocking) → recompute FOV
        if hint.requires_fov:
            if self.update_visibility_func:
                self.update_visibility_func()
            if hint.requires_paths:
                self.senses._paths_dirty = True
            return  # FOV recompute subsumes entity re-filtering

        # Light changes: check subscription overlap, update visibility + entities + objects
        if hint.light_changed_positions:
            my_subs = grid.get_entity_subscriptions(self.owner_uuid)
            overlap = hint.light_changed_positions & my_subs
            if not overlap:
                return  # No tiles in our FOV changed
            for pos in overlap:
                self._update_visibility_at(pos)
            return  # Light changes don't affect paths

        # Entity entered: add to visible dict if perceivable + lit
        if hint.entity_entered:
            uuid, pos = hint.entity_entered
            if uuid != self.owner_uuid:
                subs = grid.get_entity_subscriptions(self.owner_uuid)
                if pos in subs:
                    self._try_add_visible_entity(uuid, pos)

        # Entity left: remove from visible dict
        if hint.entity_left:
            uuid, _ = hint.entity_left
            self.senses.entities.pop(uuid, None)

        # Entity died: remove from visible + mark paths dirty
        if hint.entity_died:
            uuid, _ = hint.entity_died
            self.senses.entities.pop(uuid, None)

        # Perceivability changed: re-check one entity
        if hint.perceivability_entity:
            if hint.perceivability_entity != self.owner_uuid:
                self._recheck_entity_perceivability(hint.perceivability_entity)

        # Object updates
        if hint.object_placed:
            uuid, pos = hint.object_placed
            subs = grid.get_entity_subscriptions(self.owner_uuid)
            if pos in subs:
                self._try_add_visible_object(uuid, pos)
        if hint.object_removed:
            uuid, _ = hint.object_removed
            self.senses.objects.pop(uuid, None)

        # Mark paths dirty (deferred to turn start)
        if hint.requires_paths:
            self.senses._paths_dirty = True

    def _handle_death_event(self, event: Event) -> None:
        """Handle entity death — remove from visible + mark paths dirty."""
        if not isinstance(event, DeathEvent):
            return
        dead_uuid = event.entity_uuid

        # Ignore if WE died
        if dead_uuid == self.owner_uuid:
            return

        # Remove dead entity from visible entities and mark paths dirty
        if dead_uuid in self.senses.entities:
            self.senses.entities.pop(dead_uuid, None)
            self.senses._paths_dirty = True

    def _try_add_visible_entity(self, entity_uuid: UUID, position: Tuple[int, int]) -> None:
        """Check light + perceivability, add to senses.entities if visible."""
        grid = get_map()
        tile = grid.get_tile(*position)
        if tile:
            effective_light = tile.get_effective_light_for(self.owner_uuid, self.senses.position)
            if effective_light.value <= LightLevel.DARKNESS.value:
                return  # Too dark to see
        block = BaseBlock.get(entity_uuid)
        if block and block.is_perceivable_by(self.owner_uuid):
            self.senses.entities[entity_uuid] = position

    def _refilter_entities_at(self, position: Tuple[int, int]) -> None:
        """Re-check all entities at position. Add/remove from senses.entities."""
        grid = get_map()
        # Remove entities currently tracked at this position
        to_remove = [uuid for uuid, pos in self.senses.entities.items() if pos == position]
        for uuid in to_remove:
            del self.senses.entities[uuid]
        # Re-add entities that pass light + perceivability check
        for ent_uuid in grid.get_entities_at(position):
            if ent_uuid != self.owner_uuid:
                self._try_add_visible_entity(ent_uuid, position)

    def _recheck_entity_perceivability(self, entity_uuid: UUID) -> None:
        """Re-check if a specific entity should be in visible set."""
        block = BaseBlock.get(entity_uuid)
        if block is None:
            self.senses.entities.pop(entity_uuid, None)
            return
        position = block.position
        if position is None:
            self.senses.entities.pop(entity_uuid, None)
            return
        # Check subscription
        grid = get_map()
        if position not in grid.get_entity_subscriptions(self.owner_uuid):
            self.senses.entities.pop(entity_uuid, None)
            return
        # Check light + perceivability
        if block.is_perceivable_by(self.owner_uuid):
            tile = grid.get_tile(*position)
            if tile:
                eff = tile.get_effective_light_for(self.owner_uuid, self.senses.position)
                if eff.value > LightLevel.DARKNESS.value:
                    self.senses.entities[entity_uuid] = position
                    return
        # Failed checks → remove
        self.senses.entities.pop(entity_uuid, None)

    def _update_visibility_at(self, position: Tuple[int, int]) -> None:
        """Update senses.visible, entities, and objects at one position after light change.

        Positions are confirmed in the geometric FOV (they're in subscriptions).
        We only check effective light — no shadowcast needed.
        """
        grid = get_map()
        tile = grid.get_tile(*position)

        is_lit = True
        if tile:
            eff = tile.get_effective_light_for(self.owner_uuid, self.senses.position)
            if eff.value <= LightLevel.DARKNESS.value:
                is_lit = False

        if is_lit:
            # Now visible — add to visible + seen, refilter entities/objects
            self.senses.visible[position] = True
            self.senses.seen.add(position)
            self._refilter_entities_at(position)
            self._refilter_objects_at(position)
        else:
            # Now dark — remove from visible, remove entities/objects there
            self.senses.visible.pop(position, None)
            to_remove = [u for u, p in self.senses.entities.items() if p == position]
            for u in to_remove:
                del self.senses.entities[u]
            to_remove_obj = [u for u, p in self.senses.objects.items() if p == position]
            for u in to_remove_obj:
                del self.senses.objects[u]

    def _refilter_objects_at(self, position: Tuple[int, int]) -> None:
        """Re-check all objects at position. Add/remove from senses.objects."""
        grid = get_map()
        to_remove = [uuid for uuid, pos in self.senses.objects.items() if pos == position]
        for uuid in to_remove:
            del self.senses.objects[uuid]
        for obj_uuid in grid.get_objects_at(position):
            self._try_add_visible_object(obj_uuid, position)

    def _try_add_visible_object(self, object_uuid: UUID, position: Tuple[int, int]) -> None:
        """Add object to senses.objects if in visible area."""
        grid = get_map()
        tile = grid.get_tile(*position)
        if tile:
            effective_light = tile.get_effective_light_for(self.owner_uuid, self.senses.position)
            if effective_light.value <= LightLevel.DARKNESS.value:
                return  # Too dark to see
        self.senses.objects[object_uuid] = position

    def _handle_own_perception_change(self) -> None:
        """Check if a condition change on self affected our perception capabilities.

        Compares current perception state against snapshot. If changed:
        - Sense modes changed → full visibility recompute (light filtering changes)
        - Only passive perception changed → refilter entities + mark paths dirty
        """
        owner = BaseBlock.get(self.owner_uuid)
        if owner is None:
            return

        current_perception = owner.get_passive_perception()
        current_modes_hash = self.senses.compute_sense_modes_hash()

        perception_changed = current_perception != self.senses._last_passive_perception
        modes_changed = current_modes_hash != self.senses._last_sense_modes_hash

        if not perception_changed and not modes_changed:
            return  # No perception change — skip

        # Save old values for combat log comparison
        old_perception = self.senses._last_passive_perception

        # Update snapshots
        self.senses._last_passive_perception = current_perception
        self.senses._last_sense_modes_hash = current_modes_hash

        if modes_changed:
            # Sense modes changed (Darkvision, Truesight, etc.)
            # → Full visibility recompute (light filtering changes)
            if self.update_visibility_func:
                self.update_visibility_func()
            self.senses._paths_dirty = True
        else:
            # Only passive perception changed → just refilter entities + hazard paths
            self._refilter_all_visible_entities(old_perception, current_perception)
            self.senses._paths_dirty = True

    def _refilter_all_visible_entities(self, old_perception: int, new_perception: int) -> None:
        """Re-check all entities in visible area for perceivability changes.

        Also logs ENTITY_SPOTTED for newly visible hidden enemies and
        HAZARD_DETECTED for newly detectable hidden hazards.
        """
        grid = get_map()
        old_entities = set(self.senses.entities.keys())

        new_entities: Dict[UUID, Tuple[int, int]] = {}
        for pos in self.senses.visible:
            for ent_uuid in grid.get_entities_at(pos):
                if ent_uuid != self.owner_uuid:
                    block = BaseBlock.get(ent_uuid)
                    if block and block.is_perceivable_by(self.owner_uuid):
                        tile = grid.get_tile(*pos)
                        if tile:
                            eff = tile.get_effective_light_for(self.owner_uuid, self.senses.position)
                            if eff.value > LightLevel.DARKNESS.value:
                                new_entities[ent_uuid] = pos
                        else:
                            new_entities[ent_uuid] = pos

        self.senses.entities = new_entities

        # Log newly spotted hidden enemies
        newly_spotted = set(new_entities.keys()) - old_entities
        owner = BaseBlock.get(self.owner_uuid)
        if owner and newly_spotted:
            for spotted_uuid in newly_spotted:
                spotted = BaseBlock.get(spotted_uuid)
                if spotted and spotted.stealth_dc is not None:
                    log_entry = CombatLogEntry(
                        entry_type=CombatLogEntryType.ENTITY_SPOTTED,
                        source_name=owner.name,
                        source_uuid=str(self.owner_uuid),
                        target_name=spotted.name,
                        target_uuid=str(spotted_uuid),
                        compact=f"{{cyan:{owner.name}}} spots {{yellow:{spotted.name}}} (Perception {new_perception} vs Stealth DC {spotted.stealth_dc})",
                        verbose=f"{{cyan:{owner.name}}} sees through {{yellow:{spotted.name}}}'s hiding (Passive Perception {new_perception} vs Stealth DC {spotted.stealth_dc})",
                        detailed=f"{{cyan:{owner.name}}} sees through {{yellow:{spotted.name}}}'s hiding (Passive Perception {new_perception} vs Stealth DC {spotted.stealth_dc})",
                        data=EntitySpottedLogData(
                            observer_name=owner.name,
                            observer_uuid=str(self.owner_uuid),
                            target_name=spotted.name,
                            target_uuid=str(spotted_uuid),
                            target_position=spotted.position,
                            passive_perception=new_perception,
                            stealth_dc=spotted.stealth_dc
                        ).model_dump()
                    )
                    EventQueue.push_combat_log(log_entry, self.owner_uuid)

        # Log newly detected hidden hazards (perception increased)
        if new_perception > old_perception and owner:
            self._log_newly_detected_hazards(old_perception, new_perception)

    def _log_newly_detected_hazards(self, old_pp: int, new_pp: int) -> None:
        """Log hazards that became detectable due to perception increase."""
        grid = get_map()
        owner = BaseBlock.get(self.owner_uuid)
        if not owner:
            return
        for pos in self.senses.visible:
            tile = grid.get_tile(*pos)
            if tile is None:
                continue
            for cond in tile.active_conditions.values():
                if cond.condition_stealth_dc is not None and cond.hazard_filter is not None:
                    # Was hidden before, visible now?
                    if cond.condition_stealth_dc > old_pp and cond.condition_stealth_dc <= new_pp:
                        log_entry = CombatLogEntry(
                            entry_type=CombatLogEntryType.HAZARD_DETECTED,
                            source_name=owner.name,
                            source_uuid=str(self.owner_uuid),
                            compact=f"{{cyan:{owner.name}}} detects {{red:{cond.name}}} at ({pos[0]},{pos[1]})",
                            verbose=f"{{cyan:{owner.name}}} spots hidden {{red:{cond.name}}} at ({pos[0]},{pos[1]}) (Perception {new_pp} vs DC {cond.condition_stealth_dc})",
                            detailed=f"{{cyan:{owner.name}}} spots hidden {{red:{cond.name}}} at ({pos[0]},{pos[1]}) (Perception {new_pp} vs DC {cond.condition_stealth_dc})",
                            data=HazardDetectedLogData(
                                observer_name=owner.name,
                                observer_uuid=str(self.owner_uuid),
                                hazard_name=cond.name if cond.name else "Unknown",
                                position=pos,
                                passive_perception=new_pp,
                                stealth_dc=cond.condition_stealth_dc
                            ).model_dump()
                        )
                        EventQueue.push_combat_log(log_entry, self.owner_uuid)
