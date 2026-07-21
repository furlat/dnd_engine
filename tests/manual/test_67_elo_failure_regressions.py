"""Real-combat regressions discovered by the first complete Elo matrix."""

import pytest

from ai.evaluation.artifacts import audit_external_selfplay_subjectivity
from ai.external_selfplay import run_external_selfplay


@pytest.mark.parametrize(
    ("arena_id", "random_seed", "hero_first"),
    [
        ("item_resource_gauntlet", 5, False),
        ("item_resource_gauntlet", 10, True),
        ("srd_elite_mercenary_contract", 1, False),
        ("srd_elite_mercenary_contract", 3, True),
        ("srd_elite_mercenary_contract", 8, True),
        ("srd_elite_mercenary_contract", 9, True),
        ("forced_movement_hazard_bridge", 1, False),
    ],
)
def test_first_complete_matrix_command_cap_rows_now_finish(
    arena_id: str,
    random_seed: int,
    hero_first: bool,
) -> None:
    """Every exact v30 command-cap row must end under the original bound."""
    result = run_external_selfplay(
        arena_id,
        max_commands=240,
        hero_first=hero_first,
        random_seed=random_seed,
    )
    subjectivity = audit_external_selfplay_subjectivity(result)

    assert result.status == "encounter_ended"
    assert result.final_state == "ended"
    assert result.command_count < 240
    assert subjectivity.status == "passed"
    assert subjectivity.violations == []
