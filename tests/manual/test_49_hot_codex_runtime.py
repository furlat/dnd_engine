"""Persistent local runtime contracts for direct Codex control."""

from __future__ import annotations

import json
from pathlib import Path
from threading import Event, Thread
from types import SimpleNamespace
from typing import Any, cast

from fastapi.testclient import TestClient
import pytest

from ai.codex_tools import hot_runtime as hot_runtime_module
from ai.codex_tools.client import CodexToolClient
from ai.codex_tools.hot_runtime import (
    HotCodexBusyError,
    HotCodexExecuteRequest,
    HotCodexQueryRequest,
    HotCodexRevision,
    HotCodexSession,
    HotCodexStaleRevisionError,
    create_hot_codex_app,
)
from ai.codex_tools.session_transcript import (
    CodexSessionTranscript,
    SessionReleasePayload,
    SessionTranscript,
    TranscriptRecordType,
)
from ai.codex_tools.representation.profiles import (
    BALANCED_V2_PROFILE_ID,
    build_builtin_representation_registry,
)
from ai.codex_tools.contracts import TakeoverClaimInfo, TakeoverEntityInfo
from ai.ordered_delivery import OrderedDeliveryTimeoutError
from server.agent_protocol.observation import (
    KnowledgeState,
    ObservationEncounterState,
    ObservationEntityFact,
    ObservationObjectFact,
    ObservationSessionState,
    ObservationTileFact,
    SubjectiveWorldState,
)
from server.agent_protocol.semantics import ActionSemantics, ActionTag, action_semantics_ref
from ai.policy import PolicyDecisionCorrelation, PolicyDecisionTelemetry, PolicyHost
from ai.policy.telemetry import QueuedPolicyTelemetrySink
from server.agent_protocol.telemetry import AgentEvent
from server.agent_protocol.control import (
    ActionResolutionStatus,
    ActionAffordance,
    ActionEconomyState,
    ActionTarget,
    AffordanceSet,
    CommandResult,
    CommandResultStatus,
    DecisionEpoch,
    DecisionEpochReason,
)
from ai.subjective.runtime import QueuedAgentEventSink, SubjectiveEncounterEndedError
from ai.subjective.queries import (
    SubjectiveActionFilter,
    SubjectiveAreaQuery,
    SubjectiveQuerySelection,
)


def test_hot_session_bootstraps_once_and_queries_one_local_world() -> None:
    """The turn index and detail query share one persistent materialization."""
    runtime = _FakeRuntime(_world())
    session = HotCodexSession(
        runtime=runtime,
        claim_id="claim-1",
        faction="heroes",
        controlled_entity_uuids=("actor",),
    )

    index = session.bootstrap()
    details = session.query(HotCodexQueryRequest(
        revision=index.revision,
        selection=SubjectiveQuerySelection(row_ids=("entity|Strike|uuid=enemy",)),
    ))
    second_index = session.turn_index()

    assert runtime.bootstrap_calls == 1
    assert runtime.snapshot_fetch_calls == 1
    assert index.revision == second_index.revision
    assert index.action_index.total_rows == 1
    assert index.action_index.rows_by_bucket == {"entity_actions": 1}
    assert details.actions[0].affordance.row_id == "entity|Strike|uuid=enemy"
    assert details.revision == index.revision
    assert index.local_timing.total_ms >= 0


def test_hot_turn_index_reports_older_logs_omitted_from_bounded_view() -> None:
    """The default index discloses when earlier local logs remain queryable."""
    world = _world().model_copy(update={
        "combat_logs": [
            {
                "entry_type": "action",
                "source_name": "Sorcerer",
                "compact": f"Action {index}",
            }
            for index in range(5)
        ],
    })
    session = HotCodexSession(
        runtime=_FakeRuntime(world),
        claim_id="claim-1",
        faction="heroes",
        controlled_entity_uuids=("actor",),
    )

    index = session.bootstrap()

    assert [row.compact for row in index.recent_combat_logs] == [
        "Action 2",
        "Action 3",
        "Action 4",
    ]
    assert index.omitted_combat_log_count == 2


def test_hot_attach_adopts_existing_claim_without_takeover(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A validation-created claim becomes the hot runtime's exact lease."""
    class FakeControlClient:
        def __init__(self, base_url: str) -> None:
            self.base_url = base_url
            self.closed = False
            controls.append(self)

        def resolve_control_claim(self, **kwargs: object) -> TakeoverClaimInfo:
            assert kwargs["claim_id"] == "claim-1"
            assert kwargs["session_id"] == "session"
            assert kwargs["force"] is False
            return TakeoverClaimInfo(
                claim_id="claim-1",
                session_id="session",
                name="Codex Validation Monsters",
                faction="monsters",
                created_at=10.0,
                last_heartbeat_at=11.0,
                lease_seconds=600.0,
                expires_at=611.0,
                is_expired=False,
                claimed_entities=[],
            )

        def release(self, claim_id: str) -> dict[str, object]:
            return {"status": "released", "claim_id": claim_id}

        def heartbeat(self, _claim_id: str) -> dict[str, object]:
            return {"status": "heartbeat"}

        def close(self) -> None:
            self.closed = True

    controls: list[FakeControlClient] = []
    runtime = _FakeRuntime(_world())
    monkeypatch.setattr(hot_runtime_module, "CodexToolClient", FakeControlClient)
    monkeypatch.setattr(
        hot_runtime_module,
        "SubjectiveRuntime",
        lambda **_kwargs: runtime,
    )
    monkeypatch.setattr(HotCodexSession, "start_heartbeat", lambda self: None)

    session = HotCodexSession.attach(
        base_url="http://127.0.0.1:8000",
        claim_id="claim-1",
        session_id="session",
        transcript_directory=tmp_path,
    )

    assert session.claim_id == "claim-1"
    assert session.faction == "monsters"
    assert session.lease_seconds == 600.0
    assert runtime.bootstrap_calls == 1
    session.release()
    assert controls[0].closed is True


def test_hot_attach_infers_faction_for_explicit_entity_claim(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """An explicit hero claim must not inherit the CLI's monster-side default label."""
    class FakeControlClient:
        def __init__(self, _base_url: str) -> None:
            pass

        def resolve_control_claim(self, **_kwargs: object) -> TakeoverClaimInfo:
            return TakeoverClaimInfo(
                claim_id="claim-hero",
                session_id="session-hero",
                name="Codex Hero",
                faction=None,
                created_at=10.0,
                last_heartbeat_at=11.0,
                lease_seconds=600.0,
                expires_at=611.0,
                is_expired=False,
                claimed_entities=[TakeoverEntityInfo(
                    entity_uuid="actor",
                    entity_name="Sorcerer",
                    faction="heroes",
                    previous_controller_uuid="controller",
                )],
            )

        def close(self) -> None:
            pass

    runtime = _FakeRuntime(_world())
    monkeypatch.setattr(hot_runtime_module, "CodexToolClient", FakeControlClient)
    monkeypatch.setattr(hot_runtime_module, "SubjectiveRuntime", lambda **_kwargs: runtime)
    monkeypatch.setattr(HotCodexSession, "start_heartbeat", lambda self: None)

    session = HotCodexSession.attach(
        base_url="http://127.0.0.1:8000",
        claim_id="claim-hero",
        session_id="session-hero",
        transcript_directory=tmp_path,
    )

    assert session.faction == "heroes"


def test_hot_release_finalizes_local_transcript_when_upstream_is_unavailable(
    tmp_path: Path,
) -> None:
    """Remote teardown failure cannot discard the locally complete session record."""
    class UnavailableControlClient:
        def release(self, _claim_id: str) -> dict[str, object]:
            raise ConnectionError("backend already stopped")

        def close(self) -> None:
            return None

    runtime = _FakeRuntime(_world())
    transcript = CodexSessionTranscript(
        runtime_id="runtime-release",
        session_id="session",
        claim_id="claim-release",
        faction="monsters",
        controlled_entity_uuids=("actor",),
        representation_manifest=build_builtin_representation_registry().resolve_profile(
            BALANCED_V2_PROFILE_ID
        ),
        directory=tmp_path,
    )
    session = HotCodexSession(
        runtime=runtime,
        claim_id="claim-release",
        faction="monsters",
        controlled_entity_uuids=("actor",),
        control_client=cast(CodexToolClient, UnavailableControlClient()),
        runtime_id="runtime-release",
        transcript=transcript,
    )
    session.bootstrap()

    released = session.release()
    exported = SessionTranscript.model_validate_json(
        transcript.final_json_path.read_text(encoding="utf-8")
    )

    assert released.status == "released"
    assert released.upstream_status == "unavailable"
    assert exported.records[-1].record_type.value == "session_released"
    release_payload = SessionReleasePayload.model_validate(exported.records[-1].payload)
    assert release_payload.shutdown_failures == (
        "upstream release: ConnectionError: backend already stopped",
    )


def test_hot_release_drains_actor_telemetry_before_relinquishing_ownership(
    tmp_path: Path,
) -> None:
    """Queued actor telemetry drains before release, even if local close fails."""
    order: list[str] = []
    delivery_started = Event()
    allow_delivery = Event()
    runtime_closed = Event()
    delivered: list[AgentEvent] = []

    class OwnershipCheckingSink:
        def emit(self, event: AgentEvent) -> None:
            self.emit_many([event])

        def emit_many(self, events: list[AgentEvent]) -> None:
            delivery_started.set()
            assert allow_delivery.wait(timeout=1.0)
            assert control.ownership_held is True
            order.append("actor_telemetry.delivered")
            delivered.extend(events)

    actor_telemetry = QueuedAgentEventSink(
        OwnershipCheckingSink(),
        session_id="session",
    )

    class ActorTelemetryRuntime(_FakeRuntime):
        def close(self) -> None:
            order.append("runtime.close.started")
            allow_delivery.set()
            actor_telemetry.close(timeout_seconds=1.0)
            runtime_closed.set()
            order.append("runtime.close.finished")
            raise RuntimeError("runtime cleanup failed after telemetry flush")

    class OwnershipControlClient:
        def __init__(self) -> None:
            self.ownership_held = True

        def release(self, _claim_id: str) -> dict[str, object]:
            assert runtime_closed.is_set()
            assert delivered == [actor_event]
            order.append("upstream.release")
            self.ownership_held = False
            return {"status": "released"}

        def close(self) -> None:
            order.append("control.close")

    control = OwnershipControlClient()
    runtime = ActorTelemetryRuntime(_world())
    transcript = CodexSessionTranscript(
        runtime_id="runtime-ordered-release",
        session_id="session",
        claim_id="claim-ordered-release",
        faction="monsters",
        controlled_entity_uuids=("actor",),
        representation_manifest=build_builtin_representation_registry().resolve_profile(
            BALANCED_V2_PROFILE_ID
        ),
        directory=tmp_path,
    )
    session = HotCodexSession(
        runtime=runtime,
        claim_id="claim-ordered-release",
        faction="monsters",
        controlled_entity_uuids=("actor",),
        control_client=cast(CodexToolClient, control),
        runtime_id="runtime-ordered-release",
        transcript=transcript,
    )
    actor_event = AgentEvent(
        session_id="session",
        actor_uuid="actor",
        epoch_id="epoch-1",
        observation_cursor=5,
        event_type="command.stream_result.accepted",
        source="test.release",
        summary="Actor-scoped telemetry queued before release.",
    )
    actor_telemetry.emit(actor_event)
    assert delivery_started.wait(timeout=1.0)

    released = session.release()
    exported = SessionTranscript.model_validate_json(
        transcript.final_json_path.read_text(encoding="utf-8")
    )

    assert released.status == "released"
    assert released.upstream_status == "released"
    assert control.ownership_held is False
    assert actor_telemetry.worker_alive is False
    assert order == [
        "runtime.close.started",
        "actor_telemetry.delivered",
        "runtime.close.finished",
        "upstream.release",
        "control.close",
    ]
    release_payload = SessionReleasePayload.model_validate(exported.records[-1].payload)
    assert release_payload.shutdown_failures == (
        "subjective runtime close: RuntimeError: "
        "runtime cleanup failed after telemetry flush",
    )


def test_hot_execute_requires_exact_viewed_revision_and_uses_runtime_command_flow() -> None:
    """A direct write is revision fenced and never rediscovers rows upstream."""
    runtime = _FakeRuntime(_world())
    session = HotCodexSession(
        runtime=runtime,
        claim_id="claim-1",
        faction="heroes",
        controlled_entity_uuids=("actor",),
    )
    session.bootstrap()
    revision = session.revision()

    with pytest.raises(HotCodexStaleRevisionError):
        session.execute(HotCodexExecuteRequest(
            revision=revision.model_copy(update={"epoch_id": "old-epoch"}),
            row_id="entity|Strike|uuid=enemy",
        ))

    result = session.execute(HotCodexExecuteRequest(
        revision=revision,
        row_id="entity|Strike|uuid=enemy",
    ))

    assert result.command_result.status is CommandResultStatus.ACCEPTED
    assert runtime.execute_calls == [("entity|Strike|uuid=enemy", True, None)]
    assert runtime.snapshot_fetch_calls == 1
    assert result.revision.observation_cursor == 6
    assert result.local_total_ms >= 0
    assert result.local_timing.total_ms == result.local_total_ms
    assert result.local_timing.validation_and_prepare_ms >= 0
    assert result.local_timing.runtime_command_ms >= 0
    assert result.local_timing.policy_result_ms >= 0
    assert result.local_timing.followup_projection_ms >= 0


def test_hot_compact_command_receipt_keeps_next_context_without_diagnostics() -> None:
    """Normal operator output remains actionable and bounded after an accepted action."""
    runtime = _FakeRuntime(_world())
    session = HotCodexSession(
        runtime=runtime,
        claim_id="claim-1",
        faction="heroes",
        controlled_entity_uuids=("actor",),
    )
    session.bootstrap()

    receipt = session.execute_compact(HotCodexExecuteRequest(
        revision=session.revision(),
        row_id="entity|Strike|uuid=enemy",
    ))
    payload = receipt.model_dump(mode="json")
    encoded = json.dumps(payload, separators=(",", ":"))

    assert payload["status"] == "accepted"
    assert payload["follow_up"]["revision"]["observation_cursor"] == 6
    assert "runtime_timing" not in payload
    assert "policy_result" not in payload
    assert "selected_policy" not in payload["follow_up"]
    assert "capabilities" not in payload["follow_up"]
    assert "topology" not in payload["follow_up"]
    assert "transcript" not in payload["follow_up"]
    assert len(encoded.encode("utf-8")) < 5_000


def test_balanced_brief_retains_typed_object_summary_without_full_object_dump() -> None:
    """Profile-safe object summaries remain useful when complete objects are omitted."""
    session = HotCodexSession(
        runtime=_FakeRuntime(_door_policy_world()),
        claim_id="claim-1",
        faction="heroes",
        controlled_entity_uuids=("actor",),
        representation_profile_id=BALANCED_V2_PROFILE_ID,
    )
    session.bootstrap()

    brief = session.brief()

    assert session.turn_index().known_objects == ()
    assert len(brief.known_objects) == 1
    assert brief.known_objects[0].uuid == "door"
    assert brief.known_objects[0].is_open is False
    assert brief.known_objects[0].state_keys == ("is_open",)


def test_command_follow_up_is_an_explicit_manifest_setting() -> None:
    """A result-only ablation changes output without changing command execution."""
    runtime = _FakeRuntime(_world())
    session = HotCodexSession(
        runtime=runtime,
        claim_id="claim-1",
        faction="heroes",
        controlled_entity_uuids=("actor",),
    )
    session.bootstrap()
    session.representation_manifest = session.representation_manifest.model_copy(update={
        "components": tuple(
            component.model_copy(update={
                "parameters": {
                    **component.parameters,
                    "include_command_follow_up": False,
                },
            })
            if component.spec.component_id == "presentation.typed_json"
            else component
            for component in session.representation_manifest.components
        ),
    })

    receipt = session.execute_compact(HotCodexExecuteRequest(
        revision=session.revision(),
        row_id="entity|Strike|uuid=enemy",
    ))

    assert receipt.status == "accepted"
    assert receipt.follow_up is None


def test_hot_session_rejects_a_second_concurrent_command_writer() -> None:
    """One local runtime has exactly one command writer."""
    runtime = _FakeRuntime(_world())
    session = HotCodexSession(
        runtime=runtime,
        claim_id="claim-1",
        faction="heroes",
        controlled_entity_uuids=("actor",),
    )
    session.bootstrap()
    assert session._command_lock.acquire(blocking=False)
    try:
        with pytest.raises(HotCodexBusyError):
            session.execute(HotCodexExecuteRequest(
                revision=session.revision(),
                row_id="entity|Strike|uuid=enemy",
            ))
    finally:
        session._command_lock.release()


def test_hot_wait_consumes_the_existing_runtime_stream_without_snapshot_reload() -> None:
    """Waiting advances the persistent store instead of rebuilding it."""
    runtime = _FakeRuntime(_world(current_epoch=None, cursor=4))
    runtime.wait_world = _world()
    session = HotCodexSession(
        runtime=runtime,
        claim_id="claim-1",
        faction="heroes",
        controlled_entity_uuids=("actor",),
    )
    session.bootstrap()

    result = session.wait_for_turn()

    assert runtime.wait_calls == 1
    assert runtime.snapshot_fetch_calls == 1
    assert result.revision.epoch_id == "epoch-1"
    assert result.action_index.total_rows == 1


def test_hot_wait_returns_a_terminal_view_when_no_future_epoch_can_exist() -> None:
    """Encounter completion must end a hot wait instead of hanging forever."""
    runtime = _TerminalFakeRuntime(_world(current_epoch=None, cursor=4))
    session = HotCodexSession(
        runtime=runtime,
        claim_id="claim-1",
        faction="heroes",
        controlled_entity_uuids=("actor",),
    )
    session.bootstrap()

    result = session.wait_for_turn()

    assert result.is_terminal is True
    assert result.encounter_state == "ended"
    assert result.revision.epoch_id is None
    assert result.action_index.total_rows == 0
    assert runtime.snapshot_fetch_calls == 1


def test_hot_watch_records_opponent_terminal_state_once_without_command(
    tmp_path: Path,
) -> None:
    """A terminal stream observation seals evidence without inventing a write."""
    runtime = _TerminalFakeRuntime(_world(current_epoch=None, cursor=4))
    transcript = CodexSessionTranscript(
        runtime_id="runtime-opponent-terminal",
        session_id="session",
        claim_id="claim-opponent-terminal",
        faction="heroes",
        controlled_entity_uuids=("actor",),
        representation_manifest=build_builtin_representation_registry().resolve_profile(
            BALANCED_V2_PROFILE_ID
        ),
        directory=tmp_path,
    )
    session = HotCodexSession(
        runtime=runtime,
        claim_id="claim-opponent-terminal",
        faction="heroes",
        controlled_entity_uuids=("actor",),
        runtime_id="runtime-opponent-terminal",
        transcript=transcript,
    )
    session.bootstrap()
    app = create_hot_codex_app(session, bearer_token="secret-token")

    with TestClient(app) as client:
        brief_response = client.post(
            "/v1/watch/brief",
            headers={"Authorization": "Bearer secret-token"},
        )
        repeated_response = client.post(
            "/v1/watch",
            headers={"Authorization": "Bearer secret-token"},
        )
    exported = transcript.export()

    assert brief_response.status_code == 200
    brief = brief_response.json()
    assert brief["is_terminal"] is True
    assert brief["transcript"]["terminal"] is True
    assert brief["transcript"]["finalized"] is True
    assert repeated_response.status_code == 200
    assert repeated_response.json()["is_terminal"] is True
    assert transcript.status().terminal is True
    record_types = [record.record_type for record in exported.records]
    assert record_types.count(TranscriptRecordType.TERMINAL_SUMMARY) == 1
    assert TranscriptRecordType.COMMAND not in record_types
    assert TranscriptRecordType.COMMAND_INTENT not in record_types
    assert TranscriptRecordType.COMMAND_ACKNOWLEDGEMENT not in record_types


def test_hot_wait_does_not_block_health_reads_while_stream_is_idle() -> None:
    """An idle stream waiter must not monopolize the task-local state lock."""
    runtime = _BlockingFakeRuntime(_world(current_epoch=None, cursor=4))
    runtime.wait_world = _world()
    session = HotCodexSession(
        runtime=runtime,
        claim_id="claim-1",
        faction="heroes",
        controlled_entity_uuids=("actor",),
    )
    session.bootstrap()
    waiter = Thread(target=session.wait_for_turn)

    waiter.start()
    assert runtime.wait_started.wait(timeout=1)
    health = session.health()
    runtime.release_wait.set()
    waiter.join(timeout=1)

    assert health.status == "ready"
    assert health.revision is not None
    assert health.revision.epoch_id is None
    assert waiter.is_alive() is False


def test_hot_local_api_requires_bearer_token_and_exposes_typed_revision() -> None:
    """The task-local daemon is authenticated even on loopback."""
    runtime = _FakeRuntime(_world())
    session = HotCodexSession(
        runtime=runtime,
        claim_id="claim-1",
        faction="heroes",
        controlled_entity_uuids=("actor",),
    )
    session.bootstrap()
    app = create_hot_codex_app(session, bearer_token="secret-token")

    with TestClient(app) as client:
        assert client.get("/v1/turn").status_code == 401
        response = client.get(
            "/v1/turn",
            headers={"Authorization": "Bearer secret-token"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert HotCodexRevision.model_validate(payload["revision"]).epoch_id == "epoch-1"
    assert payload["actor"]["uuid"] == "actor"
    assert "actions" not in payload
    assert "turn" not in payload
    assert "policy_decision" not in payload


def test_hot_codex_view_and_command_share_the_typed_policy_host_lifecycle() -> None:
    """Codex sees and may execute the same acceptance-gated routine proposal."""
    runtime = _FakeRuntime(_door_policy_world())
    session = HotCodexSession(
        runtime=runtime,
        claim_id="claim-1",
        faction="monsters",
        controlled_entity_uuids=("actor",),
    )
    view = session.bootstrap()
    session.turn_index()
    session.turn_index()
    session.flush_policy_telemetry()

    assert view.selected_policy is not None
    assert view.selected_policy.intent.row_id == "move-row"  # type: ignore[union-attr]
    assert len(runtime.policy_events) == 1
    assert runtime.policy_events[0].decision.selected == view.selected_policy
    assert runtime.flush_agent_event_calls == 1

    result = session.execute(HotCodexExecuteRequest(
        revision=view.revision,
        row_id="move-row",
    ))

    assert result.policy_result is not None
    assert result.policy_result.disposition.value == "accepted"
    assert result.policy_result.memory_advanced is True
    memory = session.policy_host.memory_for("session", "actor")
    assert memory.active_routine is not None
    assert memory.active_routine.routine_id == "routine.approach_open_reassess"


def test_hot_policy_telemetry_delivery_is_complete_but_off_the_decision_path() -> None:
    """A blocked telemetry destination cannot delay the local policy view."""
    runtime = _BlockingPolicyTelemetryRuntime(_door_policy_world())
    session = HotCodexSession(
        runtime=runtime,
        claim_id="claim-1",
        faction="monsters",
        controlled_entity_uuids=("actor",),
    )

    try:
        view = session.bootstrap()

        assert view.selected_policy is not None
        assert runtime.telemetry_started.wait(timeout=1)
        assert runtime.policy_events == []
    finally:
        runtime.release_telemetry.set()
        session.flush_policy_telemetry()

    assert len(runtime.policy_events) == 1
    assert runtime.policy_events[0].decision.selected == view.selected_policy


def test_queued_policy_telemetry_sink_preserves_order_and_flushes() -> None:
    """Queued policy telemetry delivers every canonical event in source order."""
    runtime = _FakeRuntime(_world())
    queued = QueuedPolicyTelemetrySink(runtime)
    first = _policy_telemetry("first")
    second = _policy_telemetry("second")

    queued.emit_policy_decision(first)
    queued.emit_policy_decision(second)
    queued.flush()
    queued.close()

    assert runtime.policy_events == [first, second]
    assert queued.worker_alive is False


def test_queued_policy_telemetry_close_is_bounded_and_retryable() -> None:
    """A blocked destination is explicit and can finish after it recovers."""
    runtime = _BlockingPolicyTelemetryRuntime(_world())
    queued = QueuedPolicyTelemetrySink(runtime, max_depth=1)

    queued.emit_policy_decision(_policy_telemetry("blocked"))
    assert runtime.telemetry_started.wait(timeout=1.0)
    with pytest.raises(
        OrderedDeliveryTimeoutError,
        match="did not stop",
    ):
        queued.close(timeout_seconds=0.01)
    assert queued.worker_alive is True

    runtime.release_telemetry.set()
    queued.close(timeout_seconds=1.0)

    assert queued.worker_alive is False
    assert len(runtime.policy_events) == 1


def test_hot_session_can_end_turn_from_correlated_rejection_epoch() -> None:
    """Rejected writes leave the persistent runtime ready for a fresh command."""
    runtime = _RejectThenEndRuntime(_world())
    session = HotCodexSession(
        runtime=runtime,
        claim_id="claim-1",
        faction="heroes",
        controlled_entity_uuids=("actor",),
    )
    first_view = session.bootstrap()

    rejected = session.execute(HotCodexExecuteRequest(
        revision=first_view.revision,
        row_id="entity|Strike|uuid=enemy",
    ))
    ended = session.end_turn(
        hot_runtime_module.HotCodexEndTurnRequest(revision=rejected.revision)
    )

    assert rejected.command_result.status is CommandResultStatus.REJECTED
    assert rejected.revision.epoch_id == "epoch-2"
    assert ended.command_result.status is CommandResultStatus.ACCEPTED
    assert runtime.end_turn_calls == 1
    assert runtime.snapshot_fetch_calls == 1


def test_hot_turn_index_stays_small_and_details_are_queried_locally() -> None:
    """Movement-row growth stays out of the default turn response."""
    runtime = _FakeRuntime(_movement_world(row_count=32, cursor=5))
    session = HotCodexSession(
        runtime=runtime,
        claim_id="claim-1",
        faction="heroes",
        controlled_entity_uuids=("actor",),
    )

    index = session.bootstrap()
    details = session.query(HotCodexQueryRequest(
        revision=index.revision,
        selection=SubjectiveQuerySelection(
            action_filter=SubjectiveActionFilter(
                buckets=("position_actions",),
                offset=30,
                limit=2,
            ),
        ),
    ))

    one_row_size = len(HotCodexSession(
        runtime=_FakeRuntime(_movement_world(row_count=1, cursor=5)),
        claim_id="claim-small",
        faction="heroes",
        controlled_entity_uuids=("actor",),
    ).bootstrap().model_dump_json())
    assert len(index.model_dump_json()) - one_row_size < 1_000
    assert index.action_index.total_rows == 32
    assert [row.affordance.row_id for row in details.actions] == [
        "position|Move|pos=31,0",
        "position|Move|pos=32,0",
    ]
    assert details.actions[-1].affordance.targets[0].path[-1] == (32, 0)
    assert details.total_matching_actions == 32
    assert runtime.snapshot_fetch_calls == 1

    runtime.store.world = _movement_world(row_count=32, cursor=6)
    with pytest.raises(HotCodexStaleRevisionError):
        session.query(HotCodexQueryRequest(
            revision=index.revision,
            selection=SubjectiveQuerySelection(row_ids=("position|Move|pos=1,0",)),
        ))


def test_hot_turn_index_summarizes_multi_target_allocation_rows() -> None:
    """Default Codex view exposes allocation capacity without expanding rows."""
    session = HotCodexSession(
        runtime=_FakeRuntime(_multi_target_world()),
        claim_id="claim-1",
        faction="heroes",
        controlled_entity_uuids=("actor",),
    )

    index = session.bootstrap()

    assert index.action_index.total_rows == 2
    assert index.action_index.rows_by_tag["target.multi"] == 2
    assert [row.row_id for row in index.action_index.multi_target_rows] == [
        "entity|Magic Missile|uuid=enemy-a",
        "entity|Magic Missile|uuid=enemy-b",
    ]
    first = index.action_index.multi_target_rows[0]
    assert first.display_name == "Magic Missile"
    assert first.primary_target_name == "Skeleton A"
    assert first.primary_target_uuid == "enemy-a"
    assert first.selectable_target_count == 2
    assert first.allocation_count == 3
    assert first.extra_target_slots == 2
    assert first.allow_same_target is True


def test_hot_query_returns_only_locally_known_subjective_facts() -> None:
    """Area and identifier reads cannot recover facts absent from subjective state."""
    world = _door_policy_world()
    session = HotCodexSession(
        runtime=_FakeRuntime(world),
        claim_id="claim-1",
        faction="monsters",
        controlled_entity_uuids=("actor",),
    )
    index = session.bootstrap()

    details = session.query(HotCodexQueryRequest(
        revision=index.revision,
        selection=SubjectiveQuerySelection(
            entity_uuids=("actor", "hidden-enemy"),
            object_uuids=("door", "hidden-chest"),
            tile_keys=("0,0", "99,99"),
            area=SubjectiveAreaQuery(min_x=0, max_x=3, min_y=0, max_y=0),
        ),
    ))

    assert [entity.uuid for entity in details.entities] == ["actor"]
    assert [obj.uuid for obj in details.objects] == ["door"]
    assert [tile.key for tile in details.tiles] == ["0,0", "1,0", "2,0", "3,0"]
    assert details.missing_entity_uuids == ("hidden-enemy",)
    assert details.missing_object_uuids == ("hidden-chest",)
    assert details.missing_tile_keys == ("99,99",)


def test_hot_api_exposes_compact_brief_and_revision_fenced_query_reads() -> None:
    """The local API separates compact automatic context from typed detail reads."""
    runtime = _FakeRuntime(_door_policy_world())
    session = HotCodexSession(
        runtime=runtime,
        claim_id="claim-1",
        faction="monsters",
        controlled_entity_uuids=("actor",),
    )
    index = session.bootstrap()
    app = create_hot_codex_app(session, bearer_token="secret-token")
    headers = {"Authorization": "Bearer secret-token"}

    with TestClient(app) as client:
        brief_response = client.get("/v1/brief", headers=headers)
        assert brief_response.status_code == 200
        brief = brief_response.json()
        assert brief["revision"] == index.revision.model_dump(mode="json")
        assert brief["action_families"][0]["source_action_id"] == "move-row"
        assert brief["action_families"][0]["direct_row_id"] == "move-row"
        assert brief["action_families"][0]["row_count"] == 1
        assert "row_ids" not in brief["action_families"][0]
        assert brief["semantic_coverage"]["source_action_count"] == 1
        assert brief["semantic_coverage"]["unknown_count"] == 0
        assert "selected_policy" not in brief
        assert "local_timing" not in brief
        assert client.get("/v1/actions", headers=headers).status_code == 404
        response = client.post(
            "/v1/query",
            headers=headers,
            json={
                "revision": index.revision.model_dump(mode="json"),
                "selection": {
                    "action_filter": {"source_action_ids": ["move-row"]},
                },
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["revision"] == index.revision.model_dump(mode="json")
    assert payload["actions"][0]["affordance"]["row_id"] == "move-row"
    assert payload["actions"][0]["affordance"]["targets"][0]["path"][-1] == [2, 0]
    assert runtime.snapshot_fetch_calls == 1


def test_terminal_command_receipt_includes_subjective_match_summary() -> None:
    """The command ending a match returns a useful terminal result instead of silence."""
    runtime = _TerminalExecuteRuntime(_world())
    session = HotCodexSession(
        runtime=runtime,
        claim_id="claim-1",
        faction="heroes",
        controlled_entity_uuids=("actor",),
    )
    session.bootstrap()

    receipt = session.execute_compact(HotCodexExecuteRequest(
        revision=session.revision(),
        row_id="entity|Strike|uuid=enemy",
    ))

    assert receipt.follow_up is not None
    assert receipt.follow_up.is_terminal is True
    assert receipt.follow_up.encounter_summary is not None
    assert receipt.follow_up.encounter_summary.available is True
    assert receipt.follow_up.encounter_summary.outcome == "controlled_survived"
    assert receipt.follow_up.encounter_summary.subjective_winning_faction == "heroes"


class _FakeRuntime:
    """Minimal persistent runtime test double."""

    def __init__(self, world: SubjectiveWorldState) -> None:
        self.store = SimpleNamespace(world=world, materialized=world)
        self.bootstrap_calls = 0
        self.snapshot_fetch_calls = 0
        self.wait_calls = 0
        self.execute_calls: list[tuple[str, bool, Any]] = []
        self.end_turn_calls = 0
        self.wait_world: SubjectiveWorldState | None = None
        self.policy_events: list[PolicyDecisionTelemetry] = []
        self.flush_agent_event_calls = 0

    def bootstrap(self) -> None:
        self.bootstrap_calls += 1
        self.snapshot_fetch_calls += 1

    def wait_for_epoch(self) -> DecisionEpoch:
        self.wait_calls += 1
        if self.wait_world is not None:
            self.store.world = self.wait_world
            self.store.world = self.wait_world
        assert self.store.world.current_epoch is not None
        return self.store.world.current_epoch

    def execute(
        self,
        row_id: str,
        *,
        command_id: str | None = None,
        prefer_safe: bool = True,
        extra_target_uuids: list[str] | None = None,
    ) -> CommandResult:
        self.execute_calls.append((row_id, prefer_safe, extra_target_uuids))
        world = self.store.world.model_copy(update={"observation_cursor": 6})
        self.store.world = world
        self.store.world = world
        return CommandResult(
            status=CommandResultStatus.ACCEPTED,
            action_resolution=ActionResolutionStatus.COMPLETED,
            command_id=command_id or "command-1",
            session_id="session",
            actor_uuid="actor",
            requested_epoch_id="epoch-1",
            current_epoch_id="epoch-1",
            row_id=row_id,
            accepted_at_observation_cursor=6,
        )

    def end_turn(self) -> CommandResult:
        self.end_turn_calls += 1
        return CommandResult(
            status=CommandResultStatus.ACCEPTED,
            command_id="command-end",
            session_id="session",
            actor_uuid="actor",
            requested_epoch_id="epoch-1",
        )

    def close(self) -> None:
        return None

    def emit_policy_decision(self, event: PolicyDecisionTelemetry) -> None:
        self.policy_events.append(event)

    def flush_agent_events(self) -> None:
        self.flush_agent_event_calls += 1


def _policy_telemetry(decision_id: str) -> PolicyDecisionTelemetry:
    """Build one valid canonical policy event for queue-order tests."""
    world = _door_policy_world()
    decision = PolicyHost().decide(world)
    return PolicyDecisionTelemetry(
        event_id=f"policy-decision:{decision_id}",
        decision_id=decision_id,
        policy_id="shared.test",
        policy_version="test",
        controller_mode="test",
        correlation=PolicyDecisionCorrelation(
            session_id="session",
            actor_uuid="actor",
            epoch_id="epoch-1",
            observation_cursor=world.observation_cursor,
            decision_id=decision_id,
        ),
        decision=decision,
    )


class _BlockingFakeRuntime(_FakeRuntime):
    """Runtime double that keeps a stream wait open until the test releases it."""

    def __init__(self, world: SubjectiveWorldState) -> None:
        super().__init__(world)
        self.wait_started = Event()
        self.release_wait = Event()

    def wait_for_epoch(self) -> DecisionEpoch:
        self.wait_started.set()
        assert self.release_wait.wait(timeout=1)
        return super().wait_for_epoch()


class _BlockingPolicyTelemetryRuntime(_FakeRuntime):
    """Runtime double whose telemetry transport blocks until released."""

    def __init__(self, world: SubjectiveWorldState) -> None:
        super().__init__(world)
        self.telemetry_started = Event()
        self.release_telemetry = Event()

    def emit_policy_decision(self, event: PolicyDecisionTelemetry) -> None:
        self.telemetry_started.set()
        assert self.release_telemetry.wait(timeout=1)
        super().emit_policy_decision(event)


class _RejectThenEndRuntime(_FakeRuntime):
    """Runtime double that streams a replacement epoch after rejection."""

    def execute(
        self,
        row_id: str,
        *,
        command_id: str | None = None,
        prefer_safe: bool = True,
        extra_target_uuids: list[str] | None = None,
    ) -> CommandResult:
        self.execute_calls.append((row_id, prefer_safe, extra_target_uuids))
        current_epoch = self.store.world.current_epoch
        assert current_epoch is not None
        replacement = current_epoch.model_copy(update={
            "epoch_id": "epoch-2",
            "epoch_index": 2,
            "basis_observation_cursor": 6,
            "reason": DecisionEpochReason.ACTION_REJECTED,
            "affordances": current_epoch.affordances.model_copy(update={
                "computed_at_observation_cursor": 6,
            }),
        })
        world = self.store.world.model_copy(update={
            "observation_cursor": 6,
            "current_epoch": replacement,
            "epoch_cursor": 2,
        })
        self.store.world = world
        self.store.world = world
        return CommandResult(
            status=CommandResultStatus.REJECTED,
            command_id=command_id or "command-rejected",
            session_id="session",
            actor_uuid="actor",
            requested_epoch_id="epoch-1",
            current_epoch_id="epoch-2",
            row_id=row_id,
            message="Action rejected",
            accepted_at_observation_cursor=6,
        )

    def end_turn(self) -> CommandResult:
        self.end_turn_calls += 1
        return CommandResult(
            status=CommandResultStatus.ACCEPTED,
            command_id="command-end",
            session_id="session",
            actor_uuid="actor",
            requested_epoch_id="epoch-2",
        )


class _TerminalFakeRuntime(_FakeRuntime):
    """Runtime double whose stream reaches encounter completion."""

    def wait_for_epoch(self) -> DecisionEpoch:
        self.wait_calls += 1
        assert self.store.world.encounter is not None
        encounter = self.store.world.encounter.model_copy(update={"state": "ended"})
        world = self.store.world.model_copy(update={
            "observation_cursor": self.store.world.observation_cursor + 1,
            "encounter": encounter,
            "current_epoch": None,
        })
        self.store.world = world
        self.store.world = world
        raise SubjectiveEncounterEndedError("encounter ended")


class _TerminalExecuteRuntime(_FakeRuntime):
    """Runtime double whose accepted action ends the encounter."""

    def execute(
        self,
        row_id: str,
        *,
        command_id: str | None = None,
        prefer_safe: bool = True,
        extra_target_uuids: list[str] | None = None,
    ) -> CommandResult:
        self.execute_calls.append((row_id, prefer_safe, extra_target_uuids))
        assert self.store.world.encounter is not None
        encounter = self.store.world.encounter.model_copy(update={"state": "ended"})
        enemy = self.store.world.known_entities["enemy"].model_copy(update={
            "hp": 0,
            "is_dead": True,
        })
        world = self.store.world.model_copy(update={
            "observation_cursor": 6,
            "encounter": encounter,
            "known_entities": {
                **self.store.world.known_entities,
                "enemy": enemy,
            },
            "current_epoch": None,
        })
        self.store.world = world
        self.store.materialized = world
        return CommandResult(
            status=CommandResultStatus.ACCEPTED,
            action_resolution=ActionResolutionStatus.COMPLETED,
            command_id=command_id or "command-terminal",
            session_id="session",
            actor_uuid="actor",
            requested_epoch_id="epoch-1",
            current_epoch_id=None,
            row_id=row_id,
            accepted_at_observation_cursor=6,
        )


def _world(
    *,
    current_epoch: DecisionEpoch | None | object = ...,
    cursor: int = 5,
) -> SubjectiveWorldState:
    """Build one compact current-epoch subjective world."""
    if current_epoch is ...:
        row = _action_affordance(
            row_id="entity|Strike|uuid=enemy",
            bucket="entity_actions",
            template_name="Strike",
            display_name="Strike",
            action_category="attack",
            target_type="entity",
            can_afford=True,
            targets=[ActionTarget(index=0, target_uuid="enemy", target_name="Skeleton", position=(1, 0))],
        )
        current_epoch = DecisionEpoch(
            epoch_id="epoch-1",
            epoch_index=1,
            basis_observation_cursor=cursor,
            reason=DecisionEpochReason.TURN_START,
            actor_uuid="actor",
            round_number=1,
            turn_index=0,
            economy=ActionEconomyState(
                actor_uuid="actor",
                actions=1,
                movement_remaining=30,
                meaningful_commands_remaining=True,
            ),
            affordances=AffordanceSet(
                actor_uuid="actor",
                computed_at_observation_cursor=cursor,
                entity_actions=[row],
            ),
        )
    assert current_epoch is None or isinstance(current_epoch, DecisionEpoch)
    return SubjectiveWorldState(
        observation_cursor=cursor,
        session=ObservationSessionState(
            session_id="session",
            player_type="codex",
            name="Codex Hero",
            connection_status="connected",
            controlled_entity_uuids=["actor"],
            active_entity_uuid="actor",
            active_entity_name="Barbarian",
            is_my_turn=current_epoch is not None,
        ),
        encounter=ObservationEncounterState(
            uuid="encounter",
            name="Arena",
            state="active",
            round_number=1,
            current_turn_index=0,
            current_entity_uuid="actor",
            current_entity_name="Barbarian",
        ),
        known_entities={
            "actor": ObservationEntityFact(
                uuid="actor",
                name="Barbarian",
                knowledge_state=KnowledgeState.VISIBLE,
                controlled=True,
                position=(0, 0),
                hp=30,
                max_hp=30,
                faction="heroes",
            ),
            "enemy": ObservationEntityFact(
                uuid="enemy",
                name="Skeleton",
                knowledge_state=KnowledgeState.VISIBLE,
                position=(1, 0),
                hp=13,
                max_hp=13,
                faction="monsters",
            ),
        },
        current_epoch=current_epoch,
        epoch_cursor=current_epoch.epoch_index if current_epoch is not None else 0,
    )


def _door_policy_world() -> SubjectiveWorldState:
    """Build one no-contact door epoch for the shared host integration."""
    semantics = ActionSemantics(
        semantic_id="movement.voluntary",
        tags=frozenset({ActionTag.MOVEMENT_VOLUNTARY, ActionTag.INFORMATION_REVEAL}),
    )
    reference = action_semantics_ref(semantics)
    move = _action_affordance(
        row_id="move-row",
        bucket="position_actions",
        template_name="Traverse Quietly",
        display_name="Traverse Quietly",
        action_category="movement",
        target_type="position",
        can_afford=True,
        targets=[ActionTarget(index=0, position=(2, 0), path_cost=10, path=[(0, 0), (1, 0), (2, 0)])],
        target_options=[ActionTarget(index=0, position=(2, 0), path_cost=10, path=[(0, 0), (1, 0), (2, 0)])],
        semantic_id=semantics.semantic_id,
        semantics_ref=reference,
        tags=sorted(tag.value for tag in semantics.tags),
    )
    epoch = DecisionEpoch(
        epoch_id="epoch-1",
        epoch_index=1,
        basis_observation_cursor=5,
        reason=DecisionEpochReason.TURN_START,
        actor_uuid="actor",
        round_number=1,
        turn_index=0,
        economy=ActionEconomyState(
            actor_uuid="actor",
            actions=1,
            movement_remaining=30,
            meaningful_commands_remaining=True,
        ),
        affordances=AffordanceSet(
            actor_uuid="actor",
            computed_at_observation_cursor=5,
            position_actions=[move],
            semantic_catalog={reference: semantics},
        ),
    )
    world = _world(current_epoch=epoch)
    return world.model_copy(update={
        "known_entities": {"actor": world.known_entities["actor"]},
        "known_objects": {
            "door": ObservationObjectFact(
                uuid="door",
                name="Boundary",
                knowledge_state=KnowledgeState.VISIBLE,
                position=(3, 0),
                state={"is_open": False},
            )
        },
        "known_tiles": {
            f"{x},0": ObservationTileFact(
                key=f"{x},0",
                position=(x, 0),
                knowledge_state=KnowledgeState.VISIBLE,
                walkable=True,
                walking_cost=5,
            )
            for x in range(4)
        },
    })


def _multi_target_world() -> SubjectiveWorldState:
    """Build an epoch with a repeated-projectile allocation affordance."""
    semantics = ActionSemantics(
        semantic_id="damage.single_target",
        tags=frozenset({ActionTag.TARGET_MULTI}),
    )
    reference = action_semantics_ref(semantics)
    targets = (
        ActionTarget(index=0, target_uuid="enemy-a", target_name="Skeleton A", position=(1, 0)),
        ActionTarget(index=1, target_uuid="enemy-b", target_name="Skeleton B", position=(2, 0)),
    )
    rows = [
        _action_affordance(
            row_id=f"entity|Magic Missile|uuid={target.target_uuid}",
            bucket="entity_actions",
            template_name="Magic Missile",
            display_name="Magic Missile",
            action_category="spell",
            target_type="multi_entity",
            can_afford=True,
            targets=[target],
            target_options=list(targets),
            num_projectiles=3,
            allow_same_target=True,
            semantic_id=semantics.semantic_id,
            semantics_ref=reference,
            tags=sorted(tag.value for tag in semantics.tags),
        )
        for target in targets
    ]
    epoch = DecisionEpoch(
        epoch_id="epoch-1",
        epoch_index=1,
        basis_observation_cursor=5,
        reason=DecisionEpochReason.TURN_START,
        actor_uuid="actor",
        round_number=1,
        turn_index=0,
        economy=ActionEconomyState(
            actor_uuid="actor",
            actions=1,
            meaningful_commands_remaining=True,
        ),
        affordances=AffordanceSet(
            actor_uuid="actor",
            computed_at_observation_cursor=5,
            entity_actions=rows,
            semantic_catalog={reference: semantics},
        ),
    )
    world = _world(current_epoch=epoch)
    known_entities = dict(world.known_entities)
    known_entities["enemy-a"] = ObservationEntityFact(
        uuid="enemy-a",
        name="Skeleton A",
        knowledge_state=KnowledgeState.VISIBLE,
        position=(1, 0),
        hp=13,
        max_hp=13,
        faction="monsters",
    )
    known_entities["enemy-b"] = ObservationEntityFact(
        uuid="enemy-b",
        name="Skeleton B",
        knowledge_state=KnowledgeState.VISIBLE,
        position=(2, 0),
        hp=13,
        max_hp=13,
        faction="monsters",
    )
    return world.model_copy(update={"known_entities": known_entities})


def _action_affordance(**payload: Any) -> ActionAffordance:
    """Build an affordance through the public flat row validator."""
    return ActionAffordance.model_validate(payload)


def _movement_world(*, row_count: int, cursor: int) -> SubjectiveWorldState:
    """Build one Dash-like epoch with many already-flattened movement rows."""
    rows = [
        _action_affordance(
            row_id=f"position|Move|pos={index + 1},0",
            bucket="position_actions",
            template_name="Move",
            display_name="Move",
            action_category="movement",
            target_type="position",
            can_afford=True,
            targets=[
                ActionTarget(
                    index=index,
                    position=(index + 1, 0),
                    path_cost=(index + 1) * 5,
                    path=[(step, 0) for step in range(index + 2)],
                )
            ],
        )
        for index in range(row_count)
    ]
    epoch = DecisionEpoch(
        epoch_id=f"epoch-{cursor}",
        epoch_index=cursor,
        basis_observation_cursor=cursor,
        reason=DecisionEpochReason.ACTION_COMPLETED,
        actor_uuid="actor",
        round_number=1,
        turn_index=0,
        economy=ActionEconomyState(
            actor_uuid="actor",
            actions=1,
            movement_remaining=60,
            meaningful_commands_remaining=True,
        ),
        affordances=AffordanceSet(
            actor_uuid="actor",
            computed_at_observation_cursor=cursor,
            position_actions=rows,
        ),
    )
    return _world(current_epoch=epoch, cursor=cursor)
