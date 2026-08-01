"""Lifecycle and execution ownership for one native AI side assignment."""

from __future__ import annotations

from collections import deque
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
from dnd.ai.runtime.assignment_lifecycle import (
    AIAssignmentState,
    AIDecisionBudget,
    DEFAULT_MAXIMUM_CONSECUTIVE_CANCELED_ACTIONS,
    DEFAULT_MAXIMUM_DECISIONS_PER_TURN,
    assignment_turn_key,
    require_controlled_entities,
    validate_assignment_ownership,
)
from dnd.ai.runtime.state_projection import (
    AIDecisionState,
    SubjectiveAIStateProjector,
)
from dnd.controller import ControllerStepResult, TurnContext
from dnd.entity import Entity


DEFAULT_FEEDBACK_RETENTION: Final = 128


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
        self._state = AIAssignmentState.CREATED
        self._budget = AIDecisionBudget(
            maximum_decisions_per_turn=maximum,
            maximum_consecutive_canceled_actions=(
                maximum_consecutive_canceled_actions
            ),
        )
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
    def state(self) -> AIAssignmentState:
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
        if self._state is AIAssignmentState.CLOSED:
            raise RuntimeError("native AI assignment is closed")
        validate_assignment_ownership(self.controlled_entity_uuids, entities)
        self._state = AIAssignmentState.STARTED

    def close(self) -> None:
        """Close idempotently and time teardown outside custom policy code."""
        if self._state is AIAssignmentState.CLOSED:
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
            self._state = AIAssignmentState.CLOSED
            self._budget.close_turn()

    def execute_next_action(
        self,
        entity: Entity,
        context: TurnContext,
    ) -> ControllerStepResult:
        """Project, decide, validate, dispatch, and reduce one policy decision."""
        if self._state is AIAssignmentState.CREATED:
            self.start(require_controlled_entities(self.controlled_entity_uuids))
        if self._state is AIAssignmentState.CLOSED:
            return ControllerStepResult(end_turn=True)
        if entity.uuid not in self.controlled_entity_uuids:
            raise ValueError("actor is not owned by this native AI assignment")

        self._budget.reset_for_turn(assignment_turn_key(entity, context))
        if self._budget.limit_reached:
            self._record_limit_feedback(entity)
            return ControllerStepResult(end_turn=True)

        decision_sequence = self._budget.begin_decision()
        instrumentation_context = AIInstrumentationContext(
            game_id=self.game_id,
            assignment_id=self.assignment_id,
            actor_uuid=str(entity.uuid),
            decision_id=f"{self.assignment_id}:{decision_sequence}",
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
        except AIDecisionValidationError as error:
            return self._record_decision_error(
                entity=entity,
                error=error,
                outcome=NativeAIDecisionOutcome.REJECTED,
                instrumentation_context=instrumentation_context,
                row_id=error.row_id,
            )

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
                    if self._budget.turn_decisions == 1
                    else DecisionEpochReason.ACTION_COMPLETED
                ),
            )
        with self._instrumentation.measure(
            context=instrumentation_context,
            phase=AIExecutionPhase.MEMORY_REDUCTION,
        ):
            self._reduce_pre_decision_memory(decision_state)

        try:
            decision = self._runner.decide(
                binding=self._binding,
                state=decision_state.world,
                context=instrumentation_context,
            )
        except Exception as error:
            return self._record_decision_error(
                entity=entity,
                error=error,
                outcome=NativeAIDecisionOutcome.FAILED,
                instrumentation_context=instrumentation_context,
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
        if self._budget.record_resolution(
            action_canceled=resolution.action_canceled,
        ):
            return ControllerStepResult(
                event=resolution.step.event,
                end_turn=True,
            )
        return resolution.step

    def _record_decision_error(
        self,
        *,
        entity: Entity,
        error: Exception,
        outcome: NativeAIDecisionOutcome,
        instrumentation_context: AIInstrumentationContext,
        row_id: str | None = None,
    ) -> ControllerStepResult:
        """Reduce a policy-owned failure without hiding engine execution bugs."""
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
                row_id=row_id,
                outcome=outcome,
                error_type=type(error).__name__,
                error_message=str(error),
            ),
            instrumentation_context,
        )
        return ControllerStepResult(end_turn=True)

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

    def _record_limit_feedback(self, entity: Entity) -> None:
        decision_id = (
            f"{self.assignment_id}:{self._budget.next_sequence()}"
        )
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
