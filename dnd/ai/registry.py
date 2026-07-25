"""Explicit policy factories with per-assignment policy and memory ownership."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Generic, TypeVar

from dnd.ai.instrumentation import (
    AIExecutionPhase,
    AIInstrumentation,
    AIInstrumentationContext,
)
from dnd.ai.feedback import NativeAIDecisionFeedback
from dnd.ai.policy import Policy, PolicyDescriptor


StateT = TypeVar("StateT")
DecisionT = TypeVar("DecisionT")
MemoryT = TypeVar("MemoryT")


class PolicyRegistryError(RuntimeError):
    """Base error for invalid policy registry operations."""


class DuplicatePolicyError(PolicyRegistryError):
    """Raised when two implementations claim the same policy id."""


class UnknownPolicyError(PolicyRegistryError):
    """Raised when composition requests an unregistered policy."""


class PolicyFactoryIdentityError(PolicyRegistryError):
    """Raised when a factory returns a policy with an unexpected identity."""


@dataclass(frozen=True, slots=True)
class BoundPolicy(Generic[StateT, DecisionT]):
    """Type-erased live policy/memory pair for a heterogeneous registry."""

    descriptor: PolicyDescriptor
    policy: object
    memory: object
    _decide: Callable[[StateT], DecisionT]
    _reduce_state: Callable[[StateT], None]
    _reduce_feedback: Callable[[NativeAIDecisionFeedback], None]

    def decide(self, state: StateT) -> DecisionT:
        """Invoke the concrete policy with its concrete assignment memory."""
        return self._decide(state)

    def reduce_state(self, state: StateT) -> None:
        """Apply the registration-owned pure state reducer."""
        self._reduce_state(state)

    def reduce_feedback(self, feedback: NativeAIDecisionFeedback) -> None:
        """Apply the registration-owned pure authoritative feedback reducer."""
        self._reduce_feedback(feedback)


@dataclass(frozen=True, slots=True)
class _PolicyRegistration(Generic[StateT, DecisionT]):
    descriptor: PolicyDescriptor
    create: Callable[
        [AIInstrumentation, AIInstrumentationContext],
        BoundPolicy[StateT, DecisionT],
    ]


class PolicyRegistry(Generic[StateT, DecisionT]):
    """Heterogeneous registry that erases memory only after safe binding.

    Each registration method is generic in its own memory type.  The closure
    created here permanently pairs that concrete policy with that concrete
    memory, so the native runtime never casts a foreign memory object into a
    policy call.
    """

    def __init__(self) -> None:
        self._registrations: dict[
            str,
            _PolicyRegistration[StateT, DecisionT],
        ] = {}

    def register(
        self,
        *,
        descriptor: PolicyDescriptor,
        policy_factory: Callable[
            [],
            Policy[StateT, MemoryT, DecisionT],
        ],
        memory_factory: Callable[[], MemoryT],
        reduce_state: Callable[[MemoryT, StateT], None] | None = None,
        reduce_feedback: Callable[
            [MemoryT, NativeAIDecisionFeedback],
            None,
        ]
        | None = None,
    ) -> None:
        """Register one policy with its own private concrete memory type."""
        if descriptor.policy_id in self._registrations:
            raise DuplicatePolicyError(
                f"policy {descriptor.policy_id!r} is already registered"
            )

        def create(
            instrumentation: AIInstrumentation,
            context: AIInstrumentationContext,
        ) -> BoundPolicy[StateT, DecisionT]:
            with instrumentation.measure(
                context=context,
                phase=AIExecutionPhase.POLICY_CONSTRUCTION,
            ):
                policy = policy_factory()
            with instrumentation.measure(
                context=context,
                phase=AIExecutionPhase.MEMORY_CONSTRUCTION,
            ):
                memory = memory_factory()
            if policy.descriptor != descriptor:
                raise PolicyFactoryIdentityError(
                    f"policy factory for {descriptor.policy_id!r} returned "
                    f"{policy.descriptor.policy_id!r} version "
                    f"{policy.descriptor.version!r}"
                )

            def reduce_bound_state(state: StateT) -> None:
                if reduce_state is not None:
                    reduce_state(memory, state)

            def reduce_bound_feedback(
                feedback: NativeAIDecisionFeedback,
            ) -> None:
                if reduce_feedback is not None:
                    reduce_feedback(memory, feedback)

            return BoundPolicy(
                descriptor=descriptor,
                policy=policy,
                memory=memory,
                _decide=lambda state: policy.decide(state, memory),
                _reduce_state=reduce_bound_state,
                _reduce_feedback=reduce_bound_feedback,
            )

        self._registrations[descriptor.policy_id] = _PolicyRegistration(
            descriptor=descriptor,
            create=create,
        )

    def create_binding(
        self,
        policy_id: str,
        *,
        instrumentation: AIInstrumentation,
        instrumentation_context: AIInstrumentationContext,
    ) -> BoundPolicy[StateT, DecisionT]:
        """Create a fresh safely-bound heterogeneous policy assignment."""
        registration = self._registrations.get(policy_id)
        if registration is None:
            raise UnknownPolicyError(f"policy {policy_id!r} is not registered")
        if instrumentation_context.policy != registration.descriptor:
            raise ValueError(
                "instrumentation context policy does not match registry policy"
            )
        return registration.create(instrumentation, instrumentation_context)

    def require_descriptor(self, policy_id: str) -> PolicyDescriptor:
        """Return one registered identity before assignment construction."""
        registration = self._registrations.get(policy_id)
        if registration is None:
            raise UnknownPolicyError(f"policy {policy_id!r} is not registered")
        return registration.descriptor

    def descriptors(self) -> tuple[PolicyDescriptor, ...]:
        """Return identities in stable policy-id order."""
        return tuple(
            registration.descriptor
            for _, registration in sorted(self._registrations.items())
        )

    def __contains__(self, policy_id: object) -> bool:
        return policy_id in self._registrations
