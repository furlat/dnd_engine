"""Static ownership rules for action affordability and discovery requirements."""

import ast
from pathlib import Path


ENGINE_ROOT = Path(__file__).resolve().parents[2] / "dnd"
_COST_METHOD_NAMES = frozenset({
    "can_afford",
    "can_afford_action_resource",
    "can_afford_resource",
    "check_costs",
    "check_target_independent_costs",
    "get_lowest_spell_slot",
    "has_spell_slot",
})


def _action_method_definitions() -> list[tuple[Path, ast.ClassDef, ast.FunctionDef]]:
    """Return action-validation methods declared in active engine sources."""
    definitions: list[tuple[Path, ast.ClassDef, ast.FunctionDef]] = []
    for path in sorted(ENGINE_ROOT.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            for member in node.body:
                if isinstance(member, ast.FunctionDef) and member.name in {
                    "check_costs",
                    "check_target_independent_costs",
                    "get_source_dynamic_costs",
                    "get_target_dynamic_costs",
                    "_validate",
                    "pre_validate",
                    "validate_requirements_for_discovery",
                }:
                    definitions.append((path, node, member))
    return definitions


def test_base_action_owns_the_only_combined_pre_validate_surface() -> None:
    """Subclasses split requirements into the cost-independent hook."""
    owners = [
        (path.relative_to(ENGINE_ROOT), class_node.name)
        for path, class_node, method in _action_method_definitions()
        if method.name == "pre_validate"
    ]

    assert owners == [(Path("core/base_actions.py"), "BaseAction")]


def test_base_action_owns_the_only_affordability_evaluator() -> None:
    """Dynamic action costs extend the typed list instead of overriding policy."""
    owners = [
        (path.relative_to(ENGINE_ROOT), class_node.name)
        for path, class_node, method in _action_method_definitions()
        if method.name == "check_costs"
    ]

    assert owners == [(Path("core/base_actions.py"), "BaseAction")]


def test_base_action_owns_the_only_target_independent_affordability_evaluator() -> None:
    """Discovery cannot override the source-versus-target cost boundary."""
    owners = [
        (path.relative_to(ENGINE_ROOT), class_node.name)
        for path, class_node, method in _action_method_definitions()
        if method.name == "check_target_independent_costs"
    ]

    assert owners == [(Path("core/base_actions.py"), "BaseAction")]


def test_dynamic_cost_hooks_have_one_explicit_source_or_target_ownership() -> None:
    """Every current dynamic cost declares which discovery phase may read it."""
    owners = {
        method.name: [
            (path.relative_to(ENGINE_ROOT), class_node.name)
            for path, class_node, candidate in _action_method_definitions()
            if candidate.name == method.name
        ]
        for _, _, method in _action_method_definitions()
        if method.name in {
            "get_source_dynamic_costs",
            "get_target_dynamic_costs",
        }
    }

    assert owners == {
        "get_source_dynamic_costs": [
            (Path("core/base_actions.py"), "BaseAction"),
            (Path("monsters/traits.py"), "DivineEminenceAction"),
        ],
        "get_target_dynamic_costs": [
            (Path("actions.py"), "Jump"),
            (Path("core/base_actions.py"), "BaseAction"),
        ],
    }


def test_discovery_requirements_and_validation_do_not_recheck_costs() -> None:
    """Typed costs remain the sole affordability authority."""
    violations: list[str] = []
    for path, class_node, method in _action_method_definitions():
        if method.name in {
            "check_costs",
            "check_target_independent_costs",
            "get_source_dynamic_costs",
            "get_target_dynamic_costs",
            "pre_validate",
        }:
            continue
        for node in ast.walk(method):
            if isinstance(node, ast.Attribute):
                chain: list[str] = []
                cursor: ast.expr = node
                while isinstance(cursor, ast.Attribute):
                    chain.append(cursor.attr)
                    cursor = cursor.value
                if "action_economy" in chain:
                    violations.append(
                        f"{path.relative_to(ENGINE_ROOT)}:"
                        f"{node.lineno} {class_node.name}.{method.name} "
                        "reads action_economy directly"
                    )
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in _COST_METHOD_NAMES
            ):
                violations.append(
                    f"{path.relative_to(ENGINE_ROOT)}:"
                    f"{node.lineno} {class_node.name}.{method.name} "
                    f"calls {node.func.attr}()"
                )

    assert violations == []
