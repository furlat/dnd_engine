"""Artifact-backed checks for the bounded Codex local read model."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Optional

from ai.codex_tools.hot_runtime import (
    HotCodexQueryRequest,
    HotCodexSession,
)
from dnd.ai.contracts.observation_replay import apply_observation_frame, materialize_snapshot
from dnd.ai.contracts.observation import SubjectiveWorldState
from ai.policy import PolicyDecisionTelemetry
from dnd.ai.contracts.control import CommandResult, DecisionEpoch
from ai.subjective.models import AgentState
from ai.subjective.queries import SubjectiveActionFilter, SubjectiveQuerySelection


ARTIFACT = (
    Path(__file__).parents[2]
    / "ai/evidence/direct_codex_runs/20260714-rotation-3-02-codex-sorcerer-vs-ai-v148-single-stack.json"
)


def test_retained_dense_epoch_has_bounded_default_and_complete_paged_reads() -> None:
    """The real 443-row Sorcerer epoch stays small without discarding any row."""
    runtime = _ArtifactRuntime(_dense_artifact_world())
    session = HotCodexSession(
        runtime=runtime,
        claim_id="artifact-claim",
        faction="heroes",
        controlled_entity_uuids=tuple(runtime.store.world.session.controlled_entity_uuids),
    )

    index = session.bootstrap()
    epoch = runtime.store.world.current_epoch
    assert epoch is not None
    expected_row_ids = [row.row_id for row in epoch.affordances.all_rows]
    observed_row_ids: list[str] = []
    offset = 0
    while True:
        page = session.query(HotCodexQueryRequest(
            revision=index.revision,
            selection=SubjectiveQuerySelection(
                action_filter=SubjectiveActionFilter(offset=offset, limit=100),
            ),
        ))
        observed_row_ids.extend(row.affordance.row_id for row in page.actions)
        if page.next_action_offset is None:
            break
        offset = page.next_action_offset

    assert index.action_index.total_rows == 443
    assert len(index.model_dump_json()) < 32_000
    assert observed_row_ids == expected_row_ids
    assert runtime.bootstrap_calls == 1


def test_retained_dense_epoch_queries_exact_geometry_and_full_policy_on_demand() -> None:
    """Omitted path and policy detail remains locally recoverable at one revision."""
    runtime = _ArtifactRuntime(_dense_artifact_world())
    session = HotCodexSession(
        runtime=runtime,
        claim_id="artifact-claim",
        faction="heroes",
        controlled_entity_uuids=tuple(runtime.store.world.session.controlled_entity_uuids),
    )
    index = session.bootstrap()
    epoch = runtime.store.world.current_epoch
    assert epoch is not None
    movement = next(
        row for row in epoch.affordances.position_actions
        if row.action_category == "movement" and row.targets and row.targets[0].path
    )

    details = session.query(HotCodexQueryRequest(
        revision=index.revision,
        selection=SubjectiveQuerySelection(
            row_ids=(movement.row_id,),
            include_session=True,
            include_encounter=True,
            include_all_capabilities=True,
            recent_log_limit=10,
        ),
        include_policy_decision=True,
    ))

    assert details.actions[0].affordance is movement
    assert details.actions[0].affordance.targets[0].path == movement.targets[0].path
    assert details.session == runtime.store.world.session
    assert details.encounter == runtime.store.world.encounter
    assert details.capabilities == epoch.affordances.capabilities
    assert details.policy_decision is not None
    assert len(details.policy_decision.candidates) == index.policy_candidate_count
    assert len(details.policy_decision.trace) == index.policy_trace_step_count
    assert runtime.bootstrap_calls == 1


def test_compact_combat_log_preserves_bounded_subjective_causal_children() -> None:
    """The default read identifies visible multi-target outcomes without an extra query."""
    row = {
        "entry_type": "multi_entity_action",
        "source_name": "Sorcerer",
        "source_uuid": "sorcerer-uuid",
        "compact": "Sorcerer uses Magic Missile -> 10 targets",
        "success": True,
        "sub_entries": [
            {
                "entry_type": "spell_damage",
                "target_name": f"Skeleton {index}",
                "target_uuid": f"target-{index}",
                "compact": f"Magic Missile hits Skeleton {index} for {index} damage",
                "success": index > 0,
            }
            for index in range(10)
        ],
    }

    world = _dense_artifact_world().model_copy(update={"combat_logs": [row]})
    assert world.current_epoch is not None
    summary = HotCodexSession(
        runtime=_ArtifactRuntime(world),
        claim_id="claim-log",
        faction="heroes",
        controlled_entity_uuids=(world.current_epoch.actor_uuid,),
    ).bootstrap().recent_combat_logs[0]

    assert summary.source_name == "Sorcerer"
    assert summary.source_uuid == "sorcerer-uuid"
    assert len(summary.sub_entries) == 8
    assert summary.omitted_sub_entry_count == 2
    assert summary.sub_entries[0].target_name == "Skeleton 0"
    assert summary.sub_entries[0].target_uuid == "target-0"
    assert summary.sub_entries[0].success is False
    assert summary.sub_entries[-1].compact == "Magic Missile hits Skeleton 7 for 7 damage"


class _ArtifactRuntime:
    """Network-free runtime double around one replayed retained world."""

    def __init__(self, world: SubjectiveWorldState) -> None:
        self.store = SimpleNamespace(
            world=world,
            agent_state=AgentState(),
        )
        self.bootstrap_calls = 0
        self.policy_events: list[PolicyDecisionTelemetry] = []

    def bootstrap(self) -> None:
        """Record the only permitted bootstrap boundary."""
        self.bootstrap_calls += 1

    def wait_for_epoch(self) -> DecisionEpoch:
        """Reject unexpected stream waits in read-only projection tests."""
        raise AssertionError("read-only artifact runtime must not wait for an epoch")

    def execute(
        self,
        row_id: str,
        *,
        command_id: Optional[str] = None,
        prefer_safe: bool = True,
        extra_target_uuids: Optional[list[str]] = None,
    ) -> CommandResult:
        """Reject unexpected commands in read-only projection tests."""
        raise AssertionError(
            "read-only artifact runtime must not execute "
            f"{row_id} ({command_id=}, {prefer_safe=}, {extra_target_uuids=})"
        )

    def emit_policy_decision(self, event: PolicyDecisionTelemetry) -> None:
        """Retain local policy telemetry without network transport."""
        self.policy_events.append(event)

    def end_turn(self) -> CommandResult:
        """Reject unexpected turn completion in read-only projection tests."""
        raise AssertionError("read-only artifact runtime must not end a turn")

    def close(self) -> None:
        """Close the network-free test runtime."""


def _dense_artifact_world() -> SubjectiveWorldState:
    """Replay the retained run to its densest current-epoch revision."""
    payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    world = materialize_snapshot(payload["initial_subjective_snapshot"])
    best = world
    best_row_count = len(world.current_epoch.affordances.all_rows) if world.current_epoch else 0
    for frame in payload["observation_frames_response"]["frames"]:
        if frame["observation_cursor"] <= world.observation_cursor:
            continue
        world = apply_observation_frame(world, frame)
        row_count = len(world.current_epoch.affordances.all_rows) if world.current_epoch else 0
        if row_count > best_row_count:
            best = world
            best_row_count = row_count
    return best
