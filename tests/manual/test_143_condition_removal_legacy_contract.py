"""Reviewed replacement for the displaced condition-removal system suite."""

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from uuid import uuid4

import dnd.core.base_conditions as base_conditions_module
from dnd.classes.fighter import SecondWindFeature
from dnd.classes.rage import RageFeature
from dnd.core.gridmap import get_map
from dnd.entity import Entity, EntityConfig
from dnd.runtime_reset import reset_engine_runtime
from tests.engine_book.test_chapter_07_condition_lifecycle import (
    EngineBookMarkerCondition,
    reset_condition_state,
)


CoverageStatus = Literal["active", "strengthened", "stale"]


def reset_class_tutorial_state() -> None:
    """Reset the focused feature-cleanup fixture without a book dependency."""
    reset_engine_runtime(grid_size=(12, 6))


def create_class_actor(
    name: str,
    position: tuple[int, int],
) -> Entity:
    """Build the minimal actor required by feature-cleanup regressions."""
    return Entity.create(
        source_entity_uuid=uuid4(),
        name=name,
        config=EntityConfig(position=position, faction="heroes"),
    )


@dataclass(frozen=True)
class LegacyCoverage:
    """One archived removal case's reviewed replacement."""

    status: CoverageStatus
    selector: str
    rationale: str


THIS_FILE = "tests/manual/test_143_condition_removal_legacy_contract.py"
EB07_FILE = "tests/engine_book/test_chapter_07_condition_lifecycle.py"
BASIC_SELECTOR = (
    "tests/engine_book/test_chapter_08_standard_conditions.py::"
    "test_eb_08_012_standard_condition_removal_cleans_owned_state"
)
DIRECT_OWNERSHIP_SELECTOR = (
    "tests/engine_book/test_chapter_08_standard_conditions.py::"
    "test_eb_08_006_severe_conditions_own_direct_denial_transforms"
)
LINKED_SELECTOR = (
    f"{EB07_FILE}::test_eb_07_007_linked_conditions_clean_forward_and_notify_reverse"
)
DURATION_SELECTOR = (
    f"{EB07_FILE}::test_eb_07_009_entity_duration_advancement_expires_and_removes_condition"
)
UUID_SELECTOR = (
    "tests/engine_book/test_condition_transform_ownership.py::"
    "test_visual_access_remains_denied_until_every_owner_is_removed"
)
FEATURE_SELECTOR = (
    f"{THIS_FILE}::test_feature_condition_removal_cleans_actions_and_resources"
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
        "active",
        FEATURE_SELECTOR,
        "Rage feature removal unregisters both actions and its resource.",
    ),
    "test_custom_remove_hook_second_wind": LegacyCoverage(
        "active",
        FEATURE_SELECTOR,
        "Second Wind feature removal unregisters its action and resource.",
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


def test_feature_condition_removal_cleans_actions_and_resources() -> None:
    """Feature cleanup owns everything the feature registered."""
    reset_class_tutorial_state()
    barbarian = create_class_actor("Removal Barbarian", (1, 1))
    rage = RageFeature(
        source_entity_uuid=barbarian.uuid,
        target_entity_uuid=barbarian.uuid,
        rage_uses=2,
        rage_damage=2,
    )
    barbarian.add_condition(rage)
    assert barbarian.get_action_template("Rage") is not None
    assert barbarian.get_action_template("End Rage") is not None
    assert "rage" in barbarian.action_economy.resources

    barbarian.remove_condition_by_uuid(rage.uuid)

    assert barbarian.get_action_template("Rage") is None
    assert barbarian.get_action_template("End Rage") is None
    assert "rage" not in barbarian.action_economy.resources

    reset_class_tutorial_state()
    fighter = create_class_actor("Removal Fighter", (1, 1))
    second_wind = SecondWindFeature(
        source_entity_uuid=fighter.uuid,
        target_entity_uuid=fighter.uuid,
        fighter_level=5,
    )
    fighter.add_condition(second_wind)
    assert fighter.get_action_template("Second Wind") is not None
    assert "second_wind" in fighter.action_economy.resources

    fighter.remove_condition_by_uuid(second_wind.uuid)

    assert fighter.get_action_template("Second Wind") is None
    assert "second_wind" not in fighter.action_economy.resources


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
