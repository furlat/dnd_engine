"""The schema-16 world codec shared by the server and the client: tile columns, a floor item's look and state,
and an object's placement.

The seat's entering cells send their tiles' changeable scalars as packed columns, one byte per cell per column
(`TileColumns`); a floor item travels as its look (once per uuid) and its state, its boundary structure as static
content under a digest of its value; a placement travels without what the client derives (`ObjectPlacement`); an
update's object rows travel as columns (`ObjectColumns`, field names once per update).
These are pure functions: the server packs and splits, the client unpacks and joins, and `join(split(x)) == x`.
"""

from collections.abc import Mapping, Sequence
from hashlib import sha256
from typing import TypeVar
from uuid import UUID

from dnd.core.cells import bit_rows, flag_bits, mask_from_positions, mask_positions
from dnd.core.item_types import ItemIntegrity
from dnd.core.world_edges import ElevationSurfaceKind, SlopeAxis
from dnd.player.facts import (Column, FloorItem, ObjectColumns, ObjectLook, ObjectPlacement, ObjectRow, ObjectState,
    PlacementColumns, TileColumns, TileLook, TileStatic)
from dnd.types.cells import NO_ROWS, no_rows
from dnd.types.materials import TileSurface
from dnd.types.event_facts import WorldTileState
from dnd.types.world import LightLevel
from dnd.types.world_placement import (BoundaryStructure, WorldObjectPlacement, WorldObjectSupport,
    WorldPlacementKind)

Value = TypeVar("Value")
SURFACE_KINDS = (ElevationSurfaceKind.ORDINARY, ElevationSurfaceKind.STAIRS, ElevationSurfaceKind.RAMP)
SLOPE_AXES = (None, SlopeAxis.NORTH_SOUTH, SlopeAxis.EAST_WEST)


def _byte(value: int, name: str) -> int:
    if not 0 <= value <= 255:
        raise ValueError(f"A tile's {name} {value} does not fit its one-byte column")
    return value


def pack_tile_columns(tiles: Mapping[tuple[int, int], WorldTileState]) -> TileColumns | None:
    """The tiles' changeable scalars as columns over their cells; None for no tile."""
    if not tiles:
        return None
    cells = mask_from_positions(tiles)
    rows = [tiles[position] for position in mask_positions(cells)]
    elevations = tuple(row.elevation_steps for row in rows)
    return TileColumns(cells=cells,
        walking_cost=bytes(_byte(row.walking_cost, "walking cost") for row in rows),
        flying_cost=bytes(_byte(row.flying_cost, "flying cost") for row in rows),
        swimming_cost=bytes(_byte(row.swimming_cost, "swimming cost") for row in rows),
        burrowing_cost=bytes(_byte(row.burrowing_cost, "burrowing cost") for row in rows),
        flags=bytes(int(row.blocks_optics) | int(row.blocks_propagation) << 1
            | SURFACE_KINDS.index(row.surface_kind) << 2 | SLOPE_AXES.index(row.slope_axis) << 4 for row in rows),
        default_light=bytes(row.default_light.value for row in rows),
        resolved_light=bytes(row.resolved_light.value for row in rows),
        elevation_steps=elevations if any(elevations) else ())


def tile_look_id(surface: TileSurface, name: str) -> str:
    """A tile look's content id: a digest of its surface and name."""
    return sha256(f"{surface.model_dump_json()}\n{name}".encode()).hexdigest()[:16]


def unpack_tile_columns(columns: TileColumns, statics: Mapping[tuple[int, int], TileStatic],
                        looks: Mapping[str, TileLook]) -> dict[tuple[int, int], WorldTileState]:
    """The tiles the columns describe, each joined with its cell's static row and that row's look; no conditions
    or residues yet."""
    positions = mask_positions(columns.cells)
    count = len(positions)
    if any(len(column) != count for column in (columns.walking_cost, columns.flying_cost, columns.swimming_cost,
            columns.burrowing_cost, columns.flags, columns.default_light, columns.resolved_light)) or (
            columns.elevation_steps and len(columns.elevation_steps) != count):
        raise ValueError("Tile columns hold one value per cell")
    tiles = {}
    for index, position in enumerate(positions):
        static = statics.get(position)
        if static is None:
            raise ValueError("An entered tile requires its static row")
        look = looks.get(static.look)
        if look is None:
            raise ValueError("A tile's static row requires its look")
        flags = columns.flags[index]
        tiles[position] = WorldTileState(tile_uuid=static.tile_uuid, position=position, surface=look.surface,
            name=look.name, blocks_optics=bool(flags & 1), blocks_propagation=bool(flags >> 1 & 1),
            walking_cost=columns.walking_cost[index], flying_cost=columns.flying_cost[index],
            swimming_cost=columns.swimming_cost[index], burrowing_cost=columns.burrowing_cost[index],
            elevation_steps=columns.elevation_steps[index] if columns.elevation_steps else 0,
            surface_kind=SURFACE_KINDS[flags >> 2 & 3], slope_axis=SLOPE_AXES[flags >> 4 & 3],
            default_light=LightLevel(columns.default_light[index]),
            resolved_light=LightLevel(columns.resolved_light[index]))
    return tiles


def structure_id(structure: BoundaryStructure) -> str:
    """A boundary structure's content id: a digest of its value."""
    return sha256(structure.model_dump_json().encode()).hexdigest()[:16]


def split_floor_item(item: FloorItem) -> tuple[ObjectLook, ObjectState]:
    """A floor item's fixed look and changeable state (its boundary structure by content id)."""
    return (ObjectLook(item_uuid=item.item_uuid, item_id=item.item_id, visual_variant_id=item.visual_variant_id, contact_passage=item.contact_passage,
            supported_by_uuid=item.supported_by_uuid, door_mechanism=item.door_mechanism, door_swing=item.door_swing,
            maximum_hit_points=item.maximum_hit_points, concentration_capacity=item.concentration_capacity,
            construction_owner_uuid=item.construction_owner_uuid, construction_geometry=item.construction_geometry,
            known_to_creator=item.known_to_creator),
        ObjectState(name=item.name,
            visual_item_name=item.visual_item_name if item.visual_item_name != item.name else None,
            map_char=item.map_char,
            boundary_structure=structure_id(item.boundary_structure) if item.boundary_structure is not None else None,
            is_open=item.is_open, is_lit=item.is_lit, very_bright_radius_feet=item.very_bright_radius_feet,
            bright_radius_feet=item.bright_radius_feet, dim_radius_feet=item.dim_radius_feet,
            stack_count=item.stack_count, is_pickable=item.is_pickable, item_effects=item.item_effects,
            blocks_propagation=item.blocks_propagation, is_engaged=item.is_engaged,
            surface_residues=item.surface_residues, current_hit_points=item.current_hit_points,
            concentration_slots=item.concentration_slots, remnant_state=item.remnant_state,
            integrity=item.integrity, destruction_outcome=item.destruction_outcome,
            construction_suppressions=item.construction_suppressions))


def join_floor_item(look: ObjectLook, state: ObjectState, structures: Mapping[str, BoundaryStructure]) -> FloorItem:
    """The floor item of a look and a state, its boundary structure from the static rows by content id."""
    structure = None
    if state.boundary_structure is not None:
        structure = structures.get(state.boundary_structure)
        if structure is None:
            raise ValueError("An object's boundary structure requires its static row")
    return FloorItem(item_uuid=look.item_uuid, item_id=look.item_id, name=state.name,
        visual_item_name=state.visual_item_name if state.visual_item_name is not None else state.name,
        visual_variant_id=look.visual_variant_id, map_char=state.map_char,
        boundary_structure=structure, is_open=state.is_open, is_lit=state.is_lit,
        very_bright_radius_feet=state.very_bright_radius_feet, bright_radius_feet=state.bright_radius_feet,
        dim_radius_feet=state.dim_radius_feet, stack_count=state.stack_count, is_pickable=state.is_pickable,
        item_effects=state.item_effects, blocks_propagation=state.blocks_propagation,
        contact_passage=look.contact_passage, supported_by_uuid=look.supported_by_uuid, is_engaged=state.is_engaged,
        surface_residues=state.surface_residues, current_hit_points=state.current_hit_points,
        maximum_hit_points=look.maximum_hit_points, concentration_capacity=look.concentration_capacity,
        concentration_slots=state.concentration_slots, door_mechanism=look.door_mechanism, door_swing=look.door_swing,
        remnant_state=state.remnant_state, integrity=state.integrity, destruction_outcome=state.destruction_outcome,
        construction_owner_uuid=look.construction_owner_uuid, construction_geometry=look.construction_geometry,
        construction_suppressions=state.construction_suppressions, known_to_creator=look.known_to_creator)


def pack_placement(placement: WorldObjectPlacement, held_anchor: UUID | None) -> ObjectPlacement:
    """A placement without what the client derives. `held_anchor`: the tile uuid of the client's static row at
    the anchor cell, when the server knows it (the anchor's current tile, sent to the seat), else None."""
    anchor = WorldObjectSupport(position=placement.position, tile_uuid=placement.tile_uuid)
    return ObjectPlacement(position=placement.position, top_height_steps=placement.top_height_steps,
        boundary_direction=placement.boundary_direction,
        tile_uuid=None if placement.tile_uuid == held_anchor else placement.tile_uuid,
        covered_supports=() if placement.covered_supports == (anchor,) else placement.covered_supports,
        occupies_bands=placement.occupies_bands, base_height_steps=placement.base_height_steps,
        orientation=placement.orientation, removed_bands=placement.removed_bands)


def unpack_placement(identity: UUID, row: ObjectPlacement, statics: Mapping[tuple[int, int], TileStatic]
                     ) -> WorldObjectPlacement:
    """The placement of the object `identity` from its wire row and the client's static tile rows."""
    tile_uuid = row.tile_uuid
    if tile_uuid is None:
        static = statics.get(row.position)
        if static is None:
            raise ValueError("A placement without its tile uuid requires the static row of its anchor cell")
        tile_uuid = static.tile_uuid
    return WorldObjectPlacement(object_uuid=identity, tile_uuid=tile_uuid, position=row.position,
        kind=WorldPlacementKind.CENTER if row.boundary_direction is None else WorldPlacementKind.BOUNDARY,
        occupies_bands=row.occupies_bands, boundary_direction=row.boundary_direction,
        base_height_steps=row.base_height_steps, top_height_steps=row.top_height_steps, orientation=row.orientation,
        covered_supports=row.covered_supports or (WorldObjectSupport(position=row.position, tile_uuid=tile_uuid),),
        removed_bands=row.removed_bands)


def _column(cells: Sequence[tuple[int, Value]], count: int) -> Column[Value] | None:
    """The column of a group of `count` rows holding these (row, value) pairs; None when it holds none."""
    if not cells:
        return None
    if len(cells) == count:
        return Column(values=tuple(value for _, value in cells))
    flags = [False] * count
    for row, _ in cells:
        flags[row] = True
    return Column(rows=flag_bits(flags), values=tuple(value for _, value in cells))


def _held(column: Column[Value] | None, count: int) -> dict[int, Value]:
    """A column's values by row (a row it skips holds the field's default)."""
    if column is None:
        return {}
    rows = list(range(count)) if no_rows(column.rows) else [int(row) for row in bit_rows(column.rows, count)]
    if len(rows) != len(column.values) or not column.values:
        raise ValueError("A column holds one value per row it selects, and at least one")
    return dict(zip(rows, column.values))


def pack_object_rows(rows: Sequence[ObjectRow]) -> ObjectColumns | None:
    """An update's object rows as columns; None for no row."""
    count = len(rows)
    if not count:
        return None
    states = [row.state for row in rows]
    placed = [(index, row.placement) for index, row in enumerate(rows) if row.placement is not None]
    placements = None
    if placed:
        flags = [row.placement is not None for row in rows]
        at = [placement for _, placement in placed]
        size = len(at)
        placements = PlacementColumns(rows=NO_ROWS if size == count else flag_bits(flags),
            position=tuple(row.position for row in at), top_height_steps=tuple(row.top_height_steps for row in at),
            boundary_direction=_column([(i, row.boundary_direction) for i, row in enumerate(at)
                if row.boundary_direction is not None], size),
            tile_uuid=_column([(i, row.tile_uuid) for i, row in enumerate(at) if row.tile_uuid is not None], size),
            covered_supports=_column([(i, row.covered_supports) for i, row in enumerate(at) if row.covered_supports],
                size),
            occupies_bands=_column([(i, False) for i, row in enumerate(at) if not row.occupies_bands], size),
            base_height_steps=_column([(i, row.base_height_steps) for i, row in enumerate(at)
                if row.base_height_steps != 0], size),
            orientation=_column([(i, row.orientation) for i, row in enumerate(at) if row.orientation is not None],
                size),
            removed_bands=_column([(i, row.removed_bands) for i, row in enumerate(at) if row.removed_bands], size))
    return ObjectColumns(item_uuids=tuple(row.item_uuid for row in rows),
        members=_column([(i, row.members) for i, row in enumerate(rows) if row.members is not None], count),
        observed_faces=_column([(i, row.observed_faces) for i, row in enumerate(rows) if row.observed_faces], count),
        name=tuple(state.name for state in states),
        visual_item_name=_column([(i, state.visual_item_name) for i, state in enumerate(states)
            if state.visual_item_name is not None], count),
        map_char=tuple(state.map_char for state in states),
        boundary_structure=_column([(i, state.boundary_structure) for i, state in enumerate(states)
            if state.boundary_structure is not None], count),
        is_open=_column([(i, state.is_open) for i, state in enumerate(states) if state.is_open is not None], count),
        is_lit=_column([(i, state.is_lit) for i, state in enumerate(states) if state.is_lit is not None], count),
        very_bright_radius_feet=_column([(i, state.very_bright_radius_feet) for i, state in enumerate(states)
            if state.very_bright_radius_feet is not None], count),
        bright_radius_feet=_column([(i, state.bright_radius_feet) for i, state in enumerate(states)
            if state.bright_radius_feet is not None], count),
        dim_radius_feet=_column([(i, state.dim_radius_feet) for i, state in enumerate(states)
            if state.dim_radius_feet is not None], count),
        stack_count=_column([(i, state.stack_count) for i, state in enumerate(states) if state.stack_count != 1],
            count),
        is_pickable=_column([(i, False) for i, state in enumerate(states) if not state.is_pickable], count),
        item_effects=_column([(i, state.item_effects) for i, state in enumerate(states) if state.item_effects],
            count),
        blocks_propagation=_column([(i, True) for i, state in enumerate(states) if state.blocks_propagation],
            count),
        is_engaged=_column([(i, state.is_engaged) for i, state in enumerate(states) if state.is_engaged is not None],
            count),
        surface_residues=_column([(i, state.surface_residues) for i, state in enumerate(states)
            if state.surface_residues], count),
        current_hit_points=_column([(i, state.current_hit_points) for i, state in enumerate(states)
            if state.current_hit_points is not None], count),
        concentration_slots=_column([(i, state.concentration_slots) for i, state in enumerate(states)
            if state.concentration_slots], count),
        remnant_state=_column([(i, state.remnant_state) for i, state in enumerate(states)
            if state.remnant_state is not None], count),
        integrity=_column([(i, state.integrity) for i, state in enumerate(states)
            if state.integrity is not ItemIntegrity.INTACT], count),
        destruction_outcome=_column([(i, state.destruction_outcome) for i, state in enumerate(states)
            if state.destruction_outcome is not None], count),
        construction_suppressions=_column([(i, state.construction_suppressions) for i, state in enumerate(states)
            if state.construction_suppressions], count),
        placements=placements)


def unpack_object_rows(columns: ObjectColumns | None) -> tuple[ObjectRow, ...]:
    """An update's object rows from their columns, in row order."""
    if columns is None:
        return ()
    count = len(columns.item_uuids)
    if len(columns.name) != count or len(columns.map_char) != count:
        raise ValueError("A dense object column holds one value per row")
    placed: dict[int, ObjectPlacement] = {}
    if columns.placements is not None:
        at = columns.placements
        rows = list(range(count)) if no_rows(at.rows) else [int(row) for row in bit_rows(at.rows, count)]
        size = len(rows)
        if len(at.position) != size or len(at.top_height_steps) != size:
            raise ValueError("A dense placement column holds one value per placed row")
        direction, tile, supports = (_held(at.boundary_direction, size), _held(at.tile_uuid, size),
                                     _held(at.covered_supports, size))
        bands, base, orientation, removed = (_held(at.occupies_bands, size), _held(at.base_height_steps, size),
                                             _held(at.orientation, size), _held(at.removed_bands, size))
        for index, row in enumerate(rows):
            placed[row] = ObjectPlacement(position=at.position[index], top_height_steps=at.top_height_steps[index],
                boundary_direction=direction.get(index), tile_uuid=tile.get(index),
                covered_supports=supports.get(index, ()), occupies_bands=bands.get(index, True),
                base_height_steps=base.get(index, 0), orientation=orientation.get(index),
                removed_bands=removed.get(index, ()))
    members, faces = _held(columns.members, count), _held(columns.observed_faces, count)
    visual, structure = _held(columns.visual_item_name, count), _held(columns.boundary_structure, count)
    is_open, is_lit = _held(columns.is_open, count), _held(columns.is_lit, count)
    very_bright, bright, dim = (_held(columns.very_bright_radius_feet, count), _held(columns.bright_radius_feet, count),
                                _held(columns.dim_radius_feet, count))
    stack, pickable, effects = (_held(columns.stack_count, count), _held(columns.is_pickable, count),
                                _held(columns.item_effects, count))
    propagation, engaged, residues = (_held(columns.blocks_propagation, count), _held(columns.is_engaged, count),
                                      _held(columns.surface_residues, count))
    hit_points, slots, remnant = (_held(columns.current_hit_points, count), _held(columns.concentration_slots, count),
                                  _held(columns.remnant_state, count))
    integrity, outcome, suppressions = (_held(columns.integrity, count), _held(columns.destruction_outcome, count),
                                        _held(columns.construction_suppressions, count))
    return tuple(ObjectRow(item_uuid=identity, members=members.get(index), observed_faces=faces.get(index, ()),
        placement=placed.get(index), state=ObjectState(name=columns.name[index], visual_item_name=visual.get(index),
            map_char=columns.map_char[index], boundary_structure=structure.get(index), is_open=is_open.get(index),
            is_lit=is_lit.get(index), very_bright_radius_feet=very_bright.get(index),
            bright_radius_feet=bright.get(index), dim_radius_feet=dim.get(index), stack_count=stack.get(index, 1),
            is_pickable=pickable.get(index, True), item_effects=effects.get(index, ()),
            blocks_propagation=propagation.get(index, False), is_engaged=engaged.get(index),
            surface_residues=residues.get(index, ()), current_hit_points=hit_points.get(index),
            concentration_slots=slots.get(index, ()), remnant_state=remnant.get(index),
            integrity=integrity.get(index, ItemIntegrity.INTACT), destruction_outcome=outcome.get(index),
            construction_suppressions=suppressions.get(index, ())))
        for index, identity in enumerate(columns.item_uuids))
