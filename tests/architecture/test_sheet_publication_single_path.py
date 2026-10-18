"""Architecture: one sheet publisher, one path (plan E5).

The sheet is evaluated in one place, by the one publisher, which the session calls at the end of its
composition and of every operation. The sheet and initiative events have one writer each, and
publication (capture, projection, application, the client fold) never evaluates a live sheet.
"""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def calls(name: str) -> list[str]:
    """Every call of `name` in dnd/, as 'file:function'."""
    found = []
    for path in sorted((ROOT / "dnd").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for function in ast.walk(tree):
            if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for node in ast.walk(function):
                if isinstance(node, ast.Call) and (
                        isinstance(node.func, ast.Name) and node.func.id == name
                        or isinstance(node.func, ast.Attribute) and node.func.attr == name):
                    found.append(f"{path.relative_to(ROOT)}:{function.name}")
    return sorted(set(found))


def test_the_sheet_is_evaluated_only_by_its_publisher():
    assert calls("evaluate_actor_sheet") == ["dnd/actor_sheets.py:publish_actor_sheets"]


def test_the_publisher_runs_at_session_start_and_at_every_operation_end():
    assert calls("publish_actor_sheets") == ["dnd/player/session.py:publish_sheets"]
    assert calls("publish_sheets") == ["dnd/player/session.py:_operation", "dnd/player/session.py:_start_session"]


def test_sheet_and_initiative_events_have_one_writer_each():
    assert calls("ActorSheetEvent") == ["dnd/actor_sheets.py:publish_actor_sheets"]
    assert calls("InitiativeOrderChangedEvent") == ["dnd/encounter.py:publish_initiative_order"]


def test_publication_reads_no_live_sheet():
    importers = []
    for path in sorted((ROOT / "dnd" / "player").rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and node.module == "dnd.actor_sheets":
                importers.append(str(path.relative_to(ROOT)))
    assert importers == ["dnd/player/session.py"]
