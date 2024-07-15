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
from dnd.dnd_enums import Ability, Skills, SensesType, ActionType, RechargeType, UsageType, DurationType, RangeType, TargetType, ShapeType, TargetRequirementType, DamageType

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
    modifier: int
    advantage_status: AdvantageStatus = AdvantageStatus.NONE
    allow_critical: bool = True

    def expected_value(self):
        base_average = self.dice_count * (self.dice_value + 1) / 2 + self.modifier
        if self.advantage_status == AdvantageStatus.ADVANTAGE:
            advantage_average = (self.dice_value + 1) * (2 * self.dice_value + 1) / (3 * self.dice_value)
            return self.dice_count * advantage_average + self.modifier
        if self.advantage_status == AdvantageStatus.DISADVANTAGE:
            disadvantage_average = self.dice_value * (self.dice_value + 1) / (3 * self.dice_value)
            return self.dice_count * disadvantage_average + self.modifier
        return int(base_average)

    def roll_with_advantage(self) -> Tuple[int, str]:
        if self.advantage_status == AdvantageStatus.ADVANTAGE:
            rolls = [self.roll_single(), self.roll_single()]
            best_roll = max(rolls)
        elif self.advantage_status == AdvantageStatus.DISADVANTAGE:
            rolls = [self.roll_single(), self.roll_single()]
            best_roll = min(rolls)
        else:
            rolls = [self.roll_single()]
            best_roll = rolls[0]

        if self.allow_critical:
            if best_roll - self.modifier == 20:
                return best_roll, "critical_hit"
            elif best_roll - self.modifier == 1:
                return best_roll, "critical_failure"
        return best_roll, "normal"

    def roll_single(self) -> int:
        return sum(random.randint(1, self.dice_value) for _ in range(self.dice_count)) + self.modifier

    def roll(self, is_critical: bool = False) -> int:
        if is_critical:
            return sum(random.randint(1, self.dice_value) for _ in range(self.dice_count * 2)) + self.modifier
        return self.roll_single()


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

    def perform_check(self, stats_block: 'StatsBlock', dc: int, target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None, return_roll: bool = False) -> Union[bool, Tuple[int, int]]:
        print(f"Performing {self.ability.value} skill check")
        
        if self.bonus.is_auto_fail(stats_block, target, context):
            print(f"Auto-fail condition met for {self.skill.value} check")
            return (1, 1) if return_roll else False
        
        if self.bonus.is_auto_success(stats_block, target, context):
            print(f"Auto-success condition met for {self.skill.value} check")
            return (20, 20) if return_roll else True

        bonus = self.get_bonus(stats_block, target, context)
        
        # Create a combined AdvantageTracker
        advantage_tracker = AdvantageTracker()
        self.bonus.self_effects.apply_advantage_disadvantage(stats_block, target, advantage_tracker, context)
        if target:
            #get the skill of the target
            target_skill = target.skills.get_skill(self.skill)
            target_skill.bonus.target_effects.apply_advantage_disadvantage(target, stats_block, advantage_tracker, context)
        
        advantage_status = advantage_tracker.status
        
        print(f"Bonus: {bonus}, Advantage status: {advantage_status}")
        dice = Dice(dice_count=1, dice_value=20, modifier=bonus, advantage_status=advantage_status)
        roll, _ = dice.roll_with_advantage()
        total = roll + bonus
        print(f"Roll: {roll}, Total: {total}, DC: {dc}")
        if return_roll:
            return roll, total
        return total >= dc
    
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

    def perform_skill_check(self, skill: Skills, stats_block: 'StatsBlock', dc: int, target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None) -> bool:
        return self.get_skill(skill).perform_check(stats_block, dc, target, context)


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
    
    def perform_save(self, stats_block: 'StatsBlock', dc: int, target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None) -> bool:
        if self.bonus.is_auto_fail(stats_block, target, context):
            print(f"Auto-fail condition met for {self.ability.value} saving throw")
            return False
        
        if self.bonus.is_auto_success(stats_block, target, context):
            print(f"Auto-success condition met for {self.ability.value} saving throw")
            return True

        bonus = self.get_bonus(stats_block, target, context)
        # Create a combined AdvantageTracker
        advantage_tracker = AdvantageTracker()
        self.bonus.self_effects.apply_advantage_disadvantage(stats_block, target, advantage_tracker, context)
        if target:
            #get the skill of the target
            target_skill = target.saving_throws.get_ability(self.ability)
            target_skill.bonus.target_effects.apply_advantage_disadvantage(target, stats_block, advantage_tracker, context)
        
        advantage_status = advantage_tracker.status

        dice = Dice(dice_count=1, dice_value=20, modifier=bonus, advantage_status=advantage_status)
        roll, _ = dice.roll_with_advantage()
        total = roll + bonus
        print(f"Saving Throw: {self.ability.value}, Roll: {roll}, Total: {total}, DC: {dc}")
        return total >= dc

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

    def perform_save(self, ability: Ability, stats_block: 'StatsBlock', dc: int, target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None) -> bool:
        return self.get_ability(ability).perform_save(stats_block, dc, target, context)



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