"""Paused HTTP/catalog composition; run explicitly with tests/paused_server."""
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


