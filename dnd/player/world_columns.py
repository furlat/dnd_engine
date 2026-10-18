"""The schema-16 world codec shared by the server and the client: tile columns, and a floor item's look and state.

The seat's entering cells send their tiles' changeable scalars as packed columns, one byte per cell per column
(`TileColumns`); a floor item travels as its look (once per uuid) and its state. These are pure functions: the
server packs and splits, the client unpacks and joins, and `join(split(x)) == x`.
"""

from collections.abc import Mapping

from dnd.core.cells import mask_from_positions, mask_positions
from dnd.core.world_edges import ElevationSurfaceKind, SlopeAxis
from dnd.player.facts import FloorItem
from dnd.player.world_wire import ObjectLook, ObjectState, TileColumns, TileStatic
from dnd.types.event_facts import WorldTileState
from dnd.types.world import LightLevel

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


def unpack_tile_columns(columns: TileColumns, statics: Mapping[tuple[int, int], TileStatic]
                        ) -> dict[tuple[int, int], WorldTileState]:
    """The tiles the columns describe, each joined with its cell's static row; no conditions or residues yet."""
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
        flags = columns.flags[index]
        tiles[position] = WorldTileState(tile_uuid=static.tile_uuid, position=position, surface=static.surface,
            name=static.name, blocks_optics=bool(flags & 1), blocks_propagation=bool(flags >> 1 & 1),
            walking_cost=columns.walking_cost[index], flying_cost=columns.flying_cost[index],
            swimming_cost=columns.swimming_cost[index], burrowing_cost=columns.burrowing_cost[index],
            elevation_steps=columns.elevation_steps[index] if columns.elevation_steps else 0,
            surface_kind=SURFACE_KINDS[flags >> 2 & 3], slope_axis=SLOPE_AXES[flags >> 4 & 3],
            default_light=LightLevel(columns.default_light[index]),
            resolved_light=LightLevel(columns.resolved_light[index]))
    return tiles


def split_floor_item(item: FloorItem) -> tuple[ObjectLook, ObjectState]:
    """A floor item's fixed look and changeable state."""
    return (ObjectLook(item_uuid=item.item_uuid, item_id=item.item_id, visual_variant_id=item.visual_variant_id, contact_passage=item.contact_passage,
            supported_by_uuid=item.supported_by_uuid, door_mechanism=item.door_mechanism, door_swing=item.door_swing,
            maximum_hit_points=item.maximum_hit_points, concentration_capacity=item.concentration_capacity,
            construction_owner_uuid=item.construction_owner_uuid, construction_geometry=item.construction_geometry,
            known_to_creator=item.known_to_creator),
        ObjectState(name=item.name, visual_item_name=item.visual_item_name, map_char=item.map_char, boundary_structure=item.boundary_structure,
            is_open=item.is_open, is_lit=item.is_lit, very_bright_radius_feet=item.very_bright_radius_feet,
            bright_radius_feet=item.bright_radius_feet, dim_radius_feet=item.dim_radius_feet,
            stack_count=item.stack_count, is_pickable=item.is_pickable, item_effects=item.item_effects,
            blocks_propagation=item.blocks_propagation, is_engaged=item.is_engaged,
            surface_residues=item.surface_residues, current_hit_points=item.current_hit_points,
            concentration_slots=item.concentration_slots, remnant_state=item.remnant_state,
            integrity=item.integrity, destruction_outcome=item.destruction_outcome,
            construction_suppressions=item.construction_suppressions))


def join_floor_item(look: ObjectLook, state: ObjectState) -> FloorItem:
    """The floor item of a look and a state."""
    return FloorItem(item_uuid=look.item_uuid, item_id=look.item_id, name=state.name,
        visual_item_name=state.visual_item_name, visual_variant_id=look.visual_variant_id, map_char=state.map_char,
        boundary_structure=state.boundary_structure, is_open=state.is_open, is_lit=state.is_lit,
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
