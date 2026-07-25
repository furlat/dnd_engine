"""Instrumented policy invocation owned by the native AI architecture."""

from __future__ import annotations

from typing import Generic, TypeVar

from dnd.ai.instrumentation import (
    AIExecutionPhase,
    AIInstrumentation,
    AIInstrumentationContext,
)
from dnd.ai.registry import BoundPolicy


StateT = TypeVar("StateT")
DecisionT = TypeVar("DecisionT")


class InstrumentedPolicyRunner(Generic[StateT, DecisionT]):
    """Invoke policy logic while the core records timing and bounded traces."""

    def __init__(self, instrumentation: AIInstrumentation) -> None:
        self._instrumentation = instrumentation

    def decide(
        self,
        *,
        binding: BoundPolicy[StateT, DecisionT],
        state: StateT,
        context: AIInstrumentationContext,
    ) -> DecisionT:
        """Time one bound policy call, record outcome, and preserve exceptions."""
        if binding.descriptor != context.policy:
            raise ValueError(
                "instrumentation context policy does not match invoked policy"
            )
        try:
            with self._instrumentation.measure(
                context=context,
                phase=AIExecutionPhase.POLICY_DECISION,
            ):
                decision = binding.decide(state)
        except Exception as error:
            self._instrumentation.emit_event(
                context=context,
                event="policy_decision_failed",
                attributes={"error_type": type(error).__name__},
            )
            raise
        self._instrumentation.emit_event(
            context=context,
            event="policy_decision_completed",
            attributes={"decision_type": type(decision).__name__},
        )
        return decision
