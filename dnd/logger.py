from typing import Dict, Any, Type, List, Optional, Union, Tuple
from pydantic import BaseModel, Field, computed_field
from datetime import datetime, timedelta
from collections import OrderedDict
import uuid
from enum import Enum
from dnd.dnd_enums import AttackHand,RemovedReason,DurationType,NotAppliedReason,ResistanceStatus,AdvantageStatus,AutoHitStatus,CriticalStatus, DamageType,Ability, Skills, AdvantageStatus, ActionType, AttackType, DamageType, SensesType
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
        if min_bonus and max_bonus:
            return max(min_bonus, min(bonus, max_bonus))
        elif min_bonus:
            return max(min_bonus, bonus)
        elif max_bonus:
            return min(max_bonus, bonus)
        else:
            return bonus


    def combine_with(self, other: 'ValueOut',bonus_converter: Optional[BonusConverter] = None) -> 'ValueOut':
        
        new_bonuses = self.bonuses.combine_with(other.bonuses,bonus_converter = bonus_converter)
        new_min =self.min_constraints.combine_with(other.min_constraints,bonus_converter = bonus_converter)
        new_max = self.max_constraints.combine_with(other.max_constraints,bonus_converter = bonus_converter)
        new_advantage= self.advantage_tracker.combine_with(other.advantage_tracker)
        new_critical = self.critical_tracker.combine_with(other.critical_tracker)
        new_auto_hit = self.auto_hit_tracker.combine_with(other.auto_hit_tracker)
        return ValueOut(bonuses=new_bonuses,
                                     min_constraints=new_min, 
                                     max_constraints=new_max, 
                                     advantage_tracker=new_advantage, 
                                     critical_tracker=new_critical, 
                                     auto_hit_tracker=new_auto_hit,
                                     source_entity_id=self.source_entity_id if self.source_entity_id else other.source_entity_id,
                                     target_entity_id=self.target_entity_id if self.target_entity_id else other.target_entity_id)
    
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
    hit : RollOutcome
    hit_reason : HitReason = Field(default=HitReason.NORMAL)
    critical_reason : Optional[CriticalReason] = Field(default=None)

    @computed_field
    def total_roll(self) -> int:
        return self.base_roll.result + self.bonus.total_bonus
    @computed_field
    def success(self) -> bool:
        return self.hit == RollOutcome.HIT or self.hit == RollOutcome.CRIT



class SkillBonusOut(BaseLogEntry):
    log_type: str = "SkillBonus"
    skill: Skills
    proficiency_bonus: ValueOut
    ability_bonus: ValueOut
    skill_bonus: ValueOut
    total_bonus: ValueOut
    target_to_self_bonus: Optional[ValueOut] = None

class SkillRollOut(BaseLogEntry):
    log_type: str = "SkillRoll"
    skill: Skills
    ability: Ability
    skill_proficient: bool
    skill_expert: bool
    dc: int
    roll: TargetRollOut
    bonus: SkillBonusOut 

    @computed_field
    def success(self) -> bool:
        return self.roll.success
    
    @computed_field
    def total_roll(self) -> int:
        return self.roll.total_roll


   
class CrossSkillRollOut(BaseLogEntry):
    log_type: str = "CrossSkillRoll"
    source_skill: Skills
    target_skill: Skills
    target_skill_roll: SkillRollOut
    source_skill_roll: SkillRollOut

    @computed_field
    def success(self) -> bool:
        return self.source_skill_roll.success
    @computed_field
    def dc(self) -> int:
        return self.target_skill_roll.total_roll if not self.target_skill_roll.roll.hit_reason == HitReason.AUTOMISS else 0


class SavingThrowBonusOut(BaseLogEntry):
    log_type: str = "SavingThrowBonus"
    ability : Ability
    proficiency_bonus: ValueOut
    ability_bonus: ValueOut
    saving_throw_bonus: ValueOut
    total_bonus: ValueOut
    target_to_self_bonus: Optional[ValueOut] = None

class SavingThrowRollOut(BaseLogEntry):
    log_type: str = "SavingThrowRoll"
    ability: Ability
    proficient: bool
    dc: int
    roll: TargetRollOut
    bonus: SavingThrowBonusOut 

    @computed_field
    def success(self) -> bool:
        return self.roll.success
    
    @computed_field
    def total_roll(self) -> int:
        return self.roll.total_roll



    
class DamageResistanceOut(BaseLogEntry):
    log_type: str = "DamageResistancOut"
    damage_roll: 'DamageRollOut'
    resistance_status: ResistanceStatus

    def compute_damage_multiplier(self) -> float:
        if self.resistance_status == ResistanceStatus.RESISTANCE:
            return 0.5
        elif self.resistance_status == ResistanceStatus.IMMUNITY:
            return 0
        elif self.resistance_status == ResistanceStatus.VULNERABILITY:
            return 2
        else:
            return 1
        
    @computed_field
    def total_damage_taken(self) -> int:
        return int(self.damage_roll.total_damage * self.compute_damage_multiplier())
    
    @computed_field
    def resistance_delta(self) -> int:
        return int(self.damage_roll.total_damage - self.total_damage_taken)

class HealthSnapshot(BaseLogEntry):
    log_type: str = "HealthSnapshot"
    damage_taken: int
    max_hit_points: int
    temporary_hit_points: int

    @computed_field
    def current_hitpoints(self) -> int:
        return self.max_hit_points - self.damage_taken
    
class DamageTakenLog(BaseLogEntry):
    log_type: str = "HealthChange"
    health_before : HealthSnapshot
    health_after : HealthSnapshot
    damage_calculations : List[DamageResistanceOut]
    hp_damage: int
    temp_hp_damage: int
    is_dead : bool = False
    flat_damage_reduction: int
    flat_damage_reduction_bonus: ValueOut

    @computed_field
    def total_damage(self) -> int:
        return self.hp_damage + self.temp_hp_damage
    
class HealingTakenLog(BaseLogEntry):
    log_type: str = "HealthChange"
    health_before : HealthSnapshot
    health_after : HealthSnapshot
    healing_received: int

class SavingThrowRollRequest(BaseLogEntry):
    log_type: str = "SavingThrowRollRequest"
    ability: Ability
    dc: int

class Duration(BaseModel):
    time: Union[int, str]
    concentration: bool = False
    type: DurationType = Field(DurationType.ROUNDS, description="The type of duration for the effect")
    has_advanced: bool = False

    def advance(self) -> bool:
        if self.type in [DurationType.ROUNDS, DurationType.MINUTES, DurationType.HOURS]:
            if isinstance(self.time, int):
                self.time -= 1
                return self.time <= 0
        return False

    def is_expired(self) -> bool:
        return self.type != DurationType.INDEFINITE and (
            (isinstance(self.time, int) and self.time <= 0) or 
            (isinstance(self.time, str) and self.time.lower() == "expired")
        )


class ConditionNotApplied(BaseLogEntry):
    log_type: str = "ConditionNotApplied"
    condition: str
    reason: NotAppliedReason
    immunity_conditions: Optional[List[str]] = None
    requested_saving_throw : Optional[SavingThrowRollRequest] = None
    application_saving_throw_roll: Optional[SavingThrowRollOut] = None
    source_entity_id: Optional[str] = None
    target_entity_id: str

class ConditionAppliedDetails(BaseModel):
    condition_name: str
    source_entity_id: Optional[str] = None
    source_ability: Optional[str] = None

class ConditionApplied(BaseLogEntry):
    log_type: str = "ConditionApplied"
    condition: str
    source_entity_id: Optional[str] = None
    target_entity_id: str
    duration: Duration
    requested_saving_throw : Optional[SavingThrowRollRequest] = None
    application_saving_throw_roll: Optional[SavingThrowRollOut] = None
    details: ConditionAppliedDetails




class ConditionRemovedDetails(BaseModel):
    details :str

class ConditionRemoved(BaseLogEntry):
    log_type: str = "ConditionRemoved"
    condition_name: str
    removed_reason: RemovedReason
    details: Optional[ConditionRemovedDetails] = None
    requested_saving_throw : Optional[SavingThrowRollRequest] = None
    removal_saving_throw_roll: Optional[SavingThrowRollOut] = None
    removed_by_source: Optional[str] = None

class WeaponAttackBonusOut(BaseLogEntry):
    log_type: str = "WeaponattackBonus"
    total_weapon_bonus: ValueOut
    attacker_melee_bonus: Optional[ValueOut] = None
    attacker_ranged_bonus: Optional[ValueOut] = None
    weapon_melee_bonus: Optional[ValueOut] = None
    weapon_ranged_bonus: Optional[ValueOut] = None
    spell_bonus: Optional[ValueOut] = None

class WeaponDamageBonusOut(BaseLogEntry):
    log_type: str = "WeaponDamageBonus"
    total_weapon_bonus: ValueOut
    attacker_melee_bonus: Optional[ValueOut] = None
    attacker_ranged_bonus: Optional[ValueOut] = None
    weapon_melee_bonus: Optional[ValueOut] = None
    weapon_ranged_bonus: Optional[ValueOut] = None
    spell_bonus: Optional[ValueOut] = None

class DamageBonusOut(BaseLogEntry):
    log_type: str = "DamageBonus"
    hand : AttackHand
    weapon_bonus: WeaponDamageBonusOut
    ability_bonus: ValueOut
    total_bonus: ValueOut

class DamageRollOut(BaseLogEntry):
    log_type: str = "DamageRoll"
    damage_type: DamageType
    dice_roll: SimpleRollOut
    attack_roll: TargetRollOut
    damage_bonus: ValueOut

    @computed_field
    def total_damage(self) -> int:
        return self.dice_roll.result + self.damage_bonus.total_bonus

class AttackBonusOut(BaseLogEntry):
    log_type: str = "AttackBonus"
    hand: AttackHand
    weapon_bonus: WeaponAttackBonusOut
    proficiency_bonus: ValueOut
    ability_bonus: ValueOut
    total_bonus: ValueOut
    target_to_self_bonus: Optional[ValueOut] = None

class AttackRollOut(BaseLogEntry):
    log_type: str = "AttackRoll"
    hand: AttackHand
    ability: Ability
    attack_type: AttackType
    target_ac: ValueOut
    total_target_ac: int
    roll: TargetRollOut
    attack_bonus: AttackBonusOut 

    @computed_field
    def success(self) -> bool:
        return self.roll.success
    
    @computed_field
    def total_roll(self) -> int:
        return self.roll.total_roll




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
    



