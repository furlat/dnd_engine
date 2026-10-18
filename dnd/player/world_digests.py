"""The session's tile digests: each tile's digest computed once for its current value and shared by every seat.

A publication fills the cache as it reads a tile (`cached_tile_digest`); the session fold's one writer
(`_fold_version`) forgets every cell a version wrote (`forget_written`, from `AppliedWorldFact`).
"""

from collections.abc import Mapping
from dataclasses import dataclass, field

from dnd.core.cells import Position
from dnd.player.world_stamps import tile_digest
from dnd.types.event_facts import AppliedWorldFact, WorldTileState, written_cells


@dataclass(slots=True)
class TileDigests:
    tiles: dict[Position, int] = field(default_factory=dict)


def forget_written(digests: TileDigests, applied: AppliedWorldFact) -> None:
    for position in written_cells(applied):
        digests.tiles.pop(position, None)


def cached_tile_digest(digests: TileDigests, tiles: Mapping[Position, WorldTileState], position: Position) -> int:
    """The digest of the tile at a cell as of now, computed and cached on a miss."""
    if position not in digests.tiles:
        digests.tiles[position] = tile_digest(tiles[position])
    return digests.tiles[position]
