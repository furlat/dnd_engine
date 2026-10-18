"""Digest stamps: a record entering a seat's perception travels whole only when its value is not the one the seat has.

A seat's stamp of a record is a digest of the value the seat holds: the record as last sent whole, or confirmed
unchanged. A keyed change keeps the stamp only while the record's value is still the stamped one (a write that left
it equal), and drops it otherwise: the seat holds the stamped value with the change applied, which a write folded
but published to the seat later would make another value than the session's. A record re-entering perception
whose current digest equals the stamp is confirmed unchanged instead of sent whole. The digest is of the value, never of its history: a record written and written back while the seat did
not perceive it re-enters unchanged, so how a record travels tells nothing of writes the seat did not see. The rule
is `unchanged_since`; E3-bodies applies it to its body records with its own digests.

A digest is stable across processes (`stable_digest`: SHA-256 of the record's JSON, never Python's `hash`). A tile's
digest is of the tile (the session caches it per value: `world_digests.TileDigests`); an object's is of the row the seat is sent
(its disclosed state and placement), with the faces and members of that row.

The seat's stamps are knowledge, written from an emitted group only: a walk derives its own changes from each update
it builds (`stamp_world_update`) and they join the seat's at emission (`merge_world_stamps`), as the static rows do.
`stamp_replay` restores them from the updates a seat received, through the same derivation.
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from hashlib import sha256
from typing import TypeVar
from uuid import UUID

from pydantic import TypeAdapter

from dnd.core.cells import Position, mask_positions, values_items
from dnd.player.facts import ObjectRow, ObjectState, WorldUpdate
from dnd.types.event_facts import WorldTileState
from dnd.types.world import CardinalDirection
from dnd.types.world_placement import WorldObjectPlacement, placement_support_cells

_STATE = TypeAdapter(ObjectState)
Key = TypeVar("Key")
Value = TypeVar("Value")


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


def unchanged_since(stamps: Mapping[Key, int | None], key: Key, digest: int) -> bool:
    """The rule, for any record: the record `key`, whose current row digests to `digest`, is still as the seat
    holds it when the seat's stamp of it (`stamps`) is that digest."""
    return stamps.get(key) == digest


@dataclass(frozen=True, slots=True)
class ObjectView:
    """What a seat's stamp of an object adds to its digest: the faces and members of its last row, the placement
    the seat holds and the cells it touches (where the client drops it when they enter view without it)."""

    faces: frozenset[CardinalDirection]
    members: int | None
    placement: WorldObjectPlacement
    cells: frozenset[Position]


@dataclass(slots=True)
class WorldStamps:
    """A seat's stamps: the digest of each tile (by cell) and object (by uuid) as it holds them, and each object's
    view."""

    tiles: dict[Position, int] = field(default_factory=dict)
    objects: dict[UUID, int] = field(default_factory=dict)
    views: dict[UUID, ObjectView] = field(default_factory=dict)


@dataclass(slots=True)
class StampChanges:
    """A walk's changes to its seat's stamps, joining them at emission; `None` drops a stamp (an object's digest and
    view go together)."""

    tiles: dict[Position, int | None] = field(default_factory=dict)
    objects: dict[UUID, int | None] = field(default_factory=dict)
    views: dict[UUID, ObjectView | None] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SeatStamps:
    """What a walk decides from: its changes first, then the seat's stamps (as `sent` and `pending` are for the
    static rows; frozen only against rebinding, `walk` is written)."""

    held: WorldStamps
    walk: StampChanges = field(default_factory=StampChanges)


def tile_stamps(stamps: SeatStamps, position: Position) -> Mapping[Position, int | None]:
    """The stamps holding the seat's current stamp of a tile: the walk's changes when they name it."""
    return stamps.walk.tiles if position in stamps.walk.tiles else stamps.held.tiles


def object_stamps(stamps: SeatStamps, identity: UUID) -> Mapping[UUID, int | None]:
    """The stamps holding the seat's current stamp of an object: the walk's changes when they name it."""
    return stamps.walk.objects if identity in stamps.walk.objects else stamps.held.objects


def object_view(stamps: SeatStamps, identity: UUID) -> ObjectView | None:
    return stamps.walk.views[identity] if identity in stamps.walk.views else stamps.held.views.get(identity)


def stamp_world_update(stamps: SeatStamps, update: WorldUpdate, rows: Sequence[ObjectRow],
                       tile_digest_of: Callable[[Position], int],
                       placements: Mapping[UUID, WorldObjectPlacement]) -> None:
    """The walk's stamps after one update, whose object rows are `rows`. `tile_digest_of` gives the digest of a tile
    the update carries whole, and `placements` the placement of each row that carries one, as the seat holds them
    after it: live, the session's values as of the occurrence; restored, the client's.

    An entered cell's whole or unchanged tile takes its digest, and an entered cell without a tile loses its stamp.
    A perceived tile's keyed change keeps the tile's stamp only if it is still the tile's digest. A stampable row
    (which carries the object's whole state) takes its digest and view with its placement, or the placement the
    seat's stamp holds; a row with neither, or not stampable, loses it. A removed object, and a stamped object whose
    cells meet the entered cells unless the update sends or confirms it (the client drops it there), lose theirs.
    An unchanged object keeps its stamp."""
    entered = set(mask_positions(update.entered))
    whole = set(mask_positions(update.tile_columns.cells)) if update.tile_columns is not None else set()
    carried = whole | set(mask_positions(update.tiles_unchanged))
    for position in entered:
        stamps.walk.tiles[position] = tile_digest_of(position) if position in carried else None
    keyed = ({row.position for row in update.tile_changes}
             | {position for position, _ in values_items(update.resolved_light)}
             | {row.position for row in update.tile_conditions} | {row.position for row in update.residues}
             | {row.position for row in update.residues_removed}) - entered
    for position in keyed:
        digest = tile_digest_of(position)
        stamps.walk.tiles[position] = digest if tile_stamps(stamps, position).get(position) == digest else None
    dropped = set(update.objects_removed)
    if entered:
        sent = {row.item_uuid for row in rows} | set(update.objects_unchanged)
        dropped.update(identity for identity in {*stamps.held.views, *stamps.walk.views} - sent
                       if (view := object_view(stamps, identity)) is not None and view.cells & entered)
    for identity in dropped:
        stamps.walk.objects[identity] = stamps.walk.views[identity] = None
    for row in rows:
        held = object_view(stamps, row.item_uuid)
        placement = placements[row.item_uuid] if row.item_uuid in placements else held.placement if held else None
        if stampable(row.state) and placement is not None:
            stamps.walk.objects[row.item_uuid] = object_digest(row.state, placement)
            stamps.walk.views[row.item_uuid] = ObjectView(frozenset(row.observed_faces), row.members, placement,
                                                          placement_support_cells(placement))
        else:
            stamps.walk.objects[row.item_uuid] = stamps.walk.views[row.item_uuid] = None


def _apply(stamps: dict[Key, Value], changes: Mapping[Key, Value | None]) -> None:
    for key, value in changes.items():
        if value is None:
            stamps.pop(key, None)
        else:
            stamps[key] = value


def merge_world_stamps(stamps: WorldStamps, changes: StampChanges) -> None:
    """An emitted group's stamp changes join the seat's stamps."""
    _apply(stamps.tiles, changes.tiles)
    _apply(stamps.objects, changes.objects)
    _apply(stamps.views, changes.views)
