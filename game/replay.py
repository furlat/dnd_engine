"""Recorded native initialization and complete lineages for passive replay."""

from dataclasses import dataclass, field
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from dnd.core.base_object import PASSIVE_EVENT_REPLAY
from dnd.core.events import EventPhase, EventQueue
from game.presentation import (
    CompletedLineage, IntervalEnvelope, PresentationTarget, capture_interval, capture_lineages,
    reduce_interval,
)


class RecordedSequence(BaseModel):
    """Private native event inputs, including local objective diagnostics."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal[2] = 2
    initialization: IntervalEnvelope
    lineages: tuple[CompletedLineage, ...]


@dataclass(frozen=True, slots=True)
class ObserverCapture:
    """A named participant's real initialization boundary in this experiment."""

    role: str
    entity_uuid: UUID
    start_cursor: int


@dataclass(frozen=True, slots=True)
class CapturedHistory:
    """Native producer output; before is the derived reference, not wire input."""

    initialization: IntervalEnvelope
    before: PresentationTarget
    lineages: tuple[CompletedLineage, ...]
    views: dict[str, RecordedSequence] = field(default_factory=dict)


def capture_history(
    before: PresentationTarget, lineages: tuple[CompletedLineage, ...], *,
    observers: tuple[ObserverCapture, ...] = (),
) -> CapturedHistory:
    """Freeze each requested view of one completed native experiment before reset.

    The original fields retain the producer's focused single-view selection.
    Views cover actual native roots in each observer's full interval, including
    private actions that the original observer could not perceive.
    """
    if before.generation != EventQueue.generation_id():
        raise ValueError("initialization must be captured in its original native generation")
    if before.world is None:
        raise ValueError("initialization requires the recorded battlefield identity")
    initialization = capture_interval(
        name="recorded initialization", start_cursor=0, end_cursor=before.reducer_cursor,
        observer_uuid=before.observer_uuid, battlefield_id=before.world.battlefield_id,
        door_uuid=before.door_uuid, standing_torch_uuid=before.standing_torch_uuid,
    )
    if len({observer.role for observer in observers}) != len(observers):
        raise ValueError("observer roles must be unique within an experiment")
    end_cursor = EventQueue.event_cursor()
    roots = tuple((index, event) for index, event in EventQueue.iter_events_since(0)
                  if event.parent_lineage is None
                  and event.phase in (EventPhase.COMPLETION, EventPhase.CANCEL))
    views: dict[str, RecordedSequence] = {}
    for observer in observers:
        if not 0 <= observer.start_cursor <= end_cursor:
            raise ValueError("observer initialization is outside this experiment")
        startup = capture_interval(
            name=f"{observer.role} initialization", start_cursor=0, end_cursor=observer.start_cursor,
            observer_uuid=observer.entity_uuid, battlefield_id=before.world.battlefield_id,
            door_uuid=before.door_uuid, standing_torch_uuid=before.standing_torch_uuid,
        )
        latest, _ = reduce_interval(None, startup)
        if observer.entity_uuid not in latest.actors:
            raise ValueError(f"{observer.role} has no native actor at its initialization boundary")
        retained = capture_lineages(tuple(root for index, root in roots
                                         if observer.start_cursor <= index < end_cursor),
            observer_uuid=observer.entity_uuid, known_actor_uuids=frozenset(latest.actors))
        views[observer.role] = RecordedSequence(initialization=startup, lineages=retained)
    return CapturedHistory(initialization, before, lineages, views)


def encode_sequence(initialization: IntervalEnvelope, lineages: tuple[CompletedLineage, ...]) -> bytes:
    """Encode original initialization facts and retained causal roots."""
    return RecordedSequence(initialization=initialization, lineages=lineages).model_dump_json(
        warnings="error",
    ).encode("utf-8")


def decode_sequence(payload: bytes) -> tuple[PresentationTarget, tuple[CompletedLineage, ...]]:
    """Restore passive events and derive the baseline through the ordinary reducer."""
    sequence = RecordedSequence.model_validate_json(payload, context=PASSIVE_EVENT_REPLAY)
    before, _ = reduce_interval(None, sequence.initialization)
    return before, sequence.lineages
