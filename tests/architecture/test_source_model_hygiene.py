"""Repository source-model and test-harness integrity checks."""

import ast
import io
from pathlib import Path
import tokenize
import tomllib


ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = ROOT / "pyproject.toml"
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
CLASS_FEATURE_DESCRIBED_MODEL_CLASSES = {
    ROOT / "dnd" / "classes" / "fighter.py": {
        "SecondWind",
        "ActionSurging",
        "ActionSurge",
        "ExtraAttacksGranted",
        "ExtraAttack",
    },
    ROOT / "dnd" / "classes" / "barbarian.py": {
        "RecklessAttacking",
        "RecklessAttack",
        "IntimidatingPresenceImmunity",
        "IntimidatingPresence",
        "ExtendIntimidatingPresence",
    },
    ROOT / "dnd" / "classes" / "rage.py": {
        "Rage",
        "Raging",
        "EndRage",
        "Frenzied",
        "FrenziedStrike",
        "Frenzy",
    },
    ROOT / "dnd" / "classes" / "sorcerer.py": {
        "ElementalAffinityResistance",
        "ElementalAffinityResistanceAction",
        "MetamagicActive",
        "QuickenedSpell",
        "TwinnedSpell",
        "DistantSpell",
        "ConvertSlotToSP",
        "ConvertSPToSlot",
    },
}
CLASS_FEATURE_GOOGLE_DOCSTRING_CLASSES = {
    ROOT / "dnd" / "classes" / "fighter.py": {
        "SecondWind",
        "ActionSurging",
        "ActionSurge",
        "ExtraAttacksGranted",
        "ExtraAttack",
    },
    ROOT / "dnd" / "classes" / "barbarian.py": {
        "RecklessAttacking",
        "RecklessAttack",
        "IntimidatingPresenceImmunity",
        "IntimidatingPresence",
        "ExtendIntimidatingPresence",
    },
    ROOT / "dnd" / "classes" / "rage.py": {
        "Rage",
        "Raging",
        "EndRage",
        "Frenzied",
        "FrenziedStrike",
        "Frenzy",
    },
    ROOT / "dnd" / "classes" / "sorcerer.py": {
        "ElementalAffinityResistance",
        "ElementalAffinityResistanceAction",
        "MetamagicActive",
        "QuickenedSpell",
        "TwinnedSpell",
        "DistantSpell",
        "ConvertSlotToSP",
        "ConvertSPToSlot",
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
    """Active runtime code must not retain the retired Claude integration."""
    offenders: list[str] = []

    for root in RUNTIME_SOURCE_ROOTS:
        for path in sorted(root.rglob("*.py")):
            text = read_text(path)
            if "claude" in text.lower():
                offenders.append(str(path.relative_to(ROOT)))

    assert not offenders, "Runtime Claude references remain in:\n" + "\n".join(offenders)
