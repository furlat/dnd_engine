"""Provisional online Elo computed from complete paired opening blocks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from ai.evaluation.config_ladder.contracts import RatedOutcome, StrengthObservation


SideKind = Literal["hero", "monster_party"]
PairBlock = tuple[StrengthObservation, StrengthObservation]


class ProvisionalEloConfig(BaseModel):
    """Declared constants for a provisional paired Elo replay."""

    model_config = ConfigDict(frozen=True)

    initial_rating: float = Field(default=1000.0, description="Rating assigned before a configuration's first paired block.")
    k_factor: float = Field(default=32.0, gt=0, description="Maximum rating transfer for one paired-block update.")
    rating_scale: float = Field(default=400.0, gt=0, description="Elo scale in rating points per tenfold odds change.")


class PairedEloUpdate(BaseModel):
    """One atomic Elo update derived from both opening treatments."""

    model_config = ConfigDict(frozen=True)

    pair_block_id: str = Field(description="Paired opening-treatment block consumed by this update.")
    hero_configuration_id: str = Field(description="Hero configuration updated by the block.")
    monster_configuration_id: str = Field(description="Monster-party configuration updated by the block.")
    hero_score: float = Field(ge=0, le=1, description="Mean hero score across the block's two matches.")
    expected_hero_score: float = Field(ge=0, le=1, description="Hero expectation before the paired update.")
    hero_rating_before: float = Field(description="Hero rating before the paired update.")
    monster_rating_before: float = Field(description="Monster-party rating before the paired update.")
    hero_rating_after: float = Field(description="Hero rating after the paired update.")
    monster_rating_after: float = Field(description="Monster-party rating after the paired update.")
    rating_transfer: float = Field(description="Signed points transferred to the hero configuration.")


class ProvisionalEloStanding(BaseModel):
    """One provisional standing after replaying complete pair blocks."""

    model_config = ConfigDict(frozen=True)

    rank: int = Field(ge=1, description="Deterministic ordinal rank within the side category.")
    configuration_id: str = Field(description="Rated configuration identifier.")
    side_kind: SideKind = Field(description="Rated side category.")
    rating: float = Field(description="Final provisional Elo rating.")
    pair_blocks: int = Field(ge=0, description="Complete paired blocks involving this configuration.")
    matches: int = Field(ge=0, description="Individual matches represented by those paired blocks.")
    wins: int = Field(ge=0, description="Individual wins from this configuration's perspective.")
    draws: int = Field(ge=0, description="Individual draws involving this configuration.")
    losses: int = Field(ge=0, description="Individual losses from this configuration's perspective.")


class ProvisionalPairedEloResult(BaseModel):
    """Canonical provisional Elo replay over complete opening pairs."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = Field(default=1, description="Provisional paired Elo result schema version.")
    estimator: str = Field(description="Human-readable estimator declaration.")
    config: ProvisionalEloConfig = Field(description="Constants used for every paired update.")
    completed_pair_block_count: int = Field(ge=0, description="Number of atomic paired updates applied.")
    hero_standings: tuple[ProvisionalEloStanding, ...] = Field(description="Final hero standings.")
    monster_standings: tuple[ProvisionalEloStanding, ...] = Field(description="Final monster-party standings.")
    updates: tuple[PairedEloUpdate, ...] = Field(description="Applied updates in replay order.")


class EloOrderSensitivityParticipant(BaseModel):
    """Permutation envelope for one provisional Elo participant."""

    model_config = ConfigDict(frozen=True)

    configuration_id: str = Field(description="Rated configuration identifier.")
    side_kind: SideKind = Field(description="Rated side category.")
    canonical_rating: float = Field(description="Rating from lexicographically ordered pair blocks.")
    minimum_rating: float = Field(description="Minimum across canonical and seeded permutation replays.")
    lower_05_rating: float = Field(description="Fifth percentile across canonical and permutation replays.")
    median_rating: float = Field(description="Median across canonical and permutation replays.")
    upper_95_rating: float = Field(description="Ninety-fifth percentile across canonical and permutation replays.")
    maximum_rating: float = Field(description="Maximum across canonical and seeded permutation replays.")
    rating_range: float = Field(ge=0, description="Maximum minus minimum replay rating.")
    maximum_absolute_delta: float = Field(ge=0, description="Largest absolute departure from the canonical rating.")


class EloOrderSensitivityAudit(BaseModel):
    """Seeded audit of online Elo sensitivity to paired-block order."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = Field(default=1, description="Order-sensitivity audit schema version.")
    random_seed: int = Field(description="Seed used to generate block-order permutations.")
    permutation_count: int = Field(ge=1, description="Number of seeded random order replays.")
    pair_block_count: int = Field(ge=1, description="Number of complete pair blocks in each replay.")
    maximum_rating_range: float = Field(ge=0, description="Largest participant rating range in the audit.")
    participants: tuple[EloOrderSensitivityParticipant, ...] = Field(description="Participant-level order envelopes.")


@dataclass
class _StandingAccumulator:
    pair_blocks: int = 0
    matches: int = 0
    wins: int = 0
    draws: int = 0
    losses: int = 0


def canonical_pair_blocks(observations: list[StrengthObservation]) -> tuple[PairBlock, ...]:
    """Validate observations and return complete pairs in canonical block order."""
    if not observations:
        raise ValueError("paired Elo requires at least one observation")

    grouped: dict[str, list[StrengthObservation]] = {}
    for observation in observations:
        grouped.setdefault(observation.pair_block_id, []).append(observation)

    blocks: list[PairBlock] = []
    for pair_block_id in sorted(grouped):
        rows = grouped[pair_block_id]
        if len(rows) != 2:
            raise ValueError(
                f"pair block {pair_block_id!r} must contain exactly two observations; found {len(rows)}"
            )

        identity = (
            rows[0].hero_configuration_id,
            rows[0].monster_configuration_id,
            rows[0].battlefield_id,
            rows[0].deployment_id,
        )
        if any(
            (
                row.hero_configuration_id,
                row.monster_configuration_id,
                row.battlefield_id,
                row.deployment_id,
            )
            != identity
            for row in rows[1:]
        ):
            raise ValueError(
                f"pair block {pair_block_id!r} disagrees on participant or context identity"
            )

        by_opening = {row.opening_treatment: row for row in rows}
        if len(by_opening) != 2 or set(by_opening) != {"hero_first", "monster_first"}:
            raise ValueError(
                f"pair block {pair_block_id!r} must contain one hero_first and one monster_first observation"
            )
        blocks.append((by_opening["hero_first"], by_opening["monster_first"]))

    return tuple(blocks)


def build_provisional_paired_elo(
    observations: list[StrengthObservation],
    *,
    config: ProvisionalEloConfig | None = None,
) -> ProvisionalPairedEloResult:
    """Replay complete pair blocks once each in canonical block-id order."""
    blocks = canonical_pair_blocks(observations)
    return _replay_pair_blocks(blocks, config or ProvisionalEloConfig())


def audit_elo_order_sensitivity(
    observations: list[StrengthObservation],
    *,
    permutation_count: int = 1000,
    random_seed: int = 0,
    config: ProvisionalEloConfig | None = None,
) -> EloOrderSensitivityAudit:
    """Replay seeded block permutations while keeping every opening pair atomic."""
    if permutation_count < 1:
        raise ValueError("permutation_count must be at least one")

    blocks = canonical_pair_blocks(observations)
    resolved_config = config or ProvisionalEloConfig()
    canonical = _replay_pair_blocks(blocks, resolved_config)
    canonical_ratings = _ratings_by_participant(canonical)
    replay_ratings: dict[tuple[SideKind, str], list[float]] = {
        participant: [rating]
        for participant, rating in canonical_ratings.items()
    }

    rng = np.random.default_rng(random_seed)
    for _ in range(permutation_count):
        order = rng.permutation(len(blocks))
        replay = _replay_pair_blocks(tuple(blocks[int(index)] for index in order), resolved_config)
        for participant, rating in _ratings_by_participant(replay).items():
            replay_ratings[participant].append(rating)

    participant_rows: list[EloOrderSensitivityParticipant] = []
    for side_kind, configuration_id in sorted(replay_ratings):
        values = np.asarray(replay_ratings[(side_kind, configuration_id)], dtype=float)
        canonical_rating = canonical_ratings[(side_kind, configuration_id)]
        minimum = float(np.min(values))
        maximum = float(np.max(values))
        participant_rows.append(EloOrderSensitivityParticipant(
            configuration_id=configuration_id,
            side_kind=side_kind,
            canonical_rating=_rounded(canonical_rating),
            minimum_rating=_rounded(minimum),
            lower_05_rating=_rounded(float(np.quantile(values, 0.05))),
            median_rating=_rounded(float(np.quantile(values, 0.5))),
            upper_95_rating=_rounded(float(np.quantile(values, 0.95))),
            maximum_rating=_rounded(maximum),
            rating_range=_rounded(maximum - minimum),
            maximum_absolute_delta=_rounded(float(np.max(np.abs(values - canonical_rating)))),
        ))

    return EloOrderSensitivityAudit(
        random_seed=random_seed,
        permutation_count=permutation_count,
        pair_block_count=len(blocks),
        maximum_rating_range=max(row.rating_range for row in participant_rows),
        participants=tuple(participant_rows),
    )


def _replay_pair_blocks(
    blocks: tuple[PairBlock, ...],
    config: ProvisionalEloConfig,
) -> ProvisionalPairedEloResult:
    ratings: dict[tuple[SideKind, str], float] = {}
    statistics: dict[tuple[SideKind, str], _StandingAccumulator] = {}
    updates: list[PairedEloUpdate] = []

    for hero_first, monster_first in blocks:
        hero_key: tuple[SideKind, str] = ("hero", hero_first.hero_configuration_id)
        monster_key: tuple[SideKind, str] = ("monster_party", hero_first.monster_configuration_id)
        hero_before = ratings.setdefault(hero_key, config.initial_rating)
        monster_before = ratings.setdefault(monster_key, config.initial_rating)
        hero_score = (_hero_score(hero_first.outcome) + _hero_score(monster_first.outcome)) / 2.0
        expected_hero_score = 1.0 / (
            1.0 + 10.0 ** ((monster_before - hero_before) / config.rating_scale)
        )
        transfer = config.k_factor * (hero_score - expected_hero_score)
        hero_after = hero_before + transfer
        monster_after = monster_before - transfer
        ratings[hero_key] = hero_after
        ratings[monster_key] = monster_after

        hero_stats = statistics.setdefault(hero_key, _StandingAccumulator())
        monster_stats = statistics.setdefault(monster_key, _StandingAccumulator())
        hero_stats.pair_blocks += 1
        monster_stats.pair_blocks += 1
        for row in (hero_first, monster_first):
            _record_outcome(hero_stats, row.outcome, hero_perspective=True)
            _record_outcome(monster_stats, row.outcome, hero_perspective=False)

        updates.append(PairedEloUpdate(
            pair_block_id=hero_first.pair_block_id,
            hero_configuration_id=hero_first.hero_configuration_id,
            monster_configuration_id=hero_first.monster_configuration_id,
            hero_score=hero_score,
            expected_hero_score=_rounded(expected_hero_score),
            hero_rating_before=_rounded(hero_before),
            monster_rating_before=_rounded(monster_before),
            hero_rating_after=_rounded(hero_after),
            monster_rating_after=_rounded(monster_after),
            rating_transfer=_rounded(transfer),
        ))

    hero_standings = _build_standings("hero", ratings, statistics)
    monster_standings = _build_standings("monster_party", ratings, statistics)
    return ProvisionalPairedEloResult(
        estimator="provisional paired-block Elo; mean score over two opening treatments",
        config=config,
        completed_pair_block_count=len(blocks),
        hero_standings=hero_standings,
        monster_standings=monster_standings,
        updates=tuple(updates),
    )


def _build_standings(
    side_kind: SideKind,
    ratings: dict[tuple[SideKind, str], float],
    statistics: dict[tuple[SideKind, str], _StandingAccumulator],
) -> tuple[ProvisionalEloStanding, ...]:
    participants = sorted(
        (
            (configuration_id, rating)
            for (participant_side, configuration_id), rating in ratings.items()
            if participant_side == side_kind
        ),
        key=lambda item: (-item[1], item[0]),
    )
    return tuple(
        ProvisionalEloStanding(
            rank=rank,
            configuration_id=configuration_id,
            side_kind=side_kind,
            rating=_rounded(rating),
            pair_blocks=statistics[(side_kind, configuration_id)].pair_blocks,
            matches=statistics[(side_kind, configuration_id)].matches,
            wins=statistics[(side_kind, configuration_id)].wins,
            draws=statistics[(side_kind, configuration_id)].draws,
            losses=statistics[(side_kind, configuration_id)].losses,
        )
        for rank, (configuration_id, rating) in enumerate(participants, start=1)
    )


def _ratings_by_participant(
    result: ProvisionalPairedEloResult,
) -> dict[tuple[SideKind, str], float]:
    return {
        (row.side_kind, row.configuration_id): row.rating
        for row in (*result.hero_standings, *result.monster_standings)
    }


def _record_outcome(
    statistics: _StandingAccumulator,
    outcome: RatedOutcome,
    *,
    hero_perspective: bool,
) -> None:
    statistics.matches += 1
    if outcome == RatedOutcome.DRAW:
        statistics.draws += 1
    elif (outcome == RatedOutcome.HERO_WIN) == hero_perspective:
        statistics.wins += 1
    else:
        statistics.losses += 1


def _hero_score(outcome: RatedOutcome) -> float:
    if outcome == RatedOutcome.HERO_WIN:
        return 1.0
    if outcome == RatedOutcome.MONSTER_WIN:
        return 0.0
    return 0.5


def _rounded(value: float) -> float:
    return round(float(value), 10)
