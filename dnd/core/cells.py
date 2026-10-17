"""Array operations on packed cell sets (`dnd.types.cells`).

A box is (x0, y0, x1, y1), inclusive. Arrays are indexed [x - x0, y - y0], the
cell order of a mask.
"""

from collections.abc import Iterable, Mapping

import numpy as np

from dnd.types.cells import EMPTY_CELLS, EMPTY_VALUES, CellMask, CellValues

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
                         bitorder="little").reshape(mask.width, mask.height).astype(bool)


def mask_array(mask: CellMask, box: Box) -> np.ndarray:
    """The set over another box: a bool array, False where the set does not reach."""
    out = np.zeros((box[2] - box[0] + 1, box[3] - box[1] + 1), dtype=bool)
    own = mask_box(mask)
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


def pack_values(x0: int, y0: int, cells: np.ndarray, values: np.ndarray) -> CellValues:
    """The values at the True cells of `cells`, both arrays anchored at (x0, y0)."""
    mask = pack_mask(x0, y0, cells)
    if mask.width == 0:
        return EMPTY_VALUES
    box = mask_box(mask)
    assert box is not None
    part = cells[box[0] - x0:box[2] - x0 + 1, box[1] - y0:box[3] - y0 + 1]
    return CellValues(mask, values[box[0] - x0:box[2] - x0 + 1, box[1] - y0:box[3] - y0 + 1][part]
                      .astype(np.uint8).tobytes())


def values_array(values: CellValues, box: Box) -> tuple[np.ndarray, np.ndarray]:
    """The cells (bool) and their values (uint8) over another box, zero where they do not reach."""
    cells = np.zeros((box[2] - box[0] + 1, box[3] - box[1] + 1), dtype=bool)
    out = np.zeros(cells.shape, dtype=np.uint8)
    own = mask_box(values.cells)
    if own is None:
        return cells, out
    grid = _grid(values.cells)
    full = np.zeros(grid.shape, dtype=np.uint8)
    full[grid] = np.frombuffer(values.values, dtype=np.uint8)
    ax0, ay0, ax1, ay1 = max(box[0], own[0]), max(box[1], own[1]), min(box[2], own[2]), min(box[3], own[3])
    if ax0 <= ax1 and ay0 <= ay1:
        target = (slice(ax0 - box[0], ax1 - box[0] + 1), slice(ay0 - box[1], ay1 - box[1] + 1))
        source = (slice(ax0 - own[0], ax1 - own[0] + 1), slice(ay0 - own[1], ay1 - own[1] + 1))
        cells[target] = grid[source]
        out[target] = full[source]
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
    box = union_box(*(mask_box(mask) for mask in masks))
    if box is None:
        return EMPTY_CELLS
    out = np.zeros((box[2] - box[0] + 1, box[3] - box[1] + 1), dtype=bool)
    for mask in masks:
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


def update_values(previous: CellValues, cells: CellMask, changed: CellValues) -> CellValues:
    """`previous` overwritten by `changed`, at the cells of `cells` (the after-set)."""
    box = mask_box(cells)
    if box is None:
        return EMPTY_VALUES
    _, out = values_array(previous, box)
    present, fresh = values_array(changed, box)
    out[present] = fresh[present]
    return pack_values(box[0], box[1], mask_array(cells, box), out)


__all__ = ["Box", "mask_box", "union_box", "mask_array", "pack_mask", "pack_values", "values_array",
           "mask_positions", "mask_count", "mask_from_positions", "values_items", "values_from_items",
           "mask_union", "mask_difference", "mask_intersection", "update_values"]
