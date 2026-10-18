"""Revision stamps: a record entering a seat's perception travels whole only when it changed since the seat had it.

A world record's revision is the native index of its last write, which the session's one fold records from E2's
`AppliedWorldFact` (`record_world_revisions`). A seat's stamp of a record is the native index of the last update
that left the seat holding the record's value as of then: a whole send, or a keep. A keyed change does not
advance it, since a write the seat was never published may lie before it. The rule is `unchanged_since`; E3-bodies
applies it to its body records with their own revisions and stamps.

The seat's stamps are knowledge, written from an emitted group only: a walk derives its own stamps from each
update it builds (`stamp_world_update`, where `None` is a stamp the walk dropped) and they join the seat's at
emission (`merge_revision_stamps`), as the static rows do.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field
from uuid import UUID

from dnd.core.cells import mask_positions
from dnd.player.facts import WorldUpdate
from dnd.player.world_columns import placed_object_rows
from dnd.types.event_facts import AppliedWorldFact
from dnd.types.world import CardinalDirection


@dataclass(slots=True)
class WorldRevisions:
    """The native index of each world record's last write: a tile by its cell (its scalars, light, own condition
    names and residues), an object by its uuid (its state, placement and contents). `latest` is the last index
    folded: the session folds in native order, so a revision never goes back."""

    tiles: dict[tuple[int, int], int] = field(default_factory=dict)
    objects: dict[UUID, int] = field(default_factory=dict)
    latest: int = -1


def record_world_revisions(revisions: WorldRevisions, applied: AppliedWorldFact, index: int) -> None:
    """The records one folded version wrote take its native index (`_put_object` names every object it writes,
    moved ones, removed ones and containers included)."""
    if index < revisions.latest:
        raise ValueError("A session folds its versions in native order")
    revisions.latest = index
    for cells in (applied.replaced, applied.light, applied.tile_conditions,
                  (change.position for change in applied.tiles), (position for position, _ in applied.tile_fields)):
        revisions.tiles.update(dict.fromkeys(cells, index))
    revisions.objects.update(dict.fromkeys(applied.objects, index))


@dataclass(frozen=True, slots=True)
class ObjectStamp:
    """The native index at which the seat last had an object whole, with the faces and members of that row: a face
    seen now that the row did not show, or other observing members, need the object whole."""

    index: int
    faces: frozenset[CardinalDirection]
    members: int | None


@dataclass(slots=True)
class RevisionStamps:
    """A seat's stamps: the native index at which it last had each tile (by cell) and object (by uuid) whole."""

    tiles: dict[tuple[int, int], int] = field(default_factory=dict)
    objects: dict[UUID, ObjectStamp] = field(default_factory=dict)


@dataclass(slots=True)
class StampChanges:
    """A walk's changes to its seat's stamps, joining them at emission; `None` drops a stamp."""

    tiles: dict[tuple[int, int], int | None] = field(default_factory=dict)
    objects: dict[UUID, ObjectStamp | None] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SeatStamps:
    """What a walk decides from: its changes first, then the seat's stamps (as `sent` and `pending` are for the
    static rows)."""

    held: RevisionStamps
    walk: StampChanges = field(default_factory=StampChanges)


def unchanged_since(stamp: int | None, revision: int | None) -> bool:
    """The rule: a record the seat holds (`stamp`) and nothing wrote since (`revision`) is still as the seat has it."""
    return stamp is not None and revision is not None and revision <= stamp


def tile_stamp(stamps: SeatStamps, position: tuple[int, int]) -> int | None:
    return stamps.walk.tiles[position] if position in stamps.walk.tiles else stamps.held.tiles.get(position)


def object_stamp(stamps: SeatStamps, identity: UUID) -> ObjectStamp | None:
    return stamps.walk.objects[identity] if identity in stamps.walk.objects else stamps.held.objects.get(identity)


def stamp_world_update(stamps: SeatStamps, update: WorldUpdate, index: int, dropped: Iterable[UUID]) -> None:
    """The walk's stamps after one update (native index `index`): its whole tiles and unchanged cells, its placed
    object rows and unchanged objects take `index`; an entered cell without a tile, a removed object and `dropped`
    (stamped objects the client drops on the entered cells) lose their stamps. A keyed change leaves a stamp as it
    was: an unpublished write may precede it."""
    whole = set(mask_positions(update.tile_columns.cells)) if update.tile_columns is not None else set()
    unchanged = set(mask_positions(update.tiles_unchanged))
    for position in mask_positions(update.entered):
        stamps.walk.tiles[position] = index if position in whole or position in unchanged else None
    for identity in update.objects_unchanged:
        stamp = object_stamp(stamps, identity)
        if stamp is None:
            raise ValueError("An unchanged object has its stamp")
        stamps.walk.objects[identity] = ObjectStamp(index, stamp.faces, stamp.members)
    for identity in (*update.objects_removed, *dropped):
        stamps.walk.objects[identity] = None
    for identity, faces, members in placed_object_rows(update.objects):
        stamps.walk.objects[identity] = ObjectStamp(index, frozenset(faces), members)


def merge_revision_stamps(stamps: RevisionStamps, changes: StampChanges) -> None:
    """An emitted group's stamp changes join the seat's stamps."""
    for position, tile in changes.tiles.items():
        if tile is None:
            stamps.tiles.pop(position, None)
        else:
            stamps.tiles[position] = tile
    for identity, stamp in changes.objects.items():
        if stamp is None:
            stamps.objects.pop(identity, None)
        else:
            stamps.objects[identity] = stamp
