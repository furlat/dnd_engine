"""Observer-local senses cache and reactive sensory update callbacks."""

from typing import Callable, DefaultDict, Dict, List, Optional, Self, Set, Tuple, TypeVar
from uuid import UUID
from pydantic import Field, PrivateAttr

from dataclasses import dataclass
from collections import defaultdict

from dnd.core.base_block import BaseBlock
from dnd.core.base_tiles import Tile
from dnd.core.elevation import support_distance_feet
from dnd.core.gridmap import get_map
from dnd.core.values import ModifiableValue
from dnd.core.events.events_registry import (
    Event,
    EventType,
    EventPhase,
    EventQueue,
)
from dnd.core.events.world_events import (
    SensesUpdateHint,
    SpatialChangeEvent,
    SpatialEffectChangeEvent,
    SensoryUpdateEvent,
    SensoryUpdateReason,
)
from dnd.core.events.encounter_events import (
    DeathEvent,
)
from dnd.types.senses import SensesType, SenseMode
from dnd.types.world import LightLevel
from dnd.core.combat_log import CombatLogEntry, CombatLogEntryType, EntitySpottedLogData, HazardDetectedLogData


K = TypeVar("K")


@dataclass(frozen=True)
class VisibilityComputationCache:
    """One-shot visibility result that can seed an immediate full senses refresh.

    Attributes:
        position: Observer position used for the computation.
        max_distance: Maximum FOV distance used for the computation.
        visible: Light-filtered visible cells keyed by position.
        fov_positions: Geometric FOV positions before light filtering.
        entities: Visible entities keyed by UUID and position.
        objects: Visible objects keyed by UUID and position.
    """

    position: Tuple[int, int]
    max_distance: int
    visible: Dict[Tuple[int, int], bool]
    fov_positions: List[Tuple[int, int]]
    entities: Dict[UUID, Tuple[int, int]]
    objects: Dict[UUID, Tuple[int, int]]


class Senses(BaseBlock):
    """Per-observer cache of visible cells, objects, entities, and paths."""

    visual_access: ModifiableValue = Field(
        default_factory=lambda: ModifiableValue.create(
            source_entity_uuid=UUID(int=0),
            base_value=1,
            value_name="Visual Access",
        ),
        description="Neutral 1/0 gate for whether visual perception is available.",
    )
    entities: Dict[UUID, Tuple[int, int]] = Field(default_factory=dict, description="Visible entities by UUID and position.")
    objects: Dict[UUID, Tuple[int, int]] = Field(default_factory=dict, description="Visible objects by UUID and position.")
    visible: Dict[Tuple[int, int], bool] = Field(default_factory=dict, description="Cells visible after light and sense-mode filtering.")
    walkable: Dict[Tuple[int, int], bool] = Field(default_factory=dict, description="Walkability for cells in geometric FOV.")
    paths: DefaultDict[Tuple[int, int], List[Tuple[int, int]]] = Field(
        default_factory=lambda: defaultdict(list),
        description="Known subjective paths keyed by destination.",
    )
    path_costs: Dict[Tuple[int, int], int] = Field(
        default_factory=dict,
        description="Known subjective movement costs in feet keyed by destination.",
    )
    safe_paths: Dict[Tuple[int, int], List[Tuple[int, int]]] = Field(
        default_factory=dict,
        description="Known paths that avoid perceptible hazardous tiles.",
    )
    safe_path_costs: Dict[Tuple[int, int], int] = Field(
        default_factory=dict,
        description="Known safe-path movement costs in feet keyed by destination.",
    )
    sense_modes: List[SenseMode] = Field(default_factory=list, description="Special sense modes with ranges.")
    sense_mode_sources: Dict[UUID, SenseMode] = Field(
        default_factory=dict,
        description="Source-owned structural special senses keyed by grant UUID.",
    )
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
    _last_visual_access: int = PrivateAttr(default=1)
    _visibility_cache: Optional[VisibilityComputationCache] = PrivateAttr(default=None)
    _path_revision: int = PrivateAttr(default=0)
    _path_max_distance: Optional[int] = PrivateAttr(default=None)

    @property
    def path_revision(self) -> int:
        """Return the revision of the observer's materialized path facts."""
        return self._path_revision

    @property
    def path_max_distance(self) -> Optional[int]:
        """Return the maximum movement-cost distance covered by cached paths."""
        return self._path_max_distance

    def has_clean_paths_for_distance(self, max_distance: int) -> bool:
        """Return whether cached paths are clean and cover the requested radius."""
        return (
            not self._paths_dirty
            and self._path_max_distance is not None
            and self._path_max_distance >= max_distance
        )

    def compute_sense_modes_hash(self) -> int:
        """Hash of current sense modes for quick change detection."""
        return hash(tuple(sorted(
            (sm.sense_type.value, sm.range_feet)
            for sm in self.get_sense_modes()
        )))

    def snapshot_perception(self, passive_perception: int) -> None:
        """Store current perception state for change detection."""
        self._last_passive_perception = passive_perception
        self._last_sense_modes_hash = self.compute_sense_modes_hash()
        self._last_visual_access = self.visual_access.normalized_score

    def clear_visibility_cache(self) -> None:
        """Discard the one-shot visibility result used by movement refreshes."""
        self._visibility_cache = None

    def has_sense(self, sense_type: SensesType) -> bool:
        """Check if entity has a sense type (any range)."""
        return any(
            sm.sense_type == sense_type for sm in self.get_sense_modes()
        )

    def get_effective_light_levels(self, observer_uuid: UUID) -> Dict[str, int]:
        """Return subjective light for every cell currently visible to an observer.

        Args:
            observer_uuid: Entity whose special senses resolve the light levels.

        Returns:
            Mapping keyed as ``"x,y"`` with integer ``LightLevel`` values.
        """
        grid = get_map()
        levels: Dict[str, int] = {}
        for position, is_visible in sorted(self.visible.items()):
            if not is_visible:
                continue
            tile = grid.get_tile(*position)
            if tile is None:
                continue
            levels[f"{position[0]},{position[1]}"] = tile.get_effective_light_for(
                observer_uuid,
                self.position,
            ).value
        return levels

    def get_sense_range(self, sense_type: SensesType) -> int:
        """Returns range in feet. -1 = not present, 0 = unlimited."""
        for sm in self.get_sense_modes():
            if sm.sense_type == sense_type:
                return sm.range_feet
        return -1

    def get_sense_modes(self) -> List[SenseMode]:
        """Return this block's sense modes. Override of BaseBlock.get_sense_modes()."""
        ranges: Dict[SensesType, int] = {}
        for mode in (*self.sense_modes, *self.sense_mode_sources.values()):
            current = ranges.get(mode.sense_type)
            if current is None:
                ranges[mode.sense_type] = mode.range_feet
            elif current == 0 or mode.range_feet == 0:
                ranges[mode.sense_type] = 0
            else:
                ranges[mode.sense_type] = max(current, mode.range_feet)
        return [
            SenseMode(sense_type=sense_type, range_feet=range_feet)
            for sense_type, range_feet in sorted(
                ranges.items(),
                key=lambda row: row[0].value,
            )
        ]

    def add_sense_mode_source(
        self,
        source_id: UUID,
        mode: SenseMode,
    ) -> None:
        """Install one source-owned special sense contribution."""
        existing = self.sense_mode_sources.get(source_id)
        if existing is not None and existing != mode:
            raise ValueError(
                f"sense source {source_id} already owns a different mode",
            )
        self.sense_mode_sources[source_id] = mode

    def remove_sense_mode_source(self, source_id: UUID) -> bool:
        """Remove exactly one source-owned special sense contribution."""
        return self.sense_mode_sources.pop(source_id, None) is not None

    def get_distance(self, position: Tuple[int, int]) -> int:
        """Return elevation-aware support distance in five-foot units."""
        return self.get_feet_distance(position) // 5

    def get_feet_distance(self, position: Tuple[int, int]) -> int:
        """Return elevation-aware support-point distance in feet."""
        grid = get_map()
        source_tile = grid.get_tile(*self.position)
        target_tile = grid.get_tile(*position)
        if source_tile is None or target_tile is None:
            raise ValueError("distance requires both support tiles")
        return support_distance_feet(
            self.position,
            source_tile.height * 5,
            position,
            target_tile.height * 5,
        )

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
        path_costs: Optional[Dict[Tuple[int, int], int]] = None,
        safe_paths: Optional[Dict[Tuple[int, int], List[Tuple[int, int]]]] = None,
        safe_path_costs: Optional[Dict[Tuple[int, int], int]] = None,
        path_max_distance: Optional[int] = None,
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
        self.path_costs = path_costs if path_costs is not None else {}
        self.safe_paths = safe_paths if safe_paths is not None else {}
        self.safe_path_costs = safe_path_costs if safe_path_costs is not None else {}
        self._path_max_distance = path_max_distance
        self._paths_dirty = False
        self._visibility_cache = None
        self._path_revision += 1

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

    position: Tuple[int, int]
    visible: Set[Tuple[int, int]]
    seen: Set[Tuple[int, int]]
    entities: Dict[UUID, Tuple[int, int]]
    objects: Dict[UUID, Tuple[int, int]]
    paths_dirty: bool
    passive_perception: int
    sense_modes_hash: int
    visual_access: int


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


def _serialize_sense_modes(senses: Senses) -> List[SenseMode]:
    """Copy current sense modes into an immutable event payload list."""
    return [sense_mode.model_copy(deep=True) for sense_mode in senses.get_sense_modes()]


def capture_senses_snapshot(senses: Senses) -> SensesSnapshot:
    """Capture the observer cache fields carried by sensory delta events.

    Args:
        senses: Observer-local senses component to snapshot.

    Returns:
        Immutable sensory state suitable for before/after comparison.
    """
    return SensesSnapshot(
        position=senses.position,
        visible={pos for pos, is_visible in senses.visible.items() if is_visible},
        seen=set(senses.seen),
        entities=dict(senses.entities),
        objects=dict(senses.objects),
        paths_dirty=senses._paths_dirty,
        passive_perception=senses._last_passive_perception,
        sense_modes_hash=senses._last_sense_modes_hash,
        visual_access=senses._last_visual_access,
    )


def emit_sensory_update_delta(
    senses: Senses,
    owner_uuid: UUID,
    cause_event: Event,
    before: SensesSnapshot,
    after: SensesSnapshot,
    reason: SensoryUpdateReason,
    *,
    register_event: bool = True,
) -> Optional[SensoryUpdateEvent]:
    """Emit a completed sensory event for one observer-cache transition.

    Args:
        senses: Observer-local senses component after the transition.
        owner_uuid: Entity UUID that owns the senses component.
        cause_event: Causal engine event under which to parent the delta.
        before: Sensory state before the transition.
        after: Sensory state after the transition.
        reason: Typed reason for the sensory transition.
        register_event: Whether to register the completed event immediately.

    Returns:
        The completed sensory event when the snapshots differ, otherwise None.
    """
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
    visual_access_changed = before.visual_access != after.visual_access
    position_changed = before.position != after.position
    light_changed = reason == SensoryUpdateReason.LIGHT
    perception_capability_changed = (
        reason in {SensoryUpdateReason.CONDITION, SensoryUpdateReason.LIFE_STATE}
        and (passive_changed or sense_modes_changed or visual_access_changed)
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
        visual_access_changed,
        position_changed,
        light_changed,
    ))
    if not has_delta:
        return None

    sensory_event = SensoryUpdateEvent(
        source_entity_uuid=owner_uuid,
        target_entity_uuid=owner_uuid,
        observer_uuid=owner_uuid,
        observer_position=after.position,
        observer_position_changed=position_changed,
        effective_light_levels=senses.get_effective_light_levels(owner_uuid),
        cause_event_uuid=cause_event.uuid,
        update_reason=reason,
        parent_event=cause_event.uuid,
        parent_lineage=cause_event.lineage_uuid,
        phase=EventPhase.COMPLETION,
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
        sense_modes=_serialize_sense_modes(senses) if sense_modes_changed else None,
    )
    if register_event:
        EventQueue.register(sensory_event)
    return sensory_event


class SpatialSensesCallback:
    """Pre-completion lifecycle system that updates one observer's senses.

    This is registered with EventQueue.add_pre_completion_callback() and runs
    before causative events complete. It mutates backend senses exactly where
    the previous reactive callback did, then emits one observer-specific
    completed SensoryUpdateEvent carrying the immutable delta.

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
        EventType.SPATIAL_EFFECT_CHANGED,
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

    def __call__(
        self,
        event: Event,
        *,
        register_event: bool = True,
    ) -> Optional[SensoryUpdateEvent]:
        """Process an event and return its observer-specific sensory delta.

        Args:
            event: Causal engine event being processed before completion.
            register_event: Whether to register the sensory event immediately.

        Returns:
            The completed sensory event when the observer state changed.
        """
        if event.event_type == EventType.SENSORY_UPDATE:
            return
        reason: Optional[SensoryUpdateReason] = None

        if event.event_type == EventType.DEATH:
            before = self._snapshot()
            self._handle_death_event(event)
            reason = SensoryUpdateReason.DEATH

        elif event.event_type in (
            EventType.CONDITION_APPLICATION,
            EventType.CONDITION_REMOVAL,
            EventType.LIFE_STATE_CHANGE,
        ):
            if event.target_entity_uuid != self.owner_uuid:
                return
            before = self._snapshot()
            self._handle_own_perception_change()
            reason = (
                SensoryUpdateReason.LIFE_STATE
                if event.event_type == EventType.LIFE_STATE_CHANGE
                else SensoryUpdateReason.CONDITION
            )

        elif event.event_type in self.SPATIAL_EVENTS:
            might_affect = self._spatial_event_might_affect_self(event)
            if not might_affect:
                return
            before = self._snapshot()
            reason = self._handle_spatial_event(event)
            if reason is None:
                return

        else:
            return

        after = self._snapshot()
        return self._emit_sensory_update(
            event,
            before,
            after,
            reason,
            register_event=register_event,
        )

    def _spatial_event_might_affect_self(self, event: Event) -> bool:
        """Return whether a spatial event can change this observer's senses."""
        if isinstance(event, SpatialEffectChangeEvent):
            return (
                not self.senses._paths_dirty
                and any(
                    self._position_touches_known_path_space(position)
                    for position in event.get_affected_positions()
                )
            )
        if not isinstance(event, SpatialChangeEvent):
            return False

        position = event.position
        entity_uuid = event.entity_uuid

        if entity_uuid == self.owner_uuid and event.event_type == EventType.SPATIAL_PERCEIVABILITY_CHANGED:
            return False
        if entity_uuid == self.owner_uuid and event.event_type == EventType.SPATIAL_ENTITY_LEFT:
            return False
        if entity_uuid == self.owner_uuid and event.event_type == EventType.SPATIAL_ENTITY_ENTERED:
            return True
        if event.event_type == EventType.SPATIAL_ENTITY_LEFT and event.old_position is not None:
            return False

        hint = event.senses_hint
        if hint is None:
            return self.owner_uuid in get_map().get_subscribers_at(position)

        subscriptions: Optional[Set[Tuple[int, int]]] = None

        def subscribed_to(pos: Optional[Tuple[int, int]]) -> bool:
            nonlocal subscriptions
            if pos is None:
                return False
            if subscriptions is None:
                subscriptions = get_map().get_entity_subscriptions(self.owner_uuid)
            return pos in subscriptions

        if hint.light_changed_positions:
            if subscriptions is None:
                subscriptions = get_map().get_entity_subscriptions(self.owner_uuid)
            if hint.light_changed_positions & subscriptions:
                return True

        if hint.entity_entered:
            uuid, pos = hint.entity_entered
            if uuid != self.owner_uuid and subscribed_to(pos):
                return True

        if hint.entity_left:
            uuid, pos = hint.entity_left
            if uuid in self.senses.entities or subscribed_to(pos):
                return True

        if hint.entity_died:
            uuid, _ = hint.entity_died
            if uuid in self.senses.entities:
                return True

        if hint.perceivability_entity:
            if hint.perceivability_entity != self.owner_uuid:
                if hint.perceivability_entity in self.senses.entities:
                    return True
                if subscribed_to(get_map().get_entity_position(hint.perceivability_entity)):
                    return True

        if hint.object_placed:
            _, pos = hint.object_placed
            if subscribed_to(pos):
                return True

        if hint.object_removed:
            uuid, pos = hint.object_removed
            if uuid in self.senses.objects or subscribed_to(pos):
                return True

        if hint.directional_positions:
            if any(subscribed_to(pos) for pos in hint.directional_positions):
                return True

        if hint.directional_neighbors:
            if any(subscribed_to(pos) for pos in hint.directional_neighbors):
                return True

        return bool(
            hint.requires_paths
            and not self.senses._paths_dirty
            and self._path_hint_touches_known_space(hint, event)
        )

    def _path_hint_touches_known_space(self, hint: SensesUpdateHint, event: SpatialChangeEvent) -> bool:
        """Return whether a path invalidation hint touches known path space."""
        for position in self._path_hint_positions(hint, event):
            if self._position_touches_known_path_space(position):
                return True
        return False

    def _path_hint_positions(
        self,
        hint: SensesUpdateHint,
        event: SpatialChangeEvent,
    ) -> Set[Tuple[int, int]]:
        """Return positions whose movement topology may have changed."""
        positions: Set[Tuple[int, int]] = {event.position}
        if hint.entity_entered:
            positions.add(hint.entity_entered[1])
        if hint.entity_left:
            positions.add(hint.entity_left[1])
        if hint.entity_died:
            positions.add(hint.entity_died[1])
        if hint.object_placed:
            positions.add(hint.object_placed[1])
        if hint.object_removed:
            positions.add(hint.object_removed[1])
        if hint.directional_positions:
            positions.update(hint.directional_positions)
        if hint.directional_neighbors:
            positions.update(hint.directional_neighbors)
        return positions

    def _position_touches_known_path_space(self, position: Tuple[int, int]) -> bool:
        """Return whether a position belongs to this observer's path domain."""
        return (
            position in self.senses.visible
            or position in self.senses.seen
            or position in self.senses.paths
            or position in self.senses.safe_paths
        )

    def _handle_spatial_event(self, event: Event) -> Optional[SensoryUpdateReason]:
        """Apply a spatial event or hint to this observer's cache."""
        if isinstance(event, SpatialEffectChangeEvent):
            self.senses.clear_visibility_cache()
            self.senses._paths_dirty = True
            return SensoryUpdateReason.SPATIAL
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
        return capture_senses_snapshot(self.senses)

    def _emit_sensory_update(
        self,
        cause_event: Event,
        before: SensesSnapshot,
        after: SensesSnapshot,
        reason: SensoryUpdateReason,
        *,
        register_event: bool = True,
    ) -> Optional[SensoryUpdateEvent]:
        """Emit a completed `SensoryUpdateEvent` if the snapshots differ."""
        return emit_sensory_update_delta(
            self.senses,
            self.owner_uuid,
            cause_event,
            before,
            after,
            reason,
            register_event=register_event,
        )

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

        self.senses.clear_visibility_cache()

        if hint.light_changed_positions:
            my_subs = grid.get_entity_subscriptions(self.owner_uuid)
            overlap = hint.light_changed_positions & my_subs
            if not overlap:
                return
            refresh_positions = self._light_positions_requiring_visibility_refresh(overlap)
            if refresh_positions:
                self._update_visibility_for_light_positions(refresh_positions)
                self.senses._paths_dirty = True
            return

        if hint.entity_left:
            uuid, _ = hint.entity_left
            self.senses.entities.pop(uuid, None)

        if hint.entity_entered:
            uuid, pos = hint.entity_entered
            if uuid != self.owner_uuid:
                subs = grid.get_entity_subscriptions(self.owner_uuid)
                if pos in subs:
                    self._try_add_visible_entity(uuid, pos)

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
        if not self._is_tile_lit_for_observer(tile):
            return
        block = BaseBlock.get(entity_uuid)
        if block and block.is_perceivable_by(self.owner_uuid):
            self.senses.entities[entity_uuid] = position

    def _is_tile_lit_for_observer(self, tile: Optional[Tile]) -> bool:
        """Return whether a tile is lit in this observer's subjective light model."""
        if tile is None:
            return True
        if tile.resolved_light_level.value >= LightLevel.BRIGHT_LIGHT.value:
            return True
        return (
            tile.get_effective_light_for(
                self.owner_uuid,
                self.senses.position,
            ).value
            > LightLevel.DARKNESS.value
        )

    def _log_newly_spotted_entities(self, entity_uuids: Set[UUID]) -> None:
        """Publish observer-scoped logs for newly perceivable hidden entities.

        Args:
            entity_uuids: Entities newly added to this observer's visible set.
        """
        if not entity_uuids:
            return
        owner = BaseBlock.get(self.owner_uuid)
        if owner is None:
            return
        passive_perception = owner.get_passive_perception()
        for spotted_uuid in sorted(entity_uuids, key=str):
            spotted = BaseBlock.get(spotted_uuid)
            if spotted is None or spotted.stealth_dc is None:
                continue
            log_entry = CombatLogEntry(
                entry_type=CombatLogEntryType.ENTITY_SPOTTED,
                source_name=owner.name,
                source_uuid=str(self.owner_uuid),
                target_name=spotted.name,
                target_uuid=str(spotted_uuid),
                compact=f"{{cyan:{owner.name}}} spots {{yellow:{spotted.name}}} (Perception {passive_perception} vs Stealth DC {spotted.stealth_dc})",
                verbose=f"{{cyan:{owner.name}}} sees through {{yellow:{spotted.name}}}'s hiding (Passive Perception {passive_perception} vs Stealth DC {spotted.stealth_dc})",
                detailed=f"{{cyan:{owner.name}}} sees through {{yellow:{spotted.name}}}'s hiding (Passive Perception {passive_perception} vs Stealth DC {spotted.stealth_dc})",
                perceiver_uuids={str(self.owner_uuid)},
                identified_entity_observer_uuids={
                    str(spotted_uuid): {str(self.owner_uuid)},
                },
                data=EntitySpottedLogData(
                    observer_name=owner.name,
                    observer_uuid=str(self.owner_uuid),
                    target_name=spotted.name,
                    target_uuid=str(spotted_uuid),
                    target_position=spotted.position,
                    passive_perception=passive_perception,
                    stealth_dc=spotted.stealth_dc,
                ).model_dump(),
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
            if self._is_tile_lit_for_observer(tile):
                self.senses.entities[entity_uuid] = position
                return
        self.senses.entities.pop(entity_uuid, None)

    def _light_positions_requiring_visibility_refresh(
        self,
        positions: Set[Tuple[int, int]],
    ) -> Set[Tuple[int, int]]:
        """Return light-change positions that alter visible occupancy facts."""
        if not positions:
            return set()

        grid = get_map()
        occupied_positions = {
            position for position in self.senses.entities.values()
        } | {
            position for position in self.senses.objects.values()
        }
        refresh: Set[Tuple[int, int]] = set()
        for position in positions:
            tile = grid.get_tile(*position)
            is_lit = self._is_tile_lit_for_observer(tile)
            currently_visible = bool(self.senses.visible.get(position))
            if is_lit != currently_visible:
                refresh.add(position)
            elif not is_lit and position in occupied_positions:
                refresh.add(position)
        return refresh

    def _update_visibility_for_light_positions(
        self,
        positions: Set[Tuple[int, int]],
    ) -> None:
        """Apply one light-field delta to this observer's visible facts.

        Args:
            positions: Geometric-FOV positions whose effective light changed.
        """
        if not positions:
            return
        grid = get_map()
        old_entity_uuids = {
            entity_uuid
            for entity_uuid, position in self.senses.entities.items()
            if position in positions
        }
        self.senses.entities = {
            entity_uuid: position
            for entity_uuid, position in self.senses.entities.items()
            if position not in positions
        }
        self.senses.objects = {
            object_uuid: position
            for object_uuid, position in self.senses.objects.items()
            if position not in positions
        }

        lit_positions: Set[Tuple[int, int]] = set()
        for position in positions:
            tile = grid.get_tile(*position)
            is_lit = self._is_tile_lit_for_observer(tile)
            if is_lit:
                lit_positions.add(position)
                self.senses.visible[position] = True
                self.senses.seen.add(position)
            else:
                self.senses.visible.pop(position, None)

        for position in sorted(lit_positions):
            for entity_uuid in sorted(grid.get_entities_at(position), key=str):
                if entity_uuid != self.owner_uuid:
                    self._try_add_visible_entity(entity_uuid, position)
            for object_uuid in sorted(grid.get_objects_at(position), key=str):
                self._try_add_visible_object(object_uuid, position)

        new_entity_uuids = {
            entity_uuid
            for entity_uuid, position in self.senses.entities.items()
            if position in positions
        }
        self._log_newly_spotted_entities(new_entity_uuids - old_entity_uuids)

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
        if not self._is_tile_lit_for_observer(tile):
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
        current_visual_access = self.senses.visual_access.normalized_score

        perception_changed = current_perception != self.senses._last_passive_perception
        modes_changed = current_modes_hash != self.senses._last_sense_modes_hash
        visual_access_changed = current_visual_access != self.senses._last_visual_access

        if not perception_changed and not modes_changed and not visual_access_changed:
            return

        old_perception = self.senses._last_passive_perception

        self.senses._last_passive_perception = current_perception
        self.senses._last_sense_modes_hash = current_modes_hash
        self.senses._last_visual_access = current_visual_access

        if modes_changed or visual_access_changed:
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
                        if self._is_tile_lit_for_observer(tile):
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
                        perceiver_uuids={str(self.owner_uuid)},
                        identified_entity_observer_uuids={
                            str(spotted_uuid): {str(self.owner_uuid)},
                        },
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
                            perceiver_uuids={str(self.owner_uuid)},
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


@dataclass(frozen=True)
class ObserverFootprint:
    """Indexed subjective footprint used to select sensory update candidates."""

    subscribed_positions: frozenset[Tuple[int, int]]
    known_path_positions: frozenset[Tuple[int, int]]
    visible_entity_uuids: frozenset[UUID]
    visible_object_uuids: frozenset[UUID]


class SpatialSensesSystem:
    """Indexed dispatcher for observer-local pre-completion sensory callbacks.

    Candidate indexes only avoid asking definitely unrelated observers to
    recompute. `SpatialSensesCallback` remains the final rules authority for
    every selected observer.
    """

    SYSTEM_NAME = "spatial_senses"
    EVENT_TYPES = {
        EventType.DEATH,
        EventType.CONDITION_APPLICATION,
        EventType.CONDITION_REMOVAL,
        EventType.LIFE_STATE_CHANGE,
        *SpatialSensesCallback.SPATIAL_EVENTS,
    }

    def __init__(self) -> None:
        self.callbacks_by_observer: Dict[UUID, SpatialSensesCallback] = {}
        self.footprints_by_observer: Dict[UUID, ObserverFootprint] = {}
        self.observers_by_known_position: DefaultDict[
            Tuple[int, int],
            Set[UUID],
        ] = defaultdict(set)
        self.observers_by_visible_entity: DefaultDict[UUID, Set[UUID]] = defaultdict(set)
        self.observers_by_visible_object: DefaultDict[UUID, Set[UUID]] = defaultdict(set)

    def attach(self) -> None:
        """Attach this system to the dependency-neutral event lifecycle."""
        EventQueue.add_pre_completion_system(
            self.SYSTEM_NAME,
            self,
            self.EVENT_TYPES,
        )

    def reset(self) -> None:
        """Clear observer callbacks and every reverse candidate index."""
        self.callbacks_by_observer.clear()
        self.footprints_by_observer.clear()
        self.observers_by_known_position.clear()
        self.observers_by_visible_entity.clear()
        self.observers_by_visible_object.clear()

    def register_observer(self, callback: SpatialSensesCallback) -> None:
        """Register or replace one observer callback and index its current facts."""
        self.callbacks_by_observer[callback.owner_uuid] = callback
        self.refresh_observer(callback.owner_uuid)

    def unregister_observer(self, observer_uuid: UUID) -> None:
        """Remove one observer callback and every reverse-index membership."""
        self.callbacks_by_observer.pop(observer_uuid, None)
        footprint = self.footprints_by_observer.pop(observer_uuid, None)
        if footprint is not None:
            self._remove_footprint(observer_uuid, footprint)
        get_map().unsubscribe_entity(observer_uuid)

    def refresh_observer(self, observer_uuid: UUID) -> None:
        """Synchronize one observer's reverse indexes with its senses cache."""
        callback = self.callbacks_by_observer.get(observer_uuid)
        if callback is None:
            return
        senses = callback.senses
        new = ObserverFootprint(
            subscribed_positions=frozenset(
                get_map().get_entity_subscriptions(observer_uuid)
            ),
            known_path_positions=frozenset(
                set(senses.visible)
                | senses.seen
                | set(senses.paths)
                | set(senses.safe_paths)
            ),
            visible_entity_uuids=frozenset(senses.entities),
            visible_object_uuids=frozenset(senses.objects),
        )
        old = self.footprints_by_observer.get(observer_uuid)
        if old == new:
            return
        if old is not None:
            self._remove_footprint(observer_uuid, old, retained=new)
        self._add_footprint(observer_uuid, new, previous=old)
        self.footprints_by_observer[observer_uuid] = new

    def candidate_observer_uuids(self, event: Event) -> Set[UUID]:
        """Return a conservative observer set for one relevant completion."""
        registered = set(self.callbacks_by_observer)
        if event.event_type in (
            EventType.CONDITION_APPLICATION,
            EventType.CONDITION_REMOVAL,
            EventType.LIFE_STATE_CHANGE,
        ):
            target = event.target_entity_uuid
            return {target} if target is not None and target in registered else set()
        if event.event_type == EventType.DEATH:
            if not isinstance(event, DeathEvent):
                return registered
            return set(self.observers_by_visible_entity.get(event.entity_uuid, set()))
        if not isinstance(event, SpatialChangeEvent):
            return registered
        if (
            event.event_type == EventType.SPATIAL_ENTITY_LEFT
            and event.old_position is not None
        ):
            return set()

        candidates: Set[UUID] = set()
        grid = get_map()
        hint = event.senses_hint
        if (
            event.event_type == EventType.SPATIAL_LIGHT_CHANGED
            and hint is not None
            and hint.light_changed_positions
        ):
            candidates.update(
                grid.get_subscribers_for_cells(hint.light_changed_positions)
            )
            return candidates & registered

        positions = self._candidate_positions(event)
        for position in positions:
            candidates.update(grid.get_subscribers_at(position))

        if (
            event.entity_uuid is not None
            and event.entity_uuid in registered
            and event.event_type == EventType.SPATIAL_ENTITY_ENTERED
        ):
            candidates.add(event.entity_uuid)
        if hint is not None:
            if hint.entity_left:
                candidates.update(
                    self.observers_by_visible_entity.get(hint.entity_left[0], set())
                )
            if hint.entity_died:
                candidates.update(
                    self.observers_by_visible_entity.get(hint.entity_died[0], set())
                )
            if hint.perceivability_entity:
                entity_uuid = hint.perceivability_entity
                candidates.update(self.observers_by_visible_entity.get(entity_uuid, set()))
                entity_position = grid.get_entity_position(entity_uuid)
                if entity_position is not None:
                    candidates.update(grid.get_subscribers_at(entity_position))
            if hint.object_removed:
                candidates.update(
                    self.observers_by_visible_object.get(hint.object_removed[0], set())
                )
            if hint.requires_paths:
                for position in positions:
                    candidates.update(
                        self.observers_by_known_position.get(position, set())
                    )

        return candidates & registered

    def __call__(self, event: Event) -> None:
        """Dispatch an event to indexed candidates in replay-stable order."""
        sensory_events: List[SensoryUpdateEvent] = []
        for observer_uuid in sorted(self.candidate_observer_uuids(event), key=str):
            callback = self.callbacks_by_observer.get(observer_uuid)
            if callback is None:
                continue
            try:
                sensory_event = callback(event, register_event=False)
                if sensory_event is not None:
                    sensory_events.append(sensory_event)
            finally:
                self.refresh_observer(observer_uuid)
        if sensory_events:
            EventQueue.register_completion_sequence(sensory_events)

    def _candidate_positions(self, event: SpatialChangeEvent) -> Set[Tuple[int, int]]:
        """Collect all positions represented by a spatial event and its hint."""
        positions = {event.position}
        if event.old_position is not None:
            positions.add(event.old_position)
        hint = event.senses_hint
        if hint is None:
            return positions
        if hint.entity_entered:
            positions.add(hint.entity_entered[1])
        if hint.entity_left:
            positions.add(hint.entity_left[1])
        if hint.entity_died:
            positions.add(hint.entity_died[1])
        if hint.object_placed:
            positions.add(hint.object_placed[1])
        if hint.object_removed:
            positions.add(hint.object_removed[1])
        if hint.light_changed_positions:
            positions.update(hint.light_changed_positions)
        if hint.directional_positions:
            positions.update(hint.directional_positions)
        if hint.directional_neighbors:
            positions.update(hint.directional_neighbors)
        return positions

    def _remove_footprint(
        self,
        observer_uuid: UUID,
        footprint: ObserverFootprint,
        *,
        retained: Optional[ObserverFootprint] = None,
    ) -> None:
        """Remove reverse-index memberships absent from a retained footprint."""
        retained_positions = retained.known_path_positions if retained else frozenset()
        retained_entities = retained.visible_entity_uuids if retained else frozenset()
        retained_objects = retained.visible_object_uuids if retained else frozenset()
        for position in footprint.known_path_positions - retained_positions:
            self._discard_reverse(self.observers_by_known_position, position, observer_uuid)
        for entity_uuid in footprint.visible_entity_uuids - retained_entities:
            self._discard_reverse(self.observers_by_visible_entity, entity_uuid, observer_uuid)
        for object_uuid in footprint.visible_object_uuids - retained_objects:
            self._discard_reverse(self.observers_by_visible_object, object_uuid, observer_uuid)

    def _add_footprint(
        self,
        observer_uuid: UUID,
        footprint: ObserverFootprint,
        *,
        previous: Optional[ObserverFootprint],
    ) -> None:
        """Add reverse-index memberships introduced by a new footprint."""
        previous_positions = previous.known_path_positions if previous else frozenset()
        previous_entities = previous.visible_entity_uuids if previous else frozenset()
        previous_objects = previous.visible_object_uuids if previous else frozenset()
        for position in footprint.known_path_positions - previous_positions:
            self.observers_by_known_position[position].add(observer_uuid)
        for entity_uuid in footprint.visible_entity_uuids - previous_entities:
            self.observers_by_visible_entity[entity_uuid].add(observer_uuid)
        for object_uuid in footprint.visible_object_uuids - previous_objects:
            self.observers_by_visible_object[object_uuid].add(observer_uuid)

    @staticmethod
    def _discard_reverse(
        index: DefaultDict[K, Set[UUID]],
        key: K,
        observer_uuid: UUID,
    ) -> None:
        """Discard one reverse membership and remove empty keys."""
        observers = index.get(key)
        if observers is None:
            return
        observers.discard(observer_uuid)
        if not observers:
            index.pop(key, None)


spatial_senses_system = SpatialSensesSystem()
