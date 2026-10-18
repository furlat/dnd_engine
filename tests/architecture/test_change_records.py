"""Change records have one producer and one fold (plan EVENT_NATIVE_PUBLICATION §4, §8 Q4).

Static architecture checks, not gameplay evidence: an actor change is built by one dispatch over event
kinds and folded by one function; a keyed tile change is written by its writers, refilled at completion
and folded by one function. Records are data, and the engine fold modules import nothing from the player
layer.
"""

from __future__ import annotations

import ast
from functools import cache
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOTS = ("dnd", "server", "services", "custom_ai", "devtools")
RECORDS = {
    "dnd/types/actor_facts.py": ("ActorFieldValues", "HeldItem", "ItemResources", "ActorFactChange"),
    "dnd/types/event_facts.py": ("KeyedTileFields", "KeyedResidueChange", "KeyedTileChange"),
}


@cache
def _modules() -> dict[str, ast.Module]:
    return {path.relative_to(REPOSITORY_ROOT).as_posix(): ast.parse(path.read_text(encoding="utf-8"))
            for root in SOURCE_ROOTS for path in (REPOSITORY_ROOT / root).rglob("*.py")}


def _calls(name: str, keyword: str | None = None) -> set[str]:
    """The modules calling `name` (with `keyword`, when given)."""
    found: set[str] = set()
    for module, tree in _modules().items():
        for call in ast.walk(tree):
            if not isinstance(call, ast.Call):
                continue
            called = (call.func.id if isinstance(call.func, ast.Name)
                      else call.func.attr if isinstance(call.func, ast.Attribute) else None)
            if called == name and (keyword is None or any(row.arg == keyword for row in call.keywords)):
                found.add(module)
    return found


def _defined(name: str) -> set[str]:
    return {module for module, tree in _modules().items() for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == name}


def test_actor_changes_have_one_producer_and_one_fold() -> None:
    assert _defined("actor_fact_change") == _defined("apply_actor_fact_change") == {"dnd/actor_projection.py"}
    assert (_calls("ActorFactChange")) == {"dnd/actor_projection.py"}
    # Computed once by the shared fold, which seat and presentation folds read; the AI folds its own.
    assert (_calls("actor_fact_change")) == {"dnd/player/capture.py", "dnd/ai/runtime/knowledge_reduction.py"}
    assert (_calls("apply_actor_fact_change")) == {"dnd/player/actor_projection.py",
                                                      "dnd/ai/runtime/knowledge_reduction.py"}
    # The one copy of a record: the shared fold's E2 deferral of a condition's item after-value (E3-bodies).
    assert (_calls("replace", keyword="replaced_item")) == {"dnd/player/capture.py"}


def test_keyed_tile_changes_have_their_writers_and_one_fold() -> None:
    assert (_calls("KeyedTileChange")) == {"dnd/residues.py", "dnd/spatial/area_conditions.py",
                                              "dnd/core/gridmap.py"}
    assert _defined("apply_keyed_tile_change") == {"dnd/world_facts.py"}
    assert (_calls("apply_keyed_tile_change")) == {"dnd/world_facts.py"}


def test_change_records_are_data() -> None:
    for module, names in RECORDS.items():
        classes = {node.name: node for node in _modules()[module].body if isinstance(node, ast.ClassDef)}
        for name in names:
            for member in classes[name].body[1:]:  # after the docstring
                assert isinstance(member, ast.AnnAssign) or (
                    isinstance(member, ast.Assign) and [target.id for target in member.targets
                                                        if isinstance(target, ast.Name)] == ["model_config"]), name


def test_the_engine_fold_imports_no_player_layer() -> None:
    for module in ("dnd/actor_projection.py", "dnd/types/actor_facts.py", "dnd/types/event_facts.py",
                   "dnd/world_facts.py", *(name for name in _modules() if name.startswith("dnd/ai/"))):
        tree = _modules()[module]
        imported = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module}
        imported |= {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
        assert not {name for name in imported if name == "dnd.player" or name.startswith("dnd.player.")}, module
