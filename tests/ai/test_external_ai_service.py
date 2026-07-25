"""Lifecycle, fencing, concurrency, and instrumentation tests for policy providers."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from threading import Barrier

from fastapi.testclient import TestClient

from dnd.ai.contracts.control import (
    ActionAffordance,
    ActionCostProfile,
    ActionEconomyState,
    ActionSourceDefinition,
    ActionTarget,
    AffordanceSet,
    DecisionEpoch,
    DecisionEpochReason,
)
from dnd.ai.contracts.decision import (
    EndTurnIntent,
    PolicyIntent,
)
from dnd.ai.contracts.observation import (
    KnowledgeState,
    ObservationEntityFact,
    ObservationSessionState,
    SubjectiveWorldState,
)
from dnd.ai.contracts.semantics import ActionSemantics, ActionTag
from dnd.ai.feedback import NativeAIDecisionOutcome
from dnd.ai.instrumentation import (
    AIExecutionPhase,
    BoundedAIInstrumentationSink,
)
from dnd.ai.policies.basic import CanonicalPolicyRegistry
from dnd.ai.policy import PolicyDescriptor
from dnd.ai.registry import PolicyRegistry
from server.external_ai_protocol import (
    ExternalAIAssignmentOpenRequest,
    ExternalAIDecisionFeedback,
    ExternalAIDecisionRequest,
    ExternalAIProtocolIdentity,
)
from services.ai_policy_server.app import create_ai_policy_service
from services.ai_policy_server.policies import (
    EXTERNAL_BASIC_POLICY_ID,
    EXTERNAL_TACTICAL_POLICY_ID,
)


def _attack_row(target_uuid: str, order: int) -> ActionAffordance:
    return ActionAffordance(
        row_id=f"row:attack:{target_uuid}",
        source=ActionSourceDefinition(
            source_action_id=f"source:{target_uuid}",
            bucket="entity_actions",
            template_name="Attack",
            display_name="Attack",
            action_category="attack",
            target_type="entity",
            can_afford=True,
            cost=ActionCostProfile(action_cost=1),
            semantic_key="action.attack",
            semantic_id="attack.weapon",
            semantics_ref="attack",
        ),
        targets=(
            ActionTarget(
                index=order,
                target_uuid=target_uuid,
                target_name=target_uuid,
                position=(order + 1, 0),
                distance=(order + 1) * 5,
            ),
        ),
    )


def _world(
    assignment_id: str,
    *,
    epoch_id: str,
    enemy_a_hp: int = 4,
    enemy_b_hp: int = 8,
) -> SubjectiveWorldState:
    rows = (
        _attack_row("enemy-a", 0),
        _attack_row("enemy-b", 1),
    )
    epoch = DecisionEpoch(
        epoch_id=epoch_id,
        epoch_index=1,
        basis_observation_cursor=1,
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
            computed_at_observation_cursor=1,
            entity_actions=rows,
            semantic_catalog={
                "attack": ActionSemantics(
                    semantic_id="attack.weapon",
                    tags=frozenset(
                        {
                            ActionTag.ATTACK_WEAPON,
                            ActionTag.DAMAGE_SINGLE_TARGET,
                        }
                    ),
                )
            },
        ),
    )
    return SubjectiveWorldState(
        observation_cursor=1,
        session=ObservationSessionState(
            session_id=f"subjective:{assignment_id}",
            player_type="external_ai",
            name="External AI",
            connection_status="connected",
            controlled_entity_uuids=["actor"],
            active_entity_uuid="actor",
            active_entity_name="Actor",
            is_my_turn=True,
        ),
        known_entities={
            "actor": ObservationEntityFact(
                uuid="actor",
                name="Actor",
                knowledge_state=KnowledgeState.VISIBLE,
                controlled=True,
                position=(0, 0),
                normal_hp=20,
                max_hp=20,
                faction="heroes",
            ),
            "enemy-a": ObservationEntityFact(
                uuid="enemy-a",
                name="Enemy A",
                knowledge_state=KnowledgeState.VISIBLE,
                position=(1, 0),
                normal_hp=enemy_a_hp,
                hp=enemy_a_hp,
                max_hp=20,
                faction="monsters",
                is_dead=False,
            ),
            "enemy-b": ObservationEntityFact(
                uuid="enemy-b",
                name="Enemy B",
                knowledge_state=KnowledgeState.VISIBLE,
                position=(2, 0),
                normal_hp=enemy_b_hp,
                hp=enemy_b_hp,
                max_hp=20,
                faction="monsters",
                is_dead=False,
            ),
        },
        current_epoch=epoch,
        epoch_cursor=1,
    )


def _open(
    *,
    assignment_id: str,
    generation: int = 1,
    token: str | None = None,
    policy_id: str = EXTERNAL_TACTICAL_POLICY_ID,
) -> ExternalAIAssignmentOpenRequest:
    return ExternalAIAssignmentOpenRequest(
        protocol=ExternalAIProtocolIdentity(),
        assignment_id=assignment_id,
        generation=generation,
        assignment_token=token or f"server-issued-{assignment_id}",
        game_id="game",
        controlled_entity_uuids=("actor",),
        policy_id=policy_id,
    )


def _decision(
    opened: ExternalAIAssignmentOpenRequest,
    decision_id: int,
    *,
    feedback: tuple[ExternalAIDecisionFeedback, ...] = (),
) -> ExternalAIDecisionRequest:
    return ExternalAIDecisionRequest(
        protocol=ExternalAIProtocolIdentity(),
        assignment_id=opened.assignment_id,
        generation=opened.generation,
        assignment_token=opened.assignment_token,
        decision_id=decision_id,
        state=_world(
            opened.assignment_id,
            epoch_id=f"epoch-{decision_id}",
        ),
        feedback=feedback,
    )


def test_reference_service_handshake_and_idempotent_decision_cache() -> None:
    sink = BoundedAIInstrumentationSink()
    app = create_ai_policy_service(
        provider_id="reference.test",
        capacity=4,
        response_cache_size=2,
        instrumentation_sink=sink,
    )
    opened = _open(assignment_id="assignment-a")

    with TestClient(app) as client:
        handshake = client.get("/handshake")
        assert handshake.status_code == 200
        assert handshake.json()["provider_id"] == "reference.test"
        assert [
            row["policy_id"] for row in handshake.json()["policies"]
        ] == [
            EXTERNAL_BASIC_POLICY_ID,
            EXTERNAL_TACTICAL_POLICY_ID,
        ]
        assert client.post(
            "/assignments/open",
            json=opened.model_dump(mode="json"),
        ).status_code == 200

        request = _decision(opened, 1)
        first = client.post(
            "/assignments/decide",
            json=request.model_dump(mode="json"),
        )
        repeated = client.post(
            "/assignments/decide",
            json=request.model_dump(mode="json"),
        )

    assert first.status_code == repeated.status_code == 200
    assert first.content == repeated.content
    assert first.json()["intent"]["row_id"] == "row:attack:enemy-a"
    assert sum(
        timing.phase is AIExecutionPhase.POLICY_DECISION
        for timing in sink.timing_snapshot()
    ) == 1


def test_replay_conflict_out_of_order_and_stale_generation_fail_closed() -> None:
    app = create_ai_policy_service(provider_id="reference.test", capacity=2)
    opened = _open(assignment_id="assignment-a")
    with TestClient(app) as client:
        assert client.post(
            "/assignments/open",
            json=opened.model_dump(mode="json"),
        ).status_code == 200
        first = _decision(opened, 1)
        assert client.post(
            "/assignments/decide",
            json=first.model_dump(mode="json"),
        ).status_code == 200

        changed = first.model_copy(
            update={
                "state": _world(
                    opened.assignment_id,
                    epoch_id="changed-epoch",
                    enemy_a_hp=20,
                    enemy_b_hp=1,
                )
            }
        )
        conflict = client.post(
            "/assignments/decide",
            json=changed.model_dump(mode="json"),
        )
        skipped = client.post(
            "/assignments/decide",
            json=_decision(opened, 3).model_dump(mode="json"),
        )
        stale_open = _open(
            assignment_id=opened.assignment_id,
            generation=2,
            token="new-server-issued-token",
        )
        assert client.post(
            "/assignments/open",
            json=stale_open.model_dump(mode="json"),
        ).status_code == 200
        stale = client.post(
            "/assignments/decide",
            json=_decision(opened, 2).model_dump(mode="json"),
        )

    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "decision_replay_conflict"
    assert skipped.status_code == 409
    assert skipped.json()["detail"]["code"] == "decision_out_of_order"
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "assignment_fence_mismatch"


def test_feedback_and_memory_are_isolated_per_assignment() -> None:
    app = create_ai_policy_service(provider_id="reference.test", capacity=2)
    first = _open(assignment_id="assignment-a")
    second = _open(assignment_id="assignment-b")
    with TestClient(app) as client:
        for opened in (first, second):
            assert client.post(
                "/assignments/open",
                json=opened.model_dump(mode="json"),
            ).status_code == 200
            response = client.post(
                "/assignments/decide",
                json=_decision(opened, 1).model_dump(mode="json"),
            )
            assert response.json()["intent"]["row_id"] == (
                "row:attack:enemy-a"
            )

        failed = ExternalAIDecisionFeedback(
            decision_id=1,
            actor_uuid="actor",
            epoch_id="epoch-1",
            row_id="row:attack:enemy-a",
            outcome=NativeAIDecisionOutcome.FAILED,
        )
        first_next = client.post(
            "/assignments/decide",
            json=_decision(first, 2, feedback=(failed,)).model_dump(
                mode="json"
            ),
        )
        second_next = client.post(
            "/assignments/decide",
            json=_decision(second, 2).model_dump(mode="json"),
        )

    assert first_next.json()["intent"]["row_id"] == "row:attack:enemy-b"
    assert second_next.json()["intent"]["row_id"] == "row:attack:enemy-a"


@dataclass(slots=True)
class _BarrierMemory:
    calls: int = 0


class _BarrierPolicy:
    descriptor = PolicyDescriptor(
        policy_id="test.barrier",
        version="1",
        display_name="Barrier",
    )
    barrier = Barrier(2)

    def decide(
        self,
        state: SubjectiveWorldState,
        memory: _BarrierMemory,
    ) -> PolicyIntent:
        del state
        memory.calls += 1
        self.barrier.wait(timeout=3)
        return EndTurnIntent()


def test_independent_assignments_can_decide_concurrently() -> None:
    registry: CanonicalPolicyRegistry = PolicyRegistry()
    registry.register(
        descriptor=_BarrierPolicy.descriptor,
        policy_factory=_BarrierPolicy,
        memory_factory=_BarrierMemory,
    )
    app = create_ai_policy_service(
        provider_id="reference.concurrent",
        capacity=2,
        policy_registry=registry,
    )
    first = _open(
        assignment_id="assignment-a",
        policy_id=_BarrierPolicy.descriptor.policy_id,
    )
    second = _open(
        assignment_id="assignment-b",
        policy_id=_BarrierPolicy.descriptor.policy_id,
    )
    with TestClient(app) as client:
        for opened in (first, second):
            assert client.post(
                "/assignments/open",
                json=opened.model_dump(mode="json"),
            ).status_code == 200

        def decide(opened: ExternalAIAssignmentOpenRequest) -> int:
            return client.post(
                "/assignments/decide",
                json=_decision(opened, 1).model_dump(mode="json"),
            ).status_code

        with ThreadPoolExecutor(max_workers=2) as executor:
            statuses = tuple(
                executor.map(decide, (first, second))
            )

    assert statuses == (200, 200)


def test_close_is_explicit_idempotent_and_prevents_future_decisions() -> None:
    app = create_ai_policy_service(provider_id="reference.test", capacity=1)
    opened = _open(assignment_id="assignment-a")
    close_payload = {
        "protocol": ExternalAIProtocolIdentity().model_dump(mode="json"),
        "assignment_id": opened.assignment_id,
        "generation": opened.generation,
        "assignment_token": opened.assignment_token,
    }
    with TestClient(app) as client:
        assert client.post(
            "/assignments/open",
            json=opened.model_dump(mode="json"),
        ).status_code == 200
        first_close = client.post(
            "/assignments/close",
            json=close_payload,
        )
        repeated_close = client.post(
            "/assignments/close",
            json=close_payload,
        )
        after_close = client.post(
            "/assignments/decide",
            json=_decision(opened, 1).model_dump(mode="json"),
        )

    assert first_close.status_code == repeated_close.status_code == 200
    assert first_close.content == repeated_close.content
    assert first_close.json()["closed"] is True
    assert after_close.status_code == 409
    assert after_close.json()["detail"]["code"] == "assignment_closed"
