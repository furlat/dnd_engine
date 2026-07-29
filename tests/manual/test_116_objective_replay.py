"""Focused contract for the minimal ended-game objective replay artifact."""

from bisect import bisect_right
from collections.abc import Iterator
from hashlib import sha256
import json

import pytest
from pydantic import ValidationError

from dnd.core.events import EventQueue
from dnd.runtime_reset import reset_engine_runtime
from server.event_stream import event_stream
from tests.manual.live_replication_support import (
    create_stream_scene,
    execute_stream_attack,
)
from server.objective_replay import (
    OBJECTIVE_REPLAY_CONTRACT_HASH,
    OBJECTIVE_REPLAY_CONTRACT_VERSION,
    ObjectiveReplayBundle,
    ObjectiveReplaySeed,
    objective_replay_contract_summary,
    objective_replay_wire_schema,
)
from server.objective_state import build_current_objective_world
from server.objective_timeline import (
    build_objective_combat_log_frames,
    build_objective_game_event_frames,
    select_completion_frames_for_replay,
)


@pytest.fixture(autouse=True)
def clean_runtime() -> Iterator[None]:
    event_stream.stop()
    reset_engine_runtime()
    event_stream.ensure_attached()
    yield
    event_stream.stop()
    reset_engine_runtime()


def _completed_replay() -> tuple[ObjectiveReplayBundle, tuple]:
    scene = create_stream_scene()
    seed_event_cursor = EventQueue.event_cursor()
    seed_world = build_current_objective_world(encounter=scene.encounter)

    execute_stream_attack(scene.hero, scene.monster, scene.encounter)
    terminal = scene.encounter.end_encounter(reason="Replay contract test")
    terminal_index = EventQueue.get_event_index(terminal.uuid)
    assert terminal_index is not None
    terminal_event_cursor = terminal_index + 1

    generation_id = str(EventQueue.generation_id())
    source_stream_id = str(scene.encounter.uuid)
    source = event_stream.capture_objective_source_snapshot(
        scene.encounter,
        from_event_cursor=seed_event_cursor,
        through_event_cursor=terminal_event_cursor,
        from_combat_log_cursor=0,
        through_combat_log_cursor=len(scene.encounter.combat_log),
        expected_source_stream_id=source_stream_id,
        expected_generation_id=generation_id,
    )
    source_logs = source.complete_combat_log_source
    objective_logs = build_objective_combat_log_frames(source_logs)
    seed_log_cursor = bisect_right(
        [frame.event_cursor for frame in objective_logs.frames],
        seed_event_cursor,
    )
    diagnostics = build_objective_game_event_frames(
        source.event_source_slots,
        source_stream_id=source_stream_id,
        generation_id=generation_id,
        combat_log_source=source_logs,
        retained_from_cursor=0,
        from_cursor=seed_event_cursor,
        through_cursor=terminal_event_cursor,
        total=terminal_event_cursor,
    )
    completions = select_completion_frames_for_replay(diagnostics)
    bundle = ObjectiveReplayBundle(
        game_id="game-replay-1",
        encounter_uuid=source_stream_id,
        source_stream_id=source_stream_id,
        generation_id=generation_id,
        seed=ObjectiveReplaySeed(
            event_cursor=seed_event_cursor,
            combat_log_cursor=seed_log_cursor,
            world=seed_world,
        ),
        terminal_event_cursor=terminal_event_cursor,
        terminal_combat_log_cursor=objective_logs.total,
        events=completions,
        combat_log_frames=objective_logs,
    )
    return bundle, diagnostics.frames


def test_objective_replay_round_trips_only_first_play_reducer_inputs() -> None:
    bundle, _ = _completed_replay()

    restored = ObjectiveReplayBundle.model_validate_json(bundle.model_dump_json())
    payload = restored.model_dump(mode="json")

    assert payload == bundle.model_dump(mode="json")
    assert restored.replay_contract_version == OBJECTIVE_REPLAY_CONTRACT_VERSION
    assert restored.replay_contract_hash == OBJECTIVE_REPLAY_CONTRACT_HASH
    assert objective_replay_contract_summary() == {
        "replay_contract_version": OBJECTIVE_REPLAY_CONTRACT_VERSION,
        "replay_contract_hash": OBJECTIVE_REPLAY_CONTRACT_HASH,
    }
    assert restored.seed.world.equipment_by_entity
    assert all(frame.event.model_dump(mode="json")["phase"] == "completion" for frame in restored.events)
    assert restored.events[-1].event.model_dump(mode="json")["event_type"] == "encounter_end"
    assert all(frame.entry is not None for frame in restored.combat_log_frames.frames)
    assert set(payload) == {
        "replay_contract_version",
        "replay_contract_hash",
        "protocol",
        "game_id",
        "encounter_uuid",
        "source_stream_id",
        "generation_id",
        "seed",
        "terminal_event_cursor",
        "terminal_combat_log_cursor",
        "events",
        "combat_log_frames",
    }
    assert "terminal_state" not in payload
    assert "commands" not in payload
    assert "session" not in payload
    assert "available_actions" not in payload


def test_objective_replay_hash_authenticates_the_transitive_wire_schema() -> None:
    schema = objective_replay_wire_schema()
    canonical = json.dumps(schema, sort_keys=True, separators=(",", ":")).encode()

    assert sha256(canonical).hexdigest() == OBJECTIVE_REPLAY_CONTRACT_HASH
    bundle_schema = schema["bundle"]
    assert isinstance(bundle_schema, dict)
    definitions = bundle_schema["$defs"]
    assert "ObjectiveCombatLogFramesResponse" in definitions
    assert "ReplicatedWorld" in definitions


def test_objective_replay_rejects_a_source_namespace_other_than_the_encounter() -> None:
    bundle, _ = _completed_replay()
    payload = bundle.model_dump(mode="json")
    payload["source_stream_id"] = "other-source"
    payload["combat_log_frames"]["source_stream_id"] = "other-source"
    for frame in payload["combat_log_frames"]["frames"]:
        frame["source_stream_id"] = "other-source"
    for frame in payload["events"]:
        frame["source_stream_id"] = "other-source"

    with pytest.raises(ValidationError, match="source stream must equal"):
        ObjectiveReplayBundle.model_validate(payload)


def test_objective_replay_rejects_noncompletion_source_frames() -> None:
    bundle, diagnostics_frames = _completed_replay()
    noncompletion = next(
        frame
        for frame in diagnostics_frames
        if frame.event.model_dump(mode="json")["phase"] != "completion"
    )
    payload = bundle.model_dump(mode="json")
    payload["events"] = [
        noncompletion.model_dump(mode="json"),
        *payload["events"],
    ]

    with pytest.raises(ValidationError, match="only completion events"):
        ObjectiveReplayBundle.model_validate(payload)


def test_objective_replay_rejects_log_barrier_drift() -> None:
    bundle, _ = _completed_replay()
    payload = bundle.model_dump(mode="json")
    payload["seed"]["combat_log_cursor"] = payload["terminal_combat_log_cursor"] + 1

    with pytest.raises(ValidationError, match="seed log cursor exceeds"):
        ObjectiveReplayBundle.model_validate(payload)
