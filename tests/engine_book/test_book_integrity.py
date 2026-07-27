"""Repository source and test-harness integrity checks."""

import ast
import io
from pathlib import Path
import re
import tokenize
import tomllib


ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = ROOT / "pyproject.toml"
SERVER_API_FILES = [
    ROOT / "server" / "event_server.py",
    ROOT / "server" / "session.py",
]
RUNTIME_SOURCE_ROOTS = [
    ROOT / "cli",
    ROOT / "dnd",
    ROOT / "server",
]
COMBAT_LOG_MODELS = {
    ROOT / "dnd" / "core" / "combat_log.py": {
        "ModifierBreakdown",
        "DiceRollDisplay",
        "DamageRollDisplay",
        "AttackLogData",
        "MovementLogData",
        "SavingThrowLogData",
        "SpellSaveLogData",
        "SkillCheckLogData",
        "EntitySpottedLogData",
        "HazardDetectedLogData",
        "HealLogData",
        "ActionLogData",
        "TurnLogData",
        "MultiEntityLogData",
        "CombatLogEntry",
    },
}
ENCOUNTER_MODELS = {
    ROOT / "dnd" / "encounter.py": {
        "AdvanceResult",
        "CombatantState",
        "Encounter",
    },
}
CLASS_FEATURE_DESCRIBED_MODEL_CLASSES = {
    ROOT / "dnd" / "classes" / "fighter.py": {
        "FightingStyleArchery",
        "FightingStyleDefense",
        "FightingStyleDueling",
        "FightingStyleProtection",
        "FightingStyleTwoWeaponFighting",
        "GreatWeaponFighting",
        "SecondWind",
        "SecondWindFeature",
        "ActionSurging",
        "ActionSurge",
        "ActionSurgeFeature",
        "ImprovedCritical",
        "ExtraAttacksGranted",
        "ExtraAttack",
        "ExtraAttackFeature",
        "Indomitable",
        "SuperiorCritical",
        "Survivor",
    },
    ROOT / "dnd" / "classes" / "barbarian.py": {
        "RecklessAttacking",
        "RecklessAttack",
        "RecklessAttackFeature",
        "DangerSense",
        "FastMovement",
        "MindlessRage",
        "FeralInstinct",
        "BrutalCritical",
        "RelentlessRage",
        "PersistentRage",
        "IndomitableMight",
        "PrimalChampion",
        "Retaliation",
        "IntimidatingPresenceImmunity",
        "IntimidatingPresence",
        "ExtendIntimidatingPresence",
        "IntimidatingPresenceFeature",
    },
    ROOT / "dnd" / "classes" / "rage.py": {
        "Rage",
        "RageFeature",
        "Raging",
        "EndRage",
        "Frenzied",
        "FrenziedStrike",
        "Frenzy",
        "FrenzyFeature",
    },
    ROOT / "dnd" / "classes" / "sorcerer.py": {
        "DraconicResilience",
        "ElementalAffinity",
        "MetamagicActive",
        "QuickenedSpell",
        "TwinnedSpell",
        "DistantSpell",
        "ConvertSlotToSP",
        "ConvertSPToSlot",
        "SorceryPointsFeature",
    },
    ROOT / "dnd" / "classes" / "feats.py": {"LuckyFeature"},
}
CLASS_FEATURE_GOOGLE_DOCSTRING_CLASSES = {
    ROOT / "dnd" / "classes" / "fighter.py": {
        "FightingStyleArchery",
        "FightingStyleDefense",
        "FightingStyleDueling",
        "FightingStyleProtection",
        "FightingStyleTwoWeaponFighting",
        "GreatWeaponFighting",
        "SecondWind",
        "SecondWindFeature",
        "ActionSurging",
        "ActionSurge",
        "ActionSurgeFeature",
        "ImprovedCritical",
        "ExtraAttacksGranted",
        "ExtraAttack",
        "ExtraAttackFeature",
        "Indomitable",
        "SuperiorCritical",
        "Survivor",
    },
    ROOT / "dnd" / "classes" / "barbarian.py": {
        "RecklessAttacking",
        "RecklessAttack",
        "RecklessAttackFeature",
        "DangerSense",
        "FastMovement",
        "MindlessRage",
        "FeralInstinct",
        "BrutalCritical",
        "RelentlessRage",
        "PersistentRage",
        "IndomitableMight",
        "PrimalChampion",
        "Retaliation",
        "IntimidatingPresenceImmunity",
        "IntimidatingPresence",
        "ExtendIntimidatingPresence",
        "IntimidatingPresenceFeature",
    },
    ROOT / "dnd" / "classes" / "rage.py": {
        "Rage",
        "RageFeature",
        "Raging",
        "EndRage",
        "Frenzied",
        "FrenziedStrike",
        "Frenzy",
        "FrenzyFeature",
    },
    ROOT / "dnd" / "classes" / "sorcerer.py": {
        "DraconicResilience",
        "ElementalAffinity",
        "MetamagicActive",
        "QuickenedSpell",
        "TwinnedSpell",
        "DistantSpell",
        "ConvertSlotToSP",
        "ConvertSPToSlot",
        "SorceryPointsFeature",
    },
    ROOT / "dnd" / "classes" / "feats.py": {"LuckyFeature"},
}
SERVER_API_DESCRIBED_MODEL_CLASSES = {
    ROOT / "server" / "api_models.py": {
        "ActionResult",
        "AdvanceEncounterResult",
        "AoEPreviewResult",
        "CreateSessionRequest",
        "CreateSessionResponse",
        "ExecuteByIndexRequest",
        "EquipRequest",
        "EquipmentMutationResult",
        "JoinGameRequest",
        "JoinGameResponse",
        "MapEditorCatalog",
        "MapEditorCatalogEntry",
        "MapEditorCreateMapRequest",
        "MapEditorGridBounds",
        "MapEditorLightCell",
        "MapEditorLightResponse",
        "MapEditorMapSnapshot",
        "MapEditorObjectDeleteRequest",
        "MapEditorObjectPlaceRequest",
        "MapEditorSaveMapRequest",
        "MapEditorSavedMapDocument",
        "MapEditorSavedMapList",
        "MapEditorSavedMapMetadata",
        "MapEditorSavedObjectPlacement",
        "MapEditorTilePatch",
        "MapEditorTilePatchRequest",
        "MapEditorVisibilityCell",
        "MapEditorVisibilityResponse",
        "MapEditorWalkabilityCell",
        "MapEditorWalkabilityResponse",
        "PositionPreviewRequest",
        "SessionPingResponse",
        "SimpleActionRequest",
        "SpellCatalogEntry",
        "SpellCatalogMultiTarget",
        "SpellCatalogResponse",
        "SpellCatalogSavingThrow",
        "SpellCatalogVfx",
        "ToggleHandlerRequest",
        "UnequipRequest",
    },
    ROOT / "server" / "world_contracts.py": {
        "APIAppearance",
        "APICombatant",
        "APIConditionSummary",
        "APIDirectionalBlockMap",
        "APIEncounter",
        "APIEntitySummary",
        "APIEntityVisibility",
        "APIEquipmentOverview",
        "APIEquipmentSlot",
        "APIFloorObject",
        "APIGameState",
        "APIGrid",
        "APIItemSummary",
        "APITile",
        "APIVisibilityResponse",
    },
    ROOT / "server" / "event_stream.py": {
        "StreamSyncPayload",
        "GameEventPayload",
        "CombatLogPayload",
        "HeartbeatPayload",
        "EvictedPayload",
    },
}
SERVER_API_GOOGLE_DOCSTRING_CLASSES = {
    ROOT / "server" / "api_models.py": {
        "ActionResult",
        "AdvanceEncounterResult",
        "AoEPreviewResult",
        "CreateSessionRequest",
        "CreateSessionResponse",
        "ExecuteByIndexRequest",
        "EquipRequest",
        "EquipmentMutationResult",
        "JoinGameRequest",
        "JoinGameResponse",
        "MapEditorCatalog",
        "MapEditorCatalogEntry",
        "MapEditorCreateMapRequest",
        "MapEditorGridBounds",
        "MapEditorLightCell",
        "MapEditorLightResponse",
        "MapEditorMapSnapshot",
        "MapEditorObjectDeleteRequest",
        "MapEditorObjectPlaceRequest",
        "MapEditorSaveMapRequest",
        "MapEditorSavedMapDocument",
        "MapEditorSavedMapList",
        "MapEditorSavedMapMetadata",
        "MapEditorSavedObjectPlacement",
        "MapEditorTilePatch",
        "MapEditorTilePatchRequest",
        "MapEditorVisibilityCell",
        "MapEditorVisibilityResponse",
        "MapEditorWalkabilityCell",
        "MapEditorWalkabilityResponse",
        "PositionPreviewRequest",
        "SessionPingResponse",
        "SimpleActionRequest",
        "SpellCatalogEntry",
        "SpellCatalogMultiTarget",
        "SpellCatalogResponse",
        "SpellCatalogSavingThrow",
        "SpellCatalogVfx",
        "ToggleHandlerRequest",
        "UnequipRequest",
    },
    ROOT / "server" / "event_stream.py": {
        "StreamSyncPayload",
        "GameEventPayload",
        "CombatLogPayload",
        "HeartbeatPayload",
        "EvictedPayload",
    },
}
SERVER_SESSION_DESCRIBED_DATACLASS_CLASSES = {
    ROOT / "server" / "session.py": {
        "PlayerSession",
        "GameSession",
    },
}
SERVER_SESSION_GOOGLE_DOCSTRING_CLASSES = {
    ROOT / "server" / "session.py": {
        "PlayerSession",
        "GameSession",
    },
}
def read_text(path: Path) -> str:
    """Read repository text with a consistent encoding."""
    return path.read_text(encoding="utf-8")


def is_field_call(value: ast.expr | None) -> bool:
    """Return whether an AST expression calls Pydantic's Field helper."""
    if not isinstance(value, ast.Call):
        return False
    if isinstance(value.func, ast.Name):
        return value.func.id == "Field"
    if isinstance(value.func, ast.Attribute):
        return value.func.attr == "Field"
    return False


def field_has_description(value: ast.expr | None) -> bool:
    """Return whether a Field call includes a description keyword."""
    return is_field_call(value) and isinstance(value, ast.Call) and any(
        keyword.arg == "description" for keyword in value.keywords
    )


def dataclass_field_has_metadata_description(value: ast.expr | None) -> bool:
    """Return whether a dataclasses.field call includes metadata description."""
    if not isinstance(value, ast.Call):
        return False

    is_dataclass_field = (
        isinstance(value.func, ast.Name)
        and value.func.id == "field"
    ) or (
        isinstance(value.func, ast.Attribute)
        and value.func.attr == "field"
    )
    if not is_dataclass_field:
        return False

    for keyword in value.keywords:
        if keyword.arg != "metadata" or not isinstance(keyword.value, ast.Dict):
            continue

        return any(
            isinstance(key, ast.Constant)
            and key.value == "description"
            and isinstance(val, ast.Constant)
            and isinstance(val.value, str)
            and bool(val.value.strip())
            for key, val in zip(keyword.value.keys, keyword.value.values)
        )

    return False


def test_combat_log_models_use_described_pydantic_fields() -> None:
    """Cleaned combat-log models should expose described Pydantic fields."""
    failures: list[str] = []

    for path, class_names in COMBAT_LOG_MODELS.items():
        tree = ast.parse(read_text(path))
        classes = {
            node.name: node
            for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name in class_names
        }

        missing_classes = sorted(class_names - set(classes))
        for class_name in missing_classes:
            failures.append(f"{path.relative_to(ROOT)}::{class_name} missing")

        for class_name, class_node in sorted(classes.items()):
            for statement in class_node.body:
                if not isinstance(statement, ast.AnnAssign) or not isinstance(statement.target, ast.Name):
                    continue

                field_name = statement.target.id
                if field_name.startswith("_"):
                    continue

                if not is_field_call(statement.value):
                    failures.append(f"{path.relative_to(ROOT)}::{class_name}.{field_name} is not Field(...)")
                elif not field_has_description(statement.value):
                    failures.append(f"{path.relative_to(ROOT)}::{class_name}.{field_name} lacks description")

    assert not failures, "Combat-log metadata gaps:\n" + "\n".join(failures)


def test_combat_log_models_use_google_style_docstrings() -> None:
    """Guard cleaned combat-log model docstrings against terse regressions."""
    failures: list[str] = []

    for path, class_names in COMBAT_LOG_MODELS.items():
        tree = ast.parse(read_text(path))
        classes = {
            node.name: node
            for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name in class_names
        }

        missing_classes = sorted(class_names - set(classes))
        for class_name in missing_classes:
            failures.append(f"{path.relative_to(ROOT)}::{class_name} missing")

        for class_name, class_node in sorted(classes.items()):
            docstring = ast.get_docstring(class_node) or ""
            if "\n\nAttributes:\n" not in docstring:
                failures.append(f"{path.relative_to(ROOT)}::{class_name} lacks Google-style Attributes block")
                continue

            doc_lines = [line.strip() for line in docstring.splitlines()]
            for statement in class_node.body:
                if not isinstance(statement, ast.AnnAssign) or not isinstance(statement.target, ast.Name):
                    continue

                field_name = statement.target.id
                if field_name.startswith("_"):
                    continue

                if not any(line.startswith(f"{field_name}:") for line in doc_lines):
                    failures.append(f"{path.relative_to(ROOT)}::{class_name}.{field_name} missing from docstring")

    assert not failures, "Combat-log docstring gaps:\n" + "\n".join(failures)


def test_combat_log_module_has_no_inline_comments() -> None:
    """The cleaned combat-log module should not reintroduce code comments."""
    failures: list[str] = []

    for path in COMBAT_LOG_MODELS:
        text = read_text(path)
        for token in tokenize.generate_tokens(io.StringIO(text).readline):
            if token.type == tokenize.COMMENT:
                failures.append(f"{path.relative_to(ROOT)}:{token.start[0]} has inline comment")

    assert not failures, "Combat-log comment regressions:\n" + "\n".join(failures)


def test_encounter_models_use_described_pydantic_fields() -> None:
    """Cleaned encounter models should expose described Pydantic fields."""
    failures: list[str] = []

    for path, class_names in ENCOUNTER_MODELS.items():
        tree = ast.parse(read_text(path))
        classes = {
            node.name: node
            for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name in class_names
        }

        missing_classes = sorted(class_names - set(classes))
        for class_name in missing_classes:
            failures.append(f"{path.relative_to(ROOT)}::{class_name} missing")

        for class_name, class_node in sorted(classes.items()):
            for statement in class_node.body:
                if not isinstance(statement, ast.AnnAssign) or not isinstance(statement.target, ast.Name):
                    continue

                field_name = statement.target.id
                if field_name.startswith("_"):
                    continue

                if not is_field_call(statement.value):
                    failures.append(f"{path.relative_to(ROOT)}::{class_name}.{field_name} is not Field(...)")
                elif not field_has_description(statement.value):
                    failures.append(f"{path.relative_to(ROOT)}::{class_name}.{field_name} lacks description")

    assert not failures, "Encounter metadata gaps:\n" + "\n".join(failures)


def test_encounter_models_use_google_style_docstrings() -> None:
    """Guard cleaned encounter model docstrings against terse regressions."""
    failures: list[str] = []

    for path, class_names in ENCOUNTER_MODELS.items():
        tree = ast.parse(read_text(path))
        classes = {
            node.name: node
            for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name in class_names
        }

        missing_classes = sorted(class_names - set(classes))
        for class_name in missing_classes:
            failures.append(f"{path.relative_to(ROOT)}::{class_name} missing")

        for class_name, class_node in sorted(classes.items()):
            docstring = ast.get_docstring(class_node) or ""
            if "\n\nAttributes:\n" not in docstring:
                failures.append(f"{path.relative_to(ROOT)}::{class_name} lacks Google-style Attributes block")
                continue

            doc_lines = [line.strip() for line in docstring.splitlines()]
            for statement in class_node.body:
                if not isinstance(statement, ast.AnnAssign) or not isinstance(statement.target, ast.Name):
                    continue

                field_name = statement.target.id
                if field_name.startswith("_"):
                    continue

                if not any(line.startswith(f"{field_name}:") for line in doc_lines):
                    failures.append(f"{path.relative_to(ROOT)}::{class_name}.{field_name} missing from docstring")

    assert not failures, "Encounter docstring gaps:\n" + "\n".join(failures)


def test_encounter_module_has_no_inline_comments() -> None:
    """The cleaned encounter module should not reintroduce code comments."""
    failures: list[str] = []

    for path in ENCOUNTER_MODELS:
        text = read_text(path)
        for token in tokenize.generate_tokens(io.StringIO(text).readline):
            if token.type == tokenize.COMMENT:
                failures.append(f"{path.relative_to(ROOT)}:{token.start[0]} has inline comment")

    assert not failures, "Encounter comment regressions:\n" + "\n".join(failures)


def test_class_feature_models_use_described_pydantic_fields() -> None:
    """Cleaned class-feature models should expose described Pydantic fields."""
    failures: list[str] = []

    for path, class_names in CLASS_FEATURE_DESCRIBED_MODEL_CLASSES.items():
        tree = ast.parse(read_text(path))
        classes = {
            node.name: node
            for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name in class_names
        }

        missing_classes = sorted(class_names - set(classes))
        for class_name in missing_classes:
            failures.append(f"{path.relative_to(ROOT)}::{class_name} missing")

        for class_name, class_node in sorted(classes.items()):
            for statement in class_node.body:
                if not isinstance(statement, ast.AnnAssign) or not isinstance(statement.target, ast.Name):
                    continue

                field_name = statement.target.id
                if field_name.startswith("_"):
                    continue

                if not is_field_call(statement.value):
                    failures.append(f"{path.relative_to(ROOT)}::{class_name}.{field_name} is not Field(...)")
                elif not field_has_description(statement.value):
                    failures.append(f"{path.relative_to(ROOT)}::{class_name}.{field_name} lacks description")

    assert not failures, "Class-feature metadata gaps:\n" + "\n".join(failures)


def test_cleaned_class_feature_models_use_google_style_docstrings() -> None:
    """Guard cleaned class-feature model docstrings against terse regressions."""
    failures: list[str] = []

    for path, class_names in CLASS_FEATURE_GOOGLE_DOCSTRING_CLASSES.items():
        tree = ast.parse(read_text(path))
        classes = {
            node.name: node
            for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name in class_names
        }

        missing_classes = sorted(class_names - set(classes))
        for class_name in missing_classes:
            failures.append(f"{path.relative_to(ROOT)}::{class_name} missing")

        for class_name, class_node in sorted(classes.items()):
            docstring = ast.get_docstring(class_node) or ""
            if "\n\nAttributes:\n" not in docstring:
                failures.append(f"{path.relative_to(ROOT)}::{class_name} lacks Google-style Attributes block")
                continue

            doc_lines = [line.strip() for line in docstring.splitlines()]
            for statement in class_node.body:
                if not isinstance(statement, ast.AnnAssign) or not isinstance(statement.target, ast.Name):
                    continue

                field_name = statement.target.id
                if field_name.startswith("_"):
                    continue

                if not any(line.startswith(f"{field_name}:") for line in doc_lines):
                    failures.append(f"{path.relative_to(ROOT)}::{class_name}.{field_name} missing from docstring")

    assert not failures, "Class-feature docstring gaps:\n" + "\n".join(failures)


def test_cleaned_server_api_models_use_described_pydantic_fields() -> None:
    """Cleaned server API DTOs should expose described fields."""
    failures: list[str] = []

    for path, class_names in SERVER_API_DESCRIBED_MODEL_CLASSES.items():
        tree = ast.parse(read_text(path))
        classes = {
            node.name: node
            for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name in class_names
        }

        missing_classes = sorted(class_names - set(classes))
        for class_name in missing_classes:
            failures.append(f"{path.relative_to(ROOT)}::{class_name} missing")

        for class_name, class_node in sorted(classes.items()):
            for statement in class_node.body:
                if not isinstance(statement, ast.AnnAssign) or not isinstance(statement.target, ast.Name):
                    continue

                field_name = statement.target.id
                if field_name.startswith("_"):
                    continue

                if not is_field_call(statement.value):
                    failures.append(f"{path.relative_to(ROOT)}::{class_name}.{field_name} is not Field(...)")
                elif not field_has_description(statement.value):
                    failures.append(f"{path.relative_to(ROOT)}::{class_name}.{field_name} lacks description")

    assert not failures, "Server API metadata gaps:\n" + "\n".join(failures)


def test_cleaned_server_api_models_use_google_style_docstrings() -> None:
    """Guard cleaned server API DTO docstrings."""
    failures: list[str] = []

    for path, class_names in SERVER_API_GOOGLE_DOCSTRING_CLASSES.items():
        tree = ast.parse(read_text(path))
        classes = {
            node.name: node
            for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name in class_names
        }

        missing_classes = sorted(class_names - set(classes))
        for class_name in missing_classes:
            failures.append(f"{path.relative_to(ROOT)}::{class_name} missing")

        for class_name, class_node in sorted(classes.items()):
            docstring = ast.get_docstring(class_node) or ""
            if "\n\nAttributes:\n" not in docstring:
                failures.append(f"{path.relative_to(ROOT)}::{class_name} lacks Google-style Attributes block")
                continue

            doc_lines = [line.strip() for line in docstring.splitlines()]
            for statement in class_node.body:
                if not isinstance(statement, ast.AnnAssign) or not isinstance(statement.target, ast.Name):
                    continue

                field_name = statement.target.id
                if field_name.startswith("_"):
                    continue

                if not any(line.startswith(f"{field_name}:") for line in doc_lines):
                    failures.append(f"{path.relative_to(ROOT)}::{class_name}.{field_name} missing from docstring")

    assert not failures, "Server API docstring gaps:\n" + "\n".join(failures)


def test_server_session_dataclasses_use_described_fields() -> None:
    """Cleaned session dataclasses should expose described metadata fields."""
    failures: list[str] = []

    for path, class_names in SERVER_SESSION_DESCRIBED_DATACLASS_CLASSES.items():
        tree = ast.parse(read_text(path))
        classes = {
            node.name: node
            for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name in class_names
        }

        missing_classes = sorted(class_names - set(classes))
        for class_name in missing_classes:
            failures.append(f"{path.relative_to(ROOT)}::{class_name} missing")

        for class_name, class_node in sorted(classes.items()):
            for statement in class_node.body:
                if not isinstance(statement, ast.AnnAssign) or not isinstance(statement.target, ast.Name):
                    continue

                field_name = statement.target.id
                if field_name.startswith("_"):
                    continue

                if not dataclass_field_has_metadata_description(statement.value):
                    failures.append(f"{path.relative_to(ROOT)}::{class_name}.{field_name} lacks dataclass metadata description")

    assert not failures, "Server session dataclass metadata gaps:\n" + "\n".join(failures)


def test_server_session_dataclasses_use_google_style_docstrings() -> None:
    """Guard cleaned session dataclass docstrings."""
    failures: list[str] = []

    for path, class_names in SERVER_SESSION_GOOGLE_DOCSTRING_CLASSES.items():
        tree = ast.parse(read_text(path))
        classes = {
            node.name: node
            for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name in class_names
        }

        missing_classes = sorted(class_names - set(classes))
        for class_name in missing_classes:
            failures.append(f"{path.relative_to(ROOT)}::{class_name} missing")

        for class_name, class_node in sorted(classes.items()):
            docstring = ast.get_docstring(class_node) or ""
            if "\n\nAttributes:\n" not in docstring:
                failures.append(f"{path.relative_to(ROOT)}::{class_name} lacks Google-style Attributes block")
                continue

            doc_lines = [line.strip() for line in docstring.splitlines()]
            for statement in class_node.body:
                if not isinstance(statement, ast.AnnAssign) or not isinstance(statement.target, ast.Name):
                    continue

                field_name = statement.target.id
                if field_name.startswith("_"):
                    continue

                if not any(line.startswith(f"{field_name}:") for line in doc_lines):
                    failures.append(f"{path.relative_to(ROOT)}::{class_name}.{field_name} missing from docstring")

    assert not failures, "Server session dataclass docstring gaps:\n" + "\n".join(failures)


def test_pyproject_defines_uv_pytest_contract() -> None:
    """The repository exposes its tests through uv-driven pytest."""
    config = tomllib.loads(read_text(PYPROJECT))

    dev_dependencies = config["dependency-groups"]["dev"]
    pytest_config = config["tool"]["pytest"]["ini_options"]

    assert "pytest" in dev_dependencies
    assert "--capture=no" in pytest_config["addopts"]
    assert pytest_config["testpaths"] == ["tests"]
    assert pytest_config["python_files"] == "test_*.py"
    assert pytest_config["python_functions"] == "test_*"


def test_active_runtime_sources_do_not_reference_claude() -> None:
    """Active runtime code should use the Codex CLI surface, not Claude."""
    offenders: list[str] = []

    for root in RUNTIME_SOURCE_ROOTS:
        for path in sorted(root.rglob("*.py")):
            text = read_text(path)
            if "claude" in text.lower():
                offenders.append(str(path.relative_to(ROOT)))

    assert not offenders, "Runtime Claude references remain in:\n" + "\n".join(offenders)


def test_server_http_errors_do_not_use_bare_string_details() -> None:
    """Server action/API errors should expose structured correction payloads."""
    bare_string_pattern = re.compile(
        r"HTTPException\s*\([^)]*detail\s*=\s*f?[\"']",
        re.DOTALL,
    )
    offenders = [
        str(path.relative_to(ROOT))
        for path in SERVER_API_FILES
        if bare_string_pattern.search(read_text(path))
    ]

    assert not offenders, "Bare string HTTPException detail in:\n" + "\n".join(offenders)
