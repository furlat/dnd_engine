"""Architecture: a condition that can block a crossing declares the channels it blocks.

An undeclared (None) crossing predicate is consulted globally: every optical
ray checks it and FOV leaves its sparse path for every observer on the map.
"""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_crossing_predicates_declare_their_channels() -> None:
    undeclared = []
    for path in sorted((ROOT / "dnd").rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.ClassDef) or node.name == "SpatialConditionOwner":
                continue
            overrides = any(isinstance(item, ast.FunctionDef) and item.name == "blocks_crossing_between"
                            for item in node.body)
            declared = [item for item in node.body if isinstance(item, ast.AnnAssign)
                        and isinstance(item.target, ast.Name) and item.target.id == "crossing_channels"]
            if overrides and (not declared or ast.unparse(declared[0].value) == "None"):
                undeclared.append(f"{path.relative_to(ROOT)}:{node.lineno} {node.name}")
    assert undeclared == []
