"""Joint configuration-strength and policy-uplift estimation."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import NDArray
from pydantic import Field
from scipy.optimize import minimize
from scipy.special import expit

from ai.evaluation.promotion.contracts import (
    MatchupFamily,
    PromotionObservation,
    PromotionOutcome,
    PromotionPanel,
    StrictFrozenModel,
)


ELO_PER_LOG_ODDS = 400.0 / math.log(10.0)
SliceKind = Literal["panel", "matchup_family", "tag"]


class PolicyUpliftEstimate(StrictFrozenModel):
    """Candidate-minus-baseline effect estimated within one experiment."""

    candidate_generation_id: str = Field(description="Candidate policy identity.")
    baseline_generation_id: str = Field(description="Accepted baseline identity.")
    coefficient: float = Field(description="Candidate-minus-baseline log-odds coefficient.")
    elo_delta: float = Field(description="Candidate uplift in Elo-equivalent units.")
    standard_error: float | None = Field(description="Observed-information standard error.")
    elo_lower_95: float | None = Field(description="Lower 95 percent Elo bound.")
    elo_upper_95: float | None = Field(description="Upper 95 percent Elo bound.")
    games: int = Field(ge=0, description="Admitted treatment rows in the estimate.")


class RosterStrengthEstimate(StrictFrozenModel):
    """Centered nuisance strength estimate for one roster configuration."""

    configuration_id: str = Field(description="Rated roster configuration.")
    coefficient: float = Field(description="Centered fitted log-odds strength.")
    adjusted_elo: float = Field(description="Centered roster strength on a 1000-Elo scale.")
    games: int = Field(ge=0, description="Admitted rows involving this roster.")


class PolicySliceEstimate(StrictFrozenModel):
    """Candidate uplift estimated within a protected reporting stratum."""

    slice_kind: SliceKind = Field(description="Slice family.")
    slice_id: str = Field(description="Panel, matchup family, or tag identity.")
    estimate: PolicyUpliftEstimate = Field(description="Within-slice candidate uplift.")


class PromotionModelDiagnostics(StrictFrozenModel):
    """Numerical and design evidence for policy-uplift publication."""

    converged: bool = Field(description="Whether numerical optimization converged.")
    rank: int = Field(ge=0, description="Numerical rank of the design matrix.")
    parameter_count: int = Field(ge=0, description="Number of fitted coefficients.")
    observation_count: int = Field(ge=0, description="Admitted match observations.")
    complete_block_count: int = Field(ge=0, description="Complete counterbalanced blocks.")
    incomplete_block_ids: tuple[str, ...] = Field(description="Blocks excluded before fitting.")
    log_loss: float = Field(ge=0.0, description="In-sample fractional binary log loss.")
    brier_score: float = Field(ge=0.0, description="In-sample Brier score with draws scored as one half.")


class PolicyPromotionResult(StrictFrozenModel):
    """Official assignment-balanced candidate promotion estimate."""

    schema_version: Literal[1] = Field(default=1, description="Promotion result schema version.")
    estimator: str = Field(description="Declared statistical model.")
    publishable: bool = Field(description="Whether scientific model gates passed.")
    gate_reasons: tuple[str, ...] = Field(description="Failed model-publication gates.")
    global_uplift: PolicyUpliftEstimate = Field(description="Primary candidate-minus-baseline contrast.")
    roster_strengths: tuple[RosterStrengthEstimate, ...] = Field(description="Centered nuisance roster standings.")
    slices: tuple[PolicySliceEstimate, ...] = Field(description="Protected panel, family, and tag contrasts.")
    diagnostics: PromotionModelDiagnostics = Field(description="Design and fit diagnostics.")


@dataclass(frozen=True)
class _Design:
    matrix: NDArray[np.float64]
    rosters: tuple[str, ...]
    battlefields: tuple[str, ...]
    deployments: tuple[str, ...]
    roster_slice: slice
    battlefield_slice: slice
    deployment_slice: slice
    opening_index: int
    policy_index: int


def fit_policy_promotion(
    observations: list[PromotionObservation],
    *,
    regularization: float = 0.1,
    include_slices: bool = True,
) -> PolicyPromotionResult:
    """Estimate policy uplift after excluding incomplete four-treatment blocks."""
    if not observations:
        raise ValueError("At least one promotion observation is required.")
    if regularization < 0:
        raise ValueError("regularization must be non-negative.")
    retained, incomplete = _complete_block_observations(observations)
    if not retained:
        raise ValueError("No complete four-treatment promotion blocks remain.")
    candidate_ids = {row.candidate_generation_id for row in retained}
    baseline_ids = {row.baseline_generation_id for row in retained}
    if len(candidate_ids) != 1 or len(baseline_ids) != 1:
        raise ValueError("One promotion fit must compare exactly one candidate and one baseline.")
    design = _build_design(retained)
    targets = np.asarray([_target(row.outcome) for row in retained], dtype=np.float64)
    result = minimize(
        _objective,
        np.zeros(design.matrix.shape[1], dtype=np.float64),
        args=(design.matrix, targets, regularization),
        method="L-BFGS-B",
        jac=True,
        options={"maxiter": 1000, "ftol": 1e-12, "gtol": 1e-9, "maxls": 50},
    )
    coefficients = np.asarray(result.x, dtype=np.float64)
    probabilities = np.asarray(expit(design.matrix @ coefficients), dtype=np.float64)
    covariance = _covariance(design.matrix, probabilities, regularization)
    uplift = _uplift(
        retained,
        candidate_id=next(iter(candidate_ids)),
        baseline_id=next(iter(baseline_ids)),
        coefficient=float(coefficients[design.policy_index]),
        variance=float(covariance[design.policy_index, design.policy_index]),
    )
    rank = int(np.linalg.matrix_rank(design.matrix))
    gate_reasons: list[str] = []
    if rank != design.matrix.shape[1]:
        gate_reasons.append("design_matrix_rank_deficient")
    if not result.success:
        gate_reasons.append("optimizer_did_not_converge")
    if not np.all(np.isfinite(coefficients)):
        gate_reasons.append("non_finite_model_output")
    if incomplete:
        gate_reasons.append("incomplete_comparison_blocks_excluded")
    clipped = np.clip(probabilities, 1e-12, 1.0 - 1e-12)
    log_loss = float(-np.mean(targets * np.log(clipped) + (1.0 - targets) * np.log(1.0 - clipped)))
    brier = float(np.mean((probabilities - targets) ** 2))
    slices = _slice_estimates(retained, regularization) if include_slices else tuple()
    return PolicyPromotionResult(
        estimator="assignment-balanced penalized Bradley-Terry logistic model; draws contribute one-half",
        publishable=not gate_reasons,
        gate_reasons=tuple(gate_reasons),
        global_uplift=uplift,
        roster_strengths=_roster_strengths(retained, design, coefficients),
        slices=slices,
        diagnostics=PromotionModelDiagnostics(
            converged=bool(result.success),
            rank=rank,
            parameter_count=design.matrix.shape[1],
            observation_count=len(retained),
            complete_block_count=len({row.comparison_block_id for row in retained}),
            incomplete_block_ids=incomplete,
            log_loss=log_loss,
            brier_score=brier,
        ),
    )


def _build_design(observations: list[PromotionObservation]) -> _Design:
    """Build a generic side-A contrast design with one explicit policy effect."""
    rosters = tuple(sorted({row.side_a_configuration_id for row in observations} | {row.side_b_configuration_id for row in observations}))
    battlefields = tuple(sorted({
        f"{row.battlefield_id}::{row.deployment_id}"
        for row in observations
    }))
    deployments: tuple[str, ...] = tuple()
    cursor = 0
    roster_slice = slice(cursor, cursor + max(0, len(rosters) - 1))
    cursor = roster_slice.stop
    battlefield_slice = slice(cursor, cursor + max(0, len(battlefields) - 1))
    cursor = battlefield_slice.stop
    deployment_slice = slice(cursor, cursor)
    opening_index = cursor
    policy_index = cursor + 1
    matrix = np.zeros((len(observations), policy_index + 1), dtype=np.float64)
    for index, row in enumerate(observations):
        matrix[index, roster_slice] = _effects_row(row.side_a_configuration_id, rosters) - _effects_row(row.side_b_configuration_id, rosters)
        context_id = f"{row.battlefield_id}::{row.deployment_id}"
        matrix[index, battlefield_slice] = _effects_row(context_id, battlefields)
        matrix[index, opening_index] = 0.5 if row.opening_treatment == "side_a_first" else -0.5
        matrix[index, policy_index] = 1.0 if row.side_a_policy_generation_id == row.candidate_generation_id else -1.0
    return _Design(
        matrix=matrix,
        rosters=rosters,
        battlefields=battlefields,
        deployments=deployments,
        roster_slice=roster_slice,
        battlefield_slice=battlefield_slice,
        deployment_slice=deployment_slice,
        opening_index=opening_index,
        policy_index=policy_index,
    )


def _objective(
    parameters: NDArray[np.float64],
    matrix: NDArray[np.float64],
    targets: NDArray[np.float64],
    regularization: float,
) -> tuple[float, NDArray[np.float64]]:
    """Return penalized fractional binary log loss and analytic gradient."""
    eta = matrix @ parameters
    probabilities = expit(eta)
    loss = float(np.sum(np.logaddexp(0.0, eta) - targets * eta))
    penalty = parameters.copy()
    loss += 0.5 * regularization * float(penalty @ penalty)
    gradient = matrix.T @ (probabilities - targets) + regularization * penalty
    return loss, np.asarray(gradient, dtype=np.float64)


def _covariance(
    matrix: NDArray[np.float64],
    probabilities: NDArray[np.float64],
    regularization: float,
) -> NDArray[np.float64]:
    """Return inverse observed information for the fitted binary model."""
    weights = probabilities * (1.0 - probabilities)
    hessian = matrix.T @ (matrix * weights[:, None])
    penalty = np.eye(matrix.shape[1], dtype=np.float64) * regularization
    return np.linalg.pinv(hessian + penalty, rcond=1e-10)


def _complete_block_observations(
    observations: list[PromotionObservation],
) -> tuple[list[PromotionObservation], tuple[str, ...]]:
    """Retain only blocks containing each policy/opening treatment exactly once."""
    grouped: dict[str, list[PromotionObservation]] = {}
    for row in observations:
        grouped.setdefault(row.comparison_block_id, []).append(row)
    retained: list[PromotionObservation] = []
    incomplete: list[str] = []
    expected = {
        ("side_a_first", True),
        ("side_a_first", False),
        ("side_b_first", True),
        ("side_b_first", False),
    }
    for block_id, rows in sorted(grouped.items()):
        treatments = {
            (row.opening_treatment, row.side_a_policy_generation_id == row.candidate_generation_id)
            for row in rows
        }
        if len(rows) != 4 or treatments != expected:
            incomplete.append(block_id)
        else:
            retained.extend(sorted(rows, key=lambda row: row.match_id))
    return retained, tuple(incomplete)


def _uplift(
    observations: list[PromotionObservation],
    *,
    candidate_id: str,
    baseline_id: str,
    coefficient: float,
    variance: float,
) -> PolicyUpliftEstimate:
    """Convert one policy contrast and uncertainty into Elo units."""
    standard_error = math.sqrt(max(0.0, variance)) if math.isfinite(variance) else None
    elo = ELO_PER_LOG_ODDS * coefficient
    interval = 1.96 * ELO_PER_LOG_ODDS * standard_error if standard_error is not None else None
    return PolicyUpliftEstimate(
        candidate_generation_id=candidate_id,
        baseline_generation_id=baseline_id,
        coefficient=coefficient,
        elo_delta=elo,
        standard_error=standard_error,
        elo_lower_95=elo - interval if interval is not None else None,
        elo_upper_95=elo + interval if interval is not None else None,
        games=len(observations),
    )


def _roster_strengths(
    observations: list[PromotionObservation],
    design: _Design,
    coefficients: NDArray[np.float64],
) -> tuple[RosterStrengthEstimate, ...]:
    """Decode centered roster nuisance effects for diagnostics and balancing."""
    effects = _decode_effects(coefficients[design.roster_slice], design.rosters)
    rows = [
        RosterStrengthEstimate(
            configuration_id=roster_id,
            coefficient=float(effect),
            adjusted_elo=1000.0 + ELO_PER_LOG_ODDS * float(effect),
            games=sum(
                row.side_a_configuration_id == roster_id or row.side_b_configuration_id == roster_id
                for row in observations
            ),
        )
        for roster_id, effect in zip(design.rosters, effects, strict=True)
    ]
    rows.sort(key=lambda row: (-row.adjusted_elo, row.configuration_id))
    return tuple(rows)


def _slice_estimates(
    observations: list[PromotionObservation],
    regularization: float,
) -> tuple[PolicySliceEstimate, ...]:
    """Fit protected strata independently when at least one full block remains."""
    groups: list[tuple[SliceKind, str, list[PromotionObservation]]] = []
    for panel in PromotionPanel:
        groups.append(("panel", panel.value, [row for row in observations if row.panel == panel]))
    for family in MatchupFamily:
        groups.append(("matchup_family", family.value, [row for row in observations if row.matchup_family == family]))
    tags = sorted({tag for row in observations for tag in row.matchup_tags})
    for tag in tags:
        groups.append(("tag", tag, [row for row in observations if tag in row.matchup_tags]))
    rows: list[PolicySliceEstimate] = []
    for kind, slice_id, values in groups:
        retained, _ = _complete_block_observations(values)
        if not retained:
            continue
        result = fit_policy_promotion(retained, regularization=regularization, include_slices=False)
        rows.append(PolicySliceEstimate(slice_kind=kind, slice_id=slice_id, estimate=result.global_uplift))
    return tuple(rows)


def _target(outcome: PromotionOutcome) -> float:
    """Encode side-A win, loss, and draw for the logistic model."""
    if outcome == PromotionOutcome.SIDE_A_WIN:
        return 1.0
    if outcome == PromotionOutcome.SIDE_B_WIN:
        return 0.0
    return 0.5


def _effects_row(level: str, levels: tuple[str, ...]) -> NDArray[np.float64]:
    """Encode one categorical level under a sum-to-zero constraint."""
    if len(levels) <= 1:
        return np.zeros(0, dtype=np.float64)
    row = np.zeros(len(levels) - 1, dtype=np.float64)
    index = levels.index(level)
    if index == len(levels) - 1:
        row[:] = -1.0
    else:
        row[index] = 1.0
    return row


def _decode_effects(parameters: NDArray[np.float64], levels: tuple[str, ...]) -> NDArray[np.float64]:
    """Decode sum-to-zero parameters into one value per level."""
    if len(levels) == 1:
        return np.zeros(1, dtype=np.float64)
    return np.concatenate((parameters, np.asarray([-float(np.sum(parameters))])))
