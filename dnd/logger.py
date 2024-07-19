from typing import Dict, Any, Type, List, Optional, Union, Tuple
from pydantic import BaseModel, Field, computed_field
from datetime import datetime, timedelta
from collections import OrderedDict
import uuid
from enum import Enum
from dnd.dnd_enums import ResistanceStatus,AdvantageStatus,AutoHitStatus,CriticalStatus, DamageType,Ability, Skills, AdvantageStatus, ActionType, AttackType, DamageType, SensesType
from dnd.utils import update_or_concat_to_dict, update_or_sum_to_dict
from dnd.trackers import BonusTracker, BonusConverter,AdvantageTracker, CriticalTracker, AutoHitTracker


class BaseLogEntry(BaseModel):
    log_type: str = Field(default="BaseLogEntry")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    log_type: str
    source_entity_id: Optional[str] = None
    target_entity_id: Optional[str] = None

class Logger:
    _logs: OrderedDict[str, BaseLogEntry] = OrderedDict()
    _timestamp_to_id: Dict[datetime, List[str]] = {}
    _type_to_id: Dict[str, List[str]] = {}

    @classmethod
    def log(cls, log_entry: BaseLogEntry) -> BaseLogEntry:
        cls._add_log_entry(log_entry)
        return log_entry

    @classmethod
    def _add_log_entry(cls, log_entry: BaseLogEntry):
        cls._logs[log_entry.id] = log_entry
        cls._timestamp_to_id.setdefault(log_entry.timestamp, []).append(log_entry.id)
        cls._type_to_id.setdefault(log_entry.log_type, []).append(log_entry.id)

    @classmethod
    def get_logs(cls, 
                 start_time: Optional[datetime] = None, 
                 end_time: Optional[datetime] = None, 
                 log_type: Optional[str] = None, 
                 limit: Optional[int] = None) -> List[BaseLogEntry]:
        
        if log_type:
            log_ids = set(cls._type_to_id.get(log_type, []))
        else:
            log_ids = set(cls._logs.keys())

        if start_time:
            start_ids = set(id for t in cls._timestamp_to_id.keys() if t >= start_time for id in cls._timestamp_to_id[t])
            log_ids &= start_ids

        if end_time:
            end_ids = set(id for t in cls._timestamp_to_id.keys() if t <= end_time for id in cls._timestamp_to_id[t])
            log_ids &= end_ids

        sorted_logs = [log for log in cls._logs.values() if log.id in log_ids]
        sorted_logs.sort(key=lambda x: x.timestamp, reverse=True)

        return sorted_logs[:limit] if limit else sorted_logs

    @classmethod
    def get_logs_in_last(cls, delta: timedelta, log_type: Optional[str] = None, limit: Optional[int] = None) -> List[BaseLogEntry]:
        end_time = datetime.utcnow()
        start_time = end_time - delta
        return cls.get_logs(start_time=start_time, end_time=end_time, log_type=log_type, limit=limit)

    @classmethod
    def pop_logs(cls, 
                 start_time: Optional[datetime] = None, 
                 end_time: Optional[datetime] = None, 
                 log_type: Optional[str] = None, 
                 limit: Optional[int] = None) -> List[BaseLogEntry]:
        
        logs = cls.get_logs(start_time, end_time, log_type, limit)
        
        for log in logs:
            cls._logs.pop(log.id, None)
            cls._timestamp_to_id[log.timestamp].remove(log.id)
            if not cls._timestamp_to_id[log.timestamp]:
                del cls._timestamp_to_id[log.timestamp]
            cls._type_to_id[log.log_type].remove(log.id)
            if not cls._type_to_id[log.log_type]:
                del cls._type_to_id[log.log_type]

        return logs

    @classmethod
    def clear_logs(cls):
        cls._logs.clear()
        cls._timestamp_to_id.clear()
        cls._type_to_id.clear()



## classes to support ContextualLog




class ValueOut(BaseLogEntry):
    log_type: str = Field(default="ValueOut")
    bonuses: BonusTracker = Field(default_factory=BonusTracker)
    min_constraints: BonusTracker = Field(default_factory=BonusTracker)
    max_constraints: BonusTracker = Field(default_factory=BonusTracker)
    advantage_tracker: AdvantageTracker = Field(default_factory=AdvantageTracker)
    critical_tracker: CriticalTracker = Field(default_factory=CriticalTracker)
    auto_hit_tracker: AutoHitTracker = Field(default_factory=AutoHitTracker)

    @computed_field
    def total_bonus(self) -> int:
        bonus = self.bonuses.total_bonus
        min_bonus = self.min_constraints.total_bonus
        max_bonus = self.max_constraints.total_bonus
        #rule is that min bonus has priority over max bonus then so first take min(bonus, max_bonus) and then max(min_bonus, min(bonus, max_bonus))
        return max(min_bonus, min(bonus, max_bonus))


    def combine_with(self, other: 'ValueOut',bonus_converter: Optional[BonusConverter] = None) -> 'ValueOut':
        
        new_bonuses = self.bonuses.combine_with(other.bonuses,bonus_convter = bonus_converter)
        new_min =self.min_constraints.combine_with(other.min_constraints,bonus_convter = bonus_converter)
        new_max = self.max_constraints.combine_with(other.max_constraints,bonus_convter = bonus_converter)
        new_advantage= self.advantage_tracker.combine_with(other.advantage_tracker)
        new_critical = self.critical_tracker.combine_with(other.critical_tracker)
        new_auto_hit = self.auto_hit_tracker.combine_with(other.auto_hit_tracker)
        return ValueOut(bonuses=new_bonuses,
                                     min_constraints=new_min, 
                                     max_constraints=new_max, 
                                     advantage_tracker=new_advantage, 
                                     critical_tracker=new_critical, 
                                     auto_hit_tracker=new_auto_hit)
    
    def combine_with_multiple(self, others: List['ValueOut']) -> 'ValueOut':
        combined = self
        for other in others:
            combined = combined.combine_with(other)
        return combined
    
    



class SimpleRollOut(BaseLogEntry):
    log_type: str = "SimpleRoll"
    dice_count: int
    dice_value: int
    advantage_status: AdvantageStatus = AdvantageStatus.NONE
    all_rolls: List[Union[int,Tuple[int,int]]]
    chosen_rolls: List[int]

    @computed_field
    def result(self) -> int:
        return sum(self.chosen_rolls)
    
class RollOutcome(str, Enum):
    HIT = "Hit"
    MISS = "Miss"
    CRIT = "Critical Hit"

class HitReason(str, Enum):
    NORMAL = "Normal"
    CRITICAL = "Critical"
    AUTOHIT = "AutoHit"
    AUTOMISS = "AutoMiss"

class CriticalReason(str, Enum):
    NORMAL = "Normal"
    AUTO = "Auto"

class TargetRollOut(BaseLogEntry):
    log_type: str = "TargetRoll"
    bonus: ValueOut
    target: int
    base_roll: SimpleRollOut
    hit = RollOutcome
    hit_reason = HitReason = Field(default=HitReason.NORMAL)
    critical_reason = Optional[CriticalReason] = Field(default=None)

    def total_roll(self) -> int:
        return self.base_roll.result + self.bonus.total_bonus
    def success(self) -> bool:
        return self.hit == RollOutcome.HIT or self.hit == RollOutcome.CRIT


class DamageRollOut(BaseLogEntry):
    log_type: str = "DamageRoll"
    damage_type: DamageType
    dice_roll: SimpleRollOut
    attack_roll: TargetRollOut
    damage_bonus: ValueOut

    @computed_field
    def total_damage(self) -> int:
        return self.dice_roll.result + self.damage_bonus.total_bonus

class SkillRollOut(BaseLogEntry):
    log_type: str = "SkillRoll"
    skill: Skills
    ability: Ability
    skill_proficient: bool
    skill_expert: bool
    dc: int
    roll: TargetRollOut
    proficiency_bonus: ValueOut
    ability_bonus: ValueOut
    skill_bonus: ValueOut
    target_skill_bonus: Optional[ValueOut] = None


# class DiceRollLog(BaseLogEntry):
#     log_type: str = "DiceRoll"
#     base_roll: SimpleRollLog
#     modifier: ModifiableValueLog
    
#     @computed_field
#     def total_roll(self) -> int:
#         return int(self.base_roll.result + self.modifier.final_value)
#     @computed_field
#     def is_critical_hit(self, target:Optional[int]=None) -> bool:
#         if self.modifier.advantage.critical_status == CriticalStatus.NOCRIT or self.base_roll.dice_value != 20 or self.base_roll.base_dice_count != 1:
#             return False
#         elif self.modifier.advantage.critical_status == CriticalStatus.AUTOCRIT :
#             if target and self.modifier.advantage.auto_hit_status == AutoHitStatus.NONE:
#                 return self.base_roll.result >= target
#             elif target and self.modifier.advantage.auto_hit_status == AutoHitStatus.AUTOHIT:
#                 return True
#             elif target and self.modifier.advantage.auto_hit_status == AutoHitStatus.AUTOMISS:
#                 return False
#             return True 
#         else:
#             return self.base_roll.result == 20
#     @computed_field
#     def is_hit(self, target:Optional[int]=None) -> bool:
#         if self.modifier.advantage.auto_hit_status == AutoHitStatus.NONE:
#             return self.total_roll >= target and self.base_roll.result != 1
#         elif self.modifier.advantage.auto_hit_status == AutoHitStatus.AUTOHIT:
#             return True
#         elif self.modifier.advantage.auto_hit_status == AutoHitStatus.AUTOMISS:
#             return False
#         else:
#             raise ValueError("Invalid AutoHitStatus")



# class DamageRollLog(BaseLogEntry):
#     log_type: str = "DamageRoll"
#     damage_type: DamageType
#     dice_roll: DiceRollLog
#     @computed_field
#     def damage_rolled(self) -> int:
#         return self.dice_roll.total_roll

# class DamageLog(BaseLogEntry):
#     log_type: str = "Damage"
#     damage_rolls: List[DamageRollLog]

#     @computed_field
#     def total_damage(self) -> int:
#         return sum([damage.dice_roll.total_roll for damage in self.damage_rolls])




# class DamageResistanceCalculation(BaseLogEntry):
#     log_type: str = "HealthChangeCalculation"
#     damage_roll: DamageRollLog
#     resistance_status: ResistanceStatus

#     def compute_damage_multiplier(self) -> float:
#         if self.resistance_status == ResistanceStatus.RESISTANCE:
#             return 0.5
#         elif self.resistance_status == ResistanceStatus.IMMUNITY:
#             return 0
#         elif self.resistance_status == ResistanceStatus.VULNERABILITY:
#             return 2
#         else:
#             return 1
#     @computed_field
#     def total_damage_taken(self) -> int:
#         return int(self.damage_roll.damage_rolled * self.compute_damage_multiplier())
    
#     @computed_field
#     def resistance_delta(self) -> int:
#         return int(self.damage_roll.damage_rolled - self.total_damage_taken)

# class HealthSnapshot(BaseLogEntry):
#     log_type: str = "HealthSnapshot"
#     current_hp: int
#     max_hp: int
#     temp_hp: int
#     bonus_hp: int

# class DamageTakenLog(BaseLogEntry):
#     log_type: str = "HealthChange"
#     health_before : HealthSnapshot
#     health_after : HealthSnapshot
#     damage_calculations : List[DamageResistanceCalculation]
#     hp_damage: int
#     temp_hp_damage: int
#     bonus_hp_damage: int

#     @computed_field
#     def total_damage(self) -> int:
#         return self.hp_damage + self.temp_hp_damage + self.bonus_hp_damage


# class HealingTakenLog(BaseLogEntry):
#     log_type: str = "HealthChange"
#     health_before : HealthSnapshot
#     health_after : HealthSnapshot
#     healing_received: int


# class ContextualEffectsLog(BaseLogEntry):
#     log_type: str = Field(default="ContextualEffects")
#     bonuses: List[ContextualEffectLog]
#     advantage_conditions: List[ContextualEffectLog]
#     disadvantage_conditions: List[ContextualEffectLog]
#     auto_fail_conditions: List[ContextualEffectLog]
#     auto_success_conditions: List[ContextualEffectLog]
#     min_constraints: List[ContextualEffectLog]
#     max_constraints: List[ContextualEffectLog]
#     auto_critical_conditions: List[ContextualEffectLog]



# class EffectTargetType(str, Enum):
#     ABILITY_SCORE = "ability_score"
#     SKILL = "skill"
#     SAVING_THROW = "saving_throw"
#     ATTACK = "attack"
#     DAMAGE = "damage"
#     ARMOR_CLASS = "armor_class"
#     SPEED = "speed"
#     ACTION_ECONOMY = "action_economy"
#     SENSES = "senses"

# class EffectTarget(BaseModel):
#     target_type: EffectTargetType
#     ability: Optional[Ability] = None
#     skill: Optional[Skills] = None
#     attack_type: Optional[AttackType] = None
#     damage_type: Optional[DamageType] = None
#     action_type: Optional[ActionType] = None
#     sense_type: Optional[SensesType] = None

# class EffectType(str, Enum):
#     ADVANTAGE = "advantage"
#     DISADVANTAGE = "disadvantage"
#     AUTO_FAIL = "auto_fail"
#     AUTO_SUCCESS = "auto_success"
#     AUTO_CRITICAL = "auto_critical"
#     MODIFIER = "modifier"
#     SET_VALUE = "set_value"
#     MAX_VALUE = "max_value"
#     MIN_VALUE = "min_value"

# class ConditionEffect(BaseModel):
#     target: EffectTarget
#     effect_type: EffectType
#     value: Optional[int] = None
#     advantage_status: Optional[AdvantageStatus] = None

# class ConditionLog(BaseLogEntry):
#     log_type: str = "Condition"
#     condition_name: str
#     applied: bool
#     source_id: Optional[str]
#     target_id: str
#     effects: List[ConditionEffect] = Field(default_factory=list)
#     immunity_reason: Optional[str] = None

# class HealthLog(BaseLogEntry):
#     log_type: str = "Health"
#     current_hp: int
#     max_hp: int
#     temporary_hp: int
#     damage_taken: Optional[int] = None
#     healing_received: Optional[int] = None
#     source_id: Optional[str] = None
#     damage_type: Optional[DamageType] = None

# class ActionResultDetails(BaseModel):
#     hit: Optional[bool] = None
#     damage_dealt: Optional[int] = None
#     target_hp_before: Optional[int] = None
#     target_hp_after: Optional[int] = None
#     attack_roll: Optional[int] = None
#     attack_bonus: Optional[int] = None
#     advantage_status: Optional[AdvantageStatus] = None
#     target_ac: Optional[int] = None
#     saving_throw_ability: Optional[str] = None
#     saving_throw_dc: Optional[int] = None
#     saving_throw_roll: Optional[int] = None
#     saving_throw_bonus: Optional[int] = None
#     conditions_applied: List[str] = Field(default_factory=list)
#     movement: Optional[Dict[str, Any]] = None
#     failure_reason: Optional[str] = None
#     auto_success: bool = False
#     auto_failure: bool = False
#     auto_critical: bool = False

# class PrerequisiteDetails(BaseModel):
#     distance: Optional[int] = None
#     required_range: Optional[int] = None
#     is_visible: Optional[bool] = None
#     failure_reason: Optional[str] = None

# class PrerequisiteLog(BaseLogEntry):
#     log_type: str = "Prerequisite"
#     condition_name: str
#     passed: bool
#     source_id: str
#     target_id: Optional[str]
#     details: PrerequisiteDetails = Field(default_factory=PrerequisiteDetails)

# class ActionLog(BaseLogEntry):
#     log_type: str = "Action"
#     action_name: str
#     source_id: str
#     target_id: Optional[str]
#     success: bool
#     prerequisite_logs: List[PrerequisiteLog]
#     dice_rolls: List[DiceRollLog] = Field(default_factory=list)
#     damage_rolls: List[DamageRollLog] = Field(default_factory=list)
#     details: ActionResultDetails = Field(default_factory=ActionResultDetails)


# class SkillCheckLog(BaseLogEntry):
#     log_type: str = "SkillCheck"
#     skill: Skills
#     ability: Ability
#     dc: int
#     source_id: str
#     target_id: Optional[str]
#     roll_log : Optional[DiceRollLog]
#     roll: int
#     total: int
#     bonus: int
    
#     advantage_status: AdvantageStatus
#     success: bool
#     auto_success: bool = False
#     auto_fail: bool = False

# class SavingThrowLog(BaseLogEntry):
#     log_type: str = "SavingThrow"
#     ability: Ability
#     dc: int
#     source_id: str
#     target_id: Optional[str]
#     roll_log : Optional[DiceRollLog]
#     roll: int
#     total: int
#     bonus: int
#     advantage_status: AdvantageStatus
#     success: bool
#     auto_success: bool = False
#     auto_fail: bool = False


# class ConditionInfo(BaseModel):
#     condition_name: str
#     affected_entity_id: str
#     source_entity_id: Optional[str] = None
#     source_ability: Optional[str] = None
#     duration: Optional[int] = None

# class EffectSource(BaseModel):
#     source_type: SourceType
#     responsible_entity_id: str
#     condition_info: Optional[ConditionInfo] = None
#     ability_name: Optional[str] = None
#     item_name: Optional[str] = None
#     description: str

# class AdvantageSource(BaseModel):
#     effect_source: EffectSource
#     description: str

# DisadvantageSource = AdvantageSource

# class Modifier(BaseModel):
#     value: int
#     effect_source: EffectSource

# class DiceRollLog(BaseLogEntry):
#     log_type: str = "DiceRoll"
#     dice_size: int
#     roll_results: List[int]
#     modifiers: List[Modifier]
#     advantage_status: AdvantageStatus
#     advantage_sources: List[AdvantageSource]
#     disadvantage_sources: List[DisadvantageSource]
#     total_roll: int
#     is_critical: bool = False
#     is_critical_miss: bool = False
#     is_auto_critical: bool = False
#     auto_success: bool = False
#     auto_failure: bool = False

# class HitRollLog(BaseLogEntry):
#     log_type: str = "HitRoll"
#     dice_roll: DiceRollLog
#     target_ac: int
#     is_hit: bool
#     auto_hit_source: Optional[EffectSource] = None
#     auto_miss_source: Optional[EffectSource] = None
#     auto_critical_source: Optional[EffectSource] = None

# class DamageRollLog(BaseLogEntry):
#     log_type: str = "DamageRoll"
#     damage_type: DamageType
#     dice_roll: DiceRollLog

# class DamageLog(BaseLogEntry):
#     log_type: str = "Damage"
#     damage_rolls: List[DamageRollLog]
#     total_damage_by_type: Dict[DamageType, int]
#     final_damage: int

# class DamageTypeEffect(BaseModel):
#     damage_type: DamageType
#     effect_source: EffectSource

# class HealthChangeLog(BaseLogEntry):
#     log_type: str = "HealthChange"
#     target_max_hp: int
#     target_previous_hp: int
#     target_previous_temp_hp: int
#     damage_taken: int
#     temp_hp_absorbed: int
#     resistances_applied: List[DamageTypeEffect]
#     vulnerabilities_applied: List[DamageTypeEffect]
#     immunities_applied: List[DamageTypeEffect]
#     target_current_hp: int
#     target_current_temp_hp: int

# class AttackResult(str, Enum):
#     HIT = "Hit"
#     MISS = "Miss"
#     CRITICAL_HIT = "Critical Hit"




# class AttackLog(BaseLogEntry):
#     log_type: str = "Attack"
#     source_entity_id: str
#     target_entity_id: str
#     weapon_name: str
#     attack_type: AttackType
#     attacker_conditions: List[ConditionInfo]
#     target_conditions: List[ConditionInfo]
#     hit_roll_log: HitRollLog
#     damage_log: Optional[DamageLog] = None
#     health_change_log: Optional[HealthChangeLog] = None
#     final_result: AttackResult

#     def generate_log_string(self) -> str:
#         log_parts = []
        
#         # Basic attack information
#         log_parts.append(f"{self.source_entity_id} attacks {self.target_entity_id} with {self.weapon_name} ({self.attack_type.value}).")
        
#         # Conditions
#         if self.attacker_conditions:
#             attacker_conditions = ", ".join([c.condition_name for c in self.attacker_conditions])
#             log_parts.append(f"Attacker conditions: {attacker_conditions}")
#         if self.target_conditions:
#             target_conditions = ", ".join([c.condition_name for c in self.target_conditions])
#             log_parts.append(f"Target conditions: {target_conditions}")
        
#         # Hit roll
#         hit_roll = self.hit_roll_log
#         dice_roll = hit_roll.dice_roll
#         advantage_str = f"Roll with {dice_roll.advantage_status.value}:" if dice_roll.advantage_status != AdvantageStatus.NONE else "Roll:"
#         rolls_str = ", ".join([str(r) for r in dice_roll.roll_results])
#         log_parts.append(f"{advantage_str} {rolls_str}")
        
#         if dice_roll.modifiers:
#             modifiers_str = ", ".join([f"{m.value} ({m.effect_source.description})" for m in dice_roll.modifiers])
#             log_parts.append(f"Modifiers: {modifiers_str}")
        
#         log_parts.append(f"Total: {dice_roll.total_roll} vs. AC {hit_roll.target_ac}")
#         log_parts.append(f"Result: {self.final_result.value}")
        
#         # Damage (if hit)
#         if self.damage_log:
#             damage_parts = []
#             for roll in self.damage_log.damage_rolls:
#                 dice_rolls = ", ".join([str(d) for d in roll.dice_roll.roll_results])
#                 damage_parts.append(f"{roll.damage_type.value}: {dice_rolls} = {roll.dice_roll.total_roll}")
#             log_parts.append(f"Damage rolls: {'; '.join(damage_parts)}")
#             log_parts.append(f"Total damage: {self.damage_log.final_damage}")
        
#         # Health change
#         if self.health_change_log:
#             hc = self.health_change_log
#             log_parts.append(f"Target HP: {hc.target_previous_hp} -> {hc.target_current_hp}")
#             if hc.temp_hp_absorbed:
#                 log_parts.append(f"Temp HP absorbed: {hc.temp_hp_absorbed}")
#             if hc.resistances_applied:
#                 resistances = ", ".join([f"{r.damage_type.value} ({r.effect_source.description})" for r in hc.resistances_applied])
#                 log_parts.append(f"Resistances applied: {resistances}")
#             if hc.vulnerabilities_applied:
#                 vulnerabilities = ", ".join([f"{v.damage_type.value} ({v.effect_source.description})" for v in hc.vulnerabilities_applied])
#                 log_parts.append(f"Vulnerabilities applied: {vulnerabilities}")
#             if hc.immunities_applied:
#                 immunities = ", ".join([f"{i.damage_type.value} ({i.effect_source.description})" for i in hc.immunities_applied])
#                 log_parts.append(f"Immunities applied: {immunities}")
        
#         return " ".join(log_parts)
    



