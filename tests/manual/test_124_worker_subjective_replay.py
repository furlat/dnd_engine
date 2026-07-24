"""Focused terminal materialization of recorded canonical player replay."""

from __future__ import annotations

from collections.abc import Iterator
from uuid import uuid4

import pytest

from dnd.core.events import EventQueue
from dnd.core.gridmap import get_map
from dnd.entity import Entity
from dnd.runtime_reset import reset_engine_runtime
from server.event_stream import event_stream
from server.game_summary_store import WorkerGameSummaryStore
from server.live_replication import create_stream_scene, execute_stream_attack
from server.player_replay_capture import (
    SubjectiveReplayCaptureFrozenError,
    SubjectiveReplayCaptureKey,
    SubjectiveReplayCaptureStore,
)
from server.player_replication.journal import SubjectiveJournalStore
from server.player_replication.runtime import CanonicalSubjectiveReplicationRuntime
from server.replication_perspective import PerspectiveScope
from server.subjective_authority import ResolvedSubjectiveAuthority
from server.timeline_contracts import CombatLogProjection
from server.worker_player_replay import build_worker_subjective_replays


@pytest.fixture(autouse=True)
def clean_runtime() -> Iterator[None]:
    event_stream.stop()
    reset_engine_runtime()
    yield
    event_stream.stop()
    reset_engine_runtime()


def test_worker_freezes_recorded_subjective_inputs_without_event_reconstruction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hosted_game_id = uuid4()
    monkeypatch.setenv("DND_HOSTED_GAME_ID", str(hosted_game_id))
    scene = create_stream_scene()
    summary_store = WorkerGameSummaryStore()
    summary_store.capture_active_encounter(scene.encounter)
    capture_store = SubjectiveReplayCaptureStore()
    runtime = CanonicalSubjectiveReplicationRuntime(
        store=SubjectiveJournalStore(),
        source_journal=event_stream,
        grid_provider=get_map,
        entities_provider=Entity.get_all_entities,
        encounter_provider=lambda: scene.encounter,
        replay_capture_store=capture_store,
    )
    hero_uuid = str(scene.hero.uuid)
    authority = ResolvedSubjectiveAuthority(
        scope=PerspectiveScope(
            session_id="worker-replay-session",
            membership_id="worker-replay-membership",
            authority_epoch=1,
            projection=CombatLogProjection.SUBJECTIVE,
            controlled_entity_uuids=(hero_uuid,),
            observer_entity_uuids=(hero_uuid,),
            active_observer_uuid=hero_uuid,
        ),
        perspective_epoch_id="worker-replay-epoch",
    )
    try:
        context = runtime.bind(authority, encounter=scene.encounter)
        opening_bootstrap = context.bootstrap()
        execute_stream_attack(scene.hero, scene.monster, scene.encounter)
        scene.encounter.end_encounter("worker subjective replay")

        capture = summary_store.get_replay_capture(hosted_game_id)
        assert capture is not None
        capture_key = SubjectiveReplayCaptureKey(
            source_stream_id=opening_bootstrap.protocol.source_stream_id,
            generation_id=opening_bootstrap.protocol.generation_id,
            perspective_epoch_id=(
                opening_bootstrap.perspective.perspective_epoch_id
            ),
        )
        recorder = capture_store.get(capture_key)
        original_segment = recorder.segment
        late_bootstrap = opening_bootstrap.model_copy(
            update={
                "perspective": opening_bootstrap.perspective.model_copy(
                    update={"perspective_epoch_id": "late-replay-epoch"},
                ),
            }
        )
        interleaving_attempts = 0

        def segment_during_late_open_attempt():
            nonlocal interleaving_attempts
            interleaving_attempts += 1
            with pytest.raises(SubjectiveReplayCaptureFrozenError):
                capture_store.open(
                    membership_id="late-membership",
                    runtime_session_id="late-session",
                    bootstrap=late_bootstrap,
                )
            return original_segment()

        monkeypatch.setattr(recorder, "segment", segment_during_late_open_attempt)
        archive = build_worker_subjective_replays(
            capture,
            replay_capture_store=capture_store,
        )
        assert interleaving_attempts == 1
        assert archive.game_id == str(hosted_game_id)
        assert archive.opened_partition_count == 1
        assert len(archive.membership_replays) == 1
        replay = archive.membership_replays[0]
        assert replay.game_id == str(hosted_game_id)
        assert replay.membership_id == "worker-replay-membership"
        assert replay.segments[0].bootstrap == opening_bootstrap
        assert replay.terminal_source_event_cursor == EventQueue.event_cursor()
        assert replay.terminal_combat_log_cursor == len(scene.encounter.combat_log)
        assert replay.segments[-1].through_watermarks.source_event_cursor == (
            capture.terminal_event_cursor
        )
        assert replay.segments[-1].through_watermarks.combat_log_cursor == (
            capture.terminal_combat_log_cursor
        )
        retry = build_worker_subjective_replays(
            capture,
            replay_capture_store=capture_store,
        )
        assert retry is archive
        assert interleaving_attempts == 1

        ended_context = runtime.bind(
            ResolvedSubjectiveAuthority(
                scope=PerspectiveScope(
                    session_id="post-freeze-session",
                    membership_id="post-freeze-membership",
                    authority_epoch=1,
                    projection=CombatLogProjection.SUBJECTIVE,
                    controlled_entity_uuids=(hero_uuid,),
                    observer_entity_uuids=(hero_uuid,),
                    active_observer_uuid=hero_uuid,
                ),
                perspective_epoch_id="post-freeze-epoch",
            ),
            encounter=scene.encounter,
        )
        ended_encounter = ended_context.bootstrap().world.state.encounter
        assert ended_encounter is not None
        assert ended_encounter.state == "ended"
        assert build_worker_subjective_replays(
            capture,
            replay_capture_store=capture_store,
        ) is archive

        empty_archive = build_worker_subjective_replays(
            capture,
            replay_capture_store=SubjectiveReplayCaptureStore(),
        )
        assert empty_archive.opened_partition_count == 0
        assert empty_archive.membership_replays == ()
    finally:
        runtime.clear_all()
        runtime.stop()
