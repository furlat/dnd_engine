"""Order-independent adjusted Bradley-Terry and Davidson strength models."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

import numpy as np
from numpy.typing import NDArray
from scipy.optimize import minimize
from scipy.special import expit, logsumexp

from ai.evaluation.config_ladder.contracts import (
    ConfigurationStrengthResult,
    ContextEffect,
    RatedOutcome,
    StrengthDesignDiagnostics,
    StrengthObservation,
    StrengthRating,
)


ELO_PER_LOG_ODDS = 400.0 / math.log(10.0)


@dataclass(frozen=True)
class _Design:
    """Numerical design matrix with coefficient slices and level metadata."""

    matrix: NDArray[np.float64]
    heroes: tuple[str, ...]
    monsters: tuple[str, ...]
    battlefields: tuple[str, ...]
    deployment_groups: tuple[tuple[str, tuple[str, ...]], ...]
    hero_slice: slice
    monster_slice: slice
    battlefield_slice: slice
    deployment_slice: slice
    opening_index: int


def fit_configuration_strength(
    observations: list[StrengthObservation],
    *,
    regularization: float = 0.1,
    max_iterations: int = 1000,
    compute_covariance: bool = True,
) -> ConfigurationStrengthResult:
    """Fit adjusted configuration strength from retained clean outcomes.

    Args:
        observations: Clean rated match outcomes and experimental contexts.
        regularization: L2 penalty applied to non-intercept coefficients.
        max_iterations: Numerical optimizer iteration ceiling.
        compute_covariance: Whether to calculate the finite-difference observed
            covariance used for secondary standard-error diagnostics.

    Returns:
        Strength estimates, context effects, diagnostics, and publication gates.

    Raises:
        ValueError: If no observations are supplied or regularization is invalid.
    """
    if not observations:
        raise ValueError("At least one strength observation is required.")
    if regularization < 0:
        raise ValueError("Regularization must be non-negative.")
    ordered = sorted(observations, key=lambda row: row.match_id)
    design = _build_design(ordered)
    has_draws = any(row.outcome == RatedOutcome.DRAW for row in ordered)
    outcomes = np.asarray([
        _davidson_outcome_code(row.outcome) if has_draws else _binary_outcome_code(row.outcome)
        for row in ordered
    ], dtype=np.float64)
    parameter_count = design.matrix.shape[1] + (1 if has_draws else 0)
    initial = np.zeros(parameter_count, dtype=np.float64)
    objective = _davidson_objective if has_draws else _bradley_terry_objective
    result = minimize(
        objective,
        initial,
        args=(design.matrix, outcomes, regularization),
        method="L-BFGS-B",
        jac=True,
        options={"maxiter": max_iterations, "ftol": 1e-12, "gtol": 1e-9, "maxls": 50},
    )
    coefficients = np.asarray(result.x[: design.matrix.shape[1]], dtype=np.float64)
    probabilities = _hero_probabilities(design.matrix, result.x, has_draws)
    covariance = (
        _covariance_from_gradient(
            result.x,
            lambda values: objective(values, design.matrix, outcomes, regularization)[1],
        )
        if compute_covariance
        else np.full((parameter_count, parameter_count), np.nan, dtype=np.float64)
    )
    connectivity = _participant_connectivity(ordered)
    matrix_rank = int(np.linalg.matrix_rank(design.matrix))
    design_parameter_count = design.matrix.shape[1]
    finite = bool(np.all(np.isfinite(result.x)) and np.all(np.isfinite(probabilities)))
    gate_reasons: list[str] = []
    if not connectivity[0]:
        gate_reasons.append("participant_graph_disconnected")
    if matrix_rank != design_parameter_count:
        gate_reasons.append("design_matrix_rank_deficient")
    if not result.success:
        gate_reasons.append("optimizer_did_not_converge")
    if not finite:
        gate_reasons.append("non_finite_model_output")

    hero_ratings, monster_ratings = _configuration_ratings(
        ordered,
        design,
        coefficients,
        covariance[: design.matrix.shape[1], : design.matrix.shape[1]],
    )
    context_effects = _context_effects(
        design,
        coefficients,
        covariance[: design.matrix.shape[1], : design.matrix.shape[1]],
    )
    binary_targets = np.asarray([
        1.0 if row.outcome == RatedOutcome.HERO_WIN else 0.0 if row.outcome == RatedOutcome.MONSTER_WIN else 0.5
        for row in ordered
    ])
    clipped = np.clip(probabilities, 1e-12, 1.0 - 1e-12)
    log_loss = float(-np.mean(binary_targets * np.log(clipped) + (1.0 - binary_targets) * np.log(1.0 - clipped)))
    brier_score = float(np.mean((probabilities - binary_targets) ** 2))
    return ConfigurationStrengthResult(
        estimator="Davidson paired-comparison model" if has_draws else "Bradley-Terry logistic model",
        converged=bool(result.success and finite),
        publishable=not gate_reasons,
        gate_reasons=tuple(gate_reasons),
        regularization=regularization,
        hero_ratings=hero_ratings,
        monster_ratings=monster_ratings,
        context_effects=context_effects,
        design=StrengthDesignDiagnostics(
            connected=connectivity[0],
            component_count=connectivity[1],
            rank=matrix_rank,
            parameter_count=design_parameter_count,
            observation_count=len(ordered),
        ),
        log_loss=log_loss,
        brier_score=brier_score,
        iterations=int(getattr(result, "nit", 0)),
    )


def _build_design(observations: list[StrengthObservation]) -> _Design:
    """Construct a sum-to-zero effects-coded design matrix."""
    heroes = tuple(sorted({row.hero_configuration_id for row in observations}))
    monsters = tuple(sorted({row.monster_configuration_id for row in observations}))
    battlefields = tuple(sorted({row.battlefield_id for row in observations}))
    deployment_groups = tuple(
        (battlefield_id, tuple(sorted({
            row.deployment_id
            for row in observations
            if row.battlefield_id == battlefield_id
        })))
        for battlefield_id in battlefields
    )
    cursor = 1
    hero_slice = slice(cursor, cursor + max(0, len(heroes) - 1))
    cursor = hero_slice.stop
    monster_slice = slice(cursor, cursor + max(0, len(monsters) - 1))
    cursor = monster_slice.stop
    battlefield_slice = slice(cursor, cursor + max(0, len(battlefields) - 1))
    cursor = battlefield_slice.stop
    deployment_parameter_count = sum(max(0, len(levels) - 1) for _, levels in deployment_groups)
    deployment_slice = slice(cursor, cursor + deployment_parameter_count)
    cursor = deployment_slice.stop
    opening_index = cursor
    matrix = np.zeros((len(observations), opening_index + 1), dtype=np.float64)
    matrix[:, 0] = 1.0
    for row_index, observation in enumerate(observations):
        matrix[row_index, hero_slice] = _effects_row(observation.hero_configuration_id, heroes)
        matrix[row_index, monster_slice] = -_effects_row(observation.monster_configuration_id, monsters)
        matrix[row_index, battlefield_slice] = _effects_row(observation.battlefield_id, battlefields)
        matrix[row_index, deployment_slice] = _nested_deployment_row(
            observation.battlefield_id,
            observation.deployment_id,
            deployment_groups,
        )
        matrix[row_index, opening_index] = 0.5 if observation.opening_treatment == "hero_first" else -0.5
    return _Design(
        matrix=matrix,
        heroes=heroes,
        monsters=monsters,
        battlefields=battlefields,
        deployment_groups=deployment_groups,
        hero_slice=hero_slice,
        monster_slice=monster_slice,
        battlefield_slice=battlefield_slice,
        deployment_slice=deployment_slice,
        opening_index=opening_index,
    )


def _bradley_terry_objective(
    parameters: NDArray[np.float64],
    matrix: NDArray[np.float64],
    outcomes: NDArray[np.float64],
    regularization: float,
) -> tuple[float, NDArray[np.float64]]:
    """Return penalized binary log-loss and analytic gradient."""
    eta = matrix @ parameters
    targets = outcomes
    probabilities = expit(eta)
    loss = float(np.sum(np.logaddexp(0.0, eta) - targets * eta))
    penalty = parameters.copy()
    penalty[0] = 0.0
    loss += 0.5 * regularization * float(penalty @ penalty)
    gradient = matrix.T @ (probabilities - targets) + regularization * penalty
    return loss, np.asarray(gradient, dtype=np.float64)


def _davidson_objective(
    parameters: NDArray[np.float64],
    matrix: NDArray[np.float64],
    outcomes: NDArray[np.float64],
    regularization: float,
) -> tuple[float, NDArray[np.float64]]:
    """Return penalized Davidson three-outcome loss and gradient."""
    beta = parameters[:-1]
    tie_log_weight = parameters[-1]
    eta = matrix @ beta
    logits = np.column_stack((eta / 2.0, -eta / 2.0, np.full_like(eta, tie_log_weight)))
    normalizer = logsumexp(logits, axis=1)
    outcome_indices = outcomes.astype(np.int64)
    loss = float(np.sum(normalizer - logits[np.arange(len(outcomes)), outcome_indices]))
    probabilities = np.exp(logits - normalizer[:, None])
    observed_eta_weight = np.where(outcomes == 0.0, 0.5, np.where(outcomes == 1.0, -0.5, 0.0))
    expected_eta_weight = 0.5 * probabilities[:, 0] - 0.5 * probabilities[:, 1]
    beta_gradient = matrix.T @ (expected_eta_weight - observed_eta_weight)
    tie_gradient = float(np.sum(probabilities[:, 2] - (outcomes == 2.0)))
    penalty = parameters.copy()
    penalty[0] = 0.0
    loss += 0.5 * regularization * float(penalty @ penalty)
    gradient = np.concatenate((beta_gradient, np.asarray([tie_gradient]))) + regularization * penalty
    return loss, np.asarray(gradient, dtype=np.float64)


def _binary_outcome_code(outcome: RatedOutcome) -> float:
    """Encode a decisive outcome as a hero-win target."""
    if outcome == RatedOutcome.HERO_WIN:
        return 1.0
    if outcome == RatedOutcome.MONSTER_WIN:
        return 0.0
    return 0.5


def _davidson_outcome_code(outcome: RatedOutcome) -> float:
    """Encode hero, monster, and draw classes for Davidson softmax."""
    if outcome == RatedOutcome.HERO_WIN:
        return 0.0
    if outcome == RatedOutcome.MONSTER_WIN:
        return 1.0
    return 2.0


def _hero_probabilities(
    matrix: NDArray[np.float64],
    parameters: NDArray[np.float64],
    has_draws: bool,
) -> NDArray[np.float64]:
    """Return fitted hero-win probabilities."""
    if not has_draws:
        return np.asarray(expit(matrix @ parameters), dtype=np.float64)
    eta = matrix @ parameters[:-1]
    logits = np.column_stack((eta / 2.0, -eta / 2.0, np.full_like(eta, parameters[-1])))
    probabilities = np.exp(logits - logsumexp(logits, axis=1)[:, None])
    return np.asarray(probabilities[:, 0], dtype=np.float64)


def _configuration_ratings(
    observations: list[StrengthObservation],
    design: _Design,
    coefficients: NDArray[np.float64],
    covariance: NDArray[np.float64],
) -> tuple[tuple[StrengthRating, ...], tuple[StrengthRating, ...]]:
    """Project constrained coefficients onto separate hero and monster Elo tables."""
    hero_effects = _decode_effects(coefficients[design.hero_slice], design.heroes)
    monster_effects = _decode_effects(coefficients[design.monster_slice], design.monsters)
    intercept = coefficients[0]
    hero_rows = []
    for hero_id, effect in zip(design.heroes, hero_effects, strict=True):
        contrast = np.zeros(len(coefficients), dtype=np.float64)
        contrast[0] = 0.5
        contrast[design.hero_slice] = _effects_row(hero_id, design.heroes)
        hero_rows.append(_rating_row(
            configuration_id=hero_id,
            side_kind="hero",
            coefficient=intercept / 2.0 + effect,
            contrast=contrast,
            covariance=covariance,
            games=sum(row.hero_configuration_id == hero_id for row in observations),
        ))
    monster_rows = []
    for monster_id, effect in zip(design.monsters, monster_effects, strict=True):
        contrast = np.zeros(len(coefficients), dtype=np.float64)
        contrast[0] = -0.5
        contrast[design.monster_slice] = _effects_row(monster_id, design.monsters)
        monster_rows.append(_rating_row(
            configuration_id=monster_id,
            side_kind="monster_party",
            coefficient=-intercept / 2.0 + effect,
            contrast=contrast,
            covariance=covariance,
            games=sum(row.monster_configuration_id == monster_id for row in observations),
        ))
    hero_rows.sort(key=lambda row: (-row.adjusted_elo, row.configuration_id))
    monster_rows.sort(key=lambda row: (-row.adjusted_elo, row.configuration_id))
    return tuple(hero_rows), tuple(monster_rows)


def _rating_row(
    *,
    configuration_id: str,
    side_kind: str,
    coefficient: float,
    contrast: NDArray[np.float64],
    covariance: NDArray[np.float64],
    games: int,
) -> StrengthRating:
    """Create one rating row with delta-method uncertainty."""
    variance = float(contrast @ covariance @ contrast)
    standard_error = math.sqrt(max(0.0, variance)) if math.isfinite(variance) else None
    elo = 1000.0 + ELO_PER_LOG_ODDS * coefficient
    interval = 1.96 * ELO_PER_LOG_ODDS * standard_error if standard_error is not None else None
    return StrengthRating(
        configuration_id=configuration_id,
        side_kind=side_kind,
        coefficient=round(float(coefficient), 12),
        adjusted_elo=round(float(elo), 8),
        standard_error=round(standard_error, 12) if standard_error is not None else None,
        elo_lower_95=round(elo - interval, 8) if interval is not None else None,
        elo_upper_95=round(elo + interval, 8) if interval is not None else None,
        games=games,
    )


def _context_effects(
    design: _Design,
    coefficients: NDArray[np.float64],
    covariance: NDArray[np.float64],
) -> tuple[ContextEffect, ...]:
    """Decode centered context effects and uncertainty."""
    rows: list[ContextEffect] = []
    for kind, levels, coefficient_slice in (
        ("battlefield", design.battlefields, design.battlefield_slice),
    ):
        decoded = _decode_effects(coefficients[coefficient_slice], levels)
        for level, value in zip(levels, decoded, strict=True):
            contrast = np.zeros(len(coefficients), dtype=np.float64)
            contrast[coefficient_slice] = _effects_row(level, levels)
            variance = float(contrast @ covariance @ contrast)
            standard_error = math.sqrt(max(0.0, variance)) if math.isfinite(variance) else None
            rows.append(ContextEffect(
                context_kind=kind,
                context_id=level,
                coefficient=round(float(value), 12),
                elo_equivalent=round(ELO_PER_LOG_ODDS * float(value), 8),
                standard_error=round(standard_error, 12) if standard_error is not None else None,
            ))
    deployment_cursor = design.deployment_slice.start
    for battlefield_id, levels in design.deployment_groups:
        parameter_count = max(0, len(levels) - 1)
        coefficient_slice = slice(deployment_cursor, deployment_cursor + parameter_count)
        deployment_cursor += parameter_count
        decoded = _decode_effects(coefficients[coefficient_slice], levels)
        for level, value in zip(levels, decoded, strict=True):
            contrast = np.zeros(len(coefficients), dtype=np.float64)
            if parameter_count:
                contrast[coefficient_slice] = _effects_row(level, levels)
            variance = float(contrast @ covariance @ contrast)
            standard_error = math.sqrt(max(0.0, variance)) if math.isfinite(variance) else None
            rows.append(ContextEffect(
                context_kind="deployment",
                context_id=f"{battlefield_id}:{level}",
                coefficient=round(float(value), 12),
                elo_equivalent=round(ELO_PER_LOG_ODDS * float(value), 8),
                standard_error=round(standard_error, 12) if standard_error is not None else None,
            ))
    opening_value = float(coefficients[design.opening_index])
    opening_error = _diagonal_error(covariance, design.opening_index)
    rows.append(ContextEffect(
        context_kind="opening",
        context_id="hero_first_minus_monster_first",
        coefficient=round(opening_value, 12),
        elo_equivalent=round(ELO_PER_LOG_ODDS * opening_value, 8),
        standard_error=round(opening_error, 12) if opening_error is not None else None,
    ))
    return tuple(rows)


def _effects_row(level: str, levels: tuple[str, ...]) -> NDArray[np.float64]:
    """Encode one level under a sum-to-zero constraint."""
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
    """Decode sum-to-zero contrast coefficients into level effects."""
    if not levels:
        return np.zeros(0, dtype=np.float64)
    if len(levels) == 1:
        return np.zeros(1, dtype=np.float64)
    return np.concatenate((parameters, np.asarray([-float(np.sum(parameters))])))


def _nested_deployment_row(
    battlefield_id: str,
    deployment_id: str,
    groups: tuple[tuple[str, tuple[str, ...]], ...],
) -> NDArray[np.float64]:
    """Encode deployment contrasts only within their owning battlefield."""
    values: list[float] = []
    found = False
    for group_battlefield_id, levels in groups:
        width = max(0, len(levels) - 1)
        if group_battlefield_id == battlefield_id:
            values.extend(_effects_row(deployment_id, levels).tolist())
            found = True
        else:
            values.extend([0.0] * width)
    if not found:
        raise ValueError(f"Unknown deployment battlefield: {battlefield_id}")
    return np.asarray(values, dtype=np.float64)


def _covariance_from_gradient(
    parameters: NDArray[np.float64],
    gradient_function: Callable[[NDArray[np.float64]], NDArray[np.float64]],
) -> NDArray[np.float64]:
    """Approximate observed covariance from central gradient differences."""
    count = len(parameters)
    hessian = np.zeros((count, count), dtype=np.float64)
    epsilon = 1e-5
    for column in range(count):
        step = np.zeros(count, dtype=np.float64)
        step[column] = epsilon
        plus = gradient_function(parameters + step)
        minus = gradient_function(parameters - step)
        hessian[:, column] = (plus - minus) / (2.0 * epsilon)
    hessian = (hessian + hessian.T) / 2.0
    return np.linalg.pinv(hessian, rcond=1e-10)


def _diagonal_error(covariance: NDArray[np.float64], index: int) -> float | None:
    """Return a finite standard error from one covariance diagonal."""
    variance = float(covariance[index, index])
    if not math.isfinite(variance):
        return None
    return math.sqrt(max(0.0, variance))


def _participant_connectivity(observations: list[StrengthObservation]) -> tuple[bool, int]:
    """Return connectivity and component count for the comparison graph."""
    adjacency: dict[str, set[str]] = {}
    for row in observations:
        hero_id = f"hero:{row.hero_configuration_id}"
        monster_id = f"monster:{row.monster_configuration_id}"
        adjacency.setdefault(hero_id, set()).add(monster_id)
        adjacency.setdefault(monster_id, set()).add(hero_id)
    remaining = set(adjacency)
    components = 0
    while remaining:
        components += 1
        stack = [next(iter(remaining))]
        visited: set[str] = set()
        while stack:
            node = stack.pop()
            if node in visited:
                continue
            visited.add(node)
            stack.extend(adjacency[node] - visited)
        remaining -= visited
    return components == 1 and bool(adjacency), components
