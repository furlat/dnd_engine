from typing import Dict, Any, Callable, List, Tuple, TYPE_CHECKING, Optional
from pydantic import BaseModel, Field, computed_field
from enum import Enum
from dnd.dnd_enums import AdvantageStatus, CriticalStatus, AutoHitStatus
from dnd.logger import ModifiableValueLog, ValueOut, AdvantageTracker, AutoHitTracker, CriticalTracker,BonusTracker
from dnd.utils import update_or_concat_to_dict, update_or_sum_to_dict

if TYPE_CHECKING:
    from dnd.statsblock import StatsBlock

ContextAwareCondition = Callable[['StatsBlock', Optional['StatsBlock'], Optional[Dict[str, Any]]], bool]
ContextAwareAdvantage = Callable[['StatsBlock', Optional['StatsBlock'], Optional[Dict[str, Any]]], AdvantageStatus]
ContextAwareCritical = Callable[['StatsBlock', Optional['StatsBlock'], Optional[Dict[str, Any]]], CriticalStatus]
ContextAwareAutoHit = Callable[['StatsBlock', Optional['StatsBlock'], Optional[Dict[str, Any]]], AutoHitStatus]
ContextAwareBonus = Callable[['StatsBlock', Optional['StatsBlock'], Optional[Dict[str, Any]]], int]

class BaseValue(BaseModel):
    name:str = Field(default="base")
    base_value: int = Field(default=0)
    min_value: Optional[int] = Field(default=None)
    max_value: Optional[int] = Field(default=None)
    advantage : AdvantageStatus = Field(default=AdvantageStatus.NONE)
    auto_hit: AutoHitStatus = Field(default=AutoHitStatus.NONE)
    critical: CriticalStatus = Field(default=CriticalStatus.NONE)

    def apply(self) -> ValueOut:
        return ValueOut(
            bonuses=BonusTracker(bonuses={self.name: self.base_value}),
            min_constraints=BonusTracker(bonuses={self.name: self.min_value}) if self.min_value is not None else None,
            max_constraints=BonusTracker(bonuses={self.name: self.max_value}) if self.max_value is not None else None,
            advantage_tracker=AdvantageTracker(active_sources={self.name: self.advantage}),
            auto_hit_tracker=AutoHitTracker(auto_hit_statuses={self.name: self.auto_hit}),
            critical_tracker=CriticalTracker(critical_statuses={self.name: self.critical})
        )


class StaticModifier(BaseModel):
    bonuses: Dict[str, int] = Field(default_factory=dict)
    min_constraints: Dict[str, int] = Field(default_factory=dict)
    max_constraints: Dict[str, int] = Field(default_factory=dict)
    advantage_conditions: Dict[str, AdvantageStatus] = Field(default_factory=dict)
    auto_hit_conditions: Dict[str, AutoHitStatus] = Field(default_factory=dict)
    critical_conditions: Dict[str, CriticalStatus] = Field(default_factory=dict)

    def add_bonus(self, source: str, value: int):
        self.bonuses.update([source, value])
    def add_min_constraint(self, source: str, value: int):
        self.min_constraints.update([source, value])
    def add_max_constraint(self, source: str, value: int):
        self.max_constraints.update([source, value])
    def add_critical_condition(self, source: str, condition: CriticalStatus):
        self.critical_conditions.update([source, condition])
    def add_advantage_condition(self, source: str, condition: AdvantageStatus):
        self.advantage_conditions.update([source, condition])
    def add_auto_hit_condition(self, source: str, condition: AutoHitStatus):
        self.auto_hit_conditions.update([source, condition])
    def get_bonus_tracker(self) -> BonusTracker:
        return BonusTracker(bonuses=self.bonuses)
    def get_min_value_tracker(self) -> BonusTracker:
        return BonusTracker(bonuses=self.min_constraints)
    def get_max_value_tracker(self) -> BonusTracker:
        return BonusTracker(bonuses=self.max_constraints)
    def get_advantage_tracker(self) -> AdvantageTracker:
        return AdvantageTracker(active_sources=self.advantage_conditions)
    def get_auto_hit_tracker(self) -> AutoHitTracker:
        return AutoHitTracker(auto_hit_statuses=self.auto_hit_conditions)
    def get_critical_tracker(self) -> CriticalTracker:
        return CriticalTracker(critical_statuses=self.critical_conditions)
    def remove_effect(self, source: str):
        self.bonuses.pop(source, None)
        self.min_constraints.pop(source, None)
        self.max_constraints.pop(source, None)
        self.advantage_conditions.pop(source, None)
        self.auto_hit_conditions.pop(source, None)
        self.critical_conditions.pop(source, None)

    def apply(self) -> ValueOut:
        return ValueOut(
            bonuses=self.get_bonus_tracker(),
            min_constraints=self.get_min_value_tracker(),
            max_constraints=self.get_max_value_tracker(),
            advantage_tracker=self.get_advantage_tracker(),
            auto_hit_tracker=self.get_auto_hit_tracker(),
            critical_tracker=self.get_critical_tracker()
        )

class ContextualModifier(BaseModel):
    bonuses: Dict[str, ContextAwareBonus] = Field(default_factory=dict)
    min_constraints: Dict[str, ContextAwareBonus] = Field(default_factory=dict)
    max_constraints: Dict[str, ContextAwareBonus] = Field(default_factory=dict)
    advantage_conditions: Dict[str, ContextAwareAdvantage] = Field(default_factory=dict)
    auto_hit_conditions: Dict[str, ContextAwareAutoHit] = Field(default_factory=dict)
    critical_conditions: Dict[str, ContextAwareCritical] = Field(default_factory=dict)


    def add_bonus(self, source: str, bonus: ContextAwareBonus):
        self.bonuses.update([source, bonus])

    def add_min_constraint(self, source: str, constraint: ContextAwareBonus):
        self.min_constraints.update([source, constraint])

    def add_max_constraint(self, source: str, constraint: ContextAwareBonus):
        self.max_constraints.update([source, constraint])

    def add_critical_condition(self, source: str, condition: ContextAwareCritical):
        self.critical_conditions.update([source, condition])
    
    def add_advantage_condition(self, source: str, condition: ContextAwareCondition):
        self.advantage_conditions.update([source, condition])

    def add_auto_hit_condition(self, source: str, condition: ContextAwareCondition):
        self.auto_hit_conditions.update([source, condition])

    def get_bonus_tracker(self, stats_block: 'StatsBlock', target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None) -> BonusTracker:
        bonuses = {}
        for source, bonus in self.bonuses.items():
            value = bonus(stats_block, target, context)
            bonuses = update_or_sum_to_dict(bonuses, (source, value))
        return BonusTracker(bonuses=bonuses)
    
    def get_min_value_tracker(self, stats_block: 'StatsBlock', target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None) -> BonusTracker:
        min_values = {}
        for source, constraint in self.min_constraints.items():
            value = constraint(stats_block, target, context)
            min_values = update_or_sum_to_dict(min_values, (source, value))
        return BonusTracker(bonuses=min_values)
    
    def get_max_value_tracker(self, stats_block: 'StatsBlock', target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None) -> BonusTracker:
        max_values = {}
        for source, constraint in self.max_constraints.items():
            value = constraint(stats_block, target, context)
            max_values = update_or_sum_to_dict(max_values, (source, value))
        return BonusTracker(bonuses=max_values)
    
    def get_advantage_tracker(self, stats_block: 'StatsBlock', target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None) -> AdvantageTracker:
        active_advantage_status= {}
        for source, condition in self.advantage_conditions.items():
            status = condition(stats_block, target, context)
            active_advantage_status = update_or_concat_to_dict(active_advantage_status, (source, status))
        return AdvantageTracker(active_sources=active_advantage_status)
    
    def get_auto_hit_tracker(self, stats_block: 'StatsBlock', target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None) -> AutoHitTracker:
        active_auto_hit_status= {}
        for source, condition in self.auto_hit_conditions.items():
            status = condition(stats_block, target, context)
            active_auto_hit_status = update_or_concat_to_dict(active_auto_hit_status, (source, status))
        return AutoHitTracker(auto_hit_statuses=active_auto_hit_status)

    def get_critical_tracker(self, stats_block: 'StatsBlock', target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None) -> CriticalStatus:
        active_critical_status= {}
        for source, condition in self.critical_conditions.items():
            status = condition(stats_block, target, context)
            active_critical_status = update_or_concat_to_dict(active_critical_status, (source, status))
        return CriticalTracker(critical_statuses=active_critical_status)

    def remove_effect(self, source: str):
        self.bonuses.pop(source, None)
        self.min_constraints.pop(source, None)
        self.max_constraints.pop(source, None)
        self.advantage_conditions.pop(source, None)
        self.auto_hit_conditions.pop(source, None)
        self.critical_conditions.pop(source, None)

    def apply(self, stats_block: 'StatsBlock', target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None) -> ValueOut:
        return ValueOut(
            bonuses=self.get_bonus_tracker(stats_block, target, context),
            min_constraints=self.get_min_value_tracker(stats_block, target, context),
            max_constraints=self.get_max_value_tracker(stats_block, target, context),
            advantage_tracker=self.get_advantage_tracker(stats_block, target, context),
            auto_hit_tracker=self.get_auto_hit_tracker(stats_block, target, context),
            critical_tracker=self.get_critical_tracker(stats_block, target, context)
        )


class ModifiableValue(BaseModel):
    base_value: BaseValue = Field(default_factory=BaseValue)
    self_static: StaticModifier = Field(default_factory=StaticModifier)
    target_static: StaticModifier = Field(default_factory=StaticModifier)
    self_contextual: ContextualModifier = Field(default_factory=ContextualModifier)
    target_contextual: ContextualModifier = Field(default_factory=ContextualModifier)

    def apply(self, stats_block: 'StatsBlock', target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None) -> ValueOut:
        base_out = self.base_value.apply()
        static_out = self.self_static.apply()
        contextual_out = self.self_contextual.apply(stats_block, target, context)
        return base_out.combine_with_multiple([static_out, contextual_out])
    
    def apply_to_target(self, stats_block: 'StatsBlock', target: 'StatsBlock', context: Optional[Dict[str, Any]] = None) -> ValueOut:
        target_static_out = self.target_static.apply()
        target_contextual_out = self.target_contextual.apply(stats_block, target, context)
        return target_static_out.combine_with(target_contextual_out)

    def remove_effect(self, source: str):
        self.self_static.remove_effect(source)
        self.target_static.remove_effect(source)
        self.self_contextual.remove_effect(source)
        self.target_contextual.remove_effect(source)
