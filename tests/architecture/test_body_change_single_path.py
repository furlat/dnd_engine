"""Architecture: the bodies family has one conversion, one disclosure table and one builder per record
(EVENT_NATIVE_PUBLICATION_PLAN_2026-10-18 §3.3-§3.5; coordinator ruling (a) on E2's record).

Static checks, not gameplay evidence: an event's actor change becomes rows in exactly one function, run by the
session's one actor fold; every change field has a disclosure; the actor change fact and the entering body
record are built only by the bodies module.
"""

import ast
from dataclasses import fields
from functools import cache
from pathlib import Path

from dnd.player.bodies import DISCLOSURE
from dnd.types.actor_facts import ChangeField
from dnd.types.item_parts import ItemState

ROOT = Path(__file__).resolve().parents[2]


@cache
def _modules() -> dict[str, ast.Module]:
    return {path.relative_to(ROOT).as_posix(): ast.parse(path.read_text(encoding="utf-8"))
            for root in ("dnd", "server", "devtools") for path in (ROOT / root).rglob("*.py")}


def _calls(name: str) -> set[str]:
    """Each 'module:function' calling `name`."""
    found = set()
    for module, tree in _modules().items():
        for function in ast.walk(tree):
            if isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for call in ast.walk(function):
                    if isinstance(call, ast.Call) and (
                            isinstance(call.func, ast.Name) and call.func.id == name
                            or isinstance(call.func, ast.Attribute) and call.func.attr == name):
                        found.add(f"{module}:{function.name}")
    return found


def test_every_change_field_has_one_disclosure():
    assert set(DISCLOSURE) == set(ChangeField)


def test_one_conversion_run_once_per_event_by_the_session_actor_fold():
    defined = {module for module, tree in _modules().items() for node in ast.walk(tree)
               if isinstance(node, ast.FunctionDef) and node.name == "change_rows"}
    assert defined == {"dnd/player/bodies.py"}
    assert _calls("change_rows") == {"dnd/player/projection.py:_fold_actors"}


def test_the_bodies_module_builds_the_actor_change_fact_and_the_entering_body():
    assert {row.split(":")[0] for row in _calls("ActorChangeFact")} <= {"dnd/player/bodies.py",
        "devtools/fold_vectors_bodies.py"}
    assert {row.split(":")[0] for row in _calls("BodyRecord")} <= {"dnd/player/bodies.py",
        "devtools/fold_vectors_bodies.py"}
    assert {row.split(":")[0] for row in _calls("change_fact")} == {"dnd/player/projection.py"}


def test_the_session_actor_fold_has_one_writer():
    """The session's actors are written by `_fold_actors` alone, through the shared fold functions; nothing else in
    projection writes an actors mapping."""
    folds = {"dnd/player/projection.py:_fold_actors"}
    assert _calls("fold_birth") == folds
    assert _calls("fold_completed_actors") == folds
    writes = []
    for function in ast.walk(_modules()["dnd/player/projection.py"]):
        if not isinstance(function, ast.FunctionDef):
            continue
        for node in ast.walk(function):
            targets = (node.targets if isinstance(node, (ast.Assign, ast.Delete))
                       else [node.target] if isinstance(node, (ast.AugAssign, ast.AnnAssign)) else [])
            writes += [function.name for target in targets if isinstance(target, ast.Subscript)
                       and isinstance(target.value, ast.Attribute) and target.value.attr == "actors"]
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr in ("pop", "update", "clear", "setdefault", "__setitem__")
                    and isinstance(node.func.value, ast.Attribute) and node.func.value.attr == "actors"):
                writes.append(function.name)
    assert writes == []


def test_an_item_state_row_compares_every_item_state_field():
    """`ItemStateRow` changes are written field by field: the comparison names each `ItemState` field once."""
    function = next(node for node in ast.walk(_modules()["dnd/player/bodies.py"])
                    if isinstance(node, ast.FunctionDef) and node.name == "_state_changes")
    written: list[str] = [node.slice.value for node in ast.walk(function) if isinstance(node, ast.Subscript)
               and isinstance(node.value, ast.Name) and node.value.id == "changes"
               and isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str)]
    assert sorted(written) == sorted(row.name for row in fields(ItemState))
