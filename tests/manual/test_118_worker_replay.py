"""Focused worker materialization of one terminal objective replay."""

from collections.abc import Iterator
from uuid import uuid4

import pytest

from dnd.core.events import EventQueue
from dnd.runtime_reset import reset_engine_runtime
from server.event_stream import event_stream
from server.game_summary_store import WorkerGameSummaryStore
from server.live_replication import create_stream_scene, execute_stream_attack
from server.worker_replay import build_worker_objective_replay


@pytest.fixture(autouse=True)
def clean_runtime() -> Iterator[None]:
    event_stream.stop()
    reset_engine_runtime()
    yield
    event_stream.stop()
    reset_engine_runtime()


def test_terminal_capture_materializes_exact_minimal_replay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The passive store exposes no replay until exact terminal journals close."""
    hosted_game_id = uuid4()
    monkeypatch.setenv("DND_HOSTED_GAME_ID", str(hosted_game_id))
    scene = create_stream_scene()
    store = WorkerGameSummaryStore()
    store.capture_active_encounter(scene.encounter)
    assert store.get_replay_capture(hosted_game_id) is None

    execute_stream_attack(scene.hero, scene.monster, scene.encounter)
    scene.encounter.end_encounter("worker replay test")

    capture = store.get_replay_capture(hosted_game_id)
    assert capture is not None
    terminal_index, terminal_event = next(
        EventQueue.iter_events_since(capture.terminal_event_cursor - 1)
    )
    assert terminal_index == capture.terminal_event_cursor - 1
    terminal_name = terminal_event.name
    replay = build_worker_objective_replay(
        capture,
        encounter=scene.encounter,
        stream=event_stream,
    )
    replay_bytes = replay.model_dump_json().encode("utf-8")
    assert terminal_event.name == terminal_name

    terminal_event.name = "mutated after terminal objective freeze"
    terminal_event.children_events.append(uuid4())
    repeated = build_worker_objective_replay(
        capture,
        encounter=scene.encounter,
        stream=event_stream,
    )

    assert replay.game_id == str(hosted_game_id)
    assert replay.seed.world.equipment_by_entity
    assert replay.events
    assert all(
        frame.event.model_dump(mode="json")["phase"] == "completion"
        for frame in replay.events
    )
    assert replay.events[-1].event.model_dump(mode="json")["event_type"] == "encounter_end"
    assert replay.combat_log_frames.total == len(scene.encounter.combat_log)
    assert replay.terminal_event_cursor == capture.terminal_event_cursor
    assert replay.terminal_combat_log_cursor == capture.terminal_combat_log_cursor
    assert repeated.model_dump_json().encode("utf-8") == replay_bytes
    assert repeated.events[-1].event.model_dump(mode="json")["name"] == terminal_name
