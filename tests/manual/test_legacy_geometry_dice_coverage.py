"""Active contracts for displaced pure-geometry and dice-processor examples.

The archived scripts remain useful as historical oracles, but neither script is
collected by pytest.  This module gives every named archived case an explicit
active selector and replaces stochastic loops with deterministic assertions.
"""

from dataclasses import dataclass
from typing import Literal
from uuid import uuid4

import pytest

from dnd.classes.fighter import create_modified_dice_roll
from dnd.types.rolls import AttackOutcome, RollType
from dnd.core.dice import DiceRoll
from dnd.core.geometry import (
    bresenham_line,
    circle_positions,
    cone_positions,
    line_positions,
    rectangle_positions,
)
from dnd.types.rolls import AdvantageStatus, AutoHitStatus, CriticalStatus


THIS_FILE = "tests/manual/test_legacy_geometry_dice_coverage.py"

CIRCLE_SELECTOR = f"{THIS_FILE}::test_circle_geometry_contract"
BRESENHAM_SELECTOR = f"{THIS_FILE}::test_bresenham_geometry_contract"
WIDE_LINE_SELECTOR = f"{THIS_FILE}::test_widened_line_geometry_contract"
CONE_SELECTOR = f"{THIS_FILE}::test_oriented_cone_geometry_contract"
RECTANGLE_SELECTOR = f"{THIS_FILE}::test_rectangle_geometry_contract"


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

GEOMETRY_LEGACY_CASES = {
    case: LegacyCoverage(
        status="active",
        selector=selector,
        rationale="Restored as an exact deterministic geometry contract.",
    )
    for case, selector in GEOMETRY_LEGACY_SELECTORS.items()
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


def test_geometry_manifest_accounts_for_retained_cases() -> None:
    """Every retained geometry case has one explicit active selector."""
    assert len(GEOMETRY_LEGACY_CASES) == 14
    for case, row in GEOMETRY_LEGACY_CASES.items():
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
