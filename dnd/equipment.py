from typing import List, Optional, Callable, TYPE_CHECKING, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum
from dnd.contextual import ModifiableValue, ContextualEffects, ContextAwareBonus, ContextAwareCondition
from dnd.dnd_enums import ArmorType, WeaponProperty
if TYPE_CHECKING:
    from dnd.statsblock import StatsBlock
    from dnd.core import AbilityScores
    from dnd.actions import AttackType, Range, Damage



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



class Weapon(BaseModel):
    name: str
    damage: 'Damage'
    attack_type: 'AttackType'
    properties: List[WeaponProperty]
    range: 'Range'

class ArmorClass(BaseModel):
    base_ac: ModifiableValue = Field(default_factory=lambda: ModifiableValue(base_value=10))
    equipped_armor: Optional[Armor] = None
    equipped_shield: Optional[Shield] = None

    def compute_base_ac(self, ability_scores: 'AbilityScores') -> int:
        base_ac = 10 + ability_scores.dexterity.get_modifier(None)
        if self.equipped_armor:
            base_ac = self.equipped_armor.base_ac
            if self.equipped_armor.dex_bonus:
                dex_bonus = ability_scores.dexterity.get_modifier(None)
                if self.equipped_armor.max_dex_bonus is not None:
                    dex_bonus = min(dex_bonus, self.equipped_armor.max_dex_bonus)
                base_ac += dex_bonus
        if self.equipped_shield:
            base_ac += self.equipped_shield.ac_bonus
        
        self.base_ac.base_value = base_ac
        return self.base_ac.base_value

    def get_value(self, stats_block: 'StatsBlock', attacker: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None) -> int:
        return self.base_ac.get_value(stats_block, attacker, context)

    def gives_attacker_advantage(self, stats_block: 'StatsBlock', attacker: 'StatsBlock', context: Optional[Dict[str, Any]] = None) -> bool:
        return self.base_ac.target_effects.has_advantage(attacker, stats_block, context)

    def gives_attacker_disadvantage(self, stats_block: 'StatsBlock', attacker: 'StatsBlock', context: Optional[Dict[str, Any]] = None) -> bool:
        return self.base_ac.target_effects.has_disadvantage(attacker, stats_block, context)

    def gives_attacker_auto_fail(self, stats_block: 'StatsBlock', attacker: 'StatsBlock', context: Optional[Dict[str, Any]] = None) -> bool:
        return self.base_ac.causes_auto_fail(stats_block, attacker, context)

    def gives_attacker_auto_success(self, stats_block: 'StatsBlock', attacker: 'StatsBlock', context: Optional[Dict[str, Any]] = None) -> bool:
        return self.base_ac.causes_auto_success(stats_block, attacker, context)
    
    def gives_attacker_auto_critical(self, stats_block: 'StatsBlock', attacker: 'StatsBlock', context: Optional[Dict[str, Any]] = None) -> bool:
        return self.base_ac.causes_auto_critical(stats_block, attacker, context)

    def add_opponent_auto_critical_condition(self, source: str, condition: ContextAwareCondition):
        self.base_ac.target_effects.add_auto_critical_self_condition(source, condition)

    def remove_opponent_auto_critical_condition(self, source: str):
        self.base_ac.target_effects.remove_effect(source)

    def add_self_bonus(self, source: str, bonus: ContextAwareBonus):
        self.base_ac.self_effects.add_bonus(source, bonus)

    def add_opponent_bonus(self, source: str, bonus: ContextAwareBonus):
        self.base_ac.target_effects.add_bonus(source, bonus)

    def add_self_advantage_condition(self, source: str, condition: ContextAwareCondition):
        self.base_ac.self_effects.add_advantage_condition(source, condition)

    def add_opponent_advantage_condition(self, source: str, condition: ContextAwareCondition):
        self.base_ac.target_effects.add_advantage_condition(source, condition)

    def add_self_disadvantage_condition(self, source: str, condition: ContextAwareCondition):
        self.base_ac.self_effects.add_disadvantage_condition(source, condition)

    def add_opponent_disadvantage_condition(self, source: str, condition: ContextAwareCondition):
        self.base_ac.target_effects.add_disadvantage_condition(source, condition)

    def add_opponent_auto_fail_condition(self, source: str, condition: ContextAwareCondition):
        self.base_ac.target_effects.add_auto_fail_self_condition(source, condition)

    def add_opponent_auto_success_condition(self, source: str, condition: ContextAwareCondition):
        self.base_ac.target_effects.add_auto_success_self_condition(source, condition)

    def remove_self_bonus(self, source: str):
        self.base_ac.self_effects.remove_effect(source)

    def remove_opponent_bonus(self, source: str):
        self.base_ac.target_effects.remove_effect(source)

    def remove_self_advantage_condition(self, source: str):
        self.base_ac.self_effects.remove_effect(source)

    def remove_opponent_advantage_condition(self, source: str):
        self.base_ac.target_effects.remove_effect(source)

    def remove_self_disadvantage_condition(self, source: str):
        self.base_ac.self_effects.remove_effect(source)

    def remove_opponent_disadvantage_condition(self, source: str):
        self.base_ac.target_effects.remove_effect(source)

    def remove_opponent_auto_fail_condition(self, source: str):
        self.base_ac.target_effects.remove_effect(source)

    def remove_opponent_auto_success_condition(self, source: str):
        self.base_ac.target_effects.remove_effect(source)

    def remove_all_effects(self, source: str):
        self.base_ac.self_effects.remove_effect(source)
        self.base_ac.target_effects.remove_effect(source)

    def equip_armor(self, armor: Armor, ability_scores: 'AbilityScores'):
        self.equipped_armor = armor
        self.compute_base_ac(ability_scores)

    def unequip_armor(self, ability_scores: 'AbilityScores'):
        self.equipped_armor = None
        self.compute_base_ac(ability_scores)

    def equip_shield(self, shield: Shield, ability_scores: 'AbilityScores'):
        self.equipped_shield = shield
        self.compute_base_ac(ability_scores)

    def unequip_shield(self, ability_scores: 'AbilityScores'):
        self.equipped_shield = None
        self.compute_base_ac(ability_scores)