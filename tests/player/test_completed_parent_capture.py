"""Results emitted after a save completes belong to the captured operation."""

from uuid import uuid4

import pytest
from pydantic import TypeAdapter

from dnd.core.base_actions import ActionEvent
from dnd.core.base_object import PASSIVE_EVENT_REPLAY
from dnd.core.events import EventPhase, EventQueue
from dnd.player.capture import (
    CaptureCheckpoint, CompletedLineage, capture_context, capture_lineages,
)
from dnd.runtime_reset import reset_engine_runtime


@pytest.fixture(autouse=True)
def clean_runtime():
    reset_engine_runtime()
    yield
    reset_engine_runtime()


@pytest.mark.parametrize("canceled", [False, True])
def test_completed_result_after_terminal_parent_survives_capture_and_cold_read(canceled):
    actor = uuid4()
    request = ActionEvent(name="Resolved parent", source_entity_uuid=actor)
    parent = request.cancel() if canceled else request.phase_to(EventPhase.COMPLETION)
    child = ActionEvent(name="Actual result", source_entity_uuid=actor,
        parent_event=request.uuid).phase_to(EventPhase.COMPLETION)
    end = EventQueue.event_cursor()
    # A later operation can attach another result to the same native cause.
    later = ActionEvent(name="Later result", source_entity_uuid=actor,
        parent_event=request.uuid).phase_to(EventPhase.COMPLETION)
    roots = (parent,)
    context = capture_context(CaptureCheckpoint(EventQueue.generation_id()), roots, end_cursor=end)
    (retained,) = capture_lineages(roots, observer_uuid=actor, context=context)
    adapter = TypeAdapter(CompletedLineage)
    encoded = adapter.dump_json(retained)
    reset_engine_runtime()
    replay = adapter.validate_json(encoded, context=PASSIVE_EVENT_REPLAY)

    for captured in (retained, replay):
        assert captured.root.children_lineages == [child.lineage_uuid]
        assert {event.uuid for event in captured.events} == {parent.uuid, child.uuid}
        assert captured.end_cursor == end
        assert later.uuid not in captured.root.children_events
        assert later.uuid not in captured.root.lineage_children_events
        result = next(event for event in captured.events if event.uuid == child.uuid)
        assert result.parent_lineage == parent.lineage_uuid
    assert parent.children_lineages == [], "Capture must not rewrite native evidence"


def test_capture_cannot_borrow_a_child_completion_from_after_its_cutoff():
    actor = uuid4()
    parent = ActionEvent(name="Resolved parent", source_entity_uuid=actor).phase_to(EventPhase.COMPLETION)
    child = ActionEvent(name="Unfinished result", source_entity_uuid=actor, parent_event=parent.uuid)
    end = EventQueue.event_cursor()
    child.phase_to(EventPhase.COMPLETION)
    with pytest.raises(ValueError, match="terminal root and child"):
        capture_context(CaptureCheckpoint(EventQueue.generation_id()), (parent,), end_cursor=end)
