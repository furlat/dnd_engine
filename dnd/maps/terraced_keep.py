"""Courtyard and enclosed raised keep, authored with native terrain and objects.

All elevated ground has a complete lower apron. The sole stair flight is cut
into the terrace, between solid banks, rather than attached to a floating slab.
"""

from dnd.blocks.base_item import BaseItem
from dnd.content.items.environment_item_builders import build_authored_door, build_directional_wall
from dnd.content.items.world_prop_builders import build_world_prop
from dnd.core.base_block import LightLevel
from dnd.core.gridmap import GridMap
from dnd.core.world_edges import ElevationSurfaceKind, SlopeAxis
from dnd.types.materials import Material, TileSurface
from dnd.types.world import CardinalDirection


def build_terraced_keep(grid: GridMap) -> tuple[BaseItem, ...]:
    """Populate an empty native map; return its placed architectural objects."""
    if grid.get_all_tiles():
        raise ValueError("Terraced keep requires an empty map")
    stairs = {(9, 5): 0, (9, 6): 1, (9, 7): 2}
    for x in range(16):
        for y in range(16):
            p = (x, y)
            terrace = 7 <= x <= 13 and 5 <= y <= 12
            room = (2 <= x <= 5 and 3 <= y <= 6) or (9 <= x <= 12 and 9 <= y <= 11)
            material = Material.EARTH if p in stairs else Material.WOOD if terrace else Material.STONE
            grid.set_tile(x, y, name="Stair" if p in stairs else "Keep floor" if room else "Courtyard",
                surface=TileSurface(base_material=material), height=stairs.get(p, 2 if terrace else 0),
                elevation_surface_kind=ElevationSurfaceKind.STAIRS if p in stairs else ElevationSurfaceKind.ORDINARY,
                slope_axis=SlopeAxis.NORTH_SOUTH if p in stairs else None,
                default_light=LightLevel.BRIGHT_LIGHT, fire_event=False)

    objects: list[BaseItem] = []

    def enclosure(bounds: tuple[int, int, int, int], door_at: tuple[int, int], door_side: CardinalDirection) -> None:
        x0, y0, x1, y1 = bounds
        edges = [*(( (x, y0), CardinalDirection.SOUTH) for x in range(x0, x1 + 1)),
                 *(( (x, y1), CardinalDirection.NORTH) for x in range(x0, x1 + 1)),
                 *(( (x0, y), CardinalDirection.WEST) for y in range(y0, y1 + 1)),
                 *(( (x1, y), CardinalDirection.EAST) for y in range(y0, y1 + 1))]
        for p, side in edges:
            item = (build_authored_door("environment.door.indoor_door_elegant")
                    if (p, side) == (door_at, door_side)
                    else build_directional_wall(display_name="Keep masonry", material=Material.STONE))
            item.place_on_grid(p, boundary_direction=side)
            objects.append(item)

    enclosure((1, 1, 14, 14), (4, 1), CardinalDirection.SOUTH)
    enclosure((2, 3, 5, 6), (5, 4), CardinalDirection.EAST)
    enclosure((9, 9, 12, 11), (10, 9), CardinalDirection.SOUTH)
    for item_id, p, direction in (
        ("environment.furniture.table", (3, 5), CardinalDirection.NORTH),
        ("environment.furniture.bookshelf", (11, 11), CardinalDirection.NORTH),
        ("environment.furniture.writing_desk", (11, 10), CardinalDirection.NORTH),
        ("environment.furniture.sack_bundles", (3, 9), CardinalDirection.EAST),
    ):
        item = build_world_prop(item_id)
        item.place_on_grid(p, orientation=direction)
        objects.append(item)
    return tuple(objects)
