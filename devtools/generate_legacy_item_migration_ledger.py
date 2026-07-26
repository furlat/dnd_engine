"""Reconcile migrated item rows with exact canonical content references."""

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
from dnd.extensions.field_focus import FIELD_KIT_RECIPE
from dnd.items.armors import (
    NEURODRAGON_ARMOR_RECIPES_BY_LEGACY_ID,
    SRD_ARMOR_RECIPES_BY_LEGACY_ID,
)
from dnd.items.consumables import (
    NEURODRAGON_CONSUMABLE_RECIPES_BY_LEGACY_ID,
)
from dnd.items.environment_content import (
    NEURODRAGON_ENVIRONMENT_RECIPES_BY_LEGACY_ID,
)
from dnd.items.spell_items import (
    NEURODRAGON_SPELL_ITEM_RECIPES_BY_LEGACY_ID,
)
from dnd.items.torches import TORCH_RECIPE
from dnd.monsters.bestiary_items import ARMOR_SCRAPS_RECIPE
from dnd.monsters.circus_fighter_items import (
    NEURODRAGON_CIRCUS_ITEM_RECIPES_BY_LEGACY_ID,
)
from dnd.monsters.srd_roster_items import (
    SRD_CREATURE_POSSESSION_ITEM_DECLARATIONS,
    SRD_CREATURE_POSSESSION_RECIPES,
)
from dnd.items.weapons import (
    NEURODRAGON_WEAPON_RECIPES_BY_LEGACY_ID,
    SRD_WEAPON_RECIPES_BY_LEGACY_ID,
)
from dnd.spells.catalog_content import SPELL_CONTENT_DECLARATIONS_BY_NAME
from dnd.spells.conjuration import (
    GUARDIAN_OF_FAITH_OBJECT_RECIPE,
    HEROES_FEAST_OBJECT_RECIPE,
)


DEFAULT_LEDGER_PATH = (
    REPOSITORY_ROOT / "content_data" / "ledgers" / "legacy_items.json"
)
_SRD_ARMOR_LEGACY_IDS = {
    "padded": "legacy.item.factory.armor.padded_armor",
    "leather": "legacy.item.factory.armor.leather_armor",
    "studded_leather": "legacy.item.factory.armor.studded_leather",
    "hide": "legacy.item.factory.armor.hide_armor",
    "chain_shirt": "legacy.item.factory.armor.chain_shirt",
    "scale_mail": "legacy.item.factory.armor.scale_mail",
    "breastplate": "legacy.item.factory.armor.breastplate",
    "half_plate": "legacy.item.factory.armor.half_plate",
    "ring_mail": "legacy.item.factory.armor.ring_mail",
    "chain_mail": "legacy.item.factory.armor.chain_mail",
    "splint": "legacy.item.factory.armor.splint_armor",
    "plate": "legacy.item.factory.armor.plate_armor",
    "shield": "legacy.item.factory.shield.shield",
}
_SPELL_ENVIRONMENT_RECIPES_BY_LEGACY_ID = {
    "legacy.environment.spell_object.guardian_of_faith": (
        GUARDIAN_OF_FAITH_OBJECT_RECIPE
    ),
    "legacy.environment.spell_object.heroes_feast": (
        HEROES_FEAST_OBJECT_RECIPE
    ),
}
_SPELL_ENVIRONMENT_PROVIDER_REFS_BY_LEGACY_ID = {
    "legacy.environment.spell_object.guardian_of_faith": (
        SPELL_CONTENT_DECLARATIONS_BY_NAME["Guardian of Faith"].ref
    ),
    "legacy.environment.spell_object.heroes_feast": (
        SPELL_CONTENT_DECLARATIONS_BY_NAME["Heroes' Feast"].ref
    ),
}
_SRD_CREATURE_POSSESSION_RECIPE_KEYS_BY_LEGACY_ID = {
    "legacy.item.intrinsic.kobold_sling": "kobold_sling",
    "legacy.item.intrinsic.spy_hand_crossbow": "spy_hand_crossbow",
    "legacy.item.intrinsic.bandit_captain_thrown_dagger": (
        "bandit_captain_thrown_dagger"
    ),
    "legacy.item.intrinsic.orc_thrown_javelin": "thrown_javelin",
    "legacy.item.intrinsic.bugbear_morningstar": "bugbear_morningstar",
    "legacy.item.intrinsic.bugbear_thrown_javelin": "thrown_javelin",
    "legacy.item.intrinsic.ogre_greatclub": "ogre_greatclub",
    "legacy.item.intrinsic.ogre_thrown_javelin": "ogre_thrown_javelin",
    "legacy.item.intrinsic.wolf_bite": "wolf_bite",
    "legacy.item.intrinsic.dire_wolf_bite": "dire_wolf_bite",
    "legacy.item.intrinsic.zombie_slam": "zombie_slam",
    "legacy.item.intrinsic.ogre_zombie_morningstar": (
        "ogre_zombie_morningstar"
    ),
    "legacy.item.intrinsic.ghoul_claws": "ghoul_claws",
    "legacy.item.intrinsic.ghoul_bite": "ghoul_bite",
    "legacy.item.intrinsic.wolf_natural_armor": "wolf_natural_armor",
    "legacy.item.intrinsic.dire_wolf_natural_armor": (
        "dire_wolf_natural_armor"
    ),
}
_ENVIRONMENT_INVENTORY_TEST_NODEID = (
    "tests/manual/test_180_environment_content_identity.py::"
    "test_production_environment_inventory_is_exact_and_fully_migrated"
)
_CREATURE_POSSESSION_LEDGER_TEST_NODEID = (
    "tests/manual/test_156_legacy_item_migration_ledger.py::"
    "test_srd_creature_possession_roots_resolve_to_canonical_items"
)
_CREATURE_POSSESSION_RUNTIME_TEST_NODEID = (
    "tests/manual/test_180_srd_creature_possession_bindings.py::"
    "test_every_equipped_srd_creature_item_has_an_exact_runtime_binding"
)


def migrated_item_refs_by_legacy_id() -> dict[str, ContentRef]:
    """Return every implemented hard-cut item root keyed by its audit ID."""
    refs = {
        **{
            f"legacy.item.factory.weapon.{external_id}": recipe.ref
            for external_id, recipe
            in SRD_WEAPON_RECIPES_BY_LEGACY_ID.items()
        },
        **{
            f"legacy.item.factory.weapon.{external_id}": recipe.ref
            for external_id, recipe
            in NEURODRAGON_WEAPON_RECIPES_BY_LEGACY_ID.items()
        },
        **{
            _SRD_ARMOR_LEGACY_IDS[external_id]: recipe.ref
            for external_id, recipe in SRD_ARMOR_RECIPES_BY_LEGACY_ID.items()
        },
        **{
            (
                "legacy.item.factory.shield.wooden_shield"
                if external_id == "wooden_shield"
                else f"legacy.item.factory.apparel.{external_id}"
            ): recipe.ref
            for external_id, recipe
            in NEURODRAGON_ARMOR_RECIPES_BY_LEGACY_ID.items()
        },
        **{
            f"legacy.item.factory.test_items.{external_id}": recipe.ref
            for external_id, recipe
            in NEURODRAGON_CONSUMABLE_RECIPES_BY_LEGACY_ID.items()
        },
        **{
            f"legacy.item.factory.test_items.{external_id}": recipe.ref
            for external_id, recipe
            in NEURODRAGON_SPELL_ITEM_RECIPES_BY_LEGACY_ID.items()
        },
        **{
            legacy_id: recipe.ref
            for legacy_id, recipe
            in NEURODRAGON_ENVIRONMENT_RECIPES_BY_LEGACY_ID.items()
        },
        **{
            legacy_id: recipe.ref
            for legacy_id, recipe
            in _SPELL_ENVIRONMENT_RECIPES_BY_LEGACY_ID.items()
        },
        "legacy.item.factory.test_items.torch": TORCH_RECIPE.ref,
        "legacy.item.bestiary.armor_scraps": ARMOR_SCRAPS_RECIPE.ref,
        "legacy.item.extension.field_kit": FIELD_KIT_RECIPE.ref,
        **{
            f"legacy.item.circus.{external_id}": recipe.ref
            for external_id, recipe
            in NEURODRAGON_CIRCUS_ITEM_RECIPES_BY_LEGACY_ID.items()
        },
        **{
            legacy_id: SRD_CREATURE_POSSESSION_RECIPES[recipe_key].ref
            for legacy_id, recipe_key
            in _SRD_CREATURE_POSSESSION_RECIPE_KEYS_BY_LEGACY_ID.items()
        },
    }
    if len(refs) != sum((
        len(SRD_WEAPON_RECIPES_BY_LEGACY_ID),
        len(NEURODRAGON_WEAPON_RECIPES_BY_LEGACY_ID),
        len(SRD_ARMOR_RECIPES_BY_LEGACY_ID),
        len(NEURODRAGON_ARMOR_RECIPES_BY_LEGACY_ID),
        len(NEURODRAGON_CONSUMABLE_RECIPES_BY_LEGACY_ID),
        len(NEURODRAGON_SPELL_ITEM_RECIPES_BY_LEGACY_ID),
        len(NEURODRAGON_ENVIRONMENT_RECIPES_BY_LEGACY_ID),
        len(_SPELL_ENVIRONMENT_RECIPES_BY_LEGACY_ID),
        len(NEURODRAGON_CIRCUS_ITEM_RECIPES_BY_LEGACY_ID),
        len(_SRD_CREATURE_POSSESSION_RECIPE_KEYS_BY_LEGACY_ID),
        3,
    )):
        raise RuntimeError("Migrated item ledger identities overlap")
    return refs


def _render(ledger_path: Path) -> str:
    payload = json.loads(ledger_path.read_text(encoding="utf-8"))
    refs = migrated_item_refs_by_legacy_id()
    rows_by_id = {
        row["legacy_id"]: row
        for row in payload["rows"]
    }
    missing = sorted(set(refs) - set(rows_by_id))
    if missing:
        raise RuntimeError(
            "Canonical item recipes have no legacy ledger row: "
            + ", ".join(missing),
        )
    for legacy_id, ref in refs.items():
        row = rows_by_id[legacy_id]
        row["migration_status"] = "migrated"
        row["replacement_ref"] = ref.model_dump(mode="json")
        if legacy_id in {
            *NEURODRAGON_ENVIRONMENT_RECIPES_BY_LEGACY_ID,
            *_SPELL_ENVIRONMENT_RECIPES_BY_LEGACY_ID,
        }:
            measuring_nodeids = row["measuring_test_nodeids"]
            if _ENVIRONMENT_INVENTORY_TEST_NODEID not in measuring_nodeids:
                measuring_nodeids.append(_ENVIRONMENT_INVENTORY_TEST_NODEID)
    for legacy_id, recipe in (
        _SPELL_ENVIRONMENT_RECIPES_BY_LEGACY_ID.items()
    ):
        row = rows_by_id[legacy_id]
        row["classification"] = "independent_definition"
        row["provisional_ref"] = recipe.ref.model_dump(mode="json")
        row["provided_by_ref"] = None
        row["dependency_refs"] = [
            _SPELL_ENVIRONMENT_PROVIDER_REFS_BY_LEGACY_ID[
                legacy_id
            ].model_dump(mode="json"),
        ]
    creature_item_definitions = {
        declaration.ref.identity_key: declaration.item_definition
        for declaration in SRD_CREATURE_POSSESSION_ITEM_DECLARATIONS
    }
    for legacy_id, recipe_key in (
        _SRD_CREATURE_POSSESSION_RECIPE_KEYS_BY_LEGACY_ID.items()
    ):
        row = rows_by_id[legacy_id]
        recipe = SRD_CREATURE_POSSESSION_RECIPES[recipe_key]
        definition = creature_item_definitions[recipe.ref.identity_key]
        if definition is None:
            raise RuntimeError(
                f"Creature possession {recipe.ref.identity_key} has no "
                "item definition",
            )
        mechanical_notes = row["notes"].split("; ", 1)
        retained_notes = mechanical_notes[-1]
        row["notes"] = (
            f"persistence_policy={definition.persistence_policy.value}; "
            f"{retained_notes}"
        )
        measuring_nodeids = row["measuring_test_nodeids"]
        for nodeid in (
            _CREATURE_POSSESSION_LEDGER_TEST_NODEID,
            _CREATURE_POSSESSION_RUNTIME_TEST_NODEID,
        ):
            if nodeid not in measuring_nodeids:
                measuring_nodeids.append(nodeid)
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
                f"{ledger_path} is stale; regenerate the item migration ledger",
            )
        return
    ledger_path.write_text(rendered, encoding="utf-8")


if __name__ == "__main__":
    main()
