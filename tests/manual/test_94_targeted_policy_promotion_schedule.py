"""Targeted candidate-vs-baseline promotion schedule coverage."""

from __future__ import annotations

from ai.evaluation.promotion.catalog import TARGETED_POLICY_PROMOTION_MATCHUP_IDS
from ai.evaluation.promotion.experiment import (
    build_default_promotion_catalog,
    build_targeted_promotion_schedule,
)
from ai.evaluation.promotion.contracts import MatchupFamily


def test_targeted_promotion_schedule_is_balanced_and_pathology_focused() -> None:
    """The compact Elo panel keeps full four-treatment counterbalancing."""
    catalog = build_default_promotion_catalog(generated_at="2026-07-19T00:00:00+00:00")
    schedule = build_targeted_promotion_schedule(
        catalog,
        experiment_id="targeted-schedule-test",
        seeds=(1, 2),
        created_at="2026-07-19T00:00:00+00:00",
    )

    blocks = schedule.entries_by_block()
    assert len(schedule.entries) == len(TARGETED_POLICY_PROMOTION_MATCHUP_IDS) * 2 * 2 * 4
    assert len(blocks) == len(TARGETED_POLICY_PROMOTION_MATCHUP_IDS) * 2 * 2
    assert all(len(rows) == 4 for rows in blocks.values())
    assert all(
        {
            (row.opening_treatment, row.policy_assignment)
            for row in rows
        }
        == {
            ("side_a_first", "candidate_a"),
            ("side_a_first", "candidate_b"),
            ("side_b_first", "candidate_a"),
            ("side_b_first", "candidate_b"),
        }
        for rows in blocks.values()
    )
    assert {row.matchup_family for row in schedule.entries} >= {
        MatchupFamily.HERO_VS_MONSTER,
        MatchupFamily.MONSTER_VS_MONSTER,
    }
    tags = {tag for row in schedule.entries for tag in row.matchup_tags}
    assert {"sorcerer", "barbarian", "skeletons", "projectile-allocation", "srd"} <= tags
    assert {row.battlefield_id for row in schedule.entries} == {
        "battlefield.open_floor_bright",
        "battlefield.standard_hazards_closed",
    }
