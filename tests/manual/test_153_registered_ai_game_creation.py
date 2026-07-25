"""Canonical game-creation integration for registered AI policy providers."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from typing import Any

import httpx

from dnd.ai.contracts.decision import EndTurnIntent, PolicyIntent
from dnd.ai.contracts.observation import SubjectiveWorldState
from dnd.ai.policy import PolicyDescriptor, StatelessPolicyMemory
from dnd.ai.registry import PolicyRegistry
from dnd.encounter import EncounterState
from server import event_server
from server.registered_ai_controller import RegisteredAIController
from server.registered_ai_provider import RegisteredAIProviderCatalog
from services.ai_policy_server.app import create_ai_policy_service
from services.ai_policy_server.composition import (
    create_ai_policy_service_runtime,
)


EXTERNAL_POLICY = PolicyDescriptor(
    policy_id="example.remote",
    version="1",
    display_name="Example remote",
    description="Deterministic external integration policy.",
)
ADMIN_HEADERS = {"Authorization": "Bearer test-deployment-secret"}


class _EndTurnPolicy:
    """Logic-only provider policy used to expose one deterministic boundary."""

    descriptor = EXTERNAL_POLICY

    def __init__(self, probe: "_ProviderProbe") -> None:
        self._probe = probe
        probe.policy_instances.append(self)

    def decide(
        self,
        state: SubjectiveWorldState,
        memory: StatelessPolicyMemory,
    ) -> PolicyIntent:
        del memory
        actor_uuid = (
            state.current_epoch.actor_uuid
            if state.current_epoch is not None
            else "missing"
        )
        self._probe.calls.append(actor_uuid)
        return EndTurnIntent()


@dataclass
class _ProviderProbe:
    """Provider-private facts proving assignment isolation in integration."""

    calls: list[str] = field(default_factory=list)
    policy_instances: list[_EndTurnPolicy] = field(default_factory=list)
    memory_instances: list[StatelessPolicyMemory] = field(
        default_factory=list
    )
    open_requests: list[dict[str, Any]] = field(default_factory=list)


class _RecordingASGITransport(httpx.AsyncBaseTransport):
    """Capture provider open fences before forwarding to its ASGI app."""

    def __init__(self, provider_app: Any, probe: _ProviderProbe) -> None:
        self._transport = httpx.ASGITransport(app=provider_app)
        self._probe = probe

    async def handle_async_request(
        self,
        request: httpx.Request,
    ) -> httpx.Response:
        if request.url.path == "/assignments/open":
            self._probe.open_requests.append(
                json.loads(request.content)
            )
        return await self._transport.handle_async_request(request)

    async def aclose(self) -> None:
        await self._transport.aclose()


class _ProviderClientFactory:
    """Route catalog HTTP to one provider ASGI app without opening a socket."""

    def __init__(
        self,
        provider_app: Any,
        probe: _ProviderProbe,
    ) -> None:
        self._provider_app = provider_app
        self._probe = probe
        self.calls = 0

    def __call__(
        self,
        *,
        base_url: str,
        timeout: httpx.Timeout,
        transport: httpx.AsyncBaseTransport | None,
    ) -> httpx.AsyncClient:
        del transport
        self.calls += 1
        return httpx.AsyncClient(
            base_url=base_url,
            timeout=timeout,
            transport=_RecordingASGITransport(
                self._provider_app,
                self._probe,
            ),
        )


def _run[ResultT](operation: Coroutine[Any, Any, ResultT]) -> ResultT:
    return asyncio.run(operation)


def _provider_fixture(
    *,
    capacity: int,
) -> tuple[Any, Any, _ProviderClientFactory, _ProviderProbe]:
    probe = _ProviderProbe()
    registry: PolicyRegistry[SubjectiveWorldState, PolicyIntent] = (
        PolicyRegistry()
    )

    def create_memory() -> StatelessPolicyMemory:
        memory = StatelessPolicyMemory()
        probe.memory_instances.append(memory)
        return memory

    registry.register(
        descriptor=EXTERNAL_POLICY,
        policy_factory=lambda: _EndTurnPolicy(probe),
        memory_factory=create_memory,
    )
    runtime = create_ai_policy_service_runtime(
        provider_id="provider.example",
        capacity=capacity,
        policy_registry=registry,
    )
    provider_app = create_ai_policy_service(runtime=runtime)
    return (
        runtime,
        provider_app,
        _ProviderClientFactory(provider_app, probe),
        probe,
    )


def _start_payload(
    *,
    side_a: str,
    side_b: str,
    opening_side: str = "side_a",
) -> dict[str, object]:
    def side(controller: str, side_id: str) -> dict[str, str]:
        payload = {
            "controller": controller,
            "name": side_id,
        }
        if controller == "ai":
            payload["policy_id"] = EXTERNAL_POLICY.policy_id
        return payload

    return {
        "scenario": {
            "kind": "preset",
            "arena_id": "standard_skeleton_doors",
        },
        "side_a": side(side_a, "Side A"),
        "side_b": side(side_b, "Side B"),
        "opening_side": opening_side,
    }


async def _with_isolated_provider_catalog(
    operation: Callable[
        [httpx.AsyncClient, Any, _ProviderClientFactory, _ProviderProbe],
        Coroutine[Any, Any, None],
    ],
    *,
    capacity: int,
) -> None:
    await event_server.prepare_new_simulation_start()
    previous_catalog = event_server.registered_ai_provider_catalog
    if not previous_catalog.closed:
        await previous_catalog.close()
    runtime, _, factory, probe = _provider_fixture(capacity=capacity)
    catalog = RegisteredAIProviderCatalog(
        reserved_policy_ids={
            descriptor.policy_id
            for descriptor in event_server.native_policy_registry.descriptors()
        },
        client_factory=factory,
    )
    event_server.registered_ai_provider_catalog = catalog
    event_server.configure_ai_provider_admin_token("test-deployment-secret")
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=event_server.app),
            base_url="http://main-server",
        ) as client:
            await operation(client, runtime, factory, probe)
    finally:
        await event_server.prepare_new_simulation_start()
        await catalog.close()
        event_server.registered_ai_provider_catalog = (
            event_server._new_registered_ai_provider_catalog()
        )
        event_server.configure_ai_provider_admin_token(None)


def test_registered_provider_is_one_prepared_ai_path_and_defers_logic() -> None:
    """Registration, creation, activation, execution, and teardown are fenced."""

    async def exercise(
        client: httpx.AsyncClient,
        runtime: Any,
        factory: _ProviderClientFactory,
        probe: _ProviderProbe,
    ) -> None:
        unauthorized = await client.post(
            "/admin/ai/providers",
            json={
                "provider_id": "provider.example",
                "base_url": "http://provider.example",
            },
        )
        assert unauthorized.status_code == 403
        assert factory.calls == 0

        registered = await client.post(
            "/admin/ai/providers",
            headers=ADMIN_HEADERS,
            json={
                "provider_id": "provider.example",
                "base_url": "http://provider.example",
            },
        )
        assert registered.status_code == 200
        assert registered.json()["provider_id"] == "provider.example"
        assert "assignment_token" not in registered.text
        assert factory.calls == 1

        catalog = await client.get("/game-creation/catalog")
        assert catalog.status_code == 200
        external = next(
            row
            for row in catalog.json()["ai_policies"]
            if row["descriptor"]["policy_id"] == EXTERNAL_POLICY.policy_id
        )
        assert external == {
            "descriptor": EXTERNAL_POLICY.model_dump(mode="json"),
            "execution": "registered_provider",
            "provider_id": "provider.example",
            "capacity": 8,
            "active_assignments": 0,
            "available_capacity": 8,
        }

        started = await client.post(
            "/game-creation/start",
            json=_start_payload(
                side_a="human",
                side_b="ai",
                opening_side="side_b",
            ),
        )
        assert started.status_code == 200
        result = started.json()
        assert result["side_b"]["policy_id"] == EXTERNAL_POLICY.policy_id
        assert result["side_b"]["policy_execution"] == (
            "registered_provider"
        )
        assert result["side_b"]["provider_id"] == "provider.example"
        assert probe.calls == []
        assert event_server.sim.encounter is not None
        assert event_server.sim.encounter.state is EncounterState.NOT_STARTED
        external_entities = result["side_b"]["entity_assignments"]
        assert runtime.provider.handshake().active_assignments == len(
            external_entities
        )
        controllers = event_server.sim.registered_ai_controllers
        assert len(controllers) == len(external_entities)
        assert all(
            isinstance(controller, RegisteredAIController)
            for controller in controllers
        )
        assert len({controller.uuid for controller in controllers}) == len(
            controllers
        )
        assert len(
            {controller.assignment_id for controller in controllers}
        ) == len(controllers)
        assert all(
            len(controller.controlled_entity_uuids) == 1
            for controller in controllers
        )
        assert len(probe.policy_instances) == len(controllers)
        assert len({id(policy) for policy in probe.policy_instances}) == len(
            controllers
        )
        assert len(probe.memory_instances) == len(controllers)
        assert len({id(memory) for memory in probe.memory_instances}) == len(
            controllers
        )
        assert len(probe.open_requests) == len(controllers)
        assert {
            request["controlled_entity_uuids"][0]
            for request in probe.open_requests
        } == {
            row["entity_uuid"] for row in external_entities
        }
        assert len(
            {
                request["assignment_token"]
                for request in probe.open_requests
            }
        ) == len(controllers)
        assert {
            request["generation"] for request in probe.open_requests
        } == {1}

        busy = await client.delete(
            "/admin/ai/providers/provider.example",
            headers=ADMIN_HEADERS,
        )
        assert busy.status_code == 409
        assert busy.json()["detail"]["code"] == "ai_provider_conflict"

        session = await client.post(
            "/session/create",
            json={"player_type": "human", "name": "Player"},
        )
        session_id = session.json()["session_id"]
        joined = await client.post(
            "/game/join",
            json={
                "session_id": session_id,
                "entity_uuids": [
                    row["entity_uuid"]
                    for row in result["side_a"]["entity_assignments"]
                ],
            },
        )
        assert joined.status_code == 200
        bootstrap_response = await client.get(
            "/replication/bootstrap",
            params={"session_id": session_id},
        )
        assert bootstrap_response.status_code == 200
        bootstrap = bootstrap_response.json()
        activated = await client.post(
            "/game-creation/activate",
            json={
                "session_id": session_id,
                "expected_source_stream_id": bootstrap["protocol"][
                    "source_stream_id"
                ],
                "expected_generation_id": bootstrap["protocol"][
                    "generation_id"
                ],
                "expected_perspective_epoch_id": bootstrap["perspective"][
                    "perspective_epoch_id"
                ],
            },
        )
        assert activated.status_code == 200

        deadline = asyncio.get_running_loop().time() + 3.0
        while (
            not event_server.sim.waiting_for_human
            and asyncio.get_running_loop().time() < deadline
        ):
            await asyncio.sleep(0.01)
        assert probe.calls
        assert event_server.sim.waiting_for_human
        assert event_server.sim.game is not None
        assert str(event_server.sim.game.active_entity_uuid) in {
            row["entity_uuid"]
            for row in result["side_a"]["entity_assignments"]
        }

        replacement = await client.post(
            "/game-creation/start",
            json=_start_payload(side_a="human", side_b="human"),
        )
        assert replacement.status_code == 200
        assert runtime.provider.handshake().active_assignments == 0
        removed = await client.delete(
            "/admin/ai/providers/provider.example",
            headers=ADMIN_HEADERS,
        )
        assert removed.status_code == 200
        assert removed.json() == {
            "status": "unregistered",
            "provider_id": "provider.example",
        }

    _run(_with_isolated_provider_catalog(exercise, capacity=8))


def test_second_provider_side_capacity_failure_rolls_back_first_lease() -> None:
    """A two-side setup either publishes both assignments or publishes none."""

    async def exercise(
        client: httpx.AsyncClient,
        runtime: Any,
        factory: _ProviderClientFactory,
        probe: _ProviderProbe,
    ) -> None:
        del factory
        registered = await client.post(
            "/admin/ai/providers",
            headers=ADMIN_HEADERS,
            json={
                "provider_id": "provider.example",
                "base_url": "http://provider.example",
            },
        )
        assert registered.status_code == 200

        rejected = await client.post(
            "/game-creation/start",
            json=_start_payload(side_a="ai", side_b="ai"),
        )

        assert rejected.status_code == 503
        assert rejected.json()["detail"]["code"] == (
            "ai_provider_unavailable"
        )
        assert runtime.provider.handshake().active_assignments == 0
        assert len(probe.open_requests) == 1
        assert len(probe.policy_instances) == 1
        assert len(probe.memory_instances) == 1
        assert event_server.sim.encounter is None
        assert event_server.sim.game is None
        assert event_server.sim.registered_ai_controllers == []

    _run(_with_isolated_provider_catalog(exercise, capacity=1))
