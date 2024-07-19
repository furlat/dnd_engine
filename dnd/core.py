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
from dnd.contextual import ModifiableValue, AdvantageStatus, AdvantageTracker, BaseValue, ContextAwareBonus, ContextAwareCondition
from dnd.dnd_enums import RollOutcome,HitReason, CriticalReason,ResistanceStatus,Ability,AutoHitStatus,CriticalStatus, Skills, SensesType, ActionType, RechargeType, UsageType, DurationType, RangeType, TargetType, ShapeType, TargetRequirementType, DamageType
from dnd.dnd_enums import UnarmoredAc, ArmorType
from dnd.logger import ValueOut, SimpleRollOut, TargetRollOut, DamageRollOut, SkillBonusOut, SkillRollOut, CrossSkillRollOut, SavingThrowBonusOut,SavingThrowRollOut, DamageResistanceOut
from dnd.logger import HealthSnapshot, DamageTakenLog, HealingTakenLog
from dnd.spatial import DistanceMatrix, FOV, Path,Paths


    
class BaseRoll(BaseModel):
    dice_count: int
    dice_value: int

    def _single_roll(self) -> int:
        return random.randint(1, self.dice_value)
    
    def roll(self,advantage_status:AdvantageStatus) -> SimpleRollOut:
        all_rolls = []

        if advantage_status == AdvantageStatus.NONE:
            for i in range(self.dice_count):
                all_rolls.append(random.randint(1,self.dice_value))
            chosen_rolls = all_rolls
        elif advantage_status == AdvantageStatus.ADVANTAGE:
            for i in range(self.dice_count):
                all_rolls.append(random.randint(1,self.dice_value),random.randint(1,self.dice_value))
            chosen_rolls = [max(roll) for roll in all_rolls]
        elif advantage_status == AdvantageStatus.DISADVANTAGE:
            for i in range(self.dice_count):
                all_rolls.append(random.randint(1,self.dice_value),random.randint(1,self.dice_value))
            chosen_rolls = [min(roll) for roll in all_rolls]

        return SimpleRollOut(
            dice_count=self.dice_count,
            dice_value=self.dice_value,
            advantage_status=advantage_status,
            all_rolls=all_rolls,
            chosen_rolls=chosen_rolls,
        )
    
class TargetRoll(BaseModel):
    value: ValueOut

    def _roll(self) -> SimpleRollOut:
        return  BaseRoll(dice_count=1, dice_value=20).roll(self.value.advantage_tracker.status)
    
    def roll(self, target: int = 0) -> TargetRollOut:
        base_roll_out = self._roll()
        bonus = self.value.total_bonus
        total = base_roll_out.result + bonus
        hit_target = total >= target
        nat20 = base_roll_out.result == 20
        nat1 = base_roll_out.result == 1

        auto_miss = self.value.auto_hit_tracker.status == AutoHitStatus.AUTOMISS
        auto_hit = self.value.auto_hit_tracker.status == AutoHitStatus.AUTOHIT
        auto_crit = self.value.critical_tracker.status == CriticalStatus.AUTOCRIT
        
        critical_reason = None
        #first check we do not have automiss or autohit
        if auto_miss:
            outcome = RollOutcome.MISS
            reason = HitReason.AUTOMISS
        elif not auto_hit and not hit_target:
            outcome = RollOutcome.MISS
            reason = HitReason.NORMAL
        elif not auto_hit and hit_target and nat1:
            outcome = RollOutcome.MISS
            reason = HitReason.CRITICAL
            critical_reason = CriticalReason.NORMAL
          
        elif auto_hit and not auto_crit and not nat20:
            outcome = RollOutcome.HIT
            reason = HitReason.AUTOHIT
        elif auto_hit and not auto_crit and  nat20:
            outcome = RollOutcome.CRIT
            reason = HitReason.AUTOHIT
            critical_reason = CriticalReason.NORMAL
        elif auto_hit and auto_crit:
            outcome = RollOutcome.CRIT
            reason = HitReason.AUTOHIT
            critical_reason = CriticalReason.AUTO
        elif not auto_hit and hit_target and auto_crit:
            outcome = RollOutcome.CRIT
            reason = HitReason.NORMAL
            critical_reason = CriticalReason.AUTO

        elif not auto_hit and hit_target and nat20:
            outcome = RollOutcome.CRIT
            reason = HitReason.NORMAL
            critical_reason = CriticalReason.NORMAL

        elif not auto_hit and not hit_target and nat20:
            outcome = RollOutcome.CRIT
            reason = HitReason.CRITICAL
            critical_reason = CriticalReason.NORMAL
        elif not auto_hit and hit_target and not nat20:
            outcome = RollOutcome.HIT
            reason = HitReason.NORMAL

        return TargetRollOut(
            bonus = self.value,
            target = target,
            base_roll=base_roll_out,
            hit = outcome,
            hit_reason = reason,
            critical_reason = critical_reason)
                    

class AbilityScore(BaseModel):
    ability: Ability
    score: ModifiableValue = Field(default_factory=lambda: ModifiableValue(base_value=BaseValue(name="ability_score",base_value=10)))    

    def apply(self, stats_block: 'StatsBlock', target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None) -> ValueOut:
        return self.score.apply(stats_block, target, context)
    
    def get_modifier(self, stats_block: 'StatsBlock', target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None) -> int:
        return (self.apply(stats_block, target, context).total_bonus -10) // 2

    def remove_effect(self, source: str):
        self.score.remove_effect(source)

class AbilityScores(BaseModel):
    strength: AbilityScore = Field(default_factory=lambda: AbilityScore(ability=Ability.STR, score=ModifiableValue(base_value=BaseValue(name="strength_score",base_value=10))))
    dexterity: AbilityScore = Field(default_factory=lambda: AbilityScore(ability=Ability.DEX, score=ModifiableValue(base_value=BaseValue(name="dexterity_score",base_value=10))))
    constitution: AbilityScore = Field(default_factory=lambda: AbilityScore(ability=Ability.CON, score=ModifiableValue(base_value=BaseValue(name="constitution_score",base_value=10))))
    intelligence: AbilityScore = Field(default_factory=lambda: AbilityScore(ability=Ability.INT, score=ModifiableValue(base_value=BaseValue(name="intelligence_score",base_value=10))))
    wisdom: AbilityScore = Field(default_factory=lambda: AbilityScore(ability=Ability.WIS, score=ModifiableValue(base_value=BaseValue(name="wisdom_score",base_value=10))))
    charisma: AbilityScore = Field(default_factory=lambda: AbilityScore(ability=Ability.CHA, score=ModifiableValue(base_value=BaseValue(name="charisma_score",base_value=10))))
    
    def get_ability(self, ability: Ability) -> AbilityScore:
        return getattr(self, ability.value.lower())

    def get_ability_modifier(self, ability: Ability, stats_block: 'StatsBlock', target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None) -> int:
        ability_score = self.get_ability(ability)
        return ability_score.get_modifier(stats_block, target, context)


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
    bonus: ModifiableValue = Field(default_factory=lambda: ModifiableValue(base_value=BaseValue(base_value=0)))

    def _get_procifiency_converter(self):
        def proficient(proficiency_bonus:int) -> int:
            return proficiency_bonus
        def not_proficient(proficiency_bonus:int) -> int:
            return 0
        def expert(proficiency_bonus:int) -> int:
            return 2*proficiency_bonus
        if self.proficient:
            if self.expertise:
                return expert
            return proficient
        else:
            return not_proficient
        
    def _compute_bonus(self, stats_block: 'StatsBlock', target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None) -> SkillBonusOut:
        def ability_bonus_to_modifier(ability_bonus:int) -> int:
            return (ability_bonus - 10) // 2
        
        ability_bonus = stats_block.ability_scores.get_ability(self.ability).apply(stats_block, target, context)
        
        proficiency_bonus = stats_block.proficiency_bonus.apply(stats_block, target, context)
        skill_bonus = self.bonus.apply(stats_block, target, context)
        target_to_self_bonus = None
        if target:
            target_skill = target.skillset.get_skill(self.skill)
            target_to_self_bonus = target_skill.bonus.apply_to_target(target,stats_block,context)
            total_bonus = skill_bonus.combine_with(target_to_self_bonus)
        
        total_bonus = total_bonus.combine_with(ability_bonus,bonus_converter=ability_bonus_to_modifier).combine_with(proficiency_bonus,bonus_converter=self._get_procifiency_converter())
        return SkillBonusOut(
            skill=self.skill,
            ability_bonus=ability_bonus,
            proficiency_bonus=proficiency_bonus,
            skill_bonus=skill_bonus,
            target_to_self_bonus=target_to_self_bonus,
            total_bonus=total_bonus,
            source_entity_id=stats_block.id,
            target_entity_id=target.id if target else None
        )

    
    def perform_check(self, stats_block: 'StatsBlock', dc: int, target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None) -> SkillRollOut:
        skill_bonus_out = self._compute_bonus(stats_block, target, context)
        roll = TargetRoll(value=skill_bonus_out.total_bonus)
        roll_out=  roll.roll(dc)
        return SkillRollOut(
            skill=self.skill,
            ability=self.ability,
            skill_proficient=self.proficient,
            skill_expertise=self.expertise,
            dc=dc,
            roll=roll_out,
            bonus=skill_bonus_out,
            source_entity_id=stats_block.id,
            target_entity_id=target.id if target else None    
        )
    
    def perform_cross_chek(self, stats_block: 'StatsBlock',target_skill_name:Skills, target: 'StatsBlock', context: Optional[Dict[str, Any]] = None) -> CrossSkillRollOut:
        #first we roll a targetskill check against dc 0 and obtain the result to get the dc
        target_skill = target.skillset.get_skill(target_skill_name)
        target_skill_roll = target_skill.perform_check(target,0,stats_block,context)
        
        target_auto_fail= target_skill_roll.roll.hit_reason == HitReason.AUTOMISS
        dc = target_skill_roll.roll.total_roll if not target_auto_fail else 0
        #then we roll our skill
        source_skill_roll = self.perform_check(stats_block,dc,target,context)
        return CrossSkillRollOut(
            source_skill=self.skill,
            target_skill=target_skill_name,
            target_skill_roll=target_skill_roll,
            source_skill_roll=source_skill_roll
        )
    
    def remove_effects(self, source: str):
        self.bonus.remove_effect(source)

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
            skill_obj.remove_effects(source)

    def perform_skill_check(self, skill: Skills, stats_block: 'StatsBlock', dc: int, target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None) -> SkillRollOut:
        return self.get_skill(skill).perform_check(stats_block, dc, target, context)
    
    def perform_cross_skill_check(self, skill: Skills, target_skill: Skills, stats_block: 'StatsBlock', target: 'StatsBlock' , context: Optional[Dict[str, Any]] = None) -> CrossSkillRollOut:
        return self.get_skill(skill).perform_cross_chek(stats_block,target_skill,target,context)


class SavingThrow(BaseModel):
    ability: Ability
    proficient: bool
    bonus: ModifiableValue = Field(default_factory=lambda: ModifiableValue(base_value=BaseValue(base_value=0)))

    def get_bonus(self, stats_block: 'StatsBlock', target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None) -> int:
        ability_bonus = stats_block.ability_scores.get_ability_modifier(self.ability, stats_block, target, context)
        proficiency_bonus = stats_block.ability_scores.proficiency_bonus.get_value(stats_block, target, context) if self.proficient else 0
        return ability_bonus + proficiency_bonus
    
    def _get_procifiency_converter(self):
        def proficient(proficiency_bonus:int) -> int:
            return proficiency_bonus
        def not_proficient(proficiency_bonus:int) -> int:
            return 0
        if self.proficient:
            return proficient
        else:
            return not_proficient
        
    def _compute_bonus(self, stats_block: 'StatsBlock', target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None) -> SavingThrowBonusOut:
        def ability_bonus_to_modifier(ability_bonus:int) -> int:
            return (ability_bonus - 10) // 2
        
        ability_bonus = stats_block.ability_scores.get_ability(self.ability).apply(stats_block, target, context)
        
        proficiency_bonus = stats_block.proficiency_bonus.apply(stats_block, target, context)
        saving_throw_bonus = self.bonus.apply(stats_block, target, context)
        target_to_self_bonus = None
        if target:
            target_ability = target.saving_throws.get_ability(self.ability)
            target_to_self_bonus = target_ability.bonus.apply_to_target(target,stats_block,context)
            total_bonus = saving_throw_bonus.combine_with(target_to_self_bonus)
        
        total_bonus = total_bonus.combine_with(ability_bonus,bonus_converter=ability_bonus_to_modifier).combine_with(proficiency_bonus,bonus_converter=self._get_procifiency_converter())
        return SavingThrowBonusOut(
            ability=self.ability,
            ability_bonus=ability_bonus,
            proficiency_bonus=proficiency_bonus,
            saving_throw_bonus=saving_throw_bonus,
            target_to_self_bonus=target_to_self_bonus,
            total_bonus=total_bonus
        )
    
    def perform_save(self, stats_block: 'StatsBlock', dc: int, target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None) -> SavingThrowRollOut:
        saving_throw_bonus_out = self._compute_bonus(stats_block, target, context)
        roll = TargetRoll(value=saving_throw_bonus_out.total_bonus)
        roll_out=  roll.roll(dc)
        return SavingThrowRollOut(
            ability=self.ability,
            proficient=self.proficient,
            dc=dc,
            roll=roll_out,
            bonus=saving_throw_bonus_out,
            source_entity_id=stats_block.id,
            target_entity_id=target.id if target else None

        )
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

    def remove_effect(self, ability: Ability, source: str):
        saving_throw = self.get_ability(ability)
        saving_throw.remove_effect(source)

    def perform_save(self, ability: Ability, stats_block: 'StatsBlock', dc: int, target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None) -> SavingThrowRollOut:
        return self.get_ability(ability).perform_save(stats_block, dc, target, context)


class Damage(BaseModel):
    dice: BaseRoll
    damage_bonus : ValueOut
    attack_roll: TargetRollOut 
    type: DamageType
    source: Optional[str] = None

    def roll(self) -> DamageRollOut:
        damage_advantage = self.damage_bonus.advantage_tracker.status
        if self.attack_roll.hit_reason == HitReason.CRITICAL:
            dice = BaseRoll(dice_count=self.dice.dice_count*2, dice_value=self.dice.dice_value)
        else:
            dice = self.dice
        damage_roll = dice.roll(damage_advantage)
        return DamageRollOut(
            dice=dice,
            damage_bonus=self.damage_bonus,
            attack_roll=self.attack_roll,
            type=self.type,
            source=self.source,
            damage_roll=damage_roll,
        )
      

class Health(BaseModel):
    hit_dice_value: int = 6
    hit_dice_count: int = 1
    max_hit_point_bonus: ModifiableValue = Field(default_factory=lambda: ModifiableValue(base_value=0))
    damage_taken :int = 0
    temporary_hit_points: ModifiableValue = Field(default_factory=lambda: ModifiableValue(base_value=0))
    temporary_hit_points_damage_taken: int = 0
    damage_reduction: ModifiableValue = Field(default_factory=lambda: ModifiableValue(base_value=0))
    healing_bonus: ModifiableValue = Field(default_factory=lambda: ModifiableValue(base_value=0))
    vulnerabilities: List[DamageType] = Field(default_factory=list)
    resistances: List[DamageType] = Field(default_factory=list)
    immunities: List[DamageType] = Field(default_factory=list)
 

    @computed_field
    def is_dead(self) -> bool:
        return self.current_hit_points <= 0
    
    @computed_field
    def total_hit_points(self) -> int:
        return self.current_hit_points + self.bonus_hit_points
    
    def _hit_dice_exp_value(self) -> int:
        return self.hit_dice_count * (self.hit_dice_value // 2 + 1)
    
    @computed_field
    def max_hit_points(self) -> int:
        return self._hit_dice_exp_value() + self.max_hit_point_bonus.apply(self).total_bonus
    
    @computed_field
    def current_hit_points(self) -> int:
        return max(0,self.max_hit_points - self.damage_taken)
    
    def add_bonus_max_hp(self, source: str, bonus: int):
        self.max_hit_point_bonus.self_static.add_bonus(source, bonus)
    
    def remove_bonus_max_hp(self, source: str):
        self.max_hit_point_bonus.remove_effect(source)
    
    def add_temporary_hit_points(self, source: str, amount: int):
        if len(self.temporary_hit_points.self_static.bonuses.keys())>0:
            current_hp_source, current_hp_bonus = self.temporary_hit_points.self_static.bonuses.items()[-1]
     
        if amount > current_hp_bonus:
            self.temporary_hit_points.self_static.remove_effect(current_hp_source)
            self.temporary_hit_points.self_static.add_bonus(source, amount)
            self.temporary_hit_points_damage_taken = 0
    
    def damage_temporary_hit_points(self, amount: int):
        self.temporary_hit_points_damage_taken -= amount

    @computed_field
    def current_temporary_hit_points(self) -> int:
        return self.temporary_hit_points.apply(self).total_bonus - self.temporary_hit_points_damage_taken
    
    def reset_temporary_hitpoints(self):
        sources = [source for source in self.temporary_hit_points.self_static.bonuses.keys()]
        for source in sources:
            self.temporary_hit_points.remove_effect(source)
        self.temporary_hit_points_damage_taken = 0

    def get_health_snapshot(self) -> HealthSnapshot:
        return HealthSnapshot(
            max_hit_points=self.max_hit_points,
            temporary_hit_points=self.current_temporary_hit_points,
            damage_taken=self.damage_taken,
        )
    
    def _get_apply_resistance(self, damage_roll:DamageRollOut) -> DamageResistanceOut:
        if damage_roll.damage_type in self.immunities:
            resistance_status= ResistanceStatus.IMMUNITY
        elif damage_roll.damage_type in self.vulnerabilities:
            resistance_status= ResistanceStatus.VULNERABILITY
        elif damage_roll.damage_type in self.resistances:
            resistance_status= ResistanceStatus.RESISTANCE
        else:
            resistance_status= ResistanceStatus.NONE
        
        return DamageResistanceOut(damage_roll = damage_roll, resistance_status = resistance_status)


    def take_damage(self, damage_rolls: List[DamageRollOut], owner: 'StatsBlock', attacker: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None) -> DamageTakenLog:
        health_before = self.get_health_snapshot()
        damage_calculations = []
        for damage_roll in damage_rolls:
            damage_resistance = self._get_apply_resistance(damage_roll)
            damage_calculations.append(damage_resistance)

        total_damage = sum([getattr(damage_resistance,"total_damage_taken") for damage_resistance in damage_calculations])
        flat_damage_reduction_out = self.damage_reduction.apply(owner, attacker, context)
        flat_damage_reduction_bonus = flat_damage_reduction_out.total_bonus
        reduced_damage = max(0, total_damage - flat_damage_reduction_bonus)

        if self.current_temporary_hit_points > 0:
            absorbed_thp = min(self.current_temporary_hit_points, reduced_damage)
            self.damage_temporary_hit_points += absorbed_thp
            if self.current_temporary_hit_points<=0:
                self.reset_temporary_hitpoints()
                hp_damage = reduced_damage - absorbed_thp
            else:
                hp_damage = 0
        
        self.damage_taken += hp_damage
        return DamageTakenLog(
            health_before=health_before,
            health_after=self.get_health_snapshot(),
            damage_calculations=damage_calculations,
            flat_damage_reduction=total_damage-reduced_damage,
            flat_damage_reduction_bonus=flat_damage_reduction_out,
            temp_hp_damage=absorbed_thp,
            hp_damage=hp_damage,
            is_dead=self.is_dead,
        )


    def heal(self, healing: int, owner: 'StatsBlock', healer: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None) -> HealingTakenLog:
        healing_bonus_out = self.healing_bonus.apply(owner, healer, context)
        total_healing = healing + healing_bonus_out.total_bonus
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

class Armor(BaseModel):
    name: str
    type: ArmorType
    base_ac: int
    dex_bonus: bool
    max_dex_bonus: Optional[int] = None
    strength_requirement: Optional[int] = None
    stealth_disadvantage: bool = False

class Shield(BaseModel):
    name: str
    ac_bonus: int


class ArmorClass(BaseModel):
    ac: ModifiableValue = Field(default_factory=lambda: ModifiableValue(base_value=BaseValue(base_value=10)))
    equipped_armor: Optional[Armor] = None
    equipped_shield: Optional[Shield] = None
    unarmored_ac: UnarmoredAc = Field(default=UnarmoredAc.NONE)

    def _gert_unarmored_ac(self, stats_block: 'StatsBlock') -> int:
        if self.unarmored_ac == UnarmoredAc.BARBARIAN:
            return stats_block.ability_scores.constitution.apply(stats_block).total_bonus + stats_block.ability_scores.dexterity.apply(stats_block).total_bonus + 10
        elif self.unarmored_ac == UnarmoredAc.MONK:
            return stats_block.ability_scores.wisdom.apply(stats_block).total_bonus + stats_block.ability_scores.dexterity.apply(stats_block).total_bonus + 10
        elif self.unarmored_ac == UnarmoredAc.DRACONIC_SORCER or self.unarmored_ac == UnarmoredAc.MAGIC_ARMOR:
            return stats_block.ability_scores.dexterity.apply(stats_block).total_bonus + 13


    def update_ac(self, stats_block: 'StatsBlock') -> int:
        if self.equipped_armor:
            base_ac = self.equipped_armor.base_ac
            if self.equipped_armor.dex_bonus:
                dex_bonus = stats_block.ability_scores.dexterity.apply(stats_block).total_bonus
                if self.equipped_armor.max_dex_bonus is not None:
                    dex_bonus = min(dex_bonus, self.equipped_armor.max_dex_bonus)
                base_ac += dex_bonus
        else:
            base_ac = self._gert_unarmored_ac(stats_block)
        if self.equipped_shield:
            base_ac += self.equipped_shield.ac_bonus
        
        self.ac.update_base_value = base_ac

    @computed_field
    def base_ac(self) -> int:
        self.update_ac()
        return self.ac.base_value.base_value
    

    def remove_effect(self, source: str):
        self.ac.remove_effect(source)

    def equip_armor(self, armor: Armor, stats_block: 'StatsBlock'):
        self.equipped_armor = armor
        self.update_ac(stats_block)

    def unequip_armor(self,  stats_block: 'StatsBlock'):
        self.equipped_armor = None
        self.update_ac(stats_block)

    def equip_shield(self, shield: Shield, stats_block: 'StatsBlock'):
        self.equipped_shield = shield
        self.update_ac(stats_block)

    def unequip_shield(self, stats_block: 'StatsBlock'):
        self.equipped_shield = None
        self.update_ac(stats_block)

class Speed(BaseModel):
    walk: ModifiableValue = Field(default_factory=lambda: ModifiableValue(base_value=0))
    fly: ModifiableValue = Field(default_factory=lambda: ModifiableValue(base_value=0))
    swim: ModifiableValue = Field(default_factory=lambda: ModifiableValue(base_value=0))
    burrow: ModifiableValue = Field(default_factory=lambda: ModifiableValue(base_value=0))
    climb: ModifiableValue = Field(default_factory=lambda: ModifiableValue(base_value=0))

    def get_speed(self, speed_type: str, stats_block: 'StatsBlock', target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None) -> int:
        return getattr(self, speed_type).get_value(stats_block, target, context)
    
    def remove_effect(self, speed_type: str, source: str):
        getattr(self, speed_type).remove_effect(source)


    def reset_max_speed(self, source: str):
        for speed_type in ['walk', 'fly', 'swim', 'burrow', 'climb']:
            self.remove_effect(speed_type, source)

class ActionEconomy(BaseModel):
    actions: ModifiableValue = Field(default_factory=lambda: ModifiableValue(base_value=1))
    bonus_actions: ModifiableValue = Field(default_factory=lambda: ModifiableValue(base_value=1))
    reactions: ModifiableValue = Field(default_factory=lambda: ModifiableValue(base_value=1))
    movement: ModifiableValue = Field(default_factory=lambda: ModifiableValue(base_value=30))


    def reset(self):
        for attr in ['actions', 'bonus_actions', 'reactions', 'movement']:
            getattr(self, attr).base_value = getattr(self, attr).base_value

    def set_max_actions(self, source: str, value: int):
        self.actions.self_static.add_max_constraint(source, lambda stats_block, target, context: value)

    def set_max_bonus_actions(self, source: str, value: int):
        self.bonus_actions.self_static.add_max_constraint(source, lambda stats_block, target, context: value)

    def set_max_reactions(self, source: str, value: int):
        self.reactions.self_static.add_max_constraint(source, lambda stats_block, target, context: value)

    def reset_max_actions(self, source: str):
        self.actions.remove_effect(source)

    def reset_max_bonus_actions(self, source: str):
        self.bonus_actions.remove_effect(source)

    def reset_max_reactions(self, source: str):
        self.reactions.remove_effect(source)

    def modify_movement(self, source: str, value: int):
        self.movement.self_static.add_bonus(source, value)

    def remove_movement_modifier(self, source: str):
        self.movement.remove_effect(source)


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

