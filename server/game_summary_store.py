"""Bounded worker-local storage for objective terminal game summaries.

The store is a passive observer of completed EventQueue batches. It captures
objective entity state at encounter boundaries and delegates all aggregation to
the pure ``dnd.analytics`` reducer. It does not participate in engine mutation
or durable persistence.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from threading import RLock
from typing import Sequence
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from dnd.analytics import (
    EntitySnapshotV1,
    GameSummaryEvidenceV1,
    GameSummary,
    TerminalCursorV1,
    reduce_game_summary,
)
from dnd.core.events import (
    EncounterEndEvent,
    EncounterStartEvent,
    Event,
    EventPhase,
    EventQueue,
)
from dnd.encounter import Encounter
from dnd.entity import Entity
from server.objective_replay import ObjectiveReplaySeed
from server.objective_state import build_current_objective_world
from server.canonical_json import canonical_json_sha256


DEFAULT_WORKER_SUMMARY_CAPACITY = 32


@dataclass(frozen=True)
class _EncounterCapture:
    """Evidence origin retained when an encounter starts."""

    initial_entities: tuple[EntitySnapshotV1, ...]
    initial_snapshot_complete: bool
    event_origin: int
    combat_log_origin: int | None
    replay_generation_id: str
    replay_seed: ObjectiveReplaySeed | None


class WorkerSummaryEvidence(BaseModel):
    """Canonical terminal summary paired with exact source-evidence digests."""

    model_config = ConfigDict(frozen=True)

    generation_id: UUID = Field(description="EventQueue generation summarized by this evidence.")
    summary: GameSummary = Field(description="Canonical objective terminal summary.")
    source_event_digest: str = Field(min_length=64, max_length=64, description="Digest of typed event versions.")
    source_combat_log_digest: str = Field(min_length=64, max_length=64, description="Digest of structured combat logs.")


class WorkerReplayCapture(BaseModel):
    """Cold coordinates needed to materialize one terminal replay artifact."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    generation_id: str = Field(min_length=1)
    game_id: str = Field(min_length=1)
    encounter_uuid: str = Field(min_length=1)
    source_stream_id: str = Field(min_length=1)
    seed: ObjectiveReplaySeed
    terminal_event_cursor: int = Field(ge=1)
    terminal_combat_log_cursor: int = Field(ge=0)


class WorkerGameSummaryStore:
    """Collect and retain a bounded set of terminal summaries per worker.

    Args:
        max_summaries: Maximum terminal summaries retained in insertion order.
    """

    def __init__(self, max_summaries: int = DEFAULT_WORKER_SUMMARY_CAPACITY) -> None:
        if max_summaries < 1:
            raise ValueError("max_summaries must be at least 1")
        self._max_summaries = max_summaries
        self._captures: dict[UUID, _EncounterCapture] = {}
        self._directory_game_ids: dict[UUID, UUID] = {}
        self._summaries: OrderedDict[str, WorkerSummaryEvidence] = OrderedDict()
        self._replay_captures: OrderedDict[str, WorkerReplayCapture] = OrderedDict()
        self._lock = RLock()
        self.ensure_attached()

    def reset(self) -> None:
        """Clear worker-local evidence and restore the passive attachment.

        ``EventQueue.reset()`` clears callback registrations. Server reset paths
        should therefore call this method immediately afterward.
        """
        with self._lock:
            self._captures.clear()
            self._directory_game_ids.clear()
            self._summaries.clear()
            self._replay_captures.clear()
        self.ensure_attached()

    def bind_directory_game_id(
        self,
        encounter_uuid: UUID,
        game_id: UUID,
    ) -> None:
        """Bind an in-process encounter to its durable directory identity."""

        with self._lock:
            existing = self._directory_game_ids.get(encounter_uuid)
            if existing is not None and existing != game_id:
                raise ValueError(
                    f"Encounter {encounter_uuid} is already bound to game "
                    f"{existing}",
                )
            self._directory_game_ids[encounter_uuid] = game_id

    def ensure_attached(self) -> None:
        """Idempotently attach the store to EventQueue batch notifications."""
        EventQueue.add_on_event_batch_callback(self._on_event_batch)

    def capture_active_encounter(self, encounter: Encounter) -> None:
        """Adopt an encounter that started while a scenario factory reset callbacks.

        Scenario assembly owns engine-registry reset and may start the encounter
        before returning it to the server. The server calls this immediately on
        return, before any participant action, so the retained boundary remains
        the true playable initial state.
        """
        start_event = next(
            (
                event
                for _index, event in EventQueue.iter_events_since(0)
                if isinstance(event, EncounterStartEvent)
                and event.phase == EventPhase.COMPLETION
                and event.encounter_uuid == encounter.uuid
            ),
            None,
        )
        if start_event is None:
            raise ValueError(f"Encounter {encounter.uuid} has no retained start event")
        self._capture_start(start_event)

    def get(self, game_id: str | UUID | None = None) -> GameSummary | None:
        """Return a defensive copy of a retained terminal summary.

        Args:
            game_id: Hosted game id or encounter UUID. When omitted, return the
                most recently completed game.

        Returns:
            A deep copy of the immutable summary contract, or ``None`` when no
            matching terminal summary is retained.
        """
        with self._lock:
            if not self._summaries:
                return None
            if game_id is None:
                evidence = next(reversed(self._summaries.values()))
                return evidence.summary.model_copy(deep=True)

            identifier = str(game_id)
            evidence = self._summaries.get(identifier)
            if evidence is None:
                evidence = next(
                    (
                        candidate
                        for candidate in self._summaries.values()
                        if str(candidate.summary.encounter_uuid) == identifier
                    ),
                    None,
                )
            return evidence.summary.model_copy(deep=True) if evidence is not None else None

    def get_evidence(self, game_id: str | UUID | None = None) -> WorkerSummaryEvidence | None:
        """Return summary and source digests for gateway persistence."""
        with self._lock:
            if not self._summaries:
                return None
            if game_id is None:
                return next(reversed(self._summaries.values())).model_copy(deep=True)
            identifier = str(game_id)
            evidence = self._summaries.get(identifier)
            if evidence is None:
                evidence = next(
                    (
                        candidate
                        for candidate in self._summaries.values()
                        if str(candidate.summary.encounter_uuid) == identifier
                    ),
                    None,
                )
            return evidence.model_copy(deep=True) if evidence is not None else None

    def get_replay_capture(
        self,
        game_id: str | UUID | None = None,
    ) -> WorkerReplayCapture | None:
        """Return immutable seed and terminal coordinates for replay assembly."""
        with self._lock:
            if not self._replay_captures:
                return None
            if game_id is None:
                return next(reversed(self._replay_captures.values())).model_copy(deep=True)
            identifier = str(game_id)
            capture = self._replay_captures.get(identifier)
            if capture is None:
                capture = next(
                    (
                        candidate
                        for candidate in self._replay_captures.values()
                        if candidate.encounter_uuid == identifier
                    ),
                    None,
                )
            return capture.model_copy(deep=True) if capture is not None else None

    def _on_event_batch(self, events: Sequence[Event]) -> None:
        """Capture encounter boundaries observed in an authoritative batch.

        Args:
            events: Events in EventQueue append order for one completed batch.
        """
        for event in events:
            if event.phase != EventPhase.COMPLETION:
                continue
            if isinstance(event, EncounterStartEvent):
                self._capture_start(event)
            elif isinstance(event, EncounterEndEvent):
                self._capture_end(event)

    def _capture_start(self, event: EncounterStartEvent) -> None:
        """Capture initial entity state and evidence origins."""
        event_origin = EventQueue.get_event_index(event.uuid)
        if event_origin is None:
            return

        initial_entities, snapshot_complete = _capture_entities(event.combatant_uuids)
        encounter = Encounter.get(event.encounter_uuid)
        replay_generation_id = str(EventQueue.generation_id())
        replay_seed = (
            ObjectiveReplaySeed(
                event_cursor=EventQueue.event_cursor(),
                combat_log_cursor=len(encounter.combat_log),
                world=build_current_objective_world(encounter=encounter),
            )
            if encounter is not None
            else None
        )
        capture = _EncounterCapture(
            initial_entities=initial_entities,
            initial_snapshot_complete=snapshot_complete,
            event_origin=event_origin,
            combat_log_origin=(len(encounter.combat_log) if encounter is not None else None),
            replay_generation_id=replay_generation_id,
            replay_seed=replay_seed,
        )
        with self._lock:
            self._captures[event.encounter_uuid] = capture

    def _capture_end(self, event: EncounterEndEvent) -> None:
        """Reduce and retain a terminal summary from typed worker evidence."""
        terminal_event_index = EventQueue.get_event_index(event.uuid)
        with self._lock:
            capture = self._captures.pop(event.encounter_uuid, None)

        final_entities, final_snapshot_complete = _capture_entities(event.combatant_uuids)
        encounter = Encounter.get(event.encounter_uuid)

        event_history: tuple[Event, ...] = ()
        event_history_complete = capture is not None and terminal_event_index is not None
        if event_history_complete and capture is not None and terminal_event_index is not None:
            event_history = tuple(
                retained_event
                for index, retained_event in EventQueue.iter_events_since(capture.event_origin)
                if index <= terminal_event_index
            )
            event_history_complete = bool(
                event_history
                and isinstance(event_history[0], EncounterStartEvent)
                and event_history[0].encounter_uuid == event.encounter_uuid
                and event_history[-1].uuid == event.uuid
            )

        combat_log_cursor = len(encounter.combat_log) if encounter is not None else 0
        combat_logs = ()
        combat_log_complete = (
            capture is not None
            and capture.combat_log_origin is not None
            and encounter is not None
        )
        if combat_log_complete and capture is not None and encounter is not None:
            combat_logs = tuple(encounter.combat_log[capture.combat_log_origin :])

        initial_entities = capture.initial_entities if capture is not None else ()
        evidence = GameSummaryEvidenceV1(
            terminal_cursor=TerminalCursorV1(
                event_cursor=(
                    terminal_event_index + 1
                    if terminal_event_index is not None
                    else EventQueue.event_cursor()
                ),
                combat_log_cursor=combat_log_cursor,
            ),
            event_history_complete=event_history_complete,
            combat_log_complete=combat_log_complete,
            initial_snapshot_complete=(
                capture.initial_snapshot_complete if capture is not None else False
            ),
            final_snapshot_complete=final_snapshot_complete,
        )
        with self._lock:
            directory_game_id = self._directory_game_ids.get(
                event.encounter_uuid,
            )
        game_id = (
            str(directory_game_id)
            if directory_game_id is not None
            else str(event.encounter_uuid)
        )
        summary = reduce_game_summary(
            game_id=game_id,
            encounter_uuid=event.encounter_uuid,
            initial_entities=initial_entities,
            final_entities=final_entities,
            event_history=event_history,
            combat_logs=combat_logs,
            evidence=evidence,
        )
        self._retain(
            WorkerSummaryEvidence(
                generation_id=EventQueue.generation_id(),
                summary=summary,
                source_event_digest=canonical_json_sha256(
                    [retained.model_dump(mode="json") for retained in event_history]
                ),
                source_combat_log_digest=canonical_json_sha256(
                    [entry.model_dump(mode="json") for entry in combat_logs]
                ),
            )
        )
        if (
            capture is not None
            and capture.replay_seed is not None
            and terminal_event_index is not None
            and capture.replay_generation_id == str(EventQueue.generation_id())
            and capture.replay_seed.event_cursor <= terminal_event_index
        ):
            self._retain_replay_capture(
                WorkerReplayCapture(
                    generation_id=capture.replay_generation_id,
                    game_id=game_id,
                    encounter_uuid=str(event.encounter_uuid),
                    source_stream_id=str(event.encounter_uuid),
                    seed=capture.replay_seed,
                    terminal_event_cursor=terminal_event_index + 1,
                    terminal_combat_log_cursor=combat_log_cursor,
                )
            )

    def _retain(self, evidence: WorkerSummaryEvidence) -> None:
        """Retain one summary and evict the oldest entry when necessary."""
        with self._lock:
            self._summaries.pop(evidence.summary.game_id, None)
            self._summaries[evidence.summary.game_id] = evidence.model_copy(deep=True)
            while len(self._summaries) > self._max_summaries:
                self._summaries.popitem(last=False)

    def _retain_replay_capture(self, capture: WorkerReplayCapture) -> None:
        """Retain terminal replay coordinates under the same bounded policy."""
        with self._lock:
            self._replay_captures.pop(capture.game_id, None)
            self._replay_captures[capture.game_id] = capture.model_copy(deep=True)
            while len(self._replay_captures) > self._max_summaries:
                self._replay_captures.popitem(last=False)

def _capture_entities(
    entity_uuids: Sequence[UUID],
) -> tuple[tuple[EntitySnapshotV1, ...], bool]:
    """Capture objective state for the requested combatants.

    Args:
        entity_uuids: Encounter combatants to capture in authoritative order.

    Returns:
        Sorted snapshots and whether every requested entity was available.
    """
    snapshots: list[EntitySnapshotV1] = []
    for entity_uuid in entity_uuids:
        entity = Entity.get(entity_uuid)
        if entity is None:
            continue
        snapshots.append(_capture_entity(entity))
    snapshots.sort(key=lambda snapshot: str(snapshot.entity_uuid))
    return tuple(snapshots), len(snapshots) == len(entity_uuids)


def _capture_entity(entity: Entity) -> EntitySnapshotV1:
    """Capture the typed objective boundary state of one entity."""
    resources = {
        name: resource.current
        for name, resource in entity.action_economy.resources.items()
    }
    for level in range(1, 10):
        spell_slot = entity.action_economy.spell_slot_value(level)
        resources[f"spell_slot_{level}"] = spell_slot.normalized_score

    condition_semantic_keys = tuple(
        sorted(
            condition.get_semantic_key()
            for condition in entity.active_conditions.values()
        )
    )
    return EntitySnapshotV1(
        entity_uuid=entity.uuid,
        name=entity.name,
        side_id=entity.faction or f"entity:{entity.uuid}",
        normal_hit_points=entity.get_normal_hp(),
        maximum_hit_points=entity.get_max_hp(),
        temporary_hit_points=max(
            0,
            entity.health.temporary_hit_points.normalized_score,
        ),
        life_state=entity.health.life_state,
        is_defeated=not entity.is_encounter_alive,
        position=entity.position,
        condition_semantic_keys=condition_semantic_keys,
        resources=dict(sorted(resources.items())),
    )


game_summary_store = WorkerGameSummaryStore()


__all__ = [
    "DEFAULT_WORKER_SUMMARY_CAPACITY",
    "WorkerGameSummaryStore",
    "WorkerReplayCapture",
    "WorkerSummaryEvidence",
    "game_summary_store",
]
