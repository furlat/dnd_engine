"""Step movement freezes event-time position evidence for its combat log."""

from uuid import uuid4

from dnd.core.combat_log import position_evidence_key
from dnd.core.events import (
    EventPhase,
    StepMovementEvent,
)


def test_step_completion_freezes_pre_and_post_position_evidence_for_logs() -> None:
    """Effect and completion grants survive on the completion event and its log."""
    mover = uuid4()
    observer = uuid4()
    entity_key = str(mover)
    observer_key = str(observer)
    effect = StepMovementEvent(
        source_entity_uuid=mover,
        from_position=(7, 7),
        to_position=(8, 7),
        path_index=1,
        total_path_length=2,
        committed=True,
        phase=EventPhase.EFFECT,
        located_entity_observer_uuids={entity_key: {observer_key}},
        use_register=False,
    )

    completion = effect.phase_to(
        EventPhase.COMPLETION,
        located_entity_observer_uuids={entity_key: {observer_key}},
    )

    expected = {
        position_evidence_key((7, 7)): {observer_key},
        position_evidence_key((8, 7)): {observer_key},
    }
    assert completion.located_position_observer_uuids == expected
    assert completion.combat_log is not None
    assert completion.combat_log.located_position_observer_uuids == expected
