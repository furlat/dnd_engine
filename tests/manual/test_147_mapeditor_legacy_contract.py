"""Exact migration contract for the archived local mapeditor API smoke."""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from dnd.blocks.base_item import BaseItem
from dnd.core.base_block import BaseBlock
from dnd.core.events import EventQueue
from dnd.core.gridmap import get_map
from dnd.encounter import Encounter
from dnd.entity import Entity
from dnd.items.test_items import PullLeverAction, TrapLever
from server.event_server import app, sim
from server.event_stream import event_stream
from tests.engine_book.test_chapter_18_encounters_apis import (
    reset_chapter_18_state,
)


CoverageStatus = Literal["active", "strengthened", "stale"]


@dataclass(frozen=True)
class LegacyCoverage:
    """One archived mapeditor case's maintained replacement."""

    status: CoverageStatus
    selector: str
    rationale: str


THIS_FILE = "tests/manual/test_147_mapeditor_legacy_contract.py"
CATALOG_PRESET_SELECTOR = (
    f"{THIS_FILE}::test_mapeditor_catalog_and_forgotten_crypt_preset_are_complete"
)
SCRATCH_SELECTOR = (
    f"{THIS_FILE}::"
    "test_mapeditor_scratch_layers_are_visible_on_every_objective_surface"
)
ROUNDTRIP_SELECTOR = (
    f"{THIS_FILE}::"
    "test_mapeditor_save_lifecycle_and_crypt_roundtrip_are_exact"
)


MAPEDITOR_LEGACY_CASES: dict[str, LegacyCoverage] = {
    "test_catalog": LegacyCoverage(
        "active",
        CATALOG_PRESET_SELECTOR,
        "The canonical catalog retains required presets, environment objects, weapons, and consumables.",
    ),
    "test_scratch_map_and_layers": LegacyCoverage(
        "strengthened",
        SCRATCH_SELECTOR,
        "The maintained contract checks every archived terrain, directional, walkability, visibility, and entity-free assertion.",
    ),
    "test_forgotten_crypt_preset": LegacyCoverage(
        "active",
        CATALOG_PRESET_SELECTOR,
        "The preset's doors, torches, potions, lever, light, and entity-free boundary are restored.",
    ),
    "test_save_load_map_state_only": LegacyCoverage(
        "strengthened",
        ROUNDTRIP_SELECTOR,
        "The maintained contract covers duplicate denial, generated IDs, overwrite revisions, listing, deletion persistence, and a structural crypt roundtrip.",
    ),
}


def _placement_payload(
    client: TestClient,
    content_id: str,
    position: tuple[int, int],
) -> dict[str, object]:
    """Select one exact default recipe from the live mapeditor catalog."""
    catalog = client.get("/mapeditor/catalog").json()
    row = next(
        entry
        for entry in (*catalog["objects"], *catalog["loot"])
        if entry["recipe"]["ref"]["content_id"] == content_id
        and entry["recipe_preset_ref"] is None
    )
    return {
        "recipe": row["recipe"],
        "content_set_digest": row["content_set_digest"],
        "position": list(position),
    }


def test_mapeditor_manifest_accounts_for_all_4_cases() -> None:
    """Every archived mapeditor case has one exact maintained disposition."""
    assert len(MAPEDITOR_LEGACY_CASES) == 4
    assert all(
        case.startswith("test_")
        and row.selector.startswith("tests/")
        and "::test_" in row.selector
        and row.rationale
        for case, row in MAPEDITOR_LEGACY_CASES.items()
    )


def test_mapeditor_catalog_and_forgotten_crypt_preset_are_complete() -> None:
    """The editor can discover and instantiate its canonical showcase preset."""
    reset_chapter_18_state()
    client = TestClient(app)

    catalog_response = client.get("/mapeditor/catalog")

    assert catalog_response.status_code == 200
    catalog = catalog_response.json()
    assert "forgotten_crypt_arena" in {
        row["id"] for row in catalog["presets"]
    }
    object_ids = {
        row["recipe"]["ref"]["content_id"]
        for row in catalog["objects"]
    }
    loot_by_id = {
        row["recipe"]["ref"]["content_id"]: row
        for row in catalog["loot"]
        if row["recipe_preset_ref"] is None
    }
    loot_ids = set(loot_by_id)
    assert {"environment.wall_torch", "environment.door"} <= object_ids
    assert {
        "weapon.longsword",
        "armor.plate",
        "shield.shield",
        "consumable.healing_potion",
    } <= loot_ids
    assert (
        loot_by_id["weapon.longsword"]["ordering"]["sort_group"],
        loot_by_id["weapon.longsword"]["presentation"][
            "visual_variant_key"
        ],
    ) == ("weapons.martial_melee", "longsword")
    assert (
        loot_by_id["armor.plate"]["ordering"]["sort_group"],
        loot_by_id["armor.plate"]["presentation"]["visual_variant_key"],
    ) == ("armor.heavy", "plate")
    assert (
        loot_by_id["shield.shield"]["ordering"]["sort_group"],
        loot_by_id["shield.shield"]["presentation"]["visual_variant_key"],
    ) == ("armor.shields", "shield")

    preset_response = client.post(
        "/mapeditor/maps",
        json={
            "source": "preset",
            "preset_id": "forgotten_crypt_arena",
        },
    )

    assert preset_response.status_code == 200
    snapshot = preset_response.json()
    object_names = [row["name"] for row in snapshot["floor_objects"]]
    assert "Door" in object_names
    assert object_names.count("Wall Torch") == 2
    assert object_names.count("Potion of Healing") == 2
    assert "Trap Lever" in object_names
    assert Entity.get_all_entities() == []

    light_response = client.get("/mapeditor/map/light")
    assert light_response.status_code == 200
    assert any(
        cell["light_level"] > 1
        for cell in light_response.json()["cells"]
    )


def test_mapeditor_scratch_layers_are_visible_on_every_objective_surface() -> None:
    """Terrain, directional borders, doors, and walls retain exact editor semantics."""
    reset_chapter_18_state()
    client = TestClient(app)

    create_response = client.post(
        "/mapeditor/maps",
        json={
            "source": "scratch",
            "width": 4,
            "height": 3,
            "origin": [0, 0],
            "default_light": 1,
        },
    )

    assert create_response.status_code == 200
    created = create_response.json()
    assert created["grid_bounds"] == {
        "min_x": 0,
        "min_y": 0,
        "max_x": 3,
        "max_y": 2,
    }
    assert len(created["tiles"]) == 12
    assert created["floor_objects"] == []

    terrain_response = client.post(
        "/mapeditor/map/tiles",
        json={
            "tiles": [
                {"x": 1, "y": 1, "type": "Wall"},
                {"x": 2, "y": 1, "type": "Water"},
                {"x": 3, "y": 2, "type": "Difficult Terrain"},
            ],
        },
    )

    assert terrain_response.status_code == 200
    terrain = {
        (tile["x"], tile["y"]): tile
        for tile in terrain_response.json()["tiles"]
    }
    assert terrain[(1, 1)]["name"] == "Wall"
    assert terrain[(1, 1)]["walkable"] is False
    assert terrain[(2, 1)]["name"] == "Water"
    assert terrain[(2, 1)]["walkable"] is False
    assert terrain[(3, 2)]["name"] == "Difficult Terrain"
    assert terrain[(3, 2)]["walking_cost"] == 2

    directional_response = client.post(
        "/mapeditor/map/tiles",
        json={
            "tiles": [
                {
                    "x": 0,
                    "y": 0,
                    "directional_channel": "movement",
                    "direction": "east",
                    "passable": False,
                },
                {
                    "x": 0,
                    "y": 0,
                    "directional_channel": "vision",
                    "direction": "north",
                    "passable": False,
                },
            ],
        },
    )

    assert directional_response.status_code == 200
    editor_tile = next(
        tile
        for tile in directional_response.json()["tiles"]
        if (tile["x"], tile["y"]) == (0, 0)
    )
    assert editor_tile["directional_blocks_movement"]["east"] is True
    assert editor_tile["directional_blocks_vision"]["north"] is True

    current_editor_response = client.get("/mapeditor/map")
    assert current_editor_response.status_code == 200
    current_editor_tile = next(
        tile
        for tile in current_editor_response.json()["tiles"]
        if (tile["x"], tile["y"]) == (0, 0)
    )
    assert current_editor_tile["directional_blocks_movement"]["east"] is True
    assert current_editor_tile["directional_blocks_vision"]["north"] is True

    door_response = client.post(
        "/mapeditor/map/objects",
        json=_placement_payload(
            client,
            "environment.door",
            (0, 1),
        ),
    )
    assert door_response.status_code == 200
    assert door_response.json()["name"] == "Door"

    walkability_response = client.get("/mapeditor/map/walkability")
    visibility_response = client.get("/mapeditor/map/visibility")
    assert walkability_response.status_code == 200
    assert visibility_response.status_code == 200
    walkability = {
        (cell["x"], cell["y"]): cell
        for cell in walkability_response.json()["cells"]
    }
    visibility = {
        (cell["x"], cell["y"]): cell
        for cell in visibility_response.json()["cells"]
    }
    assert walkability[(0, 1)]["walkable"] is False
    assert walkability[(0, 1)]["blocker"] == "Door"
    assert visibility[(0, 1)]["blocks_visibility"] is True
    assert visibility[(1, 1)]["blocks_visibility"] is True
    assert Entity.get_all_entities() == []

    assert client.get("/grid").status_code == 404
    assert client.get("/state").status_code == 404
    encounter = Encounter(
        name="Mapeditor objective projection",
        source_entity_uuid=uuid4(),
    )
    sim.encounter = encounter
    Encounter._active_encounter = encounter
    event_stream.ensure_attached()
    try:
        objective_response = client.get(
            "/diagnostics/objective/bootstrap",
        )
        assert objective_response.status_code == 200
        objective_tile = next(
            tile
            for tile in objective_response.json()["world"]["state"]["grid"]["tiles"]
            if (tile["x"], tile["y"]) == (0, 0)
        )
        assert objective_tile["directional_blocks_movement"]["east"] is True
        assert objective_tile["directional_blocks_vision"]["north"] is True
    finally:
        sim.encounter = None
        Encounter._active_encounter = None


def _without_runtime_uuids(value: object) -> object:
    """Strip regenerated runtime identities from a cold map snapshot."""
    if isinstance(value, dict):
        return {
            key: _without_runtime_uuids(item)
            for key, item in value.items()
            if not (
                key == "uuid"
                or key.endswith("_uuid")
                or key.endswith("_uuids")
            )
        }
    if isinstance(value, list):
        return [_without_runtime_uuids(item) for item in value]
    return value


def _stable_map_snapshot(snapshot: dict[str, object]) -> dict[str, object]:
    """Normalize intentionally regenerated identities and collection order."""
    normalized = cast(
        dict[str, object],
        _without_runtime_uuids(snapshot),
    )
    tiles = cast(list[dict[str, object]], normalized["tiles"])
    floor_objects = cast(
        list[dict[str, object]],
        normalized["floor_objects"],
    )
    normalized["tiles"] = sorted(
        tiles,
        key=lambda tile: (
            cast(int, tile["x"]),
            cast(int, tile["y"]),
        ),
    )

    def floor_object_key(
        floor_object: dict[str, object],
    ) -> tuple[int, int, str]:
        position = cast(list[int], floor_object["position"])
        return (
            position[0],
            position[1],
            cast(str, floor_object["name"]),
        )

    normalized["floor_objects"] = sorted(
        floor_objects,
        key=floor_object_key,
    )
    return normalized


def _assert_floor_location_authority(
    snapshot: dict[str, object],
) -> None:
    """Every projected floor object agrees with BaseItem and GridMap."""
    grid = get_map()
    floor_objects = cast(
        list[dict[str, object]],
        snapshot["floor_objects"],
    )
    for floor_object in floor_objects:
        item = BaseBlock.get(UUID(cast(str, floor_object["uuid"])))
        assert isinstance(item, BaseItem)
        serialized_position = cast(list[int], floor_object["position"])
        position = (serialized_position[0], serialized_position[1])
        tile = grid.get_tile(position[0], position[1])
        assert tile is not None
        assert item.tile_uuid == tile.uuid
        assert item.get_position() == position


def _assert_loaded_trap_lever_is_live(
    snapshot: dict[str, object],
) -> None:
    """The regenerated lever targets the regenerated trap handler and tiles."""
    floor_objects = cast(
        list[dict[str, object]],
        snapshot["floor_objects"],
    )
    lever_row = next(
        row
        for row in floor_objects
        if row["name"] == "Trap Lever"
    )
    lever = BaseBlock.get(UUID(cast(str, lever_row["uuid"])))
    assert isinstance(lever, TrapLever)
    assert len(lever.use_action_templates) == 1
    action = lever.use_action_templates[0]
    assert isinstance(action, PullLeverAction)
    assert action.trap_handler_uuid is not None

    tiles = cast(list[dict[str, object]], snapshot["tiles"])
    spike_positions = {
        (cast(int, tile["x"]), cast(int, tile["y"]))
        for tile in tiles
        if "Spike Trap" in cast(list[str], tile["conditions"])
    }
    linked_positions = set()
    for tile_uuid in action.trap_tile_uuids:
        tile = BaseBlock.get(tile_uuid)
        assert tile is not None
        linked_positions.add(tile.position)
    assert linked_positions == spike_positions
    for position in spike_positions:
        assert any(
            handler.uuid == action.trap_handler_uuid
            for handler in EventQueue.get_spatial_handlers_at(position)
        )


def test_mapeditor_save_lifecycle_and_crypt_roundtrip_are_exact(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The file-backed editor store preserves its complete archived lifecycle."""
    monkeypatch.setenv("DND_MAPEDITOR_SAVE_DIR", str(tmp_path))
    reset_chapter_18_state()
    client = TestClient(app)

    create_response = client.post(
        "/mapeditor/maps",
        json={
            "source": "scratch",
            "width": 3,
            "height": 2,
            "origin": [0, 0],
            "default_light": 1,
        },
    )
    assert create_response.status_code == 200
    tile_response = client.post(
        "/mapeditor/map/tiles",
        json={"tiles": [{"x": 1, "y": 0, "type": "Wall", "light_level": 4}]},
    )
    assert tile_response.status_code == 200
    door_response = client.post(
        "/mapeditor/map/objects",
        json=_placement_payload(
            client,
            "environment.door",
            (2, 1),
        ),
    )
    assert door_response.status_code == 200

    save_response = client.post(
        "/mapeditor/saves",
        json={"id": "roundtrip", "name": "Roundtrip"},
    )
    assert save_response.status_code == 200
    metadata = save_response.json()
    assert metadata["id"] == "roundtrip"
    assert metadata["revision"] == 1
    assert metadata["tile_count"] == 6
    assert metadata["floor_object_count"] == 1

    duplicate_response = client.post(
        "/mapeditor/saves",
        json={"id": "roundtrip", "name": "Roundtrip"},
    )
    assert duplicate_response.status_code == 400
    assert duplicate_response.json()["detail"]["code"] == "mapeditor_save_failed"

    generated_response = client.post(
        "/mapeditor/saves",
        json={"name": "Roundtrip"},
    )
    assert generated_response.status_code == 200
    assert generated_response.json()["id"] == "roundtrip_2"

    overwrite_response = client.post(
        "/mapeditor/saves",
        json={
            "id": "roundtrip",
            "name": "Roundtrip v2",
            "overwrite": True,
        },
    )
    assert overwrite_response.status_code == 200
    assert overwrite_response.json()["revision"] == 2

    saved_text = (tmp_path / "roundtrip.json").read_text(encoding="utf-8")
    assert '"entities"' not in saved_text
    assert '"encounter"' not in saved_text

    list_response = client.get("/mapeditor/saves")
    assert list_response.status_code == 200
    assert {"roundtrip", "roundtrip_2"} <= {
        row["id"] for row in list_response.json()["maps"]
    }

    changed_response = client.post(
        "/mapeditor/maps",
        json={
            "source": "scratch",
            "width": 1,
            "height": 1,
            "origin": [9, 9],
            "default_light": 1,
        },
    )
    assert changed_response.status_code == 200

    load_response = client.post("/mapeditor/saves/roundtrip/load")
    assert load_response.status_code == 200
    loaded = load_response.json()
    assert loaded["grid_bounds"] == {
        "min_x": 0,
        "min_y": 0,
        "max_x": 2,
        "max_y": 1,
    }
    loaded_tiles = {
        (tile["x"], tile["y"]): tile
        for tile in loaded["tiles"]
    }
    assert loaded_tiles[(1, 0)]["name"] == "Wall"
    assert loaded_tiles[(1, 0)]["light_level"] == 4
    assert loaded["floor_objects"][0]["name"] == "Door"
    loaded_door_uuid = loaded["floor_objects"][0]["uuid"]
    assert Entity.get_all_entities() == []

    delete_response = client.post(
        "/mapeditor/map/objects/delete",
        json={"object_uuid": loaded_door_uuid},
    )
    assert delete_response.status_code == 200
    assert delete_response.json()["floor_objects"] == []
    deleted_save_response = client.post(
        "/mapeditor/saves",
        json={"id": "roundtrip_deleted", "name": "Roundtrip Deleted"},
    )
    assert deleted_save_response.status_code == 200
    deleted_load_response = client.post(
        "/mapeditor/saves/roundtrip_deleted/load",
    )
    assert deleted_load_response.status_code == 200
    assert deleted_load_response.json()["floor_objects"] == []

    crypt_response = client.post(
        "/mapeditor/maps",
        json={
            "source": "preset",
            "preset_id": "forgotten_crypt_arena",
        },
    )
    assert crypt_response.status_code == 200
    crypt_before = crypt_response.json()
    _assert_floor_location_authority(crypt_before)
    crypt_save_response = client.post(
        "/mapeditor/saves",
        json={"id": "crypt_exact", "name": "Crypt Exact"},
    )
    assert crypt_save_response.status_code == 200
    scratch_response = client.post(
        "/mapeditor/maps",
        json={"source": "scratch", "width": 1, "height": 1},
    )
    assert scratch_response.status_code == 200
    crypt_load_response = client.post("/mapeditor/saves/crypt_exact/load")
    assert crypt_load_response.status_code == 200
    crypt_loaded = crypt_load_response.json()
    _assert_floor_location_authority(crypt_loaded)
    _assert_loaded_trap_lever_is_live(crypt_loaded)
    assert _stable_map_snapshot(crypt_loaded) == _stable_map_snapshot(
        crypt_before,
    )
