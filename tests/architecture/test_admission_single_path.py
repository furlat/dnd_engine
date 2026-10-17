"""Architecture: one legality path (plan §14.3b).

The shared admission checks live once on BaseAction. An action adds its own
rule through `rule_error`; it never replaces the shared checks, so a forgotten
`super()` cannot skip them.
"""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_no_action_overrides_the_shared_admission_checks() -> None:
    overrides = []
    for path in sorted((ROOT / "dnd").rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ClassDef) and node.name != "BaseAction":
                overrides.extend(f"{path.relative_to(ROOT)}:{item.lineno} {node.name}" for item in node.body
                                 if isinstance(item, ast.FunctionDef) and item.name == "_admission_error")
    assert overrides == []


FAMILY_BASES = {"BaseAction", "SpellAction"}


def test_only_action_family_bases_add_source_admission() -> None:
    """A concrete action states its own rule in `rule_error`, not in the family hook."""
    definers = []
    for path in sorted((ROOT / "dnd").rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ClassDef) and node.name not in FAMILY_BASES:
                definers.extend(f"{path.relative_to(ROOT)}:{item.lineno} {node.name}" for item in node.body
                                if isinstance(item, ast.FunctionDef) and item.name == "_family_admission_error")
    assert definers == []
