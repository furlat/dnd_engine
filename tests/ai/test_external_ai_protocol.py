"""Closed wire-contract tests for registered external policy providers."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from dnd.ai.contracts.decision import EndTurnIntent
from dnd.ai.contracts.observation import (
    ObservationSessionState,
    SubjectiveWorldState,
)
from dnd.ai.feedback import NativeAIDecisionOutcome
from dnd.ai.policies.basic import BASIC_POLICY_DESCRIPTOR
from server.external_ai_protocol import (
    EXTERNAL_AI_PROTOCOL_HASH,
    EXTERNAL_AI_PROTOCOL_VERSION,
    ExternalAIAssignmentCloseRequest,
    ExternalAIAssignmentOpenRequest,
    ExternalAIDecisionFeedback,
    ExternalAIDecisionRequest,
    ExternalAIDecisionResponse,
    ExternalAIPolicyProviderHandshake,
    ExternalAIProtocolIdentity,
    external_ai_wire_schema,
)


def _world() -> SubjectiveWorldState:
    return SubjectiveWorldState(
        observation_cursor=1,
        session=ObservationSessionState(
            session_id="subjective-stream",
            player_type="external_ai",
            name="External AI",
            connection_status="connected",
            controlled_entity_uuids=["actor"],
            active_entity_uuid="actor",
            active_entity_name="Actor",
            is_my_turn=True,
        ),
    )


def _feedback(decision_id: int) -> ExternalAIDecisionFeedback:
    return ExternalAIDecisionFeedback(
        decision_id=decision_id,
        actor_uuid="actor",
        epoch_id=f"epoch-{decision_id}",
        row_id=f"row-{decision_id}",
        outcome=NativeAIDecisionOutcome.EXECUTED,
    )


def test_protocol_hash_authenticates_the_complete_closed_wire_schema() -> None:
    identity = ExternalAIProtocolIdentity()
    schema = external_ai_wire_schema()

    assert identity.version == EXTERNAL_AI_PROTOCOL_VERSION
    assert identity.contract_hash == EXTERNAL_AI_PROTOCOL_HASH
    assert len(EXTERNAL_AI_PROTOCOL_HASH) == 64
    routes = schema["routes"]
    assert isinstance(routes, tuple)
    assert routes == (
        "/handshake",
        "/assignments/open",
        "/assignments/decide",
        "/assignments/close",
    )
    assert {
        "handshake",
        "assignment_open_request",
        "assignment_lease",
        "decision_request",
        "decision_response",
        "assignment_close_request",
        "assignment_close_response",
    } <= set(schema)

    with pytest.raises(ValidationError, match="protocol version"):
        ExternalAIProtocolIdentity(version=EXTERNAL_AI_PROTOCOL_VERSION + 1)
    with pytest.raises(ValidationError, match="contract hash"):
        ExternalAIProtocolIdentity(contract_hash="0" * 64)


def test_handshake_and_assignment_messages_are_closed_and_generation_fenced() -> None:
    protocol = ExternalAIProtocolIdentity()
    handshake = ExternalAIPolicyProviderHandshake(
        protocol=protocol,
        provider_id="reference.local",
        policies=(BASIC_POLICY_DESCRIPTOR,),
        capacity=8,
        active_assignments=2,
    )
    opened = ExternalAIAssignmentOpenRequest(
        protocol=protocol,
        assignment_id="assignment-a",
        generation=3,
        assignment_token="server-issued-secret",
        game_id="game-a",
        controlled_entity_uuids=("actor",),
        policy_id=BASIC_POLICY_DESCRIPTOR.policy_id,
    )
    closed = ExternalAIAssignmentCloseRequest(
        protocol=protocol,
        assignment_id=opened.assignment_id,
        generation=opened.generation,
        assignment_token=opened.assignment_token,
    )

    assert handshake.capacity == 8
    assert handshake.available_capacity == 6
    assert opened.generation == closed.generation == 3
    assert opened.assignment_token == closed.assignment_token
    with pytest.raises(ValidationError, match="duplicate"):
        ExternalAIAssignmentOpenRequest(
            protocol=protocol,
            assignment_id="assignment-a",
            generation=3,
            assignment_token="server-issued-secret",
            game_id="game-a",
            controlled_entity_uuids=("actor", "actor"),
            policy_id=BASIC_POLICY_DESCRIPTOR.policy_id,
        )


def test_decision_feedback_is_an_ordered_delta_before_the_current_decision() -> None:
    request = ExternalAIDecisionRequest(
        protocol=ExternalAIProtocolIdentity(),
        assignment_id="assignment-a",
        generation=1,
        assignment_token="server-issued-secret",
        decision_id=3,
        state=_world(),
        feedback=(_feedback(1), _feedback(2)),
    )

    assert tuple(row.decision_id for row in request.feedback) == (1, 2)
    with pytest.raises(ValidationError, match="strictly increasing"):
        request.model_copy(
            update={"feedback": (_feedback(2), _feedback(1))}
        ).__class__.model_validate(
            {
                **request.model_dump(mode="python"),
                "feedback": (_feedback(2), _feedback(1)),
            }
        )
    with pytest.raises(ValidationError, match="before the requested decision"):
        ExternalAIDecisionRequest(
            **{
                **request.model_dump(mode="python"),
                "feedback": (_feedback(1), _feedback(3)),
            }
        )


def test_decision_response_is_a_typed_policy_intent_and_echoes_the_fence() -> None:
    response = ExternalAIDecisionResponse(
        protocol=ExternalAIProtocolIdentity(),
        assignment_id="assignment-a",
        generation=4,
        assignment_token="server-issued-secret",
        decision_id=7,
        policy=BASIC_POLICY_DESCRIPTOR,
        intent=EndTurnIntent(),
    )

    assert response.intent.kind == "end_turn"
    assert response.model_dump(mode="json")["intent"] == {
        "kind": "end_turn"
    }
    with pytest.raises(ValidationError):
        ExternalAIDecisionResponse.model_validate(
            {
                **response.model_dump(mode="json"),
                "intent": {"kind": "raw_engine_action", "payload": {}},
            }
        )


def test_decision_wire_surface_has_no_player_credentials_or_objective_payload() -> None:
    request_schema = ExternalAIDecisionRequest.model_json_schema(
        mode="serialization"
    )
    encoded = json.dumps(request_schema, sort_keys=True)
    top_level_fields = set(
        request_schema.get("properties", {})
    )

    assert top_level_fields == {
        "protocol",
        "assignment_id",
        "generation",
        "assignment_token",
        "decision_id",
        "state",
        "feedback",
    }
    assert "PlayerSession" not in encoded
    assert "player_token" not in encoded
    assert "bearer_token" not in encoded
    assert "objective_state" not in encoded
    assert "raw_events" not in encoded
