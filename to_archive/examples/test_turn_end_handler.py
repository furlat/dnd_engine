"""
Test TURN_END handler functionality.

Verifies that handlers can attach to TURN_END at EXECUTION phase,
which is required for features like Rage maintenance.
"""

from uuid import uuid4
from typing import Optional

from dnd.entity import Entity, EntityConfig
from dnd.core.events import (
    Event, EventType, EventPhase,
    EventHandler, Trigger, EventQueue
)


def test_turn_end_handler():
    """Verify handlers can attach to TURN_END at EXECUTION phase."""

    # Clear any existing state
    EventQueue.reset()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()

    # Track if handler was called
    handler_called = []

    def turn_end_processor(event: Event, _source_entity_uuid) -> Optional[Event]:
        """Handler that runs at TURN_END EXECUTION phase."""
        handler_called.append({
            'event_type': event.event_type,
            'phase': event.phase,
            'entity_uuid': getattr(event, 'entity_uuid', None)
        })
        # Mark event as modified to prove we can affect it
        return event.model_copy(update={
            'modified': True,
            'status_message': 'Handler executed at EXECUTION'
        })

    # Create entity
    source_id = uuid4()
    config = EntityConfig(position=(0, 0))
    entity = Entity.create(
        source_entity_uuid=source_id,
        name="Test Entity",
        config=config
    )

    # Create and register TURN_END handler
    # Note: entity.add_event_handler also adds to EventQueue, so only call once
    handler = EventHandler(
        name="Turn End Test Handler",
        source_entity_uuid=entity.uuid,
        trigger_conditions=[
            Trigger(
                event_type=EventType.TURN_END,
                event_phase=EventPhase.EXECUTION
            )
        ],
        event_processor=turn_end_processor
    )
    entity.add_event_handler(handler)

    # Call on_turn_end
    event = entity.on_turn_end(
        encounter_uuid=uuid4(),
        round_number=1,
        turn_index=0
    )

    # Verify handler was called
    print("=== TURN_END Handler Test ===")
    print(f"Handler called: {len(handler_called)} times")

    if handler_called:
        call = handler_called[0]
        print(f"  Event type: {call['event_type']}")
        print(f"  Phase when called: {call['phase']}")
        print(f"  Entity UUID matches: {call['entity_uuid'] == entity.uuid}")

    # Verify final event phase
    print(f"Final event phase: {event.phase}")
    print(f"Event modified: {event.modified}")

    # Assertions
    assert len(handler_called) == 1, f"Handler should be called once, was called {len(handler_called)} times"
    assert handler_called[0]['phase'] == EventPhase.EXECUTION, f"Handler should run at EXECUTION, ran at {handler_called[0]['phase']}"
    assert handler_called[0]['event_type'] == EventType.TURN_END, "Handler should receive TURN_END event"
    assert event.phase == EventPhase.COMPLETION, "Final event should be at COMPLETION"

    print("\n=== TURN_END Handler Test PASSED ===")

    # Cleanup
    EventQueue.reset()


def test_turn_end_phases_progress():
    """Verify TURN_END event progresses through all phases."""

    EventQueue.reset()
    Entity._entity_registry.clear()
    Entity._entity_by_position.clear()

    # Track phases seen
    phases_seen = []

    def phase_tracker(event: Event, _source_entity_uuid) -> Optional[Event]:
        phases_seen.append(event.phase)
        return None  # Don't modify

    # Create entity
    source_id = uuid4()
    config = EntityConfig(position=(0, 0))
    entity = Entity.create(
        source_entity_uuid=source_id,
        name="Phase Tracker Entity",
        config=config
    )

    # Add handlers for each phase
    for phase in [EventPhase.DECLARATION, EventPhase.EXECUTION, EventPhase.EFFECT, EventPhase.COMPLETION]:
        handler = EventHandler(
            name=f"Phase {phase.value} Tracker",
            source_entity_uuid=entity.uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.TURN_END,
                    event_phase=phase
                )
            ],
            event_processor=phase_tracker
        )
        EventQueue.add_event_handler(handler)

    # Call on_turn_end
    _event = entity.on_turn_end()

    print("\n=== TURN_END Phase Progression Test ===")
    print(f"Phases seen by handlers: {[p.value for p in phases_seen]}")

    # Verify phases were visited (COMPLETION is skipped by design in EventQueue)
    # From EventQueue.register: "If no listeners or event is already in completion phase, return as is"
    expected_phases = [EventPhase.DECLARATION, EventPhase.EXECUTION, EventPhase.EFFECT]

    for expected in expected_phases:
        if expected in phases_seen:
            print(f"  ✓ {expected.value} phase reached")
        else:
            print(f"  ✗ {expected.value} phase NOT reached")

    # Note: COMPLETION phase skips handlers by design
    print(f"  (COMPLETION phase skips handlers by design)")

    assert EventPhase.DECLARATION in phases_seen, "DECLARATION phase should be reached"
    assert EventPhase.EXECUTION in phases_seen, "EXECUTION phase should be reached"
    assert EventPhase.EFFECT in phases_seen, "EFFECT phase should be reached"

    print("\n=== TURN_END Phase Progression Test PASSED ===")

    EventQueue.reset()


if __name__ == "__main__":
    test_turn_end_handler()
    test_turn_end_phases_progress()
    print("\n" + "=" * 50)
    print("ALL TURN_END HANDLER TESTS PASSED")
    print("=" * 50)
