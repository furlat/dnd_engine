from __future__ import annotations
from typing import List, Union, TYPE_CHECKING, Optional, Dict, Tuple, Set, Callable, Any

if TYPE_CHECKING:
    from .statsblock import StatsBlock
from pydantic import BaseModel, Field, computed_field
from enum import Enum
from typing import List, Union
from dnd.docstrings import *
import uuid
import random
from dnd.contextual import ModifiableValue, AdvantageStatus, AdvantageTracker, ContextualEffects, ContextAwareBonus, ContextAwareCondition
from dnd.dnd_enums import ResistanceStatus,Ability,AutoHitStatus,AutoCritStatus, Skills, SensesType, ActionType, RechargeType, UsageType, DurationType, RangeType, TargetType, ShapeType, TargetRequirementType, DamageType
from dnd.logger import HealingTakenLog,DamageTakenLog,HealthSnapshot,DamageResistanceCalculation,DamageLog,SimpleRollLog,AdvantageLog,DiceRollLog, DamageRollLog, HealthLog, SkillCheckLog, SavingThrowLog, ModifiableValueLog
class RegistryHolder:
    _registry: Dict[str, 'RegistryHolder'] = {}
    _types: Set[type] = set()

    @classmethod
    def register(cls, instance: 'RegistryHolder'):
        cls._registry[instance.id] = instance
        cls._types.add(type(instance))

    @classmethod
    def get_instance(cls, instance_id: str):
        return cls._registry.get(instance_id)

    @classmethod
    def all_instances(cls, filter_type=True):
        if filter_type:
            return [instance for instance in cls._registry.values() if isinstance(instance, cls)]
        return list(cls._registry.values())

    @classmethod
    def all_instances_by_type(cls, type: type):
        return [instance for instance in cls._registry.values() if isinstance(instance, type)]

    @classmethod
    def all_types(cls, as_string=True):
        if as_string:
            return [type_name.__name__ for type_name in cls._types]
        return cls._types

class Dice(BaseModel):
    dice_count: int
    dice_value: int
    modifier: ModifiableValueLog
    
    def _roll_with_advantage(self,advantage_status:AdvantageStatus,is_critical: bool = False) -> SimpleRollLog: 
        if is_critical:
            num_dices = self.dice_count * 2
        else:
            num_dices = self.dice_count
        all_rolls = []

        if advantage_status == AdvantageStatus.NONE:
            for i in range(num_dices):
                all_rolls.append(random.randint(1,self.dice_value))
            chosen_rolls = all_rolls
        elif advantage_status == AdvantageStatus.ADVANTAGE:
            for i in range(num_dices):
                all_rolls.append(random.randint(1,self.dice_value),random.randint(1,self.dice_value))
            chosen_rolls = [max(roll) for roll in all_rolls]
        elif advantage_status == AdvantageStatus.DISADVANTAGE:
            for i in range(num_dices):
                all_rolls.append(random.randint(1,self.dice_value),random.randint(1,self.dice_value))
            chosen_rolls = [min(roll) for roll in all_rolls]
        
        return SimpleRollLog(
            base_dice_count=self.dice_count,
            dice_value=self.dice_value,
            advantage_status=advantage_status,
            critical_roll=is_critical,
            total_dice_count=num_dices,
            all_rolls=all_rolls,
            chosen_rolls=chosen_rolls,
        )

    def roll(self,is_critical: bool = False) -> Tuple[int, str, DiceRollLog]:

        base_roll_log= self._roll_with_advantage(self.modifier.advantage.advantage_status,is_critical)
        log = DiceRollLog(

            modifier=self.modifier,
            base_roll=base_roll_log,
            
        )
        return log
    



class Damage(BaseModel):
    dice: Dice
    type: DamageType

    def roll(self, is_critical: bool = False) -> Tuple[int, DamageRollLog]:
        dice_log = self.dice.roll(is_critical)
        
        damage_roll_log = DamageRollLog(
            damage_type=self.type,
            dice_roll=dice_log,
        )

        return damage_roll_log

class Health(BaseModel):
    hit_dice: Dice
    hit_point_bonus: ModifiableValue = Field(default_factory=lambda: ModifiableValue(base_value=0))
    temporary_hit_points: int = 0
    bonus_hit_points_source: Optional[str] = None
    bonus_hit_points: int = 0
    healing_bonus: ModifiableValue = Field(default_factory=lambda: ModifiableValue(base_value=0))
    current_hit_points: int = 0
    vulnerabilities: List[DamageType] = Field(default_factory=list)
    resistances: List[DamageType] = Field(default_factory=list)
    immunities: List[DamageType] = Field(default_factory=list)
    on_damage_conditions: List[Tuple[str, ContextAwareCondition]] = Field(default_factory=list)
    on_heal_conditions: List[Tuple[str, ContextAwareCondition]] = Field(default_factory=list)

    def __init__(self, **data):
        super().__init__(**data)
        if self.current_hit_points == 0:
            self.current_hit_points = self.max_hit_points
    
    @computed_field
    def total_hit_points(self) -> int:
        return self.current_hit_points + self.temporary_hit_points + self.bonus_hit_points


    @computed_field
    def max_hit_points(self) -> int:
        return max(1, self.hit_dice.expected_value() + self.hit_point_bonus.get_value(None))
    
    def _get_damage(self, damage_roll:DamageRollLog, owner, attacker, context) -> DamageResistanceCalculation:
        if damage_roll.damage_type in self.immunities:
            resistance_status= ResistanceStatus.IMMUNITY
        elif damage_roll.damage_type in self.vulnerabilities:
            resistance_status= ResistanceStatus.VULNERABILITY
        elif damage_roll.damage_type in self.resistances:
            resistance_status= ResistanceStatus.RESISTANCE
        else:
            resistance_status= ResistanceStatus.NONE
        
        return DamageResistanceCalculation(damage_roll = damage_roll, resistance_status = resistance_status)

    def get_health_snapshot(self) -> HealthSnapshot:
        return HealthSnapshot(
            current_hp=self.current_hit_points,
            max_hp=self.max_hit_points,
            temp_hp=self.temporary_hit_points,
            bonus_hp=self.bonus_hit_points,
        )

    def take_damage(self, damage: DamageLog, owner: 'StatsBlock', attacker: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None) -> DamageTakenLog:
        if isinstance(damage,Damage):
            damage = [damage]

        health_before = self.get_health_snapshot()
        damage_calculations = []
        for damage_roll in damage.damage_rolls:
            damage_calculations.append(self._get_damage(damage_roll, owner, attacker, context))

        total_damage = sum([getattr(calculation,"total_damage_taken") for calculation in damage_calculations])


        if self.temporary_hit_points > 0:
            absorbed_thp = min(self.temporary_hit_points, total_damage)
            self.temporary_hit_points -= absorbed_thp
            hp_damage = total_damage- absorbed_thp

        # Then apply to bonus hit points
        if self.bonus_hit_points > 0:
            absorbed_bhp = min(self.bonus_hit_points, hp_damage)
            self.bonus_hit_points -= absorbed_bhp
            hp_damage -= absorbed_bhp
        # Finally, apply to current hit points
        self.current_hit_points = max(0, self.current_hit_points - hp_damage)

        # Log the damage taken
        return  DamageTakenLog(
            health_before=health_before,
            health_after=self.get_health_snapshot(),
            damage_calculations=damage_calculations,
            hp_damage = hp_damage,
            temp_hp_damage=absorbed_thp,
            bonus_hp_damage=absorbed_bhp,
            source_entity_id=attacker.id if attacker else None,
            target_entity_id=owner.id if owner else None,
        )


    def heal(self, healing: int, owner: 'StatsBlock', healer: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None) -> HealingTakenLog:
        healing_bonus = self.healing_bonus.get_value(owner, healer, context)
        total_healing = healing + healing_bonus
        health_before = self.get_health_snapshot()
        old_hp = self.current_hit_points
        self.current_hit_points = min(self.max_hit_points, self.current_hit_points + total_healing)
        actual_healing = self.current_hit_points - old_hp

        # Trigger on-heal conditions
        for _, condition in self.on_heal_conditions:
            condition(owner, healer, context)

        # Log the healing received
        return HealingTakenLog(
            health_before=health_before,
            health_after=self.get_health_snapshot(),
            total_healing=actual_healing,
            source_entity_id=healer.id if healer else None,
            target_entity_id=owner.id if owner else None,
        )



    def add_temporary_hit_points(self, amount: int):
        self.temporary_hit_points = max(self.temporary_hit_points, amount)

    def set_bonus_hit_points(self, source: str, amount: int):
        if self.bonus_hit_points_source != source:
            self.bonus_hit_points = amount
            self.bonus_hit_points_source = source

    def add_on_damage_condition(self, source: str, condition: ContextAwareCondition):
        self.on_damage_conditions.append((source, condition))

    def add_on_heal_condition(self, source: str, condition: ContextAwareCondition):
        self.on_heal_conditions.append((source, condition))

    def remove_condition(self, source: str):
        self.on_damage_conditions = [c for c in self.on_damage_conditions if c[0] != source]
        self.on_heal_conditions = [c for c in self.on_heal_conditions if c[0] != source]

class Speed(BaseModel):
    walk: ModifiableValue
    fly: ModifiableValue = Field(default_factory=lambda: ModifiableValue(base_value=0))
    swim: ModifiableValue = Field(default_factory=lambda: ModifiableValue(base_value=0))
    burrow: ModifiableValue = Field(default_factory=lambda: ModifiableValue(base_value=0))
    climb: ModifiableValue = Field(default_factory=lambda: ModifiableValue(base_value=0))

    def get_speed(self, speed_type: str, stats_block: 'StatsBlock', target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None) -> int:
        return getattr(self, speed_type).get_value(stats_block, target, context)

    def add_static_modifier(self, speed_type: str, source: str, value: int):
        getattr(self, speed_type).add_static_modifier(source, value)

    def remove_static_modifier(self, speed_type: str, source: str):
        getattr(self, speed_type).remove_static_modifier(source)

    def add_bonus(self, speed_type: str, source: str, bonus: ContextAwareBonus):
        getattr(self, speed_type).add_bonus(source, bonus)

    def add_max_constraint(self, speed_type: str, source: str, constraint: ContextAwareBonus):
        getattr(self, speed_type).add_max_constraint(source, constraint)

    def remove_effect(self, speed_type: str, source: str):
        getattr(self, speed_type).remove_effect(source)

    def set_max_speed_to_zero(self, source: str):
        for speed_type in ['walk', 'fly', 'swim', 'burrow', 'climb']:
            self.add_max_constraint(speed_type, source, lambda stats_block, target, context: 0)

    def reset_max_speed(self, source: str):
        for speed_type in ['walk', 'fly', 'swim', 'burrow', 'climb']:
            self.remove_effect(speed_type, source)



class AbilityScore(BaseModel):
    ability: Ability
    score: ModifiableValue = Field(default_factory=lambda: ModifiableValue(base_value=10))

    def get_score(self, stats_block: 'StatsBlock', target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None) -> int:
        return self.score.get_value(stats_block, target, context)

    def get_modifier(self, stats_block: 'StatsBlock', target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None) -> int:
        return (self.get_score(stats_block, target, context) - 10) // 2

    def get_advantage_status(self, stats_block: 'StatsBlock', target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None) -> AdvantageStatus:
        return self.score.get_advantage_status(stats_block, target, context)
    
    def perform_ability_check(self, stats_block: 'StatsBlock', dc: int, target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None) -> bool:
        if self.score.is_auto_fail(stats_block, target, context):
            return False
        if self.score.is_auto_success(stats_block, target, context):
            return True

        modifier = self.get_modifier(stats_block, target, context)
        advantage_status = self.get_advantage_status(stats_block, target, context)
        
        dice = Dice(dice_count=1, dice_value=20, modifier=modifier, advantage_status=advantage_status)
        roll, _ = dice.roll_with_advantage()
        return roll >= dc

    def add_bonus(self, source: str, bonus: ContextAwareBonus):
        self.score.add_bonus(source, bonus)

    def add_advantage_condition(self, source: str, condition: ContextAwareCondition):
        self.score.add_advantage_condition(source, condition)

    def add_disadvantage_condition(self, source: str, condition: ContextAwareCondition):
        self.score.add_disadvantage_condition(source, condition)

    def add_auto_fail_condition(self, source: str, condition: ContextAwareCondition):
        self.score.add_auto_fail_self_condition(source, condition)

    def add_auto_success_condition(self, source: str, condition: ContextAwareCondition):
        self.score.add_auto_success_self_condition(source, condition)

    def remove_effect(self, source: str):
        self.score.remove_effect(source)

class AbilityScores(BaseModel):
    strength: AbilityScore = Field(default_factory=lambda: AbilityScore(ability=Ability.STR, score=ModifiableValue(base_value=10)))
    dexterity: AbilityScore = Field(default_factory=lambda: AbilityScore(ability=Ability.DEX, score=ModifiableValue(base_value=10)))
    constitution: AbilityScore = Field(default_factory=lambda: AbilityScore(ability=Ability.CON, score=ModifiableValue(base_value=10)))
    intelligence: AbilityScore = Field(default_factory=lambda: AbilityScore(ability=Ability.INT, score=ModifiableValue(base_value=10)))
    wisdom: AbilityScore = Field(default_factory=lambda: AbilityScore(ability=Ability.WIS, score=ModifiableValue(base_value=10)))
    charisma: AbilityScore = Field(default_factory=lambda: AbilityScore(ability=Ability.CHA, score=ModifiableValue(base_value=10)))
    proficiency_bonus: ModifiableValue = Field(default_factory=lambda: ModifiableValue(base_value=2))
    
    def get_ability(self, ability: Ability) -> AbilityScore:
        return getattr(self, ability.value.lower())

    def get_ability_modifier(self, ability: Ability, stats_block: 'StatsBlock', target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None) -> int:
        ability_score = self.get_ability(ability)
        return ability_score.get_modifier(stats_block, target, context)

    def get_proficiency_bonus(self, ability: Ability, stats_block: 'StatsBlock', target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None) -> int:
        return self.proficiency_bonus.get_value(stats_block, target, context)

    def perform_ability_check(self, ability: Ability, stats_block: 'StatsBlock', dc: int, target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None) -> bool:
        ability_score = self.get_ability(ability)
        return ability_score.perform_ability_check(stats_block, dc, target, context)

ABILITY_TO_SKILLS = {
    Ability.STR: [Skills.ATHLETICS],
    Ability.DEX: [Skills.ACROBATICS, Skills.SLEIGHT_OF_HAND, Skills.STEALTH],
    Ability.CON: [],
    Ability.INT: [Skills.ARCANA, Skills.HISTORY, Skills.INVESTIGATION, Skills.NATURE, Skills.RELIGION],
    Ability.WIS: [Skills.ANIMAL_HANDLING, Skills.INSIGHT, Skills.MEDICINE, Skills.PERCEPTION, Skills.SURVIVAL],
    Ability.CHA: [Skills.DECEPTION, Skills.INTIMIDATION, Skills.PERFORMANCE, Skills.PERSUASION]
}

class Skill(BaseModel):
    ability: Ability
    skill: Skills
    proficient: bool = False
    expertise: bool = False
    bonus: ModifiableValue = Field(default_factory=lambda: ModifiableValue(base_value=0))

    def get_bonus(self, stats_block: 'StatsBlock', target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None) -> int:
        ability_bonus = stats_block.ability_scores.get_ability_modifier(self.ability, stats_block, target, context)
        proficiency_bonus = stats_block.ability_scores.get_proficiency_bonus(self.ability, stats_block, target, context)
        if self.expertise:
            proficiency_bonus *= 2
        elif not self.proficient:
            proficiency_bonus = 0
        self.bonus.base_value = ability_bonus + proficiency_bonus
        return self.bonus.get_value(stats_block, target, context)

    def get_advantage_status(self, stats_block: 'StatsBlock', target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None) -> AdvantageStatus:
        return self.bonus.get_advantage_status(stats_block, target, context)

    def perform_check(self, stats_block: 'StatsBlock', dc: int, target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None, return_log: bool = False) -> Union[bool, SkillCheckLog]:
        print(f"Performing {self.ability.value} skill check")
        
        if self.bonus.is_auto_fail(stats_block, target, context):
            print(f"Auto-fail condition met for {self.skill.value} check")
            log = SkillCheckLog(
                skill=self.skill,
                ability=self.ability,
                dc=dc,
                source_id=stats_block.id,
                target_id=target.id if target else None,
                roll_log=None,
                roll=1,
                total=1,
                bonus=0,
                advantage_status=AdvantageStatus.NONE,
                success=False,
                auto_fail=True,
            )
            return log if return_log else False
        
        if self.bonus.is_auto_success(stats_block, target, context):
            print(f"Auto-success condition met for {self.skill.value} check")
            log = SkillCheckLog(
                skill=self.skill,
                ability=self.ability,
                source_id=stats_block.id,
                target_id=target.id if target else None,
                roll_log=None,
                dc=dc,
                roll=20,
                total=20,
                bonus=0,
                advantage_status=AdvantageStatus.NONE,
                success=True,
                auto_success=True,

            )
            return log if return_log else True

        bonus = self.get_bonus(stats_block, target, context)
        
        advantage_tracker = AdvantageTracker()
        self.bonus.self_effects.apply_advantage_disadvantage(stats_block, target, advantage_tracker, context)
        if target:
            target_skill = target.skills.get_skill(self.skill)
            target_skill.bonus.target_effects.apply_advantage_disadvantage(target, stats_block, advantage_tracker, context)
        
        advantage_status = advantage_tracker.status
        
        print(f"Bonus: {bonus}, Advantage status: {advantage_status}")
        dice = Dice(dice_count=1, dice_value=20, modifier=bonus, advantage_status=advantage_status)
        roll, _, roll_log = dice.roll_with_advantage()
        total = roll + bonus
        success = total >= dc
        print(f"Roll: {roll}, Total: {total}, DC: {dc}")

        log = SkillCheckLog(
            skill=self.skill,
            ability=self.ability,
            dc=dc,
            source_id=stats_block.id,
            target_id=target.id if target else None,
            roll_log=roll_log,
            roll=roll,
            
            total=total,
            bonus=bonus,
            advantage_status=advantage_status,
            success=success,

        )
        return log if return_log else success

    
    # Self effects
    def add_self_bonus(self, source: str, bonus: ContextAwareBonus):
        self.bonus.self_effects.add_bonus(source, bonus)

    def add_self_advantage_condition(self, source: str, condition: ContextAwareCondition):
        self.bonus.self_effects.add_advantage_condition(source, condition)

    def add_self_disadvantage_condition(self, source: str, condition: ContextAwareCondition):
        self.bonus.self_effects.add_disadvantage_condition(source, condition)

    def add_self_auto_fail_condition(self, source: str, condition: ContextAwareCondition):
        self.bonus.self_effects.add_auto_fail_self_condition(source, condition)

    def add_self_auto_success_condition(self, source: str, condition: ContextAwareCondition):
        self.bonus.self_effects.add_auto_success_self_condition(source, condition)

    # Target effects
    def add_target_bonus(self, source: str, bonus: ContextAwareBonus):
        self.bonus.target_effects.add_bonus(source, bonus)

    def add_target_advantage_condition(self, source: str, condition: ContextAwareCondition):
        self.bonus.target_effects.add_advantage_condition(source, condition)

    def add_target_disadvantage_condition(self, source: str, condition: ContextAwareCondition):
        self.bonus.target_effects.add_disadvantage_condition(source, condition)

    def add_target_auto_fail_condition(self, source: str, condition: ContextAwareCondition):
        self.bonus.target_effects.add_auto_fail_self_condition(source, condition)

    def add_target_auto_success_condition(self, source: str, condition: ContextAwareCondition):
        self.bonus.target_effects.add_auto_success_self_condition(source, condition)

    # Remove effects
    def remove_self_effect(self, source: str):
        self.bonus.self_effects.remove_effect(source)

    def remove_target_effect(self, source: str):
        self.bonus.target_effects.remove_effect(source)

    def remove_all_effects(self, source: str):
        self.remove_self_effect(source)
        self.remove_target_effect(source)

class SkillSet(BaseModel):
    acrobatics: Skill = Field(default_factory=lambda: Skill(ability=Ability.DEX, skill=Skills.ACROBATICS))
    animal_handling: Skill = Field(default_factory=lambda: Skill(ability=Ability.WIS, skill=Skills.ANIMAL_HANDLING))
    arcana: Skill = Field(default_factory=lambda: Skill(ability=Ability.INT, skill=Skills.ARCANA))
    athletics: Skill = Field(default_factory=lambda: Skill(ability=Ability.STR, skill=Skills.ATHLETICS))
    deception: Skill = Field(default_factory=lambda: Skill(ability=Ability.CHA, skill=Skills.DECEPTION))
    history: Skill = Field(default_factory=lambda: Skill(ability=Ability.INT, skill=Skills.HISTORY))
    insight: Skill = Field(default_factory=lambda: Skill(ability=Ability.WIS, skill=Skills.INSIGHT))
    intimidation: Skill = Field(default_factory=lambda: Skill(ability=Ability.CHA, skill=Skills.INTIMIDATION))
    investigation: Skill = Field(default_factory=lambda: Skill(ability=Ability.INT, skill=Skills.INVESTIGATION))
    medicine: Skill = Field(default_factory=lambda: Skill(ability=Ability.WIS, skill=Skills.MEDICINE))
    nature: Skill = Field(default_factory=lambda: Skill(ability=Ability.INT, skill=Skills.NATURE))
    perception: Skill = Field(default_factory=lambda: Skill(ability=Ability.WIS, skill=Skills.PERCEPTION))
    performance: Skill = Field(default_factory=lambda: Skill(ability=Ability.CHA, skill=Skills.PERFORMANCE))
    persuasion: Skill = Field(default_factory=lambda: Skill(ability=Ability.CHA, skill=Skills.PERSUASION))
    religion: Skill = Field(default_factory=lambda: Skill(ability=Ability.INT, skill=Skills.RELIGION))
    sleight_of_hand: Skill = Field(default_factory=lambda: Skill(ability=Ability.DEX, skill=Skills.SLEIGHT_OF_HAND))
    stealth: Skill = Field(default_factory=lambda: Skill(ability=Ability.DEX, skill=Skills.STEALTH))
    survival: Skill = Field(default_factory=lambda: Skill(ability=Ability.WIS, skill=Skills.SURVIVAL))
    proficiencies: Set[Skills] = Field(default_factory=set)
    expertise: Set[Skills] = Field(default_factory=set)

    def get_skill(self, skill: Skills) -> Skill:
        attribute_name = skill.value.lower().replace(' ', '_')
        return getattr(self, attribute_name)
    
    def set_proficiency(self, skill: Skills):
        self.proficiencies.add(skill)
        self.get_skill(skill).proficient = True

    def set_expertise(self, skill: Skills):
        self.expertise.add(skill)
        self.get_skill(skill).expertise = True
    
    def add_effect_to_all_skills(self, effect_type: str, source: str, effect: Union[ContextAwareBonus, ContextAwareCondition]):
        for skill in Skills:
            skill_obj = self.get_skill(skill)
            getattr(skill_obj, f"add_{effect_type}")(source, effect)

    def remove_effect_from_all_skills(self, effect_type: str, source: str):
        for skill in Skills:
            skill_obj = self.get_skill(skill)
            getattr(skill_obj, f"remove_{effect_type}_effect")(source)

    def remove_all_effects_from_all_skills(self, source: str):
        for skill in Skills:
            skill_obj = self.get_skill(skill)
            skill_obj.remove_all_effects(source)

    def perform_skill_check(self, skill: Skills, stats_block: 'StatsBlock', dc: int, target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None, return_log: bool = False) -> Union[bool, SkillCheckLog]:
        return self.get_skill(skill).perform_check(stats_block, dc, target, context, return_log)




class SavingThrow(BaseModel):
    ability: Ability
    proficient: bool
    bonus: ModifiableValue = Field(default_factory=lambda: ModifiableValue(base_value=0))

    def get_bonus(self, stats_block: 'StatsBlock', target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None) -> int:
        ability_bonus = stats_block.ability_scores.get_ability_modifier(self.ability, stats_block, target, context)
        proficiency_bonus = stats_block.ability_scores.proficiency_bonus.get_value(stats_block, target, context) if self.proficient else 0
        return ability_bonus + proficiency_bonus
    
    def get_advantage_status(self, stats_block: 'StatsBlock', target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None) -> AdvantageStatus:
        return self.bonus.get_advantage_status(stats_block, target, context)
    
    def perform_save(self, stats_block: 'StatsBlock', dc: int, target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None, return_log: bool = False) -> Union[bool, SavingThrowLog]:
        if self.bonus.is_auto_fail(stats_block, target, context):
            print(f"Auto-fail condition met for {self.ability.value} saving throw")
            log = SavingThrowLog(
                ability=self.ability,
                dc=dc,
                source_id=stats_block.id,
                target_id=target.id if target else None,
                roll_log=None,
                roll=1,
                total=1,
                bonus=0,
                advantage_status=AdvantageStatus.NONE,
                success=False,
                auto_fail=True,

            )
            return log if return_log else False
        
        if self.bonus.is_auto_success(stats_block, target, context):
            print(f"Auto-success condition met for {self.ability.value} saving throw")
            log = SavingThrowLog(
                ability=self.ability,
                dc=dc,
                source_id=stats_block.id,
                target_id=target.id if target else None,
                roll_log=None,
                roll=20,
                total=20,
                bonus=0,
                advantage_status=AdvantageStatus.NONE,
                success=True,
                auto_success=True,

            )
            return log if return_log else True

        bonus = self.get_bonus(stats_block, target, context)
        advantage_tracker = AdvantageTracker()
        self.bonus.self_effects.apply_advantage_disadvantage(stats_block, target, advantage_tracker, context)
        if target:
            target_save = target.saving_throws.get_ability(self.ability)
            target_save.bonus.target_effects.apply_advantage_disadvantage(target, stats_block, advantage_tracker, context)
        
        advantage_status = advantage_tracker.status

        dice = Dice(dice_count=1, dice_value=20, modifier=bonus, advantage_status=advantage_status)
        roll, _, roll_log = dice.roll_with_advantage()
        total = roll + bonus
        success = total >= dc
        print(f"Saving Throw: {self.ability.value}, Roll: {roll}, Total: {total}, DC: {dc}")

        log = SavingThrowLog(
            ability=self.ability,
            dc=dc,
            source_id=stats_block.id,
            target_id=target.id if target else None,
            roll_log=roll_log,
            roll=roll,
            total=total,
            bonus=bonus,
            advantage_status=advantage_status,
            success=success,

        )
        return log if return_log else success

    def add_bonus(self, source: str, bonus: ContextAwareBonus):
        self.bonus.add_bonus(source, bonus)

    def add_advantage_condition(self, source: str, condition: ContextAwareCondition):
        self.bonus.add_advantage_condition(source, condition)

    def add_disadvantage_condition(self, source: str, condition: ContextAwareCondition):
        self.bonus.add_disadvantage_condition(source, condition)

    def add_auto_fail_condition(self, source: str, condition: ContextAwareCondition):
        self.bonus.add_auto_fail_self_condition(source, condition)

    def add_auto_success_condition(self, source: str, condition: ContextAwareCondition):
        self.bonus.add_auto_success_self_condition(source, condition)

    def remove_effect(self, source: str):
        self.bonus.remove_effect(source)


class SavingThrows(BaseModel):
    strength: SavingThrow = Field(default_factory=lambda: SavingThrow(ability=Ability.STR, proficient=False))
    dexterity: SavingThrow = Field(default_factory=lambda: SavingThrow(ability=Ability.DEX, proficient=False))
    constitution: SavingThrow = Field(default_factory=lambda: SavingThrow(ability=Ability.CON, proficient=False))
    intelligence: SavingThrow = Field(default_factory=lambda: SavingThrow(ability=Ability.INT, proficient=False))
    wisdom: SavingThrow = Field(default_factory=lambda: SavingThrow(ability=Ability.WIS, proficient=False))
    charisma: SavingThrow = Field(default_factory=lambda: SavingThrow(ability=Ability.CHA, proficient=False))

    def get_ability(self, ability: Ability) -> SavingThrow:
        return getattr(self, ability.value.lower())

    def set_proficiency(self, ability: Ability, value: bool = True):
        savingthrow = self.get_ability(ability)
        savingthrow.proficient = value
    
    def add_auto_fail_condition(self, ability: Ability, source: str, condition: ContextAwareCondition):
        saving_throw = self.get_ability(ability)
        saving_throw.add_auto_fail_condition(source, condition)

    def add_auto_success_condition(self, ability: Ability, source: str, condition: ContextAwareCondition):
        saving_throw = self.get_ability(ability)
        saving_throw.add_auto_success_condition(source, condition)

    def remove_effect(self, ability: Ability, source: str):
        saving_throw = self.get_ability(ability)
        saving_throw.remove_effect(source)

    def perform_save(self, ability: Ability, stats_block: 'StatsBlock', dc: int, target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None, return_log: bool = False) -> Union[bool, SavingThrowLog]:
        return self.get_ability(ability).perform_save(stats_block, dc, target, context, return_log)

class BaseSpatial(BaseModel):
    battlemap_id: str
    origin: Tuple[int, int]

    def get_entities_at(self, position: Tuple[int, int]) -> List[str]:
        battlemap = RegistryHolder.get_instance(self.battlemap_id)
        return list(battlemap.positions.get(position, set()))

    def filter_positions(self, condition: Callable[[Tuple[int, int]], bool]) -> List[Tuple[int, int]]:
        raise NotImplementedError("Subclasses must implement this method")

    def get_entities(self, positions: List[Tuple[int, int]]) -> List[str]:
        battlemap = RegistryHolder.get_instance(self.battlemap_id)
        return [entity_id for pos in positions for entity_id in battlemap.positions.get(pos, set())]
    
class FOV(BaseSpatial):
    visible_tiles: Set[Tuple[int, int]] = Field(default_factory=set)

    @staticmethod
    def bresenham(start: Tuple[int, int], end: Tuple[int, int]) -> List[Tuple[int, int]]:
        x0, y0 = start
        x1, y1 = end
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy

        ray = []
        while True:
            ray.append((x0, y0))
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x0 += sx
            if e2 < dx:
                err += dx
                y0 += sy

        return ray

    def get_ray_to(self, position: Tuple[int, int]) -> Optional[List[Tuple[int, int]]]:
        if position in self.visible_tiles:
            return self.bresenham(self.origin, position)
        return None

    def get_all_rays(self) -> Dict[Tuple[int, int], List[Tuple[int, int]]]:
        return {pos: self.bresenham(self.origin, pos) for pos in self.visible_tiles}

    def is_visible(self, position: Tuple[int, int]) -> bool:
        return position in self.visible_tiles

    def filter_positions(self, condition: Callable[[Tuple[int, int]], bool]) -> List[Tuple[int, int]]:
        return [pos for pos in self.visible_tiles if condition(pos)]

    def get_visible_positions(self) -> List[Tuple[int, int]]:
        return list(self.visible_tiles)

    def get_visible_entities(self) -> List[str]:
        return self.get_entities(self.get_visible_positions())

    def get_positions_in_range(self, range: int) -> List[Tuple[int, int]]:
        return self.filter_positions(lambda pos: 
            ((pos[0] - self.origin[0])**2 + (pos[1] - self.origin[1])**2)**0.5 * 5 <= range
        )

    def get_entities_in_range(self, range: int) -> List[str]:
        return self.get_entities(self.get_positions_in_range(range))
    
class DistanceMatrix(BaseSpatial):
    distances: Dict[Tuple[int, int], int] = Field(default_factory=dict)

    def get_distance(self, position: Tuple[int, int]) -> Optional[int]:
        return self.distances.get(position)

    def filter_positions(self, condition: Callable[[Tuple[int, int]], bool]) -> List[Tuple[int, int]]:
        return [pos for pos, distance in self.distances.items() if condition(pos)]

    def get_positions_within_distance(self, max_distance: int) -> List[Tuple[int, int]]:
        return self.filter_positions(lambda pos: self.distances[pos] <= max_distance)

    def get_entities_within_distance(self, max_distance: int) -> List[str]:
        return self.get_entities(self.get_positions_within_distance(max_distance))

    def get_adjacent_positions(self) -> List[Tuple[int, int]]:
        return self.get_positions_within_distance(1)

    def get_adjacent_entities(self) -> List[str]:
        return self.get_entities(self.get_adjacent_positions())

class Path(BaseSpatial):
    path: List[Tuple[int, int]]
    
    def get_path_length(self) -> int:
        return len(self.path) - 1  # Subtract 1 because the start position is included

    def is_valid_movement(self, movement_budget: int) -> bool:
        return self.get_path_length() <= movement_budget

    def get_positions_on_path(self) -> List[Tuple[int, int]]:
        return self.path

    def get_entities_on_path(self) -> List[str]:
        return self.get_entities(self.get_positions_on_path())
    
class Paths(BaseSpatial):
    paths: Dict[Tuple[int, int], List[Tuple[int, int]]] = Field(default_factory=dict)

    def get_path_to(self, destination: Tuple[int, int]) -> Optional[List[Tuple[int, int]]]:
        return self.paths.get(destination)

    def filter_positions(self, condition: Callable[[Tuple[int, int]], bool]) -> List[Tuple[int, int]]:
        return [pos for pos in self.paths.keys() if condition(pos)]

    def get_reachable_positions(self, movement_budget: int) -> List[Tuple[int, int]]:
        return self.filter_positions(lambda pos: len(self.paths[pos]) - 1 <= movement_budget)

    def get_reachable_entities(self, movement_budget: int) -> List[str]:
        return self.get_entities(self.get_reachable_positions(movement_budget))

    def get_shortest_path_to_position(self, position: Tuple[int, int]) -> Optional[List[Tuple[int, int]]]:
        return self.get_path_to(position)
    

class Sense(BaseModel):
    type: SensesType
    range: int

class Sensory(BaseModel):
    senses: List[Sense] = Field(default_factory=list)
    battlemap_id: Union[str,None] = Field(default=None)
    origin: Union[Tuple[int, int],None] = Field(default=None)
    distance_matrix: Optional[DistanceMatrix] = None
    fov: Optional[FOV] = None
    paths: Optional[Paths] = None

    def get_ray_to(self, destination: Tuple[int, int]) -> Optional[List[Tuple[int, int]]]:
        if self.fov:
            return self.fov.get_ray_to(destination)
        return None

    def get_all_rays(self) -> Dict[Tuple[int, int], List[Tuple[int, int]]]:
        if self.fov:
            return self.fov.get_all_rays()
        return {}
    
    def update_battlemap(self, battlemap_id: str):
        self.battlemap_id = battlemap_id

    def update_distance_matrix(self, distances: Dict[Tuple[int, int], int]):
        self.distance_matrix = DistanceMatrix(
            battlemap_id=self.battlemap_id,
            origin=self.origin,
            distances=distances
        )

    def update_fov(self, visible_tiles: Set[Tuple[int, int]]):
        self.fov = FOV(
            battlemap_id=self.battlemap_id,
            origin=self.origin,
            visible_tiles=visible_tiles
        )

    def update_paths(self, paths: Dict[Tuple[int, int], List[Tuple[int, int]]]):
        self.paths = Paths(
            battlemap_id=self.battlemap_id,
            origin=self.origin,
            paths=paths
        )

    def get_distance(self, position: Tuple[int, int]) -> Optional[int]:
        if self.distance_matrix:
            return self.distance_matrix.get_distance(position)
        return None

    def is_visible(self, position: Tuple[int, int]) -> bool:
        if self.fov:
            return self.fov.is_visible(position)
        return False

    def get_path_to(self, destination: Tuple[int, int]) -> Optional[List[Tuple[int, int]]]:
        if self.paths:
            return self.paths.get_path_to(destination)
        return None

    def get_entities_within_distance(self, max_distance: int) -> List[str]:
        if self.distance_matrix:
            return self.distance_matrix.get_entities_within_distance(max_distance)
        return []

    def get_visible_entities(self) -> List[str]:
        if self.fov:
            return self.fov.get_visible_entities()
        return []

    def get_reachable_entities(self, movement_budget: int) -> List[str]:
        if self.paths:
            return self.paths.get_reachable_entities(movement_budget)
        return []

    def get_entities_in_sense_range(self, sense_type: SensesType) -> List[str]:
        sense = next((s for s in self.senses if s.type == sense_type), None)
        if sense and self.distance_matrix:
            return self.distance_matrix.get_entities_within_distance(sense.range)
        return []

    def update_origin(self, new_origin: Tuple[int, int]):
        self.origin = new_origin
        if self.distance_matrix:
            self.distance_matrix.origin = new_origin
        if self.fov:
            self.fov.origin = new_origin
        if self.paths:
            self.paths.origin = new_origin

    def clear_spatial_data(self):
        self.distance_matrix = None
        self.fov = None
        self.paths = None

class ActionEconomy(BaseModel):
    actions: ModifiableValue = Field(default_factory=lambda: ModifiableValue(base_value=1))
    bonus_actions: ModifiableValue = Field(default_factory=lambda: ModifiableValue(base_value=1))
    reactions: ModifiableValue = Field(default_factory=lambda: ModifiableValue(base_value=1))
    movement: ModifiableValue = Field(default_factory=lambda: ModifiableValue(base_value=30))


    def reset(self):
        for attr in ['actions', 'bonus_actions', 'reactions', 'movement']:
            getattr(self, attr).base_value = getattr(self, attr).base_value

    def set_max_actions(self, source: str, value: int):
        self.actions.add_max_constraint(source, lambda stats_block, target, context: value)

    def set_max_bonus_actions(self, source: str, value: int):
        self.bonus_actions.add_max_constraint(source, lambda stats_block, target, context: value)

    def set_max_reactions(self, source: str, value: int):
        self.reactions.add_max_constraint(source, lambda stats_block, target, context: value)

    def reset_max_actions(self, source: str):
        self.actions.remove_effect(source)

    def reset_max_bonus_actions(self, source: str):
        self.bonus_actions.remove_effect(source)

    def reset_max_reactions(self, source: str):
        self.reactions.remove_effect(source)

    def modify_movement(self, source: str, value: int):
        self.movement.add_static_modifier(source, value)

    def remove_movement_modifier(self, source: str):
        self.movement.remove_static_modifier(source)