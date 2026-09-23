"""Fold native event after-values into retained actor facts."""

from dataclasses import replace
from uuid import UUID

from dnd.actions import AttackEvent
from dnd.blocks.appearance import AppearanceConfig
from dnd.blocks.base_item import ItemChargeConsumptionEvent, ItemLocationStateEvent
from dnd.blocks.equipment import EquipmentEvent
from dnd.core.equipment_types import WeaponSet, WeaponSlot
from dnd.core.creature_types import Size
from dnd.core.events import DamageAppliedEvent, EntityCreatedEvent, Event, EventType, HealEvent, LifeStateChangeEvent, SpatialChangeEvent, SpatialChangeType, TemporaryHitPointsChangedEvent
from dnd.core.item_types import ItemLocation
from dnd.core.life_types import LifeState
from dnd.types.actor_facts import ActorState, ConditionFact
from dnd.types.actor import EntityStatsState
from dnd.core.base_conditions import ConditionApplicationEvent, ConditionRemovalEvent, ConditionStateChangedEvent


def actor_from_birth(birth: EntityCreatedEvent) -> ActorState:
    """Retain recorded initial values, sharing immutable item snapshots."""
    return ActorState(
        uuid=birth.entity_uuid, name=birth.entity_name,
        character_body_id=birth.character_body_id, creature_content_ref=birth.creature_content_ref,
        appearance=AppearanceConfig.model_validate(dict(birth.appearance)),
        items=tuple(birth.items),
        equipment=tuple(birth.equipment), active_weapon_set=birth.active_weapon_set,
        normal_hp=birth.maximum_hit_points - birth.damage_taken,
        maximum_hp=birth.maximum_hit_points, temporary_hp=birth.temporary_hit_points,
        life_state=LifeState(birth.life_state), armor_class=birth.armor_class,
        faction=birth.faction, creature_type=birth.creature_type,
        healing_blocked=birth.healing_blocked, damage_affinities=birth.damage_affinities,
        occupancy_layer=birth.occupancy_layer,
        temporary_hp_grant=birth.temporary_hit_points_grant,
        resolved_size=Size(birth.size), structural_base_size=Size(birth.structural_base_size),
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
        case Event(event_type=EventType.CONDITION_APPLICATION | EventType.CONDITION_REMOVAL | EventType.CONDITION_STATE_CHANGED):
            return event.target_entity_uuid
        case LifeStateChangeEvent() | TemporaryHitPointsChangedEvent():
            return event.entity_uuid
        case SpatialChangeEvent(change_type=SpatialChangeType.ENTITY_ENTERED | SpatialChangeType.ENTITY_LEFT):
            return event.entity_uuid
        case ItemLocationStateEvent(location=ItemLocation.INVENTORY | ItemLocation.EQUIPMENT):
            return event.owner_uuid
    return None


def apply_actor_fact(actor: ActorState, event: Event, condition: ConditionFact | None = None) -> ActorState:
    """Apply native after-values; do not execute damage, hooks or equipment rules."""
    match event:
        case SpatialChangeEvent(change_type=SpatialChangeType.ENTITY_ENTERED | SpatialChangeType.ENTITY_LEFT):
            return (actor if event.occupancy_layer is None
                    else replace(actor, occupancy_layer=event.occupancy_layer))
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
                           temporary_hp=event.resulting_temporary_hp,
                           temporary_hp_grant=actor.temporary_hp_grant if event.resulting_temporary_hp > 0 else None)
        case HealEvent():
            if event.was_blocked:
                return actor
            if event.resulting_normal_hp is None or event.resulting_temporary_hp is None:
                raise ValueError("healing requires committed HP after-values")
            return replace(actor, normal_hp=event.resulting_normal_hp,
                           temporary_hp=event.resulting_temporary_hp,
                           temporary_hp_grant=actor.temporary_hp_grant if event.resulting_temporary_hp > 0 else None)
        case Event(event_type=EventType.CONDITION_APPLICATION | EventType.CONDITION_REMOVAL | EventType.CONDITION_STATE_CHANGED):
            if condition is None:
                raise ValueError("condition membership requires its recorded condition fact")
            members = {member.condition_uuid: member for member in actor.conditions}
            if event.event_type is EventType.CONDITION_REMOVAL:
                members.pop(condition.condition_uuid, None)
            else:
                members[condition.condition_uuid] = condition
            actor = replace(actor, conditions=tuple(members.values()),
                           maximum_hp=actor.maximum_hp if condition.resulting_max_hp is None else condition.resulting_max_hp,
                           armor_class=actor.armor_class if condition.resulting_ac is None else condition.resulting_ac)
            return apply_stats(actor, condition.resulting_stats)
        case LifeStateChangeEvent():
            return replace(actor, life_state=event.new_state, normal_hp=event.normal_hit_points)
        case TemporaryHitPointsChangedEvent():
            return replace(actor, temporary_hp=event.resulting_temporary_hp, temporary_hp_grant=event.grant)
        case ItemLocationStateEvent(location=ItemLocation.INVENTORY | ItemLocation.EQUIPMENT):
            item = event.item_state
            items = {row.item_uuid: row for row in actor.items}
            items[item.item_uuid] = item
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


def apply_stats(actor: ActorState, stats: EntityStatsState | None) -> ActorState:
    """Install an existing native aggregate result without evaluating rules."""
    if stats is None:
        return actor
    return replace(actor, normal_hp=stats.normal_hp, maximum_hp=stats.maximum_hp,
                   temporary_hp=stats.temporary_hp, temporary_hp_grant=stats.temporary_hp_grant,
                   armor_class=stats.armor_class,
                   healing_blocked=stats.healing_blocked, damage_affinities=stats.damage_affinities,
                   resolved_size=stats.resolved_size if stats.resolved_size is not None else actor.resolved_size)


def condition_fact(event: Event, *, source_index: int | None = None) -> ConditionFact | None:
    """Read committed cold metadata; never inspect the executable condition graph."""
    if not isinstance(event, (ConditionApplicationEvent, ConditionRemovalEvent, ConditionStateChangedEvent)):
        return None
    state = event.condition_state
    if state is None:
        return None
    if isinstance(event, ConditionApplicationEvent) and source_index is not None:
        state = state.model_copy(update={"applied_source_event_cursor": source_index + 1})
    return ConditionFact(
        event_uuid=event.uuid, condition_uuid=state.condition_uuid, name=state.name,
        category=state.category, behavior_id=event.behavior_id,
        resulting_max_hp=event.resulting_stats.maximum_hp if isinstance(event, ConditionStateChangedEvent) else event.resulting_max_hp,
        resulting_ac=event.resulting_stats.armor_class if isinstance(event, ConditionStateChangedEvent) else event.resulting_ac,
        state=state, resulting_stats=event.resulting_stats,
        resulting_tile=None if isinstance(event, ConditionStateChangedEvent) else event.resulting_tile,
        resulting_item=None if isinstance(event, ConditionStateChangedEvent) else event.resulting_item,
    )
