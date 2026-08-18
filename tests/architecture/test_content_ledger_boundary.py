"""The optional content ledger stays cold and outside construction paths."""

import json
from pathlib import Path
import subprocess
import sys

from dnd.content.content_ledger import CONTENT_LEDGER, ContentLedgerKind


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_content_ledger_has_the_exact_direct_domain_inventory() -> None:
    counts = {
        kind: sum(row.kind is kind for row in CONTENT_LEDGER)
        for kind in ContentLedgerKind
    }
    assert counts == {
        ContentLedgerKind.SPECIES: 9,
        ContentLedgerKind.SPECIES_VARIANT: 4,
        ContentLedgerKind.BACKGROUND: 2,
        ContentLedgerKind.CLASS: 3,
        ContentLedgerKind.SUBCLASS: 3,
        ContentLedgerKind.PREMADE: 4,
        ContentLedgerKind.MONSTER: 36,
        ContentLedgerKind.ITEM: 146,
        ContentLedgerKind.BATTLEFIELD: 10,
        ContentLedgerKind.ROSTER: 58,
        ContentLedgerKind.DEPLOYMENT: 10,
        ContentLedgerKind.ENCOUNTER: 39,
    }
    assert all(row.content_id for row in CONTENT_LEDGER)
    assert all(row.display_name for row in CONTENT_LEDGER)
    assert all(row.description for row in CONTENT_LEDGER)


def test_fresh_content_ledger_import_does_not_load_runtime_domains() -> None:
    script = """
import json
import sys
import dnd.content.content_ledger
prefixes = (
    'dnd.entities',
    'dnd.blocks',
    'dnd.actions',
    'dnd.conditions',
    'dnd.spells',
    'dnd.game',
)
print(json.dumps({
    prefix: sorted(
        name for name in sys.modules
        if name == prefix or name.startswith(prefix + '.')
    )
    for prefix in prefixes
}))
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(completed.stdout) == {
        "dnd.entities": [],
        "dnd.blocks": [],
        "dnd.actions": [],
        "dnd.conditions": [],
        "dnd.spells": [],
        "dnd.game": [],
    }


def test_direct_builders_do_not_import_the_optional_ledger() -> None:
    builder_paths = (
        REPOSITORY_ROOT / "dnd/content/characters/character_builds.py",
        REPOSITORY_ROOT / "dnd/content/items/authored_item_builders.py",
        REPOSITORY_ROOT / "dnd/content/monsters/monster_builders.py",
        REPOSITORY_ROOT / "dnd/content/scenarios/scenario_deployment.py",
    )
    for path in builder_paths:
        assert "content_ledger" not in path.read_text(encoding="utf-8"), path
