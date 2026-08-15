"""Focused materialization of one terminal objective replay."""

from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest

from dnd.core.events import EventQueue
from dnd.runtime_reset import reset_engine_runtime
from server.event_stream import event_stream
from server.game_archive import GameArchiveStore, build_game_archive
from server.game_summary_store import GameSummaryStore
from tests.manual.live_replication_support import create_stream_scene, execute_stream_attack
from server.game_replay import build_objective_replay


@pytest.fixture(autouse=True)
def clean_runtime() -> Iterator[None]:
    event_stream.stop()
    reset_engine_runtime()
    yield
    event_stream.stop()
    reset_engine_runtime()


def test_terminal_capture_materializes_exact_minimal_replay(
    tmp_path: Path,
) -> None:
    """The passive store exposes no replay until exact terminal journals close."""
    scene = create_stream_scene()
    store = GameSummaryStore()
    store.capture_active_encounter(scene.encounter)
    assert store.get_replay_capture(scene.encounter.uuid) is None

    execute_stream_attack(scene.hero, scene.monster, scene.encounter)
    scene.encounter.end_encounter("game replay test")

    capture = store.get_replay_capture(scene.encounter.uuid)
    assert capture is not None
    evidence = store.get_evidence(scene.encounter.uuid)
    assert evidence is not None
    terminal_index, terminal_event = next(
        EventQueue.iter_events_since(capture.terminal_event_cursor - 1)
    )
    assert terminal_index == capture.terminal_event_cursor - 1
    terminal_name = terminal_event.name
    replay = build_objective_replay(
        capture,
        encounter=scene.encounter,
        stream=event_stream,
    )
    replay_bytes = replay.model_dump_json().encode("utf-8")
    assert terminal_event.name == terminal_name

    terminal_event.name = "mutated after terminal objective freeze"
    terminal_event.children_events.append(uuid4())
    repeated = build_objective_replay(
        capture,
        encounter=scene.encounter,
        stream=event_stream,
    )

    assert replay.game_id == str(scene.encounter.uuid)
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

    archive = build_game_archive(
        evidence,
        capture,
        encounter=scene.encounter,
        stream=event_stream,
    )
    archive_store = GameArchiveStore(tmp_path)
    archive_store.write(archive)
    restored = archive_store.read(scene.encounter.uuid)

    assert restored is not None
    assert restored.model_dump(mode="json") == archive.model_dump(mode="json")
    assert restored.summary == evidence.summary
    assert restored.events.from_cursor == capture.event_origin_cursor
    assert restored.events.through_cursor == capture.terminal_event_cursor
    assert len(restored.events.frames) > len(restored.replay.events)
    assert {
        frame.event.model_dump(mode="json")["phase"]
        for frame in restored.events.frames
    } >= {"declaration", "completion"}
