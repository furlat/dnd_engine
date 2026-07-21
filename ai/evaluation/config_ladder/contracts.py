"""Versioned contracts for connected configuration rating experiments."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


OpeningTreatment = Literal["hero_first", "monster_first"]


class RatedOutcome(str, Enum):
    """Official binary or drawn outcome from the hero perspective."""

    HERO_WIN = "hero_win"
    MONSTER_WIN = "monster_win"
    DRAW = "draw"


class ConnectedScheduleEntry(BaseModel):
    """One isolated match in a connected configuration experiment."""

    model_config = ConfigDict(frozen=True)

    schedule_index: int = Field(ge=0, description="Canonical zero-based commit order.")
    match_id: str = Field(description="Stable match identifier.")
    pair_block_id: str = Field(description="Identifier shared by paired opening treatments.")
    hero_configuration_id: str = Field(description="Rated hero configuration identifier.")
    hero_configuration_hash: str = Field(description="Mechanical hash expected from the hero catalog.")
    monster_configuration_id: str = Field(description="Rated monster-party configuration identifier.")
    monster_configuration_hash: str = Field(description="Mechanical hash expected from the monster catalog.")
    battlefield_id: str = Field(description="Battlefield context identifier.")
    battlefield_hash: str = Field(description="Battlefield content hash expected by the worker.")
    deployment_id: str = Field(description="Spawn deployment context identifier.")
    deployment_hash: str = Field(description="Deployment content hash expected by the worker.")
    simulation_seed: int = Field(description="Random seed shared by both opening treatments in the block.")
    opening_treatment: OpeningTreatment = Field(description="Forced faction at the front of unchanged initiative rolls.")


class ScheduleExclusion(BaseModel):
    """Typed reason a requested factorial cell was not scheduled."""

    model_config = ConfigDict(frozen=True)

    hero_configuration_id: str = Field(description="Requested hero configuration.")
    monster_configuration_id: str = Field(description="Requested monster-party configuration.")
    battlefield_id: str = Field(description="Requested battlefield.")
    deployment_id: str = Field(description="Requested deployment.")
    reason_code: str = Field(description="Stable machine-readable incompatibility code.")
    message: str = Field(description="Human-readable incompatibility explanation.")


class ConnectedRatingSchedule(BaseModel):
    """Immutable schedule for a connected cross-context rating experiment."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = Field(default=1, description="Schedule schema version.")
    experiment_id: str = Field(description="Stable experiment identifier.")
    created_at: str = Field(description="UTC schedule creation timestamp.")
    catalog_hash: str = Field(description="Combined participant and context catalog hash.")
    entries: tuple[ConnectedScheduleEntry, ...] = Field(description="Canonical ordered match rows.")
    exclusions: tuple[ScheduleExclusion, ...] = Field(default_factory=tuple, description="Rejected factorial cells.")
    schedule_hash: str = Field(description="Hash of all schedule inputs and ordered rows.")

    def entries_by_pair_block(self) -> dict[str, tuple[ConnectedScheduleEntry, ...]]:
        """Group ordered entries by paired opening-treatment block."""
        grouped: dict[str, list[ConnectedScheduleEntry]] = {}
        for entry in self.entries:
            grouped.setdefault(entry.pair_block_id, []).append(entry)
        return {key: tuple(rows) for key, rows in grouped.items()}


class ConnectivityReport(BaseModel):
    """Connectivity diagnostics for the rated bipartite participant graph."""

    model_config = ConfigDict(frozen=True)

    connected: bool = Field(description="Whether every rated participant belongs to one component.")
    component_count: int = Field(ge=0, description="Number of connected graph components.")
    hero_count: int = Field(ge=0, description="Number of distinct hero configurations.")
    monster_party_count: int = Field(ge=0, description="Number of distinct monster-party configurations.")
    edge_count: int = Field(ge=0, description="Number of distinct hero-versus-party comparisons.")
    component_members: tuple[tuple[str, ...], ...] = Field(description="Sorted participant ids in each component.")
    degree_by_participant: dict[str, int] = Field(description="Distinct opponent count by participant.")
    bridge_edges: tuple[tuple[str, str], ...] = Field(default_factory=tuple, description="Graph edges whose removal disconnects a component.")


class StrengthObservation(BaseModel):
    """One clean match supplied to the official strength estimator."""

    model_config = ConfigDict(frozen=True)

    match_id: str = Field(description="Retained match identifier.")
    pair_block_id: str = Field(description="Paired opening-treatment block identifier.")
    hero_configuration_id: str = Field(description="Hero configuration identifier.")
    monster_configuration_id: str = Field(description="Monster-party configuration identifier.")
    battlefield_id: str = Field(description="Battlefield context identifier.")
    deployment_id: str = Field(description="Deployment context identifier.")
    opening_treatment: OpeningTreatment = Field(description="Opening treatment applied to the match.")
    outcome: RatedOutcome = Field(description="Observed match result.")


class StrengthRating(BaseModel):
    """Adjusted strength estimate for one rated side configuration."""

    model_config = ConfigDict(frozen=True)

    configuration_id: str = Field(description="Rated configuration identifier.")
    side_kind: Literal["hero", "monster_party"] = Field(description="Rated side category.")
    coefficient: float = Field(description="Fitted log-odds strength coefficient.")
    adjusted_elo: float = Field(description="Coefficient converted to centered Elo units.")
    standard_error: float | None = Field(default=None, description="Observed-information standard error when estimable.")
    elo_lower_95: float | None = Field(default=None, description="Lower 95 percent Elo confidence bound.")
    elo_upper_95: float | None = Field(default=None, description="Upper 95 percent Elo confidence bound.")
    games: int = Field(ge=0, description="Clean observations involving this configuration.")


class ContextEffect(BaseModel):
    """Adjusted log-odds effect for an experimental context level."""

    model_config = ConfigDict(frozen=True)

    context_kind: Literal["battlefield", "deployment", "opening"] = Field(description="Context family.")
    context_id: str = Field(description="Context level identifier.")
    coefficient: float = Field(description="Fitted log-odds effect relative to the reference level.")
    elo_equivalent: float = Field(description="Effect converted to Elo-equivalent units.")
    standard_error: float | None = Field(default=None, description="Observed-information standard error when estimable.")


class StrengthDesignDiagnostics(BaseModel):
    """Identifiability and graph diagnostics for one model fit."""

    model_config = ConfigDict(frozen=True)

    connected: bool = Field(description="Whether the participant graph is connected.")
    component_count: int = Field(ge=0, description="Participant graph component count.")
    rank: int = Field(ge=0, description="Numerical rank of the constrained design matrix.")
    parameter_count: int = Field(ge=0, description="Number of fitted design parameters.")
    observation_count: int = Field(ge=0, description="Number of model observations after draw handling.")


class ConfigurationStrengthResult(BaseModel):
    """Official adjusted configuration strength fit and publication gates."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = Field(default=1, description="Strength result schema version.")
    estimator: str = Field(description="Estimator and link function description.")
    converged: bool = Field(description="Whether numerical optimization converged.")
    publishable: bool = Field(description="Whether all scientific publication gates passed.")
    gate_reasons: tuple[str, ...] = Field(default_factory=tuple, description="Failed publication gates.")
    regularization: float = Field(ge=0, description="Declared L2 penalty strength.")
    hero_ratings: tuple[StrengthRating, ...] = Field(description="Adjusted hero standings.")
    monster_ratings: tuple[StrengthRating, ...] = Field(description="Adjusted monster-party standings.")
    context_effects: tuple[ContextEffect, ...] = Field(description="Battlefield, deployment, and opening effects.")
    design: StrengthDesignDiagnostics = Field(description="Graph and design-matrix diagnostics.")
    log_loss: float = Field(ge=0, description="In-sample binary log loss.")
    brier_score: float = Field(ge=0, description="In-sample Brier score.")
    iterations: int = Field(ge=0, description="Optimizer iteration count.")
