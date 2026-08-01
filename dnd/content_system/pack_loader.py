"""Single audited dynamic-import boundary for trusted installed content packs."""

from __future__ import annotations

import ast
import hashlib
import sys
import tomllib
from collections import defaultdict
from collections.abc import Mapping, Sequence
from contextvars import ContextVar
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from importlib import invalidate_caches
from pathlib import Path
from types import ModuleType
from uuid import UUID

from dnd.blocks.sensory import spatial_senses_system
from dnd.content_system.artifact_digest import (
    LocalContentImportError,
    resolve_local_python_module_closure,
)
from dnd.content_system.import_boundary import import_content_pack_module
from dnd.core.base_block import BaseBlock
from dnd.core.base_conditions import SpellProtectionRegistry
from dnd.core.base_object import BaseObject
from dnd.core.content.canonical import canonical_content_sha256
from dnd.core.content.identities import validate_sha256
from dnd.core.content.pack_contracts import ContentPackManifest
from dnd.core.content.provenance import ContentSource
from dnd.core.content.recipe_presets import (
    ContentRecipePreset,
    scan_module_content_recipe_presets,
)
from dnd.core.content.registration import (
    ContentDeclaration,
    scan_module_content_declarations,
)
from dnd.core.content.registry import (
    ContentRegistryBuilder,
    FrozenContentRegistry,
)
from dnd.core.dice import Dice, DiceRoll
from dnd.core.events import EventQueue
from dnd.core.gridmap import GridMap
from dnd.core.values import BaseValue
from dnd.entity import Entity


ENGINE_CONTENT_API_VERSION = 2
CONTENT_PACK_MANIFEST_NAME = "content-pack.toml"

_FORBIDDEN_PACK_IMPORT_PREFIXES = (
    "ai",
    "custom_ai",
    "server",
    "dnd.ai",
    "dnd.content_system",
    "dnd.controller",
    "dnd.encounter",
    "dnd.premade_characters",
    "dnd.runtime_reset",
    "dnd.scenarios",
)
_DYNAMIC_CODE_IMPORT_PREFIXES = (
    "importlib",
    "runpy",
    "zipimport",
)
_DYNAMIC_CODE_BUILTIN_NAMES = frozenset({
    "compile",
    "eval",
    "exec",
})
_DYNAMIC_LOADER_METHOD_NAMES = frozenset({
    "exec_module",
    "load_module",
})
_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]

_EVENT_QUEUE_STATE_ATTRIBUTES = (
    "_events_by_lineage",
    "_events_by_uuid",
    "_events_by_type",
    "_events_by_timestamp",
    "_events_by_phase",
    "_events_by_source",
    "_events_by_target",
    "_all_events",
    "_generation_uuid",
    "_active_turn_execution_id",
    "_event_handlers",
    "_event_handlers_by_trigger",
    "_event_handlers_by_simple_trigger",
    "_event_handlers_by_source_entity_uuid",
    "_spatial_handlers",
    "_spatial_handlers_by_position",
    "_spatial_handlers_by_source_entity_uuid",
    "_handler_positions",
    "_on_event_callbacks",
    "_on_event_callback_filters",
    "_on_event_sequence_callbacks",
    "_on_event_sequence_callback_filters",
    "_on_event_batch_callbacks",
    "_on_handler_dispatch_callbacks",
    "_handler_dispatch_cursor",
    "_pre_completion_callbacks",
    "_pre_completion_systems",
    "_pre_completion_systems_by_event_type",
    "_pre_completion_running",
    "_combat_log_callback",
    "_perceiver_computer",
    "_revealed_computer",
    "_identified_entity_observer_computer",
)
_EVENT_QUEUE_CONTEXT_ATTRIBUTES = (
    "_event_batch_depth",
    "_pending_event_batch",
    "_preflight_depth",
)


def _has_import_prefix(
    module_name: str,
    prefixes: Sequence[str],
) -> bool:
    """Return whether an import is a prefix itself or one of its children."""
    return any(
        module_name == prefix or module_name.startswith(f"{prefix}.")
        for prefix in prefixes
    )


@dataclass(frozen=True, slots=True)
class DiscoveredContentPack:
    """Validated paths and cold manifest for one installed pack."""

    pack_directory: Path
    manifest_path: Path
    python_root: Path
    python_package_directory: Path
    assets_root: Path | None
    manifest: ContentPackManifest
    discovery_pack_digest: str


@dataclass(frozen=True, slots=True)
class LoadedContentSystem:
    """One atomically built immutable registry and its process identity."""

    registry: FrozenContentRegistry
    packs: tuple[DiscoveredContentPack, ...]
    built_in_artifact_digest: str
    content_set_digest: str


@dataclass(frozen=True, slots=True)
class _PackPythonModule:
    """One parsed Python module owned by a discovered content pack."""

    pack: DiscoveredContentPack
    name: str
    path: Path
    is_package: bool
    tree: ast.Module


@dataclass(frozen=True, slots=True)
class _PackImportReference:
    """One resolved static import in a content-pack module."""

    importer: str
    target: str
    requested_target: str
    path: Path
    line: int
    syntax: str
    relative: bool


@dataclass(frozen=True, slots=True)
class _RuntimeAttributeSnapshot:
    """One engine class attribute protected across pack execution."""

    owner: type[object]
    name: str
    original: object
    contents: object
    token: object


@dataclass(frozen=True, slots=True)
class _RuntimeContextSnapshot:
    """One EventQueue context-local value protected across pack execution."""

    name: str
    variable: ContextVar[object]
    contents: object
    token: object


@dataclass(frozen=True, slots=True)
class _RuntimeObjectSnapshot:
    """One process singleton whose mutable state must remain cold."""

    label: str
    target: object
    originals: dict[str, object]
    contents: dict[str, object]
    token: object


@dataclass(frozen=True, slots=True)
class _EngineRuntimeSnapshot:
    """Transactional snapshot of global gameplay state around pack imports."""

    attributes: tuple[_RuntimeAttributeSnapshot, ...]
    contexts: tuple[_RuntimeContextSnapshot, ...]
    grid_instance: GridMap | None
    grid_state: _RuntimeObjectSnapshot | None
    object_states: tuple[_RuntimeObjectSnapshot, ...]


class _PackImportCollector(ast.NodeVisitor):
    """Collect static edges and forbidden runtime-only import mechanisms."""

    def __init__(
        self,
        source_module: _PackPythonModule,
        known_module_names: frozenset[str],
    ) -> None:
        self.source_module = source_module
        self.known_module_names = known_module_names
        self.function_depth = 0
        self.references: list[_PackImportReference] = []
        self.violations: set[tuple[int, str]] = set()
        self.typing_module_aliases: set[str] = set()
        self.type_checking_aliases: set[str] = set()
        self.importlib_aliases: set[str] = {"importlib"}
        self.import_module_aliases: set[str] = set()
        self.builtins_aliases: set[str] = {"builtins"}
        self.builtin_import_aliases: set[str] = {"__import__"}
        self.dynamic_code_call_aliases: set[str] = set(
            _DYNAMIC_CODE_BUILTIN_NAMES,
        )
        self._collect_special_aliases()

    def _collect_special_aliases(self) -> None:
        for node in ast.walk(self.source_module.tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    local_name = alias.asname or alias.name
                    if alias.name in {"typing", "typing_extensions"}:
                        self.typing_module_aliases.add(local_name)
                    elif alias.name == "importlib":
                        self.importlib_aliases.add(local_name)
                    elif alias.name == "builtins":
                        self.builtins_aliases.add(local_name)
            elif isinstance(node, ast.ImportFrom):
                if node.module in {"typing", "typing_extensions"}:
                    self.type_checking_aliases.update(
                        alias.asname or alias.name
                        for alias in node.names
                        if alias.name == "TYPE_CHECKING"
                    )
                elif node.module == "importlib":
                    self.import_module_aliases.update(
                        alias.asname or alias.name
                        for alias in node.names
                        if alias.name == "import_module"
                    )
                elif node.module == "builtins":
                    self.builtin_import_aliases.update(
                        alias.asname or alias.name
                        for alias in node.names
                        if alias.name == "__import__"
                    )
                    self.dynamic_code_call_aliases.update(
                        alias.asname or alias.name
                        for alias in node.names
                        if alias.name in _DYNAMIC_CODE_BUILTIN_NAMES
                    )

    def _visit_function(self, node: ast.AST) -> None:
        self.function_depth += 1
        self.generic_visit(node)
        self.function_depth -= 1

    def _record_static_import(
        self,
        *,
        node: ast.Import | ast.ImportFrom,
        target: str,
        requested_target: str,
        syntax: str,
    ) -> None:
        self.references.append(
            _PackImportReference(
                importer=self.source_module.name,
                target=target,
                requested_target=requested_target,
                path=self.source_module.path,
                line=node.lineno,
                syntax=syntax,
                relative=isinstance(node, ast.ImportFrom) and node.level > 0,
            ),
        )
        if self.function_depth > 0:
            self.violations.add(
                (
                    node.lineno,
                    f"function-local import is forbidden: {syntax}",
                ),
            )

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        self._visit_function(node)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self._record_static_import(
                node=node,
                target=alias.name,
                requested_target=alias.name,
                syntax=f"import {alias.name}",
            )
            if _has_import_prefix(
                alias.name,
                _DYNAMIC_CODE_IMPORT_PREFIXES,
            ):
                self.violations.add(
                    (
                        node.lineno,
                        "dynamic code mechanism is forbidden: "
                        f"import {alias.name}",
                    ),
                )

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        base_module = _resolve_pack_import_from_base(
            self.source_module,
            node,
        )
        for alias in node.names:
            candidate = (
                f"{base_module}.{alias.name}"
                if base_module
                else alias.name
            )
            target = (
                candidate
                if candidate in self.known_module_names
                else base_module or candidate
            )
            dots = "." * node.level
            syntax = f"from {dots}{node.module or ''} import {alias.name}"
            self._record_static_import(
                node=node,
                target=target,
                requested_target=candidate,
                syntax=syntax,
            )
            if (
                node.module in {"typing", "typing_extensions"}
                and alias.name == "TYPE_CHECKING"
            ):
                self.violations.add(
                    (
                        node.lineno,
                        f"TYPE_CHECKING import is forbidden: {syntax}",
                    ),
                )
            if (
                node.module == "importlib"
                and alias.name == "import_module"
            ) or (
                node.module == "builtins"
                and alias.name == "__import__"
            ):
                self.violations.add(
                    (
                        node.lineno,
                        f"dynamic import mechanism is forbidden: {syntax}",
                    ),
                )
            if (
                node.module is not None
                and _has_import_prefix(
                    node.module,
                    _DYNAMIC_CODE_IMPORT_PREFIXES,
                )
            ) or (
                node.module == "builtins"
                and alias.name in _DYNAMIC_CODE_BUILTIN_NAMES
            ):
                self.violations.add(
                    (
                        node.lineno,
                        f"dynamic code mechanism is forbidden: {syntax}",
                    ),
                )

    def visit_If(self, node: ast.If) -> None:
        if self._is_type_checking_expression(node.test):
            self.violations.add(
                (
                    node.lineno,
                    "TYPE_CHECKING guard is forbidden",
                ),
            )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if self._is_dynamic_code_expression(node.func):
            self.violations.add(
                (
                    node.lineno,
                    "dynamic code call is forbidden",
                ),
            )
        elif self._is_dynamic_import_expression(node.func):
            self.violations.add(
                (
                    node.lineno,
                    "dynamic import call is forbidden",
                ),
            )
        elif (
            isinstance(node.func, ast.Name)
            and node.func.id == "getattr"
            and len(node.args) >= 2
            and isinstance(node.args[0], ast.Name)
            and isinstance(node.args[1], ast.Constant)
            and isinstance(node.args[1].value, str)
            and (
                (
                    node.args[0].id in self.importlib_aliases
                    and node.args[1].value == "import_module"
                )
                or (
                    node.args[0].id in self.builtins_aliases
                    and node.args[1].value
                    in {"__import__", *_DYNAMIC_CODE_BUILTIN_NAMES}
                )
            )
        ):
            self.violations.add(
                (
                    node.lineno,
                    "dynamic code lookup is forbidden",
                ),
            )
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if self._is_dynamic_code_expression(node):
            self.violations.add(
                (
                    node.lineno,
                    "dynamic code reference is forbidden",
                ),
            )
        elif self._is_dynamic_import_expression(node):
            self.violations.add(
                (
                    node.lineno,
                    "dynamic import reference is forbidden",
                ),
            )
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if node.id in self.dynamic_code_call_aliases:
            self.violations.add(
                (
                    node.lineno,
                    "dynamic code reference is forbidden",
                ),
            )
        elif node.id in self.builtin_import_aliases:
            self.violations.add(
                (
                    node.lineno,
                    "dynamic import reference is forbidden",
                ),
            )
        self.generic_visit(node)

    def _is_type_checking_expression(self, expression: ast.AST) -> bool:
        return any(
            (
                isinstance(node, ast.Name)
                and node.id in self.type_checking_aliases
            )
            or (
                isinstance(node, ast.Attribute)
                and node.attr == "TYPE_CHECKING"
                and isinstance(node.value, ast.Name)
                and node.value.id in self.typing_module_aliases
            )
            for node in ast.walk(expression)
        )

    def _is_dynamic_import_expression(self, expression: ast.expr) -> bool:
        if isinstance(expression, ast.Name):
            return (
                expression.id in self.import_module_aliases
                or expression.id in self.builtin_import_aliases
            )
        return (
            isinstance(expression, ast.Attribute)
            and isinstance(expression.value, ast.Name)
            and (
                (
                    expression.value.id in self.importlib_aliases
                    and expression.attr == "import_module"
                )
                or (
                    expression.value.id in self.builtins_aliases
                    and expression.attr == "__import__"
                )
            )
        )

    def _is_dynamic_code_expression(self, expression: ast.expr) -> bool:
        if isinstance(expression, ast.Name):
            return expression.id in self.dynamic_code_call_aliases
        if not isinstance(expression, ast.Attribute):
            return False
        if expression.attr in _DYNAMIC_LOADER_METHOD_NAMES:
            return True
        return (
            isinstance(expression.value, ast.Name)
            and expression.value.id in self.builtins_aliases
            and expression.attr in _DYNAMIC_CODE_BUILTIN_NAMES
        )


def discover_content_packs(
    pack_roots: Sequence[Path],
) -> tuple[DiscoveredContentPack, ...]:
    """Parse and validate immediate-child manifests without importing code."""
    normalized_roots: dict[str, Path] = {}
    for configured_root in pack_roots:
        root = configured_root.resolve(strict=True)
        if not root.is_dir():
            raise ValueError(f"Content pack root is not a directory: {root}")
        normalized_roots[root.as_posix()] = root

    discovered: list[DiscoveredContentPack] = []
    for root in (normalized_roots[key] for key in sorted(normalized_roots)):
        for child in sorted(root.iterdir(), key=lambda path: path.name):
            if child.name.startswith("."):
                continue
            manifest_path = child / CONTENT_PACK_MANIFEST_NAME
            if not manifest_path.exists():
                continue
            if child.is_symlink():
                raise ValueError(
                    f"Content pack directory cannot be a symlink: {child}",
                )
            pack_directory = child.resolve(strict=True)
            _require_within(pack_directory, root, "pack directory")
            if not pack_directory.is_dir():
                raise ValueError(
                    f"Content pack path is not a directory: {pack_directory}",
                )
            if manifest_path.is_symlink() or not manifest_path.is_file():
                raise ValueError(
                    f"Content pack manifest must be a regular file: "
                    f"{manifest_path}",
                )
            initial_pack_digest = _hash_pack_directory(pack_directory)
            manifest = ContentPackManifest.model_validate(
                tomllib.loads(manifest_path.read_text(encoding="utf-8")),
            )
            if manifest.engine_content_api != ENGINE_CONTENT_API_VERSION:
                raise ValueError(
                    f"Pack {manifest.pack_id} requires engine content API "
                    f"{manifest.engine_content_api}; supported API is "
                    f"{ENGINE_CONTENT_API_VERSION}",
                )
            python_root = _resolve_manifest_path(
                pack_directory,
                manifest.python_root,
                "python_root",
            )
            python_package_directory = (
                python_root.joinpath(*manifest.python_package.split("."))
                .resolve(strict=True)
            )
            _require_within(
                python_package_directory,
                python_root,
                "python package",
            )
            if not python_package_directory.is_dir():
                raise ValueError(
                    f"Pack {manifest.pack_id} Python package is not a directory",
                )
            if not (python_package_directory / "__init__.py").is_file():
                raise ValueError(
                    f"Pack {manifest.pack_id} Python package must contain "
                    "__init__.py",
                )
            assets_root = (
                _resolve_manifest_path(
                    pack_directory,
                    manifest.assets_root,
                    "assets_root",
                )
                if manifest.assets_root is not None
                else None
            )
            discovery_pack_digest = _hash_pack_directory(pack_directory)
            if discovery_pack_digest != initial_pack_digest:
                raise RuntimeError(
                    f"Content pack {manifest.pack_id} changed during discovery",
                )
            discovered.append(
                DiscoveredContentPack(
                    pack_directory=pack_directory,
                    manifest_path=manifest_path.resolve(strict=True),
                    python_root=python_root,
                    python_package_directory=python_package_directory,
                    assets_root=assets_root,
                    manifest=manifest,
                    discovery_pack_digest=discovery_pack_digest,
                ),
            )

    by_pack_id: dict[str, DiscoveredContentPack] = {}
    by_python_package: dict[str, DiscoveredContentPack] = {}
    for pack in discovered:
        existing = by_pack_id.get(pack.manifest.pack_id)
        if existing is not None:
            raise ValueError(
                f"Duplicate content pack {pack.manifest.pack_id}: "
                f"{existing.pack_directory} and {pack.pack_directory}",
            )
        by_pack_id[pack.manifest.pack_id] = pack
        existing_package = by_python_package.get(pack.manifest.python_package)
        if existing_package is not None:
            raise ValueError(
                "Duplicate content-pack Python package "
                f"{pack.manifest.python_package}: "
                f"{existing_package.pack_directory} and {pack.pack_directory}",
            )
        by_python_package[pack.manifest.python_package] = pack
    _validate_nonoverlapping_python_packages(discovered)
    return tuple(
        sorted(
            discovered,
            key=lambda pack: (
                pack.manifest.pack_id,
                pack.pack_directory.as_posix(),
            ),
        ),
    )


def load_content_system(
    *,
    pack_roots: Sequence[Path],
    built_in_artifact_digest: str,
    built_in_sources: Sequence[ContentSource] = (),
    built_in_declarations: Sequence[ContentDeclaration] = (),
    built_in_recipe_presets: Sequence[ContentRecipePreset] = (),
    built_in_pack_versions: Mapping[str, str] | None = None,
    built_in_pack_dependencies: Mapping[str, frozenset[str]] | None = None,
) -> LoadedContentSystem:
    """Import all validated packs and publish only a complete frozen registry."""
    validated_built_in_artifact_digest = validate_sha256(
        built_in_artifact_digest,
        "built_in_artifact_digest",
    )
    normalized_built_in_pack_versions = dict(built_in_pack_versions or {})
    normalized_built_in_pack_dependencies = {
        pack_id: frozenset(dependencies)
        for pack_id, dependencies in (
            built_in_pack_dependencies or {}
        ).items()
    }
    packs = discover_content_packs(pack_roots)
    _validate_pack_dependencies(
        packs,
        built_in_pack_versions=normalized_built_in_pack_versions,
    )
    ordered_packs = _topological_pack_order(packs)

    pre_import_digests = {
        pack.manifest.pack_id: _hash_pack_directory(pack.pack_directory)
        for pack in packs
    }
    changed_after_discovery = sorted(
        pack.manifest.pack_id
        for pack in packs
        if pre_import_digests[pack.manifest.pack_id]
        != pack.discovery_pack_digest
    )
    if changed_after_discovery:
        raise RuntimeError(
            "Content pack files changed after discovery: "
            + ", ".join(changed_after_discovery),
        )
    _validate_static_pack_imports(packs)
    if packs:
        _require_cold_engine_runtime()

    builder = ContentRegistryBuilder()
    for source in built_in_sources:
        builder.add_source(source)
    for declaration in built_in_declarations:
        builder.add_declaration(declaration)
    for preset in built_in_recipe_presets:
        builder.add_recipe_preset(preset)
    for pack in packs:
        for source in pack.manifest.sources:
            builder.add_source(source)

    module_snapshot = _snapshot_pack_modules(packs)
    runtime_snapshot = _snapshot_engine_runtime()
    installed_python_roots: tuple[str, ...] = ()
    try:
        _remove_pack_modules(packs)
        invalidate_caches()
        installed_python_roots = _install_python_roots(ordered_packs)
        for pack in ordered_packs:
            for module_name in _pack_module_names(pack):
                module = import_content_pack_module(module_name)
                _validate_loaded_module_path(pack, module)
                for declaration in scan_module_content_declarations(module):
                    if declaration.ref.pack_id != pack.manifest.pack_id:
                        raise ValueError(
                            f"Module {module_name} declares "
                            f"{declaration.ref.identity_key} for another pack",
                        )
                    builder.add_declaration(declaration)
                for preset in scan_module_content_recipe_presets(module):
                    if preset.ref.pack_id != pack.manifest.pack_id:
                        raise ValueError(
                            f"Module {module_name} exports recipe preset "
                            f"{preset.ref.identity_key} for another pack",
                        )
                    builder.add_recipe_preset(preset)

        post_import_digests = {
            pack.manifest.pack_id: _hash_pack_directory(pack.pack_directory)
            for pack in packs
        }
        changed_during_import = sorted(
            pack_id
            for pack_id, digest in pre_import_digests.items()
            if post_import_digests[pack_id] != digest
        )
        if changed_during_import:
            raise RuntimeError(
                "Content pack files changed during import: "
                + ", ".join(changed_during_import),
            )

        pack_dependencies = dict(normalized_built_in_pack_dependencies)
        for pack in packs:
            pack_dependencies[pack.manifest.pack_id] = frozenset(
                dependency.pack_id
                for dependency in pack.manifest.dependencies
            )
        registry = builder.freeze(pack_dependencies=pack_dependencies)
        runtime_mutations = _engine_runtime_mutations(runtime_snapshot)
        if runtime_mutations:
            raise RuntimeError(
                "Content pack import mutated engine runtime state: "
                + ", ".join(runtime_mutations),
            )
        content_set_digest = _content_set_digest(
            packs=packs,
            pack_digests=post_import_digests,
            built_in_artifact_digest=validated_built_in_artifact_digest,
            built_in_sources=built_in_sources,
            built_in_declarations=built_in_declarations,
            built_in_recipe_presets=built_in_recipe_presets,
            built_in_pack_versions=normalized_built_in_pack_versions,
            built_in_pack_dependencies=normalized_built_in_pack_dependencies,
        )
        return LoadedContentSystem(
            registry=registry,
            packs=packs,
            built_in_artifact_digest=validated_built_in_artifact_digest,
            content_set_digest=content_set_digest,
        )
    except BaseException:
        _restore_engine_runtime(runtime_snapshot)
        _remove_pack_modules(packs)
        sys.modules.update(module_snapshot)
        raise
    finally:
        _remove_python_roots(installed_python_roots)
        invalidate_caches()


def _snapshot_engine_runtime() -> _EngineRuntimeSnapshot:
    """Capture all process-global engine state an import must not mutate."""
    attributes = tuple(
        _snapshot_runtime_attribute(owner, name)
        for owner, name in _engine_runtime_attribute_specs()
    )
    contexts: list[_RuntimeContextSnapshot] = []
    for name in _EVENT_QUEUE_CONTEXT_ATTRIBUTES:
        variable = getattr(EventQueue, name)
        if not isinstance(variable, ContextVar):
            raise TypeError(f"EventQueue.{name} is not a ContextVar")
        current = variable.get()
        contents = _clone_runtime_state(current)
        contexts.append(
            _RuntimeContextSnapshot(
                name=name,
                variable=variable,
                contents=contents,
                token=_runtime_state_token(current),
            ),
        )

    grid_instance = GridMap._instance
    grid_state = (
        _snapshot_runtime_object("GridMap._instance", grid_instance)
        if grid_instance is not None
        else None
    )
    return _EngineRuntimeSnapshot(
        attributes=attributes,
        contexts=tuple(contexts),
        grid_instance=grid_instance,
        grid_state=grid_state,
        object_states=(
            _snapshot_runtime_object(
                "spatial_senses_system",
                spatial_senses_system,
            ),
        ),
    )


def _engine_runtime_attribute_specs(
) -> tuple[tuple[type[object], str], ...]:
    """Return every class-level runtime slot protected by cold loading."""
    return (
        (BaseObject, "_registry"),
        (BaseBlock, "_registry"),
        (BaseValue, "_registry"),
        (DiceRoll, "_registry"),
        (Dice, "_registry"),
        (Entity, "_entity_registry"),
        (Entity, "_entity_by_position"),
        (SpellProtectionRegistry, "_protections"),
        *(
            (EventQueue, attribute)
            for attribute in _EVENT_QUEUE_STATE_ATTRIBUTES
        ),
    )


def _require_cold_engine_runtime() -> None:
    """Reject external pack execution after gameplay state has come alive."""
    live_slots: list[str] = []
    event_queue_cold_values: dict[str, object] = {
        "_combat_log_callback": None,
        "_handler_dispatch_cursor": 0,
        "_identified_entity_observer_computer": None,
        "_perceiver_computer": None,
        "_revealed_computer": None,
    }
    for owner, name in _engine_runtime_attribute_specs():
        if owner is EventQueue and name == "_generation_uuid":
            continue
        value = getattr(owner, name)
        expected = event_queue_cold_values.get(name, ...)
        is_live = value != expected if expected is not ... else bool(value)
        if is_live:
            live_slots.append(
                f"{owner.__module__}.{owner.__qualname__}.{name}",
            )

    context_cold_values = {
        "_event_batch_depth": 0,
        "_pending_event_batch": None,
        "_preflight_depth": 0,
    }
    for name, expected in context_cold_values.items():
        variable = getattr(EventQueue, name)
        if not isinstance(variable, ContextVar):
            raise TypeError(f"EventQueue.{name} is not a ContextVar")
        if variable.get() != expected:
            live_slots.append(f"dnd.core.events.EventQueue.{name}")

    if GridMap._instance is not None:
        live_slots.append("dnd.core.gridmap.GridMap._instance")
    for name, value in vars(spatial_senses_system).items():
        if value:
            live_slots.append(f"spatial_senses_system.{name}")

    if live_slots:
        raise RuntimeError(
            "External content packs require a cold engine runtime; "
            "live state exists in "
            + ", ".join(sorted(live_slots)),
        )


def _snapshot_runtime_attribute(
    owner: type[object],
    name: str,
) -> _RuntimeAttributeSnapshot:
    current = getattr(owner, name)
    return _RuntimeAttributeSnapshot(
        owner=owner,
        name=name,
        original=current,
        contents=_clone_runtime_state(current),
        token=_runtime_state_token(current),
    )


def _snapshot_runtime_object(
    label: str,
    target: object,
) -> _RuntimeObjectSnapshot:
    state = vars(target)
    return _RuntimeObjectSnapshot(
        label=label,
        target=target,
        originals=dict(state),
        contents={
            key: _clone_runtime_state(value)
            for key, value in state.items()
        },
        token=_runtime_state_token(state),
    )


def _engine_runtime_mutations(
    snapshot: _EngineRuntimeSnapshot,
) -> tuple[str, ...]:
    """Return exact protected state slots changed by pack top-level code."""
    changed: list[str] = []
    for attribute in snapshot.attributes:
        current = getattr(attribute.owner, attribute.name)
        if _runtime_state_token(current) != attribute.token:
            changed.append(
                f"{attribute.owner.__module__}."
                f"{attribute.owner.__qualname__}.{attribute.name}",
            )
    for context in snapshot.contexts:
        if _runtime_state_token(context.variable.get()) != context.token:
            changed.append(f"dnd.core.events.EventQueue.{context.name}")

    if GridMap._instance is not snapshot.grid_instance:
        changed.append("dnd.core.gridmap.GridMap._instance")
    elif (
        snapshot.grid_state is not None
        and _runtime_state_token(vars(snapshot.grid_state.target))
        != snapshot.grid_state.token
    ):
        changed.append(snapshot.grid_state.label)

    for object_state in snapshot.object_states:
        if _runtime_state_token(vars(object_state.target)) != object_state.token:
            changed.append(object_state.label)
    return tuple(changed)


def _restore_engine_runtime(snapshot: _EngineRuntimeSnapshot) -> None:
    """Restore protected process globals after any failed pack bootstrap."""
    for attribute in snapshot.attributes:
        restored = _restore_runtime_value(
            attribute.original,
            attribute.contents,
        )
        setattr(attribute.owner, attribute.name, restored)
    for context in snapshot.contexts:
        context.variable.set(_clone_runtime_state(context.contents))

    GridMap._instance = snapshot.grid_instance
    if snapshot.grid_state is not None:
        _restore_runtime_object(snapshot.grid_state)
    for object_state in snapshot.object_states:
        _restore_runtime_object(object_state)


def _restore_runtime_object(snapshot: _RuntimeObjectSnapshot) -> None:
    state = vars(snapshot.target)
    for key in set(state).difference(snapshot.originals):
        state.pop(key)
    for key, original in snapshot.originals.items():
        state[key] = _restore_runtime_value(
            original,
            snapshot.contents[key],
        )


def _restore_runtime_value(original: object, contents: object) -> object:
    """Restore a mutable slot in place when possible, preserving its identity."""
    restored = _clone_runtime_state(contents)
    if isinstance(original, defaultdict) and isinstance(restored, defaultdict):
        original.clear()
        original.default_factory = restored.default_factory
        original.update(restored)
        return original
    if isinstance(original, dict) and isinstance(restored, dict):
        original.clear()
        original.update(restored)
        return original
    if isinstance(original, list) and isinstance(restored, list):
        original.clear()
        original.extend(restored)
        return original
    if isinstance(original, set) and isinstance(restored, set):
        original.clear()
        original.update(restored)
        return original
    return restored


def _clone_runtime_state(value: object) -> object:
    """Clone container topology while retaining live engine object identities."""
    if isinstance(value, defaultdict):
        cloned_defaultdict: defaultdict[object, object] = defaultdict(
            value.default_factory,
        )
        cloned_defaultdict.update({
            key: _clone_runtime_state(item)
            for key, item in value.items()
        })
        return cloned_defaultdict
    if isinstance(value, dict):
        return {
            key: _clone_runtime_state(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_clone_runtime_state(item) for item in value]
    if isinstance(value, set):
        return {_clone_runtime_state(item) for item in value}
    if isinstance(value, tuple):
        return tuple(_clone_runtime_state(item) for item in value)
    return value


def _runtime_state_token(value: object) -> object:
    """Build an equality-safe identity token for nested runtime containers."""
    if isinstance(value, defaultdict):
        rows = (
            (
                _runtime_state_token(key),
                _runtime_state_token(item),
            )
            for key, item in value.items()
        )
        return (
            "defaultdict",
            id(value),
            id(value.default_factory),
            tuple(sorted(rows, key=repr)),
        )
    if isinstance(value, dict):
        rows = (
            (
                _runtime_state_token(key),
                _runtime_state_token(item),
            )
            for key, item in value.items()
        )
        return ("dict", id(value), tuple(sorted(rows, key=repr)))
    if isinstance(value, list):
        return (
            "list",
            id(value),
            tuple(_runtime_state_token(item) for item in value),
        )
    if isinstance(value, set):
        return (
            "set",
            id(value),
            tuple(
                sorted(
                    (_runtime_state_token(item) for item in value),
                    key=repr,
                ),
            ),
        )
    if isinstance(value, tuple):
        return (
            "tuple",
            id(value),
            tuple(_runtime_state_token(item) for item in value),
        )
    if value is None or isinstance(
        value,
        (bool, bytes, float, int, str, UUID, Enum),
    ):
        return ("value", type(value).__module__, type(value).__qualname__, value)
    return (
        "identity",
        type(value).__module__,
        type(value).__qualname__,
        id(value),
    )


def _resolve_manifest_path(
    pack_directory: Path,
    relative_path: str,
    field_name: str,
) -> Path:
    resolved = (pack_directory / relative_path).resolve(strict=True)
    _require_within(resolved, pack_directory, field_name)
    if not resolved.is_dir():
        raise ValueError(
            f"Pack {field_name} is not a directory: {resolved}",
        )
    return resolved


def _require_within(path: Path, parent: Path, label: str) -> None:
    try:
        path.relative_to(parent)
    except ValueError as error:
        raise ValueError(f"Content pack {label} escapes pack directory") from error


def _validate_nonoverlapping_python_packages(
    packs: Sequence[DiscoveredContentPack],
) -> None:
    ordered = sorted(
        packs,
        key=lambda pack: pack.manifest.python_package,
    )
    for index, pack in enumerate(ordered):
        namespace = pack.manifest.python_package
        for other in ordered[index + 1 :]:
            other_namespace = other.manifest.python_package
            if not other_namespace.startswith(f"{namespace}."):
                continue
            raise ValueError(
                "Overlapping content-pack Python packages "
                f"{namespace} and {other_namespace}",
            )


def _validate_pack_dependencies(
    packs: Sequence[DiscoveredContentPack],
    *,
    built_in_pack_versions: Mapping[str, str],
) -> None:
    versions = dict(built_in_pack_versions)
    for pack in packs:
        if pack.manifest.pack_id in versions:
            raise ValueError(
                f"Duplicate content pack {pack.manifest.pack_id} between "
                "built-in and external packs",
            )
        versions[pack.manifest.pack_id] = pack.manifest.pack_version
    for pack in packs:
        for dependency in pack.manifest.dependencies:
            actual_version = versions.get(dependency.pack_id)
            if actual_version is None:
                raise ValueError(
                    f"Pack {pack.manifest.pack_id} requires missing pack "
                    f"{dependency.pack_id}",
                )
            if not _version_matches(actual_version, dependency.version):
                raise ValueError(
                    f"Pack {pack.manifest.pack_id} requires "
                    f"{dependency.pack_id} version {dependency.version}; "
                    f"found {actual_version}",
                )


def _version_matches(actual_version: str, required_version: str) -> bool:
    if required_version.isdigit():
        return actual_version.partition(".")[0] == required_version
    return actual_version == required_version


def _topological_pack_order(
    packs: Sequence[DiscoveredContentPack],
) -> tuple[DiscoveredContentPack, ...]:
    by_id = {pack.manifest.pack_id: pack for pack in packs}
    visited: set[str] = set()
    active: list[str] = []
    active_set: set[str] = set()
    ordered: list[DiscoveredContentPack] = []

    def visit(pack_id: str) -> None:
        if pack_id in visited:
            return
        if pack_id in active_set:
            start = active.index(pack_id)
            cycle = " -> ".join((*active[start:], pack_id))
            raise ValueError(f"Content pack dependency cycle: {cycle}")
        active.append(pack_id)
        active_set.add(pack_id)
        pack = by_id[pack_id]
        for dependency in pack.manifest.dependencies:
            if dependency.pack_id in by_id:
                visit(dependency.pack_id)
        active.pop()
        active_set.remove(pack_id)
        visited.add(pack_id)
        ordered.append(pack)

    for pack_id in sorted(by_id):
        visit(pack_id)
    return tuple(ordered)


def _validate_static_pack_imports(
    packs: Sequence[DiscoveredContentPack],
) -> None:
    """Validate the complete static pack graph before executing any pack code."""
    modules = _parse_pack_python_modules(packs)
    known_module_names = frozenset(modules)
    references: list[_PackImportReference] = []
    violations: list[str] = []

    for module_name in sorted(modules):
        source_module = modules[module_name]
        collector = _PackImportCollector(
            source_module,
            known_module_names,
        )
        collector.visit(source_module.tree)
        references.extend(collector.references)
        violations.extend(
            f"{source_module.pack.manifest.pack_id} "
            f"{source_module.path.name}:{line}: {detail}"
            for line, detail in sorted(collector.violations)
        )
    if violations:
        raise ValueError(
            "Content pack import policy violations:\n- "
            + "\n- ".join(violations),
        )

    for reference in sorted(
        references,
        key=lambda row: (
            row.importer,
            row.line,
            row.target,
            row.syntax,
        ),
    ):
        importing_module = modules[reference.importer]
        importing_pack = importing_module.pack
        forbidden_target = _forbidden_pack_import_target(reference)
        if forbidden_target is not None:
            raise ValueError(
                f"Pack {importing_pack.manifest.pack_id} has forbidden "
                f"composition dependency {forbidden_target} "
                f"({reference.path.name}:{reference.line})",
            )
        transitive_forbidden = _transitive_forbidden_pack_dependencies(
            reference,
        )
        if transitive_forbidden:
            raise ValueError(
                f"Pack {importing_pack.manifest.pack_id} import "
                f"{reference.target} transitively reaches forbidden "
                "composition dependency "
                + ", ".join(transitive_forbidden)
                + f" ({reference.path.name}:{reference.line})",
            )
        target_pack = _pack_owning_import(reference.target, packs)
        if target_pack is None:
            if reference.relative:
                raise ValueError(
                    f"Pack {importing_pack.manifest.pack_id} has a relative "
                    f"import outside installed content packs "
                    f"({reference.path.name}:{reference.line})",
                )
            continue
        if target_pack is importing_pack:
            continue
        allowed_pack_ids = frozenset(
            importing_pack.manifest.dependency_pack_ids,
        )
        if target_pack.manifest.pack_id in allowed_pack_ids:
            continue
        raise ValueError(
            f"Pack {importing_pack.manifest.pack_id} imports Python package "
            f"{reference.target} owned by "
            f"{target_pack.manifest.pack_id} without a direct manifest "
            f"dependency ({reference.path.name}:{reference.line})",
        )

    graph = {
        module_name: set()
        for module_name in known_module_names
    }
    for reference in references:
        if reference.target in known_module_names:
            graph[reference.importer].add(reference.target)
    cycle = _first_module_import_cycle(graph)
    if cycle is not None:
        owners = sorted({
            modules[module_name].pack.manifest.pack_id
            for module_name in cycle
        })
        raise ValueError(
            "Content pack Python import cycle "
            f"({', '.join(owners)}): {' -> '.join(cycle)}",
        )


def _forbidden_pack_import_target(
    reference: _PackImportReference,
) -> str | None:
    """Return the forbidden project-composition root reached by an import."""
    for target in (reference.target, reference.requested_target):
        for prefix in _FORBIDDEN_PACK_IMPORT_PREFIXES:
            if target == prefix or target.startswith(f"{prefix}."):
                return target
    return None


def _transitive_forbidden_pack_dependencies(
    reference: _PackImportReference,
) -> tuple[str, ...]:
    """Return forbidden roots reached through one local ``dnd`` import."""
    root_module = _local_dnd_import_root(reference)
    if root_module is None:
        return ()
    try:
        return _cached_transitive_forbidden_dependencies(root_module)
    except LocalContentImportError as error:
        raise ValueError(
            f"Cannot authenticate local dependency closure for "
            f"{reference.syntax}: {error}",
        ) from error


def _local_dnd_import_root(
    reference: _PackImportReference,
) -> str | None:
    """Choose the most precise resolvable module named by one import."""
    for candidate in (reference.requested_target, reference.target):
        if candidate != "dnd" and not candidate.startswith("dnd."):
            continue
        module_path, package_path = _local_dnd_source_candidates(candidate)
        if module_path.is_file() or package_path.is_file():
            return candidate
    return None


def _local_dnd_source_candidates(module_name: str) -> tuple[Path, Path]:
    relative = Path(*module_name.split("."))
    return (
        _REPOSITORY_ROOT / relative.with_suffix(".py"),
        _REPOSITORY_ROOT / relative / "__init__.py",
    )


@lru_cache(maxsize=256)
def _cached_transitive_forbidden_dependencies(
    root_module: str,
) -> tuple[str, ...]:
    """Resolve and inspect one immutable startup-time local source closure."""
    source_paths = resolve_local_python_module_closure(
        (root_module,),
        repository_root=_REPOSITORY_ROOT,
    )
    modules_by_path = {
        path: _module_name_for_local_source(path)
        for path in source_paths
    }
    forbidden: set[str] = set()
    for path, module_name in modules_by_path.items():
        if _has_import_prefix(
            module_name,
            _FORBIDDEN_PACK_IMPORT_PREFIXES,
        ):
            forbidden.add(module_name)
        for target in _static_import_targets_from_local_source(
            path,
            module_name,
        ):
            if _has_import_prefix(
                target,
                _FORBIDDEN_PACK_IMPORT_PREFIXES,
            ):
                forbidden.add(target)
    return tuple(sorted(forbidden))


def _module_name_for_local_source(path: Path) -> str:
    relative = path.resolve(strict=True).relative_to(_REPOSITORY_ROOT)
    if relative.name == "__init__.py":
        parts = relative.parts[:-1]
    else:
        parts = (*relative.parts[:-1], relative.stem)
    return ".".join(parts)


def _static_import_targets_from_local_source(
    path: Path,
    module_name: str,
) -> tuple[str, ...]:
    """Collect direct static targets for forbidden non-``dnd`` edges too."""
    try:
        tree = ast.parse(
            path.read_text(encoding="utf-8"),
            filename=path.as_posix(),
        )
    except (OSError, SyntaxError, UnicodeError) as error:
        raise LocalContentImportError(
            f"cannot parse local content dependency {module_name}: {error}",
        ) from error
    targets: set[str] = set()
    is_package = path.name == "__init__.py"
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            targets.update(alias.name for alias in node.names)
            continue
        if not isinstance(node, ast.ImportFrom):
            continue
        base = _local_import_from_base(
            module_name=module_name,
            is_package=is_package,
            node=node,
        )
        if base:
            targets.add(base)
        targets.update(
            f"{base}.{alias.name}" if base else alias.name
            for alias in node.names
            if alias.name != "*"
        )
    return tuple(sorted(targets))


def _local_import_from_base(
    *,
    module_name: str,
    is_package: bool,
    node: ast.ImportFrom,
) -> str:
    if node.level == 0:
        return node.module or ""
    package = module_name if is_package else module_name.rpartition(".")[0]
    parts = package.split(".") if package else []
    upward_steps = node.level - 1
    if upward_steps >= len(parts):
        raise LocalContentImportError(
            f"relative import escapes dnd package in {module_name}",
        )
    base_parts = parts[: len(parts) - upward_steps]
    if node.module:
        base_parts.extend(node.module.split("."))
    return ".".join(base_parts)


def _parse_pack_python_modules(
    packs: Sequence[DiscoveredContentPack],
) -> dict[str, _PackPythonModule]:
    modules: dict[str, _PackPythonModule] = {}
    for pack in packs:
        for path in _pack_python_files(pack):
            module_name, is_package = _pack_module_identity(pack, path)
            try:
                tree = ast.parse(
                    path.read_text(encoding="utf-8"),
                    filename=path.as_posix(),
                )
            except SyntaxError as error:
                raise ValueError(
                    f"Pack {pack.manifest.pack_id} has invalid Python source "
                    f"{path}",
                ) from error
            modules[module_name] = _PackPythonModule(
                pack=pack,
                name=module_name,
                path=path,
                is_package=is_package,
                tree=tree,
            )
    return modules


def _pack_module_identity(
    pack: DiscoveredContentPack,
    path: Path,
) -> tuple[str, bool]:
    relative = path.relative_to(pack.python_package_directory)
    is_package = relative.name == "__init__.py"
    suffix_parts = (
        relative.parts[:-1]
        if is_package
        else (*relative.parts[:-1], relative.stem)
    )
    return (
        ".".join((pack.manifest.python_package, *suffix_parts)),
        is_package,
    )


def _resolve_pack_import_from_base(
    source_module: _PackPythonModule,
    node: ast.ImportFrom,
) -> str:
    if node.level == 0:
        return node.module or ""
    package_parts = source_module.name.split(".")
    if not source_module.is_package:
        package_parts.pop()
    parent_hops = node.level - 1
    if parent_hops > len(package_parts):
        return ""
    if parent_hops:
        package_parts = package_parts[:-parent_hops]
    if node.module:
        package_parts.extend(node.module.split("."))
    return ".".join(package_parts)


def _first_module_import_cycle(
    graph: Mapping[str, set[str]],
) -> tuple[str, ...] | None:
    visited: set[str] = set()
    active: list[str] = []
    active_set: set[str] = set()

    def visit(module_name: str) -> tuple[str, ...] | None:
        if module_name in visited:
            return None
        if module_name in active_set:
            start = active.index(module_name)
            return (*active[start:], module_name)
        active.append(module_name)
        active_set.add(module_name)
        for target in sorted(graph[module_name]):
            cycle = visit(target)
            if cycle is not None:
                return cycle
        active.pop()
        active_set.remove(module_name)
        visited.add(module_name)
        return None

    for module_name in sorted(graph):
        cycle = visit(module_name)
        if cycle is not None:
            return cycle
    return None


def _pack_owning_import(
    module_name: str,
    packs: Sequence[DiscoveredContentPack],
) -> DiscoveredContentPack | None:
    for pack in packs:
        namespace = pack.manifest.python_package
        if module_name == namespace or module_name.startswith(f"{namespace}."):
            return pack
    return None


def _snapshot_pack_modules(
    packs: Sequence[DiscoveredContentPack],
) -> dict[str, ModuleType]:
    return {
        module_name: module
        for module_name, module in tuple(sys.modules.items())
        if _pack_owning_import(module_name, packs) is not None
    }


def _remove_pack_modules(
    packs: Sequence[DiscoveredContentPack],
) -> None:
    for module_name in tuple(sys.modules):
        if _pack_owning_import(module_name, packs) is not None:
            sys.modules.pop(module_name, None)


def _install_python_roots(
    packs: Sequence[DiscoveredContentPack],
) -> tuple[str, ...]:
    installed: list[str] = []
    python_roots = sorted({
        pack.python_root.as_posix()
        for pack in packs
    })
    for python_root in reversed(python_roots):
        if python_root not in sys.path:
            sys.path.insert(0, python_root)
            installed.append(python_root)
    return tuple(installed)


def _remove_python_roots(python_roots: Sequence[str]) -> None:
    for python_root in python_roots:
        if python_root in sys.path:
            sys.path.remove(python_root)


def _pack_python_files(
    pack: DiscoveredContentPack,
) -> tuple[Path, ...]:
    package_directory = pack.python_package_directory
    python_files: list[Path] = []
    for path in sorted(
        package_directory.rglob("*.py"),
        key=lambda candidate: candidate.as_posix(),
    ):
        if "__pycache__" in path.parts:
            continue
        if path.is_symlink():
            raise ValueError(f"Content pack contains symlink: {path}")
        relative = path.relative_to(package_directory)
        for depth in range(1, len(relative.parts)):
            parent = package_directory.joinpath(*relative.parts[:depth])
            if parent.is_dir() and not (parent / "__init__.py").is_file():
                raise ValueError(
                    f"Pack {pack.manifest.pack_id} contains non-package "
                    f"Python directory {parent}",
                )
        python_files.append(path)
    return tuple(python_files)


def _pack_module_names(pack: DiscoveredContentPack) -> tuple[str, ...]:
    module_names = {
        _pack_module_identity(pack, path)[0]
        for path in _pack_python_files(pack)
    }
    return tuple(
        sorted(module_names, key=lambda name: (name.count("."), name)),
    )


def _validate_loaded_module_path(
    pack: DiscoveredContentPack,
    module: ModuleType,
) -> None:
    module_path_value = getattr(module, "__file__", None)
    if not isinstance(module_path_value, str):
        raise ValueError(
            f"Pack module {module.__name__} has no concrete source path",
        )
    module_path = Path(module_path_value).resolve(strict=True)
    _require_within(
        module_path,
        pack.python_package_directory,
        f"module {module.__name__}",
    )


def _hash_pack_directory(pack_directory: Path) -> str:
    digest = hashlib.sha256()
    digest.update(b"dnd-content-pack-directory-v1")
    for path in sorted(
        pack_directory.rglob("*"),
        key=lambda candidate: candidate.as_posix(),
    ):
        relative = path.relative_to(pack_directory)
        if "__pycache__" in relative.parts or path.suffix == ".pyc":
            continue
        if path.is_symlink():
            try:
                _require_within(
                    path.resolve(strict=True),
                    pack_directory,
                    "symlink",
                )
            except FileNotFoundError as error:
                raise ValueError(
                    f"Content pack contains broken symlink: {path}",
                ) from error
            raise ValueError(f"Content pack contains symlink: {path}")
        if not path.is_file():
            continue
        relative_bytes = relative.as_posix().encode("utf-8")
        digest.update(
            len(relative_bytes).to_bytes(8, byteorder="big", signed=False),
        )
        digest.update(relative_bytes)
        content_bytes = path.read_bytes()
        digest.update(
            len(content_bytes).to_bytes(8, byteorder="big", signed=False),
        )
        digest.update(content_bytes)
    return digest.hexdigest()


def _content_set_digest(
    *,
    packs: Sequence[DiscoveredContentPack],
    pack_digests: Mapping[str, str],
    built_in_artifact_digest: str,
    built_in_sources: Sequence[ContentSource],
    built_in_declarations: Sequence[ContentDeclaration],
    built_in_recipe_presets: Sequence[ContentRecipePreset],
    built_in_pack_versions: Mapping[str, str],
    built_in_pack_dependencies: Mapping[str, frozenset[str]],
) -> str:
    payload = {
        "engine_content_api": ENGINE_CONTENT_API_VERSION,
        "built_in_artifact_digest": built_in_artifact_digest,
        "built_in_pack_versions": dict(sorted(built_in_pack_versions.items())),
        "built_in_pack_dependencies": {
            pack_id: sorted(dependencies)
            for pack_id, dependencies in sorted(
                built_in_pack_dependencies.items(),
            )
        },
        "built_in_sources": [
            source.model_dump(mode="json")
            for source in sorted(
                built_in_sources,
                key=lambda row: row.source_id,
            )
        ],
        "built_in_declarations": [
            {
                "ref": declaration.ref.model_dump(mode="json"),
                "mode": declaration.mode.value,
                "runtime_behavior_kind": (
                    declaration.runtime_behavior_kind.value
                    if declaration.runtime_behavior_kind is not None
                    else None
                ),
                "descriptor": declaration.descriptor.model_dump(mode="json"),
                "provenance": declaration.provenance.model_dump(mode="json"),
                "item_definition": (
                    declaration.item_definition.model_dump(mode="json")
                    if declaration.item_definition is not None
                    else None
                ),
                "spatial_effect_definition": (
                    declaration.spatial_effect_definition.model_dump(mode="json")
                    if declaration.spatial_effect_definition is not None
                    else None
                ),
                "definition_payload": (
                    declaration.definition_payload.model_dump(mode="json")
                    if declaration.definition_payload is not None
                    else None
                ),
                "dependencies": [
                    dependency.model_dump(mode="json")
                    for dependency in declaration.dependencies
                ],
                "condition_effect_coverage": (
                    declaration.condition_effect_coverage.value
                ),
                "condition_effect_profile": (
                    declaration.condition_effect_profile.model_dump(mode="json")
                    if declaration.condition_effect_profile is not None
                    else None
                ),
                "condition_lifecycle": (
                    declaration.condition_lifecycle.model_dump(mode="json")
                    if declaration.condition_lifecycle is not None
                    else None
                ),
            }
            for declaration in sorted(
                built_in_declarations,
                key=lambda row: row.ref.identity_key,
            )
        ],
        "built_in_recipe_presets": [
            preset.model_dump(mode="json")
            for preset in sorted(
                built_in_recipe_presets,
                key=lambda row: row.ref.identity_key,
            )
        ],
        "external_packs": [
            {
                "pack_id": pack.manifest.pack_id,
                "pack_version": pack.manifest.pack_version,
                "manifest_contract_digest": pack.manifest.contract_digest,
                "pack_digest": pack_digests[pack.manifest.pack_id],
            }
            for pack in sorted(
                packs,
                key=lambda row: row.manifest.pack_id,
            )
        ],
    }
    return canonical_content_sha256(payload)
