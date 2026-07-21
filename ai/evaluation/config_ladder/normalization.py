"""UUID-independent semantic match projections for determinism audits."""

from __future__ import annotations

import json
from hashlib import sha256
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ai.external_selfplay import ExternalSelfPlayResult, ExternalSelfPlayTrace


class NormalizedCommand(BaseModel):
    """Stable gameplay-relevant projection of one selected command."""

    model_config = ConfigDict(frozen=True)

    command_index: int = Field(ge=0, description="Command order within the match.")
    round_number: int = Field(ge=0, description="Encounter round at selection time.")
    turn_index: int = Field(ge=0, description="Encounter turn index at selection time.")
    actor_name: str = Field(description="Stable configured actor display name.")
    actor_faction: str | None = Field(default=None, description="Actor faction.")
    actor_position: tuple[int, int] | None = Field(default=None, description="Actor position before the command.")
    actor_hp: int | None = Field(default=None, description="Subjectively known actor hit points.")
    command_type: str = Field(description="Submitted command family.")
    template_name: str | None = Field(default=None, description="Selected engine action template.")
    semantic_key: str | None = Field(default=None, description="Typed action semantic key.")
    target_name: str | None = Field(default=None, description="Selected target name.")
    target_position: tuple[int, int] | None = Field(default=None, description="Selected target position.")
    target_path: tuple[tuple[int, int], ...] = Field(default_factory=tuple, description="Selected movement path.")
    affected_entity_names: tuple[str, ...] = Field(default_factory=tuple, description="Known affected entity names.")
    extra_target_names: tuple[str, ...] = Field(default_factory=tuple, description="Additional selected target names.")
    reason: str = Field(description="Policy selection reason.")
    logical_tags: tuple[str, ...] = Field(default_factory=tuple, description="Logical action tags.")
    command_status: str | None = Field(default=None, description="Server command result status.")
    action_resolution: str | None = Field(default=None, description="Typed gameplay resolution.")
    outcome_code: str | None = Field(default=None, description="Stable engine outcome code.")
    outcome_logical_tags: tuple[str, ...] = Field(default_factory=tuple, description="Logical result tags.")


class NormalizedMatchResult(BaseModel):
    """Scientific result projection excluding runtime and transport identity."""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal[1] = Field(default=1, description="Normalization schema version.")
    arena_id: str = Field(description="Composed arena identity.")
    status: str = Field(description="Self-play terminal status.")
    command_count: int = Field(ge=0, description="Selected command count.")
    final_round: int | None = Field(default=None, description="Final encounter round.")
    final_state: str | None = Field(default=None, description="Final encounter lifecycle state.")
    final_hp_by_actor: dict[str, int] = Field(description="Final hit points keyed by configured actor name.")
    final_faction_by_actor: dict[str, str] = Field(description="Final faction keyed by configured actor name.")
    commands: tuple[NormalizedCommand, ...] = Field(description="Stable semantic command sequence.")
    semantic_hash: str = Field(description="SHA-256 over all non-hash semantic fields.")


def normalize_selfplay_result(result: ExternalSelfPlayResult) -> NormalizedMatchResult:
    """Remove process, UUID, cursor, timing, and transport data from a match."""
    commands = tuple(_normalize_trace(trace) for trace in result.traces)
    payload: dict[str, Any] = {
        "schema_version": 1,
        "arena_id": result.arena_id,
        "status": result.status,
        "command_count": result.command_count,
        "final_round": result.final_round,
        "final_state": result.final_state,
        "final_hp_by_actor": dict(sorted(result.final_hp_by_actor.items())),
        "final_faction_by_actor": dict(sorted(result.final_faction_by_actor.items())),
        "commands": [row.model_dump(mode="json") for row in commands],
    }
    semantic_hash = sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return NormalizedMatchResult(**payload, semantic_hash=semantic_hash)


def _normalize_trace(trace: ExternalSelfPlayTrace) -> NormalizedCommand:
    """Project one trace onto stable gameplay semantics."""
    return NormalizedCommand(
        command_index=trace.command_index,
        round_number=trace.round_number,
        turn_index=trace.turn_index,
        actor_name=trace.actor_name,
        actor_faction=trace.actor_faction,
        actor_position=trace.actor_position,
        actor_hp=trace.actor_hp,
        command_type=trace.command_type,
        template_name=_stable_template_name(trace.template_name),
        semantic_key=trace.semantic_key,
        target_name=trace.target_name,
        target_position=trace.target_position,
        target_path=tuple(trace.target_path),
        affected_entity_names=tuple(trace.affected_entity_names),
        extra_target_names=tuple(trace.extra_target_names or ()),
        reason=trace.reason,
        logical_tags=tuple(trace.logical_tags),
        command_status=trace.command_status,
        action_resolution=trace.action_resolution,
        outcome_code=trace.outcome_code,
        outcome_logical_tags=tuple(trace.outcome_logical_tags),
    )


def _stable_template_name(template_name: str | None) -> str | None:
    """Remove runtime item identity from an otherwise semantic action name."""
    if template_name is None:
        return None
    return template_name.split("__item_", 1)[0]
