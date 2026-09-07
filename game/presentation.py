"""Finite Event capture and passive subjective target reduction for pygame."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Mapping
from uuid import UUID

from dnd.blocks.base_item import ItemLocationStateEvent
from dnd.blocks.sensory import SensesSnapshot, reduce_senses_snapshot
from dnd.core.events import (
    Event,
    EventPhase,
    EventQueue,
    SensoryUpdateEvent,
    SpatialChangeEvent,
    SpatialChangeType,
    WorldInitializedEvent,
    WorldObjectState,
    WorldTileState,
)
from dnd.core.item_types import ItemLocation, ItemPresentationState
from dnd.subjective_combat_log import project_combat_log
from dnd.types.world_placement import WorldObjectPlacement


class Disposition(StrEnum):
    """Honest final or pending presentation disposition for one source row."""

    PENDING_DISPLAY = "pending_display"
    REPRESENTED = "represented"
    STATE_ONLY = "state_only"
    NOT_DISCLOSED = "not_disclosed"
    UNSUPPORTED = "unsupported"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class ObjectiveRow:
    """Primitive diagnostic identity for one stored Event version."""

    source_index: int
    event_uuid: UUID
    lineage_uuid: UUID
    parent_event: UUID | None
    parent_lineage: UUID | None
    event_type: str
    event_class: str
    phase: str
    source_uuid: UUID
    source_name: str | None
    target_uuid: UUID | None
    target_name: str | None
    turn_execution_id: UUID | None
    status: str | None
    outcome: str | None
    canceled: bool
    modified: bool


@dataclass(frozen=True, slots=True)
class SubjectiveTextRow:
    """Already-projected subjective text retained during capture."""

    source_index: int
    text: str


@dataclass(frozen=True, slots=True)
class IntervalEnvelope:
    """One complete immutable cursor interval crossing the async seam."""

    name: str
    generation: UUID
    start_cursor: int
    end_cursor: int
    observer_uuid: UUID
    seed_cursor: int | None
    seed_snapshot: SensesSnapshot | None
    battlefield_id: str
    door_uuid: UUID
    standing_torch_uuid: UUID
    objective_rows: tuple[ObjectiveRow, ...]
    subjective_rows: tuple[SubjectiveTextRow, ...]
    admitted: tuple[tuple[int, Event], ...]
    dispositions: tuple[tuple[int, Disposition], ...]


@dataclass(slots=True)
class PresentationTarget:
    """Read-optimized indexes over detached engine values."""

    generation: UUID
    observer_uuid: UUID
    world: WorldInitializedEvent | None = None
    tiles: dict[tuple[int, int], WorldTileState] = field(default_factory=dict)
    objects: dict[UUID, WorldObjectState] = field(default_factory=dict)
    door_uuid: UUID | None = None
    door_placement: WorldObjectPlacement | None = None
    door_is_open: bool | None = None
    standing_torch_uuid: UUID | None = None
    standing_torch_state: ItemPresentationState | None = None
    senses: SensesSnapshot | None = None
    reducer_cursor: int = 0


@dataclass(frozen=True, slots=True)
class ReducedInterval:
    """Reduction result awaiting one exact displayed frame."""

    envelope: IntervalEnvelope
    dispositions: Mapping[int, Disposition]
    pending_display: frozenset[int]


@dataclass(frozen=True, slots=True)
class IntervalTerminal:
    """One terminal emitted only after display and finite hold."""

    generation: UUID
    name: str
    start_cursor: int
    end_cursor: int
    settled: bool
    failed: bool
    cancelled: bool
    failure: str | None = None


def _objective_row(index: int, event: Event) -> ObjectiveRow:
    return ObjectiveRow(
        source_index=index,
        event_uuid=event.uuid,
        lineage_uuid=event.lineage_uuid,
        parent_event=event.parent_event,
        parent_lineage=event.parent_lineage,
        event_type=event.event_type.value,
        event_class=type(event).__name__,
        phase=event.phase.value,
        source_uuid=event.source_entity_uuid,
        source_name=event.source_entity_name,
        target_uuid=event.target_entity_uuid,
        target_name=event.target_entity_name,
        turn_execution_id=event.turn_execution_id,
        status=event.status_message,
        outcome=event.outcome_code,
        canceled=event.canceled,
        modified=event.modified,
    )


def _safe_to_detach(event: Event) -> bool:
    return (
        event.context is None
        and event.combat_log is None
        and not event.effective_handler_presentations
    )


def _admitted(
    index: int,
    event: Event,
    *,
    observer_uuid: UUID,
    seed_cursor: int | None,
    battlefield_id: str,
    door_uuid: UUID,
    standing_torch_uuid: UUID,
) -> bool:
    if event.phase is not EventPhase.COMPLETION or not _safe_to_detach(event):
        return False
    if type(event) is WorldInitializedEvent:
        return event.battlefield_id == battlefield_id
    if type(event) is ItemLocationStateEvent:
        return (
            event.item_state.item_uuid == standing_torch_uuid
            and event.item_state.item_id == "environment.standing_torch"
            and event.location is ItemLocation.FLOOR
            and event.world_placement is not None
        )
    if type(event) is SpatialChangeEvent:
        return (
            event.change_type is SpatialChangeType.OBJECT_CHANGED
            and event.event_type.value == "spatial_object_changed"
            and event.object_uuid == door_uuid
        )
    if type(event) is SensoryUpdateEvent:
        return (
            event.observer_uuid == observer_uuid
            and seed_cursor is not None
            and index >= seed_cursor
        )
    return False


def capture_interval(
    *,
    name: str,
    start_cursor: int,
    end_cursor: int,
    observer_uuid: UUID,
    battlefield_id: str,
    door_uuid: UUID,
    standing_torch_uuid: UUID,
    seed_cursor: int | None = None,
    seed_snapshot: SensesSnapshot | None = None,
) -> IntervalEnvelope:
    """Synchronously copy one exact already-committed EventQueue interval."""
    generation = EventQueue.generation_id()
    cursor = EventQueue.event_cursor()
    if not 0 <= start_cursor <= end_cursor <= cursor:
        raise ValueError("invalid EventQueue interval cursors")
    if seed_snapshot is not None:
        if seed_cursor is None:
            raise ValueError("observer seed snapshot requires its source cursor")
        if not start_cursor <= seed_cursor <= end_cursor:
            raise ValueError("observer seed cursor lies outside the interval")
    indexed = tuple(
        (index, event)
        for index, event in EventQueue.iter_events_since(start_cursor)
        if index < end_cursor
    )
    if tuple(index for index, _ in indexed) != tuple(range(start_cursor, end_cursor)):
        raise RuntimeError("EventQueue interval is partial or duplicated")
    if generation != EventQueue.generation_id():
        raise RuntimeError("EventQueue generation changed during capture")

    admitted: list[tuple[int, Event]] = []
    dispositions: list[tuple[int, Disposition]] = []
    subjective: list[SubjectiveTextRow] = []
    for index, event in indexed:
        if (
            type(event) is SensoryUpdateEvent
            and event.observer_uuid == observer_uuid
            and seed_cursor is not None
            and index < seed_cursor
        ):
            raise RuntimeError("selected-observer sensory update precedes startup seed")
        is_admitted = _admitted(
            index,
            event,
            observer_uuid=observer_uuid,
            seed_cursor=seed_cursor,
            battlefield_id=battlefield_id,
            door_uuid=door_uuid,
            standing_torch_uuid=standing_torch_uuid,
        )
        if is_admitted:
            copied = event.model_copy(deep=True)
            admitted.append((index, copied))
            disposition = (
                Disposition.STATE_ONLY
                if type(event) is SensoryUpdateEvent
                else Disposition.PENDING_DISPLAY
            )
        else:
            disposition = Disposition.UNSUPPORTED
        dispositions.append((index, disposition))
        projected = project_combat_log(
            event.combat_log,
            controlled_entity_uuids=frozenset({str(observer_uuid)}),
            observer_entity_uuids=frozenset({str(observer_uuid)}),
        )
        if projected is not None:
            subjective.append(SubjectiveTextRow(index, projected.compact))

    return IntervalEnvelope(
        name=name,
        generation=generation,
        start_cursor=start_cursor,
        end_cursor=end_cursor,
        observer_uuid=observer_uuid,
        seed_cursor=seed_cursor,
        seed_snapshot=_copy_snapshot(seed_snapshot),
        battlefield_id=battlefield_id,
        door_uuid=door_uuid,
        standing_torch_uuid=standing_torch_uuid,
        objective_rows=tuple(_objective_row(index, event) for index, event in indexed),
        subjective_rows=tuple(subjective),
        admitted=tuple(admitted),
        dispositions=tuple(dispositions),
    )


def _copy_snapshot(snapshot: SensesSnapshot | None) -> SensesSnapshot | None:
    if snapshot is None:
        return None
    return SensesSnapshot(
        position=snapshot.position,
        visible=set(snapshot.visible),
        seen=set(snapshot.seen),
        entities={key: value.model_copy(deep=True) for key, value in snapshot.entities.items()},
        objects={key: value.model_copy(deep=True) for key, value in snapshot.objects.items()},
        effective_light_levels=dict(snapshot.effective_light_levels),
        paths_dirty=snapshot.paths_dirty,
        passive_perception=snapshot.passive_perception,
        sense_modes_hash=snapshot.sense_modes_hash,
        sense_modes=tuple(mode.model_copy(deep=True) for mode in snapshot.sense_modes),
        visual_access=snapshot.visual_access,
    )


def reduce_interval(
    target: PresentationTarget | None,
    envelope: IntervalEnvelope,
) -> tuple[PresentationTarget, ReducedInterval]:
    """Reduce admitted detached values in source order without live queries."""
    if target is None:
        target = PresentationTarget(
            generation=envelope.generation,
            observer_uuid=envelope.observer_uuid,
            door_uuid=envelope.door_uuid,
            standing_torch_uuid=envelope.standing_torch_uuid,
            senses=_copy_snapshot(envelope.seed_snapshot),
            reducer_cursor=envelope.start_cursor,
        )
    if target.generation != envelope.generation:
        raise RuntimeError("stale presentation interval generation")
    if target.observer_uuid != envelope.observer_uuid:
        raise RuntimeError("presentation observer changed")
    if target.reducer_cursor != envelope.start_cursor:
        raise RuntimeError("presentation interval is not contiguous")

    dispositions = dict(envelope.dispositions)
    pending: set[int] = set()
    for index, event in envelope.admitted:
        if type(event) is WorldInitializedEvent:
            target.world = event
            target.tiles = {tile.position: tile for tile in event.tiles}
            target.objects = {row.item.item_uuid: row for row in event.objects}
            door = target.objects.get(envelope.door_uuid)
            fixture = target.objects.get(envelope.standing_torch_uuid)
            if door is None or fixture is None:
                raise RuntimeError("admitted world lacks the exact door or standing fixture")
            target.door_placement = door.placement
            target.door_is_open = door.item.is_open
            target.standing_torch_state = fixture.item
            pending.add(index)
        elif type(event) is ItemLocationStateEvent:
            if event.world_placement is None:
                raise RuntimeError("admitted standing fixture lacks floor placement")
            target.standing_torch_state = event.item_state
            target.objects[event.item_state.item_uuid] = WorldObjectState(
                placement=event.world_placement,
                item=event.item_state,
            )
            pending.add(index)
        elif type(event) is SpatialChangeEvent:
            if event.placement is None or event.object_is_open is None:
                raise RuntimeError("admitted door change lacks a complete after-value")
            target.door_placement = event.placement
            target.door_is_open = event.object_is_open
            existing = target.objects.get(envelope.door_uuid)
            if existing is not None:
                target.objects[envelope.door_uuid] = existing.model_copy(update={
                    "placement": event.placement,
                    "item": existing.item.model_copy(update={"is_open": event.object_is_open}),
                })
            pending.add(index)
        elif type(event) is SensoryUpdateEvent:
            if target.senses is None:
                raise RuntimeError("sensory delta arrived without an observer seed")
            event.validate_replay_payload()
            target.senses = reduce_senses_snapshot(
                target.observer_uuid,
                target.senses,
                event,
            )
            dispositions[index] = Disposition.STATE_ONLY
        else:
            raise RuntimeError("capture admitted an unsupported Event subclass")
    target.reducer_cursor = envelope.end_cursor
    return target, ReducedInterval(
        envelope=envelope,
        dispositions=dispositions,
        pending_display=frozenset(pending),
    )


def settle_dispositions(
    reduced: ReducedInterval,
    *,
    represented: set[int],
    not_disclosed: set[int],
) -> dict[int, Disposition]:
    """Finalize only display obligations proven by the published frame."""
    if represented & not_disclosed:
        raise ValueError("one source cannot be represented and not disclosed")
    if represented | not_disclosed != set(reduced.pending_display):
        raise ValueError("display evidence does not cover every pending source")
    result = dict(reduced.dispositions)
    for index in represented:
        result[index] = Disposition.REPRESENTED
    for index in not_disclosed:
        result[index] = Disposition.NOT_DISCLOSED
    return result


__all__ = [
    "Disposition",
    "IntervalEnvelope",
    "IntervalTerminal",
    "ObjectiveRow",
    "PresentationTarget",
    "ReducedInterval",
    "SubjectiveTextRow",
    "capture_interval",
    "reduce_interval",
    "settle_dispositions",
]
