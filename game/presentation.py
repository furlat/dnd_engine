"""Finite Event capture and passive subjective target reduction for pygame."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import Mapping
from uuid import UUID

from dnd.actions import AttackEvent, JumpEvent, MovementEvent, ShoveEvent, SpellEvent
from dnd.blocks.base_item import ItemLocationStateEvent
from dnd.blocks.equipment import EquipmentEvent
from dnd.blocks.sensory import SensesSnapshot, reduce_senses_snapshot
from dnd.core.base_actions import ActionEvent, BaseCost
from dnd.core.base_object import PASSIVE_EVENT_REPLAY
from dnd.core.combat_log import CombatLogEntry
from dnd.core.base_conditions import ConditionApplicationEvent, ConditionRemovalEvent
from dnd.core.events import (
    DamageAppliedEvent,
    DamageRollResultEvent,
    D20Event,
    D20RollResultEvent,
    DeathEvent,
    DeathSaveEvent,
    EncounterEvent,
    EntityCreatedEvent,
    Event,
    EventPhase,
    EventQueue,
    EventType,
    ForcedMovementEvent,
    HealEvent,
    HealRollResultEvent,
    InstantDeathEvent,
    LifeStateChangeEvent,
    ReviveEvent,
    RoundEvent,
    SensoryUpdateEvent,
    SpatialChangeEvent,
    SpatialChangeType,
    StepMovementEvent,
    TakeDamageEvent,
    TurnEvent,
    WorldInitializedEvent,
    WorldObjectState,
    WorldTileState,
)
from dnd.core.item_types import ItemLocation, ItemPresentationState
from dnd.subjective_combat_log import project_combat_log
from dnd.types.senses import PerceivedContact
from dnd.types.world_placement import WorldObjectPlacement
from game.event_record import RecordedEvent
from game.actor_facts import ActorState, ConditionFact, actor_fact_owner, actor_from_birth, apply_actor_fact


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
    battlefield_id: str
    door_uuid: UUID | None
    standing_torch_uuid: UUID | None
    objective_rows: tuple[ObjectiveRow, ...]
    subjective_rows: tuple[SubjectiveTextRow, ...]
    admitted: tuple[tuple[int, RecordedEvent], ...]
    dispositions: tuple[tuple[int, Disposition], ...]
    conditions: tuple[ConditionFact, ...] = ()
    admissions: tuple[ActorAdmission, ...] = ()


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
    actors: dict[UUID, ActorState] = field(default_factory=dict)
    current_actor_uuid: UUID | None = None
    round_number: int = 0


@dataclass(frozen=True, slots=True)
class ActorAdmission:
    """Actor state at an actual observation version in the received lineage."""

    event_uuid: UUID
    actor: ActorState
    contact: PerceivedContact | None


@dataclass(frozen=True, slots=True)
class CompletedLineage:
    """One real causal root and its retained completed descendants.

    Events retain consumed facts, not executable value/handler graphs. Raw
    version identities remain available separately from these terminal values.
    """

    generation: UUID
    observer_uuid: UUID
    root: RecordedEvent
    events: tuple[RecordedEvent, ...]
    objective_rows: tuple[ObjectiveRow, ...]
    start_cursor: int
    end_cursor: int
    conditions: tuple[ConditionFact, ...] = ()
    dispositions: tuple[tuple[UUID, Disposition], ...] = ()
    admissions: tuple[ActorAdmission, ...] = ()


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
    event: Event,
    *,
    observer_uuid: UUID,
    battlefield_id: str,
) -> bool:
    if event.phase is not EventPhase.COMPLETION:
        return False
    if isinstance(event, EntityCreatedEvent):
        return event.entity_uuid == observer_uuid
    if isinstance(event, (TurnEvent, RoundEvent, EncounterEvent)):
        return True
    owner = actor_fact_owner(event)
    if owner is not None:
        observer = str(observer_uuid)
        return owner == observer_uuid or (
            observer in event.identified_entity_observer_uuids.get(str(owner), set())
            and observer in event.located_entity_observer_uuids.get(str(owner), set())
        )
    if not _safe_to_detach(event):
        return False
    if type(event) is WorldInitializedEvent:
        return event.battlefield_id == battlefield_id
    if type(event) is ItemLocationStateEvent:
        return (
            event.location is ItemLocation.FLOOR
            and event.world_placement is not None
        )
    if type(event) is SpatialChangeEvent:
        return (
            event.change_type is SpatialChangeType.OBJECT_CHANGED
            and event.event_type.value == "spatial_object_changed"
        )
    if type(event) is SensoryUpdateEvent:
        return event.observer_uuid == observer_uuid
    return False


def capture_interval(
    *,
    name: str,
    start_cursor: int,
    end_cursor: int,
    observer_uuid: UUID,
    battlefield_id: str,
    door_uuid: UUID | None = None,
    standing_torch_uuid: UUID | None = None,
) -> IntervalEnvelope:
    """Synchronously copy one exact already-committed EventQueue interval."""
    generation = EventQueue.generation_id()
    cursor = EventQueue.event_cursor()
    if not 0 <= start_cursor <= end_cursor <= cursor:
        raise ValueError("invalid EventQueue interval cursors")
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
    admitted_original: list[tuple[int, Event]] = []
    dispositions: list[tuple[int, Disposition]] = []
    subjective: list[SubjectiveTextRow] = []
    for index, event in indexed:
        is_admitted = _admitted(
            event,
            observer_uuid=observer_uuid,
            battlefield_id=battlefield_id,
        )
        if is_admitted:
            copied = (_retained_event(event, observer_uuid)
                      if isinstance(event, (TurnEvent, RoundEvent, EncounterEvent)) or actor_fact_owner(event) is not None
                      else event.model_copy(deep=True))
            admitted.append((index, copied))
            admitted_original.append((index, event))
            disposition = (
                Disposition.STATE_ONLY
                if isinstance(event, (EntityCreatedEvent, SensoryUpdateEvent, TurnEvent, RoundEvent, EncounterEvent))
                or actor_fact_owner(event) is not None
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
        battlefield_id=battlefield_id,
        door_uuid=door_uuid,
        standing_torch_uuid=standing_torch_uuid,
        objective_rows=tuple(_objective_row(index, event) for index, event in indexed),
        subjective_rows=tuple(subjective),
        admitted=tuple(admitted),
        dispositions=tuple(dispositions),
        conditions=tuple(fact for _, event in admitted_original if (fact := _condition_fact(event)) is not None),
        admissions=(_capture_actor_admissions(
            tuple(EventQueue.iter_events_since(0)), tuple(admitted_original), observer_uuid, frozenset(),
        ) if admitted_original else ()),
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


def apply_world_fact(target: PresentationTarget, event: Event) -> None:
    """Fold recorded world after-values without querying native world owners."""
    if isinstance(event, WorldInitializedEvent):
        target.world = event
        target.tiles = {tile.position: tile for tile in event.tiles}
        target.objects = {row.item.item_uuid: row for row in event.objects}
    elif isinstance(event, ItemLocationStateEvent) and event.location is ItemLocation.FLOOR:
        if event.world_placement is None:
            raise ValueError("floor item fact requires its recorded placement")
        existing = target.objects.get(event.item_state.item_uuid)
        target.objects[event.item_state.item_uuid] = WorldObjectState(
            placement=event.world_placement, item=event.item_state,
            contained_items=existing.contained_items if existing is not None else (),
        )
    elif isinstance(event, SpatialChangeEvent) and event.change_type is SpatialChangeType.OBJECT_CHANGED:
        existing = target.objects.get(event.object_uuid) if event.object_uuid is not None else None
        if existing is None:
            return
        values: dict[str, object] = {"boundary_structure": event.object_boundary_structure}
        for key, value in (
            ("name", event.object_name), ("map_char", event.object_map_char),
            ("is_open", event.object_is_open), ("blocks_movement", event.object_blocks_movement),
            ("blocks_optics", event.object_blocks_optics),
            ("blocks_propagation", event.object_blocks_propagation),
        ):
            if value is not None:
                values[key] = value
        target.objects[existing.item.item_uuid] = existing.model_copy(update={
            "placement": event.placement or existing.placement,
            "item": existing.item.model_copy(update=values),
        })
    else:
        return
    if target.door_uuid is not None and (door := target.objects.get(target.door_uuid)) is not None:
        target.door_placement = door.placement
        target.door_is_open = door.item.is_open
    if target.standing_torch_uuid is not None:
        fixture = target.objects.get(target.standing_torch_uuid)
        if fixture is not None:
            target.standing_torch_state = fixture.item


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
    condition_facts = {fact.event_uuid: fact for fact in envelope.conditions}
    admissions: dict[UUID, list[ActorAdmission]] = {}
    for row in envelope.admissions:
        admissions.setdefault(row.event_uuid, []).append(row)
    for index, event in envelope.admitted:
        for row in admissions.get(event.uuid, ()):
            _admit_actor(target, row)
        if event.canceled:
            continue
        owner = actor_fact_owner(event)
        if owner is not None:
            actor = target.actors.get(owner)
            if actor is not None:
                target.actors[owner] = apply_actor_fact(actor, event, condition_facts.get(event.uuid))
            dispositions[index] = Disposition.STATE_ONLY
            continue
        if isinstance(event, EntityCreatedEvent):
            # Composition is folded into observed admissions, never revealed
            # merely because a private birth exists in the recorded interval.
            dispositions[index] = Disposition.STATE_ONLY
        elif type(event) is WorldInitializedEvent:
            apply_world_fact(target, event)
            if envelope.door_uuid is not None:
                door = target.objects.get(envelope.door_uuid)
                if door is None:
                    raise RuntimeError("admitted world lacks the exact door")
                target.door_placement = door.placement
                target.door_is_open = door.item.is_open
            if envelope.standing_torch_uuid is not None:
                fixture = target.objects.get(envelope.standing_torch_uuid)
                if fixture is None:
                    raise RuntimeError("admitted world lacks the exact standing fixture")
                target.standing_torch_state = fixture.item
            pending.add(index)
        elif type(event) is ItemLocationStateEvent:
            apply_world_fact(target, event)
            pending.add(index)
        elif type(event) is SpatialChangeEvent:
            apply_world_fact(target, event)
            pending.add(index)
        elif type(event) is SensoryUpdateEvent:
            _reduce_sensory_fact(target, event)
            dispositions[index] = Disposition.STATE_ONLY
        elif isinstance(event, (TurnEvent, RoundEvent, EncounterEvent)):
            _reduce_turn_fact(target, event)
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


def copy_target(target: PresentationTarget) -> PresentationTarget:
    """Own the mutable indexes at one reduction position, sharing cold facts."""
    return replace(
        target,
        tiles=dict(target.tiles),
        objects=dict(target.objects),
        actors=dict(target.actors),
        senses=_copy_snapshot(target.senses),
    )


def _reduce_sensory_fact(target: PresentationTarget, event: SensoryUpdateEvent) -> None:
    """Apply the observer's native after-values, retaining last visual placement."""
    if event.observer_uuid != target.observer_uuid:
        return
    event.validate_replay_payload()
    target.senses = reduce_senses_snapshot(target.observer_uuid, target.senses, event)
    if event.observer_position_changed and target.observer_uuid in target.actors:
        observer = target.actors[target.observer_uuid]
        target.actors[observer.uuid] = replace(observer, last_visual_position=event.observer_position)
    for identity, contact in event.entity_contacts_changed.items():
        actor = target.actors.get(identity)
        if actor is not None and contact.visual:
            target.actors[identity] = replace(actor, last_visual_position=contact.position)


def _reduce_turn_fact(target: PresentationTarget, event: TurnEvent | RoundEvent | EncounterEvent) -> None:
    if isinstance(event, TurnEvent):
        target.round_number = event.round_number
        # Encounter transitions remain available; the acting identity follows
        # the existing event-time grant, as in the subjective encounter mapper.
        identified = (event.entity_uuid == target.observer_uuid
                      or str(target.observer_uuid) in event.identified_entity_observer_uuids.get(
                          str(event.entity_uuid), set()))
        target.current_actor_uuid = (event.entity_uuid
                                     if event.event_type is EventType.TURN_START and identified else None)
    elif isinstance(event, RoundEvent):
        target.round_number = event.round_number
    elif event.event_type is EventType.ENCOUNTER_END:
        target.current_actor_uuid = None


def seed_actors(
    target: PresentationTarget,
    births: tuple[EntityCreatedEvent, ...],
) -> PresentationTarget:
    """Establish the selected known actors at the explicit startup baseline.

    The caller supplies unchanged composition facts for this explicit startup
    baseline. Contact acquisition is not treated as observation of their birth
    or as a general rule for disclosing later actor state.
    """
    if target.senses is None:
        raise ValueError("actor startup requires an observer baseline")
    result = copy_target(target)
    for birth in births:
        if birth.phase is not EventPhase.COMPLETION:
            raise ValueError("actor startup requires completed composition")
        if birth.entity_uuid != target.observer_uuid:
            contact = target.senses.entities.get(birth.entity_uuid)
            if contact is None or not contact.visual:
                raise ValueError("selected actor startup requires a known visual contact")
        result.actors[birth.entity_uuid] = replace(
            actor_from_birth(birth),
            last_visual_position=(target.senses.position if birth.entity_uuid == target.observer_uuid
                                  else target.senses.entities[birth.entity_uuid].position),
        )
    return result


def _event_header(event: Event) -> Event:
    """Project this finite Event schema without copying a subclass's live payload.

    Condition details live in ConditionFact. Unsupported payloads retain this
    same causal/diagnostic header and an explicit unsupported disposition.
    Passive validation also preserves absent turn metadata during live capture.
    """
    header = Event.model_validate(dict(
        name=event.name, uuid=event.uuid, source_entity_uuid=event.source_entity_uuid,
        source_entity_name=event.source_entity_name,
        target_entity_uuid=event.target_entity_uuid, target_entity_name=event.target_entity_name,
        use_register=False, lineage_uuid=event.lineage_uuid, timestamp=event.timestamp,
        event_type=event.event_type, phase=event.phase, modified=event.modified,
        canceled=event.canceled, canceled_from_phase=event.canceled_from_phase,
        parent_event=event.parent_event, turn_execution_id=event.turn_execution_id,
        status_message=event.status_message, outcome_code=event.outcome_code,
        outcome_source_entity_uuid=event.outcome_source_entity_uuid,
        is_first=event.is_first, is_last=event.is_last,
        lineage_children_events=list(event.lineage_children_events),
        children_events=list(event.children_events), parent_lineage=event.parent_lineage,
        children_lineages=list(event.children_lineages),
        identified_entity_observer_uuids={
            identity: set(observers) for identity, observers in event.identified_entity_observer_uuids.items()
        },
        located_entity_observer_uuids={
            identity: set(observers) for identity, observers in event.located_entity_observer_uuids.items()
        },
        located_position_observer_uuids={
            position: set(observers) for position, observers in event.located_position_observer_uuids.items()
        },
    ), context=PASSIVE_EVENT_REPLAY)
    header._effective_handler_presentations = event.effective_handler_presentations
    return header


def _retained_event(event: Event, observer_uuid: UUID) -> Event:
    """Copy the selected event families without constructing registered models."""
    projected_log = project_combat_log(
        event.combat_log,
        controlled_entity_uuids=frozenset({str(observer_uuid)}),
        observer_entity_uuids=frozenset({str(observer_uuid)}),
    )
    if projected_log is not None:
        # CombatLogEntry.data is JSON-valued evidence. Normalize its arrays at
        # capture so original and restored inputs have the same value meaning.
        projected_log = CombatLogEntry.model_validate_json(projected_log.model_dump_json())
    common = {"use_register": False, "context": None, "combat_log": projected_log}
    match event:
        case SpellEvent() | AttackEvent():
            copied = event.model_copy(update={
                **common, "attack_bonus": None, "ac": None, "damages": None,
            })
        case TakeDamageEvent() | DamageAppliedEvent():
            copied = event.model_copy(update={**common, "damages": []})
        case DamageRollResultEvent():
            packets = [packet.model_copy(update={
                "damage": packet.damage.model_copy(update={
                    "use_register": False, "context": None, "damage_bonus": None,
                }),
            }) for packet in event.damage_packets]
            copied = event.model_copy(update={**common, "context": {}, "damage_packets": packets})
        case D20RollResultEvent():
            copied = event.model_copy(update={**common, "context": {}, "bonus": None})
        case HealRollResultEvent():
            copied = event.model_copy(update={**common, "context": {}})
        case D20Event():
            copied = event.model_copy(update={
                **common, "dice": None, "dc": event.get_dc(),
                "bonus": event.dice_roll.bonus if event.dice_roll is not None else None,
            })
        case ShoveEvent():
            copied = event.model_copy(update={**common, "shover_athletics": None})
        case MovementEvent() | JumpEvent() | StepMovementEvent() | ForcedMovementEvent():
            copied = event.model_copy(update=common)
        case SensoryUpdateEvent() | LifeStateChangeEvent() | DeathEvent() | HealEvent():
            copied = event.model_copy(update=common)
        case DeathSaveEvent() | ReviveEvent() | InstantDeathEvent() | TurnEvent() | RoundEvent() | EncounterEvent():
            copied = event.model_copy(update=common)
        case SpatialChangeEvent(change_type=(
            SpatialChangeType.PERCEIVABILITY_CHANGED | SpatialChangeType.ENTITY_ENTERED
            | SpatialChangeType.ENTITY_LEFT | SpatialChangeType.MOVEMENT_COLLISION
            | SpatialChangeType.LIGHT_CHANGED | SpatialChangeType.OBJECT_CHANGED
        )):
            copied = event.model_copy(update=common)
        case ActionEvent() if type(event) is ActionEvent:
            copied = event.model_copy(update=common)
        case EquipmentEvent():
            copied = event.model_copy(update=common)
        case ItemLocationStateEvent(location=ItemLocation.INVENTORY | ItemLocation.EQUIPMENT | ItemLocation.FLOOR):
            copied = event.model_copy(update=common)
        case _:
            copied = _event_header(event).model_copy(update=common)
    # DiceRoll contains concrete values; model_copy avoids its registering
    # constructor. Live value/Damage graphs were removed before this deep copy.
    if isinstance(copied, ActionEvent):
        copied = copied.model_copy(update={"costs": [
            BaseCost.model_validate_json(cost.model_dump_json()) for cost in copied.costs
        ]})
    return copied.model_copy(deep=True)


def _actor_participants(event: Event) -> tuple[UUID, ...]:
    """Existing families distinguish actor subjects from neutral event sources."""
    match event:
        case TurnEvent() | RoundEvent() | EncounterEvent() | SensoryUpdateEvent():
            return ()
        case SpatialChangeEvent(change_type=SpatialChangeType.LIGHT_CHANGED):
            # light_changed() stores the affected tile UUID in entity_uuid.
            # Its sensory children provide observer-specific light after-values.
            return ()
        case LifeStateChangeEvent() | DeathEvent() | ReviveEvent() | InstantDeathEvent():
            return (event.entity_uuid,)
        case SpatialChangeEvent(change_type=(
            SpatialChangeType.PERCEIVABILITY_CHANGED | SpatialChangeType.ENTITY_ENTERED
            | SpatialChangeType.ENTITY_LEFT | SpatialChangeType.MOVEMENT_COLLISION
        )):
            return (event.entity_uuid,) if event.entity_uuid is not None else ()
        case ConditionApplicationEvent() | ConditionRemovalEvent() | TakeDamageEvent() | DamageAppliedEvent() | HealEvent():
            return (event.target_entity_uuid,) if event.target_entity_uuid is not None else ()
        case ActionEvent() | StepMovementEvent() | ForcedMovementEvent() | D20Event() | D20RollResultEvent() | DamageRollResultEvent() | HealRollResultEvent():
            return tuple(identity for identity in (event.source_entity_uuid, event.target_entity_uuid)
                         if identity is not None)
        case _:
            # Unsupported payloads expose only the already-subjective log and
            # diagnostic header; their unknown source schema cannot name actors.
            return ()


def _condition_fact(event: Event) -> ConditionFact | None:
    if not isinstance(event, (ConditionApplicationEvent, ConditionRemovalEvent)):
        return None
    return ConditionFact(
        event_uuid=event.uuid, condition_uuid=event.condition.uuid,
        name=event.condition.name or "Condition", category=event.condition.condition_category,
        behavior_id=event.behavior_id, resulting_max_hp=event.resulting_max_hp,
        resulting_ac=event.resulting_ac,
    )


def _capture_actor_admissions(
    history: tuple[tuple[int, Event], ...], indexed: tuple[tuple[int, Event], ...],
    observer_uuid: UUID, known_actor_uuids: frozenset[UUID],
) -> tuple[ActorAdmission, ...]:
    """Fold private recorded facts, disclosing only actors actually observed here."""
    actors: dict[UUID, ActorState] = {}
    contacts: dict[UUID, PerceivedContact] = {}
    observer_position: tuple[int, int] | None = None
    selected = {event.uuid for _, event in indexed}
    admitted = set(known_actor_uuids)
    result: list[ActorAdmission] = []
    observer = str(observer_uuid)
    for index, event in history:
        if index > indexed[-1][0]:
            break
        completed = event.phase is EventPhase.COMPLETION and not event.canceled
        if completed and isinstance(event, EntityCreatedEvent):
            actors[event.entity_uuid] = actor_from_birth(event)
        sensory = completed and isinstance(event, SensoryUpdateEvent) and event.observer_uuid == observer_uuid
        acquired: set[UUID] = set()
        if sensory:
            assert isinstance(event, SensoryUpdateEvent)
            acquired = set(event.entity_contacts_changed) - contacts.keys()
            observer_position = event.observer_position
            for identity in event.entity_contacts_removed:
                contacts.pop(identity, None)
            contacts.update(event.entity_contacts_changed)
        if event.uuid in selected and not event.canceled:
            candidates = set(_actor_participants(event))
            owner = actor_fact_owner(event)
            if owner is not None:
                candidates.add(owner)
            observed: set[UUID] = set()
            if sensory:
                assert isinstance(event, SensoryUpdateEvent)
                observed.update(event.entity_contacts_changed)
                observed.add(observer_uuid)
                candidates.update(observed)
            for identity in sorted((candidates - admitted) | acquired, key=str):
                if identity not in actors:
                    continue
                identified = observer in event.identified_entity_observer_uuids.get(str(identity), set())
                located = observer in event.located_entity_observer_uuids.get(str(identity), set())
                if identity != observer_uuid and identity not in observed and not (identified and located):
                    continue
                contact = contacts.get(identity) if identity != observer_uuid else None
                if identity != observer_uuid and contact is None:
                    raise ValueError("observed actor requires its recorded sensory contact")
                position = (observer_position if identity == observer_uuid
                            else contact.position if contact is not None and contact.visual else None)
                result.append(ActorAdmission(
                    event.uuid, replace(actors[identity], last_visual_position=position),
                    contact.model_copy(deep=True) if contact is not None else None,
                ))
                admitted.add(identity)
        if completed:
            owner = actor_fact_owner(event)
            if owner is not None and owner in actors:
                actors[owner] = apply_actor_fact(actors[owner], event, _condition_fact(event))
    return tuple(result)


def capture_lineage(
    root: Event, *, observer_uuid: UUID, known_actor_uuids: frozenset[UUID] = frozenset(),
) -> CompletedLineage:
    """Retain a closed native lineage privately after its public operation.

    Follow existing child lineages. Operation cursor ranges and callback batches
    do not establish a render unit. Observer grants remain exact facts in this
    private record; the outgoing projection decides which payloads and geometry
    an observer receives. Unknown participants must not erase observed children.
    """
    generation = EventQueue.generation_id()
    history = tuple(EventQueue.iter_events_since(0))
    latest = {event.lineage_uuid: event for _, event in history}
    pending = [root]
    nodes: dict[UUID, Event] = {}
    while pending:
        event = pending.pop()
        if event.lineage_uuid in nodes:
            continue
        if event.phase not in (EventPhase.COMPLETION, EventPhase.CANCEL):
            raise ValueError("lineage requires terminal root and child facts")
        if event.phase is EventPhase.CANCEL:
            # Cancellation keeps raw parent/child version references; it does
            # not run completion's stable-lineage normalization. Resolve those
            # existing references without changing the retained event facts.
            children = []
            for identity in dict.fromkeys(event.lineage_children_events + event.children_events):
                child = EventQueue.get_event_by_uuid(identity)
                if child is None:
                    raise ValueError("canceled lineage is missing a required child")
                children.append(latest[child.lineage_uuid])
        else:
            children = event.get_children_events()
            if set(event.children_lineages) != {child.lineage_uuid for child in children}:
                raise ValueError("lineage is missing a required child")
        nodes[event.lineage_uuid] = event
        pending.extend(children)

    indexed = tuple(
        (index, event)
        for index, event in history
        if event.lineage_uuid in nodes
    )
    if not indexed or root.uuid not in {event.uuid for _, event in indexed}:
        raise ValueError("lineage root is absent from the current EventQueue")
    retained = tuple(
        _retained_event(event, observer_uuid)
        for _, event in indexed
        if event.uuid == nodes[event.lineage_uuid].uuid
    )
    retained_root = next(event for event in retained if event.uuid == root.uuid)
    conditions = tuple(fact for _, event in indexed
                       if event.uuid == nodes[event.lineage_uuid].uuid
                       and (fact := _condition_fact(event)) is not None)
    condition_ids = {fact.event_uuid for fact in conditions}
    dispositions = tuple(
        (event.uuid, Disposition.UNSUPPORTED) for event in retained
        if type(event) is Event and event.uuid not in condition_ids
    )
    if generation != EventQueue.generation_id():
        raise RuntimeError("EventQueue generation changed during lineage capture")
    return CompletedLineage(
        generation=generation,
        observer_uuid=observer_uuid,
        root=retained_root,
        events=retained,
        objective_rows=tuple(_objective_row(index, event) for index, event in indexed),
        start_cursor=indexed[0][0],
        end_cursor=indexed[-1][0] + 1,
        conditions=conditions,
        dispositions=dispositions,
        admissions=_capture_actor_admissions(history, indexed, observer_uuid, known_actor_uuids),
    )


def lineage_branch(lineage: CompletedLineage, root: Event) -> CompletedLineage:
    """A retained subtree view, preserving actual event and parent identities."""
    by_lineage = {event.lineage_uuid: event for event in lineage.events}
    pending = [root.lineage_uuid]
    selected: set[UUID] = set()
    while pending:
        identity = pending.pop()
        if identity in selected:
            continue
        selected.add(identity)
        pending.extend(by_lineage[identity].children_lineages)
    events = tuple(event for event in lineage.events if event.lineage_uuid in selected)
    identities = {event.uuid for event in events}
    rows = tuple(row for row in lineage.objective_rows if row.lineage_uuid in selected)
    version_ids = {row.event_uuid for row in rows}
    return replace(lineage, root=root, events=events, objective_rows=rows,
                   start_cursor=rows[0].source_index, end_cursor=rows[-1].source_index + 1,
                   conditions=tuple(row for row in lineage.conditions if row.event_uuid in identities),
                   dispositions=tuple(row for row in lineage.dispositions if row[0] in identities),
                   admissions=tuple(row for row in lineage.admissions if row.event_uuid in version_ids))


def _admit_actor(target: PresentationTarget, admission: ActorAdmission) -> None:
    """Apply the actor's recorded state at this actual observation boundary."""
    target.actors[admission.actor.uuid] = admission.actor
    if admission.contact is not None and target.senses is not None:
        target.senses.entities[admission.actor.uuid] = admission.contact.model_copy(deep=True)


def stage_actors(target: PresentationTarget, admissions: tuple[ActorAdmission, ...]) -> PresentationTarget:
    """Add the specified observed actors to a fresh presentation value."""
    result = copy_target(target)
    for admission in admissions:
        if admission.actor.uuid not in result.actors:
            _admit_actor(result, admission)
    return result


def stage_lineage(target: PresentationTarget, lineage: CompletedLineage) -> PresentationTarget:
    """Prepare newly admitted actors for binding without changing history's owner.

    The display still admits contacts at their recorded event. This preparation
    supplies the bodies and entry contacts needed to compile that first lineage.
    """
    if target.generation != lineage.generation or target.observer_uuid != lineage.observer_uuid:
        raise ValueError("lineage belongs to a different presentation baseline")
    return stage_actors(target, lineage.admissions)


def reduce_lineage(target: PresentationTarget, lineage: CompletedLineage) -> PresentationTarget:
    """Apply retained results to an owned successor, at either history position."""
    if target.generation != lineage.generation or target.observer_uuid != lineage.observer_uuid:
        raise ValueError("lineage belongs to a different presentation baseline")
    # Independent equipment roots can overlap in declaration/execution while
    # completing in order. Their earliest phase is not a consumed fact cursor.
    if lineage.end_cursor <= target.reducer_cursor:
        raise ValueError("completed lineage precedes this reduction position")
    result = copy_target(target)
    condition_facts = {fact.event_uuid: fact for fact in lineage.conditions}
    unsupported = {identity for identity, disposition in lineage.dispositions
                   if disposition is Disposition.UNSUPPORTED}
    source_indexes = {row.event_uuid: row.source_index for row in lineage.objective_rows}
    admissions = iter(sorted(lineage.admissions, key=lambda row: source_indexes[row.event_uuid]))
    admission = next(admissions, None)
    for event in lineage.events:
        while admission is not None and source_indexes[admission.event_uuid] <= source_indexes[event.uuid]:
            _admit_actor(result, admission)
            admission = next(admissions, None)
        if event.canceled or event.uuid in unsupported:
            continue
        owner = actor_fact_owner(event)
        if owner is not None:
            actor = result.actors.get(owner)
            if actor is None:
                if isinstance(event, (AttackEvent, EquipmentEvent)):
                    continue
                raise ValueError("actor fact requires its retained owner")
            result.actors[owner] = apply_actor_fact(actor, event, condition_facts.get(event.uuid))
            continue
        match event:
            case SensoryUpdateEvent():
                _reduce_sensory_fact(result, event)
            case ActionEvent() | TakeDamageEvent() | D20RollResultEvent() | DamageRollResultEvent() | HealRollResultEvent() | D20Event():
                # These facts explain causality. Only the committed applied
                # packet changes HP, so aggregate totals cannot apply it twice.
                pass
            case SpatialChangeEvent() | ItemLocationStateEvent(location=ItemLocation.FLOOR):
                apply_world_fact(result, event)
            case DeathEvent() | DeathSaveEvent() | ReviveEvent() | InstantDeathEvent():
                # Keep the cause. The actual life and sensory children supply
                # the successor facts; do not infer them from death/occupancy.
                pass
            case TurnEvent() | RoundEvent() | EncounterEvent():
                _reduce_turn_fact(result, event)
            case StepMovementEvent() | ForcedMovementEvent():
                # Senses supplies committed positions. Turn/round facts retain
                # the real engine clock; presentation does not tick conditions.
                pass
            case _:
                raise NotImplementedError(f"lineage reduction does not consume {type(event).__name__}")
    result.reducer_cursor = lineage.end_cursor
    return result


__all__ = [
    "ActorAdmission",
    "ActorState",
    "CompletedLineage",
    "ConditionFact",
    "Disposition",
    "IntervalEnvelope",
    "IntervalTerminal",
    "ObjectiveRow",
    "PresentationTarget",
    "ReducedInterval",
    "SubjectiveTextRow",
    "capture_interval",
    "capture_lineage",
    "copy_target",
    "reduce_interval",
    "reduce_lineage",
    "seed_actors",
    "stage_actors",
    "stage_lineage",
    "settle_dispositions",
]
