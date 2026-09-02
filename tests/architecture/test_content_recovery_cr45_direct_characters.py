"""Architecture gates for the direct-character recovery cut."""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from dataclasses import fields
from pathlib import Path

from dnd.blocks.spellcasting import (
    LearnedReactionSpellOwnership,
    LearnedReactionSpellSource,
    SpellcastingSource,
)
from dnd.core.base_actions import BaseAction
from dnd.core.events import EntityLevelAddedEvent, EntityLevelRemovedEvent
from dnd.core.feature_grants import AttackMultiplicityGrant
from dnd.content.characters.class_definitions import (
    BARBARIAN_RETIRED_DECLARATION_IDS,
    FIGHTER_RETIRED_DECLARATION_IDS,
    SORCERER_RETIRED_DECLARATION_IDS,
)
from dnd.entity import Entity
from dnd.content_system.builtin_inventory import BUILT_IN_DECLARATION_INVENTORY
from dnd.types.character_receipts import (
    BarbarianGrantReceipt,
    FighterGrantReceipt,
    OriginGrantReceipt,
    SorcererGrantReceipt,
)


_ROOT = Path(__file__).resolve().parents[2]
_ABILITY_NAMES = {"AbilityName", "SkillName", "SavingThrowName"}
_ABILITY_VALUES = {
    "strength",
    "dexterity",
    "constitution",
    "intelligence",
    "wisdom",
    "charisma",
}
_LEAF_PATHS = (
    "dnd/types/abilities.py",
    "dnd/types/character_progression.py",
    "dnd/types/character_receipts.py",
)
_RETIRED_CHARACTER_MODULES = frozenset({
    "dnd.classes.barbarian_progression_definitions",
    "dnd.classes.content_factories",
    "dnd.classes.progression_definitions",
    "dnd.classes.sorcerer_progression_definitions",
    "dnd.classes.sorcerer_structural_feature_definitions",
    "dnd.classes.starting_equipment_refs",
    "dnd.classes.structural_feature_definitions",
    "dnd.content_system.acolyte_starting_holdings",
    "dnd.content_system.background_starting_holdings",
    "dnd.content_system.barbarian_character_grant_appliers",
    "dnd.content_system.builtin_character_builds",
    "dnd.content_system.builtin_character_grant_appliers",
    "dnd.content_system.character_appearance",
    "dnd.content_system.character_build_validation",
    "dnd.content_system.character_content_migrations",
    "dnd.content_system.character_grant_applier_runtime",
    "dnd.content_system.character_grant_context",
    "dnd.content_system.character_grant_types",
    "dnd.content_system.character_materialization",
    "dnd.content_system.character_origin_definitions",
    "dnd.content_system.dragonborn_character_grant_appliers",
    "dnd.content_system.dragonborn_origin_definitions",
    "dnd.content_system.extra_attack_character_grant_appliers",
    "dnd.content_system.fighter_character_grant_appliers",
    "dnd.content_system.origin_character_grant_appliers",
    "dnd.content_system.origin_feature_definitions",
    "dnd.content_system.origin_innate_spellcasting",
    "dnd.content_system.origin_runtime_character_grant_appliers",
    "dnd.content_system.sorcerer_character_grant_appliers",
    "dnd.content_system.starting_apparel_definitions",
    "dnd.content_system.starting_equipment_definitions",
    "dnd.core.content.origin_features",
    "dnd.core.content.premade_characters",
    "dnd.core.content.starting_equipment",
    "dnd.player_character_body",
    "dnd.premade_characters",
})


def _tree(relative_path: str) -> ast.Module:
    tree = ast.parse((_ROOT / relative_path).read_text(encoding="utf-8"))
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            child._cr45_parent = parent
    return tree


def _production_python_paths() -> tuple[Path, ...]:
    return tuple(sorted((_ROOT / "dnd").rglob("*.py")))


def test_generic_character_runtime_is_hard_deleted_from_active_production() -> None:
    stale_imports: list[tuple[str, str]] = []
    for module in _RETIRED_CHARACTER_MODULES:
        assert not (_ROOT / f"{module.replace('.', '/')}.py").exists()

    for path in _production_python_paths():
        relative_path = path.relative_to(_ROOT).as_posix()
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                modules = tuple(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                modules = (node.module or "",)
            else:
                modules = ()
            stale_imports.extend(
                (relative_path, module)
                for module in modules
                if module in _RETIRED_CHARACTER_MODULES
            )
    assert stale_imports == []

    progression_source = (_ROOT / "dnd/core/progression.py").read_text(
        encoding="utf-8",
    )
    assert "CHARACTER_RULESET_SCHEMA_VERSION" not in progression_source
    assert "character_ruleset_digest" not in progression_source

    durable_importers: list[str] = []
    for path in _production_python_paths():
        relative_path = path.relative_to(_ROOT).as_posix()
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (
                isinstance(node, ast.ImportFrom)
                and node.module == "dnd.core.content.durable_characters"
            ):
                durable_importers.append(relative_path)
    assert durable_importers == ["dnd/core/content/character_deployment.py"]


def test_ability_names_have_one_dependency_leaf_authority() -> None:
    declarations: dict[str, list[str]] = {name: [] for name in _ABILITY_NAMES}
    stale_imports: list[tuple[str, str, str]] = []
    duplicate_ability_literals: list[str] = []

    for path in _production_python_paths():
        relative_path = path.relative_to(_ROOT).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Subscript):
                literal_name = (
                    node.value.id
                    if isinstance(node.value, ast.Name)
                    else node.value.attr
                    if isinstance(node.value, ast.Attribute)
                    else None
                )
                slice_nodes = (
                    node.slice.elts
                    if isinstance(node.slice, ast.Tuple)
                    else (node.slice,)
                )
                literal_values = {
                    item.value
                    for item in slice_nodes
                    if isinstance(item, ast.Constant)
                    and isinstance(item.value, str)
                }
                if (
                    literal_name == "Literal"
                    and literal_values == _ABILITY_VALUES
                    and relative_path != "dnd/types/abilities.py"
                ):
                    duplicate_ability_literals.append(relative_path)
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for target in targets:
                    if isinstance(target, ast.Name) and target.id in declarations:
                        declarations[target.id].append(relative_path)
            if not isinstance(node, ast.ImportFrom):
                continue
            imported = _ABILITY_NAMES.intersection(alias.name for alias in node.names)
            if imported and node.module in {
                "dnd.core.events",
                "dnd.blocks.saving_throws",
            }:
                stale_imports.extend(
                    (relative_path, node.module, name)
                    for name in sorted(imported)
                )

    assert declarations == {
        "AbilityName": ["dnd/types/abilities.py"],
        "SkillName": ["dnd/types/abilities.py"],
        "SavingThrowName": ["dnd/types/abilities.py"],
    }
    assert stale_imports == []
    assert duplicate_ability_literals == []


def test_character_value_and_receipt_modules_remain_dependency_leaves() -> None:
    forbidden_imports: list[tuple[str, str]] = []
    forbidden_runtime_devices: list[tuple[str, str]] = []

    for relative_path in _LEAF_PATHS:
        for node in ast.walk(_tree(relative_path)):
            if isinstance(node, ast.Import):
                modules = tuple(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                modules = (node.module or "",)
            else:
                modules = ()
            for module in modules:
                if module.startswith(("dnd.core", "dnd.blocks", "dnd.content")):
                    forbidden_imports.append((relative_path, module))

            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in {"getattr", "isinstance", "type"}:
                    forbidden_runtime_devices.append((relative_path, node.func.id))
            if isinstance(node, ast.Name) and node.id == "TYPE_CHECKING":
                forbidden_runtime_devices.append((relative_path, "TYPE_CHECKING"))
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                parent = getattr(node, "_cr45_parent", None)
                if parent is not None and not isinstance(parent, ast.Module):
                    forbidden_runtime_devices.append((relative_path, "late import"))

    assert forbidden_imports == []
    assert forbidden_runtime_devices == []


def test_required_owner_schemas_are_direct_and_level_facts_are_narrow() -> None:
    assert "provider_id" in SpellcastingSource.model_fields
    assert "provider_ref" not in SpellcastingSource.model_fields
    assert "spell_id" in LearnedReactionSpellOwnership.model_fields
    assert "spell_ref" not in LearnedReactionSpellOwnership.model_fields
    assert set(LearnedReactionSpellSource.model_fields) == {
        "source_id",
        "fixed_cast_rank",
        "resource_name",
    }
    assert "sources" in LearnedReactionSpellOwnership.model_fields
    assert "source_ids" not in LearnedReactionSpellOwnership.model_fields
    assert "provider_id" in AttackMultiplicityGrant.__dataclass_fields__
    assert "provider_ref" not in AttackMultiplicityGrant.__dataclass_fields__

    for event_type in (EntityLevelAddedEvent, EntityLevelRemovedEvent):
        assert "level" in event_type.model_fields
        assert "applied_class_levels" in event_type.model_fields
        assert "items" not in event_type.model_fields
        assert "ability_scores" not in event_type.model_fields


def test_entity_owns_state_not_progression_and_actions_keep_template_identity() -> None:
    required_state = {
        "character_body_id",
        "character_species",
        "character_species_variant",
        "character_background",
        "applied_origin_state",
        "applied_class_levels",
        "feature_sources",
        "prepared_spell_selections",
        "feature_toggle_selections",
    }
    retired_state = {
        "character_species_ref",
        "character_species_variant_ref",
        "character_background_ref",
        "character_origin_state",
        "character_class_levels",
        "character_feature_ids",
        "character_prepared_spell_ids",
        "character_feature_toggle_ids",
    }

    assert required_state <= Entity.model_fields.keys()
    assert retired_state.isdisjoint(Entity.model_fields)
    assert "_character_grant_receipts" in Entity.__private_attributes__
    assert "registered_template_uuid" in BaseAction.model_fields
    assert BaseAction.model_fields["registered_template_uuid"].frozen is True

    entity_methods = {
        node.name
        for node in ast.walk(_tree("dnd/entity.py"))
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert {
        "add_level",
        "remove_level",
        "add_character_level",
        "remove_character_level",
        "hydrate_character",
        "materialize_character",
    }.isdisjoint(entity_methods)


def test_receipts_name_concrete_entity_owned_surfaces() -> None:
    receipt_fields = {
        receipt_type: {field.name for field in fields(receipt_type)}
        for receipt_type in (
            OriginGrantReceipt,
            FighterGrantReceipt,
            BarbarianGrantReceipt,
            SorcererGrantReceipt,
        )
    }
    assert receipt_fields == {
        OriginGrantReceipt: {
            "step_id",
            "source_id",
            "ability_score_modifier_ids",
            "skill_proficiency_sources",
            "creature_proficiency_source_ids",
            "saving_throw_advantage_modifier_ids",
            "damage_resistance_modifier_ids",
            "melee_critical_extra_dice_modifier_ids",
            "maximum_hit_point_modifier_ids",
            "walking_speed_modifier_ids",
            "action_uuids",
            "darkness_root_owner_action_uuids",
            "handler_uuids",
            "resource_contributions",
            "sense_source_ids",
            "size_source_ids",
            "capability_sources",
            "feature_sources",
            "spell_source_ids",
            "learned_reaction_spell_sources",
        },
        FighterGrantReceipt: {
            "step_id",
            "source_id",
            "hit_die_uuids",
            "skill_proficiency_sources",
            "saving_throw_proficiency_sources",
            "creature_proficiency_source_ids",
            "ability_score_modifier_ids",
            "ability_check_proficiency_sources",
            "ranged_attack_bonus_modifier_ids",
            "armor_class_bonus_modifier_ids",
            "melee_damage_bonus_modifier_ids",
            "off_hand_melee_ability_bonus_modifier_ids",
            "off_hand_ranged_ability_bonus_modifier_ids",
            "melee_critical_threshold_modifier_ids",
            "ranged_critical_threshold_modifier_ids",
            "jump_distance_additive_modifier_ids",
            "action_uuids",
            "handler_uuids",
            "resource_contributions",
            "attack_multiplicity_grant_ids",
            "feature_sources",
        },
        BarbarianGrantReceipt: {
            "step_id",
            "source_id",
            "hit_die_uuids",
            "skill_proficiency_sources",
            "saving_throw_proficiency_sources",
            "creature_proficiency_source_ids",
            "ability_score_modifier_ids",
            "dexterity_save_advantage_modifier_ids",
            "walking_speed_modifier_ids",
            "initiative_advantage_modifier_ids",
            "melee_critical_extra_dice_modifier_ids",
            "action_uuids",
            "raging_root_owner_action_uuids",
            "reckless_root_owner_action_uuids",
                "handler_uuids",
                "resource_contributions",
                "armor_class_formula_ids",
                "attack_multiplicity_grant_ids",
                "condition_immunity_sources",
                "feature_sources",
                "replaced_rage_action_uuid",
                "replaced_rage_action_index",
                "replaced_rage_damage",
                "replaced_rage_mindless",
                "replaced_rage_persistent",
            },
        SorcererGrantReceipt: {
            "step_id",
            "source_id",
            "hit_die_uuids",
            "skill_proficiency_sources",
            "saving_throw_proficiency_sources",
            "creature_proficiency_source_ids",
            "ability_score_modifier_ids",
            "maximum_hit_point_modifier_ids",
            "action_uuids",
            "metamagic_root_owner_action_uuids",
            "elemental_affinity_root_owner_action_uuids",
            "dragon_wings_root_owner_action_uuids",
            "draconic_presence_root_owner_action_uuids",
            "handler_uuids",
            "resource_contributions",
            "resource_recovery_contributions",
            "spell_source_ids",
            "normal_spell_slot_capacity_ids",
            "learned_reaction_spell_sources",
            "spell_affinity_contribution_ids",
            "armor_class_formula_ids",
            "feature_sources",
            "replaced_spell_id",
            "replaced_spell_action_uuid",
            "replaced_spell_action_index",
            "replaced_reaction_spell_source",
            "replaced_reaction_spell_handler_was_enabled",
        },
    }


def test_direct_origin_definitions_are_cold_and_do_not_load_gameplay() -> None:
    marker = "__DIRECT_ORIGIN_IMPORTS__="
    script = (
        "import json, sys\n"
        "import dnd.content.characters.origin_definitions\n"
        "forbidden = ('dnd.entity', 'dnd.actions', 'dnd.conditions', "
        "'dnd.spells', 'dnd.content_system')\n"
        "loaded = sorted(name for name in sys.modules if any("
        "name == prefix or name.startswith(prefix + '.') for prefix in forbidden))\n"
        f"print({marker!r} + json.dumps(loaded))\n"
    )
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    marker_lines = [
        line for line in completed.stdout.splitlines() if line.startswith(marker)
    ]
    assert len(marker_lines) == 1
    assert json.loads(marker_lines[0][len(marker):]) == []


def test_direct_origin_path_has_one_procedural_owner_and_no_runtime_devices() -> None:
    direct_paths = (
        "dnd/content/characters/origin_definitions.py",
        "dnd/content/characters/origin_grants.py",
    )
    forbidden_imports: list[tuple[str, str]] = []
    forbidden_devices: list[tuple[str, str, int]] = []

    for relative_path in direct_paths:
        tree = _tree(relative_path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = tuple(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                modules = (node.module or "",)
            else:
                modules = ()
            for module in modules:
                if module.startswith("dnd.content_system"):
                    forbidden_imports.append((relative_path, module))
                if module == "dnd.core.content.runtime":
                    imported = {
                        alias.name
                        for alias in node.names
                    } if isinstance(node, ast.ImportFrom) else set()
                    if imported != {"BehaviorBinding"}:
                        forbidden_imports.append((relative_path, module))

            if isinstance(node, (ast.Import, ast.ImportFrom)):
                parent = getattr(node, "_cr45_parent", None)
                if parent is not None and not isinstance(parent, ast.Module):
                    forbidden_devices.append((relative_path, "late import", node.lineno))
            if isinstance(node, ast.Name) and node.id == "TYPE_CHECKING":
                forbidden_devices.append((relative_path, "TYPE_CHECKING", node.lineno))
            if isinstance(node, ast.Call):
                name = (
                    node.func.id
                    if isinstance(node.func, ast.Name)
                    else node.func.attr
                    if isinstance(node.func, ast.Attribute)
                    else ""
                )
                if name in {
                    "getattr",
                    "setattr",
                    "get_all_entities",
                    "bind_runtime_behavior_child",
                    "resolve_definition",
                    "resolve_typed_definition",
                }:
                    forbidden_devices.append((relative_path, name, node.lineno))
                if (
                    isinstance(node.func, ast.Attribute)
                    and node.func.attr == "get"
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "BaseBlock"
                ):
                    forbidden_devices.append(
                        (relative_path, "BaseBlock.get", node.lineno)
                    )

    assert forbidden_imports == []
    assert forbidden_devices == []


def test_legacy_origin_behaviors_are_not_installed_content() -> None:
    retired_ids = {
        "action.origin.dragonborn.breath_weapon",
        "trait.origin.half_orc.relentless_endurance",
        "trait.origin.halfling.lucky",
    }
    installed_ids = {
        declaration.ref.content_id
        for declaration in BUILT_IN_DECLARATION_INVENTORY
    }

    assert retired_ids.isdisjoint(installed_ids)
    for relative_path in (
        "dnd/origins/dragonborn.py",
        "dnd/origins/half_orc.py",
        "dnd/origins/halfling.py",
    ):
        source = (_ROOT / relative_path).read_text(encoding="utf-8")
        assert "ContentDeclaration" not in source
        assert "behavior_definition" not in source


def test_legacy_origin_runtime_paths_are_deleted_and_have_no_active_importer() -> None:
    retired_modules = {
        "dnd.content_system.character_materialization",
        "dnd.content_system.dragonborn_character_grant_appliers",
        "dnd.content_system.origin_character_grant_appliers",
        "dnd.content_system.origin_innate_spellcasting",
        "dnd.content_system.origin_runtime_character_grant_appliers",
    }
    for module in retired_modules:
        assert not (_ROOT / f"{module.replace('.', '/')}.py").exists()

    stale_imports: list[tuple[str, str]] = []
    for path in _production_python_paths():
        relative_path = path.relative_to(_ROOT).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = tuple(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                modules = (node.module or "",)
            else:
                modules = ()
            stale_imports.extend(
                (relative_path, module)
                for module in modules
                if module in retired_modules
            )

    assert stale_imports == []

    inventory_source = (
        _ROOT / "dnd/content_system/builtin_inventory.py"
    ).read_text(encoding="utf-8")
    assert "SRD_CHARACTER_ORIGIN_DECLARATIONS" not in inventory_source
    assert "SRD_PASSIVE_ORIGIN_FEATURE_DECLARATIONS" not in inventory_source
    assert "DRAGONBORN_ANCESTRY_DECLARATIONS" not in inventory_source
    assert "ACOLYTE_STARTING_HOLDINGS_DECLARATION" not in inventory_source


def test_tiefling_darkness_cleanup_uses_the_exact_action_owned_slot() -> None:
    origin_source = (
        _ROOT / "dnd/content/characters/origin_grants.py"
    ).read_text(encoding="utf-8")
    darkness_source = (
        _ROOT / "dnd/spells/conjuration.py"
    ).read_text(encoding="utf-8")
    direct_test_source = (
        _ROOT / "tests/progression/test_direct_character_origins.py"
    ).read_text(encoding="utf-8")

    assert "active_concentration_slot_uuid" in darkness_source
    assert "get_slot_by_spell_name" not in origin_source
    assert "_randint" not in direct_test_source


def test_learned_reaction_handler_reads_current_source_cost_facts() -> None:
    origin_source = (
        _ROOT / "dnd/content/characters/origin_grants.py"
    ).read_text(encoding="utf-8")
    infernal_source = (
        _ROOT / "dnd/spells/infernal.py"
    ).read_text(encoding="utf-8")

    assert "learned_reaction_spell_handler_uuid" in origin_source
    assert "fixed_cast_rank=2" in origin_source
    assert "resource_name=_TIEFLING_REBUKE_RESOURCE" in origin_source
    factory_source = infernal_source.split(
        "def create_hellish_rebuke_reaction_handler(",
        maxsplit=1,
    )[1].split("THAUMATURGY_METADATA", maxsplit=1)[0]
    assert "spellcasting_source_id" not in factory_source
    assert "fixed_cast_rank" not in factory_source
    assert "resource_name" not in factory_source


def test_direct_martial_paths_are_explicit_and_have_no_runtime_routing_devices() -> None:
    direct_paths = (
        "dnd/content/characters/class_definitions.py",
        "dnd/content/characters/barbarian_grants.py",
        "dnd/content/characters/fighter_grants.py",
        "dnd/content/characters/sorcerer_grants.py",
        "dnd/content/characters/progression.py",
        "dnd/content/characters/builds.py",
        "dnd/content/characters/premades.py",
    )
    forbidden_imports: list[tuple[str, str]] = []
    forbidden_devices: list[tuple[str, str, int]] = []

    for relative_path in direct_paths:
        tree = _tree(relative_path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = tuple(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                modules = (node.module or "",)
            else:
                modules = ()
            for module in modules:
                if module.startswith("dnd.content_system"):
                    forbidden_imports.append((relative_path, module))
                if module == "dnd.core.content.runtime":
                    imported = {
                        alias.name for alias in node.names
                    } if isinstance(node, ast.ImportFrom) else set()
                    if imported != {"BehaviorBinding"}:
                        forbidden_imports.append((relative_path, module))

            if isinstance(node, (ast.Import, ast.ImportFrom)):
                parent = getattr(node, "_cr45_parent", None)
                if parent is not None and not isinstance(parent, ast.Module):
                    forbidden_devices.append((relative_path, "late import", node.lineno))
            if isinstance(node, ast.Name) and node.id == "TYPE_CHECKING":
                forbidden_devices.append((relative_path, "TYPE_CHECKING", node.lineno))
            if isinstance(node, ast.Call):
                name = (
                    node.func.id
                    if isinstance(node.func, ast.Name)
                    else node.func.attr
                    if isinstance(node.func, ast.Attribute)
                    else ""
                )
                if name in {
                    "getattr",
                    "setattr",
                    "isinstance",
                    "type",
                    "get_all_entities",
                    "bind_runtime_behavior_child",
                    "resolve_definition",
                    "resolve_typed_definition",
                }:
                    forbidden_devices.append((relative_path, name, node.lineno))

    assert forbidden_imports == []
    assert forbidden_devices == []


def test_legacy_fighter_path_is_cut_but_shared_features_remain_admitted() -> None:
    retired_modules = {
        "dnd.content_system.fighter_character_grant_appliers",
        "dnd.content_system.builtin_character_grant_appliers",
    }
    for module in retired_modules:
        assert not (_ROOT / f"{module.replace('.', '/')}.py").exists()

    stale_imports: list[tuple[str, str]] = []
    for path in _production_python_paths():
        relative_path = path.relative_to(_ROOT).as_posix()
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                modules = tuple(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                modules = (node.module or "",)
            else:
                modules = ()
            stale_imports.extend(
                (relative_path, module)
                for module in modules
                if module in retired_modules
            )
    assert stale_imports == []

    installed_ids = {
        declaration.ref.content_id
        for declaration in BUILT_IN_DECLARATION_INVENTORY
    }
    assert FIGHTER_RETIRED_DECLARATION_IDS.isdisjoint(installed_ids)
    assert "feat.lucky" in installed_ids

    inventory_source = (
        _ROOT / "dnd/content_system/builtin_inventory.py"
    ).read_text(encoding="utf-8")
    assert "FIGHTER_PROGRESSION_DECLARATIONS" not in inventory_source


def test_legacy_barbarian_path_is_cut_but_monster_behaviors_remain_admitted() -> None:
    retired_modules = {
        "dnd.content_system.barbarian_character_grant_appliers",
        "dnd.content_system.builtin_character_grant_appliers",
    }
    for module in retired_modules:
        assert not (_ROOT / f"{module.replace('.', '/')}.py").exists()

    stale_imports: list[tuple[str, str]] = []
    for path in _production_python_paths():
        relative_path = path.relative_to(_ROOT).as_posix()
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                modules = tuple(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                modules = (node.module or "",)
            else:
                modules = ()
            stale_imports.extend(
                (relative_path, module)
                for module in modules
                if module in retired_modules
            )
    assert stale_imports == []

    installed_ids = {
        declaration.ref.content_id
        for declaration in BUILT_IN_DECLARATION_INVENTORY
    }
    assert BARBARIAN_RETIRED_DECLARATION_IDS.isdisjoint(installed_ids)
    assert {
        "action.class.barbarian.reckless_attack",
        "class_feature.barbarian.reckless_attacking",
        "feat.lucky",
    } <= installed_ids

    inventory_source = (
        _ROOT / "dnd/content_system/builtin_inventory.py"
    ).read_text(encoding="utf-8")
    assert "BARBARIAN_PROGRESSION_DECLARATIONS" not in inventory_source


def test_legacy_sorcerer_path_is_cut_but_shared_spells_remain_admitted() -> None:
    retired_modules = {
        "dnd.content_system.sorcerer_character_grant_appliers",
        "dnd.content_system.builtin_character_grant_appliers",
    }
    for module in retired_modules:
        assert not (_ROOT / f"{module.replace('.', '/')}.py").exists()

    stale_imports: list[tuple[str, str]] = []
    for path in _production_python_paths():
        relative_path = path.relative_to(_ROOT).as_posix()
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                modules = tuple(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                modules = (node.module or "",)
            else:
                modules = ()
            stale_imports.extend(
                (relative_path, module)
                for module in modules
                if module in retired_modules
            )
    assert stale_imports == []

    installed_ids = {
        declaration.ref.content_id
        for declaration in BUILT_IN_DECLARATION_INVENTORY
    }
    assert SORCERER_RETIRED_DECLARATION_IDS.isdisjoint(installed_ids)
    assert {
        "feat.lucky",
        "spell.magic_missile",
        "spell.shield",
    } <= installed_ids

    inventory_source = (
        _ROOT / "dnd/content_system/builtin_inventory.py"
    ).read_text(encoding="utf-8")
    assert "SORCERER_PROGRESSION_DECLARATIONS" not in inventory_source
    assert "SORCERER_STRUCTURAL_FEATURE_DECLARATIONS" not in inventory_source

    for relative_path in (
        "dnd/content_system/action_definitions.py",
        "dnd/content_system/condition_definitions.py",
        "dnd/content_system/condition_effect_population.py",
    ):
        assert "dnd.classes.sorcerer" not in (
            _ROOT / relative_path
        ).read_text(encoding="utf-8")
