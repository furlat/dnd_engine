"""End-to-end contracts for the profile-driven hot Codex representation."""

from __future__ import annotations

import json
from typing import Optional

from fastapi.testclient import TestClient
import pytest

from ai.codex_tools.hot_runtime import (
    HotCodexExecuteRequest,
    HotCodexInspectionGetRequest,
    HotCodexInspectionSearchRequest,
    HotCodexOracleRequest,
    HotCodexPredicateEvaluateRequest,
    HotCodexPredicateFocusRequest,
    HotCodexPredicateRegisterRequest,
    HotCodexProfileSelectRequest,
    HotCodexSession,
    HotCodexStaleRevisionError,
    create_hot_codex_app,
)
from ai.codex_tools.representation.inspection import (
    InspectionGetRequest,
    InspectionGetStatus,
    InspectionSearchRequest,
)
from ai.codex_tools.representation.predicates import (
    PredicateDefinition,
    PredicateFocusProfile,
)
from ai.codex_tools.representation.profiles import (
    BALANCED_V2_PROFILE_ID,
    CURRENT_V1_PROFILE_ID,
)
from ai.knowledge.models import AgentFacts
from ai.observation.models import SubjectiveWorldState
from ai.policy import PolicyDecision, PolicyHost
from ai.policy.contracts import PolicyExecutionConstraints
from ai.policy.host import PolicyTelemetrySink
from ai.protocol.semantics import (
    ComparisonOperator,
    FactExpression,
    FactOperator,
    FactPredicate,
    TruthValue,
)
from ai.subjective.runtime import MemoryAgentEventSink
from tests.manual.test_49_hot_codex_runtime import _FakeRuntime, _door_policy_world


class _CountingPolicyHost(PolicyHost):
    """Policy host recording exactly when tactical advice is requested."""

    def __init__(self) -> None:
        """Create an empty host and reset its decision-call counter."""
        super().__init__()
        self.decide_calls = 0

    def decide(
        self,
        world: SubjectiveWorldState,
        *,
        facts: Optional[AgentFacts] = None,
        execution_constraints: Optional[PolicyExecutionConstraints] = None,
        deadline_monotonic: Optional[float] = None,
        telemetry_sink: Optional[PolicyTelemetrySink] = None,
    ) -> PolicyDecision:
        """Count and delegate one real policy evaluation."""
        self.decide_calls += 1
        return super().decide(
            world,
            facts=facts,
            execution_constraints=execution_constraints,
            deadline_monotonic=deadline_monotonic,
            telemetry_sink=telemetry_sink,
        )


class _FailingPolicyHost(_CountingPolicyHost):
    """Policy oracle that fails without affecting direct Codex control."""

    def decide(
        self,
        world: SubjectiveWorldState,
        *,
        facts: Optional[AgentFacts] = None,
        execution_constraints: Optional[PolicyExecutionConstraints] = None,
        deadline_monotonic: Optional[float] = None,
        telemetry_sink: Optional[PolicyTelemetrySink] = None,
    ) -> PolicyDecision:
        """Raise one deterministic oracle-only failure."""
        del world, facts, execution_constraints, deadline_monotonic, telemetry_sink
        self.decide_calls += 1
        raise RuntimeError("oracle implementation exploded")


class _EventRuntime(_FakeRuntime):
    """Fake subjective runtime with the real typed agent-event sink contract."""

    def __init__(self, world: SubjectiveWorldState) -> None:
        """Create the existing transport double with an in-memory event sink."""
        super().__init__(world)
        self.event_sink = MemoryAgentEventSink()


def test_balanced_profile_never_invokes_policy_until_oracle_is_requested() -> None:
    """Neutral automatic context remains independent from tactical recommendations."""
    host = _CountingPolicyHost()
    runtime = _EventRuntime(_door_policy_world())
    session = HotCodexSession(
        runtime=runtime,
        claim_id="claim",
        faction="monsters",
        controlled_entity_uuids=("actor",),
        policy_host=host,
        representation_profile_id=BALANCED_V2_PROFILE_ID,
    )

    turn = session.bootstrap()
    representation = session.representation()

    assert host.decide_calls == 0
    assert turn.selected_policy is None
    assert "oracle.policy" not in {
        block.component_id for block in representation.representation.blocks
    }
    assert "telemetry.runtime" not in {
        block.component_id for block in representation.representation.blocks
    }

    first = session.oracle(HotCodexOracleRequest(revision=turn.revision, detail="full_trace"))
    second = session.oracle(HotCodexOracleRequest(revision=turn.revision, detail="selected_only"))

    assert host.decide_calls == 1
    assert first.advice.available is True
    assert first.advice.selected is not None
    assert second.advice.selected == first.advice.selected
    assert any(
        event.event_type == "representation.oracle_requested"
        for event in runtime.event_sink.events
    )
    event_types = {event.event_type for event in runtime.event_sink.events}
    assert "representation.profile_resolved" in event_types
    assert "representation.component_started" in event_types
    assert "representation.component_completed" in event_types
    assert "representation.generated" in event_types


def test_oracle_failure_is_typed_and_does_not_block_direct_control() -> None:
    """A failed optional adviser leaves the current server-issued rows usable."""
    host = _FailingPolicyHost()
    runtime = _FakeRuntime(_door_policy_world())
    session = HotCodexSession(
        runtime=runtime,
        claim_id="claim",
        faction="monsters",
        controlled_entity_uuids=("actor",),
        policy_host=host,
        representation_profile_id=BALANCED_V2_PROFILE_ID,
    )
    turn = session.bootstrap()

    oracle = session.oracle(HotCodexOracleRequest(revision=turn.revision))
    command = session.execute(HotCodexExecuteRequest(
        revision=turn.revision,
        row_id="move-row",
    ))

    assert oracle.advice.available is False
    assert oracle.advice.unavailable_reason == "Traditional-policy oracle failed safely (RuntimeError)."
    assert command.command_result.status.value == "accepted"
    assert runtime.execute_calls[0][0] == "move-row"


def test_current_profile_preserves_eager_policy_compatibility() -> None:
    """The compatibility profile retains the existing eager policy lifecycle."""
    host = _CountingPolicyHost()
    session = HotCodexSession(
        runtime=_FakeRuntime(_door_policy_world()),
        claim_id="claim",
        faction="monsters",
        controlled_entity_uuids=("actor",),
        policy_host=host,
        representation_profile_id=CURRENT_V1_PROFILE_ID,
    )

    turn = session.bootstrap()
    representation = session.representation()

    assert host.decide_calls == 1
    assert turn.selected_policy is not None
    assert turn.known_objects[0].uuid == "door"
    assert turn.known_objects[0].state["is_open"] is False
    oracle_block = next(
        block
        for block in representation.representation.blocks
        if block.component_id == "oracle.policy"
    )
    assert oracle_block.payload.available is True


def test_profile_selection_changes_context_only_and_never_reloads_state() -> None:
    """Profile selection preserves the materialized world and revision authority."""
    runtime = _FakeRuntime(_door_policy_world())
    session = HotCodexSession(
        runtime=runtime,
        claim_id="claim",
        faction="monsters",
        controlled_entity_uuids=("actor",),
        representation_profile_id=BALANCED_V2_PROFILE_ID,
    )
    turn = session.bootstrap()
    world_before = runtime.store.world.model_dump_json()

    selected = session.select_profile(HotCodexProfileSelectRequest(
        revision=turn.revision,
        profile_id=CURRENT_V1_PROFILE_ID,
    ))

    assert selected.profile.profile_id == CURRENT_V1_PROFILE_ID
    assert selected.revision == turn.revision
    assert runtime.store.world.model_dump_json() == world_before
    assert runtime.snapshot_fetch_calls == 1
    assert session.health().representation_manifest_digest == selected.manifest.manifest_digest


def test_predicates_and_inspection_expose_complete_local_subjective_state() -> None:
    """Codex can focus, inspect, search, and export without objective access."""
    runtime = _EventRuntime(_door_policy_world())
    session = HotCodexSession(
        runtime=runtime,
        claim_id="claim",
        faction="monsters",
        controlled_entity_uuids=("actor",),
        representation_profile_id=BALANCED_V2_PROFILE_ID,
    )
    turn = session.bootstrap()
    predicate = PredicateDefinition(
        predicate_id="codex.has_legal_action",
        description="Whether at least one authoritative affordance is legal.",
        semantic_intent="agent_authored_attention",
        expression=FactExpression(
            operator=FactOperator.PREDICATE,
            predicate=FactPredicate(
                fact_id="affordances.total_count",
                comparison=ComparisonOperator.GREATER_THAN,
                expected_value=0,
            ),
        ),
    )

    session.register_predicate(HotCodexPredicateRegisterRequest(
        revision=turn.revision,
        definition=predicate,
    ))
    focus = session.set_predicate_focus(HotCodexPredicateFocusRequest(
        revision=turn.revision,
        focus=PredicateFocusProfile(
            profile_id="codex.runtime_focus",
            always_include=(predicate.predicate_id,),
            max_automatic_items=1,
        ),
    ))
    ledger = session.evaluate_predicates(HotCodexPredicateEvaluateRequest(
        revision=turn.revision,
    ))
    exact = session.inspection_get(HotCodexInspectionGetRequest(
        revision=turn.revision,
        query=InspectionGetRequest(pointers=(
            "/world/known_objects/door/name",
            "/world/known_entities/objective-hidden-enemy",
        )),
    ))
    search = session.inspection_search(HotCodexInspectionSearchRequest(
        revision=turn.revision,
        query=InspectionSearchRequest(pattern="objective-hidden-enemy"),
    ))
    exported = session.inspection_export().export
    document = json.loads(exported.canonical_json)

    assert focus.always_include == (predicate.predicate_id,)
    assert ledger.predicate(predicate.predicate_id).truth is TruthValue.TRUE
    assert exact.result.items[0].status is InspectionGetStatus.FOUND
    assert exact.result.items[0].value == "Boundary"
    assert exact.result.items[1].status is InspectionGetStatus.MISSING
    assert search.result.total_matches == 0
    assert "objective-hidden-enemy" not in document["world"]["known_entities"]
    assert set(document) == {
        "revision",
        "world",
        "observation_frames",
        "agent_state",
        "predicates",
        "representation",
    }
    assert runtime.snapshot_fetch_calls == 1
    assert any(
        event.event_type == "representation.inspection_completed"
        for event in runtime.event_sink.events
    )


def test_inspection_and_profile_api_are_authenticated_and_revision_fenced() -> None:
    """Local HTTP routes retain authentication and stale-read semantics."""
    runtime = _FakeRuntime(_door_policy_world())
    session = HotCodexSession(
        runtime=runtime,
        claim_id="claim",
        faction="monsters",
        controlled_entity_uuids=("actor",),
        representation_profile_id=BALANCED_V2_PROFILE_ID,
    )
    turn = session.bootstrap()
    app = create_hot_codex_app(session, bearer_token="token")
    headers = {"Authorization": "Bearer token"}

    with TestClient(app) as client:
        assert client.get("/v1/representation/current").status_code == 401
        profile = client.get("/v1/representation/profile", headers=headers)
        catalog = client.get("/v1/inspect/catalog", headers=headers)
        exact = client.post(
            "/v1/inspect/get",
            headers=headers,
            json={
                "revision": turn.revision.model_dump(mode="json"),
                "query": {"pointers": ["/world/session/session_id"]},
            },
        )

        runtime.store.world = runtime.store.world.model_copy(update={
            "observation_cursor": turn.revision.observation_cursor + 1,
        })
        stale = client.post(
            "/v1/inspect/get",
            headers=headers,
            json={
                "revision": turn.revision.model_dump(mode="json"),
                "query": {"pointers": ["/world/session/session_id"]},
            },
        )

    assert profile.status_code == 200
    assert profile.json()["profile"]["profile_id"] == BALANCED_V2_PROFILE_ID
    assert catalog.status_code == 200
    assert exact.status_code == 200
    assert exact.json()["result"]["items"][0]["value"] == "session"
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "stale_revision"


def test_required_component_failure_returns_structured_503_and_keeps_world() -> None:
    """Representation failure does not mutate or discard the subjective runtime."""
    runtime = _FakeRuntime(_door_policy_world())
    session = HotCodexSession(
        runtime=runtime,
        claim_id="claim",
        faction="monsters",
        controlled_entity_uuids=("actor",),
        representation_profile_id=BALANCED_V2_PROFILE_ID,
    )
    turn = session.bootstrap()

    def fail_component(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("sensitive component failure")

    session.representation_projector._builders["actions.index"] = fail_component  # pyright: ignore[reportPrivateUsage, reportArgumentType]
    runtime.store.world = runtime.store.world.model_copy(update={
        "observation_cursor": turn.revision.observation_cursor + 1,
    })
    app = create_hot_codex_app(session, bearer_token="token")

    with TestClient(app) as client:
        failed = client.get(
            "/v1/representation/current",
            headers={"Authorization": "Bearer token"},
        )
        health = client.get(
            "/v1/health",
            headers={"Authorization": "Bearer token"},
        )

    assert failed.status_code == 503
    assert failed.json()["error"]["code"] == "representation_failed"
    assert "sensitive component failure" not in failed.text
    assert health.status_code == 200
    assert health.json()["revision"]["observation_cursor"] == turn.revision.observation_cursor + 1


def test_balanced_direct_action_does_not_advance_oracle_policy_memory() -> None:
    """Optional advice never becomes hidden control state for direct Codex actions."""
    host = _CountingPolicyHost()
    runtime = _FakeRuntime(_door_policy_world())
    session = HotCodexSession(
        runtime=runtime,
        claim_id="claim",
        faction="monsters",
        controlled_entity_uuids=("actor",),
        policy_host=host,
        representation_profile_id=BALANCED_V2_PROFILE_ID,
    )
    turn = session.bootstrap()
    advice = session.oracle(HotCodexOracleRequest(revision=turn.revision))
    assert advice.advice.selected is not None

    result = session.execute(HotCodexExecuteRequest(
        revision=turn.revision,
        row_id=advice.advice.selected.row_id or "",
    ))

    assert result.command_result.status.value == "accepted"
    assert result.policy_result is None
    assert host.memory_for("session", "actor").active_routine is None


def test_stale_direct_inspection_is_rejected_before_local_evaluation() -> None:
    """A stale caller cannot accidentally inspect a newer materialized revision."""
    runtime = _FakeRuntime(_door_policy_world())
    session = HotCodexSession(
        runtime=runtime,
        claim_id="claim",
        faction="monsters",
        controlled_entity_uuids=("actor",),
        representation_profile_id=BALANCED_V2_PROFILE_ID,
    )
    revision = session.bootstrap().revision
    runtime.store.world = runtime.store.world.model_copy(update={
        "observation_cursor": revision.observation_cursor + 1,
    })

    with pytest.raises(HotCodexStaleRevisionError):
        session.inspection_get(HotCodexInspectionGetRequest(
            revision=revision,
            query=InspectionGetRequest(pointers=("/world/session",)),
        ))
