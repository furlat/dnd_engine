"""Deferred encounter controller for an authenticated external policy provider."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import ClassVar
from uuid import UUID

from pydantic import Field, PrivateAttr

from dnd.ai.contracts.control import DecisionEpochReason
from dnd.ai.contracts.decision import PolicyIntent
from dnd.ai.feedback import NativeAIDecisionFeedback, NativeAIDecisionOutcome
from dnd.ai.instrumentation import (
    AIExecutionPhase,
    AIInstrumentation,
    AIInstrumentationContext,
)
from dnd.ai.runtime.execution import (
    AIDecisionValidationError,
    resolve_policy_intent,
)
from dnd.ai.runtime.state_projection import (
    AIDecisionState,
    SubjectiveAIStateProjector,
)
from dnd.controller import (
    Controller,
    ControllerExecutionMode,
    ControllerStepResult,
    TurnContext,
)
from dnd.entity import Entity
from server.external_ai_protocol import ExternalAIDecisionFeedback
from server.registered_ai_provider import (
    RegisteredAIAssignment,
    RegisteredAIProviderCatalog,
)


DEFAULT_REGISTERED_AI_MAXIMUM_DECISIONS_PER_TURN = 32
DEFAULT_REGISTERED_AI_MAXIMUM_CONSECUTIVE_CANCELED_ACTIONS = 3
DEFAULT_REGISTERED_AI_FEEDBACK_RETENTION = 128


class RegisteredAIControllerState(str, Enum):
    """Explicit local lifecycle around one remote policy assignment fence."""

    CREATED = "created"
    STARTED = "started"
    CLOSED = "closed"


@dataclass(frozen=True, slots=True)
class _PendingProviderDecision:
    """Exact request inputs retained across an ambiguous transport failure."""

    entity_uuid: UUID
    turn_key: tuple[str, int, int]
    sequence: int
    state: AIDecisionState
    instrumentation_context: AIInstrumentationContext
    feedback: tuple[ExternalAIDecisionFeedback, ...]


@dataclass(frozen=True, slots=True)
class RegisteredAIPendingIntent:
    """Awaited provider intent that has not crossed the engine commit fence."""

    controller_uuid: UUID
    entity_uuid: UUID
    turn_key: tuple[str, int, int]
    provider_decision_id: int
    intent: PolicyIntent
    _state: AIDecisionState
    _instrumentation_context: AIInstrumentationContext


class RegisteredAIController(Controller):
    """One side-owned provider assignment using the canonical AI executor."""

    _execution_mode: ClassVar[ControllerExecutionMode] = (
        ControllerExecutionMode.DEFERRED_AUTONOMOUS
    )
    _external_boundary_status: ClassVar[str] = "waiting_for_ai_provider"

    name: str = Field(default="Registered AI")
    controller_type: str = Field(default="registered_ai")
    game_id: str = Field(min_length=1)
    assignment_id: str = Field(min_length=1)
    provider_id: str = Field(min_length=1)
    policy_id: str = Field(min_length=1)
    controlled_entity_uuids: tuple[UUID, ...] = Field(min_length=1)
    maximum_decisions_per_turn: int = Field(
        default=DEFAULT_REGISTERED_AI_MAXIMUM_DECISIONS_PER_TURN,
        ge=1,
    )
    maximum_consecutive_canceled_actions: int = Field(
        default=DEFAULT_REGISTERED_AI_MAXIMUM_CONSECUTIVE_CANCELED_ACTIONS,
        ge=1,
    )

    _remote_assignment: RegisteredAIAssignment | None = PrivateAttr(
        default=None
    )
    _instrumentation: AIInstrumentation | None = PrivateAttr(default=None)
    _projector: SubjectiveAIStateProjector | None = PrivateAttr(default=None)
    _state: RegisteredAIControllerState = PrivateAttr(
        default=RegisteredAIControllerState.CREATED
    )
    _decision_sequence: int = PrivateAttr(default=0)
    _turn_key: tuple[str, int, int] | None = PrivateAttr(default=None)
    _turn_decisions: int = PrivateAttr(default=0)
    _consecutive_canceled_actions: int = PrivateAttr(default=0)
    _feedback: deque[NativeAIDecisionFeedback] = PrivateAttr()
    _pending_feedback: deque[ExternalAIDecisionFeedback] = PrivateAttr()
    _pending_decision: _PendingProviderDecision | None = PrivateAttr(
        default=None
    )
    _pending_intent: RegisteredAIPendingIntent | None = PrivateAttr(
        default=None
    )

    def model_post_init(self, context: object) -> None:
        super().model_post_init(context)
        self._feedback = deque(
            maxlen=DEFAULT_REGISTERED_AI_FEEDBACK_RETENTION
        )
        self._pending_feedback = deque()

    @classmethod
    async def create(
        cls,
        *,
        source_entity_uuid: UUID,
        game_id: str,
        assignment_id: str,
        controlled_entity_uuids: tuple[UUID, ...],
        policy_id: str,
        provider_catalog: RegisteredAIProviderCatalog,
        instrumentation: AIInstrumentation,
        maximum_decisions_per_turn: int = (
            DEFAULT_REGISTERED_AI_MAXIMUM_DECISIONS_PER_TURN
        ),
    ) -> "RegisteredAIController":
        """Open the provider fence before publishing a controller."""
        remote = await provider_catalog.open_assignment(
            policy_id=policy_id,
            game_id=game_id,
            assignment_id=assignment_id,
            controlled_entity_uuids=tuple(
                str(entity_uuid) for entity_uuid in controlled_entity_uuids
            ),
        )
        try:
            projector = SubjectiveAIStateProjector(
                assignment_id=assignment_id,
                controlled_entity_uuids=controlled_entity_uuids,
            )
            controller = cls(
                source_entity_uuid=source_entity_uuid,
                game_id=game_id,
                assignment_id=assignment_id,
                provider_id=remote.provider_id,
                policy_id=policy_id,
                controlled_entity_uuids=controlled_entity_uuids,
                maximum_decisions_per_turn=maximum_decisions_per_turn,
            )
            controller._remote_assignment = remote
            controller._instrumentation = instrumentation
            controller._projector = projector
            return controller
        except Exception as construction_error:
            try:
                await remote.close()
            except Exception as close_error:
                raise ExceptionGroup(
                    "registered AI controller construction and remote "
                    "assignment cleanup both failed",
                    [construction_error, close_error],
                ) from construction_error
            raise

    @property
    def state(self) -> RegisteredAIControllerState:
        return self._state

    @property
    def feedback(self) -> tuple[NativeAIDecisionFeedback, ...]:
        return tuple(self._feedback)

    @property
    def world(self):
        projector = self._require_projector()
        return projector.world

    def start(self, entities: list[Entity]) -> None:
        if self._state is RegisteredAIControllerState.CLOSED:
            raise RuntimeError("registered AI controller is closed")
        actual = {entity.uuid for entity in entities}
        expected = set(self.controlled_entity_uuids)
        if actual != expected:
            raise ValueError(
                "encounter ownership does not match registered AI assignment"
            )
        self._state = RegisteredAIControllerState.STARTED

    def on_encounter_start(self, entities: list[Entity]) -> None:
        self.start(entities)

    def can_continue_turn(
        self,
        entity: Entity,
        context: TurnContext,
    ) -> bool:
        del entity, context
        return self._state is not RegisteredAIControllerState.CLOSED

    async def request_intent(
        self,
        entity: Entity,
        context: TurnContext,
    ) -> RegisteredAIPendingIntent | ControllerStepResult:
        """Await one provider intent without executing authoritative game code."""
        if self._state is RegisteredAIControllerState.CREATED:
            self.start(self._live_controlled_entities())
        if self._state is RegisteredAIControllerState.CLOSED:
            raise RuntimeError("registered AI controller is closed")
        if entity.uuid not in self.controlled_entity_uuids:
            raise ValueError("actor is outside registered AI assignment")

        self._reset_turn_counters(entity, context)
        prepared = self._pending_intent
        if prepared is not None:
            if (
                prepared.entity_uuid != entity.uuid
                or prepared.turn_key
                != self._current_turn_key(entity, context)
            ):
                raise RuntimeError(
                    "pending provider intent crossed the authoritative "
                    "turn fence"
                )
            return prepared
        if self._turn_decisions >= self.maximum_decisions_per_turn:
            return self._record_limit_feedback(entity)

        pending = self._pending_decision
        if pending is None:
            self._turn_decisions += 1
            self._decision_sequence += 1
            provider_decision_id = (
                self._require_remote_assignment().next_decision_id
            )
            instrumentation_context = AIInstrumentationContext(
                game_id=self.game_id,
                assignment_id=self.assignment_id,
                actor_uuid=str(entity.uuid),
                decision_id=(
                    f"{self.assignment_id}:{self._decision_sequence}"
                ),
                policy=self._require_remote_assignment().policy,
            )
            with self._require_instrumentation().measure(
                context=instrumentation_context,
                phase=AIExecutionPhase.STATE_PROJECTION,
            ):
                state = self._require_projector().project_decision(
                    entity,
                    context,
                    reason=(
                        DecisionEpochReason.TURN_START
                        if self._turn_decisions == 1
                        else DecisionEpochReason.ACTION_COMPLETED
                    ),
                )
            pending = _PendingProviderDecision(
                entity_uuid=entity.uuid,
                turn_key=self._current_turn_key(entity, context),
                sequence=provider_decision_id,
                state=state,
                instrumentation_context=instrumentation_context,
                feedback=tuple(self._pending_feedback),
            )
            self._pending_decision = pending
        elif (
            pending.entity_uuid != entity.uuid
            or pending.turn_key != self._current_turn_key(entity, context)
        ):
            raise RuntimeError(
                "provider retry crossed the authoritative turn fence"
            )

        response = await self._require_remote_assignment().decide(
            state=pending.state.world,
            feedback=pending.feedback,
            decision_id=pending.sequence,
        )
        prepared = RegisteredAIPendingIntent(
            controller_uuid=self.uuid,
            entity_uuid=entity.uuid,
            turn_key=pending.turn_key,
            provider_decision_id=pending.sequence,
            intent=response.intent,
            _state=pending.state,
            _instrumentation_context=pending.instrumentation_context,
        )
        self._pending_decision = None
        self._pending_feedback.clear()
        self._pending_intent = prepared
        return prepared

    def resolve_pending_intent(
        self,
        entity: Entity,
        context: TurnContext,
        pending: RegisteredAIPendingIntent,
    ) -> ControllerStepResult:
        """Synchronously recheck fences and commit one awaited provider intent."""
        if self._state is RegisteredAIControllerState.CLOSED:
            raise RuntimeError("registered AI controller is closed")
        if pending is not self._pending_intent:
            raise RuntimeError(
                "resolution requires the exact pending provider intent"
            )
        if (
            pending.controller_uuid != self.uuid
            or pending.entity_uuid != entity.uuid
            or pending.turn_key != self._current_turn_key(entity, context)
        ):
            raise RuntimeError(
                "pending provider intent crossed the authoritative turn fence"
            )
        if entity.uuid not in self.controlled_entity_uuids:
            raise ValueError("actor is outside registered AI assignment")

        self._pending_intent = None
        try:
            resolution = resolve_policy_intent(
                entity=entity,
                turn_context=context,
                state=pending._state,
                intent=pending.intent,
                instrumentation=self._require_instrumentation(),
                instrumentation_context=(
                    pending._instrumentation_context
                ),
                project_world=lambda: self._require_projector().project_world(
                    entity,
                    context,
                ),
            )
        except Exception as error:
            outcome = (
                NativeAIDecisionOutcome.REJECTED
                if isinstance(error, AIDecisionValidationError)
                else NativeAIDecisionOutcome.FAILED
            )
            feedback = NativeAIDecisionFeedback(
                decision_id=pending._instrumentation_context.decision_id,
                actor_uuid=str(entity.uuid),
                epoch_id=pending._state.epoch_build.epoch.epoch_id,
                row_id=(
                    error.row_id
                    if isinstance(error, AIDecisionValidationError)
                    else None
                ),
                outcome=outcome,
                error_type=type(error).__name__,
                error_message=str(error),
            )
            self._record_feedback(
                pending.provider_decision_id,
                feedback,
            )
            return ControllerStepResult(end_turn=True)

        self._record_feedback(
            pending.provider_decision_id,
            resolution.feedback,
        )
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

    async def close(self) -> None:
        """Close the exact provider fence and local retained state once."""
        if self._state is RegisteredAIControllerState.CLOSED:
            return
        remote = self._require_remote_assignment()
        await remote.close()
        self._state = RegisteredAIControllerState.CLOSED
        self._pending_decision = None
        self._pending_intent = None
        self._pending_feedback.clear()
        self._turn_key = None
        self._turn_decisions = 0
        self._consecutive_canceled_actions = 0

    def _record_feedback(
        self,
        sequence: int,
        feedback: NativeAIDecisionFeedback,
    ) -> None:
        instrumentation = self._require_instrumentation()
        context = AIInstrumentationContext(
            game_id=self.game_id,
            assignment_id=self.assignment_id,
            actor_uuid=feedback.actor_uuid,
            decision_id=feedback.decision_id,
            policy=self._require_remote_assignment().policy,
        )
        with instrumentation.measure(
            context=context,
            phase=AIExecutionPhase.FEEDBACK_REDUCTION,
        ):
            self._feedback.append(feedback)
            self._pending_feedback.append(
                ExternalAIDecisionFeedback(
                    decision_id=sequence,
                    actor_uuid=feedback.actor_uuid,
                    epoch_id=feedback.epoch_id,
                    row_id=feedback.row_id,
                    outcome=feedback.outcome,
                    event_uuid=feedback.event_uuid,
                    outcome_code=feedback.outcome_code,
                    revalidation_reason=feedback.revalidation_reason,
                    error_type=feedback.error_type,
                    error_message=feedback.error_message,
                )
            )
        instrumentation.emit_event(
            context=context,
            event="registered_ai_decision_resolved",
            attributes={
                "outcome": feedback.outcome.value,
                "row_id": feedback.row_id or "",
                "provider_id": self.provider_id,
            },
        )

    def _record_limit_feedback(
        self,
        entity: Entity,
    ) -> ControllerStepResult:
        self._decision_sequence += 1
        feedback = NativeAIDecisionFeedback(
            decision_id=f"{self.assignment_id}:{self._decision_sequence}",
            actor_uuid=str(entity.uuid),
            epoch_id=(
                self.world.current_epoch.epoch_id
                if self.world is not None
                and self.world.current_epoch is not None
                else None
            ),
            row_id=None,
            outcome=NativeAIDecisionOutcome.LIMIT_REACHED,
        )
        self._feedback.append(feedback)
        self._require_instrumentation().emit_event(
            context=AIInstrumentationContext(
                game_id=self.game_id,
                assignment_id=self.assignment_id,
                actor_uuid=str(entity.uuid),
                decision_id=feedback.decision_id,
                policy=self._require_remote_assignment().policy,
            ),
            event="registered_ai_decision_limit_reached",
            attributes={"provider_id": self.provider_id},
        )
        return ControllerStepResult(end_turn=True)

    def _reset_turn_counters(
        self,
        entity: Entity,
        context: TurnContext,
    ) -> None:
        turn_key = self._current_turn_key(entity, context)
        if self._turn_key == turn_key:
            return
        if (
            self._pending_decision is not None
            or self._pending_intent is not None
        ):
            raise RuntimeError(
                "authoritative turn changed with a provider decision or "
                "intent pending"
            )
        self._turn_key = turn_key
        self._turn_decisions = 0
        self._consecutive_canceled_actions = 0

    @staticmethod
    def _current_turn_key(
        entity: Entity,
        context: TurnContext,
    ) -> tuple[str, int, int]:
        return (str(entity.uuid), context.round_number, context.turn_index)

    def _live_controlled_entities(self) -> list[Entity]:
        entities = [
            entity
            for entity_uuid in self.controlled_entity_uuids
            for entity in [Entity.get(entity_uuid)]
            if entity is not None
        ]
        if len(entities) != len(self.controlled_entity_uuids):
            raise ValueError(
                "registered AI assignment has missing controlled entities"
            )
        return entities

    def _require_remote_assignment(self) -> RegisteredAIAssignment:
        if self._remote_assignment is None:
            raise RuntimeError("registered AI assignment is not initialized")
        return self._remote_assignment

    def _require_instrumentation(self) -> AIInstrumentation:
        if self._instrumentation is None:
            raise RuntimeError("registered AI instrumentation is unavailable")
        return self._instrumentation

    def _require_projector(self) -> SubjectiveAIStateProjector:
        if self._projector is None:
            raise RuntimeError("registered AI projector is unavailable")
        return self._projector


__all__ = [
    "RegisteredAIController",
    "RegisteredAIPendingIntent",
    "RegisteredAIControllerState",
]
