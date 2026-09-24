"""Concrete retained event values at the recording boundary.

The discriminator follows the original event wire format. Validation uses the
native schemas in passive mode; it never reconstructs executable value graphs.
The presentation capture owns detaching those graphs before encoding.
"""

import json
from typing import Annotated, Any

from pydantic import BeforeValidator, PlainSerializer, TypeAdapter
from game.recording_compat import recorded_area_policy

from dnd.actions import AttackEvent, JumpEvent, MovementEvent, ShoveEvent, SpellEvent
from dnd.blocks.base_item import ItemChargeConsumptionEvent, ItemLocationStateEvent
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
    AttackD20RollResultEvent, D20Event, D20RollResultEvent, DamageAppliedEvent,
    DamageRollResultEvent, DeathEvent, DeathSaveEvent, EncounterEndEvent,
    EncounterEvent, EncounterStartEvent, EntityCreatedEvent, Event, EventPhase,
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
    Event, ActionEvent, WorldInitializedEvent, WorldModifiedEvent, EntityCreatedEvent, ConditionStateChangedEvent,
    AttackEvent, SpellEvent, MovementEvent, JumpEvent, ShoveEvent, CounterspellReactionEvent,
    EquipmentEvent, WeaponEquipEvent, WeaponUnequipEvent, ArmorEquipEvent,
    ArmorUnequipEvent, ShieldEquipEvent, ShieldUnequipEvent, ItemLocationStateEvent,
    ItemChargeConsumptionEvent, ItemDestructionEvent,
    D20Event, SavingThrowEvent, SkillCheckEvent, D20RollResultEvent,
    AttackD20RollResultEvent, SavingThrowD20RollResultEvent, SkillCheckD20RollResultEvent,
    DamageRollResultEvent, HealRollResultEvent, TakeDamageEvent, DamageAppliedEvent,
    HealEvent, TemporaryHitPointsChangedEvent, DeathEvent, DeathSaveEvent, InstantDeathEvent, ReviveEvent,
    LifeStateChangeEvent, SensoryUpdateEvent, SpatialChangeEvent, TileElevationChangeEvent,
    SpatialEffectChangeEvent, StepMovementEvent,
    ForcedMovementEvent, PortalTransferEvent, MechanismActivationEvent, EncounterEvent, EncounterStartEvent, EncounterEndEvent,
    RoundEvent, RoundStartEvent, RoundEndEvent, TurnEvent, TurnStartEvent, TurnEndEvent,
)}
LOG = TypeAdapter(CombatLogEntry | None)
HANDLERS = TypeAdapter(tuple[EffectiveHandlerPresentation, ...])
GRANTS = TypeAdapter(dict[str, set[str]])

# These facts were added after native-v2 recordings were already in use.
# Their defaults keep those presentation archives readable; old archives do
# not acquire facts that only newer native producers record.
ADDITIVE_FIELDS = {
    SpatialEffectChangeEvent: {"pressed", "previous_pressed"},
    ItemLocationStateEvent: {"replacement_item_uuid"},
    ActionEvent: {"resolved_area_positions"},
    AttackEvent: {"resolved_area_positions", "intercepted_by_condition_uuid"},
    SpellEvent: {"resolved_area_positions", "effect_id", "cast_origin", "effect_source_position", "suppressions", "area_propagation"},
    ShoveEvent: {"resolved_area_positions"},
    DamageAppliedEvent: {"body_release", "critical_hit", "impact_direction"},
    TakeDamageEvent: {"intercepted_by_condition_uuid"},
    HealEvent: {"source_condition_uuid"},
    EntityCreatedEvent: {"healing_blocked", "occupancy_layer", "temporary_hit_points_grant"},
    SensoryUpdateEvent: {"hazardous_cells_changed", "spatial_effects_changed", "spatial_effects_removed"},
    SpatialChangeEvent: {"tile_state", "tile_present", "object_state", "previous_occupancy_layer", "occupancy_layer"},
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
    wire_type = f"{type(event).__module__}.{type(event).__qualname__}"
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
    omitted = frozenset(legacy_fields - payload.keys())
    if model is SpellEvent:
        payload = recorded_area_policy(payload)
    required = {name for name, field in model.model_fields.items() if field.exclude is not True}
    required.difference_update(ADDITIVE_FIELDS.get(model, set()))
    required.difference_update(legacy_fields)
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
    return event


RecordedEvent = Annotated[Event, BeforeValidator(decode_event), PlainSerializer(encode_event)]
