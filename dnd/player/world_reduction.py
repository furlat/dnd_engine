"""The client's world fold of the schema-16 wire: what it holds of tiles, objects, contents and connectors.

The memory rules the client owns (plan §3.2, §3.4; GODOT_CLIENT_SCHEMA_16_HANDOUT_2026-10-19 §3):

- what the seat saw go is dropped first (`objects_removed`, `connectors_removed`);
- entering cells are authoritative: everything held there is dropped and replaced by what the update carries,
  but the tiles and objects it names unchanged (their value is the one the seat holds), which stay as held;
  nothing held is ever evicted otherwise, since an unchanged record off the entered cells is not sent at all;
- an object is forgotten when the seat sees its support without it (an entered cell, or `objects_removed`);
- a wall's residue faces not seen now keep their last sight (the face merge);
- a construction's suppressed cells are retired where they enter view, and a perceived provider's row replaces it;
- contents seen once are kept when the grant is lost and are whole again when regained;
- leaving perception changes nothing.

Every order comes from the wire or from sorted keys, never from set iteration, so replay rebuilds the same memory.
"""

from dataclasses import replace
from uuid import UUID

from dnd.core.cells import mask_positions, values_items
from dnd.player.facts import (ContainedItem, FloorItem, ObjectRow, PlayerObject, PlayerState, StaticStore,
    WorldUpdate)
from dnd.player.world_columns import join_floor_item, unpack_object_rows, unpack_placement, unpack_tile_columns
from dnd.types.event_facts import WorldTileState, tile_own_condition_names
from dnd.types.residues import ObjectResidueState, TileResidueState
from dnd.types.spell_suppression import SpellSuppression
from dnd.types.world import LightLevel
from dnd.types.world_placement import placement_support_cells


def _members(row: ObjectRow, observers: int) -> int:
    if row.members is not None:
        return row.members
    if observers != 1:
        raise ValueError("A seat with several observers names the members of each object row")
    return 1


def fold_static_rows(static: StaticStore, update: WorldUpdate) -> None:
    """The update's static rows into the client's store, which never prunes them; a static row never changes for
    its id (a tile's static row is the latest for its cell, an object's look the latest sent for its uuid)."""
    for row in update.tile_looks:
        if static.tile_looks.setdefault(row.look_id, row) != row:
            raise ValueError("A tile look's content id names another value")
    for row in update.tile_statics:
        static.tiles[row.position] = row
    for row in update.residue_materials:
        if static.residues.setdefault(row.residue_id, row) != row:
            raise ValueError("A residue material changed its static row")
    for row in update.object_looks:
        static.object_looks[row.item_uuid] = row
    for row in update.boundary_structures:
        if static.boundary_structures.setdefault(row.structure_id, row.structure) != row.structure:
            raise ValueError("A boundary structure's content id names another value")


def _reset_entered(memory: PlayerState, update: WorldUpdate, entered: frozenset[tuple[int, int]]) -> None:
    """Drop what the client holds on the entered cells, but the unchanged tiles and objects; the other tiles are
    the update's columns."""
    unchanged_tiles = frozenset(mask_positions(update.tiles_unchanged))
    if not unchanged_tiles <= entered or not unchanged_tiles <= memory.tiles.keys():
        raise ValueError("An unchanged tile is an entered cell the client holds")
    unchanged = frozenset(update.objects_unchanged)
    if not unchanged <= memory.objects.keys():
        raise ValueError("An unchanged object is one the client holds")
    for position in entered - unchanged_tiles:
        memory.tiles.pop(position, None)
    if update.tile_columns is not None:
        tiles = unpack_tile_columns(update.tile_columns, memory.static.tiles, memory.static.tile_looks)
        if not tiles.keys() <= entered - unchanged_tiles:
            raise ValueError("Tile columns describe entered cells only, none of them unchanged")
        memory.tiles.update(tiles)
    resent = set(update.objects.item_uuids) if update.objects is not None else set()
    for identity, held in tuple(memory.objects.items()):
        if identity not in resent and identity not in unchanged and placement_support_cells(held.placement) & entered:
            del memory.objects[identity]
            memory.object_members.pop(identity, None)
            continue
        suppressions = held.item.construction_suppressions
        if any(entered.intersection(row.positions) for row in suppressions):
            memory.objects[identity] = replace(held, item=replace(held.item, construction_suppressions=tuple(
                row.model_copy(update={"positions": tuple(position for position in row.positions
                    if position not in entered)}) for row in suppressions)))
    for identity, connector in tuple(memory.connectors.items()):
        if entered.intersection(connector.endpoints):
            del memory.connectors[identity]


def _merged_faces(held: FloorItem | None, row: tuple[ObjectResidueState, ...],
                  observed_faces: frozenset) -> tuple[ObjectResidueState, ...]:
    """The row's residues on the faces seen now, and the held residues' faces not seen now."""
    kept: dict[UUID, ObjectResidueState] = {}
    for residue in held.surface_residues if held is not None else ():
        faces = tuple(face for face in residue.faces if face not in observed_faces)
        if faces:
            kept[residue.condition_uuid] = residue.model_copy(update={"faces": faces})
    for residue in row:
        if not set(residue.faces) <= observed_faces:
            raise ValueError("An object row's residues lie on its observed faces")
        if not residue.faces:
            continue
        faces = set(residue.faces)
        prior = kept.get(residue.condition_uuid)
        if prior is not None:
            faces.update(prior.faces)
        kept[residue.condition_uuid] = residue.model_copy(update={
            "faces": tuple(sorted(faces, key=lambda face: face.value))})
    return tuple(kept[identity] for identity in sorted(kept, key=str))


def _merged_suppressions(held: FloorItem | None, row: tuple[SpellSuppression, ...]) -> tuple[SpellSuppression, ...]:
    """The row's perceived providers, then the held rows of the other providers."""
    perceived = {suppression.provider_uuid for suppression in row}
    return (*row, *(suppression for suppression in (held.construction_suppressions if held is not None else ())
        if suppression.provider_uuid not in perceived))


def _object(memory: PlayerState, row: ObjectRow, observers: int) -> None:
    identity = row.item_uuid
    held = memory.objects.get(identity)
    members = _members(row, observers)
    look = memory.static.object_looks.get(identity)
    if look is None:
        raise ValueError("An object's first row requires its look")
    placement = (unpack_placement(identity, row.placement, memory.static.tiles) if row.placement is not None
                 else held.placement if held is not None else None)
    if placement is None:
        raise ValueError("An object's first row requires its placement")
    item = join_floor_item(look, row.state, memory.static.boundary_structures)
    item = replace(item, surface_residues=_merged_faces(held.item if held is not None else None,
            item.surface_residues, frozenset(row.observed_faces)),
        construction_suppressions=_merged_suppressions(held.item if held is not None else None,
            item.construction_suppressions))
    memory.objects[identity] = PlayerObject(placement=placement, item=item,
        contained_items=held.contained_items if held is not None else None)
    memory.object_members[identity] = members


def _contained(static: StaticStore, row: ContainedItem) -> FloorItem:
    look = static.object_looks.get(row.item_uuid)
    if look is None:
        raise ValueError("A contained item requires its look")
    return join_floor_item(look, row.state, static.boundary_structures)


def _contents(memory: PlayerState, update: WorldUpdate) -> None:
    for row in update.contents:
        held = memory.objects.get(row.container_uuid)
        if held is None:
            raise ValueError("Contents require their container")
        memory.objects[row.container_uuid] = replace(held, contained_items=tuple(sorted(
            (_contained(memory.static, item) for item in row.items), key=lambda item: str(item.item_uuid))))
    for row in update.contents_changed:
        held = memory.objects.get(row.container_uuid)
        if held is None or held.contained_items is None:
            raise ValueError("A contents change requires contents the client holds")
        items = {item.item_uuid: item for item in held.contained_items}
        for identity in row.removed:
            items.pop(identity, None)
        items.update((item.item_uuid, _contained(memory.static, item)) for item in row.upserted)
        memory.objects[row.container_uuid] = replace(held, contained_items=tuple(
            items[identity] for identity in sorted(items, key=str)))


def _tiles(memory: PlayerState, update: WorldUpdate) -> None:
    """The keyed tile rows: scalars, objective light, the tile's own conditions, its residues."""
    tiles = memory.tiles

    def held(position: tuple[int, int]) -> WorldTileState:
        tile = tiles.get(position)
        if tile is None:
            raise ValueError("Tile field update requires an already known tile")
        return tile

    for row in update.tile_changes:
        tiles[row.position] = held(row.position).model_copy(update=dict(row.changes))
    for position, level in values_items(update.resolved_light):
        tiles[position] = held(position).model_copy(update={"resolved_light": LightLevel(level)})
    # The touched tiles' own condition names and residues, rebuilt once each below.
    parts: dict[tuple[int, int], tuple[str, ...]] = {}
    materials: dict[tuple[int, int], dict[str, TileResidueState]] = {}

    def residues(position: tuple[int, int]) -> dict[str, TileResidueState]:
        if position not in materials:
            tile = held(position)
            parts.setdefault(position, tile_own_condition_names(tile))
            materials[position] = {row.residue_id: row for row in tile.residues}
        return materials[position]

    for row in update.tile_conditions:
        residues(row.position)
        parts[row.position] = row.names
    for row in update.residues:
        rows = residues(row.position)
        material = memory.static.residues.get(row.residue_id)
        if material is None:
            raise ValueError("A residue requires its material's static row")
        existing = rows.get(row.residue_id)
        if row.condition_uuid is not None:
            # A whole row (a key new to the client, or one entering view) replaces what the client held.
            if row.amount is None:
                raise ValueError("A whole residue row carries its amount")
            existing = TileResidueState(condition_uuid=row.condition_uuid, residue_id=row.residue_id,
                description=material.description, amount=row.amount, max_amount=material.max_amount)
        elif existing is None:
            raise ValueError("A residue the client does not hold arrives whole")
        contributions = list(existing.contributions)
        for change in row.contributions:
            if change.index < len(contributions):
                contributions[change.index] = change.contribution
            elif change.index == len(contributions):
                contributions.append(change.contribution)
            else:
                raise ValueError("A residue contribution is set at an index it holds or appended")
        rows[row.residue_id] = existing.model_copy(update={
            "amount": row.amount if row.amount is not None else existing.amount,
            "contributions": tuple(contributions)})
    for row in update.residues_removed:
        if residues(row.position).pop(row.residue_id, None) is None:
            raise ValueError("A residue removal names a residue the client holds")
    for position, rows in materials.items():
        ordered = tuple(rows[key] for key in sorted(rows))
        tiles[position] = tiles[position].model_copy(update={"residues": ordered, "condition_names": (
            *parts[position], *(memory.static.residues[row.residue_id].name for row in ordered))})


def fold_world_update(memory: PlayerState, update: WorldUpdate) -> None:
    """Fold one occurrence's world update into the client's world."""
    fold_static_rows(memory.static, update)
    for identity in update.objects_removed:
        if memory.objects.pop(identity, None) is None:
            raise ValueError("An object removal names an object the client holds")
        memory.object_members.pop(identity, None)
    for identity in update.connectors_removed:
        if memory.connectors.pop(identity, None) is None:
            raise ValueError("A connector removal names a connector the client holds")
    entered = frozenset(mask_positions(update.entered))
    if entered:
        _reset_entered(memory, update, entered)
    observers = len(memory.viewing_audience.observers)
    for row in unpack_object_rows(update.objects):
        _object(memory, row, observers)
    _contents(memory, update)
    _tiles(memory, update)
    memory.connectors.update((row.connector_uuid, row) for row in update.connectors)
