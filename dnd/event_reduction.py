"""Composition of the accepted event-knowledge policies and batch boundary."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any, TypeAlias
from uuid import UUID

from dnd.actions.standard import AttackEvent, MovementEvent, SpellEvent
from dnd.blocks.sensory import PartyKnowledge
from dnd.core.base_conditions import ConditionApplicationEvent, ConditionRemovalEvent
from dnd.core.events.encounter_events import (
    EncounterEndEvent,
    EncounterStartEvent,
    RoundEndEvent,
    RoundStartEvent,
    TurnEndEvent,
    TurnStartEvent,
)
from dnd.core.events.entity_events import EntityCreatedEvent
from dnd.core.events.events_registry import Event, EventPhase, EventQueue
from dnd.core.events.knowledge import (
    BatchId,
    CapturedEvent,
    DeliveryId,
    EventArchive,
    EventBatch,
    EventDelivery,
    EventKnowledge,
    EventKnowledgeRouter,
    Known,
    KnowledgeDiagnostic,
    KnowledgeMask,
    ReadPath,
    SourceCoverage,
    SourceDisposition,
)
from dnd.core.events.resolution_events import (
    AttackD20RollResultEvent,
    DamageAppliedEvent,
    DamageRollResultEvent,
    TakeDamageEvent,
)
from dnd.core.events.world_events import (
    SensoryUpdateEvent,
    SpatialChangeEvent,
    SpatialChangeType,
    StepMovementEvent,
    WorldInitializedEvent,
)


_BASE_EVENT_PATHS: tuple[ReadPath, ...] = (
    ("uuid",),
    ("lineage_uuid",),
    ("timestamp",),
    ("event_type",),
    ("phase",),
    ("name",),
    ("canceled",),
    ("canceled_from_phase",),
    ("parent_event",),
    ("parent_lineage",),
    ("status_message",),
    ("outcome_code",),
)

BASE_EVENT_INTENTIONALLY_SILENT_REASON = (
    "base Event has no admitted exact-class presentation policy"
)


def _observer_strings(party: PartyKnowledge) -> frozenset[str]:
    return frozenset(str(value) for value in party.observer_uuids)


def _evidence_contains_party(
    evidence: Mapping[str, set[str]],
    party: PartyKnowledge,
    key: str | None = None,
) -> bool:
    observers = _observer_strings(party)
    if key is not None:
        return bool(observers & evidence.get(key, set()))
    return any(observers & values for values in evidence.values())


def _controlled(party: PartyKnowledge, participant_uuid: UUID | None) -> bool:
    return participant_uuid is not None and participant_uuid in party.observer_uuids


def _occurrence_known(event: Event, party: PartyKnowledge) -> bool:
    if _controlled(party, event.source_entity_uuid) or _controlled(
        party,
        event.target_entity_uuid,
    ):
        return True
    return any((
        _evidence_contains_party(event.identified_entity_observer_uuids, party),
        _evidence_contains_party(event.located_entity_observer_uuids, party),
        _evidence_contains_party(event.located_position_observer_uuids, party),
    ))


def _base_party_mask(event: Event, party: PartyKnowledge) -> KnowledgeMask | None:
    if not _occurrence_known(event, party):
        return None
    paths = set(_BASE_EVENT_PATHS)
    if party.identifies_entity(event, event.source_entity_uuid):
        paths.update((("source_entity_uuid",), ("source_entity_name",)))
    if party.identifies_entity(event, event.target_entity_uuid):
        paths.update((("target_entity_uuid",), ("target_entity_name",)))
    return KnowledgeMask(paths=frozenset(paths))


def _base_mask(
    event: Event,
    party: PartyKnowledge,
    paths: Sequence[ReadPath] = (),
    collection_paths: Sequence[ReadPath] = (),
) -> KnowledgeMask:
    """Return the base event envelope plus one row's admitted paths."""
    base = _base_party_mask(event, party) or KnowledgeMask(
        paths=frozenset(_BASE_EVENT_PATHS),
    )
    return KnowledgeMask(
        paths=base.paths | frozenset(paths),
        collection_paths=frozenset(collection_paths),
    )


def _world_initialized_mask(
    knowledge: EventKnowledge[WorldInitializedEvent],
    party: PartyKnowledge,
    _paths: Sequence[ReadPath] = (),
    _collection_paths: Sequence[ReadPath] = (),
) -> KnowledgeMask:
    """Expose only battlefield identity and bounds at cold bootstrap."""
    del knowledge, party
    return KnowledgeMask.from_paths(
        *_BASE_EVENT_PATHS,
        ("battlefield_id",),
        ("battlefield_name",),
        ("bounds",),
        ("width",),
        ("height",),
    )


def _entity_created_mask(
    knowledge: EventKnowledge[EntityCreatedEvent],
    party: PartyKnowledge,
    paths: Sequence[ReadPath] = (),
    collection_paths: Sequence[ReadPath] = (),
) -> KnowledgeMask | None:
    """Admit owned entity data or the narrow data supported by contact."""
    event = knowledge.captured._snapshot
    entity_uuid = event.entity_uuid
    if entity_uuid in party.observer_uuids:
        return _base_mask(event, party, paths, collection_paths)
    if party.identifies_entity(event, entity_uuid):
        visual_paths = {
            ("entity_uuid",),
            ("entity_kind_id",),
            ("entity_name",),
            ("entity_description",),
            ("creature_type",),
            ("size",),
            ("structural_base_size",),
            ("weight",),
            ("faction",),
            ("species",),
            ("species_variant",),
            ("background",),
            ("life_state",),
            ("equipment",),
        }
        return _base_mask(
            event,
            party,
            tuple(path for path in paths if path in visual_paths),
            tuple(path for path in collection_paths if path == ("equipment",)),
        )
    if party.locates_entity(event, entity_uuid):
        return _base_mask(
            event,
            party,
            (("entity_uuid",),),
        )
    return None


def _spatial_change_mask(
    knowledge: EventKnowledge[SpatialChangeEvent],
    party: PartyKnowledge,
    paths: Sequence[ReadPath] = (),
    collection_paths: Sequence[ReadPath] = (),
) -> KnowledgeMask | None:
    """Admit only the exact spatial subject whose event-time evidence is known."""
    event = knowledge.captured._snapshot
    position_known = party.knows_position(event, event.position)
    subject_known = False
    if event.entity_uuid is not None:
        subject_known = (
            event.entity_uuid in party.observer_uuids
            or party.identifies_entity(event, event.entity_uuid)
            or party.locates_entity(event, event.entity_uuid)
        )
    if event.object_uuid is not None:
        subject_known = subject_known or party.locates_entity(event, event.object_uuid)
    if event.change_type is SpatialChangeType.TILE_CHANGED:
        if not position_known:
            return None
    elif not (position_known or subject_known or _occurrence_known(event, party)):
        return None

    admitted = set(_BASE_EVENT_PATHS)
    if position_known or subject_known:
        admitted.add(("change_type",))
        if position_known:
            admitted.add(("position",))
            admitted.update((
                ("tile_surface",),
                ("transition_from",),
                ("transition_to",),
            ))
        if subject_known:
            admitted.update((
                ("entity_uuid",),
                ("object_uuid",),
                ("placement",),
                ("object_name",),
                ("object_is_open",),
                ("object_boundary_structure",),
            ))
    collections = (
        tuple(path for path in collection_paths if path == ("light_level_map",))
        if position_known
        else ()
    )
    return KnowledgeMask(
        paths=frozenset(admitted),
        collection_paths=frozenset(collections),
    )


def _sensory_update_mask(
    knowledge: EventKnowledge[SensoryUpdateEvent],
    party: PartyKnowledge,
    paths: Sequence[ReadPath] = (),
    collection_paths: Sequence[ReadPath] = (),
) -> KnowledgeMask | None:
    event = knowledge.captured._snapshot
    if event.observer_uuid not in party.observer_uuids:
        return None
    admitted_paths = set(_BASE_EVENT_PATHS)
    admitted_paths.update(paths)
    return KnowledgeMask(
        paths=frozenset(admitted_paths),
        collection_paths=frozenset(collection_paths),
    )


def _step_movement_mask(
    knowledge: EventKnowledge[StepMovementEvent],
    party: PartyKnowledge,
    paths: Sequence[ReadPath] = (),
    collection_paths: Sequence[ReadPath] = (),
) -> KnowledgeMask | None:
    event = knowledge.captured._snapshot
    base = _base_party_mask(event, party)
    if base is None:
        return None
    admitted = set(base.paths)
    row_paths = set(paths)
    for path in (("committed",), ("trajectory",)):
        if path in row_paths:
            admitted.add(path)
    if not event.committed:
        return KnowledgeMask(
            paths=frozenset(admitted),
        )
    controls_mover = _controlled(party, event.source_entity_uuid)
    if controls_mover or party.knows_position(event, event.from_position):
        for path in (("from_position",), ("from_elevation_feet",)):
            if path in row_paths:
                admitted.add(path)
    if controls_mover or party.knows_position(event, event.to_position):
        for path in (("to_position",), ("to_elevation_feet",)):
            if path in row_paths:
                admitted.add(path)
    if controls_mover or all(
        party.knows_position(event, position)
        for position in event.disclosed_path
    ):
        if ("disclosed_path",) in row_paths:
            admitted.add(("disclosed_path",))
    return KnowledgeMask(
        paths=frozenset(admitted),
    )


def _attack_mask(
    knowledge: EventKnowledge[Event],
    party: PartyKnowledge,
    _paths: Sequence[ReadPath] = (),
    _collection_paths: Sequence[ReadPath] = (),
) -> KnowledgeMask | None:
    event = knowledge.captured._snapshot
    base = _base_party_mask(event, party)
    if base is None:
        return None
    paths = set(base.paths)
    paths.update((
        ("presentation_kind",),
        ("weapon_name",),
        ("attack_outcome",),
    ))
    return KnowledgeMask(
        paths=frozenset(paths),
        collection_paths=frozenset((("damage_types",),)),
    )


def _damage_applied_mask(
    knowledge: EventKnowledge[Event],
    party: PartyKnowledge,
    _paths: Sequence[ReadPath] = (),
    _collection_paths: Sequence[ReadPath] = (),
) -> KnowledgeMask | None:
    event = knowledge.captured._snapshot
    if not _occurrence_known(event, party):
        return None
    base = _base_party_mask(event, party)
    if base is None:
        return None
    paths = set(base.paths)
    paths.update((
        ("applied_damage",),
        ("damage_type",),
    ))
    if _controlled(party, event.target_entity_uuid):
        paths.update((
            ("normal_hit_point_damage",),
            ("temporary_hit_point_damage",),
            ("resulting_normal_hp",),
            ("resulting_temporary_hp",),
            ("effect_id",),
        ))
    return KnowledgeMask(paths=frozenset(paths))


def _boundary_mask(
    event: Event,
    party: PartyKnowledge,
    paths: Sequence[ReadPath],
) -> KnowledgeMask | None:
    """Expose one public encounter boundary without its private roster."""
    admitted = set(_BASE_EVENT_PATHS)
    if party.identifies_entity(event, event.source_entity_uuid):
        admitted.update((("source_entity_uuid",), ("source_entity_name",)))
    if party.identifies_entity(event, event.target_entity_uuid):
        admitted.update((("target_entity_uuid",), ("target_entity_name",)))
    admitted.update(paths)
    return KnowledgeMask(paths=frozenset(admitted))


def _encounter_boundary_mask(
    knowledge: EventKnowledge[Event],
    party: PartyKnowledge,
    _paths: Sequence[ReadPath] = (),
    _collection_paths: Sequence[ReadPath] = (),
) -> KnowledgeMask | None:
    """Route encounter start/end using identity, never the complete roster."""
    event = knowledge.captured._snapshot
    known = _occurrence_known(event, party)
    if isinstance(event, (EncounterStartEvent, EncounterEndEvent)):
        known = known or bool(set(event.combatant_uuids) & set(party.observer_uuids))
    if not known:
        return None
    paths = (("encounter_uuid",),)
    if isinstance(event, EncounterEndEvent):
        paths += (("reason",),)
    return _boundary_mask(event, party, paths)


def _round_boundary_mask(
    knowledge: EventKnowledge[Event],
    party: PartyKnowledge,
    _paths: Sequence[ReadPath] = (),
    _collection_paths: Sequence[ReadPath] = (),
) -> KnowledgeMask | None:
    """Expose public round identity and number, but no participant data."""
    event = knowledge.captured._snapshot
    if not isinstance(event, (RoundStartEvent, RoundEndEvent)):
        return None
    return _boundary_mask(event, party, (("encounter_uuid",), ("round_number",)))


def _turn_boundary_mask(
    knowledge: EventKnowledge[Event],
    party: PartyKnowledge,
    _paths: Sequence[ReadPath] = (),
    _collection_paths: Sequence[ReadPath] = (),
) -> KnowledgeMask | None:
    """Expose a turn actor only when that actor is independently known."""
    event = knowledge.captured._snapshot
    if not isinstance(event, (TurnStartEvent, TurnEndEvent)):
        return None
    actor_known = (
        event.entity_uuid in party.observer_uuids
        or party.identifies_entity(event, event.entity_uuid)
        or party.locates_entity(event, event.entity_uuid)
    )
    if not (_occurrence_known(event, party) or actor_known):
        return None
    paths = [("encounter_uuid",), ("round_number",), ("turn_index",)]
    if actor_known:
        paths.append(("entity_uuid",))
    return _boundary_mask(event, party, tuple(paths))


def _movement_action_mask(
    knowledge: EventKnowledge[Event],
    party: PartyKnowledge,
    paths: Sequence[ReadPath] = (),
    collection_paths: Sequence[ReadPath] = (),
) -> KnowledgeMask | None:
    """Separate public movement outcome from private controller/path detail."""
    event = knowledge.captured._snapshot
    if not isinstance(event, MovementEvent):
        return None
    base = _base_party_mask(event, party)
    if base is None:
        return None
    controlled = _controlled(party, event.source_entity_uuid)
    admitted = set(base.paths)
    admitted.update((
        ("movement_mode",),
        ("trajectory",),
        ("termination_reason",),
    ))
    if controlled:
        admitted.update((
            ("start_position",),
            ("end_position",),
            ("requested_end_position",),
            ("objective_end_position",),
        ))
        collections = tuple(
            path
            for path in collection_paths
            if path in {("path",), ("costs",)}
        )
    else:
        # A perceived movement occurrence is public evidence that movement
        # happened, not an authorization to reopen its requested/objective
        # route or path.  Exact geometry belongs to the controlled actor.
        collections = ()
    return KnowledgeMask(
        paths=frozenset(admitted),
        collection_paths=frozenset(collections),
    )


def _attack_roll_mask(
    knowledge: EventKnowledge[Event],
    party: PartyKnowledge,
    _paths: Sequence[ReadPath] = (),
    _collection_paths: Sequence[ReadPath] = (),
) -> KnowledgeMask | None:
    """Expose a public attack-roll result, not its private roll machinery."""
    event = knowledge.captured._snapshot
    base = _base_party_mask(event, party)
    if base is None:
        return None
    admitted = set(base.paths)
    admitted.add(("result",))
    if (
        _controlled(party, event.source_entity_uuid)
        or _controlled(party, event.target_entity_uuid)
    ):
        admitted.update((("roll_type",), ("weapon_slot",)))
    return KnowledgeMask(paths=frozenset(admitted))


def _damage_roll_mask(
    knowledge: EventKnowledge[Event],
    party: PartyKnowledge,
    _paths: Sequence[ReadPath] = (),
    _collection_paths: Sequence[ReadPath] = (),
) -> KnowledgeMask | None:
    """Keep damage packets and roll context with the controlled participant."""
    event = knowledge.captured._snapshot
    base = _base_party_mask(event, party)
    if base is None:
        return None
    controlled = (
        _controlled(party, event.source_entity_uuid)
        or _controlled(party, event.target_entity_uuid)
    )
    admitted = set(base.paths)
    if not controlled:
        return KnowledgeMask(paths=frozenset(admitted))
    admitted.update((("roll_type",), ("weapon_slot",), ("attack_outcome",)))
    return KnowledgeMask(
        paths=frozenset(admitted),
        collection_paths=frozenset((("damage_packets",),)),
    )


def _take_damage_mask(
    knowledge: EventKnowledge[Event],
    party: PartyKnowledge,
    _paths: Sequence[ReadPath] = (),
    _collection_paths: Sequence[ReadPath] = (),
) -> KnowledgeMask | None:
    """Expose public damage outcome, with resulting HP owner-controlled."""
    event = knowledge.captured._snapshot
    base = _base_party_mask(event, party)
    if base is None:
        return None
    admitted = set(base.paths)
    admitted.update((("total_damage",), ("final_damage",)))
    if _controlled(party, event.target_entity_uuid):
        admitted.update((
            ("normal_hit_point_damage_cap",),
            ("resulting_hp",),
            ("effect_id",),
        ))
    return KnowledgeMask(paths=frozenset(admitted))


def _condition_lifecycle_mask(
    knowledge: EventKnowledge[Event],
    party: PartyKnowledge,
    _paths: Sequence[ReadPath] = (),
    _collection_paths: Sequence[ReadPath] = (),
) -> KnowledgeMask | None:
    """Expose condition identity/outcome, not unrelated target consequences."""
    event = knowledge.captured._snapshot
    base = _base_party_mask(event, party)
    if base is None:
        return None
    admitted = set(base.paths)
    admitted.add(("condition_behavior_id",))
    if isinstance(event, ConditionApplicationEvent):
        admitted.add(("application_disposition",))
    if _controlled(party, event.target_entity_uuid):
        admitted.update((("resulting_ac",), ("resulting_max_hp",)))
    if isinstance(event, ConditionRemovalEvent):
        admitted.add(("expired",))
    return KnowledgeMask(paths=frozenset(admitted))


def _spell_action_mask(
    knowledge: EventKnowledge[Event],
    party: PartyKnowledge,
    _paths: Sequence[ReadPath] = (),
    _collection_paths: Sequence[ReadPath] = (),
) -> KnowledgeMask | None:
    """Separate public spell identity from private save/roll mechanics."""
    event = knowledge.captured._snapshot
    base = _base_party_mask(event, party)
    if base is None:
        return None
    controlled_source = _controlled(party, event.source_entity_uuid)
    controlled_target = _controlled(party, event.target_entity_uuid)
    admitted = set(base.paths)
    admitted.update((
        ("spell_id",),
        ("spell_school",),
        ("verbal",),
        ("save_ability",),
        ("save_success",),
        ("aoe_shape_type",),
        ("range_type",),
        ("projectile_type",),
    ))
    if controlled_source:
        admitted.update((("spell_level",), ("cast_at_level",), ("source_position",)))
    if controlled_target:
        admitted.update((
            ("save_dc",),
            ("save_bonus",),
            ("aoe_radius_ft",),
            ("range_ft",),
        ))
    collections = (("damage_types",),) if controlled_source or controlled_target else ()
    return KnowledgeMask(
        paths=frozenset(admitted),
        collection_paths=frozenset(collections),
    )


ProvenanceReference: TypeAlias = tuple[UUID, int, ReadPath]
SemanticKey: TypeAlias = tuple[object, ReadPath]


_ManifestPolicy: TypeAlias = Callable[
    [EventKnowledge[Any], PartyKnowledge, Sequence[ReadPath], Sequence[ReadPath]],
    KnowledgeMask | None,
]
_ProvenancePolicy: TypeAlias = Callable[
    [CapturedEvent[Any], UUID],
    dict[SemanticKey, ProvenanceReference],
]
_Formatter: TypeAlias = Callable[[EventKnowledge[Any]], str]
_ManifestRow: TypeAlias = tuple[
    type[Event],
    _ManifestPolicy,
    tuple[ReadPath, ...],
    tuple[ReadPath, ...],
    str,
    tuple[ReadPath, ...],
    _ProvenancePolicy,
    _Formatter,
]


def _format_fields(
    knowledge: EventKnowledge[Any],
    title: str,
    fields: Sequence[tuple[str, ReadPath]] = (),
    collections: Sequence[tuple[str, ReadPath]] = (),
) -> str:
    """Build plain text solely from values admitted by one knowledge mask."""
    parts = [title]
    base_fields = (
        ("uuid", ("uuid",)),
        ("lineage", ("lineage_uuid",)),
        ("phase", ("phase",)),
        ("type", ("event_type",)),
        ("name", ("name",)),
        ("canceled", ("canceled",)),
    )
    for label, path in (*base_fields, *fields):
        value = knowledge.read(path)
        if isinstance(value, Known):
            parts.append(f"{label}={value.value}")
    for label, path in collections:
        values = knowledge.known_items(path)
        if isinstance(values, Known):
            parts.append(f"{label}_count={len(values.value)}")
    return " ".join(parts)


def _format_world_initialized(
    knowledge: EventKnowledge[WorldInitializedEvent],
) -> str:
    return _format_fields(
        knowledge,
        "World initialized",
        fields=(
            ("battlefield", ("battlefield_id",)),
            ("name", ("battlefield_name",)),
            ("bounds", ("bounds",)),
            ("width", ("width",)),
            ("height", ("height",)),
        ),
    )


def _format_entity_created(
    knowledge: EventKnowledge[EntityCreatedEvent],
) -> str:
    return _format_fields(
        knowledge,
        "Entity created",
        fields=(
            ("entity", ("entity_uuid",)),
            ("name", ("entity_name",)),
            ("kind", ("entity_kind_id",)),
            ("life", ("life_state",)),
        ),
        collections=(("equipment", ("equipment",)),),
    )


def _format_spatial_change(
    knowledge: EventKnowledge[SpatialChangeEvent],
) -> str:
    return _format_fields(
        knowledge,
        "Spatial change",
        fields=(
            ("change", ("change_type",)),
            ("position", ("position",)),
            ("entity", ("entity_uuid",)),
            ("object", ("object_uuid",)),
            ("name", ("object_name",)),
            ("open", ("object_is_open",)),
        ),
    )


def _format_sensory_update(
    knowledge: EventKnowledge[SensoryUpdateEvent],
) -> str:
    return _format_fields(
        knowledge,
        "Sensory update",
        fields=(
            ("observer", ("observer_uuid",)),
            ("reason", ("update_reason",)),
            ("observer_position", ("observer_position",)),
        ),
        collections=(
            ("visible_added", ("visible_cells_added",)),
            ("visible_removed", ("visible_cells_removed",)),
            ("contacts", ("entity_contacts_changed",)),
            ("objects", ("object_contacts_changed",)),
        ),
    )


def _format_encounter_boundary(
    knowledge: EventKnowledge[Any],
) -> str:
    return _format_fields(
        knowledge,
        "Encounter boundary",
        fields=(("encounter", ("encounter_uuid",)), ("reason", ("reason",))),
    )


def _format_encounter_start(
    knowledge: EventKnowledge[EncounterStartEvent],
) -> str:
    return _format_encounter_boundary(knowledge)


def _format_encounter_end(
    knowledge: EventKnowledge[EncounterEndEvent],
) -> str:
    return _format_encounter_boundary(knowledge)


def _format_round_boundary(
    knowledge: EventKnowledge[Any],
) -> str:
    return _format_fields(
        knowledge,
        "Round boundary",
        fields=(
            ("encounter", ("encounter_uuid",)),
            ("round", ("round_number",)),
        ),
    )


def _format_round_start(
    knowledge: EventKnowledge[RoundStartEvent],
) -> str:
    return _format_round_boundary(knowledge)


def _format_round_end(
    knowledge: EventKnowledge[RoundEndEvent],
) -> str:
    return _format_round_boundary(knowledge)


def _format_turn_boundary(
    knowledge: EventKnowledge[Any],
) -> str:
    return _format_fields(
        knowledge,
        "Turn boundary",
        fields=(
            ("encounter", ("encounter_uuid",)),
            ("actor", ("entity_uuid",)),
            ("round", ("round_number",)),
            ("turn", ("turn_index",)),
            ("actions", ("actions_used",)),
            ("bonus_actions", ("bonus_actions_used",)),
            ("movement", ("movement_used",)),
        ),
    )


def _format_turn_start(
    knowledge: EventKnowledge[TurnStartEvent],
) -> str:
    return _format_turn_boundary(knowledge)


def _format_turn_end(
    knowledge: EventKnowledge[TurnEndEvent],
) -> str:
    return _format_turn_boundary(knowledge)


def _format_movement(knowledge: EventKnowledge[MovementEvent]) -> str:
    return _format_fields(
        knowledge,
        "Movement",
        fields=(
            ("from", ("start_position",)),
            ("to", ("end_position",)),
            ("mode", ("movement_mode",)),
            ("trajectory", ("trajectory",)),
            ("result", ("termination_reason",)),
        ),
        collections=(("path", ("path",)), ("costs", ("costs",))),
    )


def _format_step(knowledge: EventKnowledge[StepMovementEvent]) -> str:
    return _format_fields(
        knowledge,
        "Movement step",
        fields=(
            ("from", ("from_position",)),
            ("to", ("to_position",)),
            ("from_elevation", ("from_elevation_feet",)),
            ("to_elevation", ("to_elevation_feet",)),
            ("trajectory", ("trajectory",)),
        ),
    )


def _format_attack(knowledge: EventKnowledge[AttackEvent]) -> str:
    return _format_fields(
        knowledge,
        "Attack",
        fields=(
            ("weapon", ("weapon_name",)),
            ("outcome", ("attack_outcome",)),
        ),
        collections=(("damage_types", ("damage_types",)),),
    )


def _format_attack_roll(
    knowledge: EventKnowledge[AttackD20RollResultEvent],
) -> str:
    return _format_fields(
        knowledge,
        "Attack roll",
        fields=(("result", ("result",)), ("slot", ("weapon_slot",))),
    )


def _format_damage_roll(
    knowledge: EventKnowledge[DamageRollResultEvent],
) -> str:
    return _format_fields(
        knowledge,
        "Damage roll",
        fields=(
            ("roll_type", ("roll_type",)),
            ("slot", ("weapon_slot",)),
            ("outcome", ("attack_outcome",)),
        ),
        collections=(("packets", ("damage_packets",)),),
    )


def _format_take_damage(knowledge: EventKnowledge[TakeDamageEvent]) -> str:
    return _format_fields(
        knowledge,
        "Damage received",
        fields=(
            ("total", ("total_damage",)),
            ("final", ("final_damage",)),
            ("effect", ("effect_id",)),
        ),
    )


def _format_damage_applied(
    knowledge: EventKnowledge[DamageAppliedEvent],
) -> str:
    return _format_fields(
        knowledge,
        "Damage applied",
        fields=(
            ("damage", ("applied_damage",)),
            ("type", ("damage_type",)),
            ("effect", ("effect_id",)),
        ),
    )


def _format_condition(
    knowledge: EventKnowledge[Any],
) -> str:
    return _format_fields(
        knowledge,
        "Condition",
        fields=(
            ("behavior", ("condition_behavior_id",)),
            ("disposition", ("application_disposition",)),
            ("expired", ("expired",)),
            ("ac", ("resulting_ac",)),
            ("max_hp", ("resulting_max_hp",)),
        ),
    )


def _format_condition_application(
    knowledge: EventKnowledge[ConditionApplicationEvent],
) -> str:
    return _format_condition(knowledge)


def _format_condition_removal(
    knowledge: EventKnowledge[ConditionRemovalEvent],
) -> str:
    return _format_condition(knowledge)


def _format_spell(knowledge: EventKnowledge[SpellEvent]) -> str:
    return _format_fields(
        knowledge,
        "Spell",
        fields=(
            ("spell", ("spell_id",)),
            ("school", ("spell_school",)),
            ("save", ("save_success",)),
            ("shape", ("aoe_shape_type",)),
            ("range", ("range_ft",)),
        ),
        collections=(("damage_types", ("damage_types",)),),
    )


def _provenance_reference(
    captured: CapturedEvent[Event],
    generation_id: UUID,
    key: object,
    semantic_path: ReadPath,
    source_path: ReadPath | None = None,
) -> tuple[SemanticKey, ProvenanceReference]:
    actual_path = semantic_path if source_path is None else source_path
    return (
        (key, semantic_path),
        (generation_id, captured.source_index, actual_path),
    )


def _no_provenance(
    _captured: CapturedEvent[Event],
    _generation_id: UUID,
) -> dict[SemanticKey, ProvenanceReference]:
    return {}


def _world_initialized_provenance(
    captured: CapturedEvent[Event],
    generation_id: UUID,
) -> dict[SemanticKey, ProvenanceReference]:
    event = captured._snapshot
    assert isinstance(event, WorldInitializedEvent)
    updates: dict[SemanticKey, ProvenanceReference] = {}
    tile_fields = (
        "surface",
        "name",
        "elevation_steps",
        "surface_kind",
        "slope_axis",
    )
    for tile_index, tile in enumerate(event.tiles):
        for field_name in tile_fields:
            source_path = ("tiles", tile_index, field_name)
            semantic_path = (
                ("tile_surface",)
                if field_name == "surface"
                else source_path
            )
            updates[_provenance_reference(
                captured,
                generation_id,
                tile.position,
                semantic_path,
                source_path,
            )[0]] = (
                generation_id,
                captured.source_index,
                source_path,
            )
    item_fields = (
        "item_uuid",
        "semantic_key",
        "name",
        "description",
        "item_kind",
        "rarity",
        "tags",
        "boundary_structure",
        "is_open",
    )
    for object_index, object_state in enumerate(event.objects):
        object_uuid = object_state.placement.object_uuid
        placement_path = ("objects", object_index, "placement")
        updates[_provenance_reference(
            captured,
            generation_id,
            object_uuid,
            ("placement",),
            placement_path,
        )[0]] = (
            generation_id,
            captured.source_index,
            placement_path,
        )
        item_semantic_paths = {
            "item_uuid": ("object_uuid",),
            "name": ("object_name",),
            "boundary_structure": ("object_boundary_structure",),
            "is_open": ("object_is_open",),
        }
        for field_name in item_fields:
            source_path = ("objects", object_index, "item", field_name)
            semantic_path = item_semantic_paths.get(field_name, source_path)
            updates[_provenance_reference(
                captured,
                generation_id,
                object_uuid,
                semantic_path,
                source_path,
            )[0]] = (
                generation_id,
                captured.source_index,
                source_path,
            )
    connector_fields = (
        "kind",
        "authored_id",
    )
    for connector_index, connector in enumerate(event.connectors):
        for endpoint_index, endpoint in enumerate(connector.endpoints):
            endpoint_path = ("connectors", connector_index, "endpoints", endpoint_index)
            updates[_provenance_reference(
                captured,
                generation_id,
                endpoint,
                endpoint_path,
                endpoint_path,
            )[0]] = (
                generation_id,
                captured.source_index,
                endpoint_path,
            )
            for field_name in connector_fields:
                source_path = ("connectors", connector_index, field_name)
                updates[_provenance_reference(
                    captured,
                    generation_id,
                    endpoint,
                    source_path,
                    source_path,
                )[0]] = (
                    generation_id,
                    captured.source_index,
                    source_path,
                )
    return updates


def _entity_created_provenance(
    captured: CapturedEvent[Event],
    generation_id: UUID,
) -> dict[SemanticKey, ProvenanceReference]:
    event = captured._snapshot
    assert isinstance(event, EntityCreatedEvent)
    fields = (
        "entity_uuid",
        "entity_kind_id",
        "entity_name",
        "entity_description",
        "creature_type",
        "size",
        "structural_base_size",
        "life_state",
        "equipment",
    )
    return {
        _provenance_reference(captured, generation_id, event.entity_uuid, (field_name,))[0]: (
            generation_id,
            captured.source_index,
            (field_name,),
        )
        for field_name in fields
    }


def _spatial_change_provenance(
    captured: CapturedEvent[Event],
    generation_id: UUID,
) -> dict[SemanticKey, ProvenanceReference]:
    event = captured._snapshot
    assert isinstance(event, SpatialChangeEvent)
    updates: dict[SemanticKey, ProvenanceReference] = {}

    def add(
        key: object,
        semantic_path: ReadPath,
        source_path: ReadPath,
    ) -> None:
        updates[_provenance_reference(
            captured,
            generation_id,
            key,
            semantic_path,
            source_path,
        )[0]] = (
            generation_id,
            captured.source_index,
            source_path,
        )

    tile_fields = (
        "tile_surface",
    )
    for field_name in tile_fields:
        if getattr(event, field_name) is not None:
            add(event.position, ("tile_surface",), (field_name,))
    if event.entity_uuid is not None:
        add(event.entity_uuid, ("entity_uuid",), ("entity_uuid",))
        add(event.entity_uuid, ("position",), ("position",))
    if event.object_uuid is not None:
        object_fields = {
            "object_uuid": ("object_uuid",),
            "position": ("position",),
            "placement": ("placement",),
            "object_name": ("object_name",),
            "object_is_open": ("object_is_open",),
            "object_boundary_structure": ("object_boundary_structure",),
        }
        for field_name, semantic_path in object_fields.items():
            if getattr(event, field_name) is not None:
                add(event.object_uuid, semantic_path, (field_name,))
    return updates


def _movement_provenance(
    captured: CapturedEvent[Event],
    generation_id: UUID,
) -> dict[SemanticKey, ProvenanceReference]:
    event = captured._snapshot
    assert isinstance(event, MovementEvent)
    paths = (
        (("entity_uuid",), ("source_entity_uuid",)),
        (("position",), ("end_position",)),
    )
    return {
        _provenance_reference(
            captured,
            generation_id,
            event.source_entity_uuid,
            semantic_path,
            source_path,
        )[0]: (
            generation_id,
            captured.source_index,
            source_path,
        )
        for semantic_path, source_path in paths
    }


def _step_movement_provenance(
    captured: CapturedEvent[Event],
    generation_id: UUID,
) -> dict[SemanticKey, ProvenanceReference]:
    event = captured._snapshot
    assert isinstance(event, StepMovementEvent)
    paths = (
        (("entity_uuid",), ("source_entity_uuid",)),
        (("position",), ("to_position",)),
    )
    return {
        _provenance_reference(
            captured,
            generation_id,
            event.source_entity_uuid,
            semantic_path,
            source_path,
        )[0]: (
            generation_id,
            captured.source_index,
            source_path,
        )
        for semantic_path, source_path in paths
    }


# This is the one Slice 3.3 policy/provenance manifest.  Every entry names the
# concrete event class, its party selector, admitted scalar and collection
# paths, its source-coverage role, and the existing paths that may receive a
# reference-only provenance update.  The base Event route below is retained
# solely for the E1/E2 intentionally-silent event contract.
_CONCRETE_EVENT_MANIFEST: tuple[_ManifestRow, ...] = (
    (
        WorldInitializedEvent,
        _world_initialized_mask,
        (("battlefield_id",), ("battlefield_name",), ("bounds",), ("width",), ("height",)),
        (),
        "bootstrap",
        (("battlefield_id",), ("tiles",), ("objects",), ("connectors",)),
        _world_initialized_provenance,
        _format_world_initialized,
    ),
    (
        EntityCreatedEvent,
        _entity_created_mask,
        (("source_entity_uuid",), ("source_entity_name",), ("target_entity_uuid",), ("target_entity_name",), ("entity_uuid",), ("entity_kind_id",), ("entity_name",), ("entity_description",), ("creature_type",), ("size",), ("structural_base_size",), ("weight",), ("faction",), ("species",), ("species_variant",), ("background",), ("life_state",)),
        (("items",), ("inventory_item_uuids",), ("equipment",), ("action_ids",), ("condition_ids",)),
        "entity_creation",
        (("entity_uuid",), ("entity_name",), ("life_state",)),
        _entity_created_provenance,
        _format_entity_created,
    ),
    (
        SpatialChangeEvent,
        _spatial_change_mask,
        (("source_entity_uuid",), ("source_entity_name",), ("target_entity_uuid",), ("target_entity_name",), ("position",), ("entity_uuid",), ("object_uuid",), ("old_position",), ("placement",), ("previous_placement",), ("tile_surface",), ("object_name",), ("object_is_open",), ("object_boundary_structure",), ("transition_from",), ("transition_to",), ("change_type",)),
        (("light_level_map",),),
        "scene_state",
        (("position",), ("entity_uuid",), ("object_uuid",), ("placement",)),
        _spatial_change_provenance,
        _format_spatial_change,
    ),
    (
        SensoryUpdateEvent,
        _sensory_update_mask,
        (
            ("source_entity_uuid",),
            ("source_entity_name",),
            ("target_entity_uuid",),
            ("target_entity_name",),
            ("observer_uuid",),
            ("observer_position",),
            ("observer_position_changed",),
            ("cause_event_uuid",),
            ("update_reason",),
            ("sense_modes_changed",),
            ("passive_perception_changed",),
            ("passive_perception",),
            ("visual_access_changed",),
            ("visual_access",),
            ("paths_dirty",),
        ),
        (
            ("visible_cells_added",),
            ("visible_cells_removed",),
            ("seen_cells_added",),
            ("entity_contacts_changed",),
            ("entity_contacts_removed",),
            ("object_contacts_changed",),
            ("object_contacts_removed",),
            ("effective_light_levels_changed",),
            ("sense_modes",),
        ),
        "sensory_projection",
        (("observer_uuid",), ("observer_position",), ("visible_cells_added",), ("entity_contacts_changed",), ("object_contacts_changed",)),
        _no_provenance,
        _format_sensory_update,
    ),
    (
        EncounterStartEvent,
        _encounter_boundary_mask,
        (("source_entity_uuid",), ("source_entity_name",), ("target_entity_uuid",), ("target_entity_name",), ("encounter_uuid",)),
        (("combatant_uuids",), ("initiative_order",)),
        "encounter_start",
        (("encounter_uuid",),),
        _no_provenance,
        _format_encounter_start,
    ),
    (
        RoundStartEvent,
        _round_boundary_mask,
        (("source_entity_uuid",), ("source_entity_name",), ("target_entity_uuid",), ("target_entity_name",), ("encounter_uuid",), ("round_number",)),
        (),
        "round_start",
        (("encounter_uuid",), ("round_number",)),
        _no_provenance,
        _format_round_start,
    ),
    (
        TurnStartEvent,
        _turn_boundary_mask,
        (("source_entity_uuid",), ("source_entity_name",), ("target_entity_uuid",), ("target_entity_name",), ("encounter_uuid",), ("entity_uuid",), ("round_number",), ("turn_index",)),
        (),
        "turn_start",
        (("encounter_uuid",), ("entity_uuid",)),
        _no_provenance,
        _format_turn_start,
    ),
    (
        MovementEvent,
        _movement_action_mask,
        (("source_entity_uuid",), ("source_entity_name",), ("target_entity_uuid",), ("target_entity_name",), ("start_position",), ("end_position",), ("requested_end_position",), ("objective_end_position",), ("movement_mode",), ("trajectory",), ("termination_reason",), ("controller_revalidation",), ("controller_revalidation_reason",)),
        (("path",), ("costs",)),
        "movement",
        (("source_entity_uuid",), ("end_position",), ("objective_end_position",)),
        _movement_provenance,
        _format_movement,
    ),
    (
        StepMovementEvent,
        _step_movement_mask,
        (
            ("source_entity_uuid",),
            ("source_entity_name",),
            ("target_entity_uuid",),
            ("target_entity_name",),
            ("committed",),
            ("from_position",),
            ("from_elevation_feet",),
            ("to_position",),
            ("to_elevation_feet",),
            ("disclosed_path",),
            ("trajectory",),
        ),
        (),
        "movement_step",
        (("source_entity_uuid",), ("from_position",), ("to_position",)),
        _step_movement_provenance,
        _format_step,
    ),
    (
        AttackEvent,
        _attack_mask,
        (("source_entity_uuid",), ("source_entity_name",), ("target_entity_uuid",), ("target_entity_name",), ("weapon_slot",), ("range",), ("is_long_range",), ("is_threatened",), ("attack_outcome",), ("weapon_name",), ("override_ability",), ("presentation_kind",)),
        (("damage_types",),),
        "attack",
        (("source_entity_uuid",), ("target_entity_uuid",), ("weapon_name",)),
        _no_provenance,
        _format_attack,
    ),
    (
        AttackD20RollResultEvent,
        _attack_roll_mask,
        (("source_entity_uuid",), ("source_entity_name",), ("target_entity_uuid",), ("target_entity_name",), ("roll_type",), ("weapon_slot",), ("result",)),
        (),
        "attack_resolution",
        (("source_entity_uuid",), ("target_entity_uuid",)),
        _no_provenance,
        _format_attack_roll,
    ),
    (
        DamageRollResultEvent,
        _damage_roll_mask,
        (("source_entity_uuid",), ("source_entity_name",), ("target_entity_uuid",), ("target_entity_name",), ("roll_type",), ("weapon_slot",), ("attack_outcome",)),
        (("damage_packets",),),
        "damage_resolution",
        (("source_entity_uuid",), ("target_entity_uuid",)),
        _no_provenance,
        _format_damage_roll,
    ),
    (
        TakeDamageEvent,
        _take_damage_mask,
        (("source_entity_uuid",), ("source_entity_name",), ("target_entity_uuid",), ("target_entity_name",), ("total_damage",), ("final_damage",), ("normal_hit_point_damage_cap",), ("resulting_hp",), ("effect_id",)),
        (),
        "damage_application",
        (("source_entity_uuid",), ("target_entity_uuid",), ("effect_id",)),
        _no_provenance,
        _format_take_damage,
    ),
    (
        DamageAppliedEvent,
        _damage_applied_mask,
        (("source_entity_uuid",), ("source_entity_name",), ("target_entity_uuid",), ("target_entity_name",), ("applied_damage",), ("normal_hit_point_damage",), ("temporary_hit_point_damage",), ("resulting_normal_hp",), ("resulting_temporary_hp",), ("damage_type",), ("effect_id",)),
        (),
        "damage_applied",
        (("source_entity_uuid",), ("target_entity_uuid",), ("effect_id",)),
        _no_provenance,
        _format_damage_applied,
    ),
    (
        ConditionApplicationEvent,
        _condition_lifecycle_mask,
        (("source_entity_uuid",), ("source_entity_name",), ("target_entity_uuid",), ("target_entity_name",), ("resulting_ac",), ("resulting_max_hp",), ("application_disposition",), ("condition_behavior_id",)),
        (),
        "condition_application",
        (("source_entity_uuid",), ("target_entity_uuid",), ("condition_behavior_id",)),
        _no_provenance,
        _format_condition_application,
    ),
    (
        ConditionRemovalEvent,
        _condition_lifecycle_mask,
        (("source_entity_uuid",), ("source_entity_name",), ("target_entity_uuid",), ("target_entity_name",), ("expired",), ("resulting_ac",), ("resulting_max_hp",), ("condition_behavior_id",)),
        (),
        "condition_removal",
        (("source_entity_uuid",), ("target_entity_uuid",), ("condition_behavior_id",)),
        _no_provenance,
        _format_condition_removal,
    ),
    (
        SpellEvent,
        _spell_action_mask,
        (("source_entity_uuid",), ("source_entity_name",), ("target_entity_uuid",), ("target_entity_name",), ("spell_id",), ("spell_level",), ("cast_at_level",), ("spell_school",), ("verbal",), ("source_position",), ("area_geometry",), ("is_threatened",), ("save_ability",), ("save_dc",), ("save_success",), ("save_bonus",), ("aoe_shape_type",), ("aoe_radius_ft",), ("range_type",), ("range_ft",), ("projectile_type",)),
        (("damage_types",),),
        "spell",
        (("source_entity_uuid",), ("target_entity_uuid",), ("source_position",)),
        _no_provenance,
        _format_spell,
    ),
    (
        TurnEndEvent,
        _turn_boundary_mask,
        (("source_entity_uuid",), ("source_entity_name",), ("target_entity_uuid",), ("target_entity_name",), ("encounter_uuid",), ("entity_uuid",), ("round_number",), ("turn_index",), ("actions_used",), ("bonus_actions_used",), ("movement_used",)),
        (),
        "turn_end",
        (("encounter_uuid",), ("entity_uuid",)),
        _no_provenance,
        _format_turn_end,
    ),
    (
        RoundEndEvent,
        _round_boundary_mask,
        (("source_entity_uuid",), ("source_entity_name",), ("target_entity_uuid",), ("target_entity_name",), ("encounter_uuid",), ("round_number",)),
        (),
        "round_end",
        (("encounter_uuid",), ("round_number",)),
        _no_provenance,
        _format_round_end,
    ),
    (
        EncounterEndEvent,
        _encounter_boundary_mask,
        (("source_entity_uuid",), ("source_entity_name",), ("target_entity_uuid",), ("target_entity_name",), ("encounter_uuid",), ("reason",)),
        (("combatant_uuids",),),
        "encounter_end",
        (("encounter_uuid",),),
        _no_provenance,
        _format_encounter_end,
    ),
)


def _manifest_mask(
    knowledge: EventKnowledge[Event],
    party: PartyKnowledge,
    selector: _ManifestPolicy,
    paths: tuple[ReadPath, ...],
    collection_paths: tuple[ReadPath, ...],
    presentation_role: str,
) -> KnowledgeMask | None:
    if not isinstance(presentation_role, str) or not presentation_role.strip():
        raise RuntimeError("missing reviewed presentation classification")
    if presentation_role == "intentionally_silent":
        return None
    mask = selector(knowledge, party, paths, collection_paths)
    if mask is None:
        return None
    row_paths = set(_BASE_EVENT_PATHS) | set(paths)
    row_collection_paths = set(collection_paths)
    if mask.allow_all:
        raise RuntimeError("subjective manifest masks may not allow all paths")
    if not mask.paths <= row_paths:
        raise RuntimeError("selector admitted a path absent from its manifest row")
    if not mask.collection_paths <= row_collection_paths:
        raise RuntimeError(
            "selector admitted a collection path absent from its manifest row"
        )
    return mask


def format_event_knowledge(knowledge: EventKnowledge[Event]) -> str:
    """Format one real captured event through its exact manifest row."""
    if knowledge.event_class is Event:
        raise RuntimeError(BASE_EVENT_INTENTIONALLY_SILENT_REASON)
    row = next(
        (candidate for candidate in _CONCRETE_EVENT_MANIFEST if candidate[0] is knowledge.event_class),
        None,
    )
    if row is None:
        raise RuntimeError(
            f"no formatter policy for {knowledge.event_class.__qualname__}"
        )
    presentation_role = row[4]
    if not isinstance(presentation_role, str) or not presentation_role.strip():
        raise RuntimeError(
            f"missing presentation classification for {knowledge.event_class.__qualname__}"
        )
    if presentation_role == "intentionally_silent":
        raise RuntimeError(
            f"{knowledge.event_class.__qualname__} is intentionally silent"
        )
    formatter = row[7]
    if not callable(formatter):
        raise RuntimeError(
            f"missing formatter policy for {knowledge.event_class.__qualname__}"
        )
    return formatter(knowledge)


def format_objective_event(captured: CapturedEvent[Event]) -> str:
    """Format the objective rail from top knowledge over a captured event."""
    return format_event_knowledge(
        EventKnowledge(captured=captured, mask=KnowledgeMask.top()),
    )


def format_subjective_delivery(delivery: EventDelivery[Event]) -> str:
    """Format the subjective rail from the delivery's existing knowledge."""
    return format_event_knowledge(delivery.knowledge)


def format_subjective_delivery_tree(
    deliveries: Sequence[EventDelivery[Event]],
) -> tuple[str, ...]:
    """Format delivered event text grouped by real parent identities.

    Parent links are read from each existing delivery.  A missing or
    mismatched parent remains a root; no synthetic relationship is created.
    Displayed child counts are calculated only from the delivered rows.
    """
    metadata: list[tuple[EventDelivery[Event], UUID, UUID | None, UUID | None]] = []
    by_uuid: dict[UUID, int] = {}
    for index, delivery in enumerate(deliveries):
        uuid_value = delivery.knowledge.read(("uuid",))
        parent_value = delivery.knowledge.read(("parent_event",))
        parent_lineage_value = delivery.knowledge.read(("parent_lineage",))
        if not isinstance(uuid_value, Known) or not isinstance(uuid_value.value, UUID):
            raise RuntimeError("delivery UUID is not readable")
        if (
            not isinstance(parent_value, Known)
            or parent_value.value is not None
            and not isinstance(parent_value.value, UUID)
        ):
            raise RuntimeError("delivery parent UUID is not readable")
        if (
            not isinstance(parent_lineage_value, Known)
            or parent_lineage_value.value is not None
            and not isinstance(parent_lineage_value.value, UUID)
        ):
            raise RuntimeError("delivery parent lineage is not readable")
        if uuid_value.value in by_uuid:
            raise RuntimeError("subjective delivery tree contains duplicate UUID")
        by_uuid[uuid_value.value] = index
        metadata.append(
            (
                delivery,
                uuid_value.value,
                parent_value.value,
                parent_lineage_value.value,
            )
        )

    children: dict[int, list[int]] = {}
    roots: list[int] = []
    for index, (_delivery, _uuid, parent_uuid, parent_lineage) in enumerate(metadata):
        parent_index = by_uuid.get(parent_uuid) if parent_uuid is not None else None
        if parent_index is None:
            roots.append(index)
            continue
        parent_event_uuid = metadata[parent_index][1]
        parent_event_lineage = metadata[parent_index][0].knowledge.read(
            ("lineage_uuid",)
        )
        if (
            parent_event_uuid == parent_uuid
            and isinstance(parent_event_lineage, Known)
            and parent_event_lineage.value == parent_lineage
        ):
            children.setdefault(parent_index, []).append(index)
        else:
            roots.append(index)

    rendered: list[str] = []
    visited: set[int] = set()

    def render(index: int, depth: int) -> None:
        if index in visited:
            raise RuntimeError("subjective delivery tree contains a cycle")
        visited.add(index)
        child_indexes = children.get(index, [])
        rendered.append(
            f"{'  ' * depth}{format_subjective_delivery(metadata[index][0])} "
            f"children_count={len(child_indexes)}"
        )
        for child_index in child_indexes:
            render(child_index, depth + 1)

    for root in roots:
        render(root, 0)
    if len(visited) != len(metadata):
        raise RuntimeError("subjective delivery tree contains an unreachable cycle")
    return tuple(rendered)


def party_event_router(
    party: PartyKnowledge,
) -> EventKnowledgeRouter[KnowledgeMask | None]:
    """Build the one exact Slice 3.3 concrete-class policy table."""
    router: EventKnowledgeRouter[KnowledgeMask | None] = EventKnowledgeRouter()
    router.register(
        Event,
        lambda _knowledge: None,
    )
    for event_class, selector, paths, collections, presentation_role, _provenance_paths, _provenance_policy, _formatter in _CONCRETE_EVENT_MANIFEST:
        router.register(
            event_class,
            lambda knowledge, selector=selector, paths=paths, collections=collections, presentation_role=presentation_role: _manifest_mask(
                knowledge,
                party,
                selector,
                paths,
                collections,
                presentation_role,
            ),
        )
    return router


def party_event_delivery(
    captured: CapturedEvent[Event],
    router: EventKnowledgeRouter[KnowledgeMask | None],
) -> EventDelivery[Event] | KnowledgeDiagnostic | None:
    """Create one readable delivery without translating the source event."""
    objective = EventKnowledge(captured=captured, mask=KnowledgeMask.top())
    selected = router.dispatch(objective)
    if isinstance(selected, KnowledgeDiagnostic):
        return selected
    if selected is None:
        return None
    return EventDelivery.create(EventKnowledge(captured=captured, mask=selected))


class EventReducer:
    """Pull and reduce one closed EventQueue tree without a second event model."""

    def __init__(
        self,
        first_observer_uuid: UUID,
        second_observer_uuid: UUID,
        *,
        generation_id: UUID | None = None,
        source_cursor: int,
    ) -> None:
        if first_observer_uuid == second_observer_uuid:
            raise ValueError("EventReducer requires two distinct controlled UUIDs")
        current_generation = EventQueue.generation_id()
        current_cursor = EventQueue.event_cursor()
        if generation_id is not None and generation_id != current_generation:
            raise RuntimeError("event queue generation changed before reducer start")
        if not 0 <= source_cursor <= current_cursor:
            raise ValueError("reducer source cursor must be within the current queue")
        self._generation_id = current_generation if generation_id is None else generation_id
        self._source_cursor = source_cursor
        self._party = PartyKnowledge.cold(first_observer_uuid, second_observer_uuid)
        self._archives: list[EventArchive] = []
        self._last_batch: EventBatch | None = None
        self._last_diagnostics: tuple[KnowledgeDiagnostic, ...] = ()
        self._provenance: dict[SemanticKey, ProvenanceReference] = {}

    @property
    def generation_id(self) -> UUID:
        return self._generation_id

    @property
    def source_cursor(self) -> int:
        return self._source_cursor

    @property
    def party_knowledge(self) -> PartyKnowledge:
        return self._party

    @property
    def last_batch(self) -> EventBatch | None:
        return self._last_batch

    @property
    def last_diagnostics(self) -> tuple[KnowledgeDiagnostic, ...]:
        return self._last_diagnostics

    @property
    def archives(self) -> tuple[EventArchive, ...]:
        return tuple(self._archives)

    @property
    def provenance(self) -> dict[SemanticKey, ProvenanceReference]:
        """Return detached archive references, never copied scene values."""
        return dict(self._provenance)

    @staticmethod
    def _captured_for_uuid(
        archive: EventArchive,
        event_uuid: UUID,
    ) -> CapturedEvent[Event] | None:
        return next(
            (captured for captured in archive.entries if captured.event_uuid == event_uuid),
            None,
        )

    @staticmethod
    def _provenance_updates_for_captured(
        captured: CapturedEvent[Event],
        generation_id: UUID,
    ) -> dict[SemanticKey, ProvenanceReference]:
        row = next(
            (
                row
                for row in _CONCRETE_EVENT_MANIFEST
                if row[0] is captured.event_class
            ),
            None,
        )
        if row is None:
            return {}
        if captured._snapshot.phase is not EventPhase.COMPLETION:
            return {}
        return row[6](captured, generation_id)

    def _resolve_disclosures(
        self,
        archive: EventArchive,
        party: PartyKnowledge,
    ) -> dict[int, int]:
        """Resolve sensory grants to exactly one same-lineage terminal."""
        disclosures: dict[int, int] = {}
        # Causality is closed-tree local.  Older archives remain available to
        # provenance disclosure, but can never repair a missing cause or
        # terminal in the tree currently being reduced.
        closed_entries = archive.entries
        for captured in archive.entries:
            event = captured._snapshot
            if not isinstance(event, SensoryUpdateEvent):
                continue
            if event.observer_uuid not in party.observer_uuids:
                continue
            grants_scene_state = bool(
                event.visible_cells_added
                or event.entity_contacts_changed
                or event.object_contacts_changed
            )
            if not grants_scene_state:
                continue
            cause = next(
                (
                    candidate
                    for candidate in closed_entries
                    if candidate.event_uuid == event.cause_event_uuid
                ),
                None,
            )
            if cause is None:
                raise RuntimeError(
                    "sensory disclosure cause event is missing from the closed archive"
                )
            candidates = tuple(
                candidate
                for candidate in closed_entries
                if (
                    candidate.event_class is cause.event_class
                    and candidate.lineage_uuid == cause.lineage_uuid
                    and candidate._snapshot.phase is EventPhase.COMPLETION
                    and candidate._snapshot.is_last
                    and candidate.source_index >= cause.source_index
                )
            )
            if len(candidates) != 1:
                raise RuntimeError("sensory disclosure did not resolve exactly one causative terminal")
            disclosures[captured.source_index] = candidates[0].source_index
        return disclosures

    def _captured_reference(
        self,
        reference: ProvenanceReference,
        current: EventArchive,
    ) -> CapturedEvent[Event] | None:
        generation_id, source_index, _path = reference
        if generation_id != self._generation_id:
            return None
        for archive in (current, *reversed(self._archives)):
            for captured in archive.entries:
                if captured.source_index == source_index:
                    return captured
        return None

    def _late_disclosures(
        self,
        captured: CapturedEvent[Event],
        provenance: Mapping[SemanticKey, ProvenanceReference],
        current: EventArchive,
        batch_id: BatchId,
        cause_source_index: int,
        next_ordinal: int,
        terminal: CapturedEvent[Event] | None = None,
    ) -> tuple[tuple[EventDelivery[Event], ...], int]:
        event = captured._snapshot
        if not isinstance(event, SensoryUpdateEvent):
            return (), next_ordinal
        semantic_values: set[object] = set(event.visible_cells_added)
        semantic_values.update(event.entity_contacts_changed)
        semantic_values.update(event.object_contacts_changed)
        nonvisual_entity_keys = {
            subject_uuid
            for subject_uuid, contact in event.entity_contacts_changed.items()
            if not contact.visual
        }
        nonvisual_object_keys = {
            object_uuid
            for object_uuid, contact in event.object_contacts_changed.items()
            if not contact.visual
        }
        selected_references = dict(provenance)
        terminal_source_index = None
        if terminal is not None:
            terminal_source_index = terminal.source_index
            selected_references.update(
                self._provenance_updates_for_captured(
                    terminal,
                    self._generation_id,
                )
            )
        paths_by_source: dict[int, set[ReadPath]] = {}
        for (semantic_key, _semantic_path), reference in selected_references.items():
            if semantic_key not in semantic_values:
                continue
            if (
                reference[1] >= captured.source_index
                and reference[1] != terminal_source_index
            ):
                continue
            path = reference[2]
            if semantic_key in nonvisual_entity_keys and path not in {
                ("entity_uuid",),
                ("entity_name",),
            }:
                continue
            if semantic_key in nonvisual_object_keys and path[-1] not in {
                "object_uuid",
                "position",
            }:
                continue
            paths_by_source.setdefault(reference[1], set()).add(path)
        result: list[EventDelivery[Event]] = []
        for source_index in sorted(paths_by_source):
            source = self._captured_reference(
                (self._generation_id, source_index, ()),
                current,
            )
            if source is None:
                continue
            source_knowledge = EventKnowledge(source, KnowledgeMask.top())
            paths = tuple(sorted(paths_by_source[source_index], key=repr))
            for path in paths:
                if not isinstance(source_knowledge.read(path), Known):
                    raise RuntimeError("provenance disclosure path is not readable")
            delivery_id: DeliveryId = (batch_id, next_ordinal)
            next_ordinal += 1
            result.append(EventDelivery.create(
                EventKnowledge(
                    source,
                    KnowledgeMask.from_paths(*paths),
                ),
                delivery_id=delivery_id,
                batch_id=batch_id,
                disclosure_cause_source_index=cause_source_index,
            ))
        return tuple(result), next_ordinal

    def reduce_next_committed_tree(self) -> EventBatch | None:
        """Pull, capture, and reduce the next closed journal tree."""
        tree = EventQueue.next_committed_tree(
            self._source_cursor,
            generation_id=self._generation_id,
        )
        if tree is None:
            return None
        start = self._source_cursor
        stop = start + len(tree)
        archive = EventArchive.capture_queue_range(start, stop)
        batch_id: BatchId = (self._generation_id, start, stop)
        router = party_event_router(self._party)
        next_party = self._party
        deliveries: list[EventDelivery[Event]] = []
        delivery_indexes: dict[int, int] = {}
        coverage: list[SourceCoverage] = []
        diagnostics: list[KnowledgeDiagnostic] = []

        provenance = dict(self._provenance)
        disclosures = self._resolve_disclosures(archive, self._party)
        for captured in archive.entries:
            result = party_event_delivery(captured, router)
            if isinstance(result, KnowledgeDiagnostic):
                diagnostics.append(result)
                coverage.append(SourceCoverage(
                    generation_id=self._generation_id,
                    source_index=captured.source_index,
                    event_uuid=captured.event_uuid,
                    disposition=SourceDisposition.ERROR,
                ))
            elif result is None:
                disposition = (
                    SourceDisposition.INTENTIONALLY_SILENT
                    if captured.event_class is Event
                    else SourceDisposition.HIDDEN
                )
                coverage.append(SourceCoverage(
                    generation_id=self._generation_id,
                    source_index=captured.source_index,
                    event_uuid=captured.event_uuid,
                    disposition=disposition,
                ))
            else:
                ordinal = len(deliveries)
                delivery_id: DeliveryId = (batch_id, ordinal)
                deliveries.append(EventDelivery.create(
                    result.knowledge,
                    delivery_id=delivery_id,
                    batch_id=batch_id,
                ))
                delivery_indexes[captured.source_index] = ordinal
                coverage.append(SourceCoverage(
                    generation_id=self._generation_id,
                    source_index=captured.source_index,
                    event_uuid=captured.event_uuid,
                    disposition=SourceDisposition.DELIVERED,
                    delivery_ids=(delivery_id,),
                ))
                if isinstance(captured._snapshot, SensoryUpdateEvent):
                    # The current sensory slot owns any late scene-state
                    # disclosure deliveries.  They retain their older source
                    # reference but use this batch's cause and delivery IDs.
                    if captured.source_index in disclosures:
                        disclosure_terminal = self._captured_reference(
                            (self._generation_id, disclosures[captured.source_index], ()),
                            archive,
                        )
                        if disclosure_terminal is None:
                            raise RuntimeError(
                                "sensory disclosure terminal is missing from closed archives"
                            )
                        late_deliveries, _next_ordinal = self._late_disclosures(
                            captured,
                            provenance,
                            archive,
                            batch_id,
                            disclosures[captured.source_index],
                            len(deliveries),
                            disclosure_terminal,
                        )
                        if late_deliveries:
                            delivery_ids = tuple(
                                delivery.delivery_id
                                for delivery in late_deliveries
                                if delivery.delivery_id is not None
                            )
                            deliveries.extend(late_deliveries)
                            coverage[-1] = SourceCoverage(
                                generation_id=self._generation_id,
                                source_index=captured.source_index,
                                event_uuid=captured.event_uuid,
                                disposition=SourceDisposition.DELIVERED,
                                delivery_ids=(
                                    coverage[-1].delivery_ids + delivery_ids
                                ),
                            )
            next_party = next_party.apply(captured)
            provenance.update(
                self._provenance_updates_for_captured(
                    captured,
                    self._generation_id,
                )
            )

        if len(coverage) != len(archive.entries):
            raise RuntimeError("one source coverage record is required per captured slot")
        if any(
            coverage_item.disposition is not SourceDisposition.DELIVERED
            and coverage_item.delivery_ids
            for coverage_item in coverage
        ):
            raise RuntimeError("only delivered source slots may own deliveries")
        for source_index, cause_source_index in disclosures.items():
            delivery_index = delivery_indexes.get(source_index)
            if delivery_index is None:
                raise RuntimeError(
                    "sensory disclosure source slot has no party delivery"
                )
            existing = deliveries[delivery_index]
            deliveries[delivery_index] = EventDelivery.create(
                existing.knowledge,
                delivery_id=existing.delivery_id,
                batch_id=existing.batch_id,
                disclosure_cause_source_index=cause_source_index,
            )
        batch = EventBatch(
            generation_id=self._generation_id,
            start=start,
            stop=stop,
            deliveries=tuple(deliveries),
            coverage=tuple(coverage),
            diagnostics=tuple(diagnostics),
        )
        self._party = next_party
        self._source_cursor = stop
        self._archives.append(archive)
        self._last_batch = batch
        self._last_diagnostics = tuple(diagnostics)
        self._provenance = provenance
        return batch

    def drain_committed_trees(self) -> tuple[EventBatch, ...]:
        """Reduce every currently closed tree in source order."""
        batches: list[EventBatch] = []
        while True:
            batch = self.reduce_next_committed_tree()
            if batch is None:
                return tuple(batches)
            batches.append(batch)
