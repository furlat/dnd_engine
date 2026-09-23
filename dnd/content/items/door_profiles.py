"""Authored door families; physical composition is independent of their media."""

from dataclasses import dataclass
from types import MappingProxyType

from dnd.core.item_types import DoorMechanism
from dnd.types.materials import Material
from dnd.types.world import WorldEdgeChannel


@dataclass(frozen=True, slots=True)
class DoorProfile:
    name: str
    material: Material
    mechanism: DoorMechanism
    hit_points: int
    supports_jammed_remnant: bool = True
    vertical_extent_steps: int = 2
    closed_channels: tuple[WorldEdgeChannel, ...] = tuple(WorldEdgeChannel)


DOOR_PROFILES = MappingProxyType({
    **{f"environment.door.{pack}_a1": DoorProfile(
        f"{pack.title()} double door", Material.WOOD, DoorMechanism.DOUBLE_HINGED, 18)
        for pack in ("fantasy", "desert")},
    **{f"environment.door.{pack}_c{index}": DoorProfile(
        f"{pack.title()} iron lift gate {index}", Material.METAL, DoorMechanism.LIFT, 27,
        closed_channels=(WorldEdgeChannel.MOVEMENT,))
        for pack in ("fantasy", "desert") for index in (1, 3, 5)},
    **{f"environment.door.desert_c{index}": DoorProfile(
        f"Desert wooden door {index}", Material.WOOD, DoorMechanism.SINGLE_HINGED, 18)
        for index in (7, 9)},
    **{f"environment.door.indoor_door_{style}": DoorProfile(
        f"{style.replace('_', ' ').title()} indoor door", Material.WOOD,
        DoorMechanism.SINGLE_HINGED, 18, supports_jammed_remnant=False)
        for style in ("shabby", "shabby_plain", "shabby_battens", "shabby_patched",
                      "elegant", "elegant_three_panel")},
})
