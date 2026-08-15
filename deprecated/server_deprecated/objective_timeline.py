"""Route-free adapter from hot engine journals to cold objective timelines.

The adapter is deliberately small and policy-free.  It accepts records that
have already been captured from :class:`EventQueue` and an exact combat-log
source window, validates that both journals describe one source generation,
and emits only dependency-neutral timeline contracts.  It never reconstructs
engine events from archived data.
"""

from __future__ import annotations

from bisect import bisect_right
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Final, Optional

from pydantic import ValidationError

from dnd.core.events import Event
from server.canonical_json import canonical_json_bytes
from server.combat_log_source import CombatLogSourceWindow
from server.event_contract import EventContractError, serialize_event
from server.timeline_contracts import (
    GameEventFrame,
    GameEventFramesResponse,
    ObjectiveCombatLogFrame,
    ObjectiveCombatLogFramesResponse,
    TimelineContractError,
    WireEvent,
)


OBJECTIVE_PERSPECTIVE_EPOCH_ID: Final[str] = "objective"


class ObjectiveTimelineError(RuntimeError):
    """Raised when hot journals cannot prove one exact objective timeline."""


EventQueueRecord = tuple[int, Event]


@dataclass(frozen=True, slots=True)
class ObjectiveEventSourceSlot:
    """Immutable cold event bytes retained at one authoritative source cursor."""

    event_index: int
    event_cursor: int
    combat_log_cursor: int
    wire_event_json: bytes

    def __post_init__(self) -> None:
        if (
            isinstance(self.event_index, bool)
            or not isinstance(self.event_index, int)
            or self.event_index < 0
        ):
            raise ObjectiveTimelineError(
                "objective event source index must be a non-negative integer"
            )
        if self.event_cursor != self.event_index + 1:
            raise ObjectiveTimelineError(
                "objective event source cursor must equal index plus one"
            )
        if (
            isinstance(self.combat_log_cursor, bool)
            or not isinstance(self.combat_log_cursor, int)
            or self.combat_log_cursor < 0
        ):
            raise ObjectiveTimelineError(
                "objective event source combat-log cursor must be non-negative"
            )
        try:
            WireEvent.model_validate_json(self.wire_event_json)
        except (TimelineContractError, ValidationError) as exc:
            raise ObjectiveTimelineError(
                "objective event source bytes violate the cold wire contract"
            ) from exc

    def wire_event(self) -> WireEvent:
        """Return a fresh validated view of the retained immutable bytes."""
        try:
            return WireEvent.model_validate_json(self.wire_event_json)
        except (TimelineContractError, ValidationError) as exc:
            raise ObjectiveTimelineError(
                "retained objective event bytes are invalid"
            ) from exc


def freeze_objective_event_source_slot(
    record: EventQueueRecord,
    *,
    combat_log_cursor: int,
) -> ObjectiveEventSourceSlot:
    """Serialize one hot event exactly once without mutating its retained value."""
    try:
        event_index, event = record
    except (TypeError, ValueError) as exc:
        raise ObjectiveTimelineError(
            "event records must be (index, Event) pairs"
        ) from exc
    if (
        isinstance(event_index, bool)
        or not isinstance(event_index, int)
        or event_index < 0
    ):
        raise ObjectiveTimelineError("event record index must be non-negative")
    if not isinstance(event, Event):
        raise ObjectiveTimelineError("event record value must be an Event")
    if (
        isinstance(combat_log_cursor, bool)
        or not isinstance(combat_log_cursor, int)
        or combat_log_cursor < 0
    ):
        raise ObjectiveTimelineError(
            "combat_log_cursor must be a non-negative integer"
        )

    try:
        detached_event = event.model_copy(deep=True)
        wire_event = WireEvent.model_validate(serialize_event(detached_event))
        wire_event_json = canonical_json_bytes(wire_event)
    except (
        EventContractError,
        TimelineContractError,
        ValidationError,
        TypeError,
        ValueError,
    ) as exc:
        raise ObjectiveTimelineError(
            f"event record at index {event_index} violates the cold timeline contract"
        ) from exc
    return ObjectiveEventSourceSlot(
        event_index=event_index,
        event_cursor=event_index + 1,
        combat_log_cursor=combat_log_cursor,
        wire_event_json=wire_event_json,
    )


def _validate_expected_identity(
    source: CombatLogSourceWindow,
    *,
    source_stream_id: str,
    generation_id: str,
) -> None:
    """Require the source journal to match the caller's captured identity."""
    if not source_stream_id:
        raise ObjectiveTimelineError("source_stream_id must not be empty")
    if not generation_id:
        raise ObjectiveTimelineError("generation_id must not be empty")
    if source.source_stream_id != source_stream_id:
        raise ObjectiveTimelineError("combat-log source stream changed")
    if source.generation_id != generation_id:
        raise ObjectiveTimelineError("combat-log generation changed")


def _complete_causal_log_cursors(
    source: CombatLogSourceWindow,
    *,
    source_stream_id: str,
    generation_id: str,
) -> tuple[int, ...]:
    """Return the complete ordered causal cursor index, or fail closed.

    A suffix or truncated source page cannot prove the barrier for an event:
    an omitted slot may have a causal event cursor at or before that event.
    Event frames therefore require the complete retained log prefix through
    the captured source total.  Ordinary combat-log page projection does not.
    """
    _validate_expected_identity(
        source,
        source_stream_id=source_stream_id,
        generation_id=generation_id,
    )
    if source.retained_from_cursor != 0 or source.from_cursor != 0:
        raise ObjectiveTimelineError(
            "event barriers require combat-log history retained from cursor zero"
        )
    if source.through_cursor != source.total:
        raise ObjectiveTimelineError(
            "event barriers require the complete captured combat-log window"
        )
    return tuple(slot.event_cursor for slot in source.slots)


def exact_combat_log_barrier(
    event_cursor: int,
    source: CombatLogSourceWindow,
    *,
    source_stream_id: str,
    generation_id: str,
) -> int:
    """Return the highest contiguous objective-log cursor causal by an event.

    Since exact source slots are contiguous and their causal event cursors are
    nondecreasing, this is both the number of causal slots and the cursor of
    the final causal slot.  ``bisect_right`` includes every log whose barrier
    is equal to the event cursor, including standalone logs at cursor zero.
    """
    if isinstance(event_cursor, bool) or not isinstance(event_cursor, int):
        raise ObjectiveTimelineError("event_cursor must be an integer")
    if event_cursor < 0:
        raise ObjectiveTimelineError("event_cursor must be non-negative")
    causal_cursors = _complete_causal_log_cursors(
        source,
        source_stream_id=source_stream_id,
        generation_id=generation_id,
    )
    return bisect_right(causal_cursors, event_cursor)


def build_objective_combat_log_frames(
    source: CombatLogSourceWindow,
    *,
    expected_source_stream_id: Optional[str] = None,
    expected_generation_id: Optional[str] = None,
) -> ObjectiveCombatLogFramesResponse:
    """Deep-copy one exact source window into objective combat-log frames."""
    if (
        expected_source_stream_id is not None
        and source.source_stream_id != expected_source_stream_id
    ):
        raise ObjectiveTimelineError("combat-log source stream changed")
    if (
        expected_generation_id is not None
        and source.generation_id != expected_generation_id
    ):
        raise ObjectiveTimelineError("combat-log generation changed")

    frames = tuple(
        ObjectiveCombatLogFrame(
            source_stream_id=source.source_stream_id,
            generation_id=source.generation_id,
            combat_log_cursor=slot.combat_log_cursor,
            event_cursor=slot.event_cursor,
            entry=slot.entry.model_copy(deep=True),
        )
        for slot in source.slots
    )
    try:
        return ObjectiveCombatLogFramesResponse(
            source_stream_id=source.source_stream_id,
            generation_id=source.generation_id,
            retained_from_cursor=source.retained_from_cursor,
            from_cursor=source.from_cursor,
            through_cursor=source.through_cursor,
            frames=frames,
            total=source.total,
        )
    except ValidationError as exc:
        raise ObjectiveTimelineError("invalid objective combat-log window") from exc


def build_objective_game_event_frame_from_source(
    slot: ObjectiveEventSourceSlot,
    *,
    source_stream_id: str,
    generation_id: str,
) -> GameEventFrame:
    """Bind one immutable source slot to an objective stream identity."""
    if not source_stream_id:
        raise ObjectiveTimelineError("source_stream_id must not be empty")
    if not generation_id:
        raise ObjectiveTimelineError("generation_id must not be empty")
    try:
        return GameEventFrame(
            source_stream_id=source_stream_id,
            generation_id=generation_id,
            event_index=slot.event_index,
            event_cursor=slot.event_cursor,
            combat_log_cursor=slot.combat_log_cursor,
            event=slot.wire_event(),
        )
    except (TimelineContractError, ValidationError) as exc:
        raise ObjectiveTimelineError(
            f"objective event source slot {slot.event_cursor} is invalid"
        ) from exc


def build_objective_game_event_frame(
    slot: ObjectiveEventSourceSlot,
    *,
    source_stream_id: str,
    generation_id: str,
    combat_log_source: CombatLogSourceWindow,
) -> GameEventFrame:
    """Validate one frozen slot against the complete causal-log source."""
    causal_log_cursors = _complete_causal_log_cursors(
        combat_log_source,
        source_stream_id=source_stream_id,
        generation_id=generation_id,
    )
    expected_log_cursor = bisect_right(
        causal_log_cursors,
        slot.event_cursor,
    )
    if slot.combat_log_cursor != expected_log_cursor:
        raise ObjectiveTimelineError(
            "objective event source slot has an inconsistent combat-log barrier"
        )
    return build_objective_game_event_frame_from_source(
        slot,
        source_stream_id=source_stream_id,
        generation_id=generation_id,
    )


def build_objective_game_event_frames(
    slots: Iterable[ObjectiveEventSourceSlot],
    *,
    source_stream_id: str,
    generation_id: str,
    combat_log_source: CombatLogSourceWindow,
    retained_from_cursor: int,
    from_cursor: int,
    through_cursor: int,
    total: int,
) -> GameEventFramesResponse:
    """Build one exact contiguous all-phase diagnostics event window."""
    causal_log_cursors = _complete_causal_log_cursors(
        combat_log_source,
        source_stream_id=source_stream_id,
        generation_id=generation_id,
    )
    materialized = tuple(slots)
    if retained_from_cursor < 0:
        raise ObjectiveTimelineError("retained_from_cursor must be non-negative")
    if from_cursor < retained_from_cursor:
        raise ObjectiveTimelineError("from_cursor precedes retained event history")
    if through_cursor < from_cursor:
        raise ObjectiveTimelineError("through_cursor must not precede from_cursor")
    if total < through_cursor:
        raise ObjectiveTimelineError("through_cursor exceeds the captured event total")
    if len(materialized) != through_cursor - from_cursor:
        raise ObjectiveTimelineError(
            "event records must cover the exact requested cursor window"
        )

    frames: list[GameEventFrame] = []
    for expected_index, slot in enumerate(materialized, start=from_cursor):
        if slot.event_index != expected_index:
            raise ObjectiveTimelineError(
                "diagnostics event source slots must be contiguous and ordered"
            )
        expected_log_cursor = bisect_right(
            causal_log_cursors,
            slot.event_cursor,
        )
        if slot.combat_log_cursor != expected_log_cursor:
            raise ObjectiveTimelineError(
                "objective event source slot has an inconsistent combat-log barrier"
            )
        frames.append(
            build_objective_game_event_frame_from_source(
                slot,
                source_stream_id=source_stream_id,
                generation_id=generation_id,
            )
        )

    try:
        return GameEventFramesResponse(
            source_stream_id=source_stream_id,
            generation_id=generation_id,
            retained_from_cursor=retained_from_cursor,
            from_cursor=from_cursor,
            through_cursor=through_cursor,
            frames=tuple(frames),
            total=total,
        )
    except ValidationError as exc:
        raise ObjectiveTimelineError("invalid objective game-event window") from exc


def select_completion_frames_for_replay(
    source: GameEventFramesResponse,
    *,
    expected_source_stream_id: Optional[str] = None,
    expected_generation_id: Optional[str] = None,
) -> tuple[GameEventFrame, ...]:
    """Select completion events without renumbering their objective cursors.

    A tuple is intentional.  Completion events are generally sparse within
    the all-phase source window, so representing the result as an exact
    contiguous ``GameEventFramesResponse`` would make a false claim.
    """
    if (
        expected_source_stream_id is not None
        and source.source_stream_id != expected_source_stream_id
    ):
        raise ObjectiveTimelineError("objective event source stream changed")
    if (
        expected_generation_id is not None
        and source.generation_id != expected_generation_id
    ):
        raise ObjectiveTimelineError("objective event generation changed")
    return tuple(
        frame.model_copy(deep=True)
        for frame in source.frames
        if getattr(frame.event, "phase", None) == "completion"
    )


__all__ = [
    "EventQueueRecord",
    "OBJECTIVE_PERSPECTIVE_EPOCH_ID",
    "ObjectiveEventSourceSlot",
    "ObjectiveTimelineError",
    "build_objective_combat_log_frames",
    "build_objective_game_event_frame",
    "build_objective_game_event_frame_from_source",
    "build_objective_game_event_frames",
    "exact_combat_log_barrier",
    "freeze_objective_event_source_slot",
    "select_completion_frames_for_replay",
]
