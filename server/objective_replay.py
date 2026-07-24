"""Minimal cold objective replay consumed by the normal game reducer.

An ended-game replay retains only the inputs used during first play: one
replicated-world seed, concrete completion events, and objective combat-log
frames.  It deliberately excludes command responses, action discovery,
session/heartbeat state, terminal snapshots, telemetry, and non-completion
engine phases.
"""

from __future__ import annotations

from bisect import bisect_right
from hashlib import sha256
import json
from typing import Final, Tuple

from pydantic import BaseModel, ConfigDict, Field, model_validator

from server.replicated_world import ReplicatedWorld
from server.timeline_contracts import (
    GameEventFrame,
    ObjectiveCombatLogFramesResponse,
    TIMELINE_CONTRACT_HASH,
    TimelineProtocolIdentity,
)


OBJECTIVE_REPLAY_CONTRACT_VERSION: Final[int] = 1
OBJECTIVE_REPLAY_CONTRACT_HASH: Final[str]


class ObjectiveReplayModel(BaseModel):
    """Immutable, closed base for durable replay values."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class ObjectiveReplaySeed(ObjectiveReplayModel):
    """Reducer state and source cursors represented before replay begins."""

    event_cursor: int = Field(
        ge=0,
        description="Objective source cursor represented by the initial world.",
    )
    combat_log_cursor: int = Field(
        ge=0,
        description="Objective log cursor represented at the initial boundary.",
    )
    world: ReplicatedWorld = Field(description="Initial objective reducer world.")


class ObjectiveReplayBundle(ObjectiveReplayModel):
    """Self-validating minimal objective replay for one ended encounter."""

    replay_contract_version: int = Field(
        default=OBJECTIVE_REPLAY_CONTRACT_VERSION,
        ge=1,
    )
    replay_contract_hash: str = Field(
        default_factory=lambda: OBJECTIVE_REPLAY_CONTRACT_HASH,
        min_length=1,
    )
    protocol: TimelineProtocolIdentity = Field(
        default_factory=TimelineProtocolIdentity,
        description="Portable decoder identities for timeline and event values.",
    )
    game_id: str = Field(min_length=1)
    encounter_uuid: str = Field(min_length=1)
    source_stream_id: str = Field(
        min_length=1,
        description="Objective encounter timeline owning event and log coordinates.",
    )
    generation_id: str = Field(min_length=1)
    seed: ObjectiveReplaySeed
    terminal_event_cursor: int = Field(ge=1)
    terminal_combat_log_cursor: int = Field(ge=0)
    events: Tuple[GameEventFrame, ...] = Field(
        default_factory=tuple,
        description="Every concrete completion after the seed, in source order.",
    )
    combat_log_frames: ObjectiveCombatLogFramesResponse = Field(
        description="Complete objective log source, including seed-time records.",
    )

    @model_validator(mode="after")
    def validate_reducer_input(self) -> "ObjectiveReplayBundle":
        """Reject mixed identities, lossy phases, gaps, and false barriers."""
        if self.replay_contract_version != OBJECTIVE_REPLAY_CONTRACT_VERSION:
            raise ValueError("unsupported objective replay contract version")
        if self.replay_contract_hash != OBJECTIVE_REPLAY_CONTRACT_HASH:
            raise ValueError("objective replay contract hash mismatch")

        encounter = self.seed.world.state.encounter
        if encounter is None or encounter.uuid != self.encounter_uuid:
            raise ValueError("replay seed does not describe the declared encounter")
        if self.source_stream_id != self.encounter_uuid:
            raise ValueError("replay source stream must equal the encounter UUID")
        if self.seed.event_cursor >= self.terminal_event_cursor:
            raise ValueError("replay seed must precede the terminal event cursor")
        if self.seed.combat_log_cursor > self.terminal_combat_log_cursor:
            raise ValueError("replay seed log cursor exceeds the terminal log cursor")

        logs = self.combat_log_frames
        if logs.source_stream_id != self.source_stream_id:
            raise ValueError("combat-log source stream does not match replay")
        if logs.generation_id != self.generation_id:
            raise ValueError("combat-log generation does not match replay")
        if logs.retained_from_cursor != 0 or logs.from_cursor != 0:
            raise ValueError("replay must retain objective combat logs from cursor zero")
        if logs.through_cursor != logs.total:
            raise ValueError("replay combat-log window must be complete")
        if logs.total != self.terminal_combat_log_cursor:
            raise ValueError("terminal combat-log cursor does not match replay logs")

        log_event_cursors = tuple(frame.event_cursor for frame in logs.frames)
        if self.seed.combat_log_cursor > logs.total:
            raise ValueError("seed combat-log cursor exceeds retained replay logs")
        if any(
            frame.event_cursor > self.seed.event_cursor
            for frame in logs.frames[: self.seed.combat_log_cursor]
        ):
            raise ValueError("seed includes a combat log beyond its event barrier")

        previous_event_cursor = self.seed.event_cursor
        previous_log_cursor = self.seed.combat_log_cursor
        for frame in self.events:
            if frame.source_stream_id != self.source_stream_id:
                raise ValueError("event source stream does not match replay")
            if frame.generation_id != self.generation_id:
                raise ValueError("event generation does not match replay")
            if frame.event_cursor <= previous_event_cursor:
                raise ValueError("replay completion events must be strictly ordered")
            if frame.event_cursor > self.terminal_event_cursor:
                raise ValueError("replay event exceeds the terminal cursor")
            payload = frame.event.model_dump(mode="json")
            if payload.get("phase") != "completion":
                raise ValueError("replay may retain only completion events")
            expected_log_cursor = bisect_right(log_event_cursors, frame.event_cursor)
            if frame.combat_log_cursor != expected_log_cursor:
                raise ValueError("event combat-log cursor does not match its exact barrier")
            if frame.combat_log_cursor < previous_log_cursor:
                raise ValueError("replay event log barriers must be nondecreasing")
            previous_event_cursor = frame.event_cursor
            previous_log_cursor = frame.combat_log_cursor

        if not self.events:
            raise ValueError("ended replay must retain a terminal completion event")
        terminal = self.events[-1]
        terminal_payload = terminal.event.model_dump(mode="json")
        if terminal.event_cursor != self.terminal_event_cursor:
            raise ValueError("last retained completion is not the terminal event cursor")
        if terminal_payload.get("event_type") != "encounter_end":
            raise ValueError("last retained completion must end the encounter")
        if any(frame.event_cursor > self.terminal_event_cursor for frame in logs.frames):
            raise ValueError("combat log exceeds the terminal event cursor")
        return self


_OBJECTIVE_REPLAY_SEMANTICS: Final[dict[str, object]] = {
    "source": "objective reducer inputs retained during first play",
    "events": "ordered concrete completion GameEventFrame values",
    "combat_logs": "complete objective-only non-null combat-log window",
    "excluded": (
        "non_completion_event_phases",
        "command_responses",
        "available_actions",
        "session_metadata",
        "heartbeats",
        "terminal_snapshot",
        "telemetry",
    ),
}


def objective_replay_wire_schema() -> dict[str, object]:
    """Return the complete transitive durable objective-replay schema."""
    return {
        "contract_version": OBJECTIVE_REPLAY_CONTRACT_VERSION,
        "timeline_contract_hash": TIMELINE_CONTRACT_HASH,
        "semantics": _OBJECTIVE_REPLAY_SEMANTICS,
        "seed": ObjectiveReplaySeed.model_json_schema(mode="serialization"),
        "bundle": ObjectiveReplayBundle.model_json_schema(mode="serialization"),
    }


OBJECTIVE_REPLAY_CONTRACT_HASH = sha256(
    json.dumps(
        objective_replay_wire_schema(),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
).hexdigest()


def objective_replay_contract_summary() -> dict[str, object]:
    """Return portable replay schema identity for manifests and SDK checks."""
    return {
        "replay_contract_version": OBJECTIVE_REPLAY_CONTRACT_VERSION,
        "replay_contract_hash": OBJECTIVE_REPLAY_CONTRACT_HASH,
    }


__all__ = [
    "OBJECTIVE_REPLAY_CONTRACT_HASH",
    "OBJECTIVE_REPLAY_CONTRACT_VERSION",
    "ObjectiveReplayBundle",
    "ObjectiveReplaySeed",
    "objective_replay_contract_summary",
    "objective_replay_wire_schema",
]
