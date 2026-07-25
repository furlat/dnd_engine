"""Lifecycle and execution ownership for one native AI side assignment."""

from __future__ import annotations

from collections import deque
from enum import Enum
from typing import Final
from uuid import UUID

from dnd.ai.contracts.control import (
    DecisionEpochReason,
)
from dnd.ai.contracts.decision import PolicyIntent
from dnd.ai.contracts.observation import SubjectiveWorldState
from dnd.ai.feedback import (
    NativeAIDecisionFeedback,
    NativeAIDecisionOutcome,
)
from dnd.ai.instrumentation import (
    AIExecutionPhase,
    AIInstrumentation,
    AIInstrumentationContext,
)
from dnd.ai.policies.basic import CanonicalPolicyRegistry
from dnd.ai.registry import BoundPolicy
from dnd.ai.runner import InstrumentedPolicyRunner
from dnd.ai.runtime.execution import (
    AIDecisionValidationError,
    resolve_policy_intent,
)
from dnd.ai.runtime.state_projection import (
    AIDecisionState,
    SubjectiveAIStateProjector,
)
from dnd.controller import ControllerStepResult, TurnContext
from dnd.entity import Entity


DEFAULT_MAXIMUM_DECISIONS_PER_TURN: Final = 32
DEFAULT_MAXIMUM_CONSECUTIVE_CANCELED_ACTIONS: Final = 3
DEFAULT_FEEDBACK_RETENTION: Final = 128


class NativeAIAssignmentState(str, Enum):
    """Explicit lifecycle for one side-owned policy assignment."""

    CREATED = "created"
    STARTED = "started"
    CLOSED = "closed"


class NativeAIAssignment:
    """Own one fresh policy, memory, projector, and bounded decision loop."""

    def __init__(
        self,
        *,
        game_id: str,
        assignment_id: str,
        controlled_entity_uuids: tuple[UUID, ...],
        policy_id: str,
        registry: CanonicalPolicyRegistry,
        instrumentation: AIInstrumentation,
        maximum_decisions_per_turn: int | None = None,
        maximum_consecutive_canceled_actions: int = (
            DEFAULT_MAXIMUM_CONSECUTIVE_CANCELED_ACTIONS
        ),
        feedback_retention: int = DEFAULT_FEEDBACK_RETENTION,
    ) -> None:
        if not game_id:
            raise ValueError("game_id must not be empty")
        if not assignment_id:
            raise ValueError("assignment_id must not be empty")
        if not controlled_entity_uuids:
            raise ValueError("native AI assignment must control at least one entity")
        if len(controlled_entity_uuids) != len(set(controlled_entity_uuids)):
            raise ValueError("controlled_entity_uuids contains duplicates")
        maximum = (
            DEFAULT_MAXIMUM_DECISIONS_PER_TURN
            if maximum_decisions_per_turn is None
            else maximum_decisions_per_turn
        )
        if maximum < 1:
            raise ValueError("maximum_decisions_per_turn must be positive")
        if maximum_consecutive_canceled_actions < 1:
            raise ValueError(
                "maximum_consecutive_canceled_actions must be positive"
            )
        if feedback_retention < 1:
            raise ValueError("feedback_retention must be positive")

        self.game_id = game_id
        self.assignment_id = assignment_id
        self.controlled_entity_uuids = tuple(
            sorted(controlled_entity_uuids, key=str)
        )
        self.policy_id = policy_id
        self.maximum_decisions_per_turn = maximum
        self.maximum_consecutive_canceled_actions = (
            maximum_consecutive_canceled_actions
        )
        self._instrumentation = instrumentation
        self._state = NativeAIAssignmentState.CREATED
        self._decision_sequence = 0
        self._turn_key: tuple[str, int, int] | None = None
        self._turn_decisions = 0
        self._consecutive_canceled_actions = 0
        self._feedback: deque[NativeAIDecisionFeedback] = deque(
            maxlen=feedback_retention
        )

        descriptor = registry.require_descriptor(policy_id)
        initialization_context = AIInstrumentationContext(
            game_id=game_id,
            assignment_id=assignment_id,
            actor_uuid=str(self.controlled_entity_uuids[0]),
            decision_id="assignment-initialization",
            policy=descriptor,
        )
        with instrumentation.measure(
            context=initialization_context,
            phase=AIExecutionPhase.ASSIGNMENT_INITIALIZATION,
        ):
            self._binding: BoundPolicy[
                SubjectiveWorldState,
                PolicyIntent,
            ] = registry.create_binding(
                policy_id,
                instrumentation=instrumentation,
                instrumentation_context=initialization_context,
            )
            self._projector = SubjectiveAIStateProjector(
                assignment_id=assignment_id,
                controlled_entity_uuids=self.controlled_entity_uuids,
            )
            self._runner: InstrumentedPolicyRunner[
                SubjectiveWorldState,
                PolicyIntent,
            ] = InstrumentedPolicyRunner(instrumentation)

    @property
    def state(self) -> NativeAIAssignmentState:
        """Return the explicit assignment lifecycle state."""
        return self._state

    @property
    def world(self) -> SubjectiveWorldState | None:
        """Return the latest retained subjective state."""
        return self._projector.world

    @property
    def feedback(self) -> tuple[NativeAIDecisionFeedback, ...]:
        """Return a stable bounded decision-feedback snapshot."""
        return tuple(self._feedback)

    @property
    def policy_binding(
        self,
    ) -> BoundPolicy[SubjectiveWorldState, PolicyIntent]:
        """Expose assignment-owned policy/memory identity for diagnostics."""
        return self._binding

    def start(self, entities: list[Entity]) -> None:
        """Start once after exact encounter ownership has been established."""
        if self._state is NativeAIAssignmentState.CLOSED:
            raise RuntimeError("native AI assignment is closed")
        actual = {entity.uuid for entity in entities}
        expected = set(self.controlled_entity_uuids)
        if actual != expected:
            raise ValueError(
                "encounter controller ownership does not match native AI assignment"
            )
        self._state = NativeAIAssignmentState.STARTED

    def close(self) -> None:
        """Close idempotently and time teardown outside custom policy code."""
        if self._state is NativeAIAssignmentState.CLOSED:
            return
        context = AIInstrumentationContext(
            game_id=self.game_id,
            assignment_id=self.assignment_id,
            actor_uuid=str(self.controlled_entity_uuids[0]),
            decision_id="assignment-teardown",
            policy=self._binding.descriptor,
        )
        with self._instrumentation.measure(
            context=context,
            phase=AIExecutionPhase.ASSIGNMENT_TEARDOWN,
        ):
            self._state = NativeAIAssignmentState.CLOSED
            self._turn_key = None
            self._turn_decisions = 0
            self._consecutive_canceled_actions = 0

    def execute_next_action(
        self,
        entity: Entity,
        context: TurnContext,
    ) -> ControllerStepResult:
        """Project, decide, validate, dispatch, and reduce one policy decision."""
        if self._state is NativeAIAssignmentState.CREATED:
            self.start(self._live_controlled_entities())
        if self._state is NativeAIAssignmentState.CLOSED:
            return ControllerStepResult(end_turn=True)
        if entity.uuid not in self.controlled_entity_uuids:
            raise ValueError("actor is not owned by this native AI assignment")

        self._reset_turn_counters_if_needed(entity, context)
        if self._turn_decisions >= self.maximum_decisions_per_turn:
            self._record_limit_feedback(entity)
            return ControllerStepResult(end_turn=True)

        self._turn_decisions += 1
        self._decision_sequence += 1
        instrumentation_context = AIInstrumentationContext(
            game_id=self.game_id,
            assignment_id=self.assignment_id,
            actor_uuid=str(entity.uuid),
            decision_id=f"{self.assignment_id}:{self._decision_sequence}",
            policy=self._binding.descriptor,
        )
        try:
            with self._instrumentation.measure(
                context=instrumentation_context,
                phase=AIExecutionPhase.DECISION_TOTAL,
            ):
                return self._execute_instrumented(
                    entity=entity,
                    turn_context=context,
                    instrumentation_context=instrumentation_context,
                )
        except Exception as error:
            outcome = (
                NativeAIDecisionOutcome.REJECTED
                if isinstance(error, AIDecisionValidationError)
                else NativeAIDecisionOutcome.FAILED
            )
            self._instrumentation.emit_event(
                context=instrumentation_context,
                event="native_ai_decision_failed",
                attributes={"error_type": type(error).__name__},
            )
            self._reduce_feedback(
                NativeAIDecisionFeedback(
                    decision_id=instrumentation_context.decision_id,
                    actor_uuid=str(entity.uuid),
                    epoch_id=(
                        self._projector.world.current_epoch.epoch_id
                        if self._projector.world is not None
                        and self._projector.world.current_epoch is not None
                        else None
                    ),
                    row_id=(
                        error.row_id
                        if isinstance(error, AIDecisionValidationError)
                        else None
                    ),
                    outcome=outcome,
                    error_type=type(error).__name__,
                    error_message=str(error),
                ),
                instrumentation_context,
            )
            return ControllerStepResult(end_turn=True)

    def _execute_instrumented(
        self,
        *,
        entity: Entity,
        turn_context: TurnContext,
        instrumentation_context: AIInstrumentationContext,
    ) -> ControllerStepResult:
        with self._instrumentation.measure(
            context=instrumentation_context,
            phase=AIExecutionPhase.STATE_PROJECTION,
        ):
            decision_state = self._projector.project_decision(
                entity,
                turn_context,
                reason=(
                    DecisionEpochReason.TURN_START
                    if self._turn_decisions == 1
                    else DecisionEpochReason.ACTION_COMPLETED
                ),
            )
        with self._instrumentation.measure(
            context=instrumentation_context,
            phase=AIExecutionPhase.MEMORY_REDUCTION,
        ):
            self._reduce_pre_decision_memory(decision_state)

        decision = self._runner.decide(
            binding=self._binding,
            state=decision_state.world,
            context=instrumentation_context,
        )
        resolution = resolve_policy_intent(
            entity=entity,
            turn_context=turn_context,
            state=decision_state,
            intent=decision,
            instrumentation=self._instrumentation,
            instrumentation_context=instrumentation_context,
            project_world=lambda: self._projector.project_world(
                entity,
                turn_context,
            ),
        )
        self._reduce_feedback(resolution.feedback, instrumentation_context)
        if resolution.action_canceled:
            self._consecutive_canceled_actions += 1
        else:
            self._consecutive_canceled_actions = 0
        if (
            self._consecutive_canceled_actions
            >= self.maximum_consecutive_canceled_actions
        ):
            return ControllerStepResult(
                event=resolution.step.event,
                end_turn=True,
            )
        return resolution.step

    def _reduce_pre_decision_memory(
        self,
        state: AIDecisionState,
    ) -> None:
        """Core reducer seam; policy memory remains assignment-local."""
        if state.world.current_epoch is None:
            raise ValueError("projected native AI state has no decision epoch")
        self._binding.reduce_state(state.world)

    def _reduce_feedback(
        self,
        feedback: NativeAIDecisionFeedback,
        context: AIInstrumentationContext,
    ) -> None:
        with self._instrumentation.measure(
            context=context,
            phase=AIExecutionPhase.FEEDBACK_REDUCTION,
        ):
            self._binding.reduce_feedback(feedback)
            self._feedback.append(feedback)
        self._instrumentation.emit_event(
            context=context,
            event="native_ai_decision_resolved",
            attributes={
                "outcome": feedback.outcome.value,
                "row_id": feedback.row_id or "",
            },
        )

    def _reset_turn_counters_if_needed(
        self,
        entity: Entity,
        context: TurnContext,
    ) -> None:
        turn_key = (
            str(entity.uuid),
            context.round_number,
            context.turn_index,
        )
        if self._turn_key == turn_key:
            return
        self._turn_key = turn_key
        self._turn_decisions = 0
        self._consecutive_canceled_actions = 0

    def _record_limit_feedback(self, entity: Entity) -> None:
        self._decision_sequence += 1
        decision_id = f"{self.assignment_id}:{self._decision_sequence}"
        context = AIInstrumentationContext(
            game_id=self.game_id,
            assignment_id=self.assignment_id,
            actor_uuid=str(entity.uuid),
            decision_id=decision_id,
            policy=self._binding.descriptor,
        )
        self._reduce_feedback(
            NativeAIDecisionFeedback(
                decision_id=decision_id,
                actor_uuid=str(entity.uuid),
                epoch_id=(
                    self._projector.world.current_epoch.epoch_id
                    if self._projector.world is not None
                    and self._projector.world.current_epoch is not None
                    else None
                ),
                row_id=None,
                outcome=NativeAIDecisionOutcome.LIMIT_REACHED,
            ),
            context,
        )

    def _live_controlled_entities(self) -> list[Entity]:
        entities = [
            entity
            for entity_uuid in self.controlled_entity_uuids
            for entity in [Entity.get(entity_uuid)]
            if entity is not None
        ]
        if len(entities) != len(self.controlled_entity_uuids):
            raise ValueError("native AI assignment has missing controlled entities")
        return entities
