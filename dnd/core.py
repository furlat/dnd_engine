from __future__ import annotations
from typing import List, Union, TYPE_CHECKING, Optional, Dict, Tuple, Set, Callable, Any
from typing_extensions import Unpack

if TYPE_CHECKING:
    from .statsblock import StatsBlock
from pydantic import BaseModel, ConfigDict, Field, computed_field
from enum import Enum
from typing import List, Union
from dnd.docstrings import *
import uuid
import random
from dnd.contextual import ModifiableValue, AdvantageStatus, AdvantageTracker, BaseValue, ContextAwareBonus, ContextAwareCondition
from dnd.dnd_enums import RollOutcome,HitReason, CriticalReason,ResistanceStatus,Ability,AutoHitStatus,CriticalStatus, Skills, SensesType, ActionType, RechargeType, UsageType, DurationType, RangeType, TargetType, ShapeType, TargetRequirementType, DamageType
from dnd.dnd_enums import AttackHand, UnarmoredAc, ArmorType, NotAppliedReason, RemovedReason, AttackType, WeaponProperty
from dnd.logger import WeaponDamageBonusOut,DamageBonusOut,ValueOut, SimpleRollOut, TargetRollOut, DamageRollOut, SkillBonusOut, SkillRollOut, CrossSkillRollOut, SavingThrowBonusOut,SavingThrowRollOut, DamageResistanceOut
from dnd.logger import AttackRollOut, AttackBonusOut, WeaponAttackBonusOut,ConditionApplied, ConditionAppliedDetails,ConditionRemoved,ConditionRemovedDetails,HealthSnapshot, DamageTakenLog, HealingTakenLog, SavingThrowRollRequest,ConditionNotApplied, Duration
from dnd.spatial import RegistryHolder,DistanceMatrix, FOV, Path,Paths

from dnd.utils import update_or_concat_to_dict
    
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
                all_rolls.append((random.randint(1,self.dice_value),random.randint(1,self.dice_value)))
            chosen_rolls = [max(roll) for roll in all_rolls]
        elif advantage_status == AdvantageStatus.DISADVANTAGE:
            for i in range(self.dice_count):
                all_rolls.append((random.randint(1,self.dice_value),random.randint(1,self.dice_value)))
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
                    

class BlockComponent(BaseModel, RegistryHolder):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(default="BlockComponent")
    description: Optional[str] = None
    owner_id: Optional[str] = None

    def get_owner(self) -> Optional['StatsBlock']:
        if self.owner_id:
            instance = self.get_instance(self.owner_id)
            if TYPE_CHECKING:
                assert isinstance(instance, StatsBlock)
            return instance
        raise ValueError("Owner not set")
    
    def set_owner(self, owner_id: str):
        if not self.is_in_registry(owner_id):
            raise ValueError(f"Owner {owner_id} is not in the registry")
        self.owner_id = owner_id
        
        # Recursively set owner for all nested BlockComponent attributes
        for attr_name, attr_value in self.__dict__.items():
            if isinstance(attr_value, BlockComponent):
                attr_value.set_owner(owner_id)
            elif isinstance(attr_value, list):
                for item in attr_value:
                    if isinstance(item, BlockComponent):
                        item.set_owner(owner_id)
            elif isinstance(attr_value, dict):
                for item in attr_value.values():
                    if isinstance(item, BlockComponent):
                        item.set_owner(owner_id)

    def get_target(self, target_id: str) -> Optional['StatsBlock']:
        instance = self.get_instance(target_id)
        if TYPE_CHECKING:
            assert isinstance(instance, StatsBlock)
        return instance

    def get_stats_blocks(self, target: Optional[str] = None) -> Tuple[Optional['StatsBlock'], Optional['StatsBlock']]:
        stats_block = self.get_owner()
        target_stats_block = self.get_target(target) if target else None
        return stats_block, target_stats_block



class AbilityScore(BlockComponent):
    ability: Ability
    score: ModifiableValue = Field(default_factory=lambda: ModifiableValue(base_value=BaseValue(name="ability_score",base_value=10)))    

    def apply(self, target: Optional[str] = None, context: Optional[Dict[str, Any]] = None) -> ValueOut:
        stats_block , target_stats_block = self.get_stats_blocks(target)
        if TYPE_CHECKING:
            assert isinstance(stats_block, StatsBlock)
            assert isinstance(target_stats_block, StatsBlock) or target_stats_block is None
        return self.score.apply(stats_block, target_stats_block, context)
    
    def get_modifier(self, target: Optional[str] = None, context: Optional[Dict[str, Any]] = None) -> int:
        base_bonus = self.apply(target, context).total_bonus
        # print(f"base_bonus: {base_bonus} for ability {self.ability}")
        return (base_bonus -10) // 2

    def remove_effect(self, source: str):
        self.score.remove_effect(source)

class AbilityScores(BlockComponent):
    name: str = Field(default="AbilityScores")
    strength: AbilityScore = Field(default_factory=lambda: AbilityScore(
        name="StrengthScore",
        ability=Ability.STR, 
        score=ModifiableValue(
            name="StrengthScore",
            base_value=BaseValue(name="base_strength_score", base_value=10, min_value=1, max_value=30))
    ))
    dexterity: AbilityScore = Field(default_factory=lambda: AbilityScore(
        name="DexterityScore",
        ability=Ability.DEX, 
        score=ModifiableValue(
            name = "DexterityScore",
            base_value=BaseValue(name="base_dexterity_score", base_value=10, min_value=1, max_value=30))
    ))
    constitution: AbilityScore = Field(default_factory=lambda: AbilityScore(
        name="ConstitutionScore",
        ability=Ability.CON, 
        score=ModifiableValue(
            name = "ConstitutionScore",
            base_value=BaseValue(name="base_constitution_score", base_value=10, min_value=1, max_value=30))
    ))
    intelligence: AbilityScore = Field(default_factory=lambda: AbilityScore(
        name="IntelligenceScore",
        ability=Ability.INT, 
        score=ModifiableValue(
            name = "IntelligenceScore",
            base_value=BaseValue(name="base_intelligence_score", base_value=10, min_value=1, max_value=30))
    ))
    wisdom: AbilityScore = Field(default_factory=lambda: AbilityScore(
        name="WisdomScore",
        ability=Ability.WIS, 
        score=ModifiableValue(
            name = "WisdomScore",
            base_value=BaseValue(name="base_wisdom_score", base_value=10, min_value=1, max_value=30))
    ))
    charisma: AbilityScore = Field(default_factory=lambda: AbilityScore(
        name="CharismaScore",
        ability=Ability.CHA, 
        score=ModifiableValue(
            name = "CharismaScore",
            base_value=BaseValue(name="base_charisma_score", base_value=10, min_value=1, max_value=30))
    ))
    def get_ability(self, ability: Ability) -> AbilityScore:
        return getattr(self, ability.value.lower())

    def get_ability_modifier(self, ability: Ability, target: Optional[str] = None, context: Optional[Dict[str, Any]] = None)  -> int:
        ability_score = self.get_ability(ability)
        return ability_score.get_modifier(target, context)


ABILITY_TO_SKILLS = {
    Ability.STR: [Skills.ATHLETICS],
    Ability.DEX: [Skills.ACROBATICS, Skills.SLEIGHT_OF_HAND, Skills.STEALTH],
    Ability.CON: [],
    Ability.INT: [Skills.ARCANA, Skills.HISTORY, Skills.INVESTIGATION, Skills.NATURE, Skills.RELIGION],
    Ability.WIS: [Skills.ANIMAL_HANDLING, Skills.INSIGHT, Skills.MEDICINE, Skills.PERCEPTION, Skills.SURVIVAL],
    Ability.CHA: [Skills.DECEPTION, Skills.INTIMIDATION, Skills.PERFORMANCE, Skills.PERSUASION]
}

class Skill(BlockComponent):
    name: str = Field(default="Skill")
    ability: Ability
    skill: Skills
    proficient: bool = False
    expertise: bool = False
    bonus: ModifiableValue = Field(default_factory=lambda: ModifiableValue(
        base_value=BaseValue(
            name="base_skill_bonus",
            base_value=0,
            min_value=None,
            max_value=None
        )
    ))

    def _get_proficiency_converter(self):
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
        
    def _compute_bonus(self, target: Optional[str] = None, context: Optional[Dict[str, Any]] = None) -> SkillBonusOut:
        def ability_bonus_to_modifier(ability_bonus:int) -> int:
            return (ability_bonus - 10) // 2
        
        stats_block , target_stats_block = self.get_stats_blocks(target)
        if TYPE_CHECKING:
            assert isinstance(stats_block, StatsBlock)
            assert isinstance(target_stats_block, StatsBlock) or target_stats_block is None
        
        ability_bonus = stats_block.ability_scores.get_ability(self.ability).apply(target, context)
        
        proficiency_bonus = stats_block.proficiency_bonus.apply(stats_block, target_stats_block, context)
        skill_bonus = self.bonus.apply(stats_block, target_stats_block, context)
        target_to_self_bonus = None
        if target_stats_block:
            target_skill = target_stats_block.skillset.get_skill(self.skill)
            target_to_self_bonus = target_skill.bonus.apply_to_target(target_stats_block,stats_block,context)
            total_bonus = skill_bonus.combine_with(target_to_self_bonus)
        else:
            total_bonus = skill_bonus
        
        total_bonus = total_bonus.combine_with(ability_bonus,bonus_converter=ability_bonus_to_modifier).combine_with(proficiency_bonus,bonus_converter=self._get_proficiency_converter())
        return SkillBonusOut(
            skill=self.skill,
            ability_bonus=ability_bonus,
            proficiency_bonus=proficiency_bonus,
            skill_bonus=skill_bonus,
            target_to_self_bonus=target_to_self_bonus,
            total_bonus=total_bonus,
            source_entity_id=stats_block.id,
            target_entity_id=target if target else None
        )

    
    def perform_check(self, dc: int, target: Optional[str] = None, context: Optional[Dict[str, Any]] = None)  -> SkillRollOut:
        skill_bonus_out = self._compute_bonus(target, context)
        roll = TargetRoll(value=skill_bonus_out.total_bonus)
        roll_out=  roll.roll(dc)
        return SkillRollOut(
            skill=self.skill,
            ability=self.ability,
            skill_proficient=self.proficient,
            skill_expert=self.expertise,
            dc=dc,
            roll=roll_out,
            bonus=skill_bonus_out,
            source_entity_id=self.owner_id,
            target_entity_id=target if target else None    
        )
    
    def perform_cross_check(self, target_skill_name:Skills, target: Optional[str] = None, context: Optional[Dict[str, Any]] = None) -> CrossSkillRollOut:
        #first we roll a targetskill check against dc 0 and obtain the result to get the dc
        stats_block , target_stats_block = self.get_stats_blocks(target)
        if stats_block is None or target_stats_block is None:
            raise ValueError("StatsBlock or TargetStatsBlock is None")  
        target_skill = target_stats_block.skillset.get_skill(target_skill_name)
        target_skill_roll = target_skill.perform_check(0,self.owner_id,context)
        
        target_auto_fail= target_skill_roll.roll.hit_reason == HitReason.AUTOMISS
        dc = target_skill_roll.roll.total_roll if not target_auto_fail else 0
        #then we roll our skill
        source_skill_roll = self.perform_check(dc,target,context)
        return CrossSkillRollOut(
            source_skill=self.skill,
            target_skill=target_skill_name,
            target_skill_roll=target_skill_roll,
            source_skill_roll=source_skill_roll
        )
    
    def remove_effects(self, source: str):
        self.bonus.remove_effect(source)

class SkillSet(BlockComponent):
    name: str = Field(default="SkillSet")
    acrobatics: Skill = Field(default_factory=lambda: Skill(name="Acrobatics", ability=Ability.DEX, skill=Skills.ACROBATICS, bonus=ModifiableValue(name="acrobatics_bonus", base_value=BaseValue(name="base_acrobatics_bonus", base_value=0))))
    animal_handling: Skill = Field(default_factory=lambda: Skill(name="AnimalHandling", ability=Ability.WIS, skill=Skills.ANIMAL_HANDLING, bonus=ModifiableValue(name="animal_handling_bonus", base_value=BaseValue(name="base_animal_handling_bonus", base_value=0))))
    arcana: Skill = Field(default_factory=lambda: Skill(name="Arcana", ability=Ability.INT, skill=Skills.ARCANA, bonus=ModifiableValue(name="arcana_bonus", base_value=BaseValue(name="base_arcana_bonus", base_value=0))))
    athletics: Skill = Field(default_factory=lambda: Skill(name="Athletics", ability=Ability.STR, skill=Skills.ATHLETICS, bonus=ModifiableValue(name="athletics_bonus", base_value=BaseValue(name="base_athletics_bonus", base_value=0))))
    deception: Skill = Field(default_factory=lambda: Skill(name="Deception", ability=Ability.CHA, skill=Skills.DECEPTION, bonus=ModifiableValue(name="deception_bonus", base_value=BaseValue(name="base_deception_bonus", base_value=0))))
    history: Skill = Field(default_factory=lambda: Skill(name="History", ability=Ability.INT, skill=Skills.HISTORY, bonus=ModifiableValue(name="history_bonus", base_value=BaseValue(name="base_history_bonus", base_value=0))))
    insight: Skill = Field(default_factory=lambda: Skill(name="Insight", ability=Ability.WIS, skill=Skills.INSIGHT, bonus=ModifiableValue(name="insight_bonus", base_value=BaseValue(name="base_insight_bonus", base_value=0))))
    intimidation: Skill = Field(default_factory=lambda: Skill(name="Intimidation", ability=Ability.CHA, skill=Skills.INTIMIDATION, bonus=ModifiableValue(name="intimidation_bonus", base_value=BaseValue(name="base_intimidation_bonus", base_value=0))))
    investigation: Skill = Field(default_factory=lambda: Skill(name="Investigation", ability=Ability.INT, skill=Skills.INVESTIGATION, bonus=ModifiableValue(name="investigation_bonus", base_value=BaseValue(name="base_investigation_bonus", base_value=0))))
    medicine: Skill = Field(default_factory=lambda: Skill(name="Medicine", ability=Ability.WIS, skill=Skills.MEDICINE, bonus=ModifiableValue(name="medicine_bonus", base_value=BaseValue(name="base_medicine_bonus", base_value=0))))
    nature: Skill = Field(default_factory=lambda: Skill(name="Nature", ability=Ability.INT, skill=Skills.NATURE, bonus=ModifiableValue(name="nature_bonus", base_value=BaseValue(name="base_nature_bonus", base_value=0))))
    perception: Skill = Field(default_factory=lambda: Skill(name="Perception", ability=Ability.WIS, skill=Skills.PERCEPTION, bonus=ModifiableValue(name="perception_bonus", base_value=BaseValue(name="base_perception_bonus", base_value=0))))
    performance: Skill = Field(default_factory=lambda: Skill(name="Performance", ability=Ability.CHA, skill=Skills.PERFORMANCE, bonus=ModifiableValue(name="performance_bonus", base_value=BaseValue(name="base_performance_bonus", base_value=0))))
    persuasion: Skill = Field(default_factory=lambda: Skill(name="Persuasion", ability=Ability.CHA, skill=Skills.PERSUASION, bonus=ModifiableValue(name="persuasion_bonus", base_value=BaseValue(name="base_persuasion_bonus", base_value=0))))
    religion: Skill = Field(default_factory=lambda: Skill(name="Religion", ability=Ability.INT, skill=Skills.RELIGION, bonus=ModifiableValue(name="religion_bonus", base_value=BaseValue(name="base_religion_bonus", base_value=0))))
    sleight_of_hand: Skill = Field(default_factory=lambda: Skill(name="SleightOfHand", ability=Ability.DEX, skill=Skills.SLEIGHT_OF_HAND, bonus=ModifiableValue(name="sleight_of_hand_bonus", base_value=BaseValue(name="base_sleight_of_hand_bonus", base_value=0))))
    stealth: Skill = Field(default_factory=lambda: Skill(name="Stealth", ability=Ability.DEX, skill=Skills.STEALTH, bonus=ModifiableValue(name="stealth_bonus", base_value=BaseValue(name="base_stealth_bonus", base_value=0))))
    survival: Skill = Field(default_factory=lambda: Skill(name="Survival", ability=Ability.WIS, skill=Skills.SURVIVAL, bonus=ModifiableValue(name="survival_bonus", base_value=BaseValue(name="base_survival_bonus", base_value=0))))
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

    def perform_skill_check(self, skill: Skills, dc: int, target: Optional[str] = None, context: Optional[Dict[str, Any]] = None) -> SkillRollOut:
        return self.get_skill(skill).perform_check(dc, target, context)
    
    def perform_cross_skill_check(self, skill: Skills, target_skill: Skills, target: str , context: Optional[Dict[str, Any]] = None) -> CrossSkillRollOut:
        return self.get_skill(skill).perform_cross_check(target_skill,target,context)

class SavingThrow(BlockComponent):
    name: str = Field(default="SavingThrow")
    ability: Ability
    proficient: bool = False
    bonus: ModifiableValue = Field(default_factory=lambda: ModifiableValue(
        name = "SavingThrowBonus",
        base_value=BaseValue(
            name="base_saving_throw_bonus",
            base_value=0,
            min_value=None,
            max_value=None
        )
    ))

    def _get_proficiency_converter(self):
        def proficient(proficiency_bonus:int) -> int:
            return proficiency_bonus
        def not_proficient(proficiency_bonus:int) -> int:
            return 0
        if self.proficient:
            return proficient
        else:
            return not_proficient
        
    def _compute_bonus(self, target: Optional[str] = None, context: Optional[Dict[str, Any]] = None) -> SavingThrowBonusOut:
        def ability_bonus_to_modifier(ability_bonus:int) -> int:
            return (ability_bonus - 10) // 2
        stats_block,target_stats_block = self.get_stats_blocks(target)
        if TYPE_CHECKING:
            assert isinstance(stats_block, StatsBlock)
            assert isinstance(target_stats_block, StatsBlock) or target_stats_block is None
        ability_bonus = stats_block.ability_scores.get_ability(self.ability).apply(target, context)
        
        proficiency_bonus = stats_block.proficiency_bonus.apply(stats_block, target_stats_block, context)
        saving_throw_bonus = self.bonus.apply(stats_block, target_stats_block, context)
        target_to_self_bonus = None
        if target_stats_block:
            target_ability = target_stats_block.saving_throws.get_ability(self.ability)
            target_to_self_bonus = target_ability.bonus.apply_to_target(target_stats_block,stats_block,context)
            total_bonus = saving_throw_bonus.combine_with(target_to_self_bonus)
        else:
            total_bonus = saving_throw_bonus
        
        total_bonus = total_bonus.combine_with(ability_bonus,bonus_converter=ability_bonus_to_modifier).combine_with(proficiency_bonus,bonus_converter=self._get_proficiency_converter())
        return SavingThrowBonusOut(
            ability=self.ability,
            ability_bonus=ability_bonus,
            proficiency_bonus=proficiency_bonus,
            saving_throw_bonus=saving_throw_bonus,
            target_to_self_bonus=target_to_self_bonus,
            total_bonus=total_bonus
        )
    
    def perform_save(self, dc: int, target: Optional[str] = None, context: Optional[Dict[str, Any]] = None) -> SavingThrowRollOut:
        saving_throw_bonus_out = self._compute_bonus( target, context)
        roll = TargetRoll(value=saving_throw_bonus_out.total_bonus)
        roll_out=  roll.roll(dc)
        return SavingThrowRollOut(
            ability=self.ability,
            proficient=self.proficient,
            dc=dc,
            roll=roll_out,
            bonus=saving_throw_bonus_out,
            source_entity_id=self.owner_id,
            target_entity_id=target if target else None

        )
    def remove_effect(self, source: str):
        self.bonus.remove_effect(source)

class SavingThrows(BlockComponent):
    name: str = Field(default="SavingThrows")
    strength: SavingThrow = Field(default_factory=lambda: SavingThrow(
        name="StrengthSavingThrow",
        ability=Ability.STR,
        proficient=False,
        bonus=ModifiableValue(
            name = "StrengthSavingThrowBonus",
            base_value=BaseValue(name="base_strength_saving_throw_bonus", base_value=0))
    ))
    dexterity: SavingThrow = Field(default_factory=lambda: SavingThrow(
        name="DexteritySavingThrow",
        ability=Ability.DEX,
        proficient=False,
        bonus=ModifiableValue(
            name = "DexteritySavingThrowBonus",
            base_value=BaseValue(name="base_dexterity_saving_throw_bonus", base_value=0))
    ))
    constitution: SavingThrow = Field(default_factory=lambda: SavingThrow(
        name="ConstitutionSavingThrow",
        ability=Ability.CON,
        proficient=False,
        bonus=ModifiableValue(
            name = "ConstitutionSavingThrowBonus",
            base_value=BaseValue(name="base_constitution_saving_throw_bonus", base_value=0))
    ))
    intelligence: SavingThrow = Field(default_factory=lambda: SavingThrow(
        name="IntelligenceSavingThrow",
        ability=Ability.INT,
        proficient=False,
        bonus=ModifiableValue(
            name = "IntelligenceSavingThrowBonus",
            base_value=BaseValue(name="base_intelligence_saving_throw_bonus", base_value=0))
    ))
    wisdom: SavingThrow = Field(default_factory=lambda: SavingThrow(
        name="WisdomSavingThrow",
        ability=Ability.WIS,
        proficient=False,
        bonus=ModifiableValue(name = "WisdomSavingThrowBonus",
                              base_value=BaseValue(name="base_wisdom_saving_throw_bonus", base_value=0))
    ))
    charisma: SavingThrow = Field(default_factory=lambda: SavingThrow(
        name="CharismaSavingThrow",
        ability=Ability.CHA,
        proficient=False,
        bonus=ModifiableValue(
            name= "CharismaSavingThrowBonus",
            base_value=BaseValue(name="base_charisma_saving_throw_bonus", base_value=0))
    ))

    def get_ability(self, ability: Ability) -> SavingThrow:
        return getattr(self, ability.value.lower())

    def set_proficiency(self, ability: Ability, value: bool = True):
        savingthrow = self.get_ability(ability)
        savingthrow.proficient = value

    def remove_effect(self, ability: Ability, source: str):
        saving_throw = self.get_ability(ability)
        saving_throw.remove_effect(source)
    
    def perform_save(self, ability: Ability, dc: int, target: Optional[str] = None, context: Optional[Dict[str, Any]] = None) -> SavingThrowRollOut:
        return self.get_ability(ability).perform_save( dc, target, context)

    def perform_save_from_request(self, request: SavingThrowRollRequest, target: Optional[str] = None, context: Optional[Dict[str, Any]] = None) -> SavingThrowRollOut:
        return self.get_ability(request.ability).perform_save(request.dc, target, context)



class Health(BlockComponent):
    name: str = Field(default="Health")
    hit_dice_value: int = 6
    hit_dice_count: int = 1
    max_hit_point_bonus: ModifiableValue = Field(default_factory=lambda: ModifiableValue(
        name = "MaxHitPointBonus",
        base_value=BaseValue(name="base_max_hp_bonus", base_value=0)
    ))
    damage_taken: int = 0
    temporary_hit_points: ModifiableValue = Field(default_factory=lambda: ModifiableValue(
        name = "TemporaryHitPoints",
        base_value=BaseValue(name="base_temporary_hp", base_value=0)
    ))
    temporary_hit_points_damage_taken: int = 0
    damage_reduction: ModifiableValue = Field(default_factory=lambda: ModifiableValue(
        name = "DamageReduction",
        base_value=BaseValue(name="base_damage_reduction", base_value=0)
    ))
    healing_bonus: ModifiableValue = Field(default_factory=lambda: ModifiableValue(
        name = "HealingBonus",
        base_value=BaseValue(name="base_healing_bonus", base_value=0)
    ))
    vulnerabilities: List[DamageType] = Field(default_factory=list)
    resistances: List[DamageType] = Field(default_factory=list)
    immunities: List[DamageType] = Field(default_factory=list)
 

    @computed_field
    @property
    def is_dead(self) -> bool:
        return self.current_hit_points <= 0
    
    @computed_field
    @property
    def total_hit_points(self) -> int:
        return self.current_hit_points + self.current_temporary_hit_points
    
    def _hit_dice_exp_value(self) -> int:
        return self.hit_dice_count * (self.hit_dice_value // 2 + 1)
    
    @computed_field
    @property
    def max_hit_points(self) -> int:
        owner_block = self.get_owner()
        if TYPE_CHECKING:
            assert isinstance(owner_block, StatsBlock)
        constitution_modifier = owner_block.ability_scores.get_ability_modifier(Ability.CON)
        total_consitution_bonus = constitution_modifier * self.hit_dice_count
        hit_dice_exp_value = self._hit_dice_exp_value()
        max_hit_point_bonus = self.max_hit_point_bonus.apply(owner_block).total_bonus
        # print(f"hit_dice_exp_value: {hit_dice_exp_value}, max_hit_point_bonus: {max_hit_point_bonus}, total_consitution_bonus: {total_consitution_bonus}, base_constitution_bonus: {constitution_modifier}")
        return hit_dice_exp_value + max_hit_point_bonus + total_consitution_bonus
    
    @computed_field
    @property
    def current_hit_points(self) -> int:
        return max(0,self.max_hit_points - self.damage_taken)
    
    def add_bonus_max_hp(self, source: str, bonus: int):
        self.max_hit_point_bonus.self_static.add_bonus(source, bonus)
    
    def remove_bonus_max_hp(self, source: str):
        self.max_hit_point_bonus.remove_effect(source)
    
    def add_temporary_hit_points(self, source: str, amount: int):
        if len(self.temporary_hit_points.self_static.bonuses.keys())>0:
            current_hp_source, current_hp_bonus = list(self.temporary_hit_points.self_static.bonuses.items())[-1]
     
        if amount > current_hp_bonus:
            self.temporary_hit_points.self_static.remove_effect(current_hp_source)
            self.temporary_hit_points.self_static.add_bonus(source, amount)
            self.temporary_hit_points_damage_taken = 0
    
    def damage_temporary_hit_points(self, amount: int):
        self.temporary_hit_points_damage_taken -= amount

    @computed_field
    @property
    def current_temporary_hit_points(self) -> int:
        owner = self.get_owner()
        if TYPE_CHECKING:
            assert isinstance(owner, StatsBlock)
        return self.temporary_hit_points.apply(owner).total_bonus - self.temporary_hit_points_damage_taken
    
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


    def take_damage(self, damage_rolls: Union[DamageRollOut,List[DamageRollOut]], attacker: Optional[str] = None, context: Optional[Dict[str, Any]] = None) -> DamageTakenLog:
        if isinstance(damage_rolls, DamageRollOut):
            damage_rolls = [damage_rolls]
        health_before = self.get_health_snapshot()
        damage_calculations = []
        for damage_roll in damage_rolls:
            damage_resistance = self._get_apply_resistance(damage_roll)
            damage_calculations.append(damage_resistance)
        
        owner_stats_block, attacker_stats_block = self.get_stats_blocks(attacker)
        if TYPE_CHECKING:
            assert isinstance(owner_stats_block, StatsBlock)
            assert isinstance(attacker_stats_block, StatsBlock) or attacker_stats_block is None

        total_damage = sum([getattr(damage_resistance,"total_damage_taken") for damage_resistance in damage_calculations])
        flat_damage_reduction_out = self.damage_reduction.apply(owner_stats_block, attacker_stats_block, context)
        flat_damage_reduction_bonus = flat_damage_reduction_out.total_bonus
        reduced_damage = max(0, total_damage - flat_damage_reduction_bonus)
        absorbed_thp = 0
        if self.current_temporary_hit_points > 0:
            absorbed_thp = min(self.current_temporary_hit_points, reduced_damage)
            self.damage_temporary_hit_points(absorbed_thp)
            if self.current_temporary_hit_points<=0:
                self.reset_temporary_hitpoints()
                hp_damage = reduced_damage - absorbed_thp
            else:
                hp_damage = 0
        else:
            hp_damage = reduced_damage
        
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
            source_entity_id=attacker_stats_block.id if attacker_stats_block else None,
            target_entity_id=owner_stats_block.id
        )


    def heal(self, healing: int, healer: Optional[str] = None, context: Optional[Dict[str, Any]] = None) -> HealingTakenLog:
        owner_stats_block ,healer_stats_block = self.get_stats_blocks(healer)
        if TYPE_CHECKING:
            assert isinstance(owner_stats_block, StatsBlock)
            assert isinstance(healer_stats_block, StatsBlock) or healer_stats_block is None
        healing_bonus_out = self.healing_bonus.apply(owner_stats_block, healer_stats_block, context)
        total_healing = healing + healing_bonus_out.total_bonus
        health_before = self.get_health_snapshot()
        actual_healing = min(total_healing, self.damage_taken)
        self.damage_taken = max(0, self.damage_taken - total_healing)



        # Log the healing received
        return HealingTakenLog(
            health_before=health_before,
            health_after=self.get_health_snapshot(),
            healing_received=actual_healing,
            source_entity_id=healer if healer else None,
            target_entity_id=self.owner_id
        )




    def set_bonus_hit_points(self, source: str, amount: int):
        if self.bonus_hit_points_source != source:
            self.bonus_hit_points = amount
            self.bonus_hit_points_source = source


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


class ArmorClass(BlockComponent):
    name: str = Field(default="ArmorClass")
    ac: ModifiableValue = Field(default_factory=lambda: ModifiableValue(
        name="armor class",
        base_value=BaseValue(name="base_armor_class", base_value=10)
    ))
    equipped_armor: Optional[Armor] = None
    equipped_shield: Optional[Shield] = None
    unarmored_ac: UnarmoredAc = Field(default=UnarmoredAc.NONE)

    def _get_unarmored_ac(self) -> int:
        owner_id = self.owner_id
        assert isinstance(owner_id, str)
        stats_block = self.get_owner()
        if TYPE_CHECKING:
            assert isinstance(stats_block, StatsBlock)
        
        if self.unarmored_ac == UnarmoredAc.BARBARIAN:
            return stats_block.ability_scores.constitution.apply().total_bonus + stats_block.ability_scores.dexterity.apply(owner_id).total_bonus + 10
        elif self.unarmored_ac == UnarmoredAc.MONK:
            return stats_block.ability_scores.wisdom.apply().total_bonus + stats_block.ability_scores.dexterity.apply(owner_id).total_bonus + 10
        elif self.unarmored_ac == UnarmoredAc.DRACONIC_SORCER or self.unarmored_ac == UnarmoredAc.MAGIC_ARMOR:
            return stats_block.ability_scores.dexterity.apply().total_bonus + 13
        else:
            return stats_block.ability_scores.dexterity.apply().total_bonus + 10


    def update_ac(self) -> None:
        stats_block = self.get_owner()
        if TYPE_CHECKING:
            assert isinstance(stats_block, StatsBlock)
        if self.equipped_armor:
            base_ac = self.equipped_armor.base_ac
            if self.equipped_armor.dex_bonus:
                dex_bonus = stats_block.ability_scores.dexterity.get_modifier()
                if self.equipped_armor.max_dex_bonus is not None:
                    dex_bonus = min(dex_bonus, self.equipped_armor.max_dex_bonus)
                base_ac += dex_bonus
        else:
            base_ac = self._get_unarmored_ac()
        if self.equipped_shield:
            base_ac += self.equipped_shield.ac_bonus
        
        self.ac.update_base_value(base_ac)

    @computed_field
    @property
    def base_ac(self) -> int:
        self.update_ac()
        return self.ac.base_value.base_value
    
    @computed_field
    @property
    def total_ac(self) -> int:
        owner = self.get_owner()
        if TYPE_CHECKING:
            assert isinstance(owner, StatsBlock)
        return self.ac.apply(owner).total_bonus
    

    def remove_effect(self, source: str):
        self.ac.remove_effect(source)

    def equip_armor(self, armor: Armor):
        self.equipped_armor = armor
        self.update_ac()

    def unequip_armor(self):
        self.equipped_armor = None
        self.update_ac()

    def equip_shield(self, shield: Shield):
        self.equipped_shield = shield
        self.update_ac()

    def unequip_shield(self):
        self.equipped_shield = None
        self.update_ac()

class Speed(BlockComponent):
    name: str = Field(default="Speed")
    walk: ModifiableValue = Field(default_factory=lambda: ModifiableValue(
        name="walk",
        base_value=BaseValue(name="base_walk_speed", base_value=30)
    ))
    fly: ModifiableValue = Field(default_factory=lambda: ModifiableValue(
        name="fly",
        base_value=BaseValue(name="base_fly_speed", base_value=0)
    ))
    swim: ModifiableValue = Field(default_factory=lambda: ModifiableValue(
        name="swim",
        base_value=BaseValue(name="base_swim_speed", base_value=0)
    ))
    burrow: ModifiableValue = Field(default_factory=lambda: ModifiableValue(
        name="burrow",
        base_value=BaseValue(name="base_burrow_speed", base_value=0)
    ))
    climb: ModifiableValue = Field(default_factory=lambda: ModifiableValue(
        name="climb",
        base_value=BaseValue(name="base_climb_speed", base_value=0)
    ))

    def reset_max_speed(self, source: str):
        for speed_type in ['walk', 'fly', 'swim', 'burrow', 'climb']:
            speed_obj: ModifiableValue = getattr(self, speed_type)
            speed_obj.remove_effect(source)

class ActionEconomy(BlockComponent):
    name: str = Field(default="ActionEconomy")
    actions: ModifiableValue = Field(default_factory=lambda: ModifiableValue(name="actions",
        base_value=BaseValue(name="base_actions", base_value=1)
    ))
    bonus_actions: ModifiableValue = Field(default_factory=lambda: ModifiableValue(
        name="bonus_actions",
        base_value=BaseValue(name="base_bonus_actions", base_value=1)
    ))
    reactions: ModifiableValue = Field(default_factory=lambda: ModifiableValue(
        name="reactions",
        base_value=BaseValue(name="base_reactions", base_value=1)
    ))
    movement: ModifiableValue = Field(default_factory=lambda: ModifiableValue(
        name="movement",
        base_value=BaseValue(name="base_movement", base_value=30)
    ))

    def set_max_actions(self, source: str, value: int):
        self.actions.self_static.add_max_constraint(source, value)

    def set_max_bonus_actions(self, source: str, value: int):
        self.bonus_actions.self_static.add_max_constraint(source, value)

    def set_max_reactions(self, source: str, value: int):
        self.reactions.self_static.add_max_constraint(source, value)
    def _constant_value(self, value: int) -> Callable[[Any, Any, Any], int]:
        def constant(*args) -> int:
            return value
        return constant
    def _sync_movement_with_speed(self):
        owner_block = self.get_owner()
        if TYPE_CHECKING:
            assert isinstance(owner_block, StatsBlock)
        self.movement.update_base_value(owner_block.speed.walk.apply(owner_block).total_bonus)

    def _remove_cost_bonus(self):
        #removes from self_static all the conditions with cost in it
        for action_type in ['actions', 'bonus_actions', 'reactions', 'movement']:
            action_obj: ModifiableValue = getattr(self, action_type)
            #all effects in the self_static
            cost_effects = [effect_name for effect_name in action_obj.self_static.bonuses.keys() if "_cost" in effect_name]
            for effect_name in cost_effects:
                action_obj.remove_effect(effect_name)

    def reset(self):
        base_action = 1
        base_bonus_action = 1
        base_reaction = 1
        self.actions.update_base_value(base_action)
        self.bonus_actions.update_base_value(base_bonus_action)
        self.reactions.update_base_value(base_reaction)
        self._sync_movement_with_speed()
        self._remove_cost_bonus()

    
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

class Sensory(BlockComponent):
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
        if self.origin is None:
            raise ValueError("Origin is not set")
        self.distance_matrix = DistanceMatrix(
            battlemap_id=self.battlemap_id if self.battlemap_id else "testing",
            origin=self.origin,
            distances=distances
        )

    def update_fov(self, visible_tiles: Set[Tuple[int, int]]):
        if self.origin is None:
            raise ValueError("Origin is not set")
        self.fov = FOV(
            battlemap_id=self.battlemap_id if self.battlemap_id else "testing",
            origin=self.origin,
            visible_tiles=visible_tiles
        )

    def update_paths(self, paths: Dict[Tuple[int, int], List[Tuple[int, int]]]):
        if self.origin is None:
            raise ValueError("Origin is not set")
        self.paths = Paths(
            battlemap_id=self.battlemap_id if self.battlemap_id else "testing",
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


    
ContextAwareImmunity = Callable[['StatsBlock', Optional['StatsBlock'],Optional[dict]], bool]

class ConditionManager(BlockComponent):
    name: str = Field(default="ConditionManager")
    active_conditions: Dict[str, Condition] = Field(default_factory=dict)
    condition_immunities: Dict[str, List[str]] = Field(default_factory=dict)
    contextual_condition_immunities: Dict[str, List[Tuple[str, ContextAwareImmunity]]] = Field(default_factory=dict)
    active_conditions_by_source: Dict[str, List[str]] = Field(default_factory=dict)
    
    
    
    def add_condition(self, condition: Condition,context: Optional[Dict[str, Any]] = None)  -> Union[ConditionApplied, ConditionNotApplied]:
        if condition.targeted_entity_id is None:
            condition.targeted_entity_id = self.owner_id
        
        condition_application_report = condition.apply(context)
        if isinstance(condition_application_report, ConditionApplied):
            self.active_conditions[condition.name] = condition
            if condition.source_entity_id is None:
                raise ValueError("Source entity id is not set")
            self.active_conditions_by_source = update_or_concat_to_dict(self.active_conditions_by_source, (condition.source_entity_id, condition.name))
        return condition_application_report

    


    def _remove_condition_from_dicts(self, condition_name: str) :
        condition = self.active_conditions.pop(condition_name)
        assert condition.source_entity_id is not None
        self.active_conditions_by_source[condition.source_entity_id].remove(condition_name)
    
    def add_condition_immunity(self, condition_name: str, immunity_name: str = "self_immunity"):
        self.condition_immunities= update_or_concat_to_dict(self.condition_immunities, (condition_name, immunity_name))

    def remove_condition_immunity(self, condition_name: str):
        self.condition_immunities.pop(condition_name)

    def add_contextual_condition_immunity(self, condition_name: str, immunity_name: str, immunity_check: ContextAwareImmunity):
        self.contextual_condition_immunities = update_or_concat_to_dict(self.contextual_condition_immunities, (condition_name, (immunity_name, immunity_check)))

    def remove_contextual_condition_immunity(self, condition_name: str, immunity_name: str):
        if condition_name in self.contextual_condition_immunities:
            self.contextual_condition_immunities[condition_name] = [
                (name, check) for name, check in self.contextual_condition_immunities[condition_name]
                if name != immunity_name
            ]
    def remove(self,condition_name:str, external_source:str = "manager") -> ConditionRemoved:
        condition = self.active_conditions[condition_name]
        return condition.remove_by_external(external_source)
    
    def advance_duration_condition(self,condition_name:str) -> Optional[ConditionRemoved]:
        condition = self.active_conditions[condition_name]
        return condition.advance_duration()
    
    def advance_durations(self) -> List[ConditionRemoved]:
        removed_conditions = []
        for condition_name in list(self.active_conditions.keys()):
            removed = self.advance_duration_condition(condition_name)
            if removed:
                removed_conditions.append(removed)
        return removed_conditions


class Condition(BlockComponent):
    name: str = Field(default="Condition")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    description: str = Field(default="A generic description of the condition.")
    duration: Duration = Field(default_factory=lambda: Duration(time=1, type=DurationType.ROUNDS))
    application_saving_throw: Optional[SavingThrowRollRequest] = None
    removal_saving_throw: Optional[SavingThrowRollRequest] = None
    targeted_entity_id: Optional[str] = None
    source_entity_id: Optional[str] = None
    source_ability: Optional[str] = None

    
    def _check_immunity(self, context: Optional[Dict[str, Any]] = None) -> Optional[ConditionNotApplied]:
        reason = None
        immunity_conditions = []
        if self.targeted_entity_id is None:
            raise ValueError("Targeted entity id is not set")
        stats_block = self.get_target(self.targeted_entity_id)
        if self.source_entity_id is None:
            raise ValueError("Source entity id is not set")
        source_stats_block = self.get_target(self.source_entity_id)
        if TYPE_CHECKING:
            assert isinstance(stats_block, StatsBlock)
            assert isinstance(source_stats_block, StatsBlock)
        if self.name in stats_block.condition_manager.condition_immunities.keys():
            reason = NotAppliedReason.IMMUNITY
            immunity_conditions = stats_block.condition_manager.condition_immunities[self.name]
        
        # Check for contextual condition immunity
        contextual_immunities = stats_block.condition_manager.contextual_condition_immunities.get(self.name, [])
        for immunity_name, immunity_check in contextual_immunities:
            if immunity_check(stats_block, source_stats_block, context):
                reason = NotAppliedReason.CONTEXTUAL_IMMUNITY if not reason else reason
                immunity_conditions.append(immunity_name)
        return ConditionNotApplied(
            condition=self.name,
            reason=reason,
            immunity_conditions=immunity_conditions,
            source_entity_id=self.source_entity_id if self.source_entity_id else None,
            target_entity_id=self.targeted_entity_id
        ) if reason else None
        

    def apply(self,context: Optional[Dict[str, Any]] = None)  -> Union[ConditionApplied, ConditionNotApplied]:
        # Check for condition immunity
        immune = self._check_immunity( context)
        application_saving_throw_roll = None
        if not isinstance(self.targeted_entity_id, str):
            raise ValueError("Targeted entity id is not set")
        stats_block = self.get_target(self.targeted_entity_id)
        if TYPE_CHECKING:
            assert isinstance(stats_block, StatsBlock)
        if immune:
            return immune
        elif self.application_saving_throw:
            application_saving_throw_roll = stats_block.saving_throws.perform_save_from_request(self.application_saving_throw, self.source_entity_id, context)
            if application_saving_throw_roll.success:
                return ConditionNotApplied(
                    condition=self.name,
                    reason=NotAppliedReason.SAVINGTHROW,
                    requested_saving_throw = self.application_saving_throw,
                    application_saving_throw_roll = application_saving_throw_roll,
                    source_entity_id=self.source_entity_id if self.source_entity_id else None,
                    target_entity_id=stats_block.id
                )
            else:
                applied_details = self._apply(context)
                stats_block.condition_manager.add_condition(self)
                return ConditionApplied(
                    condition=self.name,
                    details=applied_details,
                    source_entity_id=self.source_entity_id if self.source_entity_id else None,
                    target_entity_id=self.targeted_entity_id,
                    duration=self.duration,
                    requested_saving_throw=self.application_saving_throw,
                    application_saving_throw_roll=application_saving_throw_roll

                )
        else:
            applied_details = self._apply(context)
            return ConditionApplied(
                condition=self.name,
                details=applied_details,
                source_entity_id=self.source_entity_id if self.source_entity_id else None,
                target_entity_id=self.targeted_entity_id,
                duration=self.duration
            )
        # 
    def roll_removal_saving_throw(self, context: Optional[dict]= None) -> Optional[ConditionRemoved]:
        if not isinstance(self.targeted_entity_id, str):
            raise ValueError("Targeted entity id is not set")
        stats_block = self.get_target(self.targeted_entity_id)
        if TYPE_CHECKING:
            assert isinstance(stats_block, StatsBlock)
        if self.removal_saving_throw:
            removal_saving_throw =  stats_block.saving_throws.perform_save_from_request(self.removal_saving_throw,self.source_entity_id,context)
            if removal_saving_throw.success:
                details = self._remove_from_targeted()
                return ConditionRemoved(
                    condition_name=self.name,
                    removed_reason = RemovedReason.SAVED,
                    requested_saving_throw=self.removal_saving_throw,
                    removal_saving_throw_roll=removal_saving_throw,
                    details=details,
                    source_entity_id=self.source_entity_id if self.source_entity_id else None,
                    target_entity_id=self.targeted_entity_id
                )
        return None
    
    def process_expiration(self,) -> Optional[ConditionRemoved]:
        if self.duration.is_expired:
            details = self._remove_from_targeted()
            return ConditionRemoved(
                condition_name=self.name,
                removed_reason=RemovedReason.EXPIRED,
                details=details,
                source_entity_id=self.source_entity_id if self.source_entity_id else None,
                target_entity_id=self.targeted_entity_id
            )
        
    def remove_by_external(self,external_source:str) -> ConditionRemoved:
        details = self._remove_from_targeted()
        return ConditionRemoved(
            condition_name=self.name,
            removed_reason=RemovedReason.REMOVED,
            details=details,
            removed_by_source=external_source,
            source_entity_id=self.source_entity_id if self.source_entity_id else None,
            target_entity_id=self.targeted_entity_id
        )
    
    def advance_duration(self) -> Optional[ConditionRemoved]:
        if self.duration.advance():
            return self.process_expiration()
        elif self.removal_saving_throw:
            return self.roll_removal_saving_throw()
        return None
        
    def _remove_from_targeted(self) -> ConditionRemovedDetails:
        condition_removed_details = self._remove()
        if not isinstance(self.targeted_entity_id, str):
            raise ValueError("Targeted entity id is not set")
        targeted_block = self.get_target(self.targeted_entity_id)
        if TYPE_CHECKING:
            assert isinstance(targeted_block, StatsBlock)
        targeted_block.condition_manager._remove_condition_from_dicts(self.name)
        return condition_removed_details

    def _apply(self,context: Optional[Dict[str, Any]] = None)  -> ConditionAppliedDetails:
        raise NotImplementedError("Subclasses must implement this method")

    def _remove(self)  -> ConditionRemovedDetails:
        raise NotImplementedError("Subclasses must implement this method")

class Range(BaseModel):
    type: RangeType
    normal: int
    long: Optional[int] = None

    def __str__(self):
        if self.type == RangeType.REACH:
            return f"{self.normal} ft."
        elif self.type == RangeType.RANGE:
            return f"{self.normal}/{self.long} ft." if self.long else f"{self.normal} ft."


class Damage(BaseModel):
    dice: BaseRoll
    damage_bonus : ValueOut
    attack_roll: AttackRollOut 
    type: DamageType
    source: Optional[str] = None

    def roll(self) -> DamageRollOut:
        damage_advantage = self.damage_bonus.advantage_tracker.status
        if self.attack_roll.roll.hit_reason == HitReason.CRITICAL:
            dice = BaseRoll(dice_count=self.dice.dice_count*2, dice_value=self.dice.dice_value)
        else:
            dice = self.dice
        damage_roll = dice.roll(damage_advantage)
        return DamageRollOut(
            dice_roll=damage_roll,
            damage_bonus=self.damage_bonus,
            attack_roll=self.attack_roll,
            damage_type=self.type,
            source_entity_id=self.source if self.source else None,

        )
      

class Weapon(BaseModel):
    name: str
    damage_dice: int
    dice_numbers: int
    damage_bonus: ModifiableValue = Field(default_factory=lambda: ModifiableValue(
        name="weapon_damage_bonus",
        base_value=BaseValue(name="base_weapon_damage_bonus", base_value=0)
    ))
    attack_bonus: ModifiableValue = Field(default_factory=lambda: ModifiableValue(
        name="weapon_attack_bonus",
        base_value=BaseValue(name="base_weapon_attack_bonus", base_value=0)
    ))
    damage_type: DamageType
    attack_type: AttackType
    properties: List[WeaponProperty] = Field(default_factory=list)
    range: Range



class AttacksManager(BlockComponent):
    name: str = Field(default="AttacksManager")
    damage_bonus: ModifiableValue = Field(default_factory=lambda: ModifiableValue(
        name="general_damage_bonus",
        base_value=BaseValue(name="base_damage_bonus", base_value=0)
    ))
    hit_bonus: ModifiableValue = Field(default_factory=lambda: ModifiableValue(
        name="general_hit_bonus",
        base_value=BaseValue(name="base_hit_bonus", base_value=0)
    ))
    melee_hit_bonus: ModifiableValue = Field(default_factory=lambda: ModifiableValue(
        name="melee_hit_bonus",
        base_value=BaseValue(name="base_melee_hit_bonus", base_value=0)
    ))
    ranged_hit_bonus: ModifiableValue = Field(default_factory=lambda: ModifiableValue(
        name="ranged_hit_bonus",
        base_value=BaseValue(name="base_ranged_hit_bonus", base_value=0)
    ))
    spell_hit_bonus: ModifiableValue = Field(default_factory=lambda: ModifiableValue(
        name="spell_hit_bonus",
        base_value=BaseValue(name="base_spell_hit_bonus", base_value=0)
    ))
    melee_damage_bonus: ModifiableValue = Field(default_factory=lambda: ModifiableValue(
        name="melee_damage_bonus",
        base_value=BaseValue(name="base_melee_damage_bonus", base_value=0)
    ))
    ranged_damage_bonus: ModifiableValue = Field(default_factory=lambda: ModifiableValue(
        name="ranged_damage_bonus",
        base_value=BaseValue(name="base_ranged_damage_bonus", base_value=0)
    ))
    spell_damage_bonus: ModifiableValue = Field(default_factory=lambda: ModifiableValue(
        name="spell_damage_bonus",
        base_value=BaseValue(name="base_spell_damage_bonus", base_value=0)
    ))
    melee_right_hand: Optional[Weapon] = None
    melee_left_hand: Optional[Union[Weapon,Shield]] = None
    ranged_right_hand: Optional[Weapon] = None
    ranged_left_hand: Optional[Weapon] = None
    ambidextrous: bool = False
    dual_wielder: bool = False
    shield: Optional[Shield] = None

    def get_weapon(self, hand: AttackHand) -> Optional[Weapon]:
        if hand == AttackHand.MELEE_RIGHT:
            return self.melee_right_hand
        elif hand == AttackHand.MELEE_LEFT:
            left_hand = self.melee_left_hand
            if isinstance(left_hand,Shield):
                left_hand = None
            return left_hand
        elif hand == AttackHand.RANGED_RIGHT:
            return self.ranged_right_hand
        elif hand == AttackHand.RANGED_LEFT:
            return self.ranged_left_hand
        else:
            raise ValueError(f"Invalid hand {hand}")

    def _get_hit_bonuses_from_weapon(self,  hand: AttackHand, target: str, context: Optional[Dict[str, Any]] = None) -> WeaponAttackBonusOut:
        #we have to return the correct melee or ranged hit bonus from self
        # and also collect from the weapon the weapon.attack_bonus
        attacker_melee_bonus = None
        attacker_ranged_bonus = None
        weapon_melee_bonus = None
        weapon_ranged_bonus = None
        spell_bonus = None
        stast_block, target_stats_block = self.get_stats_blocks(target)
        if TYPE_CHECKING:
            assert isinstance(stast_block, StatsBlock)
            assert isinstance(target_stats_block, StatsBlock) or target_stats_block is None
        generic_hit_bonus = self.hit_bonus.apply(stast_block,target_stats_block,context)
        if hand == AttackHand.MELEE_RIGHT:
            attacker_melee_bonus= self.melee_hit_bonus.apply(stast_block,target_stats_block,context)
            if self.melee_right_hand:
                weapon_melee_bonus=self.melee_right_hand.attack_bonus.apply(stast_block,target_stats_block,context)
        elif hand == AttackHand.MELEE_LEFT:
            attacker_melee_bonus=self.melee_hit_bonus.apply(stast_block,target_stats_block,context)
            if self.melee_left_hand and not isinstance(self.melee_left_hand,Shield):
                weapon_melee_bonus=self.melee_left_hand.attack_bonus.apply(stast_block,target_stats_block,context)
        elif hand == AttackHand.RANGED_RIGHT:
            attacker_ranged_bonus=self.ranged_hit_bonus.apply(stast_block,target_stats_block,context)
            if self.ranged_right_hand:
                weapon_ranged_bonus=self.ranged_right_hand.attack_bonus.apply(stast_block,target_stats_block,context)
        elif hand == AttackHand.RANGED_LEFT:
            attacker_ranged_bonus=self.ranged_hit_bonus.apply(stast_block,target_stats_block,context)
            if self.ranged_left_hand:
                weapon_ranged_bonus=self.ranged_left_hand.attack_bonus.apply(stast_block,target_stats_block,context)
        elif hand == AttackHand.SPELL:
            spell_bonus=self.spell_hit_bonus.apply(stast_block,target_stats_block,context)

        all_bonuses = [attacker_melee_bonus,attacker_ranged_bonus,weapon_melee_bonus,weapon_ranged_bonus,spell_bonus] 
        all_bonuses  = [bonus for bonus in all_bonuses if bonus is not None]
        total_weapon_bonus = generic_hit_bonus.combine_with_multiple(all_bonuses)
        return WeaponAttackBonusOut(
            attacker_melee_bonus=attacker_melee_bonus,
            attacker_ranged_bonus=attacker_ranged_bonus,
            weapon_melee_bonus=weapon_melee_bonus,
            weapon_ranged_bonus=weapon_ranged_bonus,
            spell_bonus=spell_bonus,
            total_weapon_bonus=total_weapon_bonus
        )
    
    def _get_ability_bonus_from_weapon_for_damage(self, hand:AttackHand, target:Optional[str], context: Optional[Dict[str, Any]] = None) -> ValueOut:
        ability = self._get_ability_from_weapon(hand,target,context)
        owner_block = self.get_owner()
        if TYPE_CHECKING:
            assert isinstance(owner_block, StatsBlock)
        #checks if the hand is left and not ambidextrous
        if hand == AttackHand.MELEE_LEFT and not self.ambidextrous:
            #create a dummy ModifiableValue with 0 bonus and applies it with names: NoAbilityModifier and basevalue name NoAbilityModifier
            if target is not None:
                target_stats_block = self.get_target(target)
            else:
                target_stats_block = None
            return ModifiableValue(name="NoAbilityModifier",base_value=BaseValue(name="NoAbilityModifier",base_value=10)).apply(owner_block,target_stats_block,context)


        
        
        return owner_block.ability_scores.get_ability(ability).apply(target, context)
    
    def _get_ability_bonus_from_weapon(self, hand:AttackHand, target:Optional[str], context: Optional[Dict[str, Any]] = None) -> ValueOut:
        ability = self._get_ability_from_weapon(hand,target,context)
        owner_block = self.get_owner()
        if TYPE_CHECKING:
            assert isinstance(owner_block, StatsBlock)
        return owner_block.ability_scores.get_ability(ability).apply(target, context)
    
    def _get_ability_from_weapon(self, hand:AttackHand, target:Optional[str], context: Optional[Dict[str, Any]] = None) -> Ability:
        #check if is a spell
        ability =  Ability.STR
        owner_block = self.get_owner()
        if TYPE_CHECKING:
            assert isinstance(owner_block, StatsBlock)
        if hand == AttackHand.SPELL:
            ability = owner_block.spellcasting_ability
        weapon = self.get_weapon(hand)
        if weapon:
            if WeaponProperty.FINESSE in weapon.properties:
                dex_bonus = owner_block.ability_scores.dexterity.apply(target, context)
                str_bonus = owner_block.ability_scores.strength.apply(target, context)
                ability= Ability.DEX if dex_bonus.total_bonus >= str_bonus.total_bonus else Ability.STR
            elif WeaponProperty.RANGED in weapon.properties:
                ability =  Ability.DEX
            else:
                ability =  Ability.STR
        return ability

    def _get_attack_bonus(self, hand: AttackHand, target: str, context: Optional[Dict[str, Any]] = None) -> AttackBonusOut:
        def ability_bonus_to_modifier(ability_bonus:int) -> int:
            return (ability_bonus - 10) // 2
        stats_block,target_stats_block = self.get_stats_blocks(target)
        if TYPE_CHECKING:
            assert isinstance(stats_block, StatsBlock)
            assert isinstance(target_stats_block, StatsBlock)
        #computes the proficiency bonus
        proficiency_bonus = stats_block.proficiency_bonus.apply(stats_block,target_stats_block,context)
        #obtain the bonuses from the ac (i.e. debbufs on target)
        target_to_self_bonus = target_stats_block.armor_class.ac.apply_to_target(target_stats_block,stats_block,context)
        total_bonus = proficiency_bonus.combine_with(target_to_self_bonus)
        #get the list of bonuses from the weapon
        weapon_bonus_out = self._get_hit_bonuses_from_weapon(hand,target,context)
        total_weapon_bonus = weapon_bonus_out.total_weapon_bonus
        total_bonus = total_bonus.combine_with(total_weapon_bonus)
        #get the ability bonus
        ability_bonus = self._get_ability_bonus_from_weapon(hand,target,context)
        total_bonus = total_bonus.combine_with(ability_bonus,bonus_converter=ability_bonus_to_modifier)
        return AttackBonusOut(
            hand=hand,
            weapon_bonus=weapon_bonus_out,
            proficiency_bonus=proficiency_bonus,
            ability_bonus=ability_bonus,
            target_to_self_bonus=target_to_self_bonus,
            total_bonus=total_bonus
        )

        
    def roll_to_hit(self, hand:AttackHand, target: str, context: Optional[Dict[str, Any]] = None) -> AttackRollOut:
        owner_stats_block, target_stats_block = self.get_stats_blocks(target)
        if TYPE_CHECKING:
            assert isinstance(owner_stats_block, StatsBlock)
            assert isinstance(target_stats_block, StatsBlock)
        #first obtain ac of the target
        target_ac = target_stats_block.armor_class.ac.apply(target_stats_block,owner_stats_block,context)
        #get the attack bonus
        attack_bonus_out = self._get_attack_bonus(hand,target,context)
        #roll the dice
        roll = TargetRoll(value=attack_bonus_out.total_bonus)
        roll_out=  roll.roll(target_ac.total_bonus)
        if self.get_weapon(hand):
            weapon = self.get_weapon(hand)
            if TYPE_CHECKING:
                assert isinstance(weapon, Weapon)
            weapon_attack_type = weapon.attack_type
        else:
            weapon_attack_type = AttackType.MELEE_WEAPON

        return AttackRollOut(
            hand=hand,
            ability=self._get_ability_from_weapon(hand, target, context),
            attack_bonus=attack_bonus_out,
            roll=roll_out,
            target_ac=target_ac,
            total_target_ac=target_ac.total_bonus,
            attack_type=weapon_attack_type,
            source_entity_id=self.owner_id,
            target_entity_id=target
        )
    
    def _get_damage_bonuses_from_weapon(self, hand:AttackHand, target: str, context: Optional[Dict[str, Any]] = None) -> WeaponDamageBonusOut:
        #we have to return the correct melee or ranged damage bonus from self
        # and also collect from the weapon the weapon.attack_bonus
        attacker_melee_bonus = None
        attacker_ranged_bonus = None
        weapon_melee_bonus = None
        weapon_ranged_bonus = None
        spell_bonus = None
        stast_block, target_stats_block = self.get_stats_blocks(target)
        if TYPE_CHECKING:
            assert isinstance(stast_block, StatsBlock)
            assert isinstance(target_stats_block, StatsBlock)
        general_damage_bonus = self.damage_bonus.apply(stast_block,target_stats_block,context)
        if hand == AttackHand.MELEE_RIGHT:
            attacker_melee_bonus= self.melee_damage_bonus.apply(stast_block,target_stats_block,context)
            if self.melee_right_hand:
                weapon_melee_bonus=self.melee_right_hand.damage_bonus.apply(stast_block,target_stats_block,context)
        elif hand == AttackHand.MELEE_LEFT:
            attacker_melee_bonus=self.melee_damage_bonus.apply(stast_block,target_stats_block,context)
            if self.melee_left_hand:
                if not isinstance(self.melee_left_hand,Shield):
                    weapon_melee_bonus=self.melee_left_hand.damage_bonus.apply(stast_block,target_stats_block,context)
        elif hand == AttackHand.RANGED_RIGHT:
            attacker_ranged_bonus=self.ranged_damage_bonus.apply(stast_block,target_stats_block,context)
            if self.ranged_right_hand:
                weapon_ranged_bonus=self.ranged_right_hand.damage_bonus.apply(stast_block,target_stats_block,context)
        elif hand == AttackHand.RANGED_LEFT:
            attacker_ranged_bonus=self.ranged_damage_bonus.apply(stast_block,target_stats_block,context)
            if self.ranged_left_hand:
                weapon_ranged_bonus=self.ranged_left_hand.damage_bonus.apply(stast_block,target_stats_block,context)
        elif hand == AttackHand.SPELL:
            spell_bonus=self.spell_damage_bonus.apply(stast_block,target_stats_block,context)

        all_bonuses = [attacker_melee_bonus,attacker_ranged_bonus,weapon_melee_bonus,weapon_ranged_bonus,spell_bonus] 
        all_bonuses_typed :List[ValueOut] = [bonus for bonus in all_bonuses if bonus is not None]
        total_weapon_bonus = general_damage_bonus.combine_with_multiple(all_bonuses_typed)
        return WeaponDamageBonusOut(
            attacker_melee_bonus=attacker_melee_bonus,
            attacker_ranged_bonus=attacker_ranged_bonus,
            weapon_melee_bonus=weapon_melee_bonus,
            weapon_ranged_bonus=weapon_ranged_bonus,
            spell_bonus=spell_bonus,
            total_weapon_bonus=total_weapon_bonus
        )
    


    
    def _get_damage_bonus(self, hand:AttackHand, target: str, context: Optional[Dict[str, Any]] = None) -> DamageBonusOut:
        def ability_bonus_to_modifier(ability_bonus:int) -> int:
            return (ability_bonus - 10) // 2
        stats_block,target_stats_block = self.get_stats_blocks(target)
        #get the list of bonuses from the weapon
        weapon_bonus_out = self._get_damage_bonuses_from_weapon(hand,target,context)
        total_weapon_bonus = weapon_bonus_out.total_weapon_bonus
        #get the ability bonus
        ability_bonus = self._get_ability_bonus_from_weapon_for_damage(hand,target,context)
            
        total_bonus = total_weapon_bonus.combine_with(ability_bonus,bonus_converter=ability_bonus_to_modifier)
        return DamageBonusOut(
            hand=hand,
            weapon_bonus=weapon_bonus_out,
            ability_bonus=ability_bonus,
            total_bonus=total_bonus
        )
    
    def roll_damage(self, attack_roll:AttackRollOut, context: Optional[Dict[str, Any]] = None) -> DamageRollOut:
        hand = attack_roll.hand
        target = attack_roll.target_entity_id
        if target is None:
            raise ValueError("Target is None")
        weapon = self.get_weapon(hand)
        if not weapon:
            raise ValueError("Weapon is None")
        if not context:
            context = {}
        context['attack_roll'] = attack_roll #hack to implement modifer on damage bonus that depends on the attack roll like on critical hit effect
        bonus = self._get_damage_bonus(hand,target,context)
        damage = Damage(
            dice=BaseRoll(dice_count=weapon.dice_numbers,dice_value=weapon.damage_dice),
            damage_bonus=bonus.total_bonus,
            attack_roll=attack_roll,
            type=weapon.damage_type,
            source=self.owner_id,
        )
        return damage.roll()

    def can_dual_wield_melee(self, weapon: Weapon,hand:str='left') -> bool:
        if  WeaponProperty.TWO_HANDED  in weapon.properties:
            return False
        elif not self.dual_wielder and WeaponProperty.LIGHT not in weapon.properties:
            #if not dual wielder and weapon is not light it can't be dual wielded
            return False
        elif not self.dual_wielder and hand == 'left' and WeaponProperty.LIGHT in weapon.properties:
            #not dual wielder but the weapon is light and it is the left hand
            if self.melee_right_hand and WeaponProperty.LIGHT not in self.melee_right_hand.properties:
                #the right hand already has an not light weapon
                return False
            elif self.melee_right_hand and WeaponProperty.LIGHT in self.melee_right_hand.properties:
                #the right hand already has a light weapon so it can dual wield
                return True
            elif not self.melee_right_hand:
                return True
        elif not self.dual_wielder and hand == 'right':
            #not dual wielder so there either is no weapon in the left hand or the weapon in the left hand is light
            if self.melee_left_hand and WeaponProperty.LIGHT not in weapon.properties:
                #you can't dual wield a non light weapon even in the right hand
                return False
            elif self.melee_left_hand and WeaponProperty.LIGHT in weapon.properties:
                return True
            elif not self.melee_left_hand:
                return True
        elif self.dual_wielder:
            if hand == 'left' and self.melee_right_hand and WeaponProperty.TWO_HANDED in self.melee_right_hand.properties:
                return False
            else:
                return True
        return False

            
        
    def can_dual_wield_ranged(self, weapon: Weapon,hand:str='left') -> bool:
        if WeaponProperty.TWO_HANDED in weapon.properties:
            return False
        elif not self.dual_wielder and hand == 'left' and WeaponProperty.LIGHT not in weapon.properties:
            #if not dual wielder and weapon is not light it can't be dual wielded same for two handed weapons
            return False
        elif not self.dual_wielder and hand == 'left' and WeaponProperty.LIGHT in weapon.properties:
            #not dual wielder but the weapon is light and it is the left hand
            if self.ranged_right_hand and WeaponProperty.LIGHT not in self.ranged_right_hand.properties:
                #the right hand already has an not light weapon
                return False
            elif self.ranged_right_hand and WeaponProperty.LIGHT in self.ranged_right_hand.properties:
                #the right hand already has a light weapon so it can dual wield
                return True
            elif not self.ranged_right_hand:
                return True
        elif not self.dual_wielder and hand == 'right':
            #not dual wielder so there either is no weapon in the left hand or the weapon in the left hand is light
            if self.ranged_left_hand and WeaponProperty.LIGHT not in weapon.properties:
                #you can't dual wield a non light weapon even in the right hand
                return False
            elif self.ranged_left_hand and WeaponProperty.LIGHT in weapon.properties:
                return True
            elif not self.ranged_left_hand:
                return True
        elif self.dual_wielder:
            if hand == 'left' and self.ranged_right_hand and WeaponProperty.TWO_HANDED in self.ranged_right_hand.properties:
                return False
            else:
                return True
        return False
    def equip_right_hand_ranged_weapon(self, weapon: Weapon):
        if not WeaponProperty.RANGED in weapon.properties :
            raise ValueError("The weapon is not a ranged weapon")
        if WeaponProperty.TWO_HANDED in weapon.properties:
            self.unequip_left_hand_ranged_weapon()
            self.unequip_right_hand_ranged_weapon()
            self.ranged_right_hand = weapon
        elif self.can_dual_wield_ranged(weapon,hand='right'):
            ranged = True
            self.unequip_right_hand_ranged_weapon()
            self.ranged_right_hand = weapon
        else:
            raise ValueError("The weapon can't be equipped in the right hand")

    def equip_left_hand_ranged_weapon(self, weapon: Weapon):
        if not WeaponProperty.RANGED in weapon.properties:
            raise ValueError("The weapon is not a ranged weapon")
        if self.can_dual_wield_ranged(weapon,hand='left'):
            self.unequip_left_hand_ranged_weapon()
            self.ranged_left_hand = weapon
        else:
            raise ValueError("The weapon can't be equipped in the left hand")
    
        
    def equip_right_hand_melee_weapon(self,weapon:Weapon):
        if WeaponProperty.RANGED in weapon.properties:
            raise ValueError("The weapon is not a melee weapon")
        if WeaponProperty.TWO_HANDED in weapon.properties:
            self.unequip_left_hand_melee_weapon()
            self.unequip_right_hand_melee_weapon()
            self.unequip_shield()
            self.melee_right_hand = weapon
        elif self.can_dual_wield_melee(weapon,hand='right'):
            self.unequip_right_hand_melee_weapon()
            self.melee_right_hand = weapon
        elif not self.can_dual_wield_melee(weapon,hand='right'):
            self.unequip_left_hand_melee_weapon()
            self.melee_right_hand = weapon
        else:
            raise ValueError("The weapon can't be equipped in the right hand")
        
    def equip_left_hand_melee_weapon(self, weapon: Weapon):
        if WeaponProperty.RANGED in weapon.properties:
            raise ValueError("The weapon is not a melee weapon")
        if self.can_dual_wield_melee(weapon,hand='left'):
            self.unequip_left_hand_melee_weapon()
            self.unequip_shield()
            self.melee_left_hand = weapon
        else:
            raise ValueError("The weapon can't be equipped in the left hand")
    
    def _update_shield_ac_state(self, shield: Optional[Shield]):
        owner_stats_block = self.get_owner()
        if TYPE_CHECKING:
            assert isinstance(owner_stats_block, StatsBlock)
        if owner_stats_block.armor_class.equipped_shield and not shield:
            owner_stats_block.armor_class.unequip_shield()
        elif shield:
            owner_stats_block.armor_class.equip_shield(shield)
        

    def equip_shield(self, shield: Shield):
        if TYPE_CHECKING:
            assert self.melee_right_hand is not None
        if WeaponProperty.TWO_HANDED in self.melee_right_hand.properties:
            self.unequip_right_hand_melee_weapon()
            self.shield = shield
            self._update_shield_ac_state(shield)
        else:
            self.unequip_left_hand_melee_weapon()
            self.shield = shield
            self._update_shield_ac_state(shield)
    
    def unequip_shield(self):
        self.shield = None
        self._update_shield_ac_state(None)

    def unequip_right_hand_melee_weapon(self):
        self.melee_right_hand = None

    def unequip_left_hand_melee_weapon(self):
        self.melee_left_hand = None
    
    def unequip_right_hand_ranged_weapon(self):
        self.ranged_right_hand = None

    def unequip_left_hand_ranged_weapon(self):
        self.ranged_left_hand = None
    
    