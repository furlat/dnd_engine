"""Authoritative observer-local perception and navigation state.

Perception is data (plan §6b, PV1a): one settlement path recomputes each selected
observer's view with the array rule of `dnd.core.view` over the map's objective
cell grids, then publishes its cells as arrays and emits the difference of its
masks. Python runs per observer, per target on hit cells, per hazard owner and per
spatial condition; never per visible cell.
"""

from typing import AbstractSet, Any, Dict, FrozenSet, Iterable, List, Mapping, Optional, Self, Sequence, Set, Tuple
from uuid import UUID
from pydantic import Field, InstanceOf, PrivateAttr

import math
from dataclasses import dataclass

import numpy as np
import time

from dnd.core.effect_types import ObservedChangeRef, ObservedField
from dnd.action_timing import action_timing_enabled, record_action_count, record_action_timing
from dnd.core.base_object import BaseObject
from dnd.core.base_block import BaseBlock
from dnd.core.base_conditions import ConditionApplicationEvent, ConditionRemovalEvent
from dnd.core.base_tiles import Tile
from dnd.core.gridmap import GridMap, SpatialConditionOwner, get_map
from dnd.core.navigation import NO_CELLS_LAYER, NO_ROUTES, NO_SIDES_LAYER, Routes, has_route
from dnd.core.geometry import ROUTE_STEP_SHIFT, supercover_line, supercover_route_table
from dnd.core.presentation_geometry import SpherePresentationGeometry
from dnd.core.values import ModifiableValue
from dnd.core.view import (FRAME_DISTANCE_FEET, MAGICAL_DARKNESS_BIT, NO_CELLS, OFF, PLAIN, R,
    SIDE, SPECIAL, SURVIVORS, Box, CellLayer, OpticalView, PerceivedCells, Position, RouteRows, RouteSight,
    boxes_intersect, cell_visible, embed, frame_box, frame_index, frame_of, frame_rows, lit_view,
    range_bits, route_rows, route_sight, rows_positions, sense_radius_cells, union_box, window_of)
from dnd.core.events import (
    Event, EventType, EventPhase, SpatialChangeEvent,
    SpatialEffectChangeEvent, DeathEvent, EventQueue, OpenGroup, SensoryUpdateEvent,
    SensoryUpdateReason, SensesUpdateHint,
)
from dnd.core.cells import pack_layers, pack_mask, pack_values
from dnd.types.cells import EMPTY_CELLS, EMPTY_VALUES, CellMask, CellValues, no_cells
from dnd.types.event_facts import SpatialChangeType
from dnd.types.senses import (
    PerceivedContact, PerceivedLightSource, PerceivedSpatialEffect, SenseMode, SensesType, VolumeSurfaceSight,
    SensesSnapshot as SensesSnapshot,
)
from dnd.types.world import CardinalDirection, LightLevel, WorldEdgeChannel


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
# The values one settlement shares between its observers: an immutable contact, emitter
# descriptor or change reference with the same inputs is built once (discarded after the settlement).
SharedValues = Dict[Tuple[Any, ...], Any]



def _empty_seen() -> CellLayer:
    return CellLayer(0, 0, np.zeros((0, 0), dtype=bool))


class Senses(BaseBlock):
    """One observer's published perception (cells as arrays, contacts) and its navigation facts."""

    visual_access: ModifiableValue = Field(
        default_factory=lambda: ModifiableValue(
            source_entity_uuid=UUID(int=0),
            base=1,
            name="Visual Access",
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
    walkable: InstanceOf[CellLayer] = Field(default_factory=lambda: NO_CELLS_LAYER, exclude=True,
                                            description="Walkable visible cells (bool layer over the window).")
    paths: InstanceOf[Routes] = Field(default=NO_ROUTES, exclude=True,
                                      description="Known subjective routes: destinations, costs and paths.")
    safe_paths: InstanceOf[Routes] = Field(default=NO_ROUTES, exclude=True,
                                           description="Known routes that avoid perceptible hazardous tiles.")
    sense_modes: List[SenseMode] = Field(default_factory=list, description="Special sense modes with ranges.")
    sense_mode_sources: Dict[UUID, SenseMode] = Field(
        default_factory=dict,
        description="Source-owned structural special senses keyed by grant UUID.",
    )
    collision_blocked: InstanceOf[CellLayer] = Field(
        default_factory=lambda: NO_CELLS_LAYER, exclude=True,
        description="Cells discovered blocked by imperceivable entities or objects during movement (bool layer).",
    )
    directional_collision_blocked: InstanceOf[CellLayer] = Field(
        default_factory=lambda: NO_SIDES_LAYER, exclude=True,
        description="Tile sides discovered blocked by imperceivable blockers during movement (side_bit per cell).",
    )
    _paths_dirty: bool = PrivateAttr(default=False)
    _last_passive_perception: int = PrivateAttr(default=0)
    _last_sense_modes_hash: int = PrivateAttr(default=0)
    _last_visual_access: int = PrivateAttr(default=1)
    _perception_max_distance: int = PrivateAttr(default=20)
    _path_revision: int = PrivateAttr(default=0)
    _path_max_distance: Optional[int] = PrivateAttr(default=None)

    def value_fields(self) -> tuple[ModifiableValue, ...]:
        """This block's values: its value fields, in declaration order."""
        return (self.visual_access,)

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

    def replace_navigation(
        self,
        walkable: CellLayer,
        paths: Routes,
        safe_paths: Routes,
        path_max_distance: Optional[int] = None,
    ) -> None:
        """Replace navigation facts without mutating perception-owned state."""
        self.walkable = walkable
        self.paths = paths
        self.safe_paths = safe_paths
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
    """The observer's published perception as a `SensesSnapshot` of packed cell sets."""
    cells = senses.cells
    visible_cells, (light, hazard) = pack_layers(cells.visible.x0, cells.visible.y0, cells.visible.values.astype(bool),
        embed(cells.light, cells.visible.box, np.dtype(np.uint8)), embed(cells.hazard, cells.visible.box, np.dtype(np.uint8)))
    return SensesSnapshot(
        position=senses.position,
        visible=visible_cells,
        seen=pack_mask(senses.seen.x0, senses.seen.y0, senses.seen.values.astype(bool)),
        entities=dict(senses.entities),
        objects=dict(senses.objects),
        effective_light_levels=light,
        hazardous_cells=hazard,
        spatial_effects=dict(senses.spatial_effects),
        light_sources=dict(senses.light_sources),
        light_source_removals=dict(senses.light_source_removals),
        paths_dirty=senses._paths_dirty,
        passive_perception=senses._last_passive_perception,
        sense_modes_hash=senses._last_sense_modes_hash,
        sense_modes=tuple(mode.model_copy(deep=True) for mode in senses.get_sense_modes()),
        visual_access=senses._last_visual_access,
    )


@dataclass(frozen=True)
class CellChange:
    """One observer's published-cell change: the packed cells its sensory event carries (an initial
    observer's against no cells) and whether its visible, seen and hazard cells differ from before."""

    visible_added: CellMask
    visible_removed: CellMask
    seen_added: CellMask
    light_changed: CellValues        # the after light where a cell was added or its light changed
    hazards_changed: CellValues      # the after hazard where a cell was added or its hazard changed
    visible_differs: bool
    seen_differs: bool
    hazard_differs: bool


NO_CELL_CHANGE = CellChange(EMPTY_CELLS, EMPTY_CELLS, EMPTY_CELLS, EMPTY_VALUES, EMPTY_VALUES, False, False, False)


def _cell_change(before: PublishedSenses, after: PublishedSenses, initial: bool) -> CellChange:
    """Visible cells added and removed, seen cells added, and changed light / hazard after-values,
    with whether the visible, seen and hazard cells differ at all.

    Each is one mask difference over the union of the two windows, so the cost follows the window,
    not the changed cells; published cells that did not change are the same object. Each is packed
    straight from the arrays. An initial observer's delta is against no cells; its flags compare
    with what it held before.
    """
    if not initial and before.cells is after.cells and before.seen is after.seen:
        return NO_CELL_CHANGE
    seen_added, seen_differs = EMPTY_CELLS, False
    if initial or before.seen is not after.seen:
        if not before.seen.values.size or not after.seen.values.size:
            seen_differs = bool(before.seen.values.any() or after.seen.values.any())
            seen_added = pack_mask(after.seen.x0, after.seen.y0, after.seen.values.astype(bool))
        else:
            seen_box = union_box(before.seen.box, after.seen.box)
            seen_before = embed(before.seen, seen_box, np.dtype(bool))
            seen_after = embed(after.seen, seen_box, np.dtype(bool))
            # The seen cells only grow (each recompute ORs its visible cells in).
            seen_added = pack_mask(seen_box[0], seen_box[1], seen_after if initial else seen_after & ~seen_before)
            seen_differs = bool((seen_after != seen_before).any())
    b, a = before.cells, after.cells
    if not a.visible.values.size and not b.visible.values.size:
        return CellChange(EMPTY_CELLS, EMPTY_CELLS, seen_added, EMPTY_VALUES, EMPTY_VALUES, False, seen_differs, False)
    if not initial and b.visible is a.visible and b.light is a.light:
        # Only hazards can differ, on the visible cells.
        if b.hazard is a.hazard:
            return CellChange(EMPTY_CELLS, EMPTY_CELLS, seen_added, EMPTY_VALUES, EMPTY_VALUES, False, seen_differs,
                              False)
        box = a.visible.box
        moved = embed(b.hazard, box, np.dtype(bool)) != a.hazard.values
        return CellChange(EMPTY_CELLS, EMPTY_CELLS, seen_added, EMPTY_VALUES,
                          pack_values(box[0], box[1], a.visible.values.astype(bool) & moved,
                                      a.hazard.values.astype(np.uint8)), False, seen_differs, bool(moved.any()))
    box = (a.visible.box if not b.visible.values.size else b.visible.box if not a.visible.values.size
           else union_box(b.visible.box, a.visible.box))
    after_visible = embed(a.visible, box, np.dtype(bool))
    after_light = embed(a.light, box, np.dtype(np.uint8))
    after_hazard = embed(a.hazard, box, np.dtype(bool))
    before_visible = embed(b.visible, box, np.dtype(bool))
    hazard_moved = embed(b.hazard, box, np.dtype(bool)) != after_hazard
    visible_differs = bool((before_visible != after_visible).any())
    if initial:
        added, removed = after_visible, np.zeros_like(after_visible)
        light_changed = hazard_changed = after_visible
    else:
        added, removed = after_visible & ~before_visible, before_visible & ~after_visible
        light_changed = after_visible & (~before_visible | (embed(b.light, box, np.dtype(np.uint8)) != after_light))
        hazard_changed = after_visible & (~before_visible | hazard_moved)
    return CellChange(pack_mask(box[0], box[1], added), pack_mask(box[0], box[1], removed), seen_added,
                      pack_values(box[0], box[1], light_changed, after_light),
                      pack_values(box[0], box[1], hazard_changed, after_hazard.astype(np.uint8)),
                      visible_differs, seen_differs, bool(hazard_moved.any()))


def _contact_delta(before: Dict[UUID, PerceivedContact], after: Dict[UUID, PerceivedContact], initial: bool,
                   touched: Optional[FrozenSet[UUID]] = None) -> Tuple[Dict[UUID, PerceivedContact], Set[UUID]]:
    """Changed and removed contacts; an unchanged mapping is the same object, an unchanged contact too.
    With `touched`, only those targets can differ (the recompute's own row difference)."""
    if initial:
        return dict(after), set()
    if before is after:
        return {}, set()
    if touched is not None:
        return ({uuid: contact for uuid in touched if (contact := after.get(uuid)) is not None
                 and (previous := before.get(uuid)) is not contact and previous != contact},
                {uuid for uuid in touched if uuid not in after and uuid in before})
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
    cells: CellChange,
    contact_changes: Optional[Tuple[FrozenSet[UUID], FrozenSet[UUID]]] = None,
    shared: Optional[SharedValues] = None,
    contact_deltas: Optional[Tuple[Tuple[Dict[UUID, PerceivedContact], Set[UUID]],
                                   Tuple[Dict[UUID, PerceivedContact], Set[UUID]]]] = None,
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
        cells: The cell change of this before and after (`_cell_change`), against no cells when initial.
        contact_changes: The entities and objects whose contacts can differ, when known.
        shared: The settlement's shared values: equal change references are built once.
        contact_deltas: The entity and object contact deltas, when the caller computed them.

    Returns:
        The completed sensory event when the perception differs, otherwise None.
    """
    timing = action_timing_enabled()
    total_started = time.perf_counter() if timing else 0.0
    started = time.perf_counter() if timing else 0.0
    visible_added, visible_removed, seen_added = cells.visible_added, cells.visible_removed, cells.seen_added
    light_changed, hazards_changed = cells.light_changed, cells.hazards_changed

    if contact_deltas is None:
        contact_deltas = (
            _contact_delta(before.entities, after.entities, initial,
                           contact_changes[0] if contact_changes is not None else None),
            _contact_delta(before.objects, after.objects, initial,
                           contact_changes[1] if contact_changes is not None else None))
    (entity_changed, entity_removed), (object_changed, object_removed) = contact_deltas
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

    cells_changed = not (no_cells(visible_added) and no_cells(visible_removed) and no_cells(seen_added))
    light_moved, hazards_moved = not no_cells(light_changed.cells), not no_cells(hazards_changed.cells)
    has_delta = any((
        cells_changed,
        entity_changed,
        entity_removed,
        object_changed,
        object_removed,
        paths_refresh_needed,
        passive_changed,
        sense_modes_changed,
        visual_access_changed,
        position_changed,
        light_moved,
        hazards_moved,
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
    entity_changed, object_changed = _sorted_contacts(entity_changed), _sorted_contacts(object_changed)
    observed_changes: list[ObservedChangeRef] = []
    source_index = EventQueue.get_event_index(cause_event.uuid) if cause_event is not None else None
    if cause_event is not None and source_index is not None:
        fields: tuple[tuple[ObservedField, tuple[UUID, ...]], ...] = (
            ("position", (owner_uuid,) if position_changed else ()),
            ("visibility", (owner_uuid,) if cells_changed else ()),
            ("light", (owner_uuid,) if light_moved else ()),
            ("hazards", (owner_uuid,) if hazards_moved else ()),
            ("senses", (owner_uuid,) if passive_changed or sense_modes_changed or visual_access_changed else ()),
            ("paths", (owner_uuid,) if paths_refresh_needed else ()),
            ("entity_contact", (*entity_changed, *sorted(entity_removed, key=str))),
            ("object_contact", (*object_changed, *sorted(object_removed, key=str))),
            ("spatial_effect", (*effects_changed, *effects_removed)),
        )
        references = shared if shared is not None else {}
        for field, owners in fields:
            for identity in owners:
                key = ("observed", cause_event.uuid, source_index, field, identity)
                reference = references.get(key)
                if reference is None:
                    reference = references[key] = ObservedChangeRef(source_event_uuid=cause_event.uuid,
                        source_index=source_index, resolution_ref=cause_event.resolution_ref,
                        field=field, owner_uuid=identity)
                observed_changes.append(reference)
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
        entity_contacts_changed=entity_changed,
        entity_contacts_removed=entity_removed,
        object_contacts_changed=object_changed,
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
class SightInputs:
    """What an observer's sight stage reads, besides light: while all of them hold, its route
    sight and felt cells are kept. The grids are compared by value over the window, the only
    cells a route, a frame lookup or a felt cell of this view reads."""

    scalars: Tuple                   # origin, perception reach, sense modes, ordinary sight, visual access,
                                     # optical and propagation revisions, window
    exists: np.ndarray               # Tile presence over the window
    obscurement: np.ndarray          # combined OBSCUREMENT_BITS over the window
    version: int                     # the settlement's grid version these were read at


def _same_sight_inputs(first: SightInputs, second: SightInputs) -> bool:
    return (first.scalars == second.scalars and np.array_equal(first.exists, second.exists)
            and np.array_equal(first.obscurement, second.obscurement))


def _held_values(kept: np.ndarray, kept_version: int, version: int, layer: CellLayer, window: Box) -> np.ndarray:
    """A grid's window values: the kept ones while the settlement's grid version holds."""
    return kept if kept_version == version else _window_values(layer, window)


@dataclass(frozen=True)
class ObserverField:
    """One observer's settled sight, owned by the system and keyed by observer uuid.

    A settlement re-runs a stage only when its inputs changed: the sight stage on
    `sight_inputs`, the light stage on the objective light over the window (`light`);
    contacts, hazards, fixtures and emitters read the published view every time. The
    routes are kept while their key (origin, radius, optical revision) holds; the window
    and contact rows describe the last published view.
    """

    origin: Position
    window: Box                      # the published window: the frame around origin within the map cells
    selection: Box                   # the cells whose change can reach this view (window and one halo)
    optical_key: Tuple[Position, int, int]
    routes: RouteRows
    felt_keys: Tuple[Tuple[SensesType, Tuple[Position, int, int]], ...]
    felt_rows: Tuple[np.ndarray, ...]
    sight_inputs: SightInputs
    sight: RouteSight
    light: np.ndarray                # the objective light over the window the optical view was lit with
    light_version: int               # the settlement's light-grid version it was read at
    optical: OpticalView
    exists_frame: np.ndarray
    felt_frame: np.ndarray
    seen_frame: np.ndarray
    senses_frame: np.ndarray
    contact_rows: np.ndarray         # the published contacts as rows: kind, uuid halves, x, y, visual, senses
    contact_uuids: np.ndarray        # each contact row's target (object array of UUID)
    contact_changes: Optional[Tuple[FrozenSet[UUID], FrozenSet[UUID]]]  # entities, objects the last recompute touched
    table_version: Optional[int]     # the version of the target table the published contacts were resolved against
    passive: Optional[int]           # and the passive perception they were resolved with
    light_values: Dict[UUID, Tuple]  # each published emitter's descriptor inputs
    light_inputs: Optional[Tuple]    # what the published emitters were derived from (reused while equal)
    volumes: Dict[UUID, FrozenSet[Position]]          # the seen volumes the published fixtures were observed with
    upper: Dict[UUID, Tuple[VolumeSurfaceSight, ...]]  # and their upper surfaces


NO_CONTACT_ROWS = np.zeros((0, 8), dtype=np.int64)
CELL_PACK_LIMIT = 1 << 20
NO_UUIDS = np.zeros(0, dtype=object)


@dataclass(frozen=True)
class GrantTable:
    """The cells whose facts each settled observer is granted (its routes, felt cells and volume
    routes), owned by the system and their only holder: a settlement replaces its observers' rows,
    register and unregister drop a row, reset and a replaced map empty it (no rows is no table, the
    system's cold state). Each row is a bool layer over the observer's window; the rows are read
    together through one flat array."""

    observers: Tuple[UUID, ...]
    x0: np.ndarray                   # each row's window origin, width and height
    y0: np.ndarray
    width: np.ndarray
    height: np.ndarray
    offset: np.ndarray               # each row's first index in `flat`
    flat: np.ndarray                 # every row's values, x-major, concatenated


def _grant_table(rows: Sequence[Tuple[UUID, CellLayer]]) -> Optional[GrantTable]:
    """The table of these rows (observer, granted cells over its window); none without rows."""
    if not rows:
        return None
    layers = [layer for _, layer in rows]
    sizes = np.array([layer.values.size for layer in layers], dtype=np.int64)
    return GrantTable(tuple(identity for identity, _ in rows),
                      np.array([layer.x0 for layer in layers], dtype=np.int64),
                      np.array([layer.y0 for layer in layers], dtype=np.int64),
                      np.array([layer.values.shape[0] for layer in layers], dtype=np.int64),
                      np.array([layer.values.shape[1] for layer in layers], dtype=np.int64),
                      np.concatenate(([0], np.cumsum(sizes)[:-1])).astype(np.int64),
                      np.concatenate([layer.values.reshape(-1) for layer in layers]))


def _replace_grants(table: Optional[GrantTable], rows: Mapping[UUID, Optional[CellLayer]]) -> Optional[GrantTable]:
    """The table with these observers' rows replaced (None drops a row)."""
    kept = [] if table is None else [
        (identity, CellLayer(int(x0), int(y0), table.flat[offset:offset + width * height].reshape(width, height)))
        for identity, x0, y0, width, height, offset in zip(table.observers, table.x0.tolist(), table.y0.tolist(),
                                                           table.width.tolist(), table.height.tolist(),
                                                           table.offset.tolist())
        if identity not in rows]
    return _grant_table(kept + [(identity, layer) for identity, layer in rows.items() if layer is not None])


# One view's seen volumes, their upper surfaces and the cells their routes grant (`_volume_sight`).
VolumeSights = Tuple[Dict[UUID, FrozenSet[Position]], Dict[UUID, Tuple[VolumeSurfaceSight, ...]], Set[Position]]
# One view's resolved contacts (`_contacts`): entities, objects, its evidence rows and their targets, and the
# entities and objects the recompute touched (None for a first view).
ResolvedContacts = Tuple[Dict[UUID, PerceivedContact], Dict[UUID, PerceivedContact], np.ndarray, np.ndarray,
                         Optional[Tuple[FrozenSet[UUID], FrozenSet[UUID]]]]


@dataclass(frozen=True)
class VisibleStack:
    """The settled views' visible cells before and after their settlement, stacked over one box
    (a local value of one settlement)."""

    box: Box
    before: np.ndarray               # (views, width, height) bool
    after: np.ndarray


def _layers_box(layers: Iterable[CellLayer]) -> Box:
    """The union of the non-empty layers' boxes ((0, 0, -1, -1) when all are empty)."""
    boxes = [layer.box for layer in layers if layer.values.size]
    if not boxes:
        return 0, 0, -1, -1
    return (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))


def _visible_stack(before: Sequence[CellLayer], after: Sequence[CellLayer]) -> VisibleStack:
    """The views' visible cells before and after, each stacked over the union of all their boxes."""
    box = _layers_box((*before, *after))
    stacks = []
    for layers in (before, after):
        out = np.zeros((len(layers), box[2] - box[0] + 1, box[3] - box[1] + 1), dtype=bool)
        for index, layer in enumerate(layers):
            if layer.values.size:
                x0, y0 = layer.x0 - box[0], layer.y0 - box[1]
                out[index, x0:x0 + layer.values.shape[0], y0:y0 + layer.values.shape[1]] = layer.values
        stacks.append(out)
    return VisibleStack(box, stacks[0], stacks[1])


def _granted_at(table: Optional[GrantTable], positions: Iterable[Position]) -> Set[UUID]:
    """The table's observers granted any of these cells."""
    cells = np.array(list(positions), dtype=np.int64).reshape(-1, 2)
    if table is None or not cells.size:
        return set()
    i = cells[None, :, 0] - table.x0[:, None]
    j = cells[None, :, 1] - table.y0[:, None]
    inside = (i >= 0) & (i < table.width[:, None]) & (j >= 0) & (j < table.height[:, None])
    granted = np.zeros(inside.shape, dtype=bool)
    granted[inside] = table.flat[(table.offset[:, None] + i * table.height[:, None] + j)[inside]]
    return {table.observers[index] for index in np.flatnonzero(granted.any(axis=1)).tolist()}


@dataclass(frozen=True)
class LightSourceRow:
    """One active emitter's observer-independent descriptor values, read once per settlement."""

    identity: UUID
    anchor_uuid: Optional[UUID]
    values: Tuple                    # revision, position, height, appearance, radii, actor_anchored


@dataclass(frozen=True)
class LightSourceTable:
    """The active emitters of one settlement as columns (frozen, built once)."""

    rows: Tuple[LightSourceRow, ...]
    slots: np.ndarray                # each emitter's lit-slot bit index
    anchor_entity_key: np.ndarray    # the anchor's contact target key as an entity (-1 when unanchored)
    anchor_item_key: np.ndarray      # and as an object
    key: Tuple                       # every row's inputs: while they hold, the settlement keeps this table


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
    light_sources: LightSourceTable
    optical_revision: int
    propagation_revision: int
    sight_version: int               # GridMap's Tile and obscurement grid revision (advanced by their writers)
    light_version: int               # GridMap's light grid revision


STEALTH_NONE = np.iinfo(np.int64).min
ROW_ENTITY, ROW_OBJECT, ROW_SIDE, ROW_KNOWN = 0, 1, 2, 3
UUID_LOW = (1 << 64) - 1


@dataclass(frozen=True)
class ContactTable:
    """Every contact target on the map's cells, as arrays (frozen): kept across settlements and
    updated from its explicit inputs, the cells the settlement's facts name.

    A target's observer-independent facts (stealth DC, invisibility, whether its observability
    rule reads the world) are columns; unlisted targets have no row. A cell row is one (occupied
    cell, target) pair of an entity or a center object; a side row is one object on a boundary
    side, with the channels open from across that side.
    """

    box: Box                         # the map cells the table covers
    blocks: Tuple[BaseBlock, ...]
    uuids: Tuple[UUID, ...]
    uuid_objects: np.ndarray         # the same uuids as an object array, for row gathers
    targets: Dict[Tuple[UUID, bool], int]   # (uuid, listed as an entity) -> target index
    entity_index: Dict[UUID, int]
    uuid_halves: np.ndarray          # (targets, 2) uint64
    stealth: np.ndarray              # int64 stealth DC, STEALTH_NONE when unhidden
    invisible: np.ndarray            # bool
    volatile: np.ndarray             # bool: the observability rule reads the world (asked every settlement)
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
    # A target's contact for an observer is a function of the observer's view and of the target's
    # rows: its cells (or side) and its facts. A target key is its system-wide id times two plus its
    # class (0 entity, 1 object); each row's inputs are one int64 row, so two tables are compared
    # by value per target.
    target_key: np.ndarray           # per target
    cell_input: np.ndarray           # (cell rows, 6): x, y, kind, target key, stealth, invisible
    side_input: np.ndarray           # (side rows, 12): the side columns, target key, position, stealth, invisible
    cell_target_key: np.ndarray
    side_target_key: np.ndarray


def _pack_cells(keys: np.ndarray, xs: np.ndarray, ys: np.ndarray) -> np.ndarray:
    """(key, x, y) as one exact int64: 21 bits per coordinate, the key (an observer index, or 0;
    0 <= key < 2^20) above them."""
    if xs.size and (np.abs(xs).max() >= CELL_PACK_LIMIT or np.abs(ys).max() >= CELL_PACK_LIMIT
                    or keys.max() >= 1 << 20):
        raise ValueError("cell coordinates or keys exceed the packed key range")
    return (keys << 42) | ((xs + CELL_PACK_LIMIT) << 21) | (ys + CELL_PACK_LIMIT)


TargetFacts = Tuple[BaseBlock, int, int, bool, bool]  # block, key, stealth DC, invisible, volatile


def _contact_table_value(box: Box, facts: Sequence[Tuple[UUID, bool, TargetFacts]], cell_array: np.ndarray,
                         side_array: np.ndarray) -> ContactTable:
    """The table of these targets (uuid, listed as an entity, facts) and rows: cells (x, y, target,
    kind) and sides (side x, y, across x, y, across tile, optical, propagation, target, position)."""
    uuids = tuple(identity for identity, _, _ in facts)
    halves = np.array([(identity.int >> 64, identity.int & UUID_LOW) for identity in uuids],
                      dtype=np.uint64).reshape(-1, 2)
    target_key = np.array([values[1] for _, _, values in facts], dtype=np.int64)
    stealth = np.array([values[2] for _, _, values in facts], dtype=np.int64)
    invisible = np.array([values[3] for _, _, values in facts], dtype=bool)
    volatile = np.array([values[4] for _, _, values in facts], dtype=bool)
    cell_x, cell_y, cell_target, cell_kind = cell_array[:, 0], cell_array[:, 1], cell_array[:, 2], cell_array[:, 3]
    side_target = side_array[:, 7]
    cell_keys, side_keys = target_key[cell_target], target_key[side_target]
    cell_input = np.column_stack((cell_x, cell_y, cell_kind, cell_keys, stealth[cell_target],
                                  invisible[cell_target])).astype(np.int64).reshape(-1, 6)
    side_input = np.column_stack((side_array[:, :7], side_keys, side_array[:, 8:10], stealth[side_target],
                                  invisible[side_target])).astype(np.int64).reshape(-1, 12)
    uuid_objects = np.empty(len(uuids), dtype=object)
    uuid_objects[:] = uuids
    return ContactTable(
        box, tuple(values[0] for _, _, values in facts), uuids, uuid_objects,
        {(identity, as_entity): index for index, (identity, as_entity, _) in enumerate(facts)},
        {identity: index for index, (identity, as_entity, _) in enumerate(facts) if as_entity},
        halves, stealth, invisible, volatile,
        cell_x, cell_y, cell_target, cell_kind,
        side_array[:, 0], side_array[:, 1], side_array[:, 2], side_array[:, 3], side_array[:, 4] != 0,
        side_array[:, 5] != 0, side_array[:, 6] != 0, side_target, side_array[:, 8], side_array[:, 9],
        target_key, cell_input, side_input, cell_keys, side_keys)


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
    published: bool                  # the observer has a settled view (its published contacts are its own)
    lit_kept: bool                   # sight and light inputs held: the published optical view is current
    frames_kept: bool                # the visible cells and their senses held (what contacts read of the view)
    frame_changes: Optional[Set[Position]]  # with the sight held: the cells whose visibility or senses
                                            # changed (contacts read only those); None when the sight changed
    optical: OpticalView
    exists_frame: np.ndarray         # bool frame of the cells holding a Tile
    seen_frame: np.ndarray           # bool frame of the visible cells
    senses_frame: np.ndarray         # uint8 frame: contact sense bits established on visible cells
    felt_frame: np.ndarray           # uint8 frame: BLINDSIGHT / TREMORSENSE bits on felt cells


def _granted_cells(view: ObserverView, volume_grants: Set[Position]) -> CellLayer:
    """The cells whose facts a view grants, over its window: its wall-FOV routes, felt cells and the
    routes its seen volumes tested."""
    origin, window = view.origin, view.field.window
    grants = np.zeros(OFF + 1, dtype=bool)
    grants[view.field.routes.rows] = True
    grants |= view.felt_frame != 0
    if volume_grants:
        cells_array = np.array(sorted(volume_grants), dtype=np.int64)
        grants[frame_index(cells_array[:, 0], cells_array[:, 1], origin)] = True
    grants[OFF] = False
    return CellLayer(window[0], window[1], window_of(grants, origin, window))


_NO_SENSES_HINT = SensesUpdateHint()


def _perception_inert(event: Event) -> bool:
    """Whether a fact changes nothing a settlement reads: a tiles fact whose hint asks nothing.

    Residues publish it for after-values that change no traversal: amounts, and a harmless
    material's presence. A settlement reads light, obscurement, tile presence, the optical and
    propagation topology, hazard owners (only a harmful material's presence, published as tile
    mechanics), contacts, fixtures and emitters. Seats read the tile rows from the world fact,
    not from senses.
    """
    return (isinstance(event, SpatialChangeEvent) and event.change_type is SpatialChangeType.TILES_CHANGED
            and event.senses_hint == _NO_SENSES_HINT)


@dataclass
class _GroupSettlement:
    """Facts recorded for one observer while a simultaneous group is open."""

    events: List[Event]
    full: bool = False
    max_distance: Optional[int] = None


class SpatialSensesSystem:
    """Single reducer for observer-local visual cells and typed contacts."""

    SYSTEM_NAME = "spatial_senses"
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
        self._settled_with_light = False
        # The settled observers' grants (written by each settlement, dropped with their fields).
        self._grants: Optional[GrantTable] = None
        # The identity grants of a creature at a cell, valid while no observer's published
        # perception changes: every perception write (register, unregister, recompute,
        # reset, a replaced map) clears them with the grant table's write.
        self._identity_grants: Dict[Tuple[UUID, Tuple[int, int]], FrozenSet[str]] = {}
        # Contact targets' ids (each target once, in first-seen order): their keys compare by value
        # across settlements. Append-only; reset clears it with every field that holds a key.
        self._target_ids: Dict[UUID, int] = {}
        # The last settlement's emitter table, kept while every row holds (compared by value).
        self._light_table: Optional[LightSourceTable] = None
        # The contact target table, kept and updated at the cells each settlement's facts name; its
        # version advances with every update, and the update's changed target keys are kept.
        self._table: Optional[ContactTable] = None
        self._table_version = 0
        # The map the fields and tables were read from.
        self._map: Optional[GridMap] = None
        self._table_changes: Optional[np.ndarray] = None
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
        self._settled_with_light = False
        self._grants = None
        self._identity_grants.clear()
        self._target_ids.clear()
        self._light_table = None
        self._table = None
        self._table_version = 0
        self._table_changes = None
        self._map = None

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
        """Publish the group's pending light and settle every recorded observer once: with the light
        fact, before it completes (its consumers read the settled view), or after, without one."""
        self._absorbing_light, self._settled_with_light = True, False
        try:
            get_map().settle_pending_lights(parent_event=group.root_uuid)
        finally:
            self._absorbing_light = False
        if not self._settled_with_light or self._pending:
            covered = self._covered_observers if self._settled_with_light else frozenset()
            self._settle_recorded(group)
            self._covered_observers |= covered

    def _settle_recorded(self, group: OpenGroup) -> None:
        """Settle every observer recorded while the group was open, once, with all its facts."""
        root_uuid = group.root_uuid
        pending, self._pending = self._pending, {}
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
        # An observer that recorded only inert facts and was asked no refresh has nothing to settle;
        # the others settle with every fact they recorded.
        pending = {identity: settlement for identity, settlement in pending.items()
                   if settlement.full or not all(_perception_inert(event) for event in settlement.events)}
        self._covered_facts, self._covered_observers = frozenset(group.completes_after), frozenset(pending)
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
            shared: SharedValues = {}
            events = {identity: pending[identity].events for identity in observers}
            settled = self._settle(observers, events, shared=shared)
            sensory_events = self._emit_settlement(observers, settled, events, root, shared)
        finally:
            self._settling = False
        if sensory_events:
            EventQueue.register_completion_sequence(sensory_events)
            self.published_observers.update(event.observer_uuid for event in sensory_events)

    def _target_key(self, identity: UUID, as_entity: bool) -> int:
        """A contact target's key: its id times two plus its class (0 entity, 1 object)."""
        target_id = self._target_ids.setdefault(identity, len(self._target_ids))
        return target_id * 2 + (0 if as_entity else 1)

    def register_observer(self, observer_uuid: UUID, senses: Senses) -> None:
        """Register an observer without independently materializing its world view."""
        self.senses_by_observer[observer_uuid] = senses
        if self.fields.pop(observer_uuid, None) is not None:
            self._grants = _replace_grants(self._grants, {observer_uuid: None})
        self._identity_grants.clear()

    def unregister_observer(self, observer_uuid: UUID) -> None:
        """Remove an observer and its field."""
        self.senses_by_observer.pop(observer_uuid, None)
        self.published_observers.discard(observer_uuid)
        if self.fields.pop(observer_uuid, None) is not None:
            self._grants = _replace_grants(self._grants, {observer_uuid: None})
            self._identity_grants.clear()

    # ------------------------------------------------------------------ selection

    def observers_granted(self, positions: Iterable[Position]) -> Set[UUID]:
        """Observers whose last view grants any of these cells (wall field, felt cells, volume routes)."""
        return _granted_at(self._grants, positions)

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
        grants = self._identity_grants.get((subject_uuid, position))
        if grants is None:
            holders = self.contact_holders(subject_uuid, _granted_at(self._grants, (position,)))
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
                             and any(has_route(senses.paths, position) or has_route(senses.safe_paths, position)
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
            group = EventQueue.open_group()
            if self._absorbing_light and group is not None and event.event_type in (
                    EventType.SPATIAL_LIGHT_CHANGED, EventType.SPATIAL_LIGHT_SOURCES_CHANGED):
                # The group's own light fact is its last: the group settles with it, before it completes;
                # what its consumers do then reduces as after the group.
                self._absorbing_light, self._settled_with_light = False, True
                self._settle_recorded(group)
            return
        if _perception_inert(event):
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
        shared: SharedValues = {}
        events = {identity: [event] for identity in observers}
        settled = self._settle(observers, events, shared=shared)
        sensory_events = self._emit_settlement(observers, settled, events, event, shared)
        if sensory_events:
            EventQueue.register_completion_sequence(sensory_events)
            self.published_observers.update(event.observer_uuid for event in sensory_events)

    def _settle(self, observers: Sequence[UUID], events: Mapping[UUID, Sequence[Event]], *,
                shared: SharedValues,
                ) -> Dict[UUID, Tuple[PublishedSenses, Dict[UUID, Optional[PerceivedSpatialEffect]]]]:
        """Recompute every observer of one settlement; returns each one's prior published state
        and the prior values of the fixtures it re-observed."""
        befores = {identity: published_senses(self.senses_by_observer[identity]) for identity in observers}
        affected = {identity: self._affected_cells(events[identity]) for identity in observers}
        # The target table re-reads the cells the facts name (the same cells as the fixtures).
        table_cells: Optional[Set[Position]] = set()
        for identity in observers:
            cells = affected[identity]
            if cells is None:
                table_cells = None
                break
            table_cells |= cells
        touched = self._recompute(observers, affected, shared, table_cells)
        return {identity: (befores[identity], touched[identity]) for identity in observers}

    def _emit_settlement(self, observers: Sequence[UUID],
                         settled: Mapping[UUID, Tuple[PublishedSenses, Dict[UUID, Optional[PerceivedSpatialEffect]]]],
                         events: Mapping[UUID, Sequence[Event]], cause: Optional[Event],
                         shared: SharedValues) -> List[SensoryUpdateEvent]:
        """Every settled observer's sensory event; an observer settled without facts publishes a
        refresh, registered at once. Returns the settled events (registered by the caller as one
        completion sequence)."""
        diagnostic = action_timing_enabled()
        sensory_events: List[SensoryUpdateEvent] = []
        for observer_uuid in observers:
            after = published_senses(self.senses_by_observer[observer_uuid])
            initial = observer_uuid not in self.published_observers
            started = time.perf_counter() if diagnostic else 0.0
            change = _cell_change(settled[observer_uuid][0], after, initial)
            if diagnostic:
                record_action_timing("sensory.settlement.cell_changes_ms", started)
            if not events[observer_uuid]:
                self._emit_refresh(observer_uuid, settled[observer_uuid][0], after, initial, change)
                continue
            sensory_event = self._emit_settled(observer_uuid, settled[observer_uuid], after, initial, change,
                                               events[observer_uuid], cause, shared)
            if sensory_event is not None:
                sensory_events.append(sensory_event)
        return sensory_events

    def _emit_settled(self, observer_uuid: UUID,
                      settled: Tuple[PublishedSenses, Dict[UUID, Optional[PerceivedSpatialEffect]]],
                      after: PublishedSenses, initial: bool, change: CellChange,
                      events: Sequence[Event], cause: Optional[Event],
                      shared: SharedValues) -> Optional[SensoryUpdateEvent]:
        """Emit the difference of one observer's published perception."""
        senses = self.senses_by_observer[observer_uuid]
        before, effect_before = settled
        contact_changes = self.fields[observer_uuid].contact_changes
        entity_delta = _contact_delta(before.entities, after.entities, initial,
                                      contact_changes[0] if contact_changes is not None else None)
        object_delta = _contact_delta(before.objects, after.objects, initial,
                                      contact_changes[1] if contact_changes is not None else None)
        # Only the fixtures this settlement re-observed can change (an initial update carries all).
        before = _replace_effects(before, {identity: value for identity, value in effect_before.items()
                                           if value is not None})
        if not initial:
            after = _replace_effects(after, {identity: senses.spatial_effects[identity]
                                             for identity in set(effect_before) if identity in senses.spatial_effects})
        projection_changed = any((
            before.position != after.position,
            change.visible_differs,
            change.seen_differs,
            bool(entity_delta[0] or entity_delta[1]) if not initial else before.entities != after.entities,
            bool(object_delta[0] or object_delta[1]) if not initial else before.objects != after.objects,
            before.passive_perception != after.passive_perception,
            change.hazard_differs,
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
            cells=change,
            shared=shared,
            contact_deltas=(entity_delta, object_delta),
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
        self._recompute([observer_uuid], {observer_uuid: None}, {}, None)

    def publish_observer_refresh(
        self, observer_uuid: UUID, before: PublishedSenses,
    ) -> Optional[SensoryUpdateEvent]:
        """Record an independent explicit refresh after existing cache updates."""
        senses = self.senses_by_observer.get(observer_uuid)
        if senses is None:
            return None
        after = published_senses(senses)
        initial = observer_uuid not in self.published_observers
        started = time.perf_counter() if action_timing_enabled() else 0.0
        change = _cell_change(before, after, initial)
        if action_timing_enabled():
            record_action_timing("sensory.settlement.cell_changes_ms", started)
        return self._emit_refresh(observer_uuid, before, after, initial, change)

    def _emit_refresh(self, observer_uuid: UUID, before: PublishedSenses, after: PublishedSenses, initial: bool,
                      change: CellChange) -> Optional[SensoryUpdateEvent]:
        event = emit_sensory_update_delta(observer_uuid, None, before, after, SensoryUpdateReason.UNKNOWN,
                                          initial=initial, cells=change)
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
        if grid is not self._map:
            # A replaced map: every field and table read the old one.
            self.fields.clear()
            self._grants = None
            self._identity_grants.clear()
            self._light_table = None
            self._table = None
            self._map = grid
        exists = grid.cell_exists
        grid.settle_obscurement_activity()
        hazard_owners, hazard_x, hazard_y, hazard_owner = grid.hazard_owners()
        light_rows = tuple(grid.light_source_rows())
        # A table whose every row held is the same table: an observer's emitters then compare by identity.
        lights = self._light_table
        if lights is None or lights.key != light_rows:
            lights = self._light_table = LightSourceTable(
                tuple(LightSourceRow(identity, anchor, values) for identity, anchor, _, values in light_rows),
                np.array([slot for _, _, slot, _ in light_rows], dtype=np.int64),
                np.array([self._target_key(anchor, True) if anchor is not None else -1
                          for _, anchor, _, _ in light_rows], dtype=np.int64),
                np.array([self._target_key(anchor, False) if anchor is not None else -1
                          for _, anchor, _, _ in light_rows], dtype=np.int64),
                light_rows)
        return SettlementWorld(exists, grid.cell_light, grid.obscurement_layers(), grid.cell_obscurement,
                               hazard_owners, hazard_x, hazard_y, hazard_owner, lights,
                               grid.optical_revision, grid.propagation_revision, grid.sight_grid_revision,
                               grid.light_grid_revision)

    def _recompute(self, observers: Sequence[UUID], affected: Mapping[UUID, Optional[Set[Position]]],
                   shared: SharedValues, table_cells: Optional[Set[Position]],
                   ) -> Dict[UUID, Dict[UUID, Optional[PerceivedSpatialEffect]]]:
        """Recompute the observers' views with one settlement world and one target table."""
        diagnostic = action_timing_enabled()
        # The passive-perception rule runs before any world read: its contextual inputs may commit
        # world changes, which this settlement's world and target table then include.
        started = time.perf_counter() if diagnostic else 0.0
        passives = {}
        for observer_uuid in observers:
            owner = BaseBlock.get(observer_uuid)
            assert owner is not None
            passives[observer_uuid] = owner.get_passive_perception()
        if diagnostic:
            record_action_timing("sensory.settlement.passive_ms", started)
        started = time.perf_counter() if diagnostic else 0.0
        world = self._world()
        if diagnostic:
            record_action_timing("sensory.settlement.world_ms", started)
        views = []
        for observer_uuid in observers:
            record_action_count("sensory.observer_settled", 1)
            started = time.perf_counter() if diagnostic else 0.0
            views.append(self._view(observer_uuid, world))
            if diagnostic:
                record_action_timing("sensory.recompute.view_ms", started)
        started = time.perf_counter() if diagnostic else 0.0
        previous_table = self._table
        table = self._target_table(world, table_cells)
        if table is not previous_table:
            self._table_changes = (_changed_targets(previous_table, table) if previous_table is not None
                                   else np.zeros(0, dtype=np.int64))
            self._table, self._table_version = table, self._table_version + 1
        if diagnostic:
            record_action_timing("sensory.settlement.contact_table_ms", started)
        started = time.perf_counter() if diagnostic else 0.0
        named: Dict[FrozenSet[Position], np.ndarray] = {}
        changed: List[Optional[np.ndarray]] = []
        volatile = table.target_key[table.volatile]
        for view in views:
            field, cells = view.field, affected[view.owner.uuid]
            # The table versions the published contacts can be compared with: the current one, or the
            # one before it through the update's changed targets.
            base = (np.zeros(0, dtype=np.int64) if field.table_version == self._table_version
                    else self._table_changes if field.table_version == self._table_version - 1 else None)
            if view.frame_changes is not None and cells is not None and base is not None \
                    and field.passive == passives[view.owner.uuid]:
                # The sight and passive perception held: only the targets whose rows differ between
                # the two tables, which stand on a cell the facts name or whose visibility or senses
                # changed, or whose observability rule reads the world, can change contact.
                cells_key = frozenset(cells)
                at = named.get(cells_key)
                if at is None:
                    at = named[cells_key] = _targets_at(table, cells_key)
                seen_at = _targets_at(table, view.frame_changes) if view.frame_changes else at[:0]
                changed.append(np.unique(np.concatenate((base, at, seen_at, volatile))))
                record_action_count("sensory.contacts.incremental", 1)
            else:
                changed.append(None)
        contacts = self._contacts(views, table, [passives[view.owner.uuid] for view in views], changed, shared)
        if diagnostic:
            record_action_timing("sensory.settlement.contacts_ms", started)
        # The views publish stage by stage, each stage over every view: cells, volume sight, fixtures,
        # emitters, then grants and fields. Every rule hook a stage asks (hazards, fixture observations
        # and hazard perception) reads the observer's own published senses, which the earlier stages
        # wrote for every view, or the objective world, which no stage writes; no fact is stored while
        # they run.
        started = time.perf_counter() if diagnostic else 0.0
        before_visible = [self._publish_cells(view, world, passives[view.owner.uuid], resolved)
                          for view, resolved in zip(views, contacts)]
        if diagnostic:
            record_action_timing("sensory.recompute.cells_ms", started)
            started = time.perf_counter()
        sights = [self._volume_sight(view, world) for view in views]
        if diagnostic:
            record_action_timing("sensory.recompute.volume_geometry_ms", started)
            started = time.perf_counter()
        stack = _visible_stack(before_visible, [view.senses.cells.visible for view in views])
        effects = self._refresh_spatial_effects(views, sights, before_visible, affected, passives, contacts, stack)
        if diagnostic:
            record_action_timing("sensory.recompute.spatial_effects_ms", started)
            started = time.perf_counter()
        lights = self._refresh_light_sources(views, world, contacts, shared, stack)
        if diagnostic:
            record_action_timing("sensory.recompute.light_sources_ms", started)
        touched: Dict[UUID, Dict[UUID, Optional[PerceivedSpatialEffect]]] = {}
        grants: Dict[UUID, Optional[CellLayer]] = {}
        for view, (_, _, contact_rows, contact_uuids, contact_changes), (volumes, upper, volume_grants), effect_before, \
                (light_inputs, light_values) in zip(views, contacts, sights, effects, lights):
            observer_uuid, field = view.owner.uuid, view.field
            grants[observer_uuid] = _granted_cells(view, volume_grants)
            self.fields[observer_uuid] = ObserverField(
                field.origin, field.window, field.selection, field.optical_key, field.routes, field.felt_keys,
                field.felt_rows, field.sight_inputs, field.sight, field.light, field.light_version, field.optical,
                field.exists_frame, field.felt_frame, field.seen_frame, field.senses_frame,
                contact_rows, contact_uuids, contact_changes, self._table_version, passives[observer_uuid],
                light_values, light_inputs, volumes, upper)
            touched[observer_uuid] = effect_before
        # The grants are written once the settlement is published.
        self._grants = _replace_grants(self._grants, grants)
        self._identity_grants.clear()
        return touched

    def _view(self, observer_uuid: UUID, world: SettlementWorld) -> ObserverView:
        """Optical and felt cells of one observer, as arrays: the sight stage runs when its inputs
        changed, the light stage when the sight or the light over the window changed."""
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
        optical_radius = sense_radius_cells(0, max_distance) if ordinary_sight else 0
        for sense_type in (SensesType.DARKVISION, SensesType.DEVILS_SIGHT, SensesType.TRUESIGHT):
            sense_range = modes.get(sense_type)
            if sense_range is not None:
                optical_radius = max(optical_radius, sense_radius_cells(sense_range, max_distance))
        reach = optical_radius if visual_access else 0
        felt_radii = [(sense_type, bit, sense_radius_cells(modes[sense_type], max_distance))
                      for sense_type, bit in NONVISUAL_SENSES if sense_type in modes]
        for _, _, radius in felt_radii:
            reach = max(reach, radius)
        cell_box = world.exists.box
        window = (max(origin[0] - reach, cell_box[0]), max(origin[1] - reach, cell_box[1]),
                  min(origin[0] + reach, cell_box[2]), min(origin[1] + reach, cell_box[3]))
        selection = (origin[0] - reach - 1, origin[1] - reach - 1, origin[0] + reach + 1, origin[1] + reach + 1)
        scalars = (origin, max_distance, tuple(sorted(modes.items())), ordinary_sight, visual_access,
                   world.optical_revision, world.propagation_revision, window)
        previous = self.fields.get(observer_uuid)
        if previous is not None and previous.sight_inputs.scalars == scalars:
            held = previous.sight_inputs
            inputs = held if held.version == world.sight_version else SightInputs(
                scalars, _window_values(world.exists, window), _window_values(world.obscurement, window),
                world.sight_version)
            light = _held_values(previous.light, previous.light_version, world.light_version, world.light, window)
        else:
            inputs = SightInputs(scalars, _window_values(world.exists, window),
                                 _window_values(world.obscurement, window), world.sight_version)
            light = _window_values(world.light, window)
        optical_key = (origin, optical_radius if visual_access else 0, world.optical_revision)
        if previous is not None and (inputs is previous.sight_inputs or _same_sight_inputs(previous.sight_inputs, inputs)):
            routes, sight = previous.routes, previous.sight
            felt_keys, felt_rows, felt_frame = previous.felt_keys, previous.felt_rows, previous.felt_frame
            exists = previous.exists_frame
            lit_kept = light is previous.light or np.array_equal(previous.light, light)
            sight_kept = True
        else:
            record_action_count("sensory.full_recompute", 1)
            if previous is not None and previous.optical_key == optical_key:
                routes = previous.routes
            else:
                fov = grid.compute_fov(origin, optical_radius) if visual_access and optical_radius > 0 else []
                routes = route_rows(frame_rows(np.array(fov, dtype=np.int64).reshape(-1, 2), origin))
            exists = frame_of(world.exists, origin)
            sight = route_sight(routes, modes, ordinary_sight, exists, frame_of(world.obscurement, origin))
            keys: List[Tuple[SensesType, Tuple[Position, int, int]]] = []
            rows_of: List[np.ndarray] = []
            felt_frame = np.zeros(OFF + 1, dtype=np.uint8)
            previous_felt = dict(zip(previous.felt_keys, previous.felt_rows)) if previous is not None else {}
            for sense_type, bit, radius in felt_radii:
                key = (sense_type, (origin, radius, world.propagation_revision))
                rows = previous_felt.get(key)
                if rows is None:
                    rows = frame_rows(np.array(grid.compute_propagation_fov(origin, radius),
                                               dtype=np.int64).reshape(-1, 2), origin)
                keys.append(key)
                rows_of.append(rows)
                felt_frame[rows] |= bit
            felt_keys, felt_rows = tuple(keys), tuple(rows_of)
            lit_kept = sight_kept = False
        frame_changes: Optional[Set[Position]] = set() if sight_kept else None
        if lit_kept:
            optical, seen_frame, senses_frame = previous.optical, previous.seen_frame, previous.senses_frame
            frames_kept = True
        else:
            record_action_count("sensory.light_recompute", 1)
            optical = lit_view(sight, exists, frame_of(world.light, origin))
            # A light change that moves no visible cell and no eligibility keeps the contacts' view.
            frames_kept = (sight_kept and np.array_equal(optical.rows, previous.optical.rows)
                           and np.array_equal(optical.eligibility, previous.optical.eligibility))
            if frames_kept:
                seen_frame, senses_frame = previous.seen_frame, previous.senses_frame
            else:
                seen_frame = np.zeros(OFF + 1, dtype=bool)
                seen_frame[optical.rows] = True
                senses_frame = np.zeros(OFF + 1, dtype=np.uint8)
                senses_frame[optical.rows] = ELIGIBLE_SENSE_BITS[optical.eligibility]
                if sight_kept:
                    moved = np.flatnonzero((seen_frame != previous.seen_frame) | (senses_frame != previous.senses_frame))
                    frame_changes = set(rows_positions(moved, origin))
        field = ObserverField(origin, window, selection, optical_key, routes, felt_keys, felt_rows, inputs, sight,
                              light, world.light_version, optical, exists, felt_frame, seen_frame, senses_frame,
                              previous.contact_rows if previous is not None else NO_CONTACT_ROWS,
                              previous.contact_uuids if previous is not None else NO_UUIDS, None,
                              previous.table_version if previous is not None else None,
                              previous.passive if previous is not None else None,
                              previous.light_values if previous is not None else {},
                              previous.light_inputs if previous is not None else None,
                              previous.volumes if previous is not None else {},
                              previous.upper if previous is not None else {})
        return ObserverView(owner, senses, origin, modes, ordinary_sight, optical_radius if visual_access else 0,
                            field, previous is not None, lit_kept, frames_kept, frame_changes, optical, exists,
                            seen_frame,
                            senses_frame, felt_frame)

    def _target_table(self, world: SettlementWorld, named: Optional[Set[Position]]) -> ContactTable:
        """The settlement's contact targets. The kept table is updated at the cells the settlement's
        facts name: their occupancy, their targets' facts, and the boundary sides at and beside
        them; a fact that names no cells, a first settlement or a grown map builds it afresh."""
        grid = get_map()
        box = world.exists.box
        previous = self._table
        incremental = previous is not None and named is not None and previous.box == box
        if incremental and not named:
            return previous
        facts: Dict[Tuple[UUID, bool], Optional[TargetFacts]] = {}

        def target(identity: UUID, as_entity: bool) -> Optional[TargetFacts]:
            key = (identity, as_entity)
            if key not in facts:
                block = BaseBlock.get(identity)
                listed = block is not None and (block.appears_in_entity_contacts() if as_entity
                                                else block.should_include_in_senses_objects())
                facts[key] = (block, self._target_key(identity, as_entity),
                              STEALTH_NONE if block.stealth_dc is None else block.stealth_dc, block.is_invisible,
                              block.observability_reads_the_world()) if listed else None
            return facts[key]

        if not world.exists.values.size:
            cell_entries, side_entries = [], []
        elif incremental:
            assert previous is not None and named is not None
            sided = set(named)
            sided.update((x + dx, y + dy) for x, y in named for dx, dy in DELTAS.values())
            cell_entries = grid.contact_cells_at(named)
            side_entries = grid.boundary_sides_at(sided)
        else:
            cell_entries = grid.contact_cells_in_box(box)
            side_entries = grid.boundary_sides_in_box(box)
        cells: List[Tuple[UUID, bool, int, int, int]] = []
        for (x, y), (entity_ids, object_ids) in cell_entries:
            for identity in entity_ids:
                if target(identity, True) is not None:
                    cells.append((identity, True, x, y, ROW_ENTITY))
            for identity in object_ids:
                if target(identity, False) is not None:
                    cells.append((identity, False, x, y, ROW_OBJECT))
        sides: List[Tuple[Any, ...]] = []
        width, height = world.exists.values.shape
        for (x, y), direction, side_objects in side_entries:
            dx, dy = DELTAS[direction]
            i, j = x - box[0], y - box[1]
            across_inside = 0 <= i + dx < width and 0 <= j + dy < height
            across_tile = across_inside and bool(world.exists.values[i + dx, j + dy])
            channels = self._open_channels(grid, (x, y), direction) if across_tile else ()
            for identity in side_objects:
                placement = grid.get_object_placement(identity) if target(identity, False) is not None else None
                if placement is None or placement.boundary_direction is None:
                    continue
                sides.append((identity, x, y, x + dx, y + dy, across_tile, WorldEdgeChannel.OPTICAL in channels,
                              WorldEdgeChannel.PROPAGATION in channels, *placement.position))
        kept_cells = kept_sides = None
        if incremental:
            assert previous is not None and named is not None
            # Every other row and every other target's facts are the kept table's.
            def named_at(xs: np.ndarray, ys: np.ndarray, cells_named: Set[Position]) -> np.ndarray:
                named_array = np.array(list(cells_named), dtype=np.int64).reshape(-1, 2)
                return np.isin(_pack_cells(np.zeros(xs.size, dtype=np.int64), xs, ys),
                               _pack_cells(np.zeros(named_array.shape[0], dtype=np.int64),
                                           named_array[:, 0], named_array[:, 1]))
            kept_cells = ~named_at(previous.cell_x, previous.cell_y, named)
            kept_sides = ~named_at(previous.side_x, previous.side_y, sided)
            for index, kind in zip(previous.cell_target[~kept_cells].tolist(),
                                   previous.cell_kind[~kept_cells].tolist()):
                target(previous.uuids[index], kind == ROW_ENTITY)
            for index in previous.side_target[~kept_sides].tolist():
                target(previous.uuids[index], False)
            kept_targets = np.unique(np.concatenate((previous.cell_target[kept_cells],
                                                     previous.side_target[kept_sides]))).tolist()
            entity_of = {index: identity for identity, index in previous.entity_index.items()}
            for index in kept_targets:
                key = (previous.uuids[index], entity_of.get(index) == previous.uuids[index])
                if key not in facts:
                    facts[key] = (previous.blocks[index], int(previous.target_key[index]), int(previous.stealth[index]),
                                  bool(previous.invisible[index]), bool(previous.volatile[index]))
        listed = [(identity, as_entity, values) for (identity, as_entity), values in facts.items() if values is not None]
        index_of = {(identity, as_entity): index for index, (identity, as_entity, _) in enumerate(listed)}
        cell_rows = [(x, y, index_of[(identity, as_entity)], kind) for identity, as_entity, x, y, kind in cells]
        side_rows = [(x, y, ax, ay, tile, optical, propagation, index_of[(identity, False)], px, py)
                     for identity, x, y, ax, ay, tile, optical, propagation, px, py in sides]
        cell_array = np.array(cell_rows, dtype=np.int64).reshape(-1, 4)
        side_array = np.array(side_rows, dtype=np.int64).reshape(-1, 10)
        if incremental:
            assert previous is not None and kept_cells is not None and kept_sides is not None
            # The kept rows, re-indexed; a target no longer listed loses them.
            remap = np.array([index_of.get((identity, as_entity), -1)
                              for (identity, as_entity), _ in sorted(previous.targets.items(), key=lambda item: item[1])],
                             dtype=np.int64)
            old_cells = np.column_stack((previous.cell_x, previous.cell_y, remap[previous.cell_target],
                                         previous.cell_kind)).astype(np.int64).reshape(-1, 4)[kept_cells]
            old_sides = np.column_stack((previous.side_x, previous.side_y, previous.across_x, previous.across_y,
                                         previous.across_tile, previous.across_optical, previous.across_propagation,
                                         remap[previous.side_target], previous.side_position_x,
                                         previous.side_position_y)).astype(np.int64).reshape(-1, 10)[kept_sides]
            cell_array = np.concatenate((old_cells[old_cells[:, 2] >= 0], cell_array))
            side_array = np.concatenate((old_sides[old_sides[:, 7] >= 0], side_array))
        return _contact_table_value(box, listed, cell_array, side_array)

    def _publish_cells(self, view: ObserverView, world: SettlementWorld, passive: int,
                       resolved: ResolvedContacts) -> CellLayer:
        """Hazards, cells, seen cells and contacts of one view, published on its Senses.
        Returns the visible cells it published before."""
        owner, senses, origin = view.owner, view.senses, view.origin
        observer_uuid = owner.uuid
        entities, objects, _, _, _ = resolved
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
        # Each published layer that held is kept (the same object): a stage that did not run, or
        # ran to the same values, changes nothing downstream.
        published = senses.cells
        same_window = (published.visible.x0, published.visible.y0) == window[:2] and \
            published.visible.values.shape == (window[2] - window[0] + 1, window[3] - window[1] + 1)

        def kept_layer(values: np.ndarray, layer: CellLayer) -> CellLayer:
            if same_window and np.array_equal(layer.values, values):
                return layer
            return CellLayer(window[0], window[1], values)
        if view.lit_kept and same_window:
            visible, light, eligibility = published.visible, published.light, published.eligibility
        else:
            light_frame = np.zeros(OFF + 1, dtype=np.uint8)
            light_frame[view.optical.rows] = view.optical.light
            eligibility_frame = np.zeros(OFF + 1, dtype=np.uint8)
            eligibility_frame[view.optical.rows] = view.optical.eligibility
            visible = kept_layer(window_of(view.seen_frame, origin, window), published.visible)
            light = kept_layer(window_of(light_frame, origin, window), published.light)
            eligibility = kept_layer(window_of(eligibility_frame, origin, window), published.eligibility)
        hazard = kept_layer(window_of(hazard_frame, origin, window), published.hazard)
        if (visible is published.visible and light is published.light and eligibility is published.eligibility
                and hazard is published.hazard):
            cells = published
        else:
            cells = PerceivedCells(visible, light, eligibility, hazard)
        before_visible = published.visible
        if cells.visible is not before_visible:
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
        return before_visible

    def _contacts(self, views: Sequence[ObserverView], table: ContactTable, passives: Sequence[int],
                  changed: Sequence[Optional[np.ndarray]], shared: SharedValues,
                  ) -> List[ResolvedContacts]:
        """Every view's entity and object contacts, as evidence rows over the settlement's table.

        A target's contact is a function of the observer's view and of that target's rows (its
        cells or side and its facts). For a view with changed target keys (its view and passive
        perception having held), only those targets' rows are resolved again and every other row
        is the published one; a view without them resolves every row. All views' (observer, row)
        pairs are resolved as one set of arrays: the per-target rules (hiding, invisibility,
        boundary evidence) are masks; Python runs per resolved (observer, target) and per changed
        contact. A row is kind, uuid halves, x, y, visual, senses, target key."""
        grid = get_map()
        count = len(views)
        observers = np.arange(count, dtype=np.int64)
        # The (observer, table row) pairs resolved now; equal changed sets select their rows once.
        selected_rows: Dict[bytes, Tuple[np.ndarray, np.ndarray]] = {}
        every = (np.arange(table.cell_target.size), np.arange(table.side_target.size))
        parts = []
        for keys in changed:
            if keys is None:
                parts.append(every)
                continue
            memo = keys.tobytes()
            rows_of = selected_rows.get(memo)
            if rows_of is None:
                rows_of = selected_rows[memo] = (np.flatnonzero(np.isin(table.cell_target_key, keys)),
                                                 np.flatnonzero(np.isin(table.side_target_key, keys)))
            parts.append(rows_of)
        cell_obs = np.repeat(observers, [cells.size for cells, _ in parts])
        side_obs = np.repeat(observers, [sides.size for _, sides in parts])
        cell_rows = np.concatenate([cells for cells, _ in parts]).astype(np.int64)
        side_rows = np.concatenate([sides for _, sides in parts]).astype(np.int64)
        origin_x = np.array([view.origin[0] for view in views], dtype=np.int64)
        origin_y = np.array([view.origin[1] for view in views], dtype=np.int64)
        seen = np.stack([view.seen_frame for view in views]).reshape(-1)
        established = np.stack([view.senses_frame for view in views]).reshape(-1)
        felt = np.stack([view.felt_frame for view in views]).reshape(-1)

        def frame(obs: np.ndarray, xs: np.ndarray, ys: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
            """Each pair's frame row and its index in the stacked frames."""
            rows = frame_index(xs, ys, (origin_x[obs], origin_y[obs]))
            return rows, obs * (OFF + 1) + rows

        def sense_range(sense: SensesType) -> np.ndarray:
            return np.array([view.modes.get(sense, -1) for view in views], dtype=np.int64)
        truesight, see_invisible = sense_range(SensesType.TRUESIGHT), sense_range(SensesType.SEE_INVISIBLE)

        def reveals(obs: np.ndarray, rows: np.ndarray) -> np.ndarray:
            distance = FRAME_DISTANCE_FEET[rows]
            return ((truesight[obs] == 0) | ((truesight[obs] > 0) & (distance <= truesight[obs]))
                    | (see_invisible[obs] == 0) | ((see_invisible[obs] > 0) & (distance <= see_invisible[obs])))

        passive = np.array(passives, dtype=np.int64)
        own_index = np.array([table.entity_index.get(view.owner.uuid, -1) for view in views], dtype=np.int64)
        # Cell rows: the cell's own evidence.
        cell_x, cell_y = table.cell_x[cell_rows], table.cell_y[cell_rows]
        cell_kind, cell_target = table.cell_kind[cell_rows], table.cell_target[cell_rows]
        rows, at = frame(cell_obs, cell_x, cell_y)
        cell_visual = seen[at] & (reveals(cell_obs, rows) | ~table.invisible[cell_target])
        cell_mask = np.where(cell_visual, established[at], 0) | felt[at]
        cell_keep = ((table.stealth[cell_target] < passive[cell_obs]) & (cell_visual | (cell_mask != 0))
                     & ~((cell_kind == ROW_ENTITY) & (cell_target == own_index[cell_obs])))
        # Side rows: a side is reached from its owner Tile, and from across unless the far Tile's
        # exit layer blocks the channel.
        side_target = table.side_target[side_rows]
        own_rows, own = frame(side_obs, table.side_x[side_rows], table.side_y[side_rows])
        across_rows, across = frame(side_obs, table.across_x[side_rows], table.across_y[side_rows])
        own_optical = seen[own]
        own_felt = felt[own]
        across_tile = table.across_tile[side_rows]
        across_optical = seen[across] & across_tile & table.across_optical[side_rows]
        across_felt = felt[across]
        across_propagation = (across_felt != 0) & across_tile & table.across_propagation[side_rows]
        hidden = table.invisible[side_target]
        visual_own = own_optical & (reveals(side_obs, own_rows) | ~hidden)
        visual_across = across_optical & (reveals(side_obs, across_rows) | ~hidden)
        side_visual = visual_own | visual_across
        side_mask = (np.where(visual_own, established[own], 0) | np.where(visual_across, established[across], 0)
                     | np.where(own_optical | (own_felt != 0), own_felt, 0)
                     | np.where(across_optical | across_propagation, across_felt, 0))
        side_keep = (table.stealth[side_target] < passive[side_obs]) & (side_visual | (side_mask != 0))
        # Observability is the target's own rule, asked once per kept (observer, target).
        targets = max(len(table.blocks), 1)
        cell_pairs, side_pairs = cell_obs * targets + cell_target, side_obs * targets + side_target
        kept_pairs = np.unique(np.concatenate((cell_pairs[cell_keep], side_pairs[side_keep])))
        hidden_pairs = [pair for pair, obs, target in zip(kept_pairs.tolist(), (kept_pairs // targets).tolist(),
                                                          (kept_pairs % targets).tolist())
                        if not table.blocks[target].is_observable_to(views[obs].owner.uuid)]
        if hidden_pairs:
            cell_keep &= ~np.isin(cell_pairs, hidden_pairs)
            side_keep &= ~np.isin(side_pairs, hidden_pairs)
        halves = table.uuid_halves.astype(np.int64)
        resolved_cells = np.column_stack((cell_kind, halves[cell_target], cell_x, cell_y, cell_visual, cell_mask,
                                          table.target_key[cell_target])).astype(np.int64).reshape(-1, 8)[cell_keep]
        resolved_sides = np.column_stack((np.full(side_rows.size, ROW_SIDE), halves[side_target],
                                          table.side_position_x[side_rows], table.side_position_y[side_rows],
                                          side_visual, side_mask, table.target_key[side_target]
                                          )).astype(np.int64).reshape(-1, 8)[side_keep]
        cell_uuids, side_uuids = table.uuid_objects[cell_target[cell_keep]], table.uuid_objects[side_target[side_keep]]
        cell_obs, side_obs = cell_obs[cell_keep], side_obs[side_keep]
        # Explicit construction knowledge is not visual sight or truesight.
        # Only the declaring creator receives this otherwise invisible contact.
        known: List[Tuple[int, int, UUID, Position]] = []
        for obs, view in enumerate(views):
            observer_uuid = view.owner.uuid
            for identity in grid.get_known_object_candidates(observer_uuid):
                subject = BaseBlock.get(identity)
                placement = grid.get_object_placement(identity)
                if subject is not None and placement is not None and subject.is_object_known_to(observer_uuid):
                    known.append((obs, len(known), identity, placement.position))
        known_rows = np.zeros((len(known), 8), dtype=np.int64)
        known_obs = np.array([obs for obs, _, _, _ in known], dtype=np.int64)
        known_uuids = np.empty(len(known), dtype=object)
        if known:
            known_rows[:, 0] = ROW_KNOWN
            known_rows[:, 1:3] = np.array([(identity.int >> 64, identity.int & UUID_LOW)
                                           for _, _, identity, _ in known], dtype=np.uint64).astype(np.int64)
            known_rows[:, 3:5] = [position for _, _, _, position in known]
            known_rows[:, 7] = [self._target_key(identity, False) for _, _, identity, _ in known]
            known_uuids[:] = [identity for _, _, identity, _ in known]
        # The published rows; a view with changed keys keeps those of its unchanged targets.
        previous_rows = np.concatenate([view.field.contact_rows for view in views]).reshape(-1, 8)
        previous_uuids = np.concatenate([view.field.contact_uuids for view in views])
        previous_obs = np.repeat(observers, [view.field.contact_rows.shape[0] for view in views])
        key_space = int(max(previous_rows[:, 7].max(initial=0), table.target_key.max(initial=0),
                            known_rows[:, 7].max(initial=0))) + 1
        full = np.array([keys is None for keys in changed], dtype=bool)
        changed_pairs = np.concatenate([obs * key_space + keys for obs, keys in enumerate(changed)
                                        if keys is not None] or [np.zeros(0, dtype=np.int64)])

        def is_changed(obs: np.ndarray, keys: np.ndarray, kinds: np.ndarray) -> np.ndarray:
            """Rows resolved now: a full view's, a changed target's, and construction knowledge."""
            return full[obs] | np.isin(obs * key_space + keys, changed_pairs) | (kinds == ROW_KNOWN)
        compared = is_changed(previous_obs, previous_rows[:, 7], previous_rows[:, 0])
        kept = ~compared
        merged = np.concatenate((previous_rows[kept], resolved_cells, known_rows, resolved_sides))
        merged_uuids = np.concatenate((previous_uuids[kept], cell_uuids, known_uuids, side_uuids))
        merged_obs = np.concatenate((previous_obs[kept], cell_obs, known_obs, side_obs))
        merged_known = np.concatenate((np.zeros(int(kept.sum()) + resolved_cells.shape[0], dtype=np.int64),
                                       np.array([order for _, order, _, _ in known], dtype=np.int64),
                                       np.zeros(resolved_sides.shape[0], dtype=np.int64)))
        # Evidence order per view: cells x-major, within a cell entities then objects each in str
        # order (the cell's own order), construction knowledge, sides by target. str(uuid) order is
        # the order of the 128-bit value: the halves compare unsigned.
        kind = merged[:, 0]
        is_cell, is_side = kind <= ROW_OBJECT, kind == ROW_SIDE
        category = np.where(is_cell, 0, np.where(is_side, 2, 1))
        unsigned = (merged[:, 1:3].view(np.uint64) ^ np.uint64(1 << 63)).view(np.int64)
        first = np.where(is_cell, merged[:, 3], np.where(is_side, 0, merged_known))
        second = np.where(is_cell, merged[:, 4], 0)
        within = np.where(is_cell, kind, 0)
        order = np.lexsort((unsigned[:, 1], unsigned[:, 0], within, second, first, category, merged_obs))
        merged, merged_uuids, merged_obs = merged[order], merged_uuids[order], merged_obs[order]
        # The resolved rows against the published rows of the same targets: a target whose rows all
        # held keeps its contact.
        resolved = is_changed(merged_obs, merged[:, 7], merged[:, 0])
        new_changed = np.zeros(merged.shape[0], dtype=bool)
        old_changed = np.zeros(previous_rows.shape[0], dtype=bool)
        now = _row_identity(merged_obs[resolved], merged[resolved])
        before = _row_identity(previous_obs[compared], previous_rows[compared])
        new_changed[resolved] = ~_rows_in(now, before)
        old_changed[compared] = ~_rows_in(before, now)
        return _contact_maps(views, merged, merged_uuids, merged_obs, new_changed,
                             previous_rows, previous_uuids, previous_obs, old_changed, shared)

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
                      ) -> VolumeSights:
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
        steps, lengths = supercover_route_table()
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
                routes = steps[picked, :int(lengths[picked].max())] >> ROUTE_STEP_SHIFT
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
        self, views: Sequence[ObserverView], sights: Sequence[VolumeSights], before_visible: Sequence[CellLayer],
        affected: Mapping[UUID, Optional[Set[Position]]], passives: Mapping[UUID, int],
        resolved: Sequence[ResolvedContacts], stack: VisibleStack,
    ) -> List[Dict[UUID, Optional[PerceivedSpatialEffect]]]:
        """Re-observe every view's fixtures on its newly visible and affected cells, in one pass over the
        stacked views: each spatial condition's footprint meets every view's re-observed cells at once,
        and a view asks only the conditions it meets. Hidden parts keep their last observation. Returns,
        per view, the prior value of every fixture touched (none while its fixtures stand)."""
        grid = get_map()
        box, now, before = stack.box, stack.after, stack.before
        marks = np.zeros(now.shape, dtype=bool)
        named: Dict[FrozenSet[Position], np.ndarray] = {}
        everywhere = np.zeros(len(views), dtype=bool)
        for index, view in enumerate(views):
            cells = affected[view.owner.uuid]
            if cells is None:
                everywhere[index] = True
            elif cells:
                key = frozenset(cells)
                mask = named.get(key)
                if mask is None:
                    mask = named[key] = _cells_mask(key, box)
                marks[index] = mask
        reobserved = now & (everywhere[:, None, None] | ~before | marks)
        changed = reobserved | (before & ~now)
        any_reobserved = reobserved.any(axis=(1, 2)).tolist()
        any_changed = changed.any(axis=(1, 2)).tolist()
        affected_seen = (now & marks).any(axis=(1, 2)).tolist()
        results: List[Dict[UUID, Optional[PerceivedSpatialEffect]]] = [{} for _ in views]
        surfaces_of: Dict[int, Set[Position]] = {}
        # The fixture stage reads the visible cells, the seen volumes and the cells the facts name: while
        # the first two held and no named cell is visible or a volume surface, the published fixtures
        # stand. An observation also reads the observer's contacts (a fixture's anchor) and its passive
        # perception (hazard perception): any contact change or a passive change re-runs the stage.
        for index, (view, (volumes, upper, _), (_, _, _, _, contact_changes)) in enumerate(zip(views, sights, resolved)):
            surfaces = {position for positions in volumes.values() for position in positions}
            surfaces.update(row.position for rows in upper.values() for row in rows)
            cells = affected[view.owner.uuid]
            if not (view.published and view.senses.cells.visible is before_visible[index] and cells is not None
                    and contact_changes == (frozenset(), frozenset()) and view.field.passive == passives[view.owner.uuid]
                    and volumes == view.field.volumes and upper == view.field.upper
                    and not affected_seen[index] and surfaces.isdisjoint(cells)):
                surfaces_of[index] = surfaces
        # A published fixture is touched when it holds volume, upper-surface or suppression cells, or when
        # one of its cells changed.
        touched_of: Dict[int, Set[UUID]] = {}
        for index in surfaces_of:
            touched = touched_of[index] = set()
            for identity, previous in views[index].senses.spatial_effects.items():
                if (previous.visible_volume_positions or previous.upper_volume_surfaces
                        or any(row.positions for row in previous.suppressions)):
                    touched.add(identity)
                elif any_changed[index] and previous.positions and _gather(changed[index], box, previous.positions).any():
                    touched.add(identity)
        # Only a footprint meeting a re-observed cell or a volume surface can be observed now: each
        # condition's footprint is read once, against every observing view.
        live = [index for index, surfaces in surfaces_of.items() if any_reobserved[index] or surfaces]
        candidates_of: Dict[int, Dict[UUID, Tuple[SpatialConditionOwner, Set[Position], Set[Position]]]] = {
            index: {} for index in live}
        if live:
            rows_of = np.array(live, dtype=np.int64)
            reobserved_live = reobserved[rows_of]
            surface_masks = {order: _cells_mask(surfaces_of[index], box) for order, index in enumerate(live)
                             if surfaces_of[index]}
            for condition in grid.get_spatial_conditions():
                footprint = grid.condition_footprint(condition.uuid)
                if footprint is None:
                    continue
                fx0, fy0, fx1, fy1 = footprint.box
                x0, y0, x1, y1 = max(fx0, box[0]), max(fy0, box[1]), min(fx1, box[2]), min(fy1, box[3])
                if x0 > x1 or y0 > y1:
                    continue
                inside_footprint = footprint.values[x0 - fx0:x1 - fx0 + 1, y0 - fy0:y1 - fy0 + 1]
                part = (slice(x0 - box[0], x1 - box[0] + 1), slice(y0 - box[1], y1 - box[1] + 1))
                hit_cells = inside_footprint & reobserved_live[:, part[0], part[1]]
                for order, surface_mask in surface_masks.items():
                    index = live[order]
                    volumes, upper, _ = sights[index]
                    seen_on = now[index]
                    if condition.uuid in volumes or condition.uuid in upper:
                        seen_on = now[index] | _cells_mask(volumes.get(condition.uuid, frozenset()), box) | _cells_mask(
                            [row.position for row in upper.get(condition.uuid, ())], box)
                    hit_cells[order] |= inside_footprint & (surface_mask & seen_on)[part]
                orders, ox, oy = np.nonzero(hit_cells)
                if not orders.size:
                    continue
                shown = now[rows_of[orders], ox + part[0].start, oy + part[1].start].tolist()
                xs, ys = (ox + x0).tolist(), (oy + y0).tolist()
                bounds = np.searchsorted(orders, np.arange(len(live) + 1)).tolist()
                for order, index in enumerate(live):
                    low, high = bounds[order], bounds[order + 1]
                    if low == high:
                        continue
                    observed = list(zip(xs[low:high], ys[low:high]))
                    candidates_of[index][condition.uuid] = (condition, set(observed), {
                        position for position, seen in zip(observed, shown[low:high]) if seen})
        for index, surfaces in surfaces_of.items():
            view = views[index]
            observer_uuid, senses = view.owner.uuid, view.senses
            volumes, upper, _ = sights[index]
            touched = touched_of[index]
            visible_now = now[index]

            def is_visible(position: Position) -> bool:
                i, j = position[0] - box[0], position[1] - box[1]
                return 0 <= i < visible_now.shape[0] and 0 <= j < visible_now.shape[1] and bool(visible_now[i, j])

            if not any_reobserved[index] and not surfaces:
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
                results[index] = before_values
                continue
            candidates = candidates_of[index]
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
                kept = {position for position, again in zip(previous.positions,
                                                        _gather(reobserved[index], box, previous.positions).tolist())
                    if not again}
                observed = observations.pop(identity, None)
                if observed is not None and observed.positions:
                    kept.update(observed.positions)
                if kept:
                    senses.spatial_effects[identity] = (observed or previous).model_copy(
                        update={"positions": tuple(sorted(kept)),
                                "visible_volume_positions": observed.visible_volume_positions if observed is not None else (),
                                "upper_volume_surfaces": observed.upper_volume_surfaces if observed is not None else (),
                                "suppressions": observed.suppressions if observed is not None else tuple(
                                    row.model_copy(update={"positions": tuple(position for position in row.positions
                                        if is_visible(position))}) for row in previous.suppressions)},
                    )
                else:
                    senses.spatial_effects.pop(identity)
            senses.spatial_effects.update(observations)
            results[index] = before_values
        return results

    # ------------------------------------------------------------------ light sources and helpers

    def _refresh_light_sources(
        self, views: Sequence[ObserverView], world: SettlementWorld,
        resolved: Sequence[ResolvedContacts], shared: SharedValues, stack: VisibleStack,
    ) -> List[Tuple[Tuple, Dict[UUID, Tuple]]]:
        """Every view's compact emitter descriptors: the emitters lighting a visible cell; cell
        illumination has its native events. An emitter's anchor is disclosed when the observer sees it
        (its contact rows) or is it. A view's inputs are the settlement's emitter table, its visible
        cells and the targets of its visual contacts: while they hold, its published emitters stand;
        otherwise only the emitters whose row, lighting or anchor disclosure changed are described
        again. The lighting and disclosure of every view are one array pass (the stacked visible
        cells' lit-slot words, OR-ed per view). Returns, per view, those
        inputs with the per-emitter lighting and disclosure, and each published emitter's
        descriptor inputs."""
        grid = get_map()
        lights = world.light_sources
        results: Dict[int, Tuple[Tuple, Dict[UUID, Tuple]]] = {}
        pending: List[int] = []
        visual_keys_of: List[np.ndarray] = []
        for index, (view, (_, _, contact_rows, _, _)) in enumerate(zip(views, resolved)):
            visual_keys = np.sort(contact_rows[contact_rows[:, 5] != 0, 7])
            known = view.field.light_inputs
            if (known is not None and known[0] is lights and known[1] is view.senses.cells.visible
                    and np.array_equal(known[2], visual_keys)):
                results[index] = (known, view.field.light_values)
                continue
            pending.append(index)
            visual_keys_of.append(visual_keys)
        if not pending:
            return [results[index] for index in range(len(views))]
        count, emitters = len(pending), lights.slots.size
        lit = np.zeros((count, emitters), dtype=bool)
        # The current windows lie in the current cell box (a published one may predate a replaced map).
        box = _layers_box(views[index].senses.cells.visible for index in pending)
        if box[0] <= box[2]:
            words = grid.light_slot_words(box)
            slotted = (lights.slots >= 0) & (lights.slots // 64 < words.shape[2])
            if slotted.any():
                # Each view's words OR-ed over its visible cells (one masked reduce over the stacked views).
                visible = stack.after[np.array(pending, dtype=np.int64), box[0] - stack.box[0]:box[2] - stack.box[0] + 1,
                                      box[1] - stack.box[1]:box[3] - stack.box[1] + 1]
                lit_words = np.bitwise_or.reduce(np.where(visible[..., None], words[None], np.uint64(0)), axis=(1, 2))
                slots = lights.slots[slotted]
                lit[:, slotted] = ((lit_words[:, slots // 64] >> (slots % 64).astype(np.uint64)) & np.uint64(1)) != 0
        # Each view's own key, in view order (as each view's stage assigned it).
        own = np.array([self._target_key(views[index].owner.uuid, True) for index in pending], dtype=np.int64)
        key_space = int(max(lights.anchor_entity_key.max(initial=0), lights.anchor_item_key.max(initial=0),
                            own.max(initial=0), max((int(keys.max(initial=0)) for keys in visual_keys_of)))) + 1
        visual_pairs = np.concatenate([order * key_space + keys for order, keys in enumerate(visual_keys_of)])
        orders = np.arange(count, dtype=np.int64)[:, None] * key_space
        anchor_entity = (lights.anchor_entity_key >= 0)[None, :] & (
            _in_sorted(orders + lights.anchor_entity_key[None, :], visual_pairs)
            | (lights.anchor_entity_key[None, :] == own[:, None]))
        anchor_item = (lights.anchor_item_key >= 0)[None, :] & _in_sorted(orders + lights.anchor_item_key[None, :],
                                                                           visual_pairs)
        # The rows whose emitter, lighting or disclosure differ from what each view's published emitters
        # read, for the views that published from one previous table at once.
        check = np.ones((count, emitters), dtype=bool)
        gone_of: List[Tuple[UUID, ...]] = [()] * count
        tables: Dict[int, List[Tuple[int, Tuple]]] = {}
        for order, index in enumerate(pending):
            known = views[index].field.light_inputs
            if known is not None:
                tables.setdefault(id(known[0]), []).append((order, known))
        for published in tables.values():
            members = [order for order, _ in published]
            previous_index, row_changed, gone = _light_table_diff(published[0][1][0], lights)
            present = previous_index >= 0

            def before(flags: List[np.ndarray]) -> np.ndarray:
                """The published views' flags per previous emitter row, placed on the current rows."""
                values = np.zeros((len(flags), emitters), dtype=bool)
                values[:, present] = np.stack(flags)[:, previous_index[present]]
                return values
            check[members] = (row_changed[None, :] | (lit[members] != before([known[3] for _, known in published]))
                              | (anchor_entity[members] != before([known[4] for _, known in published]))
                              | (anchor_item[members] != before([known[5] for _, known in published])))
            for order in members:
                gone_of[order] = gone
        for order, index in enumerate(pending):
            senses, field = views[index].senses, views[index].field
            known = field.light_inputs
            row_check, gone = check[order], gone_of[order]
            inputs = (lights, senses.cells.visible, visual_keys_of[order], lit[order].copy(),
                      anchor_entity[order].copy(), anchor_item[order].copy())
            previous = senses.light_sources
            previous_values = field.light_values
            if known is not None and not gone and not row_check.any():
                results[index] = (inputs, previous_values)
                continue
            check_rows, lit_rows = np.flatnonzero(row_check).tolist(), lit[order, row_check].tolist()
            entity_rows, item_rows = anchor_entity[order, row_check].tolist(), anchor_item[order, row_check].tolist()
            # A first view describes every lit emitter afresh; a settled one starts from what it published.
            sources = dict(previous) if known is not None else {}
            values_of = dict(previous_values) if known is not None else {}
            membership = known is None
            replaced = False
            # Emitters gone from the table are no longer lit.
            for identity in gone:
                membership = sources.pop(identity, None) is not None or membership
                values_of.pop(identity, None)
            for row, row_lit, entity_seen, item_seen in zip(
                    [lights.rows[row_index] for row_index in check_rows], lit_rows, entity_rows, item_rows):
                identity = row.identity
                if not row_lit:
                    membership = sources.pop(identity, None) is not None or membership
                    values_of.pop(identity, None)
                    continue
                values = row.values + (row.anchor_uuid if entity_seen else None, row.anchor_uuid if item_seen else None)
                old = previous.get(identity)
                if old is not None and not old.affected_tiles and previous_values.get(identity) == values:
                    sources[identity] = old
                else:
                    key = ("light", identity, values)
                    descriptor = shared.get(key)
                    if descriptor is None:
                        revision, position, height, appearance, very_bright, bright, dim, actor_anchored, \
                            anchor_entity_uuid, anchor_item_uuid = values
                        descriptor = shared[key] = PerceivedLightSource(
                            source_uuid=identity, revision=revision, position=position, base_height_steps=height,
                            appearance=appearance, very_bright_radius_feet=very_bright, bright_radius_feet=bright,
                            dim_radius_feet=dim, actor_anchored=actor_anchored, anchor_entity_uuid=anchor_entity_uuid,
                            anchor_item_uuid=anchor_item_uuid)
                    sources[identity] = descriptor
                current = previous.get(identity)
                membership = membership or current is None
                replaced = replaced or (current is not None and current is not sources[identity])
                values_of[identity] = values
            if not membership and not replaced:
                results[index] = (inputs, values_of)
                continue
            if membership:
                # Published in table order; a replaced descriptor keeps its place.
                listed = [row.identity for row in lights.rows if row.identity in sources]
                sources = {identity: sources[identity] for identity in listed}
                values_of = {identity: values_of[identity] for identity in listed}
                for identity in previous:
                    if identity not in sources:
                        senses.light_source_removals[identity] = max(previous[identity].revision,
                            grid.light_source_revision(identity))
                for identity in sources:
                    senses.light_source_removals.pop(identity, None)
            senses.light_sources = sources
            results[index] = (inputs, values_of)
        return [results[index] for index in range(len(views))]

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
            return (_any_visible(senses.cells, self._candidate_positions(event))
                or (event.object_uuid is not None and event.object_uuid in senses.objects))
        if isinstance(event, SpatialEffectChangeEvent):
            return _any_visible(senses.cells, event.get_affected_positions())
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


def _any_visible(cells: PerceivedCells, positions: Iterable[Position]) -> bool:
    """Whether any of these cells is visible (one gather)."""
    positions = list(positions)
    return bool(positions) and bool(_gather(cells.visible.values, cells.visible.box, positions).any())


def _changed_targets(previous: ContactTable, current: ContactTable) -> np.ndarray:
    """The target keys whose rows (cells or side, and facts) differ between two tables."""
    if previous is current:
        return np.zeros(0, dtype=np.int64)
    return np.unique(np.concatenate((
        current.cell_target_key[~_rows_in(current.cell_input, previous.cell_input)],
        previous.cell_target_key[~_rows_in(previous.cell_input, current.cell_input)],
        current.side_target_key[~_rows_in(current.side_input, previous.side_input)],
        previous.side_target_key[~_rows_in(previous.side_input, current.side_input)])))


def _targets_at(table: ContactTable, positions: Set[Position]) -> np.ndarray:
    """The target keys with a cell row, or a side row by its owner or far cell, on these cells."""
    if not positions:
        return np.zeros(0, dtype=np.int64)
    named = np.array(list(positions), dtype=np.int64).reshape(-1, 2)
    cells = _pack_cells(np.zeros(named.shape[0], dtype=np.int64), named[:, 0], named[:, 1])

    def at(xs: np.ndarray, ys: np.ndarray) -> np.ndarray:
        return np.isin(_pack_cells(np.zeros(xs.size, dtype=np.int64), xs, ys), cells)
    return np.concatenate((table.cell_target_key[at(table.cell_x, table.cell_y)],
                           table.side_target_key[at(table.side_x, table.side_y) | at(table.across_x, table.across_y)]))


def _in_sorted(values: np.ndarray, keys: np.ndarray) -> np.ndarray:
    """Whether each value is among sorted keys."""
    if not keys.size:
        return np.zeros(values.shape, dtype=bool)
    return keys[np.minimum(np.searchsorted(keys, values), keys.size - 1)] == values


def _light_table_diff(previous: LightSourceTable, current: LightSourceTable,
                      ) -> Tuple[np.ndarray, np.ndarray, Tuple[UUID, ...]]:
    """Each current emitter row's index in the previous table (-1 when new), whether its row
    differs, and the emitters of the previous table no longer in the current one."""
    index = {row.identity: position for position, row in enumerate(previous.rows)}
    previous_index = np.array([index.get(row.identity, -1) for row in current.rows], dtype=np.int64)
    changed = np.array([found < 0 or previous.key[found] != row for found, row in zip(previous_index.tolist(),
                                                                                        current.key)], dtype=bool)
    current_identities = {row.identity for row in current.rows}
    return (previous_index, changed.reshape(-1),
            tuple(row.identity for row in previous.rows if row.identity not in current_identities))


def _rows_in(rows: np.ndarray, others: np.ndarray) -> np.ndarray:
    """For each int64 row, whether an equal row is among the others (exact)."""
    if not rows.shape[0] or not others.shape[0]:
        return np.zeros(rows.shape[0], dtype=bool)
    both = np.concatenate((rows, others))
    order = np.lexsort(both.T[::-1])
    ordered = both[order]
    group = np.concatenate(([0], np.cumsum((ordered[1:] != ordered[:-1]).any(axis=1))))
    from_others = order >= rows.shape[0]
    has_other = np.zeros(int(group[-1]) + 1, dtype=bool)
    has_other[group[from_others]] = True
    found = np.empty(rows.shape[0], dtype=bool)
    found[order[~from_others]] = has_other[group[~from_others]]
    return found


def _row_identity(obs: np.ndarray, rows: np.ndarray) -> np.ndarray:
    """Each (observer, contact row) as two exact int64: the observer and cell; the target key, kind,
    visual and senses. Two rows are equal exactly when their identities are: a target key names one
    uuid and its class for as long as any field holds it (`SpatialSensesSystem._target_ids` is
    append-only and cleared only with every field), so the uuid halves add nothing."""
    kind_bits = max(ROW_ENTITY, ROW_OBJECT, ROW_SIDE, ROW_KNOWN).bit_length()
    attributes = ((rows[:, 7] << kind_bits | rows[:, 0]) << 1 | rows[:, 5]) << len(SENSE_BITS)
    return np.column_stack((_pack_cells(obs, rows[:, 3], rows[:, 4]), attributes | rows[:, 6]))


def _first_rows(slot_of: np.ndarray, pairs: np.ndarray, is_touched: np.ndarray, slots: np.ndarray,
                ) -> Tuple[np.ndarray, List[int]]:
    """The first row of each (observer, target) pair on a touched slot, ordered by slot and then by
    row, and each slot's bounds in that order."""
    in_touched = np.flatnonzero(is_touched[slot_of])
    _, first = np.unique(pairs[in_touched], return_index=True)
    first = in_touched[np.sort(first)]
    first = first[np.argsort(slot_of[first], kind="stable")]
    return first, np.searchsorted(slot_of[first], slots).tolist()


def _contact_maps(views: Sequence[ObserverView], rows: np.ndarray, uuids: np.ndarray, obs: np.ndarray,
                  changed: np.ndarray, previous_rows: np.ndarray, previous_uuids: np.ndarray,
                  previous_obs: np.ndarray, previous_changed: np.ndarray, shared: SharedValues,
                  ) -> List[ResolvedContacts]:
    """Every view's entity and object contacts from the evidence rows of all views (in evidence order,
    grouped by view, with whether each row changed) and their published rows: the targets with a
    changed row are resolved again from their rows, every other contact is kept. Python runs per
    touched row and per view.

    Contacts are listed in evidence order, each at its first row, whatever the history of the
    recomputes: while the order of a class's targets held, the map is a copy of the published one
    with the touched contacts replaced in place. A published map is never mutated
    (`published_senses` holds it by reference)."""
    count = len(views)
    key_space = int(max(rows[:, 7].max(initial=0), previous_rows[:, 7].max(initial=0))) + 1
    # (observer, target) pairs and (observer, class) slots: class 0 entities, 1 objects.
    pair, previous_pair = obs * key_space + rows[:, 7], previous_obs * key_space + previous_rows[:, 7]
    slot = obs * 2 + (rows[:, 0] != ROW_ENTITY)
    previous_slot = previous_obs * 2 + (previous_rows[:, 0] != ROW_ENTITY)
    slots = np.arange(2 * count + 1)
    # The targets with a changed row, and per slot their uuids: the published rows' first, then the
    # new rows', each in row order (a touched set's iteration order reaches the removed contacts).
    touched_pairs = np.unique(np.concatenate((previous_pair[previous_changed], pair[changed])))
    touched_slot = np.concatenate((previous_slot[previous_changed], slot[changed]))
    by_slot = np.argsort(touched_slot, kind="stable")
    touched_bounds = np.searchsorted(touched_slot[by_slot], slots).tolist()
    touched_uuids = np.concatenate((previous_uuids[previous_changed], uuids[changed]))[by_slot].tolist()
    starts: List[Tuple[Dict[UUID, PerceivedContact], Dict[UUID, PerceivedContact]]] = [
        (view.senses.entities, view.senses.objects) if view.published else ({}, {}) for view in views]

    def contact(position: Position, visual: bool, mask: int, previous: Optional[PerceivedContact],
                ) -> PerceivedContact:
        special = SENSES_BY_VALUE[mask]
        if (previous is not None and previous.position == position and previous.visual == visual
                and previous.special_senses == special):
            return previous
        key = ("contact", position, visual, special)
        value = shared.get(key)
        if value is None:
            value = shared[key] = PerceivedContact(position=position, visual=visual, special_senses=special)
        return value

    # The touched targets' contacts, resolved from their rows in evidence order.
    fresh: List[Dict[UUID, PerceivedContact]] = [{} for _ in range(2 * count)]
    selected = _in_sorted(pair, touched_pairs)
    for observer, (kind, _, _, x, y, visual, mask, _), identity in zip(
            obs[selected].tolist(), rows[selected].tolist(), uuids[selected].tolist()):
        visual = bool(visual)
        start_entities, start_objects = starts[observer]
        if kind == ROW_ENTITY:
            fresh[2 * observer][identity] = contact((x, y), visual, mask, start_entities.get(identity))
            continue
        fresh_objects = fresh[2 * observer + 1]
        if kind == ROW_KNOWN:
            if identity not in fresh_objects:
                fresh_objects[identity] = contact((x, y), False, 0, start_objects.get(identity))
            continue
        found = fresh_objects.get(identity)
        if kind == ROW_SIDE or found is None:
            fresh_objects[identity] = contact((x, y), visual, mask, start_objects.get(identity))
            continue
        # A multi-cell object: the best evidence, the union of its senses in enum order.
        origin = views[observer].origin
        chosen_position = min(((not found.visual, _distance_feet(origin, found.position), found.position),
                               (not visual, _distance_feet(origin, (x, y)), (x, y))))[2]
        established = 0
        for sense in found.special_senses:
            established |= SENSE_BITS[sense]
        key = ("contact", chosen_position, found.visual or visual, SENSES_BY_ENUM[established | mask])
        merged = shared.get(key)
        if merged is None:
            merged = shared[key] = PerceivedContact(position=chosen_position, visual=key[2], special_senses=key[3])
        fresh_objects[identity] = merged
    # Each touched slot's targets at their first row, now and as published.
    is_touched = np.zeros(2 * count, dtype=bool)
    is_touched[touched_slot] = True
    first, listed_bounds = _first_rows(slot, pair, is_touched, slots)
    previous_first, previous_bounds = _first_rows(previous_slot, previous_pair, is_touched, slots)
    listed_keys, previous_keys = rows[first, 7].tolist(), previous_rows[previous_first, 7].tolist()
    listed_uuids = uuids[first].tolist()
    view_bounds = np.searchsorted(obs, np.arange(count + 1)).tolist()
    results: List[ResolvedContacts] = []
    for observer, view in enumerate(views):
        maps: List[Dict[UUID, PerceivedContact]] = []
        touched_sets: List[FrozenSet[UUID]] = []
        for class_index, published in enumerate(starts[observer]):
            at = 2 * observer + class_index
            # set() first: its insertion order fixes the frozen set's iteration order, which reaches
            # the removed contacts of the sensory event.
            touched_set = frozenset(set(touched_uuids[touched_bounds[at]:touched_bounds[at + 1]]))
            listed = slice(listed_bounds[at], listed_bounds[at + 1])
            if not touched_set:
                maps.append(published)
            elif published and listed_keys[listed] == previous_keys[previous_bounds[at]:previous_bounds[at + 1]]:
                updated = dict(published)
                updated.update(fresh[at])
                maps.append(updated)
            else:
                maps.append({identity: fresh[at][identity] if identity in fresh[at] else published[identity]
                             for identity in listed_uuids[listed]})
            touched_sets.append(touched_set)
        results.append((maps[0], maps[1], rows[view_bounds[observer]:view_bounds[observer + 1]],
                        uuids[view_bounds[observer]:view_bounds[observer + 1]],
                        (touched_sets[0], touched_sets[1]) if view.published else None))
    return results


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


def _window_values(layer: CellLayer, window: Box) -> np.ndarray:
    """A copy of a cell grid's values over a window inside its box (kept to compare by value)."""
    return layer.values[window[0] - layer.x0:window[2] - layer.x0 + 1,
                        window[1] - layer.y0:window[3] - layer.y0 + 1].copy()


def _replace_effects(value: PublishedSenses, effects: Dict[UUID, PerceivedSpatialEffect]) -> PublishedSenses:
    return PublishedSenses(value.position, value.cells, value.seen, value.entities, value.objects, effects,
                           value.light_sources, value.light_source_removals, value.paths_dirty,
                           value.passive_perception, value.sense_modes_hash, value.sense_modes, value.visual_access)


def _replace_paths_dirty(value: PublishedSenses) -> PublishedSenses:
    return PublishedSenses(value.position, value.cells, value.seen, value.entities, value.objects,
                           value.spatial_effects, value.light_sources, value.light_source_removals, True,
                           value.passive_perception, value.sense_modes_hash, value.sense_modes, value.visual_access)


spatial_senses_system = SpatialSensesSystem()
