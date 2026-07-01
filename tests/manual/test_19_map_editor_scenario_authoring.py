"""Manual Chapter 19 checks for map-editor and scenario-authoring payloads."""

import asyncio
import os
import tempfile
from typing import Any

import httpx

from dnd.controller import Controller
from dnd.core.base_block import BaseBlock
from dnd.core.base_conditions import BaseCondition, SpellProtectionRegistry
from dnd.core.base_object import BaseObject
from dnd.core.events import EventQueue
from dnd.core.gridmap import GridMap
from dnd.core.values import BaseValue
from dnd.encounter import Encounter
from dnd.entity import Entity
from server.event_server import app, sim


class ApiClient:
    """Synchronous wrapper over the real ASGI app for authoring examples."""

    def get(self, path, **kwargs):
        """Issue a GET request to the in-process app."""
        return asyncio.run(self._request("GET", path, **kwargs))

    def post(self, path, **kwargs):
        """Issue a POST request to the in-process app."""
        return asyncio.run(self._request("POST", path, **kwargs))

    def delete(self, path, **kwargs):
        """Issue a DELETE request to the in-process app."""
        return asyncio.run(self._request("DELETE", path, **kwargs))

    async def _request(self, method, path, **kwargs):
        """Run one request through HTTPX's ASGI transport."""
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://neurodragon.local",
        ) as client:
            return await client.request(method, path, **kwargs)


def reset_map_authoring_state() -> None:
    """Clear engine and server state for one map-authoring tutorial scene."""
    EventQueue.reset()
    EventQueue.set_combat_log_callback(None)
    EventQueue.set_perceiver_computer(None)
    EventQueue.set_revealed_computer(None)
    SpellProtectionRegistry.reset()
    BaseObject._registry.clear()
    BaseBlock._registry.clear()
    BaseCondition._registry.clear()
    BaseValue._registry.clear()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()
    Controller.clear_registry()
    Encounter.clear_registry()
    Encounter._combat_log_listeners.clear()
    GridMap.reset()
    sim.reset()


def tile_at(snapshot: dict[str, Any], x: int, y: int) -> dict[str, Any]:
    """Return one tile from a map-editor snapshot."""
    tile = next(
        (candidate for candidate in snapshot["tiles"] if candidate["x"] == x and candidate["y"] == y),
        None,
    )
    assert tile is not None
    return tile


def layer_cell(layer: dict[str, Any], x: int, y: int) -> dict[str, Any]:
    """Return one cell from a map-editor objective layer response."""
    cell = next(
        (candidate for candidate in layer["cells"] if candidate["x"] == x and candidate["y"] == y),
        None,
    )
    assert cell is not None
    return cell


def create_authoring_client() -> ApiClient:
    """Create an isolated in-process client for the authoring API examples."""
    reset_map_authoring_state()
    return ApiClient()


def create_tutorial_editor_map(client: ApiClient) -> dict[str, Any]:
    """Create the small scratch map used by map-authoring examples."""
    response = client.post(
        "/mapeditor/maps",
        json={
            "source": "scratch",
            "width": 4,
            "height": 3,
            "origin": [10, 20],
            "default_tile": "Floor",
            "default_light": 1,
        },
    )
    assert response.status_code == 200
    return response.json()


def patch_tutorial_room(client: ApiClient) -> dict[str, Any]:
    """Apply the tutorial wall and directional-border edits."""
    response = client.post(
        "/mapeditor/map/tiles",
        json={
            "tiles": [
                {"x": 11, "y": 21, "type": "Wall", "light_level": 4},
                {
                    "x": 12,
                    "y": 21,
                    "directional_channel": "movement",
                    "direction": "east",
                    "passable": False,
                },
            ],
        },
    )
    assert response.status_code == 200
    return response.json()


def place_tutorial_objects(client: ApiClient) -> tuple[dict[str, Any], dict[str, Any]]:
    """Place the tutorial door and wall torch."""
    door_response = client.post(
        "/mapeditor/map/objects",
        json={"catalog_id": "door", "position": [12, 21]},
    )
    torch_response = client.post(
        "/mapeditor/map/objects",
        json={"catalog_id": "wall_torch", "position": [13, 20], "options": {"lit": True}},
    )

    assert door_response.status_code == 200
    assert torch_response.status_code == 200
    return door_response.json(), torch_response.json()


def test_catalog_and_scratch_map_creation_define_the_authoring_palette(capsys) -> None:
    """The map editor exposes a catalog and creates entity-free scratch maps."""
    client = create_authoring_client()

    catalog = client.get("/mapeditor/catalog").json()
    snapshot = create_tutorial_editor_map(client)
    public_state = client.get("/state").json()
    entities = client.get("/entities").json()

    assert {"scratch", "forgotten_crypt_arena"} <= {entry["id"] for entry in catalog["presets"]}
    assert {"floor", "wall", "water", "difficult_terrain", "spike_zone"} <= {
        entry["id"] for entry in catalog["tiles"]
    }
    assert {"door", "wall_torch", "trap_lever"} <= {entry["id"] for entry in catalog["objects"]}
    assert {"healing_potion", "scroll_of_fireball", "torch"} <= {entry["id"] for entry in catalog["loot"]}

    assert snapshot["grid_bounds"] == {"min_x": 10, "min_y": 20, "max_x": 13, "max_y": 22}
    assert len(snapshot["tiles"]) == 12
    assert snapshot["floor_objects"] == []
    assert tile_at(snapshot, 10, 20)["light_level"] == 1
    assert entities == {"entities": []}
    assert public_state["entities"] == []
    assert public_state["encounter"] is None

    readout_lines = [
        (
            "catalog core: "
            f"presets={'yes' if {'scratch', 'forgotten_crypt_arena'} <= {entry['id'] for entry in catalog['presets']} else 'no'}, "
            f"tiles={'yes' if {'floor', 'wall', 'water', 'difficult_terrain', 'spike_zone'} <= {entry['id'] for entry in catalog['tiles']} else 'no'}, "
            f"objects={'yes' if {'door', 'wall_torch', 'trap_lever'} <= {entry['id'] for entry in catalog['objects']} else 'no'}, "
            f"loot={'yes' if {'healing_potion', 'scroll_of_fireball', 'torch'} <= {entry['id'] for entry in catalog['loot']} else 'no'}"
        ),
        f"scratch map: bounds={snapshot['grid_bounds']}, tiles={len(snapshot['tiles'])}, objects={len(snapshot['floor_objects'])}",
        (
            "origin tile: "
            f"name={tile_at(snapshot, 10, 20)['name']}, "
            f"light={tile_at(snapshot, 10, 20)['light_level']}"
        ),
        (
            "play state: "
            f"entities={len(public_state['entities'])}, "
            f"encounter={'none' if public_state['encounter'] is None else 'active'}, "
            f"entity_route={len(entities['entities'])}"
        ),
    ]
    expected_lines = [
        "catalog core: presets=yes, tiles=yes, objects=yes, loot=yes",
        "scratch map: bounds={'min_x': 10, 'min_y': 20, 'max_x': 13, 'max_y': 22}, tiles=12, objects=0",
        "origin tile: name=Floor, light=1",
        "play state: entities=0, encounter=none, entity_route=0",
    ]

    print("\n".join(readout_lines))

    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"


def test_tile_patches_describe_designer_edits(capsys) -> None:
    """Tile patches update terrain, light, and directional borders."""
    client = create_authoring_client()
    create_tutorial_editor_map(client)

    patched = patch_tutorial_room(client)
    wall_tile = tile_at(patched, 11, 21)
    doorway_tile = tile_at(patched, 12, 21)

    assert wall_tile["name"] == "Wall"
    assert wall_tile["walkable"] is False
    assert wall_tile["visible"] is False
    assert wall_tile["light_level"] == 4
    assert doorway_tile["name"] == "Floor"
    assert doorway_tile["directional_blocks_movement"]["east"] is True

    readout_lines = [
        (
            "wall patch: "
            f"name={wall_tile['name']}, "
            f"walkable={'yes' if wall_tile['walkable'] else 'no'}, "
            f"visible={'yes' if wall_tile['visible'] else 'no'}, "
            f"light={wall_tile['light_level']}"
        ),
        (
            "border patch: "
            f"tile={doorway_tile['name']}, "
            f"east_blocks_movement={'yes' if doorway_tile['directional_blocks_movement']['east'] else 'no'}"
        ),
        f"snapshot: bounds={patched['grid_bounds']}, tiles={len(patched['tiles'])}, objects={len(patched['floor_objects'])}",
    ]
    expected_lines = [
        "wall patch: name=Wall, walkable=no, visible=no, light=4",
        "border patch: tile=Floor, east_blocks_movement=yes",
        "snapshot: bounds={'min_x': 10, 'min_y': 20, 'max_x': 13, 'max_y': 22}, tiles=12, objects=0",
    ]

    print("\n".join(readout_lines))

    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"


def test_objects_and_objective_layers_describe_designer_edits(capsys) -> None:
    """Placed objects update map snapshots and objective layers."""
    client = create_authoring_client()
    create_tutorial_editor_map(client)
    patch_tutorial_room(client)

    door, torch = place_tutorial_objects(client)
    walkability = client.get("/mapeditor/map/walkability").json()
    visibility = client.get("/mapeditor/map/visibility").json()
    light = client.get("/mapeditor/map/light").json()

    assert door["name"] == "Door"
    assert door["position"] == [12, 21]
    assert door["state"]["blocks_movement"] is True
    assert door["state"]["is_open"] is False
    assert torch["name"] == "Wall Torch"
    assert torch["position"] == [13, 20]
    assert torch["state"]["is_lit"] is True

    assert layer_cell(walkability, 11, 21) == {"x": 11, "y": 21, "walkable": False, "blocker": "Wall"}
    assert layer_cell(walkability, 12, 21) == {"x": 12, "y": 21, "walkable": False, "blocker": "Door"}
    assert layer_cell(visibility, 11, 21) == {
        "x": 11,
        "y": 21,
        "blocks_visibility": True,
        "blocker": "Wall",
    }
    assert layer_cell(visibility, 12, 21) == {
        "x": 12,
        "y": 21,
        "blocks_visibility": True,
        "blocker": "Door",
    }
    assert layer_cell(light, 13, 20)["light_level"] == 4

    readout_lines = [
        (
            "placed door: "
            f"name={door['name']}, "
            f"position={door['position']}, "
            f"blocks={'yes' if door['state']['blocks_movement'] else 'no'}, "
            f"open={'yes' if door['state']['is_open'] else 'no'}"
        ),
        (
            "placed torch: "
            f"name={torch['name']}, "
            f"position={torch['position']}, "
            f"lit={'yes' if torch['state']['is_lit'] else 'no'}"
        ),
        (
            "walkability: "
            f"wall={layer_cell(walkability, 11, 21)['blocker']}, "
            f"door={layer_cell(walkability, 12, 21)['blocker']}"
        ),
        (
            "visibility: "
            f"wall={layer_cell(visibility, 11, 21)['blocker']}, "
            f"door={layer_cell(visibility, 12, 21)['blocker']}"
        ),
        f"light layer: torch_cell={layer_cell(light, 13, 20)['light_level']}",
    ]
    expected_lines = [
        "placed door: name=Door, position=[12, 21], blocks=yes, open=no",
        "placed torch: name=Wall Torch, position=[13, 20], lit=yes",
        "walkability: wall=Wall, door=Door",
        "visibility: wall=Wall, door=Door",
        "light layer: torch_cell=4",
    ]

    print("\n".join(readout_lines))

    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"


def test_object_deletion_updates_the_editor_snapshot(capsys) -> None:
    """Editor objects can be removed by UUID or by tile position."""
    client = create_authoring_client()
    create_tutorial_editor_map(client)
    door, torch = place_tutorial_objects(client)

    deleted_by_uuid = client.post(
        "/mapeditor/map/objects/delete",
        json={"object_uuid": door["uuid"]},
    )
    deleted_by_position = client.post(
        "/mapeditor/map/objects/delete",
        json={"position": torch["position"]},
    )

    assert deleted_by_uuid.status_code == 200
    assert [obj["name"] for obj in deleted_by_uuid.json()["floor_objects"]] == ["Wall Torch"]
    assert deleted_by_position.status_code == 200
    assert deleted_by_position.json()["floor_objects"] == []

    readout_lines = [
        (
            "delete by uuid: "
            f"status={deleted_by_uuid.status_code}, "
            f"remaining={[obj['name'] for obj in deleted_by_uuid.json()['floor_objects']]}"
        ),
        (
            "delete by position: "
            f"status={deleted_by_position.status_code}, "
            f"remaining={deleted_by_position.json()['floor_objects']}"
        ),
    ]
    expected_lines = [
        "delete by uuid: status=200, remaining=['Wall Torch']",
        "delete by position: status=200, remaining=[]",
    ]

    print("\n".join(readout_lines))

    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"


def test_save_load_roundtrip_restores_entity_free_map_state(capsys) -> None:
    """Saved editor maps round-trip tiles and reloadable object placements."""
    client = create_authoring_client()
    create_tutorial_editor_map(client)
    patch_tutorial_room(client)
    place_tutorial_objects(client)

    previous_save_dir = os.environ.get("DND_MAPEDITOR_SAVE_DIR")
    with tempfile.TemporaryDirectory() as save_dir:
        os.environ["DND_MAPEDITOR_SAVE_DIR"] = save_dir
        try:
            save_response = client.post(
                "/mapeditor/saves",
                json={"id": "tutorial_room", "name": "Tutorial Room", "overwrite": True},
            )
            document_response = client.get("/mapeditor/saves/tutorial_room")

            client.post(
                "/mapeditor/maps",
                json={"source": "scratch", "width": 1, "height": 1, "origin": [0, 0]},
            )
            loaded_response = client.post("/mapeditor/saves/tutorial_room/load")
            listed_response = client.get("/mapeditor/saves")
            deleted_response = client.delete("/mapeditor/saves/tutorial_room")
        finally:
            if previous_save_dir is None:
                os.environ.pop("DND_MAPEDITOR_SAVE_DIR", None)
            else:
                os.environ["DND_MAPEDITOR_SAVE_DIR"] = previous_save_dir

    save_payload = save_response.json()
    document = document_response.json()
    loaded = loaded_response.json()
    listed = listed_response.json()

    assert save_response.status_code == 200
    assert save_payload["id"] == "tutorial_room"
    assert save_payload["tile_count"] == 12
    assert save_payload["floor_object_count"] == 2
    assert document_response.status_code == 200
    assert document["schema_version"] == 1
    assert document["metadata"]["name"] == "Tutorial Room"
    assert {placement["catalog_id"] for placement in document["object_placements"]} == {"door", "wall_torch"}
    assert loaded_response.status_code == 200
    assert loaded["grid_bounds"] == {"min_x": 10, "min_y": 20, "max_x": 13, "max_y": 22}
    assert len(loaded["tiles"]) == 12
    assert {obj["name"] for obj in loaded["floor_objects"]} == {"Door", "Wall Torch"}
    assert listed["maps"][0]["id"] == "tutorial_room"
    assert deleted_response.status_code == 204

    readout_lines = [
        (
            "save result: "
            f"status={save_response.status_code}, "
            f"id={save_payload['id']}, "
            f"tiles={save_payload['tile_count']}, "
            f"objects={save_payload['floor_object_count']}"
        ),
        (
            "document: "
            f"schema={document['schema_version']}, "
            f"name={document['metadata']['name']}, "
            f"placements={sorted({placement['catalog_id'] for placement in document['object_placements']})}"
        ),
        (
            "loaded map: "
            f"bounds={loaded['grid_bounds']}, "
            f"tiles={len(loaded['tiles'])}, "
            f"objects={sorted({obj['name'] for obj in loaded['floor_objects']})}"
        ),
        (
            "save list/delete: "
            f"first={listed['maps'][0]['id']}, "
            f"delete_status={deleted_response.status_code}"
        ),
    ]
    expected_lines = [
        "save result: status=200, id=tutorial_room, tiles=12, objects=2",
        "document: schema=1, name=Tutorial Room, placements=['door', 'wall_torch']",
        (
            "loaded map: bounds={'min_x': 10, 'min_y': 20, 'max_x': 13, 'max_y': 22}, "
            "tiles=12, objects=['Door', 'Wall Torch']"
        ),
        "save list/delete: first=tutorial_room, delete_status=204",
    ]

    print("\n".join(readout_lines))

    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"


def test_preset_map_and_authoring_handoff_clear_combat_state(capsys) -> None:
    """Preset maps load authoring space and editor creation clears combat."""
    client = create_authoring_client()

    preset_response = client.post(
        "/mapeditor/maps",
        json={"source": "preset", "preset_id": "forgotten_crypt_arena"},
    )
    preset = preset_response.json()
    preset_state = client.get("/state").json()
    object_names = [obj["name"] for obj in preset["floor_objects"]]

    assert preset_response.status_code == 200
    assert preset["grid_bounds"] == {"min_x": 0, "min_y": 0, "max_x": 14, "max_y": 14}
    assert len(preset["tiles"]) == 225
    assert object_names.count("Directional Wall") == 8
    assert object_names.count("Door") == 1
    assert object_names.count("Potion of Healing") == 2
    assert object_names.count("Wall Torch") == 2
    assert object_names.count("Trap Lever") == 1
    assert Entity.get_all_entities() == []
    assert sim.encounter is None
    assert preset_state["entities"] == []
    assert preset_state["encounter"] is None

    start_response = client.post("/simulation/start-human", params={"character_class": "fighter"})
    assert start_response.status_code == 200
    assert sim.encounter is not None
    assert Entity.get_all_entities()
    started_entities = len(Entity.get_all_entities())
    started_encounter = sim.encounter is not None

    editor_response = client.post(
        "/mapeditor/maps",
        json={"source": "scratch", "width": 2, "height": 2, "origin": [0, 0]},
    )
    public_state = client.get("/state").json()

    assert editor_response.status_code == 200
    assert editor_response.json()["grid_bounds"] == {"min_x": 0, "min_y": 0, "max_x": 1, "max_y": 1}
    assert Entity.get_all_entities() == []
    assert sim.encounter is None
    assert public_state["entities"] == []
    assert public_state["encounter"] is None

    readout_lines = [
        (
            "preset map: "
            f"status={preset_response.status_code}, "
            f"bounds={preset['grid_bounds']}, "
            f"tiles={len(preset['tiles'])}"
        ),
        (
            "preset objects: "
            f"walls={object_names.count('Directional Wall')}, "
            f"doors={object_names.count('Door')}, "
            f"potions={object_names.count('Potion of Healing')}, "
            f"torches={object_names.count('Wall Torch')}, "
            f"levers={object_names.count('Trap Lever')}"
        ),
        (
            "preset play state: "
            f"entities={len(preset_state['entities'])}, "
            f"encounter={'none' if preset_state['encounter'] is None else 'active'}"
        ),
        (
            "running game: "
            f"status={start_response.status_code}, "
            f"entities={started_entities}, "
            f"encounter={'yes' if started_encounter else 'no'}"
        ),
        (
            "return to editor: "
            f"status={editor_response.status_code}, "
            f"bounds={editor_response.json()['grid_bounds']}, "
            f"entities={len(public_state['entities'])}, "
            f"encounter={'none' if public_state['encounter'] is None else 'active'}"
        ),
    ]
    expected_lines = [
        "preset map: status=200, bounds={'min_x': 0, 'min_y': 0, 'max_x': 14, 'max_y': 14}, tiles=225",
        "preset objects: walls=8, doors=1, potions=2, torches=2, levers=1",
        "preset play state: entities=0, encounter=none",
        "running game: status=200, entities=4, encounter=yes",
        "return to editor: status=200, bounds={'min_x': 0, 'min_y': 0, 'max_x': 1, 'max_y': 1}, entities=0, encounter=none",
    ]

    print("\n".join(readout_lines))

    assert readout_lines == expected_lines
    assert capsys.readouterr().out == "\n".join(expected_lines) + "\n"
