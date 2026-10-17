"""Real spell-created items, using native use, transfer and retirement owners.

Kept below spell schools: consumables imports spell roots and cannot be their
factory dependency. Cold item composition imports these builders at its owner.
"""
from uuid import UUID, uuid4
from pydantic import Field, PrivateAttr
from dnd.actions import entity_action_economy_cost_applier, entity_action_economy_cost_evaluator
from dnd.blocks.base_item import UsableItem, BaseItem, PreparedItemRetirement
from dnd.blocks.equipment import Weapon
from dnd.core.base_block import BaseBlock
from dnd.core.base_conditions import BaseCondition, Duration
from dnd.core.condition_types import DurationType, ConditionTag
from dnd.core.events import Event, Range, RangeType
from dnd.core.attack_types import SpellWeaponProfile
from dnd.core.creature_types import DamageType
from dnd.core.equipment_types import WeaponProperty
from dnd.core.gridmap import get_map
from dnd.core.base_actions import BaseAction, Cost, TargetType
from dnd.core.events import EventPhase, Healing
from dnd.core.values import ModifiableValue
from dnd.entity import Entity
from dnd.spells.content_metadata import srd_action_identity
from dnd.spells.spell_utils import fire_heal_roll_result


@srd_action_identity(content_id="action.spell.goodberry.eat",display_name="Eat Goodberry",
    description="Consume one real berry as a bonus action to heal 1d4 hit points.",
    parent_spell_name="Goodberry",source_page=150,sort_order=3200,adaptation_notes="BG3 bonus-action 1d4 consumption.")
class EatGoodberry(BaseAction):
    name: str = "Eat Goodberry"
    description: str = "Consume this berry to regain 1d4 hit points."
    target_type: TargetType = TargetType.SELF
    source_item_uuid: UUID | None = None
    costs: list[Cost] = Field(default_factory=lambda:[Cost(name="Eat Goodberry",cost_type="bonus_actions",cost=1,
        evaluator=entity_action_economy_cost_evaluator)])

    def _apply_costs(self,event):
        return entity_action_economy_cost_applier(event,self.source_entity_uuid)

    def _apply(self,event):
        effect=event.phase_to(EventPhase.EFFECT)
        if effect.canceled:
            return effect
        actor=Entity.get(self.source_entity_uuid)
        if actor is None:
            return effect.cancel(status_message="Berry user is absent")
        healing=Healing(source_entity_uuid=actor.uuid,target_entity_uuid=actor.uuid,healing_dice=4,dice_numbers=1,
            healing_bonus=ModifiableValue.create(source_entity_uuid=actor.uuid,base_value=0))
        roll=fire_heal_roll_result(actor.uuid,actor.uuid,healing,effect,"Goodberry")
        actor.receive_healing(roll.total,actor.uuid,source_description="Goodberry",parent_event=effect.uuid)
        return effect


class GoodberryItem(UsableItem):
    name: str = "Goodberry"
    description: str = "A temporary magical berry. Eat as a bonus action to heal 1d4."
    is_magical: bool = True
    is_consumable: bool = True
    is_pickable: bool = True
    charges: int = 1
    max_charges: int = 1
    max_stack: int = 1
    weight: float = 0.01


def build_goodberry(source_entity_uuid: UUID) -> GoodberryItem:
    return GoodberryItem(source_entity_uuid=source_entity_uuid,item_id="consumable.goodberry",
        use_action_templates=[EatGoodberry(source_entity_uuid=uuid4(),source_item_uuid=uuid4(),template=True)])


class CreatedItemsLifetime(BaseCondition):
    name: str = "Created Items"
    tags: set[ConditionTag] = Field(default_factory=lambda:{ConditionTag.MAGICAL})
    description: str = "Owns exact temporary item UUIDs through native retirement."
    duration: Duration = Field(default_factory=lambda:Duration(duration_type=DurationType.UNTIL_LONG_REST))
    item_uuids: list[UUID] = Field(default_factory=list)
    retiring: bool = False
    _retirements: list[PreparedItemRetirement] = PrivateAttr(default_factory=list)

    def model_post_init(self,context: object) -> None:
        super().model_post_init(context)
        self.name=f"{self.name}:{self.uuid}"

    def prepare_removal_state(self,event: Event) -> Event:
        self._retirements=[]
        for identity in self.item_uuids:
            item=BaseBlock.get(identity)
            if isinstance(item,BaseItem) and item.is_active:
                prepared=item.prepare_retirement(event)
                if prepared is None:
                    self.cancel_prepared_removal("Berry retirement vetoed")
                    return event.cancel(status_message="A remaining berry could not retire")
                self._retirements.append(prepared)
        return event

    def cancel_prepared_removal(self,reason: str) -> None:
        for prepared in self._retirements:
            if not prepared.committed:
                prepared.item.cancel_retirement(prepared)
        self._retirements=[]

    def _remove(self,event: Event | None=None):
        self.retiring=True
        for prepared in self._retirements:
            prepared.item.commit_retirement(prepared)
        self._retirements=[]
        return event



class FlameBladeItem(Weapon):
    name: str = "Flame Blade"
    description: str = "Temporary scimitar making melee spell attacks without ability damage."
    is_magical: bool = True
    is_pickable: bool = True
    damage_dice: int = 6
    dice_numbers: int = 3
    damage_type: DamageType = DamageType.FIRE
    properties: list[WeaponProperty] = Field(default_factory=lambda:[WeaponProperty.LIGHT,WeaponProperty.FINESSE])
    range: Range = Field(default_factory=lambda:Range(type=RangeType.REACH,normal=5))

    lifetime_condition_uuid: UUID | None = None

    def on_world_placement_committed(self,event: Event) -> None:
        super().on_world_placement_committed(event)
        profile=self.spell_attack_profile
        caster=Entity.get(profile.wielder_uuid) if profile else None
        if (caster is not None and self.lifetime_condition_uuid is not None and self.owner_uuid!=caster.uuid
                and (owner:=caster.active_conditions_by_uuid.get(self.lifetime_condition_uuid)) is not None
                and isinstance(owner,CreatedItemsLifetime) and not owner.retiring):
            caster.remove_condition_by_uuid(self.lifetime_condition_uuid,parent_event=event)


def build_flame_blade(source_entity_uuid: UUID,*,profile: SpellWeaponProfile,dice_numbers: int=3) -> FlameBladeItem:
    return FlameBladeItem(source_entity_uuid=source_entity_uuid,item_id="weapon.flame_blade",spell_attack_profile=profile,
        dice_numbers=dice_numbers,damage_bonus=ModifiableValue.create(source_entity_uuid=source_entity_uuid,base_value=0))


class FlameBladeLifetime(CreatedItemsLifetime):
    name: str = "Flame Blade"
    description: str = "Ten-turn exact blade ownership; leaving the caster's holdings retires it."
    duration: Duration = Field(default_factory=lambda:Duration(duration=10,duration_type=DurationType.ROUNDS))
    light_source_uuid: UUID | None = None

    def _apply(self,event: Event):
        modifiers,handlers,children,spatial,effect=super()._apply(event)
        caster=Entity.get(self.source_entity_uuid)
        if effect is None or effect.canceled or caster is None:
            return modifiers,handlers,children,spatial,effect
        self.light_source_uuid=get_map().add_light_source(caster.position,bright_radius_feet=10,dim_radius_feet=10,
            anchor_uuid=caster.uuid,contribution_owner_uuid=self.uuid,parent_event=effect.uuid)
        return modifiers,handlers,children,spatial,effect

    def _release_owned_runtime_state(self,*,parent_event: Event | None=None):
        if self.light_source_uuid is not None:
            get_map().remove_light_source(self.light_source_uuid,parent_event=parent_event.uuid if parent_event else None)
            self.light_source_uuid=None
        super()._release_owned_runtime_state(parent_event=parent_event)
