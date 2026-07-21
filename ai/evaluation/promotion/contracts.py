"""Typed contracts for assignment-balanced policy promotion experiments."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictFrozenModel(BaseModel):
    """Immutable promotion contract that rejects accidental schema drift."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class MatchupFamily(str, Enum):
    """Mechanical composition represented by a roster comparison."""

    HERO_VS_MONSTER = "hero_vs_monster"
    HERO_VS_HERO = "hero_vs_hero"
    MONSTER_VS_MONSTER = "monster_vs_monster"
    MIRROR = "mirror"


class PromotionPanel(str, Enum):
    """Longitudinal or expanding content panel used by promotion gates."""

    FROZEN_CORE = "frozen_core"
    EXPANDED = "expanded"


class PromotionOutcome(str, Enum):
    """Official outcome from neutral side A's perspective."""

    SIDE_A_WIN = "side_a_win"
    SIDE_B_WIN = "side_b_win"
    DRAW = "draw"


OpeningTreatment = Literal["side_a_first", "side_b_first"]
PolicyAssignment = Literal["candidate_a", "candidate_b"]


class PromotionMatchupSpec(StrictFrozenModel):
    """One roster edge selected before contexts and treatments expand."""

    matchup_id: str = Field(description="Stable roster-comparison identifier.")
    side_a_configuration_id: str = Field(description="Configuration mounted on side A.")
    side_b_configuration_id: str = Field(description="Configuration mounted on side B.")
    family: MatchupFamily = Field(description="Hero/monster composition family.")
    panel: PromotionPanel = Field(description="Frozen longitudinal or expanded content panel.")
    tags: tuple[str, ...] = Field(default_factory=tuple, description="Protected reporting and regression strata.")


class PromotionScheduleEntry(StrictFrozenModel):
    """One isolated policy-assignment treatment inside a four-match block."""

    schedule_index: int = Field(ge=0, description="Canonical zero-based commit order.")
    match_id: str = Field(description="Stable identity of this exact treatment row.")
    comparison_block_id: str = Field(description="Four-row block sharing all non-treatment inputs.")
    matchup_id: str = Field(description="Roster edge represented by this row.")
    matchup_family: MatchupFamily = Field(description="Roster composition family.")
    panel: PromotionPanel = Field(description="Longitudinal or expanding content panel.")
    matchup_tags: tuple[str, ...] = Field(description="Protected reporting strata copied from the matchup.")
    side_a_configuration_id: str = Field(description="Side-A roster configuration.")
    side_a_configuration_hash: str = Field(description="Authenticated side-A mechanical hash.")
    side_b_configuration_id: str = Field(description="Side-B roster configuration.")
    side_b_configuration_hash: str = Field(description="Authenticated side-B mechanical hash.")
    side_a_policy_generation_id: str = Field(description="Executable generation assigned to side A.")
    side_a_policy_executable_hash: str = Field(description="Authenticated side-A policy executable hash.")
    side_b_policy_generation_id: str = Field(description="Executable generation assigned to side B.")
    side_b_policy_executable_hash: str = Field(description="Authenticated side-B policy executable hash.")
    candidate_generation_id: str = Field(description="Candidate identity under test.")
    baseline_generation_id: str = Field(description="Accepted baseline identity.")
    battlefield_id: str = Field(description="Battlefield context identifier.")
    battlefield_hash: str = Field(description="Authenticated battlefield hash.")
    deployment_id: str = Field(description="Symmetric side deployment identifier.")
    deployment_hash: str = Field(description="Authenticated deployment hash.")
    simulation_seed: int = Field(description="Random seed shared by the complete comparison block.")
    opening_treatment: OpeningTreatment = Field(description="Side forced to open after unchanged initiative rolls.")
    policy_assignment: PolicyAssignment = Field(description="Side receiving the candidate policy.")


class PromotionSchedule(StrictFrozenModel):
    """Immutable counterbalanced schedule for one candidate promotion attempt."""

    schema_version: Literal[1] = Field(default=1, description="Promotion schedule schema version.")
    experiment_id: str = Field(description="Stable experiment identifier.")
    created_at: str = Field(description="UTC schedule creation timestamp.")
    candidate_generation_id: str = Field(description="Candidate generation under test.")
    baseline_generation_id: str = Field(description="Current accepted baseline generation.")
    catalog_hash: str = Field(description="Hash of roster, context, and executable policy catalogs.")
    entries: tuple[PromotionScheduleEntry, ...] = Field(description="Canonical ordered treatment rows.")
    schedule_hash: str = Field(description="SHA-256 of all schedule inputs and rows.")

    def entries_by_block(self) -> dict[str, tuple[PromotionScheduleEntry, ...]]:
        """Return complete comparison blocks in deterministic order."""
        grouped: dict[str, list[PromotionScheduleEntry]] = {}
        for entry in self.entries:
            grouped.setdefault(entry.comparison_block_id, []).append(entry)
        return {key: tuple(rows) for key, rows in sorted(grouped.items())}


class PromotionObservation(StrictFrozenModel):
    """One scientifically admitted treatment supplied to the joint model."""

    match_id: str = Field(description="Retained match identity.")
    comparison_block_id: str = Field(description="Counterbalanced four-match block identity.")
    side_a_configuration_id: str = Field(description="Side-A roster identity.")
    side_b_configuration_id: str = Field(description="Side-B roster identity.")
    side_a_policy_generation_id: str = Field(description="Side-A policy generation.")
    side_b_policy_generation_id: str = Field(description="Side-B policy generation.")
    candidate_generation_id: str = Field(description="Candidate generation under test.")
    baseline_generation_id: str = Field(description="Accepted baseline generation.")
    battlefield_id: str = Field(description="Battlefield context.")
    deployment_id: str = Field(description="Deployment context.")
    opening_treatment: OpeningTreatment = Field(description="Opening-side treatment.")
    matchup_family: MatchupFamily = Field(description="Roster composition family.")
    panel: PromotionPanel = Field(description="Frozen or expanded panel.")
    matchup_tags: tuple[str, ...] = Field(default_factory=tuple, description="Protected reporting strata.")
    outcome: PromotionOutcome = Field(description="Observed side-A result.")
