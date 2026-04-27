"""Mapeditor support functions.

This module keeps the experimental map editor API grounded in the existing
GridMap, Tile, BaseItem, and light-source contracts. It intentionally avoids
combat entities and subjective visibility.
"""

import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from uuid import UUID, uuid4

from dnd.blocks.base_item import BaseItem, UsableItem
from dnd.core.base_block import BaseBlock, LightLevel
from dnd.core.base_tiles import Tile, difficult_terrain_factory
from dnd.core.events import EventQueue
from dnd.core.gridmap import get_map, reset_map
from dnd.controller import Controller
from dnd.encounter import Encounter
from dnd.entity import Entity
from dnd.items import ARMORS, SHIELDS, WEAPONS
from dnd.items.test_items import (
    CookAction,
    PullLeverAction,
    RestAction,
    StorageChest,
    TestDoorA,
    TrapLever,
    create_acid_flask,
    create_arcane_device,
    create_arcane_machine_gun,
    create_fireball_cannon,
    create_healing_potion,
    create_potion_of_greater_invisibility,
    create_potion_of_haste,
    create_scroll_of_fire_bolt,
    create_scroll_of_fireball,
    create_scroll_of_hold_person,
    create_scroll_of_invisibility,
    create_scroll_of_mage_armor,
    create_scroll_of_magic_missile,
    create_scroll_of_spike_growth,
    create_torch,
    create_wall_torch,
    create_wand_of_fire,
    create_wand_of_magic_missiles,
    create_weapon_coat,
)
from dnd.tiles import create_spike_zone
from server.api_models import (
    APIFloorObject,
    APIGrid,
    MapEditorCatalog,
    MapEditorCatalogEntry,
    MapEditorCreateMapRequest,
    MapEditorGridBounds,
    MapEditorLightCell,
    MapEditorLightResponse,
    MapEditorMapSnapshot,
    MapEditorObjectDeleteRequest,
    MapEditorObjectPlaceRequest,
    MapEditorSaveMapRequest,
    MapEditorSavedMapDocument,
    MapEditorSavedMapList,
    MapEditorSavedMapMetadata,
    MapEditorSavedObjectPlacement,
    MapEditorTilePatch,
    MapEditorVisibilityCell,
    MapEditorVisibilityResponse,
    MapEditorWalkabilityCell,
    MapEditorWalkabilityResponse,
)
from server.event_stream import event_stream
from server.session import SessionManager


_BASE_BLOCK_FIELDS = set(BaseBlock.model_fields.keys()) | {
    "use_register",
    "blocks_dict_name_uuid",
    "blocks_dict_uuid_name",
    "values_dict_name_uuid",
    "values_dict_uuid_name",
}
_ALREADY_SERIALIZED = {"uuid", "name", "map_char"}
_SAVE_SCHEMA_VERSION = 1


def reset_editor_world() -> None:
    """Reset spatial/combat registries for an entity-free editor map."""
    reset_map()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()
    Encounter.clear_registry()
    Controller._controller_registry.clear()
    SessionManager.reset()
    EventQueue.reset()
    event_stream.ensure_attached()


def create_editor_map(request: MapEditorCreateMapRequest) -> MapEditorMapSnapshot:
    """Create an editor map from scratch or a named preset."""
    if request.include_entities:
        raise ValueError("mapeditor maps do not include entities")

    reset_editor_world()
    if request.source == "preset":
        preset_id = request.preset_id or "forgotten_crypt_arena"
        if preset_id != "forgotten_crypt_arena":
            raise ValueError(f"unknown mapeditor preset: {preset_id}")
        build_forgotten_crypt_arena_map()
    else:
        build_scratch_map(request)
    return get_editor_snapshot()


def build_scratch_map(request: MapEditorCreateMapRequest) -> None:
    """Build a simple rectangular editor map."""
    grid = get_map()
    x0, y0 = request.origin
    walkable, visible, name = _tile_properties(request.default_tile)
    grid.create_rectangle(x0, y0, request.width, request.height, walkable=walkable, visible=visible, name=name)
    for x in range(x0, x0 + request.width):
        for y in range(y0, y0 + request.height):
            tile = grid.get_tile(x, y)
            if tile is not None:
                tile.default_light = _light_level(request.default_light)


def build_forgotten_crypt_arena_map() -> None:
    """Build the current crypt arena environment without combat entities."""
    grid = get_map()
    grid.create_rectangle(0, 0, 15, 15)

    for y in range(3, 12):
        if y != 7:
            grid.set_tile(7, y, walkable=False, visible=False, name="Wall")

    door = TestDoorA(source_entity_uuid=uuid4())
    grid.place_object(door.uuid, (7, 7))

    for y in range(4):
        grid.set_tile(2, y, walkable=False, visible=True, name="Water")
    for x in range(2):
        grid.set_tile(x, 3, walkable=False, visible=True, name="Water")

    spike_positions = {(x, y) for x in range(5) for y in range(11, 15)}
    spike_tiles, spike_handler = create_spike_zone(spike_positions)
    for tile in spike_tiles:
        grid.set_tile(tile.position[0], tile.position[1], tile=tile, fire_event=False)

    for x in range(6, 9):
        for y in range(0, 3):
            tile = difficult_terrain_factory((x, y))
            grid.set_tile(x, y, tile=tile, fire_event=False)
    for x in range(6, 9):
        for y in range(12, 15):
            tile = difficult_terrain_factory((x, y))
            grid.set_tile(x, y, tile=tile, fire_event=False)

    for x in range(0, 15):
        for y in range(0, 15):
            tile = grid.get_tile(x, y)
            if tile is not None:
                tile.default_light = LightLevel.DARKNESS

    create_wall_torch(position=(14, 1), owner_uuid=uuid4(), lit=True)
    create_wall_torch(position=(14, 13), owner_uuid=uuid4(), lit=True)

    for pot_pos in [(1, 12), (3, 13)]:
        potion = create_healing_potion(uuid4(), heal_amount=10)
        potion.place_on_grid(pot_pos)

    lever_action = PullLeverAction(source_entity_uuid=uuid4(), trap_handler_uuid=spike_handler.uuid, template=True)
    lever = TrapLever(source_entity_uuid=uuid4(), use_action_templates=[lever_action], charges=1)
    lever.place_on_grid((5, 12))


def get_editor_snapshot() -> MapEditorMapSnapshot:
    """Serialize current GridMap as an entity-free editor snapshot."""
    grid = get_map()
    bounds = grid.bounds
    api_grid = APIGrid.create(grid)
    return MapEditorMapSnapshot(
        grid_bounds=MapEditorGridBounds(min_x=bounds[0], min_y=bounds[1], max_x=bounds[2], max_y=bounds[3]),
        tiles=api_grid.tiles,
        floor_objects=_floor_objects(grid),
    )


def save_current_editor_map(request: MapEditorSaveMapRequest) -> MapEditorSavedMapMetadata:
    """Persist the current entity-free editor map snapshot to a local JSON file."""
    snapshot = get_editor_snapshot()
    object_placements = _saved_object_placements(snapshot.floor_objects)
    map_id = _save_id(request.id) if request.id else _unique_save_id(request.name)
    now = _utc_now()
    path = _save_path(map_id)
    created_at = now
    revision = 1
    if path.exists():
        if not request.overwrite:
            raise ValueError(f"saved map already exists: {map_id}")
        try:
            previous = MapEditorSavedMapDocument.model_validate_json(path.read_text(encoding="utf-8")).metadata
            created_at = previous.created_at
            revision = previous.revision + 1
        except Exception:
            created_at = now
    metadata = MapEditorSavedMapMetadata(
        id=map_id,
        name=request.name,
        created_at=created_at,
        updated_at=now,
        revision=revision,
        grid_bounds=snapshot.grid_bounds,
        tile_count=len(snapshot.tiles),
        floor_object_count=len(snapshot.floor_objects),
    )
    document = MapEditorSavedMapDocument(
        schema_version=_SAVE_SCHEMA_VERSION,
        metadata=metadata,
        snapshot=snapshot,
        object_placements=object_placements,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(document.model_dump_json(indent=2), encoding="utf-8")
    return metadata


def list_saved_editor_maps() -> MapEditorSavedMapList:
    """List saved editor maps from the local JSON store."""
    maps = []
    for path in sorted(_save_dir().glob("*.json")):
        try:
            maps.append(MapEditorSavedMapDocument.model_validate_json(path.read_text(encoding="utf-8")).metadata)
        except Exception:
            continue
    maps.sort(key=lambda metadata: metadata.updated_at, reverse=True)
    return MapEditorSavedMapList(maps=maps)


def get_saved_editor_map(map_id: str) -> MapEditorSavedMapDocument:
    """Read a saved editor map document without loading it into GridMap."""
    path = _save_path(map_id)
    if not path.exists():
        raise ValueError(f"saved map not found: {map_id}")
    document = MapEditorSavedMapDocument.model_validate_json(path.read_text(encoding="utf-8"))
    if document.schema_version != _SAVE_SCHEMA_VERSION:
        raise ValueError(f"unsupported saved map schema: {document.schema_version}")
    return document


def load_saved_editor_map(map_id: str) -> MapEditorMapSnapshot:
    """Load a saved editor map into GridMap, rebuilding map state only."""
    document = get_saved_editor_map(map_id)
    _load_editor_snapshot(document.snapshot, document.object_placements)
    return get_editor_snapshot()


def delete_saved_editor_map(map_id: str) -> None:
    """Delete a saved editor map document."""
    path = _save_path(map_id)
    if not path.exists():
        raise ValueError(f"saved map not found: {map_id}")
    path.unlink()


def build_catalog() -> MapEditorCatalog:
    """Build the normalized mapeditor catalog."""
    presets = [
        _entry("scratch", "Blank Map", "presets", "map_preset", "server.mapeditor_support", placement="map"),
        _entry(
            "forgotten_crypt_arena",
            "Forgotten Crypt Arena",
            "presets",
            "map_preset",
            "server.mapeditor_support",
            placement="map",
            default_state={"has_entities": False},
        ),
    ]
    tiles = [
        _entry("floor", "Floor", "tiles", "tile", "dnd.core.gridmap", flags={"walkable": True, "blocks_vision": False}),
        _entry("wall", "Wall", "tiles", "tile", "dnd.core.gridmap", flags={"walkable": False, "blocks_vision": True}),
        _entry("water", "Water", "tiles", "tile", "dnd.core.gridmap", flags={"walkable": False, "blocks_vision": False}),
        _entry(
            "difficult_terrain",
            "Difficult Terrain",
            "tiles",
            "tile",
            "dnd.core.base_tiles",
            flags={"walkable": True, "walking_cost": 2},
        ),
        _entry(
            "spike_zone",
            "Spike Zone",
            "tiles",
            "hazard_zone",
            "dnd.tiles",
            placement="zone",
            flags={"walkable": True, "hazardous": True},
        ),
    ]
    objects = [
        _entry("door", "Door", "environment", "door", "dnd.items.test_items", map_char="pi", flags=_flags(False, False, True, False, True, True)),
        _entry("wall_torch", "Wall Torch", "environment", "light", "dnd.items.test_items", map_char="diamond", flags=_flags(False, False, True, False, False, False, emits_light=True)),
        _entry("trap_lever", "Trap Lever", "environment", "device", "dnd.items.test_items", map_char="lambda", flags=_flags(False, False, True, False, False, False), actions=["Pull Lever"]),
        _entry("storage_chest", "Chest", "environment", "container", "dnd.items.test_items", map_char="Omega", flags=_flags(False, False, True, False, False, False), actions=["Loot All"]),
        _entry("campfire", "Campfire", "environment", "camp", "dnd.items.test_items", map_char="*", flags=_flags(False, False, True, False, False, False), actions=["Rest", "Cook"]),
        _entry("arcane_device", "Arcane Device", "environment", "device", "dnd.items.test_items", map_char="phi", flags=_flags(False, False, True, False, False, False), actions=["Activate Device"]),
        _entry("arcane_machine_gun", "Arcane Machine Gun", "environment", "device", "dnd.items.test_items", map_char="sigma", flags=_flags(False, False, True, False, False, False), actions=["Magic Missile"], stability="demo"),
        _entry("fireball_cannon", "Fireball Cannon", "environment", "device", "dnd.items.test_items", map_char="sigma", flags=_flags(False, False, True, False, False, False), actions=["Fireball"], stability="demo"),
        _entry("crate", "Crate", "breakables", "breakable", "server.mapeditor_support", map_char="box", flags=_flags(False, False, False, False, False, False, targetable=True), stability="candidate", default_state={"hp": 20}),
        _entry("boulder", "Boulder", "breakables", "blocker", "server.mapeditor_support", map_char="rock", flags=_flags(False, False, False, False, True, False), stability="candidate"),
        _entry("barricade", "Barricade", "breakables", "blocker", "server.mapeditor_support", map_char="bar", flags=_flags(False, False, False, False, True, True, targetable=True), stability="candidate", default_state={"hp": 20}),
        _entry("oil_barrel", "Oil Barrel", "breakables", "breakable", "server.mapeditor_support", map_char="barrel", flags=_flags(False, False, False, False, True, False, targetable=True), stability="candidate", default_state={"hp": 12}),
    ]
    loot = []
    loot.extend(_registry_entries(WEAPONS, "loot/weapons", "weapon", "dnd.items.weapons", "dagger", equippable=True))
    loot.extend(_registry_entries(ARMORS, "loot/armor", "armor", "dnd.items.armors", "armor", equippable=True))
    loot.extend(_registry_entries(SHIELDS, "loot/armor", "shield", "dnd.items.armors", "shield", equippable=True))
    loot.extend([
        _entry("healing_potion", "Potion of Healing", "loot/consumables", "consumable", "dnd.items.test_items", map_char="theta", flags=_flags(True, False, True, True, False, False), actions=["Drink Potion"]),
        _entry("potion_of_greater_invisibility", "Potion of Greater Invisibility", "loot/consumables", "consumable", "dnd.items.test_items", map_char="theta", flags=_flags(True, False, True, True, False, False), actions=["Drink Greater Invisibility Potion"]),
        _entry("potion_of_haste", "Potion of Haste", "loot/consumables", "consumable", "dnd.items.test_items", map_char="theta", flags=_flags(True, False, True, True, False, False), actions=["Drink Haste Potion"]),
        _entry("acid_flask", "Acid Flask", "loot/consumables", "consumable", "dnd.items.test_items", map_char="!", flags=_flags(True, False, True, True, False, False), actions=["Acid Flask"]),
        _entry("weapon_coat", "Weapon Coat", "loot/consumables", "consumable", "dnd.items.test_items", map_char="phi", flags=_flags(True, False, True, True, False, False), actions=["Coat Main Hand", "Coat Off Hand"]),
        _entry("torch", "Torch", "loot/spell_items", "light", "dnd.items.test_items", map_char="diamond", flags=_flags(True, False, True, False, False, False, emits_light=True), actions=["Ignite Torch"]),
        _entry("scroll_of_fireball", "Scroll of Fireball", "loot/spell_items", "scroll", "dnd.items.test_items", map_char="sigma", flags=_flags(True, False, True, True, False, False), actions=["Fireball"]),
        _entry("scroll_of_magic_missile", "Scroll of Magic Missile", "loot/spell_items", "scroll", "dnd.items.test_items", map_char="sigma", flags=_flags(True, False, True, True, False, False), actions=["Magic Missile"]),
        _entry("scroll_of_hold_person", "Scroll of Hold Person", "loot/spell_items", "scroll", "dnd.items.test_items", map_char="sigma", flags=_flags(True, False, True, True, False, False), actions=["Hold Person"]),
        _entry("scroll_of_mage_armor", "Scroll of Mage Armor", "loot/spell_items", "scroll", "dnd.items.test_items", map_char="sigma", flags=_flags(True, False, True, True, False, False), actions=["Mage Armor"]),
        _entry("scroll_of_spike_growth", "Scroll of Spike Growth", "loot/spell_items", "scroll", "dnd.items.test_items", map_char="sigma", flags=_flags(True, False, True, True, False, False), actions=["Spike Growth"]),
        _entry("scroll_of_fire_bolt", "Scroll of Fire Bolt", "loot/spell_items", "scroll", "dnd.items.test_items", map_char="sigma", flags=_flags(True, False, True, True, False, False), actions=["Fire Bolt"]),
        _entry("scroll_of_invisibility", "Scroll of Invisibility", "loot/spell_items", "scroll", "dnd.items.test_items", map_char="sigma", flags=_flags(True, False, True, True, False, False), actions=["Invisibility"]),
        _entry("wand_of_magic_missiles", "Wand of Magic Missiles", "loot/spell_items", "wand", "dnd.items.test_items", map_char="sigma", flags=_flags(True, False, True, False, False, False), actions=["Magic Missile"]),
        _entry("wand_of_fire", "Wand of Fire", "loot/spell_items", "wand", "dnd.items.test_items", map_char="sigma", flags=_flags(True, False, True, False, False, False), actions=["Burning Hands", "Fireball"]),
    ])
    return MapEditorCatalog(presets=presets, tiles=tiles, objects=objects, loot=loot)


def apply_tile_patches(patches: Iterable[MapEditorTilePatch]) -> MapEditorMapSnapshot:
    """Apply tile patches through GridMap/Tile factories."""
    grid = get_map()
    spike_positions = set()
    for patch in patches:
        tile_type = _normalize_id(patch.type)
        if tile_type in {"spike_trap", "spike_zone", "spikes"}:
            spike_positions.add((patch.x, patch.y))
            continue
        old = grid.get_tile(patch.x, patch.y)
        old_light = old.default_light if old is not None else LightLevel.BRIGHT_LIGHT
        if tile_type == "difficult_terrain":
            tile = difficult_terrain_factory((patch.x, patch.y))
            tile.default_light = _light_level(patch.light_level) if patch.light_level is not None else old_light
            grid.set_tile(patch.x, patch.y, tile=tile)
            continue
        walkable, visible, name = _tile_properties(tile_type)
        tile = grid.set_tile(patch.x, patch.y, walkable=walkable, visible=visible, name=name)
        tile.default_light = _light_level(patch.light_level) if patch.light_level is not None else old_light

    if spike_positions:
        spike_tiles, _handler = create_spike_zone(spike_positions)
        for tile in spike_tiles:
            old = grid.get_tile(tile.position[0], tile.position[1])
            if old is not None:
                tile.default_light = old.default_light
            grid.set_tile(tile.position[0], tile.position[1], tile=tile)
    return get_editor_snapshot()


def place_catalog_object(request: MapEditorObjectPlaceRequest) -> APIFloorObject:
    """Place a catalog object or loot item on the grid."""
    catalog_id = _normalize_id(request.catalog_id)
    position = tuple(request.position)
    owner = uuid4()
    grid = get_map()

    if catalog_id == "door":
        item = TestDoorA(source_entity_uuid=owner)
        grid.place_object(item.uuid, position)
    elif catalog_id == "wall_torch":
        item = create_wall_torch(position=position, owner_uuid=owner, lit=bool(request.options.get("lit", True)))
    elif catalog_id == "trap_lever":
        item = TrapLever(source_entity_uuid=owner, charges=1)
        item.place_on_grid(position)
    elif catalog_id == "storage_chest":
        item = StorageChest(source_entity_uuid=owner)
        item.place_on_grid(position)
    elif catalog_id == "campfire":
        item = UsableItem(
            source_entity_uuid=owner,
            name="Campfire",
            is_pickable=False,
            map_char="*",
            use_action_templates=[
                RestAction(source_entity_uuid=uuid4(), template=True),
                CookAction(source_entity_uuid=uuid4(), template=True),
            ],
        )
        item.place_on_grid(position)
    elif catalog_id == "arcane_device":
        item = create_arcane_device(owner, position=position)
    elif catalog_id == "arcane_machine_gun":
        item = create_arcane_machine_gun(owner, position=position)
    elif catalog_id == "fireball_cannon":
        item = create_fireball_cannon(owner, position=position, charges=int(request.options.get("charges", 3)))
    elif catalog_id in {"crate", "boulder", "barricade", "oil_barrel"}:
        item = _create_blocker(catalog_id, owner, position)
    elif catalog_id in WEAPONS:
        item = WEAPONS[catalog_id](owner)
        item.place_on_grid(position)
    elif catalog_id in ARMORS:
        item = ARMORS[catalog_id](owner)
        item.place_on_grid(position)
    elif catalog_id in SHIELDS:
        item = SHIELDS[catalog_id](owner)
        item.place_on_grid(position)
    else:
        item = _create_loot_item(catalog_id, owner)
        if item is None:
            raise ValueError(f"unknown mapeditor catalog id: {request.catalog_id}")
        item.place_on_grid(position)

    obj_pos = grid.get_object_position(item.uuid)
    if obj_pos is None:
        obj_pos = position
    return _floor_object(item.uuid, obj_pos)


def delete_catalog_object(request: MapEditorObjectDeleteRequest) -> MapEditorMapSnapshot:
    """Delete editor object(s) by UUID or by tile position."""
    grid = get_map()
    object_ids: List[UUID] = []
    if request.object_uuid:
        object_ids.append(UUID(request.object_uuid))
    elif request.position is not None:
        object_ids.extend(grid.get_objects_at(tuple(request.position)))
    else:
        raise ValueError("object_uuid or position is required")

    if not object_ids:
        raise ValueError("no mapeditor object found to delete")
    for object_uuid in object_ids:
        if grid.get_object_position(object_uuid) is None:
            raise ValueError(f"mapeditor object not found: {object_uuid}")
        grid.remove_object(object_uuid)
    return get_editor_snapshot()


def get_walkability() -> MapEditorWalkabilityResponse:
    grid = get_map()
    cells = []
    for x, y, _tile in _iter_tiles():
        walkable = grid.is_walkable_for(x, y, requesting_entity_uuid=None)
        blocker = None if walkable else grid.identify_blocker_at((x, y))
        cells.append(MapEditorWalkabilityCell(x=x, y=y, walkable=walkable, blocker=blocker))
    return MapEditorWalkabilityResponse(cells=cells)


def get_visibility_blockers() -> MapEditorVisibilityResponse:
    cells = []
    for x, y, tile in _iter_tiles():
        blocker: Optional[str] = None
        if not tile.visible:
            blocker = tile.name
        else:
            for obj_uuid in get_map().get_objects_at((x, y)):
                block = BaseBlock.get(obj_uuid)
                if block is not None and block.blocks_vision(None):
                    blocker = block.name
                    break
        cells.append(MapEditorVisibilityCell(x=x, y=y, blocks_visibility=blocker is not None, blocker=blocker))
    return MapEditorVisibilityResponse(cells=cells)


def get_objective_light() -> MapEditorLightResponse:
    return MapEditorLightResponse(
        cells=[
            MapEditorLightCell(x=x, y=y, light_level=tile.resolved_light_level.value)
            for x, y, tile in _iter_tiles()
        ]
    )


def _load_editor_snapshot(snapshot: MapEditorMapSnapshot, object_placements: List[MapEditorSavedObjectPlacement]) -> None:
    """Rebuild GridMap from a saved editor snapshot without entities."""
    reset_editor_world()
    grid = get_map()
    spike_light: Dict[Tuple[int, int], int] = {}
    for tile_data in snapshot.tiles:
        position = (tile_data.x, tile_data.y)
        if tile_data.is_hazardous or "Spike Trap" in tile_data.conditions:
            spike_light[position] = tile_data.light_level
            continue
        if tile_data.walking_cost > 1 or _normalize_id(tile_data.name) == "difficult_terrain":
            tile = difficult_terrain_factory(position)
            tile.default_light = _light_level(tile_data.light_level)
            grid.set_tile(tile_data.x, tile_data.y, tile=tile, fire_event=False)
            continue
        tile = grid.set_tile(
            tile_data.x,
            tile_data.y,
            walkable=tile_data.walkable,
            visible=tile_data.visible,
            name=tile_data.name,
            fire_event=False,
        )
        tile.default_light = _light_level(tile_data.light_level)

    if spike_light:
        spike_tiles, _handler = create_spike_zone(set(spike_light))
        for tile in spike_tiles:
            tile.default_light = _light_level(spike_light[tile.position])
            grid.set_tile(tile.position[0], tile.position[1], tile=tile, fire_event=False)

    for placement in object_placements:
        place_catalog_object(
            MapEditorObjectPlaceRequest(
                catalog_id=placement.catalog_id,
                position=placement.position,
            )
        )


def _iter_tiles() -> Iterable[Tuple[int, int, Tile]]:
    grid = get_map()
    min_x, min_y, max_x, max_y = grid.bounds
    for y in range(min_y, max_y + 1):
        for x in range(min_x, max_x + 1):
            tile = grid.get_tile(x, y)
            if tile is not None:
                yield x, y, tile


def _floor_objects(grid: Any) -> List[APIFloorObject]:
    result = []
    for obj_uuid, obj_pos in grid._object_positions.items():
        result.append(_floor_object(obj_uuid, obj_pos))
    return result


def _floor_object(obj_uuid: UUID, obj_pos: Tuple[int, int]) -> APIFloorObject:
    obj = BaseBlock.get(obj_uuid)
    if obj is None:
        return APIFloorObject(uuid=str(obj_uuid), name="Object", position=list(obj_pos), map_char="?", state={})
    return APIFloorObject(
        uuid=str(obj_uuid),
        name=obj.name or "Object",
        position=list(obj_pos),
        map_char=getattr(obj, "map_char", "?"),
        state=_get_floor_object_state(obj),
    )


def _get_floor_object_state(obj: BaseBlock) -> Dict[str, Any]:
    all_fields = set(type(obj).model_fields.keys())
    state_fields = all_fields - _BASE_BLOCK_FIELDS - _ALREADY_SERIALIZED
    return obj.model_dump(mode="json", include=state_fields)


def _saved_object_placements(floor_objects: List[APIFloorObject]) -> List[MapEditorSavedObjectPlacement]:
    return [
        MapEditorSavedObjectPlacement(
            catalog_id=_catalog_id_for_floor_object(obj),
            name=obj.name,
            position=(obj.position[0], obj.position[1]),
        )
        for obj in floor_objects
    ]


def _catalog_id_for_floor_object(obj: APIFloorObject) -> str:
    explicit = {
        "door": "door",
        "wall_torch": "wall_torch",
        "trap_lever": "trap_lever",
        "potion_of_healing": "healing_potion",
        "chest": "storage_chest",
        "campfire": "campfire",
        "arcane_device": "arcane_device",
        "arcane_machine_gun": "arcane_machine_gun",
        "fireball_cannon": "fireball_cannon",
        "crate": "crate",
        "boulder": "boulder",
        "barricade": "barricade",
        "oil_barrel": "oil_barrel",
    }
    normalized_name = _normalize_id(obj.name)
    if normalized_name in explicit:
        return explicit[normalized_name]
    catalog_ids = {entry.id for entry in build_catalog().objects + build_catalog().loot}
    if normalized_name in catalog_ids:
        return normalized_name
    raise ValueError(f"cannot save unknown mapeditor object: {obj.name}")


def _save_dir() -> Path:
    configured = os.environ.get("DND_MAPEDITOR_SAVE_DIR")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[1] / "data" / "mapeditor" / "maps"


def _save_path(map_id: str) -> Path:
    return _save_dir() / f"{_save_id(map_id)}.json"


def _unique_save_id(name: str) -> str:
    base = _save_id(name)
    candidate = base
    suffix = 2
    while _save_path(candidate).exists():
        candidate = f"{base}_{suffix}"
        suffix += 1
    return candidate


def _save_id(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", value.strip()).strip("_").lower()
    return slug or f"map_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _tile_properties(tile_type: str) -> Tuple[bool, bool, str]:
    normalized = _normalize_id(tile_type)
    if normalized == "wall":
        return False, False, "Wall"
    if normalized == "water":
        return False, True, "Water"
    return True, True, "Floor"


def _light_level(value: int) -> LightLevel:
    if value < 0 or value > 4:
        raise ValueError("light level must be between 0 and 4")
    return LightLevel(value)


def _normalize_id(value: str) -> str:
    return value.strip().lower().replace(" ", "_").replace("-", "_")


def _create_blocker(catalog_id: str, owner: UUID, position: Tuple[int, int]) -> BaseItem:
    config = {
        "crate": {"name": "Crate", "hp": 20, "blocks_movement": False, "blocks_vision_field": False, "map_char": "C"},
        "boulder": {"name": "Boulder", "hp": 30, "blocks_movement": True, "blocks_vision_field": False, "map_char": "B"},
        "barricade": {"name": "Barricade", "hp": 20, "blocks_movement": True, "blocks_vision_field": True, "map_char": "X"},
        "oil_barrel": {"name": "Oil Barrel", "hp": 12, "blocks_movement": True, "blocks_vision_field": False, "map_char": "O"},
    }[catalog_id]
    health = BaseItem.create_item_health(owner, config["hp"])
    item = BaseItem(
        source_entity_uuid=owner,
        name=config["name"],
        is_pickable=False,
        is_targetable=True,
        health=health,
        map_char=config["map_char"],
        blocks_movement=config["blocks_movement"],
        blocks_vision_field=config["blocks_vision_field"],
    )
    item.place_on_grid(position)
    return item


def _create_loot_item(catalog_id: str, owner: UUID) -> Optional[BaseItem]:
    factories = {
        "healing_potion": lambda: create_healing_potion(owner, heal_amount=10),
        "potion_of_greater_invisibility": lambda: create_potion_of_greater_invisibility(owner),
        "potion_of_haste": lambda: create_potion_of_haste(owner),
        "acid_flask": lambda: create_acid_flask(owner),
        "weapon_coat": lambda: create_weapon_coat(owner),
        "torch": lambda: create_torch(owner),
        "scroll_of_fireball": lambda: create_scroll_of_fireball(owner),
        "scroll_of_magic_missile": lambda: create_scroll_of_magic_missile(owner),
        "scroll_of_hold_person": lambda: create_scroll_of_hold_person(owner),
        "scroll_of_mage_armor": lambda: create_scroll_of_mage_armor(owner),
        "scroll_of_spike_growth": lambda: create_scroll_of_spike_growth(owner),
        "scroll_of_fire_bolt": lambda: create_scroll_of_fire_bolt(owner),
        "scroll_of_invisibility": lambda: create_scroll_of_invisibility(owner),
        "wand_of_magic_missiles": lambda: create_wand_of_magic_missiles(owner),
        "wand_of_fire": lambda: create_wand_of_fire(owner),
    }
    factory = factories.get(catalog_id)
    return factory() if factory else None


def _entry(
    id: str,
    name: str,
    group: str,
    category: str,
    source_module: str,
    *,
    stability: str = "stable",
    placement: str = "single_tile",
    map_char: Optional[str] = None,
    visual_item_name: Optional[str] = None,
    flags: Optional[Dict[str, Any]] = None,
    actions: Optional[List[str]] = None,
    default_state: Optional[Dict[str, Any]] = None,
) -> MapEditorCatalogEntry:
    return MapEditorCatalogEntry(
        id=id,
        name=name,
        group=group,
        category=category,
        source_module=source_module,
        stability=stability,
        placement=placement,
        map_char=map_char,
        visual_item_name=visual_item_name,
        flags=flags or {},
        actions=actions or [],
        default_state=default_state or {},
    )


def _registry_entries(registry: Dict[str, Any], group: str, category: str, source_module: str, map_char: str, *, equippable: bool) -> List[MapEditorCatalogEntry]:
    entries = []
    for key in sorted(registry):
        entries.append(
            _entry(
                key,
                key.replace("_", " ").title(),
                group,
                category,
                source_module,
                map_char=map_char,
                flags=_flags(True, equippable, False, False, False, False),
            )
        )
    return entries


def _flags(
    pickable: bool,
    equippable: bool,
    usable: bool,
    consumable: bool,
    blocks_movement: bool,
    blocks_vision: bool,
    *,
    emits_light: bool = False,
    targetable: bool = False,
) -> Dict[str, Any]:
    return {
        "pickable": pickable,
        "equippable": equippable,
        "usable": usable,
        "consumable": consumable,
        "targetable": targetable,
        "blocks_movement": blocks_movement,
        "blocks_vision": blocks_vision,
        "emits_light": emits_light,
    }
