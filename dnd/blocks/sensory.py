"""Authoritative observer-local perception and navigation state.

Perception is data (plan §6b, PV1a): one settlement path recomputes each selected
observer's view with the array rule of `dnd.core.view` over the map's objective
cell grids, then publishes its cells as arrays and emits the difference of its
masks. Python runs per observer, per target on hit cells, per hazard owner and per
spatial condition; never per visible cell.
"""

from typing import AbstractSet, DefaultDict, Dict, FrozenSet, Iterable, List, Mapping, Optional, Self, Sequence, Set, Tuple
from uuid import UUID
from pydantic import Field, InstanceOf, PrivateAttr

import math
from dataclasses import dataclass

import numpy as np
from collections import defaultdict
import time

from dnd.core.effect_types import ObservedChangeRef, ObservedField
from dnd.action_timing import action_timing_enabled, record_action_count, record_action_timing
from dnd.core.base_object import BaseObject
from dnd.core.base_block import BaseBlock
from dnd.core.base_conditions import ConditionApplicationEvent, ConditionRemovalEvent
from dnd.core.base_tiles import Tile
from dnd.core.gridmap import SpatialConditionOwner, get_map
from dnd.core.geometry import supercover_line, supercover_route_table
from dnd.core.presentation_geometry import SpherePresentationGeometry
from dnd.core.values import ModifiableValue
from dnd.core.view import (CENTER, FRAME_DISTANCE_FEET, LIGHT_LEVELS, MAGICAL_DARKNESS_BIT, NO_CELLS, OFF, PLAIN, R,
    SIDE, SPECIAL, SURVIVORS, Box, CellLayer, OpticalView, PerceivedCells, Position, RouteRows, boxes_intersect,
    cell_visible, embed, frame_box, frame_index, frame_of, frame_rows, layer_positions, optical_view, range_bits,
    reach_mask, route_rows, rows_positions, union_box, visible_positions, window_of)
from dnd.core.events import (
    Event, EventType, EventPhase, SpatialChangeEvent,
    SpatialEffectChangeEvent, DeathEvent, EventQueue, OpenGroup, SensoryUpdateEvent,
    SensoryUpdateReason,
)
from dnd.types.senses import (
    PerceivedContact, PerceivedLightSource, PerceivedSpatialEffect, SenseMode, SensesType, VolumeSurfaceSight,
    SensesSnapshot as SensesSnapshot,
)
from dnd.types.world import CardinalDirection, LightLevel, WorldEdgeChannel, cell_key


# Contact sense masks: one bit per SensesType, in enum order.
SENSE_BITS = {sense: 1 << index for index, sense in enumerate(SensesType)}
BLINDSIGHT_BIT, TREMORSENSE_BIT = SENSE_BITS[SensesType.BLINDSIGHT], SENSE_BITS[SensesType.TREMORSENSE]
# The special-sense tuple of a mask in the two native orders: by value (one contact) and in enum
# order (the merge of a multi-cell object's contacts).
SENSES_BY_VALUE = tuple(tuple(sorted((sense for sense, bit in SENSE_BITS.items() if mask & bit), key=lambda s: s.value))
                        for mask in range(1 << len(SENSE_BITS)))
SENSES_BY_ENUM = tuple(tuple(sense for sense in SensesType if mask & SENSE_BITS[sense])
                       for mask in range(1 << len(SENSE_BITS)))
# The contact sense bits an optical eligibility establishes (its special visual senses).
ELIGIBLE_SENSE_BITS = np.array([sum(SENSE_BITS[sense] for sense, bit in (
    (SensesType.DARKVISION, 2), (SensesType.DEVILS_SIGHT, 4), (SensesType.TRUESIGHT, 8)) if eligibility & bit)
    for eligibility in range(16)], dtype=np.uint8)
NONVISUAL_SENSES = ((SensesType.BLINDSIGHT, BLINDSIGHT_BIT), (SensesType.TREMORSENSE, TREMORSENSE_BIT))
DELTAS = {CardinalDirection.NORTH: (0, 1), CardinalDirection.SOUTH: (0, -1),
          CardinalDirection.EAST: (1, 0), CardinalDirection.WEST: (-1, 0)}
OPPOSITE = {CardinalDirection.NORTH: CardinalDirection.SOUTH, CardinalDirection.SOUTH: CardinalDirection.NORTH,
            CardinalDirection.EAST: CardinalDirection.WEST, CardinalDirection.WEST: CardinalDirection.EAST}
CHANNELS = (WorldEdgeChannel.OPTICAL, WorldEdgeChannel.PROPAGATION)


def _empty_seen() -> CellLayer:
    return CellLayer(0, 0, np.zeros((0, 0), dtype=bool))


@dataclass(frozen=True)
class VolumeRay:
    light_position: Tuple[int, int]
    ordinary: bool
    special: bool
    upper_surface: Optional[VolumeSurfaceSight] = None


class Senses(BaseBlock):
    """One observer's published perception (cells as arrays, contacts) and its navigation facts."""

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
    cells: InstanceOf[PerceivedCells] = Field(
        default=NO_CELLS, exclude=True,
        description="Visible cells, their effective light, eligibility and known hazards, over the window.",
    )
    seen: InstanceOf[CellLayer] = Field(default_factory=_empty_seen, exclude=True,
                                        description="Cells this observer has previously seen, in map coordinates.")
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
        cells = self.cells
        xs, ys = np.nonzero(cells.visible.values)
        levels = cells.light.values[xs, ys].tolist()
        return {f"{x},{y}": level for x, y, level in zip((xs + cells.visible.x0).tolist(),
                                                        (ys + cells.visible.y0).tolist(), levels)}

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
        self.walkable = walkable
        self.paths = paths
        self.path_costs = path_costs if path_costs is not None else {}
        self.safe_paths = safe_paths if safe_paths is not None else {}
        self.safe_path_costs = safe_path_costs if safe_path_costs is not None else {}
        self._path_max_distance = path_max_distance
        self._paths_dirty = False
        self._path_revision += 1

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
        if candidate_positions is None:
            # Only cells within the reach square can be within reach (feet = floor(euclid) * 5).
            cells = reach // 5
            x, y = self.position
            candidate_positions = [(x + dx, y + dy) for dx in range(-cells, cells + 1) for dy in range(-cells, cells + 1)]
        return [position for position in candidate_positions
                if cell_visible(self.cells, position) and position != self.position
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


def _sorted_contacts(
    values: Dict[UUID, PerceivedContact],
) -> Dict[UUID, PerceivedContact]:
    """Return contacts in deterministic UUID order."""
    return {uuid: values[uuid] for uuid in sorted(values, key=str)}


@dataclass(frozen=True)
class PublishedSenses:
    """One observer's published perception at one moment: what a sensory event diffs.

    Cells, seen cells, contacts and emitters are replaced whole by each recompute
    (an unchanged one keeps its object), never mutated, so they are held by
    reference; the fixture and removal mappings, mutated in place, are detached.
    """

    position: Tuple[int, int]
    cells: PerceivedCells
    seen: CellLayer
    entities: Dict[UUID, PerceivedContact]
    objects: Dict[UUID, PerceivedContact]
    spatial_effects: Dict[UUID, PerceivedSpatialEffect]
    light_sources: Dict[UUID, PerceivedLightSource]
    light_source_removals: Dict[UUID, int]
    paths_dirty: bool
    passive_perception: int
    sense_modes_hash: int
    sense_modes: Tuple[SenseMode, ...]
    visual_access: int


def published_senses(senses: Senses) -> PublishedSenses:
    """Capture what an observer has published, for a later sensory delta."""
    return PublishedSenses(
        position=senses.position, cells=senses.cells, seen=senses.seen,
        entities=senses.entities, objects=senses.objects,
        spatial_effects=dict(senses.spatial_effects), light_sources=senses.light_sources,
        light_source_removals=dict(senses.light_source_removals), paths_dirty=senses._paths_dirty,
        passive_perception=senses._last_passive_perception, sense_modes_hash=senses._last_sense_modes_hash,
        sense_modes=tuple(senses.get_sense_modes()),  # fresh values each call; an event copies them
        visual_access=senses._last_visual_access,
    )


def capture_senses_snapshot(senses: Senses) -> SensesSnapshot:
    """The observer's published perception in the set/dict form of `SensesSnapshot`."""
    cells = senses.cells
    positions = visible_positions(cells)
    xs, ys = np.nonzero(cells.visible.values)
    light = cells.light.values[xs, ys].tolist()
    hazard = cells.hazard.values[xs, ys].tolist()
    return SensesSnapshot(
        position=senses.position,
        visible=set(positions),
        seen=set(layer_positions(senses.seen)),
        entities=dict(senses.entities),
        objects=dict(senses.objects),
        effective_light_levels={position: LIGHT_LEVELS[level] for position, level in zip(positions, light)},
        hazardous_cells=dict(zip(positions, hazard)),
        spatial_effects=dict(senses.spatial_effects),
        light_sources=dict(senses.light_sources),
        light_source_removals=dict(senses.light_source_removals),
        paths_dirty=senses._paths_dirty,
        passive_perception=senses._last_passive_perception,
        sense_modes_hash=senses._last_sense_modes_hash,
        sense_modes=tuple(mode.model_copy(deep=True) for mode in senses.get_sense_modes()),
        visual_access=senses._last_visual_access,
    )


def _mask_positions(x0: int, y0: int, mask: np.ndarray) -> List[Position]:
    xs, ys = np.nonzero(mask)
    return list(zip((xs + x0).tolist(), (ys + y0).tolist()))


def _seen_added(before: CellLayer, after: CellLayer, initial: bool) -> List[Position]:
    if initial or not before.values.size:
        return layer_positions(after)
    if not after.values.size:
        return []
    box = union_box(before.box, after.box)
    return _mask_positions(box[0], box[1], embed(after, box, np.dtype(bool)) & ~embed(before, box, np.dtype(bool)))


def _cell_delta(before: PublishedSenses, after: PublishedSenses, initial: bool,
                ) -> Tuple[List[Position], List[Position], List[Position], Dict[str, int], Dict[str, bool]]:
    """Visible cells added and removed, seen cells added, and changed light / hazard after-values.

    Each is one mask difference over the union of the two windows, so the cost
    follows the changed cells.
    """
    seen_added = _seen_added(before.seen, after.seen, initial)
    b, a = before.cells, after.cells
    if not a.visible.values.size and not b.visible.values.size:
        return [], [], seen_added, {}, {}
    box = (a.visible.box if not b.visible.values.size else b.visible.box if not a.visible.values.size
           else union_box(b.visible.box, a.visible.box))
    after_visible = embed(a.visible, box, np.dtype(bool))
    after_light = embed(a.light, box, np.dtype(np.uint8))
    after_hazard = embed(a.hazard, box, np.dtype(bool))
    if initial:
        added, removed = after_visible, np.zeros_like(after_visible)
        light_changed = hazard_changed = after_visible
    else:
        before_visible = embed(b.visible, box, np.dtype(bool))
        added, removed = after_visible & ~before_visible, before_visible & ~after_visible
        light_changed = after_visible & (~before_visible | (embed(b.light, box, np.dtype(np.uint8)) != after_light))
        hazard_changed = after_visible & (~before_visible | (embed(b.hazard, box, np.dtype(bool)) != after_hazard))
    lx, ly = np.nonzero(light_changed)
    hx, hy = np.nonzero(hazard_changed)
    light = {f"{x},{y}": level for x, y, level in zip((lx + box[0]).tolist(), (ly + box[1]).tolist(),
                                                     after_light[lx, ly].tolist())}
    hazards = {f"{x},{y}": hazardous for x, y, hazardous in zip((hx + box[0]).tolist(), (hy + box[1]).tolist(),
                                                               after_hazard[hx, hy].tolist())}
    return (_mask_positions(box[0], box[1], added), _mask_positions(box[0], box[1], removed), seen_added,
            light, hazards)


def _contact_delta(before: Dict[UUID, PerceivedContact], after: Dict[UUID, PerceivedContact], initial: bool,
                   ) -> Tuple[Dict[UUID, PerceivedContact], Set[UUID]]:
    """Changed and removed contacts; an unchanged mapping is the same object, an unchanged contact too."""
    if initial:
        return dict(after), set()
    if before is after:
        return {}, set()
    changed = {uuid: contact for uuid, contact in after.items()
               if (previous := before.get(uuid)) is not contact and previous != contact}
    return changed, set(before) - set(after)


def emit_sensory_update_delta(
    owner_uuid: UUID,
    cause_event: Optional[Event],
    before: PublishedSenses,
    after: PublishedSenses,
    reason: SensoryUpdateReason,
    *,
    register_event: bool = True,
    initial: bool = False,
) -> Optional[SensoryUpdateEvent]:
    """Emit a completed sensory event for one observer transition.

    Args:
        owner_uuid: Entity UUID that owns the senses component.
        cause_event: Actual causal event, or None for an independent refresh.
        before: Published perception before the transition.
        after: Published perception after the transition.
        reason: Typed reason for the sensory transition.
        register_event: Whether to register the completed event immediately.
        initial: Publish the complete after-state without an unrecorded seed.

    Returns:
        The completed sensory event when the perception differs, otherwise None.
    """
    timing = action_timing_enabled()
    total_started = time.perf_counter() if timing else 0.0
    started = time.perf_counter() if timing else 0.0
    visible_added, visible_removed, seen_added, light_changed, hazards_changed = _cell_delta(before, after, initial)

    entity_changed, entity_removed = _contact_delta(before.entities, after.entities, initial)
    object_changed, object_removed = _contact_delta(before.objects, after.objects, initial)
    effects_changed = {
        identity: value for identity, value in after.spatial_effects.items()
        if initial or before.spatial_effects.get(identity) != value
    }
    effects_removed = set() if initial else before.spatial_effects.keys() - after.spatial_effects.keys()

    sources_changed = ({} if not initial and before.light_sources is after.light_sources else
        {identity: value for identity, value in after.light_sources.items()
         if initial or before.light_sources.get(identity) is not value and before.light_sources.get(identity) != value})
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
        visible_cells_added=visible_added,
        visible_cells_removed=visible_removed,
        seen_cells_added=seen_added,
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
class ObserverField:
    """One observer's settled sight geometry, owned by the system and keyed by observer uuid.

    The routes and felt cells are kept while their keys (origin, radius and the
    optical or propagation revision) hold; the window and grants describe the
    last published view.
    """

    origin: Position
    window: Box                      # the published window: the frame around origin within the map cells
    selection: Box                   # the cells whose change can reach this view (window and one halo)
    optical_key: Tuple[Position, int, int]
    routes: RouteRows
    felt_keys: Tuple[Tuple[SensesType, Tuple[Position, int, int]], ...]
    felt_rows: Tuple[np.ndarray, ...]
    grants: CellLayer                # bool over the window: cells whose facts this observer is granted
    contact_rows: np.ndarray         # the published contacts as rows: kind, uuid halves, x, y, visual, senses
    known_objects: Tuple[Tuple[UUID, Position], ...]
    light_values: Dict[UUID, Tuple]  # each published emitter's descriptor inputs
    light_inputs: Optional[Tuple]    # what the published emitters were derived from (reused while equal)


NO_CONTACT_ROWS = np.zeros((0, 7), dtype=np.int64)


@dataclass(frozen=True)
class LightSourceRow:
    """One active emitter's observer-independent descriptor values, read once per settlement."""

    identity: UUID
    anchor_uuid: Optional[UUID]
    values: Tuple                    # revision, position, height, appearance, radii, actor_anchored


@dataclass(frozen=True)
class SettlementWorld:
    """The objective inputs every observer of one settlement reads the same (frozen, built once)."""

    exists: CellLayer
    light: CellLayer
    obscurement_owners: Tuple[Tuple[UUID, CellLayer], ...]
    obscurement: CellLayer           # OR of the contributing owners' bits over the cell box
    hazard_owners: Tuple[SpatialConditionOwner | BaseBlock, ...]
    hazard_x: np.ndarray             # the owners' cells, concatenated, with each cell's owner index
    hazard_y: np.ndarray
    hazard_owner: np.ndarray
    light_sources: Tuple[LightSourceRow, ...]
    light_key: Tuple                 # the emitters' descriptor inputs, for an unchanged observer's reuse
    optical_revision: int
    propagation_revision: int


STEALTH_NONE = np.iinfo(np.int64).min
ROW_ENTITY, ROW_OBJECT, ROW_SIDE = 0, 1, 2
UUID_LOW = (1 << 64) - 1


@dataclass(frozen=True)
class ContactTable:
    """The contact targets the views of one settlement can reach, as arrays (frozen, built once).

    A target's observer-independent facts (stealth DC, invisibility, boundary placement) are
    columns; unlisted targets have no row. A cell row is one (occupied cell, target) pair of an
    entity or a center object; a side row is one object on a boundary side with a reached end,
    with the channels open from across that side.
    """

    blocks: Tuple[BaseBlock, ...]
    uuids: Tuple[UUID, ...]
    entity_index: Dict[UUID, int]
    uuid_halves: np.ndarray          # (targets, 2) uint64
    stealth: np.ndarray              # int64 stealth DC, STEALTH_NONE when unhidden
    invisible: np.ndarray            # bool
    cell_x: np.ndarray
    cell_y: np.ndarray
    cell_target: np.ndarray
    cell_kind: np.ndarray            # ROW_ENTITY or ROW_OBJECT
    side_x: np.ndarray               # the owner Tile of the side
    side_y: np.ndarray
    across_x: np.ndarray
    across_y: np.ndarray
    across_tile: np.ndarray          # bool: the cell across holds a Tile
    across_optical: np.ndarray       # bool: the optical channel is open from across
    across_propagation: np.ndarray   # bool: the propagation channel is open from across
    side_target: np.ndarray
    side_position_x: np.ndarray      # the boundary placement position (the contact position)
    side_position_y: np.ndarray


@dataclass(frozen=True)
class ObserverView:
    """One observer's optical and felt cells for one settlement, before contacts and hazards."""

    owner: BaseBlock
    senses: Senses
    origin: Position
    modes: Dict[SensesType, int]
    ordinary_sight: bool
    optical_radius: int
    field: ObserverField
    optical: OpticalView
    exists_frame: np.ndarray         # bool frame of the cells holding a Tile
    seen_frame: np.ndarray           # bool frame of the visible cells
    senses_frame: np.ndarray         # uint8 frame: contact sense bits established on visible cells
    felt_frame: np.ndarray           # uint8 frame: BLINDSIGHT / TREMORSENSE bits on felt cells


@dataclass
class _GroupSettlement:
    """Facts recorded for one observer while a simultaneous group is open."""

    events: List[Event]
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
        self.fields: Dict[UUID, ObserverField] = {}
        self._pending: Dict[UUID, _GroupSettlement] = {}
        self._settling = False
        self._absorbing_light = False
        # Advanced by every recompute: the identity grants of a creature at a
        # cell hold while no observer's published perception changed.
        self.perception_revision = 0
        self._identity_grants: Dict[Tuple[UUID, Tuple[int, int]], FrozenSet[str]] = {}
        self._identity_grants_revision = -1
        # The last settled group's late-completing facts and its observers. A
        # zone change opened in that group completes right after it (its
        # completion reads settled senses); those observers already settled it.
        self._covered_facts: FrozenSet[UUID] = frozenset()
        self._covered_observers: FrozenSet[UUID] = frozenset()

    def attach(self) -> None:
        """Attach the reducer to the existing pre-completion event boundary."""
        EventQueue.add_pre_completion_system(
            self.SYSTEM_NAME,
            self,
            self.EVENT_TYPES,
        )

    def reset(self) -> None:
        """Clear observers and their fields."""
        self.senses_by_observer.clear()
        self.published_observers.clear()
        self.fields.clear()
        self._covered_facts = frozenset()
        self._covered_observers = frozenset()
        self._pending.clear()
        self._settling = False
        self._absorbing_light = False
        self.perception_revision += 1
        self._identity_grants.clear()

    def _recording(self) -> bool:
        """Whether facts are recorded for the open group instead of settled now.

        A settling group no longer records: facts other systems publish while
        settling reduce normally. The group's own pending light is absorbed so
        it merges into the observers' single pass.
        """
        group = EventQueue.open_group()
        return (group is not None and not self._settling
                and (self._absorbing_light or not group.settling))

    def settle_group(self, group: OpenGroup) -> None:
        """Publish the group's pending light, then settle every recorded observer once."""
        root_uuid = group.root_uuid
        self._absorbing_light = True
        try:
            get_map().settle_pending_lights(parent_event=root_uuid)
        finally:
            self._absorbing_light = False
        pending, self._pending = self._pending, {}
        self._covered_facts, self._covered_observers = frozenset(group.completes_after), frozenset(pending)
        # A zone change opened in the group completes right after it and its
        # covered observers skip it then: they settle its cells now, with the
        # group's own facts.
        for lineage in group.completes_after:
            versions = EventQueue.get_events_by_lineage(lineage)
            if not versions:
                continue
            for observer_uuid in self.selected_observers(versions[-1]):
                settlement = pending.get(observer_uuid)
                if settlement is not None:
                    settlement.events.insert(0, versions[-1])
        if not pending:
            return
        root = EventQueue.get_event_by_uuid(root_uuid) if root_uuid is not None else None
        sensory_events: List[SensoryUpdateEvent] = []
        self._settling = True
        try:
            observers = [identity for identity in sorted(pending, key=str)
                         if identity in self.senses_by_observer and BaseBlock.get(identity) is not None]
            for observer_uuid in observers:
                settlement = pending[observer_uuid]
                if settlement.max_distance is not None:
                    self.senses_by_observer[observer_uuid]._perception_max_distance = settlement.max_distance
            settled = self._settle(observers, {identity: pending[identity].events for identity in observers},
                                   cause=root)
            for observer_uuid in observers:
                if not pending[observer_uuid].events:
                    before, _ = settled[observer_uuid]
                    self.publish_observer_refresh(observer_uuid, before)
                    continue
                sensory_event = self._emit_settled(observer_uuid, settled[observer_uuid],
                                                   pending[observer_uuid].events, root)
                if sensory_event is not None:
                    sensory_events.append(sensory_event)
        finally:
            self._settling = False
        if sensory_events:
            EventQueue.register_completion_sequence(sensory_events)
            self.published_observers.update(event.observer_uuid for event in sensory_events)

    def register_observer(self, observer_uuid: UUID, senses: Senses) -> None:
        """Register an observer without independently materializing its world view."""
        self.senses_by_observer[observer_uuid] = senses
        self.fields.pop(observer_uuid, None)

    def unregister_observer(self, observer_uuid: UUID) -> None:
        """Remove an observer and its field."""
        self.senses_by_observer.pop(observer_uuid, None)
        self.published_observers.discard(observer_uuid)
        if self.fields.pop(observer_uuid, None) is not None:
            self.perception_revision += 1

    # ------------------------------------------------------------------ selection

    def observers_granted(self, positions: Iterable[Position]) -> Set[UUID]:
        """Observers whose last view grants any of these cells (wall field, felt cells, volume routes)."""
        cells = list(positions)
        if not cells:
            return set()
        xs, ys = np.array(cells, dtype=np.int64).reshape(-1, 2).T
        granted: Set[UUID] = set()
        for identity, field in self.fields.items():
            grants = field.grants
            i, j = xs - grants.x0, ys - grants.y0
            width, height = grants.values.shape
            inside = (i >= 0) & (i < width) & (j >= 0) & (j < height)
            if inside.any() and grants.values[i[inside], j[inside]].any():
                granted.add(identity)
        return granted

    def _observers_reaching(self, box: Box) -> Set[UUID]:
        """Observers with a settled view whose selection box intersects a change box."""
        return {identity for identity, field in self.fields.items() if boxes_intersect(field.selection, box)}

    def _holders(self, subject_uuid: UUID, *, entity: bool, item: bool) -> Set[UUID]:
        """Observers whose published contacts include the subject."""
        return {identity for identity, senses in self.senses_by_observer.items()
                if entity and subject_uuid in senses.entities or item and subject_uuid in senses.objects}

    def identifying_observers(self, subject_uuid: UUID, position: Tuple[int, int]) -> FrozenSet[str]:
        """String ids of the creature itself and each observer granted its cell holding its contact.

        Every holder is a registered Entity: only entities register as
        observers, and an entity leaves the registry after it unregisters here.
        """
        if self._identity_grants_revision != self.perception_revision:
            self._identity_grants.clear()
            self._identity_grants_revision = self.perception_revision
        grants = self._identity_grants.get((subject_uuid, position))
        if grants is None:
            holders = self.contact_holders(subject_uuid, self.observers_granted((position,)))
            holders.add(subject_uuid)
            grants = self._identity_grants[(subject_uuid, position)] = frozenset(
                str(holder) for holder in holders)
        return grants

    def contact_holders(self, subject_uuid: UUID, observers: AbstractSet[UUID]) -> Set[UUID]:
        """Those observers whose current entity contacts include this subject."""
        return {identity for identity in observers
                if (senses := self.senses_by_observer.get(identity)) is not None and subject_uuid in senses.entities}

    def selected_observers(self, event: Event) -> Set[UUID]:
        """The observers one fact can change: own facts name their observer; every other fact
        reaches the observers whose window box intersects its change box, and the holders of the
        subjects it names."""
        registered = self.senses_by_observer
        if event.event_type is EventType.TURN_START:
            return {event.source_entity_uuid} if event.source_entity_uuid in registered else set()
        grid = get_map()
        if event.event_type in {
            EventType.CONDITION_APPLICATION,
            EventType.CONDITION_REMOVAL,
            EventType.LIFE_STATE_CHANGE,
        }:
            target = event.target_entity_uuid
            if target is not None and target in registered:
                return {target}
            tile = grid.get_tile_by_uuid(target) if target is not None else None
            placement = grid.get_object_placement(target) if target is not None else None
            positions = (tile.position,) if tile is not None else placement.positions if placement is not None else ()
            return self._observers_reaching_cells(positions)
        if isinstance(event, DeathEvent):
            return self._holders(event.entity_uuid, entity=True, item=False)
        if isinstance(event, SpatialEffectChangeEvent):
            return self._observers_reaching_cells(event.get_affected_positions())
        if not isinstance(event, SpatialChangeEvent):
            return set()
        if event.event_type is EventType.SPATIAL_ENTITY_LEFT and event.old_position is not None:
            return set()
        positions = self._candidate_positions(event)
        selected = self._observers_reaching_cells(positions)
        if (event.entity_uuid is not None and event.entity_uuid in registered
                and event.event_type is EventType.SPATIAL_ENTITY_ENTERED):
            selected.add(event.entity_uuid)
        hint = event.senses_hint
        if hint is not None:
            if hint.entity_left is not None:
                selected |= self._holders(hint.entity_left[0], entity=True, item=False)
            if hint.entity_died is not None:
                selected |= self._holders(hint.entity_died[0], entity=True, item=False)
            if hint.object_removed is not None:
                selected |= self._holders(hint.object_removed[0], entity=False, item=True)
            if hint.perceivability_entity is not None:
                selected |= self._holders(hint.perceivability_entity, entity=True, item=True)
            if hint.requires_paths:
                selected |= {identity for identity, senses in registered.items() if identity in self.fields
                             and any(position in senses.paths or position in senses.safe_paths
                                     for position in positions)}
        return {identity for identity in selected if identity in registered}

    def _observers_reaching_cells(self, positions: Iterable[Position]) -> Set[UUID]:
        cells = list(positions)
        if not cells:
            return set()
        xs, ys = [cell[0] for cell in cells], [cell[1] for cell in cells]
        return self._observers_reaching((min(xs), min(ys), max(xs), max(ys)))

    # ------------------------------------------------------------------ settlement

    def __call__(self, event: Event) -> None:
        """Reduce the selected observers before the causal event completes."""
        record_action_count("sensory.reducer_call", 1)
        if self._recording():
            for observer_uuid in self.selected_observers(event):
                self._pending.setdefault(observer_uuid, _GroupSettlement([])).events.append(event)
            return
        deferred: Set[UUID] = set()
        if event.lineage_uuid in self._covered_facts:
            deferred = set(self._covered_observers)
        if event.event_type in (EventType.SPATIAL_LIGHT_CHANGED, EventType.SPATIAL_LIGHT_SOURCES_CHANGED):
            parent = EventQueue.get_event_by_uuid(event.parent_event) if event.parent_event is not None else None
            if isinstance(parent, SpatialChangeEvent) and parent.senses_hint is not None and parent.senses_hint.requires_light_recompute:
                # The geometry parent observes after every affected emitter has
                # settled. Its observers must not see partial source recomputes.
                deferred = set(self.selected_observers(parent))
        observers = [identity for identity in sorted(self.selected_observers(event), key=str)
                     if identity not in deferred and identity in self.senses_by_observer]
        if not observers:
            return
        settled = self._settle(observers, {identity: [event] for identity in observers}, cause=event)
        sensory_events = [sensory_event for observer_uuid in observers
                          if (sensory_event := self._emit_settled(observer_uuid, settled[observer_uuid], [event],
                                                                  event)) is not None]
        if sensory_events:
            EventQueue.register_completion_sequence(sensory_events)
            self.published_observers.update(event.observer_uuid for event in sensory_events)

    def _settle(self, observers: Sequence[UUID], events: Mapping[UUID, Sequence[Event]], *,
                cause: Optional[Event]) -> Dict[UUID, Tuple[PublishedSenses, Dict[UUID, Optional[PerceivedSpatialEffect]]]]:
        """Recompute every observer of one settlement; returns each one's prior published state
        and the prior values of the fixtures it re-observed."""
        del cause
        befores = {identity: published_senses(self.senses_by_observer[identity]) for identity in observers}
        affected = {identity: self._affected_cells(events[identity]) for identity in observers}
        touched = self._recompute(observers, affected)
        return {identity: (befores[identity], touched[identity]) for identity in observers}

    def _emit_settled(self, observer_uuid: UUID,
                      settled: Tuple[PublishedSenses, Dict[UUID, Optional[PerceivedSpatialEffect]]],
                      events: Sequence[Event], cause: Optional[Event]) -> Optional[SensoryUpdateEvent]:
        """Refresh the observer's light sources and emit the difference of its published perception."""
        senses = self.senses_by_observer[observer_uuid]
        initial = observer_uuid not in self.published_observers
        before, effect_before = settled
        after = published_senses(senses)
        # Only the fixtures this settlement re-observed can change (an initial update carries all).
        before = _replace_effects(before, {identity: value for identity, value in effect_before.items()
                                           if value is not None})
        if not initial:
            after = _replace_effects(after, {identity: senses.spatial_effects[identity]
                                             for identity in set(effect_before) if identity in senses.spatial_effects})
        projection_changed = any((
            before.position != after.position,
            not _same_cells(before.cells.visible, after.cells.visible),
            not _same_cells(before.seen, after.seen),
            before.entities is not after.entities and before.entities != after.entities,
            before.objects is not after.objects and before.objects != after.objects,
            before.passive_perception != after.passive_perception,
            not _same_cells(before.cells.hazard, after.cells.hazard),
            before.spatial_effects != after.spatial_effects,
        ))
        visible_topology_changed = any(self._changes_visible_topology(event, senses) for event in events)
        if projection_changed or visible_topology_changed:
            senses._paths_dirty = True
            after = _replace_paths_dirty(after)
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

    def recompute_observer(self, observer_uuid: UUID, *, max_distance: Optional[int] = None) -> None:
        """Replace one observer's published cells and contacts from the current world."""
        senses = self.senses_by_observer.get(observer_uuid)
        if senses is None or BaseBlock.get(observer_uuid) is None:
            return
        if self._recording():
            # Inside a simultaneous group perception reads see pre-group
            # perception; the observer settles once when the group closes.
            settlement = self._pending.setdefault(observer_uuid, _GroupSettlement([]))
            settlement.full = True
            if max_distance is not None:
                settlement.max_distance = max_distance
            return
        if max_distance is not None:
            senses._perception_max_distance = max_distance
        self._recompute([observer_uuid], {observer_uuid: None})

    def publish_observer_refresh(
        self, observer_uuid: UUID, before: PublishedSenses,
    ) -> Optional[SensoryUpdateEvent]:
        """Record an independent explicit refresh after existing cache updates."""
        senses = self.senses_by_observer.get(observer_uuid)
        if senses is None:
            return None
        event = emit_sensory_update_delta(
            observer_uuid, None, before, published_senses(senses),
            SensoryUpdateReason.UNKNOWN,
            initial=observer_uuid not in self.published_observers,
        )
        if event is not None:
            self.published_observers.add(observer_uuid)
        return event

    def _affected_cells(self, events: Sequence[Event]) -> Optional[Set[Position]]:
        """Cells whose fixtures and hazards the facts name; None means every visible cell."""
        positions: Set[Position] = set()
        for event in events:
            event_positions = self._hazard_positions_for(event)
            if event_positions is None:
                return None
            positions |= event_positions
        return positions

    # ------------------------------------------------------------------ the recompute

    def _world(self) -> SettlementWorld:
        grid = get_map()
        exists = grid.cell_exists
        owners = grid.obscurement_layers()
        combined = np.zeros(exists.values.shape, dtype=np.uint8)
        if exists.values.size:
            for _, layer in owners:
                combined |= embed(layer, exists.box, np.dtype(np.uint8))
        hazard_owners, hazard_x, hazard_y, hazard_owner = grid.hazard_owners()
        light_rows = grid.light_source_rows()
        return SettlementWorld(exists, grid.cell_light, owners, CellLayer(exists.x0, exists.y0, combined),
                               hazard_owners, hazard_x, hazard_y, hazard_owner,
                               tuple(LightSourceRow(identity, anchor, values) for identity, anchor, values in light_rows),
                               tuple(light_rows), grid.optical_revision, grid.propagation_revision)

    def _recompute(self, observers: Sequence[UUID],
                   affected: Mapping[UUID, Optional[Set[Position]]]) -> Dict[UUID, Dict[UUID, Optional[PerceivedSpatialEffect]]]:
        """Recompute the observers' views with one settlement world and one target table."""
        diagnostic = action_timing_enabled()
        started = time.perf_counter() if diagnostic else 0.0
        world = self._world()
        if diagnostic:
            record_action_timing("sensory.settlement.world_ms", started)
        views = []
        for observer_uuid in observers:
            record_action_count("sensory.full_recompute", 1)
            started = time.perf_counter() if diagnostic else 0.0
            views.append(self._view(observer_uuid, world))
            if diagnostic:
                record_action_timing("sensory.recompute.view_ms", started)
        started = time.perf_counter() if diagnostic else 0.0
        table = self._contact_table(views, world)
        if diagnostic:
            record_action_timing("sensory.settlement.contact_table_ms", started)
        touched = {}
        for view in views:
            touched[view.owner.uuid] = self._publish(view, world, table, affected[view.owner.uuid])
        self.perception_revision += 1
        return touched

    def _view(self, observer_uuid: UUID, world: SettlementWorld) -> ObserverView:
        """Optical and felt cells of one observer, as arrays."""
        senses = self.senses_by_observer[observer_uuid]
        owner = BaseBlock.get(observer_uuid)
        assert owner is not None
        grid = get_map()
        max_distance = senses._perception_max_distance
        origin = owner.get_position()
        assert origin is not None
        modes = {mode.sense_type: mode.range_feet for mode in senses.get_sense_modes()}
        visual_access = senses.visual_access.normalized_score > 0
        ordinary_sight = owner.has_ordinary_visual_sight()
        optical_radius = max_distance if ordinary_sight else 0
        for sense_type in (SensesType.DARKVISION, SensesType.DEVILS_SIGHT, SensesType.TRUESIGHT):
            sense_range = modes.get(sense_type)
            if sense_range is not None:
                optical_radius = max(optical_radius, max_distance if sense_range == 0 else (sense_range + 4) // 5)
        previous = self.fields.get(observer_uuid)
        optical_key = (origin, optical_radius if visual_access else 0, world.optical_revision)
        if previous is not None and previous.optical_key == optical_key:
            routes = previous.routes
        else:
            fov = grid.compute_fov(origin, optical_radius) if visual_access and optical_radius > 0 else []
            routes = route_rows(frame_rows(np.array(fov, dtype=np.int64).reshape(-1, 2), origin))
        exists = frame_of(world.exists, origin)
        optical = optical_view(routes, modes, ordinary_sight, exists, frame_of(world.obscurement, origin),
                               frame_of(world.light, origin))
        reach = optical_radius if visual_access else 0
        felt_keys: List[Tuple[SensesType, Tuple[Position, int, int]]] = []
        felt_rows: List[np.ndarray] = []
        felt_frame = np.zeros(OFF + 1, dtype=np.uint8)
        previous_felt = dict(zip(previous.felt_keys, previous.felt_rows)) if previous is not None else {}
        for sense_type, bit in NONVISUAL_SENSES:
            sense_range = modes.get(sense_type)
            if sense_range is None:
                continue
            radius = max_distance if sense_range == 0 else (sense_range + 4) // 5
            reach = max(reach, radius)
            key = (sense_type, (origin, radius, world.propagation_revision))
            rows = previous_felt.get(key)
            if rows is None:
                rows = frame_rows(np.array(grid.compute_propagation_fov(origin, radius), dtype=np.int64).reshape(-1, 2),
                                  origin)
            felt_keys.append(key)
            felt_rows.append(rows)
            felt_frame[rows] |= bit
        if reach > R:
            raise ValueError(f"perception reach {reach} exceeds the route table radius {R}")
        seen_frame = np.zeros(OFF + 1, dtype=bool)
        seen_frame[optical.rows] = True
        senses_frame = np.zeros(OFF + 1, dtype=np.uint8)
        senses_frame[optical.rows] = ELIGIBLE_SENSE_BITS[optical.eligibility]
        cell_box = world.exists.box
        window = (max(origin[0] - reach, cell_box[0]), max(origin[1] - reach, cell_box[1]),
                  min(origin[0] + reach, cell_box[2]), min(origin[1] + reach, cell_box[3]))
        selection = (origin[0] - reach - 1, origin[1] - reach - 1, origin[0] + reach + 1, origin[1] + reach + 1)
        field = ObserverField(origin, window, selection, optical_key, routes, tuple(felt_keys), tuple(felt_rows),
                              CellLayer(window[0], window[1], np.zeros((0, 0), dtype=bool)),
                              previous.contact_rows if previous is not None else NO_CONTACT_ROWS,
                              previous.known_objects if previous is not None else (),
                              previous.light_values if previous is not None else {},
                              previous.light_inputs if previous is not None else None)
        return ObserverView(owner, senses, origin, modes, ordinary_sight, optical_radius if visual_access else 0,
                            field, optical, exists, seen_frame, senses_frame, felt_frame)

    def _contact_table(self, views: Sequence[ObserverView], world: SettlementWorld) -> ContactTable:
        """Every target some view of this settlement can reach, and its observer-independent facts."""
        grid = get_map()
        box = world.exists.box
        reached = np.zeros(world.exists.values.shape, dtype=bool)
        for view in views:
            frame = view.seen_frame | (view.felt_frame != 0)
            reached |= embed(CellLayer(view.origin[0] - R, view.origin[1] - R, frame[:-1].reshape(SIDE, SIDE)),
                             box, np.dtype(bool))
        width, height = reached.shape
        blocks: List[BaseBlock] = []
        uuids: List[UUID] = []
        stealth: List[int] = []
        invisible: List[bool] = []
        index: Dict[Tuple[UUID, bool], Optional[int]] = {}
        entity_index: Dict[UUID, int] = {}

        def target(identity: UUID, as_entity: bool) -> Optional[int]:
            key = (identity, as_entity)
            if key in index:
                return index[key]
            block = BaseBlock.get(identity)
            listed = block is not None and (block.appears_in_entity_contacts() if as_entity
                                            else block.should_include_in_senses_objects())
            if block is None or not listed:
                index[key] = None
                return None
            index[key] = len(blocks)
            if as_entity:
                entity_index[identity] = len(blocks)
            blocks.append(block)
            uuids.append(identity)
            stealth.append(STEALTH_NONE if block.stealth_dc is None else block.stealth_dc)
            invisible.append(block.is_invisible)
            return index[key]

        cells: List[Tuple[int, int, int, int]] = []
        if world.exists.values.size:
            for (x, y), (entity_ids, object_ids) in grid.contact_cells_in_box(box):
                if not reached[x - box[0], y - box[1]]:
                    continue
                for identity in entity_ids:
                    if (row := target(identity, True)) is not None:
                        cells.append((x, y, row, ROW_ENTITY))
                for identity in object_ids:
                    if (row := target(identity, False)) is not None:
                        cells.append((x, y, row, ROW_OBJECT))
        sides: List[Tuple[int, ...]] = []
        if world.exists.values.size:
            exists = world.exists.values
            for (x, y), direction, side_objects in grid.boundary_sides_in_box(box):
                dx, dy = DELTAS[direction]
                i, j = x - box[0], y - box[1]
                across_inside = 0 <= i + dx < width and 0 <= j + dy < height
                if not (reached[i, j] or across_inside and reached[i + dx, j + dy]):
                    continue
                across_tile = across_inside and bool(exists[i + dx, j + dy])
                channels = self._open_channels(grid, (x, y), direction) if across_tile else ()
                for identity in side_objects:
                    row = target(identity, False)
                    placement = grid.get_object_placement(identity) if row is not None else None
                    if row is None or placement is None or placement.boundary_direction is None:
                        continue
                    sides.append((x, y, x + dx, y + dy, across_tile, WorldEdgeChannel.OPTICAL in channels,
                                  WorldEdgeChannel.PROPAGATION in channels, row, *placement.position))
        cell_array = np.array(cells, dtype=np.int64).reshape(-1, 4)
        side_array = np.array(sides, dtype=np.int64).reshape(-1, 10)
        return ContactTable(
            tuple(blocks), tuple(uuids), entity_index,
            np.array([(identity.int >> 64, identity.int & UUID_LOW) for identity in uuids],
                     dtype=np.uint64).reshape(-1, 2),
            np.array(stealth, dtype=np.int64), np.array(invisible, dtype=bool),
            cell_array[:, 0], cell_array[:, 1], cell_array[:, 2], cell_array[:, 3],
            side_array[:, 0], side_array[:, 1], side_array[:, 2], side_array[:, 3], side_array[:, 4] != 0,
            side_array[:, 5] != 0, side_array[:, 6] != 0, side_array[:, 7], side_array[:, 8], side_array[:, 9])

    def _publish(self, view: ObserverView, world: SettlementWorld, table: ContactTable,
                 affected: Optional[Set[Position]]) -> Dict[UUID, Optional[PerceivedSpatialEffect]]:
        """Contacts, hazards, volume sight and fixtures of one view; publish them on its Senses."""
        diagnostic = action_timing_enabled()
        started = time.perf_counter() if diagnostic else 0.0
        grid = get_map()
        owner, senses, origin = view.owner, view.senses, view.origin
        observer_uuid = owner.uuid
        passive = owner.get_passive_perception()
        if diagnostic:
            record_action_timing("sensory.recompute.passive_ms", started)
            started = time.perf_counter()
        entities, objects, contact_rows, known = self._contacts(view, table, passive)
        if diagnostic:
            record_action_timing("sensory.recompute.contacts_ms", started)
            started = time.perf_counter()
        window = view.field.window
        # Each hazard owner states its rule once per observer; its cells are OR-ed in one scatter.
        hazard_frame = np.zeros(OFF + 1, dtype=bool)
        cell_rows = frame_index(world.hazard_x, world.hazard_y, origin)
        reaching = np.unique(world.hazard_owner[(cell_rows != OFF) & view.seen_frame[cell_rows]])
        if reaching.size:
            hazardous = np.zeros(len(world.hazard_owners), dtype=bool)
            hazardous[reaching] = [world.hazard_owners[owner].is_hazardous_for(observer_uuid)
                                   for owner in reaching.tolist()]
            hazard_frame[cell_rows[hazardous[world.hazard_owner]]] = True
        hazard_frame[OFF] = False
        hazard_frame &= view.seen_frame
        if diagnostic:
            record_action_timing("sensory.recompute.hazards_ms", started)
            started = time.perf_counter()
        light_frame = np.zeros(OFF + 1, dtype=np.uint8)
        light_frame[view.optical.rows] = view.optical.light
        eligibility_frame = np.zeros(OFF + 1, dtype=np.uint8)
        eligibility_frame[view.optical.rows] = view.optical.eligibility
        cells = PerceivedCells(
            CellLayer(window[0], window[1], window_of(view.seen_frame, origin, window)),
            CellLayer(window[0], window[1], window_of(light_frame, origin, window)),
            CellLayer(window[0], window[1], window_of(eligibility_frame, origin, window)),
            CellLayer(window[0], window[1], window_of(hazard_frame, origin, window)))
        before_visible = senses.cells.visible
        seen = senses.seen
        seen_box = window if not seen.values.size else union_box(seen.box, window)
        senses.seen = CellLayer(seen_box[0], seen_box[1], embed(seen, seen_box, np.dtype(bool))
                                | embed(cells.visible, seen_box, np.dtype(bool)))
        # Perception is committed before fixtures are observed: an observation reads the new contacts.
        senses.position = origin
        senses.cells = cells
        senses.entities = entities
        senses.objects = objects
        senses._last_passive_perception = passive
        senses._last_sense_modes_hash = senses.compute_sense_modes_hash()
        senses._last_visual_access = senses.visual_access.normalized_score
        volumes, upper, volume_grants = self._volume_sight(view, world)
        if diagnostic:
            record_action_timing("sensory.recompute.volume_geometry_ms", started)
            started = time.perf_counter()
        effect_before = self._refresh_spatial_effects(observer_uuid, senses, cells.visible, before_visible,
                                                      affected, volumes, upper)
        if diagnostic:
            record_action_timing("sensory.recompute.spatial_effects_ms", started)
            started = time.perf_counter()
        grants = np.zeros(OFF + 1, dtype=bool)
        grants[view.field.routes.rows] = True
        grants |= view.felt_frame != 0
        if volume_grants:
            cells_array = np.array(sorted(volume_grants), dtype=np.int64)
            grants[frame_index(cells_array[:, 0], cells_array[:, 1], origin)] = True
        grants[OFF] = False
        if diagnostic:
            record_action_timing("sensory.recompute.grants_ms", started)
            started = time.perf_counter()
        light_inputs, light_values = self._refresh_light_sources(observer_uuid, senses, world, view.field)
        if diagnostic:
            record_action_timing("sensory.recompute.light_sources_ms", started)
            started = time.perf_counter()
        self.fields[observer_uuid] = ObserverField(
            view.field.origin, window, view.field.selection, view.field.optical_key, view.field.routes,
            view.field.felt_keys, view.field.felt_rows, CellLayer(window[0], window[1], window_of(grants, origin, window)),
            contact_rows, known, light_values, light_inputs)
        if diagnostic:
            record_action_timing("sensory.recompute.publish_ms", started)
        return effect_before

    def _contacts(self, view: ObserverView, table: ContactTable, passive: int,
                  ) -> Tuple[Dict[UUID, PerceivedContact], Dict[UUID, PerceivedContact], np.ndarray,
                             Tuple[Tuple[UUID, Position], ...]]:
        """Entity and object contacts as rows over the settlement's table: the per-target rules
        (hiding, invisibility, boundary evidence) are masks; Python runs per observable target and
        per contact only when the observer's rows changed."""
        grid = get_map()
        owner, senses, origin, modes = view.owner, view.senses, view.origin, view.modes
        observer_uuid = owner.uuid
        seen_frame, felt_frame, senses_frame = view.seen_frame, view.felt_frame, view.senses_frame

        def reveals(frame_rows: np.ndarray) -> np.ndarray:
            distance = FRAME_DISTANCE_FEET[frame_rows]
            return reach_mask(modes, SensesType.TRUESIGHT, distance) | reach_mask(modes, SensesType.SEE_INVISIBLE, distance)

        # Cell rows: the cell's own evidence.
        index = frame_index(table.cell_x, table.cell_y, origin)
        cell_target = table.cell_target
        cell_visual = seen_frame[index] & (reveals(index) | ~table.invisible[cell_target])
        cell_mask = np.where(cell_visual, senses_frame[index], 0) | felt_frame[index]
        cell_keep = (table.stealth[cell_target] < passive) & (cell_visual | (cell_mask != 0))
        own_index = table.entity_index.get(observer_uuid)
        if own_index is not None:
            cell_keep &= ~((table.cell_kind == ROW_ENTITY) & (cell_target == own_index))
        # Side rows: a side is reached from its owner Tile, and from across unless the far Tile's
        # exit layer blocks the channel.
        own = frame_index(table.side_x, table.side_y, origin)
        across = frame_index(table.across_x, table.across_y, origin)
        side_target = table.side_target
        own_optical = seen_frame[own]
        own_felt = felt_frame[own]
        across_optical = seen_frame[across] & table.across_tile & table.across_optical
        across_felt = felt_frame[across]
        across_propagation = (across_felt != 0) & table.across_tile & table.across_propagation
        hidden = table.invisible[side_target]
        visual_own = own_optical & (reveals(own) | ~hidden)
        visual_across = across_optical & (reveals(across) | ~hidden)
        side_visual = visual_own | visual_across
        side_mask = (np.where(visual_own, senses_frame[own], 0) | np.where(visual_across, senses_frame[across], 0)
                     | np.where(own_optical | (own_felt != 0), own_felt, 0)
                     | np.where(across_optical | across_propagation, across_felt, 0))
        side_keep = (table.stealth[side_target] < passive) & (side_visual | (side_mask != 0))
        # Observability is the target's own rule, asked once per kept target.
        kept_targets = np.unique(np.concatenate((cell_target[cell_keep], side_target[side_keep])))
        hidden_targets = [target for target in kept_targets.tolist()
                          if not table.blocks[target].is_observable_to(observer_uuid)]
        if hidden_targets:
            cell_keep &= ~np.isin(cell_target, hidden_targets)
            side_keep &= ~np.isin(side_target, hidden_targets)
        order = np.flatnonzero(cell_keep)
        order = order[np.lexsort((table.cell_y[order], table.cell_x[order]))]
        sides = np.flatnonzero(side_keep)
        halves = table.uuid_halves.astype(np.int64)
        rows = np.concatenate((
            np.column_stack((table.cell_kind[order], halves[cell_target[order]], table.cell_x[order],
                             table.cell_y[order], cell_visual[order], cell_mask[order])),
            np.column_stack((np.full(sides.size, ROW_SIDE), halves[side_target[sides]],
                             table.side_position_x[sides], table.side_position_y[sides], side_visual[sides],
                             side_mask[sides])))).astype(np.int64).reshape(-1, 7)
        # Explicit construction knowledge is not visual sight or truesight.
        # Only the declaring creator receives this otherwise invisible contact.
        known = tuple((identity, placement.position) for identity in grid.get_known_object_candidates(observer_uuid)
                      if (subject := BaseBlock.get(identity)) is not None
                      and (placement := grid.get_object_placement(identity)) is not None
                      and subject.is_object_known_to(observer_uuid))
        previous_rows = view.field.contact_rows
        if previous_rows.shape == rows.shape and np.array_equal(previous_rows, rows) \
                and view.field.known_objects == known:
            return senses.entities, senses.objects, rows, known
        previous_entities, previous_objects = senses.entities, senses.objects

        def contact(position: Position, visual: bool, mask: int, previous: Optional[PerceivedContact],
                    ) -> PerceivedContact:
            special = SENSES_BY_VALUE[mask]
            if (type(previous) is PerceivedContact and previous.position == position
                    and previous.visual == visual and previous.special_senses == special):
                return previous
            return PerceivedContact(position=position, visual=visual, special_senses=special)

        if view.field.known_objects == known and previous_rows.size:
            # Only the targets whose rows changed are resolved again; the others keep their contact.
            new_keys, old_keys = _target_keys(rows), _target_keys(previous_rows)
            new_rows, old_rows = _row_values(rows), _row_values(previous_rows)
            touched = np.unique(np.concatenate((new_keys[~np.isin(new_rows, old_rows)],
                                                old_keys[~np.isin(old_rows, new_rows)])))
            entities, objects = dict(previous_entities), dict(previous_objects)
            for group, high, low in _key_columns(touched):
                (entities if group == 0 else objects).pop(UUID(int=(high << 64) | low), None)
            selected = np.isin(new_keys, touched)
            cell_selected, side_selected = selected[:order.size], selected[order.size:]
            known_touched = bool(known)
        else:
            entities, objects = {}, {}
            cell_selected = np.ones(order.size, dtype=bool)
            side_selected = np.ones(sides.size, dtype=bool)
            known_touched = True
        cells = order[cell_selected]
        for kind, target, x, y, visual, mask in zip(
                table.cell_kind[cells].tolist(), cell_target[cells].tolist(), table.cell_x[cells].tolist(),
                table.cell_y[cells].tolist(), cell_visual[cells].tolist(), cell_mask[cells].tolist()):
            identity = table.uuids[target]
            if kind == ROW_ENTITY:
                entities[identity] = contact((x, y), visual, mask, previous_entities.get(identity))
                continue
            found = objects.get(identity)
            if found is None:
                objects[identity] = contact((x, y), visual, mask, previous_objects.get(identity))
                continue
            # A multi-cell object: the best evidence, the union of its senses in enum order.
            chosen_position = min(((not found.visual, _distance_feet(origin, found.position), found.position),
                                   (not visual, _distance_feet(origin, (x, y)), (x, y))))[2]
            established = 0
            for sense in found.special_senses:
                established |= SENSE_BITS[sense]
            objects[identity] = PerceivedContact(position=chosen_position, visual=found.visual or visual,
                                                 special_senses=SENSES_BY_ENUM[established | mask])
        if known_touched:
            for identity, position in known:
                if identity not in objects:
                    objects[identity] = PerceivedContact(position=position, visual=False, special_senses=())
        side_rows = sides[side_selected]
        for target, x, y, visual, mask in sorted(zip(
                side_target[side_rows].tolist(), table.side_position_x[side_rows].tolist(),
                table.side_position_y[side_rows].tolist(), side_visual[side_rows].tolist(),
                side_mask[side_rows].tolist()), key=lambda row: str(table.uuids[row[0]])):
            identity = table.uuids[target]
            objects[identity] = contact((x, y), visual, mask, previous_objects.get(identity))
        return entities, objects, rows, known

    @staticmethod
    def _open_channels(grid, position: Position, direction: CardinalDirection) -> Tuple[WorldEdgeChannel, ...]:
        """Channels on which a side is reached from across it: those the far Tile's exit layer does not block."""
        dx, dy = DELTAS[direction]
        blocked: Set[WorldEdgeChannel] = set()
        for identity in grid.boundary_side_objects((position[0] + dx, position[1] + dy), OPPOSITE[direction]):
            block = BaseBlock.get(identity)
            structure = block.get_boundary_structure() if block is not None else None
            if structure is not None:
                blocked.update(structure.blocked_channels)
        return tuple(channel for channel in CHANNELS if channel not in blocked)

    def _volume_sight(self, view: ObserverView, world: SettlementWorld,
                      ) -> Tuple[Dict[UUID, FrozenSet[Position]], Dict[UUID, Tuple[VolumeSurfaceSight, ...]], Set[Position]]:
        """Each seen volume's visible geometry, its upper surfaces and the routes it grants.

        First-surface sight establishes a volume. Its geometry may be viewed from
        another camera, but physical walls and every other obscuring owner still
        clip it; ground and actor sight stay the optical view's.
        """
        optical = view.optical
        if not optical.surface_rows.size:
            return {}, {}, set()
        grid = get_map()
        origin, modes = view.origin, view.modes
        surface_set = optical.surface_rows
        light = frame_of(world.light, origin)
        exists = frame_of(world.exists, origin)
        candidates = np.zeros(OFF + 1, dtype=bool)
        candidates[view.field.routes.rows] = True
        cells, lengths = supercover_route_table()
        frame = frame_box(origin)
        owner_frames = {owner_uuid: frame_of(layer, origin) for owner_uuid, layer in world.obscurement_owners
                        if boxes_intersect(layer.box, frame)}
        sights: Dict[UUID, FrozenSet[Position]] = {}
        upper: Dict[UUID, Tuple[VolumeSurfaceSight, ...]] = {}
        providers_of: Dict[UUID, Dict[UUID, FrozenSet[Position]]] = {}
        grants: Set[Position] = set()
        owners = [owner_uuid for owner_uuid, own in owner_frames.items() if own[surface_set].any()
                  and grid.get_spatial_condition(owner_uuid) is not None]
        for owner_uuid in owners:
            condition = grid.get_spatial_condition(owner_uuid)
            assert condition is not None
            own = owner_frames[owner_uuid]
            others = np.zeros(OFF + 1, dtype=np.uint8)
            for other_uuid, other in owner_frames.items():
                if other_uuid != owner_uuid:
                    others |= other
            at_entrance = own[surface_set] != 0
            entrance_light = optical.surface_light_rows[at_entrance]
            entrance_eligibility = optical.surface_eligibility[at_entrance]
            established = bool(((entrance_eligibility & SPECIAL) != 0).any() or (
                ((entrance_eligibility & PLAIN) != 0) & exists[entrance_light]
                & (light[entrance_light] > LightLevel.DARKNESS.value)).any())
            footprint = grid.condition_footprint(owner_uuid)
            assert footprint is not None
            occupied_x, occupied_y = np.nonzero(footprint.values)
            occupied_x, occupied_y = occupied_x + footprint.x0, occupied_y + footprint.y0
            suppressed = [cell for suppression in condition.spatial_suppressions for cell in suppression.positions]
            if suppressed:
                # Geometry is the footprint and the suppressed cells, sorted (x, y).
                everything = np.unique(np.concatenate((np.column_stack((occupied_x, occupied_y)),
                                                       np.array(suppressed, dtype=np.int64).reshape(-1, 2))), axis=0)
                xs, ys = everything[:, 0], everything[:, 1]
                in_footprint = _gather(footprint.values, footprint.box, everything)
            else:
                xs, ys = occupied_x, occupied_y
                in_footprint = np.ones(occupied_x.size, dtype=bool)
            observation = condition.get_spatial_observation(set(), observer_uuid=view.owner.uuid, discovered=True)
            sphere = observation.area_geometry if observation is not None else None
            base = observation.anchor_elevation_steps if observation is not None else None
            rows = frame_index(xs, ys, origin)
            in_view = candidates[rows]
            surfaces: Dict[Position, VolumeSurfaceSight] = {}
            dependencies: Set[Position] = set()
            if isinstance(sphere, SpherePresentationGeometry) and base is not None:
                radius_squared = view.optical_radius ** 2
                near = ~in_view & in_footprint & ((xs - origin[0]) ** 2 + (ys - origin[1]) ** 2 <= radius_squared)
                for position in zip(xs[near].tolist(), ys[near].tolist()):
                    # Tested routes are granted even when rejected: a remote door
                    # closing OR reopening must update this surface sight.
                    dependencies.update((cell[0] + dx, cell[1] + dy) for cell in supercover_line(origin, position)
                                        for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1))
                                        if grid.get_tile(cell[0] + dx, cell[1] + dy) is not None)
                    planes = grid.upper_volume_sight_planes(origin, position)
                    if not planes:
                        continue
                    # Sphere top in native elevation steps. Cell-corner maximum
                    # keeps a partly exposed cell without granting its lower half.
                    dx = max(0., abs(position[0] - sphere.center[0]) - .5)
                    dy = max(0., abs(position[1] - sphere.center[1]) - .5)
                    top = base + math.sqrt(max(0., (sphere.radius_feet / 5) ** 2 - dx * dx - dy * dy))
                    if all(max(a * x + b * y + c for a, b, c in planes) >= top
                           for x, y in ((position[0] + cx, position[1] + cy) for cx in (-.5, .5) for cy in (-.5, .5))):
                        continue
                    surfaces[position] = VolumeSurfaceSight(position=position, lower_height_planes=planes)
            tested = in_view.copy()
            if surfaces:
                tested |= _cells_mask(surfaces, (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())))[
                    xs - int(xs.min()), ys - int(ys.min())]
            visible: FrozenSet[Position] = frozenset()
            upper_rows: List[VolumeSurfaceSight] = []
            if tested.any() and established:
                picked = rows[tested]
                picked_x, picked_y = xs[tested], ys[tested]
                routes = cells[picked, :int(lengths[picked].max())]
                codes = own[routes]
                inside = codes != 0
                enters = inside.any(axis=1)
                entry = inside.argmax(axis=1)
                line = np.arange(picked.size)
                dark = (codes[line, entry] & MAGICAL_DARKNESS_BIT) != 0
                light_rows = routes[line, np.where(dark & (entry > 0), entry - 1, entry)]
                crossed = np.bitwise_or.reduce(others[routes], axis=1)
                eligibility = range_bits(modes, view.ordinary_sight, FRAME_DISTANCE_FEET[picked]) & SURVIVORS[crossed]
                shown = enters & exists[light_rows] & (eligibility != 0) & (
                    ((eligibility & SPECIAL) != 0)
                    | (((eligibility & PLAIN) != 0) & (light[light_rows] > LightLevel.DARKNESS.value)))
                shown_cells = list(zip(picked_x[shown].tolist(), picked_y[shown].tolist()))
                if surfaces:
                    upper_rows = [surfaces[cell] for cell in shown_cells if cell in surfaces]
                    shown_cells = [cell for cell in shown_cells if cell not in surfaces]
                visible = frozenset(shown_cells)
            if established:
                grants |= dependencies
            sights[owner_uuid] = visible
            if upper_rows:
                upper[owner_uuid] = tuple(upper_rows)
            providers_of[owner_uuid] = {row.provider_uuid: frozenset(row.positions)
                                        for row in condition.spatial_suppressions}
        touched = set(owners)
        for owner_uuid in owners:
            touched.update(providers_of[owner_uuid])
        volumes: Dict[UUID, FrozenSet[Position]] = {}
        for identity in touched:
            visible = sights.get(identity, frozenset())
            if identity in view.senses.spatial_effects and grid.get_spatial_condition(identity) is not None:
                occupied = grid.get_spatial_condition_positions(identity)
                for owner_uuid in owners:
                    provided = providers_of[owner_uuid].get(identity)
                    if provided is not None:
                        visible = visible | (sights[owner_uuid] & provided & occupied)
            if visible:
                volumes[identity] = frozenset(visible)
        return volumes, upper, grants

    def _refresh_spatial_effects(
        self, observer_uuid: UUID, senses: Senses, visible: CellLayer, before_visible: CellLayer,
        affected: Optional[Set[Position]], volumes: Mapping[UUID, FrozenSet[Position]],
        upper: Mapping[UUID, Tuple[VolumeSurfaceSight, ...]],
    ) -> Dict[UUID, Optional[PerceivedSpatialEffect]]:
        """Re-observe the fixtures on newly visible and affected cells; hidden parts keep their last
        observation. Returns the prior value of every fixture touched."""
        grid = get_map()
        box = (visible.box if not before_visible.values.size else before_visible.box if not visible.values.size
               else union_box(visible.box, before_visible.box))
        now = embed(visible, box, np.dtype(bool))
        before = embed(before_visible, box, np.dtype(bool))
        if affected is None:
            reobserved = now.copy()
        else:
            reobserved = now & ~before
            if affected:
                marks = np.zeros(now.shape, dtype=bool)
                cells = np.array(list(affected), dtype=np.int64).reshape(-1, 2)
                i, j = cells[:, 0] - box[0], cells[:, 1] - box[1]
                inside = (i >= 0) & (i < now.shape[0]) & (j >= 0) & (j < now.shape[1])
                marks[i[inside], j[inside]] = True
                reobserved |= now & marks
        changed = reobserved | (before & ~now)

        def at(mask: np.ndarray, position: Position) -> bool:
            i, j = position[0] - box[0], position[1] - box[1]
            return 0 <= i < mask.shape[0] and 0 <= j < mask.shape[1] and bool(mask[i, j])

        def is_visible(position: Position) -> bool:
            return at(now, position)

        surfaces = {row.position for rows in upper.values() for row in rows}
        surfaces.update(*volumes.values())
        touched: Set[UUID] = set()
        for identity, previous in senses.spatial_effects.items():
            if (previous.visible_volume_positions or previous.upper_volume_surfaces
                    or any(row.positions for row in previous.suppressions)):
                touched.add(identity)
            elif previous.positions and _gather(changed, box, previous.positions).any():
                touched.add(identity)
        if not reobserved.any() and not surfaces:
            before_values = {identity: senses.spatial_effects.get(identity) for identity in touched}
            for identity in touched:
                previous = senses.spatial_effects[identity]
                if previous.visible_volume_positions or previous.upper_volume_surfaces or any(row.positions for row in previous.suppressions):
                    senses.spatial_effects[identity] = previous.model_copy(update={
                        "visible_volume_positions": (),
                        "upper_volume_surfaces": (),
                        "suppressions": tuple(row.model_copy(update={"positions": tuple(
                            position for position in row.positions if is_visible(position))})
                                              for row in previous.suppressions)})
            return before_values
        candidates: Dict[UUID, Tuple[SpatialConditionOwner, Set[Position], Set[Position]]] = {}
        surface_mask = _cells_mask(surfaces, box)
        for condition in grid.get_spatial_conditions():
            footprint = grid.condition_footprint(condition.uuid)
            if footprint is None or not boxes_intersect(footprint.box, box):
                continue
            inside = embed(footprint, box, np.dtype(bool))
            seen_on = now
            if condition.uuid in volumes or condition.uuid in upper:
                seen_on = now | _cells_mask(volumes.get(condition.uuid, frozenset()), box) | _cells_mask(
                    [row.position for row in upper.get(condition.uuid, ())], box)
            observed_mask = inside & (reobserved | (surface_mask & seen_on))
            if observed_mask.any():
                candidates[condition.uuid] = (condition, set(_mask_positions(box[0], box[1], observed_mask)),
                                              set(_mask_positions(box[0], box[1], observed_mask & now)))
        observations: Dict[UUID, PerceivedSpatialEffect] = {}
        for condition, observed_positions, observed_visible in candidates.values():
            volume_positions = observed_positions & volumes.get(condition.uuid, frozenset())
            observation = condition.get_spatial_observation(
                observed_visible, observer_uuid=observer_uuid,
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
                own_volume = volumes.get(identity, frozenset())
                admitted = {position for position in outcome.positions if is_visible(position) or position in own_volume}
                suppressions.append(retained.model_copy(update={"positions": tuple(sorted(admitted))}))
            observations[identity] = observation.model_copy(update={"suppressions": tuple(suppressions)})
        touched.update(observations)
        before_values = {identity: senses.spatial_effects.get(identity) for identity in touched}
        for identity in touched:
            previous = senses.spatial_effects.get(identity)
            if previous is None:
                continue
            # Inspect only newly seen/changed visible cells. Hidden parts retain
            # their last observation, even when the objective owner was removed.
            kept = (np.array(previous.positions, dtype=np.int64).reshape(-1, 2)[
                ~_gather(reobserved, box, previous.positions)] if previous.positions else np.zeros((0, 2), np.int64))
            observed = observations.pop(identity, None)
            if observed is not None and observed.positions:
                kept = np.concatenate((kept, np.array(observed.positions, dtype=np.int64).reshape(-1, 2)))
            if kept.size:
                kept = np.unique(kept, axis=0)
                senses.spatial_effects[identity] = (observed or previous).model_copy(
                    update={"positions": tuple(zip(kept[:, 0].tolist(), kept[:, 1].tolist())),
                            "visible_volume_positions": observed.visible_volume_positions if observed is not None else (),
                            "upper_volume_surfaces": observed.upper_volume_surfaces if observed is not None else (),
                            "suppressions": observed.suppressions if observed is not None else tuple(
                                row.model_copy(update={"positions": tuple(position for position in row.positions
                                    if is_visible(position))}) for row in previous.suppressions)},
                )
            else:
                senses.spatial_effects.pop(identity)
        senses.spatial_effects.update(observations)
        return before_values

    # ------------------------------------------------------------------ light sources and helpers

    @staticmethod
    def _refresh_light_sources(observer_uuid: UUID, senses: Senses, world: SettlementWorld,
                               field: ObserverField) -> Tuple[Tuple, Dict[UUID, Tuple]]:
        """Compact emitter descriptors of the emitters lighting a visible cell; cell illumination has
        its native events. Returns what they were derived from and each descriptor's inputs."""
        grid = get_map()
        words = grid.light_slots_lit_within(senses.cells.visible)
        entities, objects = senses.entities, senses.objects
        inputs = (world.light_key, words.tobytes(), entities, objects)
        known = field.light_inputs
        if (known is not None and known[2] is entities and known[3] is objects and known[1] == inputs[1]
                and known[0] == inputs[0]):
            return known, field.light_values
        lit = grid.light_sources_in_slots(words)
        previous = senses.light_sources
        previous_values = field.light_values
        sources: Dict[UUID, PerceivedLightSource] = {}
        values_of: Dict[UUID, Tuple] = {}
        reused = True
        for row in world.light_sources:
            identity = row.identity
            if identity not in lit:
                continue
            anchor = row.anchor_uuid
            actor = entities.get(anchor) if anchor is not None else None
            item = objects.get(anchor) if anchor is not None else None
            values = row.values + (
                anchor if anchor is not None and (anchor == observer_uuid or actor is not None and actor.visual) else None,
                anchor if item is not None and item.visual else None)
            old = previous.get(identity)
            if old is not None and not old.affected_tiles and previous_values.get(identity) == values:
                sources[identity] = old
            else:
                reused = False
                revision, position, height, appearance, very_bright, bright, dim, actor_anchored, \
                    anchor_entity, anchor_item = values
                sources[identity] = PerceivedLightSource(
                    source_uuid=identity, revision=revision, position=position, base_height_steps=height,
                    appearance=appearance, very_bright_radius_feet=very_bright, bright_radius_feet=bright,
                    dim_radius_feet=dim, actor_anchored=actor_anchored, anchor_entity_uuid=anchor_entity,
                    anchor_item_uuid=anchor_item)
            values_of[identity] = values
        if reused and len(sources) == len(previous):
            return inputs, values_of
        for identity in previous:
            if identity not in sources:
                senses.light_source_removals[identity] = max(previous[identity].revision,
                    grid.light_source_revision(identity))
        for identity in sources:
            senses.light_source_removals.pop(identity, None)
        senses.light_sources = sources
        return inputs, values_of

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
                positions = set(event.senses_hint.light_changed_positions)
                # A light child of a move or placement also re-reads its cause's cells.
                parent = EventQueue.get_event_by_uuid(event.parent_event) if event.parent_event is not None else None
                if isinstance(parent, SpatialChangeEvent) and parent.event_type is not EventType.SPATIAL_LIGHT_CHANGED:
                    positions |= self._candidate_positions(parent)
                return positions
            return self._candidate_positions(event)
        if isinstance(event, SpatialEffectChangeEvent):
            return event.get_affected_positions()
        if isinstance(event, (ConditionApplicationEvent, ConditionRemovalEvent)) and event.resulting_tile is not None:
            return {event.resulting_tile.position}
        return None

    def _changes_visible_topology(self, event: Event, senses: Senses) -> bool:
        if isinstance(event, SpatialChangeEvent):
            hint = event.senses_hint
            if hint is None or not hint.requires_paths:
                return False
            return (any(cell_visible(senses.cells, position) for position in self._candidate_positions(event))
                or (event.object_uuid is not None and event.object_uuid in senses.objects))
        if isinstance(event, SpatialEffectChangeEvent):
            return any(cell_visible(senses.cells, position) for position in event.get_affected_positions())
        return False

    @staticmethod
    def _reason_for(event: Event, observer_uuid: UUID) -> SensoryUpdateReason:
        if event.event_type is EventType.TURN_START:
            return SensoryUpdateReason.TURN_START
        if event.event_type in (EventType.SPATIAL_LIGHT_CHANGED, EventType.SPATIAL_LIGHT_SOURCES_CHANGED):
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


def _row_values(rows: np.ndarray) -> np.ndarray:
    """Each contact row as one comparable value (its bytes)."""
    rows = np.ascontiguousarray(rows)
    return rows.view(np.dtype((np.void, rows.dtype.itemsize * rows.shape[1]))).ravel()


def _target_keys(rows: np.ndarray) -> np.ndarray:
    """Each contact row's target key (entity or object, uuid halves) as one comparable value."""
    return _row_values(np.column_stack(((rows[:, 0] != ROW_ENTITY).astype(np.int64), rows[:, 1], rows[:, 2])))


def _key_columns(keys: np.ndarray) -> List[Tuple[int, int, int]]:
    """Target keys back as (group, high, low) with the uuid halves unsigned."""
    columns = keys.view(np.int64).reshape(-1, 3).tolist()
    return [(group, high & UUID_LOW, low & UUID_LOW) for group, high, low in columns]


def _gather(mask: np.ndarray, box: Box, positions: Sequence[Position] | np.ndarray) -> np.ndarray:
    """A box-anchored mask's values at some cells, False outside the box."""
    cells = np.asarray(positions, dtype=np.int64).reshape(-1, 2)
    i, j = cells[:, 0] - box[0], cells[:, 1] - box[1]
    inside = (i >= 0) & (i < mask.shape[0]) & (j >= 0) & (j < mask.shape[1])
    values = np.zeros(cells.shape[0], dtype=bool)
    values[inside] = mask[i[inside], j[inside]]
    return values


def _cells_mask(positions: Iterable[Position], box: Box) -> np.ndarray:
    """A bool mask over a box holding some cells (cells outside it are left out)."""
    mask = np.zeros((box[2] - box[0] + 1, box[3] - box[1] + 1), dtype=bool)
    cells = np.array(list(positions), dtype=np.int64).reshape(-1, 2)
    if cells.size:
        i, j = cells[:, 0] - box[0], cells[:, 1] - box[1]
        inside = (i >= 0) & (i < mask.shape[0]) & (j >= 0) & (j < mask.shape[1])
        mask[i[inside], j[inside]] = True
    return mask


def _distance_feet(origin: Position, position: Position) -> int:
    return int(FRAME_DISTANCE_FEET[(position[0] - origin[0] + R) * SIDE + position[1] - origin[1] + R])


def _same_cells(first: CellLayer, second: CellLayer) -> bool:
    """Whether two layers hold the same nonzero cells with the same values."""
    if first is second:
        return True
    if not first.values.size or not second.values.size:
        return not first.values.any() and not second.values.any()
    box = union_box(first.box, second.box)
    return bool(np.array_equal(embed(first, box, first.values.dtype), embed(second, box, second.values.dtype)))


def _replace_effects(value: PublishedSenses, effects: Dict[UUID, PerceivedSpatialEffect]) -> PublishedSenses:
    return PublishedSenses(value.position, value.cells, value.seen, value.entities, value.objects, effects,
                           value.light_sources, value.light_source_removals, value.paths_dirty,
                           value.passive_perception, value.sense_modes_hash, value.sense_modes, value.visual_access)


def _replace_paths_dirty(value: PublishedSenses) -> PublishedSenses:
    return PublishedSenses(value.position, value.cells, value.seen, value.entities, value.objects,
                           value.spatial_effects, value.light_sources, value.light_source_removals, True,
                           value.passive_perception, value.sense_modes_hash, value.sense_modes, value.visual_access)


spatial_senses_system = SpatialSensesSystem()
