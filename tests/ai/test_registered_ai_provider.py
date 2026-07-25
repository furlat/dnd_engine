"""Main-server client and catalog tests for registered AI policy providers."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Coroutine
from typing import Any

import httpx
import pytest

from custom_ai.tactical import TACTICAL_POLICY_ID
from dnd.ai.contracts.control import (
    ActionEconomyState,
    AffordanceSet,
    DecisionEpoch,
    DecisionEpochReason,
)
from dnd.ai.contracts.decision import EndTurnIntent
from dnd.ai.contracts.observation import (
    ObservationSessionState,
    SubjectiveWorldState,
)
from dnd.ai.instrumentation import (
    AIExecutionPhase,
    BoundedAIInstrumentationSink,
)
from dnd.ai.policies.basic import BASIC_POLICY_DESCRIPTOR, BASIC_POLICY_ID
from dnd.ai.policy import PolicyDescriptor
from server.external_ai_protocol import (
    ExternalAIAssignmentCloseResponse,
    ExternalAIAssignmentLease,
    ExternalAIDecisionResponse,
    ExternalAIPolicyProviderHandshake,
    ExternalAIProtocolIdentity,
)
from server.registered_ai_provider import (
    RegisteredAIDecisionOrderError,
    RegisteredAIProviderBusyError,
    RegisteredAIProviderCatalog,
    RegisteredAIProviderCollisionError,
    RegisteredAIProviderProtocolError,
    RegisteredAIProviderTransportError,
)
from services.ai_policy_server.app import create_ai_policy_service
from services.ai_policy_server.composition import (
    create_ai_policy_service_runtime,
)
from services.ai_policy_server.policies import (
    EXTERNAL_BASIC_POLICY_DESCRIPTOR,
    EXTERNAL_BASIC_POLICY_ID,
)


def _run[ResultT](operation: Coroutine[Any, Any, ResultT]) -> ResultT:
    return asyncio.run(operation)


def _world(*, assignment_id: str, epoch_index: int) -> SubjectiveWorldState:
    actor_uuid = "actor"
    return SubjectiveWorldState(
        observation_cursor=epoch_index,
        session=ObservationSessionState(
            session_id=f"subjective:{assignment_id}",
            player_type="external_ai",
            name="External AI",
            connection_status="connected",
            controlled_entity_uuids=[actor_uuid],
            active_entity_uuid=actor_uuid,
            active_entity_name="Actor",
            is_my_turn=True,
        ),
        current_epoch=DecisionEpoch(
            epoch_id=f"epoch-{epoch_index}",
            epoch_index=epoch_index,
            basis_observation_cursor=epoch_index,
            reason=DecisionEpochReason.TURN_START,
            actor_uuid=actor_uuid,
            round_number=1,
            turn_index=0,
            economy=ActionEconomyState(
                actor_uuid=actor_uuid,
                meaningful_commands_remaining=False,
            ),
            affordances=AffordanceSet(
                actor_uuid=actor_uuid,
                computed_at_observation_cursor=epoch_index,
            ),
        ),
        epoch_cursor=epoch_index,
    )


class _TrackingClientFactory:
    def __init__(self) -> None:
        self.clients: list[httpx.AsyncClient] = []

    def __call__(
        self,
        *,
        base_url: str,
        timeout: httpx.Timeout,
        transport: httpx.AsyncBaseTransport | None,
    ) -> httpx.AsyncClient:
        client = httpx.AsyncClient(
            base_url=base_url,
            timeout=timeout,
            transport=transport,
        )
        self.clients.append(client)
        return client


def _handshake(
    provider_id: str,
    *,
    policies: tuple[PolicyDescriptor, ...] = (BASIC_POLICY_DESCRIPTOR,),
    capacity: int = 4,
    active_assignments: int = 0,
) -> ExternalAIPolicyProviderHandshake:
    return ExternalAIPolicyProviderHandshake(
        protocol=ExternalAIProtocolIdentity(),
        provider_id=provider_id,
        policies=policies,
        capacity=capacity,
        active_assignments=active_assignments,
    )


def test_register_validates_identity_catalog_collisions_and_capacity() -> None:
    async def exercise() -> None:
        first_app = create_ai_policy_service(
            provider_id="provider.first",
            capacity=3,
        )
        second_app = create_ai_policy_service(
            provider_id="provider.second",
            capacity=3,
        )
        native_policy_ids = {BASIC_POLICY_ID, TACTICAL_POLICY_ID}
        catalog = RegisteredAIProviderCatalog(
            reserved_policy_ids=native_policy_ids,
        )
        await catalog.register(
            provider_id="provider.first",
            base_url="http://provider.first",
            transport=httpx.ASGITransport(app=first_app),
        )

        info = catalog.provider_for_policy(EXTERNAL_BASIC_POLICY_ID)
        assert {
            descriptor.policy_id
            for descriptor in catalog.provider("provider.first").policies
        }.isdisjoint(native_policy_ids)
        assert info.provider_id == "provider.first"
        assert info.capacity == 3
        assert info.active_assignments == 0
        assert info.available_capacity == 3
        assert catalog.policy_descriptor(EXTERNAL_BASIC_POLICY_ID) == (
            EXTERNAL_BASIC_POLICY_DESCRIPTOR
        )

        with pytest.raises(
            RegisteredAIProviderCollisionError,
            match="provider.first",
        ):
            await catalog.register(
                provider_id="provider.first",
                base_url="http://provider.first-again",
                transport=httpx.ASGITransport(app=first_app),
            )
        with pytest.raises(
            RegisteredAIProviderCollisionError,
            match=EXTERNAL_BASIC_POLICY_ID,
        ):
            await catalog.register(
                provider_id="provider.second",
                base_url="http://provider.second",
                transport=httpx.ASGITransport(app=second_app),
            )
        await catalog.close()

        reserved = RegisteredAIProviderCatalog(
            reserved_policy_ids={EXTERNAL_BASIC_POLICY_ID}
        )
        with pytest.raises(
            RegisteredAIProviderCollisionError,
            match="reserved",
        ):
            await reserved.register(
                provider_id="provider.first",
                base_url="http://provider.first",
                transport=httpx.ASGITransport(app=first_app),
            )
        await reserved.close()

    _run(exercise())


@pytest.mark.parametrize(
    ("expected_provider_id", "mutate"),
    (
        (
            "provider.expected",
            lambda payload: {
                **payload,
                "provider_id": "provider.unexpected",
            },
        ),
        (
            "provider.expected",
            lambda payload: {
                **payload,
                "protocol": {
                    **payload["protocol"],
                    "version": payload["protocol"]["version"] + 1,
                },
            },
        ),
        (
            "provider.expected",
            lambda payload: {
                **payload,
                "protocol": {
                    **payload["protocol"],
                    "contract_hash": "0" * 64,
                },
            },
        ),
    ),
)
def test_register_rejects_provider_or_protocol_identity_mismatch(
    expected_provider_id: str,
    mutate: Any,
) -> None:
    factory = _TrackingClientFactory()
    valid = _handshake(expected_provider_id).model_dump(mode="json")

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/handshake"
        return httpx.Response(200, json=mutate(valid))

    async def exercise() -> None:
        catalog = RegisteredAIProviderCatalog(client_factory=factory)
        with pytest.raises(RegisteredAIProviderProtocolError):
            await catalog.register(
                provider_id=expected_provider_id,
                base_url="http://provider.expected",
                transport=httpx.MockTransport(handler),
            )
        assert catalog.providers() == ()
        assert len(factory.clients) == 1
        assert factory.clients[0].is_closed
        await catalog.close()

    _run(exercise())


def test_assignment_owns_server_fence_contiguous_ids_and_wait_timings() -> None:
    async def exercise() -> None:
        sink = BoundedAIInstrumentationSink()
        app = create_ai_policy_service(
            provider_id="provider.lifecycle",
            capacity=2,
        )
        catalog = RegisteredAIProviderCatalog(
            instrumentation_sink=sink,
        )
        await catalog.register(
            provider_id="provider.lifecycle",
            base_url="http://provider.lifecycle",
            transport=httpx.ASGITransport(app=app),
        )
        assignment = await catalog.open_assignment(
            policy_id=EXTERNAL_BASIC_POLICY_ID,
            assignment_id="assignment",
            game_id="game",
            controlled_entity_uuids=("actor",),
        )

        assert assignment.generation == 1
        assert assignment.assignment_token
        assert len(assignment.assignment_token) >= 32
        assert assignment.policy == EXTERNAL_BASIC_POLICY_DESCRIPTOR
        assert catalog.provider("provider.lifecycle").active_assignments == 1
        first = await assignment.decide(
            state=_world(assignment_id="assignment", epoch_index=1)
        )
        second = await assignment.decide(
            state=_world(assignment_id="assignment", epoch_index=2)
        )
        assert isinstance(first.intent, EndTurnIntent)
        assert first.decision_id == 1
        assert second.decision_id == 2
        with pytest.raises(
            RegisteredAIDecisionOrderError,
            match="expected 3",
        ):
            await assignment.decide(
                state=_world(assignment_id="assignment", epoch_index=3),
                decision_id=4,
            )

        old_token = assignment.assignment_token
        await assignment.close()
        assert catalog.provider("provider.lifecycle").active_assignments == 0
        replacement = await catalog.open_assignment(
            policy_id=EXTERNAL_BASIC_POLICY_ID,
            assignment_id="assignment",
            game_id="game",
            controlled_entity_uuids=("actor",),
        )
        assert replacement.generation == 2
        assert replacement.assignment_token != old_token
        await replacement.close()
        await catalog.close()

        phases = tuple(timing.phase for timing in sink.timing_snapshot())
        assert phases.count(AIExecutionPhase.PROVIDER_HANDSHAKE_WAIT) == 1
        assert phases.count(
            AIExecutionPhase.PROVIDER_ASSIGNMENT_OPEN_WAIT
        ) == 2
        assert phases.count(AIExecutionPhase.PROVIDER_DECISION_WAIT) == 2
        assert phases.count(
            AIExecutionPhase.PROVIDER_ASSIGNMENT_CLOSE_WAIT
        ) == 2

    _run(exercise())


def test_transport_and_server_retries_reuse_exact_idempotent_requests() -> None:
    open_bodies: list[bytes] = []
    decision_bodies: list[bytes] = []
    open_calls = 0
    decision_calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal open_calls, decision_calls
        if request.url.path == "/handshake":
            return httpx.Response(
                200,
                json=_handshake("provider.retry").model_dump(mode="json"),
            )
        payload = json.loads(request.content)
        if request.url.path == "/assignments/open":
            open_calls += 1
            open_bodies.append(request.content)
            if open_calls == 1:
                raise httpx.ConnectError("transient", request=request)
            return httpx.Response(
                200,
                json=ExternalAIAssignmentLease(
                    protocol=ExternalAIProtocolIdentity(),
                    assignment_id=payload["assignment_id"],
                    generation=payload["generation"],
                    assignment_token=payload["assignment_token"],
                    game_id=payload["game_id"],
                    controlled_entity_uuids=tuple(
                        payload["controlled_entity_uuids"]
                    ),
                    policy=BASIC_POLICY_DESCRIPTOR,
                ).model_dump(mode="json"),
            )
        if request.url.path == "/assignments/decide":
            decision_calls += 1
            decision_bodies.append(request.content)
            if decision_calls == 1:
                return httpx.Response(503, json={"detail": "transient"})
            return httpx.Response(
                200,
                json=ExternalAIDecisionResponse(
                    protocol=ExternalAIProtocolIdentity(),
                    assignment_id=payload["assignment_id"],
                    generation=payload["generation"],
                    assignment_token=payload["assignment_token"],
                    decision_id=payload["decision_id"],
                    policy=BASIC_POLICY_DESCRIPTOR,
                    intent=EndTurnIntent(),
                ).model_dump(mode="json"),
            )
        if request.url.path == "/assignments/close":
            return httpx.Response(
                200,
                json=ExternalAIAssignmentCloseResponse(
                    protocol=ExternalAIProtocolIdentity(),
                    assignment_id=payload["assignment_id"],
                    generation=payload["generation"],
                    assignment_token=payload["assignment_token"],
                ).model_dump(mode="json"),
            )
        raise AssertionError(request.url.path)

    async def exercise() -> None:
        catalog = RegisteredAIProviderCatalog(max_attempts=2)
        await catalog.register(
            provider_id="provider.retry",
            base_url="http://provider.retry",
            transport=httpx.MockTransport(handler),
        )
        assignment = await catalog.open_assignment(
            policy_id=BASIC_POLICY_ID,
            assignment_id="assignment",
            game_id="game",
            controlled_entity_uuids=("actor",),
        )
        response = await assignment.decide(
            state=_world(assignment_id="assignment", epoch_index=1)
        )
        assert response.decision_id == 1
        assert open_bodies[0] == open_bodies[1]
        assert decision_bodies[0] == decision_bodies[1]
        assert b"session_token" not in decision_bodies[0]
        assert b"objective" not in decision_bodies[0]
        await catalog.close()

    _run(exercise())


def test_malformed_or_mismatched_responses_fail_closed() -> None:
    mode = "open"

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal mode
        if request.url.path == "/handshake":
            return httpx.Response(
                200,
                json=_handshake("provider.malformed").model_dump(mode="json"),
            )
        payload = json.loads(request.content)
        if request.url.path == "/assignments/open":
            if mode == "malformed-open":
                return httpx.Response(200, content=b"{broken")
            return httpx.Response(
                200,
                json=ExternalAIAssignmentLease(
                    protocol=ExternalAIProtocolIdentity(),
                    assignment_id=payload["assignment_id"],
                    generation=payload["generation"],
                    assignment_token=payload["assignment_token"],
                    game_id=payload["game_id"],
                    controlled_entity_uuids=tuple(
                        payload["controlled_entity_uuids"]
                    ),
                    policy=BASIC_POLICY_DESCRIPTOR,
                ).model_dump(mode="json"),
            )
        if request.url.path == "/assignments/decide":
            wrong_policy = BASIC_POLICY_DESCRIPTOR.model_copy(
                update={"version": "unexpected"}
            )
            return httpx.Response(
                200,
                json=ExternalAIDecisionResponse(
                    protocol=ExternalAIProtocolIdentity(),
                    assignment_id=payload["assignment_id"],
                    generation=payload["generation"],
                    assignment_token=payload["assignment_token"],
                    decision_id=payload["decision_id"],
                    policy=wrong_policy,
                    intent=EndTurnIntent(),
                ).model_dump(mode="json"),
            )
        if request.url.path == "/assignments/close":
            return httpx.Response(
                200,
                json=ExternalAIAssignmentCloseResponse(
                    protocol=ExternalAIProtocolIdentity(),
                    assignment_id=payload["assignment_id"],
                    generation=payload["generation"],
                    assignment_token=payload["assignment_token"],
                ).model_dump(mode="json"),
            )
        raise AssertionError(request.url.path)

    async def exercise() -> None:
        nonlocal mode
        catalog = RegisteredAIProviderCatalog(max_attempts=1)
        await catalog.register(
            provider_id="provider.malformed",
            base_url="http://provider.malformed",
            transport=httpx.MockTransport(handler),
        )
        mode = "malformed-open"
        with pytest.raises(
            RegisteredAIProviderProtocolError,
            match="decode",
        ):
            await catalog.open_assignment(
                policy_id=BASIC_POLICY_ID,
                assignment_id="malformed",
                game_id="game",
                controlled_entity_uuids=("actor",),
            )
        mode = "open"
        assignment = await catalog.open_assignment(
            policy_id=BASIC_POLICY_ID,
            assignment_id="mismatch",
            game_id="game",
            controlled_entity_uuids=("actor",),
        )
        with pytest.raises(
            RegisteredAIProviderProtocolError,
            match="policy",
        ):
            await assignment.decide(
                state=_world(assignment_id="mismatch", epoch_index=1)
            )
        await catalog.close()

    _run(exercise())


def test_every_assignment_response_must_echo_exact_fence_and_policy() -> None:
    response_mode = "open-fence"

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal response_mode
        if request.url.path == "/handshake":
            return httpx.Response(
                200,
                json=_handshake("provider.fences").model_dump(mode="json"),
            )
        payload = json.loads(request.content)
        if request.url.path == "/assignments/open":
            response_token = (
                "wrong-server-issued-token"
                if response_mode == "open-fence"
                else payload["assignment_token"]
            )
            return httpx.Response(
                200,
                json=ExternalAIAssignmentLease(
                    protocol=ExternalAIProtocolIdentity(),
                    assignment_id=payload["assignment_id"],
                    generation=payload["generation"],
                    assignment_token=response_token,
                    game_id=payload["game_id"],
                    controlled_entity_uuids=tuple(
                        payload["controlled_entity_uuids"]
                    ),
                    policy=BASIC_POLICY_DESCRIPTOR,
                ).model_dump(mode="json"),
            )
        if request.url.path == "/assignments/decide":
            response_assignment_id = (
                "wrong-assignment"
                if response_mode == "decision-fence"
                else payload["assignment_id"]
            )
            return httpx.Response(
                200,
                json=ExternalAIDecisionResponse(
                    protocol=ExternalAIProtocolIdentity(),
                    assignment_id=response_assignment_id,
                    generation=payload["generation"],
                    assignment_token=payload["assignment_token"],
                    decision_id=payload["decision_id"],
                    policy=BASIC_POLICY_DESCRIPTOR,
                    intent=EndTurnIntent(),
                ).model_dump(mode="json"),
            )
        if request.url.path == "/assignments/close":
            response_generation = (
                payload["generation"] + 1
                if response_mode == "close-fence"
                else payload["generation"]
            )
            return httpx.Response(
                200,
                json=ExternalAIAssignmentCloseResponse(
                    protocol=ExternalAIProtocolIdentity(),
                    assignment_id=payload["assignment_id"],
                    generation=response_generation,
                    assignment_token=payload["assignment_token"],
                ).model_dump(mode="json"),
            )
        raise AssertionError(request.url.path)

    async def exercise() -> None:
        nonlocal response_mode
        catalog = RegisteredAIProviderCatalog(max_attempts=1)
        await catalog.register(
            provider_id="provider.fences",
            base_url="http://provider.fences",
            transport=httpx.MockTransport(handler),
        )
        with pytest.raises(
            RegisteredAIProviderProtocolError,
            match="server fence",
        ):
            await catalog.open_assignment(
                policy_id=BASIC_POLICY_ID,
                assignment_id="wrong-open",
                game_id="game",
                controlled_entity_uuids=("actor",),
            )

        response_mode = "valid"
        assignment = await catalog.open_assignment(
            policy_id=BASIC_POLICY_ID,
            assignment_id="assignment",
            game_id="game",
            controlled_entity_uuids=("actor",),
        )
        response_mode = "decision-fence"
        with pytest.raises(
            RegisteredAIProviderProtocolError,
            match="assignment fence",
        ):
            await assignment.decide(
                state=_world(assignment_id="assignment", epoch_index=1)
            )
        response_mode = "close-fence"
        with pytest.raises(
            RegisteredAIProviderProtocolError,
            match="server fence",
        ):
            await assignment.close()
        response_mode = "valid"
        await assignment.close()
        await catalog.close()

    _run(exercise())


def test_uncertain_decision_can_only_retry_the_identical_request() -> None:
    decision_calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal decision_calls
        if request.url.path == "/handshake":
            return httpx.Response(
                200,
                json=_handshake("provider.uncertain").model_dump(mode="json"),
            )
        payload = json.loads(request.content)
        if request.url.path == "/assignments/open":
            return httpx.Response(
                200,
                json=ExternalAIAssignmentLease(
                    protocol=ExternalAIProtocolIdentity(),
                    assignment_id=payload["assignment_id"],
                    generation=payload["generation"],
                    assignment_token=payload["assignment_token"],
                    game_id=payload["game_id"],
                    controlled_entity_uuids=tuple(
                        payload["controlled_entity_uuids"]
                    ),
                    policy=BASIC_POLICY_DESCRIPTOR,
                ).model_dump(mode="json"),
            )
        if request.url.path == "/assignments/decide":
            decision_calls += 1
            if decision_calls == 1:
                raise httpx.ReadTimeout("uncertain", request=request)
            return httpx.Response(
                200,
                json=ExternalAIDecisionResponse(
                    protocol=ExternalAIProtocolIdentity(),
                    assignment_id=payload["assignment_id"],
                    generation=payload["generation"],
                    assignment_token=payload["assignment_token"],
                    decision_id=payload["decision_id"],
                    policy=BASIC_POLICY_DESCRIPTOR,
                    intent=EndTurnIntent(),
                ).model_dump(mode="json"),
            )
        if request.url.path == "/assignments/close":
            return httpx.Response(
                200,
                json=ExternalAIAssignmentCloseResponse(
                    protocol=ExternalAIProtocolIdentity(),
                    assignment_id=payload["assignment_id"],
                    generation=payload["generation"],
                    assignment_token=payload["assignment_token"],
                ).model_dump(mode="json"),
            )
        raise AssertionError(request.url.path)

    async def exercise() -> None:
        catalog = RegisteredAIProviderCatalog(max_attempts=1)
        await catalog.register(
            provider_id="provider.uncertain",
            base_url="http://provider.uncertain",
            transport=httpx.MockTransport(handler),
        )
        assignment = await catalog.open_assignment(
            policy_id=BASIC_POLICY_ID,
            assignment_id="assignment",
            game_id="game",
            controlled_entity_uuids=("actor",),
        )
        original = _world(assignment_id="assignment", epoch_index=1)
        with pytest.raises(RegisteredAIProviderTransportError):
            await assignment.decide(state=original)
        with pytest.raises(
            RegisteredAIDecisionOrderError,
            match="exact same",
        ):
            await assignment.decide(
                state=_world(assignment_id="assignment", epoch_index=2)
            )
        recovered = await assignment.decide(state=original)
        assert recovered.decision_id == 1
        assert assignment.next_decision_id == 2
        await catalog.close()

    _run(exercise())


def test_timeout_is_bounded_and_client_errors_are_not_retried() -> None:
    timeout_calls = 0

    async def timeout_handler(request: httpx.Request) -> httpx.Response:
        nonlocal timeout_calls
        timeout_calls += 1
        raise httpx.ReadTimeout("timed out", request=request)

    async def client_error_handler(
        request: httpx.Request,
    ) -> httpx.Response:
        nonlocal timeout_calls
        timeout_calls += 1
        return httpx.Response(400, json={"detail": "bad request"})

    async def exercise() -> None:
        nonlocal timeout_calls
        timed = RegisteredAIProviderCatalog(
            timeout_seconds=0.01,
            max_attempts=2,
        )
        with pytest.raises(
            RegisteredAIProviderTransportError,
            match="2 attempts",
        ):
            await timed.register(
                provider_id="provider.timeout",
                base_url="http://provider.timeout",
                transport=httpx.MockTransport(timeout_handler),
            )
        assert timeout_calls == 2
        await timed.close()

        timeout_calls = 0
        rejected = RegisteredAIProviderCatalog(max_attempts=3)
        with pytest.raises(
            RegisteredAIProviderTransportError,
            match="HTTP 400",
        ):
            await rejected.register(
                provider_id="provider.rejected",
                base_url="http://provider.rejected",
                transport=httpx.MockTransport(client_error_handler),
            )
        assert timeout_calls == 1
        await rejected.close()

    _run(exercise())


def test_unregister_closes_remote_assignments_and_owned_http_client() -> None:
    async def exercise() -> None:
        runtime = create_ai_policy_service_runtime(
            provider_id="provider.close",
            capacity=2,
        )
        app = create_ai_policy_service(runtime=runtime)
        factory = _TrackingClientFactory()
        catalog = RegisteredAIProviderCatalog(client_factory=factory)
        await catalog.register(
            provider_id="provider.close",
            base_url="http://provider.close",
            transport=httpx.ASGITransport(app=app),
        )
        await catalog.open_assignment(
            policy_id=EXTERNAL_BASIC_POLICY_ID,
            assignment_id="assignment",
            game_id="game",
            controlled_entity_uuids=("actor",),
        )
        assert runtime.provider.handshake().active_assignments == 1

        with pytest.raises(
            RegisteredAIProviderBusyError,
            match="still owns 1 live assignments",
        ):
            await catalog.unregister("provider.close")

        assert runtime.provider.handshake().active_assignments == 1
        assert len(factory.clients) == 1
        assert not factory.clients[0].is_closed
        assert len(catalog.providers()) == 1

        await catalog.unregister("provider.close", force=True)

        assert runtime.provider.handshake().active_assignments == 0
        assert len(factory.clients) == 1
        assert factory.clients[0].is_closed
        assert catalog.providers() == ()
        await catalog.close()

    _run(exercise())
