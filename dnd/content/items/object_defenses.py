"""Native material defaults for attackable objects, independent of their art."""

from types import MappingProxyType

from dnd.types.materials import Material


OBJECT_ARMOR_CLASS_BY_MATERIAL = MappingProxyType({
    Material.EARTH: 10,
    Material.SAND: 10,
    Material.WATER: 10,
    Material.FABRIC: 11,
    Material.VEGETATION: 11,
    Material.GLASS: 13,
    Material.ICE: 13,
    Material.WOOD: 15,
    Material.STONE: 17,
    Material.METAL: 19,
})
