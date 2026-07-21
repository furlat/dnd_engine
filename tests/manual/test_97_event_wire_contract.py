"""Focused checks for the generated engine-event wire contract."""

from uuid import uuid4

import pytest

from devtools.generate_event_contract import build_manifest
from dnd.actions import JumpEvent, MovementEvent
from dnd.core.events import Event, EventPhase, EventType
from server.api_models import EventHistoryResponse
from server.event_contract import (
    EVENT_CONTRACT,
    EventContractError,
    event_contract_summary,
    serialize_event,
)
from server.event_stream import GameEventPayload


def test_generated_contract_covers_every_semantic_and_concrete_event() -> None:
    """The checked-in manifest equals a fresh scan of the runtime model graph."""
    assert build_manifest() == EVENT_CONTRACT
    assert set(EVENT_CONTRACT["event_types"]) == {
        event_type.value for event_type in EventType
    }
    assert event_contract_summary()["wire_types"] == sorted(EVENT_CONTRACT["event_classes"])


def test_concrete_wire_type_distinguishes_move_jump_and_generic_events() -> None:
    """Shared semantic categories never erase concrete payload identity."""
    source_uuid = uuid4()
    movement = MovementEvent(
        source_entity_uuid=source_uuid,
        start_position=(0, 0),
        end_position=(1, 0),
        path=[(0, 0), (1, 0)],
        phase=EventPhase.COMPLETION,
    )
    jump = JumpEvent(
        source_entity_uuid=source_uuid,
        start_position=(0, 0),
        end_position=(2, 1),
        jump_distance=10,
        path=[(0, 0), (1, 0), (2, 1)],
        phase=EventPhase.COMPLETION,
    )
    generic = Event(
        name="Generic movement notification",
        source_entity_uuid=source_uuid,
        event_type=EventType.MOVEMENT,
        phase=EventPhase.COMPLETION,
    )

    movement_payload = serialize_event(movement)
    jump_payload = serialize_event(jump)
    generic_payload = serialize_event(generic)

    assert movement_payload["event_type"] == jump_payload["event_type"] == "movement"
    assert movement_payload["wire_type"] == "dnd.actions.MovementEvent"
    assert jump_payload["wire_type"] == "dnd.actions.JumpEvent"
    assert generic_payload["wire_type"] == "dnd.core.events.Event"
    assert movement_payload["trajectory"] == "path"
    assert jump_payload["trajectory"] == "direct_arc"


def test_history_and_sse_use_the_identical_event_serializer() -> None:
    """REST history and live SSE envelopes expose byte-equivalent event objects."""
    event = MovementEvent(
        source_entity_uuid=uuid4(),
        start_position=(2, 7),
        end_position=(3, 7),
        path=[(2, 7), (3, 7)],
        phase=EventPhase.COMPLETION,
    )
    history = EventHistoryResponse(
        generation_id="generation-a",
        events=[event],
        count=1,
        total=1,
    ).model_dump(mode="json")
    stream = GameEventPayload(
        generation_id="generation-a",
        event_index=0,
        event_cursor=1,
        combat_log_cursor=0,
        event=event,
    ).model_dump(mode="json")

    assert history["events"][0] == stream["event"] == serialize_event(event)
    assert history["generation_id"] == stream["generation_id"] == "generation-a"
    assert stream["event"]["path"] == [[2, 7], [3, 7]]


def test_unknown_event_subclass_fails_at_the_transport_boundary() -> None:
    """A new event class cannot silently reach clients before regeneration."""

    class UnregisteredEvent(Event):
        pass

    event = UnregisteredEvent(
        name="Unregistered",
        source_entity_uuid=uuid4(),
        event_type=EventType.TRIGGER_EVENT,
        phase=EventPhase.COMPLETION,
    )

    with pytest.raises(EventContractError, match="absent from the generated wire contract"):
        serialize_event(event)
