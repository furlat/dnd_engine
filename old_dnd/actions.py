from pydantic import BaseModel, Field, computed_field
from typing import List, Optional, Union, Dict, Any, Tuple, Set, Callable, TYPE_CHECKING, TypeVar
from enum import Enum
from old_dnd.contextual import ModifiableValue, AdvantageStatus, ContextAwareCondition, ContextAwareBonus, BaseValue
from old_dnd.core import (BlockComponent,Ability,  AdvantageTracker, DurationType, RegistryHolder, Damage,Weapon, Armor, Condition)
from old_dnd.dnd_enums import (PrerequisiteType, DamageType,  RangeType, ShapeType, TargetType,
                               TargetRequirementType, UsageType,
                               RechargeType, ActionType, AttackType, SourceType,WeaponProperty, ArmorType,HitReason, AttackHand
                               )
from old_dnd.statsblock import StatsBlock



from old_dnd.logger import ConditionApplied, ConditionNotApplied, Logger, BaseLogEntry, SkillRollOut, SavingThrowRollOut, AttackRollOut, DamageRollOut, ActionType 
from old_dnd.logger import PrerequisiteDetails, PrerequisiteLog, ActionLog, ActionResultDetails, ActionCost

if TYPE_CHECKING:
    from old_dnd.statsblock import StatsBlock
    from old_dnd.conditions import Condition
    from old_dnd.battlemap import BattleMap, Entity

# Types
Position = Tuple[int, int]
Target = Union[StatsBlock, Position]


# Prerequisite system
class Prerequisite(BaseModel):
    name: str
    type: PrerequisiteType

    def check(self, source: StatsBlock, target: Target, context: Dict[str, Any]) -> Tuple[bool, PrerequisiteDetails]:
        raise NotImplementedError("Subclasses must implement this method")

ACTION_TYPE_TO_ATTRIBUTE = {
    ActionType.ACTION: "actions",
    ActionType.BONUS_ACTION: "bonus_actions",
    ActionType.REACTION: "reactions",
    ActionType.MOVEMENT: "movement",
    # Add any other action types here
}

class ActionEconomyPrerequisite(Prerequisite):
    type: PrerequisiteType = PrerequisiteType.ACTION_ECONOMY
    action_type: ActionType
    cost: int

    def check(self, source: StatsBlock, target: Target, context: Dict[str, Any]) -> Tuple[bool, PrerequisiteDetails]:
        attribute_name = ACTION_TYPE_TO_ATTRIBUTE.get(self.action_type)
        if attribute_name is None:
            raise ValueError(f"Unsupported action type: {self.action_type}")
        
        available = getattr(source.action_economy, attribute_name).apply(source).total_bonus
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
        if not target_position:
            raise ValueError("Target position not found")
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
        if not target_position:
            raise ValueError("Target position not found")
        distance = source.get_distance(target_position)
        if distance is None:
            raise ValueError("Distance could not be calculated")
        
        max_range = self.range_long if self.range_type == RangeType.RANGE and self.range_long else self.range_normal
        details = PrerequisiteDetails(distance=distance, required_range=max_range)
        print(f" Checking range \n Distance: {distance}, Max Range: {max_range}")
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
    name: str = "Path Exists"

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
    source: StatsBlock 
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
        costs = self._get_costs()
        
        if costs is None:
            return []
        costs = [cost for cost in costs if cost is not None]
        
        return [self._create_action_economy_prerequisite_single(cost) for cost in costs]

    def add_cost_prequisites(self):
        for prerequisite in self.create_action_economy_prerequisites():
            self.add_prerequisite(prerequisite.name, prerequisite)

    def remove_prerequisite(self, name: str):
        self.prerequisites.pop(name, None)

    def check_prerequisites(self, source: Optional[StatsBlock] = None, target: Optional[Target] = None, context: Optional[Dict[str, Any]] = None) -> Tuple[bool, Dict[str, PrerequisiteLog]]:
        source = source or self.source
        target = target or self.target
        context = context or self.context or {}
        
        if not isinstance(source, StatsBlock):
            raise TypeError(f"Expected source to be StatsBlock, got {type(source)}")
        if not source or not target:
            raise ValueError("Source and target must be provided either through binding or as method arguments.")
        
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
        source = source if source else self.source
        
        costs = self._get_costs(source)
        if costs is None:
            return
        costs = [cost for cost in costs if cost is not None]
        for cost in costs:
            #chheck for movement vs movemetns
            if cost.type == ActionType.MOVEMENT:
                action_economy_attr : ModifiableValue = getattr(source.action_economy, f"{cost.type.value.lower()}")
            else:
                action_economy_attr : ModifiableValue = getattr(source.action_economy, f"{cost.type.value.lower()}s")
            if cost.cost > 0:
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
    attack_hand: AttackHand
    default_prerequisites: bool = Field(default=True)

    def __init__(self, **data):
        super().__init__(**data)
        if self.default_prerequisites:
            self._add_default_prerequisites()

    @computed_field
    def weapon(self) -> Optional[Weapon]:
        return self.source.attacks_manager.get_weapon(self.attack_hand)

    @computed_field
    def attack_type(self) -> AttackType:
        if self.weapon:
            return self.weapon.attack_type
        elif self.attack_hand in [AttackHand.MELEE_RIGHT, AttackHand.MELEE_LEFT]:
            return AttackType.MELEE_SPELL
        else:
            return AttackType.RANGED_SPELL

    @computed_field
    def range_type(self) -> Optional[RangeType]:
        return self.weapon.range.type if self.weapon else None

    @computed_field
    def range_normal(self) -> Optional[int]:
        return self.weapon.range.normal if self.weapon else None

    @computed_field
    def range_long(self) -> Optional[int]:
        if self.weapon and self.weapon.range.type == RangeType.RANGE:
            return self.weapon.range.long
        return None

    @classmethod
    def from_weapon(cls, weapon: Weapon, source: 'Entity', hand: AttackHand):
        return cls(
            name=f"{weapon.name} Attack",
            description=f"Attack with {weapon.name}",
            attack_hand=hand,
            source=source
        )

    def _add_default_prerequisites(self):
        if isinstance(self.range_type, RangeType) and isinstance(self.range_normal, int) and isinstance(self.range_long, int):
            self.add_prerequisite("Range", RangePrerequisite(name="Range", range_type=self.range_type, range_normal=self.range_normal, range_long=self.range_long))
        self.add_prerequisite("Line of Sight", LineOfSightPrerequisite(name="Line of Sight"))

    def _get_costs(self, source: Optional[StatsBlock] = None) -> List[ActionCost]:
        if self.attack_hand in [AttackHand.MELEE_LEFT, AttackHand.RANGED_LEFT]:
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
        total_attack_bonus = attack_roll.attack_bonus.total_bonus.total_bonus
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
    path: Optional[List[Tuple[int, int]]] = None
    target: Optional[Tuple[int, int]] = None

    def __init__(self, **data):
        super().__init__(**data)
        self.add_prerequisite("Path Exists", PathExistsPrerequisite())
        if not self.path and self.target:
            self._set_path(self.source, self.target, self.context)

    def _get_costs(self, source: Optional[StatsBlock] = None) -> List[ActionCost]:
        if not self.path:
            return [ActionCost(type=ActionType.MOVEMENT, cost=0)]
        same_cell = len(self.path) - 1 == 0

        cost = (len(self.path) - 1) * 5 if not same_cell else 0
        return [ActionCost(type=ActionType.MOVEMENT, cost=cost)]

    def _set_path(self, source: StatsBlock, target: Tuple[int, int], context: Optional[Dict[str, Any]] = None) -> None:
        if not isinstance(target, tuple) or len(target) != 2:
            raise ValueError("Invalid target position")
        path = source.sensory.get_path_to(target)
        if not path:
            raise ValueError("No valid path to target")
        self.path = path

    def _apply(self, source: StatsBlock, target: Tuple[int, int], context: Dict[str, Any]) -> Tuple[bool, ActionResultDetails, List[Any], List[Any]]:
        start_position = source.position
        end_position = target
        movement_cost = (len(self.path) - 1) * 5 if self.path else 0
        if not source.sensory.battlemap_id:
            raise ValueError("Entity is not on a battlemap")
        battlemap = RegistryHolder.get_instance(source.sensory.battlemap_id)
        if TYPE_CHECKING:
            assert isinstance(battlemap, BattleMap)
            assert isinstance(source, Entity)

        
        if not battlemap:
            return False, ActionResultDetails(success=False, reason="Entity is not on a battlemap"), [], []

        # Move the entity
        if self.step_by_step and self.path:
            for step in self.path[1:]:
                battlemap.move_entity_without_update(source, step)
        else:
            battlemap.move_entity_without_update(source, end_position)

        # Update entity senses after movement is complete
        battlemap.update_entity_senses(source)

        result_details = ActionResultDetails(
            success=True,
            reason=f"Moved from {start_position} to {end_position}",
            effects={
                "start_position": start_position,
                "end_position": end_position,
                "movement_cost": movement_cost,
                "path": self.path
            }
        )

        return True, result_details, [], []


    def __str__(self):
        movement_type = "Step-by-step" if self.step_by_step else "Direct"
        return f"{self.name}: {movement_type} movement to {self.target}"