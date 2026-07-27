"""Static dependency-boundary checks for production Python modules.

These checks intentionally parse source instead of importing it.  Architecture
violations must remain visible even when an import would fail, perform startup
work, or be hidden inside a function to avoid a runtime circular import.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PRODUCTION_ROOT_NAMES = ("dnd", "server", "ai")
SUPPLEMENTAL_SOURCE_ROOT_NAMES = ("tests", "devtools")
PROJECT_PACKAGE_NAMES = frozenset(PRODUCTION_ROOT_NAMES)

IGNORED_DIRECTORY_NAMES = frozenset({
    "__pycache__",
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "archive",
    "archived",
    "build",
    "dist",
    "generated",
    "test",
    "tests",
    "to_archive",
    "vendor",
    "vendors",
    "venv",
})

CONCRETE_ENTITY_DEPENDENCY_PREFIXES = (
    "dnd.actions",
    "dnd.actions_functional",
    "dnd.classes",
    "dnd.conditions",
    "dnd.extensions",
    "dnd.items",
    "dnd.monsters",
    "dnd.reactions",
    "dnd.scenarios",
    "dnd.spells",
    "dnd.tile_conditions",
)

SAFE_LEAF_MODULES = frozenset({
    "dnd.core.action_types",
    "dnd.core.condition_types",
    "dnd.core.effect_types",
    "dnd.core.equipment_types",
    "dnd.core.item_types",
    "dnd.core.life_types",
    "dnd.core.presentation_geometry",
})

CANONICAL_NEUTRAL_SYMBOL_OWNERS = {
    "ActionPresentationKind": "dnd.core.action_types",
    "ContentDefinitionKind": "dnd.core.content.identities",
    "ContentRef": "dnd.core.content.identities",
    "BehaviorBinding": "dnd.core.content.runtime",
    "RuntimeBehaviorKind": "dnd.core.content.runtime",
    "HandlerDispatchOutcome": "dnd.core.content.runtime",
    "HandlerDispatchEvidence": "dnd.core.content.runtime",
    "EffectiveHandlerPresentation": "dnd.core.content.runtime",
    "ConditionTag": "dnd.core.condition_types",
    "LifeState": "dnd.core.life_types",
    "WeaponSlot": "dnd.core.equipment_types",
    "BodyPart": "dnd.core.equipment_types",
    "RingSlot": "dnd.core.equipment_types",
    "EquipmentSlot": "dnd.core.equipment_types",
    "EffectOrigin": "dnd.core.effect_types",
    "ItemLocation": "dnd.core.item_types",
    "ItemPresentationState": "dnd.core.item_types",
    "APIItemSummary": "server.world_contracts",
    "APIEquipmentSlot": "server.world_contracts",
    "APIEquipmentOverview": "server.world_contracts",
    "APIAppearance": "server.world_contracts",
    "APIConditionSummary": "server.world_contracts",
    "APIEntitySummary": "server.world_contracts",
    "APIDirectionalBlockMap": "server.world_contracts",
    "APITile": "server.world_contracts",
    "APIGrid": "server.world_contracts",
    "APICombatant": "server.world_contracts",
    "APIEncounter": "server.world_contracts",
    "APIFloorObject": "server.world_contracts",
    "APIGameState": "server.world_contracts",
    "APIEntityVisibility": "server.world_contracts",
    "APIVisibilityResponse": "server.world_contracts",
}

CONTENT_CONTRACT_MODULE_PREFIX = "dnd.core.content"
CONTENT_CONTRACT_ALLOWED_NEUTRAL_DEPENDENCIES = frozenset({
    "dnd.core.condition_types",
    "dnd.core.equipment_types",
    "dnd.core.progression",
})
CONTENT_PACK_LOADER_MODULE = "dnd.content_system.pack_loader"
CONTENT_PACK_IMPORT_BOUNDARY_MODULE = "dnd.content_system.import_boundary"
CONTENT_PACK_IMPORT_FUNCTION = "import_content_pack_module"

WORLD_CONTRACT_ALLOWED_PROJECT_DEPENDENCIES = frozenset({
    "dnd.core.equipment_types",
    "dnd.core.life_types",
    "dnd.core.senses",
})

MECHANISM_MODULES = frozenset({
    "dnd.entity",
    "dnd.core.base_actions",
    "dnd.encounter",
})

CONCRETE_CONDITION_NAMES = frozenset({
    "Blinded",
    "Charmed",
    "Dead",
    "Deafened",
    "Disengaging",
    "Dodging",
    "Dying",
    "Exhaustion",
    "Frightened",
    "Grappled",
    "Hidden",
    "Incapacitated",
    "Invisible",
    "Paralyzed",
    "Petrified",
    "Poisoned",
    "Prone",
    "Restrained",
    "Stunned",
    "Unconscious",
})


@dataclass(frozen=True)
class SourceModule:
    """One parsed production module."""

    name: str
    path: Path
    is_package: bool
    tree: ast.Module

    @property
    def display_path(self) -> str:
        """Return a stable repository-relative path for failure messages."""
        return self.path.relative_to(REPOSITORY_ROOT).as_posix()


@dataclass(frozen=True)
class ImportReference:
    """One statically resolved import edge."""

    importer: str
    path: Path
    line: int
    target: str
    syntax: str
    function_local: bool = False
    dynamic: bool = False

    @property
    def location(self) -> str:
        """Return a stable source location."""
        relative_path = self.path.relative_to(REPOSITORY_ROOT).as_posix()
        return f"{relative_path}:{self.line}"


@dataclass(frozen=True)
class DynamicImportViolation:
    """A dynamic import that targets, or may target, project code."""

    path: Path
    line: int
    detail: str

    @property
    def location(self) -> str:
        """Return a stable source location."""
        relative_path = self.path.relative_to(REPOSITORY_ROOT).as_posix()
        return f"{relative_path}:{self.line}"


def _is_ignored_python_path(path: Path) -> bool:
    """Return whether a Python path is test, archive, generated, or vendor code."""
    relative_path = path.relative_to(REPOSITORY_ROOT)
    directory_names = {part.casefold() for part in relative_path.parts[:-1]}
    if directory_names & IGNORED_DIRECTORY_NAMES:
        return True
    lowered_name = path.name.casefold()
    return (
        ".generated." in lowered_name
        or lowered_name.endswith("_generated.py")
        or lowered_name.startswith("generated_")
    )


def _module_name_for_path(path: Path) -> tuple[str, bool]:
    """Return the importable module name and package status for a source path."""
    relative_path = path.relative_to(REPOSITORY_ROOT).with_suffix("")
    parts = list(relative_path.parts)
    is_package = parts[-1] == "__init__"
    if is_package:
        parts.pop()
    return ".".join(parts), is_package


@lru_cache(maxsize=1)
def _source_modules() -> dict[str, SourceModule]:
    """Parse every in-scope production module exactly once."""
    modules: dict[str, SourceModule] = {}
    for root_name in PRODUCTION_ROOT_NAMES:
        source_root = REPOSITORY_ROOT / root_name
        for path in sorted(source_root.rglob("*.py")):
            if _is_ignored_python_path(path):
                continue
            module_name, is_package = _module_name_for_path(path)
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
            modules[module_name] = SourceModule(
                name=module_name,
                path=path,
                is_package=is_package,
                tree=tree,
            )
    return modules


def _supplemental_candidate_modules(pattern: str) -> tuple[SourceModule, ...]:
    """Find tests/devtools candidates quickly, then parse only matching files."""
    roots = [
        str(REPOSITORY_ROOT / root_name)
        for root_name in SUPPLEMENTAL_SOURCE_ROOT_NAMES
        if (REPOSITORY_ROOT / root_name).exists()
    ]
    if not roots:
        return ()
    result = subprocess.run(
        [
            "rg",
            "-l",
            "--glob",
            "*.py",
            "--glob",
            "!**/archive/**",
            "--glob",
            "!**/archived/**",
            "--glob",
            "!**/to_archive/**",
            pattern,
            *roots,
        ],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode not in {0, 1}:
        raise AssertionError(f"rg source-policy scan failed: {result.stderr.strip()}")
    modules: list[SourceModule] = []
    for raw_path in sorted(filter(None, result.stdout.splitlines())):
        path = Path(raw_path)
        module_name, is_package = _module_name_for_path(path)
        modules.append(SourceModule(
            name=module_name,
            path=path,
            is_package=is_package,
            tree=ast.parse(path.read_text(encoding="utf-8"), filename=str(path)),
        ))
    return tuple(modules)


def _module_package_parts(source_module: SourceModule) -> list[str]:
    """Return the package parts used to resolve relative imports."""
    parts = source_module.name.split(".")
    return parts if source_module.is_package else parts[:-1]


def _resolve_import_from_base(
    source_module: SourceModule,
    node: ast.ImportFrom,
) -> str:
    """Resolve an ``ImportFrom`` base, including arbitrary relative levels."""
    if node.level == 0:
        return node.module or ""

    package_parts = _module_package_parts(source_module)
    parent_hops = node.level - 1
    if parent_hops > len(package_parts):
        return ""
    if parent_hops:
        package_parts = package_parts[:-parent_hops]
    if node.module:
        package_parts.extend(node.module.split("."))
    return ".".join(package_parts)


def _project_root_name(module_name: str) -> str:
    """Return the first component of a possibly empty module name."""
    return module_name.partition(".")[0]


def _is_project_module_name(module_name: str) -> bool:
    """Return whether a module name belongs to a production project package."""
    return _project_root_name(module_name) in PROJECT_PACKAGE_NAMES


class _ImportCollector(ast.NodeVisitor):
    """Collect static imports while retaining lexical function scope."""

    def __init__(self, source_module: SourceModule, known_modules: frozenset[str]) -> None:
        self.source_module = source_module
        self.known_modules = known_modules
        self.function_depth = 0
        self.references: list[ImportReference] = []

    def _visit_function(self, node: ast.AST) -> None:
        """Visit one function-like scope."""
        self.function_depth += 1
        self.generic_visit(node)
        self.function_depth -= 1

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        self._visit_function(node)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.references.append(ImportReference(
                importer=self.source_module.name,
                path=self.source_module.path,
                line=node.lineno,
                target=alias.name,
                syntax=f"import {alias.name}",
                function_local=self.function_depth > 0,
            ))

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        base_module = _resolve_import_from_base(self.source_module, node)
        for alias in node.names:
            candidate = f"{base_module}.{alias.name}" if base_module else alias.name
            target = candidate if candidate in self.known_modules else base_module
            if not target:
                target = candidate
            dots = "." * node.level
            imported_from = f"{dots}{node.module or ''}"
            self.references.append(ImportReference(
                importer=self.source_module.name,
                path=self.source_module.path,
                line=node.lineno,
                target=target,
                syntax=f"from {imported_from} import {alias.name}",
                function_local=self.function_depth > 0,
            ))


def _dynamic_import_aliases(tree: ast.Module) -> tuple[set[str], set[str], set[str]]:
    """Return aliases for importlib, import_module, and builtins."""
    importlib_aliases = {"importlib"}
    import_module_aliases: set[str] = set()
    builtins_aliases = {"builtins"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "importlib":
                    importlib_aliases.add(alias.asname or alias.name)
                elif alias.name == "builtins":
                    builtins_aliases.add(alias.asname or alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module == "importlib":
            for alias in node.names:
                if alias.name == "import_module":
                    import_module_aliases.add(alias.asname or alias.name)
    return importlib_aliases, import_module_aliases, builtins_aliases


def _dynamic_import_kind(
    function: ast.expr,
    importlib_aliases: set[str],
    import_module_aliases: set[str],
    builtins_aliases: set[str],
) -> str | None:
    """Classify supported dynamic-import call forms."""
    if isinstance(function, ast.Name):
        if function.id == "__import__":
            return "__import__"
        if function.id in import_module_aliases:
            return "importlib.import_module"
        return None
    if not isinstance(function, ast.Attribute) or not isinstance(function.value, ast.Name):
        return None
    if function.attr == "import_module" and function.value.id in importlib_aliases:
        return "importlib.import_module"
    if function.attr == "__import__" and function.value.id in builtins_aliases:
        return "__import__"
    return None


def _resolve_dynamic_name(source_module: SourceModule, requested_name: str) -> str:
    """Resolve a literal dynamic module name when it is relative."""
    if not requested_name.startswith("."):
        return requested_name
    relative_level = len(requested_name) - len(requested_name.lstrip("."))
    relative_module = requested_name[relative_level:] or None
    synthetic_node = ast.ImportFrom(
        module=relative_module,
        names=[ast.alias(name="__dynamic__")],
        level=relative_level,
    )
    return _resolve_import_from_base(source_module, synthetic_node)


def _dynamic_import_findings(
    source_module: SourceModule,
) -> tuple[list[ImportReference], list[DynamicImportViolation]]:
    """Collect literal project edges and unverifiable dynamic import calls."""
    importlib_aliases, import_module_aliases, builtins_aliases = _dynamic_import_aliases(
        source_module.tree
    )
    references: list[ImportReference] = []
    violations: list[DynamicImportViolation] = []
    for node in ast.walk(source_module.tree):
        if not isinstance(node, ast.Call):
            continue
        kind = _dynamic_import_kind(
            node.func,
            importlib_aliases,
            import_module_aliases,
            builtins_aliases,
        )
        if kind is None:
            continue
        if not node.args or not isinstance(node.args[0], ast.Constant) or not isinstance(node.args[0].value, str):
            violations.append(DynamicImportViolation(
                path=source_module.path,
                line=node.lineno,
                detail=f"{kind} target is not a string literal and cannot be proven external",
            ))
            continue
        requested_name = node.args[0].value
        resolved_name = _resolve_dynamic_name(source_module, requested_name)
        if requested_name.startswith(".") or _is_project_module_name(resolved_name):
            references.append(ImportReference(
                importer=source_module.name,
                path=source_module.path,
                line=node.lineno,
                target=resolved_name,
                syntax=f'{kind}("{requested_name}")',
                dynamic=True,
            ))
            violations.append(DynamicImportViolation(
                path=source_module.path,
                line=node.lineno,
                detail=f"dynamic project import {kind}(\"{requested_name}\")",
            ))
    return references, violations


@lru_cache(maxsize=1)
def _import_references() -> tuple[ImportReference, ...]:
    """Return all static and literal-dynamic import edges."""
    modules = _source_modules()
    known_modules = frozenset(modules)
    references: list[ImportReference] = []
    for source_module in modules.values():
        collector = _ImportCollector(source_module, known_modules)
        collector.visit(source_module.tree)
        references.extend(collector.references)
        dynamic_references, _ = _dynamic_import_findings(source_module)
        references.extend(dynamic_references)
    return tuple(references)


@lru_cache(maxsize=1)
def _dynamic_import_violations() -> tuple[DynamicImportViolation, ...]:
    """Return all dynamic project or unverifiable import calls."""
    violations: list[DynamicImportViolation] = []
    for source_module in _source_modules().values():
        _, module_violations = _dynamic_import_findings(source_module)
        violations.extend(module_violations)
    return tuple(violations)


def _typing_checking_locations(source_module: SourceModule) -> list[tuple[int, str]]:
    """Find imports and references used to hide dependencies behind TYPE_CHECKING."""
    typing_aliases = {"typing", "typing_extensions"}
    imported_names: set[str] = set()
    locations: set[tuple[int, str]] = set()
    for node in ast.walk(source_module.tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in {"typing", "typing_extensions"}:
                    typing_aliases.add(alias.asname or alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module in {"typing", "typing_extensions"}:
            for alias in node.names:
                if alias.name == "TYPE_CHECKING":
                    imported_name = alias.asname or alias.name
                    imported_names.add(imported_name)
                    locations.add((node.lineno, f"imports {node.module}.TYPE_CHECKING"))

    for node in ast.walk(source_module.tree):
        if isinstance(node, ast.Attribute) and node.attr == "TYPE_CHECKING":
            if isinstance(node.value, ast.Name) and node.value.id in typing_aliases:
                locations.add((node.lineno, "references typing.TYPE_CHECKING"))
        elif isinstance(node, ast.Name) and node.id in imported_names:
            locations.add((node.lineno, f"references {node.id}"))
    return sorted(locations)


def _known_project_target(target: str, known_modules: frozenset[str]) -> str | None:
    """Return an exact discovered project target, excluding ignored source trees."""
    return target if target in known_modules else None


def _strongly_connected_components(
    graph: dict[str, set[str]],
) -> list[tuple[str, ...]]:
    """Return cyclic components using Tarjan's algorithm."""
    index = 0
    stack: list[str] = []
    on_stack: set[str] = set()
    indices: dict[str, int] = {}
    low_links: dict[str, int] = {}
    cyclic_components: list[tuple[str, ...]] = []

    def visit(node: str) -> None:
        nonlocal index
        indices[node] = index
        low_links[node] = index
        index += 1
        stack.append(node)
        on_stack.add(node)

        for target in sorted(graph[node]):
            if target not in indices:
                visit(target)
                low_links[node] = min(low_links[node], low_links[target])
            elif target in on_stack:
                low_links[node] = min(low_links[node], indices[target])

        if low_links[node] != indices[node]:
            return
        component: list[str] = []
        while True:
            member = stack.pop()
            on_stack.remove(member)
            component.append(member)
            if member == node:
                break
        if len(component) > 1 or node in graph[node]:
            cyclic_components.append(tuple(sorted(component)))

    for node in sorted(graph):
        if node not in indices:
            visit(node)
    return sorted(cyclic_components)


def _top_level_symbol_definitions(source_module: SourceModule) -> set[str]:
    """Return names defined directly by a module, excluding imported aliases."""
    definitions: set[str] = set()
    for node in source_module.tree.body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            definitions.add(node.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets: Iterable[ast.expr]
            if isinstance(node, ast.Assign):
                targets = node.targets
            else:
                targets = (node.target,)
            for target in targets:
                if isinstance(target, ast.Name):
                    definitions.add(target.id)
                elif isinstance(target, (ast.Tuple, ast.List)):
                    definitions.update(
                        element.id
                        for element in target.elts
                        if isinstance(element, ast.Name)
                    )
    return definitions


def _expression_mentions_active_conditions(node: ast.AST) -> bool:
    """Return whether an expression reads an active-condition index."""
    for child in ast.walk(node):
        if isinstance(child, ast.Name) and child.id == "active_conditions":
            return True
        if isinstance(child, ast.Attribute) and child.attr in {
            "active_conditions",
            "active_conditions_by_uuid",
            "active_conditions_by_source",
        }:
            return True
    return False


def _constant_condition_name(node: ast.AST) -> str | None:
    """Return a forbidden concrete condition name from a literal expression."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        if node.value in CONCRETE_CONDITION_NAMES:
            return node.value
    return None


def _mechanical_condition_name_uses(source_module: SourceModule) -> list[tuple[int, str]]:
    """Find concrete condition names used to drive mechanism behavior."""
    findings: set[tuple[int, str]] = set()
    for node in ast.walk(source_module.tree):
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and node.value in CONCRETE_CONDITION_NAMES
        ):
            findings.add((node.lineno, f"concrete condition literal {node.value!r}"))
        if isinstance(node, ast.Compare) and _expression_mentions_active_conditions(node):
            expressions = (node.left, *node.comparators)
            for expression in expressions:
                condition_name = _constant_condition_name(expression)
                if condition_name is not None:
                    findings.add((node.lineno, f"membership check for {condition_name!r}"))
        elif isinstance(node, ast.Subscript) and _expression_mentions_active_conditions(node.value):
            condition_name = _constant_condition_name(node.slice)
            if condition_name is not None:
                findings.add((node.lineno, f"condition index lookup for {condition_name!r}"))
        elif isinstance(node, ast.Call):
            method_name = node.func.attr if isinstance(node.func, ast.Attribute) else None
            if method_name not in {
                "add_condition_immunity",
                "advance_duration_condition",
                "check_condition_immunity",
                "get",
                "pop",
                "reduce_condition_level",
                "remove_condition",
            }:
                continue
            if not node.args:
                continue
            condition_name = _constant_condition_name(node.args[0])
            if condition_name is None:
                continue
            if method_name in {"get", "pop"} and not _expression_mentions_active_conditions(node.func):
                continue
            findings.add((node.lineno, f"{method_name} uses {condition_name!r}"))
    return sorted(findings)


def _life_state_assignments(source_module: SourceModule) -> list[int]:
    """Return direct assignments to an entity health life-state field."""
    findings: list[int] = []
    for node in ast.walk(source_module.tree):
        targets: Iterable[ast.expr]
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign):
            targets = (node.target,)
        elif isinstance(node, ast.AugAssign):
            targets = (node.target,)
        else:
            continue
        for target in targets:
            if not isinstance(target, ast.Attribute) or target.attr != "life_state":
                continue
            owner = target.value
            if isinstance(owner, ast.Attribute) and owner.attr == "health":
                findings.append(node.lineno)
    return findings


def _format_import_references(references: Iterable[ImportReference]) -> str:
    """Format import findings consistently."""
    return "\n".join(
        f"- {reference.location}: {reference.syntax} -> {reference.target}"
        for reference in sorted(
            references,
            key=lambda item: (item.location, item.target, item.syntax),
        )
    )


def test_production_has_no_function_local_or_dynamic_project_imports() -> None:
    """Imports may not be hidden inside functions or dynamic loader calls."""
    local_imports = [
        reference
        for reference in _import_references()
        if reference.function_local and not reference.dynamic
    ]
    boundary = _source_modules().get(CONTENT_PACK_IMPORT_BOUNDARY_MODULE)
    approved_dynamic_finding = (
        (
            boundary.path,
            next(
                node.lineno
                for node in ast.walk(boundary.tree)
                if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "importlib"
                and node.func.attr == "import_module"
            ),
            "importlib.import_module target is not a string literal and "
            "cannot be proven external",
        )
        if boundary is not None
        else None
    )
    dynamic_violations = [
        violation
        for violation in _dynamic_import_violations()
        if (
            violation.path,
            violation.line,
            violation.detail,
        ) != approved_dynamic_finding
    ]
    messages: list[str] = []
    if local_imports:
        messages.append(
            "Function-local imports are forbidden:\n"
            + _format_import_references(local_imports)
        )
    if dynamic_violations:
        messages.append(
            "Dynamic imports of project code, or unverifiable dynamic imports, are forbidden:\n"
            + "\n".join(
                f"- {violation.location}: {violation.detail}"
                for violation in sorted(
                    dynamic_violations,
                    key=lambda item: (item.location, item.detail),
                )
            )
        )
    assert not messages, "\n\n".join(messages)


def test_content_pack_import_boundary_is_one_exact_function_and_caller() -> None:
    """One tiny audited function is the sole dynamic import primitive."""
    modules = _source_modules()
    assert CONTENT_PACK_IMPORT_BOUNDARY_MODULE in modules
    boundary = modules[CONTENT_PACK_IMPORT_BOUNDARY_MODULE]
    loader = modules[CONTENT_PACK_LOADER_MODULE]

    non_docstring_body = [
        node
        for node in boundary.tree.body
        if not (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        )
    ]
    assert len(non_docstring_body) == 4
    assert (
        isinstance(non_docstring_body[0], ast.ImportFrom)
        and non_docstring_body[0].module == "__future__"
        and [alias.name for alias in non_docstring_body[0].names]
        == ["annotations"]
    )
    assert (
        isinstance(non_docstring_body[1], ast.Import)
        and [alias.name for alias in non_docstring_body[1].names]
        == ["importlib"]
    )
    assert (
        isinstance(non_docstring_body[2], ast.ImportFrom)
        and non_docstring_body[2].module == "types"
        and [alias.name for alias in non_docstring_body[2].names]
        == ["ModuleType"]
    )
    function = non_docstring_body[3]
    assert isinstance(function, ast.FunctionDef)
    assert function.name == CONTENT_PACK_IMPORT_FUNCTION
    assert [argument.arg for argument in function.args.args] == ["module_name"]
    assert function.args.posonlyargs == []
    assert function.args.kwonlyargs == []
    assert function.args.vararg is None
    assert function.args.kwarg is None
    assert len(function.body) == 1
    returned = function.body[0]
    assert isinstance(returned, ast.Return)
    assert isinstance(returned.value, ast.Call)
    assert (
        isinstance(returned.value.func, ast.Attribute)
        and isinstance(returned.value.func.value, ast.Name)
        and returned.value.func.value.id == "importlib"
        and returned.value.func.attr == "import_module"
    )
    assert (
        len(returned.value.args) == 1
        and isinstance(returned.value.args[0], ast.Name)
        and returned.value.args[0].id == "module_name"
        and returned.value.keywords == []
    )

    boundary_imports = [
        (source_module.name, node)
        for source_module in modules.values()
        for node in source_module.tree.body
        if isinstance(node, ast.ImportFrom)
        and node.module == CONTENT_PACK_IMPORT_BOUNDARY_MODULE
    ]
    assert len(boundary_imports) == 1
    importer_name, boundary_import = boundary_imports[0]
    assert importer_name == CONTENT_PACK_LOADER_MODULE
    assert [
        (alias.name, alias.asname)
        for alias in boundary_import.names
    ] == [(CONTENT_PACK_IMPORT_FUNCTION, None)]

    callers = [
        (source_module.name, node)
        for source_module in modules.values()
        for node in ast.walk(source_module.tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == CONTENT_PACK_IMPORT_FUNCTION
    ]
    assert len(callers) == 1
    assert callers[0][0] == CONTENT_PACK_LOADER_MODULE

    loader_importlib_imports = [
        node
        for node in loader.tree.body
        if (
            isinstance(node, ast.Import)
            and any(alias.name == "importlib" for alias in node.names)
        )
        or (
            isinstance(node, ast.ImportFrom)
            and node.module == "importlib"
            and any(alias.name == "import_module" for alias in node.names)
        )
    ]
    assert loader_importlib_imports == []

    references, violations = _dynamic_import_findings(boundary)
    assert references == []
    assert len(violations) == 1
    assert violations[0].line == returned.lineno
    assert violations[0].detail == (
        "importlib.import_module target is not a string literal and cannot be "
        "proven external"
    )

    assert list(_dynamic_import_violations()) == violations


def test_active_python_has_no_function_local_imports() -> None:
    """No active source or test module may hide imports inside a function."""
    modules = _supplemental_candidate_modules(
        r"(^\s+(from|import)\s+|:\s*(from|import)\s+)"
    )
    known_modules = frozenset(module.name for module in modules)
    local_imports: list[ImportReference] = []
    for source_module in modules:
        collector = _ImportCollector(source_module, known_modules)
        collector.visit(source_module.tree)
        local_imports.extend(
            reference
            for reference in collector.references
            if reference.function_local
        )
    assert not local_imports, (
        "Function-local imports are forbidden across active Python:\n"
        + _format_import_references(local_imports)
    )


def test_production_has_no_type_checking_import_workarounds() -> None:
    """TYPE_CHECKING must not be used to conceal an invalid runtime edge."""
    findings: list[str] = []
    for source_module in _source_modules().values():
        for line, detail in _typing_checking_locations(source_module):
            findings.append(f"- {source_module.display_path}:{line}: {detail}")
    assert not findings, "TYPE_CHECKING workarounds are forbidden:\n" + "\n".join(findings)


def test_active_python_has_no_type_checking_import_workarounds() -> None:
    """Tests and devtools must not normalize TYPE_CHECKING cycle workarounds."""
    findings: list[str] = []
    for source_module in _supplemental_candidate_modules("TYPE_CHECKING"):
        for line, detail in _typing_checking_locations(source_module):
            findings.append(f"- {source_module.display_path}:{line}: {detail}")
    assert not findings, "TYPE_CHECKING workarounds are forbidden:\n" + "\n".join(findings)


def test_internal_import_graph_has_no_cycles() -> None:
    """The complete static project graph, including local imports, must be acyclic."""
    known_modules = frozenset(_source_modules())
    graph = {module_name: set() for module_name in known_modules}
    for reference in _import_references():
        target = _known_project_target(reference.target, known_modules)
        if target is not None:
            graph[reference.importer].add(target)

    components = _strongly_connected_components(graph)
    component_messages: list[str] = []
    for component in components:
        component_set = set(component)
        internal_edges = sorted(
            (
                reference
                for reference in _import_references()
                if reference.importer in component_set
                and _known_project_target(reference.target, known_modules) in component_set
            ),
            key=lambda item: (item.importer, item.target, item.location, item.syntax),
        )
        edge_text = "; ".join(
            f"{edge.importer} -> {_known_project_target(edge.target, known_modules)} "
            f"({edge.location})"
            for edge in internal_edges
        )
        component_messages.append(f"- {', '.join(component)}: {edge_text}")
    assert not component_messages, (
        "Circular project imports are forbidden, including cycles hidden by local imports:\n"
        + "\n".join(component_messages)
    )


def test_dependency_direction_is_respected() -> None:
    """Project packages and Entity may only depend in the approved direction."""
    violations: list[ImportReference] = []
    for reference in _import_references():
        importer_root = _project_root_name(reference.importer)
        target_root = _project_root_name(reference.target)
        if importer_root == "dnd" and target_root in {"server", "ai"}:
            violations.append(reference)
            continue
        if importer_root == "server" and target_root == "ai":
            violations.append(reference)
            continue
        if reference.importer == "dnd.entity" and any(
            reference.target == prefix or reference.target.startswith(f"{prefix}.")
            for prefix in CONCRETE_ENTITY_DEPENDENCY_PREFIXES
        ):
            violations.append(reference)
    assert not violations, (
        "Dependency direction violations:\n" + _format_import_references(violations)
    )


def test_event_server_import_does_not_load_client_facing_ai_package() -> None:
    """Importing the server in a fresh process must not import any ``ai`` module."""
    marker = "__DND_ARCH_AI_MODULES__="
    script = (
        "import json, sys\n"
        "import server.event_server\n"
        "loaded = sorted(name for name in sys.modules "
        "if name == 'ai' or name.startswith('ai.'))\n"
        f"print({marker!r} + json.dumps(loaded))\n"
    )
    try:
        completed = subprocess.run(
            [sys.executable, "-c", script],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise AssertionError(
            "Fresh import of server.event_server exceeded the 30-second isolation timeout"
        ) from error

    assert completed.returncode == 0, (
        "Fresh import of server.event_server failed before isolation could be checked:\n"
        f"stdout:\n{completed.stdout}\n"
        f"stderr:\n{completed.stderr}"
    )
    marker_lines = [
        line for line in completed.stdout.splitlines() if line.startswith(marker)
    ]
    assert len(marker_lines) == 1, (
        "Fresh import did not emit exactly one AI isolation result:\n"
        f"stdout:\n{completed.stdout}\n"
        f"stderr:\n{completed.stderr}"
    )
    loaded_ai_modules = json.loads(marker_lines[0][len(marker):])
    assert loaded_ai_modules == [], (
        "Importing server.event_server loaded client-facing ai modules:\n- "
        + "\n- ".join(loaded_ai_modules)
    )


def test_neutral_symbols_have_one_canonical_leaf_owner() -> None:
    """Neutral enums and transport DTOs must be defined only in their leaf module."""
    definitions_by_symbol: dict[str, list[str]] = {
        symbol: [] for symbol in CANONICAL_NEUTRAL_SYMBOL_OWNERS
    }
    for source_module in _source_modules().values():
        definitions = _top_level_symbol_definitions(source_module)
        for symbol in definitions_by_symbol:
            if symbol in definitions:
                definitions_by_symbol[symbol].append(source_module.name)

    violations: list[str] = []
    for symbol, expected_owner in CANONICAL_NEUTRAL_SYMBOL_OWNERS.items():
        actual_owners = sorted(definitions_by_symbol[symbol])
        if actual_owners != [expected_owner]:
            actual = ", ".join(actual_owners) if actual_owners else "missing"
            violations.append(
                f"- {symbol}: expected {expected_owner}; found {actual}"
            )
    assert not violations, (
        "Neutral symbols must have exactly one canonical leaf owner:\n"
        + "\n".join(violations)
    )


def test_world_contract_dtos_are_not_reexported_through_api_models() -> None:
    """World DTOs have one import surface instead of an api_models compatibility alias."""
    api_models = _source_modules()["server.api_models"]
    forbidden_symbols = {
        symbol
        for symbol, owner in CANONICAL_NEUTRAL_SYMBOL_OWNERS.items()
        if owner == "server.world_contracts"
    }
    reexports = sorted({
        alias.asname or alias.name
        for node in api_models.tree.body
        if isinstance(node, ast.ImportFrom)
        and node.module == "server.world_contracts"
        for alias in node.names
        if alias.name in forbidden_symbols
    })
    assert reexports == [], (
        "Import world DTOs from server.world_contracts, never server.api_models: "
        + ", ".join(reexports)
    )


def test_safe_leaf_modules_have_no_project_dependencies() -> None:
    """Canonical leaf types must remain importable without another project layer."""
    modules = _source_modules()
    missing = sorted(SAFE_LEAF_MODULES - modules.keys())
    forbidden_imports = [
        reference
        for reference in _import_references()
        if reference.importer in SAFE_LEAF_MODULES
        and _is_project_module_name(reference.target)
    ]
    messages: list[str] = []
    if missing:
        messages.append("Missing canonical safe leaf modules: " + ", ".join(missing))
    if forbidden_imports:
        messages.append(
            "Safe leaf modules import project code:\n"
            + _format_import_references(forbidden_imports)
        )
    assert not messages, "\n\n".join(messages)


def test_content_contract_package_has_one_exact_import_surface_and_direction() -> None:
    """Content contracts are a package of neutral leaves, never a broad alias."""
    old_module_path = REPOSITORY_ROOT / "dnd" / "core" / "content.py"
    assert not old_module_path.exists(), (
        "dnd/core/content.py must not coexist with the canonical content package"
    )

    root_imports = [
        reference
        for reference in _import_references()
        if reference.target == CONTENT_CONTRACT_MODULE_PREFIX
    ]
    assert not root_imports, (
        "Import exact dnd.core.content submodules; the package root is not an API:\n"
        + _format_import_references(root_imports)
    )

    forbidden_edges = [
        reference
        for reference in _import_references()
        if (
            reference.importer == CONTENT_CONTRACT_MODULE_PREFIX
            or reference.importer.startswith(f"{CONTENT_CONTRACT_MODULE_PREFIX}.")
        )
        and _is_project_module_name(reference.target)
        and not (
            reference.target == CONTENT_CONTRACT_MODULE_PREFIX
            or reference.target.startswith(f"{CONTENT_CONTRACT_MODULE_PREFIX}.")
            or reference.target
            in CONTENT_CONTRACT_ALLOWED_NEUTRAL_DEPENDENCIES
        )
    ]
    assert not forbidden_edges, (
        "Content contracts may depend only on sibling content-contract leaves "
        "and explicitly enumerated dependency-neutral primitives:\n"
        + _format_import_references(forbidden_edges)
    )


def test_retired_content_kind_has_no_definition_or_use() -> None:
    """Definition and runtime behavior kinds must never collapse into one enum."""
    findings: list[str] = []
    for source_module in _source_modules().values():
        if "ContentKind" in _top_level_symbol_definitions(source_module):
            findings.append(f"- {source_module.display_path}: defines ContentKind")
        for node in ast.walk(source_module.tree):
            if isinstance(node, ast.Name) and node.id == "ContentKind":
                findings.append(
                    f"- {source_module.display_path}:{node.lineno}: uses ContentKind"
                )
    assert not findings, (
        "ContentKind is retired; use ContentDefinitionKind or "
        "RuntimeBehaviorKind explicitly:\n" + "\n".join(sorted(set(findings)))
    )


def test_cold_content_contract_imports_do_not_load_gameplay_or_server_layers() -> None:
    """Importing identity/runtime leaves cannot trigger concrete engine startup."""
    marker = "__DND_CONTENT_COLD_IMPORTS__="
    script = (
        "import json, sys\n"
        "import dnd.core.content.identities\n"
        "import dnd.core.content.runtime\n"
        "forbidden = ('ai', 'server', 'dnd.entity', 'dnd.items', "
        "'dnd.monsters', 'dnd.actions', 'dnd.conditions', 'dnd.spells')\n"
        "loaded = sorted(name for name in sys.modules if any("
        "name == prefix or name.startswith(prefix + '.') for prefix in forbidden))\n"
        f"print({marker!r} + json.dumps(loaded))\n"
    )
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, (
        "Fresh content-contract import failed:\n"
        f"stdout:\n{completed.stdout}\n"
        f"stderr:\n{completed.stderr}"
    )
    marker_lines = [
        line for line in completed.stdout.splitlines() if line.startswith(marker)
    ]
    assert len(marker_lines) == 1
    loaded = json.loads(marker_lines[0][len(marker):])
    assert loaded == [], (
        "Cold content contracts loaded gameplay/server layers:\n- "
        + "\n- ".join(loaded)
    )


def test_world_contracts_are_a_cold_transport_leaf() -> None:
    """World DTOs may depend only on dependency-neutral engine value types."""
    source_module = _source_modules()["server.world_contracts"]
    forbidden_imports = [
        reference
        for reference in _import_references()
        if reference.importer == source_module.name
        and _is_project_module_name(reference.target)
        and reference.target not in WORLD_CONTRACT_ALLOWED_PROJECT_DEPENDENCIES
    ]
    mapper_methods = [
        f"{node.name}.{child.name} at {source_module.display_path}:{child.lineno}"
        for node in source_module.tree.body
        if isinstance(node, ast.ClassDef)
        for child in node.body
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
        and child.name in {"create", "from_entity", "from_grid", "from_item"}
    ]
    messages: list[str] = []
    if forbidden_imports:
        messages.append(
            "World contracts import runtime project code:\n"
            + _format_import_references(forbidden_imports)
        )
    if mapper_methods:
        messages.append(
            "World contracts own engine projection methods:\n- "
            + "\n- ".join(mapper_methods)
        )
    assert not messages, "\n\n".join(messages)


def test_persistent_spell_zones_receive_explicit_effect_provenance() -> None:
    """Every concrete ZoneControlCondition creation carries EffectOrigin."""
    zone_class_names: set[str] = set()
    for source_module in _source_modules().values():
        if not source_module.name.startswith("dnd."):
            continue
        for node in ast.walk(source_module.tree):
            if not isinstance(node, ast.ClassDef):
                continue
            if any(
                (isinstance(base, ast.Name) and base.id == "ZoneControlCondition")
                or (
                    isinstance(base, ast.Attribute)
                    and base.attr == "ZoneControlCondition"
                )
                for base in node.bases
            ):
                zone_class_names.add(node.name)

    missing_provenance: list[str] = []
    for source_module in _source_modules().values():
        if not source_module.name.startswith("dnd."):
            continue
        for node in ast.walk(source_module.tree):
            if not isinstance(node, ast.Call):
                continue
            called_name: str | None = None
            if isinstance(node.func, ast.Name):
                called_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                called_name = node.func.attr
            if called_name not in zone_class_names:
                continue
            if "effect_origin" not in {keyword.arg for keyword in node.keywords}:
                missing_provenance.append(
                    f"- {source_module.display_path}:{node.lineno}: {called_name}"
                )

    assert zone_class_names, "No concrete ZoneControlCondition subclasses were found"
    assert not missing_provenance, (
        "Persistent spell zones must receive explicit EffectOrigin provenance:\n"
        + "\n".join(sorted(missing_provenance))
    )


def test_mechanisms_do_not_interpret_concrete_condition_names() -> None:
    """Entity and mechanisms consume neutral transformed state, not rule names."""
    findings: list[str] = []
    modules = _source_modules()
    for module_name in sorted(MECHANISM_MODULES):
        source_module = modules[module_name]
        for line, detail in _mechanical_condition_name_uses(source_module):
            findings.append(f"- {source_module.display_path}:{line}: {detail}")
    assert not findings, (
        "Mechanism modules may not branch on concrete condition names:\n"
        + "\n".join(findings)
    )


def test_life_state_has_one_authoritative_writer_and_no_condition_mirror() -> None:
    """LifeState is committed by Entity and is never mirrored as a condition."""
    assignments: list[str] = []
    for source_module in _source_modules().values():
        for line in _life_state_assignments(source_module):
            assignments.append(f"{source_module.name}:{line}")

    assert len(assignments) == 1 and assignments[0].startswith("dnd.entity:"), (
        "Entity must remain the sole authoritative health.life_state writer:\n- "
        + "\n- ".join(assignments)
    )

    condition_definitions = _top_level_symbol_definitions(
        _source_modules()["dnd.conditions"]
    )
    forbidden = {
        "Dying",
        "Dead",
        "life_state_change_processor",
        "create_life_state_change_handler",
    } & condition_definitions
    assert not forbidden, (
        "Life-state conditions/handlers would create a second authority: "
        + ", ".join(sorted(forbidden))
    )


def test_floor_items_use_the_canonical_placement_boundary() -> None:
    """Production code must not bypass BaseItem.place_on_grid."""

    class RawPlacementCollector(ast.NodeVisitor):
        """Collect direct GridMap.place_object calls with lexical ownership."""

        def __init__(self) -> None:
            self.class_names: list[str] = []
            self.function_names: list[str] = []
            self.calls: list[tuple[str | None, str | None, int]] = []

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            self.class_names.append(node.name)
            self.generic_visit(node)
            self.class_names.pop()

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            self.function_names.append(node.name)
            self.generic_visit(node)
            self.function_names.pop()

        def visit_AsyncFunctionDef(
            self,
            node: ast.AsyncFunctionDef,
        ) -> None:
            self.function_names.append(node.name)
            self.generic_visit(node)
            self.function_names.pop()

        def visit_Call(self, node: ast.Call) -> None:
            if (
                isinstance(node.func, ast.Attribute)
                and node.func.attr == "place_object"
            ):
                self.calls.append(
                    (
                        self.class_names[-1] if self.class_names else None,
                        (
                            self.function_names[-1]
                            if self.function_names
                            else None
                        ),
                        node.lineno,
                    )
                )
            self.generic_visit(node)

    allowed = {
        (
            "dnd.blocks.base_item",
            "BaseItem",
            "place_on_grid",
        ),
        (
            "dnd.spells.evocation",
            "ContinualFlameObject",
            "setup_light",
        ),
    }
    found: set[tuple[str, str | None, str | None]] = set()
    details: list[str] = []
    for source_module in _source_modules().values():
        collector = RawPlacementCollector()
        collector.visit(source_module.tree)
        for class_name, function_name, line in collector.calls:
            found.add((source_module.name, class_name, function_name))
            details.append(
                f"- {source_module.display_path}:{line}: "
                f"{class_name or '<module>'}.{function_name or '<body>'}"
            )

    assert found == allowed, (
        "Only BaseItem.place_on_grid and the deliberate non-item "
        "ContinualFlameObject may call GridMap.place_object directly.\n"
        + "\n".join(details)
    )


def test_weapon_attack_events_have_one_metadata_snapshot_boundary() -> None:
    """Alternate weapon actions cannot construct incomplete AttackEvents."""

    class AttackEventCallCollector(ast.NodeVisitor):
        """Collect direct AttackEvent constructors with lexical ownership."""

        def __init__(self) -> None:
            self.class_names: list[str] = []
            self.function_names: list[str] = []
            self.calls: list[tuple[str | None, str | None, int]] = []

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            self.class_names.append(node.name)
            self.generic_visit(node)
            self.class_names.pop()

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            self.function_names.append(node.name)
            self.generic_visit(node)
            self.function_names.pop()

        def visit_Call(self, node: ast.Call) -> None:
            if isinstance(node.func, ast.Name) and node.func.id == "AttackEvent":
                self.calls.append(
                    (
                        self.class_names[-1] if self.class_names else None,
                        (
                            self.function_names[-1]
                            if self.function_names
                            else None
                        ),
                        node.lineno,
                    )
                )
            self.generic_visit(node)

    allowed = {
        (
            "dnd.actions",
            None,
            "create_weapon_attack_declaration_event",
        ),
        (
            "dnd.monsters.traits",
            "NaturalAttack",
            "_create_declaration_event",
        ),
    }
    found: set[tuple[str, str | None, str | None]] = set()
    details: list[str] = []
    for source_module in _source_modules().values():
        collector = AttackEventCallCollector()
        collector.visit(source_module.tree)
        for class_name, function_name, line in collector.calls:
            found.add((source_module.name, class_name, function_name))
            details.append(
                f"- {source_module.display_path}:{line}: "
                f"{class_name or '<module>'}.{function_name or '<body>'}"
            )

    assert found == allowed, (
        "Equipped and unarmed weapon attacks must snapshot metadata through "
        "create_weapon_attack_declaration_event; only NaturalAttack owns an "
        "explicit non-equipment snapshot.\n"
        + "\n".join(details)
    )
