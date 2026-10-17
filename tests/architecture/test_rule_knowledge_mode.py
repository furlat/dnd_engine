"""Architecture: admission reads the world with the scan's knowledge (plan §14.3b, Q-W2).

Discovery and preview build a subjective scan (what the actor perceives);
execution builds an objective one. A rule or helper that takes the scan must
pass that knowledge on, so the available-actions list cannot reveal what the
actor does not perceive.
"""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TREES = {path: ast.parse(path.read_text(encoding="utf-8")) for path in sorted((ROOT / "dnd").rglob("*.py"))}


def _functions():
    for path, tree in TREES.items():
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                yield path, node


def _parameters(node: ast.FunctionDef) -> list[str]:
    return [argument.arg for argument in node.args.args + node.args.kwonlyargs]


def _callee(call: ast.Call) -> str | None:
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return call.func.id if isinstance(call.func, ast.Name) else None


def _mode_taking_names() -> set[str]:
    names: dict[str, set[bool]] = {}
    for _, node in _functions():
        names.setdefault(node.name, set()).add("subjective" in _parameters(node))
    return {name for name, modes in names.items() if modes == {True}}


def test_function_names_agree_on_taking_a_knowledge_mode() -> None:
    """A name either always takes `subjective` or never does, so the checks below are exact."""
    names: dict[str, set[bool]] = {}
    for _, node in _functions():
        names.setdefault(node.name, set()).add("subjective" in _parameters(node))
    assert sorted(name for name, modes in names.items() if len(modes) > 1) == []


def test_scan_readers_pass_the_scan_knowledge_on() -> None:
    mode_taking = _mode_taking_names()
    violations = []
    for path, node in _functions():
        parameters = _parameters(node)
        if "scan" not in parameters:
            continue
        where = f"{path.relative_to(ROOT)}:{node.lineno} {node.name}"
        if "subjective" in parameters:
            violations.append(f"{where} takes both a scan and its own knowledge mode")
        for call in ast.walk(node):
            if not isinstance(call, ast.Call):
                continue
            callee = _callee(call)
            mode = {keyword.arg: ast.unparse(keyword.value) for keyword in call.keywords}.get("subjective")
            if callee in mode_taking and mode != "scan.subjective":
                violations.append(f"{where}:{call.lineno} {callee}(subjective={mode})")
            if callee == "get_entities_at" and node.name != "cell_occupied":
                violations.append(f"{where}:{call.lineno} reads actual occupancy; use cell_occupied(scan, cell)")
    assert violations == []


def test_every_scan_states_its_knowledge() -> None:
    unstated = []
    for path, tree in TREES.items():
        for call in ast.walk(tree):
            if isinstance(call, ast.Call) and _callee(call) == "action_scan":
                if "subjective" not in {keyword.arg for keyword in call.keywords}:
                    unstated.append(f"{path.relative_to(ROOT)}:{call.lineno}")
    assert unstated == []
