"""Canonical live composition for perspective-partitioned player replication.

The runtime is the sole bridge between mutable engine state and the cold
subjective journal.  It attaches behind :mod:`server.event_stream`, so the
objective source journal finalizes combat-log barriers before this runtime
projects the corresponding causal batch.  Route and SSE layers only resolve a
context and read its already-validated bootstrap, windows, and subscription.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from threading import RLock
from typing import Optional, Protocol

from dnd.core.events import Event, EventPhase, EventQueue, EventType, StepMovementEvent
from dnd.core.gridmap import GridMap, get_map
from dnd.encounter import Encounter
from dnd.entity import Entity
from server.combat_log_source import CombatLogSourceSlot, CombatLogSourceWindow
from server.event_stream import event_stream
from server.player_replay import SubjectiveReplaySegmentEnd
from server.player_replay_capture import (
    SubjectiveReplayCaptureFrozenError,
    SubjectiveReplayCaptureStore,
    SubjectiveReplayRecorder,
    subjective_replay_capture_store,
)
from server.player_replication.combat_log_projection import (
    CanonicalSubjectiveCombatLogProjector,
    canonical_subjective_combat_log_projector,
)
from server.player_replication.journal import (
    DEFAULT_SUBSCRIPTION_DEPTH,
    SubjectiveFrameProjector,
    SubjectiveJournalIdentityError,
    SubjectiveJournalPartitionKey,
    SubjectiveJournalStore,
    SubjectiveReplicationJournal,
    SubjectiveSubscription,
    SubjectiveSubscriptionSnapshot,
    SubjectiveWorldProjectionContext,
    subjective_journal_store,
)
from server.player_replication.mapper import (
    CausalEventBatch,
    ProjectedEventSlot,
    canonical_subjective_presentation_mapper,
)
from server.player_replication.world_projection import (
    CanonicalSubjectiveWorldProjector,
    diff_subjective_worlds,
)
from server.player_replication_contract import (
    PerspectiveKind,
    PlayerReplicationProtocolIdentity,
    PlayerReplicationWatermarks,
    SubjectiveCombatLogFramesResponse,
    SubjectiveFramesResponse,
    SubjectivePerspective,
    SubjectiveReplicatedWorld,
    SubjectiveReplicationBootstrap,
)
from server.subjective_authority import ResolvedSubjectiveAuthority


class SubjectiveRuntimeError(RuntimeError):
    """Base error for canonical live replication composition failures."""


class SubjectiveRuntimeIdentityError(SubjectiveRuntimeError):
    """A caller addressed a stale or mismatched runtime partition."""


class SubjectiveRuntimeProjectionError(SubjectiveRuntimeError):
    """A live source boundary could not be projected exactly."""


@dataclass(frozen=True)
class SubjectiveRuntimeDiagnosticSnapshot:
    """Immutable read-only checkpoint from an already-open player partition."""

    protocol: PlayerReplicationProtocolIdentity
    perspective: SubjectivePerspective
    watermarks: PlayerReplicationWatermarks
    world: SubjectiveReplicatedWorld


class ExactCombatLogSourceJournal(Protocol):
    """Objective source-journal surface consumed by the subjective runtime."""

    def ensure_attached(self) -> None:
        """Attach source capture before subjective batch capture."""
        ...

    def add_finalized_combat_log_source_listener(
        self,
        callback: Callable[[CombatLogSourceSlot], None],
    ) -> None:
        """Register a passive observer for finalized exact source slots."""
        ...

    def remove_finalized_combat_log_source_listener(
        self,
        callback: Callable[[CombatLogSourceSlot], None],
    ) -> None:
        """Remove a finalized source-slot observer."""
        ...

    def capture_combat_log_source_window(
        self,
        encounter: Optional[Encounter],
        *,
        from_cursor: int,
        through_cursor: Optional[int] = None,
        limit: Optional[int] = None,
        expected_generation_id: Optional[str] = None,
    ) -> CombatLogSourceWindow:
        """Capture an exact finalized objective source window."""
        ...


class CanonicalSubjectiveReplicationContext:
    """One authority-stable live reducer timeline and its secure spatial memory."""

    def __init__(
        self,
        *,
        authority: ResolvedSubjectiveAuthority,
        encounter: Encounter,
        protocol: PlayerReplicationProtocolIdentity,
        perspective: SubjectivePerspective,
        journal: SubjectiveReplicationJournal,
        source_journal: ExactCombatLogSourceJournal,
        frame_projector: SubjectiveFrameProjector[CausalEventBatch],
        combat_log_projector: CanonicalSubjectiveCombatLogProjector,
        world_projector: CanonicalSubjectiveWorldProjector,
        replay_capture_store: SubjectiveReplayCaptureStore,
    ) -> None:
        self.authority = authority
        self.encounter = encounter
        self.protocol = protocol
        self.perspective = perspective
        self.journal = journal
        self.partition_key = journal.partition_key
        self.session_id = authority.scope.session_id
        self._source_journal = source_journal
        self._frame_projector = frame_projector
        self._combat_log_projector = combat_log_projector
        self._world_projector = world_projector
        self._replay_capture_store = replay_capture_store
        self._replay_recorder: Optional[SubjectiveReplayRecorder] = None
        self._world = None
        self._pending_log_slots: dict[int, CombatLogSourceSlot] = {}

    @property
    def healthy(self) -> bool:
        """Return whether this partition still proves exact continuity."""
        return self.journal.healthy

    @property
    def unhealthy_reason(self) -> Optional[str]:
        """Return the first fail-closed reason, if any."""
        return self.journal.unhealthy_reason

    def validate_identity(
        self,
        *,
        expected_source_stream_id: Optional[str] = None,
        expected_generation_id: Optional[str] = None,
        expected_perspective_epoch_id: Optional[str] = None,
    ) -> None:
        """Reject stale optimistic identities without falling back to another view."""
        expectations = (
            (
                "source stream",
                expected_source_stream_id,
                self.protocol.source_stream_id,
            ),
            ("generation", expected_generation_id, self.protocol.generation_id),
            (
                "perspective epoch",
                expected_perspective_epoch_id,
                self.perspective.perspective_epoch_id,
            ),
        )
        for label, expected, actual in expectations:
            if expected is not None and expected != actual:
                raise SubjectiveRuntimeIdentityError(
                    f"expected {label} {expected!r}, current value is {actual!r}"
                )

    def bootstrap(self) -> SubjectiveReplicationBootstrap:
        """Capture a current reducer seed using this partition's retained memory."""
        self._require_current_generation()
        bootstrap = self.journal.project_bootstrap(self._world_projector)
        self._world = bootstrap.world
        return bootstrap

    def _diagnostic_snapshot(self) -> SubjectiveRuntimeDiagnosticSnapshot:
        """Copy the retained reducer boundary without projecting or mutating it."""
        self._require_current_generation()
        if not self.healthy:
            raise SubjectiveRuntimeProjectionError(
                self.unhealthy_reason or "subjective replication partition is unhealthy"
            )
        if self._world is None:
            raise SubjectiveRuntimeProjectionError(
                "subjective replication partition has no retained world"
            )
        return SubjectiveRuntimeDiagnosticSnapshot(
            protocol=self.protocol,
            perspective=self.perspective,
            watermarks=self.journal.watermarks,
            world=self._world.model_copy(deep=True),
        )

    def frames(
        self,
        *,
        from_observation_cursor: int,
        limit: Optional[int] = None,
    ) -> SubjectiveFramesResponse:
        """Return one exact retained observation window."""
        self._require_current_generation()
        return self.journal.observation_window(
            from_observation_cursor=from_observation_cursor,
            limit=limit,
        )

    def combat_log(
        self,
        *,
        from_combat_log_cursor: int,
        limit: Optional[int] = None,
    ) -> SubjectiveCombatLogFramesResponse:
        """Return one exact retained nullable subjective-log window."""
        self._require_current_generation()
        return self.journal.combat_log_window(
            from_combat_log_cursor=from_combat_log_cursor,
            limit=limit,
        )

    def subscribe(
        self,
        *,
        max_depth: int = DEFAULT_SUBSCRIPTION_DEPTH,
    ) -> SubjectiveSubscription:
        """Subscribe to sync, frame, and combat-log deliveries for this exact epoch."""
        self._require_current_generation()
        return self.journal.subscribe(max_depth=max_depth)

    def subscribe_with_backfill(
        self,
        *,
        from_observation_cursor: int,
        from_combat_log_cursor: int,
        max_depth: int = DEFAULT_SUBSCRIPTION_DEPTH,
    ) -> SubjectiveSubscriptionSnapshot:
        """Atomically subscribe and capture exact histories through the queued sync."""
        self._require_current_generation()
        return self.journal.subscribe_with_backfill(
            from_observation_cursor=from_observation_cursor,
            from_combat_log_cursor=from_combat_log_cursor,
            max_depth=max_depth,
        )

    def unsubscribe(self, subscription: SubjectiveSubscription) -> None:
        """Release one live subscriber without affecting the retained partition."""
        self.journal.unsubscribe(subscription)

    def _initialize(self) -> SubjectiveReplicationBootstrap:
        """Seed exact prior logs and one atomic current world boundary."""
        self._seed_existing_combat_logs()
        return self.bootstrap()

    def _attach_replay_recorder(
        self,
        recorder: SubjectiveReplayRecorder,
    ) -> None:
        """Attach only after the provisional reducer seed is fully proven."""

        if self._replay_recorder is not None:
            raise SubjectiveRuntimeProjectionError(
                "subjective replay recorder is already attached"
            )
        if (
            recorder.key.source_stream_id != self.partition_key.source_stream_id
            or recorder.key.generation_id != self.partition_key.generation_id
            or recorder.key.perspective_epoch_id
            != self.partition_key.perspective_epoch_id
        ):
            raise SubjectiveRuntimeIdentityError(
                "subjective replay recorder belongs to another partition"
            )
        self._replay_recorder = recorder

    def _seed_existing_combat_logs(self) -> None:
        """Consume exact source history captured before this perspective opened."""
        current = self.journal.watermarks.combat_log_cursor
        total = len(self.encounter.combat_log)
        while current < total:
            try:
                window = self._source_journal.capture_combat_log_source_window(
                    self.encounter,
                    from_cursor=current,
                    through_cursor=current + 1,
                    expected_generation_id=self.protocol.generation_id,
                )
                slot = window.slots[0]
                if slot.event_cursor > self.journal.watermarks.source_event_cursor:
                    raise SubjectiveRuntimeProjectionError(
                        "existing combat-log barrier exceeds the opening event cursor"
                    )
                self.journal.project_and_append_combat_log(
                    slot,
                    self._combat_log_projector,
                )
            except Exception as exc:
                self._fail(f"initial combat-log catch-up failed: {type(exc).__name__}: {exc}")
                if isinstance(exc, SubjectiveRuntimeProjectionError):
                    raise
                raise SubjectiveRuntimeProjectionError(
                    "initial exact combat-log history is unavailable"
                ) from exc
            current += 1

    def _consume_batch(self, slots: tuple[ProjectedEventSlot, ...]) -> None:
        """Project one not-yet-consumed suffix, then release eligible log slots."""
        if not self.healthy:
            return
        previous = self.journal.watermarks
        pending = tuple(
            slot for slot in slots if slot.source_event_cursor > previous.source_event_cursor
        )
        if not pending:
            self._drain_finalized_combat_logs()
            return
        if pending[0].source_event_cursor != previous.source_event_cursor + 1:
            self._fail("subjective runtime missed a source event cursor")
            return
        if self._world is None:
            self._fail("subjective runtime has no atomic world seed")
            return

        through_source_cursor = pending[-1].source_event_cursor
        prospective_watermarks = PlayerReplicationWatermarks(
            source_event_cursor=through_source_cursor,
            observation_cursor=previous.observation_cursor + 1,
            presentation_cursor=previous.presentation_cursor,
            combat_log_cursor=previous.combat_log_cursor,
        )
        try:
            current_world = self._world_projector.project_world(
                SubjectiveWorldProjectionContext(
                    protocol=self.protocol,
                    perspective=self.perspective,
                    captured_watermarks=prospective_watermarks,
                )
            )
            patches = diff_subjective_worlds(self._world, current_world)
            source = CausalEventBatch(
                slots=pending,
                through_source_event_cursor=through_source_cursor,
                patches=patches,
            )
            frame = self.journal.project_and_append_frame(source, self._frame_projector)
            recorder = self._replay_recorder
            if recorder is not None:
                recorder.append_frame(frame)
            self._world = current_world
            self._drain_finalized_combat_logs()
            self._close_terminal_replay_if_complete()
        except Exception as exc:
            self._fail(f"causal batch projection failed: {type(exc).__name__}: {exc}")

    def _note_finalized_combat_log(self, slot: CombatLogSourceSlot) -> None:
        """Queue one finalized source slot and release it only behind its barrier."""
        if not self.healthy:
            return
        if (
            slot.source_stream_id != self.protocol.source_stream_id
            or slot.generation_id != self.protocol.generation_id
        ):
            return
        current = self.journal.watermarks.combat_log_cursor
        if slot.combat_log_cursor <= current:
            return
        existing = self._pending_log_slots.get(slot.combat_log_cursor)
        if existing is not None and existing != slot:
            self._fail("conflicting finalized combat-log source notification")
            return
        self._pending_log_slots[slot.combat_log_cursor] = slot
        self._drain_finalized_combat_logs()

    def _drain_finalized_combat_logs(self) -> None:
        """Append the contiguous finalized prefix whose event barriers were consumed."""
        while self.healthy:
            next_cursor = self.journal.watermarks.combat_log_cursor + 1
            slot = self._pending_log_slots.get(next_cursor)
            if slot is None:
                break
            if slot.event_cursor > self.journal.watermarks.source_event_cursor:
                break
            try:
                frame = self.journal.project_and_append_combat_log(
                    slot,
                    self._combat_log_projector,
                )
                recorder = self._replay_recorder
                if recorder is not None:
                    recorder.append_combat_log(
                        frame,
                        watermarks=self.journal.watermarks,
                    )
            except Exception as exc:
                self._fail(
                    f"finalized combat-log projection failed: {type(exc).__name__}: {exc}"
                )
                return
            del self._pending_log_slots[next_cursor]
        if self.healthy:
            self._close_terminal_replay_if_complete()

    def _close_terminal_replay_if_complete(self) -> None:
        """Seal only after the END cue and every finalized source-log slot drain."""

        recorder = self._replay_recorder
        if recorder is None or recorder.closed or not recorder.encounter_ended:
            return
        if self._pending_log_slots:
            return
        if self.journal.watermarks.combat_log_cursor != len(self.encounter.combat_log):
            return
        self._replay_capture_store.close(
            recorder.key,
            SubjectiveReplaySegmentEnd.ENCOUNTER_ENDED,
        )

    def _require_current_generation(self) -> None:
        current_generation = str(EventQueue.generation_id())
        if current_generation != self.protocol.generation_id:
            raise SubjectiveRuntimeIdentityError(
                "subjective replication context belongs to a retired EventQueue generation"
            )

    def _retire(self, reason: str) -> None:
        recorder = self._replay_recorder
        if recorder is not None and not recorder.closed:
            if self.healthy:
                try:
                    self._replay_capture_store.close(
                        recorder.key,
                        SubjectiveReplaySegmentEnd.PERSPECTIVE_RETIRED,
                    )
                except Exception as exc:
                    self._replay_capture_store.abort(
                        recorder.key,
                        recorder,
                        reason=(
                            "perspective retirement could not seal replay segment: "
                            f"{type(exc).__name__}: {exc}"
                        ),
                    )
            else:
                self._replay_capture_store.abort(
                    recorder.key,
                    recorder,
                    reason=(
                        self.unhealthy_reason
                        or f"subjective perspective retired: {reason}"
                    ),
                )
        self._replay_recorder = None
        self._pending_log_slots.clear()
        self.journal.close(reason)

    def _fail(self, reason: str) -> None:
        recorder = self._replay_recorder
        if recorder is not None and not recorder.closed:
            self._replay_capture_store.abort(
                recorder.key,
                recorder,
                reason=reason,
            )
            self._replay_recorder = None
        self.journal.close(reason)


class CanonicalSubjectiveReplicationRuntime:
    """Own and update every canonical live subjective partition in this process."""

    def __init__(
        self,
        *,
        store: SubjectiveJournalStore = subjective_journal_store,
        source_journal: ExactCombatLogSourceJournal = event_stream,
        grid_provider: Callable[[], GridMap] = get_map,
        entities_provider: Callable[[], Iterable[Entity]] = Entity.get_all_entities,
        encounter_provider: Callable[[], Optional[Encounter]] = Encounter.get_active,
        frame_projector: SubjectiveFrameProjector[CausalEventBatch] = (
            canonical_subjective_presentation_mapper
        ),
        combat_log_projector: CanonicalSubjectiveCombatLogProjector = (
            canonical_subjective_combat_log_projector
        ),
        replay_capture_store: SubjectiveReplayCaptureStore = (
            subjective_replay_capture_store
        ),
    ) -> None:
        self._store = store
        self._source_journal = source_journal
        self._grid_provider = grid_provider
        self._entities_provider = entities_provider
        self._encounter_provider = encounter_provider
        self._frame_projector = frame_projector
        self._combat_log_projector = combat_log_projector
        self._replay_capture_store = replay_capture_store
        self._contexts: dict[
            SubjectiveJournalPartitionKey,
            CanonicalSubjectiveReplicationContext,
        ] = {}
        self._generation_id = str(EventQueue.generation_id())
        self._attached = False
        self._lock = RLock()

    def ensure_attached(self) -> None:
        """Attach after the objective stream and retire any prior generation."""
        with self._lock:
            # A source stream may have been stopped and reattached independently.
            # Remove our callback first so idempotent recovery always restores the
            # required source-finalization-before-subjective-projection order.
            EventQueue.remove_on_event_callback(self._on_movement_step_completion)
            EventQueue.remove_on_event_batch_callback(self._on_event_batch)
            self._source_journal.ensure_attached()
            current_generation = str(EventQueue.generation_id())
            if current_generation != self._generation_id:
                for key in tuple(self._contexts):
                    if key.generation_id != current_generation:
                        self.retire(key, reason="event_queue_generation_retired")
                self._generation_id = current_generation
            EventQueue.add_on_event_callback(
                self._on_movement_step_completion,
                event_types={EventType.STEP_MOVEMENT},
                phases={EventPhase.COMPLETION},
            )
            EventQueue.add_on_event_batch_callback(self._on_event_batch)
            self._source_journal.add_finalized_combat_log_source_listener(
                self._on_finalized_combat_log_source
            )
            self._attached = True

    def stop(self) -> None:
        """Detach runtime callbacks without stopping the objective source journal."""
        with self._lock:
            EventQueue.remove_on_event_callback(self._on_movement_step_completion)
            EventQueue.remove_on_event_batch_callback(self._on_event_batch)
            self._source_journal.remove_finalized_combat_log_source_listener(
                self._on_finalized_combat_log_source
            )
            self._attached = False

    def bind(
        self,
        authority: ResolvedSubjectiveAuthority,
        *,
        encounter: Optional[Encounter] = None,
    ) -> CanonicalSubjectiveReplicationContext:
        """Resolve or atomically open one current authority/source partition."""
        with self._lock:
            return self._bind(authority, encounter=encounter)

    def _bind(
        self,
        authority: ResolvedSubjectiveAuthority,
        *,
        encounter: Optional[Encounter] = None,
    ) -> CanonicalSubjectiveReplicationContext:
        """Open one context while the runtime partition registry is locked."""
        self.ensure_attached()
        selected_encounter = encounter if encounter is not None else self._encounter_provider()
        if selected_encounter is None:
            raise SubjectiveRuntimeIdentityError(
                "an encounter/source stream is required for player replication"
            )
        perspective = _perspective_from_authority(authority)
        protocol = PlayerReplicationProtocolIdentity(
            source_stream_id=str(selected_encounter.uuid),
            generation_id=str(EventQueue.generation_id()),
        )
        key = SubjectiveJournalPartitionKey(
            source_stream_id=protocol.source_stream_id,
            generation_id=protocol.generation_id,
            perspective_epoch_id=perspective.perspective_epoch_id,
        )

        for existing_key, context in tuple(self._contexts.items()):
            if context.session_id == authority.scope.session_id and existing_key != key:
                self.retire(existing_key, reason="subjective_authority_epoch_rotated")

        existing = self._contexts.get(key)
        if existing is not None:
            if existing.authority != authority or existing.encounter is not selected_encounter:
                raise SubjectiveRuntimeIdentityError(
                    "subjective partition identity was reused with different authority or source"
                )
            return existing

        opening_event_cursor = EventQueue.event_cursor()
        journal = self._store.open(
            protocol=protocol,
            perspective=perspective,
            initial_source_event_cursor=opening_event_cursor,
        )
        world_projector = CanonicalSubjectiveWorldProjector(
            perspective=perspective,
            grid_provider=self._grid_provider,
            entities_provider=self._entities_provider,
            encounter_provider=lambda: selected_encounter,
        )
        context = CanonicalSubjectiveReplicationContext(
            authority=authority,
            encounter=selected_encounter,
            protocol=protocol,
            perspective=perspective,
            journal=journal,
            source_journal=self._source_journal,
            frame_projector=self._frame_projector,
            combat_log_projector=self._combat_log_projector,
            world_projector=world_projector,
            replay_capture_store=self._replay_capture_store,
        )
        recorder: Optional[SubjectiveReplayRecorder] = None
        try:
            opening_bootstrap = context._initialize()
            if EventQueue.event_cursor() != opening_event_cursor:
                raise SubjectiveRuntimeProjectionError(
                    "event cursor changed while opening the atomic subjective seed"
                )
            try:
                recorder = self._replay_capture_store.open(
                    membership_id=authority.scope.membership_id,
                    runtime_session_id=authority.scope.session_id,
                    bootstrap=opening_bootstrap,
                )
            except SubjectiveReplayCaptureFrozenError:
                encounter_state = opening_bootstrap.world.state.encounter
                if encounter_state is None or encounter_state.state != "ended":
                    raise
            else:
                context._attach_replay_recorder(recorder)
                context._close_terminal_replay_if_complete()
        except Exception as exc:
            failure_reason = (
                "subjective runtime initialization failed: "
                f"{type(exc).__name__}: {exc}"
            )
            context._fail(failure_reason)
            if recorder is not None:
                self._replay_capture_store.abort(
                    recorder.key,
                    recorder,
                    reason=failure_reason,
                )
            self._store.discard_uninitialized(key, journal)
            raise
        self._contexts[key] = context
        return context

    def get(
        self,
        key: SubjectiveJournalPartitionKey,
    ) -> CanonicalSubjectiveReplicationContext:
        """Return one exact live context without generation or epoch fallback."""
        with self._lock:
            context = self._contexts.get(key)
            if context is None:
                raise SubjectiveJournalIdentityError(
                    "canonical subjective runtime partition does not exist"
                )
            return context

    def diagnostic_snapshot(
        self,
        authority: ResolvedSubjectiveAuthority,
        *,
        encounter: Optional[Encounter] = None,
    ) -> SubjectiveRuntimeDiagnosticSnapshot:
        """Read an already-open partition without binding or refreshing it.

        This hook exists only for authorized parity diagnostics.  Absence is a
        hard error: a diagnostic read must never create a player journal,
        bootstrap a perspective, attach callbacks, or advance any cursor.
        """

        with self._lock:
            selected_encounter = (
                encounter if encounter is not None else self._encounter_provider()
            )
            if selected_encounter is None:
                raise SubjectiveRuntimeIdentityError(
                    "an encounter/source stream is required for player diagnostics"
                )
            perspective = _perspective_from_authority(authority)
            key = SubjectiveJournalPartitionKey(
                source_stream_id=str(selected_encounter.uuid),
                generation_id=str(EventQueue.generation_id()),
                perspective_epoch_id=perspective.perspective_epoch_id,
            )
            context = self._contexts.get(key)
            if context is None:
                raise SubjectiveRuntimeIdentityError(
                    "subjective parity requires an already-open player partition"
                )
            if context.authority != authority or context.encounter is not selected_encounter:
                raise SubjectiveRuntimeIdentityError(
                    "subjective diagnostic partition authority or source changed"
                )
            return context._diagnostic_snapshot()

    def retire(
        self,
        key: SubjectiveJournalPartitionKey,
        *,
        reason: str = "subjective_runtime_partition_retired",
    ) -> None:
        """Retire one partition, its subscriptions, and its spatial memory."""
        with self._lock:
            context = self._contexts.pop(key, None)
            if context is not None:
                context._retire(reason)
            self._store.retire(key)

    def retire_session(self, session_id: str) -> None:
        """Rotate away every perspective and memory owned by one session."""
        with self._lock:
            keys = tuple(
                key
                for key, context in self._contexts.items()
                if context.session_id == session_id
            )
            for key in keys:
                self.retire(key, reason="subjective_session_authority_retired")

    def clear_generation(self, *, source_stream_id: str, generation_id: str) -> None:
        """Retire every perspective for one exact source generation."""
        with self._lock:
            keys = tuple(
                key
                for key in self._contexts
                if key.source_stream_id == source_stream_id
                and key.generation_id == generation_id
            )
            for key in keys:
                self.retire(key, reason="subjective_source_generation_retired")
            self._store.clear_generation(
                source_stream_id=source_stream_id,
                generation_id=generation_id,
            )

    def clear_all(self) -> None:
        """Retire all journals, subscriptions, and retained spatial memories."""
        with self._lock:
            for key in tuple(self._contexts):
                self.retire(key, reason="subjective_runtime_cleared")
            self._store.clear_all()

    def _on_movement_step_completion(self, event: Event) -> None:
        """Project each committed movement step at its authoritative world state.

        Actions retain one outer causal batch for objective storage, combat-log
        finalization, and non-movement state changes.  A committed movement step
        is also an independently observable reducer boundary: position and every
        causally produced sensory update have already committed, while the next
        path step has not begun.  Consuming the exact source prefix here preserves
        that engine-owned timing without asking clients to reconstruct FOV or
        light from a final action snapshot.
        """
        if not isinstance(event, StepMovementEvent) or not event.committed:
            return
        with self._lock:
            if not self._contexts:
                return
            current_generation = str(EventQueue.generation_id())
            if current_generation != self._generation_id:
                self.ensure_attached()
                return
            through_cursor = EventQueue.event_cursor()
            current_contexts = tuple(
                context
                for context in self._contexts.values()
                if context.protocol.generation_id == current_generation
            )
            if not current_contexts:
                return
            earliest_cursor = min(
                context.journal.watermarks.source_event_cursor
                for context in current_contexts
            )
            stored = tuple(EventQueue.iter_events_since(earliest_cursor))
            if not stored or stored[-1][0] + 1 != through_cursor:
                self._fail_generation("movement step source prefix is unavailable")
                return
            for context in current_contexts:
                previous_cursor = context.journal.watermarks.source_event_cursor
                pending = tuple(
                    ProjectedEventSlot(
                        source_event_cursor=event_index + 1,
                        event=stored_event,
                    )
                    for event_index, stored_event in stored
                    if previous_cursor < event_index + 1 <= through_cursor
                )
                if pending:
                    context._consume_batch(pending)

    def _on_event_batch(self, events: Sequence[Event]) -> None:
        """Project one exact causal batch after objective log finalization."""
        with self._lock:
            if not events or not self._contexts:
                return
            current_generation = str(EventQueue.generation_id())
            if current_generation != self._generation_id:
                self.ensure_attached()
                return
            through_cursor = EventQueue.event_cursor()
            first_cursor = through_cursor - len(events) + 1
            if first_cursor < 1:
                self._fail_generation("invalid causal batch cursor interval")
                return
            slots = tuple(
                ProjectedEventSlot(
                    source_event_cursor=cursor,
                    event=event,
                )
                for cursor, event in enumerate(events, start=first_cursor)
            )
            stored = tuple(
                event
                for _, event in EventQueue.iter_events_since(first_cursor - 1)
            )
            if tuple(event.uuid for event in stored) != tuple(event.uuid for event in events):
                self._fail_generation("causal batch is not the exact EventQueue suffix")
                return
            for context in tuple(self._contexts.values()):
                if context.protocol.generation_id == current_generation:
                    context._consume_batch(slots)

    def _on_finalized_combat_log_source(self, slot: CombatLogSourceSlot) -> None:
        """Forward one finalized source fact to its exact subjective partitions."""
        with self._lock:
            for context in tuple(self._contexts.values()):
                context._note_finalized_combat_log(slot)

    def _fail_generation(self, reason: str) -> None:
        with self._lock:
            for context in tuple(self._contexts.values()):
                if context.protocol.generation_id == self._generation_id:
                    context._fail(reason)


def _perspective_from_authority(
    authority: ResolvedSubjectiveAuthority,
) -> SubjectivePerspective:
    scope = authority.scope
    if scope.projection.value != "subjective":
        raise SubjectiveRuntimeIdentityError(
            "canonical player replication requires subjective authority"
        )
    controlled = tuple(scope.controlled_entity_uuids)
    observers = tuple(scope.observer_entity_uuids)
    return SubjectivePerspective(
        perspective_epoch_id=authority.perspective_epoch_id,
        kind=(
            PerspectiveKind.CONTROLLED_KNOWLEDGE_UNION
            if controlled
            else PerspectiveKind.SPECTATOR_KNOWLEDGE_UNION
        ),
        controlled_entity_uuids=controlled,
        observer_entity_uuids=observers,
        active_observer_uuid=scope.active_observer_uuid,
    )


canonical_subjective_replication_runtime = CanonicalSubjectiveReplicationRuntime()


__all__ = [
    "CanonicalSubjectiveReplicationContext",
    "CanonicalSubjectiveReplicationRuntime",
    "ExactCombatLogSourceJournal",
    "SubjectiveRuntimeError",
    "SubjectiveRuntimeDiagnosticSnapshot",
    "SubjectiveRuntimeIdentityError",
    "SubjectiveRuntimeProjectionError",
    "canonical_subjective_replication_runtime",
]
