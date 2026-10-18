"""A walk group's golden vectors fold to their expected client values (`devtools/fold_vectors_groups.py`)."""

import json
from uuid import UUID
from pathlib import Path

import pytest
from pydantic import TypeAdapter

from devtools.fold_vectors_groups import DIRECTORY, GENERATION, documents
from dnd.player.facts import PlayerLineage, PlayerState, PlayerWorld, WorldUpdate
from dnd.player.reduction import lineage_branch, reduce_lineage
from dnd.player.world_reduction import fold_world_update

VECTORS = sorted(DIRECTORY.glob("*.json"))
WORLD = PlayerWorld(battlefield_id="vectors", battlefield_name="Vectors", bounds=(0, 0, 9, 9), width=10, height=10)


def test_the_vector_files_are_their_written_source():
    assert {path.name: path.read_text() for path in VECTORS} == documents()


@pytest.mark.parametrize("path", VECTORS, ids=[path.stem for path in VECTORS])
def test_a_group_folds_its_roots_in_native_order(path: Path):
    vector = json.loads(path.read_text())
    group = TypeAdapter(PlayerLineage).validate_json(json.dumps(vector["group"]))
    client = PlayerState(generation=GENERATION, observer_uuid=UUID(vector["observers"][0]), world=WORLD)
    fold_world_update(client, TypeAdapter(WorldUpdate).validate_json(json.dumps(vector["initial"])))
    after = reduce_lineage(client, group)
    assert sorted(str(identity) for identity in after.objects) == vector["expected"]["objects"]
    assert group.root is not None
    branch = lineage_branch(group, group.events[group.root])
    assert [row.occurrence for row in branch.events] == vector["expected"]["root_branch_occurrences"]
