"""Reviewed replacement for the displaced condition-removal system suite."""

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import dnd.core.base_conditions as base_conditions_module
from dnd.core.gridmap import get_map
from tests.engine.test_condition_lifecycle import (
    EngineBookMarkerCondition,
    reset_condition_state,
)


CoverageStatus = Literal["active", "strengthened", "stale"]


@dataclass(frozen=True)
class LegacyCoverage:
    """One archived removal case's reviewed replacement."""

    status: CoverageStatus
    selector: str
    rationale: str


THIS_FILE = "tests/manual/test_143_condition_removal_legacy_contract.py"
EB07_FILE = "tests/engine/test_condition_lifecycle.py"
BASIC_SELECTOR = (
    "tests/engine/test_standard_conditions.py::"
    "test_eb_08_012_standard_condition_removal_cleans_owned_state"
)
DIRECT_OWNERSHIP_SELECTOR = (
    "tests/engine/test_standard_conditions.py::"
    "test_eb_08_006_severe_conditions_own_direct_denial_transforms"
)
LINKED_SELECTOR = (
    f"{EB07_FILE}::test_eb_07_007_linked_conditions_clean_forward_and_notify_reverse"
)
DURATION_SELECTOR = (
    f"{EB07_FILE}::test_eb_07_009_entity_duration_advancement_expires_and_removes_condition"
)
UUID_SELECTOR = (
    "tests/engine/test_condition_transform_ownership.py::"
    "test_visual_access_remains_denied_until_every_owner_is_removed"
)
BARBARIAN_FEATURE_SELECTOR = (
    "tests/progression/test_barbarian_berserker_materialization.py::"
    "test_level_twenty_berserker_materializes_and_reverses_exactly"
)
FIGHTER_FEATURE_SELECTOR = (
    "tests/progression/test_fighter_champion_materialization.py::"
    "test_fighter_five_champion_materializes_and_reverses_exactly"
)
ARCHITECTURE_SELECTOR = (
    f"{THIS_FILE}::test_base_condition_cleanup_contains_no_hidden_late_import"
)
TILE_SELECTOR = (
    f"{THIS_FILE}::test_tile_uses_the_same_successful_condition_removal_lifecycle"
)


CONDITION_REMOVAL_LEGACY_CASES: dict[str, LegacyCoverage] = {
    "test_basic_condition_removal": LegacyCoverage(
        "strengthened",
        BASIC_SELECTOR,
        "Maintained coverage removes every standard condition and checks all owned state.",
    ),
    "test_sub_condition_removal": LegacyCoverage(
        "strengthened",
        DIRECT_OWNERSHIP_SELECTOR,
        "Paralyzed owns its neutral transforms directly, fabricates no Incapacitated child, and restores its gates on removal.",
    ),
    "test_nested_sub_conditions": LegacyCoverage(
        "strengthened",
        DIRECT_OWNERSHIP_SELECTOR,
        "Stunned fabricates no Incapacitated child and exact action, movement, save, and incoming-attack gates are restored on removal.",
    ),
    "test_external_condition_removal": LegacyCoverage(
        "strengthened",
        LINKED_SELECTOR,
        "Maintained coverage asserts both forward linked cleanup and reverse parent notification.",
    ),
    "test_duration_expiration": LegacyCoverage(
        "strengthened",
        DURATION_SELECTOR,
        "Maintained coverage verifies Entity-owned duration progression and exact removal.",
    ),
    "test_custom_remove_hook_rage": LegacyCoverage(
        "strengthened",
        BARBARIAN_FEATURE_SELECTOR,
        "Canonical character-composition removal reverses the exact Rage action/resource receipt.",
    ),
    "test_custom_remove_hook_second_wind": LegacyCoverage(
        "strengthened",
        FIGHTER_FEATURE_SELECTOR,
        "Canonical character-composition removal reverses the exact Second Wind action/resource receipt.",
    ),
    "test_no_late_imports_in_base_conditions": LegacyCoverage(
        "active",
        ARCHITECTURE_SELECTOR,
        "The architectural prohibition remains an executable AST assertion.",
    ),
    "test_remove_condition_by_uuid": LegacyCoverage(
        "strengthened",
        UUID_SELECTOR,
        "Maintained coverage uses identity removal with overlapping independent owners.",
    ),
    "test_tile_condition_removal": LegacyCoverage(
        "active",
        TILE_SELECTOR,
        "A successful tile condition follows the same BaseBlock identity cleanup.",
    ),
}


def test_condition_removal_manifest_accounts_for_all_10_cases() -> None:
    """Every archived condition-removal case has a reviewed disposition."""
    assert len(CONDITION_REMOVAL_LEGACY_CASES) == 10
    assert all(
        case.startswith("test_")
        and row.selector.startswith("tests/")
        and "::test_" in row.selector
        and row.rationale
        for case, row in CONDITION_REMOVAL_LEGACY_CASES.items()
    )


def test_base_condition_cleanup_contains_no_hidden_late_import() -> None:
    """BaseCondition cleanup must not conceal an upward dependency in a method."""
    module_path = Path(base_conditions_module.__file__)
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    base_condition = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "BaseCondition"
    )
    cleanup = next(
        node
        for node in base_condition.body
        if isinstance(node, ast.FunctionDef) and node.name == "cleanup_own_state"
    )

    assert not any(
        isinstance(node, (ast.Import, ast.ImportFrom))
        for node in ast.walk(cleanup)
    )


def test_tile_uses_the_same_successful_condition_removal_lifecycle() -> None:
    """Tile conditions index and clean by UUID without Entity coupling."""
    reset_condition_state()
    tile = get_map().get_tile(4, 4)
    assert tile is not None
    condition = EngineBookMarkerCondition(
        name="Tile Removal Marker",
        source_entity_uuid=tile.uuid,
        target_entity_uuid=tile.uuid,
    )
    completion = tile.add_condition(condition)

    assert completion is not None
    assert tile.active_conditions["Tile Removal Marker"] is condition
    assert tile.active_conditions_by_uuid[condition.uuid] is condition

    tile.remove_condition_by_uuid(condition.uuid)

    assert condition.applied is False
    assert "Tile Removal Marker" not in tile.active_conditions
    assert condition.uuid not in tile.active_conditions_by_uuid
