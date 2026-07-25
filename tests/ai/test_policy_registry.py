"""Assignment-fresh policy registry tests."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import cast

import pytest

from dnd.ai.instrumentation import (
    AIExecutionPhase,
    AIInstrumentation,
    AIInstrumentationContext,
    BoundedAIInstrumentationSink,
)
from dnd.ai.policy import PolicyDescriptor
from dnd.ai.registry import (
    DuplicatePolicyError,
    PolicyFactoryIdentityError,
    PolicyRegistry,
    UnknownPolicyError,
)


@dataclass
class _Memory:
    decisions: int = 0


class _Policy:
    descriptor = PolicyDescriptor(
        policy_id="test.fresh",
        version="1",
        display_name="Fresh",
    )

    def decide(self, state: str, memory: _Memory) -> str:
        memory.decisions += 1
        return state


def _clock(values: tuple[int, ...]) -> Callable[[], int]:
    iterator: Iterator[int] = iter(values)
    return lambda: next(iterator)


def _context(
    *,
    descriptor: PolicyDescriptor = _Policy.descriptor,
    decision_id: str = "assignment-initialization",
) -> AIInstrumentationContext:
    return AIInstrumentationContext(
        game_id="game",
        assignment_id="assignment",
        actor_uuid="actor",
        decision_id=decision_id,
        policy=descriptor,
    )


def test_registry_creates_fresh_policy_and_memory_per_assignment() -> None:
    registry: PolicyRegistry[str, str] = PolicyRegistry()
    registry.register(
        descriptor=_Policy.descriptor,
        policy_factory=_Policy,
        memory_factory=_Memory,
    )

    instrumentation = AIInstrumentation()
    first = registry.create_binding(
        "test.fresh",
        instrumentation=instrumentation,
        instrumentation_context=_context(decision_id="initialize-1"),
    )
    second = registry.create_binding(
        "test.fresh",
        instrumentation=instrumentation,
        instrumentation_context=_context(decision_id="initialize-2"),
    )

    assert first.policy is not second.policy
    assert first.memory is not second.memory
    assert first.decide("one") == "one"
    first_memory = cast(_Memory, first.memory)
    second_memory = cast(_Memory, second.memory)
    assert first_memory.decisions == 1
    assert second_memory.decisions == 0
    assert registry.descriptors() == (_Policy.descriptor,)
    assert registry.require_descriptor("test.fresh") == _Policy.descriptor


def test_registry_rejects_duplicate_unknown_and_mismatched_factories() -> None:
    registry: PolicyRegistry[str, str] = PolicyRegistry()
    registry.register(
        descriptor=_Policy.descriptor,
        policy_factory=_Policy,
        memory_factory=_Memory,
    )

    with pytest.raises(DuplicatePolicyError):
        registry.register(
            descriptor=_Policy.descriptor,
            policy_factory=_Policy,
            memory_factory=_Memory,
        )
    with pytest.raises(UnknownPolicyError):
        registry.create_binding(
            "missing",
            instrumentation=AIInstrumentation(),
            instrumentation_context=_context(),
        )
    with pytest.raises(UnknownPolicyError):
        registry.require_descriptor("missing")

    wrong_descriptor = PolicyDescriptor(
        policy_id="test.expected",
        version="1",
        display_name="Expected",
    )
    mismatch_registry: PolicyRegistry[str, str] = PolicyRegistry()
    mismatch_registry.register(
        descriptor=wrong_descriptor,
        policy_factory=_Policy,
        memory_factory=_Memory,
    )
    with pytest.raises(PolicyFactoryIdentityError):
        mismatch_registry.create_binding(
            "test.expected",
            instrumentation=AIInstrumentation(),
            instrumentation_context=_context(descriptor=wrong_descriptor),
        )


def test_registry_times_policy_and_memory_construction_without_factory_plumbing() -> None:
    registry: PolicyRegistry[str, str] = PolicyRegistry()
    factory_calls: list[str] = []

    def create_policy() -> _Policy:
        factory_calls.append("policy")
        return _Policy()

    def create_memory() -> _Memory:
        factory_calls.append("memory")
        return _Memory()

    registry.register(
        descriptor=_Policy.descriptor,
        policy_factory=create_policy,
        memory_factory=create_memory,
    )
    sink = BoundedAIInstrumentationSink()
    instrumentation = AIInstrumentation(
        sink=sink,
        wall_clock_ns=_clock((10, 20, 30, 50)),
        thread_cpu_clock_ns=_clock((1, 3, 5, 9)),
    )
    context = _context()

    binding = registry.create_binding(
        "test.fresh",
        instrumentation=instrumentation,
        instrumentation_context=context,
    )

    assert isinstance(binding.policy, _Policy)
    assert isinstance(binding.memory, _Memory)
    assert factory_calls == ["policy", "memory"]
    timings = sink.timing_snapshot()
    assert tuple(timing.phase for timing in timings) == (
        AIExecutionPhase.POLICY_CONSTRUCTION,
        AIExecutionPhase.MEMORY_CONSTRUCTION,
    )
    assert tuple(timing.wall_duration_ns for timing in timings) == (10, 20)
    assert tuple(timing.thread_cpu_duration_ns for timing in timings) == (2, 4)


def test_registry_rejects_mismatched_construction_instrumentation() -> None:
    registry: PolicyRegistry[str, str] = PolicyRegistry()
    registry.register(
        descriptor=_Policy.descriptor,
        policy_factory=_Policy,
        memory_factory=_Memory,
    )
    instrumentation = AIInstrumentation()
    mismatched_context = _context(
        descriptor=PolicyDescriptor(
            policy_id="test.other",
            version="1",
            display_name="Other",
        )
    )
    with pytest.raises(ValueError, match="does not match"):
        registry.create_binding(
            "test.fresh",
            instrumentation=instrumentation,
            instrumentation_context=mismatched_context,
        )
