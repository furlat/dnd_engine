"""Exact migration inventory for current creature-producing factory roots."""

from __future__ import annotations

import ast
from hashlib import sha256
from pathlib import Path

from dnd.core.content.identities import ContentDefinitionKind
from dnd.core.content.inventory import (
    LegacyContentClassification,
    LegacyContentMigrationLedger,
    LegacyMigrationStatus,
)
from devtools.generate_legacy_creature_migration_ledger import (
    migrated_creature_refs_by_legacy_id,
)
from dnd.classes.content_factories import (
    PLAYER_CLASS_CREATURE_DECLARATIONS_BY_ID,
)
from dnd.monsters.bestiary_content import (
    BESTIARY_CREATURE_DECLARATIONS_BY_ID,
)
from dnd.monsters.srd_roster import (
    SRD_CREATURE_DECLARATIONS_BY_ID,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
LEDGER_PATH = REPOSITORY_ROOT / "content_data/ledgers/legacy_creatures.json"
STRUCTURAL_NODEID = (
    "tests/manual/test_157_legacy_creature_migration_ledger.py"
    "::test_current_creature_factory_inventory_matches_ledger"
)
SRD_MONSTER_IDS = (
    "commoner",
    "bandit",
    "cultist",
    "guard",
    "tribal_warrior",
    "kobold",
    "acolyte",
    "scout",
    "thug",
    "spy",
    "berserker",
    "bandit_captain",
    "priest",
    "cult_fanatic",
    "knight",
    "veteran",
    "mage",
    "orc",
    "hobgoblin",
    "bugbear",
    "gnoll",
    "ogre",
    "wolf",
    "dire_wolf",
    "zombie",
    "ogre_zombie",
    "ghoul",
)
_EXPECTED_BESTIARY_LEGACY_IDS = {
    (
        "legacy.creature.bestiary.caster"
        if creature_id == "generic_caster"
        else f"legacy.creature.bestiary.{creature_id}"
    )
    for creature_id in BESTIARY_CREATURE_DECLARATIONS_BY_ID
}
_EXPECTED_PLAYER_CLASS_LEGACY_IDS = {
    f"legacy.creature.player.{class_id}"
    for class_id in PLAYER_CLASS_CREATURE_DECLARATIONS_BY_ID
}
_EXPECTED_EXTENSION_ROOTS = {
    "legacy.creature.extension.circus_warrior": (
        "creature.circus_warrior",
        ("dnd/monsters/circus_fighter.py:create_warrior",),
    ),
    "legacy.creature.extension.aegis_spell_feature_actor": (
        "creature.aegis_spell_feature_actor",
        (
            "dnd/extensions/aegis_spark.py:create_spell_feature_actor",
            "dnd/extensions/__init__.py:create_spell_feature_actor",
        ),
    ),
    "legacy.creature.extension.field_medic": (
        "creature.field_medic",
        (
            "dnd/extensions/field_focus.py:create_field_medic",
            "dnd/extensions/__init__.py:create_field_medic",
        ),
    ),
}
_EXPECTED_MIGRATED_CREATURE_IDS = (
    {f"legacy.creature.srd.{monster_id}" for monster_id in SRD_MONSTER_IDS}
    | _EXPECTED_BESTIARY_LEGACY_IDS
    | _EXPECTED_PLAYER_CLASS_LEGACY_IDS
)
_EXPECTED_CREATURE_IDS = (
    _EXPECTED_MIGRATED_CREATURE_IDS | set(_EXPECTED_EXTENSION_ROOTS)
)
_EXPECTED_SRD_PROVISIONAL_CREATURE_IDS = (
    {f"legacy.creature.srd.{monster_id}" for monster_id in SRD_MONSTER_IDS}
    | {
        "legacy.creature.bestiary.goblin",
        "legacy.creature.bestiary.skeleton",
    }
)
ENTITY_FACTORY_MODULES = (
    "dnd/monsters/bestiary.py",
    "dnd/monsters/circus_fighter.py",
    "dnd/extensions/aegis_spark.py",
    "dnd/extensions/field_focus.py",
)


def _ledger() -> LegacyContentMigrationLedger:
    return LegacyContentMigrationLedger.model_validate_json(
        LEDGER_PATH.read_text(encoding="utf-8"),
    )


def _module_tree(relative_path: str) -> ast.Module:
    return ast.parse(
        (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8"),
        filename=relative_path,
    )


def _entity_factory_locators(relative_path: str) -> set[str]:
    """Return public, explicitly Entity-returning factory roots in one module."""
    locators: set[str] = set()
    for node in _module_tree(relative_path).body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not node.name.startswith("create_") or node.name.startswith("_"):
            continue
        annotation = node.returns
        returns_entity = (
            isinstance(annotation, ast.Name)
            and annotation.id == "Entity"
        ) or (
            isinstance(annotation, ast.Constant)
            and annotation.value == "Entity"
        )
        if returns_entity:
            locators.add(f"{relative_path}:{node.name}")
    return locators


def _current_factory_locators() -> set[str]:
    return set().union(*(
        _entity_factory_locators(relative_path)
        for relative_path in ENTITY_FACTORY_MODULES
    ))


def _top_level_test_names(relative_path: str) -> set[str]:
    return {
        node.name
        for node in _module_tree(relative_path).body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
    }


def test_legacy_creature_ledger_validates_exact_provisional_inventory() -> None:
    """Every audited root has one typed, provenance-oriented destination."""
    ledger = _ledger()

    assert len(ledger.rows) == len(ledger.rows_by_id)
    assert set(ledger.rows_by_id) == _EXPECTED_CREATURE_IDS
    assert set(ledger.unmigrated_ids) == set(_EXPECTED_EXTENSION_ROOTS)
    assert {
        row.legacy_id
        for row in ledger.rows
        if row.migration_status == LegacyMigrationStatus.MIGRATED
    } == _EXPECTED_MIGRATED_CREATURE_IDS
    assert {
        row.legacy_id
        for row in ledger.rows
        if row.migration_status == LegacyMigrationStatus.INVENTORIED
    } == set(_EXPECTED_EXTENSION_ROOTS)
    assert {
        row.legacy_id: row.provisional_ref.pack_id
        for row in ledger.rows
        if row.provisional_ref is not None
    } == {
        legacy_id: (
            "content.srd_5_1_cc"
            if legacy_id in _EXPECTED_SRD_PROVISIONAL_CREATURE_IDS
            else "content.neurodragon"
        )
        for legacy_id in _EXPECTED_CREATURE_IDS
    }
    assert all(
        row.definition_kind == ContentDefinitionKind.CREATURE
        and row.classification
        == LegacyContentClassification.INDEPENDENT_DEFINITION
        and row.provisional_ref is not None
        and (
            (
                row.migration_status == LegacyMigrationStatus.MIGRATED
                and row.replacement_ref is not None
            )
            or (
                row.migration_status == LegacyMigrationStatus.INVENTORIED
                and row.replacement_ref is None
            )
        )
        for row in ledger.rows
    )
    for row in ledger.rows:
        assert row.provisional_ref is not None
        expected_hash = sha256(
            (
                f"{row.legacy_id}:"
                "provisional-creature-factory-contract-v1"
            ).encode()
        ).hexdigest()
        assert row.provisional_ref.definition_contract_hash == expected_hash


def test_current_creature_factory_inventory_matches_ledger() -> None:
    """A production creature root cannot disappear or appear unclassified."""
    ledger = _ledger()
    primary_locators = {
        row.legacy_locators[0]
        for row in ledger.rows
        if row.legacy_locators[0].split(":", 1)[0] in ENTITY_FACTORY_MODULES
    }

    assert _current_factory_locators() == primary_locators
    assert all(
        STRUCTURAL_NODEID in row.measuring_test_nodeids
        or row.legacy_id.startswith("legacy.creature.extension.")
        for row in ledger.rows
    )


def test_srd_registry_has_exact_twenty_seven_ledger_destinations() -> None:
    """The canonical 5.1 CC registry maps one-to-one to attributed rows."""
    ledger = _ledger()
    srd_rows = {
        row.legacy_id.removeprefix("legacy.creature.srd."): row
        for row in ledger.rows
        if row.legacy_id.startswith("legacy.creature.srd.")
    }
    migrated_refs = migrated_creature_refs_by_legacy_id()
    assert tuple(SRD_CREATURE_DECLARATIONS_BY_ID) == SRD_MONSTER_IDS
    assert tuple(srd_rows) == SRD_MONSTER_IDS
    for monster_id, declaration in SRD_CREATURE_DECLARATIONS_BY_ID.items():
        row = srd_rows[monster_id]
        assert row.provisional_ref is not None
        assert row.provisional_ref.pack_id == "content.srd_5_1_cc"
        assert row.provisional_ref.content_id == f"creature.{monster_id}"
        assert row.migration_status == LegacyMigrationStatus.MIGRATED
        assert row.replacement_ref == declaration.ref
        assert migrated_refs[row.legacy_id] == declaration.ref
        assert all(
            locator.startswith("dnd/monsters/srd_roster.py:")
            for locator in row.legacy_locators
        )


def test_active_bestiary_and_class_roots_have_exact_ledger_destinations() -> None:
    """The ten active scenario factories now resolve through authenticated refs."""
    rows = _ledger().rows_by_id
    expected = {
        **{
            (
                "legacy.creature.bestiary.caster"
                if creature_id == "generic_caster"
                else f"legacy.creature.bestiary.{creature_id}"
            ): declaration.ref
            for creature_id, declaration
            in BESTIARY_CREATURE_DECLARATIONS_BY_ID.items()
        },
        **{
            f"legacy.creature.player.{class_id}": declaration.ref
            for class_id, declaration
            in PLAYER_CLASS_CREATURE_DECLARATIONS_BY_ID.items()
        },
    }
    assert set(expected) == (
        _EXPECTED_BESTIARY_LEGACY_IDS
        | _EXPECTED_PLAYER_CLASS_LEGACY_IDS
    )
    for legacy_id, ref in expected.items():
        row = rows[legacy_id]
        assert row.migration_status == LegacyMigrationStatus.MIGRATED
        assert row.replacement_ref == ref


def test_closed_actor_dispatch_locators_are_explicit() -> None:
    """Scenario lookup branches remain attributable to their real factories."""
    rows = _ledger().rows_by_id
    assembler_source = (
        REPOSITORY_ROOT / "dnd/scenarios/evaluation/assembler.py"
    ).read_text(encoding="utf-8")
    bestiary_branches = {
        "goblin": "legacy.creature.bestiary.goblin",
        "goblin_archer": "legacy.creature.bestiary.goblin_archer",
        "caster": "legacy.creature.bestiary.caster",
        "skeleton_warrior": "legacy.creature.bestiary.skeleton_warrior",
        "skeleton_archer": "legacy.creature.bestiary.skeleton_archer",
        "skeleton_warlock": "legacy.creature.bestiary.skeleton_warlock",
    }
    class_branches = {
        "BarbarianActorBlueprint": "legacy.creature.player.barbarian",
        "FighterActorBlueprint": "legacy.creature.player.fighter",
        "SorcererActorBlueprint": "legacy.creature.player.sorcerer",
    }

    for branch, legacy_id in bestiary_branches.items():
        assert f'blueprint.archetype == "{branch}"' in assembler_source
        assert (
            "dnd/scenarios/evaluation/assembler.py:"
            f"_build_bestiary_actor[{branch}]"
        ) in rows[legacy_id].legacy_locators
    assert rows["legacy.creature.bestiary.skeleton"].legacy_locators == (
        "dnd/monsters/bestiary.py:create_skeleton",
    )
    for branch, legacy_id in class_branches.items():
        assert f"isinstance(blueprint, {branch})" in assembler_source
        assert (
            "dnd/scenarios/evaluation/assembler.py:"
            f"_build_class_actor[{branch}]"
        ) in rows[legacy_id].legacy_locators


def test_extension_and_special_factory_roots_remain_accounted() -> None:
    """Neurodragon extension roots are explicit without centralizing factories."""
    rows = _ledger().rows_by_id
    extension_init = (
        REPOSITORY_ROOT / "dnd/extensions/__init__.py"
    ).read_text(encoding="utf-8")

    assert {
        legacy_id
        for legacy_id in rows
        if legacy_id.startswith("legacy.creature.extension.")
    } == set(_EXPECTED_EXTENSION_ROOTS)
    for legacy_id, (content_id, locators) in _EXPECTED_EXTENSION_ROOTS.items():
        row = rows[legacy_id]
        assert row.provisional_ref is not None
        assert row.provisional_ref.pack_id == "content.neurodragon"
        assert row.provisional_ref.content_id == content_id
        assert row.legacy_locators == locators
    assert "create_spell_feature_actor" in extension_init
    assert "create_field_medic" in extension_init


def test_every_ledger_row_cites_existing_measuring_test() -> None:
    """Migration evidence is executable, not an unchecked prose citation."""
    test_names_by_path: dict[str, set[str]] = {}

    for row in _ledger().rows:
        for nodeid in row.measuring_test_nodeids:
            relative_path, separator, test_name = nodeid.partition("::")
            assert separator == "::", nodeid
            test_names = test_names_by_path.setdefault(
                relative_path,
                _top_level_test_names(relative_path),
            )
            assert test_name in test_names, nodeid
