#!/usr/bin/env python3
"""Discover direct ``BaseAction`` construction-to-``apply`` source sites.

This is a standalone developer audit helper.  The action class universe and
execution sites are recovered from Python syntax; the installed content
registry is loaded only to validate reviewed identity keys.  The checked
dispositions at the bottom are deliberately an exact review ledger.  Adding a
source site without reviewing it, or leaving a ledger row after its source site
disappears, makes this command fail.

The scanner covers direct calls in one lexical scope, including both forms::

    action = SomeAction(...)
    action.apply(...)

    SomeAction(...).apply(...)

Simple aliases and conservative control-flow merges are supported.  A value
constructed in one function and applied in another is intentionally outside
this helper's definition of a *direct* site.
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import TypeAlias


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BASE_ACTION_FQN = "dnd.core.base_actions.BaseAction"
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))


@dataclass(frozen=True, order=True, slots=True)
class SourceSpan:
    """Zero-based columns and one-based lines for one syntax node."""

    line: int
    column: int
    end_line: int
    end_column: int

    @classmethod
    def from_node(cls, node: ast.AST) -> "SourceSpan":
        return cls(
            line=node.lineno,
            column=node.col_offset,
            end_line=node.end_lineno,
            end_column=node.end_col_offset,
        )


@dataclass(frozen=True, order=True, slots=True)
class ActionSite:
    """One direct action construction reaching one ``apply`` invocation."""

    path: str
    scope: str
    action_class: str
    constructor: SourceSpan
    apply: SourceSpan
    receiver_name: str | None

    @property
    def key(self) -> str:
        """Return the stable, review-ledger identity for this exact site."""
        return (
            f"{self.path}:{self.constructor.line}:{self.constructor.column}"
            f"->{self.apply.line}:{self.apply.column}"
            f"|{self.scope}|{self.action_class}"
        )


class Disposition(str, Enum):
    """Reviewed presentation-bridge outcome for one direct source site."""

    CONNECTED_EXPLICIT_BINDING = "CONNECTED_EXPLICIT_BINDING"
    BROKEN_FRAME_BLOCKING = "BROKEN_FRAME_BLOCKING"
    BROKEN_SEMANTIC_OMISSION = "BROKEN_SEMANTIC_OMISSION"
    INTENTIONAL_STATE_ONLY = "INTENTIONAL_STATE_ONLY"


@dataclass(frozen=True, slots=True)
class CheckedDisposition:
    """Human-reviewed bridge meaning attached to one source-derived site."""

    disposition: Disposition
    expected_identity_key: str | None
    detail: str


@dataclass(frozen=True, slots=True)
class ModuleSyntax:
    """Parsed module facts needed for deterministic name resolution."""

    path: Path
    relative_path: str
    module: str
    tree: ast.Module
    imports: Mapping[str, str]
    classes: Mapping[str, str]


@dataclass(frozen=True, order=True, slots=True)
class ConstructorBinding:
    """One statically resolved action constructor reaching a local name."""

    action_class: str
    span: SourceSpan


BindingSet: TypeAlias = frozenset[ConstructorBinding]
BindingEnvironment: TypeAlias = dict[str, BindingSet]


def _module_name(path: Path, root: Path) -> str:
    relative = path.relative_to(root).with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _resolve_import_from(module: str, imported: str | None, level: int) -> str:
    if level == 0:
        return imported or ""
    package_parts = module.split(".")[:-1]
    keep = len(package_parts) - (level - 1)
    if keep < 0:
        return imported or ""
    parts = package_parts[:keep]
    if imported:
        parts.extend(imported.split("."))
    return ".".join(parts)


def _module_imports(tree: ast.Module, module: str) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for statement in tree.body:
        if isinstance(statement, ast.Import):
            for alias in statement.names:
                binding = alias.asname or alias.name.split(".")[0]
                aliases[binding] = alias.name if alias.asname else binding
        elif isinstance(statement, ast.ImportFrom):
            imported_module = _resolve_import_from(
                module,
                statement.module,
                statement.level,
            )
            for alias in statement.names:
                if alias.name == "*":
                    continue
                binding = alias.asname or alias.name
                aliases[binding] = f"{imported_module}.{alias.name}"
    return aliases


def _parse_modules(root: Path) -> tuple[ModuleSyntax, ...]:
    modules: list[ModuleSyntax] = []
    for path in sorted((root / "dnd").rglob("*.py")):
        relative_path = path.relative_to(root).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative_path)
        module = _module_name(path, root)
        classes = {
            statement.name: f"{module}.{statement.name}"
            for statement in tree.body
            if isinstance(statement, ast.ClassDef)
        }
        imports = _module_imports(tree, module)
        # Resolve simple module-level class aliases/re-exports to a fixed point.
        # This makes `A = ImportedAction` and package `__init__` re-exports
        # participate in the same class/call universe as direct imports.
        changed = True
        while changed:
            changed = False
            symbols = {**imports, **classes}
            for statement in tree.body:
                if not (
                    isinstance(statement, ast.Assign)
                    and len(statement.targets) == 1
                    and isinstance(statement.targets[0], ast.Name)
                    and isinstance(statement.value, (ast.Name, ast.Attribute))
                ):
                    continue
                target = statement.targets[0].id
                if isinstance(statement.value, ast.Name):
                    resolved = symbols.get(statement.value.id)
                else:
                    parts: list[str] = []
                    cursor: ast.expr = statement.value
                    while isinstance(cursor, ast.Attribute):
                        parts.append(cursor.attr)
                        cursor = cursor.value
                    resolved = (
                        symbols.get(cursor.id) if isinstance(cursor, ast.Name)
                        else None
                    )
                    if resolved is not None:
                        resolved = ".".join((resolved, *reversed(parts)))
                if resolved is not None and imports.get(target) != resolved:
                    imports[target] = resolved
                    changed = True
        modules.append(
            ModuleSyntax(
                path=path,
                relative_path=relative_path,
                module=module,
                tree=tree,
                imports=imports,
                classes=classes,
            ),
        )
    return tuple(modules)


def _resolve_expression(
    expression: ast.expr,
    module: ModuleSyntax,
    local_symbols: Mapping[str, str] | None = None,
) -> str | None:
    symbols = local_symbols or {}
    if isinstance(expression, ast.Name):
        resolved = (
            symbols.get(expression.id)
            or module.classes.get(expression.id)
            or module.imports.get(expression.id)
        )
        if resolved is not None:
            return resolved
        if expression.id in {
            "object", "str", "int", "float", "bool", "dict", "list",
            "tuple", "set", "frozenset", "Exception", "ValueError",
        }:
            return f"builtins.{expression.id}"
        return None
    if isinstance(expression, ast.Attribute):
        owner = _resolve_expression(expression.value, module, symbols)
        if owner is not None:
            return f"{owner}.{expression.attr}"
    if isinstance(expression, ast.Subscript):
        return _resolve_expression(expression.value, module, symbols)
    return None


def discover_action_classes(
    modules: Sequence[ModuleSyntax],
) -> tuple[frozenset[str], tuple[str, ...]]:
    """Return the fixed-point ``BaseAction`` class closure and unresolved bases."""
    direct_bases: dict[str, tuple[str, ...]] = {}
    unresolved: list[str] = []
    for module in modules:
        for statement in module.tree.body:
            if not isinstance(statement, ast.ClassDef):
                continue
            class_fqn = module.classes[statement.name]
            resolved_bases: list[str] = []
            for base in statement.bases:
                resolved = _resolve_expression(base, module)
                if resolved is None:
                    unresolved.append(
                        f"{module.relative_path}:{base.lineno}:"
                        f"{base.col_offset}:{class_fqn}:{ast.unparse(base)}",
                    )
                else:
                    resolved_bases.append(resolved)
            direct_bases[class_fqn] = tuple(resolved_bases)

    action_classes = {BASE_ACTION_FQN}
    changed = True
    while changed:
        changed = False
        for class_fqn, bases in sorted(direct_bases.items()):
            if class_fqn not in action_classes and any(
                base in action_classes for base in bases
            ):
                action_classes.add(class_fqn)
                changed = True
    unresolved_action_candidates = tuple(sorted(
        row for row in unresolved
        if not row.rsplit(":", 1)[-1].startswith((
            "Sequence[", "Mapping[", "dict[", "list[", "tuple[",
            "set[", "frozenset[",
        ))
        and any(token in row.rsplit(":", 1)[-1] for token in (
            "Action", "Spell", "Attack", "Move", "Dash", "Shove",
        ))
    ))
    return frozenset(action_classes), unresolved_action_candidates


def _constructor_binding(
    expression: ast.expr,
    *,
    module: ModuleSyntax,
    action_classes: frozenset[str],
    local_symbols: Mapping[str, str],
) -> ConstructorBinding | None:
    if not isinstance(expression, ast.Call):
        return None
    action_class = _resolve_expression(expression.func, module, local_symbols)
    if action_class not in action_classes:
        return None
    return ConstructorBinding(
        action_class=action_class,
        span=SourceSpan.from_node(expression),
    )


def _merge_environments(environments: Iterable[BindingEnvironment]) -> BindingEnvironment:
    merged: BindingEnvironment = {}
    for environment in environments:
        for name, bindings in environment.items():
            merged[name] = merged.get(name, frozenset()) | bindings
    return merged


def _binding_keys(target: ast.expr) -> tuple[str, ...]:
    if isinstance(target, ast.Name):
        return (target.id,)
    if isinstance(target, ast.Attribute):
        parts = [target.attr]
        cursor = target.value
        while isinstance(cursor, ast.Attribute):
            parts.append(cursor.attr)
            cursor = cursor.value
        if isinstance(cursor, ast.Name):
            return (".".join((cursor.id, *reversed(parts))),)
        return ()
    if isinstance(target, (ast.Tuple, ast.List)):
        return tuple(
            name for item in target.elts for name in _binding_keys(item)
        )
    if isinstance(target, ast.Starred):
        return _binding_keys(target.value)
    return ()


class _ExpressionApplyVisitor(ast.NodeVisitor):
    """Find direct/chained apply calls without entering nested lexical scopes."""

    def __init__(
        self,
        *,
        module: ModuleSyntax,
        scope: str,
        action_classes: frozenset[str],
        bindings: BindingEnvironment,
        local_symbols: Mapping[str, str],
    ) -> None:
        self.module = module
        self.scope = scope
        self.action_classes = action_classes
        self.bindings = bindings
        self.local_symbols = local_symbols
        self.sites: list[ActionSite] = []

    def visit_Lambda(self, node: ast.Lambda) -> None:  # noqa: N802
        return

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
        return

    def visit_AsyncFunctionDef(  # noqa: N802
        self,
        node: ast.AsyncFunctionDef,
    ) -> None:
        return

    def visit_ClassDef(self, node: ast.ClassDef) -> None:  # noqa: N802
        return

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        if isinstance(node.func, ast.Attribute) and node.func.attr == "apply":
            receiver = node.func.value
            direct = _constructor_binding(
                receiver,
                module=self.module,
                action_classes=self.action_classes,
                local_symbols=self.local_symbols,
            )
            candidates: BindingSet = frozenset((direct,)) if direct else frozenset()
            receiver_keys = _binding_keys(receiver)
            receiver_name = receiver_keys[0] if len(receiver_keys) == 1 else None
            if receiver_name is not None:
                candidates |= self.bindings.get(receiver_name, frozenset())
            for candidate in sorted(candidates):
                self.sites.append(
                    ActionSite(
                        path=self.module.relative_path,
                        scope=self.scope,
                        action_class=candidate.action_class,
                        constructor=candidate.span,
                        apply=SourceSpan.from_node(node),
                        receiver_name=receiver_name,
                    ),
                )
        self.generic_visit(node)

    def visit_NamedExpr(self, node: ast.NamedExpr) -> None:  # noqa: N802
        # Python evaluates the value before assigning the target.
        self.visit(node.value)
        keys = _binding_keys(node.target)
        constructor = _constructor_binding(
            node.value,
            module=self.module,
            action_classes=self.action_classes,
            local_symbols=self.local_symbols,
        )
        values = frozenset((constructor,)) if constructor else frozenset()
        for key in keys:
            if values:
                self.bindings[key] = values
            else:
                self.bindings.pop(key, None)
            if "." not in key:
                self.local_symbols[key] = "<local-shadow>"


class _ScopeScanner:
    """Conservative statement-order scanner for one lexical scope."""

    def __init__(
        self,
        *,
        module: ModuleSyntax,
        scope: str,
        action_classes: frozenset[str],
    ) -> None:
        self.module = module
        self.scope = scope
        self.action_classes = action_classes
        self.sites: list[ActionSite] = []
        self.local_symbols: dict[str, str] = {}

    def _scan_expression(
        self,
        expression: ast.expr | None,
        bindings: BindingEnvironment,
    ) -> None:
        if expression is None:
            return
        visitor = _ExpressionApplyVisitor(
            module=self.module,
            scope=self.scope,
            action_classes=self.action_classes,
            bindings=bindings,
            local_symbols=self.local_symbols,
        )
        visitor.visit(expression)
        self.sites.extend(visitor.sites)

    def _value_bindings(
        self,
        value: ast.expr,
        bindings: BindingEnvironment,
    ) -> BindingSet:
        constructor = _constructor_binding(
            value,
            module=self.module,
            action_classes=self.action_classes,
            local_symbols=self.local_symbols,
        )
        if constructor is not None:
            return frozenset((constructor,))
        if isinstance(value, ast.Name):
            return bindings.get(value.id, frozenset())
        return frozenset()

    def _replace_targets(
        self,
        environment: BindingEnvironment,
        targets: Iterable[ast.expr],
        values: BindingSet,
    ) -> None:
        for target in targets:
            for name in _binding_keys(target):
                if "." not in name:
                    self.local_symbols[name] = "<local-shadow>"
                if values:
                    environment[name] = values
                else:
                    environment.pop(name, None)

    def scan(
        self,
        statements: Sequence[ast.stmt],
        initial: BindingEnvironment | None = None,
    ) -> BindingEnvironment:
        environment = dict(initial or {})
        for statement in statements:
            if isinstance(statement, ast.Assign):
                self._scan_expression(statement.value, environment)
                values = self._value_bindings(statement.value, environment)
                self._replace_targets(environment, statement.targets, values)
                resolved_symbol = _resolve_expression(
                    statement.value,
                    self.module,
                    self.local_symbols,
                )
                if resolved_symbol in self.action_classes:
                    for target in statement.targets:
                        for name in _binding_keys(target):
                            if "." not in name:
                                self.local_symbols[name] = resolved_symbol
            elif isinstance(statement, ast.AnnAssign):
                self._scan_expression(statement.annotation, environment)
                self._scan_expression(statement.value, environment)
                values = (
                    self._value_bindings(statement.value, environment)
                    if statement.value is not None
                    else frozenset()
                )
                self._replace_targets(environment, (statement.target,), values)
            elif isinstance(statement, ast.AugAssign):
                self._scan_expression(statement.target, environment)
                self._scan_expression(statement.value, environment)
                self._replace_targets(environment, (statement.target,), frozenset())
            elif isinstance(statement, (ast.Expr, ast.Return, ast.Raise, ast.Assert)):
                for value in ast.iter_child_nodes(statement):
                    if isinstance(value, ast.expr):
                        self._scan_expression(value, environment)
            elif isinstance(statement, ast.If):
                self._scan_expression(statement.test, environment)
                body = self.scan(statement.body, dict(environment))
                otherwise = self.scan(statement.orelse, dict(environment))
                environment = _merge_environments((body, otherwise))
            elif isinstance(statement, (ast.For, ast.AsyncFor)):
                self._scan_expression(statement.iter, environment)
                loop_environment = dict(environment)
                self._replace_targets(
                    loop_environment,
                    (statement.target,),
                    frozenset(),
                )
                body = self.scan(statement.body, loop_environment)
                otherwise = self.scan(statement.orelse, dict(environment))
                environment = _merge_environments((environment, body, otherwise))
            elif isinstance(statement, ast.While):
                self._scan_expression(statement.test, environment)
                body = self.scan(statement.body, dict(environment))
                otherwise = self.scan(statement.orelse, dict(environment))
                environment = _merge_environments((environment, body, otherwise))
            elif isinstance(statement, (ast.With, ast.AsyncWith)):
                with_environment = dict(environment)
                for item in statement.items:
                    self._scan_expression(item.context_expr, environment)
                    if item.optional_vars is not None:
                        self._replace_targets(
                            with_environment,
                            (item.optional_vars,),
                            frozenset(),
                        )
                environment = self.scan(statement.body, with_environment)
            elif isinstance(statement, (ast.Try, ast.TryStar)):
                body = self.scan(statement.body, dict(environment))
                branches = [body]
                for handler in statement.handlers:
                    # An exception can arise after any successful prefix in the
                    # try body; conservatively expose both incoming and body
                    # bindings to the handler.
                    handler_environment = _merge_environments(
                        (environment, body),
                    )
                    if handler.name:
                        handler_environment.pop(handler.name, None)
                    branches.append(self.scan(handler.body, handler_environment))
                merged = _merge_environments(branches)
                merged = self.scan(statement.orelse, merged)
                environment = self.scan(statement.finalbody, merged)
            elif isinstance(statement, ast.Match):
                self._scan_expression(statement.subject, environment)
                branches = [environment]
                for case in statement.cases:
                    case_environment = dict(environment)
                    self._scan_expression(case.guard, case_environment)
                    branches.append(self.scan(case.body, case_environment))
                environment = _merge_environments(branches)
            elif isinstance(statement, ast.Global):
                for name in statement.names:
                    self.local_symbols.pop(name, None)
            elif isinstance(statement, ast.Nonlocal):
                for name in statement.names:
                    self.local_symbols.pop(name, None)
            elif isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                # Nested lexical scopes are scanned independently below.
                environment.pop(statement.name, None)
                self.local_symbols.pop(statement.name, None)
            elif isinstance(statement, (ast.Import, ast.ImportFrom)):
                # Local imports are available after their statement.
                local_tree = ast.Module(body=[statement], type_ignores=[])
                self.local_symbols.update(
                    _module_imports(local_tree, self.module.module),
                )
            elif isinstance(statement, ast.Delete):
                self._replace_targets(environment, statement.targets, frozenset())
                for target in statement.targets:
                    for name in _binding_keys(target):
                        self.local_symbols.pop(name, None)
            else:
                # Cover syntax with no local data-flow rule while still finding
                # chained calls in its directly owned expressions.
                for child in ast.iter_child_nodes(statement):
                    if isinstance(child, ast.expr):
                        self._scan_expression(child, environment)
        return environment


def _iter_lexical_scopes(
    module: ModuleSyntax,
) -> Iterable[tuple[str, Sequence[ast.stmt], frozenset[str]]]:
    """Yield module/class/function bodies once with deterministic qualnames."""

    def recurse(
        node: ast.AST,
        prefix: tuple[str, ...],
    ) -> Iterable[tuple[str, Sequence[ast.stmt], frozenset[str]]]:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                class_prefix = (*prefix, child.name)
                yield ".".join(class_prefix), child.body, frozenset()
                yield from recurse(child, class_prefix)
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                function_prefix = (*prefix, child.name)
                arguments = child.args
                parameter_names = frozenset(
                    argument.arg for argument in (
                        *arguments.posonlyargs,
                        *arguments.args,
                        *arguments.kwonlyargs,
                        *((arguments.vararg,) if arguments.vararg else ()),
                        *((arguments.kwarg,) if arguments.kwarg else ()),
                    )
                )
                yield ".".join(function_prefix), child.body, parameter_names
                yield from recurse(child, function_prefix)
            else:
                # ExceptHandler and match_case are wrapper nodes rather than
                # statements, so generic AST recursion is required to find
                # definitions inside their suites.
                yield from recurse(child, prefix)

    yield "<module>", module.tree.body, frozenset()
    yield from recurse(module.tree, ())


def discover_action_sites(
    modules: Sequence[ModuleSyntax],
    action_classes: frozenset[str],
) -> tuple[ActionSite, ...]:
    sites: dict[str, ActionSite] = {}
    for module in modules:
        for scope, statements, parameter_names in _iter_lexical_scopes(module):
            scanner = _ScopeScanner(
                module=module,
                scope=scope,
                action_classes=action_classes,
            )
            for parameter_name in parameter_names:
                scanner.local_symbols[parameter_name] = "<local-shadow>"
            scanner.scan(statements)
            for site in scanner.sites:
                sites[site.key] = site
    return tuple(sorted(sites.values(), key=lambda site: site.key))


def _run_scanner_self_tests() -> tuple[str, ...]:
    """Exercise supported syntax so future scanner regressions fail closed."""
    source = '''
from dnd.actions import Attack

def assigned():
    action = Attack()
    action.apply()

def chained():
    Attack().apply()

def shadowed(Attack):
    Attack().apply()

def aliased():
    LocalAttack = Attack
    LocalAttack().apply()

def named_expression():
    (action := Attack())
    action.apply()

def attribute_holder(self):
    self.action = Attack()
    self.action.apply()

def reassigned():
    action = Attack()
    action = None
    action.apply()

def exception_path():
    try:
        action = Attack()
        raise RuntimeError()
    except RuntimeError:
        action.apply()

try:
    pass
except RuntimeError:
    def nested_except():
        Attack().apply()

match 1:
    case 1:
        def nested_match():
            Attack().apply()
'''
    tree = ast.parse(source, filename="dnd/_presentation_scanner_fixture.py")
    module_name = "dnd._presentation_scanner_fixture"
    module = ModuleSyntax(
        path=Path("dnd/_presentation_scanner_fixture.py"),
        relative_path="dnd/_presentation_scanner_fixture.py",
        module=module_name,
        tree=tree,
        imports=_module_imports(tree, module_name),
        classes={},
    )
    sites = discover_action_sites((module,), frozenset({"dnd.actions.Attack"}))
    counts: dict[str, int] = {}
    for site in sites:
        counts[site.scope] = counts.get(site.scope, 0) + 1
    expected = {
        "assigned": 1,
        "chained": 1,
        "aliased": 1,
        "named_expression": 1,
        "attribute_holder": 1,
        "exception_path": 1,
        "nested_except": 1,
        "nested_match": 1,
    }
    errors: list[str] = []
    if counts != expected:
        errors.append(f"site syntax fixture mismatch: {counts!r} != {expected!r}")
    if any(site.scope in {"shadowed", "reassigned"} for site in sites):
        errors.append("shadow/reassignment fixture produced a false action site")
    return tuple(errors)


# This is review data, not source discovery.  Exact-set validation below makes
# both new source sites and obsolete ledger rows visible instead of silently
# classifying them by a broad heuristic.
CHECKED_DISPOSITIONS: Mapping[str, CheckedDisposition] = {
    (
        "dnd/actions_functional.py:571:13->577:11|execute_drop|"
        "dnd.actions.Drop"
    ): CheckedDisposition(
        disposition=Disposition.BROKEN_SEMANTIC_OMISSION,
        expected_identity_key="content.srd_5_1_cc:action:action.core.drop@1",
        detail="The direct Drop instance is not admitted through the binding gateway.",
    ),
    (
        "dnd/classes/barbarian.py:494:13->501:13|retaliation_processor|"
        "dnd.actions.Attack"
    ): CheckedDisposition(
        disposition=Disposition.BROKEN_FRAME_BLOCKING,
        expected_identity_key="content.srd_5_1_cc:reaction:reaction.class_feature.barbarian.retaliation@1",
        detail="The emitted nested Attack has no exact authored reaction attribution.",
    ),
    (
        "dnd/monsters/traits.py:604:25->613:20|MultiattackAction._apply|"
        "dnd.actions.Attack"
    ): CheckedDisposition(
        disposition=Disposition.BROKEN_FRAME_BLOCKING,
        expected_identity_key=None,
        detail="The emitted child Attack loses the selected configured Multiattack identity.",
    ),
    (
        "dnd/reactions.py:79:26->96:12|opportunity_attack_processor|"
        "dnd.actions.Attack"
    ): CheckedDisposition(
        disposition=Disposition.CONNECTED_EXPLICIT_BINDING,
        expected_identity_key="core.rules:reaction:reaction.opportunity_attack@1",
        detail="The processor explicitly copies the active reaction binding before apply.",
    ),
    (
        "dnd/spells/enchantment.py:1708:16->1708:16|"
        "CommandFleeEffect._activate_commanded_turn|dnd.actions.Move"
    ): CheckedDisposition(
        disposition=Disposition.BROKEN_SEMANTIC_OMISSION,
        expected_identity_key="content.srd_5_1_cc:spell:spell.command@1",
        detail="Movement still renders through its context-owned route, but the authored Command cause identity is omitted.",
    ),
    (
        "dnd/spells/evocation.py:3100:27->3107:12|Sunbeam._apply|"
        "dnd.spells.evocation.SunbeamStrike"
    ): CheckedDisposition(
        disposition=Disposition.BROKEN_SEMANTIC_OMISSION,
        expected_identity_key="content.srd_5_1_cc:action:action.spell.sunbeam.strike@1",
        detail="The initial follow-up action is directly applied without its action binding.",
    ),
    (
        "dnd/spells/evocation.py:3516:17->3525:24|TrueStrike._apply|"
        "dnd.actions.Attack"
    ): CheckedDisposition(
        disposition=Disposition.BROKEN_FRAME_BLOCKING,
        expected_identity_key="content.srd_5_1_cc:spell:spell.true_strike@1",
        detail="The nested Attack emits without the enclosing True Strike attribution.",
    ),
    (
        "dnd/spells/necromancy.py:1272:25->1272:25|"
        "EyebitePanickedEffect._create_flee_handler.processor|dnd.actions.Dash"
    ): CheckedDisposition(
        disposition=Disposition.BROKEN_SEMANTIC_OMISSION,
        expected_identity_key="content.srd_5_1_cc:spell:spell.eyebite@1",
        detail="Dash state survives, but the authored Eyebite cause identity is omitted.",
    ),
    (
        "dnd/spells/necromancy.py:1544:27->1553:12|Eyebite._apply|"
        "dnd.spells.necromancy.EyebiteStrike"
    ): CheckedDisposition(
        disposition=Disposition.BROKEN_SEMANTIC_OMISSION,
        expected_identity_key="content.srd_5_1_cc:action:action.spell.eyebite.strike@1",
        detail="The initial follow-up action is directly applied without its action binding.",
    ),
    (
        "dnd/spells/transmutation.py:1855:25->1862:12|Telekinesis._apply|"
        "dnd.spells.transmutation.TelekinesisGrab"
    ): CheckedDisposition(
        disposition=Disposition.BROKEN_SEMANTIC_OMISSION,
        expected_identity_key=(
            "content.srd_5_1_cc:action:action.spell.telekinesis.grab@1"
        ),
        detail="The initial follow-up action is directly applied without its action binding.",
    ),
}


def build_report(root: Path = REPOSITORY_ROOT) -> dict[str, object]:
    modules = _parse_modules(root)
    action_classes, unresolved_bases = discover_action_classes(modules)
    sites = discover_action_sites(modules, action_classes)
    discovered_keys = {site.key for site in sites}
    checked_keys = set(CHECKED_DISPOSITIONS)
    missing_dispositions = sorted(discovered_keys - checked_keys)
    stale_dispositions = sorted(checked_keys - discovered_keys)
    self_test_errors = list(_run_scanner_self_tests())

    site_rows: list[dict[str, object]] = []
    for site in sites:
        row: dict[str, object] = asdict(site)
        row["key"] = site.key
        checked = CHECKED_DISPOSITIONS.get(site.key)
        row["checked_disposition"] = (
            {
                **asdict(checked),
                "disposition": checked.disposition.value,
            }
            if checked is not None
            else None
        )
        site_rows.append(row)

    identity_validation_errors: list[str] = []
    try:
        from dnd.content_system.bootstrap import bootstrap_content_system

        registry_identity_keys = set(
            bootstrap_content_system().registry.declarations
        )
        for site_key, checked in CHECKED_DISPOSITIONS.items():
            expected = checked.expected_identity_key
            if expected is not None and expected not in registry_identity_keys:
                identity_validation_errors.append(
                    f"{site_key}->{expected}",
                )
    except Exception as exc:
        identity_validation_errors.append(
            f"content registry validation failed: {exc}",
        )
    exact = (
        not missing_dispositions
        and not stale_dispositions
        and not unresolved_bases
        and not identity_validation_errors
        and not self_test_errors
    )
    return {
        "schema_version": 1,
        "repository_root": str(root.resolve()),
        "base_action_class": BASE_ACTION_FQN,
        "module_count": len(modules),
        "action_class_count_including_base": len(action_classes),
        "action_class_descendant_count": len(action_classes - {BASE_ACTION_FQN}),
        "site_count": len(sites),
        "checked_disposition_count": len(CHECKED_DISPOSITIONS),
        "exact_set_match": exact,
        "missing_dispositions": missing_dispositions,
        "stale_dispositions": stale_dispositions,
        "unresolved_class_bases": list(unresolved_bases),
        "identity_validation_errors": identity_validation_errors,
        "self_test_errors": self_test_errors,
        "sites": site_rows,
    }


def _text_report(report: Mapping[str, object]) -> str:
    lines = [
        f"BaseAction descendants: {report['action_class_descendant_count']}",
        f"direct construct->apply sites: {report['site_count']}",
        f"checked dispositions: {report['checked_disposition_count']}",
        f"exact set match: {report['exact_set_match']}",
    ]
    for row in report["sites"]:
        assert isinstance(row, dict)
        checked = row["checked_disposition"]
        disposition = (
            checked["disposition"]
            if isinstance(checked, dict)
            else "MISSING_DISPOSITION"
        )
        lines.append(f"{disposition:38} {row['key']}")
    for label in ("missing_dispositions", "stale_dispositions"):
        values = report[label]
        assert isinstance(values, list)
        for value in values:
            lines.append(f"{label}: {value}")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=REPOSITORY_ROOT,
        help="Repository root containing dnd/ (default: this tool's parent).",
    )
    parser.add_argument(
        "--format",
        choices=("json", "text"),
        default="json",
        help="Output format (default: json).",
    )
    args = parser.parse_args(argv)

    report = build_report(args.root.resolve())
    if args.format == "text":
        print(_text_report(report))
    else:
        print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["exact_set_match"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
