"""Finite Event capture: the seat-independent recorded versions each seat's projection walks."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import Mapping
from uuid import UUID

from dnd.actions import AttackEvent, JumpEvent, MovementEvent, TraverseConnectorEvent, ShoveEvent, SpellEvent
from dnd.blocks.base_item import ItemResourceChangeEvent, ItemHoldingsReleasedEvent, ItemLocationStateEvent
from dnd.blocks.equipment import EquipmentEvent
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
    MechanismInstallEvent, TraversalConnectorChangeEvent,
    Event,
    EventPhase,
    EventQueue,
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
from dnd.subjective_combat_log import SharedRenders, project_combat_log
from dnd.player.audience import PlayerAudience, resolve_audience

from dnd.player.event_record import RecordedCombatLog, RecordedEvent
from dnd.player.sheet_facts import sheet_fact
from dnd.types.actor_sheet import ActorSheetChange
from dnd.player.facts import PlayerLogEntry
from dnd.actor_projection import actor_fact_change, actor_fact_owner
from dnd.actor_projection import condition_fact as committed_condition_fact
from dnd.types.actor_facts import ActorFactChange, ConditionFact


class Disposition(StrEnum):
    """A retained header-only version's disposition: a foreign sensory payload no seat consumes, or an
    unsupported payload (publication refuses it)."""

    NOT_DISCLOSED = "not_disclosed"
    UNSUPPORTED = "unsupported"


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
class WorldInterval:
    """An interval's completed versions as the session's one world fold reads them: their seat-independent
    retained bodies (a sensory version's payload left out) and condition facts.

    Server-side projection input only: it reaches no seat's wire, spool or replay. Every seat of a session starts
    from the same one (EVENT_NATIVE_PUBLICATION_PLAN §5b).
    """

    events: tuple[tuple[int, RecordedEvent], ...] = ()
    conditions: tuple[ConditionFact, ...] = ()
    # The shared fold's actor change of each of these versions that has one, by event uuid (the session's actors).
    actor_fact_changes: Mapping[UUID, ActorFactChange] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class IntervalEnvelope:
    """One complete immutable cursor interval crossing the async seam."""

    name: str
    generation: UUID
    start_cursor: int
    end_cursor: int
    observer_uuid: UUID
    battlefield_id: str
    objective_rows: tuple[ObjectiveRow, ...]
    admitted: tuple[tuple[int, RecordedEvent], ...]
    conditions: tuple[ConditionFact, ...] = ()
    audience: PlayerAudience | None = None
    # The audience's combat-log entry of each admitted event that has one.
    logs: dict[UUID, PlayerLogEntry] = field(default_factory=dict)
    # The interval's world as every seat's session folds it.
    world_interval: WorldInterval = field(default_factory=WorldInterval)


@dataclass(slots=True)
class CaptureCheckpoint:
    """The EventQueue's actor change records, advanced once per version for every audience.

    Each non-canceled version has one record: the actor change of a completed version (plan §4), else None.
    `root_of` and `trees` place the lineages of each still-open root; `pending` keeps the records of that
    root's folded versions until it completes, so a root's capture never reads history again.
    `initiative` is the encounter's order (its start, then each join or leave); a session has one encounter.
    """

    generation: UUID
    cursor: int = 0
    root_of: dict[UUID, UUID] = field(default_factory=dict)
    trees: dict[UUID, list[UUID]] = field(default_factory=dict)
    pending: dict[UUID, dict[UUID, ActorFactChange | None]] = field(default_factory=dict)
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
    audience: PlayerAudience | None = None
    # Exact already-recorded versions that caused an observation before completion.
    observed_sources: tuple[RecordedEvent, ...] = ()
    # The native combat log of each retained event that has one, by event uuid: seat-independent (the retained
    # bodies carry none); each seat's walk projects its own entry from it (RecordedSequence 6).
    native_logs: Mapping[UUID, RecordedCombatLog] = field(default_factory=dict)
    # The shared fold's actor change of each retained event that has one, by event uuid.
    actor_fact_changes: Mapping[UUID, ActorFactChange] = field(default_factory=dict)


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
    audience: PlayerAudience | None = None,
    context: CaptureContext | None = None,
) -> IntervalEnvelope:
    """Synchronously copy one exact already-committed EventQueue interval.

    `context` carries the shared fold's records for the interval; without it
    this capture reads the history from its start.
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

    records = (context or capture_context(CaptureCheckpoint(generation), end_cursor=end_cursor)).records
    bodies = context.bodies if context is not None else {}
    completed = tuple((index, event) for index, event in indexed if event.phase is EventPhase.COMPLETION)
    return IntervalEnvelope(
        name=name,
        generation=generation,
        start_cursor=start_cursor,
        end_cursor=end_cursor,
        observer_uuid=observer_uuid,
        audience=audience,
        battlefield_id=battlefield_id,
        objective_rows=tuple(_objective_row(index, event) for index, event in indexed),
        admitted=tuple(admitted),
        conditions=tuple(fact for _, event in admitted_original if (fact := _condition_fact(event)) is not None),
        logs=logs,
        world_interval=WorldInterval(events=tuple((index, _cached_body(event, None, True, bodies))
                for index, event in completed),
            conditions=tuple(fact for _, event in completed if (fact := _condition_fact(event)) is not None),
            actor_fact_changes=_actor_fact_changes(records, (event for _, event in completed))),
    )


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


@dataclass(slots=True)
class SharedLogEntries:
    """One walk group's log entries for all its seats: each native entry rendered once per distinct disclosure
    (`SharedRenders`) and wrapped once as a `PlayerLogEntry`."""

    renders: SharedRenders = field(default_factory=SharedRenders)
    entries: dict[int, PlayerLogEntry] = field(default_factory=dict)


def seat_log_entry(log: CombatLogEntry | None, audience: PlayerAudience, *,
                   known_entity_names: Mapping[str, str] | None = None,
                   known_connector_uuids: frozenset[str] = frozenset(),
                   known_content_ids: frozenset[str] = frozenset(),
                   retained_entries: dict[int, CombatLogEntry | None] | None = None,
                   shared: SharedLogEntries | None = None) -> PlayerLogEntry | None:
    """The one projection of a native log for a seat: rendered, without nested copies or grants.

    Nested child entries inform the rendering; the seat receives each child's
    own entry with its node, so its target indices refer to those (see
    `PlayerLogEntry`). With `shared`, seats deciding alike on an entry share its rendering.
    """
    projected = project_combat_log(log, known_entity_names=known_entity_names, retained_entries=retained_entries,
        known_connector_uuids=known_connector_uuids, known_content_ids=known_content_ids,
        controlled_entity_uuids=audience.controlled_ids, observer_entity_uuids=audience.observer_ids,
        shared=shared.renders if shared is not None else None)
    if projected is None:
        return None
    if shared is not None and (entry := shared.entries.get(id(projected))) is not None:
        return entry
    entry = PlayerLogEntry(entry_type=projected.entry_type, source_name=projected.source_name,
        source_uuid=projected.source_uuid, target_name=projected.target_name, target_uuid=projected.target_uuid,
        compact=projected.compact, verbose=projected.verbose, detailed=projected.detailed, data=projected.data,
        success=projected.success)
    if shared is not None:
        shared.entries[id(projected)] = entry
    return entry


def _retained_event(event: Event, audience: PlayerAudience, *, omit_sensory_payload: bool = False,
                    bodies: dict[tuple[UUID, bool, bool | None], Event] | None = None) -> Event:
    """The seat's retained event: the shared detached body (its combat log is the seat's `logs` entry)."""
    controls = _controller_redaction(event, audience)
    return _cached_body(event, controls, omit_sensory_payload, bodies)


def _cached_body(event: Event, controls: bool | None, omit_sensory_payload: bool,
                 bodies: dict[tuple[UUID, bool, bool | None], Event] | None) -> Event:
    """A version's retained body, built once per capture for its redaction and sensory payload choice."""
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
            copied = event.model_copy(update={**common, "dice": None, "dc": event.get_dc(), "bonus": None})
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
        case WorldInitializedEvent() | WorldModifiedEvent() | TileElevationChangeEvent() | SpatialEffectChangeEvent() | SpatialEffectInteractionEvent() | SpatialChangeEvent() | MechanismInstallEvent():
            copied = event.model_copy(update=common)
        case TraversalConnectorChangeEvent():
            # The connector's cold rows are its world fact's (WorldModifiedEvent); the live connectors stay native.
            copied = event.model_copy(update={**common, "old_connector": None, "new_connector": None})
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


def _actor_fact_changes(records: Mapping[UUID, ActorFactChange | None], events: Iterable[Event]
                        ) -> dict[UUID, ActorFactChange]:
    """These retained events' actor changes, read from the one record of each."""
    return {event.uuid: change for event in events if (change := records.get(event.uuid)) is not None}


def advance_capture(checkpoint: CaptureCheckpoint, end: int) -> dict[UUID, ActorFactChange | None]:
    """Read versions up to `end` once for every audience: their records and those of roots completing here."""
    if checkpoint.generation != EventQueue.generation_id():
        raise ValueError("capture checkpoint belongs to another EventQueue generation")
    root_of, trees, pending = checkpoint.root_of, checkpoint.trees, checkpoint.pending
    records: dict[UUID, ActorFactChange | None] = {}
    for index, event in EventQueue.iter_events_since(checkpoint.cursor):
        if index >= end:
            break
        completed = event.phase is EventPhase.COMPLETION and not event.canceled
        lineage = event.lineage_uuid
        root = root_of.get(lineage)
        if root is None:
            root = lineage if event.parent_lineage is None else root_of.get(event.parent_lineage)
            if root is not None:
                root_of[lineage] = root
                trees.setdefault(root, []).append(lineage)
        if not event.canceled:
            change = actor_fact_change(event, _condition_fact(event)) if completed else None
            records[event.uuid] = change
            if root is not None:
                pending.setdefault(root, {})[event.uuid] = change
        if completed:
            match event:
                case EncounterStartEvent() | InitiativeOrderChangedEvent():
                    checkpoint.initiative = tuple(event.initiative_order)
        if event.parent_lineage is None and event.phase in (EventPhase.COMPLETION, EventPhase.CANCEL):
            # The root completes: its whole tree is captured now, never again.
            for member in trees.pop(lineage, ()):
                root_of.pop(member, None)
            records.update(pending.pop(lineage, {}))
        checkpoint.cursor = index + 1
    return records


def capture_lineage(root: Event, *, observer_uuid: UUID, audience: PlayerAudience | None = None) -> CompletedLineage:
    """Retain a closed native lineage privately after its public operation.

    Follow existing child lineages. Operation cursor ranges and callback batches
    do not establish a render unit. Observer grants remain exact facts in this
    private record; the outgoing projection decides which payloads and geometry
    an observer receives. Unknown participants must not erase observed children.
    """
    return capture_lineages((root,), observer_uuid=observer_uuid, audience=audience)[0]


@dataclass(frozen=True, slots=True)
class CaptureContext:
    """One operation's seat-independent capture over the EventQueue's existing indexes.

    `roots` are the roots it captures (by uuid, as given), `groups` their walk groups, each named by its root,
    in the roots' order, and `graphs` each group's lineage graph by that root. `records` holds each
    version's actor change record from the shared fold and `bodies` each retained event's detached body:
    every seat shares them; a seat's capture adds only its redactions.
    """

    generation: UUID
    end_cursor: int
    roots: tuple[UUID, ...] = ()
    groups: tuple[Event, ...] = ()
    graphs: dict[UUID, "LineageGraph"] = field(default_factory=dict)
    records: dict[UUID, ActorFactChange | None] = field(default_factory=dict)
    bodies: dict[tuple[UUID, bool, bool | None], Event] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class LineageGraph:
    """One root's terminal node per lineage and every version in source order, shared by every seat."""

    nodes: dict[UUID, Event]
    indexed: tuple[tuple[int, Event], ...]
    conditions: tuple[ConditionFact, ...]
    objective_rows: tuple[ObjectiveRow, ...]
    # Each node's native combat log, by its uuid (`CompletedLineage.native_logs`).
    native_logs: Mapping[UUID, CombatLogEntry]


def capture_context(checkpoint: CaptureCheckpoint, roots: tuple[Event, ...] = (), *,
                    end_cursor: int | None = None) -> CaptureContext:
    """The roots' walk groups and their graphs, then one advance of the shared fold past their last version (or
    to `end_cursor`).

    Roots whose versions interleave form one walk group: a root completing inside another root's execution
    is captured, walked, folded and published with it, in native order, so every fold (the session world,
    the seats', the clients') takes their changes in the order they happened. A group is named by its root
    completing last; a root overlapping no other is its own group.
    """
    context = CaptureContext(EventQueue.generation_id(), EventQueue.event_cursor(),
        roots=tuple(dict.fromkeys(root.uuid for root in roots)))
    graphs: dict[UUID, LineageGraph] = {}
    named: dict[UUID, Event] = {}
    # Each root's completion: its own version's index.
    completions: dict[UUID, int] = {}
    for root in roots:
        if root.uuid not in graphs:
            graphs[root.uuid] = _lineage_graph(root, context)
            named[root.uuid] = root
            completions[root.uuid] = next(index for index, event in graphs[root.uuid].indexed if event.uuid == root.uuid)
    # By first version: a root starting before the last version of the group open so far joins it.
    members: list[list[UUID]] = []
    last = -1
    for identity in sorted(graphs, key=lambda identity: graphs[identity].indexed[0][0]):
        graph = graphs[identity]
        if members and graph.indexed[0][0] < last:
            members[-1].append(identity)
        else:
            members.append([identity])
        last = max(last, graph.indexed[-1][0])
    for group in members:
        root = max(group, key=completions.__getitem__)
        context.graphs[root] = graphs[root] if len(group) == 1 else _merged_graph(
            tuple(graphs[identity] for identity in group))
    context = replace(context, groups=tuple(named[identity] for identity in context.roots if identity in context.graphs))
    end = end_cursor if end_cursor is not None else max(
        (graph.indexed[-1][0] + 1 for graph in context.graphs.values()), default=checkpoint.cursor)
    context.records.update(advance_capture(checkpoint, end))
    for graph in context.graphs.values():
        # Each version is captured from its own record: the shared fold never reads history again.
        for index, event in graph.indexed:
            if not event.canceled and event.uuid not in context.records:
                raise ValueError(f"Version {index} precedes the capture checkpoint and was not retained")
    return context


def _lineage_versions(context: CaptureContext, identity: UUID) -> tuple[tuple[int, Event], ...]:
    return tuple((index, event) for event in EventQueue.get_events_by_lineage(identity)
        if (index := EventQueue.get_event_index(event.uuid)) is not None and index < context.end_cursor)


def capture_lineages(
    roots: tuple[Event, ...], *, observer_uuid: UUID, audience: PlayerAudience | None = None,
    context: CaptureContext | None = None, omit_foreign_sensory_payloads: bool = False,
) -> tuple[CompletedLineage, ...]:
    """Project each audience from the same original operation evidence.

    Without a shared `context` this capture reads the history from its start.
    """
    audience = resolve_audience(observer_uuid, audience)
    if context is None:
        context = capture_context(CaptureCheckpoint(EventQueue.generation_id()), roots)
    elif tuple(dict.fromkeys(root.uuid for root in roots)) != context.roots:
        raise ValueError("A capture context captures the roots it was built from")
    return tuple(_capture_lineage(root, observer_uuid=observer_uuid, audience=audience, context=context,
        omit_foreign_sensory_payloads=omit_foreign_sensory_payloads) for root in context.groups)


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
    return _graph(nodes, indexed)


def _graph(nodes: dict[UUID, Event], indexed: tuple[tuple[int, Event], ...]) -> LineageGraph:
    conditions = tuple(fact for _, event in indexed
                       if event.uuid == nodes[event.lineage_uuid].uuid
                       and (fact := _condition_fact(event)) is not None)
    return LineageGraph(nodes, indexed, conditions,
                        tuple(_objective_row(index, event) for index, event in indexed),
                        {event.uuid: event.combat_log for event in nodes.values() if event.combat_log is not None})


def _merged_graph(graphs: tuple[LineageGraph, ...]) -> LineageGraph:
    """One walk group's graph: its roots' lineages and versions together, in source order."""
    nodes: dict[UUID, Event] = {}
    for graph in graphs:
        nodes.update(graph.nodes)
    if len(nodes) != sum(len(graph.nodes) for graph in graphs):
        raise ValueError("Two roots share a lineage")
    return _graph(nodes, tuple(sorted((row for graph in graphs for row in graph.indexed), key=lambda row: row[0])))


def _capture_lineage(
    root: Event, *, observer_uuid: UUID, audience: PlayerAudience, context: CaptureContext,
    omit_foreign_sensory_payloads: bool = False,
) -> CompletedLineage:
    generation = context.generation
    if generation != EventQueue.generation_id():
        raise RuntimeError("EventQueue generation changed during lineage capture")
    graph = context.graphs[root.uuid]
    nodes, indexed, conditions = graph.nodes, graph.indexed, graph.conditions
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
    retained = tuple(_retained_event(nodes[event.lineage_uuid], audience,
        omit_sensory_payload=event.uuid in omitted_sensory, bodies=context.bodies)
        for _, event in indexed if event.uuid == nodes[event.lineage_uuid].uuid)
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
        observed_sources=tuple(_retained_event(event, audience, bodies=context.bodies)
            for _, event in indexed
            if event.uuid in observed_source_ids and event.uuid not in retained_ids),
        native_logs=graph.native_logs,
        actor_fact_changes=_actor_fact_changes(context.records, retained),
    )


__all__ = [
    "CompletedLineage",
    "ConditionFact",
    "Disposition",
    "IntervalEnvelope",
    "ObjectiveRow",
    "capture_interval",
    "capture_lineage",
    "SharedLogEntries",
    "seat_log_entry",
]
