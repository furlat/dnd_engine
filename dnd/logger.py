from typing import Dict, Any, Type, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime, timedelta
from collections import OrderedDict
import uuid
from enum import Enum
from dnd.dnd_enums import AdvantageStatus, DamageType,Ability, Skills, AdvantageStatus, ActionType, AttackType, DamageType, SensesType


class BaseLogEntry(BaseModel):
    log_type: str = Field(default="BaseLogEntry")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    log_type: str
    entity_id: Optional[str] = None

class ContextualEffectLog(BaseLogEntry):
    log_type: str = Field(default="ContextualEffect")
    effect_type: str
    applied: bool
    value: Optional[int] = None

class DiceRollLog(BaseLogEntry):
    log_type: str = "DiceRoll"
    dice_count: int
    dice_value: int
    modifier: int
    advantage_status: AdvantageStatus
    rolls: List[int]
    total: int
    critical_status: str
    auto_critical: bool = False
    auto_hit: bool = False

class DamageRollLog(BaseLogEntry):
    log_type: str = "DamageRoll"
    damage_type: DamageType
    dice_roll: DiceRollLog
    total_damage: int

class ModifiableValueLog(BaseLogEntry):
    log_type: str = Field(default="ModifiableValue")
    base_value: int
    static_modifiers: Dict[str, int]
    self_effects: List[ContextualEffectLog]
    target_effects: List[ContextualEffectLog]
    advantage_status: AdvantageStatus
    final_value: int
    min_constraint: Optional[int] = None
    max_constraint: Optional[int] = None
    auto_fail: bool = False
    auto_success: bool = False
    auto_critical: bool = False

class ContextualEffectsLog(BaseLogEntry):
    log_type: str = Field(default="ContextualEffects")
    bonuses: List[ContextualEffectLog]
    advantage_conditions: List[ContextualEffectLog]
    disadvantage_conditions: List[ContextualEffectLog]
    auto_fail_conditions: List[ContextualEffectLog]
    auto_success_conditions: List[ContextualEffectLog]
    min_constraints: List[ContextualEffectLog]
    max_constraints: List[ContextualEffectLog]
    auto_critical_conditions: List[ContextualEffectLog]



class EffectTargetType(str, Enum):
    ABILITY_SCORE = "ability_score"
    SKILL = "skill"
    SAVING_THROW = "saving_throw"
    ATTACK = "attack"
    DAMAGE = "damage"
    ARMOR_CLASS = "armor_class"
    SPEED = "speed"
    ACTION_ECONOMY = "action_economy"
    SENSES = "senses"

class EffectTarget(BaseModel):
    target_type: EffectTargetType
    ability: Optional[Ability] = None
    skill: Optional[Skills] = None
    attack_type: Optional[AttackType] = None
    damage_type: Optional[DamageType] = None
    action_type: Optional[ActionType] = None
    sense_type: Optional[SensesType] = None

class EffectType(str, Enum):
    ADVANTAGE = "advantage"
    DISADVANTAGE = "disadvantage"
    AUTO_FAIL = "auto_fail"
    AUTO_SUCCESS = "auto_success"
    AUTO_CRITICAL = "auto_critical"
    MODIFIER = "modifier"
    SET_VALUE = "set_value"
    MAX_VALUE = "max_value"
    MIN_VALUE = "min_value"

class ConditionEffect(BaseModel):
    target: EffectTarget
    effect_type: EffectType
    value: Optional[int] = None
    advantage_status: Optional[AdvantageStatus] = None

class ConditionLog(BaseLogEntry):
    log_type: str = "Condition"
    condition_name: str
    applied: bool
    source_id: Optional[str]
    target_id: str
    duration: Optional[int]
    effects: List[ConditionEffect] = Field(default_factory=list)
    immunity_reason: Optional[str] = None

class HealthLog(BaseLogEntry):
    log_type: str = "Health"
    current_hp: int
    max_hp: int
    temporary_hp: int
    damage_taken: Optional[int] = None
    healing_received: Optional[int] = None
    source_id: Optional[str] = None
    damage_type: Optional[DamageType] = None

class ActionResultDetails(BaseModel):
    hit: Optional[bool] = None
    damage_dealt: Optional[int] = None
    target_hp_before: Optional[int] = None
    target_hp_after: Optional[int] = None
    attack_roll: Optional[int] = None
    attack_bonus: Optional[int] = None
    advantage_status: Optional[AdvantageStatus] = None
    target_ac: Optional[int] = None
    saving_throw_ability: Optional[str] = None
    saving_throw_dc: Optional[int] = None
    saving_throw_roll: Optional[int] = None
    saving_throw_bonus: Optional[int] = None
    conditions_applied: List[str] = Field(default_factory=list)
    movement: Optional[Dict[str, Any]] = None
    failure_reason: Optional[str] = None
    auto_success: bool = False
    auto_failure: bool = False
    auto_critical: bool = False

class PrerequisiteDetails(BaseModel):
    distance: Optional[int] = None
    required_range: Optional[int] = None
    is_visible: Optional[bool] = None
    failure_reason: Optional[str] = None

class PrerequisiteLog(BaseLogEntry):
    log_type: str = "Prerequisite"
    condition_name: str
    passed: bool
    source_id: str
    target_id: Optional[str]
    details: PrerequisiteDetails = Field(default_factory=PrerequisiteDetails)

class ActionLog(BaseLogEntry):
    log_type: str = "Action"
    action_name: str
    source_id: str
    target_id: Optional[str]
    success: bool
    prerequisite_logs: List[PrerequisiteLog]
    dice_rolls: List[DiceRollLog] = Field(default_factory=list)
    damage_rolls: List[DamageRollLog] = Field(default_factory=list)
    details: ActionResultDetails = Field(default_factory=ActionResultDetails)


class SkillCheckLog(BaseLogEntry):
    log_type: str = "SkillCheck"
    skill: Skills
    ability: Ability
    dc: int
    source_id: str
    target_id: Optional[str]
    roll_log : Optional[DiceRollLog]
    roll: int
    total: int
    bonus: int
    
    advantage_status: AdvantageStatus
    success: bool
    auto_success: bool = False
    auto_fail: bool = False

class SavingThrowLog(BaseLogEntry):
    log_type: str = "SavingThrow"
    ability: Ability
    dc: int
    source_id: str
    target_id: Optional[str]
    roll_log : Optional[DiceRollLog]
    roll: int
    total: int
    bonus: int
    advantage_status: AdvantageStatus
    success: bool
    auto_success: bool = False
    auto_fail: bool = False


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

