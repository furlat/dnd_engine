"""Test-only diagnostics around the shipped external policy service."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from threading import Lock
from typing import Any

from fastapi import FastAPI

from dnd.ai.contracts.decision import EndTurnIntent, PolicyIntent
from dnd.ai.contracts.observation import SubjectiveWorldState
from dnd.ai.instrumentation import BoundedAIInstrumentationSink
from dnd.ai.policy import PolicyDescriptor
from server.external_ai_protocol import (
    ExternalAIAssignmentCloseRequest,
    ExternalAIAssignmentCloseResponse,
    ExternalAIAssignmentLease,
    ExternalAIAssignmentOpenRequest,
    ExternalAIDecisionRequest,
    ExternalAIDecisionResponse,
)
from services.ai_policy_server.external_ai_registry import (
    ExternalAIProviderRegistry,
)
from services.ai_policy_server.app import create_ai_policy_service
from services.ai_policy_server.composition import (
    AIPolicyServiceRuntime,
    create_reference_policy_registry,
)


LIVE_TEST_PROVIDER_ID = "reference.live-test"
LIVE_TEST_PROVIDER_CAPACITY = 4
LIVE_TEST_POLICY_ID = "test.external.end-turn"
LIVE_TEST_POLICY_DESCRIPTOR = PolicyDescriptor(
    policy_id=LIVE_TEST_POLICY_ID,
    version="1",
    display_name="Live Socket End Turn",
    description="Deterministic test-only policy that ends every actor turn.",
)


@dataclass(slots=True)
class _EndTurnMemory:
    actor_uuids: set[str] = field(default_factory=set)
    state_reductions: int = 0


class _EndTurnPolicy:
    descriptor = LIVE_TEST_POLICY_DESCRIPTOR

    def decide(
        self,
        state: SubjectiveWorldState,
        memory: _EndTurnMemory,
    ) -> PolicyIntent:
        del state, memory
        return EndTurnIntent()


def _reduce_end_turn_state(
    memory: _EndTurnMemory,
    state: SubjectiveWorldState,
) -> None:
    epoch = state.current_epoch
    if epoch is not None:
        memory.actor_uuids.add(epoch.actor_uuid)
    memory.state_reductions += 1


def _token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class _AuditedExternalAIProviderRegistry(ExternalAIProviderRegistry):
    """Retain non-secret lifecycle evidence beside the real provider runtime."""

    def __init__(self) -> None:
        policies = create_reference_policy_registry()
        policies.register(
            descriptor=LIVE_TEST_POLICY_DESCRIPTOR,
            policy_factory=_EndTurnPolicy,
            memory_factory=_EndTurnMemory,
            reduce_state=_reduce_end_turn_state,
        )
        sink = BoundedAIInstrumentationSink()
        super().__init__(
            provider_id=LIVE_TEST_PROVIDER_ID,
            capacity=LIVE_TEST_PROVIDER_CAPACITY,
            policy_registry=policies,
            instrumentation_sink=sink,
        )
        self.policy_registry = policies
        self.sink = sink
        self._audit_lock = Lock()
        self._audit_assignments: dict[str, dict[str, Any]] = {}

    def open_assignment(
        self,
        request: ExternalAIAssignmentOpenRequest,
    ) -> ExternalAIAssignmentLease:
        lease = super().open_assignment(request)
        assignment = self._assignments[request.assignment_id]
        binding = assignment.binding
        if binding is None:
            raise RuntimeError("new provider assignment has no policy binding")
        with self._audit_lock:
            self._audit_assignments[request.assignment_id] = {
                "assignment_id": request.assignment_id,
                "game_id": request.game_id,
                "generation": request.generation,
                "token_digest": _token_digest(request.assignment_token),
                "controlled_entity_uuids": list(
                    request.controlled_entity_uuids
                ),
                "policy_id": request.policy_id,
                "policy_instance_id": id(binding.policy),
                "memory_instance_id": id(binding.memory),
                "memory_actor_uuids": [],
                "decision_ids": [],
                "decision_actors": [],
                "decision_rounds": [],
                "decision_intents": [],
                "closed": False,
                "close_token_digest": None,
            }
        return lease

    def decide(
        self,
        request: ExternalAIDecisionRequest,
    ) -> ExternalAIDecisionResponse:
        response = super().decide(request)
        assignment = self._assignments[request.assignment_id]
        binding = assignment.binding
        if binding is None:
            raise RuntimeError("decided provider assignment lost its binding")
        actors = getattr(binding.memory, "actors", None)
        if actors is None:
            actors = getattr(binding.memory, "actor_uuids", ())
        epoch = request.state.current_epoch
        with self._audit_lock:
            row = self._audit_assignments[request.assignment_id]
            row["decision_ids"].append(request.decision_id)
            row["decision_actors"].append(
                epoch.actor_uuid if epoch is not None else None
            )
            row["decision_rounds"].append(
                epoch.round_number if epoch is not None else None
            )
            row["decision_intents"].append(
                response.intent.model_dump(mode="json")
            )
            row["memory_actor_uuids"] = sorted(actors)
        return response

    def close_assignment(
        self,
        request: ExternalAIAssignmentCloseRequest,
    ) -> ExternalAIAssignmentCloseResponse:
        response = super().close_assignment(request)
        with self._audit_lock:
            row = self._audit_assignments[request.assignment_id]
            row["closed"] = True
            row["close_token_digest"] = _token_digest(
                request.assignment_token
            )
        return response

    def audit_snapshot(self) -> dict[str, Any]:
        with self._audit_lock:
            assignments = [
                {
                    key: list(value)
                    if isinstance(value, list)
                    else value
                    for key, value in row.items()
                }
                for _, row in sorted(self._audit_assignments.items())
            ]
        handshake = self.handshake()
        return {
            "provider_id": self.provider_id,
            "capacity": self.capacity,
            "active_assignments": handshake.active_assignments,
            "assignments": assignments,
        }


_provider = _AuditedExternalAIProviderRegistry()
_runtime = AIPolicyServiceRuntime(
    provider=_provider,
    policy_registry=_provider.policy_registry,
    instrumentation_sink=_provider.sink,
)
app: FastAPI = create_ai_policy_service(runtime=_runtime)


@app.get("/test/audit")
def get_audit_snapshot() -> dict[str, Any]:
    """Expose localhost-only evidence from this dedicated test process."""
    return _provider.audit_snapshot()
