from collections import Counter

import pytest

from ai.evaluation.config_ladder.contracts import RatedOutcome, StrengthObservation
from ai.evaluation.config_ladder.online_elo import (
    audit_elo_order_sensitivity,
    build_provisional_paired_elo,
)
from ai.evaluation.config_ladder.uncertainty import (
    bootstrap_configuration_strength,
    iter_paired_cluster_bootstrap_samples,
)


def test_provisional_elo_updates_complete_pairs_in_canonical_order() -> None:
    observations = [
        *_pair("block-z", RatedOutcome.MONSTER_WIN, RatedOutcome.MONSTER_WIN),
        *_pair("block-a", RatedOutcome.HERO_WIN, RatedOutcome.HERO_WIN),
    ]

    result = build_provisional_paired_elo(observations)
    reversed_result = build_provisional_paired_elo(list(reversed(observations)))

    assert [row.pair_block_id for row in result.updates] == ["block-a", "block-z"]
    assert result == reversed_result
    assert result.completed_pair_block_count == 2
    assert result.updates[0].hero_score == 1.0
    assert result.updates[0].hero_rating_after == 1016.0
    assert result.updates[0].monster_rating_after == 984.0
    assert result.hero_standings[0].matches == 4
    assert result.hero_standings[0].pair_blocks == 2


def test_provisional_elo_rejects_incomplete_or_mismatched_pairs() -> None:
    incomplete = _pair("block-a", RatedOutcome.HERO_WIN, RatedOutcome.MONSTER_WIN)[:1]
    mismatched = list(_pair("block-b", RatedOutcome.HERO_WIN, RatedOutcome.MONSTER_WIN))
    mismatched[1] = mismatched[1].model_copy(update={"monster_configuration_id": "monsters.other"})

    with pytest.raises(ValueError, match="exactly two observations"):
        build_provisional_paired_elo(list(incomplete))
    with pytest.raises(ValueError, match="disagrees on participant or context identity"):
        build_provisional_paired_elo(mismatched)


def test_order_sensitivity_audit_is_seeded_and_keeps_pairs_atomic() -> None:
    observations = []
    for index, outcome in enumerate((
        RatedOutcome.HERO_WIN,
        RatedOutcome.HERO_WIN,
        RatedOutcome.HERO_WIN,
        RatedOutcome.MONSTER_WIN,
        RatedOutcome.MONSTER_WIN,
        RatedOutcome.MONSTER_WIN,
    )):
        observations.extend(_pair(f"block-{index}", outcome, outcome))

    first = audit_elo_order_sensitivity(observations, permutation_count=40, random_seed=701)
    second = audit_elo_order_sensitivity(list(reversed(observations)), permutation_count=40, random_seed=701)

    assert first == second
    assert first.random_seed == 701
    assert first.permutation_count == 40
    assert first.maximum_rating_range > 0
    assert all(row.minimum_rating <= row.canonical_rating <= row.maximum_rating for row in first.participants)


def test_paired_cluster_samples_preserve_both_openings_and_seed() -> None:
    observations = [
        row
        for index in range(4)
        for row in _pair(
            f"block-{index}",
            RatedOutcome.HERO_WIN if index % 2 == 0 else RatedOutcome.MONSTER_WIN,
            RatedOutcome.MONSTER_WIN if index % 2 == 0 else RatedOutcome.HERO_WIN,
        )
    ]

    first = list(iter_paired_cluster_bootstrap_samples(observations, replicate_count=8, random_seed=77))
    second = list(iter_paired_cluster_bootstrap_samples(list(reversed(observations)), replicate_count=8, random_seed=77))

    assert [[row.match_id for row in sample] for sample in first] == [
        [row.match_id for row in sample]
        for sample in second
    ]
    assert all(len(sample) == len(observations) for sample in first)
    for sample in first:
        by_block_and_opening = Counter((row.pair_block_id, row.opening_treatment) for row in sample)
        for block_id in {row.pair_block_id for row in sample}:
            assert by_block_and_opening[(block_id, "hero_first")] == by_block_and_opening[(block_id, "monster_first")]


def test_paired_bootstrap_reports_deterministic_rank_intervals_and_top_n() -> None:
    observations = _connected_strength_fixture()

    first = bootstrap_configuration_strength(
        observations,
        replicate_count=24,
        random_seed=1701,
        top_n=1,
        regularization=0.25,
    )
    second = bootstrap_configuration_strength(
        list(reversed(observations)),
        replicate_count=24,
        random_seed=1701,
        top_n=1,
        regularization=0.25,
    )

    assert first == second
    assert first.random_seed == 1701
    assert first.successful_replicates == 24
    assert first.success_rate == 1.0
    heroes = {row.configuration_id: row for row in first.hero_intervals}
    monsters = {row.configuration_id: row for row in first.monster_intervals}
    assert heroes["hero.strong"].point_estimate_elo > heroes["hero.weak"].point_estimate_elo
    assert monsters["monsters.strong"].point_estimate_elo > monsters["monsters.weak"].point_estimate_elo
    assert heroes["hero.strong"].top_n_probability > heroes["hero.weak"].top_n_probability
    assert all(1 <= row.rank_lower_95 <= row.rank_upper_95 <= 2 for row in first.hero_intervals)
    assert all(0.0 <= row.top_n_probability <= 1.0 for row in (*first.hero_intervals, *first.monster_intervals))


def _pair(
    block_id: str,
    hero_first_outcome: RatedOutcome,
    monster_first_outcome: RatedOutcome,
    *,
    hero_id: str = "hero.a",
    monster_id: str = "monsters.a",
) -> tuple[StrengthObservation, StrengthObservation]:
    shared = {
        "pair_block_id": block_id,
        "hero_configuration_id": hero_id,
        "monster_configuration_id": monster_id,
        "battlefield_id": "field.open",
        "deployment_id": "deployment.default",
    }
    return (
        StrengthObservation(
            match_id=f"{block_id}-hero-first",
            opening_treatment="hero_first",
            outcome=hero_first_outcome,
            **shared,
        ),
        StrengthObservation(
            match_id=f"{block_id}-monster-first",
            opening_treatment="monster_first",
            outcome=monster_first_outcome,
            **shared,
        ),
    )


def _connected_strength_fixture() -> list[StrengthObservation]:
    observations: list[StrengthObservation] = []
    hero_ids = ("hero.strong", "hero.weak")
    monster_ids = ("monsters.weak", "monsters.strong")
    hero_win_blocks = {
        ("hero.strong", "monsters.weak"): 8,
        ("hero.strong", "monsters.strong"): 6,
        ("hero.weak", "monsters.weak"): 3,
        ("hero.weak", "monsters.strong"): 0,
    }
    for hero_id in hero_ids:
        for monster_id in monster_ids:
            for index in range(8):
                outcome = (
                    RatedOutcome.HERO_WIN
                    if index < hero_win_blocks[(hero_id, monster_id)]
                    else RatedOutcome.MONSTER_WIN
                )
                observations.extend(_pair(
                    f"{hero_id}-{monster_id}-{index}",
                    outcome,
                    outcome,
                    hero_id=hero_id,
                    monster_id=monster_id,
                ))
    return observations
