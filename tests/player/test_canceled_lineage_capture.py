"""A canceled action still owns its already-completed causal children."""

from uuid import uuid4

from dnd.core.base_actions import ActionEvent
from dnd.core.events import EventPhase, EventQueue
from dnd.player.capture import capture_lineage, lineage_branch
from dnd.runtime_reset import reset_engine_runtime


def test_canceled_parent_retains_completed_child_in_closed_lineage():
    reset_engine_runtime()
    try:
        actor = uuid4()
        parent = ActionEvent(name="Interrupted action", source_entity_uuid=actor)
        child = ActionEvent(name="Completed response", source_entity_uuid=actor,
            parent_event=parent.uuid).phase_to(EventPhase.COMPLETION)
        canceled = parent.cancel()
        cursor = EventQueue.event_cursor()

        retained = capture_lineage(canceled, observer_uuid=actor)
        branch = lineage_branch(retained, retained.root)

        assert retained.root.canceled
        assert retained.root.children_lineages == [child.lineage_uuid]
        assert {event.uuid for event in branch.events} == {canceled.uuid, child.uuid}
        retained_child = next(event for event in branch.events if event.uuid == child.uuid)
        assert retained_child.parent_lineage == retained.root.lineage_uuid
        assert retained_child.phase is EventPhase.COMPLETION
        # Retention normalizes its own header without rewriting native evidence.
        assert canceled.children_lineages == []
        assert EventQueue.event_cursor() == cursor
    finally:
        reset_engine_runtime()
