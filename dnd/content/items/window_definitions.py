"""Fixed window identities and coarse physical profiles, independent of artwork."""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from dnd.content.items.authored_item_definitions import AuthoredItemDefinition
from dnd.core.creature_types import Size
from dnd.types.materials import Material


@dataclass(frozen=True, slots=True)
class WindowDefinition:
    """One family with a parent wall and an optional, separate insert target."""

    wall: AuthoredItemDefinition
    insert: AuthoredItemDefinition | None
    wall_material: Material = Material.STONE
    wall_hit_points: int = 27
    insert_material: Material = Material.WOOD
    insert_hit_points: int = 12
    insert_blocks_optics: bool = False
    maximum_size: Size = Size.MEDIUM
    height_steps: int = 2
    wall_armor_class: int | None = None
    insert_armor_class: int | None = None


def _grilled_window(code: str, *, material: Material = Material.STONE, maximum_size: Size = Size.MEDIUM) -> WindowDefinition:
    return WindowDefinition(
        wall_material=material, wall_hit_points=18 if material is Material.WOOD else 27,
        maximum_size=maximum_size, insert_material=Material.METAL if code in ("a4", "a5") else Material.WOOD,
        wall=AuthoredItemDefinition(
            item_id=f"environment.window.fantasy_{code}.wall",
            name=f"Window wall {code.upper()}",
            description="A wall surrounding a window opening, with its frame and sill.",
            tags=("environment", "window_frame"),
        ),
        insert=AuthoredItemDefinition(
            item_id=f"environment.window.fantasy_{code}.insert",
            name=f"Window grille {code.upper()}",
            description="A fixed grille in the opening, separate from the surrounding wall.",
            tags=("environment", "window_insert", "fixed_grille"),
        ),
    )


WINDOW_DEFINITIONS: Mapping[str, WindowDefinition] = MappingProxyType({
    "environment.window.fantasy_a4": _grilled_window("a4", maximum_size=Size.SMALL),
    "environment.window.fantasy_a5": _grilled_window("a5", maximum_size=Size.SMALL),
    "environment.window.fantasy_c4": _grilled_window("c4", material=Material.WOOD),
    "environment.window.fantasy_d16": _grilled_window("d16"),
    "environment.window.fantasy_d7": _grilled_window("d7"),
    "environment.window.fantasy_f16": _grilled_window("f16"),
    "environment.window.fantasy_f7": _grilled_window("f7"),
    "environment.window.fantasy_g7": WindowDefinition(
        wall=AuthoredItemDefinition(
            item_id="environment.window.fantasy_g7.wall",
            name="Empty window wall G7",
            description="A wall with an empty window opening; no insert fills the aperture.",
            tags=("environment", "window_frame", "empty_aperture"),
        ),
        insert=None, wall_material=Material.WOOD, wall_hit_points=18,
    ),
    "environment.window.fantasy_g8": _grilled_window("g8", material=Material.WOOD),
    "environment.window.fantasy_g9": WindowDefinition(
        wall_material=Material.WOOD, wall_hit_points=18, insert_blocks_optics=True,
        wall=AuthoredItemDefinition(
            item_id="environment.window.fantasy_g9.wall",
            name="Shuttered window wall G9",
            description="A wall surrounding a shuttered window, with its frame and sill.",
            tags=("environment", "window_frame"),
        ),
        insert=AuthoredItemDefinition(
            item_id="environment.window.fantasy_g9.insert",
            name="Window shutter G9",
            description="A fixed wooden shutter filling the opening, separate from the wall.",
            tags=("environment", "window_insert", "shutter"),
        ),
    ),
})
