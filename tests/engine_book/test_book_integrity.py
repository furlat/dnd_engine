"""Integrity checks for the engine-book documentation/test contract."""

import ast
import io
from pathlib import Path
import re
import tokenize
import tomllib


ROOT = Path(__file__).resolve().parents[2]
ENGINE_BOOK = ROOT / "engine_book"
NOTES = ENGINE_BOOK / "notes"
CHAPTERS = ENGINE_BOOK / "chapters"
OUTLINE = ENGINE_BOOK / "outline.md"
PARITY_MATRIX = ENGINE_BOOK / "parity_matrix.md"
PYPROJECT = ROOT / "pyproject.toml"
SERVER_API_FILES = [
    ROOT / "server" / "event_server.py",
    ROOT / "server" / "session.py",
]
EVENT_SERVER_CLEAN_NODES = {
    ROOT / "server" / "event_server.py": {
        "EventMonitor",
        "SimulationState",
        "_api_http_exception",
        "_entity_lookup_exception",
        "_equipment_context",
        "_equipment_http_exception",
        "_equipment_slot_map",
        "_event_filter_http_exception",
        "_get_floor_object_state",
        "_grid_state_context",
        "_handler_http_exception",
        "_known_entity_summaries",
        "_mapeditor_context",
        "_mapeditor_http_exception",
        "_resolve_entity_or_raise",
        "_serialize_entity_handlers",
        "_session_context",
        "_session_http_exception",
        "_simulation_context",
        "_simulation_http_exception",
        "action_cursor_fields",
        "advance_encounter",
        "build_session_status",
        "setup_combat",
        "setup_arena_combat",
        "setup_aoe_test_arena",
        "create_dex_fighter",
        "create_barbarian_hero",
        "create_session",
        "delete_session",
        "http_exception_handler",
        "lifespan",
        "create_mapeditor_map",
        "delete_mapeditor_object",
        "delete_mapeditor_save",
        "get_combat_log",
        "get_encounter",
        "get_entities",
        "get_entity",
        "get_grid",
        "get_game_status",
        "get_mapeditor_catalog",
        "get_mapeditor_light",
        "get_mapeditor_map",
        "get_mapeditor_save",
        "get_mapeditor_visibility",
        "get_mapeditor_walkability",
        "get_simulation_status",
        "get_spell_catalog",
        "get_state",
        "get_tile_info",
        "get_visibility",
        "get_session_entities",
        "join_game",
        "list_mapeditor_saves",
        "load_mapeditor_save",
        "patch_mapeditor_tiles",
        "pause_simulation",
        "ping_session",
        "place_mapeditor_object",
        "reset_simulation",
        "resume_simulation",
        "root",
        "run_combat_loop",
        "save_mapeditor_map",
        "set_turn_delay",
        "start_simulation",
        "step_simulation",
        "timing_middleware",
        "unhandled_exception_handler",
        "validate_session_action",
    },
}
EVENT_SERVER_GOOGLE_DOCSTRING_CLASSES = {
    ROOT / "server" / "event_server.py": {
        "EventMonitor",
        "SimulationState",
    },
}
EVENT_SERVER_GOOGLE_DOCSTRING_FUNCTIONS = {
    ROOT / "server" / "event_server.py": {
        "_api_http_exception",
        "_entity_lookup_exception",
        "_equipment_context",
        "_equipment_http_exception",
        "_equipment_slot_map",
        "_event_filter_http_exception",
        "_get_floor_object_state",
        "_grid_state_context",
        "_handler_http_exception",
        "_known_entity_summaries",
        "_mapeditor_context",
        "_mapeditor_http_exception",
        "_resolve_entity_or_raise",
        "_serialize_entity_handlers",
        "_session_context",
        "_session_http_exception",
        "_simulation_context",
        "_simulation_http_exception",
        "action_cursor_fields",
        "advance_encounter",
        "build_session_status",
        "setup_combat",
        "setup_arena_combat",
        "setup_aoe_test_arena",
        "create_dex_fighter",
        "create_barbarian_hero",
        "create_session",
        "delete_session",
        "http_exception_handler",
        "lifespan",
        "create_mapeditor_map",
        "delete_mapeditor_object",
        "delete_mapeditor_save",
        "get_combat_log",
        "get_encounter",
        "get_entities",
        "get_entity",
        "get_grid",
        "get_game_status",
        "get_mapeditor_catalog",
        "get_mapeditor_light",
        "get_mapeditor_map",
        "get_mapeditor_save",
        "get_mapeditor_visibility",
        "get_mapeditor_walkability",
        "get_simulation_status",
        "get_spell_catalog",
        "get_state",
        "get_tile_info",
        "get_visibility",
        "get_session_entities",
        "join_game",
        "list_mapeditor_saves",
        "load_mapeditor_save",
        "patch_mapeditor_tiles",
        "pause_simulation",
        "ping_session",
        "place_mapeditor_object",
        "reset_simulation",
        "resume_simulation",
        "root",
        "run_combat_loop",
        "save_mapeditor_map",
        "set_turn_delay",
        "start_simulation",
        "step_simulation",
        "timing_middleware",
        "unhandled_exception_handler",
        "validate_session_action",
    },
}
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
CONTROLLER_MODELS = {
    ROOT / "dnd" / "controller.py": {
        "TurnContext",
        "Controller",
        "PassController",
        "HumanController",
        "CodexController",
        "ExternalAIController",
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
    ROOT / "dnd" / "classes" / "fighter_factory.py": {"FighterConfig"},
    ROOT / "dnd" / "classes" / "barbarian_factory.py": {"BarbarianConfig"},
    ROOT / "dnd" / "classes" / "sorcerer_factory.py": {"SorcererConfig"},
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
    ROOT / "dnd" / "classes" / "fighter_factory.py": {"FighterConfig"},
    ROOT / "dnd" / "classes" / "barbarian_factory.py": {"BarbarianConfig"},
    ROOT / "dnd" / "classes" / "sorcerer_factory.py": {"SorcererConfig"},
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
        "APIAppearance",
        "APICombatant",
        "APICurrentTurn",
        "APIEntityFull",
        "APIEntitySummary",
        "APIEncounter",
        "APIEquipmentOverview",
        "APIEquipmentSlot",
        "APIFloorObject",
        "APIGameState",
        "APIGrid",
        "APIItemSummary",
        "APISimulationStatus",
        "APITile",
        "AttackRequest",
        "CombatLogHistoryResponse",
        "ControlledEntitiesResponse",
        "CreateSessionRequest",
        "CreateSessionResponse",
        "EntityActionRequest",
        "EventHistoryResponse",
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
        "MoveRequest",
        "PositionActionRequest",
        "SelfActionRequest",
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
SERVER_API_GOOGLE_DOCSTRING_CLASSES = {
    ROOT / "server" / "api_models.py": {
        "ActionResult",
        "AdvanceEncounterResult",
        "AoEPreviewResult",
        "APIAppearance",
        "APICombatant",
        "APICurrentTurn",
        "APIEntityFull",
        "APIEntitySummary",
        "APIEncounter",
        "APIEquipmentOverview",
        "APIEquipmentSlot",
        "APIFloorObject",
        "APIGameState",
        "APIGrid",
        "APIItemSummary",
        "APISimulationStatus",
        "APITile",
        "AttackRequest",
        "CombatLogHistoryResponse",
        "ControlledEntitiesResponse",
        "CreateSessionRequest",
        "CreateSessionResponse",
        "EntityActionRequest",
        "EventHistoryResponse",
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
        "MoveRequest",
        "PositionActionRequest",
        "SelfActionRequest",
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
RULE_RELATIONSHIP_LABELS = [
    "SRD-aligned",
    "Engine adaptation",
    "Not implemented",
    "Engine extension",
]
LOCAL_REFERENCE_PREFIXES = (
    "cli/",
    "dnd/",
    "engine_book/",
    "examples/",
    "interactive_ruleset/",
    "server/",
    "tests/",
)


def read_text(path: Path) -> str:
    """Read repository text with a consistent encoding."""
    return path.read_text(encoding="utf-8")


def markdown_section(text: str, heading: str) -> str:
    """Return a markdown section body starting at a level-two heading."""
    start = text.find(heading)
    if start == -1:
        return ""

    end = text.find("\n## ", start + 1)
    return text[start:end if end != -1 else len(text)]


def local_backtick_references(text: str) -> list[str]:
    """Return backticked local paths or globs from markdown text."""
    references: list[str] = []

    for match in re.finditer(r"`([^`]+)`", text):
        value = match.group(1)
        if value.startswith(LOCAL_REFERENCE_PREFIXES):
            references.append(value)

    return references


def local_reference_exists(reference: str) -> bool:
    """Return whether a local backticked path or glob resolves in the repo."""
    if "*" in reference:
        return any(ROOT.glob(reference))

    normalized = reference.rstrip("/")
    return (ROOT / normalized).exists()


def collect_engine_book_test_functions() -> dict[str, set[str]]:
    """Return executable engine-book test functions by pytest filename."""
    functions_by_file: dict[str, set[str]] = {}

    for test_path in sorted((ROOT / "tests" / "engine_book").glob("test_chapter_*.py")):
        text = read_text(test_path)
        functions_by_file[test_path.name] = set(
            re.findall(r"^def (test_eb_\d{2}_\d{3}_[a-zA-Z0-9_]+)\(", text, re.MULTILINE)
        )

    return functions_by_file


def is_main_guard(test: ast.expr) -> bool:
    """Return whether an AST expression is an executable script guard."""
    return (
        isinstance(test, ast.Compare)
        and isinstance(test.left, ast.Name)
        and test.left.id == "__name__"
        and len(test.ops) == 1
        and isinstance(test.ops[0], ast.Eq)
        and len(test.comparators) == 1
        and isinstance(test.comparators[0], ast.Constant)
        and test.comparators[0].value == "__main__"
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


def named_top_level_nodes(
    path: Path,
    names: set[str],
) -> dict[str, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef]:
    """Return top-level classes/functions by name from a Python file."""
    tree = ast.parse(read_text(path))
    nodes: dict[str, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef] = {}

    for node in tree.body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names:
            nodes[node.name] = node

    return nodes


def collect_engine_book_test_ranges() -> dict[int, tuple[int, int, str]]:
    """Return chapter example ranges from executable engine-book tests."""
    ranges: dict[int, tuple[int, int, str]] = {}

    for test_path in sorted((ROOT / "tests" / "engine_book").glob("test_chapter_*.py")):
        text = read_text(test_path)
        ids = [
            (int(match.group(1)), int(match.group(2)))
            for match in re.finditer(r"^def test_eb_(\d{2})_(\d{3})_", text, re.MULTILINE)
        ]
        if not ids:
            continue

        chapters = {chapter for chapter, _ in ids}
        assert len(chapters) == 1, f"Mixed EB chapter IDs in {test_path.name}: {chapters}"

        chapter = chapters.pop()
        numbers = [number for _, number in ids]
        ranges[chapter] = (min(numbers), max(numbers), test_path.name)

    return ranges


def test_engine_book_required_files_exist() -> None:
    """The book has the required root files and bottom-up note files."""
    required_root_files = [
        ENGINE_BOOK / "goal.md",
        ENGINE_BOOK / "outline.md",
        PARITY_MATRIX,
        ENGINE_BOOK / "glossary.md",
    ]

    for path in required_root_files:
        assert path.exists(), f"Missing required engine_book file: {path}"

    chapter_numbers = {
        int(match.group(1))
        for path in NOTES.glob("*.md")
        if (match := re.match(r"(\d{2})_", path.name))
    }
    assert set(range(1, 19)) <= chapter_numbers


def test_every_engine_book_test_function_has_a_parity_matrix_row() -> None:
    """Every executable EB pytest function is represented in the parity matrix."""
    matrix = read_text(PARITY_MATRIX)
    functions_by_file = collect_engine_book_test_functions()
    missing: list[str] = []

    for test_filename, function_names in sorted(functions_by_file.items()):
        for function_name in sorted(function_names):
            example_id = function_name.removeprefix("test_").split("_", 3)
            eb_id = f"{example_id[0].upper()}-{example_id[1]}-{example_id[2]}"
            if function_name not in matrix or eb_id not in matrix:
                missing.append(f"{test_filename}::{function_name}")

    assert not missing, "Missing parity rows:\n" + "\n".join(missing)


def test_parity_matrix_rows_reference_existing_engine_book_tests() -> None:
    """Parity rows that cite engine-book tests should point to live tests."""
    functions_by_file = collect_engine_book_test_functions()
    stale: list[str] = []

    for line in read_text(PARITY_MATRIX).splitlines():
        if not line.startswith("| EB-"):
            continue

        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 5:
            stale.append(f"Malformed parity row: {line}")
            continue

        test_path = cells[3].strip("`")
        function_name = cells[4].strip("`")
        if not test_path.startswith("tests/engine_book/test_chapter_"):
            continue

        test_filename = Path(test_path).name
        if test_filename not in functions_by_file:
            stale.append(f"{test_path}::{function_name} references missing test file")
        elif function_name not in functions_by_file[test_filename]:
            stale.append(f"{test_path}::{function_name} references missing function")

    assert not stale, "Stale parity rows:\n" + "\n".join(stale)


def test_no_engine_book_tests_remain_in_examples() -> None:
    """Engine-book tests live in tests/engine_book, not examples."""
    stale_examples = sorted((ROOT / "examples").glob("test_engine_book_*.py"))
    assert not stale_examples, "Engine-book tests still in examples:\n" + "\n".join(str(path) for path in stale_examples)


def test_outline_book_example_ranges_match_executable_tests() -> None:
    """Outline chapter summaries should not drift behind executable EB tests."""
    outline = read_text(OUTLINE)
    test_ranges = collect_engine_book_test_ranges()
    missing_or_stale: list[str] = []

    for chapter, (first, last, filename) in sorted(test_ranges.items()):
        expected = (first, last)
        range_lines = [
            line
            for line in outline.splitlines()
            if f"`tests/engine_book/{filename}`" in line and f"EB-{chapter:02d}-" in line
        ]
        parsed_ranges = []
        for line in range_lines:
            match = re.search(
                rf"EB-{chapter:02d}-(\d{{3}}) through EB-{chapter:02d}-(\d{{3}})",
                line,
            )
            if match:
                parsed_ranges.append((int(match.group(1)), int(match.group(2))))

        if parsed_ranges != [expected]:
            expected_text = f"EB-{chapter:02d}-{first:03d} through EB-{chapter:02d}-{last:03d}"
            found_text = ", ".join(
                f"EB-{chapter:02d}-{start:03d} through EB-{chapter:02d}-{end:03d}"
                for start, end in parsed_ranges
            ) or "no range"
            missing_or_stale.append(f"Chapter {chapter:02d} {filename}: expected {expected_text}; found {found_text}")

    assert not missing_or_stale, "Stale outline EB ranges:\n" + "\n".join(missing_or_stale)


def test_chapter_matrix_has_no_tbd_or_missing_for_written_chapters() -> None:
    """Written chapter rows should not advertise missing parity in the matrix."""
    matrix = read_text(PARITY_MATRIX)
    chapter_rows = [
        line for line in matrix.splitlines()
        if re.match(r"\| \d{2}\. ", line)
    ]
    assert len(chapter_rows) >= 18

    bad_rows = [
        line for line in chapter_rows
        if "TBD" in line or "| missing |" in line or "| Not started |" in line
    ]
    assert not bad_rows, "Incomplete chapter rows:\n" + "\n".join(bad_rows)


def test_written_chapters_keep_required_contract_sections() -> None:
    """Each written chapter should keep source, rules, parity, and hygiene sections."""
    missing: list[str] = []
    chapter_paths = sorted(CHAPTERS.glob("*.md"))
    if not chapter_paths:
        return

    for path in chapter_paths:
        text = read_text(path)
        required_headings = [
            "## Purpose",
            "## Source Files Studied",
            "## Rules Relationship",
        ]

        for heading in required_headings:
            if heading not in text:
                missing.append(f"{path.name}: missing {heading}")

        if "Parity test:" not in text and "Parity tests:" not in text and "Coverage Status" not in text and "Coverage Added" not in text:
            missing.append(f"{path.name}: missing parity coverage references")

        if "Hygiene" not in text and "Documentation Hygiene" not in text:
            missing.append(f"{path.name}: missing documentation hygiene notes")

    assert not missing, "Chapter contract gaps:\n" + "\n".join(missing)


def test_written_chapter_source_and_rules_references_are_valid() -> None:
    """Chapter source and rules sections should cite valid local evidence."""
    failures: list[str] = []
    chapter_paths = sorted(CHAPTERS.glob("*.md"))
    if not chapter_paths:
        return

    for path in chapter_paths:
        text = read_text(path)
        source_section = markdown_section(text, "## Source Files Studied")
        rule_section = markdown_section(text, "## Rules Relationship")

        source_references = local_backtick_references(source_section)
        if not source_references:
            failures.append(f"{path.name}: source section has no local path references")

        for reference in source_references:
            if not local_reference_exists(reference):
                failures.append(f"{path.name}: source reference does not resolve: {reference}")

        if not any(label in rule_section for label in RULE_RELATIONSHIP_LABELS):
            failures.append(f"{path.name}: rules section lacks required relationship label")

        for reference in local_backtick_references(rule_section):
            if reference.startswith("interactive_ruleset/") and not local_reference_exists(reference):
                failures.append(f"{path.name}: SRD reference does not resolve: {reference}")

    assert not failures, "Chapter reference gaps:\n" + "\n".join(failures)


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


def test_controller_models_use_described_pydantic_fields() -> None:
    """Cleaned controller models should expose described Pydantic fields."""
    failures: list[str] = []

    for path, class_names in CONTROLLER_MODELS.items():
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

    assert not failures, "Controller metadata gaps:\n" + "\n".join(failures)


def test_controller_models_use_google_style_docstrings() -> None:
    """Guard cleaned controller model docstrings against terse regressions."""
    failures: list[str] = []

    for path, class_names in CONTROLLER_MODELS.items():
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

    assert not failures, "Controller docstring gaps:\n" + "\n".join(failures)


def test_controller_module_has_no_inline_comments() -> None:
    """The cleaned controller module should not reintroduce code comments."""
    failures: list[str] = []

    for path in CONTROLLER_MODELS:
        text = read_text(path)
        for token in tokenize.generate_tokens(io.StringIO(text).readline):
            if token.type == tokenize.COMMENT:
                failures.append(f"{path.relative_to(ROOT)}:{token.start[0]} has inline comment")

    assert not failures, "Controller comment regressions:\n" + "\n".join(failures)


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


def test_event_server_cleaned_nodes_do_not_use_print_debugging() -> None:
    """Guard cleaned event-server nodes against print-based debugging."""
    failures: list[str] = []

    for path, node_names in EVENT_SERVER_CLEAN_NODES.items():
        nodes = named_top_level_nodes(path, node_names)

        missing_nodes = sorted(node_names - set(nodes))
        for node_name in missing_nodes:
            failures.append(f"{path.relative_to(ROOT)}::{node_name} missing")

        for node_name, node in sorted(nodes.items()):
            for child in ast.walk(node):
                if (
                    isinstance(child, ast.Call)
                    and isinstance(child.func, ast.Name)
                    and child.func.id == "print"
                ):
                    failures.append(f"{path.relative_to(ROOT)}::{node_name} uses print() at line {child.lineno}")

    assert not failures, "Event-server print debugging regressions:\n" + "\n".join(failures)


def test_event_server_cleaned_nodes_have_no_inline_comments() -> None:
    """Guard cleaned event-server nodes against reintroduced code comments."""
    failures: list[str] = []

    for path, node_names in EVENT_SERVER_CLEAN_NODES.items():
        nodes = named_top_level_nodes(path, node_names)
        spans = [
            (node_name, node.lineno, node.end_lineno or node.lineno)
            for node_name, node in nodes.items()
        ]

        text = read_text(path)
        for token in tokenize.generate_tokens(io.StringIO(text).readline):
            if token.type != tokenize.COMMENT:
                continue

            for node_name, start, end in spans:
                if start <= token.start[0] <= end:
                    failures.append(f"{path.relative_to(ROOT)}::{node_name} line {token.start[0]} has inline comment")

    assert not failures, "Event-server comment regressions:\n" + "\n".join(failures)


def test_event_server_cleaned_classes_use_google_style_docstrings() -> None:
    """Guard cleaned event-server state class docstrings."""
    failures: list[str] = []

    for path, class_names in EVENT_SERVER_GOOGLE_DOCSTRING_CLASSES.items():
        nodes = named_top_level_nodes(path, class_names)

        missing_classes = sorted(class_names - set(nodes))
        for class_name in missing_classes:
            failures.append(f"{path.relative_to(ROOT)}::{class_name} missing")

        for class_name, node in sorted(nodes.items()):
            if not isinstance(node, ast.ClassDef):
                failures.append(f"{path.relative_to(ROOT)}::{class_name} is not a class")
                continue

            docstring = ast.get_docstring(node) or ""
            if "\n\nAttributes:\n" not in docstring:
                failures.append(f"{path.relative_to(ROOT)}::{class_name} lacks Google-style Attributes block")

    assert not failures, "Event-server docstring regressions:\n" + "\n".join(failures)


def test_event_server_cleaned_functions_use_google_style_docstrings() -> None:
    """Guard cleaned event-server setup function docstrings."""
    failures: list[str] = []

    for path, function_names in EVENT_SERVER_GOOGLE_DOCSTRING_FUNCTIONS.items():
        nodes = named_top_level_nodes(path, function_names)

        missing_functions = sorted(function_names - set(nodes))
        for function_name in missing_functions:
            failures.append(f"{path.relative_to(ROOT)}::{function_name} missing")

        for function_name, node in sorted(nodes.items()):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                failures.append(f"{path.relative_to(ROOT)}::{function_name} is not a function")
                continue

            docstring = ast.get_docstring(node) or ""
            public_arg_count = len([arg for arg in node.args.args if arg.arg != "self"])
            if public_arg_count and "\n\nArgs:\n" not in docstring:
                failures.append(f"{path.relative_to(ROOT)}::{function_name} lacks Google-style Args block")
            if "\n\nReturns:\n" not in docstring and "\n\nYields:\n" not in docstring:
                failures.append(f"{path.relative_to(ROOT)}::{function_name} lacks Google-style Returns/Yields block")

    assert not failures, "Event-server function docstring regressions:\n" + "\n".join(failures)


def test_goal_records_uv_pytest_parity_requirement() -> None:
    """The goal file preserves the user's uv-driven pytest requirement."""
    goal = read_text(ENGINE_BOOK / "goal.md")

    assert "uv" in goal
    assert "tests/engine_book/" in goal
    assert "1:1 parity" in goal


def test_pyproject_defines_uv_pytest_contract() -> None:
    """The repository exposes engine-book parity through uv-driven pytest."""
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
