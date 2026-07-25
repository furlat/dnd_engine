"""One authoritative validation and execution path for every AI deployment."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from dnd.action_dispatch import ActionDispatchResult, dispatch_available_action
from dnd.ai.contracts.control import ActionAffordance, END_TURN_ROW_ID
from dnd.ai.contracts.decision import EndTurnIntent, ExecuteIntent, PolicyIntent
from dnd.ai.contracts.observation import SubjectiveWorldState
from dnd.ai.contracts.semantics import ActionTag
from dnd.ai.feedback import NativeAIDecisionFeedback, NativeAIDecisionOutcome
from dnd.ai.instrumentation import (
    AIExecutionPhase,
    AIInstrumentation,
    AIInstrumentationContext,
)
from dnd.ai.runtime.movement_revalidation import (
    SubjectiveMovementContinuationGuard,
)
from dnd.ai.runtime.state_projection import AIDecisionState
from dnd.controller import ControllerStepResult, TurnContext
from dnd.core.base_actions import AvailableActionInfo, AvailableTarget
from dnd.core.events import Event
from dnd.entity import Entity


@dataclass(frozen=True, slots=True)
class ValidatedExecuteDecision:
    """Exact current-epoch public row and private engine binding."""

    intent: ExecuteIntent
    affordance: ActionAffordance
    action_info: AvailableActionInfo
    target: AvailableTarget
    extra_target_uuids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AIDecisionResolution:
    """Authoritative engine result plus reducer feedback for one intent."""

    step: ControllerStepResult
    feedback: NativeAIDecisionFeedback
    action_canceled: bool = False


class AIDecisionValidationError(ValueError):
    """Raised when a policy intent is not executable in its current epoch."""

    def __init__(self, message: str, *, row_id: str | None = None) -> None:
        super().__init__(message)
        self.row_id = row_id


def resolve_policy_intent(
    *,
    entity: Entity,
    turn_context: TurnContext,
    state: AIDecisionState,
    intent: PolicyIntent,
    instrumentation: AIInstrumentation,
    instrumentation_context: AIInstrumentationContext,
    project_world: Callable[[], SubjectiveWorldState],
) -> AIDecisionResolution:
    """Validate and execute one policy intent through the sole engine bridge."""
    with instrumentation.measure(
        context=instrumentation_context,
        phase=AIExecutionPhase.DECISION_VALIDATION,
    ):
        validated = validate_policy_intent(state, intent)
    if isinstance(validated, EndTurnIntent):
        return AIDecisionResolution(
            step=ControllerStepResult(end_turn=True),
            feedback=NativeAIDecisionFeedback(
                decision_id=instrumentation_context.decision_id,
                actor_uuid=str(entity.uuid),
                epoch_id=state.epoch_build.epoch.epoch_id,
                row_id=None,
                outcome=NativeAIDecisionOutcome.END_TURN,
            ),
        )

    affordance = validated.affordance
    semantics = state.epoch_build.epoch.affordances.semantics_for(affordance)
    movement_guard = (
        SubjectiveMovementContinuationGuard(
            actor_uuid=str(entity.uuid),
            world=state.world,
            project_world=project_world,
        )
        if ActionTag.MOVEMENT_VOLUNTARY in semantics.tags
        else None
    )
    with instrumentation.measure(
        context=instrumentation_context,
        phase=AIExecutionPhase.ACTION_EXECUTION,
    ):
        dispatch = dispatch_available_action(
            entity,
            action_info=validated.action_info,
            target=validated.target,
            extra_target_uuids=validated.extra_target_uuids,
            prefer_safe=validated.intent.prefer_safe,
            movement_guard=movement_guard,
        )
    return AIDecisionResolution(
        step=ControllerStepResult(event=dispatch.event),
        feedback=_feedback_from_dispatch(
            instrumentation_context=instrumentation_context,
            epoch_id=state.epoch_build.epoch.epoch_id,
            row_id=affordance.row_id,
            dispatch=dispatch,
        ),
        action_canceled=dispatch.canceled,
    )


def validate_policy_intent(
    state: AIDecisionState,
    intent: PolicyIntent,
) -> EndTurnIntent | ValidatedExecuteDecision:
    """Bind a public policy intent to current private execution authority."""
    if isinstance(intent, EndTurnIntent):
        return intent
    if not isinstance(intent, ExecuteIntent):
        raise AIDecisionValidationError(
            "policy returned an unsupported decision type"
        )
    epoch = state.epoch_build.epoch
    if epoch.actor_uuid != state.world.session.active_entity_uuid:
        raise AIDecisionValidationError(
            "decision epoch actor does not match subjective turn"
        )
    affordance = epoch.affordances.row_by_id(intent.row_id)
    if affordance is None:
        raise AIDecisionValidationError(
            "policy selected a row absent from the current epoch",
            row_id=intent.row_id,
        )
    if affordance.row_id == END_TURN_ROW_ID:
        return EndTurnIntent()
    if not affordance.can_afford:
        raise AIDecisionValidationError(
            "policy selected an unaffordable row",
            row_id=intent.row_id,
        )
    binding = state.epoch_build.execution_authority.binding_for(affordance)
    if binding is None or binding.target is None:
        raise AIDecisionValidationError(
            "selected row has no exact private execution binding",
            row_id=intent.row_id,
        )
    try:
        extra_targets = affordance.validated_extra_target_uuids(
            intent.extra_target_uuids
        )
    except ValueError as error:
        raise AIDecisionValidationError(
            str(error),
            row_id=intent.row_id,
        ) from error
    return ValidatedExecuteDecision(
        intent=intent,
        affordance=affordance,
        action_info=binding.action_info,
        target=binding.target,
        extra_target_uuids=extra_targets,
    )


def _feedback_from_dispatch(
    *,
    instrumentation_context: AIInstrumentationContext,
    epoch_id: str,
    row_id: str,
    dispatch: ActionDispatchResult,
) -> NativeAIDecisionFeedback:
    event: Event | None = dispatch.event
    if dispatch.movement_revalidation_reason is not None:
        outcome = NativeAIDecisionOutcome.INTERRUPTED
    elif dispatch.canceled:
        outcome = NativeAIDecisionOutcome.CANCELED
    else:
        outcome = NativeAIDecisionOutcome.EXECUTED
    return NativeAIDecisionFeedback(
        decision_id=instrumentation_context.decision_id,
        actor_uuid=instrumentation_context.actor_uuid,
        epoch_id=epoch_id,
        row_id=row_id,
        outcome=outcome,
        event_uuid=str(event.uuid) if event is not None else None,
        outcome_code=getattr(event, "outcome_code", None),
        revalidation_reason=dispatch.movement_revalidation_reason,
    )


__all__ = [
    "AIDecisionResolution",
    "AIDecisionValidationError",
    "ValidatedExecuteDecision",
    "resolve_policy_intent",
    "validate_policy_intent",
]
