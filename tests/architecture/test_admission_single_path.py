"""Architecture: one legality path (plan §14.3b).

The shared admission checks live once on BaseAction. An action adds its own
rule through `rule_error`; it never replaces the shared checks, so a forgotten
`super()` cannot skip them.
"""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_no_action_overrides_the_shared_admission_checks() -> None:
    overrides = []
    for path in sorted((ROOT / "dnd").rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ClassDef) and node.name != "BaseAction":
                overrides.extend(f"{path.relative_to(ROOT)}:{item.lineno} {node.name}" for item in node.body
                                 if isinstance(item, ast.FunctionDef) and item.name == "_admission_error")
    assert overrides == []


FAMILY_BASES = {"BaseAction", "SpellAction"}


def test_only_action_family_bases_add_source_admission() -> None:
    """A concrete action states its own rule in `rule_error`, not in the family hook."""
    definers = []
    for path in sorted((ROOT / "dnd").rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ClassDef) and node.name not in FAMILY_BASES:
                definers.extend(f"{path.relative_to(ROOT)}:{item.lineno} {node.name}" for item in node.body
                                if isinstance(item, ast.FunctionDef) and item.name == "_family_admission_error")
    assert definers == []


HANDLER_ADMISSION_ACTIONS = {"SummonSpell"}


def test_only_named_handler_admission_actions_keep_their_own_admission() -> None:
    """`_validate` is BaseAction's alone; handler-based admission is the named list (plan §14.3b)."""
    validators, handler_admissions = [], set()
    for path in sorted((ROOT / "dnd").rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ClassDef) and node.name != "BaseAction":
                for item in node.body:
                    if isinstance(item, ast.FunctionDef) and item.name == "_validate":
                        validators.append(f"{path.relative_to(ROOT)}:{item.lineno} {node.name}")
                    if isinstance(item, ast.FunctionDef) and item.name == "handler_admission_error":
                        handler_admissions.add(node.name)
    assert validators == []
    assert handler_admissions == HANDLER_ADMISSION_ACTIONS


PROFILE_HOOKS = {"get_outcome_profile", "get_fixed_healing", "get_self_setup_profile", "get_target_effect_profile",
                 "get_world_effect_profile", "get_action_target_effect_profile", "get_action_damage_roll_profiles"}


def test_profile_hooks_take_no_actor() -> None:
    """Profile hooks resolve their actor from the action's source (plan Q-W6); nobody passes one in."""
    with_actor = []
    for path in sorted((ROOT / "dnd").rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.FunctionDef) and node.name in PROFILE_HOOKS:
                if any(argument.arg in ("actor", "entity") for argument in node.args.args):
                    with_actor.append(f"{path.relative_to(ROOT)}:{node.lineno} {node.name}")
    assert with_actor == []
