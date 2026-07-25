"""Generation-fenced external policy assignments with isolated live memory."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
import hashlib
import hmac
import json
from threading import Lock, RLock

from pydantic import TypeAdapter

from dnd.ai.contracts.decision import PolicyIntent
from dnd.ai.contracts.observation import SubjectiveWorldState
from dnd.ai.instrumentation import (
    AIExecutionPhase,
    AIInstrumentation,
    AIInstrumentationContext,
    AIInstrumentationSink,
    BoundedAIInstrumentationSink,
)
from dnd.ai.policies.basic import CanonicalPolicyRegistry
from dnd.ai.policy import PolicyDescriptor
from dnd.ai.registry import BoundPolicy, UnknownPolicyError
from dnd.ai.runner import InstrumentedPolicyRunner
from server.external_ai_protocol import (
    ExternalAIAssignmentCloseRequest,
    ExternalAIAssignmentCloseResponse,
    ExternalAIAssignmentLease,
    ExternalAIAssignmentOpenRequest,
    ExternalAIDecisionRequest,
    ExternalAIDecisionResponse,
    ExternalAIPolicyProviderHandshake,
    ExternalAIProtocolIdentity,
)


_POLICY_INTENT_ADAPTER = TypeAdapter(PolicyIntent)


class ExternalAIRegistryError(RuntimeError):
    """Base provider failure with a stable HTTP-facing error code."""

    code = "external_ai_registry_error"
    status_code = 409

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message

    def detail(self) -> dict[str, str]:
        """Return the closed structured error body used by the service."""
        return {"code": self.code, "message": self.message}


class ExternalAICapacityError(ExternalAIRegistryError):
    code = "provider_capacity_exhausted"
    status_code = 429


class ExternalAIPolicyUnavailableError(ExternalAIRegistryError):
    code = "policy_not_advertised"
    status_code = 400


class ExternalAIAssignmentNotFoundError(ExternalAIRegistryError):
    code = "assignment_not_found"
    status_code = 404


class ExternalAIAssignmentFenceError(ExternalAIRegistryError):
    code = "assignment_fence_mismatch"


class ExternalAIAssignmentConflictError(ExternalAIRegistryError):
    code = "assignment_open_conflict"


class ExternalAIAssignmentClosedError(ExternalAIRegistryError):
    code = "assignment_closed"


class ExternalAIDecisionOrderError(ExternalAIRegistryError):
    code = "decision_out_of_order"


class ExternalAIDecisionReplayConflictError(ExternalAIRegistryError):
    code = "decision_replay_conflict"


class ExternalAIFeedbackOrderError(ExternalAIRegistryError):
    code = "feedback_out_of_order"


class ExternalAIStateOwnershipError(ExternalAIRegistryError):
    code = "subjective_state_ownership_mismatch"
    status_code = 400


class ExternalAIProviderShutdownError(ExternalAIRegistryError):
    code = "provider_shutdown"
    status_code = 503


@dataclass(frozen=True, slots=True)
class _CachedDecision:
    request_hash: str
    response: ExternalAIDecisionResponse


@dataclass(slots=True)
class _ExternalAIAssignment:
    open_request: ExternalAIAssignmentOpenRequest
    lease: ExternalAIAssignmentLease
    binding: BoundPolicy[SubjectiveWorldState, PolicyIntent] | None
    runner: InstrumentedPolicyRunner[SubjectiveWorldState, PolicyIntent] | None
    response_cache_size: int
    lock: Lock = field(default_factory=Lock)
    last_decision_id: int = 0
    last_feedback_decision_id: int = 0
    response_cache: OrderedDict[int, _CachedDecision] = field(
        default_factory=OrderedDict
    )
    close_response: ExternalAIAssignmentCloseResponse | None = None

    @property
    def closed(self) -> bool:
        return self.close_response is not None


class ExternalAIProviderRegistry:
    """Own external provider assignments without spawning or gameplay I/O.

    The registry has one lock per assignment.  State reduction, feedback
    reduction, and policy invocation all run beneath that lock, giving each
    memory object exactly one writer while allowing unrelated assignments to
    decide concurrently.
    """

    def __init__(
        self,
        *,
        provider_id: str,
        capacity: int,
        policy_registry: CanonicalPolicyRegistry,
        response_cache_size: int = 64,
        instrumentation_sink: AIInstrumentationSink | None = None,
    ) -> None:
        if not provider_id:
            raise ValueError("provider_id must not be empty")
        if capacity < 1:
            raise ValueError("capacity must be positive")
        if response_cache_size < 1:
            raise ValueError("response_cache_size must be positive")
        self.provider_id = provider_id
        self.capacity = capacity
        self.response_cache_size = response_cache_size
        self._policy_registry = policy_registry
        self._instrumentation_sink = (
            instrumentation_sink or BoundedAIInstrumentationSink()
        )
        self._instrumentation = AIInstrumentation(
            sink=self._instrumentation_sink
        )
        self._assignments: dict[str, _ExternalAIAssignment] = {}
        self._registry_lock = RLock()
        self._shutdown = False

    @property
    def instrumentation_sink(self) -> AIInstrumentationSink:
        """Expose the configured core sink for diagnostics exporters."""
        return self._instrumentation_sink

    def handshake(self) -> ExternalAIPolicyProviderHandshake:
        """Return a cold, deterministic catalog plus live capacity."""
        with self._registry_lock:
            active = sum(
                not assignment.closed
                for assignment in self._assignments.values()
            )
        return ExternalAIPolicyProviderHandshake(
            protocol=ExternalAIProtocolIdentity(),
            provider_id=self.provider_id,
            policies=self._policy_registry.descriptors(),
            capacity=self.capacity,
            active_assignments=active,
        )

    def open_assignment(
        self,
        request: ExternalAIAssignmentOpenRequest,
    ) -> ExternalAIAssignmentLease:
        """Open exactly one generation or replace it with a newer fence."""
        self._require_running()
        try:
            descriptor = self._policy_registry.require_descriptor(
                request.policy_id
            )
        except UnknownPolicyError as error:
            raise ExternalAIPolicyUnavailableError(str(error)) from error

        with self._registry_lock:
            self._require_running()
            existing = self._assignments.get(request.assignment_id)
            if existing is None:
                if self._active_assignment_count() >= self.capacity:
                    raise ExternalAICapacityError(
                        "external AI provider has no assignment capacity"
                    )
                created = self._create_assignment(request, descriptor)
                self._assignments[request.assignment_id] = created
                return created.lease

            with existing.lock:
                if request.generation < existing.open_request.generation:
                    raise ExternalAIAssignmentFenceError(
                        "assignment generation is stale"
                    )
                if request.generation == existing.open_request.generation:
                    self._require_token(
                        existing.open_request.assignment_token,
                        request.assignment_token,
                    )
                    if request != existing.open_request:
                        raise ExternalAIAssignmentConflictError(
                            "assignment generation is already open with "
                            "different immutable parameters"
                        )
                    if existing.closed:
                        raise ExternalAIAssignmentClosedError(
                            "assignment generation is already closed"
                        )
                    return existing.lease
                if hmac.compare_digest(
                    request.assignment_token,
                    existing.open_request.assignment_token,
                ):
                    raise ExternalAIAssignmentFenceError(
                        "a newer assignment generation must rotate its token"
                    )
                replacement = self._create_assignment(request, descriptor)
                self._close_assignment(existing)
                self._assignments[request.assignment_id] = replacement
                return replacement.lease

    def decide(
        self,
        request: ExternalAIDecisionRequest,
    ) -> ExternalAIDecisionResponse:
        """Reduce ordered inputs and invoke one assignment policy exactly once."""
        self._require_running()
        assignment = self._require_assignment(request.assignment_id)
        with assignment.lock:
            self._require_active_fence(
                assignment,
                generation=request.generation,
                assignment_token=request.assignment_token,
            )
            request_hash = _request_hash(request)
            cached = assignment.response_cache.get(request.decision_id)
            if cached is not None:
                if cached.request_hash != request_hash:
                    raise ExternalAIDecisionReplayConflictError(
                        "decision id was already used by a different request"
                    )
                assignment.response_cache.move_to_end(request.decision_id)
                return cached.response

            expected_decision_id = assignment.last_decision_id + 1
            if request.decision_id != expected_decision_id:
                raise ExternalAIDecisionOrderError(
                    "decision id must be contiguous; expected "
                    f"{expected_decision_id}, received {request.decision_id}"
                )
            self._validate_feedback_delta(assignment, request)
            actor_uuid = self._validate_subjective_state(
                assignment,
                request.state,
            )
            binding = assignment.binding
            runner = assignment.runner
            if binding is None or runner is None:
                raise ExternalAIAssignmentClosedError(
                    "assignment generation is closed"
                )
            context = AIInstrumentationContext(
                game_id=assignment.open_request.game_id,
                assignment_id=request.assignment_id,
                actor_uuid=actor_uuid,
                decision_id=(
                    f"{request.assignment_id}:{request.generation}:"
                    f"{request.decision_id}"
                ),
                policy=binding.descriptor,
            )
            with self._instrumentation.measure(
                context=context,
                phase=AIExecutionPhase.DECISION_TOTAL,
            ):
                if request.feedback:
                    with self._instrumentation.measure(
                        context=context,
                        phase=AIExecutionPhase.FEEDBACK_REDUCTION,
                    ):
                        for feedback in request.feedback:
                            binding.reduce_feedback(feedback.to_native())
                with self._instrumentation.measure(
                    context=context,
                    phase=AIExecutionPhase.MEMORY_REDUCTION,
                ):
                    binding.reduce_state(request.state)
                intent = _POLICY_INTENT_ADAPTER.validate_python(
                    runner.decide(
                        binding=binding,
                        state=request.state,
                        context=context,
                    )
                )
            response = ExternalAIDecisionResponse(
                protocol=ExternalAIProtocolIdentity(),
                assignment_id=request.assignment_id,
                generation=request.generation,
                assignment_token=request.assignment_token,
                decision_id=request.decision_id,
                policy=binding.descriptor,
                intent=intent,
            )
            assignment.last_decision_id = request.decision_id
            if request.feedback:
                assignment.last_feedback_decision_id = (
                    request.feedback[-1].decision_id
                )
            assignment.response_cache[request.decision_id] = _CachedDecision(
                request_hash=request_hash,
                response=response,
            )
            while (
                len(assignment.response_cache)
                > assignment.response_cache_size
            ):
                assignment.response_cache.popitem(last=False)
            return response

    def close_assignment(
        self,
        request: ExternalAIAssignmentCloseRequest,
    ) -> ExternalAIAssignmentCloseResponse:
        """Close one exact fence and retain an idempotent tombstone."""
        assignment = self._require_assignment(request.assignment_id)
        with assignment.lock:
            self._require_fence(
                assignment,
                generation=request.generation,
                assignment_token=request.assignment_token,
            )
            if assignment.close_response is not None:
                return assignment.close_response
            return self._close_assignment(assignment)

    def shutdown(self) -> None:
        """Stop admitting work and tear down every live assignment once."""
        with self._registry_lock:
            if self._shutdown:
                return
            self._shutdown = True
            assignments = tuple(self._assignments.values())
        for assignment in assignments:
            with assignment.lock:
                self._close_assignment(assignment)

    def _create_assignment(
        self,
        request: ExternalAIAssignmentOpenRequest,
        descriptor: PolicyDescriptor,
    ) -> _ExternalAIAssignment:
        policy_descriptor = self._policy_registry.require_descriptor(
            request.policy_id
        )
        if descriptor != policy_descriptor:
            raise ExternalAIPolicyUnavailableError(
                "policy descriptor changed during assignment creation"
            )
        context = AIInstrumentationContext(
            game_id=request.game_id,
            assignment_id=request.assignment_id,
            actor_uuid=request.controlled_entity_uuids[0],
            decision_id=(
                f"{request.assignment_id}:{request.generation}:"
                "assignment-initialization"
            ),
            policy=policy_descriptor,
        )
        with self._instrumentation.measure(
            context=context,
            phase=AIExecutionPhase.ASSIGNMENT_INITIALIZATION,
        ):
            binding = self._policy_registry.create_binding(
                request.policy_id,
                instrumentation=self._instrumentation,
                instrumentation_context=context,
            )
            runner: InstrumentedPolicyRunner[
                SubjectiveWorldState,
                PolicyIntent,
            ] = InstrumentedPolicyRunner(self._instrumentation)
        lease = ExternalAIAssignmentLease(
            protocol=ExternalAIProtocolIdentity(),
            assignment_id=request.assignment_id,
            generation=request.generation,
            assignment_token=request.assignment_token,
            game_id=request.game_id,
            controlled_entity_uuids=request.controlled_entity_uuids,
            policy=policy_descriptor,
        )
        return _ExternalAIAssignment(
            open_request=request,
            lease=lease,
            binding=binding,
            runner=runner,
            response_cache_size=self.response_cache_size,
        )

    def _close_assignment(
        self,
        assignment: _ExternalAIAssignment,
    ) -> ExternalAIAssignmentCloseResponse:
        if assignment.close_response is not None:
            return assignment.close_response
        binding = assignment.binding
        descriptor = (
            binding.descriptor
            if binding is not None
            else assignment.lease.policy
        )
        context = AIInstrumentationContext(
            game_id=assignment.open_request.game_id,
            assignment_id=assignment.open_request.assignment_id,
            actor_uuid=assignment.open_request.controlled_entity_uuids[0],
            decision_id=(
                f"{assignment.open_request.assignment_id}:"
                f"{assignment.open_request.generation}:assignment-teardown"
            ),
            policy=descriptor,
        )
        with self._instrumentation.measure(
            context=context,
            phase=AIExecutionPhase.ASSIGNMENT_TEARDOWN,
        ):
            assignment.response_cache.clear()
            assignment.binding = None
            assignment.runner = None
            assignment.close_response = ExternalAIAssignmentCloseResponse(
                protocol=ExternalAIProtocolIdentity(),
                assignment_id=assignment.open_request.assignment_id,
                generation=assignment.open_request.generation,
                assignment_token=assignment.open_request.assignment_token,
            )
        return assignment.close_response

    def _require_running(self) -> None:
        with self._registry_lock:
            if self._shutdown:
                raise ExternalAIProviderShutdownError(
                    "external AI provider has shut down"
                )

    def _require_assignment(
        self,
        assignment_id: str,
    ) -> _ExternalAIAssignment:
        with self._registry_lock:
            assignment = self._assignments.get(assignment_id)
        if assignment is None:
            raise ExternalAIAssignmentNotFoundError(
                f"assignment {assignment_id!r} is not registered"
            )
        return assignment

    def _require_active_fence(
        self,
        assignment: _ExternalAIAssignment,
        *,
        generation: int,
        assignment_token: str,
    ) -> None:
        self._require_fence(
            assignment,
            generation=generation,
            assignment_token=assignment_token,
        )
        if assignment.closed:
            raise ExternalAIAssignmentClosedError(
                "assignment generation is closed"
            )

    @staticmethod
    def _require_fence(
        assignment: _ExternalAIAssignment,
        *,
        generation: int,
        assignment_token: str,
    ) -> None:
        if generation != assignment.open_request.generation:
            raise ExternalAIAssignmentFenceError(
                "assignment generation does not match the active fence"
            )
        ExternalAIProviderRegistry._require_token(
            assignment.open_request.assignment_token,
            assignment_token,
        )

    @staticmethod
    def _require_token(expected: str, received: str) -> None:
        if not hmac.compare_digest(expected, received):
            raise ExternalAIAssignmentFenceError(
                "assignment token does not match the active fence"
            )

    @staticmethod
    def _validate_feedback_delta(
        assignment: _ExternalAIAssignment,
        request: ExternalAIDecisionRequest,
    ) -> None:
        if (
            request.feedback
            and request.feedback[0].decision_id
            <= assignment.last_feedback_decision_id
        ):
            raise ExternalAIFeedbackOrderError(
                "feedback must be a new ordered delta"
            )
        if any(
            feedback.decision_id > assignment.last_decision_id
            for feedback in request.feedback
        ):
            raise ExternalAIFeedbackOrderError(
                "feedback references a decision not yet made"
            )
        controlled = set(
            assignment.open_request.controlled_entity_uuids
        )
        if any(
            feedback.actor_uuid not in controlled
            for feedback in request.feedback
        ):
            raise ExternalAIStateOwnershipError(
                "feedback actor is outside assignment ownership"
            )

    @staticmethod
    def _validate_subjective_state(
        assignment: _ExternalAIAssignment,
        state: SubjectiveWorldState,
    ) -> str:
        controlled = set(
            assignment.open_request.controlled_entity_uuids
        )
        state_controlled = set(state.session.controlled_entity_uuids)
        if state_controlled != controlled:
            raise ExternalAIStateOwnershipError(
                "subjective state controlled entities do not match assignment"
            )
        epoch = state.current_epoch
        if epoch is None:
            raise ExternalAIStateOwnershipError(
                "decision state has no current decision epoch"
            )
        if (
            epoch.actor_uuid not in controlled
            or state.session.active_entity_uuid != epoch.actor_uuid
            or not state.session.is_my_turn
        ):
            raise ExternalAIStateOwnershipError(
                "subjective state actor does not match assignment authority"
            )
        return epoch.actor_uuid

    def _active_assignment_count(self) -> int:
        return sum(
            not assignment.closed
            for assignment in self._assignments.values()
        )


def _request_hash(request: ExternalAIDecisionRequest) -> str:
    canonical = json.dumps(
        request.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


__all__ = [
    "ExternalAIAssignmentClosedError",
    "ExternalAIAssignmentConflictError",
    "ExternalAIAssignmentFenceError",
    "ExternalAIAssignmentNotFoundError",
    "ExternalAICapacityError",
    "ExternalAIDecisionOrderError",
    "ExternalAIDecisionReplayConflictError",
    "ExternalAIFeedbackOrderError",
    "ExternalAIPolicyUnavailableError",
    "ExternalAIProviderRegistry",
    "ExternalAIProviderShutdownError",
    "ExternalAIRegistryError",
    "ExternalAIStateOwnershipError",
]
