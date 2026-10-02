"""Fixed windows composed of ordinary items and a state-checked passage."""

from dataclasses import dataclass
from uuid import UUID, uuid4

from dnd.blocks.base_item import BaseItem, WorldItem
from dnd.content.items.window_definitions import WINDOW_DEFINITIONS, WindowDefinition
from dnd.content.items.object_defenses import OBJECT_ARMOR_CLASS_BY_MATERIAL
from dnd.core.gridmap import get_map
from dnd.core.item_types import ItemDestructionProfile, ItemIntegrity
from dnd.core.traversal_connectors import (
    ApertureTraversal, ConnectorProvocationPolicy, TraversalConnectorDefinition,
    TraversalConnectorKind,
)
from dnd.types.physical_access import ContactPassage
from dnd.types.world import CardinalDirection, WorldEdgeChannel
from dnd.types.world_placement import BoundaryStructure, BoundaryStructureKind, WorldPlacementKind, WorldPlacementSpec


def build_window_component(
    family: str, *, insert: bool = False, source_entity_uuid: UUID,
    supported_by_uuid: UUID | None = None, destroyed: bool = False,
) -> WorldItem:
    profile = WINDOW_DEFINITIONS[family]
    definition = profile.insert if insert else profile.wall
    if definition is None:
        raise ValueError(f"{family} has no insert")
    material = profile.insert_material if insert else profile.wall_material
    armor_class = profile.insert_armor_class if insert else profile.wall_armor_class
    channels = (tuple(WorldEdgeChannel) if insert and profile.insert_blocks_optics
                else (WorldEdgeChannel.MOVEMENT,))
    return WorldItem(
        source_entity_uuid=source_entity_uuid, supported_by_uuid=supported_by_uuid,
        item_id=definition.item_id, name=definition.name, description=definition.description,
        tags=list(definition.tags), is_pickable=False, is_targetable=True,
        include_in_adjacent_senses_objects=True,
        armor_class=(armor_class if armor_class is not None
                     else OBJECT_ARMOR_CLASS_BY_MATERIAL[material]),
        health=BaseItem.create_item_health(source_entity_uuid,
            profile.insert_hit_points if insert else profile.wall_hit_points),
        world_placement_spec=WorldPlacementSpec(kind=WorldPlacementKind.BOUNDARY,
            occupies_bands=not insert, vertical_extent_steps=profile.height_steps),
        boundary_structure=BoundaryStructure(structure=BoundaryStructureKind.WALL,
            material=material, blocked_channels=channels,
            contact_passage=ContactPassage.BLOCKED if insert else ContactPassage.HAND_AND_LIGHT_WEAPONS),
        destruction_profile=ItemDestructionProfile(
            name=f"Broken {definition.name.lower()}",
            description="Broken fragments remain without obstructing the passage.",
            placement_spec=WorldPlacementSpec(kind=WorldPlacementKind.BOUNDARY,
                occupies_bands=False, vertical_extent_steps=1),
            boundary_structure=BoundaryStructure(structure=BoundaryStructureKind.WALL,
                material=material, blocked_channels=(), contact_passage=ContactPassage.CLEAR)),
        integrity=ItemIntegrity.DESTROYED if destroyed else ItemIntegrity.INTACT,
    )


@dataclass(frozen=True, slots=True)
class WindowAssembly:
    wall: WorldItem
    insert: WorldItem | None


def place_window(
    family: str, position: tuple[int, int], direction: CardinalDirection, *,
    source_entity_uuid: UUID | None = None, wall_destroyed: bool = False,
    insert_destroyed: bool = False,
) -> WindowAssembly:
    """Compose one authored assembly; failed placement leaves no live fragment."""
    profile: WindowDefinition = WINDOW_DEFINITIONS[family]
    source_uuid = source_entity_uuid or uuid4()
    wall = build_window_component(family, source_entity_uuid=source_uuid, destroyed=wall_destroyed)
    insert = (build_window_component(family, insert=True, source_entity_uuid=source_uuid,
        supported_by_uuid=wall.uuid, destroyed=wall_destroyed or insert_destroyed)
        if profile.insert is not None else None)
    dx, dy = {CardinalDirection.NORTH: (0, 1), CardinalDirection.SOUTH: (0, -1),
              CardinalDirection.EAST: (1, 0), CardinalDirection.WEST: (-1, 0)}[direction]
    destination = (position[0] + dx, position[1] + dy)
    grid = get_map()
    try:
        # A window always connects two supports, even while its insert blocks crossing.
        if grid.get_tile(*destination) is None:
            raise ValueError("window requires a support on each side")
        connector = None if wall_destroyed else TraversalConnectorDefinition(
            authored_id=f"connector.window.{wall.uuid.hex}", kind=TraversalConnectorKind.PASSAGE,
            presentation_key="window", endpoint_positions=(position, destination),
            movement_cost_feet=0, aperture=ApertureTraversal(
                frame_uuid=wall.uuid, maximum_size=profile.maximum_size),
            bidirectional=True, enabled=True,
            provocation_policy=ConnectorProvocationPolicy.PROVOKES_SOURCE_EXIT)
        components = (wall,) if insert is None else (wall, insert)
        placements = grid.place_object_assembly(tuple(item.uuid for item in components), position,
            direction, connector_definition=connector)
        for item, placement in zip(components, placements, strict=True):
            item.synchronize_floor_placement(placement)
        return WindowAssembly(wall, insert)
    except Exception:
        wall.retire()
        raise
