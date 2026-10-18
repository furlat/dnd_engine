"""A seat's digest stamps rebuilt from its own records: the restore of `world_stamps`' seat knowledge.

The live stamps follow the updates the seat was emitted (`stamp_world_update` in each walk), digesting the values the
session sent; these follow the same updates as the seat received them, folded into a client world by the reference
fold, digesting what the client holds after each. The two are equal: the client holds what it was sent. Without
stamps (no replay) the seat's next re-entry sends every record whole, which is always correct.
"""

from collections.abc import Iterable

from dnd.player.facts import PlayerState, WorldUpdate
from dnd.player.world_columns import unpack_object_rows
from dnd.player.world_reduction import fold_world_update
from dnd.player.world_stamps import SeatStamps, WorldStamps, merge_world_stamps, stamp_world_update, tile_digest


def replay_world_stamps(memory: PlayerState, updates: Iterable[WorldUpdate]) -> WorldStamps:
    """The stamps of a seat whose client world is `memory` (empty at the start) after these world updates, in the
    order the seat received them."""
    stamps = SeatStamps(WorldStamps())
    for update in updates:
        fold_world_update(memory, update)
        stamp_world_update(stamps, update, unpack_object_rows(update.objects),
                           lambda position: tile_digest(memory.tiles[position]),
                           lambda identity: memory.objects[identity].placement)
    restored = WorldStamps()
    merge_world_stamps(restored, stamps.walk)
    return restored
