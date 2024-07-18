from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from datetime import datetime
import uuid
from dnd.dnd_enums import (AdvantageStatus, AttackType, DamageType, Ability, SourceType)
from enum import Enum

class BaseLogEntry(BaseModel):
    log_type: str = Field(default="BaseLogEntry")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    entity_id: Optional[str] = None

class ConditionInfo(BaseModel):
    condition_name: str
    affected_entity_id: str
    source_entity_id: Optional[str] = None
    source_ability: Optional[str] = None
    duration: Optional[int] = None

class EffectSource(BaseModel):
    source_type: SourceType
    responsible_entity_id: str
    condition_info: Optional[ConditionInfo] = None
    ability_name: Optional[str] = None
    item_name: Optional[str] = None
    description: str

class AdvantageSource(BaseModel):
    effect_source: EffectSource
    description: str

DisadvantageSource = AdvantageSource

class Modifier(BaseModel):
    value: int
    effect_source: EffectSource

class DiceRollLog(BaseLogEntry):
    log_type: str = "DiceRoll"
    dice_size: int
    roll_results: List[int]
    modifiers: List[Modifier]
    advantage_status: AdvantageStatus
    advantage_sources: List[AdvantageSource]
    disadvantage_sources: List[DisadvantageSource]
    total_roll: int
    is_critical: bool = False
    is_critical_miss: bool = False
    is_auto_critical: bool = False
    auto_success: bool = False
    auto_failure: bool = False

class HitRollLog(BaseLogEntry):
    log_type: str = "HitRoll"
    dice_roll: DiceRollLog
    target_ac: int
    is_hit: bool
    auto_hit_source: Optional[EffectSource] = None
    auto_miss_source: Optional[EffectSource] = None
    auto_critical_source: Optional[EffectSource] = None

class DamageRollLog(BaseLogEntry):
    log_type: str = "DamageRoll"
    damage_type: DamageType
    dice_roll: DiceRollLog

class DamageLog(BaseLogEntry):
    log_type: str = "Damage"
    damage_rolls: List[DamageRollLog]
    total_damage_by_type: Dict[DamageType, int]
    final_damage: int

class DamageTypeEffect(BaseModel):
    damage_type: DamageType
    effect_source: EffectSource

class HealthChangeLog(BaseLogEntry):
    log_type: str = "HealthChange"
    target_max_hp: int
    target_previous_hp: int
    target_previous_temp_hp: int
    damage_taken: int
    temp_hp_absorbed: int
    resistances_applied: List[DamageTypeEffect]
    vulnerabilities_applied: List[DamageTypeEffect]
    immunities_applied: List[DamageTypeEffect]
    target_current_hp: int
    target_current_temp_hp: int

class AttackResult(str, Enum):
    HIT = "Hit"
    MISS = "Miss"
    CRITICAL_HIT = "Critical Hit"




class AttackLog(BaseLogEntry):
    log_type: str = "Attack"
    source_entity_id: str
    target_entity_id: str
    weapon_name: str
    attack_type: AttackType
    attacker_conditions: List[ConditionInfo]
    target_conditions: List[ConditionInfo]
    hit_roll_log: HitRollLog
    damage_log: Optional[DamageLog] = None
    health_change_log: Optional[HealthChangeLog] = None
    final_result: AttackResult

    def generate_log_string(self) -> str:
        log_parts = []
        
        # Basic attack information
        log_parts.append(f"{self.source_entity_id} attacks {self.target_entity_id} with {self.weapon_name} ({self.attack_type.value}).")
        
        # Conditions
        if self.attacker_conditions:
            attacker_conditions = ", ".join([c.condition_name for c in self.attacker_conditions])
            log_parts.append(f"Attacker conditions: {attacker_conditions}")
        if self.target_conditions:
            target_conditions = ", ".join([c.condition_name for c in self.target_conditions])
            log_parts.append(f"Target conditions: {target_conditions}")
        
        # Hit roll
        hit_roll = self.hit_roll_log
        dice_roll = hit_roll.dice_roll
        advantage_str = f"Roll with {dice_roll.advantage_status.value}:" if dice_roll.advantage_status != AdvantageStatus.NONE else "Roll:"
        rolls_str = ", ".join([str(r) for r in dice_roll.roll_results])
        log_parts.append(f"{advantage_str} {rolls_str}")
        
        if dice_roll.modifiers:
            modifiers_str = ", ".join([f"{m.value} ({m.effect_source.description})" for m in dice_roll.modifiers])
            log_parts.append(f"Modifiers: {modifiers_str}")
        
        log_parts.append(f"Total: {dice_roll.total_roll} vs. AC {hit_roll.target_ac}")
        log_parts.append(f"Result: {self.final_result.value}")
        
        # Damage (if hit)
        if self.damage_log:
            damage_parts = []
            for roll in self.damage_log.damage_rolls:
                dice_rolls = ", ".join([str(d) for d in roll.dice_roll.roll_results])
                damage_parts.append(f"{roll.damage_type.value}: {dice_rolls} = {roll.dice_roll.total_roll}")
            log_parts.append(f"Damage rolls: {'; '.join(damage_parts)}")
            log_parts.append(f"Total damage: {self.damage_log.final_damage}")
        
        # Health change
        if self.health_change_log:
            hc = self.health_change_log
            log_parts.append(f"Target HP: {hc.target_previous_hp} -> {hc.target_current_hp}")
            if hc.temp_hp_absorbed:
                log_parts.append(f"Temp HP absorbed: {hc.temp_hp_absorbed}")
            if hc.resistances_applied:
                resistances = ", ".join([f"{r.damage_type.value} ({r.effect_source.description})" for r in hc.resistances_applied])
                log_parts.append(f"Resistances applied: {resistances}")
            if hc.vulnerabilities_applied:
                vulnerabilities = ", ".join([f"{v.damage_type.value} ({v.effect_source.description})" for v in hc.vulnerabilities_applied])
                log_parts.append(f"Vulnerabilities applied: {vulnerabilities}")
            if hc.immunities_applied:
                immunities = ", ".join([f"{i.damage_type.value} ({i.effect_source.description})" for i in hc.immunities_applied])
                log_parts.append(f"Immunities applied: {immunities}")
        
        return " ".join(log_parts)
    
