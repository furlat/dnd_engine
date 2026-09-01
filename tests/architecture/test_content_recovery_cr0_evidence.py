"""Public evidence gates for the CR-0 content-recovery freeze.

The manifest is audit data.  These tests read it directly and prove that it
still describes the public content boundaries in this checkout; production
code never loads it.
"""

from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import sys
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Any

from dnd.content_system.builtin_character_builds import BUILTIN_PREMADE_BUILDS
from dnd.content_system.builtin_inventory import BUILT_IN_DECLARATION_INVENTORY
from dnd.content_system.builtin_inventory import BUILT_IN_RECIPE_PRESET_INVENTORY
from dnd.content_system.character_appearance import BARBARIAN_HUMAN_APPEARANCE
from dnd.content_system.character_appearance import FIGHTER_HUMAN_APPEARANCE
from dnd.content_system.character_appearance import PLAYER_CHARACTER_APPEARANCE_OPTIONS
from dnd.content_system.character_appearance import SORCERER_HUMAN_APPEARANCE
from dnd.monsters.bestiary import CASTER_APPEARANCE
from dnd.monsters.bestiary import GOBLIN_APPEARANCE
from dnd.monsters.bestiary import SKELETON_APPEARANCE
from dnd.monsters.bestiary_content import BESTIARY_CREATURE_WARDROBE_GRANTS_BY_KEY
from dnd.monsters.configured_srd_creatures import (
    CONFIGURED_SRD_CREATURE_WARDROBE_GRANTS_BY_ID,
)
from dnd.monsters.srd_roster import SRD_CREATURE_DECLARATIONS


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = (
    REPOSITORY_ROOT
    / "content_data"
    / "ledgers"
    / "content_recovery_cr0_evidence.json"
)
MANIFEST_REPOSITORY_PATH = MANIFEST_PATH.relative_to(REPOSITORY_ROOT).as_posix()
REQUIRED_TOP_LEVEL_FIELDS = {
    "schema_version",
    "authority",
    "source_artifacts",
    "legacy_authorities",
    "implemented_content",
    "binding_reconciliation",
    "python_binding_overlay",
    "srd_proof_overlay",
    "production_importers",
    "excluded_or_rescued_test_modules",
    "maintained_in_process_nodes",
}
EXPECTED_SECTION_COUNTS = {
    "source_artifacts": 14,
    "legacy_authorities": 1_551,
    "implemented_content": 1_014,
    "python_binding_overlay": 788,
    "srd_proof_overlay": 182,
    "production_importers": 234,
    "excluded_or_rescued_test_modules": 81,
    "maintained_in_process_nodes": 105,
}
EXPECTED_DECLARATION_MODES = Counter(
    {"factory": 191, "behavior_identity": 395, "typed_definition": 87}
)
CURRENT_EVIDENCE_STATES = {
    "current_and_accepted",
    "current_only_keep",
    "conflict_requires_owner_cut",
}
ACCEPTED_COMMIT = "513dd97"
ACCEPTED_DIRECT_ITEM_ONLY = {
    "apparel.cloth_shoes.blue",
    "apparel.cloth_shoes.dark",
    "apparel.cloth_shoes.red",
    "apparel.common_clothes.farmhand_tunic",
    "apparel.common_clothes.peasant_rags",
    "apparel.costume.pit_fighter_wrap",
    "apparel.iron_helmet.steel",
    "apparel.leather_boots.brown",
    "apparel.leather_boots.dark",
    "apparel.leather_shoes.brown",
    "apparel.robes.acolyte_vestments",
    "apparel.robes.dark_cultist",
    "apparel.robes.hedge_wizard",
    "apparel.robes.necromancer",
    "apparel.robes.priest_vestments",
    "apparel.robes.red_mage",
    "apparel.robes.wizard",
    "apparel.sandals.rope",
    "apparel.travelers_clothes.thief_garb",
    "apparel.wizard_hat.red",
    "environment.cliff_face",
}


@lru_cache(maxsize=1)
def _manifest() -> dict[str, Any]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _git(*arguments: str) -> bytes:
    return subprocess.check_output(
        ["git", *arguments],
        cwd=REPOSITORY_ROOT,
    )


def _artifact_bytes(row: dict[str, Any]) -> bytes:
    location = row["git_object_or_path"]
    if row["source_tier"] == "current_reconstructed_engine":
        return (REPOSITORY_ROOT / location).read_bytes()
    return _git("show", location)


def _artifact_json(artifact_id: str) -> Any:
    row = next(
        row
        for row in _manifest()["source_artifacts"]
        if row["artifact_id"] == artifact_id
    )
    return json.loads(_artifact_bytes(row))


def _content_ref_identity(ref: dict[str, Any]) -> str:
    return (
        f"{ref['pack_id']}:{ref['definition_kind']}:"
        f"{ref['content_id']}@{ref['content_version']}"
    )


def _preset_ref_identity(ref: dict[str, Any]) -> str:
    return f"{ref['pack_id']}:preset:{ref['preset_id']}@{ref['preset_version']}"


@lru_cache(maxsize=1)
def _source_tree(repository_path: str) -> ast.Module:
    path = REPOSITORY_ROOT / repository_path
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _declarations() -> dict[str, Any]:
    return {
        declaration.ref.identity_key: declaration
        for declaration in BUILT_IN_DECLARATION_INVENTORY
    }


def _presets() -> dict[str, Any]:
    return {
        preset.ref.identity_key: preset
        for preset in BUILT_IN_RECIPE_PRESET_INVENTORY
    }


def _assigned_names(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        else:
            continue
        names.update(target.id for target in targets if isinstance(target, ast.Name))
    return names


def _assignment_line(tree: ast.Module, name: str) -> int:
    for node in tree.body:
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        else:
            continue
        if any(
            isinstance(target, ast.Name) and target.id == name
            for target in targets
        ):
            return node.lineno
    raise AssertionError(f"missing assignment for {name}")


def _definition_locations(tree: ast.Module) -> set[tuple[str, int]]:
    locations: set[tuple[str, int]] = set()

    def visit(body: list[ast.stmt], prefix: str = "") -> None:
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                qualified_name = f"{prefix}{node.name}"
                start_line = min(
                    [node.lineno, *(decorator.lineno for decorator in node.decorator_list)]
                )
                locations.add((qualified_name, start_line))
                visit(node.body, f"{qualified_name}.<locals>.")
            elif isinstance(node, ast.ClassDef):
                qualified_name = f"{prefix}{node.name}"
                start_line = min(
                    [node.lineno, *(decorator.lineno for decorator in node.decorator_list)]
                )
                locations.add((qualified_name, start_line))
                visit(node.body, f"{qualified_name}.")

    visit(tree.body)
    return locations


def _legacy_declaration_rows() -> dict[str, dict[str, Any]]:
    return {
        row["legacy_identity"]: row
        for row in _manifest()["legacy_authorities"]
        if row["authority_kind"] == "declaration"
    }


def _literal_string(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _assignment_value(tree: ast.Module, name: str) -> ast.AST:
    for node in tree.body:
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        else:
            continue
        if any(isinstance(target, ast.Name) and target.id == name for target in targets):
            return node.value
    raise AssertionError(f"missing assignment for {name}")


def _call_bindings(call: ast.Call, tree: ast.Module) -> dict[str, ast.AST]:
    """Bind one local helper/spec call without executing authored content."""
    parameter_names: list[str] = []
    if isinstance(call.func, ast.Name):
        definition = next(
            (
                node
                for node in tree.body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                and node.name == call.func.id
            ),
            None,
        )
        if isinstance(definition, (ast.FunctionDef, ast.AsyncFunctionDef)):
            parameter_names = [
                argument.arg
                for argument in (
                    *definition.args.posonlyargs,
                    *definition.args.args,
                    *definition.args.kwonlyargs,
                )
            ]
        elif isinstance(definition, ast.ClassDef):
            parameter_names = [
                node.target.id
                for node in definition.body
                if isinstance(node, ast.AnnAssign)
                and isinstance(node.target, ast.Name)
            ]
    bindings = dict(zip(parameter_names, call.args, strict=False))
    bindings.update(
        (keyword.arg, keyword.value)
        for keyword in call.keywords
        if keyword.arg is not None
    )
    return bindings


def _module_path(module: str) -> str:
    base = REPOSITORY_ROOT.joinpath(*module.split("."))
    file_path = base.with_suffix(".py")
    if file_path.is_file():
        return file_path.relative_to(REPOSITORY_ROOT).as_posix()
    init_path = base / "__init__.py"
    assert init_path.is_file(), module
    return init_path.relative_to(REPOSITORY_ROOT).as_posix()


def _import_bindings(tree: ast.Module) -> dict[str, tuple[str, str | None]]:
    bindings: dict[str, tuple[str, str | None]] = {}
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                local_name = alias.asname or alias.name.split(".", 1)[0]
                bindings[local_name] = (alias.name, None)
        elif isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                if alias.name != "*":
                    bindings[alias.asname or alias.name] = (node.module, alias.name)
    return bindings


@lru_cache(maxsize=None)
def _module_definition(module: str, symbol: str) -> tuple[str, str]:
    source_path = _module_path(module)
    tree = _source_tree(source_path)
    top_level = {
        name: line
        for name, line in _definition_locations(tree)
        if "." not in name
    }
    if symbol in top_level:
        return source_path, f"{symbol}:{top_level[symbol]}"
    imported = _import_bindings(tree).get(symbol)
    assert imported is not None and imported[1] is not None, (module, symbol)
    return _module_definition(imported[0], imported[1])


def _resolve_definition(
    expression: ast.AST,
    source_path: str,
    tree: ast.Module,
) -> tuple[str, str]:
    if isinstance(expression, ast.Name):
        top_level = {
            name: line
            for name, line in _definition_locations(tree)
            if "." not in name
        }
        if expression.id in top_level:
            return source_path, f"{expression.id}:{top_level[expression.id]}"
        imported = _import_bindings(tree)[expression.id]
        assert imported[1] is not None
        return _module_definition(imported[0], imported[1])
    assert isinstance(expression, ast.Attribute)
    parts: list[str] = []
    current: ast.AST = expression
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    assert isinstance(current, ast.Name)
    imported = _import_bindings(tree)[current.id]
    assert imported[1] is None
    assert len(parts) == 1
    return _module_definition(imported[0], parts[0])


def _semantic_ids_for_mode(mode: str) -> set[str]:
    return {
        declaration.ref.content_id
        for declaration in BUILT_IN_DECLARATION_INVENTORY
        if declaration.mode.value == mode
    }


def _record_owner(
    owners: dict[str, dict[str, str]],
    semantic_id: str,
    source_path: str,
    source_symbol: str,
) -> None:
    owner = {"source_path": source_path, "source_symbol": source_symbol}
    existing = owners.setdefault(semantic_id, owner)
    assert existing == owner, (semantic_id, existing, owner)


def _static_behavior_owners() -> dict[str, dict[str, str]]:
    expected = _semantic_ids_for_mode("behavior_identity")
    owners: dict[str, dict[str, str]] = {}
    owner_fields = (
        "action_type",
        "condition_type",
        "handler_type",
        "spell_type",
        "behavior_type",
    )
    for path in _tracked_python_paths("dnd/"):
        source_path = path.relative_to(REPOSITORY_ROOT).as_posix()
        tree = _source_tree(source_path)
        for node in ast.walk(tree):
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                for decorator in node.decorator_list:
                    if not isinstance(decorator, ast.Call):
                        continue
                    content_id = _literal_string(
                        _call_bindings(decorator, tree).get("content_id")
                    )
                    if content_id in expected:
                        line = min(
                            node.lineno,
                            *(entry.lineno for entry in node.decorator_list),
                        )
                        _record_owner(
                            owners,
                            content_id,
                            source_path,
                            f"{node.name}:{line}",
                        )
            if not isinstance(node, ast.Call):
                continue
            bindings = _call_bindings(node, tree)
            content_id = _literal_string(bindings.get("content_id"))
            if content_id not in expected:
                continue
            owner_expression = next(
                (bindings[field] for field in owner_fields if field in bindings),
                None,
            )
            if owner_expression is None:
                continue
            owner_path, owner_symbol = _resolve_definition(
                owner_expression,
                source_path,
                tree,
            )
            _record_owner(owners, content_id, owner_path, owner_symbol)
    assert set(owners) == expected
    return owners


def _nested_definition_line(tree: ast.Module, parent: str, child: str) -> int:
    qualified_name = f"{parent}.<locals>.{child}"
    return next(
        line
        for name, line in _definition_locations(tree)
        if name == qualified_name
    )


def _tuple_call_keyword_values(
    tree: ast.Module,
    assignment_name: str,
    call_name: str,
    keyword_name: str,
) -> tuple[str, ...]:
    value = _assignment_value(tree, assignment_name)
    return tuple(
        literal
        for node in ast.walk(value)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == call_name
        and (literal := _literal_string(_call_bindings(node, tree).get(keyword_name)))
        is not None
    )


def _static_factory_owners() -> dict[str, dict[str, str]]:
    expected = _semantic_ids_for_mode("factory")
    owners: dict[str, dict[str, str]] = {}
    for path in _tracked_python_paths("dnd/"):
        source_path = path.relative_to(REPOSITORY_ROOT).as_posix()
        tree = _source_tree(source_path)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in node.decorator_list:
                if not isinstance(decorator, ast.Call):
                    continue
                content_id = _literal_string(
                    _call_bindings(decorator, tree).get("content_id")
                )
                if content_id in expected:
                    line = min(
                        node.lineno,
                        *(entry.lineno for entry in node.decorator_list),
                    )
                    _record_owner(
                        owners,
                        content_id,
                        source_path,
                        f"{node.name}:{line}",
                    )

    configured_path = "dnd/monsters/configured_srd_creatures.py"
    configured_tree = _source_tree(configured_path)
    configured_line = _nested_definition_line(
        configured_tree,
        "_declare_configured_srd_creature",
        "factory",
    )
    configured_ids = {
        literal
        for node in ast.walk(
            _assignment_value(
                configured_tree,
                "CONFIGURED_SRD_CREATURE_WARDROBE_GRANTS_BY_ID",
            )
        )
        if (literal := _literal_string(node)) is not None
        and f"creature.configured_srd.{literal}" in expected
    }
    for creature_id in configured_ids:
        _record_owner(
            owners,
            f"creature.configured_srd.{creature_id}",
            configured_path,
            f"_build_configured_srd_{creature_id}:{configured_line}",
        )

    roster_path = "dnd/monsters/srd_roster.py"
    roster_tree = _source_tree(roster_path)
    roster_line = _nested_definition_line(roster_tree, "_declare_srd_creature", "factory")
    for creature_id in _tuple_call_keyword_values(
        roster_tree,
        "_SRD_CREATURE_FACTS",
        "_SrdCreatureFacts",
        "creature_id",
    ):
        _record_owner(
            owners,
            f"creature.{creature_id}",
            roster_path,
            f"_build_{creature_id}:{roster_line}",
        )

    assert set(owners) == expected
    return owners


def _tuple_literal_rows(tree: ast.Module, assignment_name: str) -> tuple[ast.Tuple, ...]:
    value = _assignment_value(tree, assignment_name)
    assert isinstance(value, (ast.Tuple, ast.List))
    return tuple(row for row in value.elts if isinstance(row, ast.Tuple))


def _static_structural_owners() -> dict[str, dict[str, str]]:
    expected = _semantic_ids_for_mode("typed_definition")
    owners: dict[str, dict[str, str]] = {}
    direct_collections = {
        "dnd/classes/barbarian_progression_definitions.py": "BARBARIAN_PROGRESSION_DECLARATIONS",
        "dnd/classes/progression_definitions.py": "FIGHTER_PROGRESSION_DECLARATIONS",
        "dnd/classes/sorcerer_progression_definitions.py": "SORCERER_PROGRESSION_DECLARATIONS",
        "dnd/content_system/acolyte_starting_holdings.py": "ACOLYTE_STARTING_HOLDINGS_DECLARATION",
        "dnd/content_system/origin_feature_definitions.py": "SRD_PASSIVE_ORIGIN_FEATURE_DECLARATIONS",
        "dnd/monsters/multiattack_definitions.py": "SRD_MULTIATTACK_CONFIGURATION_DECLARATIONS",
    }
    for source_path, collection in direct_collections.items():
        tree = _source_tree(source_path)
        assert collection in _assigned_names(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            content_id = _literal_string(_call_bindings(node, tree).get("content_id"))
            if content_id in expected:
                _record_owner(owners, content_id, source_path, collection)

    equipment_path = "dnd/content_system/starting_equipment_definitions.py"
    equipment_tree = _source_tree(equipment_path)
    equipment_owner = "STARTING_EQUIPMENT_PACKAGE_DECLARATIONS"
    assert equipment_owner in _assigned_names(equipment_tree)
    for row in _tuple_literal_rows(equipment_tree, "_PACKAGE_ROWS"):
        class_id = _literal_string(row.elts[0])
        preset_id = _literal_string(row.elts[1])
        assert class_id is not None and preset_id is not None
        _record_owner(
            owners,
            f"starting_equipment.{class_id}.{preset_id}",
            equipment_path,
            equipment_owner,
        )

    apparel_path = "dnd/content_system/starting_apparel_definitions.py"
    apparel_tree = _source_tree(apparel_path)
    apparel_owner = "STARTING_APPAREL_PACKAGE_DECLARATIONS"
    assert apparel_owner in _assigned_names(apparel_tree)
    for row in _tuple_literal_rows(apparel_tree, "_PACKAGE_ROWS"):
        apparel_id = _literal_string(row.elts[0])
        assert apparel_id is not None
        _record_owner(
            owners,
            f"starting_apparel.{apparel_id}",
            apparel_path,
            apparel_owner,
        )

    ancestry_path = "dnd/content_system/dragonborn_origin_definitions.py"
    ancestry_tree = _source_tree(ancestry_path)
    ancestry_owner = "DRAGONBORN_ANCESTRY_DECLARATIONS"
    assert ancestry_owner in _assigned_names(ancestry_tree)
    for row in _tuple_literal_rows(ancestry_tree, "_ANCESTRY_RULES"):
        ancestry = row.elts[0]
        assert isinstance(ancestry, ast.Attribute)
        _record_owner(
            owners,
            f"trait.origin.dragonborn.ancestry.{ancestry.attr.lower()}",
            ancestry_path,
            ancestry_owner,
        )

    origin_path = "dnd/content_system/character_origin_definitions.py"
    origin_tree = _source_tree(origin_path)
    srd_owner = "SRD_CHARACTER_ORIGIN_DECLARATIONS"
    neurodragon_owner = "NEURODRAGON_CHARACTER_ORIGIN_DECLARATIONS"
    for owner in (srd_owner, neurodragon_owner):
        assert owner in _assigned_names(origin_tree)
    species_names = {
        literal
        for node in ast.walk(_assignment_value(origin_tree, "_SPECIES_REFS"))
        if (literal := _literal_string(node)) is not None
        and f"species.{literal}" in expected
    }
    variant_names = {
        literal
        for node in ast.walk(_assignment_value(origin_tree, "_VARIANT_REFS"))
        if (literal := _literal_string(node)) is not None
        and f"species_variant.{literal}" in expected
    }
    for name in species_names:
        _record_owner(owners, f"species.{name}", origin_path, srd_owner)
    for name in variant_names:
        _record_owner(owners, f"species_variant.{name}", origin_path, srd_owner)
    _record_owner(owners, "background.acolyte", origin_path, srd_owner)
    _record_owner(owners, "background.adventurer", origin_path, neurodragon_owner)
    assert set(owners) == expected
    return owners


@lru_cache(maxsize=None)
def _static_owner_rows(authority_kind: str) -> dict[str, dict[str, str]]:
    if authority_kind == "behavior_identity":
        return _static_behavior_owners()
    if authority_kind == "materializable_root":
        return _static_factory_owners()
    assert authority_kind == "structural_definition"
    return _static_structural_owners()


def _validate_static_owner(identity: str, authority_kind: str) -> None:
    declaration_row = _legacy_declaration_rows()[identity]
    declaration_tree = _source_tree(declaration_row["source_path"])
    assert declaration_row["source_symbol_or_row"] in _assigned_names(declaration_tree)
    manifest_row = _definition_manifest_rows()[identity]
    semantic_id = manifest_row["semantic_id"]
    assert manifest_row["current_owner"] == _static_owner_rows(authority_kind)[semantic_id]


def _definition_manifest_rows() -> dict[str, dict[str, Any]]:
    return {
        row["row_id"].removeprefix("definition::"): row
        for row in _manifest()["implemented_content"]
        if row["row_id"].startswith("definition::")
    }


def _tracked_python_paths(prefix: str) -> tuple[Path, ...]:
    tracked = _git("ls-files", "*.py").decode("utf-8").splitlines()
    return tuple(
        REPOSITORY_ROOT / path
        for path in tracked
        if path.startswith(prefix) and (REPOSITORY_ROOT / path).is_file()
    )


def _current_importer_keys() -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    paths = {
        path
        for prefix in ("dnd/", "ai/", "devtools/")
        for path in _tracked_python_paths(prefix)
    }
    for path in sorted(paths):
        relative_path = path.relative_to(REPOSITORY_ROOT).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imported_modules: set[str] = set()
        uses_content_ref = False
        defines_content_ref = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported_modules.add(node.module or "")
                uses_content_ref |= any(
                    alias.name == "ContentRef" for alias in node.names
                )
            elif isinstance(node, ast.Name) and node.id == "ContentRef":
                uses_content_ref = True
            elif isinstance(node, ast.Attribute) and node.attr == "ContentRef":
                uses_content_ref = True
            elif isinstance(node, ast.ClassDef) and node.name == "ContentRef":
                defines_content_ref = True

        imports_content_runtime = any(
            module == "dnd.content_system"
            or module.startswith("dnd.content_system.")
            or module == "dnd.core.content"
            or module.startswith("dnd.core.content.")
            for module in imported_modules
        )
        if not relative_path.startswith("dnd/"):
            if imports_content_runtime or uses_content_ref:
                keys.add((relative_path, "nonproduction_tooling_importer"))
            continue

        if any(
            module == "dnd.content_system"
            or module.startswith("dnd.content_system.")
            for module in imported_modules
        ):
            keys.add((relative_path, "imports_dnd_content_system"))
        if any(
            module == "dnd.core.content"
            or module.startswith("dnd.core.content.")
            for module in imported_modules
        ):
            keys.add((relative_path, "imports_dnd_core_content"))
        if uses_content_ref:
            keys.add((relative_path, "uses_ContentRef"))
        if defines_content_ref:
            keys.add((relative_path, "defines_ContentRef"))
        if relative_path == "dnd/core/item_types.py":
            keys.add((relative_path, "carries_item_content_ref_snapshot"))
    return keys


def _appearance_option_payload(option: Any) -> dict[str, Any]:
    return {
        "option_id": option.option_id,
        "display_name": option.display_name,
        "control_kind": option.control_kind,
        "default_value_id": option.default_value_id,
        "values": [
            {
                "value_id": value.value_id,
                "display_name": value.display_name,
                "runtime_value": value.runtime_value,
                "tint_rgb": value.tint_rgb,
                "tint_source_option_id": value.tint_source_option_id,
            }
            for value in option.values
        ],
    }


def _possession_payload(grants: Any) -> list[dict[str, Any]]:
    return [
        {
            "recipe": grant.recipe.model_dump(mode="json", exclude_none=True),
            "disposition": grant.disposition.value,
            "equipment_slot": (
                grant.equipment_slot.value
                if grant.equipment_slot is not None
                else None
            ),
        }
        for grant in grants
    ]


def _assert_overlay_metadata(
    row: dict[str, Any],
    *,
    domain: str,
    source_path: str,
    source_symbol: str,
    target_cut: str = "CR-8",
    evidence_tier: str = "current_reconstructed_engine",
    disposition: str = "renderer_binding",
    conflict: Any = None,
) -> None:
    assert row["owning_domain"] == domain
    assert row["source_path"] == source_path
    assert row["source_symbol_or_line"] == source_symbol
    assert row["target_cut"] == target_cut
    assert row["evidence_tier"] == evidence_tier
    assert row["disposition"] == disposition
    assert row["conflict"] == conflict


def _literal_keyword(call: ast.Call, keyword_name: str) -> Any:
    keyword = next(
        keyword for keyword in call.keywords if keyword.arg == keyword_name
    )
    return ast.literal_eval(keyword.value)


def _artifact_row_count(artifact_id: str, payload: bytes) -> int:
    if artifact_id.endswith(".neurodragon_source_text"):
        return len(payload.decode("utf-8").splitlines())
    document = json.loads(payload)
    if artifact_id.endswith(".icon_bindings"):
        return len(document["definitions"]) + len(document["recipe_presets"])
    if artifact_id.endswith(".authored_item_visuals"):
        categories = document["inventory"]["categories"]
        return (
            len(categories)
            + sum(len(category["variants"]) for category in categories)
            + len(document["inventory"]["source_visual_variant_id_collisions"])
        )
    if artifact_id.endswith(".game_icon_asset_index"):
        return len(document["assets"])
    if artifact_id.endswith(".srd_coverage"):
        return len(document["rows"])
    return 1


def _authored_visual_rows(document: dict[str, Any]) -> dict[str, Any]:
    rows: dict[str, Any] = {}
    for category in document["inventory"]["categories"]:
        base_category = category["base_category"]
        base_row = dict(category)
        variants = base_row.pop("variants")
        rows[f"{base_category}||"] = base_row
        for variant in variants:
            identity = (
                f"{base_category}|{variant['inventory_id']}|"
                f"{variant['source_visual_variant_id']}"
            )
            rows[identity] = variant
    for collision_id, identities in document["inventory"][
        "source_visual_variant_id_collisions"
    ].items():
        rows[f"collision::{collision_id}"] = identities
    return rows


def _artifact_pair_rows(pair_id: str, artifact_id: str) -> dict[str, Any]:
    if pair_id == "neurodragon_source_text":
        row = next(
            row
            for row in _manifest()["source_artifacts"]
            if row["artifact_id"] == artifact_id
        )
        return {
            str(index): line
            for index, line in enumerate(
                _artifact_bytes(row).decode("utf-8").splitlines(),
                start=1,
            )
        }
    document = _artifact_json(artifact_id)
    if pair_id == "icon_definition_bindings":
        return {
            _content_ref_identity(row["content_ref"]): row
            for row in document["definitions"]
        }
    if pair_id == "recipe_preset_icon_bindings":
        return {
            _preset_ref_identity(row["preset_ref"]): row
            for row in document["recipe_presets"]
        }
    if pair_id == "authored_item_visuals":
        return _authored_visual_rows(document)
    if pair_id == "game_icon_asset_index":
        return {row["icon_key"]: row for row in document["assets"]}
    if pair_id == "srd_source_coverage":
        return {row["source_entry_id"]: row for row in document["rows"]}
    if pair_id.endswith("_source_json"):
        return {document["source_id"]: document}
    raise AssertionError(f"unknown artifact pair: {pair_id}")


def _default_rule_matches(
    rule: dict[str, Any],
    identity: str,
    row: Any,
) -> bool:
    match = rule["match"]
    if match == {"otherwise": True}:
        return True
    if "definition_kind_in" in match:
        return row["content_ref"]["definition_kind"] in match[
            "definition_kind_in"
        ]
    if "icon_key_prefix_in" in match:
        return any(identity.startswith(prefix) for prefix in match["icon_key_prefix_in"])
    raise AssertionError(f"unsupported default rule: {match}")


def _accepted_direct_item_ids() -> set[str]:
    def tuple_call_ids(path: str, tuple_names: set[str]) -> list[str]:
        tree = ast.parse(_git("show", f"{ACCEPTED_COMMIT}:{path}").decode("utf-8"))
        identities: list[str] = []
        for node in tree.body:
            if isinstance(node, ast.Assign):
                targets = node.targets
            elif isinstance(node, ast.AnnAssign):
                targets = [node.target]
            else:
                continue
            if not any(
                isinstance(target, ast.Name) and target.id in tuple_names
                for target in targets
            ):
                continue
            assert isinstance(node.value, (ast.Tuple, ast.List))
            for entry in node.value.elts:
                assert isinstance(entry, ast.Call)
                value: object | None = None
                if entry.args and isinstance(entry.args[0], ast.Constant):
                    value = entry.args[0].value
                if value is None:
                    value = next(
                        (
                            keyword.value.value
                            for keyword in entry.keywords
                            if keyword.arg == "item_id"
                            and isinstance(keyword.value, ast.Constant)
                        ),
                        None,
                    )
                assert isinstance(value, str)
                identities.append(value)
        return identities

    identities = [
        *tuple_call_ids(
            "dnd/content/items/authored_item_definitions.py",
            {"_ACOLYTE_GEAR", "_STATIC_BLOCKERS", "_AUTHORED_WEAPONS", "_AUTHORED_WEARABLES"},
        ),
        *tuple_call_ids(
            "dnd/content/items/item_catalog.py",
            {"_SPECIAL_DIRECT_ITEMS"},
        ),
    ]
    assert len(identities) == len(set(identities)) == 146
    return set(identities)


def _accepted_test_exists(proof: str) -> bool:
    git_object, separator, test_name = proof.partition("::")
    assert separator
    revision, separator, path = git_object.partition(":")
    assert separator
    tree = ast.parse(_git("show", f"{revision}:{path}").decode("utf-8"))
    return any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == test_name.split("[", 1)[0]
        for node in tree.body
    )


def test_manifest_shape_counts_ordering_and_authority() -> None:
    manifest = _manifest()
    assert set(manifest) == REQUIRED_TOP_LEVEL_FIELDS
    assert manifest["schema_version"] == 1
    assert MANIFEST_PATH.read_bytes() == (
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")

    for section, expected_count in EXPECTED_SECTION_COUNTS.items():
        assert len(manifest[section]) == expected_count
    assert len(manifest["binding_reconciliation"]["artifact_pairs"]) == 8
    assert len(manifest["binding_reconciliation"]["rows"]) == 121

    authority = manifest["authority"]
    for plan_key in ("governing_plan", "implementation_plan"):
        plan = authority[plan_key]
        assert _sha256((REPOSITORY_ROOT / plan["path"]).read_bytes()) == plan[
            "sha256"
        ]
    for git_object in {
        authority["repository_head"],
        *authority["evidence_objects"].values(),
    }:
        subprocess.run(
            ["git", "cat-file", "-e", f"{git_object}^{{commit}}"],
            cwd=REPOSITORY_ROOT,
            check=True,
        )

    ordered_unique_sections = (
        ("source_artifacts", lambda row: row["artifact_id"]),
        (
            "legacy_authorities",
            lambda row: (
                row["authority_kind"],
                row["legacy_identity"],
                row["source_path"],
                row["source_symbol_or_row"],
            ),
        ),
        ("implemented_content", lambda row: row["row_id"]),
        (
            "python_binding_overlay",
            lambda row: (
                row["semantic_id"],
                row["source_path"],
                row["source_symbol_or_line"],
            ),
        ),
        ("srd_proof_overlay", lambda row: row["source_row_identity"]),
        (
            "production_importers",
            lambda row: (row["path"], row["import_category"]),
        ),
        ("excluded_or_rescued_test_modules", lambda row: row["path"]),
    )
    for section, key in ordered_unique_sections:
        identities = [key(row) for row in manifest[section]]
        assert identities == sorted(identities)
        assert len(identities) == len(set(identities))

    pairs = manifest["binding_reconciliation"]["artifact_pairs"]
    pair_ids = [row["pair_id"] for row in pairs]
    assert pair_ids == sorted(pair_ids)
    assert len(pair_ids) == len(set(pair_ids))
    reconciliation_rows = manifest["binding_reconciliation"]["rows"]
    reconciliation_ids = [
        (row["artifact_pair"], row["stable_row_identity"])
        for row in reconciliation_rows
    ]
    assert reconciliation_ids == sorted(reconciliation_ids)
    assert len(reconciliation_ids) == len(set(reconciliation_ids))

    maintained = manifest["maintained_in_process_nodes"]
    assert maintained == sorted(maintained)
    assert len(maintained) == len(set(maintained))
    assert _sha256(("\n".join(maintained) + "\n").encode("utf-8")) == (
        "f689e92102b7a6e25c832cdc030d88618ab2048cd174e87869d76ed59cdcab33"
    )


def test_current_and_accepted_artifact_hashes_are_exact() -> None:
    for row in _manifest()["source_artifacts"]:
        payload = _artifact_bytes(row)
        assert _sha256(payload) == row["sha256"]
        assert _artifact_row_count(row["artifact_id"], payload) == row["row_count"]


def test_srd_source_inventory_and_proof_overlay_are_exact() -> None:
    manifest = _manifest()
    source = _artifact_json("current.srd_coverage")
    rows = source["rows"]
    assert len(rows) == 925
    assert Counter(row["implementation_status"] for row in rows) == Counter(
        {"playable": 177, "partial": 5, "missing": 743}
    )
    source_ids = [row["source_entry_id"] for row in rows]
    assert len(source_ids) == len(set(source_ids))

    implemented_ids = {
        row["row_id"] for row in manifest["implemented_content"]
    }
    expected_overlay: dict[str, str] = {}
    for row in rows:
        if row["implementation_status"] not in {"playable", "partial"}:
            continue
        if row["content_ref"] is None:
            assert row["source_entry_id"] == "srd_5_1.magic_item.spell_scroll"
            target = "current_family::srd_spell_scroll"
        else:
            target = f"definition::{_content_ref_identity(row['content_ref'])}"
        assert target in implemented_ids
        expected_overlay[row["source_entry_id"]] = target

    actual_overlay = {
        row["source_row_identity"]: row["implemented_content_row_id"]
        for row in manifest["srd_proof_overlay"]
    }
    assert actual_overlay == expected_overlay
    assert all(
        row["status_conflict"] is None
        for row in manifest["srd_proof_overlay"]
    )


def validate_historical_bindings_and_current_non_item_overlay(
    item_relevant_ids: set[str],
) -> None:
    reconciliation = _manifest()["binding_reconciliation"]
    overrides_by_pair: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in reconciliation["rows"]:
        overrides_by_pair[row["artifact_pair"]][
            row["stable_row_identity"]
        ] = row

    for pair in reconciliation["artifact_pairs"]:
        pair_id = pair["pair_id"]
        current_rows = _artifact_pair_rows(pair_id, pair["current_artifact_id"])
        accepted_rows = _artifact_pair_rows(pair_id, pair["accepted_artifact_id"])
        assert len(current_rows) == pair["current_row_count"]
        assert len(accepted_rows) == pair["accepted_row_count"]
        overrides = overrides_by_pair[pair_id]
        assert len(overrides) == pair["changed_or_collision_row_count"]
        assert pair["default_rules"][-1]["match"] == {"otherwise": True}

        union = set(current_rows) | set(accepted_rows)
        assert set(overrides) <= union
        for identity in sorted(union):
            current = current_rows.get(identity)
            accepted = accepted_rows.get(identity)
            if identity in overrides:
                override = overrides[identity]
                assert override["current_value"] == current
                assert override["accepted_value"] == accepted
                continue
            row = current if current is not None else accepted
            specific_matches = [
                rule
                for rule in pair["default_rules"][:-1]
                if _default_rule_matches(rule, identity, row)
            ]
            assert len(specific_matches) <= 1
            assert _default_rule_matches(pair["default_rules"][-1], identity, row)

        changed_identities = {
            identity
            for identity in union
            if current_rows.get(identity) != accepted_rows.get(identity)
        }
        if pair_id == "authored_item_visuals":
            assert set(overrides) == {
                identity for identity in union if identity.startswith("collision::")
            }
        else:
            assert set(overrides) == changed_identities

    overlay_rows = {
        row["semantic_id"]: row
        for row in _manifest()["python_binding_overlay"]
    }
    checked_ids: set[str] = set()
    definition_rows = _definition_manifest_rows()
    presentation_cut_kinds = {
        "action",
        "reaction",
        "condition",
        "spell",
        "trait",
        "feat",
        "class_feature",
    }
    for identity, declaration in sorted(_declarations().items()):
        semantic_id = f"definition_presentation::{identity}"
        if semantic_id in item_relevant_ids:
            continue
        row = overlay_rows[semantic_id]
        owner = definition_rows[identity]["current_owner"]
        definition_kind = declaration.ref.definition_kind.value
        _assert_overlay_metadata(
            row,
            domain=definition_kind,
            source_path=owner["source_path"],
            source_symbol=owner["source_symbol"],
            target_cut=(
                "CR-9" if definition_kind in presentation_cut_kinds else "CR-8"
            ),
        )
        presentation = declaration.descriptor.presentation.model_dump(
            mode="json",
            exclude_none=True,
        )
        presentation.pop("icon_key", None)
        assert row["authored_value"] == {
            key: value
            for key, value in presentation.items()
            if value not in (None, "", [], (), {})
        }
        checked_ids.add(semantic_id)

    appearance_tree = _source_tree("dnd/content_system/character_appearance.py")
    assert _assignment_line(
        appearance_tree,
        "PLAYER_CHARACTER_APPEARANCE_OPTIONS",
    ) == 180
    for option in PLAYER_CHARACTER_APPEARANCE_OPTIONS:
        semantic_id = f"character_appearance_option::{option.option_id}"
        row = overlay_rows[semantic_id]
        _assert_overlay_metadata(
            row,
            domain="characters",
            source_path="dnd/content_system/character_appearance.py",
            source_symbol="PLAYER_CHARACTER_APPEARANCE_OPTIONS:180",
        )
        assert row["authored_value"] == _appearance_option_payload(option)
        checked_ids.add(semantic_id)

    selections = {
        "barbarian": BARBARIAN_HUMAN_APPEARANCE,
        "fighter": FIGHTER_HUMAN_APPEARANCE,
        "sorcerer": SORCERER_HUMAN_APPEARANCE,
    }
    for key, selection in selections.items():
        symbol = f"{key.upper()}_HUMAN_APPEARANCE"
        assert symbol in _assigned_names(appearance_tree)
        semantic_id = f"builtin_selection.{key}"
        row = overlay_rows[semantic_id]
        _assert_overlay_metadata(
            row,
            domain="characters",
            source_path="dnd/content_system/character_appearance.py",
            source_symbol=symbol,
        )
        assert row["authored_value"] == selection.model_dump(
            mode="json",
            exclude_none=True,
        )
        checked_ids.add(semantic_id)

    builds_tree = _source_tree("dnd/content_system/builtin_character_builds.py")
    assert "BUILTIN_PREMADE_BUILDS" in _assigned_names(builds_tree)
    for premade_id, build in sorted(BUILTIN_PREMADE_BUILDS.items()):
        semantic_id = f"premade_appearance::{premade_id}"
        row = overlay_rows[semantic_id]
        _assert_overlay_metadata(
            row,
            domain="characters",
            source_path="dnd/content_system/builtin_character_builds.py",
            source_symbol=f"BUILTIN_PREMADE_BUILDS[{premade_id}]",
        )
        assert row["authored_value"] == build.appearance.model_dump(
            mode="json",
            exclude_none=True,
        )
        checked_ids.add(semantic_id)

    bestiary_tree = _source_tree("dnd/monsters/bestiary.py")
    for key, appearance in {
        "goblin": GOBLIN_APPEARANCE,
        "skeleton": SKELETON_APPEARANCE,
        "caster": CASTER_APPEARANCE,
    }.items():
        symbol = f"{key.upper()}_APPEARANCE"
        assert symbol in _assigned_names(bestiary_tree)
        semantic_id = f"bestiary_appearance::{key}"
        row = overlay_rows[semantic_id]
        _assert_overlay_metadata(
            row,
            domain="monsters",
            source_path="dnd/monsters/bestiary.py",
            source_symbol=symbol,
        )
        assert row["authored_value"] == appearance.model_dump(
            mode="json",
            exclude_none=True,
        )
        checked_ids.add(semantic_id)

    wardrobe_sources = (
        (
            "bestiary_wardrobe",
            BESTIARY_CREATURE_WARDROBE_GRANTS_BY_KEY,
            "dnd/monsters/bestiary_content.py",
            "BESTIARY_CREATURE_WARDROBE_GRANTS_BY_KEY",
        ),
        (
            "configured_srd_wardrobe",
            CONFIGURED_SRD_CREATURE_WARDROBE_GRANTS_BY_ID,
            "dnd/monsters/configured_srd_creatures.py",
            "CONFIGURED_SRD_CREATURE_WARDROBE_GRANTS_BY_ID",
        ),
    )
    for prefix, wardrobes, source_path, symbol in wardrobe_sources:
        assert symbol in _assigned_names(_source_tree(source_path))
        for key, grants in sorted(wardrobes.items()):
            semantic_id = f"{prefix}::{key}"
            if semantic_id in item_relevant_ids:
                continue
            row = overlay_rows[semantic_id]
            _assert_overlay_metadata(
                row,
                domain="monsters",
                source_path=source_path,
                source_symbol=f"{symbol}[{key}]",
            )
            assert row["authored_value"] == _possession_payload(grants)
            checked_ids.add(semantic_id)

    srd_tree = _source_tree("dnd/monsters/srd_roster.py")
    srd_source_content_ids = {
        f"creature.{keyword.value.value}"
        for node in ast.walk(srd_tree)
        if isinstance(node, ast.Call)
        for keyword in node.keywords
        if keyword.arg == "creature_id"
        and isinstance(keyword.value, ast.Constant)
        and isinstance(keyword.value.value, str)
    }
    for declaration in SRD_CREATURE_DECLARATIONS:
        assert declaration.definition_payload is None
        content_id = declaration.ref.content_id
        assert content_id in srd_source_content_ids
        semantic_id = f"srd_creature_appearance::{declaration.ref.identity_key}"
        row = overlay_rows[semantic_id]
        _assert_overlay_metadata(
            row,
            domain="monsters",
            source_path="dnd/monsters/srd_roster.py",
            source_symbol=content_id,
        )
        assert row["authored_value"] == {"appearance": None}
        checked_ids.add(semantic_id)

    tile_tree = _source_tree("dnd/core/base_tiles.py")
    tile_functions = {
        node.name: node
        for node in tile_tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    for semantic_id, symbol in {
        "tile.floor": "floor_factory",
        "tile.dark_floor": "dark_floor_factory",
        "tile.wall": "wall_factory",
        "tile.water": "water_factory",
        "tile.difficult_terrain": "difficult_terrain_factory",
    }.items():
        function = tile_functions[symbol]
        sprite_calls = [
            node
            for node in ast.walk(function)
            if isinstance(node, ast.Call)
            and any(keyword.arg == "sprite_name" for keyword in node.keywords)
        ]
        assert len(sprite_calls) == 1
        row = overlay_rows[semantic_id]
        _assert_overlay_metadata(
            row,
            domain="tiles",
            source_path="dnd/core/base_tiles.py",
            source_symbol=f"{symbol}:{function.lineno}",
        )
        assert row["authored_value"] == {
            "sprite": _literal_keyword(sprite_calls[0], "sprite_name")
        }
        checked_ids.add(semantic_id)

    connector_tree = _source_tree("dnd/scenarios/battlefield_catalog.py")
    connector_assignment = next(
        node
        for node in connector_tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name)
            and target.id == "_ELEVATION_PROVING_CONNECTORS"
            for target in node.targets
        )
    )
    assert isinstance(connector_assignment.value, ast.Tuple)
    connector_ids: set[str] = set()
    for call in connector_assignment.value.elts:
        assert isinstance(call, ast.Call)
        authored_id_keyword = next(
            keyword for keyword in call.keywords if keyword.arg == "authored_id"
        )
        presentation_keyword = next(
            keyword for keyword in call.keywords if keyword.arg == "presentation_key"
        )
        semantic_id = ast.literal_eval(authored_id_keyword.value)
        presentation_key = ast.literal_eval(presentation_keyword.value)
        row = overlay_rows[semantic_id]
        _assert_overlay_metadata(
            row,
            domain="scenarios",
            source_path="dnd/scenarios/battlefield_catalog.py",
            source_symbol=row["source_symbol_or_line"],
        )
        assert row["source_symbol_or_line"].startswith("presentation_key:")
        assert row["authored_value"] == {
            "presentation_key": presentation_key
        }
        connector_ids.add(semantic_id)
    assert connector_ids == {
        "connector.proving.ladder",
        "connector.proving.rope",
        "connector.proving.lift",
        "connector.proving.vertical_stairs",
        "connector.proving.passage",
    }
    checked_ids.update(connector_ids)

    accepted_spatial_source = _git(
        "show",
        f"{ACCEPTED_COMMIT}:dnd/content/spatial_effect_recipes.py",
    ).decode("utf-8").splitlines()
    for semantic_id, row in overlay_rows.items():
        if not semantic_id.startswith("spatial_effect."):
            continue
        if semantic_id in item_relevant_ids:
            continue
        prefix, separator, raw_line = row["source_symbol_or_line"].partition(":")
        assert prefix == "content_id" and separator
        line = int(raw_line)
        assert accepted_spatial_source[line - 1].strip() == (
            f'content_id="{semantic_id}",'
        )
        _assert_overlay_metadata(
            row,
            domain="spatial",
            source_path=f"{ACCEPTED_COMMIT}:dnd/content/spatial_effect_recipes.py",
            source_symbol=f"content_id:{line}",
            target_cut="CR-9",
            evidence_tier="accepted_checkpoint",
        )
        assert row["authored_value"] == {
            "visual_variant_key": semantic_id,
            "vfx_profile": semantic_id,
        }
        checked_ids.add(semantic_id)

    gap_id = "unresolved.gap_png"
    gap_row = overlay_rows[gap_id]
    gap_line = int(gap_row["source_symbol_or_line"].removeprefix("line:"))
    gap_source = _git(
        "show",
        gap_row["source_path"],
    ).decode("utf-8").splitlines()
    assert "gap.png" in gap_source[gap_line - 1]
    _assert_overlay_metadata(
        gap_row,
        domain="scenarios",
        source_path=(
            "1f2e525:BACKEND_FRONTEND_RESPONSIBILITY_LEAK_AUDIT_2026-08-15.md"
        ),
        source_symbol="line:88",
        evidence_tier="forensic_only",
        disposition="forensic_only_reject",
        conflict={
            "kind": "no_implementation_source_match",
            "detail": (
                "no tracked current, accepted, July, broken, or "
                "broken-filesystem implementation source owns gap.png"
            ),
        },
    )
    assert gap_row["authored_value"] == {"asset_name": "gap.png"}
    checked_ids.add(gap_id)

    assert checked_ids == set(overlay_rows) - item_relevant_ids


def test_production_never_imports_cr0_evidence() -> None:
    forbidden_module = "tests.architecture.test_content_recovery_cr0_evidence"
    violations: list[str] = []
    for prefix in ("dnd/", "ai/", "server/"):
        for path in _tracked_python_paths(prefix):
            relative_path = path.relative_to(REPOSITORY_ROOT).as_posix()
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
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
            if (
                MANIFEST_REPOSITORY_PATH in source
                or forbidden_module in imported_modules
            ):
                violations.append(relative_path)
    assert violations == []


def test_every_structural_definition_has_one_exact_authored_owner() -> None:
    declarations = _declarations()
    structural_identities = {
        identity
        for identity, declaration in declarations.items()
        if declaration.mode.value == "typed_definition"
    }
    assert len(structural_identities) == 87
    manifest_rows = _definition_manifest_rows()
    assert set(manifest_rows) >= structural_identities
    for identity in sorted(structural_identities):
        _validate_static_owner(identity, "structural_definition")
