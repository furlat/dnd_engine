"""Encounter controller backed by one in-process native AI assignment."""

from __future__ import annotations

from typing import ClassVar
from uuid import UUID

from pydantic import Field, PrivateAttr

from dnd.ai.instrumentation import AIInstrumentation
from dnd.ai.policies.basic import (
    BASIC_POLICY_ID,
    CanonicalPolicyRegistry,
)
from dnd.ai.runtime.assignment import NativeAIAssignment
from dnd.controller import (
    Controller,
    ControllerExecutionMode,
    ControllerStepResult,
    TurnContext,
)
from dnd.entity import Entity


class NativeAIController(Controller):
    """Autonomous controller using a logic-only policy in the server process."""

    _execution_mode: ClassVar[ControllerExecutionMode] = (
        ControllerExecutionMode.AUTONOMOUS
    )

    name: str = Field(default="Native AI", description="Display controller name.")
    controller_type: str = Field(
        default="native_ai",
        description="Stable native in-process controller identity.",
    )
    game_id: str = Field(description="Game identity used for diagnostics.")
    assignment_id: str = Field(description="Stable side assignment identity.")
    controlled_entity_uuids: tuple[UUID, ...] = Field(
        description="Entities sharing one policy and memory assignment."
    )
    policy_id: str = Field(default=BASIC_POLICY_ID)
    maximum_decisions_per_turn: int | None = Field(default=None, ge=1)

    _policy_registry: CanonicalPolicyRegistry | None = PrivateAttr(default=None)
    _instrumentation: AIInstrumentation | None = PrivateAttr(default=None)
    _assignment: NativeAIAssignment | None = PrivateAttr(default=None)

    @classmethod
    def create(
        cls,
        *,
        source_entity_uuid: UUID,
        game_id: str,
        assignment_id: str,
        controlled_entity_uuids: tuple[UUID, ...],
        registry: CanonicalPolicyRegistry,
        policy_id: str = BASIC_POLICY_ID,
        instrumentation: AIInstrumentation | None = None,
        maximum_decisions_per_turn: int | None = None,
    ) -> "NativeAIController":
        """Create one side-owned native controller with fresh live state."""
        controller = cls(
            source_entity_uuid=source_entity_uuid,
            game_id=game_id,
            assignment_id=assignment_id,
            controlled_entity_uuids=controlled_entity_uuids,
            policy_id=policy_id,
            maximum_decisions_per_turn=maximum_decisions_per_turn,
        )
        controller._policy_registry = registry
        controller._instrumentation = instrumentation or AIInstrumentation()
        controller._assignment = controller._new_assignment()
        return controller

    @property
    def assignment(self) -> NativeAIAssignment:
        """Return the retained assignment created by explicit composition."""
        return self._ensure_assignment()

    @property
    def instrumentation(self) -> AIInstrumentation:
        """Return core-owned instrumentation used by this assignment."""
        self._ensure_assignment()
        instrumentation = self._instrumentation
        if instrumentation is None:
            raise RuntimeError("native AI instrumentation is not initialized")
        return instrumentation

    def start(self, entities: list[Entity]) -> None:
        """Start assignment ownership explicitly and idempotently."""
        self._ensure_assignment().start(entities)

    def close(self) -> None:
        """Close assignment ownership idempotently."""
        assignment = self._assignment
        if assignment is not None:
            assignment.close()

    def on_encounter_start(self, entities: list[Entity]) -> None:
        """Start after the encounter has committed controller ownership."""
        self.start(entities)

    def on_encounter_end(self, entities: list[Entity]) -> None:
        """Tear down assignment-local policy, memory, and projection state."""
        del entities
        self.close()

    def execute_next_action(
        self,
        entity: Entity,
        context: TurnContext,
    ) -> ControllerStepResult:
        """Delegate the full execution pipeline to the assignment runtime."""
        return self._ensure_assignment().execute_next_action(entity, context)

    def can_continue_turn(self, entity: Entity, context: TurnContext) -> bool:
        """Let the assignment's bounded decision loop choose when to stop."""
        del entity, context
        return True

    def _ensure_assignment(self) -> NativeAIAssignment:
        assignment = self._assignment
        if assignment is None:
            raise RuntimeError(
                "native AI controller must be created through explicit "
                "policy composition",
            )
        return assignment

    def _new_assignment(self) -> NativeAIAssignment:
        if self._policy_registry is None or self._instrumentation is None:
            raise RuntimeError("native AI controller runtime is not initialized")
        return NativeAIAssignment(
            game_id=self.game_id,
            assignment_id=self.assignment_id,
            controlled_entity_uuids=self.controlled_entity_uuids,
            policy_id=self.policy_id,
            registry=self._policy_registry,
            instrumentation=self._instrumentation,
            maximum_decisions_per_turn=self.maximum_decisions_per_turn,
        )
