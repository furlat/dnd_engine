"""Subjective vision as data (plan §6b): the sense x interceptor rule, its tables, and one view as arrays;
and the objective wall FOV those views and area propagation start from (`wall_visibility`).

What can stop sight is a finite set (walls, heavy obscurement, magical darkness, the
light at the target cell) and so is what can see (plain sight, darkvision, Devil's
Sight, Truesight, each with a range). Per cell, four eligibility bits (plain,
darkvision, Devil's Sight, Truesight) are the range bits AND the survivors of the
route's obscurement bits; the effective light, or "not seen", is one lookup in a
16 x 5 table. Both tables are generated from `visual_route_modes` and
`route_light_levels`, the one statement of the rule.

The observer's frame is the (2R + 1)^2 square of the supercover route table around
its origin (R = ROUTE_TABLE_RADIUS); a frame cell's flat index is also the table row
of the route to it. Map data reaches a frame through `CellLayer`, a 2D array
anchored at a map coordinate. Functions here take primitives (origin, sense ranges,
layers) and never import a block, an entity or the map.
"""

import functools
from dataclasses import dataclass
from typing import AbstractSet, Collection, Dict, FrozenSet, List, Mapping, Optional, Sequence, Set, Tuple

import numpy as np

from dnd.core.geometry import (ROUTE_STEP_SHIFT, ROUTE_TABLE_RADIUS, STEP_ALONG_X, STEP_ALONG_Y, STEP_DIAGONAL,
                               supercover_route_table, supercover_routes)
from dnd.types.senses import OBSCUREMENT_BITS, OBSCUREMENT_SETS, OpticalObscurement, SensesType
from dnd.types.world import CardinalDirection, LightLevel

Position = Tuple[int, int]
Box = Tuple[int, int, int, int]  # inclusive (min_x, min_y, max_x, max_y)


# ---------------------------------------------------------------- the rule


def sense_in_range(modes: Mapping[SensesType, int], sense_type: SensesType, distance_feet: int) -> bool:
    """Whether a sense with this range (0 is unlimited) reaches the distance."""
    sense_range = modes.get(sense_type)
    return sense_range is not None and (sense_range == 0 or distance_feet <= sense_range)


def visual_route_modes(modes: Mapping[SensesType, int], ordinary_sight: bool, distance: int,
                       obscurements: AbstractSet[OpticalObscurement], light: LightLevel,
                       ) -> Tuple[bool, Set[SensesType]]:
    """Ordinary and special visual eligibility of one optical route (range, obscurement, light)."""
    ordinary = (ordinary_sight and OpticalObscurement.HEAVY not in obscurements
                and OpticalObscurement.MAGICAL_DARKNESS not in obscurements
                and light.value > LightLevel.DARKNESS.value)
    special: Set[SensesType] = set()
    if OpticalObscurement.HEAVY not in obscurements:
        for sense in (SensesType.DARKVISION, SensesType.DEVILS_SIGHT, SensesType.TRUESIGHT):
            if (sense_in_range(modes, sense, distance)
                    and (sense is not SensesType.DARKVISION
                         or OpticalObscurement.MAGICAL_DARKNESS not in obscurements)):
                special.add(sense)
    return ordinary, special


def route_light_levels(ordinary: bool, special: AbstractSet[SensesType]) -> Dict[LightLevel, Optional[LightLevel]]:
    """The effective light of each objective light for one eligibility, None when not seen."""
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


# ---------------------------------------------------------------- the tables

PLAIN, DARKVISION, DEVILS_SIGHT, TRUESIGHT = 1, 2, 4, 8
SPECIAL = DARKVISION | DEVILS_SIGHT | TRUESIGHT
VISUAL_SENSES = ((SensesType.DARKVISION, DARKVISION), (SensesType.DEVILS_SIGHT, DEVILS_SIGHT),
                 (SensesType.TRUESIGHT, TRUESIGHT))
UNSEEN = 255
MAGICAL_DARKNESS_BIT = OBSCUREMENT_BITS[OpticalObscurement.MAGICAL_DARKNESS]
HEAVY_BIT = OBSCUREMENT_BITS[OpticalObscurement.HEAVY]
LIGHT_LEVELS = tuple(LightLevel(value) for value in range(len(LightLevel)))


def eligibility_bits(ordinary: bool, special: AbstractSet[SensesType]) -> int:
    return (PLAIN if ordinary else 0) | sum(bit for sense, bit in VISUAL_SENSES if sense in special)


def _survivor_table() -> np.ndarray:
    """Eligibility bits an obscurement mask lets through, with every sense in range."""
    unlimited = {sense: 0 for sense, _ in VISUAL_SENSES}
    return np.array([eligibility_bits(*visual_route_modes(unlimited, True, 0, OBSCUREMENT_SETS[mask],
                                                          LightLevel.BRIGHT_LIGHT))
                     for mask in range(len(OBSCUREMENT_SETS))], dtype=np.uint8)


def _light_table() -> np.ndarray:
    """(eligibility, objective light) -> effective light, UNSEEN where not seen."""
    table = np.full((16, len(LightLevel)), UNSEEN, dtype=np.uint8)
    for eligibility in range(16):
        levels = route_light_levels(bool(eligibility & PLAIN), eligibility_senses(eligibility))
        for light, effective in levels.items():
            if effective is not None:
                table[eligibility, light.value] = effective.value
    return table


def eligibility_senses(eligibility: int) -> FrozenSet[SensesType]:
    """The special visual senses an eligibility establishes."""
    return frozenset(sense for sense, bit in VISUAL_SENSES if eligibility & bit)


SURVIVORS = _survivor_table()
LIGHT_TABLE = _light_table()


# ---------------------------------------------------------------- map-anchored layers


@dataclass(frozen=True)
class CellLayer:
    """A 2D array anchored at a map coordinate: values[i, j] is cell (x0 + i, y0 + j)."""

    x0: int
    y0: int
    values: np.ndarray

    @property
    def box(self) -> Box:
        width, height = self.values.shape[:2]
        return self.x0, self.y0, self.x0 + width - 1, self.y0 + height - 1


def cells_layer(cells: Collection[Position], value: int | bool) -> CellLayer:
    """A layer over the cells' bounding box holding `value` at the cells (bool for True, else uint8)."""
    dtype = np.dtype(bool) if value is True else np.dtype(np.uint8)
    if not cells:
        return CellLayer(0, 0, np.zeros((0, 0), dtype=dtype))
    xs, ys = np.array(list(cells), dtype=np.int64).reshape(-1, 2).T
    x0, y0 = int(xs.min()), int(ys.min())
    values = np.zeros((int(xs.max()) - x0 + 1, int(ys.max()) - y0 + 1), dtype=dtype)
    values[xs - x0, ys - y0] = value
    return CellLayer(x0, y0, values)


def layer_value(layer: CellLayer, position: Position) -> int:
    """The layer's value at a map cell, 0 outside it."""
    i, j = position[0] - layer.x0, position[1] - layer.y0
    width, height = layer.values.shape
    return int(layer.values[i, j]) if 0 <= i < width and 0 <= j < height else 0


def layer_positions(layer: CellLayer, mask: Optional[np.ndarray] = None) -> List[Position]:
    """Map cells where the layer (or the given same-shaped mask) is nonzero, x-major sorted."""
    xs, ys = np.nonzero(layer.values if mask is None else mask)
    return list(zip((xs + layer.x0).tolist(), (ys + layer.y0).tolist()))


def boxes_intersect(first: Box, second: Box) -> bool:
    return not (first[2] < second[0] or second[2] < first[0] or first[3] < second[1] or second[3] < first[1])


def embed(layer: CellLayer, box: Box, dtype: np.dtype) -> np.ndarray:
    """The layer's values over another box, zero where it does not reach."""
    out = np.zeros((box[2] - box[0] + 1, box[3] - box[1] + 1), dtype=dtype)
    lx0, ly0, lx1, ly1 = layer.box
    ax0, ay0 = max(box[0], lx0), max(box[1], ly0)
    ax1, ay1 = min(box[2], lx1), min(box[3], ly1)
    if ax0 <= ax1 and ay0 <= ay1:
        out[ax0 - box[0]:ax1 - box[0] + 1, ay0 - box[1]:ay1 - box[1] + 1] = \
            layer.values[ax0 - lx0:ax1 - lx0 + 1, ay0 - ly0:ay1 - ly0 + 1]
    return out


def union_box(first: Box, second: Box) -> Box:
    return (min(first[0], second[0]), min(first[1], second[1]), max(first[2], second[2]), max(first[3], second[3]))


# ---------------------------------------------------------------- the frame

R = ROUTE_TABLE_RADIUS
SIDE = 2 * R + 1
CELLS = SIDE * SIDE
OFF = CELLS                  # padded "outside" index: always zero / False
CENTER = R * SIDE + R


def _frame_distance_feet() -> np.ndarray:
    """grid_distance_feet from the frame center to every frame cell (OFF -> 0)."""
    dx, dy = np.meshgrid(np.arange(-R, R + 1), np.arange(-R, R + 1), indexing="ij")
    squared = (dx * dx + dy * dy).ravel().astype(np.float64)
    return np.append(np.sqrt(squared).astype(np.int64) * 5, 0)


FRAME_DISTANCE_FEET = _frame_distance_feet()


def sense_radius_cells(range_feet: int, max_distance: int) -> int:
    """Cells one sense reaches: an unlimited sense (0 ft) reaches `max_distance`.

    Perception reaches at most R cells (400 ft): the frame every view is computed in.
    """
    return min(max_distance if range_feet == 0 else (range_feet + 4) // 5, R)


def frame_box(origin: Position) -> Box:
    return origin[0] - R, origin[1] - R, origin[0] + R, origin[1] + R


def frame_of(layer: CellLayer, origin: Position) -> np.ndarray:
    """The layer seen from an origin: a flat frame of CELLS + 1 values, OFF and outside zero."""
    flat = np.zeros(CELLS + 1, dtype=layer.values.dtype)
    flat[:CELLS].reshape(SIDE, SIDE)[...] = embed(layer, frame_box(origin), layer.values.dtype)
    return flat


def frame_rows(positions: np.ndarray, origin: Position) -> np.ndarray:
    """Sorted unique frame rows of (n, 2) map positions; every position must lie in the frame."""
    if positions.size == 0:
        return np.zeros(0, dtype=np.int64)
    offsets = positions.astype(np.int64) - np.asarray(origin, dtype=np.int64)
    if np.abs(offsets).max() > R:
        raise ValueError(f"perception reach exceeds the route table radius {R}")
    return np.unique((offsets[:, 0] + R) * SIDE + offsets[:, 1] + R)


def frame_index(xs: np.ndarray, ys: np.ndarray, origin: Position) -> np.ndarray:
    """Frame rows of map cells, OFF for cells outside the frame."""
    fx, fy = xs - origin[0] + R, ys - origin[1] + R
    inside = (fx >= 0) & (fx < SIDE) & (fy >= 0) & (fy < SIDE)
    return np.where(inside, fx * SIDE + fy, OFF)


def rows_positions(rows: np.ndarray, origin: Position) -> List[Position]:
    return list(zip((rows // SIDE - R + origin[0]).tolist(), (rows % SIDE - R + origin[1]).tolist()))


def layer_window(layer: CellLayer, window: Box) -> np.ndarray:
    """A view of a layer's values over a window inside its box (writes reach the layer)."""
    return layer.values[window[0] - layer.x0:window[2] - layer.x0 + 1, window[1] - layer.y0:window[3] - layer.y0 + 1]


def window_of(frame: np.ndarray, origin: Position, window: Box) -> np.ndarray:
    """The part of a flat frame inside a window box (which must lie inside the frame)."""
    fx0, fy0 = origin[0] - R, origin[1] - R
    return frame[:CELLS].reshape(SIDE, SIDE)[window[0] - fx0:window[2] - fx0 + 1,
                                             window[1] - fy0:window[3] - fy0 + 1].copy()


# ---------------------------------------------------------------- routes


@dataclass(frozen=True)
class RouteRows:
    """Physical-FOV candidates of one origin and radius, with their supercover route gathers."""

    rows: np.ndarray       # frame rows of the wall-FOV candidates, sorted
    before: np.ndarray     # every route's cells without its endpoint, concatenated, plus one OFF sentinel
    starts: np.ndarray     # each route's first offset in `before`
    empty: np.ndarray      # routes with no cell before the endpoint (the origin)
    near: np.ndarray       # the route cell before the endpoint (OFF for the origin)


def route_rows(rows: np.ndarray) -> RouteRows:
    steps, lengths = supercover_route_table()
    row_lengths = lengths[rows].astype(np.int64)
    width = int(row_lengths.max()) if rows.size else 1
    kept = np.arange(width)[None, :] < (row_lengths - 1)[:, None]
    before = np.append((steps[rows, :width][kept] >> ROUTE_STEP_SHIFT).astype(np.int64), OFF)
    starts = (np.concatenate(([0], np.cumsum(row_lengths - 1)[:-1])).astype(np.int64) if rows.size
              else np.zeros(0, np.int64))
    near = np.where(row_lengths >= 2, steps[rows, np.maximum(row_lengths - 2, 0)] >> ROUTE_STEP_SHIFT,
                    OFF).astype(np.int64)
    return RouteRows(rows, before, starts, row_lengths < 2, near)


def routes_or(routes: RouteRows, bits: np.ndarray) -> np.ndarray:
    """Per route, the OR of a frame's bits over the cells before its endpoint."""
    if routes.rows.size == 0:
        return np.zeros(0, dtype=bits.dtype)
    combined = np.bitwise_or.reduceat(bits[routes.before], routes.starts)
    combined[routes.empty] = 0
    return combined


def range_bits(modes: Mapping[SensesType, int], ordinary_sight: bool, distance: np.ndarray) -> np.ndarray:
    """Per cell, PLAIN for ordinary sight and each special visual sense's bit where it reaches."""
    bits = np.full(distance.shape, PLAIN if ordinary_sight else 0, dtype=np.uint8)
    for sense, bit in VISUAL_SENSES:
        sense_range = modes.get(sense)
        if sense_range is None:
            continue
        bits |= bit if sense_range == 0 else np.where(distance <= sense_range, bit, 0).astype(np.uint8)
    return bits


def reach_mask(modes: Mapping[SensesType, int], sense_type: SensesType, distance: np.ndarray) -> np.ndarray:
    """Where one sense reaches (bool, aligned with the distances)."""
    sense_range = modes.get(sense_type)
    if sense_range is None:
        return np.zeros(distance.shape, dtype=bool)
    if sense_range == 0:
        return np.ones(distance.shape, dtype=bool)
    return distance <= sense_range


@dataclass(frozen=True)
class RouteSight:
    """One observer's wall-FOV routes judged without light: what range and obscurement let through.

    Light is the only input of sight it leaves out, so a light change re-reads only `lit_view`.
    """

    rows: np.ndarray             # wall-FOV candidates holding a Tile, sorted
    in_range: np.ndarray         # range bits per row
    at_cell: np.ndarray          # OBSCUREMENT_BITS at each row's cell
    before: np.ndarray           # OBSCUREMENT_BITS on the route before each row's cell
    near: np.ndarray             # the route cell before each row's cell (OFF for the origin)


@dataclass(frozen=True)
class OpticalView:
    """One observer's optical cells in its frame: the visible ones and the first opaque surfaces."""

    rows: np.ndarray             # visible frame rows, sorted
    light: np.ndarray            # effective LightLevel values, aligned with rows
    eligibility: np.ndarray      # eligibility bits, aligned with rows
    surface_rows: np.ndarray     # first opaque volume surfaces seen (their contents are not)
    surface_light_rows: np.ndarray   # whose light shows the surface
    surface_eligibility: np.ndarray


def route_sight(routes: RouteRows, modes: Mapping[SensesType, int], ordinary_sight: bool,
                exists: np.ndarray, obscurement: np.ndarray) -> RouteSight:
    """Range and obscurement of every wall-FOV route; `exists` and `obscurement` are flat frames."""
    keep = exists[routes.rows]
    rows = routes.rows[keep]
    before = routes_or(routes, obscurement)[keep] if obscurement.any() else np.zeros(rows.size, dtype=np.uint8)
    return RouteSight(rows, range_bits(modes, ordinary_sight, FRAME_DISTANCE_FEET[rows]), obscurement[rows],
                      before, routes.near[keep])


def lit_view(sight: RouteSight, exists: np.ndarray, light: np.ndarray) -> OpticalView:
    """Visible cells, effective light and eligibility of the routes under the objective light.

    `light` is a flat frame (objective LightLevel) around the routes' origin. A hidden
    cell that itself carries obscurement is a first opaque surface, judged on the route
    before it: its own cloud does not hide its surface; under magical darkness the light
    comes from the previous route cell.
    """
    rows, at_cell, before, in_range = sight.rows, sight.at_cell, sight.before, sight.in_range
    eligibility = in_range & SURVIVORS[before | at_cell]
    effective = LIGHT_TABLE[eligibility, light[rows]]
    visible = effective != UNSEEN
    surface = ~visible & (at_cell != 0)
    surface_rows = rows[surface]
    surface_eligibility = in_range[surface] & SURVIVORS[before[surface]]
    near = sight.near[surface]
    surface_light = np.where(((at_cell[surface] & MAGICAL_DARKNESS_BIT) != 0) & (surface_rows != CENTER)
                             & exists[near], near, surface_rows)
    established = surface_eligibility != 0
    return OpticalView(rows[visible], effective[visible], eligibility[visible], surface_rows[established],
                       surface_light[established], surface_eligibility[established])


# ---------------------------------------------------------------- the wall FOV

# A cell's outgoing cardinal edges, in bit order: east, west, north, south.
CARDINAL_DIRECTIONS = (CardinalDirection.EAST, CardinalDirection.WEST, CardinalDirection.NORTH, CardinalDirection.SOUTH)
CARDINAL_STEPS = ((1, 0), (-1, 0), (0, 1), (0, -1))
OPPOSITE_CARDINAL = tuple(CARDINAL_STEPS.index((-dx, -dy)) for dx, dy in CARDINAL_STEPS)
# The steps a route can enter a cell by, one entry layer each (`entry_layers`): the cardinal ones in
# CARDINAL_STEPS order, then the diagonal ones; and the route table's kind of each.
ENTRY_STEPS = CARDINAL_STEPS + ((1, 1), (1, -1), (-1, 1), (-1, -1))
ENTRY_KINDS = tuple(STEP_DIAGONAL if dx and dy else STEP_ALONG_X if dx else STEP_ALONG_Y for dx, dy in ENTRY_STEPS)


# Routes gathered per batch of targets: bounds the step array a long reach builds.
_ROUTE_BATCH = 16384


# Shifts that spread a cell's four cardinal edge bits over four layers (CARDINAL_STEPS order).
EDGE_SHIFTS = np.arange(len(CARDINAL_STEPS), dtype=np.uint16)[:, None, None]
EDGE_SHIFTS.setflags(write=False)


def entered_by(step: int, size: int) -> Tuple[slice, slice]:
    """Along an axis of `size` cells, the cells a step of `step` enters and, aligned, the cells it leaves."""
    return slice(max(step, 0), size + min(step, 0)), slice(max(-step, 0), size - max(step, 0))


def covering_box(boxes: Sequence[Box]) -> Box:
    """The smallest box holding every box (at least one)."""
    return functools.reduce(union_box, boxes)


def compact_window_groups(windows: Sequence[Box]) -> List[List[int]]:
    """The windows of one batch of wall-FOV solves, as index groups whose covering box holds no more
    cells than their windows together: a group that does not is split at its median window along the
    box's longer side, so far-apart origins (another room, another island) never share one large box."""
    def area(box: Box) -> int:
        return (box[2] - box[0] + 1) * (box[3] - box[1] + 1)
    done: List[List[int]] = []
    pending = [list(range(len(windows)))] if windows else []
    while pending:
        group = pending.pop()
        box = covering_box([windows[index] for index in group])
        if len(group) == 1 or area(box) <= sum(area(windows[index]) for index in group):
            done.append(group)
            continue
        axis = 0 if box[2] - box[0] >= box[3] - box[1] else 1
        ranked = sorted(group, key=lambda index: windows[index][axis] + windows[index][axis + 2])
        pending += [ranked[:len(ranked) // 2], ranked[len(ranked) // 2:]]
    return done


def entry_layers(stop: np.ndarray, blocked: np.ndarray) -> np.ndarray:
    """Per ENTRY_STEPS step and cell, whether a route entering the cell by that step stops there: the step blocks,
    or the cell it leaves stops (`stop`: no Tile, or a center that blocks). A cardinal step blocks when its edge
    does (`blocked`: bit d set when the cell's edge toward its neighbor in CARDINAL_STEPS[d] blocks); a diagonal
    one when no bridge (a cell beside both of its ends) is open, that is, neither stops nor has a blocked leg.
    A cell entered from outside the arrays stays False."""
    width, height = stop.shape
    edges = ((blocked[None] >> EDGE_SHIFTS) & 1) != 0
    # A cardinal step out of a cell stops at its edge or at the cell itself.
    leaving = edges | stop[None]
    along_x = {step: entered_by(step, width) for step in (-1, 0, 1)}
    along_y = {step: entered_by(step, height) for step in (-1, 0, 1)}
    layers = np.zeros((len(ENTRY_STEPS), width, height), dtype=bool)
    for layer, (dx, dy) in enumerate(ENTRY_STEPS):
        (xs, from_xs), (ys, from_ys) = along_x[dx], along_y[dy]
        if not (dx and dy):
            layers[layer, xs, ys] = leaving[layer, from_xs, from_ys]
            continue
        edge_x, edge_y = CARDINAL_STEPS.index((dx, 0)), CARDINAL_STEPS.index((0, dy))
        # From p = c - (dx, dy) through (c.x, p.y) or through (p.x, c.y).
        through_x = edges[edge_x, from_xs, from_ys] | leaving[edge_y, xs, from_ys]
        through_y = edges[edge_y, from_xs, from_ys] | leaving[edge_x, from_xs, ys]
        layers[layer, xs, ys] = (through_x & through_y) | stop[from_xs, from_ys]
    return layers


def wall_visibility(stop: CellLayer, blocked: CellLayer,
                    solves: Sequence[Tuple[Position, Box, np.ndarray]]) -> List[Tuple[np.ndarray, np.ndarray]]:
    """For each (origin, window, targets), the targets whose supercover route from the origin is clear, as
    window indices, x-major.

    `stop` and `blocked` (as in `entry_layers`) cover one box holding every window; a window holds its origin,
    and `targets` marks the cells of the window asked about. A route is clear when every step crosses an open
    edge and no cell strictly between the origin and the target stops it; a diagonal step is open through a
    bridge that does not stop and has both legs open. A route and its bridges stay in the box between the origin
    and its target, so only the inputs there are read.

    A cell's entry bits depend on the origin only through the quadrant it is entered from: they are built once
    for every origin, and each origin's frame takes the layers of its quadrants. The exception is the first
    step: a route leaves its origin whatever the origin's center, so the neighbors of an origin that stops are
    rebuilt with its stop cleared (a bridge is never the origin). The route table's steps then read one bit per
    step of every target's route; every read steps back toward the origin from a cell off its row or column,
    so it stays in the window.
    """
    layers = entry_layers(stop.values, blocked.values)
    return [_clear_targets(origin, window, targets, stop, blocked, layers) for origin, window, targets in solves]


def _clear_targets(origin: Position, window: Box, targets: np.ndarray, stop: CellLayer, blocked: CellLayer,
                   layers: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """One origin's clear targets (`wall_visibility`), from the entry layers of the solve's box."""
    width, height = targets.shape
    oi, oj = origin[0] - window[0], origin[1] - window[1]
    # The frame holds the window: the kept route table's within R, a larger one beyond it.
    radius = max(R, oi, oj, width - 1 - oi, height - 1 - oj)
    side = 2 * radius + 1
    fx, fy = radius - oi, radius - oj
    frame = np.zeros((side * side + 1) << ROUTE_STEP_SHIFT, dtype=bool)   # STEP_NONE and the padding stay zero
    entry = frame[:(side * side) << ROUTE_STEP_SHIFT].reshape(side, side, 1 << ROUTE_STEP_SHIFT)[
        fx:fx + width, fy:fy + height]
    ax, ay = window[0] - stop.x0, window[1] - stop.y0
    for layer, ((dx, dy), kind) in enumerate(zip(ENTRY_STEPS, ENTRY_KINDS)):
        # The cells a route from the origin enters by this step: past the origin along each axis the step moves.
        xs = slice(oi + 1, width) if dx > 0 else slice(0, oi) if dx < 0 else slice(0, width)
        ys = slice(oj + 1, height) if dy > 0 else slice(0, oj) if dy < 0 else slice(0, height)
        entry[xs, ys, kind] = layers[layer, ax + xs.start:ax + xs.stop, ay + ys.start:ay + ys.stop]
    gx, gy = origin[0] - stop.x0, origin[1] - stop.y0
    if stop.values[gx, gy]:
        x0, y0 = max(gx - 1, 0), max(gy - 1, 0)
        near_stop = stop.values[x0:gx + 2, y0:gy + 2].copy()
        near_stop[gx - x0, gy - y0] = False
        near = entry_layers(near_stop, blocked.values[x0:gx + 2, y0:gy + 2])
        for layer, ((dx, dy), kind) in enumerate(zip(ENTRY_STEPS, ENTRY_KINDS)):
            if 0 <= oi + dx < width and 0 <= oj + dy < height:
                entry[oi + dx, oj + dy, kind] = near[layer, gx + dx - x0, gy + dy - y0]
    ti, tj = np.nonzero(targets)
    clear = np.zeros(ti.size, dtype=bool)
    for start in range(0, ti.size, _ROUTE_BATCH):
        batch = slice(start, start + _ROUTE_BATCH)
        steps, _ = supercover_routes(ti[batch] - oi, tj[batch] - oj, radius)
        clear[batch] = ~frame[steps].any(axis=1)
    return ti[clear], tj[clear]


# ---------------------------------------------------------------- published cells and their queries


@dataclass(frozen=True)
class PerceivedCells:
    """An observer's published cells over its window: what it sees, in which light, with which
    eligibility, and which seen cells it knows to be hazardous. Values outside `visible` are zero."""

    visible: CellLayer       # bool
    light: CellLayer         # uint8 effective LightLevel
    eligibility: CellLayer   # uint8 eligibility bits
    hazard: CellLayer        # bool


def empty_layer(dtype: type) -> CellLayer:
    return CellLayer(0, 0, np.zeros((0, 0), dtype=dtype))


NO_CELLS = PerceivedCells(empty_layer(bool), empty_layer(np.uint8), empty_layer(np.uint8), empty_layer(bool))


def cell_visible(cells: PerceivedCells, position: Position) -> bool:
    return bool(layer_value(cells.visible, position))


def cell_light(cells: PerceivedCells, position: Position) -> Optional[LightLevel]:
    """The observer-effective light of a visible cell, None for a cell it does not see."""
    return LIGHT_LEVELS[layer_value(cells.light, position)] if layer_value(cells.visible, position) else None


def cell_hazard(cells: PerceivedCells, position: Position) -> Optional[bool]:
    """Whether a visible cell is known hazardous, None for a cell the observer does not see."""
    return bool(layer_value(cells.hazard, position)) if layer_value(cells.visible, position) else None


def visible_positions(cells: PerceivedCells) -> List[Position]:
    """Every visible cell, x-major sorted."""
    return layer_positions(cells.visible)


def visible_count(cells: PerceivedCells) -> int:
    return int(np.count_nonzero(cells.visible.values))


def cell_seen(seen: CellLayer, position: Position) -> bool:
    """Whether a cell is in an observer's memory of seen cells."""
    return bool(layer_value(seen, position))


def visible_box(cells: PerceivedCells) -> Optional[Box]:
    """The bounding box of the visible cells, None when none is visible."""
    xs, ys = np.nonzero(cells.visible.values)
    if not xs.size:
        return None
    x0, y0 = cells.visible.x0, cells.visible.y0
    return int(xs.min()) + x0, int(ys.min()) + y0, int(xs.max()) + x0, int(ys.max()) + y0
