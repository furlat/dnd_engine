"""One observer's subjective vision as a sense x interceptor table applied as arrays (plan §6b).

The frame is the (2R + 1)^2 square of the supercover route table around the
observer (R = FRAME_RADIUS); a frame cell's flat index is also the table row of
the route to it, so obscurement along every candidate route is one ragged
gather plus one segmented OR.

Per cell: 4 eligibility bits (plain, darkvision, Devil's Sight, Truesight) =
range bits AND the survivors of the route's obscurement bits; the effective
light (or "not seen") is one lookup in a 16 x 5 table. Both tables are built
from `_visual_route_modes` / `_route_light_levels`, exact by construction.
Python runs per observer, per target on visible/felt cells, and per hazard
owner; never per cell.
"""

from dataclasses import dataclass
from time import perf_counter_ns
from typing import Dict, List, Optional, Tuple
from uuid import UUID

import numpy as np

from dnd.blocks.sensory import Senses, SpatialSensesSystem
from dnd.core.base_block import BaseBlock
from dnd.core.gridmap import SPATIAL_CHUNK_SIZE, GridMap
from dnd.types.senses import OBSCUREMENT_BITS, OBSCUREMENT_SETS, OpticalObscurement, PerceivedContact, SensesType
from dnd.types.world import CardinalDirection, LightLevel, WorldEdgeChannel

from devtools.perception_arrays_spike.frame_routes import (CELLS, CENTER, FRAME_RADIUS as R, OFF, SIDE,
    frame_distance_feet, frame_route_table)
from devtools.perception_arrays_spike.world_arrays import PAD, TargetFacts, WorldArrays

DISTANCE_FEET = frame_distance_feet()
SENSE_BITS = {sense: 1 << index for index, sense in enumerate(SensesType)}
BS, TR = SENSE_BITS[SensesType.BLINDSIGHT], SENSE_BITS[SensesType.TREMORSENSE]
# Contact special-sense tuples in the two native orders: value-sorted (_resolve_contact) and enum order (object merge).
BY_VALUE = tuple(tuple(sorted((s for s, bit in SENSE_BITS.items() if mask & bit), key=lambda s: s.value))
                 for mask in range(1 << len(SENSE_BITS)))
LEVELS = tuple(LightLevel(value) for value in range(len(LightLevel)))

# Eligibility bits, in the plan's order.
PLAIN, ELIG_DV, ELIG_DS, ELIG_TS = 1, 2, 4, 8
VISUAL_SENSES = ((SensesType.DARKVISION, ELIG_DV), (SensesType.DEVILS_SIGHT, ELIG_DS), (SensesType.TRUESIGHT, ELIG_TS))
UNSEEN = 255
DARK = OBSCUREMENT_BITS[OpticalObscurement.MAGICAL_DARKNESS]


def _eligibility(ordinary: bool, special) -> int:
    return (PLAIN if ordinary else 0) | sum(bit for sense, bit in VISUAL_SENSES if sense in special)


def _survivor_table() -> np.ndarray:
    """Eligibility bits an obscurement mask lets through, read off `_visual_route_modes` with every sense in range."""
    unlimited = {sense: 0 for sense, _ in VISUAL_SENSES}
    return np.array([_eligibility(*SpatialSensesSystem._visual_route_modes(
        unlimited, True, 0, OBSCUREMENT_SETS[mask], LightLevel.BRIGHT_LIGHT)) for mask in range(len(OBSCUREMENT_SETS))],
        dtype=np.uint8)


def _light_table() -> np.ndarray:
    """(eligibility, objective light) -> effective light, UNSEEN for None, from `_route_light_levels`."""
    table = np.full((16, len(LightLevel)), UNSEEN, dtype=np.uint8)
    for eligibility in range(16):
        levels = SpatialSensesSystem._route_light_levels(
            bool(eligibility & PLAIN), frozenset(sense for sense, bit in VISUAL_SENSES if eligibility & bit))
        for light, effective in levels.items():
            if effective is not None:
                table[eligibility, light.value] = effective.value
    return table


SURVIVORS = _survivor_table()
LIGHT_TABLE = _light_table()
# The special senses an eligibility establishes, as SENSE_BITS (contacts carry them).
ELIGIBLE_SENSES = np.array([sum(SENSE_BITS[sense] for sense, bit in VISUAL_SENSES if eligibility & bit)
                            for eligibility in range(16)], dtype=np.uint8)
DELTAS = {CardinalDirection.NORTH: (0, 1), CardinalDirection.SOUTH: (0, -1),
          CardinalDirection.EAST: (1, 0), CardinalDirection.WEST: (-1, 0)}
OPPOSITE = {CardinalDirection.NORTH: CardinalDirection.SOUTH, CardinalDirection.SOUTH: CardinalDirection.NORTH,
            CardinalDirection.EAST: CardinalDirection.WEST, CardinalDirection.WEST: CardinalDirection.EAST}
CHANNELS = (WorldEdgeChannel.OPTICAL, WorldEdgeChannel.PROPAGATION)


@dataclass(frozen=True)
class RouteRows:
    """Physical-FOV candidates of one (origin, radius, optical revision), with their route gathers."""

    rows: np.ndarray       # frame indices of the wall-FOV candidates
    before: np.ndarray     # every route's cells without its endpoint, concatenated, plus one OFF sentinel
    starts: np.ndarray     # each route's first offset in `before`
    empty: np.ndarray      # routes with no cell before the endpoint (the origin)
    near: np.ndarray       # the route cell before the endpoint (OFF for the origin)


@dataclass
class FrameCaches:
    """Array forms of the GridMap's own cached FOVs, keyed like them."""

    optical: Dict[Tuple[Tuple[int, int], int, int], RouteRows]
    propagation: Dict[Tuple[Tuple[int, int], int, int], np.ndarray]


@dataclass(frozen=True)
class Contact:
    """One established contact before it becomes a PerceivedContact."""

    uuid: UUID
    position: Tuple[int, int]
    visual: bool
    senses: int            # SENSE_BITS mask


@dataclass(frozen=True)
class ArrayView:
    """Settled subjective vision of one observer, in its frame."""

    origin: Tuple[int, int]
    visible_rows: np.ndarray       # frame indices
    effective_light: np.ndarray    # uint8 LightLevel, aligned with visible_rows
    eligibility: np.ndarray        # uint8 eligibility bits, aligned with visible_rows
    hazardous: np.ndarray          # bool, aligned with visible_rows
    surface_rows: np.ndarray       # first opaque volume surfaces (not visible; their geometry is)
    surface_light_rows: np.ndarray
    surface_ordinary: np.ndarray
    surface_special: np.ndarray
    entities: Tuple[Contact, ...]
    cell_objects: Tuple[Contact, ...]      # a multi-cell object has one per cell
    known_objects: Tuple[Tuple[UUID, Tuple[int, int]], ...]
    boundary_objects: Tuple[Contact, ...]
    fov_cache_hit: bool
    counts: Dict[str, int]
    phases_ns: Dict[str, int]


def new_caches() -> FrameCaches:
    return FrameCaches({}, {})


def _route_rows(rows: np.ndarray) -> RouteRows:
    cells, lengths = frame_route_table()
    row_lengths = lengths[rows].astype(np.int64)
    width = int(row_lengths.max()) if rows.size else 1
    kept = np.arange(width)[None, :] < (row_lengths - 1)[:, None]
    before = np.append(cells[rows, :width][kept].astype(np.int64), OFF)
    starts = (np.concatenate(([0], np.cumsum(row_lengths - 1)[:-1])).astype(np.int64) if rows.size
              else np.zeros(0, np.int64))
    near = np.where(row_lengths >= 2, cells[rows, np.maximum(row_lengths - 2, 0)], OFF).astype(np.int64)
    return RouteRows(rows, before, starts, row_lengths < 2, near)


def _to_rows(positions, origin: Tuple[int, int]) -> np.ndarray:
    if not positions:
        return np.zeros(0, dtype=np.int64)
    offsets = np.array(positions, dtype=np.int64) - origin
    assert np.abs(offsets).max() <= R, "spike frame covers routes up to FRAME_RADIUS"
    return np.unique((offsets[:, 0] + R) * SIDE + offsets[:, 1] + R)


def _frame(grid: np.ndarray, world: WorldArrays, origin: Tuple[int, int]) -> np.ndarray:
    sx, sy = origin[0] - world.min_x + PAD - R, origin[1] - world.min_y + PAD - R
    flat = np.zeros(CELLS + 1, dtype=grid.dtype)
    flat[:CELLS] = grid[sx:sx + SIDE, sy:sy + SIDE].ravel()
    return flat


def _frame_index(x: np.ndarray, y: np.ndarray, origin: Tuple[int, int]) -> np.ndarray:
    fx, fy = x - origin[0] + R, y - origin[1] + R
    inside = (fx >= 0) & (fx < SIDE) & (fy >= 0) & (fy < SIDE)
    return np.where(inside, fx * SIDE + fy, OFF)


def _in_range(modes: Dict[SensesType, int], sense: SensesType, distance: np.ndarray) -> np.ndarray:
    sense_range = modes.get(sense)
    if sense_range is None:
        return np.zeros(distance.shape, dtype=bool)
    if sense_range == 0:
        return np.ones(distance.shape, dtype=bool)
    return distance <= sense_range


def _range_bits(modes: Dict[SensesType, int], ordinary_sight: bool, distance: np.ndarray) -> np.ndarray:
    bits = np.full(distance.shape, PLAIN if ordinary_sight else 0, dtype=np.uint8)
    for sense, bit in VISUAL_SENSES:
        if sense in modes:
            bits |= np.where(_in_range(modes, sense, distance), bit, 0).astype(np.uint8)
    return bits


def _chunk_rows(index, bounds: Tuple[int, int, int, int]):
    """Rows of one GridMap chunk index inside inclusive bounds (stand-in for PV1's GridMap bounds query)."""
    min_x, min_y, max_x, max_y = bounds
    return [(position, row)
            for cx in range(min_x // SPATIAL_CHUNK_SIZE, max_x // SPATIAL_CHUNK_SIZE + 1)
            for cy in range(min_y // SPATIAL_CHUNK_SIZE, max_y // SPATIAL_CHUNK_SIZE + 1)
            for position, row in index.get((cx, cy), {}).items()
            if min_x <= position[0] <= max_x and min_y <= position[1] <= max_y]


@dataclass
class Passive:
    """The observer's passive perception, read at most once per recompute."""

    owner: BaseBlock
    value: Optional[int] = None


def _facts(world: WorldArrays, grid: GridMap, identity: UUID, as_entity: bool) -> Optional[TargetFacts]:
    """A target's observer-independent facts, read once per operation."""
    key = (identity, as_entity)
    if key in world.targets:
        return world.targets[key]
    block = BaseBlock.get(identity)
    facts = None
    if block is not None:
        placement = None if as_entity else grid.get_object_placement(identity)
        facts = TargetFacts(block, block.appears_in_entity_contacts() if as_entity
                            else block.should_include_in_senses_objects(),
                            block.stealth_dc, block.is_invisible,
                            placement.position if placement is not None and placement.boundary_direction is not None
                            else None)
    world.targets[key] = facts
    return facts


def _admitted(facts: TargetFacts, observer_uuid: UUID, passive: Passive) -> bool:
    """Per-target gates of _resolve_contact: observability (per observer), then hiding."""
    if not facts.block.is_observable_to(observer_uuid):
        return False
    if facts.stealth_dc is not None:
        if passive.value is None:
            passive.value = passive.owner.get_passive_perception()
        if facts.stealth_dc >= passive.value:
            return False
    return True


def _side_layer(side_index, position: Tuple[int, int], direction: CardinalDirection) -> Tuple[UUID, ...]:
    row = side_index.get((position[0] // SPATIAL_CHUNK_SIZE, position[1] // SPATIAL_CHUNK_SIZE), {}).get(position)
    return row.get(direction, ()) if row is not None else ()


def _open_channels(world: WorldArrays, side_index, position: Tuple[int, int],
                   direction: CardinalDirection) -> Tuple[WorldEdgeChannel, ...]:
    """Channels on which a side is reached from across it: those the far Tile's own exit layer does not block."""
    key = (position, direction)
    if key in world.side_channels:
        return world.side_channels[key]
    dx, dy = DELTAS[direction]
    blocked = set()
    for identity in _side_layer(side_index, (position[0] + dx, position[1] + dy), OPPOSITE[direction]):
        block = BaseBlock.get(identity)
        structure = block.get_boundary_structure() if block is not None else None
        if structure is not None:
            blocked.update(structure.blocked_channels)
    world.side_channels[key] = tuple(channel for channel in CHANNELS if channel not in blocked)
    return world.side_channels[key]


def array_recompute(world: WorldArrays, caches: FrameCaches, grid: GridMap, observer_uuid: UUID,
                    owner: BaseBlock, senses: Senses) -> ArrayView:
    """Replace one observer's visual cells and contacts, as arrays (no per-cell Python)."""
    marks = [perf_counter_ns()]
    phases: Dict[str, int] = {}
    counts: Dict[str, int] = {}

    def mark(name: str) -> None:
        marks.append(perf_counter_ns())
        phases[name] = marks[-1] - marks[-2]

    max_distance = senses._perception_max_distance
    origin = owner.get_position()
    modes = {mode.sense_type: mode.range_feet for mode in senses.get_sense_modes()}
    visual_access = senses.visual_access.normalized_score > 0
    ordinary_sight = owner.has_ordinary_visual_sight()
    optical_radius = max_distance if ordinary_sight else 0
    for sense, _ in VISUAL_SENSES:
        sense_range = modes.get(sense)
        if sense_range is not None:
            optical_radius = max(optical_radius, max_distance if sense_range == 0 else (sense_range + 4) // 5)
    mark("inputs")

    fov_hit = True
    if visual_access and optical_radius > 0:
        key = (origin, optical_radius, world.optical_revision)
        routes = caches.optical.get(key)
        fov_hit = routes is not None
        if routes is None:
            routes = caches.optical[key] = _route_rows(_to_rows(grid.compute_fov(origin, optical_radius), origin))
    else:
        routes = _route_rows(np.zeros(0, dtype=np.int64))
    mark("fov_rows")

    exists = _frame(world.exists, world, origin)
    keep = exists[routes.rows]
    rows = routes.rows[keep]
    bits = _frame(world.obscurement, world, origin)
    at_cell = bits[rows]
    if routes.rows.size and bits.any():
        before = np.bitwise_or.reduceat(bits[routes.before], routes.starts)
        before[routes.empty] = 0
        before = before[keep]
    else:
        before = np.zeros(rows.size, dtype=np.uint8)
    distance = DISTANCE_FEET[rows]
    in_range = _range_bits(modes, ordinary_sight, distance)
    eligibility = in_range & SURVIVORS[before | at_cell]
    effective = LIGHT_TABLE[eligibility, _frame(world.light, world, origin)[rows]]
    visible = effective != UNSEEN
    visible_rows = rows[visible]
    mark("optics")

    # First opaque volume surface: a hidden cell that itself carries obscurement,
    # judged on the route before it (its own cloud does not hide its surface).
    surface = ~visible & (at_cell != 0)
    s_rows = rows[surface]
    s_eligibility = in_range[surface] & SURVIVORS[before[surface]]
    s_near = routes.near[keep][surface]
    s_light = np.where(((at_cell[surface] & DARK) != 0) & (s_rows != CENTER) & exists[s_near], s_near, s_rows)
    s_keep = s_eligibility != 0
    mark("surfaces")

    nonvisual = np.zeros(CELLS + 1, dtype=np.uint8)
    reach = optical_radius if visual_access else 0
    for sense, bit in ((SensesType.BLINDSIGHT, BS), (SensesType.TREMORSENSE, TR)):
        sense_range = modes.get(sense)
        if sense_range is None:
            continue
        radius = max_distance if sense_range == 0 else (sense_range + 4) // 5
        reach = max(reach, radius)
        key = (origin, radius, world.propagation_revision)
        felt = caches.propagation.get(key)
        if felt is None:
            felt = caches.propagation[key] = _to_rows(grid.compute_propagation_fov(origin, radius), origin)
        nonvisual[felt] |= bit
    seen_frame = np.zeros(CELLS + 1, dtype=bool)
    seen_frame[visible_rows] = True
    senses_frame = np.zeros(CELLS + 1, dtype=np.uint8)
    senses_frame[visible_rows] = ELIGIBLE_SENSES[eligibility[visible]]
    reach = min(reach, R)
    bounds = (origin[0] - reach, origin[1] - reach, origin[0] + reach, origin[1] + reach)
    mark("nonvisual")

    # Occupants in the window index the visible mask; per-target checks run on hit cells only.
    passive = Passive(owner)
    entities: List[Contact] = []
    cell_objects: List[Contact] = []
    occupied = _chunk_rows(grid._contact_candidate_cells, bounds)
    counts["occupied_cells"] = len(occupied)
    counts["hit_cells"] = 0
    if occupied:
        index = _frame_index(np.fromiter((row[0][0] for row in occupied), np.int64, len(occupied)),
                             np.fromiter((row[0][1] for row in occupied), np.int64, len(occupied)), origin)
        seen, felt = seen_frame[index], nonvisual[index]
        cell_distance = DISTANCE_FEET[index]
        reveals = _in_range(modes, SensesType.TRUESIGHT, cell_distance) | _in_range(
            modes, SensesType.SEE_INVISIBLE, cell_distance)
        hit = np.flatnonzero(seen | (felt != 0))
        counts["hit_cells"] = int(hit.size)
        for i, cell_seen, cell_senses, cell_felt, cell_reveals in zip(
                hit.tolist(), seen[hit].tolist(), senses_frame[index[hit]].tolist(), felt[hit].tolist(),
                reveals[hit].tolist()):
            position, (entity_ids, object_ids) = occupied[i]
            for identities, out, is_entity in ((entity_ids, entities, True), (object_ids, cell_objects, False)):
                for identity in identities:
                    if is_entity and identity == observer_uuid:
                        continue
                    facts = _facts(world, grid, identity, is_entity)
                    if facts is None or not facts.listed or not _admitted(facts, observer_uuid, passive):
                        continue
                    visual = cell_seen and (cell_reveals or not facts.invisible)
                    mask = (cell_senses if visual else 0) | cell_felt
                    if visual or mask:
                        out.append(Contact(identity, position, visual, mask))
    known = tuple((identity, placement.position) for identity in grid.get_known_object_candidates(observer_uuid)
                  if (subject := BaseBlock.get(identity)) is not None
                  and (placement := grid.get_object_placement(identity)) is not None
                  and subject.is_object_known_to(observer_uuid))
    mark("cell_contacts")

    # Boundary evidence per target: a side is reached from its owner Tile (exit) and,
    # unless that Tile's own exit layer blocks the channel, from across the side (entry).
    boundary_objects: List[Contact] = []
    side_index = grid._boundary_candidate_cells
    sides = [(position, direction, identities)
             for position, row in _chunk_rows(side_index, (bounds[0] - 1, bounds[1] - 1, bounds[2] + 1, bounds[3] + 1))
             for direction, identities in row.items() if identities]
    counts["boundary_sides"] = len(sides)
    counts["boundary_targets"] = 0
    if sides:
        own_x = np.fromiter((side[0][0] for side in sides), np.int64, len(sides))
        own_y = np.fromiter((side[0][1] for side in sides), np.int64, len(sides))
        step = np.array([DELTAS[side[1]] for side in sides], dtype=np.int64)
        own, across = _frame_index(own_x, own_y, origin), _frame_index(own_x + step[:, 0], own_y + step[:, 1], origin)
        reached = np.flatnonzero(seen_frame[own] | (nonvisual[own] != 0) | seen_frame[across] | (nonvisual[across] != 0))
        # One gather for both ends of every reached side: seen, felt, eligible senses, invisibility revealed.
        ends = np.concatenate((own[reached], across[reached]))
        end_distance = DISTANCE_FEET[ends]
        end_rows = list(zip(seen_frame[ends].tolist(), nonvisual[ends].tolist(), senses_frame[ends].tolist(),
                            (_in_range(modes, SensesType.TRUESIGHT, end_distance)
                             | _in_range(modes, SensesType.SEE_INVISIBLE, end_distance)).tolist()))
        across_exists = exists[across[reached]].tolist()
        # Evidence rows per target, as _collect_boundary_evidence records them: an optical row
        # where the end is seen, a propagation row where it is felt.
        evidence: Dict[UUID, List[Tuple[bool, int, int, bool]]] = {}
        for k, i in enumerate(reached.tolist()):
            position, direction, identities = sides[i]
            rows_k: List[Tuple[bool, int, int, bool]] = []
            for end_row, channels in ((end_rows[k], CHANNELS), (end_rows[k + reached.size], (
                    _open_channels(world, side_index, position, direction) if across_exists[k] else ()))):
                end_seen, end_felt, end_senses, end_reveals = end_row
                if end_seen and WorldEdgeChannel.OPTICAL in channels:
                    rows_k.append((True, end_felt, end_senses, end_reveals))
                if end_felt and WorldEdgeChannel.PROPAGATION in channels:
                    rows_k.append((False, end_felt, 0, False))
            if rows_k:
                for identity in identities:
                    evidence.setdefault(identity, []).extend(rows_k)
        counts["boundary_targets"] = len(evidence)
        for identity, rows_i in evidence.items():
            facts = _facts(world, grid, identity, False)
            if (facts is None or facts.boundary_position is None or not facts.listed
                    or not _admitted(facts, observer_uuid, passive)):
                continue
            hidden = facts.invisible
            visual, mask = False, 0
            for row_seen, row_felt, row_senses, row_reveals in rows_i:
                row_visual = row_seen and (row_reveals or not hidden)
                visual |= row_visual
                mask |= (row_senses if row_visual else 0) | row_felt
            if visual or mask:
                boundary_objects.append(Contact(identity, facts.boundary_position, visual, mask))
    mark("boundary_contacts")

    hazard = np.zeros(CELLS + 1, dtype=bool)
    low_x, low_y, high_x, high_y = origin[0] - R, origin[1] - R, origin[0] + R, origin[1] + R
    asked = 0
    for row in world.hazard_owners:
        bx0, by0, bx1, by1 = row.footprint.bounds
        if bx1 < low_x or bx0 > high_x or by1 < low_y or by0 > high_y:
            continue
        asked += 1
        if row.owner.is_hazardous_for(observer_uuid):
            hazard[_frame_index(row.footprint.x, row.footprint.y, origin)] = True
    hazard[OFF] = False
    counts["hazard_owners_asked"] = asked
    hazardous = hazard[visible_rows]
    mark("hazards")

    return ArrayView(origin, visible_rows, effective[visible], eligibility[visible], hazardous,
                     s_rows[s_keep], s_light[s_keep], (s_eligibility[s_keep] & PLAIN) != 0,
                     (s_eligibility[s_keep] & (ELIG_DV | ELIG_DS | ELIG_TS)) != 0,
                     tuple(entities), tuple(cell_objects), known, tuple(boundary_objects), fov_hit, counts, phases)


def frame_positions(rows: np.ndarray, origin: Tuple[int, int]) -> List[Tuple[int, int]]:
    return list(zip((rows // SIDE - R + origin[0]).tolist(), (rows % SIDE - R + origin[1]).tolist()))


def _perceived(contact: Contact) -> PerceivedContact:
    return PerceivedContact(position=contact.position, visual=contact.visual, special_senses=BY_VALUE[contact.senses])


def materialize(view: ArrayView) -> Dict[str, object]:
    """The Senses fields today's recompute writes, in their dict/set form (for equality and timing)."""
    positions = frame_positions(view.visible_rows, view.origin)
    origin = view.origin
    objects: Dict[UUID, PerceivedContact] = {}
    for row in view.cell_objects:
        contact = _perceived(row)
        previous = objects.get(row.uuid)
        if previous is not None:
            # A multi-cell object: the native merge (best evidence, union of senses in enum order).
            chosen = min((previous, contact), key=lambda c: (
                not c.visual, int(DISTANCE_FEET[(c.position[0] - origin[0] + R) * SIDE + c.position[1] - origin[1] + R]),
                c.position))
            established = set(previous.special_senses) | set(contact.special_senses)
            contact = PerceivedContact(position=chosen.position, visual=previous.visual or contact.visual,
                                       special_senses=tuple(s for s in SensesType if s in established))
        objects[row.uuid] = contact
    for identity, position in view.known_objects:
        objects.setdefault(identity, PerceivedContact(position=position, visual=False, special_senses=()))
    for row in view.boundary_objects:
        objects[row.uuid] = _perceived(row)
    return {
        "visible": set(positions),
        "entities": {row.uuid: _perceived(row) for row in view.entities},
        "objects": objects,
        "hazardous_cells": dict(zip(positions, view.hazardous.tolist())),
        "effective_light_levels": dict(zip(positions, [LEVELS[value] for value in view.effective_light.tolist()])),
    }


def surface_rays(view: ArrayView) -> set:
    """(position, light position, ordinary, special) for each first opaque surface."""
    return set(zip(frame_positions(view.surface_rows, view.origin),
                   frame_positions(view.surface_light_rows, view.origin),
                   view.surface_ordinary.tolist(), view.surface_special.tolist()))
