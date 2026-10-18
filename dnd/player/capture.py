"""Finite Event capture and passive subjective target reduction for pygame."""

from __future__ import annotations

from collections import ChainMap
from collections.abc import Collection, Iterable
from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import Mapping
from uuid import UUID

from dnd.actions import AttackEvent, JumpEvent, MovementEvent, TraverseConnectorEvent, ShoveEvent, SpellEvent
from dnd.blocks.base_item import ItemResourceChangeEvent, ItemHoldingsReleasedEvent, ItemLocationStateEvent
from dnd.blocks.equipment import EquipmentEvent
from dnd.core.sensory_fold import copy_senses_snapshot, reduce_senses_snapshot
from dnd.core.base_actions import ActionEvent, BaseCost
from dnd.core.combat_log import CombatLogEntry
from dnd.spells.abjuration import CounterspellReactionEvent
from dnd.core.base_object import PASSIVE_EVENT_REPLAY
from dnd.core.base_conditions import ConditionApplicationEvent, ConditionRemovalEvent, ConditionStateChangedEvent
from dnd.core.events import (
    SpellMasteryStudiedEvent, ConditionMembershipCommittedEvent, RestResourcesRecoveredEvent, PermanentFeatureUsedEvent, ActionApplicationCommittedEvent, MaximumHitPointReductionEvent, EffectApplicationEvent, ActionCostsCommittedEvent, RestCompletedEvent, SpellbookChangedEvent, SpellPreparationChangedEvent, HealingAppliedEvent, SpellDamageRollResultEvent,
    AreaReachEvent,
    DamageAppliedEvent,
    DamageRollResultEvent,
    D20Event,
    D20RollResultEvent,
    DeathEvent,
    DeathSaveEvent,
    EncounterEvent,
    ActorSheetEvent, EncounterStartEvent, EntityCreatedEvent, EntityFactionChangedEvent, InitiativeOrderChangedEvent,
    Event,
    EventPhase,
    EventQueue,
    EventType,
    ExposedFlameEvent,
    ForcedMovementEvent,
    PortalTransferEvent, MechanismActivationEvent, StandOfferEvent,
    HealEvent,
    HealRollResultEvent,
    InstantDeathEvent,
    ItemDestructionEvent,
    LifeStateChangeEvent,
    ReviveEvent,
    RoundEvent,
    SensoryUpdateEvent,
    SpatialChangeEvent,
    SpatialChangeType,
    SpatialEffectChangeEvent, SpatialEffectInteractionEvent,
    StepMovementEvent,
    TakeDamageEvent,
    TileElevationChangeEvent,
    TemporaryHitPointsChangedEvent,
    TurnEvent,
    WorldInitializedEvent,
    WorldModifiedEvent,
)
from dnd.core.item_types import ItemLocation
from dnd.subjective_combat_log import project_combat_log
from dnd.types.senses import PerceivedContact
from dnd.world_facts import copy_world_facts, apply_world_fact as apply_recorded_world_fact
from dnd.player.audience import PlayerAudience, resolve_audience

from dnd.player.event_record import RecordedEvent
from dnd.player.sheet_facts import sheet_fact
from dnd.types.actor_sheet import ActorSheetChange
from dnd.player.facts import PlayerLogEntry
from dnd.player.actor_facts import ActorState, ConditionFact, PresentationTarget
from dnd.actor_projection import actor_fact_change, actor_fact_owner, actor_from_birth
from dnd.actor_projection import condition_fact as committed_condition_fact
from dnd.player.actor_projection import apply_presented_change
from dnd.types.actor_facts import ActorFactChange


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
    admitted: tuple[tuple[int, RecordedEvent], ...]
    dispositions: tuple[tuple[int, Disposition], ...]
    conditions: tuple[ConditionFact, ...] = ()
    admissions: tuple[ActorAdmission, ...] = ()
    audience: PlayerAudience | None = None
    # The audience's combat-log entry of each admitted event that has one.
    logs: dict[UUID, PlayerLogEntry] = field(default_factory=dict)
    # The shared fold's actor change of each admitted event that has one, by event uuid.
    actor_fact_changes: Mapping[UUID, ActorFactChange] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ActorAdmission:
    """Actor state at an actual observation version in the received lineage."""

    event_uuid: UUID
    actor: ActorState
    contact: PerceivedContact | None
    observer_uuid: UUID | None = None


@dataclass(frozen=True, slots=True)
class AdmissionEvidence:
    """One version's seat-independent capture evidence, read at that version.

    `observer` is the tracked observer of a completed sensory delta (else
    None), `observed` its changed contacts plus itself and `acquired` the
    contacts it did not hold before. `candidates` are the participants and
    the fact owner. For each of these identities: its actor (before a
    completed version's fold; after an arrival's or departure's fold at its
    effect), the tracked observers holding it as a contact, and its own last
    sensory position. `actor_fact_change` is the actor change the shared fold
    applied at this version (plan §4): the one record of it, which every
    seat's fold applies.
    """

    observer: UUID | None
    observed: frozenset[UUID]
    acquired: frozenset[UUID]
    candidates: frozenset[UUID]
    actors: Mapping[UUID, ActorState]
    holders: Mapping[UUID, Mapping[UUID, PerceivedContact]]
    positions: Mapping[UUID, tuple[int, int]]
    actor_fact_change: ActorFactChange | None = None


@dataclass(slots=True)
class CaptureCheckpoint:
    """The recorded actor/contact fold of the EventQueue, advanced once per version for every audience.

    Contacts and positions are kept for every tracked observer (the union of
    the audiences sharing it). `root_of` and `trees` place the lineages of
    each still-open root; `pending` keeps the evidence of that root's folded
    versions until it completes, so a root's capture never folds history again.
    `initiative` is the encounter's order (its start, then each join or leave); a session has one encounter.
    """

    generation: UUID
    observers: frozenset[UUID]
    cursor: int = 0
    actors: dict[UUID, ActorState] = field(default_factory=dict)
    contacts: dict[UUID, dict[UUID, PerceivedContact]] = field(default_factory=dict)
    positions: dict[UUID, tuple[int, int]] = field(default_factory=dict)
    root_of: dict[UUID, UUID] = field(default_factory=dict)
    trees: dict[UUID, list[UUID]] = field(default_factory=dict)
    pending: dict[UUID, dict[UUID, AdmissionEvidence]] = field(default_factory=dict)
    initiative: tuple[UUID, ...] = ()


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
    audience: PlayerAudience | None = None
    # Exact already-recorded versions that caused an observation before completion.
    observed_sources: tuple[RecordedEvent, ...] = ()
    # The audience's combat-log entry of each retained event that has one.
    logs: dict[UUID, PlayerLogEntry] = field(default_factory=dict)
    # The shared fold's actor change of each retained event that has one, by event uuid.
    actor_fact_changes: Mapping[UUID, ActorFactChange] = field(default_factory=dict)


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
    if isinstance(event, SpatialEffectChangeEvent):
        return True
    if isinstance(event, (ConditionApplicationEvent, ConditionRemovalEvent, ConditionStateChangedEvent)) and (
            event.resulting_tile is not None or event.resulting_item is not None):
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
    if isinstance(event, (WorldModifiedEvent, TileElevationChangeEvent)):
        # Retain native support changes before the baseline, just as placements
        # below. The player projection still owns which after-values are seen.
        return True
    if type(event) is ItemLocationStateEvent:
        return (
            event.location is ItemLocation.FLOOR
            and event.world_placement is not None
            or event.location is ItemLocation.DESTROYED
        )
    if type(event) is SpatialChangeEvent:
        # Initialization may include ordinary placements, lights (authored
        # torches are lit only after the cold map is published) and tile rows
        # recorded after the cold map. Their after-values are needed before
        # observer disclosure, just like later changes to the same records.
        return event.change_type in (
            SpatialChangeType.OBJECT_PLACED, SpatialChangeType.OBJECT_CHANGED,
            SpatialChangeType.OBJECT_REMOVED, SpatialChangeType.LIGHT_CHANGED,
            SpatialChangeType.TILES_CHANGED,
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
    audience: PlayerAudience | None = None,
    context: CaptureContext | None = None,
) -> IntervalEnvelope:
    """Synchronously copy one exact already-committed EventQueue interval.

    `context` carries the shared fold's evidence for the interval; without it
    this audience folds the history from its start.
    """
    audience = resolve_audience(observer_uuid, audience)
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
    logs: dict[UUID, PlayerLogEntry] = {}
    for index, event in indexed:
        # A controlled actor's birth and sheet facts, for its sheet (`sheet_facts`).
        sheet = sheet_fact(event) if event.phase is EventPhase.COMPLETION else None
        is_admitted = (sheet is not None and audience.controls(sheet.actor_uuid)) or any(
            _admitted(event, observer_uuid=identity, battlefield_id=battlefield_id) for identity in audience.observers)
        if is_admitted:
            admitted.append((index, _retained_event(event, audience)))
            admitted_original.append((index, event))
            entry = seat_log_entry(event.combat_log, audience)
            if entry is not None:
                logs[event.uuid] = entry
            disposition = (
                Disposition.STATE_ONLY
                if isinstance(event, (EntityCreatedEvent, SensoryUpdateEvent, TurnEvent, RoundEvent, EncounterEvent))
                or actor_fact_owner(event) is not None or sheet is not None
                else Disposition.PENDING_DISPLAY
            )
        else:
            disposition = Disposition.UNSUPPORTED
        dispositions.append((index, disposition))

    evidence: Mapping[UUID, AdmissionEvidence] = {}
    if admitted_original:
        evidence = (context or capture_context(
            CaptureCheckpoint(generation, frozenset(audience.observers)), end_cursor=end_cursor)).evidence
    return IntervalEnvelope(
        name=name,
        generation=generation,
        start_cursor=start_cursor,
        end_cursor=end_cursor,
        observer_uuid=observer_uuid,
        audience=audience,
        battlefield_id=battlefield_id,
        door_uuid=door_uuid,
        standing_torch_uuid=standing_torch_uuid,
        objective_rows=tuple(_objective_row(index, event) for index, event in indexed),
        admitted=tuple(admitted),
        dispositions=tuple(dispositions),
        conditions=tuple(fact for _, event in admitted_original if (fact := _condition_fact(event)) is not None),
        admissions=(_derive_admissions(tuple(admitted_original), audience, evidence, frozenset())
                    if admitted_original else ()),
        logs=logs,
        actor_fact_changes=_actor_fact_changes(evidence, (event for _, event in admitted_original)),
    )


def apply_world_fact(target: PresentationTarget, event: Event, condition: ConditionFact | None = None) -> bool:
    """Fold recorded world after-values, reporting whether any were applied (actors take their own changes)."""
    if not apply_recorded_world_fact(target.recorded_world, event, condition):
        return False
    if target.door_uuid is not None and (door := target.objects.get(target.door_uuid)) is not None:
        target.door_placement = door.placement
        target.door_is_open = door.item.is_open
    if target.standing_torch_uuid is not None:
        fixture = target.objects.get(target.standing_torch_uuid)
        if fixture is not None:
            target.standing_torch_state = fixture.item
    return True


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
        if (change := recorded_actor_change(envelope.actor_fact_changes, event)) is not None:
            apply_presented_change(target.actors, change)
        condition = condition_facts.get(event.uuid)
        if condition is not None and (condition.resulting_tile is not None or condition.resulting_item is not None):
            apply_world_fact(target, event, condition)
            pending.add(index)
            continue
        if actor_fact_owner(event) is not None:
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
        elif isinstance(event, (SpatialChangeEvent, WorldModifiedEvent, TileElevationChangeEvent,
                                SpatialEffectChangeEvent, SpatialEffectInteractionEvent)):
            apply_world_fact(target, event)
            pending.add(index)
        elif type(event) is SensoryUpdateEvent:
            _reduce_sensory_fact(target, event)
            dispositions[index] = Disposition.STATE_ONLY
        elif isinstance(event, (TurnEvent, RoundEvent, EncounterEvent)):
            _reduce_turn_fact(target, event)
            dispositions[index] = Disposition.STATE_ONLY
        elif sheet_fact(event) is not None:
            # A sheet fact; the HUD projection reads it from the admitted events.
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
        recorded_world=copy_world_facts(target.recorded_world),
        actors=dict(target.actors),
        senses=copy_senses_snapshot(target.senses) if target.senses is not None else None,
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
    The header holds the version's frozen grant values themselves.
    """
    children, lineage_children = EventQueue.child_links(event)
    header = Event.model_validate(dict(
        name=event.name, uuid=event.uuid, source_entity_uuid=event.source_entity_uuid,
        source_entity_name=event.source_entity_name,
        target_entity_uuid=event.target_entity_uuid, target_entity_name=event.target_entity_name,
        use_register=False, lineage_uuid=event.lineage_uuid, timestamp=event.timestamp,
        event_type=event.event_type, phase=event.phase, modified=event.modified,
        canceled=event.canceled, canceled_from_phase=event.canceled_from_phase,
        parent_event=event.parent_event, turn_execution_id=event.turn_execution_id,
        resolution_ref=event.resolution_ref,
        status_message=event.status_message, outcome_code=event.outcome_code,
        outcome_source_entity_uuid=event.outcome_source_entity_uuid,
        is_first=event.is_first, is_last=event.is_last,
        lineage_children_events=lineage_children,
        children_events=children, parent_lineage=event.parent_lineage,
        children_lineages=event.children_lineages,
    ), context=PASSIVE_EVENT_REPLAY)
    header.identified_entity_observer_uuids = event.identified_entity_observer_uuids
    header.located_entity_observer_uuids = event.located_entity_observer_uuids
    header.located_position_observer_uuids = event.located_position_observer_uuids
    header._effective_handler_presentations = event.effective_handler_presentations
    return header


def _controller_redaction(event: Event, audience: PlayerAudience) -> bool | None:
    """Whether this seat controls the source, for the families that redact non-controllers; None otherwise."""
    match event:
        case SpellbookChangedEvent() | SpellMasteryStudiedEvent() | PermanentFeatureUsedEvent() | SpellPreparationChangedEvent() | ActorSheetEvent():
            return audience.controls(event.source_entity_uuid)
    return None


def seat_log_entry(log: CombatLogEntry | None, audience: PlayerAudience, *,
                   known_entity_names: Mapping[str, str] | None = None,
                   known_connector_uuids: frozenset[str] = frozenset(),
                   known_content_ids: frozenset[str] = frozenset(),
                   retained_entries: dict[int, CombatLogEntry | None] | None = None) -> PlayerLogEntry | None:
    """The one projection of a native log for a seat: rendered, without nested copies or grants.

    Nested child entries inform the rendering; the seat receives each child's
    own entry with its node, so its target indices refer to those (see
    `PlayerLogEntry`).
    """
    projected = project_combat_log(log, known_entity_names=known_entity_names, retained_entries=retained_entries,
        known_connector_uuids=known_connector_uuids, known_content_ids=known_content_ids,
        controlled_entity_uuids=audience.controlled_ids, observer_entity_uuids=audience.observer_ids)
    if projected is None:
        return None
    return PlayerLogEntry(entry_type=projected.entry_type, source_name=projected.source_name,
        source_uuid=projected.source_uuid, target_name=projected.target_name, target_uuid=projected.target_uuid,
        compact=projected.compact, verbose=projected.verbose, detailed=projected.detailed, data=projected.data,
        success=projected.success)


def _retained_event(event: Event, audience: PlayerAudience, *, omit_sensory_payload: bool = False,
                    bodies: dict[tuple[UUID, bool, bool | None], Event] | None = None) -> Event:
    """The seat's retained event: the shared detached body (its combat log is the seat's `logs` entry)."""
    controls = _controller_redaction(event, audience)
    key = (event.uuid, omit_sensory_payload, controls)
    body = bodies.get(key) if bodies is not None else None
    if body is None:
        body = _retained_body(event, controls, omit_sensory_payload=omit_sensory_payload)
        if bodies is not None:
            bodies[key] = body
    return body


def _retained_body(event: Event, controls: bool | None, *, omit_sensory_payload: bool) -> Event:
    """The selected event families' seat body, without constructing registered models (no combat log).

    Stored versions are frozen values (P7b): the body shares the version's payload by reference and
    carries its child links as of this capture.
    """
    children, lineage_children = EventQueue.child_links(event)
    common = {"use_register": False, "context": None, "combat_log": None,
              "children_events": children, "lineage_children_events": lineage_children}
    match event:
        case SensoryUpdateEvent() if omit_sensory_payload:
            copied = _event_header(event).model_copy(update=common)
        case AttackEvent():
            copied = event.model_copy(update={
                **common, "attack_bonus": None, "ac": None, "damages": None, "additional_damages": [],
            })
        case SpellEvent():
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
        case SpellDamageRollResultEvent():
            copied = event.model_copy(update={**common,"context":{},"damage":event.damage.model_copy(
                update={"use_register":False,"context":None,"damage_bonus":None})})
        case SpellbookChangedEvent():
            copied = event.model_copy(update=common if controls else {
                **common,"scribed_spell_ids":(),"learned_spell_id":""})
        case SpellMasteryStudiedEvent():
            copied = event.model_copy(update=common if controls else {
                **common,"applied_class_levels":()})
        case PermanentFeatureUsedEvent():
            copied = event.model_copy(update=common if controls else {
                **common,"permanent_feature_uses":()})
        case SpellPreparationChangedEvent():
            copied = event.model_copy(update=common if controls else {
                **common,"prepared_spell_selections":(),"casting_source_id":""})
        case ActorSheetEvent():
            copied = event.model_copy(update=common if controls else {**common, "change": ActorSheetChange()})
        case InitiativeOrderChangedEvent():
            copied = event.model_copy(update=common)
        case HealRollResultEvent():
            copied = event.model_copy(update={**common, "context": {}})
        case D20Event():
            copied = event.model_copy(update={
                **common, "dice": None, "dc": event.get_dc(),
                "bonus": event.dice_roll.bonus if event.dice_roll is not None else None,
            })
        case SpellMasteryStudiedEvent() | ConditionMembershipCommittedEvent() | RestResourcesRecoveredEvent() | PermanentFeatureUsedEvent() | ActionApplicationCommittedEvent() | MaximumHitPointReductionEvent() | EffectApplicationEvent() | ActionCostsCommittedEvent() | RestCompletedEvent() | HealingAppliedEvent():
            copied = event.model_copy(update=common)
        case CounterspellReactionEvent():
            copied = event.model_copy(update=common)
        case ShoveEvent():
            copied = event.model_copy(update={**common, "shover_athletics": None})
        case AreaReachEvent() | MovementEvent() | JumpEvent() | TraverseConnectorEvent() | StepMovementEvent() | ForcedMovementEvent() | PortalTransferEvent() | MechanismActivationEvent() | StandOfferEvent():
            copied = event.model_copy(update=common)
        case EntityCreatedEvent() | EntityFactionChangedEvent() | SensoryUpdateEvent() | LifeStateChangeEvent() | DeathEvent() | HealEvent() | TemporaryHitPointsChangedEvent() | ConditionStateChangedEvent():
            copied = event.model_copy(update=common)
        case DeathSaveEvent() | ReviveEvent() | InstantDeathEvent() | TurnEvent() | RoundEvent() | EncounterEvent():
            copied = event.model_copy(update=common)
        case WorldInitializedEvent() | WorldModifiedEvent() | TileElevationChangeEvent() | SpatialEffectChangeEvent() | SpatialEffectInteractionEvent() | SpatialChangeEvent():
            copied = event.model_copy(update=common)
        case ActionEvent() if type(event) is ActionEvent:
            copied = event.model_copy(update=common)
        case EquipmentEvent() | ItemResourceChangeEvent() | ItemHoldingsReleasedEvent():
            copied = event.model_copy(update=common)
        case ItemLocationStateEvent() | ItemDestructionEvent() | ExposedFlameEvent():
            copied = event.model_copy(update=common)
        case _:
            copied = _event_header(event).model_copy(update=common)
    # DiceRoll contains concrete values; model_copy avoids its registering
    # constructor. Live value/Damage graphs were removed above.
    if isinstance(copied, ActionEvent):
        copied = copied.model_copy(update={"costs": [
            BaseCost.model_validate_json(cost.model_dump_json()) for cost in copied.costs
        ]})
    return copied


def _actor_participants(event: Event) -> tuple[UUID, ...]:
    """Existing families distinguish actor subjects from neutral event sources."""
    match event:
        case TurnEvent() | RoundEvent() | EncounterEvent() | SensoryUpdateEvent():
            return ()
        case ItemResourceChangeEvent() | ItemHoldingsReleasedEvent():
            return (event.source_entity_uuid,) if event.source_entity_uuid is not None else ()
        case SpatialChangeEvent(change_type=SpatialChangeType.LIGHT_CHANGED):
            # light_changed() stores the affected tile UUID in entity_uuid.
            # Its sensory children provide observer-specific light after-values.
            return ()
        case EntityFactionChangedEvent() | LifeStateChangeEvent() | DeathEvent() | ReviveEvent() | InstantDeathEvent() | TemporaryHitPointsChangedEvent():
            return (event.entity_uuid,)
        case SpatialChangeEvent(change_type=(
            SpatialChangeType.PERCEIVABILITY_CHANGED | SpatialChangeType.ENTITY_ENTERED
            | SpatialChangeType.ENTITY_LEFT | SpatialChangeType.MOVEMENT_COLLISION
        )):
            return (event.entity_uuid,) if event.entity_uuid is not None else ()
        case ConditionApplicationEvent() | ConditionRemovalEvent() | ConditionStateChangedEvent() | TakeDamageEvent() | DamageAppliedEvent() | HealEvent() | PortalTransferEvent() | StandOfferEvent():
            return (event.target_entity_uuid,) if event.target_entity_uuid is not None else ()
        case ActionEvent() | StepMovementEvent() | ForcedMovementEvent() | D20Event() | D20RollResultEvent() | DamageRollResultEvent() | HealRollResultEvent():
            return tuple(identity for identity in (event.source_entity_uuid, event.target_entity_uuid)
                         if identity is not None)
        case _:
            # Unsupported payloads expose only the already-subjective log and
            # diagnostic header; their unknown source schema cannot name actors.
            return ()


def _condition_fact(event: Event) -> ConditionFact | None:
    if (recorded := committed_condition_fact(event)) is not None:
        return recorded
    if not isinstance(event, (ConditionApplicationEvent, ConditionRemovalEvent)):
        return None
    return ConditionFact(
        event_uuid=event.uuid, condition_uuid=event.condition.uuid,
        name=event.condition.name or "Condition", category=event.condition.condition_category,
        behavior_id=event.behavior_id, resulting_max_hp=event.resulting_max_hp,
        resulting_ac=event.resulting_ac, resulting_tile=event.resulting_tile,
        resulting_item=event.resulting_item,
        consumed=isinstance(event, ConditionRemovalEvent) and event.consumed,
    )


def recorded_actor_change(changes: Mapping[UUID, ActorFactChange], event: Event) -> ActorFactChange | None:
    """A retained event's actor change; every fact with an owner was recorded one by the shared fold."""
    change = changes.get(event.uuid)
    if change is None and actor_fact_owner(event) is not None:
        raise ValueError(f"actor fact {event.uuid} lacks its recorded actor change")
    return change


def _actor_fact_changes(evidence: Mapping[UUID, AdmissionEvidence], events: Iterable[Event]
                        ) -> dict[UUID, ActorFactChange]:
    """These retained events' actor changes, read from the one record of each: its version's evidence row."""
    return {event.uuid: change for event in events
            if (row := evidence.get(event.uuid)) is not None and (change := row.actor_fact_change) is not None}


def advance_capture(checkpoint: CaptureCheckpoint, end: int) -> dict[UUID, AdmissionEvidence]:
    """Fold versions up to `end` once for every audience; their evidence and that of roots completing here."""
    if checkpoint.generation != EventQueue.generation_id():
        raise ValueError("capture checkpoint belongs to another EventQueue generation")
    actors, contacts, positions = checkpoint.actors, checkpoint.contacts, checkpoint.positions
    observers, root_of, trees, pending = checkpoint.observers, checkpoint.root_of, checkpoint.trees, checkpoint.pending
    evidence: dict[UUID, AdmissionEvidence] = {}
    for index, event in EventQueue.iter_events_since(checkpoint.cursor):
        if index >= end:
            break
        completed = event.phase is EventPhase.COMPLETION and not event.canceled
        if completed and isinstance(event, EntityCreatedEvent):
            actors[event.entity_uuid] = actor_from_birth(event)
        change: ActorFactChange | None = None
        if (not event.canceled and event.phase is EventPhase.EFFECT
                and isinstance(event, SpatialChangeEvent)
                and event.change_type in (SpatialChangeType.ENTITY_LEFT, SpatialChangeType.ENTITY_ENTERED)
                and event.entity_uuid is not None and event.entity_uuid in actors):
            # The committed arrival or departure is the actor's at its effect, before its sensory children.
            change = actor_fact_change(event)
            if change is not None:
                apply_presented_change(actors, change)
        observer: UUID | None = None
        observed: frozenset[UUID] = frozenset()
        acquired: frozenset[UUID] = frozenset()
        if completed and isinstance(event, SensoryUpdateEvent) and event.observer_uuid in observers:
            observer = event.observer_uuid
            member = contacts.setdefault(observer, {})
            acquired = frozenset(event.entity_contacts_changed.keys() - member.keys())
            positions[observer] = event.observer_position
            for identity in event.entity_contacts_removed:
                member.pop(identity, None)
            member.update(event.entity_contacts_changed)
            observed = frozenset((*event.entity_contacts_changed, observer))
        lineage = event.lineage_uuid
        root = root_of.get(lineage)
        if root is None:
            root = lineage if event.parent_lineage is None else root_of.get(event.parent_lineage)
            if root is not None:
                root_of[lineage] = root
                trees.setdefault(root, []).append(lineage)
        if completed:
            # Records, then the version's frozen row (actors before the fold), then the fold.
            change = actor_fact_change(event, _condition_fact(event))
        if not event.canceled:
            candidates = set(_actor_participants(event))
            owner = actor_fact_owner(event)
            if owner is not None:
                candidates.add(owner)
            identities = candidates | observed | acquired
            row = AdmissionEvidence(observer, observed, acquired, frozenset(candidates),
                {identity: actors[identity] for identity in identities if identity in actors},
                {identity: {member: held[identity] for member, held in contacts.items() if identity in held}
                 for identity in identities},
                {identity: positions[identity] for identity in identities if identity in positions},
                change)
            evidence[event.uuid] = row
            if root is not None:
                pending.setdefault(root, {})[event.uuid] = row
        if completed:
            match event:
                case EncounterStartEvent() | InitiativeOrderChangedEvent():
                    checkpoint.initiative = tuple(event.initiative_order)
            if change is not None:
                # TODO(E3-bodies): E2 keeps today's shared fold, where a condition's item after-value does not
                # reach the actors holding the item; every seat's fold applies it.
                apply_presented_change(actors, replace(change, replaced_item=None))
            if (isinstance(event, SpatialChangeEvent) and event.terminal_release is not None
                    and event.entity_uuid is not None):
                actors.pop(event.entity_uuid, None)
                positions.pop(event.entity_uuid, None)
                for member in contacts.values():
                    member.pop(event.entity_uuid, None)
                if event.entity_uuid in contacts:
                    contacts[event.entity_uuid].clear()
        if event.parent_lineage is None and event.phase in (EventPhase.COMPLETION, EventPhase.CANCEL):
            # The root completes: its whole tree is captured now, never again.
            for member in trees.pop(lineage, ()):
                root_of.pop(member, None)
            evidence.update(pending.pop(lineage, {}))
        checkpoint.cursor = index + 1
    return evidence


def _derive_admissions(
    indexed: tuple[tuple[int, Event], ...], audience: PlayerAudience,
    evidence: Mapping[UUID, AdmissionEvidence], known_actor_uuids: Collection[UUID],
    newly_known_actor_uuids: Collection[UUID] = (),
) -> tuple[ActorAdmission, ...]:
    """One audience's admissions over these versions, read from their recorded evidence."""
    admitted: set[UUID] = set()
    result: list[ActorAdmission] = []
    for index, event in indexed:
        if event.canceled:
            continue
        row = evidence.get(event.uuid)
        if row is None:
            raise ValueError(f"Version {index} precedes the capture checkpoint and was not retained")
        sensory = row.observer is not None and audience.observes(row.observer)
        observed = row.observed if sensory else frozenset()
        acquired = row.acquired if sensory else frozenset()
        for identity in sorted({identity for identity in row.candidates | observed
                if identity not in known_actor_uuids and identity not in newly_known_actor_uuids
                and identity not in admitted} | acquired, key=str):
            actor = row.actors.get(identity)
            if actor is None:
                continue
            holders = row.holders[identity]
            witnesses = [member for member in audience.observers
                if member == identity or member in holders and (
                    sensory and member == row.observer and identity in observed
                    or str(member) in event.identified_entity_observer_uuids.get(str(identity), set())
                    and str(member) in event.located_entity_observer_uuids.get(str(identity), set()))]
            if not witnesses:
                continue
            witness = min(witnesses, key=lambda member: (
                member != identity, not (member == identity or holders[member].visual), member.int))
            contact = holders.get(witness) if witness != identity else None
            position = (row.positions.get(identity) if witness == identity
                        else contact.position if contact is not None and contact.visual else None)
            result.append(ActorAdmission(event.uuid, replace(actor, last_visual_position=position), contact, witness))
            admitted.add(identity)
    return tuple(result)


def capture_lineage(
    root: Event, *, observer_uuid: UUID, known_actor_uuids: Collection[UUID] = frozenset(),
    audience: PlayerAudience | None = None,
) -> CompletedLineage:
    """Retain a closed native lineage privately after its public operation.

    Follow existing child lineages. Operation cursor ranges and callback batches
    do not establish a render unit. Observer grants remain exact facts in this
    private record; the outgoing projection decides which payloads and geometry
    an observer receives. Unknown participants must not erase observed children.
    """
    return capture_lineages((root,), observer_uuid=observer_uuid,
                            known_actor_uuids=known_actor_uuids, audience=audience)[0]


@dataclass(frozen=True, slots=True)
class CaptureContext:
    """One operation's seat-independent capture over the EventQueue's existing indexes.

    `graphs` holds each root's lineage graph, `evidence` each version's
    admission evidence from the shared fold and `bodies` each retained event's
    detached body: every seat shares them and adds only its own admissions and
    combat log.
    """

    generation: UUID
    end_cursor: int
    graphs: dict[UUID, "LineageGraph"] = field(default_factory=dict)
    evidence: dict[UUID, AdmissionEvidence] = field(default_factory=dict)
    bodies: dict[tuple[UUID, bool, bool | None], Event] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class LineageGraph:
    """One root's terminal node per lineage and every version in source order, shared by every seat."""

    nodes: dict[UUID, Event]
    indexed: tuple[tuple[int, Event], ...]
    conditions: tuple[ConditionFact, ...]
    objective_rows: tuple[ObjectiveRow, ...]


def capture_context(checkpoint: CaptureCheckpoint, roots: tuple[Event, ...] = (), *,
                    end_cursor: int | None = None) -> CaptureContext:
    """Each root's graph, then one advance of the shared fold past their last version (or to `end_cursor`)."""
    context = CaptureContext(EventQueue.generation_id(), EventQueue.event_cursor())
    for root in roots:
        if root.uuid not in context.graphs:
            context.graphs[root.uuid] = _lineage_graph(root, context)
    end = end_cursor if end_cursor is not None else max(
        (graph.indexed[-1][0] + 1 for graph in context.graphs.values()), default=checkpoint.cursor)
    context.evidence.update(advance_capture(checkpoint, end))
    return context


def _lineage_versions(context: CaptureContext, identity: UUID) -> tuple[tuple[int, Event], ...]:
    return tuple((index, event) for event in EventQueue.get_events_by_lineage(identity)
        if (index := EventQueue.get_event_index(event.uuid)) is not None and index < context.end_cursor)


def capture_lineages(
    roots: tuple[Event, ...], *, observer_uuid: UUID,
    known_actor_uuids: Collection[UUID] = frozenset(), audience: PlayerAudience | None = None,
    context: CaptureContext | None = None, known_entity_names: Mapping[str, str] | None = None,
    known_connector_uuids: frozenset[str] = frozenset(), known_content_ids: frozenset[str] = frozenset(),
    omit_foreign_sensory_payloads: bool = False,
) -> tuple[CompletedLineage, ...]:
    """Project each audience from the same original operation evidence.

    Without a shared `context` this audience folds the history from its start.
    """
    audience = resolve_audience(observer_uuid, audience)
    if context is None:
        context = capture_context(CaptureCheckpoint(EventQueue.generation_id(), frozenset(audience.observers)), roots)
    known: set[UUID] = set()
    names = ChainMap({}, known_entity_names or {})
    retained: list[CompletedLineage] = []
    for root in roots:
        lineage = _capture_lineage(root, observer_uuid=observer_uuid, audience=audience,
            known_actor_uuids=known_actor_uuids, newly_known_actor_uuids=known,
            context=context, known_entity_names=names,
            known_connector_uuids=known_connector_uuids, known_content_ids=known_content_ids,
            omit_foreign_sensory_payloads=omit_foreign_sensory_payloads)
        retained.append(lineage)
        known.update(admission.actor.uuid for admission in lineage.admissions)
        names.update((str(admission.actor.uuid), admission.actor.name) for admission in lineage.admissions)
    return tuple(retained)


def _lineage_graph(root: Event, context: CaptureContext) -> LineageGraph:
    """One root's seat-independent capture: terminal nodes, every version in source order."""
    versions: dict[UUID, tuple[tuple[int, Event], ...]] = {}
    pending = [root]
    nodes: dict[UUID, Event] = {}
    while pending:
        event = pending.pop()
        if event.lineage_uuid in nodes:
            continue
        if event.phase not in (EventPhase.COMPLETION, EventPhase.CANCEL):
            raise ValueError("lineage requires terminal root and child facts")
        versions[event.lineage_uuid] = _lineage_versions(context, event.lineage_uuid)
        if event.phase is EventPhase.CANCEL:
            # Cancellation keeps raw parent/child version references; it does
            # not run completion's stable-lineage normalization. Resolve those
            # existing references on the retained header as well as traversing
            # them, so cold consumers receive the same complete causal graph.
            children = []
            children_events, lineage_children = EventQueue.child_links(event)
            for identity in dict.fromkeys(lineage_children + children_events):
                child = EventQueue.get_event_by_uuid(identity)
                if child is None:
                    raise ValueError("canceled lineage is missing a required child")
                child_versions = _lineage_versions(context, child.lineage_uuid)
                if not child_versions:
                    raise ValueError("canceled lineage is missing a required child")
                children.append(child_versions[-1][1])
            event = event.model_copy(update={"children_lineages": list(dict.fromkeys(
                child.lineage_uuid for child in children))})
        else:
            children = []
            for identity in event.children_lineages:
                child_versions = _lineage_versions(context, identity)
                if not child_versions:
                    raise ValueError("lineage is missing a required child")
                children.append(child_versions[-1][1])
        nodes[event.lineage_uuid] = event
        pending.extend(children)

    indexed = tuple(sorted((row for identity in nodes for row in versions.get(identity, ())),
                           key=lambda row: row[0]))
    if not indexed or root.uuid not in {event.uuid for _, event in indexed}:
        raise ValueError("lineage root is absent from the current EventQueue")
    conditions = tuple(fact for _, event in indexed
                       if event.uuid == nodes[event.lineage_uuid].uuid
                       and (fact := _condition_fact(event)) is not None)
    return LineageGraph(nodes, indexed, conditions,
                        tuple(_objective_row(index, event) for index, event in indexed))


def _capture_lineage(
    root: Event, *, observer_uuid: UUID, audience: PlayerAudience, known_actor_uuids: Collection[UUID],
    context: CaptureContext, known_entity_names: Mapping[str, str],
    known_connector_uuids: frozenset[str], known_content_ids: frozenset[str],
    newly_known_actor_uuids: Collection[UUID] = (),
    omit_foreign_sensory_payloads: bool = False,
) -> CompletedLineage:
    generation = context.generation
    if generation != EventQueue.generation_id():
        raise RuntimeError("EventQueue generation changed during lineage capture")
    graph = context.graphs[root.uuid]
    nodes, indexed, conditions = graph.nodes, graph.indexed, graph.conditions
    admissions = _derive_admissions(indexed, audience, context.evidence, known_actor_uuids, newly_known_actor_uuids)
    names = ChainMap({}, known_entity_names)
    retained_logs: dict[int, CombatLogEntry | None] = {}
    admissions_at: dict[UUID, list[ActorAdmission]] = {}
    for admission in admissions:
        admissions_at.setdefault(admission.event_uuid, []).append(admission)
    # Source versions are selected from original evidence before admission.
    # Even a foreign observer's reference retains its exact source payload.
    observed_source_ids = {
        reference.source_event_uuid for event in nodes.values()
        if isinstance(event, SensoryUpdateEvent) for reference in event.observed_changes
    }
    omitted_sensory = {
        event.uuid for event in nodes.values()
        if omit_foreign_sensory_payloads and isinstance(event, SensoryUpdateEvent)
        and not audience.observes(event.observer_uuid) and _safe_to_detach(event)
        and event.uuid not in observed_source_ids
    }
    retained_values = []
    logs: dict[UUID, PlayerLogEntry] = {}
    for _, event in indexed:
        for admission in admissions_at.get(event.uuid, ()):
            names[str(admission.actor.uuid)] = admission.actor.name
        if event.uuid == nodes[event.lineage_uuid].uuid:
            node = nodes[event.lineage_uuid]
            retained_values.append(_retained_event(node, audience,
                omit_sensory_payload=event.uuid in omitted_sensory, bodies=context.bodies))
            entry = seat_log_entry(node.combat_log, audience,
                known_entity_names=names, known_connector_uuids=known_connector_uuids,
                known_content_ids=known_content_ids, retained_entries=retained_logs)
            if entry is not None:
                logs[node.uuid] = entry
    retained = tuple(retained_values)
    retained_root = next(event for event in retained if event.uuid == root.uuid)
    condition_ids = {fact.event_uuid for fact in conditions}
    dispositions = tuple(
        (event.uuid, Disposition.NOT_DISCLOSED if event.uuid in omitted_sensory else Disposition.UNSUPPORTED)
        for event in retained
        if type(event) is Event and event.uuid not in condition_ids
    )
    retained_ids = {event.uuid for event in retained}
    if generation != EventQueue.generation_id():
        raise RuntimeError("EventQueue generation changed during lineage capture")
    return CompletedLineage(
        generation=generation,
        observer_uuid=observer_uuid,
        audience=audience,
        root=retained_root,
        events=retained,
        objective_rows=graph.objective_rows,
        start_cursor=indexed[0][0],
        end_cursor=indexed[-1][0] + 1,
        conditions=conditions,
        dispositions=dispositions,
        admissions=admissions,
        observed_sources=tuple(_retained_event(event, audience, bodies=context.bodies)
            for _, event in indexed
            if event.uuid in observed_source_ids and event.uuid not in retained_ids),
        logs=logs,
        actor_fact_changes=_actor_fact_changes(context.evidence, retained),
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
                   admissions=tuple(row for row in lineage.admissions if row.event_uuid in version_ids),
                   logs={identity: entry for identity, entry in lineage.logs.items() if identity in identities},
                   actor_fact_changes={identity: change for identity, change in lineage.actor_fact_changes.items()
                                       if identity in identities})


def _admit_actor(target: PresentationTarget, admission: ActorAdmission) -> None:
    """Apply the actor's recorded state at this actual observation boundary."""
    target.actors[admission.actor.uuid] = admission.actor
    if admission.contact is not None and target.senses is not None:
        target.senses.entities[admission.actor.uuid] = admission.contact


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
    not_disclosed = {identity for identity, disposition in lineage.dispositions
                     if disposition is Disposition.NOT_DISCLOSED}
    source_indexes = {row.event_uuid: row.source_index for row in lineage.objective_rows}
    admissions = iter(sorted(lineage.admissions, key=lambda row: source_indexes[row.event_uuid]))
    admission = next(admissions, None)
    for event in lineage.events:
        while admission is not None and source_indexes[admission.event_uuid] <= source_indexes[event.uuid]:
            _admit_actor(result, admission)
            admission = next(admissions, None)
        if event.canceled or event.uuid in unsupported:
            continue
        if (change := recorded_actor_change(lineage.actor_fact_changes, event)) is not None:
            apply_presented_change(result.actors, change)
        condition = condition_facts.get(event.uuid)
        if condition is not None and (condition.resulting_tile is not None or condition.resulting_item is not None):
            apply_world_fact(result, event, condition)
            continue
        owner = actor_fact_owner(event)
        if owner is not None:
            if owner not in result.actors and not isinstance(event, (AttackEvent, EquipmentEvent, SpatialChangeEvent)):
                raise ValueError("actor fact requires its retained owner")
            continue
        match event:
            case SensoryUpdateEvent():
                _reduce_sensory_fact(result, event)
            case Event(event_type=EventType.SENSORY_UPDATE) if event.uuid in not_disclosed:
                # Audience capture retains only the causal header for an
                # unrelated observer whose sensory payload has no consumer.
                pass
            case SpellMasteryStudiedEvent() | ConditionMembershipCommittedEvent() | RestResourcesRecoveredEvent() | PermanentFeatureUsedEvent() | ActionApplicationCommittedEvent() | MaximumHitPointReductionEvent() | EffectApplicationEvent() | ActionCostsCommittedEvent() | RestCompletedEvent() | HealingAppliedEvent():
                # Admission/causal facts have no extra after-values or choreography.
                pass
            case ActorSheetEvent() | InitiativeOrderChangedEvent():
                # Sheet and order facts are the HUD projection's, not a presented world value.
                pass
            case ActionEvent() | TakeDamageEvent() | D20RollResultEvent() | DamageRollResultEvent() | HealRollResultEvent() | SpellDamageRollResultEvent() | SpellbookChangedEvent() | SpellPreparationChangedEvent() | D20Event():
                # These facts explain causality. Only the committed applied
                # packet changes HP, so aggregate totals cannot apply it twice.
                pass
            case SpatialChangeEvent() | ItemLocationStateEvent():
                apply_world_fact(result, event)
            case DeathEvent() | DeathSaveEvent() | ReviveEvent() | InstantDeathEvent() | ItemDestructionEvent():
                # Keep the cause. The actual life and sensory children supply
                # the successor facts; do not infer them from death/occupancy.
                pass
            case TurnEvent() | RoundEvent() | EncounterEvent():
                _reduce_turn_fact(result, event)
            case AreaReachEvent() | StepMovementEvent() | ForcedMovementEvent() | PortalTransferEvent() | MechanismActivationEvent() | StandOfferEvent() | SpatialEffectChangeEvent() | SpatialEffectInteractionEvent():
                # Senses supplies committed positions and observed fixture state.
                # Spatial lifecycle events retain causality, not another state writer.
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
    "capture_interval",
    "capture_lineage",
    "copy_target",
    "reduce_interval",
    "reduce_lineage",
    "seat_log_entry",
    "seed_actors",
    "stage_actors",
    "stage_lineage",
    "settle_dispositions",
]
