"""Architecture: every zone turn trigger runs at EXECUTION (plan PB3 M; human Q7).

EXECUTION fires before the turn's auto-stand, duration advance and action
reset, so a creature knocked prone by a turn-start save still stands that turn
and "until your next turn" effects still apply to the save. One convention for
every zone, declared where the zone builds its turn handler.
"""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOOKS = {"_create_zone_turn_start_handler", "_create_zone_turn_end_handler"}
TURN_EVENTS = {"TURN_START", "TURN_END"}


def _attributes(call: ast.Call) -> set[tuple[str, str]]:
    values = [*call.args, *(keyword.value for keyword in call.keywords)]
    return {(value.value.id, value.attr) for value in values
            if isinstance(value, ast.Attribute) and isinstance(value.value, ast.Name)}


def _misphased_turn_calls(path: Path) -> list[str]:
    found: list[str] = []
    for hook in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if not (isinstance(hook, ast.FunctionDef) and hook.name in HOOKS):
            continue
        for call in ast.walk(hook):
            if not isinstance(call, ast.Call):
                continue
            attributes = _attributes(call)
            if any(("EventType", name) in attributes for name in TURN_EVENTS) and (
                    ("EventPhase", "EXECUTION") not in attributes):
                found.append(f"{path.relative_to(ROOT)}:{call.lineno} {hook.name}")
    return found


def test_zone_turn_triggers_run_at_execution() -> None:
    assert sorted(found for path in (ROOT / "dnd").rglob("*.py")
                  for found in _misphased_turn_calls(path)) == []
