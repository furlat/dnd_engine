"""Dependency-neutral transport values for authorized objective diagnostics.

The objective diagnostics surface is intentionally separate from subjective
player replication.  It exposes one reducer-complete world snapshot and the
same cold event/log timeline contracts used by ended-game replay, without
carrying sessions, commands, heartbeats, or hot engine objects.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from server.replicated_world import ReplicatedWorld
from server.timeline_contracts import TimelineModel, TimelineProtocolIdentity


class ObjectiveDiagnosticsCursorState(TimelineModel):
    """Identity and exact source cursors for one objective timeline."""

    projection: Literal["objective"] = Field(
        default="objective",
        description="Explicit boundary preventing subjective decoder reuse.",
    )
    protocol: TimelineProtocolIdentity = Field(default_factory=TimelineProtocolIdentity)
    source_stream_id: str = Field(
        min_length=1,
        description="Encounter timeline owning both objective cursors.",
    )
    generation_id: str = Field(
        min_length=1,
        description="EventQueue generation containing the objective timeline.",
    )
    event_cursor: int = Field(
        ge=0,
        description="Exact consumed objective event cursor.",
    )
    combat_log_cursor: int = Field(
        ge=0,
        description="Exact consumed objective combat-log cursor.",
    )


class ObjectiveDiagnosticsBootstrap(ObjectiveDiagnosticsCursorState):
    """Atomic objective reducer seed and the source cursors it represents."""

    world: ReplicatedWorld = Field(
        description="Complete objective world represented by both cursors.",
    )

    @model_validator(mode="after")
    def validate_encounter_source(self) -> "ObjectiveDiagnosticsBootstrap":
        encounter = self.world.state.encounter
        if encounter is None:
            raise ValueError("objective diagnostics require an encounter world")
        if encounter.uuid != self.source_stream_id:
            raise ValueError("objective world encounter does not match source stream")
        return self


class ObjectiveDiagnosticsSync(ObjectiveDiagnosticsCursorState):
    """First SSE frame fixing the stream identity and replay boundaries."""


class SubjectiveParityMismatch(TimelineModel):
    """One bounded, privacy-safe difference in the censored render manifest."""

    path: str = Field(min_length=1, max_length=512)
    expected_json: str = Field(max_length=4096)
    actual_json: str = Field(max_length=4096)


class SubjectiveRenderParityDiagnosticsResponse(TimelineModel):
    """ADMINISTER-only comparison of live subjective state with an independent oracle."""

    projection: Literal["subjective_parity"] = "subjective_parity"
    source_stream_id: str = Field(min_length=1)
    generation_id: str = Field(min_length=1)
    perspective_epoch_id: str = Field(min_length=1)
    source_event_cursor: int = Field(ge=0)
    observation_cursor: int = Field(ge=0)
    presentation_cursor: int = Field(ge=0)
    combat_log_cursor: int = Field(ge=0)
    expected_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    actual_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    matches: bool
    compared_path_count: int = Field(
        ge=1,
        description="Number of manifest paths compared; prevents vacuous success.",
    )
    visible_tile_count: int = Field(ge=0)
    structural_edge_count: int = Field(ge=0)
    door_edge_count: int = Field(ge=0)
    non_empty_structural_edges: bool
    mismatches: tuple[SubjectiveParityMismatch, ...] = Field(
        default_factory=tuple,
        max_length=100,
    )

    @model_validator(mode="after")
    def validate_result(self) -> "SubjectiveRenderParityDiagnosticsResponse":
        if self.door_edge_count > self.structural_edge_count:
            raise ValueError("door edge count cannot exceed structural edge count")
        if self.non_empty_structural_edges != (self.structural_edge_count > 0):
            raise ValueError("structural-edge non-empty flag does not match its count")
        if self.matches != (
            self.expected_digest == self.actual_digest and not self.mismatches
        ):
            raise ValueError("parity status does not match digests and mismatches")
        return self


__all__ = [
    "ObjectiveDiagnosticsBootstrap",
    "ObjectiveDiagnosticsCursorState",
    "ObjectiveDiagnosticsSync",
    "SubjectiveParityMismatch",
    "SubjectiveRenderParityDiagnosticsResponse",
]
