"""Focused regressions for causal turn-execution identity."""

import asyncio

from dnd.encounters.controllers import PassController
from dnd.core.events.events_registry import (
    Event,
    EventPhase,
    EventQueue,
    EventType,
)
from tests.manual.controller_test_support import (
    create_controller_pair,
    reset_controller_catalogue_state,
    start_ordered_controller_encounter,
)


def test_event_versions_and_children_inherit_active_turn_execution_id() -> None:
    """Every event in one active causal turn carries the same opaque identity."""
    reset_controller_catalogue_state()
    hero, monster = create_controller_pair()
    encounter = start_ordered_controller_encounter(
        hero,
        monster,
        PassController(source_entity_uuid=hero.uuid),
        PassController(source_entity_uuid=monster.uuid),
        first_actor=hero,
    )

    turn_start = encounter.start_turn()
    assert turn_start is not None
    assert turn_start.turn_execution_id is not None

    parent = Event(
        event_type=EventType.BASE_ACTION,
        source_entity_uuid=hero.uuid,
        target_entity_uuid=monster.uuid,
    )
    execution = parent.phase_to(EventPhase.EXECUTION)
    child = Event(
        event_type=EventType.TAKE_DAMAGE,
        source_entity_uuid=hero.uuid,
        target_entity_uuid=monster.uuid,
        parent_event=execution.uuid,
    )

    assert parent.turn_execution_id == turn_start.turn_execution_id
    assert execution.turn_execution_id == turn_start.turn_execution_id
    assert child.turn_execution_id == turn_start.turn_execution_id


def test_each_actual_turn_gets_a_new_identity_and_reset_clears_context() -> None:
    """Turn identity is not derived from reusable round/index coordinates."""
    reset_controller_catalogue_state()
    hero, monster = create_controller_pair()
    encounter = start_ordered_controller_encounter(
        hero,
        monster,
        PassController(source_entity_uuid=hero.uuid),
        PassController(source_entity_uuid=monster.uuid),
        first_actor=hero,
    )

    first = encounter.start_turn()
    assert first is not None
    first_id = first.turn_execution_id
    assert first_id is not None

    encounter.end_turn()
    second = encounter.next_turn()
    assert second is not None
    assert second.turn_execution_id is not None
    assert second.turn_execution_id != first_id

    EventQueue.reset()
    outside_turn = Event(
        event_type=EventType.BASE_ACTION,
        source_entity_uuid=hero.uuid,
        target_entity_uuid=monster.uuid,
    )
    assert outside_turn.turn_execution_id is None


def test_turn_identity_survives_separate_async_request_contexts() -> None:
    """One server turn keeps its identity across distinct request tasks."""
    reset_controller_catalogue_state()
    hero, monster = create_controller_pair()
    encounter = start_ordered_controller_encounter(
        hero,
        monster,
        PassController(source_entity_uuid=hero.uuid),
        PassController(source_entity_uuid=monster.uuid),
        first_actor=hero,
    )

    async def start_in_request_context() -> Event:
        turn_start = encounter.start_turn()
        assert turn_start is not None
        return turn_start

    turn_start = asyncio.run(start_in_request_context())
    between_requests = Event(
        event_type=EventType.BASE_ACTION,
        source_entity_uuid=hero.uuid,
        target_entity_uuid=monster.uuid,
    )

    async def end_in_request_context() -> None:
        encounter.end_turn()

    asyncio.run(end_in_request_context())

    assert between_requests.turn_execution_id == turn_start.turn_execution_id
    assert encounter.current_turn_execution_id is None
