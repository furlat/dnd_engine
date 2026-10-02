"""Three equipped backpack powers and four ordinary attack payload stacks."""
from types import MappingProxyType
from typing import cast
from uuid import UUID


from dnd.actions import SpellAction, SpellEvent
from dnd.blocks.base_item import UsableItem
from dnd.blocks.equipment import Armor
from dnd.core.attack_types import AttackAmmunitionPayload, DamageDieValue
from dnd.core.base_actions import BaseAction, TargetType
from dnd.core.base_conditions import Duration
from dnd.core.condition_types import DurationType
from dnd.core.creature_types import DamageType
from dnd.core.equipment_types import BodyPart, WeaponSlot, ArmorType
from dnd.core.events import Event, EventPhase
from dnd.entity import Entity
from dnd.items.consumables import _TimedFireWeaponCoatCondition
from dnd.items.spell_items import SpellGrantingItem
from dnd.spells.abjuration import Resistance
from dnd.spells.roster_support import Longstrider


class EmberQuiverActivation(SpellAction):
    name: str = "Ember Quiver"
    target_type: TargetType = TargetType.SELF
    alt_skip_slot: bool = True
    selected_weapon_uuid: UUID | None = None

    def _create_declaration_event(self, parent_event: Event | None = None, use_register: bool = True):
        actor = Entity.get(self.source_entity_uuid)
        weapon = actor.equipment.get_weapon(WeaponSlot.RANGED_MAIN) if actor else None
        self.selected_weapon_uuid = weapon.uuid if weapon else None
        return super()._create_declaration_event(parent_event, use_register=use_register)

    def _validate(self,event: SpellEvent):
        actor = Entity.get(self.source_entity_uuid)
        weapon = actor.equipment.get_weapon(WeaponSlot.RANGED_MAIN) if actor else None
        if weapon is None or not weapon.supports_arrow_payload:
            return event.cancel(status_message="Ember Quiver requires an equipped bow or crossbow")
        return super()._validate(event)

    def _apply(self,event: SpellEvent):
        actor = Entity.get(self.source_entity_uuid)
        weapon = actor.equipment.get_weapon(WeaponSlot.RANGED_MAIN) if actor else None
        if (actor is None or weapon is None or weapon.uuid != self.selected_weapon_uuid
                or not weapon.supports_arrow_payload):
            return event.cancel(status_message="Bow or crossbow missing")
        condition = _TimedFireWeaponCoatCondition(source_entity_uuid=actor.uuid,target_entity_uuid=weapon.uuid,
            coated_weapon_uuid=weapon.uuid,duration=Duration(duration_type=DurationType.ROUNDS,duration=10))
        result = weapon.add_condition(condition,parent_event=event)
        if result is None or result.canceled or not condition.applied:
            return event.cancel(status_message="Fire coating rejected")
        return event.phase_to(EventPhase.EFFECT)


class PoweredBackpack(SpellGrantingItem, Armor):
    """Composition of the existing wearable and finite spell-item capabilities."""
    is_consumable: bool = False
    max_stack: int = 1
    body_part: BodyPart = BodyPart.BACKPACK
    recharge_on_long_rest: bool = True

    def permits_use_by(self, actor_uuid: UUID) -> bool:
        actor=Entity.get(actor_uuid)
        return actor is not None and actor.equipment.backpack is not None and actor.equipment.backpack.uuid == self.uuid

    def get_use_actions(self,user_entity_uuid: UUID) -> list[BaseAction]:
        actor = Entity.get(user_entity_uuid)
        if actor is None or actor.equipment.backpack is None or actor.equipment.backpack.uuid != self.uuid:
            return []
        actions = super().get_use_actions(user_entity_uuid)
        for action in actions:
            action.target_type = TargetType.SELF
            action.target_entity_uuid = user_entity_uuid
            action.include_self = True
        return actions


# Original gameplay definitions; silhouettes are accepted existing Bag2 donors.
PACK_POWERS = MappingProxyType({
    "gear.ember_quiver": ("Ember Quiver",EmberQuiverActivation,"Quiver"),
    "gear.wayfarer_pack": ("Wayfarer's Pack",Longstrider,"Quiver"),
    "gear.warden_pack": ("Warden's Pack",Resistance,"Back Canister"),
})
ARROW_PAYLOADS = MappingProxyType({
    "consumable.arrow.ember": ("Ember Arrow",DamageType.FIRE,6,None),
    "consumable.arrow.frost": ("Frost Arrow",DamageType.COLD,6,None),
    "consumable.arrow.storm": ("Storm Arrow",DamageType.LIGHTNING,6,None),
    "consumable.arrow.venom": ("Venom Arrow",DamageType.POISON,4,10),
})


def build_powered_backpack(item_id: str, actor_uuid: UUID, quantity: int = 1) -> PoweredBackpack:
    if quantity != 1:
        raise ValueError("A backpack is one physical possession")
    name,action_type,visual = PACK_POWERS[item_id]
    return PoweredBackpack(item_id=item_id,source_entity_uuid=actor_uuid,name=name,
        visual_item_name=visual,type=ArmorType.CLOTH,use_action_templates=[action_type(source_entity_uuid=actor_uuid,template=True,
            alt_skip_slot=True,target_type=TargetType.SELF,include_self=True)],charges=1,max_charges=1)


def build_special_arrow(item_id: str, actor_uuid: UUID, quantity: int = 1) -> UsableItem:
    if not 1 <= quantity <= 99:
        raise ValueError("Special arrows stack from 1 to 99")
    name,damage_type,die,dc = ARROW_PAYLOADS[item_id]
    return UsableItem(item_id=item_id,source_entity_uuid=actor_uuid,name=name,is_consumable=True,
        is_pickable=True,stack_id=item_id,stack_count=quantity,max_stack=99,charges=1,max_charges=1,
        attack_ammunition_payload=AttackAmmunitionPayload(item_id=item_id,damage_type=damage_type,
            damage_die=cast(DamageDieValue,die),save_dc=dc),use_action_templates=[])
