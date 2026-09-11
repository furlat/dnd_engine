"""Captured historical headers preserve native metadata during an active turn."""

from dnd.core.base_object import BaseObject, PASSIVE_EVENT_REPLAY
from dnd.core.dice import DiceRoll
from dnd.core.events import EventQueue, EventType
from game.replay import RecordedSequence, encode_sequence
from tests.game.scenarios import movement_with_paralysis


def test_pre_encounter_condition_does_not_acquire_the_capture_turn() -> None:
    # This native feature is applied before encounter startup. The history is
    # captured later, while the mover's actual turn is active.
    source = movement_with_paralysis(17)
    assert source.lineages[0].root.turn_execution_id is not None
    original = {row.event_uuid: row for row in source.initialization.objective_rows}
    conditions = tuple(event for _, event in source.initialization.admitted
                       if event.event_type is EventType.CONDITION_APPLICATION)
    assert conditions and any(original[event.uuid].turn_execution_id is None for event in conditions)
    existing_rolls = dict(DiceRoll._registry)
    recording = RecordedSequence.model_validate_json(
        encode_sequence(source.initialization, source.lineages), context=PASSIVE_EVENT_REPLAY,
    )
    for initialization in (source.initialization, recording.initialization):
        for _, event in initialization.admitted:
            row = original[event.uuid]
            assert (event.uuid, event.lineage_uuid, event.parent_event, event.parent_lineage,
                    event.phase.value, event.turn_execution_id) == (
                row.event_uuid, row.lineage_uuid, row.parent_event, row.parent_lineage,
                row.phase, row.turn_execution_id,
            )
    assert EventQueue.event_cursor() == 0
    assert BaseObject._registry == {}
    assert DiceRoll._registry == existing_rolls
