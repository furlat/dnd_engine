"""Concrete retained event values at the recording boundary.

The discriminator follows the original event wire format. Validation uses the
native schemas in passive mode; it never reconstructs executable value graphs.
The presentation capture owns detaching those graphs before encoding.
"""

import json
from typing import Annotated, Any
from uuid import UUID

from dnd.core.effect_types import ApplicationResolutionRef, EventResolutionRef, ResolutionRef
from dnd.types.event_facts import SpatialChangeType

from pydantic import BeforeValidator, PlainSerializer, TypeAdapter
from game.recording_compat import recorded_area_policy, recorded_application, legacy_damage_reference

from dnd.actions import AttackEvent, JumpEvent, MovementEvent, TraverseConnectorEvent, ShoveEvent, SpellEvent
from dnd.blocks.base_item import ItemResourceChangeEvent, ItemHoldingsReleasedEvent, ItemLocationStateEvent
from dnd.blocks.equipment import (
    ArmorEquipEvent, ArmorUnequipEvent, EquipmentEvent, ShieldEquipEvent,
    ShieldUnequipEvent, WeaponEquipEvent, WeaponUnequipEvent,
)
from dnd.core.base_actions import ActionEvent
from dnd.spells.abjuration import CounterspellReactionEvent
from dnd.core.base_conditions import ConditionStateChangedEvent
from dnd.core.base_object import PASSIVE_EVENT_REPLAY
from dnd.core.combat_log import CombatLogEntry
from dnd.core.content.runtime import EffectiveHandlerPresentation
from dnd.core.events import (
    AreaReachEvent, AttackD20RollResultEvent, D20Event, D20RollResultEvent, DamageAppliedEvent,
    DamageRollResultEvent, DeathEvent, DeathSaveEvent, EncounterEndEvent,
    EncounterEvent, EncounterStartEvent, EntityCreatedEvent, EntityFactionChangedEvent, Event, EventPhase,
    ForcedMovementEvent, PortalTransferEvent, MechanismActivationEvent, HealEvent, HealRollResultEvent, InstantDeathEvent,
    ItemDestructionEvent, LifeStateChangeEvent, ReviveEvent, RoundEndEvent, RoundEvent, RoundStartEvent,
    SavingThrowD20RollResultEvent, SavingThrowEvent, SensoryUpdateEvent,
    SkillCheckD20RollResultEvent, SkillCheckEvent, SpatialChangeEvent, SpatialEffectChangeEvent,
    StepMovementEvent, TakeDamageEvent, TurnEndEvent, TurnEvent, TurnStartEvent,
    WorldInitializedEvent, WorldModifiedEvent, TileElevationChangeEvent, TemporaryHitPointsChangedEvent,
)


# Concrete event families, not spell/creature recipes. Unknown runtime graphs
# must first acquire a retained capture contract; they cannot decode by importing
# arbitrary classes named by a file. Technical headers remain ordinary Event.
EVENT_MODELS = {f"{model.__module__}.{model.__qualname__}": model for model in (
    Event, ActionEvent, AreaReachEvent, WorldInitializedEvent, WorldModifiedEvent, EntityCreatedEvent, EntityFactionChangedEvent, ConditionStateChangedEvent,
    AttackEvent, SpellEvent, MovementEvent, JumpEvent, TraverseConnectorEvent, ShoveEvent, CounterspellReactionEvent,
    EquipmentEvent, WeaponEquipEvent, WeaponUnequipEvent, ArmorEquipEvent,
    ArmorUnequipEvent, ShieldEquipEvent, ShieldUnequipEvent, ItemLocationStateEvent,
    ItemResourceChangeEvent, ItemHoldingsReleasedEvent, ItemDestructionEvent,
    D20Event, SavingThrowEvent, SkillCheckEvent, D20RollResultEvent,
    AttackD20RollResultEvent, SavingThrowD20RollResultEvent, SkillCheckD20RollResultEvent,
    DamageRollResultEvent, HealRollResultEvent, TakeDamageEvent, DamageAppliedEvent,
    HealEvent, TemporaryHitPointsChangedEvent, DeathEvent, DeathSaveEvent, InstantDeathEvent, ReviveEvent,
    LifeStateChangeEvent, SensoryUpdateEvent, SpatialChangeEvent, TileElevationChangeEvent,
    SpatialEffectChangeEvent, StepMovementEvent,
    ForcedMovementEvent, PortalTransferEvent, MechanismActivationEvent, EncounterEvent, EncounterStartEvent, EncounterEndEvent,
    RoundEvent, RoundStartEvent, RoundEndEvent, TurnEvent, TurnStartEvent, TurnEndEvent,
)}
# Keep the original archive discriminator while the Python name describes both operations.
ITEM_RESOURCE_WIRE_TYPE = "dnd.blocks.base_item.ItemChargeConsumptionEvent"
EVENT_MODELS[ITEM_RESOURCE_WIRE_TYPE] = EVENT_MODELS.pop(
    "dnd.blocks.base_item.ItemResourceChangeEvent")
LOG = TypeAdapter(CombatLogEntry | None)
HANDLERS = TypeAdapter(tuple[EffectiveHandlerPresentation, ...])
GRANTS = TypeAdapter(dict[str, set[str]])

# These facts were added after native-v2 recordings were already in use.
# Their defaults keep those presentation archives readable; old archives do
# not acquire facts that only newer native producers record.
ADDITIVE_FIELDS = {
    ItemResourceChangeEvent: {"resource_change"},
    EquipmentEvent: {"release_reason"},
    WeaponEquipEvent: {"release_reason"},
    WeaponUnequipEvent: {"release_reason"},
    ArmorEquipEvent: {"release_reason"},
    ArmorUnequipEvent: {"release_reason"},
    ShieldEquipEvent: {"release_reason"},
    ShieldUnequipEvent: {"release_reason"},
    SpatialEffectChangeEvent: {"pressed", "previous_pressed"},
    ItemLocationStateEvent: {"replacement_item_uuid"},
    ActionEvent: {"resolved_area_positions"},
    AttackEvent: {"resolved_area_positions", "intercepted_by_condition_uuid", "target_kind",
                  "target_position", "target_base_height_steps", "attack_source_kind", "natural_weapon", "additional_damages", "attack_is_magical", "projectile_deflection_position"},
    SpellEvent: {"summon_application", "resolved_area_positions", "effect_id", "cast_origin", "effect_source_position", "suppressions", "area_propagation", "target_kind", "target_position", "target_base_height_steps"},
    ShoveEvent: {"resolved_area_positions"},
    DamageAppliedEvent: {"body_release", "critical_hit", "impact_direction", "spatial_source"},
    TakeDamageEvent: {"intercepted_by_condition_uuid", "spatial_source", "effect_origin"},
    HealEvent: {"source_condition_uuid"},
    EntityCreatedEvent: {"healing_blocked", "occupancy_layer", "temporary_hit_points_grant", "summon_origin", "initial_condition_states"},
    SensoryUpdateEvent: {"observed_changes", "hazardous_cells_changed", "spatial_effects_changed", "spatial_effects_removed"},
    SpatialChangeEvent: {"commit_event_uuid", "tile_state", "tile_present", "object_state", "previous_occupancy_layer", "occupancy_layer", "terminal_release"},
    MovementEvent: {"movement_mode", "start_layer", "end_layer", "resolved_area_positions"},
    JumpEvent: {"movement_mode", "start_layer", "end_layer", "resolved_area_positions"},
    StepMovementEvent: {"movement_mode", "from_layer", "to_layer", "resolved_speed_feet"},
}

# Retained pre-interruption completion archives did not record these declarations.
# They suffice for completion replay, but cannot establish a cancellation receipt.
LEGACY_COMPLETION_FIELDS = {
    model: {"action_economy_spent"}
    for model in EVENT_MODELS.values() if "action_economy_spent" in model.model_fields
}
LEGACY_COMPLETION_FIELDS[SpellEvent].update({"harmful", "harmful_target_entity_uuids", "target_type"})


def encode_event(event: Event) -> dict[str, Any]:
    """Retain the concrete payload plus the facts native dumps exclude."""
    wire_type = (ITEM_RESOURCE_WIRE_TYPE if isinstance(event, ItemResourceChangeEvent)
                 else f"{type(event).__module__}.{type(event).__qualname__}")
    if wire_type not in EVENT_MODELS:
        raise ValueError(f"event has no retained recording contract: {wire_type}")
    payload = {
        "wire_type": wire_type,
        **event.model_dump(mode="json", serialize_as_any=True, warnings="error"),
        "combat_log": LOG.dump_python(event.combat_log, mode="json", warnings="error"),
        "identified_entity_observer_uuids": GRANTS.dump_python(
            event.identified_entity_observer_uuids, mode="json", warnings="error"),
        "located_entity_observer_uuids": GRANTS.dump_python(
            event.located_entity_observer_uuids, mode="json", warnings="error"),
        "located_position_observer_uuids": GRANTS.dump_python(
            event.located_position_observer_uuids, mode="json", warnings="error"),
        "effective_handler_presentations": HANDLERS.dump_python(
            event.effective_handler_presentations, mode="json", warnings="error"),
    }
    if "application" in event._recorded_omissions and isinstance(event, ActionEvent):
        application = payload.pop("application", None)
        payload["application_id"] = application["application_id"] if application is not None else None
        payload["application_index"] = application["index"] if application is not None else None
    for name in event._recorded_omissions - event.model_fields_set:
        payload.pop(name, None)
    return payload


def decode_event(value: Any) -> Event:
    """Read a recorded concrete event without ambient runtime construction."""
    if isinstance(value, Event):
        return value
    payload = dict(value)
    wire_type = payload.pop("wire_type", None)
    if wire_type not in EVENT_MODELS:
        raise ValueError(f"unknown or missing recorded event wire_type: {wire_type}")
    model = EVENT_MODELS[wire_type]
    legacy_fields = (LEGACY_COMPLETION_FIELDS.get(model, set())
                     if payload.get("phase") == EventPhase.COMPLETION.value
                     and payload.get("canceled") is False else set())
    omitted = frozenset((legacy_fields | ADDITIVE_FIELDS.get(model, set()) | {"resolution_ref"}) - payload.keys())
    if model is SpatialChangeEvent and "commit_event_uuid" not in payload:
        omitted = omitted | {"commit_event_uuid"}
    if "application_id" in payload or "application_index" in payload:
        omitted = omitted | {"application"}
    if model is SpellEvent:
        payload = recorded_area_policy(payload)
    payload = recorded_application(payload)
    required = {name for name, field in model.model_fields.items() if field.exclude is not True}
    required.difference_update(ADDITIVE_FIELDS.get(model, set()))
    required.difference_update(legacy_fields)
    required.discard("resolution_ref")
    required.update(("combat_log", "identified_entity_observer_uuids",
                     "located_entity_observer_uuids", "located_position_observer_uuids",
                     "effective_handler_presentations"))
    missing = required - payload.keys()
    if missing:
        raise ValueError(f"incomplete recorded {wire_type}: missing {sorted(missing)}")
    handlers = HANDLERS.validate_python(payload.pop("effective_handler_presentations"))
    event = model.model_validate_json(
        json.dumps(payload), context=PASSIVE_EVENT_REPLAY,
    )
    event._effective_handler_presentations = handlers
    event._recorded_omissions = omitted
    # Compatibility defaults are computed input values, not recorded facts.
    event.model_fields_set.difference_update(omitted)
    return event


def upgrade_recorded_resolutions(events: tuple[Event, ...]) -> tuple[Event, ...]:
    """Admit old native relations only when retained resolution evidence proves them.

    No runtime registry, recipe, creature identity or target/time guess is used.
    Current packets (including explicit unknown references) pass through unchanged.
    """
    by_lineage = {event.lineage_uuid: event for event in events}
    resolved: dict[UUID, ResolutionRef | None] = {}
    pending: set[UUID] = set()

    def reference(event: Event) -> ResolutionRef | None:
        if event.lineage_uuid in resolved:
            return resolved[event.lineage_uuid]
        if event.lineage_uuid in pending:
            raise ValueError("Cyclic legacy event ancestry")
        if "resolution_ref" not in event._recorded_omissions:
            return event.resolution_ref
        pending.add(event.lineage_uuid)
        parent = by_lineage.get(event.parent_lineage) if event.parent_lineage is not None else None
        result: ResolutionRef | None = None
        if isinstance(event, ActionEvent):
            application = event.application
            if application is not None and "application" in event._recorded_omissions:
                owner = parent
                while isinstance(owner, AreaReachEvent):
                    owner = by_lineage.get(owner.parent_lineage) if owner.parent_lineage is not None else None
                if not isinstance(owner, ActionEvent):
                    raise ValueError(f"Legacy application {event.uuid} has no recorded action owner")
                application = application.model_copy(update={"lineage_uuid": owner.lineage_uuid})
            result = (ApplicationResolutionRef(lineage_uuid=application.lineage_uuid,
                application_id=application.application_id) if application is not None
                else EventResolutionRef(lineage_uuid=event.lineage_uuid))
        elif isinstance(event, TakeDamageEvent):
            # A legacy object result can reduce without a damage-animation owner.
            # Projection diagnoses missing proof if it admits a creature request.
            result = (legacy_damage_reference(event.uuid, event.lineage_uuid,
                event.parent_lineage, is_request=True) if event.parent_lineage is None else None)
        elif parent is not None:
            result = reference(parent)
        pending.remove(event.lineage_uuid)
        resolved[event.lineage_uuid] = result
        return result

    result = []
    for event in events:
        if "resolution_ref" not in event._recorded_omissions:
            result.append(event)
            continue
        owner = reference(event)
        update: dict[str, Any] = {"resolution_ref": owner}
        if isinstance(event, ActionEvent) and event.application is not None and isinstance(owner, ApplicationResolutionRef):
            update["application"] = event.application.model_copy(update={"lineage_uuid": owner.lineage_uuid})
        result.append(event.model_copy(update=update))
    return tuple(result)


def upgrade_recorded_spatial_commits(events: tuple[Event, ...],
                                    versions: tuple[tuple[UUID, UUID], ...]) -> tuple[Event, ...]:
    """Old membership producers committed before their first publication."""
    declarations: dict[UUID, UUID] = {}
    for lineage, version in versions:
        declarations.setdefault(lineage, version)
    result = []
    for event in events:
        if (isinstance(event, SpatialChangeEvent) and "commit_event_uuid" in event._recorded_omissions
                and event.change_type in (SpatialChangeType.ENTITY_ENTERED, SpatialChangeType.ENTITY_LEFT)):
            commit = declarations.get(event.lineage_uuid)
            if commit is None:
                raise ValueError(f"Legacy spatial change {event.uuid} lacks its commit publication")
            event = event.model_copy(update={"commit_event_uuid": commit})
        result.append(event)
    return tuple(result)


RecordedEvent = Annotated[Event, BeforeValidator(decode_event), PlainSerializer(encode_event)]
