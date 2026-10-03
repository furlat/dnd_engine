"""Equip-scoped native composition for the accepted item property families."""
from dataclasses import dataclass
from functools import partial
from uuid import UUID

from dnd.core.base_block import BaseBlock
from dnd.core.base_actions import ActionEvent
from dnd.core.content.runtime import RuntimeBehaviorKind, bind_runtime_behavior_child
from dnd.core.events import Damage, DamageRollResultEvent, Event, EventHandler, EventPhase, EventQueue, EventType, Trigger
from dnd.core.item_properties import ArmorPenalties, ItemProperty, UnseenStrike, WearerBonus, WearerValue
from dnd.core.modifiers import AdvantageModifier, AdvantageStatus, ContextualNumericalModifier, NumericalModifier
from dnd.core.values import ModifiableValue


@dataclass(frozen=True, slots=True)
class ItemPropertyContribution:
    wearer_uuid: UUID
    handle_uuid: UUID
    value: ModifiableValue | None = None
    contextual: bool = False


def _strength_penalty(source_entity_uuid: UUID, target_entity_uuid: UUID | None = None,
                      context: dict | None = None, *, strength: ModifiableValue,
                      requirement: int, name: str) -> NumericalModifier | None:
    if strength.score >= requirement:
        return None
    return NumericalModifier(name=name, value=-10, use_register=False, source_entity_uuid=source_entity_uuid,
                             target_entity_uuid=source_entity_uuid)


def _unseen_strike(event: Event, source_entity_uuid: UUID, *, item_uuid: UUID,
                   property: UnseenStrike) -> Event | None:
    if not isinstance(event, DamageRollResultEvent) or event.source_entity_uuid != source_entity_uuid:
        return None
    attack = EventQueue.get_event_by_uuid(event.parent_event) if event.parent_event else None
    if not isinstance(attack, ActionEvent) or attack.event_type != EventType.ATTACK or attack.source_item_uuid != item_uuid:
        return None
    target = BaseBlock.get(event.target_entity_uuid) if event.target_entity_uuid else None
    senses = target.get_senses() if target is not None else None
    if senses is None:
        return None
    contact = senses.entities.get(source_entity_uuid)
    if contact is not None and contact.visual:
        return None
    damage = Damage(name=property.name, source_entity_uuid=source_entity_uuid,
        target_entity_uuid=event.target_entity_uuid, damage_dice=property.die,
        dice_numbers=property.count, damage_type=property.damage_type,
        damage_bonus=ModifiableValue.create(source_entity_uuid=source_entity_uuid,
            target_entity_uuid=event.target_entity_uuid, base_value=0,
            value_name=f"{property.name} Damage Bonus"))
    return event.append_damage_roll(damage, damage.get_dice(event.attack_outcome).roll,
        property.name, f"{property.count}d{property.die} {property.damage_type.value.lower()} (unseen attacker)")


def install_item_properties(item_uuid: UUID, item_id: str, item_name: str,
                            wearer_uuid: UUID, properties: tuple[ItemProperty, ...]) -> list[ItemPropertyContribution]:
    wearer = BaseBlock.get(wearer_uuid)
    if wearer is None:
        return []
    values = wearer.get_item_wearer_values()
    contributions: list[ItemPropertyContribution] = []
    for property in properties:
        if isinstance(property, UnseenStrike):
            handler = EventHandler(name=property.name, content_kind=RuntimeBehaviorKind.ITEM,
                source_entity_uuid=wearer_uuid,
                trigger_conditions=[Trigger(event_type=EventType.DAMAGE_ROLL_RESULT,
                    event_phase=EventPhase.EFFECT, event_source_entity_uuid=wearer_uuid)],
                event_processor=partial(_unseen_strike, item_uuid=item_uuid, property=property))
            bind_runtime_behavior_child(handler, provided_by_id=item_id, origin_root_id=item_id,
                                        runtime_owner_uuid=wearer_uuid)
            wearer.add_event_handler(handler)
            contributions.append(ItemPropertyContribution(wearer_uuid, handler.uuid))
        elif isinstance(property, WearerBonus):
            if values is None:
                continue
            value = values.charisma if property.target is WearerValue.CHARISMA else values.spell_attack
            handle = value.self_static.add_value_modifier(NumericalModifier(name=property.name,
                value=property.bonus, source_entity_uuid=item_uuid, target_entity_uuid=wearer_uuid))
            contributions.append(ItemPropertyContribution(wearer_uuid, handle, value))
        elif isinstance(property, ArmorPenalties):
            if values is None:
                continue
            if property.stealth_disadvantage:
                handle = values.stealth.self_static.add_advantage_modifier(AdvantageModifier(
                    name=f"{item_name} Stealth Disadvantage", value=AdvantageStatus.DISADVANTAGE,
                    source_entity_uuid=wearer_uuid))
                contributions.append(ItemPropertyContribution(wearer_uuid, handle, values.stealth))
            if property.strength_requirement is not None:
                name = f"{item_name} Strength Requirement"
                for speed in values.speeds:
                    handle = speed.self_contextual.add_value_modifier(ContextualNumericalModifier(
                        name=name, source_entity_uuid=wearer_uuid, target_entity_uuid=wearer_uuid,
                        callable=partial(_strength_penalty, strength=values.strength,
                            requirement=property.strength_requirement, name=name)))
                    contributions.append(ItemPropertyContribution(wearer_uuid, handle, speed, True))
    return contributions


def release_item_properties(contributions: list[ItemPropertyContribution]) -> None:
    for contribution in contributions:
        if contribution.value is not None:
            if contribution.contextual:
                contribution.value.self_contextual.remove_value_modifier(contribution.handle_uuid)
            else:
                contribution.value.self_static.remove_modifier(contribution.handle_uuid)
        else:
            wearer = BaseBlock.get(contribution.wearer_uuid)
            handler = EventHandler.get(contribution.handle_uuid)
            if wearer is not None and isinstance(handler, EventHandler):
                wearer.remove_event_handler(handler)
    contributions.clear()
