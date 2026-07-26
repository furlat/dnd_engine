"""Projection from authenticated promotion evidence to the offline report."""

from __future__ import annotations

from datetime import datetime, timezone

from ai.evaluation.content_catalog import build_implemented_content_catalog
from ai.evaluation.promotion.catalog_snapshot import PromotionCatalogSnapshot
from ai.evaluation.promotion.contracts import MatchupFamily, PromotionSchedule
from ai.evaluation.promotion.experiment import PromotionExperimentAnalysis
from ai.evaluation.promotion.report import (
    ContentCatalogProjection,
    CountMetricProjection,
    EfficiencyProjection,
    EloEstimateProjection,
    PolicyIdentityProjection,
    PolicyPromotionReportProjection,
    PolicySliceProjection,
    PromotionDecisionProjection,
    RateMetricProjection,
    ReportSource,
    RosterStrengthProjection,
    ScheduleCompositionProjection,
    TimingMetricProjection,
    WorkerEvidenceProjection,
)
from ai.policy.source import CONTROLLER_PROFILE
from dnd.monsters.srd_roster import SRD_CREATURE_RECIPES_BY_ID


def build_promotion_report_projection(
    schedule: PromotionSchedule,
    catalog: PromotionCatalogSnapshot,
    analysis: PromotionExperimentAnalysis,
    *,
    generated_at: str | None = None,
) -> PolicyPromotionReportProjection:
    """Build a strictly JSON-derived report projection from retained evidence."""
    candidate = catalog.policy(schedule.candidate_generation_id)
    baseline = catalog.policy(schedule.baseline_generation_id)
    configurations = {row.configuration_id: row for row in catalog.configurations}
    completed_matches = analysis.scheduled_matches - analysis.infrastructure_failures
    elapsed_seconds = analysis.total_match_elapsed_ms / 1000.0
    rates: list[RateMetricProjection] = []
    if elapsed_seconds > 0.0:
        rates.extend((
            RateMetricProjection(
                metric_id="aggregate_matches_per_second",
                label="Aggregate completed matches",
                value=completed_matches / elapsed_seconds,
                unit="matches/s",
            ),
            RateMetricProjection(
                metric_id="aggregate_commands_per_second",
                label="Aggregate commands",
                value=analysis.total_commands / elapsed_seconds,
                unit="commands/s",
            ),
        ))
    implemented_count = len(build_implemented_content_catalog())
    hero_count = sum(row.side_kind == "hero" for row in catalog.configurations)
    monster_count = sum(row.side_kind == "monster_party" for row in catalog.configurations)
    return PolicyPromotionReportProjection(
        source=ReportSource(
            experiment_id=schedule.experiment_id,
            title=f"Policy Promotion: {candidate.policy_version} vs {baseline.policy_version}",
            generated_at=generated_at or datetime.now(timezone.utc).isoformat(),
            schedule_hash=schedule.schedule_hash,
            catalog_hash=catalog.catalog_hash,
        ),
        candidate=_policy_identity(candidate),
        baseline=_policy_identity(baseline),
        decision=PromotionDecisionProjection(
            accepted=analysis.decision.accepted,
            reasons=analysis.decision.reasons,
        ),
        global_uplift=_elo_projection(analysis.model.global_uplift),
        slices=tuple(
            PolicySliceProjection(
                slice_kind=row.slice_kind,
                slice_id=row.slice_id,
                label=row.slice_id.replace("_", " ").title(),
                estimate=_elo_projection(row.estimate),
            )
            for row in analysis.model.slices
        ),
        roster_strengths=tuple(
            RosterStrengthProjection(
                configuration_id=row.configuration_id,
                label=configurations[row.configuration_id].title,
                roster_kind=configurations[row.configuration_id].side_kind,
                adjusted_elo=row.adjusted_elo,
                games=row.games,
            )
            for row in analysis.model.roster_strengths
        ),
        schedule=ScheduleCompositionProjection(
            total_matches=len(schedule.entries),
            comparison_blocks=len(schedule.entries_by_block()),
            hero_vs_monster=analysis.matchup_counts.get(MatchupFamily.HERO_VS_MONSTER.value, 0),
            monster_vs_monster=analysis.matchup_counts.get(MatchupFamily.MONSTER_VS_MONSTER.value, 0),
            hero_vs_hero=analysis.matchup_counts.get(MatchupFamily.HERO_VS_HERO.value, 0),
            mirror=analysis.matchup_counts.get(MatchupFamily.MIRROR.value, 0),
        ),
        workers=WorkerEvidenceProjection(
            scheduled_matches=analysis.scheduled_matches,
            completed_matches=completed_matches,
            eligible_matches=analysis.eligible_matches,
            infrastructure_failures=analysis.infrastructure_failures,
            subjectivity_violations=analysis.subjectivity_violations,
            protocol_failures=analysis.protocol_failures,
            deterministic_mismatches=analysis.deterministic_mismatches,
            content_coverage_regressions=analysis.content_coverage_regressions,
            max_active_workers=analysis.max_active_workers,
        ),
        efficiency=EfficiencyProjection(
            total_commands=analysis.total_commands,
            timings=(
                TimingMetricProjection(
                    metric_id="aggregate_match_elapsed",
                    label="Aggregate match elapsed",
                    milliseconds=analysis.total_match_elapsed_ms,
                ),
                TimingMetricProjection(
                    metric_id="mean_match_elapsed",
                    label="Mean match elapsed",
                    milliseconds=analysis.mean_match_elapsed_ms,
                ),
                TimingMetricProjection(
                    metric_id="p95_match_elapsed",
                    label="P95 match elapsed",
                    milliseconds=analysis.p95_match_elapsed_ms,
                ),
            ),
            rates=tuple(rates),
        ),
        content=ContentCatalogProjection(
            catalog_counts=(
                CountMetricProjection(metric_id="hero_configurations", label="Hero configurations", value=hero_count),
                CountMetricProjection(metric_id="monster_configurations", label="Monster configurations", value=monster_count),
                CountMetricProjection(
                    metric_id="srd_monsters",
                    label="Implemented SRD monsters",
                    value=len(SRD_CREATURE_RECIPES_BY_ID),
                ),
                CountMetricProjection(
                    metric_id="implemented_identities",
                    label="Implemented content identities",
                    value=implemented_count,
                ),
            ),
            effect_counts=(
                CountMetricProjection(
                    metric_id="handlers_effected",
                    label="Distinct handlers effected",
                    value=analysis.effected_handler_identities,
                ),
                CountMetricProjection(
                    metric_id="conditions_applied",
                    label="Distinct conditions applied",
                    value=analysis.applied_condition_identities,
                ),
                CountMetricProjection(
                    metric_id="items_consumed",
                    label="Distinct items consumed",
                    value=analysis.consumed_item_identities,
                ),
            ),
        ),
    )


def _policy_identity(identity) -> PolicyIdentityProjection:
    """Project one authenticated executable policy identity."""
    return PolicyIdentityProjection(
        generation_id=identity.generation_id,
        display_name=identity.policy_name,
        version=identity.policy_version,
        executable_sha256=identity.executable_sha256,
        controller_profile=CONTROLLER_PROFILE,
    )


def _elo_projection(estimate) -> EloEstimateProjection:
    """Project one fitted candidate-minus-baseline contrast."""
    return EloEstimateProjection(
        candidate_generation_id=estimate.candidate_generation_id,
        baseline_generation_id=estimate.baseline_generation_id,
        elo_delta=estimate.elo_delta,
        elo_lower_95=estimate.elo_lower_95,
        elo_upper_95=estimate.elo_upper_95,
        games=estimate.games,
    )
