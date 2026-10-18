"""The schema-16 world golden vectors fold to their expected client worlds (plan §3.3-§3.5).

Each file of `sdk/protocol/fold-vectors/world/` is a seat's audience and a sequence of received world updates with
the client world expected after each, written by hand (`devtools/fold_vectors_world.py`). Godot folds the same files.
"""

import json
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import TypeAdapter

from devtools.fold_vectors_world import DIRECTORY, documents
from dnd.player.audience import PlayerAudience
from dnd.player.facts import ObjectRow, PlayerState, PlayerWorld, TileFieldUpdate, WorldUpdate
from dnd.player.world_reduction import fold_world_update

UPDATE = TypeAdapter(WorldUpdate)
VECTORS = sorted(DIRECTORY.glob("*.json"))
GENERATION = UUID("00000000-0000-4000-8000-00000000f000")
WORLD = PlayerWorld(battlefield_id="vectors", battlefield_name="Vectors", bounds=(0, 0, 9, 9), width=10, height=10)


def seat(observers: list[str]) -> PlayerState:
    """An empty client of a seat with these observers."""
    identities = tuple(UUID(observer) for observer in observers)
    return PlayerState(generation=GENERATION, observer_uuid=identities[0], world=WORLD,
        audience=PlayerAudience(controlled=(), observers=identities, revision=0))


ONE = [str(UUID("00000000-0000-4000-8000-00000000000a"))]
TWO = [*ONE, str(UUID("00000000-0000-4000-8000-00000000000b"))]


def client_world_view(memory: PlayerState) -> dict:
    """What the client holds of the world, in the vectors' expected shape."""
    return {
        "tiles": {f"{x},{y}": {"tile": str(tile.tile_uuid), "walking_cost": tile.walking_cost,
                               "blocks_optics": tile.blocks_optics, "resolved_light": tile.resolved_light.value,
                               "conditions": list(tile.condition_names),
                               "residues": {row.residue_id: {"amount": row.amount,
                                                             "contributions": len(row.contributions)}
                                            for row in tile.residues}}
                  for (x, y), tile in memory.tiles.items()},
        "objects": {str(identity): {"position": list(obj.placement.position),
                                    "members": memory.object_members[identity], "name": obj.item.name,
                                    "is_open": obj.item.is_open,
                                    "faces": {str(row.condition_uuid): [face.value for face in row.faces]
                                              for row in obj.item.surface_residues},
                                    "suppressions": {str(row.provider_uuid): [list(cell) for cell in row.positions]
                                                     for row in obj.item.construction_suppressions},
                                    "contents": [str(item.item_uuid) for item in obj.contained_items]
                                        if obj.contained_items is not None else None}
                    for identity, obj in memory.objects.items()},
        "connectors": sorted(str(identity) for identity in memory.connectors),
    }


def _fold(memory: PlayerState, step: dict) -> PlayerState:
    fold_world_update(memory, UPDATE.validate_json(json.dumps(step["update"])))
    return memory


def test_the_vector_files_are_their_written_source():
    assert {path.name: path.read_text() for path in VECTORS} == documents()


@pytest.mark.parametrize("path", VECTORS, ids=[path.stem for path in VECTORS])
def test_vector_folds_to_its_expected_worlds(path: Path):
    vector = json.loads(path.read_text())
    memory = seat(vector["observers"])
    for index, step in enumerate(vector["steps"]):
        _fold(memory, step)
        assert client_world_view(memory) == step["expected"], f"step {index}"


def _vector(name: str) -> dict:
    return json.loads((DIRECTORY / f"{name}.json").read_text())


def test_a_seat_with_several_observers_must_name_each_object_rows_members():
    step = _vector("w1_an_object_moved_unseen_is_dropped_when_its_cell_reenters")["steps"][0]
    with pytest.raises(ValueError, match="names the members of each object row"):
        _fold(seat(TWO), step)


def test_keyed_rows_require_what_they_change():
    first = _vector("w1_an_object_moved_unseen_is_dropped_when_its_cell_reenters")["steps"][0]
    with pytest.raises(ValueError, match="already known tile"):
        fold_world_update(seat(ONE), WorldUpdate(occurrence=0, tile_changes=(
            TileFieldUpdate(position=(9, 9), changes={"walking_cost": 2}),)))
    with pytest.raises(ValueError, match="names an object the client holds"):
        fold_world_update(seat(ONE), WorldUpdate(occurrence=0, objects=(
            ObjectRow(item_uuid=UPDATE.validate_json(json.dumps(first["update"])).objects[0].item_uuid, members=1),)))
    without_look = {**first["update"], "object_looks": []}
    with pytest.raises(ValueError, match="first row requires its look"):
        _fold(seat(ONE), {"update": without_look})
