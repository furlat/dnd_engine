"""Active contracts for displaced pure-geometry and dice-processor examples.

The archived scripts remain useful as historical oracles, but neither script is
collected by pytest.  This module gives every named archived case an explicit
active selector and replaces stochastic loops with deterministic assertions.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal
from uuid import uuid4

import pytest

from dnd.classes import dice_processor_utils
from dnd.classes.dice_processor_utils import (
    ceiling_results,
    floor_results,
    maximize_all,
    minimize_all,
    reroll_below_and_substitute,
    reroll_below_keep_best,
    reroll_ones_once,
    set_all_to,
    substitute_value,
)
from dnd.classes.fighter import create_modified_dice_roll
from dnd.core.dice import AttackOutcome, DiceRoll, RollType
from dnd.core.geometry import (
    bresenham_line,
    circle_positions,
    cone_positions,
    line_positions,
    rectangle_positions,
)
from dnd.core.values import AdvantageStatus, AutoHitStatus, CriticalStatus


THIS_FILE = "tests/manual/test_legacy_geometry_dice_coverage.py"

CIRCLE_SELECTOR = f"{THIS_FILE}::test_circle_geometry_contract"
BRESENHAM_SELECTOR = f"{THIS_FILE}::test_bresenham_geometry_contract"
WIDE_LINE_SELECTOR = f"{THIS_FILE}::test_widened_line_geometry_contract"
CONE_SELECTOR = f"{THIS_FILE}::test_oriented_cone_geometry_contract"
RECTANGLE_SELECTOR = f"{THIS_FILE}::test_rectangle_geometry_contract"
MODIFIED_ROLL_SELECTOR = (
    f"{THIS_FILE}::test_create_modified_roll_preserves_original_and_rules_metadata"
)
STATIC_PROCESSOR_SELECTOR = (
    f"{THIS_FILE}::test_static_dice_processors_replace_only_results"
)
REROLL_SELECTOR = (
    f"{THIS_FILE}::test_reroll_processors_are_deterministic_and_touch_only_eligible_dice"
)
CHAIN_SELECTOR = f"{THIS_FILE}::test_chained_processors_preserve_ordered_semantics"
METADATA_SELECTOR = f"{THIS_FILE}::test_all_processors_preserve_identity_metadata"


CoverageStatus = Literal["active", "strengthened", "retired", "stale", "unresolved"]


@dataclass(frozen=True)
class LegacyCoverage:
    """One archived case's current disposition."""

    status: CoverageStatus
    selector: str
    rationale: str


GEOMETRY_LEGACY_SELECTORS: dict[str, str] = {
    "test_circle_radius_2": CIRCLE_SELECTOR,
    "test_circle_exclude_center": CIRCLE_SELECTOR,
    "test_bresenham_straight": BRESENHAM_SELECTOR,
    "test_bresenham_vertical": BRESENHAM_SELECTOR,
    "test_bresenham_diagonal": BRESENHAM_SELECTOR,
    "test_bresenham_steep": BRESENHAM_SELECTOR,
    "test_line_width_1": WIDE_LINE_SELECTOR,
    "test_line_width_3": WIDE_LINE_SELECTOR,
    "test_cone_east": CONE_SELECTOR,
    "test_cone_north": CONE_SELECTOR,
    "test_cone_diagonal": CONE_SELECTOR,
    "test_rectangle_centered": RECTANGLE_SELECTOR,
    "test_rectangle_non_centered_east": RECTANGLE_SELECTOR,
    "test_rectangle_non_centered_north": RECTANGLE_SELECTOR,
}

DICE_PROCESSOR_LEGACY_SELECTORS: dict[str, str] = {
    "test_create_modified_dice_roll": MODIFIED_ROLL_SELECTOR,
    "test_maximize_all": STATIC_PROCESSOR_SELECTOR,
    "test_minimize_all": STATIC_PROCESSOR_SELECTOR,
    "test_set_all_to": STATIC_PROCESSOR_SELECTOR,
    "test_substitute_value": STATIC_PROCESSOR_SELECTOR,
    "test_floor_results": STATIC_PROCESSOR_SELECTOR,
    "test_ceiling_results": STATIC_PROCESSOR_SELECTOR,
    "test_reroll_below_and_substitute": REROLL_SELECTOR,
    "test_reroll_below_keep_best": REROLL_SELECTOR,
    "test_reroll_ones_once": REROLL_SELECTOR,
    "test_chained_processors": CHAIN_SELECTOR,
    "test_preserves_metadata": METADATA_SELECTOR,
}

GEOMETRY_LEGACY_CASES = {
    case: LegacyCoverage(
        status="active",
        selector=selector,
        rationale="Restored as an exact deterministic geometry contract.",
    )
    for case, selector in GEOMETRY_LEGACY_SELECTORS.items()
}

DICE_PROCESSOR_LEGACY_CASES = {
    case: LegacyCoverage(
        status="active",
        selector=selector,
        rationale="Restored as an exact deterministic immutable-roll contract.",
    )
    for case, selector in DICE_PROCESSOR_LEGACY_SELECTORS.items()
}


def make_roll(
    results: list[int],
    *,
    bonus: int = 2,
    outcome: AttackOutcome = AttackOutcome.HIT,
) -> DiceRoll:
    """Build one immutable damage-roll fixture with non-default metadata."""
    return DiceRoll(
        dice_uuid=uuid4(),
        roll_type=RollType.DAMAGE,
        results=results,
        total=sum(results) + bonus,
        bonus=bonus,
        advantage_status=AdvantageStatus.NONE,
        critical_status=CriticalStatus.NOCRIT,
        auto_hit_status=AutoHitStatus.NONE,
        source_entity_uuid=uuid4(),
        target_entity_uuid=uuid4(),
        attack_outcome=outcome,
    )


def test_geometry_and_dice_manifests_account_for_all_26_cases() -> None:
    """Every archived function has one explicit active pytest selector."""
    assert len(GEOMETRY_LEGACY_CASES) == 14
    assert len(DICE_PROCESSOR_LEGACY_CASES) == 12
    assert set(GEOMETRY_LEGACY_CASES).isdisjoint(DICE_PROCESSOR_LEGACY_CASES)
    for case, row in {
        **GEOMETRY_LEGACY_CASES,
        **DICE_PROCESSOR_LEGACY_CASES,
    }.items():
        assert case.startswith("test_")
        assert row.status == "active"
        assert row.selector.startswith("tests/") and "::test_" in row.selector
        assert row.rationale


def test_circle_geometry_contract() -> None:
    """A radius-two filled circle uses Euclidean distance and optional center."""
    expected = {
        (5, 3),
        (4, 4),
        (5, 4),
        (6, 4),
        (3, 5),
        (4, 5),
        (5, 5),
        (6, 5),
        (7, 5),
        (4, 6),
        (5, 6),
        (6, 6),
        (5, 7),
    }

    assert circle_positions((5, 5), 2) == expected
    assert circle_positions((5, 5), 2, include_center=False) == expected - {
        (5, 5)
    }


@pytest.mark.parametrize(
    ("start", "end", "expected"),
    (
        ((0, 0), (5, 0), [(0, 0), (1, 0), (2, 0), (3, 0), (4, 0), (5, 0)]),
        ((0, 0), (0, 4), [(0, 0), (0, 1), (0, 2), (0, 3), (0, 4)]),
        ((0, 0), (3, 3), [(0, 0), (1, 1), (2, 2), (3, 3)]),
        ((0, 0), (2, 5), [(0, 0), (0, 1), (1, 2), (1, 3), (2, 4), (2, 5)]),
    ),
    ids=("horizontal", "vertical", "diagonal", "steep"),
)
def test_bresenham_geometry_contract(
    start: tuple[int, int],
    end: tuple[int, int],
    expected: list[tuple[int, int]],
) -> None:
    """Bresenham rays remain ordered and inclusive for principal slopes."""
    assert bresenham_line(start, end) == expected


def test_widened_line_geometry_contract() -> None:
    """Line length and perpendicular width expansion have stable footprints."""
    assert line_positions((0, 0), (5, 0), length=5, width=1) == {
        (0, 0),
        (1, 0),
        (2, 0),
        (3, 0),
        (4, 0),
        (5, 0),
    }
    assert line_positions((0, 0), (5, 0), length=3, width=3) == {
        (x, y)
        for x in range(4)
        for y in (-1, 0, 1)
    }


def test_oriented_cone_geometry_contract() -> None:
    """Cardinal and diagonal cones point forward and always exclude the apex."""
    east = cone_positions((0, 0), (5, 0), length=3, angle_degrees=53)
    north = cone_positions((0, 0), (0, 5), length=3, angle_degrees=53)
    northeast = cone_positions((0, 0), (5, 5), length=3, angle_degrees=53)

    assert east == {(1, 0), (2, 0), (3, 0)}
    assert north == {(0, 1), (0, 2), (0, 3)}
    assert northeast == {(1, 1), (1, 2), (2, 1), (2, 2)}
    assert (0, 0) not in east | north | northeast
    assert (-1, 0) not in east
    assert (0, -1) not in north
    assert (-1, -1) not in northeast


def test_rectangle_geometry_contract() -> None:
    """Centered and directional square footprints retain their orientation."""
    centered = rectangle_positions((5, 5), size=3, centered=True)
    east = rectangle_positions(
        (0, 0),
        size=3,
        direction=(5, 0),
        centered=False,
    )
    north = rectangle_positions(
        (0, 0),
        size=3,
        direction=(0, 5),
        centered=False,
    )

    assert centered == {
        (x, y)
        for x in range(4, 7)
        for y in range(4, 7)
    }
    assert east == {(x, y) for x in range(3) for y in (-1, 0, 1)}
    assert north == {(x, y) for x in (-1, 0, 1) for y in range(3)}


def test_create_modified_roll_preserves_original_and_rules_metadata() -> None:
    """Result replacement creates a new value without corrupting causal metadata."""
    original = make_roll([1, 2, 5], bonus=2)

    modified = create_modified_dice_roll(original, [4, 6, 5])

    assert original.results == [1, 2, 5]
    assert original.total == 10
    assert modified.results == [4, 6, 5]
    assert modified.total == 17
    assert modified.roll_uuid != original.roll_uuid
    assert modified.dice_uuid == original.dice_uuid
    assert modified.bonus == original.bonus
    assert modified.roll_type == original.roll_type
    assert modified.advantage_status == original.advantage_status
    assert modified.critical_status == original.critical_status
    assert modified.auto_hit_status == original.auto_hit_status
    assert modified.source_entity_uuid == original.source_entity_uuid
    assert modified.target_entity_uuid == original.target_entity_uuid
    assert modified.attack_outcome == original.attack_outcome


@pytest.mark.parametrize(
    ("processor", "expected"),
    (
        (lambda roll: maximize_all(roll, 6), [6, 6, 6]),
        (minimize_all, [1, 1, 1]),
        (lambda roll: set_all_to(roll, 4), [4, 4, 4]),
        (lambda roll: substitute_value(roll, 1, 2), [2, 2, 5]),
        (lambda roll: floor_results(roll, 2), [2, 2, 5]),
        (lambda roll: ceiling_results(roll, 4), [1, 2, 4]),
    ),
    ids=("maximize", "minimize", "set", "substitute", "floor", "ceiling"),
)
def test_static_dice_processors_replace_only_results(
    processor: Callable[[DiceRoll], DiceRoll],
    expected: list[int],
) -> None:
    """Deterministic processors transform each die and recompute the total."""
    original = make_roll([1, 2, 5], bonus=3)

    modified = processor(original)

    assert modified.results == expected
    assert modified.total == sum(expected) + 3
    assert original.results == [1, 2, 5]
    assert original.total == 11


def test_reroll_processors_are_deterministic_and_touch_only_eligible_dice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rerolls consume one random face per eligible die with their stated policy."""
    queued = iter((6, 1, 2, 5, 1))

    def deterministic_randint(low: int, high: int) -> int:
        value = next(queued)
        assert low <= value <= high
        return value

    monkeypatch.setattr(dice_processor_utils.random, "randint", deterministic_randint)

    substitute = reroll_below_and_substitute(make_roll([1, 2, 5]), 2, 6)
    keep_best = reroll_below_keep_best(make_roll([1, 1, 4]), 1, 6)
    reroll_ones = reroll_ones_once(make_roll([1, 2, 3]), 6)

    assert substitute.results == [6, 1, 5]
    assert keep_best.results == [2, 5, 4]
    assert reroll_ones.results == [1, 2, 3]


def test_chained_processors_preserve_ordered_semantics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A mandatory low reroll followed by a floor applies in that order."""
    queued = iter((1, 6))
    monkeypatch.setattr(
        dice_processor_utils.random,
        "randint",
        lambda _low, _high: next(queued),
    )
    original = make_roll([1, 2, 4], bonus=0)

    rerolled = reroll_below_and_substitute(original, threshold=2, dice_size=6)
    floored = floor_results(rerolled, minimum=2)

    assert rerolled.results == [1, 6, 4]
    assert floored.results == [2, 6, 4]
    assert floored.total == 12


def test_all_processors_preserve_identity_metadata() -> None:
    """Every non-random processor preserves the original causal roll identity."""
    original = make_roll([1, 2, 3], bonus=5, outcome=AttackOutcome.CRIT)
    processors: tuple[Callable[[DiceRoll], DiceRoll], ...] = (
        lambda roll: maximize_all(roll, 6),
        minimize_all,
        lambda roll: set_all_to(roll, 4),
        lambda roll: substitute_value(roll, 1, 2),
        lambda roll: floor_results(roll, 2),
        lambda roll: ceiling_results(roll, 5),
    )

    for processor in processors:
        modified = processor(original)
        assert modified.dice_uuid == original.dice_uuid
        assert modified.source_entity_uuid == original.source_entity_uuid
        assert modified.target_entity_uuid == original.target_entity_uuid
        assert modified.bonus == original.bonus
        assert modified.roll_type == original.roll_type
        assert modified.advantage_status == original.advantage_status
        assert modified.critical_status == original.critical_status
        assert modified.auto_hit_status == original.auto_hit_status
        assert modified.attack_outcome == original.attack_outcome
