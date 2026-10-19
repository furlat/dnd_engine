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
ENCOUNTER_MODELS = {
    ROOT / "dnd" / "encounter.py": {
        "AdvanceResult",
        "CombatantState",
        "Encounter",
    },
}
CLASS_FEATURE_DESCRIBED_MODEL_CLASSES = {
    ROOT / "dnd" / "conditions.py": {"ExtraAttacksGranted"},
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
        "ElementalAffinityResistance",
        "ElementalAffinityResistanceAction",
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
    ROOT / "dnd" / "conditions.py": {"ExtraAttacksGranted"},
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
        "ElementalAffinityResistance",
        "ElementalAffinityResistanceAction",
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
WORLD_REGISTRY_NAMES = frozenset({"get_all_entities", "_entity_registry"})
KEYED_REGISTRY_OPS = frozenset({"get", "pop"})
# The only functions in dnd/ that may read every registered Entity (plan §14.8).
WORLD_SCAN_EXCEPTIONS = {
    "dnd/entity.py": "get_all_entities",  # the registry's own accessor
    "dnd/runtime_reset.py": "reset_engine_runtime",  # clears the registry
    "dnd/content_system/pack_loader.py": "_engine_runtime_attribute_specs",  # cold-runtime check
    "dnd/scenarios/encounter_assembler.py": "assemble_encounter_recipe",  # empty-world setup guard
}
def read_text(path: Path) -> str:
    """Read repository text with a consistent encoding."""
    return path.read_text(encoding="utf-8")


def is_class_variable(statement: ast.AnnAssign) -> bool:
    """Class-level execution policy is not a Pydantic model field."""
    annotation = statement.annotation
    if not isinstance(annotation, ast.Subscript):
        return False
    return (
        isinstance(annotation.value, ast.Name) and annotation.value.id == "ClassVar"
        or isinstance(annotation.value, ast.Attribute) and annotation.value.attr == "ClassVar"
    )


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


def is_discriminator_tag(statement: ast.AnnAssign) -> bool:
    """A tagged-union tag (`kind: Literal["..."] = "..."`): a self-describing wire constant of the published
    client schema, not a field to describe."""
    return (isinstance(statement.target, ast.Name) and statement.target.id == "kind"
            and isinstance(statement.annotation, ast.Subscript) and isinstance(statement.annotation.value, ast.Name)
            and statement.annotation.value.id == "Literal" and isinstance(statement.value, ast.Constant))


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
                if field_name.startswith("_") or is_discriminator_tag(statement):
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
            if not any(isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name)
                       and not statement.target.id.startswith("_") and not is_discriminator_tag(statement)
                       for statement in class_node.body):
                # Only a tag over its parent's documented fields.
                continue
            docstring = ast.get_docstring(class_node) or ""
            if "\n\nAttributes:\n" not in docstring:
                failures.append(f"{path.relative_to(ROOT)}::{class_name} lacks Google-style Attributes block")
                continue

            doc_lines = [line.strip() for line in docstring.splitlines()]
            for statement in class_node.body:
                if not isinstance(statement, ast.AnnAssign) or not isinstance(statement.target, ast.Name):
                    continue

                field_name = statement.target.id
                if field_name.startswith("_") or is_discriminator_tag(statement):
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
                if field_name.startswith("_") or is_class_variable(statement):
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
                if field_name.startswith("_") or is_class_variable(statement):
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
    """Active runtime code should use the Codex CLI surface, not Claude."""
    offenders: list[str] = []

    for root in RUNTIME_SOURCE_ROOTS:
        for path in sorted(root.rglob("*.py")):
            text = read_text(path)
            if "claude" in text.lower():
                offenders.append(str(path.relative_to(ROOT)))

    assert not offenders, "Runtime Claude references remain in:\n" + "\n".join(offenders)


def world_registry_reads(path: Path) -> list[tuple[str, int]]:
    """(enclosing function, line) of each whole-world Entity registry read.

    That is `get_all_entities`, or `_entity_registry` used other than by key
    (`[uuid]`, `.get`, `.pop`), by attribute or by name in a string.
    """
    reads: list[tuple[str, int]] = []

    def visit(node: ast.AST, function: str, parent: ast.AST | None) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            function = node.name
        name = (node.attr if isinstance(node, ast.Attribute)
                else node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None)
        keyed = (isinstance(parent, ast.Subscript) and parent.value is node
                 or isinstance(parent, ast.Attribute) and parent.attr in KEYED_REGISTRY_OPS)
        if name in WORLD_REGISTRY_NAMES and not (name == "_entity_registry" and keyed):
            reads.append((function, node.lineno))
        for child in ast.iter_child_nodes(node):
            visit(child, function, node)

    visit(ast.parse(read_text(path)), "<module>", None)
    return reads


def test_dnd_never_iterates_every_registered_entity_outside_the_listed_owners() -> None:
    """Execution reads bounded owners and discovery reads perception (plan §14.8)."""
    offenders: list[str] = []
    used: set[str] = set()
    for path in sorted((ROOT / "dnd").rglob("*.py")):
        relative = path.relative_to(ROOT).as_posix()
        for function, line in world_registry_reads(path):
            if WORLD_SCAN_EXCEPTIONS.get(relative) == function:
                used.add(relative)
            else:
                offenders.append(f"{relative}:{line} in {function}")

    assert not offenders, "Whole-world Entity registry reads in dnd/:\n" + "\n".join(offenders)
    assert used == set(WORLD_SCAN_EXCEPTIONS), "Stale world-scan exceptions: " + ", ".join(
        sorted(set(WORLD_SCAN_EXCEPTIONS) - used))
