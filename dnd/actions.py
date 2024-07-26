from pydantic import BaseModel, Field, computed_field
from typing import List, Optional, Union, Dict, Any, Tuple, Set, Callable, TYPE_CHECKING, TypeVar
from enum import Enum
from dnd.contextual import ModifiableValue, AdvantageStatus, ContextAwareCondition, ContextAwareBonus, BaseValue
from dnd.core import (BlockComponent,Ability,  AdvantageTracker, DurationType, RegistryHolder, Damage,Weapon, Armor, Condition)
from dnd.dnd_enums import (PrerequisiteType, DamageType,  RangeType, ShapeType, TargetType,
                               TargetRequirementType, UsageType,
                               RechargeType, ActionType, AttackType, SourceType,WeaponProperty, ArmorType,HitReason, AttackHand
                               )
from dnd.statsblock import StatsBlock



from dnd.logger import ConditionApplied, ConditionNotApplied, Logger, BaseLogEntry, SkillRollOut, SavingThrowRollOut, AttackRollOut, DamageRollOut, ActionType 
from dnd.logger import PrerequisiteDetails, PrerequisiteLog, ActionLog, ActionResultDetails, ActionCost

if TYPE_CHECKING:
    from dnd.statsblock import StatsBlock
    from dnd.conditions import Condition
    from dnd.battlemap import BattleMap, Entity

# Types
Position = Tuple[int, int]
Target = Union[StatsBlock, Position]


# Prerequisite system
class Prerequisite(BaseModel):
    name: str
    type: PrerequisiteType

    def check(self, source: StatsBlock, target: Target, context: Dict[str, Any]) -> Tuple[bool, PrerequisiteDetails]:
        raise NotImplementedError("Subclasses must implement this method")

class ActionEconomyPrerequisite(Prerequisite):
    type: PrerequisiteType = PrerequisiteType.ACTION_ECONOMY
    action_type: ActionType
    cost: int

    def check(self, source: StatsBlock, target: Target, context: Dict[str, Any]) -> Tuple[bool, PrerequisiteDetails]:
        available = getattr(source.action_economy, f"{self.action_type.value.lower()}s").apply(source).total_bonus
        details = PrerequisiteDetails(
            available_actions=available,
            required_actions=self.cost
        )
        if available >= self.cost:
            return True, details
        details.failure_reason = f"Not enough {self.action_type.value} available"
        return False, details

class LineOfSightPrerequisite(Prerequisite):
    type: PrerequisiteType = PrerequisiteType.LINE_OF_SIGHT

    def check(self, source: StatsBlock, target: Target, context: Dict[str, Any]) -> Tuple[bool, PrerequisiteDetails]:
        target_position = target.sensory.origin if isinstance(target, StatsBlock) else target
        is_visible = source.is_visible(target_position)
        details = PrerequisiteDetails(is_visible=is_visible)
        if not is_visible:
            details.failure_reason = "Target is not visible"
        return is_visible, details

class RangePrerequisite(Prerequisite):
    type: PrerequisiteType = PrerequisiteType.RANGE
    range_type: RangeType
    range_normal: int
    range_long: Optional[int] = None

    def check(self, source: StatsBlock, target: Target, context: Dict[str, Any]) -> Tuple[bool, PrerequisiteDetails]:
        target_position = target.sensory.origin if isinstance(target, StatsBlock) else target
        distance = source.get_distance(target_position)
        max_range = self.range_long if self.range_type == RangeType.RANGE and self.range_long else self.range_normal
        details = PrerequisiteDetails(distance=distance, required_range=max_range)
        if distance is None:
            details.failure_reason = "Distance could not be calculated"
            return False, details
        if distance <= max_range:
            return True, details
        details.failure_reason = f"Target is out of range"
        return False, details

class TargetTypePrerequisite(Prerequisite):
    type: PrerequisiteType = PrerequisiteType.TARGET
    allowed_types: List[TargetType]

    def check(self, source: StatsBlock, target: Target, context: Dict[str, Any]) -> Tuple[bool, PrerequisiteDetails]:
        details = PrerequisiteDetails()
        if isinstance(target, StatsBlock):
            if TargetType.SELF in self.allowed_types and target.id == source.id:
                return True, details
            if TargetType.ALLY in self.allowed_types and target.meta.alignment == source.meta.alignment:
                return True, details
            if TargetType.ENEMY in self.allowed_types and target.meta.alignment != source.meta.alignment:
                return True, details
        elif isinstance(target, tuple) and TargetType.POSITION in self.allowed_types:
            return True, details
        
        details.failure_reason = f"Invalid target type. Allowed types: {', '.join(t.value for t in self.allowed_types)}"
        return False, details

class PathExistsPrerequisite(Prerequisite):
    type: PrerequisiteType = PrerequisiteType.PATH

    def check(self, source: StatsBlock, target: Target, context: Dict[str, Any]) -> Tuple[bool, PrerequisiteDetails]:
        if not isinstance(target, tuple) or len(target) != 2:
            return False, PrerequisiteDetails(failure_reason="Invalid target position")

        path = source.sensory.get_path_to(target)
        details = PrerequisiteDetails(path_length=len(path) if path else 0)
        
        if not path:
            details.failure_reason = "No valid path to target position"
            return False, details
        
        context['path'] = path  # Store the path in the context for later use
        return True, details

class MovementBudgetPrerequisite(Prerequisite):
    type: PrerequisiteType = PrerequisiteType.ACTION_ECONOMY

    def check(self, source: StatsBlock, target: Target, context: Dict[str, Any]) -> Tuple[bool, PrerequisiteDetails]:
        path = source.sensory.get_path_to(target)
        movement_budget = source.action_economy.movement.apply(source).total_bonus
        movement_cost = (len(path) - 1) * 5 if path else 0  # Each step is 5 feet
        print(f"testing movement budget {movement_budget} {movement_cost}")
        
        details = PrerequisiteDetails(
            movement_budget=movement_budget,
            path_length=len(path) - 1 if path else 0,
            required_actions=movement_cost
        )
        
        if movement_cost > movement_budget:
            details.failure_reason = f"Insufficient movement points. Required: {movement_cost}, Available: {movement_budget}"
            return False, details
        
        return True, details
    
def check_prerequisites(prerequisites: Dict[str, Prerequisite], source: StatsBlock, target: Target, context: Dict[str, Any]) -> Tuple[bool, Dict[str, PrerequisiteLog]]:
    all_passed = True
    logs = {}
    
    for name, prerequisite in prerequisites.items():
        passed, details = prerequisite.check(source, target, context)
        log = PrerequisiteLog(
            prerequisite_type=prerequisite.type,
            passed=passed,
            details=details,
            source_entity_id=source.id,
            target_entity_id=target.id if isinstance(target, StatsBlock) else str(target)
        )
        Logger.log(log)
        logs[name] = log
        all_passed = all_passed and passed

    return all_passed, logs

# Action system
T = TypeVar('T', bound='Action')
class Action(BaseModel):
    name: str
    description: str
    cost: Optional[List[ActionCost]] = None
    prerequisites: Dict[str, Prerequisite] = Field(default_factory=dict)
    source: Optional[StatsBlock] = None
    target: Optional[Target] = None
    context: Optional[Dict[str, Any]] = None

    def __init__(self, **data):
        super().__init__(**data)
        self.add_cost_prequisites()
    
    def add_prerequisite(self, name: str, prerequisite: Prerequisite):
        self.prerequisites[name] = prerequisite

    def _get_costs(self, source: Optional[StatsBlock]=None) -> Optional[List[ActionCost]]:
        return self.cost if self.cost else None
    
    def _create_action_economy_prerequisite_single(self,action_cost :ActionCost) -> ActionEconomyPrerequisite:
        cost_type =action_cost.type
        cost_unit = action_cost.cost

        return ActionEconomyPrerequisite(name="Action Economy", action_type=cost_type, cost=cost_unit)

    def create_action_economy_prerequisites(self) -> List[ActionEconomyPrerequisite]:
        return [self._create_action_economy_prerequisite_single(cost) for cost in self._get_costs() if self._get_costs() and cost is not None]

    def add_cost_prequisites(self):
        for prerequisite in self.create_action_economy_prerequisites():
            self.add_prerequisite(prerequisite.name, prerequisite)

    def remove_prerequisite(self, name: str):
        self.prerequisites.pop(name, None)

    def check_prerequisites(self, source: Optional[StatsBlock] = None, target: Optional[Target] = None, context: Optional[Dict[str, Any]] = None) -> Tuple[bool, Dict[str, PrerequisiteLog]]:
        source = source or self.source
        target = target or self.target
        context = context or self.context or {}
        
        if not source or not target:
            raise ValueError("Source and target must be provided either through binding or as method arguments.")
        
        all_passed = True
        logs = {}
        
        for name, prerequisite in self.prerequisites.items():
            passed, details = prerequisite.check(source, target, context)
            log = PrerequisiteLog(
                prerequisite_type=prerequisite.type,
                passed=passed,
                details=details,
                source_entity_id=source.id,
                target_entity_id=target.id if isinstance(target, StatsBlock) else str(target)
            )
            Logger.log(log)
            logs[name] = log
            all_passed = all_passed and passed

        return all_passed, logs
    
    

    def apply_cost(self, source: Optional[StatsBlock] = None):
        source = source or self.source
        if not source:
            raise ValueError("Source must be provided either through binding or as a method argument.")
        costs = self._get_costs(source)
        for cost in costs:
            action_economy_attr : ModifiableValue = getattr(source.action_economy, f"{cost.type.value.lower()}s")
            action_economy_attr.self_static.add_bonus(f"{self.name}_cost", -cost.cost)

    def apply(self, source: Optional[StatsBlock] = None, targets: Optional[Union[List[Target], Target]] = None, context: Optional[Dict[str, Any]] = None) -> List[ActionLog]:
        source = source or self.source
        targets = targets or ([self.target] if self.target else None)
        context = context or self.context or {}
        
        if not source or not targets:
            raise ValueError("Source and targets must be provided either through binding or as method arguments.")
        
        if not isinstance(targets, list):
            targets = [targets]
        
        action_logs = []

        for target in targets:
            prerequisites_passed, prerequisite_logs = self.check_prerequisites(source, target, context)
            
            if not prerequisites_passed:
                action_log = ActionLog(
                    action_name=self.name,
                    source_entity_id=source.id,
                    target_entity_id=target.id if isinstance(target, StatsBlock) else str(target),
                    success=False,
                    prerequisite_logs=prerequisite_logs,
                    result_details=ActionResultDetails(
                        success=False,
                        reason="Prerequisites not met"
                    )
                )
            else:
                self.apply_cost(source)
                success, result_details, dice_rolls, damage_rolls = self._apply(source, target, context)
                action_log = ActionLog(
                    action_name=self.name,
                    source_entity_id=source.id,
                    target_entity_id=target.id if isinstance(target, StatsBlock) else str(target),
                    success=success,
                    prerequisite_logs=prerequisite_logs,
                    result_details=result_details,
                    dice_rolls=dice_rolls,
                    damage_rolls=damage_rolls
                )
            
            action_logs.append(action_log)
            Logger.log(action_log)
        
        return action_logs

    def _apply(self, source: StatsBlock, target: Target, context: Dict[str, Any]) -> Tuple[bool, ActionResultDetails, List[AttackRollOut], List[DamageRollOut]]:
        raise NotImplementedError("Subclasses must implement this method")

    def bind(self: T, source: StatsBlock, target: Target, context: Optional[Dict[str, Any]] = None) -> T:
        return self.__class__(
            **self.model_dump(exclude={'source', 'target', 'context'}),
            source=source,
            target=target,
            context=context or {}
        )
    
class Attack(Action):
    attack_type: AttackType
    attack_hand: AttackHand
    range_type: RangeType
    range_normal: int
    range_long: Optional[int] = None
    default_prerequisites: bool = Field(default=True)

    def __init__(self, **data):
        super().__init__(**data)
        if self.default_prerequisites:
            self._add_default_prerequisites()

    def _add_default_prerequisites(self):
        self.add_prerequisite("Range", RangePrerequisite(name="Range", range_type=self.range_type, range_normal=self.range_normal, range_long=self.range_long))
        self.add_prerequisite("Line of Sight", LineOfSightPrerequisite(name="Line of Sight"))
    
    
    def _get_costs(self,source: Optional[StatsBlock] = None ) -> List[ActionCost]:
        if self.attack_hand == AttackHand.MELEE_LEFT or self.attack_hand == AttackHand.RANGED_LEFT:
            return [ActionCost(type=ActionType.BONUS_ACTION, cost=1)]
        else:
            return [ActionCost(type=ActionType.ACTION, cost=1)]
        
    def _apply(self, source: StatsBlock, target: Target, context: Dict[str, Any]) -> Tuple[bool, ActionResultDetails, List[AttackRollOut], List[DamageRollOut]]:
        if not isinstance(target, StatsBlock):
            return False, ActionResultDetails(success=False, reason="Invalid target type"), [], []

        attack_roll = source.perform_attack(self.attack_hand, target.id, context)
        
        if not attack_roll.success:
            return False, ActionResultDetails(success=False, reason="Attack missed"), [attack_roll], []

        damage_roll = source.roll_damage(attack_roll, context)
        target.take_damage(damage_roll, source.id, context)

        return True, ActionResultDetails(success=True, effects={"damage": damage_roll.total_damage}), [attack_roll], [damage_roll]

    def chance_to_hit(self, source: StatsBlock, target: StatsBlock, context: Optional[Dict[str, Any]] = None) -> Tuple[Optional[int], float, str]:
        attack_roll = source.perform_attack(self.attack_hand, target.id, context)
        
        if attack_roll.roll.hit_reason == HitReason.AUTOHIT:
            return None, 1.0, "Auto-hit"
        if attack_roll.roll.hit_reason == HitReason.AUTOMISS:
            return None, 0.0, "Auto-miss"

        target_ac = target.ac
        total_attack_bonus = attack_roll.attack_bonus.total_bonus
        min_roll_to_hit = max(1, target_ac - total_attack_bonus)

        if min_roll_to_hit > 20:
            return None, 0.0, "Impossible to hit"
        if min_roll_to_hit <= 1:
            return 1, 1.0, "Always hits"

        base_probability = (21 - min_roll_to_hit) / 20
        
        advantage_status = attack_roll.roll.bonus.advantage_tracker.status
        if advantage_status == AdvantageStatus.ADVANTAGE:
            hit_probability = 1 - (1 - base_probability) ** 2
            status = "Advantage"
        elif advantage_status == AdvantageStatus.DISADVANTAGE:
            hit_probability = base_probability ** 2
            status = "Disadvantage"
        else:
            hit_probability = base_probability
            status = "Normal"

        return min_roll_to_hit, hit_probability, status

    def __str__(self):
        range_str = f"{self.range_normal} ft." if self.range_type == RangeType.REACH else f"{self.range_normal}/{self.range_long} ft."
        return f"{self.attack_type.value} Attack using {self.attack_hand.value}, Range: {range_str}"
    
class SelfCondition(Action):
    conditions: List[Condition] = Field(default_factory=list)

    def _apply(self, source: StatsBlock, target: StatsBlock, context: Dict[str, Any]) -> Tuple[bool, ActionResultDetails, List[Any], List[Any]]:
        if source.id != target.id:
            return False, ActionResultDetails(success=False, reason="SelfCondition can only be applied to self"), [], []

        condition_logs = []
        applied_conditions = []
        
        for condition in self.conditions:
            condition.source_entity_id = source.id
            condition.targeted_entity_id = source.id
            application_result = source.condition_manager.add_condition(condition, context)
            
            if isinstance(application_result, ConditionApplied):
                applied_conditions.append(condition.name)
                condition_logs.append(application_result)
            elif isinstance(application_result, ConditionNotApplied):
                condition_logs.append(application_result)

        success = len(applied_conditions) > 0
        reason = f"Applied {', '.join(applied_conditions)} to self." if success else "No conditions were applied."
        
        result_details = ActionResultDetails(
            success=success,
            reason=reason,
            effects={"applied_conditions": applied_conditions}
        )

        return success, result_details, condition_logs, []

    def __str__(self):
        conditions_str = ', '.join([c.name for c in self.conditions])
        return f"{self.name}: Applies {conditions_str} to self. {self.description}"




class MovementAction(Action):
    step_by_step: bool = Field(default=False)

    def __init__(self, **data):
        super().__init__(**data)
        self.add_prerequisite("Path Exists", PathExistsPrerequisite())
        self.add_prerequisite("Movement Budget", MovementBudgetPrerequisite())

    def _apply(self, source: StatsBlock, target: Target, context: Dict[str, Any]) -> Tuple[bool, ActionResultDetails, List[Any], List[Any]]:
        if not isinstance(target, tuple) or len(target) != 2:
            return False, ActionResultDetails(success=False, reason="Invalid target position"), [], []

        battlemap: Optional['BattleMap'] = RegistryHolder.get_instance(source.sensory.battlemap_id)
        if not battlemap:
            return False, ActionResultDetails(success=False, reason="Entity is not on a battlemap"), [], []

        path = source.sensory.get_path_to(target)
        if not path:
            return False, ActionResultDetails(success=False, reason="No valid path to target"), [], []

        start_position = source.sensory.origin
        end_position = target
        movement_cost = (len(path) - 1) * 5  # Each step is 5 feet

        if self.step_by_step:
            for step in path[1:]:  # Skip the first step as it's the starting position
                battlemap.move_entity(source, step)
                battlemap.update_entity_fov(source)
        else:
            battlemap.move_entity(source, end_position)
            battlemap.update_entity_fov(source)

        source.action_economy.movement.self_static.add_bonus("movement_used", -movement_cost)

        result_details = ActionResultDetails(
            success=True,
            reason=f"Moved from {start_position} to {end_position}",
            effects={
                "start_position": start_position,
                "end_position": end_position,
                "movement_cost": movement_cost,
                "path": path
            }
        )

        return True, result_details, [], []  # No dice rolls or damage rolls for movement

    def apply(self, source: StatsBlock, targets: Union[List[Target], Target], context: Dict[str, Any] = None) -> List[ActionLog]:
        if not isinstance(targets, tuple) or len(targets) != 2:
            raise ValueError("MovementAction requires a single target position (tuple of two integers)")

        return super().apply(source, targets, context)

    def __str__(self):
        movement_type = "Step-by-step" if self.step_by_step else "Direct"
        return f"{self.name}: {movement_type} movement to target position"
