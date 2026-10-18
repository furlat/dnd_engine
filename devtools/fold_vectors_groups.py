"""Golden vectors of a walk group's client fold: roots whose versions interleave arrive as one group.

`capture_context` makes the roots of an operation whose versions interleave one walk group: a root completing
inside another root's execution is published with it, as one `PlayerLineage` whose nodes are in native order,
named by the root completing last. The nested root is a parentless lineage inside the root's interval. The client
folds the group's nodes in occurrence order, so it takes the changes in the order they happened, and a branch of
the root keeps the nested lineage (`lineage_branch`).

The expected values are written here by hand from those rules, never dumped from the fold; Godot folds the same
files (`sdk/protocol/fold-vectors/groups/*.json`). `tests/player/test_group_fold_vectors.py` folds them with the
reference fold.

    PYTHONPATH=. python devtools/fold_vectors_groups.py   # write the files (the vector test checks they are current)
"""

import argparse
import json
from pathlib import Path
from uuid import UUID

from pydantic import TypeAdapter

from devtools.fold_vectors_world import A, BOX, entering, item, look_and_row, placement, tile
from dnd.player.facts import PlayerLineage, PlayerNode, VersionRows, WorldUpdate
from dnd.types.event_facts import EventPhase

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / "sdk" / "protocol" / "fold-vectors" / "groups"
GENERATION = UUID("00000000-0000-4000-8000-00000000f000")
UPDATE = TypeAdapter(WorldUpdate)
LINEAGE = TypeAdapter(PlayerLineage)


def node(occurrence: int, lineage: int, phase: EventPhase, *, parent: int | None = None,
         children: tuple[int, ...] = ()) -> PlayerNode:
    return PlayerNode(occurrence=occurrence, lineage=lineage, parent_lineage=parent, children_lineages=children,
        phase=phase)


def vectors() -> dict[str, dict]:
    floor = tuple(tile(position) for position in ((0, 0), (1, 0), (2, 0)))
    box_look, box_row = look_and_row(item(BOX, "Box"), placement(BOX, (1, 0)))
    # Root lineage 1 runs over occurrences 1-4; lineage 3, a root of its own, starts and completes inside it.
    group = PlayerLineage(generation=GENERATION, observer_uuid=A, lineage=1, root=3,
        events=(node(1, 1, EventPhase.EXECUTION, children=(2,)),
                node(2, 2, EventPhase.COMPLETION, parent=1),
                node(3, 3, EventPhase.COMPLETION),
                node(4, 1, EventPhase.COMPLETION, children=(2,))),
        version_rows=VersionRows(occurrences=(1, 2, 3, 4), lineages=(1, 2, 3, 1)), start_cursor=1, end_cursor=5,
        world_updates=(WorldUpdate(occurrence=2, object_looks=(box_look,), objects=(box_row,)),
                       WorldUpdate(occurrence=3, objects_removed=(BOX,))))
    return {
        "g1_a_nested_root_folds_inside_its_group_in_native_order": {
            "rule": "Roots whose versions interleave arrive as one group, in native order: the box the root places "
                    "at occurrence 2 is removed by the nested root at occurrence 3, so the client ends without it "
                    "(folded per root in completion order, the removal would precede the placement). A branch "
                    "of the root keeps the parentless nested lineage inside its interval.",
            "initial": UPDATE.dump_python(entering(0, floor), mode="json"),
            "group": LINEAGE.dump_python(group, mode="json"),
            "expected": {"objects": [], "root_branch_occurrences": [1, 2, 3, 4]},
        },
    }


def documents() -> dict[str, str]:
    """Each vector file's text."""
    return {f"{name}.json": json.dumps({"name": name, "observers": [str(A)], **vector}, indent=1) + "\n"
            for name, vector in vectors().items()}


def main() -> None:
    argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter).parse_args()
    wanted = documents()
    DIRECTORY.mkdir(parents=True, exist_ok=True)
    for path in DIRECTORY.glob("*.json"):
        if path.name not in wanted:
            path.unlink()
    for name, text in wanted.items():
        (DIRECTORY / name).write_text(text)


if __name__ == "__main__":
    main()
