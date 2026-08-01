"""In-memory exact recorder for durable canonical player replay artifacts.

The recorder sits above the live journal.  It retains already-validated player
DTOs by reference during play and performs one full cold-contract validation
when an ended-game bundle is materialized.  It never reads engine events or
reprojects mutable world state.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from threading import RLock
from typing import Optional

from server.player_replay import (
    SubjectivePlayerReplayBundle,
    SubjectivePlayerReplayArchive,
    SubjectiveReplayDelivery,
    SubjectiveReplaySegment,
    SubjectiveReplaySegmentEnd,
    subjective_bootstrap_encounter_ended,
)
from server.player_replication_contract import (
    EncounterPresentationCue,
    EncounterTransition,
    PlayerReplicationWatermarks,
    SubjectiveCombatLogDelivery,
    SubjectiveCombatLogFrame,
    SubjectiveFrameDelivery,
    SubjectiveReplicationBootstrap,
    SubjectiveReplicationFrame,
)


class SubjectiveReplayCaptureError(RuntimeError):
    """A live capture could not preserve exact canonical reducer continuity."""


class SubjectiveReplayCaptureNotReadyError(SubjectiveReplayCaptureError):
    """Terminal capture cannot freeze while a reducer segment remains open."""


class SubjectiveReplayCaptureFrozenError(SubjectiveReplayCaptureError):
    """A terminal source is frozen and cannot accept another partition."""


@dataclass(frozen=True)
class SubjectiveReplayCaptureKey:
    """Complete live partition identity used by the capture registry."""

    source_stream_id: str
    generation_id: str
    perspective_epoch_id: str

class SubjectiveReplayRecorder:
    """Append-only recording of one live subjective journal partition."""

    def __init__(
        self,
        *,
        segment_index: int,
        membership_id: str,
        runtime_session_id: str,
        bootstrap: SubjectiveReplicationBootstrap,
    ) -> None:
        if segment_index < 0:
            raise ValueError("segment_index must be nonnegative")
        if not membership_id:
            raise ValueError("membership_id must not be empty")
        if not runtime_session_id:
            raise ValueError("runtime_session_id must not be empty")
        self.segment_index = segment_index
        self.membership_id = membership_id
        self.runtime_session_id = runtime_session_id
        self.bootstrap = SubjectiveReplicationBootstrap.model_validate_json(
            bootstrap.model_dump_json()
        )
        self.key = SubjectiveReplayCaptureKey(
            source_stream_id=self.bootstrap.protocol.source_stream_id,
            generation_id=self.bootstrap.protocol.generation_id,
            perspective_epoch_id=self.bootstrap.perspective.perspective_epoch_id,
        )
        self._deliveries: list[SubjectiveReplayDelivery] = []
        self._through = self.bootstrap.watermarks
        self._presentation_ids: set[str] = set()
        self._encounter_ended = subjective_bootstrap_encounter_ended(
            self.bootstrap,
        )
        self._end_reason: Optional[SubjectiveReplaySegmentEnd] = None
        self._aborted = False
        self._lock = RLock()

    @property
    def through_watermarks(self) -> PlayerReplicationWatermarks:
        with self._lock:
            return self._through

    @property
    def closed(self) -> bool:
        with self._lock:
            return self._end_reason is not None

    @property
    def encounter_ended(self) -> bool:
        with self._lock:
            return self._encounter_ended

    @property
    def aborted(self) -> bool:
        with self._lock:
            return self._aborted

    def append_frame(
        self,
        frame: SubjectiveReplicationFrame,
    ) -> SubjectiveFrameDelivery:
        """Record one canonical frame after its journal commit."""

        delivery = SubjectiveFrameDelivery(frame=frame)
        with self._lock:
            self._require_open()
            if self._encounter_ended:
                raise SubjectiveReplayCaptureError(
                    "cannot record an observation frame after encounter end"
                )
            if (
                frame.source_stream_id != self.key.source_stream_id
                or frame.generation_id != self.key.generation_id
                or frame.perspective_epoch_id != self.key.perspective_epoch_id
            ):
                raise SubjectiveReplayCaptureError(
                    "observation frame belongs to another replay partition"
                )
            if frame.watermarks.observation_cursor != self._through.observation_cursor + 1:
                raise SubjectiveReplayCaptureError(
                    "replay observation cursor is not contiguous"
                )
            if frame.presentation_from_cursor != self._through.presentation_cursor:
                raise SubjectiveReplayCaptureError(
                    "replay presentation cursor is not contiguous"
                )
            if frame.watermarks.combat_log_cursor != self._through.combat_log_cursor:
                raise SubjectiveReplayCaptureError(
                    "observation frame advanced the replay combat-log cursor"
                )
            if not frame.watermarks.dominates(self._through):
                raise SubjectiveReplayCaptureError("replay observation watermarks moved backwards")
            frame_ids = {cue.presentation_id for cue in frame.presentation}
            if self._presentation_ids & frame_ids:
                raise SubjectiveReplayCaptureError(
                    "replay presentation ID was already recorded"
                )
            self._presentation_ids.update(frame_ids)
            terminal_cues = tuple(
                cue
                for cue in frame.presentation
                if isinstance(cue, EncounterPresentationCue)
                and cue.transition is EncounterTransition.END
            )
            if len(terminal_cues) > 1:
                raise SubjectiveReplayCaptureError(
                    "one replay frame cannot end the encounter twice"
                )
            self._encounter_ended = bool(terminal_cues)
            self._deliveries.append(delivery)
            self._through = frame.watermarks
            return delivery

    def append_combat_log(
        self,
        frame: SubjectiveCombatLogFrame,
        *,
        watermarks: PlayerReplicationWatermarks,
    ) -> SubjectiveCombatLogDelivery:
        """Record one canonical nullable log slot after its journal commit."""

        delivery = SubjectiveCombatLogDelivery(
            watermarks=watermarks,
            frame=frame,
        )
        with self._lock:
            self._require_open()
            if (
                frame.source_stream_id != self.key.source_stream_id
                or frame.generation_id != self.key.generation_id
                or frame.perspective_epoch_id != self.key.perspective_epoch_id
            ):
                raise SubjectiveReplayCaptureError(
                    "combat-log frame belongs to another replay partition"
                )
            if frame.combat_log_cursor != self._through.combat_log_cursor + 1:
                raise SubjectiveReplayCaptureError(
                    "replay combat-log cursor is not contiguous"
                )
            if frame.event_cursor > self._through.source_event_cursor:
                raise SubjectiveReplayCaptureError(
                    "replay combat-log barrier exceeds consumed source events"
                )
            expected = self._through.model_copy(
                update={"combat_log_cursor": frame.combat_log_cursor}
            )
            if watermarks != expected:
                raise SubjectiveReplayCaptureError(
                    "replay combat-log delivery has inconsistent watermarks"
                )
            self._deliveries.append(delivery)
            self._through = watermarks
            return delivery

    def close(
        self,
        reason: SubjectiveReplaySegmentEnd,
    ) -> SubjectiveReplaySegment:
        """Seal this partition at an explicit reducer reset boundary."""

        with self._lock:
            if self._aborted:
                raise SubjectiveReplayCaptureError("replay segment was aborted")
            if self._end_reason is not None and self._end_reason is not reason:
                raise SubjectiveReplayCaptureError(
                    "replay segment was already closed for another reason"
                )
            if (
                reason is SubjectiveReplaySegmentEnd.ENCOUNTER_ENDED
                and not self._encounter_ended
            ):
                raise SubjectiveReplayCaptureError(
                    "cannot close encounter-ended replay without a terminal reducer fact"
                )
            if (
                reason is SubjectiveReplaySegmentEnd.PERSPECTIVE_RETIRED
                and self._encounter_ended
            ):
                raise SubjectiveReplayCaptureError(
                    "terminal replay segment cannot be relabeled perspective-retired"
                )
            self._end_reason = reason
            return self._segment()

    def abort(self) -> None:
        """Make a failed partial capture permanently unpublishable."""

        with self._lock:
            if self._end_reason is not None:
                return
            self._aborted = True
            self._deliveries.clear()
            self._presentation_ids.clear()

    def segment(self) -> SubjectiveReplaySegment:
        """Return the sealed cold segment, rejecting an active capture."""

        with self._lock:
            if self._aborted:
                raise SubjectiveReplayCaptureError("replay segment was aborted")
            if self._end_reason is None:
                raise SubjectiveReplayCaptureError("replay segment is still active")
            return self._segment()

    def _segment(self) -> SubjectiveReplaySegment:
        assert self._end_reason is not None
        return SubjectiveReplaySegment(
            segment_index=self.segment_index,
            membership_id=self.membership_id,
            runtime_session_id=self.runtime_session_id,
            bootstrap=self.bootstrap,
            deliveries=tuple(self._deliveries),
            through_watermarks=self._through,
            end_reason=self._end_reason,
        )

    def _require_open(self) -> None:
        if self._aborted:
            raise SubjectiveReplayCaptureError("replay segment was aborted")
        if self._end_reason is not None:
            raise SubjectiveReplayCaptureError("replay segment is already closed")

class SubjectiveReplayCaptureStore:
    """Process-local registry retaining exact segments until artifact publication."""

    def __init__(self) -> None:
        self._recorders: dict[SubjectiveReplayCaptureKey, SubjectiveReplayRecorder] = {}
        self._membership_indices: dict[tuple[str, str], int] = {}
        self._opened_partition_counts: dict[str, int] = {}
        self._aborted_sources: set[str] = set()
        self._aborted_source_reasons: dict[str, str] = {}
        self._frozen_sources: set[str] = set()
        self._frozen_archives: dict[str, SubjectivePlayerReplayArchive] = {}
        self._source_closed_listeners: list[Callable[[str], None]] = []
        self._lock = RLock()

    def add_source_closed_listener(
        self,
        listener: Callable[[str], None],
    ) -> None:
        """Register one process-lifetime notification for newly sealed segments."""

        with self._lock:
            if listener not in self._source_closed_listeners:
                self._source_closed_listeners.append(listener)

    def remove_source_closed_listener(
        self,
        listener: Callable[[str], None],
    ) -> None:
        """Remove one terminal-ready notification listener."""

        with self._lock:
            if listener in self._source_closed_listeners:
                self._source_closed_listeners.remove(listener)

    def open(
        self,
        *,
        membership_id: str,
        runtime_session_id: str,
        bootstrap: SubjectiveReplicationBootstrap,
    ) -> SubjectiveReplayRecorder:
        """Open one exact partition capture without merging authority epochs."""

        key = SubjectiveReplayCaptureKey(
            source_stream_id=bootstrap.protocol.source_stream_id,
            generation_id=bootstrap.protocol.generation_id,
            perspective_epoch_id=bootstrap.perspective.perspective_epoch_id,
        )
        with self._lock:
            existing = self._recorders.get(key)
            if existing is not None:
                if (
                    existing.membership_id != membership_id
                    or existing.runtime_session_id != runtime_session_id
                    or existing.bootstrap != bootstrap
                ):
                    raise SubjectiveReplayCaptureError(
                        "replay partition identity was reused with different ownership or seed"
                    )
                return existing
            if key.source_stream_id in self._frozen_sources:
                raise SubjectiveReplayCaptureFrozenError(
                    "terminal player replay capture is already frozen"
                )
            index_key = (key.source_stream_id, membership_id)
            segment_index = self._membership_indices.get(index_key, 0)
            recorder = SubjectiveReplayRecorder(
                segment_index=segment_index,
                membership_id=membership_id,
                runtime_session_id=runtime_session_id,
                bootstrap=bootstrap,
            )
            self._recorders[key] = recorder
            self._membership_indices[index_key] = segment_index + 1
            self._opened_partition_counts[key.source_stream_id] = (
                self._opened_partition_counts.get(key.source_stream_id, 0) + 1
            )
            return recorder

    def get(
        self,
        key: SubjectiveReplayCaptureKey,
    ) -> SubjectiveReplayRecorder:
        """Return one exact capture partition."""

        with self._lock:
            recorder = self._recorders.get(key)
            if recorder is None:
                raise SubjectiveReplayCaptureError("subjective replay capture does not exist")
            return recorder

    def close(
        self,
        key: SubjectiveReplayCaptureKey,
        reason: SubjectiveReplaySegmentEnd,
    ) -> SubjectiveReplaySegment:
        """Seal one capture while retaining it for later artifact publication."""

        with self._lock:
            recorder = self._recorders.get(key)
            if recorder is None:
                raise SubjectiveReplayCaptureError(
                    "subjective replay capture does not exist"
                )
            was_closed = recorder.closed
            segment = recorder.close(reason)
            listeners = (
                ()
                if was_closed
                else tuple(self._source_closed_listeners)
            )
        for listener in listeners:
            listener(key.source_stream_id)
        return segment

    def abort(
        self,
        key: SubjectiveReplayCaptureKey,
        recorder: Optional[SubjectiveReplayRecorder] = None,
        *,
        reason: Optional[str] = None,
    ) -> None:
        """Discard one failed provisional or partial capture without publishing it."""

        with self._lock:
            existing = self._recorders.get(key)
            if existing is None or (recorder is not None and existing is not recorder):
                return
            if existing.closed:
                return
            self._recorders.pop(key)
            existing.abort()
            self._aborted_sources.add(key.source_stream_id)
            if reason and key.source_stream_id not in self._aborted_source_reasons:
                self._aborted_source_reasons[key.source_stream_id] = reason
            index_key = (key.source_stream_id, existing.membership_id)
            next_index = self._membership_indices.get(index_key)
            if next_index == existing.segment_index + 1:
                self._membership_indices[index_key] = existing.segment_index

    def build_bundle(
        self,
        *,
        game_id: str,
        encounter_uuid: str,
        membership_id: str,
        terminal_source_event_cursor: int,
        terminal_combat_log_cursor: int,
    ) -> SubjectivePlayerReplayBundle:
        """Materialize one membership's sealed segments without reprojection."""

        with self._lock:
            recorders = tuple(
                recorder
                for key, recorder in self._recorders.items()
                if key.source_stream_id == encounter_uuid
                and recorder.membership_id == membership_id
            )
        if not recorders:
            raise SubjectiveReplayCaptureError(
                "no subjective replay segments exist for this membership"
            )
        try:
            segments = tuple(
                recorder.segment()
                for recorder in sorted(
                    recorders,
                    key=lambda candidate: candidate.segment_index,
                )
            )
            return SubjectivePlayerReplayBundle(
                game_id=game_id,
                encounter_uuid=encounter_uuid,
                membership_id=membership_id,
                terminal_source_event_cursor=terminal_source_event_cursor,
                terminal_combat_log_cursor=terminal_combat_log_cursor,
                segments=segments,
            )
        except ValueError as exc:
            raise SubjectiveReplayCaptureError(
                "recorded subjective inputs do not form an exact ended-game replay: "
                f"{type(exc).__name__}: {exc}"
            ) from exc

    def memberships(self, *, encounter_uuid: str) -> tuple[str, ...]:
        """Return stable membership identities with captured replay segments."""

        with self._lock:
            return tuple(
                sorted(
                    {
                        recorder.membership_id
                        for key, recorder in self._recorders.items()
                        if key.source_stream_id == encounter_uuid
                    }
                )
            )

    def build_archive(
        self,
        *,
        game_id: str,
        encounter_uuid: str,
        terminal_source_event_cursor: int,
        terminal_combat_log_cursor: int,
    ) -> SubjectivePlayerReplayArchive:
        """Atomically freeze and cache every membership's exact reducer inputs."""

        with self._lock:
            cached = self._frozen_archives.get(encounter_uuid)
            if cached is not None:
                if (
                    cached.game_id != game_id
                    or cached.terminal_source_event_cursor
                    != terminal_source_event_cursor
                    or cached.terminal_combat_log_cursor
                    != terminal_combat_log_cursor
                ):
                    raise SubjectiveReplayCaptureError(
                        "terminal player replay retry changed immutable coordinates"
                    )
                return cached
            opened_partition_count = self._opened_partition_counts.get(
                encounter_uuid,
                0,
            )
            if encounter_uuid in self._aborted_sources:
                self._frozen_sources.add(encounter_uuid)
                reason = self._aborted_source_reasons.get(
                    encounter_uuid,
                    "capture aborted without a recorded reason",
                )
                raise SubjectiveReplayCaptureError(
                    "a canonical player partition failed and cannot be replayed "
                    f"exactly: {reason}"
                )
            source_recorders = tuple(
                recorder
                for key, recorder in self._recorders.items()
                if key.source_stream_id == encounter_uuid
            )
            if any(not recorder.closed for recorder in source_recorders):
                raise SubjectiveReplayCaptureNotReadyError(
                    "canonical player replay segments are still being finalized"
                )

            self._frozen_sources.add(encounter_uuid)
            memberships = tuple(
                sorted({recorder.membership_id for recorder in source_recorders})
            )
            bundles = tuple(
                self.build_bundle(
                    game_id=game_id,
                    encounter_uuid=encounter_uuid,
                    membership_id=membership_id,
                    terminal_source_event_cursor=terminal_source_event_cursor,
                    terminal_combat_log_cursor=terminal_combat_log_cursor,
                )
                for membership_id in memberships
            )
            try:
                archive = SubjectivePlayerReplayArchive(
                    game_id=game_id,
                    encounter_uuid=encounter_uuid,
                    terminal_source_event_cursor=terminal_source_event_cursor,
                    terminal_combat_log_cursor=terminal_combat_log_cursor,
                    opened_partition_count=opened_partition_count,
                    membership_replays=bundles,
                )
            except ValueError as exc:
                raise SubjectiveReplayCaptureError(
                    "canonical player partitions are missing from the ended-game "
                    f"archive: {type(exc).__name__}: {exc}"
                ) from exc
            self._frozen_archives[encounter_uuid] = archive
            return archive

    def clear(self) -> None:
        """Discard captures after their immutable artifacts have been published."""

        with self._lock:
            self._recorders.clear()
            self._membership_indices.clear()
            self._opened_partition_counts.clear()
            self._aborted_sources.clear()
            self._aborted_source_reasons.clear()
            self._frozen_sources.clear()
            self._frozen_archives.clear()


subjective_replay_capture_store = SubjectiveReplayCaptureStore()


__all__ = [
    "SubjectiveReplayCaptureError",
    "SubjectiveReplayCaptureFrozenError",
    "SubjectiveReplayCaptureKey",
    "SubjectiveReplayCaptureNotReadyError",
    "SubjectiveReplayCaptureStore",
    "SubjectiveReplayRecorder",
    "subjective_replay_capture_store",
]
