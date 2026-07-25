"""Exact encounter boundaries for registered asynchronous AI providers."""

from __future__ import annotations

from collections.abc import Sequence
from typing import ClassVar
from uuid import uuid4

import pytest
from pydantic import Field, PrivateAttr

from dnd.controller import (
    Controller,
    ControllerExecutionMode,
    ControllerStepResult,
    HumanController,
    TurnContext,
)
from dnd.core.events import Event, EventQueue, EventType
from dnd.encounter import TurnState
from dnd.entity import Entity
from dnd.scenarios.controller_catalogue import (
    create_controller_pair,
    reset_controller_catalogue_state,
    start_ordered_controller_encounter,
)


class _DeferredTestController(Controller):
    _execution_mode: ClassVar[ControllerExecutionMode] = (
        ControllerExecutionMode.DEFERRED_AUTONOMOUS
    )
    _external_boundary_status: ClassVar[str] = "waiting_for_ai_provider"

    name: str = Field(default="Deferred test controller")
    controller_type: str = Field(default="registered_ai")

    def can_continue_turn(
        self,
        entity: Entity,
        context: TurnContext,
    ) -> bool:
        del entity, context
        return True


class _TwoDecisionController(Controller):
    name: str = Field(default="Two decision controller")
    controller_type: str = Field(default="two_decisions")

    _calls: int = PrivateAttr(default=0)

    @property
    def calls(self) -> int:
        return self._calls

    def execute_next_action(
        self,
        entity: Entity,
        context: TurnContext,
    ) -> ControllerStepResult:
        del entity, context
        self._calls += 1
        return ControllerStepResult(end_turn=self._calls >= 2)


def _scene():
    reset_controller_catalogue_state()
    hero, monster = create_controller_pair()
    controller = _DeferredTestController(source_entity_uuid=monster.uuid)
    encounter = start_ordered_controller_encounter(
        hero,
        monster,
        HumanController(source_entity_uuid=hero.uuid),
        controller,
        first_actor=monster,
    )
    return hero, monster, controller, encounter


def test_deferred_step_requires_exact_actor_and_controller_fences() -> None:
    """A response cannot commit after turn ownership changes."""
    _, monster, controller, encounter = _scene()

    waiting = encounter.advance_one_controller_boundary()

    assert waiting.status == "waiting_for_ai_provider"
    assert waiting.entity_uuid == monster.uuid
    assert encounter.turn_state is TurnState.IN_PROGRESS
    context = encounter.build_current_turn_context()
    assert context.entity_uuid == monster.uuid

    with pytest.raises(ValueError, match="actor fence changed"):
        encounter.resolve_deferred_controller_step(
            entity_uuid=uuid4(),
            controller_uuid=controller.uuid,
            step=ControllerStepResult(end_turn=True),
        )
    with pytest.raises(ValueError, match="ownership fence changed"):
        encounter.resolve_deferred_controller_step(
            entity_uuid=monster.uuid,
            controller_uuid=uuid4(),
            step=ControllerStepResult(end_turn=True),
        )

    assert encounter.get_current_entity() is monster
    assert encounter.turn_state is TurnState.IN_PROGRESS


def test_deferred_controller_can_resolve_multiple_steps_then_end_turn() -> None:
    """The server may await between decisions without duplicating a turn."""
    hero, monster, controller, encounter = _scene()
    assert encounter.advance_one_controller_boundary().status == (
        "waiting_for_ai_provider"
    )

    first = encounter.resolve_deferred_controller_step(
        entity_uuid=monster.uuid,
        controller_uuid=controller.uuid,
        step=ControllerStepResult(),
    )

    assert first.status == "deferred_action_completed"
    assert encounter.get_current_entity() is monster
    assert encounter.turn_state is TurnState.IN_PROGRESS
    assert encounter.combatants[monster.uuid].turn_count == 0

    finished = encounter.resolve_deferred_controller_step(
        entity_uuid=monster.uuid,
        controller_uuid=controller.uuid,
        step=ControllerStepResult(end_turn=True),
    )

    assert finished.status == "advanced_autonomous"
    assert encounter.combatants[monster.uuid].turn_count == 1
    assert encounter.turn_state is TurnState.NOT_STARTED
    waiting_for_human = encounter.advance_one_controller_boundary()
    assert waiting_for_human.status == "waiting_for_human"
    assert waiting_for_human.entity_uuid == hero.uuid
    assert encounter.turn_state is TurnState.IN_PROGRESS


def test_action_boundary_yields_between_native_policy_decisions() -> None:
    """Server scheduling can interleave HTTP/SSE without changing turn flow."""
    reset_controller_catalogue_state()
    hero, monster = create_controller_pair()
    controller = _TwoDecisionController(source_entity_uuid=monster.uuid)
    encounter = start_ordered_controller_encounter(
        hero,
        monster,
        HumanController(source_entity_uuid=hero.uuid),
        controller,
        first_actor=monster,
    )

    first = encounter.advance_one_controller_action_boundary()

    assert first.status == "autonomous_action_completed"
    assert controller.calls == 1
    assert encounter.get_current_entity() is monster
    assert encounter.combatants[monster.uuid].turn_count == 0
    assert encounter.turn_state is TurnState.IN_PROGRESS

    second = encounter.advance_one_controller_action_boundary()

    assert second.status == "advanced_autonomous"
    assert controller.calls == 2
    assert encounter.combatants[monster.uuid].turn_count == 1
    assert encounter.turn_state is TurnState.NOT_STARTED

    reset_controller_catalogue_state()
    hero, monster = create_controller_pair()
    complete_controller = _TwoDecisionController(
        source_entity_uuid=monster.uuid
    )
    complete_encounter = start_ordered_controller_encounter(
        hero,
        monster,
        HumanController(source_entity_uuid=hero.uuid),
        complete_controller,
        first_actor=monster,
    )
    complete = complete_encounter.advance_one_controller_boundary()

    assert complete.status == "advanced_autonomous"
    assert complete_controller.calls == 2
    assert complete_encounter.combatants[monster.uuid].turn_count == 1


def test_controller_action_boundary_projects_turn_lifecycle_once() -> None:
    """One end-turn decision cannot trigger a world projection per child event."""
    reset_controller_catalogue_state()
    hero, monster = create_controller_pair()
    controller = _TwoDecisionController(source_entity_uuid=monster.uuid)
    encounter = start_ordered_controller_encounter(
        hero,
        monster,
        HumanController(source_entity_uuid=hero.uuid),
        controller,
        first_actor=monster,
    )
    batches: list[tuple[Event, ...]] = []

    def capture(events: Sequence[Event]) -> None:
        batches.append(tuple(events))

    EventQueue.add_on_event_batch_callback(capture)
    try:
        assert encounter.advance_one_controller_action_boundary().status == (
            "autonomous_action_completed"
        )
        batches.clear()

        assert encounter.advance_one_controller_action_boundary().status == (
            "advanced_autonomous"
        )
    finally:
        EventQueue.remove_on_event_batch_callback(capture)

    assert len(batches) == 1
    assert any(
        event.event_type is EventType.TURN_END
        for event in batches[0]
    )
