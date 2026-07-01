"""Observer-local senses cache and reactive sensory update callbacks."""

from typing import Dict, Optional, List, Self, Tuple, Set, DefaultDict, Callable
from uuid import UUID
from pydantic import Field, PrivateAttr

import math
from dataclasses import dataclass
from collections import defaultdict

from dnd.core.base_block import BaseBlock
from dnd.core.gridmap import get_map
from dnd.core.events import (
    Event, EventType, EventPhase, SensesUpdateHint, SpatialChangeEvent,
    DeathEvent, EventQueue, SensoryUpdateEvent, SensoryUpdateReason
)
from dnd.core.base_block import SensesType, SenseMode, LightLevel
from dnd.core.combat_log import CombatLogEntry, CombatLogEntryType, EntitySpottedLogData, HazardDetectedLogData


class Senses(BaseBlock):
    """Per-observer cache of visible cells, objects, entities, and paths."""

    entities: Dict[UUID, Tuple[int, int]] = Field(default_factory=dict, description="Visible entities by UUID and position.")
    objects: Dict[UUID, Tuple[int, int]] = Field(default_factory=dict, description="Visible objects by UUID and position.")
    visible: Dict[Tuple[int, int], bool] = Field(default_factory=dict, description="Cells visible after light and sense-mode filtering.")
    walkable: Dict[Tuple[int, int], bool] = Field(default_factory=dict, description="Walkability for cells in geometric FOV.")
    paths: DefaultDict[Tuple[int, int], List[Tuple[int, int]]] = Field(
        default_factory=lambda: defaultdict(list),
        description="Known subjective paths keyed by destination.",
    )
    safe_paths: Dict[Tuple[int, int], List[Tuple[int, int]]] = Field(
        default_factory=dict,
        description="Known paths that avoid perceptible hazardous tiles.",
    )
    sense_modes: List[SenseMode] = Field(default_factory=list, description="Special sense modes with ranges.")
    seen: Set[Tuple[int, int]] = Field(default_factory=set, description="Cells this observer has previously seen.")
    collision_blocked: Set[Tuple[int, int]] = Field(
        default_factory=set,
        description="Cells discovered blocked by imperceivable entities or objects during movement.",
    )
    directional_collision_blocked: Set[Tuple[Tuple[int, int], str]] = Field(
        default_factory=set,
        description="Tile-relative transitions discovered blocked by imperceivable blockers during movement.",
    )
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

    def add_entity(self, entity_uuid: UUID, position: Tuple[int, int]) -> None:
        """Add a visible entity to the cache."""
        self.entities[entity_uuid] = position

    def get_distance(self, position: Tuple[int, int]) -> int:
        """Return Euclidean tile distance from this senses position."""
        return int(math.sqrt((self.position[0] - position[0])**2 + (self.position[1] - position[1])**2))

    def get_feet_distance(self, position: Tuple[int, int]) -> int:
        """Return Euclidean distance in feet from this senses position."""
        return self.get_distance(position) * 5

    def get_path_to_entity(self, entity_uuid: UUID, max_path_length: Optional[int] = None) -> List[Tuple[int, int]]:
        """Return a cached path to a visible entity, optionally bounded by length."""
        if entity_uuid not in self.entities:
            return []
        path = self.paths.get(self.entities[entity_uuid], [])
        if max_path_length is None or len(path) <= max_path_length:
            return path
        else:
            return []

    def update_seen(self, visible: Dict[Tuple[int, int], bool]) -> None:
        """Add currently visible cells to the memory set."""
        visible_positions = {key for key, value in visible.items() if value}
        self.seen.update(visible_positions)

    def update_senses(
        self,
        entities: Dict[UUID, Tuple[int, int]],
        visible: Dict[Tuple[int, int], bool],
        walkable: Dict[Tuple[int, int], bool],
        paths: DefaultDict[Tuple[int, int], List[Tuple[int, int]]],
        objects: Optional[Dict[UUID, Tuple[int, int]]] = None,
    ) -> None:
        """Replace visible entities, cells, objects, walkability, and paths."""
        self.entities = {}
        self.objects = {}
        self.visible = {}
        self.walkable = {}
        self.paths = defaultdict(list)
        self.entities = entities
        self.objects = objects if objects is not None else {}
        self.visible = visible
        self.update_seen(visible)
        self.walkable = walkable
        self.paths = paths
        self._paths_dirty = False

    def get_threathened_positions(self) -> List[Tuple[int, int]]:
        """Return neighboring positions threatened by this observer.

        A position is threatened if it's:
        1. Adjacent to this entity (including diagonals)
        2. Visible to this entity
        3. On a walkable tile (regardless of occupancy - an occupied cell is still threatened)
        4. Physical propagation can cross from this entity to that tile

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
        candidates = neighbors & visible_set & walkable_set
        grid = get_map()
        return [
            pos for pos in candidates
            if grid.can_propagate_transition(position, pos, self.source_entity_uuid)
        ]

    @classmethod
    def create(
        cls,
        source_entity_uuid: UUID,
        name: str = "Senses",
        source_entity_name: Optional[str] = None,
        target_entity_uuid: Optional[UUID] = None,
        target_entity_name: Optional[str] = None,
        position: Tuple[int, int] = (0, 0),
    ) -> Self:
        """Create a senses block for one owning entity."""
        return cls(source_entity_uuid=source_entity_uuid, name=name, source_entity_name=source_entity_name, target_entity_uuid=target_entity_uuid, target_entity_name=target_entity_name, position=position)

    def create_spatial_callback(
        self,
        owner_uuid: UUID,
        update_senses_func: Optional[Callable[[], None]] = None,
        update_visibility_func: Optional[Callable[[], None]] = None
    ) -> "SpatialSensesCallback":
        """Create the observer-local sensory lifecycle system.

        Uses closure to access the senses instance without importing Entity.
        The system runs before relevant events complete and triggers
        appropriate updates:
        - Self-movement: visibility-only update per step + mark paths dirty
        - Other changes: apply incremental hint (no Dijkstra)
        - Dijkstra runs only at turn start and movement end (explicit calls)

        This uses EventQueue's pre-completion lifecycle hook instead of normal
        EventHandlers because event handlers do not fire at COMPLETION, and
        sensory children must be created before the causative event finalizes
        its stable child-lineage metadata.

        Args:
            owner_uuid: UUID of the entity that owns this Senses block
            update_senses_func: Optional callable to trigger full senses update
                (visibility + paths). Not called from callbacks; only stored
                for potential explicit use.
            update_visibility_func: Optional callable to trigger visibility-only
                update (FOV + entity filter, no Dijkstra).

        Returns:
            SpatialSensesCallback that should be registered with EventQueue as
            a pre-completion callback.
        """
        return SpatialSensesCallback(
            self, owner_uuid, update_senses_func, update_visibility_func
        )


@dataclass(frozen=True)
class SensesSnapshot:
    """Immutable observer cache snapshot used to build sensory deltas."""

    visible: Set[Tuple[int, int]]
    seen: Set[Tuple[int, int]]
    entities: Dict[UUID, Tuple[int, int]]
    objects: Dict[UUID, Tuple[int, int]]
    paths_dirty: bool
    passive_perception: int
    sense_modes_hash: int


def _sorted_positions(positions: Set[Tuple[int, int]]) -> List[Tuple[int, int]]:
    """Return positions sorted for deterministic sensory payloads."""
    return sorted(positions, key=lambda pos: (pos[0], pos[1]))


def _sorted_uuid_position_dict(values: Dict[UUID, Tuple[int, int]]) -> Dict[UUID, Tuple[int, int]]:
    """Return UUID-position mapping sorted by UUID string."""
    return {uuid: values[uuid] for uuid in sorted(values.keys(), key=str)}


def _sorted_uuid_move_dict(
    values: Dict[UUID, Tuple[Tuple[int, int], Tuple[int, int]]]
) -> Dict[UUID, Tuple[Tuple[int, int], Tuple[int, int]]]:
    """Return UUID movement mapping sorted by UUID string."""
    return {uuid: values[uuid] for uuid in sorted(values.keys(), key=str)}


def _serialize_sense_modes(senses: Senses) -> List[Dict[str, object]]:
    """Serialize sense modes into stable event payload dictionaries."""
    return [
        {"sense_type": sm.sense_type.value, "range_feet": sm.range_feet}
        for sm in senses.get_sense_modes()
    ]


class SpatialSensesCallback:
    """Pre-completion lifecycle system that updates one observer's senses.

    This is registered with EventQueue.add_pre_completion_callback() and runs
    before causative events complete. It mutates backend senses exactly where
    the previous reactive callback did, then emits an observer-specific
    SensoryUpdateEvent child so animated clients can consume staged truth.

    Key design principle: Callbacks NEVER run Dijkstra (update_senses_func).
    All paths go through update_visibility_func (FOV only, no paths) plus
    _paths_dirty flag. Full Dijkstra only happens at:
    - Turn start (Encounter.start_turn -> update_entity_senses)
    - Movement end (Move._apply finally -> update_entity_senses)

    The class name is kept for compatibility with existing construction sites,
    but it now acts as a first-class sensory update system rather than a passive
    post-storage callback.
    """

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
    ) -> None:
        """Create a callback bound to one observer.

        Args:
            senses: Senses block to mutate.
            owner_uuid: Owning entity UUID.
            update_senses_func: Stored full recompute callback.
            update_visibility_func: Visibility-only recompute callback.
        """
        self.senses = senses
        self.owner_uuid = owner_uuid
        self.update_senses_func = update_senses_func
        self.update_visibility_func = update_visibility_func

    def __call__(self, event: Event) -> None:
        """Process an event before completion and emit a sensory child if needed."""
        if event.event_type == EventType.SENSORY_UPDATE:
            return

        before = self._snapshot()
        reason: Optional[SensoryUpdateReason] = None

        if event.event_type == EventType.DEATH:
            self._handle_death_event(event)
            reason = SensoryUpdateReason.DEATH

        elif event.event_type in (EventType.CONDITION_APPLICATION, EventType.CONDITION_REMOVAL):
            if event.target_entity_uuid != self.owner_uuid:
                return
            self._handle_own_perception_change()
            reason = SensoryUpdateReason.CONDITION

        elif event.event_type in self.SPATIAL_EVENTS:
            reason = self._handle_spatial_event(event)
            if reason is None:
                return

        else:
            return

        after = self._snapshot()
        self._emit_sensory_update(event, before, after, reason)

    def _handle_spatial_event(self, event: Event) -> Optional[SensoryUpdateReason]:
        """Apply a spatial event or hint to this observer's cache."""
        if not isinstance(event, SpatialChangeEvent):
            return None

        position = event.position
        entity_uuid = event.entity_uuid

        if entity_uuid == self.owner_uuid and event.event_type == EventType.SPATIAL_PERCEIVABILITY_CHANGED:
            return None

        if entity_uuid == self.owner_uuid and event.event_type in (
            EventType.SPATIAL_ENTITY_ENTERED, EventType.SPATIAL_ENTITY_LEFT
        ):
            if event.event_type == EventType.SPATIAL_ENTITY_LEFT:
                return None
            if self.update_visibility_func:
                self.update_visibility_func()
            self.senses._paths_dirty = True
            return SensoryUpdateReason.SELF_MOVEMENT

        hint = event.senses_hint
        if hint is not None:
            self._apply_hint(hint, event)
            return self._reason_for_spatial_event(event)
        else:
            grid = get_map()
            subscribers = grid.get_subscribers_at(position)
            if self.owner_uuid not in subscribers:
                return None
            if self.update_visibility_func:
                self.update_visibility_func()
            self.senses._paths_dirty = True
            return self._reason_for_spatial_event(event)

    def _reason_for_spatial_event(self, event: SpatialChangeEvent) -> SensoryUpdateReason:
        """Map a spatial event type to a sensory update reason."""
        if event.event_type == EventType.SPATIAL_LIGHT_CHANGED:
            return SensoryUpdateReason.LIGHT
        if event.event_type == EventType.SPATIAL_PERCEIVABILITY_CHANGED:
            return SensoryUpdateReason.PERCEIVABILITY
        return SensoryUpdateReason.SPATIAL

    def _snapshot(self) -> SensesSnapshot:
        """Capture current cache state before or after a reactive update."""
        return SensesSnapshot(
            visible={pos for pos, is_visible in self.senses.visible.items() if is_visible},
            seen=set(self.senses.seen),
            entities=dict(self.senses.entities),
            objects=dict(self.senses.objects),
            paths_dirty=self.senses._paths_dirty,
            passive_perception=self.senses._last_passive_perception,
            sense_modes_hash=self.senses._last_sense_modes_hash,
        )

    def _emit_sensory_update(
        self,
        cause_event: Event,
        before: SensesSnapshot,
        after: SensesSnapshot,
        reason: SensoryUpdateReason,
    ) -> None:
        """Emit a completed `SensoryUpdateEvent` if the snapshots differ."""
        visible_added = after.visible - before.visible
        visible_removed = before.visible - after.visible
        seen_added = after.seen - before.seen

        entity_added_keys = set(after.entities) - set(before.entities)
        entity_removed_keys = set(before.entities) - set(after.entities)
        entity_moved = {
            uuid: (before.entities[uuid], after.entities[uuid])
            for uuid in set(before.entities) & set(after.entities)
            if before.entities[uuid] != after.entities[uuid]
        }

        object_added_keys = set(after.objects) - set(before.objects)
        object_removed_keys = set(before.objects) - set(after.objects)
        object_moved = {
            uuid: (before.objects[uuid], after.objects[uuid])
            for uuid in set(before.objects) & set(after.objects)
            if before.objects[uuid] != after.objects[uuid]
        }

        passive_changed = before.passive_perception != after.passive_perception
        sense_modes_changed = before.sense_modes_hash != after.sense_modes_hash
        perception_capability_changed = (
            reason == SensoryUpdateReason.CONDITION
            and (passive_changed or sense_modes_changed)
        )
        paths_refresh_needed = (
            ((not before.paths_dirty) and after.paths_dirty)
            or (perception_capability_changed and after.paths_dirty)
        )

        has_delta = any((
            visible_added,
            visible_removed,
            seen_added,
            entity_added_keys,
            entity_removed_keys,
            entity_moved,
            object_added_keys,
            object_removed_keys,
            object_moved,
            paths_refresh_needed,
            passive_changed,
            sense_modes_changed,
        ))
        if not has_delta:
            return

        sensory_event = SensoryUpdateEvent(
            source_entity_uuid=self.owner_uuid,
            target_entity_uuid=self.owner_uuid,
            observer_uuid=self.owner_uuid,
            cause_event_uuid=cause_event.uuid,
            update_reason=reason,
            parent_event=cause_event.uuid,
            phase=EventPhase.DECLARATION,
            use_register=False,
            visible_cells_added=_sorted_positions(visible_added),
            visible_cells_removed=_sorted_positions(visible_removed),
            seen_cells_added=_sorted_positions(seen_added),
            visible_entities_added=_sorted_uuid_position_dict({
                uuid: after.entities[uuid] for uuid in entity_added_keys
            }),
            visible_entities_removed=_sorted_uuid_position_dict({
                uuid: before.entities[uuid] for uuid in entity_removed_keys
            }),
            visible_entities_moved=_sorted_uuid_move_dict(entity_moved),
            visible_objects_added=_sorted_uuid_position_dict({
                uuid: after.objects[uuid] for uuid in object_added_keys
            }),
            visible_objects_removed=_sorted_uuid_position_dict({
                uuid: before.objects[uuid] for uuid in object_removed_keys
            }),
            visible_objects_moved=_sorted_uuid_move_dict(object_moved),
            paths_dirty=paths_refresh_needed,
            passive_perception_changed=passive_changed,
            passive_perception=after.passive_perception if passive_changed else None,
            sense_modes_changed=sense_modes_changed,
            sense_modes=_serialize_sense_modes(self.senses) if sense_modes_changed else None,
        )

        current = EventQueue.register(sensory_event)
        if current.canceled:
            return
        current = current.phase_to(EventPhase.EXECUTION)
        current = EventQueue.register(current)
        if current.canceled:
            return
        current = current.phase_to(EventPhase.EFFECT)
        current = EventQueue.register(current)
        if current.canceled:
            return
        current = current.phase_to(EventPhase.COMPLETION)
        EventQueue.register(current)

    def _apply_hint(self, hint: SensesUpdateHint, _event: Event) -> None:
        """Apply targeted update based on event hint.

        NEVER calls update_senses_func, so no Dijkstra runs here.
        All path changes set _paths_dirty for deferred recomputation at turn start.
        """
        grid = get_map()

        if hint.requires_fov:
            if self.update_visibility_func:
                self.update_visibility_func()
            if hint.requires_paths:
                self.senses._paths_dirty = True
            return

        if hint.light_changed_positions:
            my_subs = grid.get_entity_subscriptions(self.owner_uuid)
            overlap = hint.light_changed_positions & my_subs
            if not overlap:
                return
            for pos in overlap:
                self._update_visibility_at(pos)
            return

        if hint.entity_entered:
            uuid, pos = hint.entity_entered
            if uuid != self.owner_uuid:
                subs = grid.get_entity_subscriptions(self.owner_uuid)
                if pos in subs:
                    self._try_add_visible_entity(uuid, pos)

        if hint.entity_left:
            uuid, _ = hint.entity_left
            self.senses.entities.pop(uuid, None)

        if hint.entity_died:
            uuid, _ = hint.entity_died
            self.senses.entities.pop(uuid, None)

        if hint.perceivability_entity:
            if hint.perceivability_entity != self.owner_uuid:
                self._recheck_entity_perceivability(hint.perceivability_entity)

        if hint.object_placed:
            uuid, pos = hint.object_placed
            subs = grid.get_entity_subscriptions(self.owner_uuid)
            if pos in subs:
                self._try_add_visible_object(uuid, pos)
        if hint.object_removed:
            uuid, _ = hint.object_removed
            self.senses.objects.pop(uuid, None)

        if hint.requires_paths:
            self.senses._paths_dirty = True

    def _handle_death_event(self, event: Event) -> None:
        """Handle entity death by removing visibility and dirtying paths."""
        if not isinstance(event, DeathEvent):
            return
        dead_uuid = event.entity_uuid

        if dead_uuid == self.owner_uuid:
            return

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
                return
        block = BaseBlock.get(entity_uuid)
        if block and block.is_perceivable_by(self.owner_uuid):
            self.senses.entities[entity_uuid] = position

    def _refilter_entities_at(self, position: Tuple[int, int]) -> None:
        """Re-check all entities at position. Add/remove from senses.entities.

        Generates ENTITY_SPOTTED combat logs for newly visible hidden enemies
        (e.g., light change illuminates a hidden entity).
        """
        grid = get_map()
        old_at_pos = {uuid for uuid, pos in self.senses.entities.items() if pos == position}
        for uuid in old_at_pos:
            del self.senses.entities[uuid]
        for ent_uuid in grid.get_entities_at(position):
            if ent_uuid != self.owner_uuid:
                self._try_add_visible_entity(ent_uuid, position)

        new_at_pos = {uuid for uuid, pos in self.senses.entities.items() if pos == position}
        newly_spotted = new_at_pos - old_at_pos
        if newly_spotted:
            owner = BaseBlock.get(self.owner_uuid)
            if owner:
                pp = owner.get_passive_perception()
                for spotted_uuid in newly_spotted:
                    spotted = BaseBlock.get(spotted_uuid)
                    if spotted and spotted.stealth_dc is not None:
                        log_entry = CombatLogEntry(
                            entry_type=CombatLogEntryType.ENTITY_SPOTTED,
                            source_name=owner.name,
                            source_uuid=str(self.owner_uuid),
                            target_name=spotted.name,
                            target_uuid=str(spotted_uuid),
                            compact=f"{{cyan:{owner.name}}} spots {{yellow:{spotted.name}}} (Perception {pp} vs Stealth DC {spotted.stealth_dc})",
                            verbose=f"{{cyan:{owner.name}}} sees through {{yellow:{spotted.name}}}'s hiding (Passive Perception {pp} vs Stealth DC {spotted.stealth_dc})",
                            detailed=f"{{cyan:{owner.name}}} sees through {{yellow:{spotted.name}}}'s hiding (Passive Perception {pp} vs Stealth DC {spotted.stealth_dc})",
                            data=EntitySpottedLogData(
                                observer_name=owner.name,
                                observer_uuid=str(self.owner_uuid),
                                target_name=spotted.name,
                                target_uuid=str(spotted_uuid),
                                target_position=position,
                                passive_perception=pp,
                                stealth_dc=spotted.stealth_dc
                            ).model_dump()
                        )
                        EventQueue.push_combat_log(log_entry, self.owner_uuid)

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
        grid = get_map()
        if position not in grid.get_entity_subscriptions(self.owner_uuid):
            self.senses.entities.pop(entity_uuid, None)
            return
        if block.is_perceivable_by(self.owner_uuid):
            tile = grid.get_tile(*position)
            if tile:
                eff = tile.get_effective_light_for(self.owner_uuid, self.senses.position)
                if eff.value > LightLevel.DARKNESS.value:
                    self.senses.entities[entity_uuid] = position
                    return
        self.senses.entities.pop(entity_uuid, None)

    def _update_visibility_at(self, position: Tuple[int, int]) -> None:
        """Update senses.visible, entities, and objects at one position after light change.

        Positions are confirmed in the geometric FOV. Only effective light is
        checked here; shadowcast already happened when subscriptions were built.
        """
        grid = get_map()
        tile = grid.get_tile(*position)

        is_lit = True
        if tile:
            eff = tile.get_effective_light_for(self.owner_uuid, self.senses.position)
            if eff.value <= LightLevel.DARKNESS.value:
                is_lit = False

        if is_lit:
            self.senses.visible[position] = True
            self.senses.seen.add(position)
            self._refilter_entities_at(position)
            self._refilter_objects_at(position)
        else:
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
        block = BaseBlock.get(object_uuid)
        if block is None:
            return
        if not block.should_include_in_senses_objects():
            return
        if not block.is_perceivable_by(self.owner_uuid):
            return
        adjacent = (
            position != self.senses.position
            and max(
                abs(position[0] - self.senses.position[0]),
                abs(position[1] - self.senses.position[1]),
            ) <= 1
        )
        if adjacent and block.should_include_in_adjacent_senses_objects():
            self.senses.objects[object_uuid] = position
            return
        if position not in self.senses.visible:
            return
        tile = grid.get_tile(*position)
        if tile:
            effective_light = tile.get_effective_light_for(self.owner_uuid, self.senses.position)
            if effective_light.value <= LightLevel.DARKNESS.value:
                return
        self.senses.objects[object_uuid] = position

    def _handle_own_perception_change(self) -> None:
        """Check if a condition change on self affected our perception capabilities.

        Compares current perception state against snapshot. If changed:
        - Sense modes changed -> full visibility recompute (light filtering changes)
        - Only passive perception changed -> refilter entities + mark paths dirty
        """
        owner = BaseBlock.get(self.owner_uuid)
        if owner is None:
            return

        current_perception = owner.get_passive_perception()
        current_modes_hash = self.senses.compute_sense_modes_hash()

        perception_changed = current_perception != self.senses._last_passive_perception
        modes_changed = current_modes_hash != self.senses._last_sense_modes_hash

        if not perception_changed and not modes_changed:
            return

        old_perception = self.senses._last_passive_perception

        self.senses._last_passive_perception = current_perception
        self.senses._last_sense_modes_hash = current_modes_hash

        if modes_changed:
            if self.update_visibility_func:
                self.update_visibility_func()
            self.senses._paths_dirty = True
        else:
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
                    if cond.condition_stealth_dc >= old_pp and cond.condition_stealth_dc < new_pp:
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
