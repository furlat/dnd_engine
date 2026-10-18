"""Change records have one producer and one fold (plan EVENT_NATIVE_PUBLICATION §4, §8 Q4).

Static architecture checks, not gameplay evidence: an actor change is built by one dispatch over event
kinds and folded by one function; a keyed tile change is written by its writers, refilled at completion
and folded by one function. The engine fold module imports nothing from the player layer.
"""

from __future__ import annotations

import ast
from functools import cache
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOTS = ("dnd", "server", "services", "custom_ai", "devtools")


@cache
def _modules() -> dict[str, ast.Module]:
    return {path.relative_to(REPOSITORY_ROOT).as_posix(): ast.parse(path.read_text(encoding="utf-8"))
            for root in SOURCE_ROOTS for path in (REPOSITORY_ROOT / root).rglob("*.py")}


def _called_in(name: str) -> dict[str, set[str]]:
    """For each module, the enclosing top-level functions (or `<module>`) that call `name`."""
    found: dict[str, set[str]] = {}
    for module, tree in _modules().items():
        for node in tree.body:
            owner = node.name if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) else "<module>"
            for call in ast.walk(node):
                if (isinstance(call, ast.Call)
                        and (isinstance(call.func, ast.Name) and call.func.id == name
                             or isinstance(call.func, ast.Attribute) and call.func.attr == name)):
                    found.setdefault(module, set()).add(owner)
    return found


def _defined(name: str) -> set[str]:
    return {module for module, tree in _modules().items() for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == name}


def test_actor_changes_have_one_producer_and_one_fold() -> None:
    assert _defined("actor_fact_change") == {"dnd/actor_projection.py"}
    assert _called_in("ActorFactChange") == {"dnd/actor_projection.py": {"actor_fact_change"}}
    # Computed once by the shared fold; seat and presentation folds read its records. The AI folds its own.
    assert _called_in("actor_fact_change") == {
        "dnd/player/capture.py": {"advance_capture"},
        "dnd/ai/runtime/knowledge_reduction.py": {"AIKnowledge"},
    }
    assert _defined("apply_actor_fact_change") == {"dnd/actor_projection.py"}
    assert _called_in("apply_actor_fact_change") == {
        "dnd/player/actor_projection.py": {"apply_presented_change"},
        "dnd/ai/runtime/knowledge_reduction.py": {"AIKnowledge"},
    }
    # The folds that preceded the records are gone, not kept beside them.
    for retired in ("apply_actor_fact", "remove_previous_item_holdings", "apply_stats"):
        assert not _defined(retired), retired


def test_keyed_tile_changes_have_their_writers_and_one_fold() -> None:
    assert set(_called_in("KeyedTileChange")) == {
        "dnd/residues.py", "dnd/spatial/area_conditions.py", "dnd/core/gridmap.py"}
    assert _called_in("KeyedTileChange")["dnd/core/gridmap.py"] == {"GridMap"}
    assert _defined("apply_keyed_tile_change") == {"dnd/world_facts.py"}
    assert _called_in("apply_keyed_tile_change") == {"dnd/world_facts.py": {"apply_world_fact"}}
    # Whole tile rows left the tiles fact.
    assert not [path for path in (REPOSITORY_ROOT / "dnd").rglob("*.py") if "tile_states" in path.read_text(encoding="utf-8")]


def test_the_engine_fold_imports_no_player_layer() -> None:
    for module in ("dnd/actor_projection.py", "dnd/types/actor_facts.py", "dnd/world_facts.py",
                   "dnd/ai/runtime/knowledge_reduction.py"):
        imported = {node.module for node in ast.walk(_modules()[module])
                    if isinstance(node, ast.ImportFrom) and node.module is not None}
        imported |= {alias.name for node in ast.walk(_modules()[module]) if isinstance(node, ast.Import)
                     for alias in node.names}
        assert not {name for name in imported if name == "dnd.player" or name.startswith("dnd.player.")}, module
