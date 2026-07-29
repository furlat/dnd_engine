"""Static import boundaries for the native AI architecture."""

from __future__ import annotations

import ast
import subprocess
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
AI_ROOT = REPOSITORY_ROOT / "dnd" / "ai"
AI_BOUNDARY_ROOTS = (
    AI_ROOT,
    REPOSITORY_ROOT / "custom_ai",
    REPOSITORY_ROOT / "services" / "ai_policy_server",
)
AI_BOUNDARY_FILES = (
    REPOSITORY_ROOT / "dnd" / "action_dispatch.py",
    REPOSITORY_ROOT / "server" / "ai_policy_composition.py",
    REPOSITORY_ROOT / "server" / "external_ai_protocol.py",
    REPOSITORY_ROOT
    / "services"
    / "ai_policy_server"
    / "external_ai_registry.py",
    REPOSITORY_ROOT / "server" / "registered_ai_controller.py",
    REPOSITORY_ROOT / "server" / "registered_ai_provider.py",
)
POLICY_LOGIC_ROOTS = (
    AI_ROOT / "policies",
    REPOSITORY_ROOT / "custom_ai",
)
POLICY_LOGIC_FILES = (
    AI_ROOT / "policy.py",
    AI_ROOT / "specification.py",
)
FORBIDDEN_NATIVE_PREFIXES = ("server", "ai", "custom_ai")
FORBIDDEN_POLICY_PREFIXES = (
    "dnd.actions",
    "dnd.actions_functional",
    "dnd.encounter",
    "dnd.entity",
    "dnd.core.base_actions",
)
FORBIDDEN_POLICY_INSTRUMENTATION_PREFIXES = (
    "logging",
    "time",
    "dnd.ai.instrumentation",
)

RETIRED_EVALUATION_IMPORT_PREFIXES = (
    "ai.evaluation",
    "ai.external_selfplay",
    "ai.validation_harness",
    "dnd.scenarios.ai_validation_arenas",
    "dnd.scenarios.evaluation",
    "server.agent_protocol.gauntlet",
    "server.gauntlet_event_stream",
)
RETIRED_SCENARIO_SYMBOLS = frozenset({
    "ActorBlueprint",
    "BattlefieldSpec",
    "LegacyScenarioRecipe",
    "SideConfigurationSpec",
    "ValidationArena",
    "ValidationArenaSpec",
})
RETIRED_EVALUATION_SYMBOLS = frozenset({
    "ConnectedRatingSchedule",
    "EloConfig",
    "EloGauntletEvent",
    "EloGauntletEventSink",
    "EloGauntletEventStream",
    "EloGauntletSummary",
    "EloMatrixSchedule",
    "GauntletEvent",
    "GauntletEventIngestRequest",
    "GauntletEventSink",
    "GauntletEventStream",
    "GauntletFailureRow",
    "GauntletPerformanceSummary",
    "GauntletSchedule",
    "GauntletSummary",
    "GauntletWatcherState",
    "LiveGauntletEventStream",
    "RatingAdmissionCreate",
    "RatingAdmissionRecord",
    "RatingEstimateCreate",
    "RatingEstimateRecord",
    "RatingRunCreate",
    "RatingRunRecord",
    "RatingRunStatus",
    "RatingSnapshot",
    "ValidationBoundaryResult",
    "ValidationEncounterInfo",
    "ValidationGameStatus",
    "ValidationHarnessClient",
    "ValidationHarnessHTTPError",
    "ValidationMode",
    "ValidationScheduleEntry",
    "ValidationSessionPing",
    "ValidationSessionRow",
    "ValidationStartResult",
    "build_validation_schedule",
    "encounter_matches_focus",
    "mode_for_focus",
})
RETIRED_EVALUATION_SOURCE_PATHS = (
    REPOSITORY_ROOT / "ai" / "external_selfplay.py",
    REPOSITORY_ROOT / "ai" / "validation_harness.py",
    REPOSITORY_ROOT / "dnd" / "scenarios" / "ai_validation_arenas.py",
    REPOSITORY_ROOT / "server" / "agent_protocol" / "gauntlet.py",
    REPOSITORY_ROOT / "server" / "gauntlet_event_stream.py",
)
RETIRED_SURFACE_SEARCH_PATTERN = (
    r"ai\.evaluation|ai\.external_selfplay|external_selfplay|"
    r"ai\.validation_harness|validation_harness|ValidationHarness|"
    r"Validation(?:BoundaryResult|EncounterInfo|GameStatus|Mode|"
    r"ScheduleEntry|SessionPing|SessionRow|StartResult)|"
    r"build_validation_schedule|encounter_matches_focus|mode_for_focus|"
    r"dnd\.scenarios\.evaluation|ai_validation_arenas|"
    r"ValidationArena|SideConfigurationSpec|ActorBlueprint|"
    r"LegacyScenarioRecipe|BattlefieldSpec|Gauntlet|Elo|"
    r"Rating(?:Run|Admission|Estimate|Snapshot)|"
    r"gauntlet_event_stream|/ai/gauntlets"
)


def _production_paths() -> tuple[Path, ...]:
    return tuple(
        sorted(
            path
            for root in (REPOSITORY_ROOT / "dnd", REPOSITORY_ROOT / "server")
            for path in root.rglob("*.py")
            if "__pycache__" not in path.parts
        )
    )


def _maintained_python_paths() -> tuple[Path, ...]:
    roots = (
        "ai",
        "custom_ai",
        "devtools",
        "dnd",
        "server",
        "services",
        "tests",
    )
    ignored_directories = {
        "__pycache__",
        "archive",
        "archived",
        "to_archive",
    }
    source_roots = tuple(
        str(REPOSITORY_ROOT / root_name)
        for root_name in roots
        if (REPOSITORY_ROOT / root_name).exists()
    )
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
            RETIRED_SURFACE_SEARCH_PATTERN,
            *source_roots,
        ],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode in {0, 1}, result.stderr
    return tuple(
        sorted(
            path
            for raw_path in result.stdout.splitlines()
            if raw_path
            if not ignored_directories.intersection(
                (path := Path(raw_path)).parts
            )
        )
    )


def _native_ai_paths() -> tuple[Path, ...]:
    return tuple(
        sorted(
            path
            for path in AI_ROOT.rglob("*.py")
            if "__pycache__" not in path.parts
        )
    )


def _ai_boundary_paths() -> tuple[Path, ...]:
    paths = set(AI_BOUNDARY_FILES)
    for root in AI_BOUNDARY_ROOTS:
        paths.update(root.rglob("*.py"))
    return tuple(sorted(path for path in paths if path.exists()))


def _policy_logic_paths() -> tuple[Path, ...]:
    paths = set(POLICY_LOGIC_FILES)
    for root in POLICY_LOGIC_ROOTS:
        paths.update(root.rglob("*.py"))
    return tuple(sorted(path for path in paths if path.exists()))


def _import_targets(
    tree: ast.AST,
) -> tuple[tuple[ast.Import | ast.ImportFrom, str], ...]:
    targets: list[tuple[ast.Import | ast.ImportFrom, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            targets.extend((node, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            targets.append((node, node.module))
    return tuple(targets)


def _is_prefixed(target: str, prefixes: tuple[str, ...]) -> bool:
    return any(target == prefix or target.startswith(f"{prefix}.") for prefix in prefixes)


def _module_name(path: Path) -> str:
    relative = path.relative_to(REPOSITORY_ROOT).with_suffix("")
    parts = relative.parts
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _find_cycles(graph: dict[str, set[str]]) -> tuple[tuple[str, ...], ...]:
    visiting: list[str] = []
    visiting_set: set[str] = set()
    visited: set[str] = set()
    cycles: set[tuple[str, ...]] = set()

    def visit(module: str) -> None:
        if module in visited:
            return
        if module in visiting_set:
            start = visiting.index(module)
            cycles.add(tuple((*visiting[start:], module)))
            return
        visiting.append(module)
        visiting_set.add(module)
        for dependency in sorted(graph[module]):
            visit(dependency)
        visiting.pop()
        visiting_set.remove(module)
        visited.add(module)

    for module in sorted(graph):
        visit(module)
    return tuple(sorted(cycles))


def test_native_ai_never_imports_server_legacy_ai_or_custom_policy_packages() -> None:
    violations: list[str] = []
    for path in _native_ai_paths():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node, target in _import_targets(tree):
            if _is_prefixed(target, FORBIDDEN_NATIVE_PREFIXES):
                relative = path.relative_to(REPOSITORY_ROOT)
                violations.append(f"{relative}:{node.lineno} imports {target}")
    assert violations == []


def test_policy_logic_never_imports_live_engine_runtime_objects() -> None:
    violations: list[str] = []
    for path in _policy_logic_paths():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node, target in _import_targets(tree):
            if _is_prefixed(target, FORBIDDEN_POLICY_PREFIXES):
                relative = path.relative_to(REPOSITORY_ROOT)
                violations.append(f"{relative}:{node.lineno} imports {target}")
    assert violations == []


def test_policy_logic_never_owns_clocks_logging_or_instrumentation() -> None:
    """Policies describe choices; the core runner measures their execution."""
    violations: list[str] = []
    for path in _policy_logic_paths():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node, target in _import_targets(tree):
            if _is_prefixed(
                target,
                FORBIDDEN_POLICY_INSTRUMENTATION_PREFIXES,
            ):
                relative = path.relative_to(REPOSITORY_ROOT)
                violations.append(f"{relative}:{node.lineno} imports {target}")
    assert violations == []


def test_native_ai_contains_no_function_local_imports_or_type_checking_escape() -> None:
    violations: list[str] = []
    for path in _native_ai_paths():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        parents: dict[ast.AST, ast.AST] = {}
        for parent in ast.walk(tree):
            for child in ast.iter_child_nodes(parent):
                parents[child] = parent
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id == "TYPE_CHECKING":
                relative = path.relative_to(REPOSITORY_ROOT)
                violations.append(f"{relative}:{node.lineno} uses TYPE_CHECKING")
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            parent = parents.get(node)
            while parent is not None and not isinstance(
                parent,
                (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda),
            ):
                parent = parents.get(parent)
            if parent is not None:
                relative = path.relative_to(REPOSITORY_ROOT)
                violations.append(f"{relative}:{node.lineno} has a local import")
    assert violations == []


def test_complete_ai_boundary_has_no_local_imports_or_type_checking_escape() -> None:
    """Transport composition follows the same explicit dependency rule."""
    violations: list[str] = []
    for path in _ai_boundary_paths():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        parents: dict[ast.AST, ast.AST] = {}
        for parent in ast.walk(tree):
            for child in ast.iter_child_nodes(parent):
                parents[child] = parent
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id == "TYPE_CHECKING":
                relative = path.relative_to(REPOSITORY_ROOT)
                violations.append(f"{relative}:{node.lineno} uses TYPE_CHECKING")
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            parent = parents.get(node)
            while parent is not None and not isinstance(
                parent,
                (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda),
            ):
                parent = parents.get(parent)
            if parent is not None:
                relative = path.relative_to(REPOSITORY_ROOT)
                violations.append(f"{relative}:{node.lineno} has a local import")
    assert violations == []


def test_complete_ai_boundary_import_graph_is_acyclic() -> None:
    """The core, custom-policy, provider, and transport seam has no cycle."""
    paths_by_module = {
        _module_name(path): path for path in _ai_boundary_paths()
    }
    graph = {module: set() for module in paths_by_module}
    for module, path in paths_by_module.items():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for _, target in _import_targets(tree):
            candidate = target
            while candidate:
                if candidate in graph:
                    graph[module].add(candidate)
                    break
                if "." not in candidate:
                    break
                candidate = candidate.rsplit(".", 1)[0]
    assert _find_cycles(graph) == ()


def test_engine_and_server_do_not_import_the_abandoned_top_level_ai_package() -> None:
    violations: list[str] = []
    for path in _production_paths():
        if AI_ROOT in path.parents:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node, target in _import_targets(tree):
            if target == "ai" or target.startswith("ai."):
                relative = path.relative_to(REPOSITORY_ROOT)
                violations.append(f"{relative}:{node.lineno} imports {target}")
    assert violations == []


def test_maintained_python_has_no_retired_evaluation_imports_or_symbols() -> None:
    """The hard cut has no import alias or relocated compatibility surface."""
    violations: list[str] = []
    for path in _maintained_python_paths():
        if path == Path(__file__).resolve():
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node, target in _import_targets(tree):
            if _is_prefixed(target, RETIRED_EVALUATION_IMPORT_PREFIXES):
                relative = path.relative_to(REPOSITORY_ROOT)
                violations.append(f"{relative}:{node.lineno} imports {target}")
        for node in ast.walk(tree):
            identifier: str | None = None
            if isinstance(node, ast.Name):
                identifier = node.id
            elif isinstance(node, ast.Attribute):
                identifier = node.attr
            elif isinstance(
                node,
                (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef),
            ):
                identifier = node.name
            elif isinstance(node, ast.alias):
                identifier = node.name.rsplit(".", 1)[-1]
            if identifier is None:
                continue
            if (
                identifier in RETIRED_SCENARIO_SYMBOLS
                or identifier.endswith("ActorBlueprint")
                or identifier in RETIRED_EVALUATION_SYMBOLS
            ):
                relative = path.relative_to(REPOSITORY_ROOT)
                violations.append(
                    f"{relative}:{getattr(node, 'lineno', 0)} uses {identifier}"
                )
    assert violations == []


def test_abandoned_evaluation_runtime_is_absent() -> None:
    """Elo, gauntlet, and direct self-play are not parallel production paths."""
    evaluation_sources = tuple(
        path.relative_to(REPOSITORY_ROOT)
        for root in (
            REPOSITORY_ROOT / "ai" / "evaluation",
            REPOSITORY_ROOT / "dnd" / "scenarios" / "evaluation",
        )
        if root.exists()
        for path in root.rglob("*.py")
    )
    assert evaluation_sources == ()
    assert [
        path.relative_to(REPOSITORY_ROOT)
        for path in RETIRED_EVALUATION_SOURCE_PATHS
        if path.exists()
    ] == []

    route_violations: list[str] = []
    for path in _production_paths():
        source = path.read_text(encoding="utf-8")
        if "/ai/gauntlets" not in source:
            continue
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and "/ai/gauntlets" in node.value
            ):
                relative = path.relative_to(REPOSITORY_ROOT)
                route_violations.append(
                    f"{relative}:{node.lineno} retains {node.value!r}"
                )
    assert route_violations == []


def test_deleted_server_owned_ai_contract_modules_are_not_imported() -> None:
    obsolete = (
        "server.agent_protocol.control",
        "server.agent_protocol.immutable",
        "server.agent_protocol.observation",
        "server.agent_protocol.observation_replay",
        "server.agent_protocol.semantics",
        "server.agent_runtime.action_semantics",
        "server.agent_runtime.epochs",
    )
    violations: list[str] = []
    for path in _production_paths():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node, target in _import_targets(tree):
            if _is_prefixed(target, obsolete):
                relative = path.relative_to(REPOSITORY_ROOT)
                violations.append(f"{relative}:{node.lineno} imports {target}")
    assert violations == []


def test_engine_and_server_action_execution_share_the_core_dispatcher() -> None:
    """HTTP and AI execution are the only consumers of the core dispatcher."""
    consumers: list[Path] = []
    for path in _production_paths():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            if node.module != "dnd.action_dispatch":
                continue
            if any(
                alias.name == "dispatch_available_action"
                for alias in node.names
            ):
                consumers.append(path.relative_to(REPOSITORY_ROOT))
    assert consumers == [
        Path("dnd/ai/runtime/execution.py"),
        Path("server/event_server.py"),
    ]


def test_execute_available_action_is_private_to_the_core_dispatch_boundary() -> None:
    """Only the dispatcher and documented convenience wrapper call the primitive."""
    importers: list[Path] = []
    call_sites: list[tuple[Path, str]] = []
    for path in _production_paths():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        parents: dict[ast.AST, ast.AST] = {}
        for parent in ast.walk(tree):
            for child in ast.iter_child_nodes(parent):
                parents[child] = parent
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.ImportFrom)
                and node.module == "dnd.actions_functional"
                and any(
                    alias.name == "execute_available_action"
                    for alias in node.names
                )
            ):
                importers.append(path.relative_to(REPOSITORY_ROOT))
            if not isinstance(node, ast.Call):
                continue
            if not (
                (
                    isinstance(node.func, ast.Name)
                    and node.func.id == "execute_available_action"
                )
                or (
                    isinstance(node.func, ast.Attribute)
                    and node.func.attr == "execute_available_action"
                )
            ):
                continue
            enclosing = parents.get(node)
            while enclosing is not None and not isinstance(
                enclosing,
                (ast.FunctionDef, ast.AsyncFunctionDef),
            ):
                enclosing = parents.get(enclosing)
            call_sites.append(
                (
                    path.relative_to(REPOSITORY_ROOT),
                    enclosing.name
                    if isinstance(
                        enclosing,
                        (ast.FunctionDef, ast.AsyncFunctionDef),
                    )
                    else "<module>",
                )
            )

    assert importers == [Path("dnd/action_dispatch.py")]
    assert call_sites == [
        (Path("dnd/action_dispatch.py"), "dispatch_available_action"),
        (Path("dnd/actions_functional.py"), "execute_by_index"),
    ]
