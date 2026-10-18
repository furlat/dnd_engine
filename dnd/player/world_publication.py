"""A seat's world publication (player schema 16): what it perceives of tiles, objects, contents and connectors
change at one occurrence.

Functions of the session world as of the occurrence (`WorldFacts`), what the occurrence wrote (`AppliedWorldFact`,
which names the records: this module never compares world states), the seat's composed view before and after it
and the seat's knowledge (the objects it observes, the containers whose contents it sees and the static rows it
was sent), which `seat_world_update` advances. The client's memory is never read: what it holds follows from the
rules
(EVENT_NATIVE_PUBLICATION_PLAN_2026-10-18 §3.2-§3.5; world brief §2-§3):

- a record perceived before and after the occurrence travels as its keyed change;
- a record entering perception travels whole: a cell entering the composed view (or a visible tile replaced),
  every object touching it and every connector with an endpoint there; an object newly observed; a container
  whose contents become visible;
- the seat sees an object go when it observed it and the occurrence removed or moved it, or when it sees the
  object's support without it;
- leaving perception sends nothing;
- static rows (a tile's surface and name, a residue material, an object's look) travel once per seat.
"""

from collections.abc import Collection, Iterable
from dataclasses import dataclass
from uuid import UUID

from dnd.core.cells import mask_difference, mask_from_positions, mask_intersection, mask_positions, mask_union, \
    values_from_items
from dnd.core.item_types import ItemIntegrity, ItemPresentationState, ItemRemnantState
from dnd.player.audience import AudiencePerception, PlayerAudience
from dnd.player.facts import (BoundaryStructureStatic, ContainedItem, ContainerContents, ContentsChange,
    ContributionRow, FloorItem, ObjectLook, ObjectRow, ObjectState, PlayerObject, ResidueKey, ResidueMaterial,
    ResidueRow, TileConditions, TileFieldUpdate, TileLook, TileStatic, WorldUpdate)
from dnd.player.static_sent import StaticSent
from dnd.player.world_columns import (pack_object_rows, pack_placement, pack_tile_columns, split_floor_item,
    tile_look_id)
from dnd.types.cells import EMPTY_CELLS, CellMask, cell_in
from dnd.types.event_facts import (AppliedWorldFact, WorldConnectorState, WorldTileChanges, WorldTileState,
    tile_own_condition_names, tile_residue_names)
from dnd.types.residues import ObjectResidueState, TileResidueState
from dnd.types.senses import SensesSnapshot
from dnd.types.world import CardinalDirection
from dnd.types.world_placement import CARDINAL_DELTAS, OPPOSITE_DIRECTION, WorldObjectPlacement, placement_support_cells
from dnd.world_facts import WorldFacts, world_objects_at

Position = tuple[int, int]


def object_observed(world: WorldFacts, view: SensesSnapshot | None, identity: UUID) -> bool:
    """A contact, or a boundary's appearance through either visible incident support (an attachment needs its own
    contact: a visible supporting wall is no permission to disclose a hidden insert)."""
    if view is None:
        return False
    if identity in view.objects:
        return True
    obj = world.objects[identity]
    direction = obj.placement.boundary_direction
    if obj.item.supported_by_uuid is not None or direction is None or obj.item.boundary_structure is None:
        return False
    x, y = obj.placement.position
    dx, dy = CARDINAL_DELTAS[direction]
    return cell_in(view.visible, (x, y)) or cell_in(view.visible, (x + dx, y + dy))


def observed_faces(placement: WorldObjectPlacement, visible: CellMask) -> tuple[CardinalDirection, ...]:
    """A boundary's faces whose viewing cell is visible, by value; a center object has none."""
    direction = placement.boundary_direction
    if direction is None:
        return ()
    x, y = placement.position
    dx, dy = CARDINAL_DELTAS[direction]
    faces = [face for face, cell in ((OPPOSITE_DIRECTION[direction], (x, y)), (direction, (x + dx, y + dy)))
             if cell_in(visible, cell)]
    return tuple(sorted(faces, key=lambda face: face.value))


def observed_remnant(state: ItemRemnantState | None, known: Collection[UUID]) -> ItemRemnantState | None:
    """A composite names only the attachments whose look the seat was sent: never an undisclosed identity."""
    if state is None:
        return None
    return state.model_copy(update={"intact_supported_items": tuple(
        identity for identity in state.intact_supported_items if identity in known)})


def floor_item(item: ItemPresentationState, residues: tuple[ObjectResidueState, ...]) -> FloorItem:
    return FloorItem(item_uuid=item.item_uuid, item_id=item.item_id, name=item.name,
        visual_item_name=item.visual_item_name, visual_variant_id=item.visual_variant_id,
        stack_count=item.stack_count, is_pickable=item.is_pickable, item_effects=item.item_effects,
        map_char=item.map_char, boundary_structure=item.boundary_structure,
        contact_passage=item.contact_passage,
        supported_by_uuid=item.supported_by_uuid,
        blocks_propagation=item.blocks_propagation,
        is_open=item.is_open, is_lit=item.is_lit, is_engaged=item.is_engaged,
        very_bright_radius_feet=item.very_bright_radius_feet,
        bright_radius_feet=item.bright_radius_feet,
        dim_radius_feet=item.dim_radius_feet,
        surface_residues=residues, current_hit_points=item.current_hit_points, maximum_hit_points=item.maximum_hit_points,
        concentration_capacity=item.concentration_capacity, concentration_slots=item.concentration_slots,
        door_mechanism=item.door_mechanism, door_swing=item.door_swing, remnant_state=item.remnant_state,
        integrity=item.integrity, destruction_outcome=item.destruction_outcome,
        construction_owner_uuid=item.construction_owner_uuid, construction_geometry=item.construction_geometry,
        construction_suppressions=item.construction_suppressions, known_to_creator=item.known_to_creator)


def contents_granted(world: WorldFacts, view: SensesSnapshot, identity: UUID) -> bool:
    """A container's contents are seen while it is open (or broken) and in visual contact."""
    obj = world.objects[identity]
    contact = view.objects.get(identity)
    return (obj.contained_items is not None and contact is not None and contact.visual
            and (obj.item.is_open is True or obj.item.integrity is ItemIntegrity.DESTROYED))


def disclosed_floor_item(world: WorldFacts, view: SensesSnapshot, identity: UUID, known: Collection[UUID]) -> FloorItem:
    """What the seat sees of an observed object now: residues on its observed faces, the suppression rows of
    providers it perceives (their cells it sees), a remnant naming only known attachments."""
    obj = world.objects[identity]
    faces = set(observed_faces(obj.placement, view.visible))
    residues = {}
    for residue in obj.item.surface_residues:
        seen = tuple(face for face in residue.faces if face in faces)
        if seen:
            residues[residue.condition_uuid] = residue.model_copy(update={"faces": seen})
    suppressions = []
    for outcome in obj.item.construction_suppressions:
        provider = view.spatial_effects.get(outcome.provider_uuid)
        if provider is not None and provider.area_geometry is not None:
            suppressions.append(outcome.model_copy(update={"provider_content_ref": provider.content_ref,
                "area_geometry": provider.area_geometry, "anchor_elevation_steps": provider.anchor_elevation_steps,
                "positions": tuple(sorted(position for position in outcome.positions
                    if cell_in(view.visible, position)))}))
    item = obj.item.model_copy(update={"remnant_state": observed_remnant(obj.item.remnant_state, known),
        "construction_suppressions": tuple(suppressions)})
    return floor_item(item, tuple(residues[key] for key in sorted(residues, key=str)))


def disclosed_world_object(world: WorldFacts, view: SensesSnapshot, identity: UUID,
                           known: Collection[UUID]) -> PlayerObject:
    """An observed object as the seat sees it now, with its contents when they are seen."""
    obj = world.objects[identity]
    contents = (tuple(floor_item(child, ()) for child in obj.contained_items or ())
                if contents_granted(world, view, identity) else None)
    return PlayerObject(placement=obj.placement, item=disclosed_floor_item(world, view, identity, known),
        contained_items=contents)


def object_members(world: WorldFacts, perception: AudiencePerception, audience: PlayerAudience,
                   identity: UUID) -> int | None:
    """Which observers observe the object (bit i: `audience.observers[i]`); None for a one-observer seat.

    Exact whenever an object row is sent; between rows the client holds the bits of its last row (D2), and a
    contact's members are the sensory contact rows' (`object_contact_members`, E3-sensory)."""
    if len(audience.observers) == 1:
        return None
    return sum(1 << index for index, observer in enumerate(audience.observers)
               if object_observed(world, perception.members.get(observer), identity))


@dataclass(frozen=True, slots=True)
class SensedWorld:
    """A member's sensory occurrence, as the seat's world publication reads it: the object contacts and spatial
    effects it changed or removed."""

    contacts: frozenset[UUID]
    effects: frozenset[UUID]


def _whole_residue(position: Position, residue: TileResidueState) -> ResidueRow:
    return ResidueRow(position=position, residue_id=residue.residue_id, condition_uuid=residue.condition_uuid,
        amount=residue.amount, contributions=tuple(ContributionRow(index=index, contribution=row)
            for index, row in enumerate(residue.contributions)))


@dataclass(slots=True)
class _Rows:
    """One update's rows as they are built."""

    tile_looks: list[TileLook]
    tile_statics: list[TileStatic]
    residue_materials: list[ResidueMaterial]
    object_looks: list[ObjectLook]
    boundary_structures: list[BoundaryStructureStatic]


def _material(rows: _Rows, tile: WorldTileState, residue_id: str, sent: StaticSent, pending: StaticSent) -> None:
    """A residue material's static row, once per seat (its name is the tile's name for it)."""
    if residue_id in sent.residues or residue_id in pending.residues:
        return
    index = next((index for index, row in enumerate(tile.residues) if row.residue_id == residue_id), None)
    if index is None:
        raise ValueError(f"A residue material's static row is read from a tile holding it ({residue_id})")
    residue = tile.residues[index]
    rows.residue_materials.append(ResidueMaterial(residue_id=residue_id, name=tile_residue_names(tile)[index],
        description=residue.description, max_amount=residue.max_amount))
    pending.residues.add(residue_id)


def _look(rows: _Rows, look: ObjectLook, sent: StaticSent, pending: StaticSent) -> None:
    if look.item_uuid not in sent.object_looks and look.item_uuid not in pending.object_looks:
        rows.object_looks.append(look)
        pending.object_looks.add(look.item_uuid)


def _split(rows: _Rows, item: FloorItem, sent: StaticSent, pending: StaticSent) -> ObjectState:
    """A floor item's state; its look and its boundary structure travel as static rows, once per seat."""
    look, state = split_floor_item(item)
    _look(rows, look, sent, pending)
    identity = state.boundary_structure
    if (item.boundary_structure is not None and identity is not None and identity not in sent.boundary_structures
            and identity not in pending.boundary_structures):
        rows.boundary_structures.append(BoundaryStructureStatic(structure_id=identity, structure=item.boundary_structure))
        pending.boundary_structures.add(identity)
    return state


def _contained(rows: _Rows, items: Iterable[ItemPresentationState], sent: StaticSent,
               pending: StaticSent) -> tuple[ContainedItem, ...]:
    result = []
    for child in items:
        result.append(ContainedItem(item_uuid=child.item_uuid, state=_split(rows, floor_item(child, ()), sent, pending)))
    return tuple(result)


def _scalars(changes: WorldTileChanges, keys: Iterable[str], tile: WorldTileState) -> None:
    """A kept tile's written scalars with their values as of the occurrence. Its condition names follow its own
    conditions' and residues' rows (a residue writer's names are its materials', which the client derives)."""
    for key in keys:
        match key:
            case "walking_cost":
                changes["walking_cost"] = tile.walking_cost
            case "flying_cost":
                changes["flying_cost"] = tile.flying_cost
            case "swimming_cost":
                changes["swimming_cost"] = tile.swimming_cost
            case "burrowing_cost":
                changes["burrowing_cost"] = tile.burrowing_cost
            case "blocks_optics":
                changes["blocks_optics"] = tile.blocks_optics
            case "blocks_propagation":
                changes["blocks_propagation"] = tile.blocks_propagation
            case "elevation_steps":
                changes["elevation_steps"] = tile.elevation_steps
            case "surface_kind":
                changes["surface_kind"] = tile.surface_kind
            case "slope_axis":
                changes["slope_axis"] = tile.slope_axis
            case "default_light":
                changes["default_light"] = tile.default_light
            case "condition_names":
                pass
            case _:
                raise ValueError(f"No player wire field for the tile field {key}")


def seat_world_update(world: WorldFacts, occurrence: int, applied: tuple[AppliedWorldFact, ...], before: CellMask,
                      view: SensesSnapshot, perception: AudiencePerception, audience: PlayerAudience,
                      sensed: SensedWorld | None, *, observed: set[UUID], granted: set[UUID], sent: StaticSent,
                      pending: StaticSent) -> WorldUpdate | None:
    """One seat's world update at an occurrence, or None when it perceives no world change there.

    `applied` is what the occurrence wrote (for a member's sensory occurrence, what the changes it saw happen
    wrote, folded at their own versions): it names the records written, whose values are read from `world` as
    of the occurrence. `before` is the composed view's visible cells before it, `view` the composed view after
    it. It writes the seat knowledge it is given: `observed` and `granted` (the seat's observed objects and seen
    contents) become the seat's perception after it, and the static rows sent here join `pending` (the walk's,
    merged into `sent` once its group is emitted, never mid-walk: plan §3.5).
    """
    visible = view.visible
    replaced = set().union(*(row.replaced for row in applied))
    entered_cells = mask_intersection(mask_from_positions(replaced), visible) if replaced else EMPTY_CELLS
    left: set[Position] = set()
    if before is not visible:
        entered_cells = mask_union(entered_cells, mask_difference(visible, before))
        left.update(mask_positions(mask_difference(before, visible)))
    entered = set(mask_positions(entered_cells))
    rows = _Rows([], [], [], [], [])

    # Tiles: the entered cells whole (their static rows first: a placement's anchor tile is derived from them).
    tiles = {position: world.tiles[position] for position in sorted(entered) if position in world.tiles}
    tile_conditions: dict[Position, tuple[str, ...]] = {}
    residues: dict[tuple[Position, str], ResidueRow] = {}
    residues_removed: dict[tuple[Position, str], ResidueKey] = {}
    for position, tile in tiles.items():
        if tile.tile_uuid not in sent.tiles and tile.tile_uuid not in pending.tiles:
            look = tile_look_id(tile.surface, tile.name)
            if look not in sent.tile_looks and look not in pending.tile_looks:
                rows.tile_looks.append(TileLook(look_id=look, surface=tile.surface, name=tile.name))
                pending.tile_looks.add(look)
            rows.tile_statics.append(TileStatic(position=position, tile_uuid=tile.tile_uuid, look=look))
            pending.tiles.add(tile.tile_uuid)
        if own := tile_own_condition_names(tile):
            tile_conditions[position] = own
        for residue in tile.residues:
            _material(rows, tile, residue.residue_id, sent, pending)
            residues[(position, residue.residue_id)] = _whole_residue(position, residue)

    # Objects: which the occurrence can change the seat's observation of, and which it observes after.
    written = set().union(*(row.objects for row in applied))
    moved = set().union(*(row.moved for row in applied))
    contacts = sensed.contacts if sensed is not None else frozenset()
    effects = sensed.effects if sensed is not None else frozenset()
    touching = world_objects_at(world, entered)
    for position in entered & world.constructions_by_position.keys():
        touching.update(world.constructions_by_position[position])
    providers = set()
    for identity in effects:
        providers.update(world.constructions_by_provider.get(identity, ()))
    candidates = written | world_objects_at(world, entered | left) | touching | providers | contacts
    after = {identity for identity in candidates
             if identity in world.objects and object_observed(world, view, identity)}
    before_observed = observed & candidates
    whole = (after - observed) | (after & (touching | providers))
    for identity in sorted(whole, key=str):
        _look(rows, split_floor_item(floor_item(world.objects[identity].item, ()))[0], sent, pending)
    known = sent.object_looks | pending.object_looks
    # A composite names an attachment once its look is sent: its row is sent again with the new name.
    remnants = {remnant for identity in whole for remnant in world.remnants_by_item.get(identity, ())}
    remnants = {identity for identity in remnants - whole
                if identity in after or identity not in candidates and identity in observed}
    changed = ((after & before_observed & written) | remnants) - whole
    object_rows = []
    held_tiles = sent.tiles | pending.tiles
    for identity in sorted(whole | changed, key=str):
        placement = world.objects[identity].placement
        anchor = world.tiles.get(placement.position)
        state = _split(rows, disclosed_floor_item(world, view, identity, known), sent, pending)
        object_rows.append(ObjectRow(item_uuid=identity, members=object_members(world, perception, audience, identity),
            state=state, placement=pack_placement(placement, anchor.tile_uuid
                if anchor is not None and anchor.tile_uuid in held_tiles else None)
                if identity in whole or identity in moved else None,
            observed_faces=observed_faces(placement, visible)))
    removed = sorted((identity for identity in before_observed - after
        if identity in written or identity not in world.objects
        or any(cell_in(visible, cell) for cell in placement_support_cells(world.objects[identity].placement))),
        key=str)
    observed.difference_update(candidates)
    observed.update(after)

    # Contents: whole when they become seen (or their container is sent whole), keyed while seen.
    granted_after = {identity for identity in after if contents_granted(world, view, identity)}
    contents = []
    for identity in sorted(granted_after - (granted - whole), key=str):
        contents.append(ContainerContents(container_uuid=identity, items=_contained(rows,
            world.objects[identity].contained_items or (), sent, pending)))
    keyed_contents: dict[UUID, tuple[set[UUID], set[UUID]]] = {}
    for row in applied:
        for owner, added, removed_items in row.contents:
            if owner in granted and owner in granted_after and owner not in whole:
                upserts, removals = keyed_contents.setdefault(owner, (set(), set()))
                upserts.update(added)
                removals.update(removed_items)
    contents_changed = []
    for owner in sorted(keyed_contents, key=str):
        upserts, removals = keyed_contents[owner]
        held = {child.item_uuid: child for child in world.objects[owner].contained_items or ()}
        contents_changed.append(ContentsChange(container_uuid=owner,
            upserted=_contained(rows, (held[identity] for identity in sorted(upserts & held.keys(), key=str)),
                sent, pending),
            removed=tuple(sorted(removals - held.keys(), key=str))))
    granted.difference_update(candidates)
    granted.update(granted_after)

    # Connectors: the entered cells' whole, then the ones written while perceived.
    connectors: dict[UUID, WorldConnectorState] = {}
    if entered:
        for row in world.connectors.values():
            if entered.intersection(row.endpoints) and all(cell_in(visible, point) for point in row.endpoints):
                connectors[row.connector_uuid] = row
    connectors_removed = []
    for record in applied:
        for identity, previous in record.connectors:
            current = world.connectors.get(identity)
            if current is not None and all(cell_in(visible, point) for point in current.endpoints):
                connectors[identity] = current
            elif (previous is not None and identity not in connectors_removed
                  and all(cell_in(before, point) and cell_in(visible, point) for point in previous.endpoints)):
                connectors.pop(identity, None)
                connectors_removed.append(identity)

    # Keyed tile changes of the perceived tiles.
    tile_changes: dict[Position, WorldTileChanges] = {}
    light: dict[Position, int] = {}

    def perceived(position: Position) -> WorldTileState | None:
        """A tile seen before and after the occurrence (and not entering), as of now; leaving sends nothing."""
        return (world.tiles.get(position) if position not in entered and cell_in(before, position)
                and cell_in(visible, position) else None)

    # Each touched material: whether the client held it before this update (its first change here is not a new
    # deposit) and whether it was removed in between.
    materials: dict[tuple[Position, str], tuple[bool, set[int], bool]] = {}
    for record in applied:
        for change in record.tiles:
            if (tile := perceived(change.position)) is None:
                continue
            _scalars(tile_changes.setdefault(change.position, WorldTileChanges()), change.fields, tile)
            for residue in change.residues:
                key = (change.position, residue.residue_id)
                held, indexes, removed_between = materials.get(key, (key not in record.new_residues, set(), False))
                if residue.contribution_index is not None:
                    indexes.add(residue.contribution_index)
                materials[key] = (held, indexes, removed_between or residue.state is None)
        for position, keys in record.tile_fields:
            if (tile := perceived(position)) is not None:
                _scalars(tile_changes.setdefault(position, WorldTileChanges()), keys, tile)
        for position in record.light:
            if (tile := perceived(position)) is not None:
                light[position] = tile.resolved_light.value
        for position in record.tile_conditions:
            if (tile := perceived(position)) is not None:
                tile_conditions[position] = tile_own_condition_names(tile)
    for (position, residue_id), (held, indexes, removed_between) in materials.items():
        tile = world.tiles[position]
        now = next((row for row in tile.residues if row.residue_id == residue_id), None)
        if now is None:
            if held:
                residues_removed[(position, residue_id)] = ResidueKey(position=position, residue_id=residue_id)
        elif not held or removed_between:
            _material(rows, tile, residue_id, sent, pending)
            residues[(position, residue_id)] = _whole_residue(position, now)
        else:
            residues[(position, residue_id)] = ResidueRow(position=position, residue_id=residue_id, amount=now.amount,
                contributions=tuple(ContributionRow(index=index, contribution=now.contributions[index])
                    for index in sorted(indexes)))
    tile_changes = {position: changes for position, changes in tile_changes.items() if changes}
    update = WorldUpdate(occurrence=occurrence, entered=entered_cells,
        tile_looks=tuple(rows.tile_looks), tile_statics=tuple(rows.tile_statics), tile_columns=pack_tile_columns(tiles),
        tile_conditions=tuple(TileConditions(position=position, names=names)
            for position, names in sorted(tile_conditions.items())),
        tile_changes=tuple(TileFieldUpdate(position=position, changes=changes)
            for position, changes in sorted(tile_changes.items())),
        resolved_light=values_from_items(light), residue_materials=tuple(rows.residue_materials),
        boundary_structures=tuple(rows.boundary_structures),
        residues=tuple(residues[key] for key in sorted(residues)),
        residues_removed=tuple(residues_removed[key] for key in sorted(residues_removed)),
        object_looks=tuple(rows.object_looks), objects=pack_object_rows(object_rows), objects_removed=tuple(removed),
        contents=tuple(contents), contents_changed=tuple(contents_changed),
        connectors=tuple(connectors[identity] for identity in sorted(connectors, key=str)),
        connectors_removed=tuple(connectors_removed))
    return None if update == WorldUpdate(occurrence=occurrence) else update
