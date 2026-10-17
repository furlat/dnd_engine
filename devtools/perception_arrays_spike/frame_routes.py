"""The observer frame and its supercover route table, sized to the engine's perception reach.

Gallery observers perceive up to 80 cells (`update_all_entities_senses(max_distance=80)`),
beyond the engine's 40-cell vectorized table, so the spike tables every route in a
radius-80 frame with the engine's own stepping rule (`supercover_route_table`).
A frame cell's flat index is also the table row of the route to it.
"""

from functools import lru_cache
from typing import Tuple

import numpy as np

FRAME_RADIUS = 80
SIDE = 2 * FRAME_RADIUS + 1
CELLS = SIDE * SIDE
OFF = CELLS                  # padded "outside" index: always zero / False
CENTER = FRAME_RADIUS * SIDE + FRAME_RADIUS


@lru_cache(maxsize=1)
def frame_route_table() -> Tuple[np.ndarray, np.ndarray]:
    """`supercover_route_table` for FRAME_RADIUS: rows of flat cells padded with OFF, and lengths."""
    radius = FRAME_RADIUS
    dx, dy = (axis.ravel() for axis in np.meshgrid(
        np.arange(-radius, radius + 1), np.arange(-radius, radius + 1), indexing="ij"))
    nx, ny, sx, sy = np.abs(dx), np.abs(dy), np.sign(dx), np.sign(dy)
    x, y, ix, iy = (np.zeros_like(dx) for _ in range(4))
    cells = np.full((dx.size, 2 * radius + 1), OFF, dtype=np.int32)
    cells[:, 0] = CENTER
    lengths = np.ones(dx.size, dtype=np.int32)
    for step in range(1, 2 * radius + 1):
        active = (ix < nx) | (iy < ny)
        x_mid = (1 + 2 * ix) * ny
        y_mid = (1 + 2 * iy) * nx
        move_x = active & (ix < nx) & ((iy >= ny) | (x_mid < y_mid))
        move_y = active & ~move_x & (iy < ny) & ((ix >= nx) | (y_mid < x_mid))
        step_x = move_x | (active & ~move_x & ~move_y)
        step_y = move_y | (active & ~move_x & ~move_y)
        x += sx * step_x
        y += sy * step_y
        ix += step_x
        iy += step_y
        cells[active, step] = ((x + radius) * SIDE + (y + radius))[active]
        lengths += active
    return cells, lengths


@lru_cache(maxsize=1)
def frame_distance_feet() -> np.ndarray:
    """grid_distance_feet from the frame center to every frame cell (OFF -> 0)."""
    dx, dy = np.meshgrid(np.arange(-FRAME_RADIUS, FRAME_RADIUS + 1), np.arange(-FRAME_RADIUS, FRAME_RADIUS + 1),
                         indexing="ij")
    squared = (dx * dx + dy * dy).ravel().astype(np.float64)
    # Same IEEE sqrt + truncation as grid_distances_feet.
    return np.append(np.sqrt(squared).astype(np.int64) * 5, 0)
