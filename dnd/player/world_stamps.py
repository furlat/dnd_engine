"""Digest stamps: a record entering a seat's perception travels whole only when its value is not the one the seat has.

A seat's stamp of a record is a digest of the value the seat holds: the record as last sent (whole, or as a keyed
change of a record the seat perceives, which leaves the seat with the record's value as of then), or confirmed
unchanged. A record re-entering perception whose current digest equals the stamp is confirmed unchanged instead of
sent whole. The digest is of the value, never of its history: a record written and written back while the seat did
not perceive it re-enters unchanged, so how a record travels tells nothing of writes the seat did not see. The rule
is `unchanged_since`; E3-bodies applies it to its body records with its own digests.

A digest is stable across processes (`stable_digest`: SHA-256 of the record's JSON, never Python's `hash`). A tile's
digest is the session's (`WorldDigests`, computed once per written value: every seat reads the same tile); an
object's is of the row the seat is sent (its disclosed state and placement), with the faces and members of that row.

The seat's stamps are knowledge, written from an emitted group only: a walk derives its own changes from each update
it builds (`stamp_world_update`) and they join the seat's at emission (`merge_world_stamps`), as the static rows do.
`stamp_replay` restores them from the updates a seat received, through the same derivation.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from hashlib import sha256
from uuid import UUID

from pydantic import TypeAdapter

from dnd.core.cells import mask_positions, values_items
from dnd.player.facts import ObjectRow, ObjectState, WorldUpdate
from dnd.types.event_facts import AppliedWorldFact, WorldTileState
from dnd.types.world import CardinalDirection
from dnd.types.world_placement import WorldObjectPlacement, placement_support_cells
from dnd.world_facts import WorldFacts

Position = tuple[int, int]
_STATE = TypeAdapter(ObjectState)


def stable_digest(data: bytes) -> int:
    """A value's digest, the same in every process."""
    return int.from_bytes(sha256(data).digest()[:8], "big")


def tile_digest(tile: WorldTileState) -> int:
    """A tile as a seat holds it: its static part, scalars, light, condition names and residues."""
    return stable_digest(tile.model_dump_json().encode())


def object_digest(state: ObjectState, placement: WorldObjectPlacement) -> int:
    """An object as a seat holds it from its row: the disclosed state and the placement."""
    return stable_digest(_STATE.dump_json(state) + b"\n" + placement.model_dump_json().encode())


def stampable(state: ObjectState) -> bool:
    """Whether an object's row can be confirmed unchanged. Its suppressions are not (the client retires their cells
    where they enter view), nor its item effects or concentration slots (the seat's numbering and the lineages it was
    disclosed map them as the update is emitted): such an object travels whole."""
    return not state.construction_suppressions and not state.item_effects and not state.concentration_slots


@dataclass(slots=True)
class WorldDigests:
    """The session's tile digests, each computed once for the tile's current value; a write forgets it."""

    tiles: dict[Position, int] = field(default_factory=dict)


def forget_written(digests: WorldDigests, applied: AppliedWorldFact) -> None:
    """A folded version's written cells lose their digests (`AppliedWorldFact` names every cell it wrote)."""
    for cells in (applied.replaced, applied.light, applied.tile_conditions,
                  (change.position for change in applied.tiles), (position for position, _ in applied.tile_fields)):
        for position in cells:
            digests.tiles.pop(position, None)


def session_tile_digest(digests: WorldDigests, world: WorldFacts, position: Position) -> int:
    """The digest of the session's tile at a cell, as of now."""
    if position not in digests.tiles:
        digests.tiles[position] = tile_digest(world.tiles[position])
    return digests.tiles[position]


@dataclass(frozen=True, slots=True)
class ObjectStamp:
    """The digest of an object as the seat holds it, with the faces and members of its last row and the cells its
    placement touches (where the client drops it when they enter view without it)."""

    digest: int
    faces: frozenset[CardinalDirection]
    members: int | None
    cells: frozenset[Position]


@dataclass(slots=True)
class WorldStamps:
    """A seat's stamps: tiles by cell, objects by uuid."""

    tiles: dict[Position, int] = field(default_factory=dict)
    objects: dict[UUID, ObjectStamp] = field(default_factory=dict)


@dataclass(slots=True)
class StampChanges:
    """A walk's changes to its seat's stamps, joining them at emission; `None` drops a stamp."""

    tiles: dict[Position, int | None] = field(default_factory=dict)
    objects: dict[UUID, ObjectStamp | None] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SeatStamps:
    """What a walk decides from: its changes first, then the seat's stamps (as `sent` and `pending` are for the
    static rows)."""

    held: WorldStamps
    walk: StampChanges = field(default_factory=StampChanges)


def unchanged_since(stamp: int | None, digest: int) -> bool:
    """The rule: a record whose current digest is the seat's stamp is still as the seat has it."""
    return stamp == digest


def tile_stamp(stamps: SeatStamps, position: Position) -> int | None:
    return stamps.walk.tiles[position] if position in stamps.walk.tiles else stamps.held.tiles.get(position)


def object_stamp(stamps: SeatStamps, identity: UUID) -> ObjectStamp | None:
    return stamps.walk.objects[identity] if identity in stamps.walk.objects else stamps.held.objects.get(identity)


def stamp_world_update(stamps: SeatStamps, update: WorldUpdate, rows: Sequence[ObjectRow],
                       tile_digest_at: Callable[[Position], int],
                       placement_of: Callable[[UUID], WorldObjectPlacement]) -> None:
    """The walk's stamps after one update, whose object rows are `rows`; `tile_digest_at` and `placement_of` give a
    tile's digest and an object's placement as the seat holds them after it.

    Every tile the update sends or confirms takes its digest: an entered cell's whole or unchanged tile, and a
    perceived tile's keyed change (the seat's tile is the record's value as of then). An entered cell without a
    tile loses its stamp. Every stampable row takes its digest, faces, members and cells, any other row loses it;
    a removed object, and a stamped object whose cells meet the entered cells unless the update sends or confirms
    it (the client drops it there), lose theirs. An unchanged object keeps its stamp."""
    entered = set(mask_positions(update.entered))
    whole = set(mask_positions(update.tile_columns.cells)) if update.tile_columns is not None else set()
    held = whole | set(mask_positions(update.tiles_unchanged))
    for position in entered:
        stamps.walk.tiles[position] = tile_digest_at(position) if position in held else None
    keyed = ({row.position for row in update.tile_changes}
             | {position for position, _ in values_items(update.resolved_light)}
             | {row.position for row in update.tile_conditions} | {row.position for row in update.residues}
             | {row.position for row in update.residues_removed}) - entered
    for position in keyed:
        stamps.walk.tiles[position] = tile_digest_at(position)
    sent = {row.item_uuid for row in rows} | set(update.objects_unchanged)
    if entered:
        for identity in {*stamps.held.objects, *stamps.walk.objects} - sent:
            stamp = object_stamp(stamps, identity)
            if stamp is not None and stamp.cells & entered:
                stamps.walk.objects[identity] = None
    for identity in update.objects_removed:
        stamps.walk.objects[identity] = None
    for row in rows:
        placement = placement_of(row.item_uuid)
        stamps.walk.objects[row.item_uuid] = ObjectStamp(object_digest(row.state, placement),
            frozenset(row.observed_faces), row.members, placement_support_cells(placement)) \
            if stampable(row.state) else None


def merge_world_stamps(stamps: WorldStamps, changes: StampChanges) -> None:
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
