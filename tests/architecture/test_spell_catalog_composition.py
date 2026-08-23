"""Import-direction gates for native and extension spell catalog composition."""

from __future__ import annotations

import ast
from pathlib import Path


_ROOT = Path(__file__).resolve().parents[2]


def test_native_spell_catalog_has_no_extension_dependency() -> None:
    """The native spell package cannot reach upward into extension content."""
    source_path = _ROOT / "dnd" / "spells" / "catalog_content.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imported_modules = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }

    assert not any(
        module == "dnd.extensions"
        or module.startswith("dnd.extensions.")
        for module in imported_modules
    )
