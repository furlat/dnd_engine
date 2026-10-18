"""Array operations on packed cell sets (`dnd.types.cells`).

A box is (x0, y0, x1, y1), inclusive. Arrays are indexed [x - x0, y - y0], the
cell order of a mask.
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

import numpy as np

from dnd.types.cells import EMPTY_CELLS, EMPTY_VALUES, NO_ROWS, CellMask, CellValues, RowBits

Box = tuple[int, int, int, int]
Position = tuple[int, int]


def mask_box(mask: CellMask) -> Box | None:
    if mask.width == 0:
        return None
    return mask.x0, mask.y0, mask.x0 + mask.width - 1, mask.y0 + mask.height - 1


def union_box(*boxes: Box | None) -> Box | None:
    present = [box for box in boxes if box is not None]
    if not present:
        return None
    return (min(box[0] for box in present), min(box[1] for box in present),
            max(box[2] for box in present), max(box[3] for box in present))


def _grid(mask: CellMask) -> np.ndarray:
    count = mask.width * mask.height
    return np.unpackbits(np.frombuffer(mask.bits, dtype=np.uint8), count=count,
                         bitorder="little").reshape(mask.width, mask.height).view(bool)


def mask_array(mask: CellMask, box: Box) -> np.ndarray:
    """The set over another box: a bool array, False where the set does not reach."""
    own = mask_box(mask)
    if own == box:
        return _grid(mask)
    out = np.zeros((box[2] - box[0] + 1, box[3] - box[1] + 1), dtype=bool)
    if own is None:
        return out
    ax0, ay0, ax1, ay1 = max(box[0], own[0]), max(box[1], own[1]), min(box[2], own[2]), min(box[3], own[3])
    if ax0 <= ax1 and ay0 <= ay1:
        out[ax0 - box[0]:ax1 - box[0] + 1, ay0 - box[1]:ay1 - box[1] + 1] = \
            _grid(mask)[ax0 - own[0]:ax1 - own[0] + 1, ay0 - own[1]:ay1 - own[1] + 1]
    return out


def _trim(x0: int, y0: int, cells: np.ndarray) -> tuple[int, int, slice, slice] | None:
    xs = np.flatnonzero(cells.any(axis=1))
    if not xs.size:
        return None
    ys = np.flatnonzero(cells.any(axis=0))
    return (x0 + int(xs[0]), y0 + int(ys[0]), slice(int(xs[0]), int(xs[-1]) + 1),
            slice(int(ys[0]), int(ys[-1]) + 1))


def pack_mask(x0: int, y0: int, cells: np.ndarray) -> CellMask:
    """The set of the True cells of a bool array anchored at (x0, y0)."""
    trimmed = _trim(x0, y0, cells)
    if trimmed is None:
        return EMPTY_CELLS
    left, bottom, xs, ys = trimmed
    part = cells[xs, ys]
    return CellMask(left, bottom, part.shape[0], part.shape[1],
                    np.packbits(part.ravel(), bitorder="little").tobytes())


def pack_layers(x0: int, y0: int, cells: np.ndarray, *layers: np.ndarray) -> tuple[CellMask, tuple[CellValues, ...]]:
    """The set of the True cells of `cells` and each layer's values there, packed over one trimmed box."""
    trimmed = _trim(x0, y0, cells)
    if trimmed is None:
        return EMPTY_CELLS, tuple(EMPTY_VALUES for _ in layers)
    left, bottom, xs, ys = trimmed
    part = cells[xs, ys]
    mask = CellMask(left, bottom, part.shape[0], part.shape[1], np.packbits(part.ravel(), bitorder="little").tobytes())
    return mask, tuple(CellValues(mask, layer[xs, ys][part].astype(np.uint8).tobytes()) for layer in layers)


def pack_values(x0: int, y0: int, cells: np.ndarray, values: np.ndarray) -> CellValues:
    """The values at the True cells of `cells`, both arrays anchored at (x0, y0)."""
    return pack_layers(x0, y0, cells, values)[1][0]


def _embed(own: Box, box: Box, grid: np.ndarray, layers: list[np.ndarray]) -> tuple[np.ndarray, list[np.ndarray]]:
    """Arrays over `own` placed over another box, zero where they do not reach."""
    if own == box:
        return grid, layers
    cells = np.zeros((box[2] - box[0] + 1, box[3] - box[1] + 1), dtype=bool)
    outs = [np.zeros(cells.shape, dtype=np.uint8) for _ in layers]
    ax0, ay0, ax1, ay1 = max(box[0], own[0]), max(box[1], own[1]), min(box[2], own[2]), min(box[3], own[3])
    if ax0 <= ax1 and ay0 <= ay1:
        target = (slice(ax0 - box[0], ax1 - box[0] + 1), slice(ay0 - box[1], ay1 - box[1] + 1))
        source = (slice(ax0 - own[0], ax1 - own[0] + 1), slice(ay0 - own[1], ay1 - own[1] + 1))
        cells[target] = grid[source]
        for out, layer in zip(outs, layers):
            out[target] = layer[source]
    return cells, outs


def cell_layers(mask: CellMask, layers: tuple[CellValues, ...], box: Box) -> tuple[np.ndarray, list[np.ndarray]]:
    """A set and per-cell values at its cells over another box (zero elsewhere), unpacking the set once
    for the values that share its cells."""
    own = mask_box(mask)
    if own is None:
        shape = (box[2] - box[0] + 1, box[3] - box[1] + 1)
        return np.zeros(shape, dtype=bool), [np.zeros(shape, dtype=np.uint8) for _ in layers]
    grid = _grid(mask)
    full = []
    for layer in layers:
        if layer.cells == mask:
            values = np.zeros(grid.shape, dtype=np.uint8)
            values[grid] = np.frombuffer(layer.values, dtype=np.uint8)
            full.append(values)
        else:
            full.append(values_array(layer, own)[1] * grid)
    return _embed(own, box, grid, full)


def values_array(values: CellValues, box: Box) -> tuple[np.ndarray, np.ndarray]:
    """The cells (bool) and their values (uint8) over another box, zero where they do not reach."""
    own = mask_box(values.cells)
    if own is None:
        shape = (box[2] - box[0] + 1, box[3] - box[1] + 1)
        return np.zeros(shape, dtype=bool), np.zeros(shape, dtype=np.uint8)
    grid = _grid(values.cells)
    full = np.zeros(grid.shape, dtype=np.uint8)
    full[grid] = np.frombuffer(values.values, dtype=np.uint8)
    cells, (out,) = _embed(own, box, grid, [full])
    return cells, out


def mask_positions(mask: CellMask) -> list[Position]:
    """The set's cells in cell order."""
    if mask.width == 0:
        return []
    xs, ys = np.nonzero(_grid(mask))
    return list(zip((xs + mask.x0).tolist(), (ys + mask.y0).tolist()))


def mask_count(mask: CellMask) -> int:
    return int(np.unpackbits(np.frombuffer(mask.bits, dtype=np.uint8)).sum()) if mask.width else 0


def mask_from_positions(positions: Iterable[Position]) -> CellMask:
    cells = np.array(list(positions), dtype=np.int64).reshape(-1, 2)
    if not cells.size:
        return EMPTY_CELLS
    x0, y0 = int(cells[:, 0].min()), int(cells[:, 1].min())
    grid = np.zeros((int(cells[:, 0].max()) - x0 + 1, int(cells[:, 1].max()) - y0 + 1), dtype=bool)
    grid[cells[:, 0] - x0, cells[:, 1] - y0] = True
    return pack_mask(x0, y0, grid)


def values_items(values: CellValues) -> list[tuple[Position, int]]:
    """Each cell with its value, in cell order."""
    return list(zip(mask_positions(values.cells), values.values))


def values_from_items(items: Mapping[Position, int]) -> CellValues:
    if not items:
        return EMPTY_VALUES
    cells = np.array(list(items), dtype=np.int64).reshape(-1, 2)
    x0, y0 = int(cells[:, 0].min()), int(cells[:, 1].min())
    shape = (int(cells[:, 0].max()) - x0 + 1, int(cells[:, 1].max()) - y0 + 1)
    grid, out = np.zeros(shape, dtype=bool), np.zeros(shape, dtype=np.uint8)
    grid[cells[:, 0] - x0, cells[:, 1] - y0] = True
    out[cells[:, 0] - x0, cells[:, 1] - y0] = np.fromiter(items.values(), dtype=np.uint8, count=len(items))
    return pack_values(x0, y0, grid, out)


def mask_union(*masks: CellMask) -> CellMask:
    present = [mask for mask in masks if mask.width]
    if len(present) <= 1:
        return present[0] if present else EMPTY_CELLS
    box = union_box(*(mask_box(mask) for mask in present))
    assert box is not None
    out = np.zeros((box[2] - box[0] + 1, box[3] - box[1] + 1), dtype=bool)
    for mask in present:
        out |= mask_array(mask, box)
    return pack_mask(box[0], box[1], out)


def mask_difference(first: CellMask, second: CellMask) -> CellMask:
    box = mask_box(first)
    if box is None or second.width == 0:
        return first
    return pack_mask(box[0], box[1], mask_array(first, box) & ~mask_array(second, box))


def mask_intersection(first: CellMask, second: CellMask) -> CellMask:
    box = mask_box(first)
    if box is None or second.width == 0:
        return EMPTY_CELLS
    return pack_mask(box[0], box[1], mask_array(first, box) & mask_array(second, box))


def update_cells(visible: CellMask, light: CellValues, hazard: CellValues, removed: CellMask, added: CellMask,
                 light_changed: CellValues, hazard_changed: CellValues) -> tuple[CellMask, CellValues, CellValues]:
    """An observer's cells after a delta, over one box: visible minus removed plus added, and the light
    and hazard values overwritten by the changed ones, kept at the visible cells."""
    if (not (removed.width or added.width or light_changed.cells.width or hazard_changed.cells.width)
            and light.cells == visible and hazard.cells == visible):
        return visible, light, hazard
    box = union_box(mask_box(visible), mask_box(added))
    if box is None:
        return EMPTY_CELLS, EMPTY_VALUES, EMPTY_VALUES
    if not (removed.width or added.width):
        # The same cells: only the values that changed move.
        grid = _grid(visible)
        result = []
        for previous, changed in ((light, light_changed), (hazard, hazard_changed)):
            if not changed.cells.width and previous.cells == visible:
                result.append(previous)
                continue
            _, (values,) = cell_layers(visible, (previous,), box)
            if changed.cells.width:
                present, fresh = values_array(changed, box)
                values[present] = fresh[present]
            result.append(CellValues(visible, values[grid].tobytes()))
        return visible, result[0], result[1]
    after, layers = cell_layers(visible, (light, hazard), box)
    if removed.width:
        after = after & ~mask_array(removed, box)
    if added.width:
        after = after | mask_array(added, box)
    for out, changed in zip(layers, (light_changed, hazard_changed)):
        if changed.cells.width:
            present, fresh = values_array(changed, box)
            out[present] = fresh[present]
    if not removed.width:
        # Nothing left the set, so the union of two tight boxes is tight.
        cells = CellMask(box[0], box[1], after.shape[0], after.shape[1],
                         np.packbits(after.ravel(), bitorder="little").tobytes())
        return cells, CellValues(cells, layers[0][after].tobytes()), CellValues(cells, layers[1][after].tobytes())
    cells, (light_after, hazard_after) = pack_layers(box[0], box[1], after, *layers)
    return cells, light_after, hazard_after


@dataclass(frozen=True, slots=True, eq=False)
class CellRows:
    """A row table of map cells: row i is cell (xs[i], ys[i]) holding values[i] (zero in a table of plain cells).

    The arrays are read-only.
    """

    xs: np.ndarray
    ys: np.ndarray
    values: np.ndarray


def _rows(xs: np.ndarray, ys: np.ndarray, values: np.ndarray) -> CellRows:
    for array in (xs, ys, values):
        array.flags.writeable = False
    return CellRows(xs, ys, values)


def mask_rows(mask: CellMask) -> CellRows:
    """A set's cells as a row table, in cell order."""
    if mask.width == 0:
        return _rows(np.zeros(0, dtype=np.int64), np.zeros(0, dtype=np.int64), np.zeros(0, dtype=np.uint8))
    xs, ys = np.nonzero(_grid(mask))
    return _rows(xs + mask.x0, ys + mask.y0, np.zeros(xs.size, dtype=np.uint8))


def layer_rows(layers: Sequence[CellValues]) -> CellRows:
    """The (cell, value) rows of value layers: by cell in cell order, then by layer."""
    parts = []
    for rank, layer in enumerate(layers):
        xs, ys = np.nonzero(_grid(layer.cells))
        parts.append((xs + layer.cells.x0, ys + layer.cells.y0, np.frombuffer(layer.values, dtype=np.uint8),
                      np.full(xs.size, rank)))
    if not parts:
        return mask_rows(EMPTY_CELLS)
    xs, ys, values, ranks = (np.concatenate(column) for column in zip(*parts))
    order = np.lexsort((ranks, ys, xs))
    return _rows(xs[order], ys[order], values[order])


def row_bits(rows: np.ndarray) -> RowBits:
    """The subset of a row table named by ascending row indices."""
    if not rows.size:
        return NO_ROWS
    first, last = int(rows[0]) >> 3, int(rows[-1]) >> 3
    flags = np.zeros((last - first + 1) * 8, dtype=bool)
    flags[rows - first * 8] = True
    return RowBits(first, np.packbits(flags, bitorder="little").tobytes())


def flag_bits(flags: Sequence[bool]) -> RowBits:
    """The subset of a row table of the rows whose flag is set."""
    return row_bits(np.flatnonzero(np.asarray(flags, dtype=bool)))


def bit_rows(bits: RowBits, count: int) -> np.ndarray:
    """The ascending row indices of a subset of a `count`-row table."""
    if not bits.bits:
        return np.zeros(0, dtype=np.int64)
    rows = np.flatnonzero(np.unpackbits(np.frombuffer(bits.bits, dtype=np.uint8), bitorder="little")) + 8 * bits.start
    if rows[-1] >= count:
        raise ValueError("A row subset names a row outside its table")
    return rows


def _points(xs: np.ndarray, ys: np.ndarray) -> CellMask:
    """The set of cells (xs[i], ys[i]); a cell named twice is a ValueError."""
    x0, y0 = int(xs.min()), int(ys.min())
    grid = np.zeros((int(xs.max()) - x0 + 1, int(ys.max()) - y0 + 1), dtype=bool)
    grid[xs - x0, ys - y0] = True
    if np.count_nonzero(grid) != xs.size:
        raise ValueError("A row subset names one cell twice")
    # The box spans the cells' extremes, so it is their bounding box.
    return CellMask(x0, y0, grid.shape[0], grid.shape[1], np.packbits(grid.ravel(), bitorder="little").tobytes())


def selected_mask(rows: CellRows, bits: RowBits) -> CellMask:
    """The set of the cells of a row subset."""
    index = bit_rows(bits, rows.xs.size)
    if not index.size:
        return EMPTY_CELLS
    return _points(rows.xs[index], rows.ys[index])


def selected_values(rows: CellRows, bits: RowBits) -> CellValues:
    """The cells of a row subset with the values of their rows (rows are in cell order: so are the values)."""
    index = bit_rows(bits, rows.xs.size)
    if not index.size:
        return EMPTY_VALUES
    return CellValues(_points(rows.xs[index], rows.ys[index]), rows.values[index].tobytes())


def zeros_left_out(values: CellValues, cells: CellMask) -> CellValues:
    """The values without a zero at a cell of `cells`.

    For an observer's delta whose `cells` it adds to its view (cells it did not
    see before: the native difference), its fold reads zero at an added cell
    without a value (`update_cells` keeps values only at visible cells), so a
    zero there is left out of the values it is sent.
    """
    own = mask_box(values.cells)
    if own is None or cells.width == 0:
        return values
    present, levels = values_array(values, own)
    dropped = present & (levels == 0) & mask_array(cells, own)
    if not dropped.any():
        return values
    return pack_values(own[0], own[1], present & ~dropped, levels)


def shared_cells(masks: Sequence[CellMask]) -> tuple[CellMask, list[RowBits]]:
    """One row table of every cell the sets name (their union, in cell order) and each set as a subset of it.

    Equal sets are one subset (many observers send the same cells).
    """
    distinct = [mask for mask in dict.fromkeys(masks) if mask.width]
    box = union_box(*(mask_box(mask) for mask in distinct))
    if box is None:
        return EMPTY_CELLS, [NO_ROWS for _ in masks]
    grids = [mask_array(mask, box) for mask in distinct]
    union = np.logical_or.reduce(grids)
    rank = (np.cumsum(union.ravel()) - 1).reshape(union.shape)
    bits = {mask: row_bits(rank[grid]) for mask, grid in zip(distinct, grids)}
    return pack_mask(box[0], box[1], union), [bits.get(mask, NO_ROWS) for mask in masks]


def shared_values(values: Sequence[CellValues]) -> tuple[tuple[CellValues, ...], list[RowBits]]:
    """The distinct (cell, value) pairs of value sets as layers, and each set as a subset of their rows.

    Layer k holds, for each cell with more than k distinct values among the
    sets, its (k+1)-th smallest. Rows are by cell in cell order, then by value
    (`layer_rows`). Equal sets are one subset.
    """
    distinct = [row for row in dict.fromkeys(values) if row.cells.width]
    box = union_box(*(mask_box(row.cells) for row in distinct))
    if box is None:
        return (), [NO_ROWS for _ in values]
    held = [values_array(row, box) for row in distinct]
    domain = np.unique(np.concatenate([levels[cells] for cells, levels in held]))
    shape = held[0][0].shape
    present = np.zeros((domain.size, *shape), dtype=bool)
    for cells, levels in held:
        xs, ys = np.nonzero(cells)
        present[np.searchsorted(domain, levels[xs, ys]), xs, ys] = True
    counts = present.sum(axis=0)
    below = np.cumsum(present, axis=0) - present
    offsets = (np.cumsum(counts.ravel()) - counts.ravel()).reshape(shape)
    layers = []
    for layer in range(int(counts.max())):
        levels = np.zeros(shape, dtype=np.uint8)
        for index, value in enumerate(domain):
            levels[present[index] & (below[index] == layer)] = value
        layers.append(pack_values(box[0], box[1], counts > layer, levels))
    bits = {}
    for row, (cells, levels) in zip(distinct, held):
        xs, ys = np.nonzero(cells)
        bits[row] = row_bits(offsets[xs, ys] + below[np.searchsorted(domain, levels[xs, ys]), xs, ys])
    return tuple(layers), [bits.get(row, NO_ROWS) for row in values]


__all__ = ["CellRows", "mask_rows", "layer_rows", "row_bits", "flag_bits", "bit_rows", "selected_mask", "selected_values",
           "zeros_left_out", "shared_cells", "shared_values", "Box", "mask_box", "union_box", "mask_array", "cell_layers", "pack_mask", "pack_layers", "pack_values", "values_array",
           "mask_positions", "mask_count", "mask_from_positions", "values_items", "values_from_items",
           "mask_union", "mask_difference", "mask_intersection", "update_cells"]
