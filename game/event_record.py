"""Concrete retained event values at the recording boundary.

The discriminator follows the original event wire format. Validation uses the
native schemas in passive mode; it never reconstructs executable value graphs.
The presentation capture owns detaching those graphs before encoding.
"""

import json
from typing import Annotated, Any

from pydantic import BeforeValidator, PlainSerializer, TypeAdapter

from dnd.actions import AttackEvent, JumpEvent, MovementEvent, ShoveEvent, SpellEvent
from dnd.blocks.base_item import ItemChargeConsumptionEvent, ItemLocationStateEvent
from dnd.blocks.equipment import (
    ArmorEquipEvent, ArmorUnequipEvent, EquipmentEvent, ShieldEquipEvent,
    ShieldUnequipEvent, WeaponEquipEvent, WeaponUnequipEvent,
)
from dnd.core.base_actions import ActionEvent
from dnd.core.base_object import PASSIVE_EVENT_REPLAY
from dnd.core.combat_log import CombatLogEntry
from dnd.core.content.runtime import EffectiveHandlerPresentation
from dnd.core.events import (
    AttackD20RollResultEvent, D20Event, D20RollResultEvent, DamageAppliedEvent,
    DamageRollResultEvent, DeathEvent, DeathSaveEvent, EncounterEndEvent,
    EncounterEvent, EncounterStartEvent, EntityCreatedEvent, Event,
    ForcedMovementEvent, HealEvent, HealRollResultEvent, InstantDeathEvent,
    LifeStateChangeEvent, ReviveEvent, RoundEndEvent, RoundEvent, RoundStartEvent,
    SavingThrowD20RollResultEvent, SavingThrowEvent, SensoryUpdateEvent,
    SkillCheckD20RollResultEvent, SkillCheckEvent, SpatialChangeEvent,
    StepMovementEvent, TakeDamageEvent, TurnEndEvent, TurnEvent, TurnStartEvent,
    WorldInitializedEvent,
)


# Concrete event families, not spell/creature recipes. Unknown runtime graphs
# must first acquire a retained capture contract; they cannot decode by importing
# arbitrary classes named by a file. Technical headers remain ordinary Event.
EVENT_MODELS = {f"{model.__module__}.{model.__qualname__}": model for model in (
    Event, ActionEvent, WorldInitializedEvent, EntityCreatedEvent,
    AttackEvent, SpellEvent, MovementEvent, JumpEvent, ShoveEvent,
    EquipmentEvent, WeaponEquipEvent, WeaponUnequipEvent, ArmorEquipEvent,
    ArmorUnequipEvent, ShieldEquipEvent, ShieldUnequipEvent, ItemLocationStateEvent,
    ItemChargeConsumptionEvent,
    D20Event, SavingThrowEvent, SkillCheckEvent, D20RollResultEvent,
    AttackD20RollResultEvent, SavingThrowD20RollResultEvent, SkillCheckD20RollResultEvent,
    DamageRollResultEvent, HealRollResultEvent, TakeDamageEvent, DamageAppliedEvent,
    HealEvent, DeathEvent, DeathSaveEvent, InstantDeathEvent, ReviveEvent,
    LifeStateChangeEvent, SensoryUpdateEvent, SpatialChangeEvent, StepMovementEvent,
    ForcedMovementEvent, EncounterEvent, EncounterStartEvent, EncounterEndEvent,
    RoundEvent, RoundStartEvent, RoundEndEvent, TurnEvent, TurnStartEvent, TurnEndEvent,
)}
LOG = TypeAdapter(CombatLogEntry | None)
HANDLERS = TypeAdapter(tuple[EffectiveHandlerPresentation, ...])
GRANTS = TypeAdapter(dict[str, set[str]])


def encode_event(event: Event) -> dict[str, Any]:
    """Retain the concrete payload plus the facts native dumps exclude."""
    wire_type = f"{type(event).__module__}.{type(event).__qualname__}"
    if wire_type not in EVENT_MODELS:
        raise ValueError(f"event has no retained recording contract: {wire_type}")
    return {
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


def decode_event(value: Any) -> Event:
    """Read a recorded concrete event without ambient runtime construction."""
    if isinstance(value, Event):
        return value
    payload = dict(value)
    wire_type = payload.pop("wire_type", None)
    if wire_type not in EVENT_MODELS:
        raise ValueError(f"unknown or missing recorded event wire_type: {wire_type}")
    model = EVENT_MODELS[wire_type]
    required = {name for name, field in model.model_fields.items() if field.exclude is not True}
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
    return event


RecordedEvent = Annotated[Event, BeforeValidator(decode_event), PlainSerializer(encode_event)]
