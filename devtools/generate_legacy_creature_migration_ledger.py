"""Reconcile migrated creature rows with exact canonical content references."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from dnd.core.content.identities import ContentRef
from dnd.core.content.inventory import LegacyContentMigrationLedger
from dnd.classes.content_factories import (
    PLAYER_CLASS_CREATURE_DECLARATIONS_BY_ID,
)
from dnd.monsters.bestiary_content import (
    BESTIARY_CREATURE_DECLARATIONS_BY_ID,
)
from dnd.monsters.srd_roster import SRD_CREATURE_DECLARATIONS_BY_ID


DEFAULT_LEDGER_PATH = (
    REPOSITORY_ROOT / "content_data" / "ledgers" / "legacy_creatures.json"
)


def migrated_creature_refs_by_legacy_id() -> dict[str, ContentRef]:
    """Return every completed creature hard cut keyed by its audit identity."""
    refs = {
        f"legacy.creature.srd.{creature_id}": declaration.ref
        for creature_id, declaration
        in SRD_CREATURE_DECLARATIONS_BY_ID.items()
    }
    refs.update({
        (
            "legacy.creature.bestiary.caster"
            if creature_id == "generic_caster"
            else f"legacy.creature.bestiary.{creature_id}"
        ): declaration.ref
        for creature_id, declaration
        in BESTIARY_CREATURE_DECLARATIONS_BY_ID.items()
    })
    refs.update({
        f"legacy.creature.player.{class_id}": declaration.ref
        for class_id, declaration
        in PLAYER_CLASS_CREATURE_DECLARATIONS_BY_ID.items()
    })
    if len(refs) != 37:
        raise RuntimeError(
            "The canonical current creature migration requires 37 roots",
        )
    return refs


def _render(ledger_path: Path) -> str:
    payload = json.loads(ledger_path.read_text(encoding="utf-8"))
    refs = migrated_creature_refs_by_legacy_id()
    rows_by_id = {
        row["legacy_id"]: row
        for row in payload["rows"]
    }
    missing = sorted(set(refs) - set(rows_by_id))
    if missing:
        raise RuntimeError(
            "Canonical creature recipes have no legacy ledger row: "
            + ", ".join(missing),
        )
    for legacy_id, ref in refs.items():
        row = rows_by_id[legacy_id]
        row["migration_status"] = "migrated"
        row["replacement_ref"] = ref.model_dump(mode="json")
    validated = LegacyContentMigrationLedger.model_validate(payload)
    return json.dumps(
        validated.model_dump(mode="json"),
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
    ) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--ledger",
        type=Path,
        default=DEFAULT_LEDGER_PATH,
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail when canonical recipes and checked-in rows differ.",
    )
    arguments = parser.parse_args()
    ledger_path = arguments.ledger.resolve()
    rendered = _render(ledger_path)
    if arguments.check:
        if ledger_path.read_text(encoding="utf-8") != rendered:
            raise SystemExit(
                f"{ledger_path} is stale; regenerate the creature migration ledger",
            )
        return
    ledger_path.write_text(rendered, encoding="utf-8")


if __name__ == "__main__":
    main()
