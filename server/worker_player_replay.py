"""Materialize terminal player replay bundles from live canonical recordings."""

from __future__ import annotations

from server.game_summary_store import WorkerReplayCapture
from server.player_replay import SubjectivePlayerReplayArchive
from server.player_replay_capture import (
    SubjectiveReplayCaptureError,
    SubjectiveReplayCaptureNotReadyError,
    SubjectiveReplayCaptureStore,
    subjective_replay_capture_store,
)


class WorkerPlayerReplayError(RuntimeError):
    """Recorded player reducer inputs cannot prove exact terminal replay."""


class WorkerPlayerReplayNotReady(WorkerPlayerReplayError):
    """A terminal source exists but a canonical player segment is still open."""


def build_worker_subjective_replays(
    capture: WorkerReplayCapture,
    *,
    replay_capture_store: SubjectiveReplayCaptureStore = (
        subjective_replay_capture_store
    ),
) -> SubjectivePlayerReplayArchive:
    """Freeze every membership recording without reading events or live world state."""

    if capture.source_stream_id != capture.encounter_uuid:
        raise WorkerPlayerReplayError(
            "player replay source stream must be the encounter timeline"
        )
    try:
        archive = replay_capture_store.build_archive(
            game_id=capture.game_id,
            encounter_uuid=capture.encounter_uuid,
            terminal_source_event_cursor=capture.terminal_event_cursor,
            terminal_combat_log_cursor=capture.terminal_combat_log_cursor,
        )
        for bundle in archive.membership_replays:
            terminal_generation = (
                bundle.segments[-1].bootstrap.protocol.generation_id
            )
            if terminal_generation != capture.generation_id:
                raise WorkerPlayerReplayError(
                    "terminal player replay generation does not match worker evidence"
                )
    except SubjectiveReplayCaptureNotReadyError as exc:
        raise WorkerPlayerReplayNotReady(str(exc)) from exc
    except SubjectiveReplayCaptureError as exc:
        raise WorkerPlayerReplayError(
            "recorded player reducer inputs are incomplete or invalid"
        ) from exc
    return archive


__all__ = [
    "WorkerPlayerReplayError",
    "WorkerPlayerReplayNotReady",
    "build_worker_subjective_replays",
]
