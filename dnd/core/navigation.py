"""Navigation as arrays (plan §6b PT): the result of a path search, an observer's admitted routes, and their paths.

A search runs over a padded box of map cells; a cell's flat index is (x - x0) * height + (y - y0), so flat
order is (x, y) order, and the extra index OFF (= width * height) stands for "no cell". Its result is a
`PathTree`: each reached cell's cost and predecessor and the cells in the order the search found them. An
observer's navigation is `Routes`: the destinations admitted over one tree, in tree order, each with the kind of
path chosen for it (the tree path, or an equal-cost monotone route the preference picked). Paths are rebuilt
from the predecessors when read; nothing per cell is kept in Python containers. Every array here is read-only.

The neighbour order (`STEPS`) and the route preference are the engine's movement rules: changing either changes
which of several equal-cost paths a creature walks. The search itself runs in its predicate's owner
(`GridMap.compute_paths`); this module takes primitives and arrays and never imports a block, an entity or the
map (imports: numpy, dnd.core.view).
"""

from dataclasses import dataclass
import math
from typing import Collection, Dict, List, Optional, Sequence, Tuple

import numpy as np

from dnd.core.view import CellLayer, embed

Position = Tuple[int, int]
Box = Tuple[int, int, int, int]  # inclusive (min_x, min_y, max_x, max_y)

# The search's neighbour order: north, east, south, west, then the diagonals. A cell's predecessor is the
# first expanded cell, in this order, that reaches it. Bit d of an edge-answer byte is the step STEPS[d].
STEPS: Tuple[Position, ...] = ((0, 1), (1, 0), (0, -1), (-1, 0), (1, 1), (1, -1), (-1, 1), (-1, -1))
CARDINAL_COUNT = 4
STEP_INDEX: Dict[Position, int] = {step: index for index, step in enumerate(STEPS)}
STEP_BITS = (1 << np.arange(len(STEPS))).astype(np.uint8)
# Tile-relative direction names (`Tile.directions_toward`, CardinalDirection values) as STEPS indices: the bit
# a remembered directional collision and a boundary side use.
DIRECTION_STEP: Dict[str, int] = {"north": 0, "east": 1, "south": 2, "west": 3}
# Weighted searches add this to a diagonal step's priority (not to its cost), so equal costs prefer fewer
# diagonals.
DIAGONAL_EPSILON = 0.001
# Route kinds: the tree path, or the monotone route taking the diagonal steps first or the cardinal steps first.
TREE_ROUTE, DIAGONAL_FIRST, CARDINAL_FIRST = 0, 1, 2


def frozen_array(values: np.ndarray) -> np.ndarray:
    """The array, made read-only (a kept value is never written)."""
    values.flags.writeable = False
    return values


@dataclass(frozen=True, eq=False)
class PathTree:
    """One path search's published result, from `origin` over the padded box (x0, y0, width, height); its
    arrays are flat over the box plus OFF.

    `cost` is each reached cell's cost in movement units (-1 unreached), `pred` its predecessor (OFF for the
    origin and unreached cells), `order` the reached cells in the order the search found them (origin first).
    """

    origin: Position
    x0: int
    y0: int
    width: int
    height: int
    cost: np.ndarray
    pred: np.ndarray
    order: np.ndarray


@dataclass(frozen=True, eq=False)
class Routes:
    """Destinations over one tree, in tree order (`destinations`, flat), each one's index there by cell (`slot`,
    -1 for any other cell) and the kind of path chosen for it (`kinds`): an observer's admitted routes, or
    every reached cell of a search (`reached_routes`)."""

    tree: PathTree
    destinations: np.ndarray
    slot: np.ndarray
    kinds: np.ndarray


@dataclass(frozen=True, eq=False)
class PathSearch:
    """A search and the inputs it read, kept together by the map's path cache: `reached` holds every reached
    cell with its tree path; `step_cost` is the movement-unit cost of entering each cell (0 without a Tile);
    bit d of `allowed` answers the step STEPS[d] out of a cell where the same bit of `settled` is set."""

    reached: Routes
    step_cost: np.ndarray
    allowed: np.ndarray
    settled: np.ndarray


def flat_offsets(height: int) -> np.ndarray:
    """The flat index offset of each of the STEPS in a box of this height."""
    return np.array([dx * height + dy for dx, dy in STEPS], dtype=np.int64)


def search_box(start: Position, max_distance: Optional[int], bounds: Box) -> Box:
    """The cells a search from `start` can reach: within floor(max_distance) steps (every step costs at least
    one unit) and inside the map bounds."""
    if max_distance is None:
        return bounds
    radius = max(0, math.floor(max_distance))
    return (max(bounds[0], start[0] - radius), max(bounds[1], start[1] - radius),
            min(bounds[2], start[0] + radius), min(bounds[3], start[1] + radius))


def padded(box: Box) -> Tuple[int, int, int, int]:
    """(x0, y0, width, height) of a search box with a one-cell ring that is never entered."""
    return box[0] - 1, box[1] - 1, box[2] - box[0] + 3, box[3] - box[1] + 3


def path_tree(origin: Position, x0: int, y0: int, width: int, height: int, cost: np.ndarray, pred: np.ndarray,
              order: np.ndarray) -> PathTree:
    return PathTree(origin, x0, y0, width, height, frozen_array(cost), frozen_array(pred), frozen_array(order))


def lone_search(origin: Position) -> PathSearch:
    """The search that reaches only its origin."""
    x0, y0, width, height = padded((origin[0], origin[1], origin[0], origin[1]))
    size = width * height
    flat = (origin[0] - x0) * height + origin[1] - y0
    cost = np.full(size + 1, -1, dtype=np.int64)
    cost[flat] = 0
    tree = path_tree(origin, x0, y0, width, height, cost, np.full(size + 1, size, dtype=np.int64),
                     np.array([flat], dtype=np.int64))
    return PathSearch(reached_routes(tree), frozen_array(np.zeros(size + 1, dtype=np.float64)),
                      frozen_array(np.zeros(size + 1, dtype=np.uint8)), frozen_array(np.zeros(size + 1, dtype=np.uint8)))


# ---------------------------------------------------------------- reading a tree


def _flat(tree: PathTree, position: Position) -> int:
    """A cell's flat index in the tree's box, OFF outside it."""
    i, j = position[0] - tree.x0, position[1] - tree.y0
    if 0 <= i < tree.width and 0 <= j < tree.height:
        return i * tree.height + j
    return tree.width * tree.height


def _position(tree: PathTree, flat: int) -> Position:
    return tree.x0 + flat // tree.height, tree.y0 + flat % tree.height


def _chain(tree: PathTree, flat: int) -> List[Position]:
    off = tree.width * tree.height
    pred = tree.pred
    reversed_path = []
    while flat != off:
        reversed_path.append(_position(tree, flat))
        flat = int(pred[flat])
    reversed_path.reverse()
    return reversed_path


def tree_box(tree: PathTree) -> Box:
    """The box of map cells the tree's arrays cover."""
    return tree.x0, tree.y0, tree.x0 + tree.width - 1, tree.y0 + tree.height - 1


def tree_cells(tree: PathTree, layer: CellLayer) -> np.ndarray:
    """A map layer over the tree's box as a flat bool array (OFF False)."""
    return np.append(embed(layer, tree_box(tree), np.dtype(bool)).ravel(), False)


def tree_mask(tree: PathTree, positions: Collection[Position]) -> np.ndarray:
    """Some map cells over the tree's box as a flat bool array (cells outside it are dropped)."""
    mask = np.zeros(tree.width * tree.height + 1, dtype=bool)
    if positions:
        cells = np.array(list(positions), dtype=np.int64).reshape(-1, 2) - (tree.x0, tree.y0)
        inside = (cells[:, 0] >= 0) & (cells[:, 0] < tree.width) & (cells[:, 1] >= 0) & (cells[:, 1] < tree.height)
        mask[cells[inside, 0] * tree.height + cells[inside, 1]] = True
    return mask


# ---------------------------------------------------------------- admitted routes


def _ancestors(pred: np.ndarray, cells: np.ndarray, off: int) -> np.ndarray:
    """Row k holds the k-th predecessor of each cell (OFF past the origin): the paths, reversed, by column."""
    rows = [cells]
    current = cells
    while True:
        current = pred[current]
        if (current == off).all():
            return np.stack(rows)
        rows.append(current)


def _routes(tree: PathTree, destinations: np.ndarray, kinds: np.ndarray) -> Routes:
    slot = np.full(tree.width * tree.height + 1, -1, dtype=np.int64)
    slot[destinations] = np.arange(destinations.size)
    return Routes(tree, frozen_array(destinations), frozen_array(slot), frozen_array(kinds))


def admit(tree: PathTree, known: np.ndarray, end_blocked: np.ndarray) -> Routes:
    """The reached cells whose whole path (origin included) is in `known` and that are not in `end_blocked`,
    in tree order; each with its tree path."""
    off = tree.width * tree.height
    cells = tree.order
    paths = _ancestors(tree.pred, cells, off)
    known_path = np.where(paths != off, known[paths], True).all(axis=0)
    destinations = cells[known_path & ~end_blocked[cells]]
    return _routes(tree, destinations, np.zeros(destinations.size, dtype=np.uint8))


def reached_routes(tree: PathTree) -> Routes:
    """Every reached cell of a tree, in the order the search found it, with its tree path."""
    return _routes(tree, tree.order, np.zeros(tree.order.size, dtype=np.uint8))


NO_ROUTES = admit(lone_search((0, 0)).reached.tree, np.zeros(10, dtype=bool), np.zeros(10, dtype=bool))


def route_count(routes: Routes) -> int:
    return int(routes.destinations.size)


def has_route(routes: Routes, position: Position) -> bool:
    return bool(routes.slot[_flat(routes.tree, position)] >= 0)


def route_units(routes: Routes, position: Position) -> Optional[int]:
    """A destination's movement cost in movement units, None for any other cell."""
    flat = _flat(routes.tree, position)
    return int(routes.tree.cost[flat]) if routes.slot[flat] >= 0 else None


def route_cost(routes: Routes, position: Position) -> Optional[int]:
    """A destination's movement cost in feet, None for any other cell."""
    units = route_units(routes, position)
    return units * 5 if units is not None else None


def route_destinations(routes: Routes) -> List[Position]:
    """The admitted destinations, in tree order."""
    tree = routes.tree
    return list(zip((routes.destinations // tree.height + tree.x0).tolist(),
                    (routes.destinations % tree.height + tree.y0).tolist()))


def _monotone(origin: Position, destination: Position, kind: int) -> List[Position]:
    """The route taking the diagonal steps first (DIAGONAL_FIRST) or the cardinal steps first; the vectorized
    form is `route_candidates`' `candidate`."""
    dx, dy = destination[0] - origin[0], destination[1] - origin[1]
    sx, sy = (dx > 0) - (dx < 0), (dy > 0) - (dy < 0)
    diagonal = [(sx, sy)] * min(abs(dx), abs(dy))
    cardinal = [(sx, 0) if abs(dx) > abs(dy) else (0, sy)] * abs(abs(dx) - abs(dy))
    path = [origin]
    for step_x, step_y in (diagonal + cardinal if kind == DIAGONAL_FIRST else cardinal + diagonal):
        x, y = path[-1]
        path.append((x + step_x, y + step_y))
    return path


def route(routes: Routes, position: Position) -> Optional[List[Position]]:
    """The path chosen for an admitted destination (a new list), None for any other cell."""
    tree = routes.tree
    flat = _flat(tree, position)
    index = int(routes.slot[flat])
    if index < 0:
        return None
    kind = int(routes.kinds[index])
    return _chain(tree, flat) if kind == TREE_ROUTE else _monotone(tree.origin, position, kind)


def routes_box(routes: Routes) -> Optional[Box]:
    """The bounding box of every cell on the chosen paths, None without destinations. A monotone route lies in
    the box of its origin and destination."""
    if not routes.destinations.size:
        return None
    tree = routes.tree
    off = tree.width * tree.height
    parts = [routes.destinations, np.array([_flat(tree, tree.origin)], dtype=np.int64)]
    along_tree = routes.kinds == TREE_ROUTE
    if along_tree.any():
        paths = _ancestors(tree.pred, routes.destinations[along_tree], off)
        parts.append(paths[paths != off])
    cells = np.concatenate(parts)
    xs, ys = cells // tree.height + tree.x0, cells % tree.height + tree.y0
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


def routes_touch(routes: Routes, mask: np.ndarray) -> bool:
    """Whether a cell after the origin on an admitted tree path is in the flat mask."""
    if not routes.destinations.size:
        return False
    off = routes.tree.width * routes.tree.height
    paths = _ancestors(routes.tree.pred, routes.destinations, off)
    paths = paths[paths != off]
    return bool(mask[paths[paths != _flat(routes.tree, routes.tree.origin)]].any())


# ---------------------------------------------------------------- the route preference


@dataclass(frozen=True, eq=False)
class RouteCandidates:
    """The equal-cost monotone routes `route_candidates` keeps for one `Routes`, before their steps are read.

    `chosen` indexes `Routes.destinations`; per route (diagonal-first, then cardinal-first) `cells`,
    `previous` and `directions` are (steps, chosen) arrays (OFF past its end), `considered` says whether it is
    weighed at all (differs from the current path, known, same cost), `risk` its risk words. `best` / `turns`
    are the tree paths' risk and turns, `floor` the fewest turns possible.
    """

    chosen: np.ndarray
    within: np.ndarray
    cells: Tuple[np.ndarray, np.ndarray]
    previous: Tuple[np.ndarray, np.ndarray]
    directions: Tuple[np.ndarray, np.ndarray]
    considered: Tuple[np.ndarray, np.ndarray]
    risk: Tuple[np.ndarray, np.ndarray]
    best: np.ndarray
    turns: np.ndarray
    floor: np.ndarray


def _risk_bits(size: int, hazard: np.ndarray, domains: Sequence[np.ndarray]) -> Tuple[np.ndarray, np.ndarray]:
    """Per cell, as uint64 words over one bit space (each hazardous cell, then each reactor): its own hazard bit,
    and the reactors whose threat domain holds it. A step's risk is the target's hazard bit plus the reactors
    whose domain holds the source and not the target."""
    hazardous = np.flatnonzero(hazard[:size])
    bits = hazardous.size + len(domains)
    words = (bits + 63) // 64
    own = np.zeros((size + 1, words), dtype=np.uint64)
    member = np.zeros((size + 1, words), dtype=np.uint64)
    if hazardous.size:
        index = np.arange(hazardous.size)
        own[hazardous, index // 64] = np.left_shift(np.uint64(1), (index % 64).astype(np.uint64))
    for reactor, domain in enumerate(domains):
        bit = hazardous.size + reactor
        member[np.flatnonzero(domain[:size]), bit // 64] |= np.left_shift(np.uint64(1), np.uint64(bit % 64))
    return own, member


def _path_risk(sources: np.ndarray, targets: np.ndarray, valid: np.ndarray,
               own: np.ndarray, member: np.ndarray) -> np.ndarray:
    """OR of the step risks over the valid steps of each column: (steps, columns) -> (columns, words)."""
    risk = own[targets] | (member[sources] & ~member[targets])
    risk[~valid] = 0
    return np.bitwise_or.reduce(risk, axis=0) if risk.shape[0] else np.zeros(risk.shape[1:], dtype=np.uint64)


def route_candidates(routes: Routes, search: PathSearch, known: np.ndarray, hazard: np.ndarray,
                     domains: Sequence[np.ndarray], has_reachable_hazard: bool) -> Optional[RouteCandidates]:
    """The route preference's candidates (first pass; `choose_routes` decides once their steps are read).

    A destination is weighed when its tree path has more turns than the fewest possible (one when both
    diagonal and cardinal steps are needed) or crosses a hazardous cell (`hazard`) or leaves a hostile's threat
    domain (`domains`, in reactor order), and the tree path's integer cost in feet (each entered cell's cost
    must be a positive integer) equals its cost. Its candidates are the diagonal-first and the cardinal-first
    route (the second skipped when it is the same route as the first and the first differs from the tree
    path); a candidate is considered when it differs from the tree path, every cell is `known`, and it has the
    same integer cost. None when no destination is weighed.
    """
    tree = routes.tree
    height, size = tree.height, tree.width * tree.height
    origin = _flat(tree, tree.origin)
    cells = routes.destinations
    dx = cells // height - origin // height
    dy = cells % height - origin % height
    moving = (dx != 0) | (dy != 0)
    if not moving.any():
        return None
    diagonal_steps = np.minimum(np.abs(dx), np.abs(dy))
    cardinal_steps = np.abs(np.abs(dx) - np.abs(dy))
    minimum_turns = ((diagonal_steps > 0) & (cardinal_steps > 0)).astype(np.int64)
    direction_of = np.zeros(2 * height + 3, dtype=np.int64)
    direction_of[flat_offsets(height) + height + 1] = np.arange(len(STEPS))

    paths = _ancestors(tree.pred, cells, size)
    steps = paths[1:] != size                                   # step k: paths[k + 1] -> paths[k]
    step_direction = direction_of[np.where(steps, paths[:-1] - paths[1:], 0) + height + 1]
    turns = (steps[:-1] & steps[1:] & (step_direction[:-1] != step_direction[1:])).sum(axis=0)
    weighed = moving & ~((turns == minimum_turns) & (not has_reachable_hazard) & (not domains))
    if not weighed.any():
        return None
    own, member = _risk_bits(size, hazard, domains)
    best = _path_risk(paths[1:], paths[:-1], steps, own, member)
    weighed &= ~((turns == minimum_turns) & ~best.any(axis=1))
    step_cost = search.step_cost
    integral = (step_cost > 0) & (step_cost == np.floor(step_cost))
    feet = np.where(integral, step_cost, 0).astype(np.int64) * 5
    tree_feet = np.where(steps, feet[paths[:-1]], 0).sum(axis=0)
    tree_integral = np.where(steps, integral[paths[:-1]], True).all(axis=0)
    weighed &= tree_integral & (tree_feet == tree.cost[cells] * 5)
    if not weighed.any():
        return None

    chosen = np.flatnonzero(weighed)
    d, c = diagonal_steps[chosen], cardinal_steps[chosen]
    sx, sy = np.sign(dx[chosen]), np.sign(dy[chosen])
    wide = np.abs(dx[chosen]) > np.abs(dy[chosen])
    cx, cy = np.where(wide, sx, 0), np.where(wide, 0, sy)
    length = d + c
    k = np.arange(1, int(length.max()) + 1)[:, None]          # (steps, chosen)
    within = k <= length[None, :]
    depth = steps[:, chosen].sum(axis=0)
    tree_cells_by_depth = paths[:, chosen]
    diagonal_direction = direction_of[sx * height + sy + height + 1]
    cardinal_direction = direction_of[cx * height + cy + height + 1]
    columns = np.arange(chosen.size)[None, :]

    def candidate(first_x, first_y, first_steps, first_direction, second_x, second_y, second_direction):
        """The route taking `first_steps` steps one way, then the rest the other way: cells, the cell before
        each, step directions, and whether it is considered, with its risk."""
        along_first = np.minimum(k, first_steps[None, :])
        along_second = np.maximum(k - first_steps[None, :], 0)
        flat = origin + (along_first * first_x + along_second * second_x) * height + (
            along_first * first_y + along_second * second_y)
        flat = np.where(within, flat, size)
        previous = np.vstack([np.full((1, flat.shape[1]), origin, dtype=np.int64), flat[:-1]])
        directions = np.where(k <= first_steps[None, :], first_direction[None, :], second_direction[None, :])
        tree_cell = tree_cells_by_depth[np.clip(depth[None, :] - k, 0, tree_cells_by_depth.shape[0] - 1), columns]
        equal = (length == depth) & np.where(within, flat == tree_cell, True).all(axis=0)
        known_route = np.where(within, known[flat], True).all(axis=0)
        same_cost = (np.where(within, integral[flat], True).all(axis=0)
                     & (np.where(within, feet[flat], 0).sum(axis=0) == tree_feet[chosen]))
        return flat, previous, directions, equal, known_route & same_cost, _path_risk(previous, flat, within, own, member)

    first = candidate(sx, sy, d, diagonal_direction, cx, cy, cardinal_direction)
    second = candidate(cx, cy, c, cardinal_direction, sx, sy, diagonal_direction)
    same_route = (d == 0) | (c == 0)
    considered_first = ~first[3] & first[4]
    considered_second = ~second[3] & ~(~first[3] & same_route) & second[4]
    return RouteCandidates(chosen, within, (first[0], second[0]), (first[1], second[1]), (first[2], second[2]),
                           (considered_first, considered_second), (first[5], second[5]), best[chosen],
                           turns[chosen], minimum_turns[chosen])


def candidate_steps(search: PathSearch, candidates: RouteCandidates) -> Tuple[List[Position], List[Position]]:
    """The steps of considered candidates the search did not settle, as (sources, targets), each once."""
    tree = search.reached.tree
    sources: List[np.ndarray] = []
    for previous, directions, considered in zip(candidates.previous, candidates.directions, candidates.considered):
        read = candidates.within & considered[None, :]
        unsettled = read & ((search.settled[previous] & STEP_BITS[directions]) == 0)
        sources.append(np.stack([previous[unsettled], directions[unsettled]], axis=1))
    pairs = np.unique(np.concatenate(sources), axis=0)
    cells, directions = pairs[:, 0], pairs[:, 1]
    xs, ys = (cells // tree.height + tree.x0).tolist(), (cells % tree.height + tree.y0).tolist()
    steps = [STEPS[direction] for direction in directions.tolist()]
    return list(zip(xs, ys)), [(x + dx, y + dy) for x, y, (dx, dy) in zip(xs, ys, steps)]


def choose_routes(routes: Routes, search: PathSearch, candidates: RouteCandidates,
                  steps: Tuple[List[Position], List[Position]], answers: Sequence[bool]) -> Routes:
    """The route preference's decision (second pass), with `answers` for the `candidate_steps` `steps`.

    Per destination, the diagonal-first then the cardinal-first candidate is taken when it is considered, every
    step is allowed, and its risk is a subset of the current best risk and either smaller or with fewer turns
    than the current path; a taken route becomes the best.
    """
    tree = search.reached.tree
    allowed, settled = search.allowed.copy(), search.settled.copy()
    sources, targets = steps
    if sources:
        cells = np.array([(x - tree.x0) * tree.height + y - tree.y0 for x, y in sources], dtype=np.int64)
        bits = STEP_BITS[[STEP_INDEX[(t[0] - s[0], t[1] - s[1])] for s, t in zip(sources, targets)]]
        np.bitwise_or.at(settled, cells, bits)
        granted = np.array(answers, dtype=bool)
        np.bitwise_or.at(allowed, cells[granted], bits[granted])
    best, best_turns, floor = candidates.best, candidates.turns, candidates.floor
    taken = []
    for previous, directions, considered, risk in zip(candidates.previous, candidates.directions,
                                                      candidates.considered, candidates.risk):
        steps_allowed = np.where(candidates.within, (allowed[previous] & STEP_BITS[directions]) != 0,
                                 True).all(axis=0)
        subset = ~(risk & ~best).any(axis=1)
        same = (risk == best).all(axis=1)
        take = considered & steps_allowed & subset & ~(same & (floor >= best_turns))
        best = np.where(take[:, None], risk, best)
        best_turns = np.where(take, floor, best_turns)
        taken.append(take)
    kinds = routes.kinds.copy()
    kinds[candidates.chosen[taken[0]]] = DIAGONAL_FIRST
    kinds[candidates.chosen[taken[1]]] = CARDINAL_FIRST
    return Routes(tree, routes.destinations, routes.slot, frozen_array(kinds))


# ---------------------------------------------------------------- remembered collisions


def no_collisions() -> CellLayer:
    """An empty remembered-cell layer (bool)."""
    return CellLayer(0, 0, frozen_array(np.zeros((0, 0), dtype=bool)))


def no_side_collisions() -> CellLayer:
    """An empty remembered-side layer (bit 1 << DIRECTION_STEP[direction] per cell)."""
    return CellLayer(0, 0, frozen_array(np.zeros((0, 0), dtype=np.uint8)))


def layer_key(layer: Optional[CellLayer]) -> Tuple[Tuple[int, int, int], ...]:
    """A layer's nonzero cells and values, x-major: a hashable key for what it holds."""
    if layer is None or not layer.values.size:
        return ()
    xs, ys = np.nonzero(layer.values)
    return tuple(zip((xs + layer.x0).tolist(), (ys + layer.y0).tolist(), layer.values[xs, ys].astype(int).tolist()))


def mark_cell(layer: CellLayer, position: Position, bits: int) -> CellLayer:
    """A new layer holding the old one's values plus `bits` at one cell (the old layer is not written)."""
    if layer.values.size:
        box = (min(layer.x0, position[0]), min(layer.y0, position[1]),
               max(layer.box[2], position[0]), max(layer.box[3], position[1]))
    else:
        box = (position[0], position[1], position[0], position[1])
    values = embed(layer, box, layer.values.dtype)
    i, j = position[0] - box[0], position[1] - box[1]
    values[i, j] = values[i, j] | bits
    return CellLayer(box[0], box[1], frozen_array(values))
