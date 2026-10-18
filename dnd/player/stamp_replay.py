"""A seat's revision stamps rebuilt from its own records: the restore of `revision_stamps`' seat knowledge.

The live stamps follow the updates the seat was emitted (`stamp_world_update` in each walk); these follow the same
updates as the seat received them, folded into a client world by the reference fold. An object the client drops
(held before an update, not after) loses its stamp, where the live walk drops the objects it leaves unsent on the
entered cells: the two differ only on an object written since its stamp (moved away unseen), which travels whole
either way. Records number occurrences in the seat's public numbering; `native_of` maps each to its native index
(the seat's `public_cursors`, inverted), which no record carries. Without stamps (no replay) the seat's next
re-entry sends every record whole, which is always correct.
"""

from collections.abc import Iterable, Mapping

from dnd.player.facts import PlayerState, WorldUpdate
from dnd.player.revision_stamps import RevisionStamps, SeatStamps, merge_revision_stamps, stamp_world_update
from dnd.player.world_reduction import fold_world_update


def replay_revision_stamps(memory: PlayerState, updates: Iterable[WorldUpdate], native_of: Mapping[int, int]
                           ) -> RevisionStamps:
    """The stamps of a seat whose client world is `memory` (empty at the start) after these world updates, in the
    order the seat received them. Every stamped record is one the client holds."""
    stamps = SeatStamps(RevisionStamps())
    for update in updates:
        held = set(memory.objects)
        fold_world_update(memory, update)
        stamp_world_update(stamps, update, native_of[update.occurrence], held - memory.objects.keys())
        if not ({identity for identity, stamp in stamps.walk.objects.items() if stamp is not None}
                <= memory.objects.keys()
                and {cell for cell, stamp in stamps.walk.tiles.items() if stamp is not None} <= memory.tiles.keys()):
            raise ValueError("A stamped record is one the client holds")
    restored = RevisionStamps()
    merge_revision_stamps(restored, stamps.walk)
    return restored
