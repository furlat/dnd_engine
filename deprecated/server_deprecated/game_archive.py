"""Database-free terminal archive for one in-process game."""

from __future__ import annotations

import os
from pathlib import Path
import tempfile
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from dnd.analytics import GameSummary
from dnd.encounter import Encounter
from server.canonical_json import canonical_json_bytes
from server.event_stream import DndEventStream
from server.game_replay import build_objective_replay
from server.game_summary_store import GameReplayCapture, GameSummaryEvidence
from server.objective_replay import ObjectiveReplayBundle
from server.objective_timeline import (
    build_objective_combat_log_frames,
    build_objective_game_event_frames,
)
from server.timeline_contracts import (
    GameEventFramesResponse,
    ObjectiveCombatLogFramesResponse,
    TimelineProtocolIdentity,
)


class GameArchiveError(RuntimeError):
    """Raised when a complete terminal archive cannot be built or stored."""


class GameArchive(BaseModel):
    """Cold summary, complete objective timeline, and reducer replay."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal[1] = 1
    protocol: TimelineProtocolIdentity = Field(
        default_factory=TimelineProtocolIdentity,
    )
    game_id: str = Field(min_length=1)
    encounter_uuid: str = Field(min_length=1)
    generation_id: str = Field(min_length=1)
    source_event_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_combat_log_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    summary: GameSummary
    events: GameEventFramesResponse
    combat_log_frames: ObjectiveCombatLogFramesResponse
    replay: ObjectiveReplayBundle

    @model_validator(mode="after")
    def _validate_identity(self) -> Self:
        if self.game_id != self.encounter_uuid:
            raise ValueError("single-game archives use the encounter UUID as game id")
        if str(self.summary.encounter_uuid) != self.encounter_uuid:
            raise ValueError("summary belongs to another encounter")
        if self.summary.game_id != self.game_id:
            raise ValueError("summary belongs to another game")
        for value in (self.events, self.combat_log_frames, self.replay):
            if value.source_stream_id != self.encounter_uuid:
                raise ValueError("archive source streams do not match")
            if value.generation_id != self.generation_id:
                raise ValueError("archive generations do not match")
        if self.events.through_cursor != self.replay.terminal_event_cursor:
            raise ValueError("archive event cursor does not match replay")
        if (
            self.combat_log_frames.through_cursor
            != self.replay.terminal_combat_log_cursor
        ):
            raise ValueError("archive combat-log cursor does not match replay")
        return self


def build_game_archive(
    evidence: GameSummaryEvidence,
    capture: GameReplayCapture,
    *,
    encounter: Encounter,
    stream: DndEventStream,
) -> GameArchive:
    """Freeze the complete terminal objective history into a cold archive."""
    if evidence.summary.game_id != capture.game_id:
        raise GameArchiveError("summary and replay capture belong to different games")
    source = stream.capture_objective_source_snapshot(
        encounter,
        from_event_cursor=capture.event_origin_cursor,
        through_event_cursor=capture.terminal_event_cursor,
        from_combat_log_cursor=0,
        through_combat_log_cursor=capture.terminal_combat_log_cursor,
        expected_source_stream_id=capture.source_stream_id,
        expected_generation_id=capture.generation_id,
    )
    logs = build_objective_combat_log_frames(
        source.complete_combat_log_source,
        expected_source_stream_id=capture.source_stream_id,
        expected_generation_id=capture.generation_id,
    )
    events = build_objective_game_event_frames(
        source.event_source_slots,
        source_stream_id=capture.source_stream_id,
        generation_id=capture.generation_id,
        combat_log_source=source.complete_combat_log_source,
        retained_from_cursor=0,
        from_cursor=capture.event_origin_cursor,
        through_cursor=capture.terminal_event_cursor,
        total=capture.terminal_event_cursor,
    )
    replay = build_objective_replay(
        capture,
        encounter=encounter,
        stream=stream,
    )
    return GameArchive(
        game_id=capture.game_id,
        encounter_uuid=capture.encounter_uuid,
        generation_id=capture.generation_id,
        source_event_digest=evidence.source_event_digest,
        source_combat_log_digest=evidence.source_combat_log_digest,
        summary=evidence.summary,
        events=events,
        combat_log_frames=logs,
        replay=replay,
    )


class GameArchiveStore:
    """Atomic filesystem store addressed directly by encounter UUID."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def write(self, archive: GameArchive) -> Path:
        """Atomically replace one game's complete archive."""
        game_id = str(UUID(archive.game_id))
        game_dir = self.root / game_id
        game_dir.mkdir(parents=True, exist_ok=True)
        destination = game_dir / "archive.json"
        payload = canonical_json_bytes(archive.model_dump(mode="json"))
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=".archive-",
            suffix=".tmp",
            dir=game_dir,
        )
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, destination)
        except Exception:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
            raise
        return destination

    def read(self, game_id: str | UUID) -> GameArchive | None:
        """Read and validate one archive without touching engine registries."""
        identifier = str(UUID(str(game_id)))
        path = self.root / identifier / "archive.json"
        if not path.is_file():
            return None
        return GameArchive.model_validate_json(path.read_bytes())


__all__ = [
    "GameArchive",
    "GameArchiveError",
    "GameArchiveStore",
    "build_game_archive",
]
