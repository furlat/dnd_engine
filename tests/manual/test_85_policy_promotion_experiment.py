"""Assignment-balanced AI generation promotion contracts."""

from __future__ import annotations

from ai.evaluation.promotion import (
    MatchupFamily,
    PromotionMatchupSpec,
    PromotionObservation,
    PromotionOutcome,
    PromotionPanel,
    build_default_promotion_matchups,
    build_promotion_schedule,
    build_symmetric_promotion_deployments,
    fit_policy_promotion,
)
from ai.policy.generations import (
    BASELINE_GENERATION_ID,
    CANDIDATE_GENERATION_ID,
    get_policy_implementation,
)
from ai.evaluation.promotion.experiment import (
    build_default_promotion_catalog,
    build_default_promotion_schedule,
)
from ai.evaluation.promotion.gates import PromotionEvidenceGates, evaluate_promotion
from dnd.scenarios.evaluation.battlefield_catalog import get_battlefield
from dnd.scenarios.evaluation.combatant_catalog import (
    get_combatant_configuration,
    list_combatant_configurations,
)
from dnd.scenarios.evaluation.deployment_catalog import get_deployment


def test_promotion_schedule_counterbalances_policy_and_opening_in_atomic_blocks() -> None:
    """Every causal cell contains both openings and both policy assignments."""
    hero = get_combatant_configuration("hero.barbarian_l5_berserker_torch")
    monsters = get_combatant_configuration("monsters.berserker_duelist")
    battlefield = get_battlefield("battlefield.open_floor_bright")
    deployments = tuple(get_deployment(deployment_id) for deployment_id in battlefield.deployment_ids)
    candidate = get_policy_implementation(CANDIDATE_GENERATION_ID).identity
    baseline = get_policy_implementation(BASELINE_GENERATION_ID).identity
    schedule = build_promotion_schedule(
        configurations=(hero, monsters),
        matchups=(PromotionMatchupSpec(
            matchup_id="barbarian-vs-duelist",
            side_a_configuration_id=hero.configuration_id,
            side_b_configuration_id=monsters.configuration_id,
            family=MatchupFamily.HERO_VS_MONSTER,
            panel=PromotionPanel.FROZEN_CORE,
            tags=("melee",),
        ),),
        battlefields=(battlefield,),
        deployments=deployments,
        seeds=(1701,),
        candidate=candidate,
        baseline=baseline,
        experiment_id="promotion-contract-test",
        created_at="2026-07-18T00:00:00+00:00",
    )

    eligible_deployments = tuple(row for row in deployments if row.portable and row.rating_eligible)
    assert len(schedule.entries) == 4 * len(eligible_deployments)
    assert len(schedule.entries_by_block()) == len(eligible_deployments)
    for block in schedule.entries_by_block().values():
        assert {
            (row.opening_treatment, row.policy_assignment)
            for row in block
        } == {
            ("side_a_first", "candidate_a"),
            ("side_a_first", "candidate_b"),
            ("side_b_first", "candidate_a"),
            ("side_b_first", "candidate_b"),
        }
    assert all(row.side_a_policy_generation_id != row.side_b_policy_generation_id for row in schedule.entries)
    assert len({row.simulation_seed for row in schedule.entries}) == 1


def test_joint_model_recovers_candidate_uplift_across_hero_and_monster_matchups() -> None:
    """Policy strength is estimated separately from roster and opening effects."""
    observations: list[PromotionObservation] = []
    for block_index in range(24):
        family = MatchupFamily.HERO_VS_MONSTER if block_index % 2 == 0 else MatchupFamily.MONSTER_VS_MONSTER
        side_a = "hero.barbarian" if family == MatchupFamily.HERO_VS_MONSTER else "monsters.undead"
        side_b = "monsters.undead" if block_index % 3 else "monsters.raiders"
        if side_a == side_b:
            side_b = "monsters.raiders"
        for opening in ("side_a_first", "side_b_first"):
            for candidate_on_a in (True, False):
                observations.append(_observation(
                    block_id=f"block-{block_index}",
                    suffix=f"{opening}-{candidate_on_a}",
                    side_a=side_a,
                    side_b=side_b,
                    opening=opening,
                    candidate_on_a=candidate_on_a,
                    family=family,
                    outcome=(PromotionOutcome.SIDE_A_WIN if candidate_on_a else PromotionOutcome.SIDE_B_WIN),
                ))

    result = fit_policy_promotion(observations, regularization=0.25)

    assert result.publishable
    assert result.global_uplift.elo_delta > 100.0
    assert result.global_uplift.elo_lower_95 is not None
    assert result.global_uplift.elo_lower_95 > 0.0
    assert {row.slice_id for row in result.slices} >= {
        PromotionPanel.FROZEN_CORE.value,
        MatchupFamily.HERO_VS_MONSTER.value,
        MatchupFamily.MONSTER_VS_MONSTER.value,
    }
    decision = evaluate_promotion(
        result,
        PromotionEvidenceGates(
            scheduled_matches=len(observations),
            eligible_matches=len(observations),
            infrastructure_failures=0,
            subjectivity_violations=0,
            protocol_failures=0,
            deterministic_mismatches=0,
            content_coverage_regressions=0,
        ),
    )
    assert decision.accepted


def test_incomplete_comparison_block_is_excluded_and_blocks_publication() -> None:
    """One missing treatment cannot bias the candidate effect."""
    complete = [
        _observation(
            block_id="complete",
            suffix=f"{opening}-{candidate_on_a}",
            side_a="hero.alpha",
            side_b="monsters.beta",
            opening=opening,
            candidate_on_a=candidate_on_a,
            family=MatchupFamily.HERO_VS_MONSTER,
            outcome=PromotionOutcome.DRAW,
        )
        for opening in ("side_a_first", "side_b_first")
        for candidate_on_a in (True, False)
    ]
    incomplete = [
        _observation(
            block_id="incomplete",
            suffix=str(index),
            side_a="monsters.beta",
            side_b="monsters.gamma",
            opening="side_a_first",
            candidate_on_a=bool(index),
            family=MatchupFamily.MONSTER_VS_MONSTER,
            outcome=PromotionOutcome.DRAW,
        )
        for index in range(2)
    ]

    result = fit_policy_promotion([*complete, *incomplete], regularization=0.25)

    assert not result.publishable
    assert result.diagnostics.observation_count == 4
    assert result.diagnostics.incomplete_block_ids == ("incomplete",)
    assert "incomplete_comparison_blocks_excluded" in result.gate_reasons


def test_default_sparse_field_covers_every_configuration_and_monster_duels() -> None:
    """Expansion remains connected without an all-pairs schedule explosion."""
    configurations = list_combatant_configurations()
    matchups = build_default_promotion_matchups(configurations)
    covered = {
        configuration_id
        for matchup in matchups
        for configuration_id in (
            matchup.side_a_configuration_id,
            matchup.side_b_configuration_id,
        )
    }
    symmetric = build_symmetric_promotion_deployments((
        get_battlefield("battlefield.open_floor_bright"),
    ))

    assert covered == {row.configuration_id for row in configurations if row.rating_eligible}
    assert any(row.family == MatchupFamily.MONSTER_VS_MONSTER for row in matchups)
    assert any(row.panel == PromotionPanel.EXPANDED for row in matchups)
    assert len(matchups) < len(configurations) * 5
    assert len(symmetric[0].hero_slots) == len(symmetric[0].monster_slots) == 5


def test_default_catalog_and_schedule_bind_all_executable_and_content_identities() -> None:
    """The runnable loop authenticates the expanded catalog and both policies."""
    catalog = build_default_promotion_catalog(generated_at="2026-07-18T00:00:00+00:00")
    schedule = build_default_promotion_schedule(
        catalog,
        experiment_id="default-promotion-contract",
        seeds=(1801,),
        created_at="2026-07-18T00:00:00+00:00",
    )

    assert len(catalog.configurations) == 58
    assert len(catalog.policy_generations) == 2
    assert schedule.catalog_hash == catalog.catalog_hash
    assert len(schedule.entries) % 4 == 0
    assert all(len(block) == 4 for block in schedule.entries_by_block().values())
    assert any(row.matchup_family == MatchupFamily.MONSTER_VS_MONSTER for row in schedule.entries)


def _observation(
    *,
    block_id: str,
    suffix: str,
    side_a: str,
    side_b: str,
    opening: str,
    candidate_on_a: bool,
    family: MatchupFamily,
    outcome: PromotionOutcome,
) -> PromotionObservation:
    """Build one compact synthetic promotion observation."""
    return PromotionObservation(
        match_id=f"{block_id}-{suffix}",
        comparison_block_id=block_id,
        side_a_configuration_id=side_a,
        side_b_configuration_id=side_b,
        side_a_policy_generation_id=(CANDIDATE_GENERATION_ID if candidate_on_a else BASELINE_GENERATION_ID),
        side_b_policy_generation_id=(BASELINE_GENERATION_ID if candidate_on_a else CANDIDATE_GENERATION_ID),
        candidate_generation_id=CANDIDATE_GENERATION_ID,
        baseline_generation_id=BASELINE_GENERATION_ID,
        battlefield_id="battlefield.open",
        deployment_id="deployment.symmetric",
        opening_treatment=opening,
        matchup_family=family,
        panel=PromotionPanel.FROZEN_CORE,
        matchup_tags=("core",),
        outcome=outcome,
    )
