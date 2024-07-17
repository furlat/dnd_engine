from typing import Dict, Any, Callable, List, Tuple, TYPE_CHECKING, Optional
from pydantic import BaseModel, Field
from enum import Enum
from dnd.dnd_enums import AdvantageStatus
from dnd.logger import ContextualEffectLog, ModifiableValueLog, ContextualEffectsLog

if TYPE_CHECKING:
    from dnd.statsblock import StatsBlock



class AdvantageTracker(BaseModel):
    counter: int = 0

    def add_advantage(self):
        self.counter += 1

    def add_disadvantage(self):
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

    def is_auto_critical_self(self, stats_block: 'StatsBlock', target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None, return_log: bool = False) -> bool | Tuple[bool, List[ContextualEffectLog]]:
        auto_critical_logs = []
        is_auto_critical = False
        for source, condition in self.auto_critical_self_conditions:
            applied = condition(stats_block, target, context)
            is_auto_critical |= applied
            if return_log:
                auto_critical_logs.append(ContextualEffectLog(
                    source=source,
                    effect_type="auto_critical_self",
                    applied=applied,
                    entity_id=stats_block.id
                ))
        return (is_auto_critical, auto_critical_logs) if return_log else is_auto_critical

    def is_auto_critical_target(self, stats_block: 'StatsBlock', target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None, return_log: bool = False) -> bool | Tuple[bool, List[ContextualEffectLog]]:
        auto_critical_logs = []
        is_auto_critical = False
        for source, condition in self.auto_critical_target_conditions:
            applied = condition(stats_block, target, context)
            is_auto_critical |= applied
            if return_log:
                auto_critical_logs.append(ContextualEffectLog(
                    source=source,
                    effect_type="auto_critical_target",
                    applied=applied,
                    entity_id=stats_block.id
                ))
        return (is_auto_critical, auto_critical_logs) if return_log else is_auto_critical
    
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

    def compute_bonus(self, stats_block: 'StatsBlock', target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None, return_log: bool = False) -> int | Tuple[int, List[ContextualEffectLog]]:
        total_bonus = 0
        bonus_logs = []
        for source, bonus in self.bonuses:
            value = bonus(stats_block, target, context)
            total_bonus += value
            if return_log:
                bonus_logs.append(ContextualEffectLog(
                    source=source,
                    effect_type="bonus",
                    applied=True,
                    value=value,
                    entity_id=stats_block.id
                ))
        return (total_bonus, bonus_logs) if return_log else total_bonus

    def compute_min_constraint(self, stats_block: 'StatsBlock', target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None, return_log: bool = False) -> Optional[int] | Tuple[Optional[int], List[ContextualEffectLog]]:
        constraints = []
        constraint_logs = []
        for source, constraint in self.min_constraints:
            value = constraint(stats_block, target, context)
            constraints.append(value)
            if return_log:
                constraint_logs.append(ContextualEffectLog(
                    source=source,
                    effect_type="min_constraint",
                    applied=True,
                    value=value,
                    entity_id=stats_block.id
                ))
        min_constraint = max(constraints) if constraints else None
        return (min_constraint, constraint_logs) if return_log else min_constraint

    def compute_max_constraint(self, stats_block: 'StatsBlock', target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None, return_log: bool = False) -> Optional[int] | Tuple[Optional[int], List[ContextualEffectLog]]:
        constraints = []
        constraint_logs = []
        for source, constraint in self.max_constraints:
            value = constraint(stats_block, target, context)
            constraints.append(value)
            if return_log:
                constraint_logs.append(ContextualEffectLog(
                    source=source,
                    effect_type="max_constraint",
                    applied=True,
                    value=value,
                    entity_id=stats_block.id
                ))
        max_constraint = min(constraints) if constraints else None
        return (max_constraint, constraint_logs) if return_log else max_constraint

    def has_advantage(self, stats_block: 'StatsBlock', target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None, return_log: bool = False) -> bool | Tuple[bool, List[ContextualEffectLog]]:
        advantage_logs = []
        has_adv = False
        for source, condition in self.advantage_conditions:
            applied = condition(stats_block, target, context)
            has_adv |= applied
            if return_log:
                advantage_logs.append(ContextualEffectLog(
                    source=source,
                    effect_type="advantage",
                    applied=applied,
                    entity_id=stats_block.id
                ))
        return (has_adv, advantage_logs) if return_log else has_adv

    def has_disadvantage(self, stats_block: 'StatsBlock', target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None, return_log: bool = False) -> bool | Tuple[bool, List[ContextualEffectLog]]:
        disadvantage_logs = []
        has_dis = False
        for source, condition in self.disadvantage_conditions:
            applied = condition(stats_block, target, context)
            has_dis |= applied
            if return_log:
                disadvantage_logs.append(ContextualEffectLog(
                    source=source,
                    effect_type="disadvantage",
                    applied=applied,
                    entity_id=stats_block.id
                ))
        return (has_dis, disadvantage_logs) if return_log else has_dis

    def is_auto_fail_self(self, stats_block: 'StatsBlock', target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None, return_log: bool = False) -> bool | Tuple[bool, List[ContextualEffectLog]]:
        auto_fail_logs = []
        is_auto_fail = False
        for source, condition in self.auto_fail_self_conditions:
            applied = condition(stats_block, target, context)
            is_auto_fail |= applied
            if return_log:
                auto_fail_logs.append(ContextualEffectLog(
                    source=source,
                    effect_type="auto_fail_self",
                    applied=applied,
                    entity_id=stats_block.id
                ))
        return (is_auto_fail, auto_fail_logs) if return_log else is_auto_fail

    def is_auto_fail_target(self, stats_block: 'StatsBlock', target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None, return_log: bool = False) -> bool | Tuple[bool, List[ContextualEffectLog]]:
        auto_fail_logs = []
        is_auto_fail = False
        for source, condition in self.auto_fail_target_conditions:
            applied = condition(stats_block, target, context)
            is_auto_fail |= applied
            if return_log:
                auto_fail_logs.append(ContextualEffectLog(
                    source=source,
                    effect_type="auto_fail_target",
                    applied=applied,
                    entity_id=stats_block.id
                ))
        return (is_auto_fail, auto_fail_logs) if return_log else is_auto_fail

    def is_auto_success_self(self, stats_block: 'StatsBlock', target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None, return_log: bool = False) -> bool | Tuple[bool, List[ContextualEffectLog]]:
        auto_success_logs = []
        is_auto_success = False
        for source, condition in self.auto_success_self_conditions:
            applied = condition(stats_block, target, context)
            is_auto_success |= applied
            if return_log:
                auto_success_logs.append(ContextualEffectLog(
                    source=source,
                    effect_type="auto_success_self",
                    applied=applied,
                    entity_id=stats_block.id
                ))
        return (is_auto_success, auto_success_logs) if return_log else is_auto_success

    def is_auto_success_target(self, stats_block: 'StatsBlock', target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None, return_log: bool = False) -> bool | Tuple[bool, List[ContextualEffectLog]]:
        auto_success_logs = []
        is_auto_success = False
        for source, condition in self.auto_success_target_conditions:
            applied = condition(stats_block, target, context)
            is_auto_success |= applied
            if return_log:
                auto_success_logs.append(ContextualEffectLog(
                    source=source,
                    effect_type="auto_success_target",
                    applied=applied,
                    entity_id=stats_block.id
                ))
        return (is_auto_success, auto_success_logs) if return_log else is_auto_success

    def get_advantage_status(self, stats_block: 'StatsBlock', target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None, return_log: bool = False) -> AdvantageStatus | Tuple[AdvantageStatus, List[ContextualEffectLog]]:
        has_adv, adv_logs = self.has_advantage(stats_block, target, context, return_log=True)
        has_dis, dis_logs = self.has_disadvantage(stats_block, target, context, return_log=True)
        
        if has_adv and not has_dis:
            status = AdvantageStatus.ADVANTAGE
        elif has_dis and not has_adv:
            status = AdvantageStatus.DISADVANTAGE
        else:
            status = AdvantageStatus.NONE
        
        return (status, adv_logs + dis_logs) if return_log else status

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

    def get_log(self, stats_block: 'StatsBlock', target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None) -> ContextualEffectsLog:
        _, bonus_logs = self.compute_bonus(stats_block, target, context, return_log=True)
        _, advantage_logs = self.has_advantage(stats_block, target, context, return_log=True)
        _, disadvantage_logs = self.has_disadvantage(stats_block, target, context, return_log=True)
        _, auto_fail_self_logs = self.is_auto_fail_self(stats_block, target, context, return_log=True)
        _, auto_fail_target_logs = self.is_auto_fail_target(stats_block, target, context, return_log=True)
        _, auto_success_self_logs = self.is_auto_success_self(stats_block, target, context, return_log=True)
        _, auto_success_target_logs = self.is_auto_success_target(stats_block, target, context, return_log=True)
        _, min_constraint_logs = self.compute_min_constraint(stats_block, target, context, return_log=True)
        _, max_constraint_logs = self.compute_max_constraint(stats_block, target, context, return_log=True)
        
        auto_critical_self_logs = [
            ContextualEffectLog(source=source, effect_type="auto_critical_self", applied=condition(stats_block, target, context), entity_id=stats_block.id)
            for source, condition in self.auto_critical_self_conditions
        ]
        auto_critical_target_logs = [
            ContextualEffectLog(source=source, effect_type="auto_critical_target", applied=condition(stats_block, target, context), entity_id=stats_block.id)
            for source, condition in self.auto_critical_target_conditions
        ]

        return ContextualEffectsLog(
            entity_id=stats_block.id,
            bonuses=bonus_logs,
            advantage_conditions=advantage_logs,
            disadvantage_conditions=disadvantage_logs,
            auto_fail_conditions=auto_fail_self_logs + auto_fail_target_logs,
            auto_success_conditions=auto_success_self_logs + auto_success_target_logs,
            min_constraints=min_constraint_logs,
            max_constraints=max_constraint_logs,
            auto_critical_conditions=auto_critical_self_logs + auto_critical_target_logs
        )

class ModifiableValue(BaseModel):
    base_value: int
    static_modifiers: Dict[str, int] = Field(default_factory=dict)
    self_effects: ContextualEffects = Field(default_factory=ContextualEffects)
    target_effects: ContextualEffects = Field(default_factory=ContextualEffects)
    advantage_tracker: AdvantageTracker = Field(default_factory=AdvantageTracker)

    def get_value(self, stats_block: 'StatsBlock', target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None, return_log: bool = False) -> int | Tuple[int, ModifiableValueLog]:
        total = self.base_value + sum(self.static_modifiers.values())
        
        self_bonus, self_bonus_logs = self.self_effects.compute_bonus(stats_block, target, context, return_log=True)
        total += self_bonus
        
        target_bonus, target_bonus_logs = 0, []
        if target:
            target_bonus, target_bonus_logs = self.target_effects.compute_bonus(target, stats_block, context, return_log=True)
        total += target_bonus

        min_constraint, min_constraint_logs = self.self_effects.compute_min_constraint(stats_block, target, context, return_log=True)
        max_constraint, max_constraint_logs = self.self_effects.compute_max_constraint(stats_block, target, context, return_log=True)

        if min_constraint is not None:
            total = max(total, min_constraint)
        if max_constraint is not None:
            total = min(total, max_constraint)

        final_value = max(0, total)

        if return_log:
            advantage_status, adv_dis_logs = self.get_advantage_status(stats_block, target, context, return_log=True)
            
            log = ModifiableValueLog(
                entity_id=stats_block.id,
                base_value=self.base_value,
                static_modifiers=self.static_modifiers,
                self_effects=self_bonus_logs + min_constraint_logs + max_constraint_logs,
                target_effects=target_bonus_logs,
                advantage_status=advantage_status,
                final_value=final_value,
                min_constraint=min_constraint,
                max_constraint=max_constraint,
                auto_fail=self.is_auto_fail(stats_block, target, context),
                auto_success=self.is_auto_success(stats_block, target, context),
                auto_critical=self.is_auto_critical(stats_block, target, context)
            )
            return final_value, log
        
        return final_value

    def add_static_modifier(self, source: str, value: int):
        self.static_modifiers[source] = value

    def remove_static_modifier(self, source: str):
        self.static_modifiers.pop(source, None)

    def get_advantage_status(self, stats_block: 'StatsBlock', target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None, return_log: bool = False) -> AdvantageStatus | Tuple[AdvantageStatus, List[ContextualEffectLog]]:
        self.advantage_tracker.reset()
        self_status, self_logs = self.self_effects.get_advantage_status(stats_block, target, context, return_log=True)
        target_status, target_logs = AdvantageStatus.NONE, []
        if target:
            target_status, target_logs = self.target_effects.get_advantage_status(target, stats_block, context, return_log=True)
        
        # Apply the advantage and disadvantage to the advantage_tracker
        if self_status == AdvantageStatus.ADVANTAGE or target_status == AdvantageStatus.ADVANTAGE:
            self.advantage_tracker.add_advantage()
        if self_status == AdvantageStatus.DISADVANTAGE or target_status == AdvantageStatus.DISADVANTAGE:
            self.advantage_tracker.add_disadvantage()
        
        final_status = self.advantage_tracker.status
        
        if return_log:
            return final_status, self_logs + target_logs
        return final_status

    def is_auto_fail(self, stats_block: 'StatsBlock', target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None, return_log: bool = False) -> bool | Tuple[bool, List[ContextualEffectLog]]:
        self_fail, self_logs = self.self_effects.is_auto_fail_self(stats_block, target, context, return_log=True)
        target_fail, target_logs = False, []
        if target:
            target_fail, target_logs = self.target_effects.is_auto_fail_target(target, stats_block, context, return_log=True)
        
        is_fail = self_fail or target_fail
        
        if return_log:
            return is_fail, self_logs + target_logs
        return is_fail

    def causes_auto_fail(self, stats_block: 'StatsBlock', target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None, return_log: bool = False) -> bool | Tuple[bool, List[ContextualEffectLog]]:
        self_cause, self_logs = self.self_effects.is_auto_fail_target(stats_block, target, context, return_log=True)
        target_cause, target_logs = False, []
        if target:
            target_cause, target_logs = self.target_effects.is_auto_fail_self(target, stats_block, context, return_log=True)
        
        causes_fail = self_cause or target_cause
        
        if return_log:
            return causes_fail, self_logs + target_logs
        return causes_fail

    def is_auto_success(self, stats_block: 'StatsBlock', target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None, return_log: bool = False) -> bool | Tuple[bool, List[ContextualEffectLog]]:
        self_success, self_logs = self.self_effects.is_auto_success_self(stats_block, target, context, return_log=True)
        target_success, target_logs = False, []
        if target:
            target_success, target_logs = self.target_effects.is_auto_success_target(target, stats_block, context, return_log=True)
        
        is_success = self_success or target_success
        
        if return_log:
            return is_success, self_logs + target_logs
        return is_success

    def causes_auto_success(self, stats_block: 'StatsBlock', target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None, return_log: bool = False) -> bool | Tuple[bool, List[ContextualEffectLog]]:
        self_cause, self_logs = self.self_effects.is_auto_success_target(stats_block, target, context, return_log=True)
        target_cause, target_logs = False, []
        if target:
            target_cause, target_logs = self.target_effects.is_auto_success_self(target, stats_block, context, return_log=True)
        
        causes_success = self_cause or target_cause
        
        if return_log:
            return causes_success, self_logs + target_logs
        return causes_success

    def is_auto_critical(self, stats_block: 'StatsBlock', target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None, return_log: bool = False) -> bool | Tuple[bool, List[ContextualEffectLog]]:
        self_crit, self_logs = self.self_effects.is_auto_critical_self(stats_block, target, context, return_log=True)
        target_crit, target_logs = False, []
        if target:
            target_crit, target_logs = self.target_effects.is_auto_critical_target(target, stats_block, context, return_log=True)
        
        is_crit = self_crit or target_crit
        
        if return_log:
            return is_crit, self_logs + target_logs
        return is_crit

    def causes_auto_critical(self, stats_block: 'StatsBlock', target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None, return_log: bool = False) -> bool | Tuple[bool, List[ContextualEffectLog]]:
        self_cause, self_logs = self.self_effects.is_auto_critical_target(stats_block, target, context, return_log=True)
        target_cause, target_logs = False, []
        if target:
            target_cause, target_logs = self.target_effects.is_auto_critical_self(target, stats_block, context, return_log=True)
        
        causes_crit = self_cause or target_cause
        
        if return_log:
            return causes_crit, self_logs + target_logs
        return causes_crit

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

    def get_log(self, stats_block: 'StatsBlock', target: Optional['StatsBlock'] = None, context: Optional[Dict[str, Any]] = None) -> ModifiableValueLog:
        _, log = self.get_value(stats_block, target, context, return_log=True)
        return log
