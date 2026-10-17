"""Objective world grids for the perception-arrays spike (plan §6b "World grids").

Built once per operation from GridMap reads; in PV1 GridMap owns and writes them.
- exists / light: dense per-cell grids (light: the resolved LightLevel);
- obscurement: per-owner footprint masks, the combined bits derived from them;
- hazard owners: each owner with its footprint; the rule stays the owner's
  `is_hazardous_for`, called per observer (no hazard grid).
There is no occupant grid: contacts query GridMap's occupants in the window.
Observer-independent facts of a target (listed, stealth DC, invisible, boundary
placement) and a side's open channels are memoized lazily for the operation,
the first time some observer's visible cells reach them.
Grids are padded by FRAME_RADIUS so any observer frame is a plain slice.
"""

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple
from uuid import UUID

import numpy as np

from dnd.core.base_block import BaseBlock
from dnd.core.base_tiles import Tile
from dnd.core.gridmap import GridMap, SpatialConditionOwner
from dnd.types.senses import OBSCUREMENT_BITS
from dnd.types.world import CardinalDirection, WorldEdgeChannel

from devtools.perception_arrays_spike.frame_routes import FRAME_RADIUS

PAD = FRAME_RADIUS


@dataclass(frozen=True)
class Footprint:
    """One owner's cells, with a per-cell value (obscurement bits) when the owner has one."""

    owner_uuid: UUID
    x: np.ndarray
    y: np.ndarray
    bits: np.ndarray
    bounds: Tuple[int, int, int, int]


@dataclass(frozen=True)
class HazardOwner:
    """An owner whose hazard predicate is per (owner, observer), with its footprint."""

    owner: SpatialConditionOwner | BaseBlock | Tile
    footprint: Footprint


@dataclass(frozen=True)
class TargetFacts:
    """What every observer reads the same about one contact target during one operation."""

    block: BaseBlock
    listed: bool                                  # appears_in_entity_contacts / should_include_in_senses_objects
    stealth_dc: Optional[int]
    invisible: bool
    boundary_position: Optional[Tuple[int, int]]  # placement position of a boundary placement


@dataclass(frozen=True)
class WorldArrays:
    min_x: int
    min_y: int
    exists: np.ndarray            # bool, padded (W + 2P, H + 2P)
    light: np.ndarray             # uint8 resolved LightLevel
    obscurement_owners: Tuple[Footprint, ...]
    obscurement: np.ndarray       # uint8, OR of the owners' OBSCUREMENT_BITS (derived)
    hazard_owners: Tuple[HazardOwner, ...]
    optical_revision: int
    propagation_revision: int
    timings_ms: Dict[str, float]
    targets: Dict[Tuple[UUID, bool], Optional[TargetFacts]]     # (uuid, as entity?) -> facts, filled lazily
    side_channels: Dict[Tuple[Tuple[int, int], CardinalDirection], Tuple[WorldEdgeChannel, ...]]


def _footprint(owner_uuid: UUID, cells: List[Tuple[int, int]], bits: List[int]) -> Footprint:
    x = np.array([cell[0] for cell in cells], dtype=np.int64)
    y = np.array([cell[1] for cell in cells], dtype=np.int64)
    return Footprint(owner_uuid, x, y, np.array(bits, dtype=np.uint8),
                     (int(x.min()), int(y.min()), int(x.max()), int(y.max())))


def build_world_arrays(grid: GridMap, clock: Callable[[], float]) -> WorldArrays:
    """Objective grids for one operation; `clock` returns seconds."""
    timings: Dict[str, float] = {}
    started = clock()
    min_x, min_y, max_x, max_y = grid.bounds
    shape = (max_x - min_x + 1 + 2 * PAD, max_y - min_y + 1 + 2 * PAD)
    tiles = grid.get_all_tiles()
    gx = np.fromiter((p[0] for p in tiles), dtype=np.int64, count=len(tiles)) - min_x + PAD
    gy = np.fromiter((p[1] for p in tiles), dtype=np.int64, count=len(tiles)) - min_y + PAD
    exists = np.zeros(shape, dtype=bool)
    exists[gx, gy] = True
    light = np.zeros(shape, dtype=np.uint8)
    light[gx, gy] = np.fromiter((tile.resolved_light_level.value for tile in tiles.values()), dtype=np.uint8,
                                count=len(tiles))
    timings['exists_light_ms'] = (clock() - started) * 1000

    started = clock()
    center = ((min_x + max_x) // 2, (min_y + max_y) // 2)
    by_owner: Dict[UUID, Tuple[List[Tuple[int, int]], List[int]]] = {}
    for position, owners in grid.capture_optical_obscurements(center, max(max_x - min_x, max_y - min_y) + 1).items():
        for owner_uuid, values in owners.items():
            cells, bits = by_owner.setdefault(owner_uuid, ([], []))
            cells.append(position)
            bits.append(sum(OBSCUREMENT_BITS[value] for value in values))
    obscurement_owners = tuple(_footprint(owner_uuid, cells, bits) for owner_uuid, (cells, bits) in by_owner.items())
    timings['obscurement_footprints_ms'] = (clock() - started) * 1000
    started = clock()
    obscurement = np.zeros(shape, dtype=np.uint8)
    for footprint in obscurement_owners:
        obscurement[footprint.x - min_x + PAD, footprint.y - min_y + PAD] |= footprint.bits
    timings['obscurement_combined_ms'] = (clock() - started) * 1000

    started = clock()
    hazard_owners: List[HazardOwner] = []
    capable = grid.hazard_capable_cells(tiles.keys())
    object_cells: Dict[UUID, List[Tuple[int, int]]] = {}
    for position in capable:
        tile = tiles[position]
        if tile.active_conditions or tile.residue_states():
            hazard_owners.append(HazardOwner(tile, _footprint(tile.uuid, [position], [0])))
        for identity in grid.get_objects_at(position):
            object_cells.setdefault(identity, []).append(position)
    for identity, cells in object_cells.items():
        block = BaseBlock.get(identity)
        if block is not None and block.active_conditions:
            hazard_owners.append(HazardOwner(block, _footprint(identity, cells, [0] * len(cells))))
    for condition in grid.get_spatial_conditions():
        cells = list(grid.get_spatial_condition_positions(condition.uuid))
        if cells:
            hazard_owners.append(HazardOwner(condition, _footprint(condition.uuid, cells, [0] * len(cells))))
    timings['hazard_owners_ms'] = (clock() - started) * 1000
    return WorldArrays(min_x, min_y, exists, light, obscurement_owners, obscurement, tuple(hazard_owners),
                       grid.optical_revision, grid.propagation_revision, timings, {}, {})
