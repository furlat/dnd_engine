from typing import DefaultDict, Dict, Optional, Any, List, ClassVar, Union, Tuple, Set
from uuid import UUID, uuid4
from pydantic import BaseModel, Field
from collections import defaultdict

from dnd.core.values import ModifiableValue
from dnd.core.modifiers import NumericalModifier
from dnd.core.values import CriticalStatus, AutoHitStatus
from dnd.core.base_conditions import BaseCondition
from dnd.core.dice import Dice, RollType, DiceRoll, AttackOutcome
from dnd.core.events import Event, RangeType, SavingThrowEvent, SkillCheckEvent
from dnd.core.base_block import BaseBlock
from dnd.blocks.abilities import AbilityScoresConfig, AbilityScores
from dnd.blocks.saving_throws import SavingThrowSetConfig, SavingThrowSet
from dnd.blocks.health import HealthConfig, Health
from dnd.blocks.equipment import EquipmentConfig, Equipment, WeaponSlot, WeaponProperty, Range, Shield, Damage
from dnd.blocks.action_economy import ActionEconomyConfig, ActionEconomy
from dnd.blocks.skills import SkillSetConfig, SkillSet
from dnd.blocks.sensory import Senses
from dnd.core.events import AbilityName, SkillName
from dnd.core.gridmap import get_map
from dnd.core.base_actions import (
    BaseAction, TargetType,
    AvailableTarget, AvailableActionInfo, AvailableActionsResult
)


def determine_attack_outcome(roll: DiceRoll, ac: Union[int, ModifiableValue]) -> AttackOutcome:
        """
        Determine attack outcome based on roll and AC.
        
        Args:
            roll: The dice roll result
            ac: The armor class to check against
            
        Returns:
            AttackOutcome: The outcome of the attack
        """
        target_ac = ac.normalized_score if isinstance(ac, ModifiableValue) else ac
        
        # First check auto miss which overrides everything else
        if roll.auto_hit_status == AutoHitStatus.AUTOMISS:
            return AttackOutcome.MISS
        # Second check if the roll is an auto hit (with critical check)
        elif roll.auto_hit_status == AutoHitStatus.AUTOHIT:
            if roll.critical_status == CriticalStatus.AUTOCRIT or roll.results == 20:
                return AttackOutcome.CRIT
            else:
                return AttackOutcome.HIT
        # Check for natural 1 (critical miss)
        elif roll.results == 1:
            return AttackOutcome.CRIT_MISS
        # Check if roll meets or exceeds AC (with critical check)
        elif roll.total >= target_ac:
            if roll.critical_status == CriticalStatus.AUTOCRIT or roll.results == 20:
                return AttackOutcome.CRIT
            else:
                return AttackOutcome.HIT
        # Finally, it's a miss
        else:
            return AttackOutcome.MISS
        
class EntityConfig(BaseModel):
    ability_scores: AbilityScoresConfig = Field(default_factory=AbilityScoresConfig,description="Ability scores for the entity")
    skill_set: SkillSetConfig = Field(default_factory=SkillSetConfig,description="Skill set for the entity")
    saving_throws: SavingThrowSetConfig = Field(default_factory=SavingThrowSetConfig,description="Saving throws for the entity")
    health: HealthConfig = Field(default_factory=HealthConfig,description="Health for the entity")
    equipment: EquipmentConfig = Field(default_factory=EquipmentConfig,description="Equipment for the entity")
    action_economy: ActionEconomyConfig = Field(default_factory=ActionEconomyConfig,description="Action economy for the entity")
    proficiency_bonus: int = Field(default=0,description="Proficiency bonus for the entity")
    proficiency_bonus_modifiers: List[Tuple[str, int]] = Field(default_factory=list,description="Any additional static modifiers applied to the proficiency bonus")
    initiative_modifiers: List[Tuple[str, int]] = Field(default_factory=list,description="Any additional static modifiers applied to initiative (e.g., Alert feat +5)")
    position: Tuple[int,int] = Field(default_factory=lambda: (0,0),description="Position of the entity")
    sprite_name: Optional[str] = Field(default=None,description="The name of the sprite to use for the entity")

class Entity(BaseBlock):
    """ Base class for dnd entities in the game it acts as container for blocks and implements common functionalities that
    require interactions between blocks """

    name: str = Field(default="Entity")
    ability_scores: AbilityScores = Field(default_factory=lambda: AbilityScores.create(source_entity_uuid=uuid4()))
    skill_set: SkillSet = Field(default_factory=lambda: SkillSet.create(source_entity_uuid=uuid4()))
    saving_throws: SavingThrowSet = Field(default_factory=lambda: SavingThrowSet.create(source_entity_uuid=uuid4()))
    health: Health = Field(default_factory=lambda: Health.create(source_entity_uuid=uuid4()))
    equipment: Equipment = Field(default_factory=lambda: Equipment.create(source_entity_uuid=uuid4()))
    action_economy: ActionEconomy = Field(default_factory=lambda: ActionEconomy.create(source_entity_uuid=uuid4()))
    proficiency_bonus: ModifiableValue = Field(default_factory=lambda: ModifiableValue.create(source_entity_uuid=uuid4(), value_name="proficiency_bonus", base_value=2))
    initiative: ModifiableValue = Field(default_factory=lambda: ModifiableValue.create(source_entity_uuid=uuid4(), value_name="initiative", base_value=0))
    senses: Senses = Field(default_factory=lambda: Senses.create(source_entity_uuid=uuid4()))
    allow_events_conditions: bool = Field(default=True, description="If True, events and conditions will be allowed to be added to the block")
    sprite_name: Optional[str] = Field(default=None, description="The name of the sprite to use for the entity")

    # Action registry - stores action templates for this entity
    registered_actions: List[BaseAction] = Field(default_factory=list, description="Registered action templates for this entity")

    _entity_registry: ClassVar[Dict[UUID, 'Entity']] = {}
    _entity_by_position: ClassVar[DefaultDict[Tuple[int, int], List['Entity']]] = defaultdict(list)

    def __init__(self, **data):
        """
        Initialize the BaseBlock and register it in the class registry.

        Args:
            **data: Keyword arguments to initialize the BaseBlock attributes.
        """
        super().__init__(**data)
        self.__class__._entity_registry[self.uuid] = self
        self.__class__._entity_by_position[self.position].append(self)
        # Also register with GridMap for spatial queries
        get_map().register_entity(self.uuid, self.position)
        # Note: Action templates are set up via actions_functional.setup_standard_actions()
        # Called from entity factories (e.g., bestiary.py) after entity creation

    @classmethod
    def update_entity_position(cls, entity: 'Entity', new_position: Tuple[int, int]):
        """Update entity position in both class registry and GridMap."""
        cls._entity_by_position[entity.position].remove(entity)
        cls._entity_by_position[new_position].append(entity)
        entity._set_position(new_position)
        # Also update GridMap (handles dirty tracking)
        get_map().move_entity(entity.uuid, new_position)

    @classmethod
    def register_entity(cls, entity: 'Entity'):
        cls._entity_registry[entity.uuid] = entity

    @classmethod
    def get_all_entities(cls) -> List['Entity']:
        return list(cls._entity_registry.values())
    
    @classmethod
    def get_all_entities_at_position(cls, position: Tuple[int,int]) -> List['Entity']:
        return cls._entity_by_position[position]
    
    @classmethod
    def get(cls, uuid: UUID) -> Optional['Entity']:
        return cls._entity_registry.get(uuid)
    
    @classmethod
    def create(cls, source_entity_uuid: UUID, name: str = "Entity",description: Optional[str] = None,config: Optional[EntityConfig] = None) -> 'Entity':
        """
        Create a new Entity instance with the given parameters. All sub-blocks will share
        the same source_entity_uuid as the entity itself.

        Args:
            source_entity_uuid (UUID): The UUID that will be used as both the entity's UUID and source_entity_uuid
            name (str): The name of the entity. Defaults to "Entity"

        Returns: 
            Entity: The newly created Entity instance
        """
        if config is None:
            return cls(
                uuid=source_entity_uuid,
                source_entity_uuid=source_entity_uuid,
                name=name)
        else:
            ability_scores = AbilityScores.create(source_entity_uuid=source_entity_uuid,config=config.ability_scores)
            skill_set = SkillSet.create(source_entity_uuid=source_entity_uuid,config=config.skill_set)
            saving_throws = SavingThrowSet.create(source_entity_uuid=source_entity_uuid,config=config.saving_throws)
            health = Health.create(source_entity_uuid=source_entity_uuid,config=config.health)
            equipment = Equipment.create(source_entity_uuid=source_entity_uuid,config=config.equipment)
            senses = Senses.create(source_entity_uuid=source_entity_uuid,position=config.position)
            action_economy = ActionEconomy.create(source_entity_uuid=source_entity_uuid,config=config.action_economy)
            proficiency_bonus = ModifiableValue.create(source_entity_uuid=source_entity_uuid,base_value=config.proficiency_bonus)
            for modifier in config.proficiency_bonus_modifiers:
                proficiency_bonus.self_static.add_value_modifier(NumericalModifier.create(source_entity_uuid=source_entity_uuid,name=modifier[0],value=modifier[1]))

            # Initiative base is DEX modifier
            dex_mod = ability_scores.get_ability("dexterity").modifier
            initiative = ModifiableValue.create(source_entity_uuid=source_entity_uuid,base_value=dex_mod,value_name="initiative")
            for modifier in config.initiative_modifiers:
                initiative.self_static.add_value_modifier(NumericalModifier.create(source_entity_uuid=source_entity_uuid,name=modifier[0],value=modifier[1]))

            return cls(
                uuid=source_entity_uuid,
                source_entity_uuid=source_entity_uuid,
                name=name,
                description=description,
                ability_scores=ability_scores,
                skill_set=skill_set,
                saving_throws=saving_throws,
                health=health,
                equipment=equipment,
                senses=senses,
                action_economy=action_economy,
                proficiency_bonus=proficiency_bonus,
                initiative=initiative,
                position=config.position,
                sprite_name=config.sprite_name
            )

    def _set_position(self,new_position: Tuple[int,int]):
        """ move the entity to a new position without updating the registry  - should not be used directly"""
        self.position = new_position
        self.senses.position = new_position 

    def move(self,new_position: Tuple[int,int], update_senses: bool = True):
        """ move the entity to a new position """
        
        Entity.update_entity_position(self,new_position)
        if update_senses:
            Entity.update_all_entities_senses()
        
    def get_target_entity(self,copy: bool = False) -> Optional['Entity']:
        if self.target_entity_uuid is None:
            return None
        target_entity = Entity.get(self.target_entity_uuid)
        assert isinstance(target_entity, Entity)
        return target_entity if not copy else target_entity.model_copy(deep=True)
    
    def check_condition_immunity(self, condition_name: str) -> bool:
        #first check static immunities
        for static_immunity in self.condition_immunities:
            if static_immunity[0] == condition_name:
                return True
        #then check contextual immunities
        condition_contextual_immunities = self.contextual_condition_immunities.get(condition_name,[])
        for _, immunity_check in condition_contextual_immunities:
            if immunity_check(self,self.get_target_entity(copy=True),self.context):
                return True
        return False
    

    
    def add_condition(self, condition: BaseCondition, context: Optional[Dict[str, Any]] = None, check_save_throw: bool = True, parent_event: Optional[Event] = None)  -> Optional[Event]:
        """ Overrides the base method of BaseBlock to add the saving throw checks"""
        if condition.name is None:
            raise ValueError("BaseCondition name is not set")
        if condition.target_entity_uuid is None:
            condition.target_entity_uuid = self.uuid
        if context is not None:
            condition.set_context(context)
        
        declaration_event = condition.declare_event(parent_event)

        if self.check_condition_immunity(condition.name):
            if declaration_event is not None:
                return declaration_event.cancel(status_message=f"Condition {condition.name} is immune")
            else:
                return None
        if check_save_throw and condition.application_saving_throw is not None:
            (_, _, success) = self.saving_throw(condition.application_saving_throw)
            if success:
                if declaration_event is not None:
                    return declaration_event.cancel(status_message=f"Target passed the {condition.application_saving_throw.ability_name} saving throw with")
                else:
                    return None
        condition_applied = condition.apply(declaration_event=declaration_event)
        if condition_applied:
            if condition.name in self.active_conditions:
                #already present we need to remove the old one and add the new one for now not stackable
                self.remove_condition(condition.name)
            self.active_conditions[condition.name] = condition
            self.active_conditions_by_uuid[condition.uuid] = condition
            self.active_conditions_by_source[condition.source_entity_uuid].append(condition.name)
        return condition_applied
    
    

    
    def advance_duration_condition(self,condition_name:str, skip_save_throw: bool = False) -> bool:
        """ Overrides the base method of BaseBlock to add the saving throw checks"""
        condition = self.active_conditions[condition_name]
        if not skip_save_throw and condition.removal_saving_throw is not None:
            (_, _, success) = self.saving_throw(condition.removal_saving_throw)
            if success:
                self.remove_condition(condition_name)
                return True
        removed = condition.progress()
        if removed:
            self.active_conditions.pop(condition_name)
            self._remove_condition_from_dicts(condition)
        return removed
    

    
    
    def _get_bonuses_for_skill(self, skill_name: SkillName) -> Tuple[ModifiableValue,ModifiableValue,ModifiableValue,ModifiableValue]:
        proficiency_bonus = self.proficiency_bonus
        skill = self.skill_set.get_skill(skill_name)
        skill_bonus = skill.skill_bonus
        proficiency_bonus_multiplier_callable = skill._get_proficiency_converter()
        ability_name = skill.ability
        ability = self.ability_scores.get_ability(ability_name)
        ability_bonus = ability.ability_score
        ability_modifier_bonus = ability.modifier_bonus
        normalized_proficiency_bonus = proficiency_bonus.model_copy(deep=True)
        normalized_proficiency_bonus.update_normalizers(proficiency_bonus_multiplier_callable)
        return normalized_proficiency_bonus, skill_bonus, ability_bonus, ability_modifier_bonus
    
    def _get_bonuses_for_saving_throw(self, ability_name: AbilityName) -> Tuple[ModifiableValue,ModifiableValue,ModifiableValue,ModifiableValue]:
        saving_throw = self.saving_throws.get_saving_throw(ability_name)
        saving_throw_bonus = saving_throw.bonus
        proficiency_bonus_multiplier_callable = saving_throw._get_proficiency_converter()
        proficiency_bonus = self.proficiency_bonus
        ability_bonus = self.ability_scores.get_ability(ability_name).ability_score
        ability_modifier_bonus = self.ability_scores.get_ability(ability_name).modifier_bonus

        normalized_proficiency_bonus = proficiency_bonus.model_copy(deep=True)
        normalized_proficiency_bonus.update_normalizers(proficiency_bonus_multiplier_callable)
        return normalized_proficiency_bonus, saving_throw_bonus, ability_bonus,ability_modifier_bonus
    
    def _get_attack_bonuses(self,weapon_slot: WeaponSlot = WeaponSlot.MELEE_MAIN) -> Tuple[ModifiableValue,ModifiableValue,List[ModifiableValue],List[ModifiableValue],Range ]:
        """ We have to get from weapon and then from equipment
        attack_bonus
        ability bonuses
        weapon attack bonus """
        weapon = self.equipment._get_weapon_by_slot(weapon_slot)

        ability_bonuses : List[ModifiableValue] = []
        dexterity_bonus = self.ability_scores.get_ability("dexterity").ability_score
        dexterity_modifier_bonus = self.ability_scores.get_ability("dexterity").modifier_bonus
        strength_bonus = self.ability_scores.get_ability("strength").ability_score
        strength_modifier_bonus = self.ability_scores.get_ability("strength").modifier_bonus
        attack_bonuses : List[ModifiableValue] = [self.equipment.attack_bonus]
        if weapon is None or isinstance(weapon, Shield):
            weapon_bonus=self.equipment.unarmed_attack_bonus
            attack_bonuses.append(self.equipment.melee_attack_bonus)
            ability_bonuses.append(strength_bonus)
            ability_bonuses.append(strength_modifier_bonus)
            range = Range(type=RangeType.REACH,normal=5)
        else:
            weapon_bonus=weapon.attack_bonus
            range = weapon.range
            if range.type == RangeType.RANGE:

                attack_bonuses.append(self.equipment.ranged_attack_bonus)
                ability_bonuses.append(dexterity_bonus)
                ability_bonuses.append(dexterity_modifier_bonus)
            elif range.type == RangeType.REACH and WeaponProperty.FINESSE in weapon.properties:
                attack_bonuses.append(self.equipment.melee_attack_bonus)
                combined_strength_bonus = strength_bonus.combine_values([strength_modifier_bonus])
                combined_dexterity_bonus = dexterity_bonus.combine_values([dexterity_modifier_bonus])
                if combined_strength_bonus.normalized_score >= combined_dexterity_bonus.normalized_score:
                    ability_bonuses.append(strength_bonus)
                    ability_bonuses.append(strength_modifier_bonus)
                else:
                    ability_bonuses.append(dexterity_bonus)
                    ability_bonuses.append(dexterity_modifier_bonus)
            else:
                attack_bonuses.append(self.equipment.melee_attack_bonus)
                ability_bonuses.append(strength_bonus)
                ability_bonuses.append(strength_modifier_bonus)
        proficiency_bonus = self.proficiency_bonus
        
        return proficiency_bonus, weapon_bonus, attack_bonuses, ability_bonuses, range
      
    

    
    def saving_throw_bonus(self, target_entity_uuid: Optional[UUID], ability_name: AbilityName) -> ModifiableValue:
        should_clear_target = False
        if target_entity_uuid is not None and target_entity_uuid != self.target_entity_uuid:
            self.set_target_entity(target_entity_uuid)
            should_clear_target = True
        target_entity = None
        if self.target_entity_uuid:
            target_entity = self.get_target_entity(copy=True)
            assert isinstance(target_entity, Entity)
            if target_entity.target_entity_uuid != self.uuid:
                target_entity.set_target_entity(self.uuid)
            saving_throw_bonuses_target = target_entity._get_bonuses_for_saving_throw(ability_name)

        saving_throw_bonuses_source =self._get_bonuses_for_saving_throw(ability_name)
        if target_entity is not None:
            for mod_source,mod_target in zip(saving_throw_bonuses_source,saving_throw_bonuses_target):
                mod_source.set_from_target(mod_target)    
        total_bonus_source = saving_throw_bonuses_source[0].combine_values(list(saving_throw_bonuses_source)[1:]).model_copy(deep=True)
        
        if should_clear_target:
            self.clear_target_entity()

        return total_bonus_source

    def skill_bonus(self, target_entity_uuid: Optional[UUID], skill_name: SkillName) -> ModifiableValue:
        should_clear_target = False
        if target_entity_uuid is not None and target_entity_uuid != self.target_entity_uuid:
            self.set_target_entity(target_entity_uuid)
            should_clear_target = True
        
        target_entity = None
        if self.target_entity_uuid:
            target_entity = self.get_target_entity(copy=True)
            assert isinstance(target_entity, Entity)
            if target_entity.target_entity_uuid != self.uuid:
                target_entity.set_target_entity(self.uuid)
            skill_bonuses_target = target_entity._get_bonuses_for_skill(skill_name)

        skill_bonuses_source = self._get_bonuses_for_skill(skill_name)
        if target_entity is not None:
            for mod_source, mod_target in zip(skill_bonuses_source, skill_bonuses_target):
                mod_source.set_from_target(mod_target)
        
        total_bonus_source = skill_bonuses_source[0].combine_values(list(skill_bonuses_source)[1:]).model_copy(deep=True)
        
        if should_clear_target:
            self.clear_target_entity()
            if target_entity is not None:
                target_entity.clear_target_entity() 
            for mod_source, mod_target in zip(skill_bonuses_source, skill_bonuses_target):
                mod_source.reset_from_target()
                mod_target.reset_from_target()

        return total_bonus_source

    def skill_bonus_cross(self, target_entity_uuid: UUID, skill_name: SkillName) -> Tuple[ModifiableValue, ModifiableValue]:
        should_clear_target = False
        if target_entity_uuid is not None and target_entity_uuid != self.target_entity_uuid:
            self.set_target_entity(target_entity_uuid)
            should_clear_target = True
        
        target_entity = self.get_target_entity(copy=True)
        assert isinstance(target_entity, Entity)
        if target_entity.target_entity_uuid != self.uuid:
            target_entity.set_target_entity(self.uuid)

        skill_bonuses_source = self._get_bonuses_for_skill(skill_name)
        skill_bonuses_target = target_entity._get_bonuses_for_skill(skill_name)

        for mod_source, mod_target in zip(skill_bonuses_source, skill_bonuses_target):
            mod_target.set_from_target(mod_source)
            mod_source.set_from_target(mod_target)

        total_bonus_source = skill_bonuses_source[0].combine_values(list(skill_bonuses_source)[1:]).model_copy(deep=True)
        total_bonus_target = skill_bonuses_target[0].combine_values(list(skill_bonuses_target)[1:]).model_copy(deep=True)

        if should_clear_target:
            self.clear_target_entity()
            target_entity.clear_target_entity()
        for mod_source, mod_target in zip(skill_bonuses_source, skill_bonuses_target):
            mod_source.reset_from_target()
            mod_target.reset_from_target()

        return total_bonus_source, total_bonus_target
    
    def ac_bonus(self, target_entity_uuid: Optional[UUID]=None) -> ModifiableValue:
        """ missing effects from target attack bonus"""
        should_clear_target = False
        if target_entity_uuid is not None and target_entity_uuid != self.target_entity_uuid:
            self.set_target_entity(target_entity_uuid)
            should_clear_target = True

        if self.equipment.is_unarmored():
            unarmored_values = self.equipment.get_unarmored_ac_values()
            abilities = self.equipment.get_unarmored_abilities()
            ability_bonuses = [self.ability_scores.get_ability(ability).ability_score for ability in abilities]
            ability_modifier_bonuses = [self.ability_scores.get_ability(ability).modifier_bonus for ability in abilities]
            ac_bonus = unarmored_values[0].combine_values(unarmored_values[1:]+ability_bonuses+ability_modifier_bonuses)
        else:
            armored_values = self.equipment.get_armored_ac_values()
            max_dexterity_bonus = self.equipment.get_armored_max_dex_bonus()
            dexterity_bonus = self.ability_scores.get_ability("dexterity").ability_score
            dexterity_modifier_bonus = self.ability_scores.get_ability("dexterity").modifier_bonus
            combined_dexterity_bonus = dexterity_bonus.combine_values([dexterity_modifier_bonus])
            
            # Only cap dexterity if there's a max_dexterity_bonus
            if max_dexterity_bonus is not None and combined_dexterity_bonus.normalized_score > max_dexterity_bonus.normalized_score:
                combined_dexterity_bonus = max_dexterity_bonus
            
            ac_bonus = armored_values[0].combine_values(armored_values[1:]+[combined_dexterity_bonus])
        
        if should_clear_target:
            self.clear_target_entity()
        return ac_bonus
    
    
    def attack_bonus(self, weapon_slot: WeaponSlot = WeaponSlot.MELEE_MAIN, target_entity_uuid: Optional[UUID] = None) -> ModifiableValue:
        """ missing effects from target armor bonus"""
        should_clear_target = False
        if target_entity_uuid is not None and target_entity_uuid != self.target_entity_uuid:
            self.set_target_entity(target_entity_uuid)
            should_clear_target = True
    
        proficiency_bonus, weapon_bonus, attack_bonuses, ability_bonuses, _ = self._get_attack_bonuses(weapon_slot)
        bonuses = [weapon_bonus] + attack_bonuses + ability_bonuses
        source_attack_bonus = proficiency_bonus.combine_values(bonuses)
        
        if should_clear_target:
            self.clear_target_entity()
        return source_attack_bonus
    

    def get_damages(self, weapon_slot: WeaponSlot = WeaponSlot.MELEE_MAIN, target_entity_uuid: Optional[UUID] = None) -> List[Damage]:
        should_clear_target = False
        if target_entity_uuid is not None and target_entity_uuid != self.target_entity_uuid:
            self.set_target_entity(target_entity_uuid)
            should_clear_target = True
        damages = self.equipment.get_damages(weapon_slot, self.ability_scores)
        if should_clear_target:
            self.clear_target_entity()
        return damages
    
    def take_damage(self, damages: List[Damage], attack_outcome: AttackOutcome) -> List[DiceRoll]:
        """ From each damage we get the dice and damage type and we roll it """
        
        rolls = []
        for damage in damages:
            dice = damage.get_dice(attack_outcome=attack_outcome)
            roll = dice.roll
            rolls.append(roll)
            self.health.take_damage(roll.total, damage.damage_type, source_entity_uuid=damage.source_entity_uuid)


        return rolls
    
    def get_hp(self) -> int:
        """ total health of the entity """
        con_modifier = self.ability_scores.get_ability("constitution").get_combined_values()
        return self.health.get_total_hit_points(constitution_modifier=con_modifier.normalized_score)
    
    def get_weapon_range(self, weapon_slot: WeaponSlot = WeaponSlot.MELEE_MAIN) -> Range:
        """
        Get the range of a weapon without calculating attack bonuses.

        Args:
            weapon_slot: Which weapon slot to check

        Returns:
            Range: The range of the weapon
        """
        weapon = self.equipment._get_weapon_by_slot(weapon_slot)

        if weapon is None or isinstance(weapon, Shield):
            return Range(type=RangeType.REACH, normal=5)
        else:
            return weapon.range

    def is_threatened(self) -> bool:
        """
        Check if any visible entity threatens this entity's position.

        An entity is threatened if it's within the threatened positions
        (adjacent cells) of any other visible entity. Used for ranged attack
        disadvantage - making a ranged attack while threatened imposes disadvantage.

        Returns:
            bool: True if any visible entity threatens this entity's position
        """
        my_position = self.senses.position
        for entity_uuid in self.senses.entities.keys():
            other_entity = Entity.get(entity_uuid)
            if other_entity and my_position in other_entity.senses.get_threathened_positions():
                return True
        return False

    def roll_d20(self, bonus: ModifiableValue,roll_type: RollType = RollType.ATTACK) -> DiceRoll:
        """
        Roll attack dice based on attack bonus.

        Args:
            attack_bonus: The total attack bonus to use
            
        Returns:
            DiceRoll: The result of the attack roll
        """
        attack_dice = Dice(count=1, value=20, bonus=bonus, roll_type=roll_type)
        return attack_dice.roll
        
    
    def create_saving_throw_request(self, target_entity_uuid: UUID, ability_name: AbilityName, dc: Union[int,UUID]) -> SavingThrowEvent:
        """ request a saving throw from the target entity """
        #if dc is a uuid get the modifiable value ensure is coming from self (has self.uuid as source entity uuid)
        if isinstance(dc,UUID):
            
            self.set_target_entity(dc)
            new_dc = ModifiableValue.get(dc)
            if new_dc is None or new_dc.source_entity_uuid != self.uuid:
                raise ValueError("DC is not coming from self oir not present")
            new_dc = new_dc.model_copy(deep=True)
            new_dc.set_target_entity(target_entity_uuid)
            int_dc = new_dc.normalized_score
        else:
            int_dc = dc
        self.clear_target_entity()
        return SavingThrowEvent(source_entity_uuid=self.uuid, target_entity_uuid=target_entity_uuid, ability_name=ability_name, dc=int_dc)
    

    def create_skill_check_request(self, target_entity_uuid: UUID, skill_name: SkillName, dc: Union[int,UUID]) -> SkillCheckEvent:
        """ request a skill check from the target entity """
        if isinstance(dc,UUID):
            self.set_target_entity(dc)
            dc_modifier = ModifiableValue.get(dc)
            if dc_modifier is None or dc_modifier.source_entity_uuid != self.uuid:
                raise ValueError(f"not present {dc_modifier is None} or not coming from self")
            if target_entity_uuid != dc_modifier.target_entity_uuid:
                new_dc = dc_modifier.model_copy(deep=True)
                new_dc.set_target_entity(target_entity_uuid)
            else:
                new_dc = dc_modifier
            int_dc = new_dc.normalized_score
        else:
            int_dc = dc
        self.clear_target_entity()
        return SkillCheckEvent(source_entity_uuid=self.uuid, target_entity_uuid=target_entity_uuid, skill_name=skill_name, dc=int_dc)
    
    def saving_throw(self, request: SavingThrowEvent) -> Tuple[AttackOutcome,DiceRoll,bool]:
        """ make a saving throw"""
        #first assert that the target of the saving throw is self
        if request.target_entity_uuid != self.uuid:
            raise ValueError("Target entity uuid does not match")
        #second set the target to the requester source entity
        self.set_target_entity(request.source_entity_uuid)
        #second get the saving throw from the request
        saving_throw = self.saving_throw_bonus(request.source_entity_uuid, request.ability_name)
        #third get the dc for the saving throw
        
        dc = request.get_dc()

        if dc is None:
            raise ValueError(f"DC is not set for {request.ability_name} saving throw with event id {request.uuid}")
        #create the dice
        roll = self.roll_d20(saving_throw,RollType.SAVE)

        saving_throw_outcome = determine_attack_outcome(roll,dc)

        self.clear_target_entity()
        return saving_throw_outcome, roll, True if saving_throw_outcome not in [AttackOutcome.MISS,AttackOutcome.CRIT_MISS] else False
    
    def skill_check(self, request: SkillCheckEvent) -> Tuple[AttackOutcome,DiceRoll,bool]:
        """ make a skill check """
        if request.target_entity_uuid != self.uuid:
            raise ValueError("Target entity uuid does not match")
        self.set_target_entity(request.source_entity_uuid)
        skill_check = self.skill_bonus(request.source_entity_uuid, request.skill_name)
        dc = request.get_dc()
        if dc is None:
            raise ValueError(f"DC is not set for {request.skill_name} skill check with event id {request.uuid}")
        #create the dice
        roll = self.roll_d20(skill_check,RollType.CHECK)
        skill_check_outcome = determine_attack_outcome(roll,dc)
        self.clear_target_entity()
        return skill_check_outcome, roll, True if skill_check_outcome not in [AttackOutcome.MISS,AttackOutcome.CRIT_MISS] else False


    @staticmethod
    def compute_senses_from_position(
        position: Tuple[int, int],
        seen: Set[Tuple[int, int]],
        max_distance: int = 10,
        entity_uuid: Optional[UUID] = None
    ) -> Tuple[Dict[Tuple[int, int], bool], DefaultDict[Tuple[int, int], List[Tuple[int, int]]], Dict[Tuple[int, int], bool], Dict[UUID, Tuple[int, int]]]:
        """
        Compute senses data from a position.

        Args:
            position: The position to compute from
            seen: Set of previously seen positions
            max_distance: Maximum view/movement distance
            entity_uuid: If provided, pathfinding will exclude cells occupied by other entities

        Returns:
            (visible_dict, paths, walkable, visible_entities)
        """
        grid = get_map()

        # Get visible cells using shadowcast
        visible_positions = grid.compute_fov(position, max_distance)
        visible_dict = {pos: True for pos in visible_positions}

        # Get walkable paths using dijkstra (with occupancy check if entity_uuid provided)
        _, paths = grid.compute_paths(position, max_distance, requesting_entity_uuid=entity_uuid)

        # Filter paths to only include those where:
        # 1. The destination is currently visible
        # 2. All positions in the path are either seen before OR currently visible
        filtered_paths: DefaultDict[Tuple[int, int], List[Tuple[int, int]]] = defaultdict(list)
        for pos, path in paths.items():
            # Check if destination is visible and all path positions are known (seen or visible)
            if pos in visible_dict and all(step in seen or step in visible_dict for step in path):
                filtered_paths[pos] = path

        # Get entities at visible positions
        visible_entities: Dict[UUID, Tuple[int, int]] = {}
        for pos in visible_positions:
            entities = Entity.get_all_entities_at_position(pos)
            for entity in entities:
                visible_entities[entity.uuid] = pos

        # Build walkable dict from grid
        walkable = {pos: grid.is_walkable(pos[0], pos[1]) for pos in visible_positions}

        return visible_dict, filtered_paths, walkable, visible_entities

    def create_senses_copy_at_position(self, position: Tuple[int, int], max_distance: int = 10) -> 'Senses':
        """Create a copy of senses as if entity were at a different position."""
        senses = self.senses.model_copy(deep=True)
        senses.position = position
        visible_dict, filtered_paths, walkable, visible_entities = Entity.compute_senses_from_position(
            position, self.senses.seen, max_distance, entity_uuid=self.uuid
        )

        senses.update_senses(
            entities=visible_entities,
            visible=visible_dict,
            walkable=walkable,
            paths=filtered_paths
        )
        return senses

    def update_entity_senses(self, max_distance: int = 10):
        """
        Update the entity's senses using shadowcasting and pathfinding.

        This computes:
        - Visible cells within max_distance using shadowcast
        - Paths to reachable cells using dijkstra (excludes cells occupied by other entities)
        - Entities present in visible cells

        After updating, subscribes to visible cells so this entity
        receives SpatialChangeEvents when something changes in its FOV.

        Args:
            max_distance: Maximum view/movement distance (default 10)
        """
        visible_dict, filtered_paths, walkable, visible_entities = Entity.compute_senses_from_position(
            self.position, self.senses.seen, max_distance, entity_uuid=self.uuid
        )
        # Update the senses block
        self.senses.update_senses(
            entities=visible_entities,
            visible=visible_dict,
            walkable=walkable,
            paths=filtered_paths
        )
        # Subscribe to visible cells for spatial change notifications
        visible_cells = set(visible_dict.keys())
        get_map().subscribe_to_cells(self.uuid, visible_cells)

    @classmethod
    def update_all_entities_senses(cls, max_distance: int = 10):
        """Update the senses for all entities."""
        for entity in cls.get_all_entities():
            entity.update_entity_senses(max_distance)

    # =========================================================================
    # Action Registry System
    # =========================================================================

    def register_action(self, action: BaseAction) -> None:
        """Register an action template.

        Args:
            action: The action template to register (must have template=True)

        Raises:
            ValueError: If the action is not a template
        """
        if not action.template:
            raise ValueError("Can only register templates (template=True)")
        self.registered_actions.append(action)

    def unregister_action(self, name: str) -> None:
        """Remove an action template by name.

        Args:
            name: The name of the action template to remove
        """
        self.registered_actions = [a for a in self.registered_actions if a.name != name]

    def get_action_template(self, name: str) -> Optional[BaseAction]:
        """Get a registered action template by name.

        Args:
            name: The name of the action template

        Returns:
            The action template, or None if not found
        """
        return next((a for a in self.registered_actions if a.name == name), None)

    @property
    def entity_actions(self) -> List[BaseAction]:
        """Actions that target other entities (Attack)."""
        return [a for a in self.registered_actions if a.target_type == TargetType.ENTITY]

    @property
    def position_actions(self) -> List[BaseAction]:
        """Actions that target positions (Move)."""
        return [a for a in self.registered_actions if a.target_type == TargetType.POSITION]

    @property
    def self_actions(self) -> List[BaseAction]:
        """Actions that target self (Dash, Dodge, etc.)."""
        return [a for a in self.registered_actions if a.target_type == TargetType.SELF]

    def get_available_actions(self) -> AvailableActionsResult:
        """Get all available actions for this entity.

        Returns an AvailableActionsResult with all actions the entity can currently
        perform, grouped by target type. Each action includes valid targets with
        indices for easy selection (e.g., 'attack 0', 'move 3').

        This method is agnostic of specific action subclasses - it simply iterates
        over registered actions by target type and calls pre_validate() on each.
        """
        result = AvailableActionsResult(
            entity_uuid=self.uuid,
            remaining_movement=self.action_economy.movement.normalized_score
        )

        # SELF actions - validate once, no targets needed
        for template in self.self_actions:
            if template.pre_validate():
                template_name = template.name or "Unknown"
                result.self_actions.append(AvailableActionInfo(
                    template_name=template_name,
                    target_type=TargetType.SELF,
                    valid_targets=[AvailableTarget(index=0)],
                    can_afford=True,
                    display_name=template_name,
                    description=template.description,
                    cost_type=template.costs[0].cost_type if template.costs else "actions",
                    cost_amount=template.costs[0].cost if template.costs else 0
                ))

        # ENTITY actions - validate for each visible entity
        for template in self.entity_actions:
            valid_targets: List[AvailableTarget] = []
            idx = 0
            for target_uuid, target_pos in self.senses.entities.items():
                if target_uuid == self.uuid:
                    continue
                template.set_target_entity(target_uuid)
                if template.pre_validate():
                    target_entity = Entity.get(target_uuid)
                    valid_targets.append(AvailableTarget(
                        index=idx,
                        target_uuid=target_uuid,
                        target_name=target_entity.name if target_entity else None,
                        distance=self.senses.get_feet_distance(target_pos)
                    ))
                    idx += 1

            if valid_targets:
                template_name = template.name or "Unknown"

                # Extract weapon info for attacks
                weapon_name: Optional[str] = None
                weapon_slot_str: Optional[str] = None
                display_name = template_name

                # Check if template has weapon_slot (Attack actions)
                weapon_slot_attr = getattr(template, 'weapon_slot', None)
                if weapon_slot_attr is not None:
                    weapon_slot_str = weapon_slot_attr.value if hasattr(weapon_slot_attr, 'value') else str(weapon_slot_attr)
                    weapon = self.equipment._get_weapon_by_slot(weapon_slot_attr)
                    if weapon and hasattr(weapon, 'name'):
                        weapon_name = weapon.name
                        display_name = weapon_name  # Use weapon name as display name

                result.entity_actions.append(AvailableActionInfo(
                    template_name=template_name,
                    target_type=TargetType.ENTITY,
                    valid_targets=valid_targets,
                    can_afford=True,
                    display_name=display_name,
                    description=template.description,
                    cost_type=template.costs[0].cost_type if template.costs else "actions",
                    cost_amount=template.costs[0].cost if template.costs else 0,
                    weapon_slot=weapon_slot_str,
                    weapon_name=weapon_name
                ))

        # POSITION actions - validate for each reachable position
        for template in self.position_actions:
            valid_positions: List[AvailableTarget] = []
            idx = 0
            for pos, path in self.senses.paths.items():
                if pos == self.senses.position:
                    continue
                template.set_target_position(pos)
                if template.pre_validate():
                    path_cost = (len(path) - 1) * 5  # feet
                    valid_positions.append(AvailableTarget(
                        index=idx,
                        position=pos,
                        distance=self.senses.get_feet_distance(pos),
                        path_cost=path_cost
                    ))
                    idx += 1

            if valid_positions:
                template_name = template.name or "Unknown"
                result.position_actions.append(AvailableActionInfo(
                    template_name=template_name,
                    target_type=TargetType.POSITION,
                    valid_targets=valid_positions,
                    can_afford=True,
                    display_name=template_name,
                    description=f"{result.remaining_movement}ft remaining",
                    cost_type="movement",
                    cost_amount=0
                ))

        return result
