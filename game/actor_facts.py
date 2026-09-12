"""Actor values reduced identically before disclosure and during presentation."""

from dataclasses import dataclass, replace
from uuid import UUID

from dnd.actions import AttackEvent
from dnd.blocks.appearance import AppearanceConfig
from dnd.blocks.base_item import ItemChargeConsumptionEvent, ItemLocationStateEvent
from dnd.blocks.equipment import EquipmentEvent
from dnd.core.condition_types import ConditionCategory
from dnd.core.equipment_types import WeaponSet, WeaponSlot
from dnd.core.events import DamageAppliedEvent, EntityCreatedEvent, Event, EventType, HealEvent, LifeStateChangeEvent
from dnd.core.item_types import ItemLocation, ItemPresentationState
from dnd.core.life_types import LifeState


@dataclass(frozen=True, slots=True)
class ConditionFact:
    """A condition's presentation facts, without its live rules/ownership graph."""

    event_uuid: UUID
    condition_uuid: UUID
    name: str
    category: ConditionCategory
    behavior_id: str | None
    resulting_max_hp: int | None
    resulting_ac: int | None


@dataclass(frozen=True, slots=True)
class ActorState:
    """Retained actor facts; appearance remains independent of the drawer."""

    uuid: UUID
    name: str
    character_body_id: str | None
    creature_content_ref: str | None
    appearance: AppearanceConfig
    items: tuple[ItemPresentationState, ...]
    equipment: tuple[tuple[str, UUID], ...]
    active_weapon_set: WeaponSet
    normal_hp: int
    maximum_hp: int
    temporary_hp: int
    life_state: LifeState
    armor_class: int = 10
    conditions: tuple[ConditionFact, ...] = ()
    last_visual_position: tuple[int, int] | None = None


def actor_from_birth(birth: EntityCreatedEvent) -> ActorState:
    """Copy the recorded initial aggregate, without consulting native owners."""
    return ActorState(
        uuid=birth.entity_uuid, name=birth.entity_name,
        character_body_id=birth.character_body_id, creature_content_ref=birth.creature_content_ref,
        appearance=AppearanceConfig.model_validate(dict(birth.appearance)),
        items=tuple(item.model_copy(deep=True) for item in birth.items),
        equipment=tuple(birth.equipment), active_weapon_set=birth.active_weapon_set,
        normal_hp=birth.maximum_hit_points - birth.damage_taken,
        maximum_hp=birth.maximum_hit_points, temporary_hp=birth.temporary_hit_points,
        life_state=LifeState(birth.life_state), armor_class=birth.armor_class,
    )


def actor_fact_owner(event: Event) -> UUID | None:
    """Identify the aggregate receiving an already committed actor fact."""
    match event:
        case AttackEvent() if event.attack_outcome is not None:
            return event.source_entity_uuid
        case EquipmentEvent() | ItemChargeConsumptionEvent():
            return event.source_entity_uuid
        case DamageAppliedEvent() | HealEvent():
            return event.target_entity_uuid
        case Event(event_type=EventType.CONDITION_APPLICATION | EventType.CONDITION_REMOVAL):
            return event.target_entity_uuid
        case LifeStateChangeEvent():
            return event.entity_uuid
        case ItemLocationStateEvent(location=ItemLocation.INVENTORY | ItemLocation.EQUIPMENT):
            return event.owner_uuid
    return None


def apply_actor_fact(actor: ActorState, event: Event, condition: ConditionFact | None = None) -> ActorState:
    """Apply native after-values; do not execute damage, hooks or equipment rules."""
    match event:
        case ItemChargeConsumptionEvent():
            items = tuple(item.model_copy(update={
                "charges": event.charges_after, "stack_count": event.stack_count_after,
            }) if item.item_uuid == event.item_uuid else item for item in actor.items
                if not (event.item_destroyed and item.item_uuid == event.item_uuid))
            equipment = tuple((slot, identity) for slot, identity in actor.equipment
                              if not (event.item_destroyed and identity == event.item_uuid))
            return replace(actor, items=items, equipment=equipment)
        case AttackEvent() if event.attack_outcome is not None:
            selected = (WeaponSet.RANGED if event.weapon_slot in
                        (WeaponSlot.RANGED_MAIN, WeaponSlot.RANGED_OFF) else WeaponSet.MELEE)
            return replace(actor, active_weapon_set=selected)
        case DamageAppliedEvent():
            return replace(actor, normal_hp=event.resulting_normal_hp,
                           temporary_hp=event.resulting_temporary_hp)
        case HealEvent():
            if event.was_blocked:
                return actor
            if event.resulting_normal_hp is None or event.resulting_temporary_hp is None:
                raise ValueError("healing requires committed HP after-values")
            return replace(actor, normal_hp=event.resulting_normal_hp,
                           temporary_hp=event.resulting_temporary_hp)
        case Event(event_type=EventType.CONDITION_APPLICATION | EventType.CONDITION_REMOVAL):
            if condition is None:
                raise ValueError("condition membership requires its recorded condition fact")
            members = {member.condition_uuid: member for member in actor.conditions}
            if event.event_type is EventType.CONDITION_REMOVAL:
                members.pop(condition.condition_uuid, None)
            elif condition.category is not ConditionCategory.INTERNAL:
                members[condition.condition_uuid] = condition
            return replace(actor, conditions=tuple(members.values()),
                           maximum_hp=actor.maximum_hp if condition.resulting_max_hp is None else condition.resulting_max_hp,
                           armor_class=actor.armor_class if condition.resulting_ac is None else condition.resulting_ac)
        case LifeStateChangeEvent():
            return replace(actor, life_state=event.new_state, normal_hp=event.normal_hit_points)
        case ItemLocationStateEvent(location=ItemLocation.INVENTORY | ItemLocation.EQUIPMENT):
            item = event.item_state
            items = {row.item_uuid: row for row in actor.items}
            items[item.item_uuid] = item.model_copy(deep=True)
            equipment = {slot: identity for slot, identity in actor.equipment if identity != item.item_uuid}
            if event.location is ItemLocation.EQUIPMENT:
                if event.equipment_slot is None:
                    raise ValueError("equipped item fact requires its committed slot")
                equipment[event.equipment_slot.value] = item.item_uuid
            return replace(actor, items=tuple(items.values()), equipment=tuple(equipment.items()),
                           armor_class=actor.armor_class if event.entity_armor_class_after is None else event.entity_armor_class_after)
        case EquipmentEvent():
            return (actor if event.active_weapon_set_after is None
                    else replace(actor, active_weapon_set=event.active_weapon_set_after))
    return actor
