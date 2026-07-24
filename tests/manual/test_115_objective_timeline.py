"""Focused checks for the hot-to-cold objective timeline adapter."""

from collections.abc import Iterator
from uuid import uuid4

import pytest

from dnd.actions import AttackEvent, MovementEvent
from dnd.core.combat_log import CombatLogEntry, CombatLogEntryType
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import Event, EventPhase, EventQueue, EventType
from dnd.core.modifiers import ContextualNumericalModifier, NumericalModifier
from dnd.core.values import ModifiableValue
from server.combat_log_source import CombatLogSourceSlot, CombatLogSourceWindow
from server.event_contract import serialize_event
from server.objective_timeline import (
    OBJECTIVE_PERSPECTIVE_EPOCH_ID,
    ObjectiveEventSourceSlot,
    ObjectiveTimelineError,
    build_objective_combat_log_frames,
    build_objective_game_event_frame,
    build_objective_game_event_frame_from_source,
    build_objective_game_event_frames,
    exact_combat_log_barrier,
    freeze_objective_event_source_slot,
    select_completion_frames_for_replay,
)
from server.timeline_contracts import (
    CombatLogProjection,
    GameEventFrame,
    GameEventFramesResponse,
)


SOURCE_STREAM_ID = "encounter-objective-1"


@pytest.fixture(autouse=True)
def clean_event_queue() -> Iterator[None]:
    EventQueue.reset()
    yield
    EventQueue.reset()


def _entry(label: str, *, child: CombatLogEntry | None = None) -> CombatLogEntry:
    return CombatLogEntry(
        entry_type=CombatLogEntryType.ACTION,
        source_name="Archivist",
        source_uuid="source-1",
        compact=label,
        verbose=label,
        detailed=label,
        sub_entries=[] if child is None else [child],
    )


def _source_window(
    *,
    generation_id: str,
    through_cursor: int = 3,
    total: int = 3,
) -> CombatLogSourceWindow:
    child = _entry("nested damage")
    entries = (
        _entry("parent attack", child=child),
        _entry("condition applied"),
        _entry("turn ended"),
    )
    causal_event_cursors = (2, 2, 4)
    slots = tuple(
        CombatLogSourceSlot(
            source_stream_id=SOURCE_STREAM_ID,
            generation_id=generation_id,
            combat_log_cursor=index + 1,
            event_cursor=causal_event_cursors[index],
            entry=entries[index],
        )
        for index in range(through_cursor)
    )
    return CombatLogSourceWindow(
        source_stream_id=SOURCE_STREAM_ID,
        generation_id=generation_id,
        retained_from_cursor=0,
        from_cursor=0,
        through_cursor=through_cursor,
        total=total,
        slots=slots,
    )


def _register_all_phase_records() -> tuple[tuple[int, Event], ...]:
    source_uuid = uuid4()
    Event(
        name="Movement declared",
        source_entity_uuid=source_uuid,
        event_type=EventType.MOVEMENT,
        phase=EventPhase.DECLARATION,
    )
    MovementEvent(
        source_entity_uuid=source_uuid,
        source_entity_name="Scout",
        start_position=(2, 7),
        end_position=(4, 7),
        requested_end_position=(5, 7),
        path=[(2, 7), (3, 7), (4, 7)],
        phase=EventPhase.COMPLETION,
    )
    Event(
        name="Condition effect",
        source_entity_uuid=source_uuid,
        event_type=EventType.CONDITION_APPLICATION,
        phase=EventPhase.EFFECT,
    )
    Event(
        name="Turn completed",
        source_entity_uuid=source_uuid,
        event_type=EventType.TURN_END,
        phase=EventPhase.COMPLETION,
    )
    Event(
        name="Canceled follow-up",
        source_entity_uuid=source_uuid,
        event_type=EventType.BASE_ACTION,
        phase=EventPhase.CANCEL,
        canceled=True,
        canceled_from_phase=EventPhase.EXECUTION,
    )
    return tuple(EventQueue.iter_events_since(0))


def _freeze_records(
    records: tuple[tuple[int, Event], ...],
    *,
    logs: CombatLogSourceWindow,
) -> tuple[ObjectiveEventSourceSlot, ...]:
    """Freeze raw queue records once at their exact causal-log barriers."""
    return tuple(
        freeze_objective_event_source_slot(
            record,
            combat_log_cursor=exact_combat_log_barrier(
                record[0] + 1,
                logs,
                source_stream_id=logs.source_stream_id,
                generation_id=logs.generation_id,
            ),
        )
        for record in records
    )


def test_objective_log_frames_are_stable_non_null_and_deep_copied() -> None:
    generation_id = str(EventQueue.generation_id())
    source = _source_window(generation_id=generation_id)

    response = build_objective_combat_log_frames(
        source,
        expected_source_stream_id=SOURCE_STREAM_ID,
        expected_generation_id=generation_id,
    )

    assert response.perspective_epoch_id == OBJECTIVE_PERSPECTIVE_EPOCH_ID == "objective"
    assert response.projection is CombatLogProjection.OBJECTIVE
    assert all(frame.entry is not None for frame in response.frames)
    assert response.frames[0].entry is not source.slots[0].entry
    assert response.frames[0].entry is not None
    assert response.frames[0].entry.sub_entries[0] is not source.slots[0].entry.sub_entries[0]

    source.slots[0].entry.sub_entries[0].compact = "mutated hot entry"
    assert response.frames[0].entry.sub_entries[0].compact == "nested damage"
    assert response.model_dump(mode="json")["frames"][0]["entry"]["sub_entries"]


def test_all_phase_diagnostics_are_contiguous_cold_and_use_exact_log_barriers() -> None:
    records = _register_all_phase_records()
    generation_id = str(EventQueue.generation_id())
    logs = _source_window(generation_id=generation_id)
    slots = _freeze_records(records, logs=logs)

    response = build_objective_game_event_frames(
        slots,
        source_stream_id=SOURCE_STREAM_ID,
        generation_id=generation_id,
        combat_log_source=logs,
        retained_from_cursor=0,
        from_cursor=0,
        through_cursor=len(records),
        total=len(records),
    )

    assert [frame.event_index for frame in response.frames] == [0, 1, 2, 3, 4]
    assert [frame.event_cursor for frame in response.frames] == [1, 2, 3, 4, 5]
    assert [frame.combat_log_cursor for frame in response.frames] == [0, 2, 2, 3, 3]
    assert [frame.event.model_dump(mode="json")["phase"] for frame in response.frames] == [
        "declaration",
        "completion",
        "effect",
        "completion",
        "cancel",
    ]

    movement = response.frames[1].event.model_dump(mode="json")
    assert movement["wire_type"] == "dnd.actions.MovementEvent"
    assert movement["path"] == [[2, 7], [3, 7], [4, 7]]
    assert movement["requested_end_position"] == [5, 7]
    assert movement["termination_reason"] == "completed"

    restored = GameEventFramesResponse.model_validate_json(response.model_dump_json())
    assert restored == response
    assert restored.frames[1].event.model_dump(mode="json")["path"] == [
        [2, 7],
        [3, 7],
        [4, 7],
    ]
    assert exact_combat_log_barrier(
        2,
        logs,
        source_stream_id=SOURCE_STREAM_ID,
        generation_id=generation_id,
    ) == 2


def test_one_hot_record_becomes_one_cold_frame() -> None:
    records = _register_all_phase_records()
    generation_id = str(EventQueue.generation_id())
    logs = _source_window(generation_id=generation_id)
    slot = _freeze_records((records[1],), logs=logs)[0]

    frame = build_objective_game_event_frame(
        slot,
        source_stream_id=SOURCE_STREAM_ID,
        generation_id=generation_id,
        combat_log_source=logs,
    )

    restored = GameEventFrame.model_validate_json(frame.model_dump_json())
    assert restored.event_index == 1
    assert restored.event_cursor == 2
    assert restored.combat_log_cursor == 2
    assert restored.event.model_dump(mode="json")["wire_type"] == "dnd.actions.MovementEvent"


def test_freezing_contextual_event_is_once_only_stable_and_nonmutating(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cold source bytes never reevaluate or write into a retained hot event."""
    source_uuid = uuid4()
    target_uuid = uuid4()
    contextual_state = {"bonus": 8}
    attack_bonus = ModifiableValue.create(
        source_entity_uuid=source_uuid,
        target_entity_uuid=target_uuid,
        base_value=3,
        value_name="Contextual attack",
    )

    def current_bonus(
        contextual_source_uuid,
        contextual_target_uuid,
        _context,
    ) -> NumericalModifier:
        return NumericalModifier(
            source_entity_uuid=contextual_source_uuid,
            target_entity_uuid=contextual_target_uuid,
            name="Current contextual bonus",
            value=contextual_state["bonus"],
            use_register=False,
        )

    attack_bonus.self_contextual.add_value_modifier(
        ContextualNumericalModifier(
            source_entity_uuid=source_uuid,
            target_entity_uuid=source_uuid,
            name="Current contextual bonus",
            callable=current_bonus,
            use_register=False,
        )
    )
    event = AttackEvent(
        source_entity_uuid=source_uuid,
        target_entity_uuid=target_uuid,
        source_entity_name="Archivist",
        target_entity_name="Target",
        weapon_slot=WeaponSlot.MELEE_MAIN,
        attack_bonus=attack_bonus,
        phase=EventPhase.COMPLETION,
        use_register=False,
    )
    assert event.attack_bonus is not None
    source_modifier = next(
        iter(event.attack_bonus.self_contextual.value_modifiers.values())
    )
    serialized_events: list[Event] = []

    def count_serialization(candidate: Event):
        serialized_events.append(candidate)
        return serialize_event(candidate)

    monkeypatch.setattr(
        "server.objective_timeline.serialize_event",
        count_serialization,
    )

    slot = freeze_objective_event_source_slot(
        (0, event),
        combat_log_cursor=0,
    )
    first = build_objective_game_event_frame_from_source(
        slot,
        source_stream_id=SOURCE_STREAM_ID,
        generation_id="generation-1",
    )
    first_bytes = first.model_dump_json().encode("utf-8")

    contextual_state["bonus"] = 50
    second = build_objective_game_event_frame_from_source(
        slot,
        source_stream_id=SOURCE_STREAM_ID,
        generation_id="generation-1",
    )

    assert len(serialized_events) == 1
    assert serialized_events[0] is not event
    assert source_modifier.cached_results == {}
    assert second.model_dump_json().encode("utf-8") == first_bytes
    assert first.event.model_dump(mode="json")["attack_bonus"]["score"] == 11


def test_replay_completion_selection_preserves_sparse_objective_coordinates() -> None:
    records = _register_all_phase_records()
    generation_id = str(EventQueue.generation_id())
    logs = _source_window(generation_id=generation_id)
    diagnostics = build_objective_game_event_frames(
        _freeze_records(records, logs=logs),
        source_stream_id=SOURCE_STREAM_ID,
        generation_id=generation_id,
        combat_log_source=logs,
        retained_from_cursor=0,
        from_cursor=0,
        through_cursor=5,
        total=5,
    )

    completion_frames = select_completion_frames_for_replay(
        diagnostics,
        expected_source_stream_id=SOURCE_STREAM_ID,
        expected_generation_id=generation_id,
    )

    assert isinstance(completion_frames, tuple)
    assert [frame.event_index for frame in completion_frames] == [1, 3]
    assert [frame.event_cursor for frame in completion_frames] == [2, 4]
    assert [frame.combat_log_cursor for frame in completion_frames] == [2, 3]
    assert all(
        frame.event.model_dump(mode="json")["phase"] == "completion"
        for frame in completion_frames
    )


def test_adapter_fails_closed_on_mixed_identity_incomplete_logs_and_event_gaps() -> None:
    records = _register_all_phase_records()
    generation_id = str(EventQueue.generation_id())
    complete_logs = _source_window(generation_id=generation_id)

    with pytest.raises(ObjectiveTimelineError, match="generation changed"):
        build_objective_game_event_frame(
            _freeze_records((records[0],), logs=complete_logs)[0],
            source_stream_id=SOURCE_STREAM_ID,
            generation_id="another-generation",
            combat_log_source=complete_logs,
        )

    incomplete_logs = _source_window(
        generation_id=generation_id,
        through_cursor=2,
        total=3,
    )
    with pytest.raises(ObjectiveTimelineError, match="complete captured combat-log window"):
        build_objective_game_event_frame(
            freeze_objective_event_source_slot(
                records[0],
                combat_log_cursor=0,
            ),
            source_stream_id=SOURCE_STREAM_ID,
            generation_id=generation_id,
            combat_log_source=incomplete_logs,
        )

    with pytest.raises(ObjectiveTimelineError, match="contiguous and ordered"):
        build_objective_game_event_frames(
            _freeze_records((records[0], records[2]), logs=complete_logs),
            source_stream_id=SOURCE_STREAM_ID,
            generation_id=generation_id,
            combat_log_source=complete_logs,
            retained_from_cursor=0,
            from_cursor=0,
            through_cursor=2,
            total=5,
        )

    with pytest.raises(ObjectiveTimelineError, match="source stream changed"):
        build_objective_combat_log_frames(
            complete_logs,
            expected_source_stream_id="another-stream",
        )
