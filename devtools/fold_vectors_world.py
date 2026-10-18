"""Golden vectors of the schema-16 world client fold (EVENT_NATIVE_PUBLICATION_PLAN_2026-10-18 §3.3-§3.5).

A vector is a seat's audience and a sequence of received world updates, with the client world expected after each.
The expected worlds are written here by hand from the client's rules, never dumped from the fold:

- the cells an update enters are authoritative: the client drops what it held there and keeps what the update
  carries (tiles from their static row and columns, every object touching them, every connector reaching them);
- an object is forgotten when its support enters view without it, or when the seat sees it go (`objects_removed`);
- a wall's residue faces not seen now keep their last sight;
- a construction's suppressed cells are retired where they enter view; a perceived provider's row replaces it;
- contents are kept when their grant is lost and whole again when regained;
- leaving view changes nothing; static rows come once per id and are never pruned;
- a placement travels without what the client derives (`ObjectPlacement`), a boundary structure as a static row
  under its content id, a visual name only when it is not the name.

The files are what Godot folds too (`sdk/protocol/fold-vectors/world/*.json`);
`tests/player/test_world_fold_vectors.py` folds them with the reference fold
(`dnd.player.world_reduction.fold_world_update`).

    PYTHONPATH=. python devtools/fold_vectors_world.py   # write the files (the vector test checks they are current)
"""

import argparse
from dataclasses import dataclass, replace
import json
from pathlib import Path
from uuid import UUID

from pydantic import TypeAdapter

from dnd.core.cells import mask_from_positions, values_from_items
from dnd.core.traversal_connectors import ConnectorProvocationPolicy, TraversalConnectorKind
from dnd.core.world_edges import ElevationSurfaceKind, SlopeAxis
from dnd.player.facts import (BoundaryStructureStatic, ContainedItem, ContainerContents, ContentsChange, ContributionRow,
    FloorItem, ObjectRow, ResidueKey, ResidueMaterial, ResidueRow, TileConditions, TileFieldUpdate, TileStatic,
    WorldUpdate)
from dnd.player.world_columns import pack_placement, pack_tile_columns, split_floor_item, structure_id
from dnd.types.event_facts import WorldConnectorState, WorldTileState
from dnd.types.materials import Material, TileSurface
from dnd.types.residues import ObjectResidueState, ResidueContribution, ResidueEllipse
from dnd.types.spell_suppression import SpellSuppression
from dnd.types.world import CardinalDirection, LightLevel
from dnd.types.world import WorldEdgeChannel
from dnd.types.world_placement import (BoundaryStructure, BoundaryStructureKind, WorldObjectPlacement,
    WorldObjectSupport, WorldPlacementKind)

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / "sdk" / "protocol" / "fold-vectors" / "world"
UPDATE = TypeAdapter(WorldUpdate)

Position = tuple[int, int]
A, B = UUID("00000000-0000-4000-8000-00000000000a"), UUID("00000000-0000-4000-8000-00000000000b")
BOX, TORCH, WALL, CHEST = (UUID(f"00000000-0000-4000-8000-00000000200{index}") for index in range(1, 5))
POTION, ROPE, STONE_WALL = (UUID(f"00000000-0000-4000-8000-00000000300{index}") for index in range(1, 4))
LADDER, ROPE_LINE = UUID("00000000-0000-4000-8000-000000004001"), UUID("00000000-0000-4000-8000-000000004002")
BLOOD_ON_WALL, SOOT_ON_WALL = UUID("00000000-0000-4000-8000-000000005001"), UUID("00000000-0000-4000-8000-000000005002")
BLOOD_AT_1_0 = UUID("00000000-0000-4000-8000-000000005101")
FOG = UUID("00000000-0000-4000-8000-000000006001")
CRATE, CART, SIGN, BANNER = (UUID(f"00000000-0000-4000-8000-00000000700{index}") for index in range(1, 5))
EAST_WALL = UUID("00000000-0000-4000-8000-000000007005")
PLACEMENT = TypeAdapter(WorldObjectPlacement)
STONE_WALL_STRUCTURE = BoundaryStructure(structure=BoundaryStructureKind.WALL, material=Material.STONE,
    blocked_channels=(WorldEdgeChannel.MOVEMENT, WorldEdgeChannel.OPTICAL))
STONE = TileSurface(base_material=Material.STONE)


def tile_uuid(position: Position, generation: int = 0) -> UUID:
    """A tile's uuid: one per cell per replacement."""
    x, y = position
    return UUID(f"00000000-0000-4000-8000-0001{generation:02d}{x:03d}{y:03d}")


def tile(position: Position, *, generation: int = 0, light: LightLevel = LightLevel.BRIGHT_LIGHT,
         walking_cost: int = 1, blocks_optics: bool = False) -> WorldTileState:
    return WorldTileState(tile_uuid=tile_uuid(position, generation), position=position, surface=STONE,
        name="Stone floor", blocks_optics=blocks_optics, blocks_propagation=blocks_optics, walking_cost=walking_cost,
        flying_cost=1, swimming_cost=0, burrowing_cost=0, elevation_steps=0,
        surface_kind=ElevationSurfaceKind.ORDINARY, default_light=light, resolved_light=light)


def static(row: WorldTileState) -> TileStatic:
    return TileStatic(position=row.position, tile_uuid=row.tile_uuid, surface=row.surface, name=row.name)


def placement(identity: UUID, position: Position, direction: CardinalDirection | None = None) -> WorldObjectPlacement:
    owner = tile_uuid(position)
    return WorldObjectPlacement(object_uuid=identity, tile_uuid=owner, position=position,
        kind=WorldPlacementKind.BOUNDARY if direction is not None else WorldPlacementKind.CENTER,
        occupies_bands=direction is None, boundary_direction=direction, base_height_steps=0, top_height_steps=2,
        covered_supports=(WorldObjectSupport(position=position, tile_uuid=owner),))


def item(identity: UUID, name: str, **values) -> FloorItem:
    return FloorItem(item_uuid=identity, item_id=f"item.fold_vectors.{name.lower().replace(' ', '_')}", name=name,
        visual_item_name=values.pop("visual_item_name", name.lower()), visual_variant_id=None, map_char=name[0],
        boundary_structure=None, is_open=values.pop("is_open", None), is_lit=None, **values)


def look_and_row(value: FloorItem, at: WorldObjectPlacement | None, *, members: int | None = None,
                 faces: tuple[CardinalDirection, ...] = (), anchor: UUID | None = None):
    """An object's look and row; its placement packed against the client's static row at its anchor cell
    (`anchor`, default the vectors' tile there)."""
    look, state = split_floor_item(value)
    return look, ObjectRow(item_uuid=value.item_uuid, members=members, state=state, observed_faces=faces,
        placement=pack_placement(at, anchor if anchor is not None else tile_uuid(at.position)) if at is not None else None)


def connector(identity: UUID, endpoints: tuple[Position, Position]) -> WorldConnectorState:
    return WorldConnectorState(connector_uuid=identity, authored_id=f"connector.{identity.int}",
        kind=TraversalConnectorKind.LADDER, presentation_key="ladder", endpoints=endpoints,
        support_tile_uuids=(tile_uuid(endpoints[0]), tile_uuid(endpoints[1])), endpoint_elevations_feet=(0, 10),
        movement_cost_feet=10, bidirectional=True, enabled=True,
        provocation_policy=ConnectorProvocationPolicy.DOES_NOT_PROVOKE)


def entering(occurrence: int, tiles: tuple[WorldTileState, ...], *, statics: tuple[WorldTileState, ...] | None = None,
             cells: tuple[Position, ...] = (), **rows) -> WorldUpdate:
    """An update entering these cells: their tiles (static rows for `statics`, default all) and the given rows."""
    return WorldUpdate(occurrence=occurrence, entered=mask_from_positions(cells or tuple(row.position for row in tiles)),
        tile_statics=tuple(static(row) for row in (tiles if statics is None else statics)),
        tile_columns=pack_tile_columns({row.position: row for row in tiles}), **rows)


BLOOD = ResidueMaterial(residue_id="residue.blood", name="Blood", description="A pool of blood.", max_amount=3)
SPLASH = ResidueContribution(ellipses=(ResidueEllipse(center=(1.5, 0.5), radius_x=0.4, radius_y=0.3),))
SPATTER = ResidueContribution(ellipses=(ResidueEllipse(center=(1.2, 0.8), radius_x=0.2, radius_y=0.2),))


def wall_residue(identity: UUID, residue: str, *faces: CardinalDirection) -> ObjectResidueState:
    return ObjectResidueState(condition_uuid=identity, residue_id=residue, description=residue, faces=faces)


@dataclass(frozen=True)
class Step:
    update: WorldUpdate
    expected: dict


def view(tiles: dict | None = None, objects: dict | None = None, connectors: tuple[UUID, ...] = ()) -> dict:
    return {"tiles": tiles or {}, "objects": objects or {}, "connectors": sorted(str(row) for row in connectors)}


TILE = TypeAdapter(WorldTileState)


def tile_view(row: WorldTileState, *, conditions: tuple[str, ...] = (), residues: dict | None = None) -> dict:
    """The client's tile: every field of `row` (its static part and scalars), its condition names and residues."""
    return {"tile": TILE.dump_python(row.model_copy(update={"condition_names": (), "residues": ()}), mode="json"),
            "conditions": list(conditions), "residues": residues or {}}


def object_view(at: WorldObjectPlacement, *, members: int = 1, name: str, is_open: bool | None = None,
                faces: dict | None = None, suppressions: dict | None = None, contents: list | None = None,
                visual: str | None = None, structure: BoundaryStructure | None = None) -> dict:
    """The client's object: its whole decoded placement, members, names, door state, faces, suppressions,
    contents and boundary structure."""
    return {"placement": PLACEMENT.dump_python(at, mode="json"), "members": members, "name": name,
            "visual_item_name": visual if visual is not None else name.lower(), "is_open": is_open,
            "faces": faces or {}, "suppressions": suppressions or {}, "contents": contents,
            "structure": structure.model_dump(mode="json") if structure is not None else None}


def vectors() -> dict[str, tuple[str, tuple[UUID, ...], list[Step]]]:
    floor = {position: tile(position) for position in ((0, 0), (1, 0), (2, 0), (3, 0))}
    t = {f"{x},{y}": tile_view(row) for (x, y), row in floor.items()}
    box_at, torch_at, chest_at = placement(BOX, (1, 0)), placement(TORCH, (2, 0)), placement(CHEST, (3, 0))
    box_look, box_at_1 = look_and_row(item(BOX, "Box"), box_at)
    torch_look, torch_row = look_and_row(item(TORCH, "Torch", supported_by_uuid=WALL), torch_at)
    wall = item(WALL, "Wall", maximum_hit_points=30, current_hit_points=30)
    wall_at = placement(WALL, (0, 0), CardinalDirection.NORTH)
    wall_look, _ = split_floor_item(wall)
    north_cell = tile((0, 1))
    chest = item(CHEST, "Chest", is_open=True)
    chest_look, chest_row = look_and_row(chest, chest_at)
    potion_look, potion_state = split_floor_item(item(POTION, "Potion"))
    rope_look, rope_state = split_floor_item(item(ROPE, "Rope"))
    construction = item(STONE_WALL, "Stone wall", construction_suppressions=(
        SpellSuppression(provider_uuid=FOG, positions=((2, 0), (3, 0))),))
    construction_at = placement(STONE_WALL, (0, 0))
    construction_look, construction_row = look_and_row(construction, construction_at)
    replaced = tile((1, 0), generation=1, walking_cost=2)
    # w12: every scalar a tile column carries, at values other than the floor's.
    wood = TileSurface(base_material=Material.WOOD)
    varied = (
        tile((0, 0)).model_copy(update={"surface_kind": ElevationSurfaceKind.STAIRS,
            "slope_axis": SlopeAxis.NORTH_SOUTH, "elevation_steps": 3, "walking_cost": 2, "flying_cost": 0}),
        tile((1, 0)).model_copy(update={"surface_kind": ElevationSurfaceKind.RAMP, "slope_axis": SlopeAxis.EAST_WEST,
            "elevation_steps": -2, "swimming_cost": 7, "burrowing_cost": 255, "blocks_propagation": True,
            "default_light": LightLevel.DARKNESS, "resolved_light": LightLevel.DIM_LIGHT}),
        tile((2, 0)).model_copy(update={"blocks_optics": True, "blocks_propagation": False, "surface": wood,
            "name": "Plank wall", "default_light": LightLevel.DIM_LIGHT, "resolved_light": LightLevel.BRIGHT_LIGHT}))
    # w11: a centre object at its defaults; a two-cell object raised off the floor with a removed band; a boundary
    # with an orientation; an object naming another tile than the cell's held static row; two walls of one
    # structure.
    crate_at = placement(CRATE, (1, 0))
    cart_at = WorldObjectPlacement(object_uuid=CART, tile_uuid=tile_uuid((2, 0)), position=(2, 0),
        kind=WorldPlacementKind.CENTER, occupies_bands=False, base_height_steps=1, top_height_steps=3,
        covered_supports=(WorldObjectSupport(position=(2, 0), tile_uuid=tile_uuid((2, 0))),
                          WorldObjectSupport(position=(3, 0), tile_uuid=tile_uuid((3, 0)))),
        removed_bands=((3, 0, 2),))
    sign_at = placement(SIGN, (3, 0), CardinalDirection.EAST).model_copy(update={"orientation": CardinalDirection.NORTH})
    older = tile_uuid((0, 0), generation=7)
    banner_at = WorldObjectPlacement(object_uuid=BANNER, tile_uuid=older, position=(0, 0),
        kind=WorldPlacementKind.CENTER, occupies_bands=True, base_height_steps=0, top_height_steps=2,
        covered_supports=(WorldObjectSupport(position=(0, 0), tile_uuid=older),))
    east_wall_at = placement(EAST_WALL, (2, 0), CardinalDirection.EAST)
    walled = replace(wall, boundary_structure=STONE_WALL_STRUCTURE)
    placed = (look_and_row(item(CRATE, "Crate"), crate_at), look_and_row(item(CART, "Cart"), cart_at),
              look_and_row(item(SIGN, "Sign", visual_item_name="Sign"), sign_at),
              look_and_row(item(BANNER, "Banner"), banner_at),
              look_and_row(walled, wall_at), look_and_row(replace(walled, item_uuid=EAST_WALL), east_wall_at))
    return {
        "w1_an_object_moved_unseen_is_dropped_when_its_cell_reenters": (
            "Entered cells are authoritative: an object the client holds on a cell entering view without it is gone.",
            (A,), [
            Step(entering(0, tuple(floor.values()), object_looks=(box_look,), objects=(box_at_1,)),
                 view(t, {str(BOX): object_view(box_at, name="Box")})),
            # The box is moved while the seat sees neither cell: nothing is sent, the client keeps its last sight.
            Step(WorldUpdate(occurrence=1), view(t, {str(BOX): object_view(box_at, name="Box")})),
            Step(entering(2, (floor[(1, 0)],), statics=()), view(t)),
        ]),
        "w2_an_object_seen_gone_is_removed": (
            "A seat that sees an object's support without it is told so; other objects stay.",
            (A,), [
            Step(entering(0, tuple(floor.values()), object_looks=(box_look, torch_look), objects=(box_at_1, torch_row)),
                 view(t, {str(BOX): object_view(box_at, name="Box"), str(TORCH): object_view(torch_at, name="Torch")})),
            Step(WorldUpdate(occurrence=1, objects_removed=(TORCH,)), view(t, {str(BOX): object_view(box_at, name="Box")})),
        ]),
        "w3_leaving_view_keeps_memory": (
            "Leaving view sends nothing: tiles, objects, contents and connectors stay as last seen.",
            (A,), [
            Step(entering(0, tuple(floor.values()), object_looks=(chest_look, potion_look), objects=(chest_row,),
                          contents=(ContainerContents(container_uuid=CHEST,
                              items=(ContainedItem(item_uuid=POTION, state=potion_state),)),),
                          connectors=(connector(LADDER, ((0, 0), (1, 0))),)),
                 view(t, {str(CHEST): object_view(chest_at, name="Chest", is_open=True, contents=[str(POTION)])},
                      (LADDER,))),
            Step(WorldUpdate(occurrence=1),
                 view(t, {str(CHEST): object_view(chest_at, name="Chest", is_open=True, contents=[str(POTION)])},
                      (LADDER,))),
        ]),
        "w4_a_walls_unseen_faces_keep_their_last_sight": (
            "A wall's residues are authoritative for the faces seen now; the others keep their last sight, and a "
            "face cleaned in view goes.",
            (A,), [
            Step(entering(0, (floor[(0, 0)],), object_looks=(wall_look,), objects=(look_and_row(replace(wall,
                     surface_residues=(wall_residue(BLOOD_ON_WALL, "residue.blood", CardinalDirection.SOUTH),)),
                     wall_at, faces=(CardinalDirection.SOUTH,))[1],)),
                 view({"0,0": tile_view(floor[(0, 0)])}, {str(WALL): object_view(wall_at, name="Wall",
                     faces={str(BLOOD_ON_WALL): ["south"]})})),
            # The far side comes into view: its soot is seen there, the blood on the near face is not seen now.
            Step(entering(1, (north_cell,), objects=(look_and_row(replace(wall, surface_residues=(
                     wall_residue(SOOT_ON_WALL, "residue.soot", CardinalDirection.NORTH),)),
                     None, faces=(CardinalDirection.NORTH,))[1],)),
                 view({"0,0": tile_view(floor[(0, 0)]), "0,1": tile_view(north_cell)},
                      {str(WALL): object_view(wall_at, name="Wall",
                          faces={str(BLOOD_ON_WALL): ["south"], str(SOOT_ON_WALL): ["north"]})})),
            # The near face is washed while both faces are seen: its blood goes, the soot stays.
            Step(WorldUpdate(occurrence=2, objects=(look_and_row(replace(wall, surface_residues=(
                     wall_residue(SOOT_ON_WALL, "residue.soot", CardinalDirection.NORTH),)),
                     None, faces=(CardinalDirection.NORTH, CardinalDirection.SOUTH))[1],)),
                 view({"0,0": tile_view(floor[(0, 0)]), "0,1": tile_view(north_cell)},
                      {str(WALL): object_view(wall_at, name="Wall", faces={str(SOOT_ON_WALL): ["north"]})})),
        ]),
        "w5_suppressed_cells_retire_where_they_enter_view": (
            "A construction's suppressed cells entering view without it are retired; its provider's row replaces "
            "its own when perceived.",
            (A,), [
            Step(entering(0, tuple(floor.values()), object_looks=(construction_look,), objects=(construction_row,)),
                 view(t, {str(STONE_WALL): object_view(construction_at, name="Stone wall",
                     suppressions={str(FOG): [[2, 0], [3, 0]]})})),
            Step(entering(1, (floor[(3, 0)],), statics=()),
                 view(t, {str(STONE_WALL): object_view(construction_at, name="Stone wall", suppressions={str(FOG): [[2, 0]]})})),
            Step(WorldUpdate(occurrence=2, objects=(look_and_row(replace(construction, construction_suppressions=(
                     SpellSuppression(provider_uuid=FOG, positions=((1, 0),)),)), None)[1],)),
                 view(t, {str(STONE_WALL): object_view(construction_at, name="Stone wall", suppressions={str(FOG): [[1, 0]]})})),
        ]),
        "w6_a_connector_is_reset_by_its_cells_and_upserted_in_view": (
            "A connector reaching an entered cell is dropped unless sent again; one added in view is upserted.",
            (A,), [
            Step(entering(0, tuple(floor.values()), connectors=(connector(LADDER, ((0, 0), (1, 0))),)),
                 view(t, {}, (LADDER,))),
            Step(entering(1, (floor[(0, 0)],), statics=()), view(t)),
            Step(WorldUpdate(occurrence=2, connectors=(connector(ROPE_LINE, ((2, 0), (3, 0))),)), view(t, {}, (ROPE_LINE,))),
            Step(WorldUpdate(occurrence=3, connectors_removed=(ROPE_LINE,)), view(t)),
        ]),
        "w7_a_tile_reenters_with_its_current_values": (
            "A re-entering tile carries its current values without its static row; a tile replaced in view enters "
            "with its new static row.",
            (A,), [
            Step(entering(0, tuple(floor.values())), view(t)),
            Step(entering(1, (tile((1, 0), light=LightLevel.DIM_LIGHT),), statics=(),
                          tile_conditions=(TileConditions(position=(1, 0), names=("Difficult terrain",)),)),
                 view({**t, "1,0": tile_view(tile((1, 0), light=LightLevel.DIM_LIGHT),
                                             conditions=("Difficult terrain",))})),
            Step(WorldUpdate(occurrence=2, tile_changes=(TileFieldUpdate(position=(1, 0),
                     changes={"walking_cost": 2}),), resolved_light=values_from_items({(1, 0): 3})),
                 view({**t, "1,0": tile_view(tile((1, 0), light=LightLevel.DIM_LIGHT).model_copy(update={
                     "walking_cost": 2, "resolved_light": LightLevel.BRIGHT_LIGHT}),
                     conditions=("Difficult terrain",))})),
            Step(entering(3, (replaced,)), view({**t, "1,0": tile_view(replaced)})),
        ]),
        "w8_residues_are_keyed_by_cell_and_material": (
            "A new material arrives whole; a known one changes its amount and the contributions it set or appended; "
            "a removal takes it and its name away.",
            (A,), [
            Step(entering(0, tuple(floor.values())), view(t)),
            Step(WorldUpdate(occurrence=1, residue_materials=(BLOOD,), residues=(ResidueRow(position=(1, 0),
                     residue_id="residue.blood", condition_uuid=BLOOD_AT_1_0, amount=1,
                     contributions=(ContributionRow(index=0, contribution=SPLASH),)),)),
                 view({**t, "1,0": tile_view(floor[(1, 0)], conditions=("Blood",),
                                             residues={"residue.blood": {"amount": 1, "contributions": 1}})})),
            Step(WorldUpdate(occurrence=2, residues=(ResidueRow(position=(1, 0), residue_id="residue.blood", amount=3,
                     contributions=(ContributionRow(index=0, contribution=SPLASH.model_copy(update={"amount": 2})),
                                    ContributionRow(index=1, contribution=SPATTER))),)),
                 view({**t, "1,0": tile_view(floor[(1, 0)], conditions=("Blood",),
                                             residues={"residue.blood": {"amount": 3, "contributions": 2}})})),
            Step(WorldUpdate(occurrence=3, residues_removed=(ResidueKey(position=(1, 0), residue_id="residue.blood"),)),
                 view(t)),
        ]),
        "w9_contents_are_whole_on_grant_and_kept_when_it_is_lost": (
            "A container's contents arrive whole when the seat sees into it, change by item while it does, stay as "
            "last seen when it no longer does, and arrive whole again when it does.",
            (A,), [
            Step(entering(0, tuple(floor.values()), object_looks=(chest_look, potion_look), objects=(chest_row,),
                          contents=(ContainerContents(container_uuid=CHEST,
                              items=(ContainedItem(item_uuid=POTION, state=potion_state),)),)),
                 view(t, {str(CHEST): object_view(chest_at, name="Chest", is_open=True, contents=[str(POTION)])})),
            Step(WorldUpdate(occurrence=1, object_looks=(rope_look,), contents_changed=(ContentsChange(
                     container_uuid=CHEST, upserted=(ContainedItem(item_uuid=ROPE, state=rope_state),),
                     removed=(POTION,)),)),
                 view(t, {str(CHEST): object_view(chest_at, name="Chest", is_open=True, contents=[str(ROPE)])})),
            # The chest closes: the seat sees it close, its contents stay as last seen.
            Step(WorldUpdate(occurrence=2, objects=(look_and_row(replace(chest, is_open=False), None)[1],)),
                 view(t, {str(CHEST): object_view(chest_at, name="Chest", is_open=False, contents=[str(ROPE)])})),
            Step(WorldUpdate(occurrence=3, objects=(chest_row,), contents=(ContainerContents(container_uuid=CHEST,
                     items=(ContainedItem(item_uuid=POTION, state=potion_state),)),)),
                 view(t, {str(CHEST): object_view(chest_at, name="Chest", is_open=True, contents=[str(POTION)])})),
        ]),
        "w10_object_rows_name_their_members": (
            "A seat with several observers names the members observing each object in each of its rows, as of "
            "that row.",
            (A, B), [
            Step(entering(0, tuple(floor.values()), object_looks=(box_look,),
                          objects=(replace(box_at_1, members=0b01),)),
                 view(t, {str(BOX): object_view(box_at, members=1, name="Box")})),
            Step(WorldUpdate(occurrence=1, objects=(replace(box_at_1, members=0b11, placement=None),)),
                 view(t, {str(BOX): object_view(box_at, members=3, name="Box")})),
            Step(WorldUpdate(occurrence=2, objects=(replace(box_at_1, members=0b10, placement=None),)),
                 view(t, {str(BOX): object_view(box_at, members=2, name="Box")})),
        ]),
        "w12_tile_columns_carry_every_scalar": (
            "An entered tile's scalars travel as one byte per cell per column: the four costs, default and objective "
            "light, the flags (optics, propagation, surface kind, slope axis) and signed elevations; its surface "
            "and name are its static row.",
            (A,), [
            Step(entering(0, varied), view({f"{x},{y}": tile_view(row) for (x, y), row in
                                            ((row.position, row) for row in varied)})),
        ]),
        "w11_placements_and_structures_decode_exactly": (
            "A placement leaves out its object, its anchor tile when the client holds that cell's static row, its "
            "lone anchor support, its kind and its defaults; anything else travels. A boundary structure is a static "
            "row under its content id, once; a visual name equal to the name is left out.",
            (A,), [
            Step(entering(0, tuple(floor.values()), object_looks=tuple(look for look, _ in placed),
                          boundary_structures=(BoundaryStructureStatic(structure_id=structure_id(STONE_WALL_STRUCTURE),
                              structure=STONE_WALL_STRUCTURE),),
                          objects=tuple(row for _, row in sorted(placed, key=lambda pair: str(pair[1].item_uuid)))),
                 view(t, {str(CRATE): object_view(crate_at, name="Crate"),
                          str(CART): object_view(cart_at, name="Cart"),
                          str(SIGN): object_view(sign_at, name="Sign", visual="Sign"),
                          str(BANNER): object_view(banner_at, name="Banner"),
                          str(WALL): object_view(wall_at, name="Wall", structure=STONE_WALL_STRUCTURE),
                          str(EAST_WALL): object_view(east_wall_at, name="Wall", structure=STONE_WALL_STRUCTURE)})),
        ]),
    }


def documents() -> dict[str, str]:
    """Each vector file's text."""
    result = {}
    for name, (rule, observers, steps) in vectors().items():
        rows = [{"update": UPDATE.dump_python(step.update, mode="json"), "expected": step.expected} for step in steps]
        result[f"{name}.json"] = json.dumps({"name": name, "rule": rule,
            "observers": [str(observer) for observer in observers], "steps": rows}, indent=1) + "\n"
    return result


def main() -> None:
    argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter).parse_args()
    wanted = documents()
    DIRECTORY.mkdir(parents=True, exist_ok=True)
    for path in DIRECTORY.glob("*.json"):
        if path.name not in wanted:
            path.unlink()
    for name, text in wanted.items():
        (DIRECTORY / name).write_text(text)


if __name__ == "__main__":
    main()
