"""Exact migration inventory for every current item-construction root."""

from __future__ import annotations

import ast
from pathlib import Path

from dnd.content_system.bootstrap import bootstrap_content_system
from dnd.core.content.identities import ContentDefinitionKind
from dnd.core.content.inventory import (
    LegacyContentClassification,
    LegacyContentMigrationLedger,
    LegacyMigrationStatus,
)
from devtools.generate_legacy_item_migration_ledger import (
    migrated_item_refs_by_legacy_id,
)


_ROOT = Path(__file__).resolve().parents[2]
_LEDGER_PATH = _ROOT / "content_data" / "ledgers" / "legacy_items.json"
_PRIMARY_FACTORY_FILES = {
    "dnd/items/weapons.py": set(),
    "dnd/items/armors.py": set(),
    "dnd/items/consumables.py": set(),
    "dnd/items/spell_items.py": set(),
    "dnd/items/torches.py": set(),
    "dnd/items/test_items.py": set(),
}
_RETIRED_LOOKUP_MAP_NAMES = frozenset({"WEAPONS", "ARMORS", "SHIELDS"})
_MIGRATED_ITEM_REFS_BY_LEGACY_ID = migrated_item_refs_by_legacy_id()
_EXPECTED_ADDITIONAL_INDEPENDENT_ROOTS = {
    "legacy.environment.directional_wall",
    "legacy.environment.directional_door",
    "legacy.environment.test_door_a",
    "legacy.environment.trap_lever",
    "legacy.environment.storage_chest",
    "legacy.environment.campfire",
    "legacy.environment.blocker.crate",
    "legacy.environment.blocker.boulder",
    "legacy.environment.blocker.barricade",
    "legacy.environment.blocker.oil_barrel",
    "legacy.item.factory.test_items.wall_torch",
    "legacy.item.factory.test_items.arcane_device",
    "legacy.item.factory.test_items.arcane_machine_gun",
    "legacy.item.factory.test_items.fireball_cannon",
    "legacy.environment.spell_object.guardian_of_faith",
    "legacy.environment.spell_object.heroes_feast",
    "legacy.item.extension.field_kit",
    "legacy.item.circus.rusty_dagger",
    "legacy.item.circus.flaming_scimitar",
    "legacy.item.circus.performer_armor",
    "legacy.item.circus.longsword_plus_one",
    "legacy.item.circus.soul_draining_morningstar",
}
_EXPECTED_ROOT_OWNED_ITEM_ROOTS = {
    "legacy.item.intrinsic.kobold_sling",
    "legacy.item.intrinsic.spy_hand_crossbow",
    "legacy.item.intrinsic.bandit_captain_thrown_dagger",
    "legacy.item.intrinsic.orc_thrown_javelin",
    "legacy.item.intrinsic.bugbear_morningstar",
    "legacy.item.intrinsic.bugbear_thrown_javelin",
    "legacy.item.intrinsic.ogre_greatclub",
    "legacy.item.intrinsic.ogre_thrown_javelin",
    "legacy.item.intrinsic.wolf_bite",
    "legacy.item.intrinsic.dire_wolf_bite",
    "legacy.item.intrinsic.zombie_slam",
    "legacy.item.intrinsic.ogre_zombie_morningstar",
    "legacy.item.intrinsic.ghoul_claws",
    "legacy.item.intrinsic.ghoul_bite",
    "legacy.item.intrinsic.wolf_natural_armor",
    "legacy.item.intrinsic.dire_wolf_natural_armor",
}
_EXPECTED_PRIVATE_BEHAVIORS = {
    "legacy.behavior.item_owned.assassin_dagger_unseen_strike",
    "legacy.behavior.item_owned.arcane_staff_spell_attack",
    "legacy.behavior.item_owned.acid_flask_spell",
    "legacy.behavior.item_owned.healing_potion_drink",
    "legacy.behavior.item_owned.weapon_coat_apply_fire",
    "legacy.behavior.item_owned.weapon_coat_apply_lightning",
    "legacy.behavior.item_owned.weapon_coat_apply_concentration",
    "legacy.behavior.item_owned.weapon_coat_apply_timed",
    "legacy.behavior.item_owned.arcane_device_activate",
    "legacy.behavior.item_owned.greater_invisibility_potion_drink",
    "legacy.behavior.item_owned.torch_state_actions",
    "legacy.behavior.item_owned.wall_torch_state_actions",
    "legacy.behavior.item_owned.haste_potion_drink",
    "legacy.behavior.item_owned.directional_door_state_actions",
    "legacy.behavior.item_owned.test_door_a_state_actions",
    "legacy.behavior.item_owned.test_door_b_interact",
    "legacy.behavior.item_owned.trap_lever_pull",
    "legacy.behavior.item_owned.storage_chest_loot_all",
    "legacy.behavior.item_owned.campfire_rest",
    "legacy.behavior.item_owned.campfire_cook",
    "legacy.behavior.item_owned.field_kit_deploy",
    "legacy.behavior.spell_object.guardian_warded",
    "legacy.behavior.spell_object.heroes_feast_eat",
    "legacy.behavior.spell_object.heroes_feast_buff",
}
_EXPECTED_UNMIGRATED_ITEM_IDS = (
    _EXPECTED_PRIVATE_BEHAVIORS
    | {"legacy.fixture.item.test_door_b"}
)
_EXPECTED_VARIANT_LOCATORS = {
    "dnd/scenarios/evaluation/wardrobes.py:ApparelGrant[common_clothes|82000001|Farmhand's Tunic]",
    "dnd/scenarios/evaluation/wardrobes.py:ApparelGrant[common_clothes|82000009|Peasant's Rags]",
    "dnd/scenarios/evaluation/wardrobes.py:ApparelGrant[travelers_clothes|84000006|Thief's Garb]",
    "dnd/scenarios/evaluation/wardrobes.py:ApparelGrant[costume|85000004|Pit Fighter's Wrap]",
    "dnd/scenarios/evaluation/wardrobes.py:ApparelGrant[robes|8100000b|Hedge Wizard's Robe]",
    "dnd/scenarios/evaluation/wardrobes.py:ApparelGrant[robes|81000008|Dark Cultist Robes]",
    "dnd/scenarios/evaluation/wardrobes.py:ApparelGrant[robes|81000003|Priest's Vestments]",
    "dnd/scenarios/evaluation/wardrobes.py:ApparelGrant[robes|81000004|Necromancer's Robe]",
    "dnd/scenarios/evaluation/wardrobes.py:ApparelGrant[robes|81000007|Acolyte's Vestments]",
    "dnd/scenarios/evaluation/wardrobes.py:ApparelGrant[robes|81000001|Wizard's Robe]",
    "dnd/scenarios/evaluation/wardrobes.py:ApparelGrant[cloth_shoes|b0000003|Dark Cloth Shoes]",
    "dnd/scenarios/evaluation/wardrobes.py:ApparelGrant[cloth_shoes|b0000005|Blue Cloth Shoes]",
    "dnd/scenarios/evaluation/wardrobes.py:ApparelGrant[leather_boots|b0000008|Dark Boots]",
    "dnd/scenarios/evaluation/wardrobes.py:ApparelGrant[leather_boots|b0000009|Brown Boots]",
    "dnd/scenarios/evaluation/wardrobes.py:ApparelGrant[sandals|b0000002|Rope Sandals]",
    "dnd/scenarios/evaluation/wardrobes.py:ApparelGrant[leather_shoes|b0000007|Brown Leather Shoes]",
    "dnd/classes/sorcerer_factory.py:create_robes[81000005]",
    "dnd/classes/sorcerer_factory.py:create_cloth_shoes[b0000004]",
    "dnd/classes/fighter_factory.py:create_iron_helmet[h0000008]",
    "dnd/classes/sorcerer_factory.py:create_wizard_hat[h0000011]",
}


def _load_ledger() -> LegacyContentMigrationLedger:
    return LegacyContentMigrationLedger.model_validate_json(
        _LEDGER_PATH.read_text(encoding="utf-8"),
    )


def _top_level_functions(relative_path: str) -> set[str]:
    module = ast.parse(
        (_ROOT / relative_path).read_text(encoding="utf-8"),
        filename=relative_path,
    )
    return {
        node.name
        for node in module.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _retired_lookup_maps_from_source() -> set[str]:
    relative_path = "dnd/items/__init__.py"
    module = ast.parse(
        (_ROOT / relative_path).read_text(encoding="utf-8"),
        filename=relative_path,
    )
    found: set[str] = set()
    for node in module.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if (
            not isinstance(target, ast.Name)
            or target.id not in _RETIRED_LOOKUP_MAP_NAMES
        ):
            continue
        found.add(target.id)
    return found


def test_legacy_item_migration_ledger_validates_as_closed_model() -> None:
    """The checked-in inventory is typed, exact, and free of fallback identities."""
    ledger = _load_ledger()

    assert ledger.schema_version == 1
    assert len(ledger.rows) == len(ledger.rows_by_id)
    assert set(ledger.rows_by_id) == (
        set(_MIGRATED_ITEM_REFS_BY_LEGACY_ID)
        | _EXPECTED_UNMIGRATED_ITEM_IDS
    )
    assert set(ledger.unmigrated_ids) == _EXPECTED_UNMIGRATED_ITEM_IDS
    assert {
        row.legacy_id
        for row in ledger.rows
        if row.migration_status == LegacyMigrationStatus.MIGRATED
    } == set(_MIGRATED_ITEM_REFS_BY_LEGACY_ID)

    independent_refs = []
    for row in ledger.rows:
        if row.classification == LegacyContentClassification.INDEPENDENT_DEFINITION:
            assert row.provisional_ref is not None
            assert row.provided_by_ref is None
            independent_refs.append(row.provisional_ref.identity_key)
        elif row.classification == LegacyContentClassification.ROOT_OWNED_BEHAVIOR:
            assert row.provisional_ref is None
            assert row.provided_by_ref is not None
        elif row.classification == LegacyContentClassification.FIXTURE_ONLY:
            assert row.provisional_ref is not None
            assert row.provisional_ref.pack_id == "content.fixture_internal"
        else:
            raise AssertionError(
                f"Unexpected item-ledger classification: {row.classification}",
            )

        for ref in (
            row.provisional_ref,
            row.provided_by_ref,
            *row.dependency_refs,
        ):
            if ref is None:
                continue
            assert not ref.content_id.startswith("dnd.")
            assert not any(character.isupper() for character in ref.content_id)

    assert len(independent_refs) == len(set(independent_refs))


def test_primary_item_factory_inventory_is_exact() -> None:
    """Every remaining public named item factory has one migration row."""
    ledger = _load_ledger()
    expected_locators = {
        f"{relative_path}:{factory_name}"
        for relative_path, expected_names in _PRIMARY_FACTORY_FILES.items()
        for factory_name in expected_names
    }
    assert expected_locators == set()

    for relative_path, expected_names in _PRIMARY_FACTORY_FILES.items():
        actual_names = {
            name
            for name in _top_level_functions(relative_path)
            if name.startswith("create_")
        }
        assert actual_names == expected_names

    ledger_locators = {
        locator
        for row in ledger.rows
        if row.migration_status == LegacyMigrationStatus.INVENTORIED
        for locator in row.legacy_locators
        if any(
            locator.startswith(f"{relative_path}:create_")
            for relative_path in _PRIMARY_FACTORY_FILES
        )
    }
    assert ledger_locators == expected_locators

    owners = {
        locator: [
            row.legacy_id
            for row in ledger.rows
            if locator in row.legacy_locators
        ]
        for locator in expected_locators
    }
    assert all(len(row_ids) == 1 for row_ids in owners.values())


def test_legacy_lookup_maps_have_exact_ledger_coverage() -> None:
    """All three callable lookup maps are retired, never left empty as aliases."""
    ledger = _load_ledger()
    assert _retired_lookup_maps_from_source() == set()
    inventoried_lookup_locators = {
        locator
        for row in ledger.rows
        if row.migration_status == LegacyMigrationStatus.INVENTORIED
        for locator in row.legacy_locators
        if locator.startswith("dnd/items/__init__.py:")
    }
    assert inventoried_lookup_locators == set()


def test_migrated_item_roots_use_exact_content_refs() -> None:
    """Every migrated item has only its authenticated registry root."""
    ledger = _load_ledger()
    for legacy_id, replacement_ref in (
        _MIGRATED_ITEM_REFS_BY_LEGACY_ID.items()
    ):
        row = ledger.rows_by_id[legacy_id]
        assert row.migration_status == LegacyMigrationStatus.MIGRATED
        assert row.replacement_ref == replacement_ref
        for locator in row.legacy_locators:
            relative_path, symbol = locator.split(":", 1)
            if symbol.startswith("create_"):
                assert symbol not in _top_level_functions(relative_path)
                continue
            if not symbol.startswith(("WEAPONS[", "ARMORS[", "SHIELDS[")):
                continue
            map_name, _ = symbol.rstrip("]").split("[", 1)
            assert map_name in _RETIRED_LOOKUP_MAP_NAMES
            assert map_name not in _retired_lookup_maps_from_source()


def test_srd_creature_possession_roots_resolve_to_canonical_items() -> None:
    """Every former inline possession names its exact canonical item root."""
    ledger = _load_ledger()
    registry = bootstrap_content_system().registry

    assert _EXPECTED_ROOT_OWNED_ITEM_ROOTS <= set(
        _MIGRATED_ITEM_REFS_BY_LEGACY_ID,
    )
    for legacy_id in _EXPECTED_ROOT_OWNED_ITEM_ROOTS:
        expected_ref = _MIGRATED_ITEM_REFS_BY_LEGACY_ID[legacy_id]
        row = ledger.rows_by_id[legacy_id]

        assert row.migration_status == LegacyMigrationStatus.MIGRATED
        assert row.replacement_ref == expected_ref
        assert expected_ref.definition_kind == ContentDefinitionKind.ITEM
        declaration = registry.resolve_factory(expected_ref)
        assert declaration.item_definition is not None
        assert row.notes.startswith(
            "persistence_policy="
            f"{declaration.item_definition.persistence_policy.value}; ",
        )


def test_additional_item_and_environment_roots_are_explicitly_classified() -> None:
    """Local, intrinsic, fixture, and spell-created objects cannot disappear."""
    ledger = _load_ledger()
    row_ids = set(ledger.rows_by_id)

    expected_additional_rows = (
        _EXPECTED_ADDITIONAL_INDEPENDENT_ROOTS
        | _EXPECTED_ROOT_OWNED_ITEM_ROOTS
        | {"legacy.fixture.item.test_door_b"}
    )

    additional_rows = {
        row_id
        for row_id in row_ids
        if (
            row_id in _EXPECTED_ADDITIONAL_INDEPENDENT_ROOTS
            or row_id in _EXPECTED_ROOT_OWNED_ITEM_ROOTS
            or row_id == "legacy.fixture.item.test_door_b"
        )
    }
    assert additional_rows == expected_additional_rows

    for row_id in _EXPECTED_ADDITIONAL_INDEPENDENT_ROOTS:
        row = ledger.rows_by_id[row_id]
        assert row.classification == LegacyContentClassification.INDEPENDENT_DEFINITION
        assert row.provisional_ref is not None

    for row_id in _EXPECTED_ROOT_OWNED_ITEM_ROOTS:
        row = ledger.rows_by_id[row_id]
        assert row.classification == LegacyContentClassification.ROOT_OWNED_BEHAVIOR
        assert row.provided_by_ref is not None
        assert row.provided_by_ref.definition_kind == ContentDefinitionKind.CREATURE
        assert row.migration_status == LegacyMigrationStatus.MIGRATED
        assert row.replacement_ref == (
            _MIGRATED_ITEM_REFS_BY_LEGACY_ID[row_id]
        )


def test_important_recipe_variants_and_behavior_providers_are_frozen() -> None:
    """Observed recipes stay variants and private mechanics retain exact owners."""
    ledger = _load_ledger()
    all_locators = {
        locator
        for row in ledger.rows
        for locator in row.legacy_locators
    }
    actual_variant_locators = {
        locator
        for locator in all_locators
        if (
            locator.startswith(
                "dnd/scenarios/evaluation/wardrobes.py:ApparelGrant[",
            )
            or locator
            in {
                "dnd/classes/sorcerer_factory.py:create_robes[81000005]",
                "dnd/classes/sorcerer_factory.py:create_cloth_shoes[b0000004]",
                "dnd/classes/fighter_factory.py:create_iron_helmet[h0000008]",
                "dnd/classes/sorcerer_factory.py:create_wizard_hat[h0000011]",
            }
        )
    }
    assert actual_variant_locators == _EXPECTED_VARIANT_LOCATORS

    potion = ledger.rows_by_id[
        "legacy.item.factory.test_items.healing_potion"
    ]
    assert "parameters=heal_amount" in potion.notes
    assert "observed=7,10,12,14,16,18" in potion.notes
    wand = ledger.rows_by_id["legacy.item.factory.test_items.wand_of_fire"]
    assert "observed_charges=4,7" in wand.notes

    behavior_ids = {
        row.legacy_id
        for row in ledger.rows
        if row.legacy_id.startswith("legacy.behavior.")
    }
    assert behavior_ids == _EXPECTED_PRIVATE_BEHAVIORS

    independent_refs = {
        row.provisional_ref.identity_key
        for row in ledger.rows
        if row.provisional_ref is not None
    }
    for row_id in _EXPECTED_PRIVATE_BEHAVIORS:
        row = ledger.rows_by_id[row_id]
        assert row.classification == LegacyContentClassification.ROOT_OWNED_BEHAVIOR
        assert row.provided_by_ref is not None
        if row.provided_by_ref.definition_kind in {
            ContentDefinitionKind.ITEM,
            ContentDefinitionKind.ENVIRONMENT_OBJECT,
        }:
            assert row.provided_by_ref.identity_key in independent_refs

    wolf_bite = ledger.rows_by_id["legacy.item.intrinsic.wolf_bite"]
    dire_bite = ledger.rows_by_id["legacy.item.intrinsic.dire_wolf_bite"]
    ghoul_bite = ledger.rows_by_id["legacy.item.intrinsic.ghoul_bite"]
    assert wolf_bite.provided_by_ref is not None
    assert dire_bite.provided_by_ref is not None
    assert ghoul_bite.provided_by_ref is not None
    assert len(
        {
            wolf_bite.provided_by_ref.identity_key,
            dire_bite.provided_by_ref.identity_key,
            ghoul_bite.provided_by_ref.identity_key,
        },
    ) == 3
    assert {wolf_bite.notes, dire_bite.notes, ghoul_bite.notes} == {
        "persistence_policy=intrinsic; Bite 2d4 piercing hidden",
        "persistence_policy=intrinsic; Bite 2d6 piercing hidden",
        "persistence_policy=intrinsic; Bite 2d6 piercing light hidden",
    }


def test_all_cited_measuring_nodeids_exist() -> None:
    """No ledger row can cite a missing file or a prose-only test identity."""
    ledger = _load_ledger()
    functions_by_file: dict[str, set[str]] = {}

    for row in ledger.rows:
        for locator in row.legacy_locators:
            source_path = locator.split(":", 1)[0]
            assert (_ROOT / source_path).is_file(), (
                f"{row.legacy_id} cites missing construction source {source_path}"
            )

        for nodeid in row.measuring_test_nodeids:
            parts = nodeid.split("::")
            assert len(parts) == 2, (
                f"{row.legacy_id} must cite an exact test function: {nodeid}"
            )
            relative_path, function_name = parts
            test_path = _ROOT / relative_path
            assert test_path.is_file(), (
                f"{row.legacy_id} cites missing test file {relative_path}"
            )
            if relative_path not in functions_by_file:
                functions_by_file[relative_path] = _top_level_functions(
                    relative_path,
                )
            assert function_name in functions_by_file[relative_path], (
                f"{row.legacy_id} cites missing test function {nodeid}"
            )
