"""Scientific and gameplay gates for accepting a candidate policy generation."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from ai.evaluation.promotion.contracts import PromotionPanel, StrictFrozenModel
from ai.evaluation.promotion.model import PolicyPromotionResult


class PromotionEvidenceGates(StrictFrozenModel):
    """Non-statistical evidence accumulated by isolated match workers."""

    scheduled_matches: int = Field(ge=0, description="Total immutable treatment rows.")
    eligible_matches: int = Field(ge=0, description="Rows admitted to the policy model.")
    infrastructure_failures: int = Field(ge=0, description="Rows without authenticated completed evidence.")
    subjectivity_violations: int = Field(ge=0, description="Independent hidden-information violations.")
    protocol_failures: int = Field(ge=0, description="Rejected, stale, error, or missing command results.")
    deterministic_mismatches: int = Field(ge=0, description="Replicated semantic outcomes that disagreed.")
    content_coverage_regressions: int = Field(ge=0, description="Protected content identities losing effect evidence.")


class PromotionDecision(StrictFrozenModel):
    """Auditable accept/reject decision for one candidate generation."""

    schema_version: Literal[1] = Field(default=1, description="Promotion decision schema version.")
    accepted: bool = Field(description="Whether the candidate may replace the accepted baseline.")
    candidate_generation_id: str = Field(description="Candidate identity under review.")
    baseline_generation_id: str = Field(description="Baseline identity being challenged.")
    reasons: tuple[str, ...] = Field(description="Every failed promotion gate.")
    global_elo_delta: float = Field(description="Primary assignment-balanced candidate uplift.")
    global_elo_lower_95: float | None = Field(description="Lower confidence bound used by the gate.")


def evaluate_promotion(
    result: PolicyPromotionResult,
    evidence: PromotionEvidenceGates,
    *,
    minimum_eligible_matches: int = 40,
    expanded_panel_floor_elo: float = -10.0,
) -> PromotionDecision:
    """Require credible global gain and no scientific or protected regressions."""
    uplift = result.global_uplift
    reasons = list(result.gate_reasons)
    if not result.publishable:
        reasons.append("promotion_model_not_publishable")
    if uplift.elo_lower_95 is None or uplift.elo_lower_95 <= 0.0:
        reasons.append("global_candidate_uplift_not_credible")
    if evidence.eligible_matches < minimum_eligible_matches:
        reasons.append("insufficient_eligible_matches")
    if evidence.infrastructure_failures:
        reasons.append("infrastructure_failures_present")
    if evidence.subjectivity_violations:
        reasons.append("subjectivity_violations_present")
    if evidence.protocol_failures:
        reasons.append("protocol_failures_present")
    if evidence.deterministic_mismatches:
        reasons.append("deterministic_replay_mismatches_present")
    if evidence.content_coverage_regressions:
        reasons.append("content_coverage_regressions_present")

    frozen = next(
        (row.estimate for row in result.slices if row.slice_kind == "panel" and row.slice_id == PromotionPanel.FROZEN_CORE.value),
        None,
    )
    expanded = next(
        (row.estimate for row in result.slices if row.slice_kind == "panel" and row.slice_id == PromotionPanel.EXPANDED.value),
        None,
    )
    if frozen is None or frozen.elo_lower_95 is None or frozen.elo_lower_95 <= 0.0:
        reasons.append("frozen_core_uplift_not_credible")
    if expanded is not None and expanded.elo_delta < expanded_panel_floor_elo:
        reasons.append("expanded_panel_regressed")
    for row in result.slices:
        if row.slice_kind not in {"matchup_family", "tag"}:
            continue
        upper = row.estimate.elo_upper_95
        if upper is not None and upper < 0.0:
            reasons.append(f"credible_slice_regression:{row.slice_kind}:{row.slice_id}")

    unique_reasons = tuple(sorted(set(reasons)))
    return PromotionDecision(
        accepted=not unique_reasons,
        candidate_generation_id=uplift.candidate_generation_id,
        baseline_generation_id=uplift.baseline_generation_id,
        reasons=unique_reasons,
        global_elo_delta=uplift.elo_delta,
        global_elo_lower_95=uplift.elo_lower_95,
    )
