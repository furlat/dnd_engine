"""Focused tests for the local mapeditor API surface.

Run with:
    python examples/test_mapeditor_api.py
"""

import sys
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from server.event_server import app


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"  PASSED: {message}")


def test_catalog() -> None:
    client = TestClient(app)
    response = client.get("/mapeditor/catalog")
    check(response.status_code == 200, "catalog endpoint returns 200")
    data = response.json()
    object_ids = {entry["id"] for entry in data["objects"]}
    loot_ids = {entry["id"] for entry in data["loot"]}
    preset_ids = {entry["id"] for entry in data["presets"]}
    check("forgotten_crypt_arena" in preset_ids, "catalog includes crypt preset")
    check("wall_torch" in object_ids, "catalog includes wall torch")
    check("door" in object_ids, "catalog includes door")
    check("longsword" in loot_ids, "catalog includes weapon registry entries")
    check("healing_potion" in loot_ids, "catalog includes consumables")


def test_scratch_map_and_layers() -> None:
    client = TestClient(app)
    response = client.post(
        "/mapeditor/maps",
        json={"source": "scratch", "width": 4, "height": 3, "origin": [0, 0], "default_light": 1},
    )
    check(response.status_code == 200, "scratch map creation returns 200")
    data = response.json()
    check(data["grid_bounds"] == {"min_x": 0, "min_y": 0, "max_x": 3, "max_y": 2}, "scratch bounds are inclusive")
    check(len(data["tiles"]) == 12, "scratch map has expected tile count")
    check(data["floor_objects"] == [], "scratch map starts without objects")

    response = client.post(
        "/mapeditor/map/tiles",
        json={
            "tiles": [
                {"x": 1, "y": 1, "type": "Wall"},
                {"x": 2, "y": 1, "type": "Water"},
                {"x": 3, "y": 2, "type": "Difficult Terrain"},
            ]
        },
    )
    check(response.status_code == 200, "tile patch returns 200")
    tiles = {(tile["x"], tile["y"]): tile for tile in response.json()["tiles"]}
    check(tiles[(1, 1)]["name"] == "Wall" and not tiles[(1, 1)]["walkable"], "wall tile is non-walkable")
    check(tiles[(2, 1)]["name"] == "Water" and not tiles[(2, 1)]["walkable"], "water tile is non-walkable")
    check(tiles[(3, 2)]["walking_cost"] == 2, "difficult terrain has walking cost 2")

    response = client.post("/mapeditor/map/objects", json={"catalog_id": "door", "position": [0, 1]})
    check(response.status_code == 200, "door placement returns 200")
    check(response.json()["name"] == "Door", "placed object is a door")

    walkability = client.get("/mapeditor/map/walkability").json()["cells"]
    door_walk = next(cell for cell in walkability if cell["x"] == 0 and cell["y"] == 1)
    check(not door_walk["walkable"] and door_walk["blocker"] == "Door", "closed door blocks walkability")

    visibility = client.get("/mapeditor/map/visibility").json()["cells"]
    door_visibility = next(cell for cell in visibility if cell["x"] == 0 and cell["y"] == 1)
    wall_visibility = next(cell for cell in visibility if cell["x"] == 1 and cell["y"] == 1)
    check(door_visibility["blocks_visibility"], "closed door blocks visibility")
    check(wall_visibility["blocks_visibility"], "wall blocks visibility")


def test_forgotten_crypt_preset() -> None:
    client = TestClient(app)
    response = client.post("/mapeditor/maps", json={"source": "preset", "preset_id": "forgotten_crypt_arena"})
    check(response.status_code == 200, "crypt preset creation returns 200")
    data = response.json()
    names = [obj["name"] for obj in data["floor_objects"]]
    check("Door" in names, "crypt preset includes door")
    check(names.count("Wall Torch") == 2, "crypt preset includes two wall torches")
    check(names.count("Potion of Healing") == 2, "crypt preset includes two healing potions")
    check("Trap Lever" in names, "crypt preset includes trap lever")

    entities = client.get("/entities").json()["entities"]
    check(entities == [], "mapeditor preset does not create entities")

    light = client.get("/mapeditor/map/light").json()["cells"]
    check(any(cell["light_level"] > 1 for cell in light), "crypt preset has objective torch light")


def test_save_load_map_state_only() -> None:
    client = TestClient(app)
    with tempfile.TemporaryDirectory() as save_dir:
        import os

        old_save_dir = os.environ.get("DND_MAPEDITOR_SAVE_DIR")
        os.environ["DND_MAPEDITOR_SAVE_DIR"] = save_dir
        try:
            response = client.post(
                "/mapeditor/maps",
                json={"source": "scratch", "width": 3, "height": 2, "origin": [0, 0], "default_light": 1},
            )
            check(response.status_code == 200, "save test scratch map creation returns 200")
            response = client.post(
                "/mapeditor/map/tiles",
                json={"tiles": [{"x": 1, "y": 0, "type": "Wall", "light_level": 4}]},
            )
            check(response.status_code == 200, "save test tile patch returns 200")
            response = client.post("/mapeditor/map/objects", json={"catalog_id": "door", "position": [2, 1]})
            check(response.status_code == 200, "save test object placement returns 200")

            response = client.post("/mapeditor/saves", json={"id": "roundtrip", "name": "Roundtrip"})
            check(response.status_code == 200, "map save returns 200")
            metadata = response.json()
            check(metadata["id"] == "roundtrip", "save uses requested id")
            check(metadata["revision"] == 1, "new save starts at revision 1")
            check(metadata["tile_count"] == 6, "save metadata records tile count")
            check(metadata["floor_object_count"] == 1, "save metadata records object count")

            response = client.post("/mapeditor/saves", json={"id": "roundtrip", "name": "Roundtrip"})
            check(response.status_code == 400, "explicit duplicate save id does not overwrite by default")

            response = client.post("/mapeditor/saves", json={"name": "Roundtrip"})
            check(response.status_code == 200, "same display name without id creates a new save")
            check(response.json()["id"] == "roundtrip_2", "new save name gets unique id")

            response = client.post("/mapeditor/saves", json={"id": "roundtrip", "name": "Roundtrip v2", "overwrite": True})
            check(response.status_code == 200, "explicit overwrite succeeds when requested")
            check(response.json()["revision"] == 2, "overwrite increments saved map revision")

            saved_path = Path(save_dir) / "roundtrip.json"
            saved_text = saved_path.read_text(encoding="utf-8")
            check('"entities"' not in saved_text, "save file does not serialize entities")
            check('"encounter"' not in saved_text, "save file does not serialize encounter state")

            response = client.get("/mapeditor/saves")
            check(response.status_code == 200, "save list returns 200")
            check(any(item["id"] == "roundtrip" for item in response.json()["maps"]), "save list includes saved map")

            response = client.post(
                "/mapeditor/maps",
                json={"source": "scratch", "width": 1, "height": 1, "origin": [9, 9], "default_light": 1},
            )
            check(response.status_code == 200, "map can be changed before loading save")

            response = client.post("/mapeditor/saves/roundtrip/load")
            check(response.status_code == 200, "map load returns 200")
            loaded = response.json()
            check(loaded["grid_bounds"] == {"min_x": 0, "min_y": 0, "max_x": 2, "max_y": 1}, "loaded map restores bounds")
            tiles = {(tile["x"], tile["y"]): tile for tile in loaded["tiles"]}
            check(tiles[(1, 0)]["name"] == "Wall", "loaded map restores wall tile")
            check(tiles[(1, 0)]["light_level"] == 4, "loaded map restores tile light")
            check(loaded["floor_objects"][0]["name"] == "Door", "loaded map restores floor object placement")
            loaded_door_uuid = loaded["floor_objects"][0]["uuid"]

            entities = client.get("/entities").json()["entities"]
            check(entities == [], "loaded map does not create entities")

            response = client.post("/mapeditor/map/objects/delete", json={"object_uuid": loaded_door_uuid})
            check(response.status_code == 200, "object delete by uuid returns 200")
            check(response.json()["floor_objects"] == [], "object delete removes floor object from current map")

            response = client.post("/mapeditor/saves", json={"id": "roundtrip_deleted", "name": "Roundtrip Deleted"})
            check(response.status_code == 200, "deleted-object map saves")
            response = client.post("/mapeditor/saves/roundtrip_deleted/load")
            check(response.status_code == 200, "deleted-object map loads")
            check(response.json()["floor_objects"] == [], "loaded deleted-object map keeps object deleted")

            response = client.post("/mapeditor/maps", json={"source": "preset", "preset_id": "forgotten_crypt_arena"})
            check(response.status_code == 200, "exact crypt preset can be recreated before save")
            crypt_before = response.json()
            response = client.post("/mapeditor/saves", json={"id": "crypt_exact", "name": "Crypt Exact"})
            check(response.status_code == 200, "exact crypt preset saves")
            response = client.post("/mapeditor/maps", json={"source": "scratch", "width": 1, "height": 1})
            check(response.status_code == 200, "map can be changed before loading exact crypt")
            response = client.post("/mapeditor/saves/crypt_exact/load")
            check(response.status_code == 200, "exact crypt preset loads")
            crypt_loaded = response.json()
            check(crypt_loaded["grid_bounds"] == crypt_before["grid_bounds"], "exact crypt load restores bounds")
            check(len(crypt_loaded["tiles"]) == len(crypt_before["tiles"]), "exact crypt load restores tile count")
            check(len(crypt_loaded["floor_objects"]) == len(crypt_before["floor_objects"]), "exact crypt load restores object count")
            check(
                sorted(obj["name"] for obj in crypt_loaded["floor_objects"]) == sorted(obj["name"] for obj in crypt_before["floor_objects"]),
                "exact crypt load restores object names",
            )
        finally:
            if old_save_dir is None:
                os.environ.pop("DND_MAPEDITOR_SAVE_DIR", None)
            else:
                os.environ["DND_MAPEDITOR_SAVE_DIR"] = old_save_dir


def main() -> None:
    print("\n=== Mapeditor API Tests ===")
    test_catalog()
    test_scratch_map_and_layers()
    test_forgotten_crypt_preset()
    test_save_load_map_state_only()
    print("\nALL MAPEDITOR API TESTS PASSED")


if __name__ == "__main__":
    main()
