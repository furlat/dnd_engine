"""Architecture: only GridMap touches GridMap's private state (plan R6, P1/P2).

Owners commit spatial state through GridMap's public owner API, so revision
bumps and cache invalidation always happen at the write.
"""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _private_gridmap_accesses(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: list[str] = []
    for scope in ast.walk(tree):
        if not isinstance(scope, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        bound = {target.id for node in ast.walk(scope) if isinstance(node, ast.Assign)
            and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name)
            and node.value.func.id == "get_map"
            for target in node.targets if isinstance(target, ast.Name)}
        for node in ast.walk(scope):
            if not (isinstance(node, ast.Attribute) and node.attr.startswith("_")
                    and not node.attr.startswith("__")):
                continue
            value = node.value
            if ((isinstance(value, ast.Call) and isinstance(value.func, ast.Name) and value.func.id == "get_map")
                    or (isinstance(value, ast.Name) and value.id in bound)):
                found.append(f"{path.relative_to(ROOT)}:{node.lineno} {node.attr}")
    return found


def test_no_private_gridmap_access_outside_gridmap() -> None:
    accesses = sorted({access for path in (ROOT / "dnd").rglob("*.py")
        if path.name != "gridmap.py" for access in _private_gridmap_accesses(path)})
    assert accesses == []
