"""Core-owned timing and bounded trace tests."""

from __future__ import annotations

from collections.abc import Callable, Iterator

import pytest

from dnd.ai.instrumentation import (
    AIExecutionPhase,
    AIInstrumentation,
    AIInstrumentationContext,
    BoundedAIInstrumentationSink,
)
from dnd.ai.policy import PolicyDescriptor, StatelessPolicyMemory
from dnd.ai.registry import PolicyRegistry
from dnd.ai.runner import InstrumentedPolicyRunner


DESCRIPTOR = PolicyDescriptor(
    policy_id="test.instrumented",
    version="1",
    display_name="Instrumented",
)
CONTEXT = AIInstrumentationContext(
    game_id="game",
    assignment_id="assignment",
    actor_uuid="actor",
    decision_id="decision",
    policy=DESCRIPTOR,
)


def _clock(values: tuple[int, ...]) -> Callable[[], int]:
    iterator: Iterator[int] = iter(values)
    return lambda: next(iterator)


class _LogicOnlyPolicy:
    descriptor = DESCRIPTOR

    def __init__(self) -> None:
        self.calls = 0

    def decide(self, state: str, memory: StatelessPolicyMemory) -> str:
        del memory
        self.calls += 1
        return f"decision:{state}"


class _FailingLogicOnlyPolicy:
    descriptor = DESCRIPTOR

    def decide(self, state: str, memory: StatelessPolicyMemory) -> str:
        del state, memory
        raise LookupError("policy failure")


def test_runner_owns_policy_timing_and_completion_trace() -> None:
    sink = BoundedAIInstrumentationSink()
    instrumentation = AIInstrumentation(
        sink=sink,
        wall_clock_ns=_clock((100, 160)),
        thread_cpu_clock_ns=_clock((20, 27)),
    )
    registry: PolicyRegistry[str, str] = PolicyRegistry()
    registry.register(
        descriptor=DESCRIPTOR,
        policy_factory=_LogicOnlyPolicy,
        memory_factory=StatelessPolicyMemory,
    )
    binding = registry.create_binding(
        DESCRIPTOR.policy_id,
        instrumentation=AIInstrumentation(),
        instrumentation_context=CONTEXT,
    )
    runner: InstrumentedPolicyRunner[str, str] = (
        InstrumentedPolicyRunner(instrumentation)
    )

    decision = runner.decide(
        binding=binding,
        state="state",
        context=CONTEXT,
    )

    assert decision == "decision:state"
    policy = binding.policy
    assert isinstance(policy, _LogicOnlyPolicy)
    assert policy.calls == 1
    timing = sink.timing_snapshot()[0]
    assert timing.phase is AIExecutionPhase.POLICY_DECISION
    assert timing.wall_duration_ns == 60
    assert timing.thread_cpu_duration_ns == 7
    assert timing.succeeded is True
    assert timing.error_type is None
    event = sink.event_snapshot()[0]
    assert event.event == "policy_decision_completed"
    assert event.attributes == (("decision_type", "str"),)


def test_runner_records_failure_without_swallowing_policy_exception() -> None:
    sink = BoundedAIInstrumentationSink()
    instrumentation = AIInstrumentation(
        sink=sink,
        wall_clock_ns=_clock((500, 530)),
        thread_cpu_clock_ns=_clock((80, 82)),
    )
    registry: PolicyRegistry[str, str] = PolicyRegistry()
    registry.register(
        descriptor=DESCRIPTOR,
        policy_factory=_FailingLogicOnlyPolicy,
        memory_factory=StatelessPolicyMemory,
    )
    binding = registry.create_binding(
        DESCRIPTOR.policy_id,
        instrumentation=AIInstrumentation(),
        instrumentation_context=CONTEXT,
    )
    runner: InstrumentedPolicyRunner[str, str] = (
        InstrumentedPolicyRunner(instrumentation)
    )

    with pytest.raises(LookupError, match="policy failure"):
        runner.decide(
            binding=binding,
            state="state",
            context=CONTEXT,
        )

    timing = sink.timing_snapshot()[0]
    assert timing.succeeded is False
    assert timing.error_type == "LookupError"
    assert sink.event_snapshot()[0].event == "policy_decision_failed"


def test_instrumentation_sink_and_event_attributes_are_bounded() -> None:
    sink = BoundedAIInstrumentationSink(maximum_timings=1, maximum_events=2)
    instrumentation = AIInstrumentation(
        sink=sink,
        maximum_event_attributes=1,
        maximum_attribute_length=4,
    )

    for index in range(3):
        instrumentation.emit_event(
            context=CONTEXT,
            event=f"event_{index}",
            attributes={"second": "discarded", "first": "123456"},
        )
    with instrumentation.measure(
        context=CONTEXT,
        phase=AIExecutionPhase.STATE_PROJECTION,
    ):
        pass
    with instrumentation.measure(
        context=CONTEXT,
        phase=AIExecutionPhase.ACTION_EXECUTION,
    ):
        pass

    events = sink.event_snapshot()
    assert tuple(event.event for event in events) == ("event_1", "event_2")
    assert events[-1].attributes == (("firs", "1234"),)
    timings = sink.timing_snapshot()
    assert len(timings) == 1
    assert timings[0].phase is AIExecutionPhase.ACTION_EXECUTION
