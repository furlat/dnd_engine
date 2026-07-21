"""Paired-cluster bootstrap uncertainty for adjusted strength standings."""

from __future__ import annotations

from collections import Counter
import math
from typing import Iterator, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from ai.evaluation.config_ladder.contracts import (
    ConfigurationStrengthResult,
    StrengthObservation,
)
from ai.evaluation.config_ladder.online_elo import SideKind, canonical_pair_blocks
from ai.evaluation.config_ladder.strength_model import fit_configuration_strength


class ConfigurationBootstrapInterval(BaseModel):
    """Bootstrap Elo and rank uncertainty for one configuration."""

    model_config = ConfigDict(frozen=True)

    configuration_id: str = Field(description="Rated configuration identifier.")
    side_kind: SideKind = Field(description="Rated side category.")
    point_estimate_elo: float = Field(description="Adjusted Elo from the unresampled paired dataset.")
    elo_lower_95: float = Field(description="Lower percentile bound of the paired-bootstrap Elo interval.")
    elo_median: float = Field(description="Median adjusted Elo across successful bootstrap replicates.")
    elo_upper_95: float = Field(description="Upper percentile bound of the paired-bootstrap Elo interval.")
    rank_lower_95: int = Field(ge=1, description="Lower discrete percentile bound for within-side rank.")
    rank_median: int = Field(ge=1, description="Median within-side rank across successful replicates.")
    rank_upper_95: int = Field(ge=1, description="Upper discrete percentile bound for within-side rank.")
    top_n_probability: float = Field(ge=0, le=1, description="Fraction of successful replicates ranked in the requested top N.")
    successful_replicates: int = Field(ge=1, description="Successful replicates contributing to this interval.")


class PairedBootstrapStrengthResult(BaseModel):
    """Adjusted-strength point fit with paired-cluster bootstrap uncertainty."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = Field(default=1, description="Paired bootstrap result schema version.")
    estimator: str = Field(description="Bootstrap unit and fitted estimator declaration.")
    random_seed: int = Field(description="Seed used for paired-block resampling.")
    requested_replicates: int = Field(ge=1, description="Number of bootstrap fits requested.")
    successful_replicates: int = Field(ge=0, description="Replicates passing fit and design checks.")
    failed_replicates: int = Field(ge=0, description="Replicates excluded from interval summaries.")
    success_rate: float = Field(ge=0, le=1, description="Successful replicates divided by requested replicates.")
    pair_block_count: int = Field(ge=1, description="Complete opening pairs sampled per replicate.")
    top_n: int = Field(ge=1, description="Rank cutoff used for top-N probabilities.")
    regularization: float = Field(ge=0, description="L2 penalty passed to every adjusted strength fit.")
    minimum_success_rate: float = Field(ge=0, le=1, description="Bootstrap success-rate publication threshold.")
    publishable: bool = Field(description="Whether point-fit and bootstrap publication gates passed.")
    gate_reasons: tuple[str, ...] = Field(default_factory=tuple, description="Failed bootstrap publication gates.")
    failure_counts: dict[str, int] = Field(default_factory=dict, description="Excluded replicate counts by stable reason.")
    point_estimate: ConfigurationStrengthResult = Field(description="Existing adjusted model fit on all validated pairs.")
    hero_intervals: tuple[ConfigurationBootstrapInterval, ...] = Field(description="Hero Elo and rank intervals.")
    monster_intervals: tuple[ConfigurationBootstrapInterval, ...] = Field(description="Monster-party Elo and rank intervals.")


def iter_paired_cluster_bootstrap_samples(
    observations: list[StrengthObservation],
    *,
    replicate_count: int,
    random_seed: int,
) -> Iterator[list[StrengthObservation]]:
    """Yield seeded samples of whole pair blocks, with replacement."""
    if replicate_count < 1:
        raise ValueError("replicate_count must be at least one")

    blocks = canonical_pair_blocks(observations)
    rng = np.random.default_rng(random_seed)
    for _ in range(replicate_count):
        selected = rng.integers(0, len(blocks), size=len(blocks))
        yield [
            observation
            for block_index in selected
            for observation in blocks[int(block_index)]
        ]


def bootstrap_configuration_strength(
    observations: list[StrengthObservation],
    *,
    replicate_count: int = 2000,
    random_seed: int = 0,
    top_n: int = 3,
    regularization: float = 0.1,
    max_iterations: int = 1000,
    minimum_success_rate: float = 0.95,
) -> PairedBootstrapStrengthResult:
    """Fit adjusted strength and obtain 95 percent paired-bootstrap intervals."""
    if replicate_count < 1:
        raise ValueError("replicate_count must be at least one")
    if top_n < 1:
        raise ValueError("top_n must be at least one")
    if regularization < 0:
        raise ValueError("regularization must be non-negative")
    if max_iterations < 1:
        raise ValueError("max_iterations must be at least one")
    if not 0.0 <= minimum_success_rate <= 1.0:
        raise ValueError("minimum_success_rate must be between zero and one")

    blocks = canonical_pair_blocks(observations)
    canonical_observations = [observation for block in blocks for observation in block]
    point_estimate = fit_configuration_strength(
        canonical_observations,
        regularization=regularization,
        max_iterations=max_iterations,
    )
    expected_participants = _participant_ids(point_estimate)
    elo_samples: dict[tuple[SideKind, str], list[float]] = {
        participant: []
        for participant in expected_participants
    }
    rank_samples: dict[tuple[SideKind, str], list[int]] = {
        participant: []
        for participant in expected_participants
    }
    failures: Counter[str] = Counter()
    successful_replicates = 0

    samples = iter_paired_cluster_bootstrap_samples(
        canonical_observations,
        replicate_count=replicate_count,
        random_seed=random_seed,
    )
    for sample in samples:
        try:
            fitted = fit_configuration_strength(
                sample,
                regularization=regularization,
                max_iterations=max_iterations,
                compute_covariance=False,
            )
        except Exception as error:  # A failed replicate is data, not a failed bootstrap run.
            failures[f"fit_exception:{type(error).__name__}"] += 1
            continue

        fitted_participants = _participant_ids(fitted)
        if fitted_participants != expected_participants:
            failures["participant_set_changed"] += 1
            continue
        if not fitted.publishable:
            reason = "+".join(fitted.gate_reasons) or "model_not_publishable"
            failures[reason] += 1
            continue
        fitted_ratings = _ratings_by_participant(fitted)
        if not all(math.isfinite(value) for value in fitted_ratings.values()):
            failures["non_finite_rating"] += 1
            continue

        successful_replicates += 1
        for participant, rating in fitted_ratings.items():
            elo_samples[participant].append(rating)
        for participant, rank in _ranks_by_participant(fitted).items():
            rank_samples[participant].append(rank)

    success_rate = successful_replicates / replicate_count
    gate_reasons: list[str] = []
    if not point_estimate.publishable:
        gate_reasons.append("point_estimate_not_publishable")
    if successful_replicates == 0:
        gate_reasons.append("no_successful_bootstrap_replicates")
    if success_rate < minimum_success_rate:
        gate_reasons.append("bootstrap_success_rate_below_threshold")

    point_ratings = _ratings_by_participant(point_estimate)
    hero_intervals: tuple[ConfigurationBootstrapInterval, ...] = ()
    monster_intervals: tuple[ConfigurationBootstrapInterval, ...] = ()
    if successful_replicates:
        hero_intervals = _build_intervals(
            "hero",
            point_ratings,
            elo_samples,
            rank_samples,
            top_n,
            successful_replicates,
        )
        monster_intervals = _build_intervals(
            "monster_party",
            point_ratings,
            elo_samples,
            rank_samples,
            top_n,
            successful_replicates,
        )

    return PairedBootstrapStrengthResult(
        estimator="paired-cluster percentile bootstrap of adjusted Bradley-Terry/Davidson strength",
        random_seed=random_seed,
        requested_replicates=replicate_count,
        successful_replicates=successful_replicates,
        failed_replicates=replicate_count - successful_replicates,
        success_rate=_rounded(success_rate),
        pair_block_count=len(blocks),
        top_n=top_n,
        regularization=regularization,
        minimum_success_rate=minimum_success_rate,
        publishable=not gate_reasons,
        gate_reasons=tuple(gate_reasons),
        failure_counts=dict(sorted(failures.items())),
        point_estimate=point_estimate,
        hero_intervals=hero_intervals,
        monster_intervals=monster_intervals,
    )


def _build_intervals(
    side_kind: SideKind,
    point_ratings: dict[tuple[SideKind, str], float],
    elo_samples: dict[tuple[SideKind, str], list[float]],
    rank_samples: dict[tuple[SideKind, str], list[int]],
    top_n: int,
    successful_replicates: int,
) -> tuple[ConfigurationBootstrapInterval, ...]:
    participants = sorted(
        (
            (configuration_id, rating)
            for (participant_side, configuration_id), rating in point_ratings.items()
            if participant_side == side_kind
        ),
        key=lambda item: (-item[1], item[0]),
    )
    rows: list[ConfigurationBootstrapInterval] = []
    for configuration_id, point_rating in participants:
        participant = (side_kind, configuration_id)
        elos = np.asarray(elo_samples[participant], dtype=float)
        ranks = np.asarray(rank_samples[participant], dtype=int)
        elo_quantiles = np.quantile(elos, (0.025, 0.5, 0.975))
        rank_quantiles = np.quantile(ranks, (0.025, 0.5, 0.975), method="nearest")
        rows.append(ConfigurationBootstrapInterval(
            configuration_id=configuration_id,
            side_kind=side_kind,
            point_estimate_elo=_rounded(point_rating),
            elo_lower_95=_rounded(float(elo_quantiles[0])),
            elo_median=_rounded(float(elo_quantiles[1])),
            elo_upper_95=_rounded(float(elo_quantiles[2])),
            rank_lower_95=int(rank_quantiles[0]),
            rank_median=int(rank_quantiles[1]),
            rank_upper_95=int(rank_quantiles[2]),
            top_n_probability=_rounded(float(np.mean(ranks <= top_n))),
            successful_replicates=successful_replicates,
        ))
    return tuple(rows)


def _participant_ids(result: ConfigurationStrengthResult) -> set[tuple[SideKind, str]]:
    return {
        (rating.side_kind, rating.configuration_id)
        for rating in (*result.hero_ratings, *result.monster_ratings)
    }


def _ratings_by_participant(
    result: ConfigurationStrengthResult,
) -> dict[tuple[SideKind, str], float]:
    return {
        (rating.side_kind, rating.configuration_id): rating.adjusted_elo
        for rating in (*result.hero_ratings, *result.monster_ratings)
    }


def _ranks_by_participant(
    result: ConfigurationStrengthResult,
) -> dict[tuple[SideKind, str], int]:
    ranks: dict[tuple[SideKind, str], int] = {}
    for ratings in (result.hero_ratings, result.monster_ratings):
        for rank, rating in enumerate(ratings, start=1):
            ranks[(rating.side_kind, rating.configuration_id)] = rank
    return ranks


def _rounded(value: float) -> float:
    return round(float(value), 10)
