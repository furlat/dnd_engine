"""Import-direction gates for native and extension spell catalog composition."""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path


_ROOT = Path(__file__).resolve().parents[2]


def test_content_bootstrap_and_composed_spell_catalog_cold_start() -> None:
    """A fresh process must not cycle through extensions while dnd.spells loads."""
    script = """
from dnd.content_system.bootstrap import bootstrap_content_system
from server.spell_catalog import build_spell_catalog
loaded = bootstrap_content_system(pack_roots=())
catalog = build_spell_catalog()
assert len(loaded.registry.declarations) > 0
assert any(row.id == "aegis_spark" for row in catalog.spells)
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert result.returncode == 0, result.stderr


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
