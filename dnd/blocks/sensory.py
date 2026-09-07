"""Authoritative observer-local perception and navigation state."""

from typing import DefaultDict, Dict, List, Optional, Self, Set, Tuple, TypeVar, cast
from uuid import UUID
from pydantic import Field, PrivateAttr

import math
from dataclasses import dataclass
from collections import defaultdict
import time

from dnd.action_timing import action_timing_enabled, record_action_timing
from dnd.core.base_block import BaseBlock
from dnd.core.gridmap import get_map
from dnd.core.values import ModifiableValue
from dnd.core.events import (
    Event, EventType, EventPhase, SpatialChangeEvent,
    SpatialEffectChangeEvent, DeathEvent, EventQueue, SensoryUpdateEvent,
    SensoryUpdateReason,
)
from dnd.core.base_block import LightLevel
from dnd.types.senses import OpticalObscurement, PerceivedContact, SenseMode, SensesType
from dnd.types.world import CardinalDirection, WorldEdgeChannel


K = TypeVar("K")


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
    entities: Dict[UUID, PerceivedContact] = Field(default_factory=dict, description="Perceived entity contacts by UUID.")
    objects: Dict[UUID, PerceivedContact] = Field(default_factory=dict, description="Perceived object contacts by UUID.")
    visible: Dict[Tuple[int, int], bool] = Field(default_factory=dict, description="Cells visible after light and sense-mode filtering.")
    effective_light_levels: Dict[Tuple[int, int], LightLevel] = Field(
        default_factory=dict,
        description="Observer-effective light after-values for visible cells.",
    )
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
    _perception_max_distance: int = PrivateAttr(default=20)
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

    def has_sense(self, sense_type: SensesType) -> bool:
        """Check if entity has a sense type (any range)."""
        return any(
            sm.sense_type == sense_type for sm in self.get_sense_modes()
        )

    def has_sense_in_range(self, sense_type: SensesType, distance_feet: int) -> bool:
        """Check if a sense type covers a specific distance."""
        for sm in self.get_sense_modes():
            if sm.sense_type == sense_type:
                return sm.range_feet == 0 or distance_feet <= sm.range_feet
        return False

    def get_effective_light_levels(self, observer_uuid: UUID) -> Dict[str, int]:
        """Return subjective light for every cell currently visible to an observer.

        Args:
            observer_uuid: Entity whose special senses resolve the light levels.

        Returns:
            Mapping keyed as ``"x,y"`` with integer ``LightLevel`` values.
        """
        del observer_uuid
        return {
            f"{position[0]},{position[1]}": level.value
            for position, level in sorted(self.effective_light_levels.items())
        }

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
        """Return Euclidean tile distance from this senses position."""
        return int(math.sqrt((self.position[0] - position[0])**2 + (self.position[1] - position[1])**2))

    def get_feet_distance(self, position: Tuple[int, int]) -> int:
        """Return Euclidean distance in feet from this senses position."""
        return self.get_distance(position) * 5

    def get_path_to_entity(self, entity_uuid: UUID, max_path_length: Optional[int] = None) -> List[Tuple[int, int]]:
        """Return a cached path to a visible entity, optionally bounded by length."""
        if entity_uuid not in self.entities:
            return []
        path = self.paths.get(self.entities[entity_uuid].position, [])
        if max_path_length is None or len(path) <= max_path_length:
            return path
        else:
            return []

    def update_seen(self, visible: Dict[Tuple[int, int], bool]) -> None:
        """Add currently visible cells to the memory set."""
        visible_positions = {key for key, value in visible.items() if value}
        self.seen.update(visible_positions)

    def replace_navigation(
        self,
        walkable: Dict[Tuple[int, int], bool],
        paths: DefaultDict[Tuple[int, int], List[Tuple[int, int]]],
        path_costs: Optional[Dict[Tuple[int, int], int]] = None,
        safe_paths: Optional[Dict[Tuple[int, int], List[Tuple[int, int]]]] = None,
        safe_path_costs: Optional[Dict[Tuple[int, int], int]] = None,
        path_max_distance: Optional[int] = None,
    ) -> None:
        """Replace navigation facts without mutating perception-owned state."""
        self.walkable = {}
        self.paths = defaultdict(list)
        self.walkable = walkable
        self.paths = paths
        self.path_costs = path_costs if path_costs is not None else {}
        self.safe_paths = safe_paths if safe_paths is not None else {}
        self.safe_path_costs = safe_path_costs if safe_path_costs is not None else {}
        self._path_max_distance = path_max_distance
        self._paths_dirty = False
        self._path_revision += 1

    def replace_perception(
        self,
        *,
        position: Tuple[int, int],
        visible: Dict[Tuple[int, int], bool],
        seen: Set[Tuple[int, int]],
        entities: Dict[UUID, PerceivedContact],
        objects: Dict[UUID, PerceivedContact],
        effective_light_levels: Dict[Tuple[int, int], LightLevel],
        passive_perception: int,
        sense_modes_hash: int,
        visual_access: int,
    ) -> None:
        """Replace exactly the fields owned by subjective perception reduction."""
        self.position = position
        self.visible = visible
        self.seen = seen
        self.entities = entities
        self.objects = objects
        self.effective_light_levels = effective_light_levels
        self._last_passive_perception = passive_perception
        self._last_sense_modes_hash = sense_modes_hash
        self._last_visual_access = visual_access

    def apply_sensory_update(self, event: SensoryUpdateEvent) -> None:
        """Apply one recorded observer delta without reading live world state."""
        event.validate_replay_payload()
        reduced = reduce_senses_snapshot(
            self.source_entity_uuid,
            capture_senses_snapshot(self),
            event,
        )

        if event.sense_modes_changed:
            reduced_modes = list(reduced.sense_modes)
            if self.get_sense_modes() != reduced_modes:
                self.sense_modes = [
                    mode.model_copy(deep=True) for mode in reduced_modes
                ]
                self.sense_mode_sources.clear()

        self.replace_perception(
            position=reduced.position,
            visible={position: True for position in reduced.visible},
            seen=set(reduced.seen),
            entities=dict(reduced.entities),
            objects=dict(reduced.objects),
            effective_light_levels=dict(reduced.effective_light_levels),
            passive_perception=reduced.passive_perception,
            sense_modes_hash=reduced.sense_modes_hash,
            visual_access=reduced.visual_access,
        )
        self._paths_dirty = reduced.paths_dirty

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

@dataclass(frozen=True)
class SensesSnapshot:
    """Immutable observer cache snapshot used to build sensory deltas."""

    position: Tuple[int, int]
    visible: Set[Tuple[int, int]]
    seen: Set[Tuple[int, int]]
    entities: Dict[UUID, PerceivedContact]
    objects: Dict[UUID, PerceivedContact]
    effective_light_levels: Dict[Tuple[int, int], LightLevel]
    paths_dirty: bool
    passive_perception: int
    sense_modes_hash: int
    sense_modes: Tuple[SenseMode, ...]
    visual_access: int


def reduce_senses_snapshot(
    expected_observer_uuid: UUID,
    previous: SensesSnapshot,
    event: SensoryUpdateEvent,
) -> SensesSnapshot:
    """Reduce one observer Event into a fresh passive sensory snapshot."""
    if event.observer_uuid != expected_observer_uuid:
        raise ValueError("sensory update belongs to a different observer")

    visible = set(previous.visible)
    visible.difference_update(event.visible_cells_removed)
    visible.update(event.visible_cells_added)

    entities = dict(previous.entities)
    for entity_uuid in event.entity_contacts_removed:
        entities.pop(entity_uuid, None)
    entities.update(
        {
            entity_uuid: contact.model_copy(deep=True)
            for entity_uuid, contact in event.entity_contacts_changed.items()
        }
    )

    objects = dict(previous.objects)
    for object_uuid in event.object_contacts_removed:
        objects.pop(object_uuid, None)
    objects.update(
        {
            object_uuid: contact.model_copy(deep=True)
            for object_uuid, contact in event.object_contacts_changed.items()
        }
    )

    light_levels = dict(previous.effective_light_levels)
    for position in event.visible_cells_removed:
        light_levels.pop(position, None)
    for key, level in event.effective_light_levels_changed.items():
        x_text, y_text = key.split(",", maxsplit=1)
        light_levels[(int(x_text), int(y_text))] = LightLevel(level)

    sense_modes = tuple(
        mode.model_copy(deep=True) for mode in previous.sense_modes
    )
    sense_modes_hash = previous.sense_modes_hash
    if event.sense_modes_changed and event.sense_modes is not None:
        sense_modes = tuple(
            mode.model_copy(deep=True) for mode in event.sense_modes
        )
        sense_modes_hash = hash(
            tuple(
                sorted(
                    (mode.sense_type.value, mode.range_feet)
                    for mode in sense_modes
                )
            )
        )

    return SensesSnapshot(
        position=(
            event.observer_position
            if event.observer_position_changed
            else previous.position
        ),
        visible=visible,
        seen=set(previous.seen) | set(event.seen_cells_added),
        entities=entities,
        objects=objects,
        effective_light_levels=light_levels,
        paths_dirty=previous.paths_dirty or event.paths_dirty,
        passive_perception=(
            event.passive_perception
            if event.passive_perception_changed
            and event.passive_perception is not None
            else previous.passive_perception
        ),
        sense_modes_hash=sense_modes_hash,
        sense_modes=sense_modes,
        visual_access=(
            event.visual_access
            if event.visual_access_changed and event.visual_access is not None
            else previous.visual_access
        ),
    )


def _sorted_positions(positions: Set[Tuple[int, int]]) -> List[Tuple[int, int]]:
    """Return positions sorted for deterministic sensory payloads."""
    return sorted(positions, key=lambda pos: (pos[0], pos[1]))


def _sorted_contacts(
    values: Dict[UUID, PerceivedContact],
) -> Dict[UUID, PerceivedContact]:
    """Return contacts in deterministic UUID order."""
    return {uuid: values[uuid] for uuid in sorted(values, key=str)}


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
        effective_light_levels=dict(senses.effective_light_levels),
        paths_dirty=senses._paths_dirty,
        passive_perception=senses._last_passive_perception,
        sense_modes_hash=senses._last_sense_modes_hash,
        sense_modes=tuple(
            mode.model_copy(deep=True) for mode in senses.get_sense_modes()
        ),
        visual_access=senses._last_visual_access,
    )


def emit_sensory_update_delta(
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
        owner_uuid: Entity UUID that owns the senses component.
        cause_event: Causal engine event under which to parent the delta.
        before: Sensory state before the transition.
        after: Sensory state after the transition.
        reason: Typed reason for the sensory transition.
        register_event: Whether to register the completed event immediately.

    Returns:
        The completed sensory event when the snapshots differ, otherwise None.
    """
    timing = action_timing_enabled()
    total_started = time.perf_counter() if timing else 0.0
    started = time.perf_counter() if timing else 0.0
    visible_added = after.visible - before.visible
    visible_removed = before.visible - after.visible
    seen_added = after.seen - before.seen

    entity_changed = {
        uuid: contact
        for uuid, contact in after.entities.items()
        if before.entities.get(uuid) != contact
    }
    entity_removed = set(before.entities) - set(after.entities)
    object_changed = {
        uuid: contact
        for uuid, contact in after.objects.items()
        if before.objects.get(uuid) != contact
    }
    object_removed = set(before.objects) - set(after.objects)
    light_changed = {
        f"{position[0]},{position[1]}": level.value
        for position, level in sorted(after.effective_light_levels.items())
        if before.effective_light_levels.get(position) != level
    }

    passive_changed = before.passive_perception != after.passive_perception
    sense_modes_changed = before.sense_modes_hash != after.sense_modes_hash
    visual_access_changed = before.visual_access != after.visual_access
    position_changed = before.position != after.position
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
        entity_changed,
        entity_removed,
        object_changed,
        object_removed,
        paths_refresh_needed,
        passive_changed,
        sense_modes_changed,
        visual_access_changed,
        position_changed,
        light_changed,
    ))
    if not has_delta:
        if timing:
            record_action_timing("sensory_reducer.emit.delta_ms", started)
            record_action_timing("sensory_reducer.emit.total_ms", total_started)
        return None

    if timing:
        record_action_timing("sensory_reducer.emit.delta_ms", started)
    started = time.perf_counter() if timing else 0.0
    sensory_event = SensoryUpdateEvent(
        source_entity_uuid=owner_uuid,
        target_entity_uuid=owner_uuid,
        observer_uuid=owner_uuid,
        observer_position=after.position,
        observer_position_changed=position_changed,
        effective_light_levels_changed=light_changed,
        cause_event_uuid=cause_event.uuid,
        update_reason=reason,
        parent_event=cause_event.uuid,
        parent_lineage=cause_event.lineage_uuid,
        phase=EventPhase.COMPLETION,
        use_register=False,
        visible_cells_added=_sorted_positions(visible_added),
        visible_cells_removed=_sorted_positions(visible_removed),
        seen_cells_added=_sorted_positions(seen_added),
        entity_contacts_changed=_sorted_contacts(entity_changed),
        entity_contacts_removed=entity_removed,
        object_contacts_changed=_sorted_contacts(object_changed),
        object_contacts_removed=object_removed,
        paths_dirty=paths_refresh_needed,
        passive_perception_changed=passive_changed,
        passive_perception=after.passive_perception if passive_changed else None,
        sense_modes_changed=sense_modes_changed,
        sense_modes=(
            [mode.model_copy(deep=True) for mode in after.sense_modes]
            if sense_modes_changed
            else None
        ),
        visual_access_changed=visual_access_changed,
        visual_access=after.visual_access if visual_access_changed else None,
    )
    if timing:
        record_action_timing("sensory_reducer.emit.construct_event_ms", started)

    started = time.perf_counter() if timing else 0.0
    if register_event:
        EventQueue.register(sensory_event)
    if timing:
        record_action_timing("sensory_reducer.emit.completion_ms", started)
        record_action_timing("sensory_reducer.emit.total_ms", total_started)
    return sensory_event


@dataclass(frozen=True)
class ObserverFootprint:
    """Indexed facts used only to select candidate observers."""

    known_path_positions: frozenset[Tuple[int, int]]
    entity_uuids: frozenset[UUID]
    object_uuids: frozenset[UUID]


class SpatialSensesSystem:
    """Single reducer for observer-local visual cells and typed contacts."""

    SYSTEM_NAME = "spatial_senses"
    DEFAULT_VISUAL_RADIUS_CELLS = 20
    SPATIAL_EVENTS = {
        EventType.SPATIAL_ENTITY_ENTERED,
        EventType.SPATIAL_ENTITY_LEFT,
        EventType.SPATIAL_TILE_CHANGED,
        EventType.SPATIAL_OBJECT_PLACED,
        EventType.SPATIAL_OBJECT_REMOVED,
        EventType.SPATIAL_OBJECT_CHANGED,
        EventType.SPATIAL_PERCEIVABILITY_CHANGED,
        EventType.SPATIAL_LIGHT_CHANGED,
        EventType.SPATIAL_EFFECT_CHANGED,
    }
    EVENT_TYPES = {
        EventType.DEATH,
        EventType.CONDITION_APPLICATION,
        EventType.CONDITION_REMOVAL,
        EventType.LIFE_STATE_CHANGE,
        EventType.TURN_START,
        *SPATIAL_EVENTS,
    }

    def __init__(self) -> None:
        self.senses_by_observer: Dict[UUID, Senses] = {}
        self.footprints_by_observer: Dict[UUID, ObserverFootprint] = {}
        self.observers_by_known_position: DefaultDict[
            Tuple[int, int], Set[UUID]
        ] = defaultdict(set)
        self.observers_by_entity: DefaultDict[UUID, Set[UUID]] = defaultdict(set)
        self.observers_by_object: DefaultDict[UUID, Set[UUID]] = defaultdict(set)

    def attach(self) -> None:
        """Attach the reducer to the existing pre-completion event boundary."""
        EventQueue.add_pre_completion_system(
            self.SYSTEM_NAME,
            self,
            self.EVENT_TYPES,
        )

    def reset(self) -> None:
        """Clear observers and candidate indexes."""
        self.senses_by_observer.clear()
        self.footprints_by_observer.clear()
        self.observers_by_known_position.clear()
        self.observers_by_entity.clear()
        self.observers_by_object.clear()

    def register_observer(self, observer_uuid: UUID, senses: Senses) -> None:
        """Register an observer without independently materializing its world view."""
        self.senses_by_observer[observer_uuid] = senses

    def unregister_observer(self, observer_uuid: UUID) -> None:
        """Remove an observer and all of its candidate memberships."""
        self.senses_by_observer.pop(observer_uuid, None)
        footprint = self.footprints_by_observer.pop(observer_uuid, None)
        if footprint is not None:
            self._remove_footprint(observer_uuid, footprint)
        get_map().unsubscribe_entity(observer_uuid)

    def recompute_observer(
        self,
        observer_uuid: UUID,
        *,
        max_distance: Optional[int] = None,
    ) -> None:
        """Replace one observer's exact visual cells and perceived contacts."""
        senses = self.senses_by_observer.get(observer_uuid)
        owner = BaseBlock.get(observer_uuid)
        if senses is None or owner is None:
            return
        if max_distance is not None:
            senses._perception_max_distance = max_distance
        max_distance = senses._perception_max_distance
        origin = cast(Tuple[int, int], owner.get_position())
        grid = get_map()
        modes = {
            mode.sense_type: mode.range_feet
            for mode in senses.get_sense_modes()
        }
        visual_access = senses.visual_access.normalized_score > 0
        ordinary_sight = owner.has_ordinary_visual_sight()
        optical_radius = max_distance if ordinary_sight else 0
        for sense_type in (
            SensesType.DARKVISION,
            SensesType.DEVILS_SIGHT,
            SensesType.TRUESIGHT,
        ):
            sense_range = modes.get(sense_type)
            if sense_range is not None:
                optical_radius = max(
                    optical_radius,
                    max_distance if sense_range == 0 else (sense_range + 4) // 5,
                )

        optical_candidates = (
            set(grid.compute_fov(origin, optical_radius))
            if visual_access and optical_radius > 0
            else set()
        )
        visible: Dict[Tuple[int, int], bool] = {}
        effective_light: Dict[Tuple[int, int], LightLevel] = {}
        visual_modes_by_position: Dict[Tuple[int, int], Set[SensesType]] = {}
        for position in optical_candidates:
            tile = grid.get_tile(*position)
            if tile is None:
                continue
            distance = senses.get_feet_distance(position)
            obscurements = grid.get_optical_obscurements_on_route(
                origin,
                position,
            )
            establishing_modes: Set[SensesType] = set()
            ordinary_establishes = (
                ordinary_sight
                and OpticalObscurement.HEAVY not in obscurements
                and OpticalObscurement.MAGICAL_DARKNESS not in obscurements
                and tile.resolved_light_level.value > LightLevel.DARKNESS.value
            )
            if self._sense_in_range(modes, SensesType.DARKVISION, distance) and (
                OpticalObscurement.HEAVY not in obscurements
                and OpticalObscurement.MAGICAL_DARKNESS not in obscurements
            ):
                establishing_modes.add(SensesType.DARKVISION)
            if self._sense_in_range(modes, SensesType.DEVILS_SIGHT, distance) and (
                OpticalObscurement.HEAVY not in obscurements
            ):
                establishing_modes.add(SensesType.DEVILS_SIGHT)
            if self._sense_in_range(modes, SensesType.TRUESIGHT, distance) and (
                OpticalObscurement.HEAVY not in obscurements
            ):
                establishing_modes.add(SensesType.TRUESIGHT)
            if not ordinary_establishes and not establishing_modes:
                continue
            visible[position] = True
            visual_modes_by_position[position] = establishing_modes
            resolved = tile.resolved_light_level
            if (
                resolved.value <= LightLevel.DARKNESS.value
                and establishing_modes
                & {SensesType.DEVILS_SIGHT, SensesType.TRUESIGHT}
            ):
                resolved = LightLevel.BRIGHT_LIGHT
            elif (
                resolved is LightLevel.DARKNESS
                and SensesType.DARKVISION in establishing_modes
            ):
                resolved = LightLevel.DIM_LIGHT
            elif (
                resolved is LightLevel.DIM_LIGHT
                and SensesType.DARKVISION in establishing_modes
            ):
                resolved = LightLevel.BRIGHT_LIGHT
            effective_light[position] = resolved

        nonvisual_positions: Dict[SensesType, Set[Tuple[int, int]]] = {}
        for sense_type in (SensesType.BLINDSIGHT, SensesType.TREMORSENSE):
            sense_range = modes.get(sense_type)
            if sense_range is None:
                continue
            radius = max_distance if sense_range == 0 else (sense_range + 4) // 5
            nonvisual_positions[sense_type] = set(
                grid.compute_propagation_fov(origin, radius)
            )

        boundary_evidence: Dict[
            UUID,
            Set[Tuple[Tuple[int, int], bool, Tuple[SensesType, ...]]],
        ] = defaultdict(set)
        self._collect_boundary_evidence(
            boundary_evidence,
            set(visible),
            WorldEdgeChannel.OPTICAL,
            visual=True,
            senses_by_position=visual_modes_by_position,
        )
        for sense_type, positions in nonvisual_positions.items():
            self._collect_boundary_evidence(
                boundary_evidence,
                positions,
                WorldEdgeChannel.PROPAGATION,
                visual=False,
                fixed_senses=(sense_type,),
            )

        entity_contacts: Dict[UUID, PerceivedContact] = {}
        object_contacts: Dict[UUID, PerceivedContact] = {}
        candidate_positions = set(visible)
        for positions in nonvisual_positions.values():
            candidate_positions.update(positions)
        for position in candidate_positions:
            for entity_uuid in sorted(grid.get_entities_at(position), key=str):
                if entity_uuid == observer_uuid:
                    continue
                subject = BaseBlock.get(entity_uuid)
                if subject is None or not subject.appears_in_entity_contacts():
                    continue
                contact = self._resolve_contact(
                    owner,
                    senses,
                    subject,
                    position,
                    position in visible,
                    visual_modes_by_position.get(position, set()),
                    nonvisual_positions,
                    modes,
                )
                if contact is not None:
                    entity_contacts[entity_uuid] = contact
            for object_uuid in sorted(grid.get_center_objects_at(position), key=str):
                subject = BaseBlock.get(object_uuid)
                if subject is None or not subject.should_include_in_senses_objects():
                    continue
                contact = self._resolve_contact(
                    owner,
                    senses,
                    subject,
                    position,
                    position in visible,
                    visual_modes_by_position.get(position, set()),
                    nonvisual_positions,
                    modes,
                )
                if contact is not None:
                    object_contacts[object_uuid] = contact

        for object_uuid in sorted(boundary_evidence, key=str):
            subject = BaseBlock.get(object_uuid)
            placement = grid.get_object_placement(object_uuid)
            if (
                subject is None
                or placement is None
                or placement.boundary_direction is None
                or not subject.should_include_in_senses_objects()
            ):
                continue
            evidence = tuple(sorted(
                boundary_evidence[object_uuid],
                key=lambda row: (
                    row[0],
                    not row[1],
                    tuple(sense.value for sense in row[2]),
                ),
            ))
            contact = self._resolve_contact(
                owner,
                senses,
                subject,
                placement.position,
                False,
                set(),
                nonvisual_positions,
                modes,
                route_evidence=evidence,
                contact_position=placement.position,
            )
            if contact is not None:
                object_contacts[object_uuid] = contact

        senses.replace_perception(
            position=origin,
            visible=visible,
            seen=set(senses.seen) | set(visible),
            entities=entity_contacts,
            objects=object_contacts,
            effective_light_levels=effective_light,
            passive_perception=owner.get_passive_perception(),
            sense_modes_hash=senses.compute_sense_modes_hash(),
            visual_access=senses.visual_access.normalized_score,
        )
        subscribed = set(optical_candidates)
        for positions in nonvisual_positions.values():
            subscribed.update(positions)
        grid.subscribe_to_cells(observer_uuid, subscribed)
        self.refresh_observer(observer_uuid)

    @staticmethod
    def _sense_in_range(
        modes: Dict[SensesType, int],
        sense_type: SensesType,
        distance_feet: int,
    ) -> bool:
        sense_range = modes.get(sense_type)
        return sense_range is not None and (
            sense_range == 0 or distance_feet <= sense_range
        )

    def _collect_boundary_evidence(
        self,
        result: DefaultDict[
            UUID,
            Set[Tuple[Tuple[int, int], bool, Tuple[SensesType, ...]]],
        ],
        positions: Set[Tuple[int, int]],
        channel: WorldEdgeChannel,
        *,
        visual: bool,
        senses_by_position: Optional[Dict[Tuple[int, int], Set[SensesType]]] = None,
        fixed_senses: Tuple[SensesType, ...] = (),
    ) -> None:
        grid = get_map()
        for position in sorted(positions):
            evidence_senses = (
                tuple(sorted(senses_by_position.get(position, set()), key=lambda value: value.value))
                if senses_by_position is not None
                else fixed_senses
            )
            for direction in CardinalDirection:
                exit_layer, entry_layer = grid.get_boundary_route_layers(
                    position,
                    direction,
                    channel,
                )
                for object_uuid in (*exit_layer, *entry_layer):
                    result[object_uuid].add(
                        (position, visual, evidence_senses)
                    )

    def _resolve_contact(
        self,
        owner: BaseBlock,
        senses: Senses,
        subject: BaseBlock,
        position: Tuple[int, int],
        cell_visual: bool,
        visual_modes: Set[SensesType],
        nonvisual_positions: Dict[SensesType, Set[Tuple[int, int]]],
        modes: Dict[SensesType, int],
        *,
        route_evidence: Optional[
            Tuple[Tuple[Tuple[int, int], bool, Tuple[SensesType, ...]], ...]
        ] = None,
        contact_position: Optional[Tuple[int, int]] = None,
    ) -> Optional[PerceivedContact]:
        if (
            subject.stealth_dc is not None
            and subject.stealth_dc >= owner.get_passive_perception()
        ):
            return None
        evidence = route_evidence or ((
            position,
            cell_visual,
            tuple(sorted(visual_modes, key=lambda value: value.value)),
        ),)
        visual = False
        special: Set[SensesType] = set()
        for evidence_position, evidence_visual, evidence_modes in evidence:
            distance = senses.get_feet_distance(evidence_position)
            invisibility_bypassed = not subject.is_invisible or any((
                self._sense_in_range(modes, SensesType.TRUESIGHT, distance),
                self._sense_in_range(modes, SensesType.SEE_INVISIBLE, distance),
            ))
            if evidence_visual and invisibility_bypassed:
                visual = True
                special.update(evidence_modes)
            special.update(
                sense_type
                for sense_type, positions in nonvisual_positions.items()
                if evidence_position in positions
            )
        if not visual and not special:
            return None
        return PerceivedContact(
            position=contact_position or position,
            visual=visual,
            special_senses=tuple(sorted(special, key=lambda value: value.value)),
        )

    def refresh_observer(self, observer_uuid: UUID) -> None:
        """Synchronize one observer's candidate reverse indexes."""
        senses = self.senses_by_observer.get(observer_uuid)
        if senses is None:
            return
        new = ObserverFootprint(
            known_path_positions=frozenset(
                set(senses.visible)
                | set(senses.paths)
                | set(senses.safe_paths)
            ),
            entity_uuids=frozenset(senses.entities),
            object_uuids=frozenset(senses.objects),
        )
        old = self.footprints_by_observer.get(observer_uuid)
        if old == new:
            return
        if old is not None:
            self._remove_footprint(observer_uuid, old, retained=new)
        self._add_footprint(observer_uuid, new, previous=old)
        self.footprints_by_observer[observer_uuid] = new

    def candidate_observer_uuids(self, event: Event) -> Set[UUID]:
        """Return a conservative indexed observer set for one completion."""
        registered = set(self.senses_by_observer)
        if event.event_type is EventType.TURN_START:
            return (
                {event.source_entity_uuid}
                if event.source_entity_uuid in registered
                else set()
            )
        if event.event_type in {
            EventType.CONDITION_APPLICATION,
            EventType.CONDITION_REMOVAL,
            EventType.LIFE_STATE_CHANGE,
        }:
            target = event.target_entity_uuid
            return {target} if target is not None and target in registered else set()
        if isinstance(event, DeathEvent):
            return set(self.observers_by_entity.get(event.entity_uuid, set()))
        if isinstance(event, SpatialEffectChangeEvent):
            grid = get_map()
            candidates: Set[UUID] = set()
            for position in event.get_affected_positions():
                candidates.update(grid.get_subscribers_at(position))
            return candidates & registered
        if not isinstance(event, SpatialChangeEvent):
            return set()
        if (
            event.event_type is EventType.SPATIAL_ENTITY_LEFT
            and event.old_position is not None
        ):
            return set()

        positions = self._candidate_positions(event)
        grid = get_map()
        candidates: Set[UUID] = set()
        for position in positions:
            candidates.update(grid.get_subscribers_at(position))
        if (
            event.entity_uuid is not None
            and event.entity_uuid in registered
            and event.event_type is EventType.SPATIAL_ENTITY_ENTERED
        ):
            candidates.add(event.entity_uuid)
        hint = event.senses_hint
        if hint is not None:
            if hint.entity_left is not None:
                candidates.update(self.observers_by_entity.get(hint.entity_left[0], set()))
            if hint.entity_died is not None:
                candidates.update(self.observers_by_entity.get(hint.entity_died[0], set()))
            if hint.object_removed is not None:
                candidates.update(self.observers_by_object.get(hint.object_removed[0], set()))
            if hint.perceivability_entity is not None:
                changed_uuid = hint.perceivability_entity
                candidates.update(self.observers_by_entity.get(changed_uuid, set()))
                candidates.update(self.observers_by_object.get(changed_uuid, set()))
            if hint.requires_paths:
                for position in positions:
                    candidates.update(self.observers_by_known_position.get(position, set()))
        return candidates & registered

    def __call__(self, event: Event) -> None:
        """Reduce indexed observers before the causal event completes."""
        sensory_events: List[SensoryUpdateEvent] = []
        for observer_uuid in sorted(self.candidate_observer_uuids(event), key=str):
            senses = self.senses_by_observer.get(observer_uuid)
            if senses is None:
                continue
            before = capture_senses_snapshot(senses)
            self.recompute_observer(observer_uuid)
            after = capture_senses_snapshot(senses)
            projection_changed = any((
                before.position != after.position,
                before.visible != after.visible,
                before.seen != after.seen,
                before.entities != after.entities,
                before.objects != after.objects,
                before.passive_perception != after.passive_perception,
            ))
            visible_topology_changed = False
            if isinstance(event, SpatialChangeEvent):
                hint = event.senses_hint
                visible_topology_changed = bool(
                    hint is not None
                    and hint.requires_paths
                    and self._candidate_positions(event) & after.visible
                )
                visible_topology_changed = visible_topology_changed or bool(
                    event.object_uuid is not None
                    and event.object_uuid in after.objects
                    and hint is not None
                    and hint.requires_paths
                )
            elif isinstance(event, SpatialEffectChangeEvent):
                visible_topology_changed = bool(
                    event.get_affected_positions() & after.visible
                )
            if projection_changed or visible_topology_changed:
                senses._paths_dirty = True
                after = capture_senses_snapshot(senses)
            sensory_event = emit_sensory_update_delta(
                observer_uuid,
                event,
                before,
                after,
                self._reason_for(event, observer_uuid),
                register_event=False,
            )
            if sensory_event is not None:
                sensory_events.append(sensory_event)
        if sensory_events:
            EventQueue.register_completion_sequence(sensory_events)

    @staticmethod
    def _reason_for(event: Event, observer_uuid: UUID) -> SensoryUpdateReason:
        if event.event_type is EventType.TURN_START:
            return SensoryUpdateReason.TURN_START
        if event.event_type is EventType.SPATIAL_LIGHT_CHANGED:
            return SensoryUpdateReason.LIGHT
        if event.event_type is EventType.SPATIAL_PERCEIVABILITY_CHANGED:
            return SensoryUpdateReason.PERCEIVABILITY
        if event.event_type is EventType.DEATH:
            return SensoryUpdateReason.DEATH
        if event.event_type is EventType.LIFE_STATE_CHANGE:
            return SensoryUpdateReason.LIFE_STATE
        if event.event_type in {
            EventType.CONDITION_APPLICATION,
            EventType.CONDITION_REMOVAL,
        }:
            return SensoryUpdateReason.CONDITION
        if isinstance(event, SpatialChangeEvent) and event.entity_uuid == observer_uuid:
            return SensoryUpdateReason.SELF_MOVEMENT
        return SensoryUpdateReason.SPATIAL

    @staticmethod
    def _candidate_positions(event: SpatialChangeEvent) -> Set[Tuple[int, int]]:
        positions = {event.position}
        if event.old_position is not None:
            positions.add(event.old_position)
        hint = event.senses_hint
        if hint is None:
            return positions
        for fact in (
            hint.entity_entered,
            hint.entity_left,
            hint.entity_died,
            hint.object_placed,
            hint.object_removed,
        ):
            if fact is not None:
                positions.add(fact[1])
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
        retained_positions = retained.known_path_positions if retained else frozenset()
        retained_entities = retained.entity_uuids if retained else frozenset()
        retained_objects = retained.object_uuids if retained else frozenset()
        for position in footprint.known_path_positions - retained_positions:
            self._discard_reverse(self.observers_by_known_position, position, observer_uuid)
        for entity_uuid in footprint.entity_uuids - retained_entities:
            self._discard_reverse(self.observers_by_entity, entity_uuid, observer_uuid)
        for object_uuid in footprint.object_uuids - retained_objects:
            self._discard_reverse(self.observers_by_object, object_uuid, observer_uuid)

    def _add_footprint(
        self,
        observer_uuid: UUID,
        footprint: ObserverFootprint,
        *,
        previous: Optional[ObserverFootprint],
    ) -> None:
        previous_positions = previous.known_path_positions if previous else frozenset()
        previous_entities = previous.entity_uuids if previous else frozenset()
        previous_objects = previous.object_uuids if previous else frozenset()
        for position in footprint.known_path_positions - previous_positions:
            self.observers_by_known_position[position].add(observer_uuid)
        for entity_uuid in footprint.entity_uuids - previous_entities:
            self.observers_by_entity[entity_uuid].add(observer_uuid)
        for object_uuid in footprint.object_uuids - previous_objects:
            self.observers_by_object[object_uuid].add(observer_uuid)

    @staticmethod
    def _discard_reverse(
        index: DefaultDict[K, Set[UUID]],
        key: K,
        observer_uuid: UUID,
    ) -> None:
        observers = index.get(key)
        if observers is None:
            return
        observers.discard(observer_uuid)
        if not observers:
            index.pop(key, None)


spatial_senses_system = SpatialSensesSystem()
