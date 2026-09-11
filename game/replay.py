"""Recorded native initialization and complete lineages for passive replay."""

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict

from dnd.core.base_object import PASSIVE_EVENT_REPLAY
from dnd.core.events import EventQueue
from game.presentation import (
    CompletedLineage, IntervalEnvelope, PresentationTarget, capture_interval, reduce_interval,
)


@dataclass(frozen=True, slots=True)
class CapturedHistory:
    """Native producer output; before is the derived reference, not wire input."""

    initialization: IntervalEnvelope
    before: PresentationTarget
    lineages: tuple[CompletedLineage, ...]


def capture_history(before: PresentationTarget, lineages: tuple[CompletedLineage, ...]) -> CapturedHistory:
    """Freeze original setup events before the native producer closes its runtime."""
    if before.generation != EventQueue.generation_id():
        raise ValueError("initialization must be captured in its original native generation")
    if before.world is None:
        raise ValueError("initialization requires the recorded battlefield identity")
    initialization = capture_interval(
        name="recorded initialization", start_cursor=0, end_cursor=before.reducer_cursor,
        observer_uuid=before.observer_uuid, battlefield_id=before.world.battlefield_id,
        door_uuid=before.door_uuid, standing_torch_uuid=before.standing_torch_uuid,
    )
    return CapturedHistory(initialization, before, lineages)


class RecordedSequence(BaseModel):
    """Event inputs required to reconstruct and replay an already produced sequence."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal[2] = 2
    initialization: IntervalEnvelope
    lineages: tuple[CompletedLineage, ...]


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
