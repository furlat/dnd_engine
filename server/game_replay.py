"""Materialize one terminal objective replay from in-process journals."""

from __future__ import annotations

from dnd.core.events import EventQueue
from dnd.encounter import Encounter
from pydantic import ValidationError

from server.combat_log_source import CombatLogSourceError
from server.event_stream import DndEventStream
from server.game_summary_store import GameReplayCapture
from server.objective_replay import ObjectiveReplayBundle
from server.objective_timeline import (
    ObjectiveTimelineError,
    build_objective_combat_log_frames,
    build_objective_game_event_frames,
    select_completion_frames_for_replay,
)


class GameReplayError(RuntimeError):
    """Raised when the live journals cannot prove the captured replay."""


def build_objective_replay(
    capture: GameReplayCapture,
    *,
    encounter: Encounter,
    stream: DndEventStream,
) -> ObjectiveReplayBundle:
    """Freeze exact terminal journals into the minimal cold replay contract."""
    if str(encounter.uuid) != capture.encounter_uuid:
        raise GameReplayError("replay capture belongs to another encounter")
    if capture.source_stream_id != capture.encounter_uuid:
        raise GameReplayError("replay source stream must be the encounter timeline")
    if str(EventQueue.generation_id()) != capture.generation_id:
        raise GameReplayError("event generation changed before replay capture")
    if EventQueue.event_cursor() < capture.terminal_event_cursor:
        raise GameReplayError("terminal event cursor is no longer retained")
    if len(encounter.combat_log) != capture.terminal_combat_log_cursor:
        raise GameReplayError("terminal combat-log cursor changed after capture")

    try:
        source = stream.capture_objective_source_snapshot(
            encounter,
            from_event_cursor=capture.seed.event_cursor,
            through_event_cursor=capture.terminal_event_cursor,
            from_combat_log_cursor=0,
            through_combat_log_cursor=capture.terminal_combat_log_cursor,
            expected_source_stream_id=capture.source_stream_id,
            expected_generation_id=capture.generation_id,
        )
        source_logs = source.complete_combat_log_source
        objective_logs = build_objective_combat_log_frames(
            source_logs,
            expected_source_stream_id=capture.source_stream_id,
            expected_generation_id=capture.generation_id,
        )
        all_phases = build_objective_game_event_frames(
            source.event_source_slots,
            source_stream_id=capture.source_stream_id,
            generation_id=capture.generation_id,
            combat_log_source=source_logs,
            retained_from_cursor=0,
            from_cursor=capture.seed.event_cursor,
            through_cursor=capture.terminal_event_cursor,
            total=capture.terminal_event_cursor,
        )
        return ObjectiveReplayBundle(
            game_id=capture.game_id,
            encounter_uuid=capture.encounter_uuid,
            source_stream_id=capture.source_stream_id,
            generation_id=capture.generation_id,
            seed=capture.seed,
            terminal_event_cursor=capture.terminal_event_cursor,
            terminal_combat_log_cursor=capture.terminal_combat_log_cursor,
            events=select_completion_frames_for_replay(
                all_phases,
                expected_source_stream_id=capture.source_stream_id,
                expected_generation_id=capture.generation_id,
            ),
            combat_log_frames=objective_logs,
        )
    except (CombatLogSourceError, ObjectiveTimelineError, ValidationError) as exc:
        raise GameReplayError("live journals cannot prove an exact replay") from exc


__all__ = ["GameReplayError", "build_objective_replay"]
