"""Fold native event after-values into retained actor facts."""

from dataclasses import replace
from uuid import UUID

from dnd.actions import AttackEvent
from dnd.blocks.appearance import AppearanceConfig
from dnd.blocks.base_item import ItemResourceChangeEvent, ItemHoldingsReleasedEvent, ItemLocationStateEvent
from dnd.blocks.equipment import EquipmentEvent
from dnd.core.equipment_types import WeaponSet, WeaponSlot
from dnd.core.creature_types import Size
from dnd.core.events import DamageAppliedEvent, EntityCreatedEvent, EntityFactionChangedEvent, Event, EventType, HealEvent, LifeStateChangeEvent, SpatialChangeEvent, SpatialChangeType, TemporaryHitPointsChangedEvent
from dnd.core.item_types import ItemLocation, ItemPresentationState
from dnd.core.life_types import LifeState
from dnd.types.actor_facts import ActorFactChange, ActorFieldValues, ActorState, ConditionFact, HeldItem, ItemResources
from dnd.types.actor import EntityStatsState, SpatialDisposition
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
        life_state=LifeState(birth.life_state), remains_disposition=birth.remains_disposition, armor_class=birth.armor_class,
        faction=birth.faction, creature_type=birth.creature_type,
        healing_blocked=birth.healing_blocked, damage_affinities=birth.damage_affinities,
        occupancy_layer=birth.occupancy_layer,
        temporary_hp_grant=birth.temporary_hit_points_grant,
        resolved_size=Size(birth.size), structural_base_size=Size(birth.structural_base_size),
        summon_origin=birth.summon_origin,
        conditions=tuple(ConditionFact(event_uuid=birth.uuid,
            condition_uuid=state.condition_uuid, name=state.name, category=state.category,
            behavior_id=state.behavior_id, resulting_max_hp=None, resulting_ac=None, state=state)
            for state in birth.initial_condition_states),
    )


def actor_fact_owner(event: Event) -> UUID | None:
    """Identify the aggregate receiving an already committed actor fact."""
    match event:
        case AttackEvent() if event.attack_outcome is not None:
            return event.source_entity_uuid
        case EquipmentEvent() | ItemResourceChangeEvent() | ItemHoldingsReleasedEvent():
            return event.source_entity_uuid
        case DamageAppliedEvent() | HealEvent():
            return event.target_entity_uuid
        case Event(event_type=EventType.CONDITION_APPLICATION | EventType.CONDITION_REMOVAL | EventType.CONDITION_STATE_CHANGED):
            return event.target_entity_uuid
        case LifeStateChangeEvent() | TemporaryHitPointsChangedEvent() | EntityFactionChangedEvent():
            return event.entity_uuid
        case SpatialChangeEvent(change_type=SpatialChangeType.ENTITY_ENTERED | SpatialChangeType.ENTITY_LEFT):
            return event.entity_uuid
        case ItemLocationStateEvent(location=ItemLocation.INVENTORY | ItemLocation.EQUIPMENT):
            return event.owner_uuid
    return None


def _hit_points(normal_hp: int, temporary_hp: int) -> ActorFieldValues:
    """Damage and healing write both pools; an emptied temporary pool loses its grant."""
    values: ActorFieldValues = {"normal_hp": normal_hp, "temporary_hp": temporary_hp}
    if temporary_hp <= 0:
        values["temporary_hp_grant"] = None
    return values


def _stats_values(stats: EntityStatsState) -> ActorFieldValues:
    """A native aggregate result as after-values, without evaluating rules."""
    values: ActorFieldValues = {
        "normal_hp": stats.normal_hp, "maximum_hp": stats.maximum_hp, "temporary_hp": stats.temporary_hp,
        "temporary_hp_grant": stats.temporary_hp_grant, "armor_class": stats.armor_class,
        "spatial_disposition": stats.spatial_disposition, "healing_blocked": stats.healing_blocked,
        "damage_affinities": stats.damage_affinities,
    }
    if stats.resolved_size is not None:
        values["resolved_size"] = stats.resolved_size
    return values


def actor_fact_change(event: Event, condition: ConditionFact | None = None) -> ActorFactChange | None:
    """The one dispatch from a committed event to its actor change (plan §4).

    Each arm writes what the engine fold writes for that fact, as native after-values; no rule is run.
    Every fact with an owner gets a change, even one writing nothing, so its owner is rewritten exactly
    when a fact reaches it.
    """
    owner = actor_fact_owner(event)
    match event:
        case EntityFactionChangedEvent():
            return ActorFactChange(owner, {"faction": event.faction_after})
        case ItemHoldingsReleasedEvent():
            return ActorFactChange(owner, released_by_owner=event.item_uuid)
        case ItemLocationStateEvent(location=ItemLocation.INVENTORY | ItemLocation.EQUIPMENT):
            slot: str | None = None
            if event.location is ItemLocation.EQUIPMENT:
                if event.equipment_slot is None:
                    raise ValueError("equipped item fact requires its committed slot")
                slot = event.equipment_slot.value
            values: ActorFieldValues = {}
            if event.entity_armor_class_after is not None:
                values["armor_class"] = event.entity_armor_class_after
            # One location has one holder: the item leaves every other holder.
            return ActorFactChange(owner, values, held_item=HeldItem(event.item_state, slot),
                                   released_by_others=event.item_state.item_uuid)
        case ItemLocationStateEvent():
            return ActorFactChange(None, released_by_others=event.item_state.item_uuid)
        case SpatialChangeEvent(change_type=SpatialChangeType.ENTITY_ENTERED | SpatialChangeType.ENTITY_LEFT):
            values = {}
            if event.change_type is SpatialChangeType.ENTITY_ENTERED:
                values["spatial_disposition"] = SpatialDisposition.PRESENT
            if event.occupancy_layer is not None:
                values["occupancy_layer"] = event.occupancy_layer
            return ActorFactChange(owner, values)
        case ItemResourceChangeEvent():
            return ActorFactChange(owner, used_item=ItemResources(event.item_uuid, event.charges_after,
                event.stack_count_after, event.item_destroyed))
        case AttackEvent() if event.attack_outcome is not None:
            selected = (WeaponSet.NONE if event.attack_source_kind != "equipped" else
                        WeaponSet.RANGED if event.weapon_slot in
                        (WeaponSlot.RANGED_MAIN, WeaponSlot.RANGED_OFF) else WeaponSet.MELEE)
            return ActorFactChange(owner, {"active_weapon_set": selected})
        case DamageAppliedEvent():
            return ActorFactChange(owner, _hit_points(event.resulting_normal_hp, event.resulting_temporary_hp))
        case HealEvent():
            if event.was_blocked:
                return ActorFactChange(owner)
            if event.resulting_normal_hp is None or event.resulting_temporary_hp is None:
                raise ValueError("healing requires committed HP after-values")
            return ActorFactChange(owner, _hit_points(event.resulting_normal_hp, event.resulting_temporary_hp))
        case Event(event_type=EventType.CONDITION_APPLICATION | EventType.CONDITION_REMOVAL | EventType.CONDITION_STATE_CHANGED):
            if condition is None:
                if owner is None:
                    return None  # A target-less membership (no recorded state) changes no actor.
                raise ValueError("condition membership requires its recorded condition fact")
            values = {}
            if condition.resulting_max_hp is not None:
                values["maximum_hp"] = condition.resulting_max_hp
            if condition.resulting_ac is not None:
                values["armor_class"] = condition.resulting_ac
            if condition.resulting_stats is not None:
                values.update(_stats_values(condition.resulting_stats))
            removed = event.event_type is EventType.CONDITION_REMOVAL
            return ActorFactChange(owner, values, conditions_set=() if removed else (condition,),
                                   conditions_removed=(condition.condition_uuid,) if removed else (),
                                   replaced_item=condition.resulting_item)
        case LifeStateChangeEvent():
            return ActorFactChange(owner, {"life_state": event.new_state, "normal_hp": event.normal_hit_points,
                                           "remains_disposition": event.remains_disposition})
        case TemporaryHitPointsChangedEvent():
            return ActorFactChange(owner, {"temporary_hp": event.resulting_temporary_hp,
                                           "temporary_hp_grant": event.grant})
        case EquipmentEvent():
            return ActorFactChange(owner, {} if event.active_weapon_set_after is None
                                   else {"active_weapon_set": event.active_weapon_set_after})
    return None


def _without_item(items: tuple[ItemPresentationState, ...], equipment: tuple[tuple[str, UUID], ...], identity: UUID
                  ) -> tuple[tuple[ItemPresentationState, ...], tuple[tuple[str, UUID], ...]]:
    """Holdings with one item out of the inventory and every layer."""
    return (tuple(item for item in items if item.item_uuid != identity),
            tuple((slot, worn) for slot, worn in equipment if worn != identity))


def _owner_after(actor: ActorState, change: ActorFactChange) -> ActorState:
    conditions = actor.conditions
    if change.conditions_set or change.conditions_removed:
        members = {member.condition_uuid: member for member in actor.conditions}
        for identity in change.conditions_removed:
            members.pop(identity, None)
        for member in change.conditions_set:
            members[member.condition_uuid] = member
        conditions = tuple(members.values())
    items, equipment = actor.items, actor.equipment
    if change.released_by_owner is not None:
        items, equipment = _without_item(items, equipment, change.released_by_owner)
    if (used := change.used_item) is not None:
        if used.destroyed:
            items, equipment = _without_item(items, equipment, used.item_uuid)
        else:
            items = tuple(item.model_copy(update={"charges": used.charges, "stack_count": used.stack_count})
                          if item.item_uuid == used.item_uuid else item for item in items)
    if (held := change.held_item) is not None:
        identity = held.item.item_uuid
        by_uuid = {item.item_uuid: item for item in items}
        by_uuid[identity] = held.item
        items = tuple(by_uuid.values())
        slots = {slot: worn for slot, worn in equipment if worn != identity}
        if held.slot is not None:
            slots[held.slot] = identity
        equipment = tuple(slots.items())
    return replace(actor, **change.values, conditions=conditions, items=items, equipment=equipment)


def apply_actor_fact_change(actors: dict[UUID, ActorState], change: ActorFactChange) -> tuple[UUID, ...]:
    """The one fold of an actor change into a set of actors (plan §4); the identities it rewrote, in order.

    The item's other holders release it first, then the owner takes the change, then every holder of a
    replaced item takes its copy. Holders are those of this set: each fold's own holdings decide.
    """
    written: list[UUID] = []
    if (released := change.released_by_others) is not None:
        for identity, actor in tuple(actors.items()):
            if identity != change.owner_uuid and any(item.item_uuid == released for item in actor.items):
                items, equipment = _without_item(actor.items, actor.equipment, released)
                actors[identity] = replace(actor, items=items, equipment=equipment)
                written.append(identity)
    if change.owner_uuid is not None and (owner := actors.get(change.owner_uuid)) is not None:
        actors[change.owner_uuid] = _owner_after(owner, change)
        written.append(change.owner_uuid)
    if (replaced := change.replaced_item) is not None:
        for identity, actor in tuple(actors.items()):
            if any(item.item_uuid == replaced.item_uuid for item in actor.items):
                actors[identity] = replace(actor, items=tuple(
                    replaced if item.item_uuid == replaced.item_uuid else item for item in actor.items))
                written.append(identity)
    return tuple(written)


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
        resulting_max_hp=(event.resulting_stats.maximum_hp if event.resulting_stats is not None else None)
            if isinstance(event, ConditionStateChangedEvent) else event.resulting_max_hp,
        resulting_ac=(event.resulting_stats.armor_class if event.resulting_stats is not None else None)
            if isinstance(event, ConditionStateChangedEvent) else event.resulting_ac,
        state=state, resulting_stats=event.resulting_stats,
        resulting_tile=event.resulting_tile,
        resulting_item=event.resulting_item,
        consumed=isinstance(event, ConditionRemovalEvent) and event.consumed,
    )
