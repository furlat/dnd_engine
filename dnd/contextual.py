from typing import Dict, Any, Callable, List, Tuple, TYPE_CHECKING, Optional
from pydantic import BaseModel, Field
from enum import Enum

if TYPE_CHECKING:
    from dnd.statsblock import StatsBlock

class AdvantageStatus(str, Enum):
    NONE = "None"
    ADVANTAGE = "Advantage"
    DISADVANTAGE = "Disadvantage"

class AdvantageTracker(BaseModel):
    counter: int = 0

    def add_advantage(self, stats_block: 'StatsBlock'):
        if 'Advantage' not in stats_block.modifier_immunity:
            self.counter += 1

    def add_disadvantage(self, stats_block: 'StatsBlock'):
        if 'Disadvantage' not in stats_block.modifier_immunity:
            self.counter -= 1

    def reset(self):
        self.counter = 0

    @property
    def status(self) -> AdvantageStatus:
        if self.counter > 0:
            return AdvantageStatus.ADVANTAGE
        elif self.counter < 0:
            return AdvantageStatus.DISADVANTAGE
        else:
            return AdvantageStatus.NONE

ContextAwareCondition = Callable[['StatsBlock', Optional['StatsBlock'], Optional[Dict[str, Any]]], bool]
ContextAwareBonus = Callable[['StatsBlock', Optional['StatsBlock'], Optional[Dict[str, Any]]], int]

class ContextualEffects(BaseModel):
    bonuses: List[Tuple[str, ContextAwareBonus]] = Field(default_factory=list)
    advantage_conditions: List[Tuple[str, ContextAwareCondition]] = Field(default_factory=list)
    disadvantage_conditions: List[Tuple[str, ContextAwareCondition]] = Field(default_factory=list)
    auto_fail_self_conditions: List[Tuple[str, ContextAwareCondition]] = Field(default_factory=list)
    auto_fail_target_conditions: List[Tuple[str, ContextAwareCondition]] = Field(default_factory=list)
    auto_success_self_conditions: List[Tuple[str, ContextAwareCondition]] = Field(default_factory=list)
    auto_success_target_conditions: List[Tuple[str, ContextAwareCondition]] = Field(default_factory=list)
    min_constraints: List[Tuple[str, ContextAwareBonus]] = Field(default_factory=list)
    max_constraints: List[Tuple[str, ContextAwareBonus]] = Field(default_factory=list)
    auto_critical_self_conditions: List[Tuple[str, ContextAwareCondition]] = Field(default_factory=list)
    auto_critical_target_conditions: List[Tuple[str, ContextAwareCondition]] = Field(default_factory=list)

    def add_auto_critical_self_condition(self, source: str, condition: ContextAwareCondition):
        self.auto_critical_self_conditions.append((source, condition))

    def add_auto_critical_target_condition(self, source: str, condition: ContextAwareCondition):
        self.auto_critical_target_conditions.append((source, condition))

    def is_auto_critical_self(self, stats_block: 'StatsBlock', target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None) -> bool:
        return any(condition(stats_block, target, context) for _, condition in self.auto_critical_self_conditions)

    def is_auto_critical_target(self, stats_block: 'StatsBlock', target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None) -> bool:
        return any(condition(stats_block, target, context) for _, condition in self.auto_critical_target_conditions)


    def add_bonus(self, source: str, bonus: ContextAwareBonus):
        self.bonuses.append((source, bonus))

    def add_advantage_condition(self, source: str, condition: ContextAwareCondition):
        self.advantage_conditions.append((source, condition))

    def add_disadvantage_condition(self, source: str, condition: ContextAwareCondition):
        self.disadvantage_conditions.append((source, condition))

    def add_auto_fail_self_condition(self, source: str, condition: ContextAwareCondition):
        self.auto_fail_self_conditions.append((source, condition))

    def add_auto_fail_target_condition(self, source: str, condition: ContextAwareCondition):
        self.auto_fail_target_conditions.append((source, condition))

    def add_auto_success_self_condition(self, source: str, condition: ContextAwareCondition):
        self.auto_success_self_conditions.append((source, condition))

    def add_auto_success_target_condition(self, source: str, condition: ContextAwareCondition):
        self.auto_success_target_conditions.append((source, condition))

    def add_min_constraint(self, source: str, constraint: ContextAwareBonus):
        self.min_constraints.append((source, constraint))

    def add_max_constraint(self, source: str, constraint: ContextAwareBonus):
        self.max_constraints.append((source, constraint))

    def compute_bonus(self, stats_block: 'StatsBlock', target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None) -> int:
        return sum(bonus(stats_block, target, context) for _, bonus in self.bonuses)

    def compute_min_constraint(self, stats_block: 'StatsBlock', target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None) -> Optional[int]:
        constraints = [constraint(stats_block, target, context) for _, constraint in self.min_constraints]
        return max(constraints) if constraints else None

    def compute_max_constraint(self, stats_block: 'StatsBlock', target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None) -> Optional[int]:
        constraints = [constraint(stats_block, target, context) for _, constraint in self.max_constraints]
        return min(constraints) if constraints else None

    def has_advantage(self, stats_block: 'StatsBlock', target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None) -> bool:
        return any(condition(stats_block, target, context) for _, condition in self.advantage_conditions)

    def has_disadvantage(self, stats_block: 'StatsBlock', target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None) -> bool:
        return any(condition(stats_block, target, context) for _, condition in self.disadvantage_conditions)

    def is_auto_fail_self(self, stats_block: 'StatsBlock', target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None) -> bool:
        return any(condition(stats_block, target, context) for _, condition in self.auto_fail_self_conditions)

    def is_auto_fail_target(self, stats_block: 'StatsBlock', target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None) -> bool:
        return any(condition(stats_block, target, context) for _, condition in self.auto_fail_target_conditions)

    def is_auto_success_self(self, stats_block: 'StatsBlock', target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None) -> bool:
        return any(condition(stats_block, target, context) for _, condition in self.auto_success_self_conditions)

    def is_auto_success_target(self, stats_block: 'StatsBlock', target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None) -> bool:
        return any(condition(stats_block, target, context) for _, condition in self.auto_success_target_conditions)

    def get_advantage_status(self, stats_block: 'StatsBlock', target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None) -> AdvantageStatus:
        has_adv = self.has_advantage(stats_block, target, context)
        has_dis = self.has_disadvantage(stats_block, target, context)
        if has_adv and not has_dis:
            return AdvantageStatus.ADVANTAGE
        elif has_dis and not has_adv:
            return AdvantageStatus.DISADVANTAGE
        else:
            return AdvantageStatus.NONE

    def apply_advantage_disadvantage(self, stats_block: 'StatsBlock', target: Optional['StatsBlock'], advantage_tracker: AdvantageTracker, context: Optional[Dict[str, Any]] = None):
        if self.has_advantage(stats_block, target, context):
            advantage_tracker.add_advantage(stats_block)
        if self.has_disadvantage(stats_block, target, context):
            advantage_tracker.add_disadvantage(stats_block)

    def remove_effect(self, source: str):
        self.bonuses = [b for b in self.bonuses if b[0] != source]
        self.advantage_conditions = [a for a in self.advantage_conditions if a[0] != source]
        self.disadvantage_conditions = [d for d in self.disadvantage_conditions if d[0] != source]
        self.auto_fail_self_conditions = [af for af in self.auto_fail_self_conditions if af[0] != source]
        self.auto_fail_target_conditions = [af for af in self.auto_fail_target_conditions if af[0] != source]
        self.auto_success_self_conditions = [as_ for as_ in self.auto_success_self_conditions if as_[0] != source]
        self.auto_success_target_conditions = [as_ for as_ in self.auto_success_target_conditions if as_[0] != source]
        self.min_constraints = [mc for mc in self.min_constraints if mc[0] != source]
        self.max_constraints = [mc for mc in self.max_constraints if mc[0] != source]
        self.auto_critical_self_conditions = [ac for ac in self.auto_critical_self_conditions if ac[0] != source]
        self.auto_critical_target_conditions = [ac for ac in self.auto_critical_target_conditions if ac[0] != source]

class ModifiableValue(BaseModel):
    base_value: int
    static_modifiers: Dict[str, int] = Field(default_factory=dict)
    self_effects: ContextualEffects = Field(default_factory=ContextualEffects)
    target_effects: ContextualEffects = Field(default_factory=ContextualEffects)
    advantage_tracker: AdvantageTracker = Field(default_factory=AdvantageTracker)

    def get_value(self, stats_block: 'StatsBlock', target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None) -> int:
        total = self.base_value + sum(self.static_modifiers.values())
        total += self.self_effects.compute_bonus(stats_block, target, context)
        if target:
            total += self.target_effects.compute_bonus(target, stats_block, context)

        min_constraint = self.self_effects.compute_min_constraint(stats_block, target, context)
        max_constraint = self.self_effects.compute_max_constraint(stats_block, target, context)

        if min_constraint is not None:
            total = max(total, min_constraint)
        if max_constraint is not None:
            total = min(total, max_constraint)

        return max(0, total)

    def add_static_modifier(self, source: str, value: int):
        self.static_modifiers[source] = value

    def remove_static_modifier(self, source: str):
        self.static_modifiers.pop(source, None)

    def get_advantage_status(self, stats_block: 'StatsBlock', target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None) -> AdvantageStatus:
        self.advantage_tracker.reset()
        self.self_effects.apply_advantage_disadvantage(stats_block, target, self.advantage_tracker, context)
        if target:
            self.target_effects.apply_advantage_disadvantage(target, stats_block, self.advantage_tracker, context)
        return self.advantage_tracker.status

    def is_auto_fail(self, stats_block: 'StatsBlock', target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None) -> bool:
        return (self.self_effects.is_auto_fail_self(stats_block, target, context) or
                (target and self.target_effects.is_auto_fail_target(target, stats_block, context)))

    def causes_auto_fail(self, stats_block: 'StatsBlock', target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None) -> bool:
        return (self.self_effects.is_auto_fail_target(stats_block, target, context) or
                (target and self.target_effects.is_auto_fail_self(target, stats_block, context)))

    def is_auto_success(self, stats_block: 'StatsBlock', target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None) -> bool:
        return (self.self_effects.is_auto_success_self(stats_block, target, context) or
                (target and self.target_effects.is_auto_success_target(target, stats_block, context)))

    def causes_auto_success(self, stats_block: 'StatsBlock', target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None) -> bool:
        return (self.self_effects.is_auto_success_target(stats_block, target, context) or
                (target and self.target_effects.is_auto_success_self(target, stats_block, context)))

    def is_auto_critical(self, stats_block: 'StatsBlock', target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None) -> bool:
        return (self.self_effects.is_auto_critical_self(stats_block, target, context) or
                (target and self.target_effects.is_auto_critical_target(target, stats_block, context)))

    def causes_auto_critical(self, stats_block: 'StatsBlock', target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None) -> bool:
        return (self.self_effects.is_auto_critical_target(stats_block, target, context) or
                (target and self.target_effects.is_auto_critical_self(target, stats_block, context)))

    def add_auto_critical_self_condition(self, source: str, condition: ContextAwareCondition):
        self.self_effects.add_auto_critical_self_condition(source, condition)

    def add_auto_critical_target_condition(self, source: str, condition: ContextAwareCondition):
        self.self_effects.add_auto_critical_target_condition(source, condition)
        
    def add_bonus(self, source: str, bonus: ContextAwareBonus):
        self.self_effects.add_bonus(source, bonus)

    def add_advantage_condition(self, source: str, condition: ContextAwareCondition):
        self.self_effects.add_advantage_condition(source, condition)

    def add_disadvantage_condition(self, source: str, condition: ContextAwareCondition):
        self.self_effects.add_disadvantage_condition(source, condition)

    def add_auto_fail_self_condition(self, source: str, condition: ContextAwareCondition):
        self.self_effects.add_auto_fail_self_condition(source, condition)

    def add_auto_fail_target_condition(self, source: str, condition: ContextAwareCondition):
        self.self_effects.add_auto_fail_target_condition(source, condition)

    def add_auto_success_self_condition(self, source: str, condition: ContextAwareCondition):
        self.self_effects.add_auto_success_self_condition(source, condition)

    def add_auto_success_target_condition(self, source: str, condition: ContextAwareCondition):
        self.self_effects.add_auto_success_target_condition(source, condition)

    def add_min_constraint(self, source: str, constraint: ContextAwareBonus):
        self.self_effects.add_min_constraint(source, constraint)

    def add_max_constraint(self, source: str, constraint: ContextAwareBonus):
        self.self_effects.add_max_constraint(source, constraint)
    
    

    def remove_effect(self, source: str):
        self.self_effects.remove_effect(source)
        self.target_effects.remove_effect(source)
