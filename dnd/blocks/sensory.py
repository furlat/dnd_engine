"""Authoritative observer-local perception and navigation state."""

from typing import AbstractSet, DefaultDict, Dict, Iterable, List, Optional, Self, Sequence, Set, Tuple, TypeVar, cast
from uuid import UUID
from pydantic import Field, PrivateAttr

import math
from dataclasses import dataclass, field, replace
from collections import defaultdict
import time

from dnd.core.effect_types import ObservedChangeRef, ObservedField
from dnd.action_timing import action_timing_enabled, record_action_count, record_action_timing
from dnd.core.base_object import BaseObject
from dnd.core.base_block import BaseBlock
from dnd.core.base_conditions import ConditionApplicationEvent, ConditionRemovalEvent
from dnd.core.base_tiles import Tile
from dnd.core.gridmap import BoundarySnapshot, OpticalSnapshot, SpatialConditionOwner, boundary_snapshot_covers, get_map
from dnd.core.geometry import grid_distance_feet, supercover_line
from dnd.core.presentation_geometry import SpherePresentationGeometry
from dnd.core.values import ModifiableValue
from dnd.core.events import (
    Event, EventType, EventPhase, SpatialChangeEvent,
    SpatialEffectChangeEvent, DeathEvent, EventQueue, SensoryUpdateEvent,
    SensoryUpdateReason,
)
from dnd.types.senses import (
    OpticalObscurement, PerceivedContact, PerceivedLightSource, PerceivedSpatialEffect, SenseMode, SensesType, VolumeSurfaceSight,
    SensesSnapshot as SensesSnapshot,
    reduce_senses_snapshot as reduce_senses_snapshot,
)
from dnd.types.world import CardinalDirection, LightLevel, ObserverRevisions, WorldEdgeChannel


K = TypeVar("K")


@dataclass(frozen=True)
class VolumeRay:
    light_position: Tuple[int, int]
    ordinary: bool
    special: bool
    upper_surface: Optional[VolumeSurfaceSight] = None


@dataclass(frozen=True)
class VolumeField:
    """One local volume's settled geometry and illumination dependencies."""

    entrances: Tuple[VolumeRay, ...]
    rays: Dict[Tuple[int, int], VolumeRay]
    providers: Dict[UUID, frozenset[Tuple[int, int]]]
    dependencies: frozenset[Tuple[int, int]]


@dataclass(frozen=True)
class ObserverField:
    """Resolved cell evidence and the inputs under which it was computed."""

    modes: Dict[SensesType, int]
    ordinary_sight: bool
    visible_volumes: Dict[UUID, frozenset[Tuple[int, int]]]
    upper_volume_surfaces: Dict[UUID, Tuple[VolumeSurfaceSight, ...]]
    max_distance: int
    revisions: ObserverRevisions
    visual_modes: Dict[Tuple[int, int], frozenset[SensesType]]
    nonvisual_positions: Dict[SensesType, Set[Tuple[int, int]]]
    optical_routes: Dict[Tuple[int, int], Tuple[bool, frozenset[SensesType]]]
    boundaries: BoundarySnapshot
    volume_fields: Dict[UUID, VolumeField]
    volume_light_owners: Dict[Tuple[int, int], Set[UUID]]
    volume_provider_owners: Dict[UUID, Set[UUID]]
    volume_sights: Dict[UUID, frozenset[Tuple[int, int]]]
    grant_base_cells: Set[Tuple[int, int]]
    dependency_bounds: Tuple[int, int, int, int]
    volume_dependencies: Set[Tuple[int, int]]
    volume_grants: Dict[UUID, frozenset[Tuple[int, int]]]


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
    hazardous_cells: Dict[Tuple[int, int], bool] = Field(
        default_factory=dict, description="Native resolved hazard values for currently visible cells.",
    )
    spatial_effects: Dict[UUID, PerceivedSpatialEffect] = Field(
        default_factory=dict, description="Discovered fixture cells and their last observed state.",
    )
    light_sources: Dict[UUID, PerceivedLightSource] = Field(default_factory=dict)
    light_source_removals: Dict[UUID, int] = Field(default_factory=dict)
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
    _field: Optional[ObserverField] = PrivateAttr(default=None)
    _effects_by_position: Optional[Dict[Tuple[int, int], Set[UUID]]] = PrivateAttr(default=None)
    _active_effects: Set[UUID] = PrivateAttr(default_factory=set)

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
            if mode.contribution_owner_uuid is not None:
                owner = BaseObject.get_contribution_owner(mode.contribution_owner_uuid)
                if owner is None or not owner.contributions_active():
                    continue
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
        self._field = None

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
        self.hazardous_cells = dict(reduced.hazardous_cells)
        self.spatial_effects = dict(reduced.spatial_effects)
        self.light_sources = dict(reduced.light_sources)
        self.light_source_removals = dict(reduced.light_source_removals)
        self._effects_by_position = None
        self._active_effects.clear()

    def get_threathened_positions(self, *, close_pressure: bool = False,
                                 knowledge_observer_uuid: Optional[UUID] = None,
                                 candidate_positions: Optional[Iterable[Tuple[int, int]]] = None) -> List[Tuple[int, int]]:
        """Current main-hand reach through structural providers, without cost gates.

        Close-range pressure is capped at five feet independently of OA reach.
        Creature occupancy and floor navigation costs do not block weapon contact.
        Supplied candidates restrict the query while retaining native visibility.
        """
        actor = BaseBlock.get(self.source_entity_uuid)
        if actor is None:
            return []
        access, reach = actor.get_melee_threat_access()
        if close_pressure:
            reach = min(reach, 5)
        if reach <= 0:
            return []
        grid = get_map()
        candidates = (self.visible.items() if candidate_positions is None else
                      ((position, self.visible.get(position, False)) for position in candidate_positions))
        return [position for position, visible in candidates
                if visible and position != self.position
                and self.get_feet_distance(position) <= reach
                and grid.can_reach_between(self.position, position, access, self.source_entity_uuid,
                    subjective=knowledge_observer_uuid is not None,
                    knowledge_observer_uuid=knowledge_observer_uuid)]

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
    return _capture_senses_transition(senses, senses.seen)


def _capture_senses_transition(senses: Senses, seen: Set[Tuple[int, int]], *,
        positions: Optional[Set[Tuple[int, int]]] = None,
        entities: Optional[Set[UUID]] = None, objects: Optional[Set[UUID]] = None,
        effects: Optional[Set[UUID]] = None) -> SensesSnapshot:
    """Detach one current field, with only the discovery entries needed by its delta."""
    return SensesSnapshot(
        position=senses.position,
        visible={pos for pos in senses.visible if senses.visible[pos]} if positions is None else {
            pos for pos in positions if senses.visible.get(pos, False)},
        seen=set(seen),
        entities=dict(senses.entities) if entities is None else {
            identity: senses.entities[identity] for identity in entities if identity in senses.entities},
        objects=dict(senses.objects) if objects is None else {
            identity: senses.objects[identity] for identity in objects if identity in senses.objects},
        effective_light_levels=dict(senses.effective_light_levels) if positions is None else {
            pos: senses.effective_light_levels[pos] for pos in positions if pos in senses.effective_light_levels},
        hazardous_cells=dict(senses.hazardous_cells) if positions is None else {
            pos: senses.hazardous_cells[pos] for pos in positions if pos in senses.hazardous_cells},
        spatial_effects=dict(senses.spatial_effects) if effects is None else {
            identity: senses.spatial_effects[identity] for identity in effects if identity in senses.spatial_effects},
        light_sources=dict(senses.light_sources),
        light_source_removals=dict(senses.light_source_removals),
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
    cause_event: Optional[Event],
    before: SensesSnapshot,
    after: SensesSnapshot,
    reason: SensoryUpdateReason,
    *,
    register_event: bool = True,
    initial: bool = False,
) -> Optional[SensoryUpdateEvent]:
    """Emit a completed sensory event for one observer-cache transition.

    Args:
        owner_uuid: Entity UUID that owns the senses component.
        cause_event: Actual causal event, or None for an independent refresh.
        before: Sensory state before the transition.
        after: Sensory state after the transition.
        reason: Typed reason for the sensory transition.
        register_event: Whether to register the completed event immediately.
        initial: Publish the complete after-state without an unrecorded seed.

    Returns:
        The completed sensory event when the snapshots differ, otherwise None.
    """
    timing = action_timing_enabled()
    total_started = time.perf_counter() if timing else 0.0
    started = time.perf_counter() if timing else 0.0
    visible_added = after.visible if initial else after.visible - before.visible
    visible_removed = set() if initial else before.visible - after.visible
    seen_added = after.seen if initial else after.seen - before.seen

    entity_changed = {
        uuid: contact
        for uuid, contact in after.entities.items()
        if initial or before.entities.get(uuid) != contact
    }
    entity_removed = set() if initial else set(before.entities) - set(after.entities)
    object_changed = {
        uuid: contact
        for uuid, contact in after.objects.items()
        if initial or before.objects.get(uuid) != contact
    }
    object_removed = set() if initial else set(before.objects) - set(after.objects)
    light_changed = {
        f"{position[0]},{position[1]}": level.value
        for position, level in sorted((position, level)
            for position, level in after.effective_light_levels.items()
            if initial or before.effective_light_levels.get(position) != level)
    }
    hazards_changed = {
        f"{position[0]},{position[1]}": hazardous
        for position, hazardous in sorted((position, hazardous)
            for position, hazardous in after.hazardous_cells.items()
            if initial or before.hazardous_cells.get(position) != hazardous)
    }
    effects_changed = {
        identity: value for identity, value in after.spatial_effects.items()
        if initial or before.spatial_effects.get(identity) != value
    }
    effects_removed = set() if initial else before.spatial_effects.keys() - after.spatial_effects.keys()

    sources_changed = {identity: value for identity, value in after.light_sources.items()
        if initial or before.light_sources.get(identity) != value}
    sources_removed = {identity: revision for identity, revision in after.light_source_removals.items()
        if not initial and before.light_source_removals.get(identity) != revision}
    passive_changed = initial or before.passive_perception != after.passive_perception
    sense_modes_changed = initial or before.sense_modes_hash != after.sense_modes_hash
    visual_access_changed = initial or before.visual_access != after.visual_access
    position_changed = initial or before.position != after.position
    perception_capability_changed = (
        reason in {SensoryUpdateReason.CONDITION, SensoryUpdateReason.LIFE_STATE}
        and (passive_changed or sense_modes_changed or visual_access_changed)
    )
    paths_refresh_needed = (
        (initial and after.paths_dirty)
        or ((not before.paths_dirty) and after.paths_dirty)
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
        hazards_changed,
        effects_changed,
        effects_removed,
        sources_changed,
        sources_removed,
    ))
    if not has_delta:
        if timing:
            record_action_timing("sensory_reducer.emit.delta_ms", started)
            record_action_timing("sensory_reducer.emit.total_ms", total_started)
        return None

    if timing:
        record_action_timing("sensory_reducer.emit.delta_ms", started)
    started = time.perf_counter() if timing else 0.0
    observed_changes: list[ObservedChangeRef] = []
    source_index = EventQueue.get_event_index(cause_event.uuid) if cause_event is not None else None
    if cause_event is not None and source_index is not None:
        fields: tuple[tuple[ObservedField, tuple[UUID, ...]], ...] = (
            ("position", (owner_uuid,) if position_changed else ()),
            ("visibility", (owner_uuid,) if visible_added or visible_removed or seen_added else ()),
            ("light", (owner_uuid,) if light_changed else ()),
            ("hazards", (owner_uuid,) if hazards_changed else ()),
            ("senses", (owner_uuid,) if passive_changed or sense_modes_changed or visual_access_changed else ()),
            ("paths", (owner_uuid,) if paths_refresh_needed else ()),
            ("entity_contact", (*entity_changed, *entity_removed)),
            ("object_contact", (*object_changed, *object_removed)),
            ("spatial_effect", (*effects_changed, *effects_removed)),
        )
        for field, owners in fields:
            for identity in owners:
                observed_changes.append(ObservedChangeRef(source_event_uuid=cause_event.uuid,
                    source_index=source_index, resolution_ref=cause_event.resolution_ref,
                    field=field, owner_uuid=identity))
    sensory_event = SensoryUpdateEvent(
        source_entity_uuid=owner_uuid,
        target_entity_uuid=owner_uuid,
        observer_uuid=owner_uuid,
        observed_changes=tuple(observed_changes),
        initial=initial,
        observer_position=after.position,
        observer_position_changed=position_changed,
        effective_light_levels_changed=light_changed,
        light_sources_changed=sources_changed,
        light_sources_removed=sources_removed,
        hazardous_cells_changed=hazards_changed,
        spatial_effects_changed=effects_changed,
        spatial_effects_removed=effects_removed,
        cause_event_uuid=cause_event.uuid if cause_event is not None else None,
        update_reason=reason,
        parent_event=cause_event.uuid if cause_event is not None else None,
        parent_lineage=cause_event.lineage_uuid if cause_event is not None else None,
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


@dataclass
class _GroupSettlement:
    """Facts recorded for one observer while a simultaneous group is open."""

    events: List[Event] = field(default_factory=list)
    full: bool = False
    max_distance: Optional[int] = None


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
        EventType.SPATIAL_LIGHT_SOURCES_CHANGED,
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
        self.published_observers: Set[UUID] = set()
        self.footprints_by_observer: Dict[UUID, ObserverFootprint] = {}
        self.observers_by_known_position: DefaultDict[
            Tuple[int, int], Set[UUID]
        ] = defaultdict(set)
        self.observers_by_entity: DefaultDict[UUID, Set[UUID]] = defaultdict(set)
        self.observers_by_object: DefaultDict[UUID, Set[UUID]] = defaultdict(set)
        self._pending: Dict[UUID, _GroupSettlement] = {}
        self._settling = False
        self._absorbing_light = False

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
        self.published_observers.clear()
        self.footprints_by_observer.clear()
        self.observers_by_known_position.clear()
        self.observers_by_entity.clear()
        self.observers_by_object.clear()
        self._pending.clear()
        self._settling = False
        self._absorbing_light = False

    def _recording(self) -> bool:
        """Whether facts are recorded for the open group instead of settled now.

        A settling group no longer records: facts other systems publish while
        settling reduce normally. The group's own pending light is absorbed so
        it merges into the observers' single pass.
        """
        group = EventQueue.open_group()
        return (group is not None and not self._settling
                and (self._absorbing_light or not group.settling))

    def settle_group(self, root_uuid: Optional[UUID]) -> None:
        """Publish the group's pending light, then settle every recorded observer once."""
        self._absorbing_light = True
        try:
            get_map().settle_pending_lights(parent_event=root_uuid)
        finally:
            self._absorbing_light = False
        pending, self._pending = self._pending, {}
        if not pending:
            return
        root = EventQueue.get_event_by_uuid(root_uuid) if root_uuid is not None else None
        sensory_events: List[SensoryUpdateEvent] = []
        self._settling = True
        try:
            for observer_uuid in sorted(pending, key=str):
                senses = self.senses_by_observer.get(observer_uuid)
                if senses is None or BaseBlock.get(observer_uuid) is None:
                    continue
                settlement = pending[observer_uuid]
                if settlement.max_distance is not None:
                    senses._perception_max_distance = settlement.max_distance
                if not settlement.events:
                    before = capture_senses_snapshot(senses)
                    self.recompute_observer(observer_uuid)
                    self.publish_observer_refresh(observer_uuid, before)
                    continue
                light_event = self._settled_light_only(observer_uuid, senses, settlement)
                sensory_event = (self._update_light(observer_uuid, senses, light_event) if light_event is not None
                    else self._reduce_observer(observer_uuid, senses, settlement.events,
                        force_full=settlement.full, cause=root))
                if sensory_event is not None:
                    sensory_events.append(sensory_event)
        finally:
            self._settling = False
        if sensory_events:
            EventQueue.register_completion_sequence(sensory_events)
            self.published_observers.update(event.observer_uuid for event in sensory_events)

    def _settled_light_only(self, observer_uuid: UUID, senses: Senses,
                            settlement: _GroupSettlement) -> Optional[SpatialChangeEvent]:
        """The group's light fact when it is all this observer recorded and light alone can settle it."""
        events = settlement.events
        if (settlement.full or len(events) != 1 or observer_uuid not in self.published_observers
                or not isinstance(events[0], SpatialChangeEvent)
                or events[0].event_type is not EventType.SPATIAL_LIGHT_CHANGED):
            return None
        event = events[0]
        return event if self._can_update_light(observer_uuid, senses, event, covers_group=True) else None

    def register_observer(self, observer_uuid: UUID, senses: Senses) -> None:
        """Register an observer without independently materializing its world view."""
        self.senses_by_observer[observer_uuid] = senses
        senses._field = None

    def unregister_observer(self, observer_uuid: UUID) -> None:
        """Remove an observer and all of its candidate memberships."""
        self.senses_by_observer.pop(observer_uuid, None)
        self.published_observers.discard(observer_uuid)
        footprint = self.footprints_by_observer.pop(observer_uuid, None)
        if footprint is not None:
            self._remove_footprint(observer_uuid, footprint)
        get_map().unsubscribe_entity(observer_uuid)

    def recompute_observer(
        self,
        observer_uuid: UUID,
        *,
        max_distance: Optional[int] = None,
        hazard_positions: Optional[Set[Tuple[int, int]]] = None,
        effect_before: Optional[Dict[UUID, Optional[PerceivedSpatialEffect]]] = None,
        light_event: Optional[SpatialChangeEvent] = None,
    ) -> Set[Tuple[int, int]]:
        """Replace one observer's exact visual cells and perceived contacts."""
        senses = self.senses_by_observer.get(observer_uuid)
        owner = BaseBlock.get(observer_uuid)
        if senses is None or owner is None:
            return set()
        if self._recording():
            # Inside a simultaneous group perception reads see pre-group
            # perception; the observer settles once when the group closes.
            settlement = self._pending.setdefault(observer_uuid, _GroupSettlement())
            settlement.full = True
            if max_distance is not None:
                settlement.max_distance = max_distance
            return set()
        record_action_count("sensory.full_recompute", 1)
        # Temporary movement investigation; removed with diagnostic tooling.
        diagnostic = action_timing_enabled()
        phase_started = time.perf_counter() if diagnostic else 0.0
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

        if diagnostic:
            record_action_timing("sensory.recompute.observer_inputs_ms", phase_started)
            phase_started = time.perf_counter()
        optical_candidates = (
            set(grid.compute_fov(origin, optical_radius))
            if visual_access and optical_radius > 0
            else set()
        )
        if diagnostic:
            record_action_timing("sensory.recompute.physical_fov_ms", phase_started)
            phase_started = time.perf_counter()
        visible: Dict[Tuple[int, int], bool] = {}
        effective_light: Dict[Tuple[int, int], LightLevel] = {}
        visual_modes_by_position: Dict[Tuple[int, int], frozenset[SensesType]] = {}
        optics = grid.capture_optical_obscurements(origin, optical_radius)
        if diagnostic:
            record_action_timing("sensory.recompute.optical_inputs_ms", phase_started)
            phase_started = time.perf_counter()
        optical_routes: Dict[Tuple[int, int], Tuple[bool, frozenset[SensesType]]] = {}
        surface_routes: Dict[Tuple[int, int], VolumeRay] = {}
        # Route eligibility has only range and obscurement inputs within this
        # observer solve. Keep the shared mode value immutable across cells.
        mode_results: Dict[Tuple[int, frozenset[OpticalObscurement]], Tuple[bool, frozenset[SensesType]]] = {}
        no_obscurements: frozenset[OpticalObscurement] = frozenset()
        range_affects_modes = any(sense in modes for sense in (
            SensesType.DARKVISION, SensesType.DEVILS_SIGHT, SensesType.TRUESIGHT))
        light_results: Dict[Tuple[bool, frozenset[SensesType]], Dict[LightLevel, Optional[LightLevel]]] = {}
        previous_field = senses._field
        revisions = grid.observer_spatial_revisions(observer_uuid)
        reuse_ordinary_light = (
            light_event is not None and light_event.light_level_map is not None
            and previous_field is not None and not modes and not previous_field.modes
            and visual_access and ordinary_sight and previous_field.ordinary_sight
            and senses._last_visual_access == senses.visual_access.normalized_score
            and previous_field.max_distance == max_distance and not optics
            and not previous_field.volume_fields
            and all(route[0] for route in previous_field.optical_routes.values())
            and previous_field.revisions.optical == revisions.optical
            and previous_field.revisions.propagation == revisions.propagation
            and revisions.illumination - previous_field.revisions.illumination in (0, 1)
        )
        if reuse_ordinary_light:
            # The exact new physical field is already resolved. Ordinary sight
            # has no origin-dependent range class, and this single committed
            # light batch names every overlap value that needs a fresh read.
            assert previous_field is not None and light_event is not None
            assert light_event.light_level_map is not None
            changed_light = {tuple(map(int, key.split(","))) for key in light_event.light_level_map}
            refresh = (optical_candidates - previous_field.optical_routes.keys()) | (optical_candidates & changed_light)
            effective_light = {position: level for position, level in senses.effective_light_levels.items()
                if position in optical_candidates and position not in refresh}
            supported_refresh = set()
            for position in refresh:
                tile = grid.get_tile(*position)
                if tile is None:
                    continue
                supported_refresh.add(position)
                level = tile.resolved_light_level
                if level > LightLevel.DARKNESS:
                    effective_light[position] = level
            # Keep native candidate traversal for contact/discovery ordering.
            visible = {position: True for position in optical_candidates if position in effective_light}
            no_special: frozenset[SensesType] = frozenset()
            visual_modes_by_position = dict.fromkeys(visible, no_special)
            supported_routes = (optical_candidates & previous_field.optical_routes.keys()) | supported_refresh
            optical_routes = dict.fromkeys(supported_routes, (True, no_special))
            if diagnostic:
                record_action_count("sensory.recompute.reused_optical_cells", len(optical_candidates) - len(refresh))
                record_action_count("sensory.recompute.refreshed_optical_cells", len(refresh))
        else:
            for position in optical_candidates:
                tile = grid.get_tile(*position)
                if tile is None:
                    continue
                distance = grid_distance_feet(origin, position) if range_affects_modes else 0
                obscurements = grid.get_optical_obscurements_on_route(
                    origin,
                    position,
                    snapshot=optics,
                ) if optics else set()
                route_key = distance, frozenset(obscurements) if obscurements else no_obscurements
                route_modes = mode_results.get(route_key)
                if route_modes is None:
                    ordinary_eligible, special = self._visual_route_modes(
                        modes, ordinary_sight, distance, obscurements, LightLevel.BRIGHT_LIGHT,
                    )
                    route_modes = ordinary_eligible, frozenset(special)
                    mode_results[route_key] = route_modes
                ordinary_eligible, establishing_modes = route_modes
                optical_routes[position] = route_modes
                levels = light_results.get(route_modes)
                if levels is None:
                    levels = self._route_light_levels(ordinary_eligible, establishing_modes)
                    light_results[route_modes] = levels
                resolved = levels[tile.resolved_light_level]
                if resolved is None:
                    # Seeing the first opaque volume surface is not seeing its
                    # contents. Physical wall FOV, range and light still constrain it.
                    at_surface = grid.get_optical_obscurements_at(position, snapshot=optics) if optics else set()
                    if at_surface:
                        prefix = supercover_line(origin, position)[:-1]
                        before_surface: Set[OpticalObscurement] = set()
                        for cell in prefix:
                            before_surface.update(grid.get_optical_obscurements_at(cell, snapshot=optics))
                        potential_normal, potential_special = self._visual_route_modes(
                            modes, ordinary_sight, distance, before_surface, LightLevel.BRIGHT_LIGHT,
                        )
                        light_position = position
                        if OpticalObscurement.MAGICAL_DARKNESS in at_surface and prefix:
                            near = grid.get_tile(*prefix[-1])
                            if near is not None:
                                light_position = prefix[-1]
                        if potential_normal or potential_special:
                            surface_routes[position] = VolumeRay(light_position, potential_normal, bool(potential_special))
                    continue
                visible[position] = True
                visual_modes_by_position[position] = establishing_modes
                effective_light[position] = resolved
        if diagnostic:
            record_action_timing("sensory.recompute.optical_filtering_ms", phase_started)
            phase_started = time.perf_counter()
        nonvisual_positions: Dict[SensesType, Set[Tuple[int, int]]] = {}
        for sense_type in (SensesType.BLINDSIGHT, SensesType.TREMORSENSE):
            sense_range = modes.get(sense_type)
            if sense_range is None:
                continue
            radius = max_distance if sense_range == 0 else (sense_range + 4) // 5
            nonvisual_positions[sense_type] = set(
                grid.compute_propagation_fov(origin, radius)
            )

        if diagnostic:
            record_action_timing("sensory.recompute.nonvisual_geometry_ms", phase_started)
            phase_started = time.perf_counter()
        previous_boundaries = (previous_field.boundaries
            if light_event is not None and previous_field is not None
            and previous_field.revisions.optical == revisions.optical
            and previous_field.revisions.propagation == revisions.propagation else None)
        boundary_positions = optical_candidates | set().union(*nonvisual_positions.values())
        boundaries = (grid.capture_boundary_snapshot(boundary_positions) if previous_boundaries is None else
            grid.shift_observer_boundaries(boundary_positions, previous_boundaries))
        if diagnostic:
            record_action_timing("sensory.recompute.boundary_snapshot_ms", phase_started)
            phase_started = time.perf_counter()
        boundary_evidence: Dict[
            UUID,
            Set[Tuple[Tuple[int, int], bool, Tuple[SensesType, ...]]],
        ] = defaultdict(set)
        self._collect_boundary_evidence(
            boundary_evidence,
            set(visible),
            WorldEdgeChannel.OPTICAL,
            visual=True,
            senses_by_position=visual_modes_by_position, snapshot=boundaries,
        )
        for sense_type, positions in nonvisual_positions.items():
            self._collect_boundary_evidence(
                boundary_evidence,
                positions,
                WorldEdgeChannel.PROPAGATION,
                visual=False,
                fixed_senses=(sense_type,), snapshot=boundaries,
            )

        if diagnostic:
            record_action_timing("sensory.recompute.boundary_evidence_ms", phase_started)
            phase_started = time.perf_counter()
        entity_contacts: Dict[UUID, PerceivedContact] = {}
        object_contacts: Dict[UUID, PerceivedContact] = {}
        candidate_positions = set(visible)
        for positions in nonvisual_positions.values():
            candidate_positions.update(positions)
        occupied_positions = grid.get_contact_candidate_cells(candidate_positions)
        for position in candidate_positions:
            if position not in occupied_positions:
                continue
            for entity_uuid in grid.get_ordered_entities_at(position):
                if entity_uuid == observer_uuid:
                    continue
                subject = BaseBlock.get(entity_uuid)
                if subject is None or not subject.appears_in_entity_contacts():
                    continue
                contact = self._resolve_contact(
                    owner,
                    origin,
                    subject,
                    position,
                    position in visible,
                    visual_modes_by_position.get(position, set()),
                    nonvisual_positions,
                    modes,
                    previous_contact=senses.entities.get(entity_uuid),
                )
                if contact is not None:
                    entity_contacts[entity_uuid] = contact
            for object_uuid in grid.get_ordered_center_objects_at(position):
                subject = BaseBlock.get(object_uuid)
                if subject is None or not subject.should_include_in_senses_objects():
                    continue
                contact = self._resolve_contact(
                    owner,
                    origin,
                    subject,
                    position,
                    position in visible,
                    visual_modes_by_position.get(position, set()),
                    nonvisual_positions,
                    modes,
                    previous_contact=senses.objects.get(object_uuid),
                )
                if contact is not None:
                    previous = object_contacts.get(object_uuid)
                    if previous is not None:
                        chosen = min((previous, contact), key=lambda row: (
                            not row.visual, grid_distance_feet(origin, row.position), row.position,
                        ))
                        established = set(previous.special_senses) | set(contact.special_senses)
                        contact = PerceivedContact(
                            position=chosen.position, visual=previous.visual or contact.visual,
                            special_senses=tuple(mode for mode in SensesType if mode in established),
                        )
                    object_contacts[object_uuid] = contact

        if diagnostic:
            record_action_timing("sensory.recompute.cell_contacts_ms", phase_started)
            phase_started = time.perf_counter()
        # Explicit construction knowledge is not visual sight or truesight.
        # Only the declaring creator receives this otherwise invisible contact.
        for identity in grid.get_known_object_candidates(observer_uuid):
            subject = BaseBlock.get(identity)
            placement = grid.get_object_placement(identity)
            if (subject is not None and placement is not None
                    and subject.is_object_known_to(observer_uuid) and identity not in object_contacts):
                object_contacts[identity] = PerceivedContact(position=placement.position, visual=False, special_senses=())

        if diagnostic:
            record_action_timing("sensory.recompute.known_object_contacts_ms", phase_started)
            phase_started = time.perf_counter()
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
                origin,
                subject,
                placement.position,
                False,
                set(),
                nonvisual_positions,
                modes,
                route_evidence=evidence,
                contact_position=placement.position,
                previous_contact=senses.objects.get(object_uuid),
            )
            if contact is not None:
                object_contacts[object_uuid] = contact

        if diagnostic:
            record_action_timing("sensory.recompute.boundary_contacts_ms", phase_started)
            phase_started = time.perf_counter()
        newly_seen = visible.keys() - senses.seen
        senses.seen.update(newly_seen)
        senses.replace_perception(
            position=origin,
            visible=visible,
            seen=senses.seen,
            entities=entity_contacts,
            objects=object_contacts,
            effective_light_levels=effective_light,
            passive_perception=owner.get_passive_perception(),
            sense_modes_hash=senses.compute_sense_modes_hash(),
            visual_access=senses.visual_access.normalized_score,
        )
        if diagnostic:
            record_action_timing("sensory.recompute.perception_commit_ms", phase_started)
            phase_started = time.perf_counter()
        volume_fields, volume_dependencies = self._visible_volume_geometry(origin, optical_candidates,
            surface_routes, modes, ordinary_sight, senses, optical_radius, optics=optics, boundaries=boundaries)
        if diagnostic:
            record_action_timing("sensory.recompute.volume_geometry_ms", phase_started)
            phase_started = time.perf_counter()
        volume_light_owners: Dict[Tuple[int, int], Set[UUID]] = defaultdict(set)
        volume_provider_owners: Dict[UUID, Set[UUID]] = defaultdict(set)
        for identity, volume in volume_fields.items():
            for ray in (*volume.entrances, *volume.rays.values()):
                volume_light_owners[ray.light_position].add(identity)
            for provider in volume.providers:
                volume_provider_owners[provider].add(identity)
        influence_radius = max(optical_radius, *(max_distance if distance == 0 else (distance + 4) // 5
            for sense, distance in modes.items() if sense in (SensesType.BLINDSIGHT, SensesType.TREMORSENSE)), 0)
        dependency_bounds = (origin[0] - influence_radius - 1, origin[1] - influence_radius - 1,
            origin[0] + influence_radius + 1, origin[1] + influence_radius + 1)
        grants = optical_candidates | set().union(*nonvisual_positions.values())
        grid.subscribe_to_cells(observer_uuid, grants | volume_dependencies,
            dependency_cells=volume_dependencies, dependency_bounds=dependency_bounds)
        senses._field = ObserverField(
            modes=modes,
            ordinary_sight=ordinary_sight,
            visible_volumes={},
            upper_volume_surfaces={},
            max_distance=max_distance,
            revisions=grid.observer_spatial_revisions(observer_uuid),
            visual_modes=visual_modes_by_position,
            nonvisual_positions=nonvisual_positions,
            optical_routes=optical_routes, boundaries=boundaries,
            volume_fields=volume_fields,
            volume_light_owners=volume_light_owners,
            volume_provider_owners=volume_provider_owners,
            volume_sights={},
            grant_base_cells=grants,
            dependency_bounds=dependency_bounds,
            volume_dependencies=volume_dependencies,
            volume_grants={},
        )
        if diagnostic:
            record_action_timing("sensory.recompute.field_memberships_ms", phase_started)
            phase_started = time.perf_counter()
        self._update_volume_light(senses, set(volume_fields))
        if diagnostic:
            record_action_timing("sensory.recompute.volume_light_ms", phase_started)
            phase_started = time.perf_counter()
        changed_effects = self._refresh_hazards(observer_uuid, senses, hazard_positions)
        if effect_before is not None:
            effect_before.update(changed_effects)
        if diagnostic:
            record_action_timing("sensory.recompute.hazards_ms", phase_started)
            phase_started = time.perf_counter()
        self.refresh_observer(observer_uuid)
        if diagnostic:
            record_action_timing("sensory.recompute.observer_reverse_memberships_ms", phase_started)
            phase_started = time.perf_counter()
        return newly_seen

    @staticmethod
    def _refresh_hazards(
        observer_uuid: UUID, senses: Senses,
        affected_positions: Optional[Set[Tuple[int, int]]],
        *, hazard_before: Optional[Dict[Tuple[int, int], Optional[bool]]] = None,
        visibility_changed_positions: Optional[Set[Tuple[int, int]]] = None,
    ) -> Dict[UUID, Optional[PerceivedSpatialEffect]]:
        """Resolve new/affected visible cells using the existing native hazard rule."""
        if senses._effects_by_position is None:
            senses._effects_by_position = {}
            SpatialSensesSystem._index_effect_changes(senses,
                {identity: None for identity in senses.spatial_effects})
        effect_index = senses._effects_by_position
        visible = senses.visible.keys()
        if visibility_changed_positions is None:
            departed = senses.hazardous_cells.keys() - visible
            positions = visible - senses.hazardous_cells.keys()
        else:
            # The caller has just changed visibility only inside this set.
            # Hazard membership outside it already matches the current view.
            departed = {position for position in visibility_changed_positions
                if position in senses.hazardous_cells and position not in visible}
            positions = {position for position in visibility_changed_positions
                if position in visible and position not in senses.hazardous_cells}
        positions.update(visible if affected_positions is None else visible & affected_positions)
        if hazard_before is not None:
            hazard_before.update((position, senses.hazardous_cells.get(position))
                for position in positions | departed)
        for position in departed:
            senses.hazardous_cells.pop(position)
        volumes = senses._field.visible_volumes if senses._field is not None else {}
        upper = senses._field.upper_volume_surfaces if senses._field is not None else {}
        surfaces = {row.position for rows in upper.values() for row in rows}
        surfaces.update(set().union(*volumes.values()) if volumes else set())
        touched = set(senses._active_effects)
        for position in positions | departed:
            touched.update(effect_index.get(position, ()))
        if not positions and not surfaces:
            before = {identity: senses.spatial_effects.get(identity) for identity in touched}
            for identity in touched:
                previous = senses.spatial_effects[identity]
                if previous.visible_volume_positions or previous.upper_volume_surfaces or any(row.positions for row in previous.suppressions):
                    senses.spatial_effects[identity] = previous.model_copy(update={
                        "visible_volume_positions": (),
                        "upper_volume_surfaces": (),
                        "suppressions": tuple(row.model_copy(update={"positions": tuple(
                            position for position in row.positions if position in visible)})
                                              for row in previous.suppressions)})
            SpatialSensesSystem._index_effect_changes(senses, before)
            return before
        grid = get_map()
        candidates: Dict[UUID, Tuple[SpatialConditionOwner, Set[Tuple[int, int]]]] = {}
        for position in positions | surfaces:
            for condition in grid.get_spatial_conditions_at(position):
                if (position not in visible and position not in volumes.get(condition.uuid, ())
                        and not any(row.position == position for row in upper.get(condition.uuid, ()))):
                    continue
                if condition.uuid not in candidates:
                    candidates[condition.uuid] = (condition, set())
                candidates[condition.uuid][1].add(position)
        observations: Dict[UUID, PerceivedSpatialEffect] = {}
        for condition, observed_positions in candidates.values():
            volume_positions = observed_positions & volumes.get(condition.uuid, frozenset())
            observation = condition.get_spatial_observation(
                observed_positions & visible, observer_uuid=observer_uuid,
                discovered=condition.uuid in senses.spatial_effects,
            )
            if observation is not None:
                observations[condition.uuid] = observation.model_copy(update={
                    "owner_revision": condition.observation_revision,
                    "duration": condition.snapshot_duration(),
                    "positions": tuple(sorted(set(observation.positions) | volume_positions)),
                    "visible_volume_positions": tuple(sorted(volume_positions)),
                    "upper_volume_surfaces": upper.get(condition.uuid, ()),
                })
        # Resolve references after all candidates: a first observation must not
        # depend on whether the provider or its affected field was visited first.
        for identity, observation in observations.items():
            previous = senses.spatial_effects.get(identity)
            retained_suppressions = ({row.provider_uuid: row for row in previous.suppressions}
                if previous is not None and previous.area_geometry == observation.area_geometry else {})
            suppressions = []
            for outcome in candidates[identity][0].spatial_suppressions:
                retained = retained_suppressions.get(outcome.provider_uuid)
                provider = observations.get(outcome.provider_uuid, senses.spatial_effects.get(outcome.provider_uuid))
                if retained is None:
                    if provider is None or provider.area_geometry is None:
                        continue
                    retained = outcome.model_copy(update={
                        "provider_content_ref": provider.content_ref,
                        "area_geometry": provider.area_geometry,
                        "anchor_elevation_steps": provider.anchor_elevation_steps})
                # Only currently admitted geometry is added, never hidden ground.
                admitted = set(outcome.positions) & (visible | volumes.get(identity, frozenset()))
                suppressions.append(retained.model_copy(update={"positions": tuple(sorted(admitted))}))
            observations[identity] = observation.model_copy(update={"suppressions": tuple(suppressions)})
        touched.update(observations)
        before = {identity: senses.spatial_effects.get(identity) for identity in touched}
        for identity in touched:
            previous = senses.spatial_effects.get(identity)
            if previous is None:
                continue
            # Inspect only newly seen/changed visible cells. Hidden parts retain
            # their last observation, even when the objective owner was removed.
            retained = set(previous.positions) - positions
            observed = observations.pop(identity, None)
            if observed is not None:
                retained.update(observed.positions)
            if retained:
                senses.spatial_effects[identity] = (observed or previous).model_copy(
                    update={"positions": tuple(sorted(retained)),
                            "visible_volume_positions": observed.visible_volume_positions if observed is not None else (),
                            "upper_volume_surfaces": observed.upper_volume_surfaces if observed is not None else (),
                            "suppressions": observed.suppressions if observed is not None else tuple(
                                row.model_copy(update={"positions": tuple(position for position in row.positions
                                    if position in visible)}) for row in previous.suppressions)},
                )
            else:
                senses.spatial_effects.pop(identity)
        senses.spatial_effects.update(observations)
        for x, y in positions:
            senses.hazardous_cells[(x, y)] = grid.is_position_hazardous_for(x, y, observer_uuid)
        SpatialSensesSystem._index_effect_changes(senses, before)
        return before

    @staticmethod
    def _index_effect_changes(senses: Senses, before: Dict[UUID, Optional[PerceivedSpatialEffect]]) -> None:
        index = senses._effects_by_position
        assert index is not None
        for identity, previous in before.items():
            current = senses.spatial_effects.get(identity)
            old_positions = set(previous.positions) if previous is not None else set()
            new_positions = set(current.positions) if current is not None else set()
            for position in old_positions - new_positions:
                members = index[position]
                members.discard(identity)
                if not members:
                    del index[position]
            for position in new_positions - old_positions:
                index.setdefault(position, set()).add(identity)
            if current is not None and (current.visible_volume_positions or current.upper_volume_surfaces
                    or any(row.positions for row in current.suppressions)):
                senses._active_effects.add(identity)
            else:
                senses._active_effects.discard(identity)

    @classmethod
    def _visible_volume_geometry(cls, origin: Tuple[int, int], candidates: Set[Tuple[int, int]],
            first_surfaces: Dict[Tuple[int, int], VolumeRay], modes: Dict[SensesType, int],
            ordinary_sight: bool, senses: Senses, optical_radius: int,
            *, optics: Optional[OpticalSnapshot] = None, boundaries: Optional[BoundarySnapshot] = None,
            ) -> Tuple[Dict[UUID, VolumeField], Set[Tuple[int, int]]]:
        """Observe a volume's geometry without treating its own interior as a wall.

        First-surface sight establishes the object. Its geometry may be viewed
        from another camera, but physical walls and all other obscuration owners
        still clip it. Ground/actor sight remains the separate original query.
        """
        grid = get_map()
        owners = {condition.uuid: condition for position in first_surfaces
                  for condition in grid.get_spatial_conditions_at(position)
                  if condition.get_optical_obscurement_at(position) is not None}
        result = {}
        dependencies: Set[Tuple[int, int]] = set()
        for identity, condition in owners.items():
            entrances = tuple(ray for position, ray in first_surfaces.items()
                if condition.get_optical_obscurement_at(position) is not None)
            rays = {}
            owner_dependencies = set()
            occupied = grid.get_spatial_condition_positions(identity)
            geometry_positions = occupied
            for suppression in condition.spatial_suppressions:
                geometry_positions = geometry_positions | set(suppression.positions)
            observation = condition.get_spatial_observation(set(), observer_uuid=senses.source_entity_uuid,
                discovered=True)
            sphere = observation.area_geometry if observation is not None else None
            base = observation.anchor_elevation_steps if observation is not None else None
            for position in sorted(geometry_positions):
                planes = ()
                if position not in candidates:
                    if (not isinstance(sphere, SpherePresentationGeometry) or base is None
                            or position not in occupied
                            or sum((position[i] - origin[i]) ** 2 for i in (0, 1)) > optical_radius ** 2):
                        continue
                    # Subscribe to tested routes even when rejected: a remote
                    # door closing OR reopening must update this surface sight.
                    owner_dependencies.update((cell[0]+dx, cell[1]+dy)
                        for cell in supercover_line(origin, position)
                        for dx,dy in ((0,0),(1,0),(-1,0),(0,1),(0,-1))
                        if grid.get_tile(cell[0]+dx, cell[1]+dy) is not None)
                    planes = grid.upper_volume_sight_planes(origin, position, snapshot=boundaries)
                    if not planes:
                        continue
                    # Sphere top in native elevation steps. Cell-corner maximum
                    # keeps a partly exposed cell without granting its lower half.
                    dx = max(0., abs(position[0] - sphere.center[0]) - .5)
                    dy = max(0., abs(position[1] - sphere.center[1]) - .5)
                    top = base + math.sqrt(max(0., (sphere.radius_feet / 5) ** 2 - dx*dx - dy*dy))
                    if all(max(a*x + b*y + c for a,b,c in planes) >= top
                           for x,y in ((position[0]+dx, position[1]+dy)
                                       for dx in (-.5,.5) for dy in (-.5,.5))):
                        continue
                route = supercover_line(origin, position)
                entry = next((index for index, cell in enumerate(route)
                              if condition.get_optical_obscurement_at(cell) is not None), None)
                if entry is None:
                    continue
                light_position = route[entry]
                if (condition.get_optical_obscurement_at(light_position) is OpticalObscurement.MAGICAL_DARKNESS
                        and entry > 0):
                    light_position = route[entry - 1]
                tile = grid.get_tile(*light_position)
                if tile is None:
                    continue
                obscurements = grid.get_optical_obscurements_on_route(
                    origin, position, excluded_owner_uuid=identity, snapshot=optics)
                normal, special = cls._visual_route_modes(modes, ordinary_sight,
                    grid_distance_feet(origin, position), obscurements, LightLevel.BRIGHT_LIGHT)
                if normal or special:
                    rays[position] = VolumeRay(light_position, normal, bool(special),
                        VolumeSurfaceSight(position=position, lower_height_planes=planes) if planes else None)
            providers = {row.provider_uuid: frozenset(row.positions)
                for row in condition.spatial_suppressions}
            result[identity] = VolumeField(entrances, rays, providers, frozenset(owner_dependencies))
            if any(ray.special or (ray.ordinary and (tile := grid.get_tile(*ray.light_position)) is not None
                    and tile.resolved_light_level.value > LightLevel.DARKNESS.value) for ray in entrances):
                dependencies.update(owner_dependencies)
        return result, dependencies

    @staticmethod
    def _update_volume_light(senses: Senses, owners: Set[UUID]) -> None:
        """Filter only volumes whose entrance or surface light changed."""
        field = senses._field
        assert field is not None
        grid = get_map()
        touched = set(owners)
        grants_changed = False
        for identity in owners:
            volume = field.volume_fields[identity]
            touched.update(volume.providers)
            established = any(ray.special or (ray.ordinary
                and (tile := grid.get_tile(*ray.light_position)) is not None
                and tile.resolved_light_level.value > LightLevel.DARKNESS.value)
                for ray in volume.entrances)
            grants = volume.dependencies if established else frozenset()
            grants_changed |= grants != field.volume_grants.get(identity, frozenset())
            field.volume_grants[identity] = grants
            visible = set()
            upper = []
            if established:
                for position, ray in volume.rays.items():
                    tile = grid.get_tile(*ray.light_position)
                    if ray.special or (ray.ordinary and tile is not None
                            and tile.resolved_light_level.value > LightLevel.DARKNESS.value):
                        if ray.upper_surface is None:
                            visible.add(position)
                        else:
                            upper.append(ray.upper_surface)
            field.volume_sights[identity] = frozenset(visible)
            if upper:
                field.upper_volume_surfaces[identity] = tuple(upper)
            else:
                field.upper_volume_surfaces.pop(identity, None)
        if grants_changed:
            grants = field.grant_base_cells | set().union(*field.volume_grants.values())
            grid.subscribe_to_cells(senses.source_entity_uuid, grants,
                dependency_cells=field.volume_dependencies, dependency_bounds=field.dependency_bounds)
        for identity in touched:
            visible = field.volume_sights.get(identity, frozenset())
            if identity in senses.spatial_effects and grid.get_spatial_condition(identity) is not None:
                occupied = grid.get_spatial_condition_positions(identity)
                for owner in field.volume_provider_owners.get(identity, ()):
                    visible = visible | (field.volume_sights.get(owner, frozenset())
                        & field.volume_fields[owner].providers[identity] & occupied)
            if visible:
                field.visible_volumes[identity] = visible
            else:
                field.visible_volumes.pop(identity, None)

    @staticmethod
    def _route_light_levels(
        ordinary: bool, special: AbstractSet[SensesType],
    ) -> Dict[LightLevel, Optional[LightLevel]]:
        """Resolve each objective light once for one optical eligibility value."""
        levels: Dict[LightLevel, Optional[LightLevel]] = {}
        for light in LightLevel:
            if not special and not (ordinary and light > LightLevel.DARKNESS):
                levels[light] = None
            elif light <= LightLevel.DARKNESS and (
                SensesType.DEVILS_SIGHT in special or SensesType.TRUESIGHT in special
            ):
                levels[light] = LightLevel.BRIGHT_LIGHT
            elif light is LightLevel.DARKNESS and SensesType.DARKVISION in special:
                levels[light] = LightLevel.DIM_LIGHT
            elif light is LightLevel.DIM_LIGHT and SensesType.DARKVISION in special:
                levels[light] = LightLevel.BRIGHT_LIGHT
            else:
                levels[light] = light
        return levels

    @staticmethod
    def _visual_route_modes(
        modes: Dict[SensesType, int], ordinary_sight: bool, distance: int,
        obscurements: AbstractSet[OpticalObscurement], light: LightLevel,
    ) -> Tuple[bool, Set[SensesType]]:
        """Resolve the existing light/range/obscurement rule for one optical ray."""
        ordinary = (ordinary_sight and OpticalObscurement.HEAVY not in obscurements
                    and OpticalObscurement.MAGICAL_DARKNESS not in obscurements
                    and light.value > LightLevel.DARKNESS.value)
        special: Set[SensesType] = set()
        if OpticalObscurement.HEAVY not in obscurements:
            for sense in (SensesType.DARKVISION, SensesType.DEVILS_SIGHT, SensesType.TRUESIGHT):
                if (SpatialSensesSystem._sense_in_range(modes, sense, distance)
                        and (sense is not SensesType.DARKVISION
                             or OpticalObscurement.MAGICAL_DARKNESS not in obscurements)):
                    special.add(sense)
        return ordinary, special

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
        senses_by_position: Optional[Dict[Tuple[int, int], frozenset[SensesType]]] = None,
        fixed_senses: Tuple[SensesType, ...] = (),
        snapshot: Optional[BoundarySnapshot] = None,
    ) -> None:
        grid = get_map()
        candidates = positions
        if snapshot is not None:
            candidates = (positions & snapshot.routes.keys()) | {
                position for position in positions - snapshot.coverage_base
                if not boundary_snapshot_covers(snapshot, position)}
        for position in sorted(candidates):
            evidence_senses = (
                tuple(sorted(senses_by_position.get(position, set()), key=lambda value: value.value))
                if senses_by_position is not None
                else fixed_senses
            )
            directions = (snapshot.routes.get(position, ())
                if snapshot is not None and boundary_snapshot_covers(snapshot, position) else CardinalDirection)
            for direction in directions:
                exit_layer, entry_layer = grid.get_boundary_route_layers(
                    position,
                    direction,
                    channel, snapshot=snapshot,
                )
                for object_uuid in (*exit_layer, *entry_layer):
                    result[object_uuid].add(
                        (position, visual, evidence_senses)
                    )

    def _resolve_contact(
        self,
        owner: BaseBlock,
        observer_position: Tuple[int, int],
        subject: BaseBlock,
        position: Tuple[int, int],
        cell_visual: bool,
        visual_modes: AbstractSet[SensesType],
        nonvisual_positions: Dict[SensesType, Set[Tuple[int, int]]],
        modes: Dict[SensesType, int],
        *,
        route_evidence: Optional[
            Tuple[Tuple[Tuple[int, int], bool, Tuple[SensesType, ...]], ...]
        ] = None,
        contact_position: Optional[Tuple[int, int]] = None,
        previous_contact: Optional[PerceivedContact] = None,
    ) -> Optional[PerceivedContact]:
        if not subject.is_observable_to(owner.uuid):
            return None
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
            distance = grid_distance_feet(observer_position, evidence_position)
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
        resolved_position = contact_position or position
        resolved_senses = tuple(sorted(special, key=lambda value: value.value))
        # Native predicates above remain authoritative. Reuse only the exact
        # immutable contact schema; extensions may carry additional state.
        if (type(previous_contact) is PerceivedContact
                and previous_contact.position == resolved_position
                and previous_contact.visual == visual
                and previous_contact.special_senses == resolved_senses):
            if action_timing_enabled():
                record_action_count("sensory.recompute.reused_contacts", 1)
            return previous_contact
        return PerceivedContact(position=resolved_position, visual=visual,
            special_senses=resolved_senses)

    def publish_observer_refresh(
        self, observer_uuid: UUID, before: SensesSnapshot,
    ) -> Optional[SensoryUpdateEvent]:
        """Record an independent explicit refresh after existing cache updates."""
        senses = self.senses_by_observer.get(observer_uuid)
        if senses is None:
            return None
        self._refresh_light_sources(observer_uuid, senses)
        event = emit_sensory_update_delta(
            observer_uuid, None, before, capture_senses_snapshot(senses),
            SensoryUpdateReason.UNKNOWN,
            initial=observer_uuid not in self.published_observers,
        )
        if event is not None:
            self.published_observers.add(observer_uuid)
        return event

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
        registered = self.senses_by_observer
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
            if target is not None and target in registered:
                return {target}
            grid = get_map()
            tile = grid.get_tile_by_uuid(target) if target is not None else None
            placement = grid.get_object_placement(target) if target is not None else None
            positions = (tile.position,) if tile is not None else placement.positions if placement is not None else ()
            candidates: Set[UUID] = set()
            for position in positions:
                candidates.update(grid.get_subscribers_at(position))
            return {identity for identity in candidates if identity in registered}
        if isinstance(event, DeathEvent):
            return set(self.observers_by_entity.get(event.entity_uuid, set()))
        if isinstance(event, SpatialEffectChangeEvent):
            grid = get_map()
            candidates: Set[UUID] = set()
            for position in event.get_affected_positions():
                candidates.update(grid.get_subscribers_at(position))
            return {identity for identity in candidates if identity in registered}
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
        return {identity for identity in candidates if identity in registered}

    def __call__(self, event: Event) -> None:
        """Reduce indexed observers before the causal event completes."""
        record_action_count("sensory.reducer_call", 1)
        if self._recording():
            for observer_uuid in self.candidate_observer_uuids(event):
                self._pending.setdefault(observer_uuid, _GroupSettlement()).events.append(event)
            return
        sensory_events: List[SensoryUpdateEvent] = []
        deferred: Set[UUID] = set()
        if event.event_type in (EventType.SPATIAL_LIGHT_CHANGED, EventType.SPATIAL_LIGHT_SOURCES_CHANGED):
            parent = EventQueue.get_event_by_uuid(event.parent_event) if event.parent_event is not None else None
            if isinstance(parent, SpatialChangeEvent) and parent.senses_hint is not None and parent.senses_hint.requires_light_recompute:
                # The geometry parent observes after every affected emitter has
                # settled. Its observers must not see partial source recomputes.
                deferred = self.candidate_observer_uuids(parent)
        for observer_uuid in sorted(self.candidate_observer_uuids(event), key=str):
            if observer_uuid in deferred:
                continue
            senses = self.senses_by_observer.get(observer_uuid)
            if senses is None:
                continue
            if (event.event_type is EventType.SPATIAL_LIGHT_SOURCES_CHANGED
                    and observer_uuid in self.published_observers):
                record_action_count("sensory.light_sources_only", 1)
                before = _capture_senses_transition(senses, set(), positions=set(),
                    entities=set(), objects=set(), effects=set())
                self._refresh_light_sources(observer_uuid, senses)
                after = _capture_senses_transition(senses, set(), positions=set(),
                    entities=set(), objects=set(), effects=set())
                sensory_event = emit_sensory_update_delta(observer_uuid, event, before, after,
                    SensoryUpdateReason.LIGHT, register_event=False)
                if sensory_event is not None:
                    sensory_events.append(sensory_event)
                continue
            if (isinstance(event, SpatialChangeEvent)
                    and event.event_type is EventType.SPATIAL_LIGHT_CHANGED
                    and observer_uuid in self.published_observers
                    and self._can_update_light(observer_uuid, senses, event)):
                sensory_event = self._update_light(observer_uuid, senses, event)
                if sensory_event is not None:
                    sensory_events.append(sensory_event)
                continue
            if (
                event.event_type is EventType.SPATIAL_ENTITY_ENTERED
                and observer_uuid in self.published_observers
                and self._field_is_current(observer_uuid, senses)
            ):
                movement = cast(SpatialChangeEvent, event)
                if (
                    movement.entity_uuid is not None
                    and movement.entity_uuid != observer_uuid
                    and movement.old_position is not None
                ):
                    sensory_event = self._update_entity_contact(observer_uuid, senses, movement)
                    if sensory_event is not None:
                        sensory_events.append(sensory_event)
                    continue
            sensory_event = self._reduce_observer(observer_uuid, senses, (event,))
            if sensory_event is not None:
                sensory_events.append(sensory_event)
        if sensory_events:
            EventQueue.register_completion_sequence(sensory_events)
            self.published_observers.update(event.observer_uuid for event in sensory_events)

    def _reduce_observer(
        self,
        observer_uuid: UUID,
        senses: Senses,
        events: Sequence[Event],
        *,
        force_full: bool = False,
        cause: Optional[Event] = None,
    ) -> Optional[SensoryUpdateEvent]:
        """Settle one observer for one fact, or for every fact of a closed group.

        The hazard-only path applies only when every fact is a hazard-refresh
        kind and the observer's field is still current; otherwise one full
        recompute covers the union of the facts (plan §5.3-5.4).
        """
        initial = observer_uuid not in self.published_observers
        effect_before: Dict[UUID, Optional[PerceivedSpatialEffect]] = {}
        hazard_before: Optional[Dict[Tuple[int, int], Optional[bool]]] = None
        newly_seen: Set[Tuple[int, int]] = set()
        hazard_positions: Optional[Set[Tuple[int, int]]] = set()
        for event in events:
            event_positions = self._hazard_positions_for(event)
            hazard_positions = (None if hazard_positions is None or event_positions is None
                else hazard_positions | event_positions)
        # Hazard-refresh kinds: the observer's own refresh, residue membership,
        # movement topology (paths are lazy; sight-moving support changes bump
        # the optical revision, which `_field_is_current` rejects), and spatial
        # condition membership (it bumps exactly its data's channels; the
        # contacts of objects on its cells are refreshed too, since a condition
        # can gate their observability, e.g. trap hardware).
        cheap_kinds = all(self._is_owner_refresh(event, observer_uuid) or self._residue_tile(event) is not None
            or self._is_tile_refresh(event) or isinstance(event, SpatialEffectChangeEvent) for event in events)
        gated_objects: Set[UUID] = set()
        field = senses._field
        only_refresh_hazards = (
            not force_full
            and cheap_kinds
            and observer_uuid in self.published_observers
            and field is not None
            and field.revisions.occupancy == get_map().observer_spatial_revisions(observer_uuid).occupancy
            and self._field_is_current(observer_uuid, senses)
        )
        if only_refresh_hazards:
            record_action_count("sensory.hazard_only", 1)
            if any(isinstance(event, SpatialEffectChangeEvent) for event in events):
                gated_objects = {identity for event in events if isinstance(event, SpatialEffectChangeEvent)
                                 for position in event.get_affected_positions()
                                 for identity in get_map().get_objects_at(position)}
            before = _capture_senses_transition(senses, set(), positions=set(),
                entities=set(), objects=gated_objects, effects=set())
            for identity in gated_objects:
                contact = self._object_contact(observer_uuid, senses, identity)
                if contact is None:
                    senses.objects.pop(identity, None)
                else:
                    senses.objects[identity] = contact
            if gated_objects:
                self.refresh_observer(observer_uuid)
            # A child light completion can already have refreshed the moving
            # observer at this committed position. Reuse only a fully current
            # field; the parent still publishes its own delta/path boundary.
            # Inert tile after-values and residue membership do not change contacts
            # when field and occupancy revisions still match. Refresh their
            # hazards without resolving every visible cell again.
            # Support elevation, traversal and other spatial changes retain
            # their full refresh (including upper-volume sight planes).
            hazard_before = {}
            effect_before = self._refresh_hazards(observer_uuid, senses, hazard_positions,
                hazard_before=hazard_before, visibility_changed_positions=set())
            before = replace(before, hazardous_cells={position: value
                for position, value in hazard_before.items() if value is not None})
        else:
            before = _capture_senses_transition(senses, set(), effects=set())
            newly_seen = self.recompute_observer(observer_uuid, hazard_positions=hazard_positions,
                effect_before=effect_before,
                light_event=self._single_light_event(events))
        before = replace(before, spatial_effects={identity: value for identity, value in effect_before.items()
            if value is not None})
        if not only_refresh_hazards:
            self._refresh_light_sources(observer_uuid, senses)
        after = _capture_senses_transition(senses, senses.seen if initial else newly_seen,
            positions=set() if only_refresh_hazards else None,
            entities=set() if only_refresh_hazards else None,
            objects=gated_objects if only_refresh_hazards else None,
            effects=None if initial else set(effect_before))
        if hazard_before is not None:
            after = replace(after, hazardous_cells={position: senses.hazardous_cells[position]
                for position in hazard_before if position in senses.hazardous_cells})
        projection_changed = any((
            before.position != after.position,
            before.visible != after.visible,
            before.seen != after.seen,
            before.entities != after.entities,
            before.objects != after.objects,
            before.passive_perception != after.passive_perception,
            before.hazardous_cells != after.hazardous_cells,
            before.spatial_effects != after.spatial_effects,
        ))
        visible_topology_changed = any(self._changes_visible_topology(event, senses) for event in events)
        if projection_changed or visible_topology_changed:
            senses._paths_dirty = True
            after = replace(after, paths_dirty=True)
        # A group's settlement attaches to its still-open root: a completed
        # fact can no longer adopt children (lineage capture follows them).
        return emit_sensory_update_delta(
            observer_uuid,
            cause if cause is not None else events[-1],
            before,
            after,
            self._reason_for(events[-1], observer_uuid),
            register_event=False,
            initial=initial,
        )

    @staticmethod
    def _residue_tile(event: Event) -> Optional[Tile]:
        """The Tile whose residue membership this condition fact changed, if any."""
        if (isinstance(event, (ConditionApplicationEvent, ConditionRemovalEvent))
                and event.target_entity_uuid is not None
                and event.condition.snapshot_tile_residue() is not None):
            return get_map().get_tile_by_uuid(event.target_entity_uuid)
        return None

    def _hazard_positions_for(self, event: Event) -> Optional[Set[Tuple[int, int]]]:
        """Cells whose hazards a fact can change; None means every visible cell."""
        residue_tile = self._residue_tile(event)
        if residue_tile is not None:
            return {residue_tile.position}
        if isinstance(event, SpatialChangeEvent):
            if (event.event_type is EventType.SPATIAL_LIGHT_CHANGED and event.senses_hint is not None
                    and event.senses_hint.light_changed_positions is not None):
                return set(event.senses_hint.light_changed_positions)
            return self._candidate_positions(event)
        if isinstance(event, SpatialEffectChangeEvent):
            return event.get_affected_positions()
        if isinstance(event, (ConditionApplicationEvent, ConditionRemovalEvent)) and event.resulting_tile is not None:
            return {event.resulting_tile.position}
        return None

    @staticmethod
    def _is_owner_refresh(event: Event, observer_uuid: UUID) -> bool:
        return (
            event.event_type is EventType.TURN_START
            or (event.event_type in (EventType.CONDITION_APPLICATION, EventType.CONDITION_REMOVAL)
                and event.target_entity_uuid == observer_uuid)
            or (isinstance(event, SpatialChangeEvent)
                and event.event_type is EventType.SPATIAL_ENTITY_ENTERED
                and event.entity_uuid == observer_uuid)
        )

    @staticmethod
    def _is_tile_refresh(event: Event) -> bool:
        # Movement topology (costs, support) never needs a full observer
        # recompute: paths are lazy and marked dirty, and any change that moves
        # sight geometry bumps the observer's optical revision.
        return (isinstance(event, SpatialChangeEvent)
            and event.event_type is EventType.SPATIAL_TILE_CHANGED
            and event.senses_hint is not None
            and not event.senses_hint.requires_fov)

    @staticmethod
    def _single_light_event(events: Sequence[Event]) -> Optional[SpatialChangeEvent]:
        lights = [event for event in events if isinstance(event, SpatialChangeEvent)
            and event.event_type is EventType.SPATIAL_LIGHT_CHANGED]
        return lights[0] if len(lights) == 1 else None

    def _changes_visible_topology(self, event: Event, senses: Senses) -> bool:
        if isinstance(event, SpatialChangeEvent):
            hint = event.senses_hint
            if hint is None or not hint.requires_paths:
                return False
            return (any(senses.visible.get(position, False) for position in self._candidate_positions(event))
                or (event.object_uuid is not None and event.object_uuid in senses.objects))
        if isinstance(event, SpatialEffectChangeEvent):
            return any(senses.visible.get(position, False) for position in event.get_affected_positions())
        return False

    @staticmethod
    def _refresh_light_sources(observer_uuid: UUID, senses: Senses) -> None:
        """Retain compact emitter descriptors; cell illumination has its native events."""
        grid = get_map()
        visible = {position for position, value in senses.visible.items() if value}
        sources = grid.observe_light_sources(observer_uuid, visible, senses.entities, senses.objects,
            senses.light_sources)
        for identity, previous in senses.light_sources.items():
            if identity not in sources:
                senses.light_source_removals[identity] = max(previous.revision, grid.light_source_revision(identity))
        for identity in sources:
            senses.light_source_removals.pop(identity, None)
        senses.light_sources = sources

    def _field_is_current(self, observer_uuid: UUID, senses: Senses, *, illumination: bool = True) -> bool:
        """Whether retained cell evidence still describes this observer's world."""
        field = senses._field
        owner = BaseBlock.get(observer_uuid)
        if field is None or owner is None or owner.get_position() != senses.position:
            return False
        revisions = get_map().observer_spatial_revisions(observer_uuid)
        return (
            field.revisions.optical == revisions.optical
            and field.revisions.propagation == revisions.propagation
            and (not illumination or field.revisions.illumination == revisions.illumination)
            and field.max_distance == senses._perception_max_distance
            and field.ordinary_sight == owner.has_ordinary_visual_sight()
            and senses._last_visual_access == senses.visual_access.normalized_score
            and senses._last_passive_perception == owner.get_passive_perception()
            and field.modes == {mode.sense_type: mode.range_feet for mode in senses.get_sense_modes()}
        )

    def _can_update_light(self, observer_uuid: UUID, senses: Senses, event: SpatialChangeEvent, *,
                          covers_group: bool = False) -> bool:
        field = senses._field
        if field is None or not self._field_is_current(observer_uuid, senses, illumination=False):
            return False
        revisions = get_map().observer_spatial_revisions(observer_uuid)
        # A group's settled light fact carries every illumination change of the
        # group, so any gap is covered by it; otherwise a gap means buffered
        # changes that require a complete current solve.
        if not covers_group and revisions.illumination - field.revisions.illumination not in (0, 1):
            return False
        if revisions.occupancy == field.revisions.occupancy:
            return True
        parent = EventQueue.get_event_by_uuid(event.parent_event) if event.parent_event is not None else None
        return (revisions.occupancy == field.revisions.occupancy + 1
            and isinstance(parent, SpatialChangeEvent)
            and parent.event_type is EventType.SPATIAL_ENTITY_ENTERED
            and self._covers_occupancy(observer_uuid, parent))

    @staticmethod
    def _covers_occupancy(observer_uuid: UUID, event: SpatialChangeEvent) -> bool:
        """Associate one outstanding local membership change with its native entry."""
        grid = get_map()
        return (event.entity_uuid is not None and event.old_position is not None
            and grid.get_entity_position(event.entity_uuid) == event.position
            and any(observer_uuid in grid.get_dependent_observers_at(position)
                for position in (event.old_position, event.position)))

    def _update_light(self, observer_uuid: UUID, senses: Senses,
            event: SpatialChangeEvent) -> Optional[SensoryUpdateEvent]:
        """Refilter the changed optical cells and their contact dependents."""
        record_action_count("sensory.light_delta", 1)
        grid = get_map()
        field = senses._field
        owner = BaseBlock.get(observer_uuid)
        assert field is not None and owner is not None
        # Notification coverage includes the emitter's whole footprint. Only
        # actual level changes invalidate existing cell/contact evidence.
        positions = (set(event.senses_hint.light_changed_positions)
            if event.senses_hint is not None and event.senses_hint.light_changed_positions is not None
            else self._candidate_positions(event))
        entities: Set[UUID] = set()
        objects: Set[UUID] = set()
        parent = EventQueue.get_event_by_uuid(event.parent_event) if event.parent_event is not None else None
        if isinstance(parent, SpatialChangeEvent):
            positions.update(self._candidate_positions(parent))
            if parent.entity_uuid is not None:
                entities.add(parent.entity_uuid)
            if parent.object_uuid is not None:
                objects.add(parent.object_uuid)
        for position in grid.get_contact_candidate_cells(positions):
            entities.update(grid.get_entities_at(position))
            objects.update(grid.get_center_objects_at(position))
        boundary_positions = (positions & field.boundaries.routes.keys()) | {
            position for position in positions - field.boundaries.coverage_base
            if not boundary_snapshot_covers(field.boundaries, position)}
        for position in boundary_positions:
            if not grid.has_tile(*position):
                continue
            directions = (field.boundaries.routes.get(position, ())
                if boundary_snapshot_covers(field.boundaries, position) else CardinalDirection)
            for direction in directions:
                for channel in (WorldEdgeChannel.OPTICAL, WorldEdgeChannel.PROPAGATION):
                    exits, entries = grid.get_boundary_route_layers(position, direction, channel, snapshot=field.boundaries)
                    objects.update(exits)
                    objects.update(entries)
        entities.discard(observer_uuid)
        volume_owners = set().union(*(field.volume_light_owners.get(position, ()) for position in positions))
        before = _capture_senses_transition(senses, positions & senses.seen,
            positions=positions, entities=entities, objects=objects, effects=set())
        light_results: Dict[Tuple[bool, frozenset[SensesType]], Dict[LightLevel, Optional[LightLevel]]] = {}
        for position in positions & field.optical_routes.keys():
            tile = grid.get_tile(*position)
            assert tile is not None
            route = field.optical_routes[position]
            ordinary, special = route
            levels = light_results.get(route)
            if levels is None:
                levels = self._route_light_levels(ordinary, special)
                light_results[route] = levels
            light = levels[tile.resolved_light_level]
            if light is None:
                senses.visible.pop(position, None)
                senses.effective_light_levels.pop(position, None)
                field.visual_modes.pop(position, None)
                continue
            senses.visible[position] = True
            field.visual_modes[position] = special
            senses.effective_light_levels[position] = light
            senses.seen.add(position)
        for identity in entities:
            subject = BaseBlock.get(identity)
            position = grid.get_entity_position(identity)
            contact = (self._resolve_contact(owner, senses.position, subject, position,
                position in senses.visible, field.visual_modes.get(position, set()),
                field.nonvisual_positions, field.modes)
                if subject is not None and position is not None and subject.appears_in_entity_contacts() else None)
            if contact is None:
                senses.entities.pop(identity, None)
            else:
                senses.entities[identity] = contact
        for identity in objects:
            contact = self._object_contact(observer_uuid, senses, identity)
            if contact is None:
                senses.objects.pop(identity, None)
            else:
                senses.objects[identity] = contact
        senses._field = replace(field, revisions=grid.observer_spatial_revisions(observer_uuid))
        self._update_volume_light(senses, volume_owners)
        effect_before = self._refresh_hazards(observer_uuid, senses, positions,
            visibility_changed_positions=positions)
        before = replace(before, spatial_effects={identity: value for identity, value in effect_before.items()
            if value is not None})
        self.refresh_observer(observer_uuid)
        self._refresh_light_sources(observer_uuid, senses)
        after = _capture_senses_transition(senses, positions & senses.seen,
            positions=positions, entities=entities, objects=objects, effects=set(effect_before))
        if (before.visible != after.visible or before.seen != after.seen
                or before.entities != after.entities or before.objects != after.objects
                or before.hazardous_cells != after.hazardous_cells or before.spatial_effects != after.spatial_effects):
            senses._paths_dirty = True
            after = replace(after, paths_dirty=True)
        return emit_sensory_update_delta(observer_uuid, event, before, after,
            self._reason_for(event, observer_uuid), register_event=False)

    def _object_contact(self, observer_uuid: UUID, senses: Senses, identity: UUID) -> Optional[PerceivedContact]:
        """Aggregate this object's complete current evidence after a local input change."""
        grid = get_map()
        field = senses._field
        owner = BaseBlock.get(observer_uuid)
        subject = BaseBlock.get(identity)
        placement = grid.get_object_placement(identity)
        if field is None or owner is None or subject is None or placement is None:
            return None
        contact = None
        if subject.should_include_in_senses_objects() and placement.boundary_direction is None:
            for position in placement.positions:
                candidate = self._resolve_contact(owner, senses.position, subject, position,
                    position in senses.visible, field.visual_modes.get(position, set()),
                    field.nonvisual_positions, field.modes)
                if candidate is None:
                    continue
                if contact is not None:
                    chosen = min((contact, candidate), key=lambda row: (
                        not row.visual, grid_distance_feet(senses.position, row.position), row.position))
                    established = set(contact.special_senses) | set(candidate.special_senses)
                    candidate = PerceivedContact(position=chosen.position, visual=contact.visual or candidate.visual,
                        special_senses=tuple(mode for mode in SensesType if mode in established))
                contact = candidate
        if contact is None and subject.is_object_known_to(observer_uuid):
            contact = PerceivedContact(position=placement.position, visual=False, special_senses=())
        if subject.should_include_in_senses_objects() and placement.boundary_direction is not None:
            dx, dy = {CardinalDirection.NORTH: (0, 1), CardinalDirection.SOUTH: (0, -1),
                CardinalDirection.EAST: (1, 0), CardinalDirection.WEST: (-1, 0)}[placement.boundary_direction]
            x, y = placement.position
            incident = {(x, y), (x + dx, y + dy)}
            evidence = defaultdict(set)
            self._collect_boundary_evidence(evidence, incident & senses.visible.keys(), WorldEdgeChannel.OPTICAL,
                visual=True, senses_by_position=field.visual_modes, snapshot=field.boundaries)
            for sense, reached in field.nonvisual_positions.items():
                self._collect_boundary_evidence(evidence, incident & reached, WorldEdgeChannel.PROPAGATION,
                    visual=False, fixed_senses=(sense,), snapshot=field.boundaries)
            routes = tuple(sorted(evidence.get(identity, ()), key=lambda row: (
                row[0], not row[1], tuple(sense.value for sense in row[2]))))
            if routes:
                resolved = self._resolve_contact(owner, senses.position, subject, placement.position,
                    False, set(), field.nonvisual_positions, field.modes,
                    route_evidence=routes, contact_position=placement.position)
                if resolved is not None:
                    contact = resolved
        return contact

    def _update_entity_contact(
        self, observer_uuid: UUID, senses: Senses, event: SpatialChangeEvent,
    ) -> Optional[SensoryUpdateEvent]:
        """Apply one membership change using the existing resolved cell evidence."""
        record_action_count("sensory.contact_delta", 1)
        subject_uuid = cast(UUID, event.entity_uuid)
        owner = cast(BaseBlock, BaseBlock.get(observer_uuid))
        field = cast(ObserverField, senses._field)
        subject = BaseBlock.get(subject_uuid)
        before = senses.entities.get(subject_uuid)
        lights_before = dict(senses.light_sources)
        removals_before = dict(senses.light_source_removals)
        contact = None
        if subject is not None and subject.appears_in_entity_contacts():
            position = cast(Tuple[int, int], subject.get_position())
            if subject_uuid in get_map().get_entities_at(position):
                contact = self._resolve_contact(
                    owner, senses.position, subject, position, position in senses.visible,
                    field.visual_modes.get(position, set()), field.nonvisual_positions,
                    field.modes,
                )
        contact_changed = before != contact
        if contact_changed:
            if contact is None:
                senses.entities.pop(subject_uuid, None)
                self._discard_reverse(self.observers_by_entity, subject_uuid, observer_uuid)
            else:
                senses.entities[subject_uuid] = contact
                self.observers_by_entity[subject_uuid].add(observer_uuid)
            if (before is None) != (contact is None):
                footprint = self.footprints_by_observer[observer_uuid]
                self.footprints_by_observer[observer_uuid] = ObserverFootprint(
                    known_path_positions=footprint.known_path_positions,
                    entity_uuids=frozenset(senses.entities),
                    object_uuids=footprint.object_uuids,
                )
        paths_were_dirty = senses._paths_dirty
        if contact_changed or (
            event.senses_hint is not None and event.senses_hint.requires_paths
            and any(position in senses.visible for position in self._candidate_positions(event))
        ):
            senses._paths_dirty = True
        paths_changed = senses._paths_dirty and not paths_were_dirty
        revisions = get_map().observer_spatial_revisions(observer_uuid)
        if revisions.occupancy == field.revisions.occupancy + 1 and self._covers_occupancy(observer_uuid, event):
            senses._field = replace(field, revisions=revisions)
        if contact_changed:
            self._refresh_light_sources(observer_uuid, senses)
        lights = {identity: value for identity, value in senses.light_sources.items()
            if lights_before.get(identity) != value}
        removals = {identity: revision for identity, revision in senses.light_source_removals.items()
            if removals_before.get(identity) != revision}
        if not contact_changed and not paths_changed and not lights and not removals:
            return None
        return SensoryUpdateEvent(
            light_sources_changed=lights, light_sources_removed=removals,
            source_entity_uuid=observer_uuid, target_entity_uuid=observer_uuid,
            observer_uuid=observer_uuid, observer_position=senses.position,
            cause_event_uuid=event.uuid, parent_event=event.uuid,
            observed_changes=tuple(ObservedChangeRef(source_event_uuid=event.uuid,
                source_index=source_index, resolution_ref=event.resolution_ref,
                field=field, owner_uuid=identity)
                for field, identity in (("entity_contact", subject_uuid), ("paths", observer_uuid))
                if (field == "entity_contact" and contact_changed or field == "paths" and paths_changed)
                and (source_index := EventQueue.get_event_index(event.uuid)) is not None),
            parent_lineage=event.lineage_uuid, phase=EventPhase.COMPLETION,
            update_reason=self._reason_for(event, observer_uuid), use_register=False,
            entity_contacts_changed={subject_uuid: contact} if contact_changed and contact is not None else {},
            entity_contacts_removed={subject_uuid} if contact_changed and contact is None else set(),
            paths_dirty=paths_changed,
        )

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
        positions = event.get_affected_positions()
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
