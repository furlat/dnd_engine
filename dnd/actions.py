from pydantic import BaseModel, Field, computed_field
from typing import List, Optional, Union, Dict, Any, Tuple, Set, Callable, TYPE_CHECKING
from enum import Enum
from dnd.contextual import ModifiableValue, AdvantageStatus, ContextAwareCondition, ContextAwareBonus
from dnd.core import (Dice, Ability,  AdvantageTracker, DurationType, RegistryHolder)
from dnd.equipment import Weapon, Armor, WeaponProperty, ArmorType
from dnd.dnd_enums import (DamageType,  RangeType, ShapeType, TargetType,
                               TargetRequirementType, UsageType,
                               RechargeType, ActionType, AttackType)



if TYPE_CHECKING:
    from dnd.statsblock import StatsBlock
    from dnd.conditions import Condition
    from dnd.battlemap import BattleMap, Entity

class ActionCost(BaseModel):
    type: ActionType
    cost: int

class LimitedRecharge(BaseModel):
    recharge_type: RechargeType
    recharge_rate: int

class LimitedUsage(BaseModel):
    usage_type: UsageType
    usage_number: int
    recharge: Union[LimitedRecharge, None]
class Range(BaseModel):
    type: RangeType
    normal: int
    long: Optional[int] = None

    def __str__(self):
        if self.type == RangeType.REACH:
            return f"{self.normal} ft."
        elif self.type == RangeType.RANGE:
            return f"{self.normal}/{self.long} ft." if self.long else f"{self.normal} ft."

class Targeting(BaseModel):
    type: TargetType
    shape: Union[ShapeType, None] = None
    size: Union[int, None] = None  # size of the area of effect
    line_of_sight: bool = True
    number_of_targets: Union[int, None] = None
    requirement: TargetRequirementType = TargetRequirementType.ANY
    description: str = ""

    def target_docstring(self):
        target_str = self.type.value
        if self.type == TargetType.AREA and self.shape and self.size:
            target_str += f" ({self.shape.value}, {self.size} ft.)"
        if self.number_of_targets:
            target_str += f", up to {self.number_of_targets} targets"
        if self.line_of_sight:
            target_str += ", requiring line of sight"
        if self.requirement != TargetRequirementType.ANY:
            target_str += f", {self.requirement.value.lower()} targets only"
        return target_str

def add_default_prerequisites(action:'Action'):
    action.add_prerequisite("Line of Sight", check_line_of_sight)
    action.add_prerequisite("Range", check_range)

def check_line_of_sight(stats_block: 'StatsBlock', target: 'StatsBlock', context: Optional[Dict[str, Any]] = None) -> bool:
    return stats_block.is_visible(target.sensory.origin)

def check_range(stats_block: 'StatsBlock', target: 'StatsBlock', context: Optional[Dict[str, Any]] = None) -> bool:
    if not context:
        return False
    action : Union[Attack,DcAttack]= context.get('action')
    if not action or not hasattr(action, 'range'):
        return False
    distance = stats_block.sensory.distance_matrix.get_distance(target.sensory.origin)
    return distance is not None and distance <= action.range.normal

def check_valid_path(stats_block: 'StatsBlock', target=None, context=dict) -> bool:
    path  = context.get('path', [])
    movement_budget = stats_block.action_economy.movement.get_value(stats_block)
    return (len(path) - 1 <= movement_budget and 
            all(stats_block.sensory.fov.is_visible(pos) for pos in path) and
            stats_block.sensory.paths.get_path_to(path[-1]) == path)

class Damage(BaseModel):
    dice: Dice
    type: DamageType

    def average_damage(self):
        return self.dice.expected_value()

class Action(BaseModel):
    name: str
    description: str
    cost: List[ActionCost]
    limited_usage: Union[LimitedUsage, None]
    targeting: Targeting
    stats_block: 'StatsBlock'
    prerequisite_conditions: Dict[str, ContextAwareCondition] = Field(default_factory=dict)

    def add_prerequisite(self, name: str, condition: ContextAwareCondition):
        self.prerequisite_conditions[name] = condition

    def remove_prerequisite(self, name: str):
        self.prerequisite_conditions.pop(name, None)

    def prerequisite(self, stats_block: 'StatsBlock', target: 'StatsBlock', context: Optional[Dict[str, Any]] = None) -> Tuple[bool, List[str]]:
        failed_conditions = []
        for condition_name, condition_check in self.prerequisite_conditions.items():
            if not condition_check(stats_block, target, context):
                failed_conditions.append(f"Failed condition: {condition_name}")
        return len(failed_conditions) == 0, failed_conditions

    def apply(self, targets: Union[List['StatsBlock'], 'StatsBlock'], context: Optional[Dict[str, Any]] = None) -> List[Tuple[bool, str]]:
        if not isinstance(targets, list):
            targets = [targets]
        else:
            raise ValueError("Targets must be a list of StatsBlock objects or a single StatsBlock object")
        
        results = []
        for target in targets:
            can_perform, failed_conditions = self.prerequisite(self.stats_block, target, context)
            if not can_perform:
                results.append((False, "; ".join(failed_conditions)))
            else:
                results.append(self._apply(target, context))
        
        return results

    def _apply(self, target: 'StatsBlock', context: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
        raise NotImplementedError("Subclasses must implement this method")



class Attack(Action):
    attack_type: AttackType
    ability: Ability
    range: Range
    damage: List[Damage]
    weapon: Optional[Weapon] = None
    is_critical_hit: bool = False
    hit_bonus: ModifiableValue = Field(default_factory=lambda: ModifiableValue(base_value=0))

    def __init__(self, **data):
        super().__init__(**data)
        self.update_hit_bonus()
        add_default_prerequisites(self)

    def _apply(self, target: 'StatsBlock', context: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
        hit, details = self.roll_to_hit(target, context, verbose=True)
        
        if hit:
            damage = self.roll_damage(context)
            target.take_damage(damage)
            return True, f"Hit! Dealt {damage} damage to {target.name}. {target.name} now has {target.current_hit_points}/{target.max_hit_points} HP."
        else:
            return False, f"Miss! Attack roll ({details['roll']}) did not meet target AC ({details['armor_class']})."

    def update_hit_bonus(self):
        ability_modifier = getattr(self.stats_block.ability_scores, self.ability.value.lower()).get_modifier(self.stats_block)
        self.hit_bonus.base_value = ability_modifier + self.stats_block.proficiency_bonus

    @computed_field
    def average_damage(self) -> float:
        ability_modifier = getattr(self.stats_block.ability_scores, self.ability.value.lower()).get_modifier(self.stats_block)
        return sum(d.dice.expected_value() + ability_modifier for d in self.damage)

    def action_docstring(self):
        attack_range = str(self.range)
        ability_modifier = getattr(self.stats_block.ability_scores, self.ability.value.lower()).get_modifier(self.stats_block)
        damage_strings = [
            f"{d.dice.dice_count}d{d.dice.dice_value} + {ability_modifier} {d.type.value} damage"
            for d in self.damage
        ]
        damage_string = " plus ".join(damage_strings)
        return f"{self.attack_type.value} Attack: +{self.hit_bonus.get_value(self.stats_block)} to hit, {attack_range}, {self.targeting.target_docstring()}. Hit: {damage_string}. Average damage: {self.average_damage:.1f}."

    def add_contextual_advantage(self, source: str, condition: ContextAwareCondition):
        self.hit_bonus.add_advantage_condition(source, condition)

    def add_contextual_disadvantage(self, source: str, condition: ContextAwareCondition):
        self.hit_bonus.add_disadvantage_condition(source, condition)

    def add_contextual_bonus(self, source: str, bonus: ContextAwareBonus):
        self.hit_bonus.add_bonus(source, bonus)

    def add_auto_fail_condition(self, source: str, condition: ContextAwareCondition):
        self.hit_bonus.add_auto_fail_self_condition(source, condition)

    def add_auto_success_condition(self, source: str, condition: ContextAwareCondition):
        self.hit_bonus.add_auto_success_self_condition(source, condition)

    def add_auto_critical_condition(self, source: str, condition: ContextAwareCondition):
        self.hit_bonus.add_auto_critical_self_condition(source, condition)

    def roll_to_hit(self, target: 'StatsBlock', context: Optional[Dict[str, Any]] = None, verbose: bool = False) -> Union[bool, Tuple[bool, Dict[str, Any]]]:
        details = {
            "auto_fail": False,
            "auto_success": False,
            "target_causes_auto_fail": False,
            "target_causes_auto_success": False,
            "advantage_status": AdvantageStatus.NONE,
            "is_auto_critical": False,
            "roll": 0,
            "total_hit_bonus": 0,
            "armor_class": target.armor_class.get_value(target, self.stats_block, context),
            "is_critical_hit": False,
            "self_advantages": [],
            "self_disadvantages": [],
            "target_advantages": [],
            "target_disadvantages": []
        }

        # Check for auto-fail conditions
        if self.hit_bonus.is_auto_fail(self.stats_block, target, context):
            self.is_critical_hit = False
            details["auto_fail"] = True
            details["hit"] = False
            return (False, details) if verbose else False
        
        # Check if the target's armor class causes auto-fail or auto-success
        elif target.armor_class.gives_attacker_auto_fail(target, self.stats_block, context):
            self.is_critical_hit = False
            details["target_causes_auto_fail"] = True
            details["hit"] = False
            return (False, details) if verbose else False
        
         # Check for auto-critical conditions
        elif self.hit_bonus.is_auto_critical(self.stats_block, target, context):
            self.is_critical_hit = True
            details["is_auto_critical"] = True
            details["hit"] = True
            return (True, details) if verbose else True

        # Check if the target's armor class causes auto-critical
        elif target.armor_class.gives_attacker_auto_critical(target, self.stats_block, context):
            self.is_critical_hit = True
            details["is_auto_critical"] = True
            details["hit"] = True
            return (True, details) if verbose else True

        # Check for auto-success conditions
        elif self.hit_bonus.is_auto_success(self.stats_block, target, context):
            self.is_critical_hit = True
            details["auto_success"] = True
            details["hit"] = True
            return (True, details) if verbose else True

     # Check if the target's armor class causes auto-success

        elif target.armor_class.gives_attacker_auto_success(target, self.stats_block, context):
            self.is_critical_hit = True
            details["target_causes_auto_success"] = True
            details["hit"] = True
            return (True, details) if verbose else True

        total_hit_bonus = self.hit_bonus.get_value(self.stats_block, target, context)
        advantage_status = self.hit_bonus.get_advantage_status(self.stats_block, target, context)

        # Check if the target's armor class gives advantage to the attacker
        if target.armor_class.gives_attacker_advantage(target, self.stats_block, context):
            if advantage_status == AdvantageStatus.DISADVANTAGE:
                advantage_status = AdvantageStatus.NONE
            else:
                advantage_status = AdvantageStatus.ADVANTAGE
        # Check if the target's armor class gives disadvantage to the attacker
        elif target.armor_class.gives_attacker_disadvantage(target, self.stats_block, context):
            if advantage_status == AdvantageStatus.ADVANTAGE:
                advantage_status = AdvantageStatus.NONE
            else:
                advantage_status = AdvantageStatus.DISADVANTAGE

        dice = Dice(dice_count=1, dice_value=20, modifier=total_hit_bonus, advantage_status=advantage_status)
        roll, roll_status = dice.roll_with_advantage()

        self.is_critical_hit = roll_status == "critical_hit"
        hit = roll >= target.armor_class.get_value(target, self.stats_block, context)

        details.update({
            "hit": hit,
            "roll": roll,
            "roll_status": roll_status,
            "total_hit_bonus": total_hit_bonus,
            "advantage_status": advantage_status,
            "is_critical_hit": self.is_critical_hit,
            "self_advantages": self.hit_bonus.self_effects.advantage_conditions,
            "self_disadvantages": self.hit_bonus.self_effects.disadvantage_conditions,
            "target_advantages": target.armor_class.base_ac.target_effects.advantage_conditions,
            "target_disadvantages": target.armor_class.base_ac.target_effects.disadvantage_conditions
        })

        return (hit, details) if verbose else hit


    def remove_effect(self, source: str):
        self.hit_bonus.remove_effect(source)

    def roll_damage(self, context: Optional[Dict[str, Any]] = None) -> int:
        total_damage = 0
        for damage in self.damage:
            dice = Dice(
                dice_count=damage.dice.dice_count,
                dice_value=damage.dice.dice_value,
                modifier=damage.dice.modifier,
                advantage_status=self.hit_bonus.get_advantage_status(self.stats_block, context=context)
            )
            total_damage += dice.roll(is_critical=self.is_critical_hit)
        return total_damage


class DcAttack(Action):
    ability: Ability
    saving_throw: Ability
    range: Range
    damage: List[Damage]
    dc_bonus: ModifiableValue = Field(default_factory=lambda: ModifiableValue(base_value=0))
    is_critical_fail: bool = False
    half_damage_on_success: bool = True
    conditions_on_success: List['Condition'] = Field(default_factory=list)
    conditions_on_failure: List['Condition'] = Field(default_factory=list)

    def __init__(self, **data):
        super().__init__(**data)
        self.update_dc()
        add_default_prerequisites(self)

    def update_dc(self):
        ability_modifier = getattr(self.stats_block.ability_scores, self.ability.value.lower()).get_modifier(self.stats_block)
        self.dc_bonus.base_value = 8 + ability_modifier + self.stats_block.proficiency_bonus

    def _apply(self, target: 'StatsBlock', context: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
        save_success, details = self.roll_saving_throw(target, context, verbose=True)
        
        if save_success:
            success, message = self._apply_success(target, details, context)
            self._apply_conditions(target, self.conditions_on_success)
        else:
            success, message = self._apply_failure(target, details, context)
            self._apply_conditions(target, self.conditions_on_failure)
        
        return success, message

    def _apply_success(self, target: 'StatsBlock', details: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
        if self.half_damage_on_success and self.damage:
            damage = self.roll_damage(context) // 2
            target.take_damage(damage)
            return True, f"Target succeeded save but takes half damage! Dealt {damage} damage to {target.name}. {target.name} now has {target.current_hit_points}/{target.max_hit_points} HP."
        else:
            return False, f"Target succeeded save! No damage taken."

    def _apply_failure(self, target: 'StatsBlock', details: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
        if self.damage:
            damage = self.roll_damage(context)
            target.take_damage(damage)
            return True, f"Target failed save! Dealt {damage} damage to {target.name}. {target.name} now has {target.current_hit_points}/{target.max_hit_points} HP."
        else:
            return True, f"Target failed save!"

    def _apply_conditions(self, target: 'StatsBlock', conditions: List['Condition']) -> None:
        for condition in conditions:
            target.apply_condition(condition)

    def roll_saving_throw(self, target: 'StatsBlock', context: Optional[Dict[str, Any]] = None, verbose: bool = False) -> Union[bool, Tuple[bool, Dict[str, Any]]]:
        details = {
            "auto_fail": False,
            "auto_success": False,
            "advantage_status": AdvantageStatus.NONE,
            "roll": 0,
            "dc": self.dc_bonus.get_value(self.stats_block, target, context),
            "is_critical_fail": False,
        }

        # Check for auto-fail conditions
        if target.saving_throws.get_ability(self.saving_throw).bonus.is_auto_fail(target, self.stats_block, context):
            self.is_critical_fail = True
            details["auto_fail"] = True
            details["save_success"] = False
            return (False, details) if verbose else False

        # Check for auto-success conditions
        if target.saving_throws.get_ability(self.saving_throw).bonus.is_auto_success(target, self.stats_block, context):
            self.is_critical_fail = False
            details["auto_success"] = True
            details["save_success"] = True
            return (True, details) if verbose else True

        saving_throw = target.saving_throws.get_ability(self.saving_throw)
        advantage_status = saving_throw.bonus.get_advantage_status(target, self.stats_block, context)

        dice = Dice(dice_count=1, dice_value=20, modifier=saving_throw.get_bonus(target), advantage_status=advantage_status)
        roll, roll_status = dice.roll_with_advantage()

        self.is_critical_fail = roll_status == "critical_failure"
        save_success = roll >= details["dc"]

        details.update({
            "save_success": save_success,
            "roll": roll,
            "roll_status": roll_status,
            "advantage_status": advantage_status,
            "is_critical_fail": self.is_critical_fail,
        })

        return (save_success, details) if verbose else save_success

    def roll_damage(self, context: Optional[Dict[str, Any]] = None) -> int:
        total_damage = 0
        for damage in self.damage:
            dice = Dice(
                dice_count=damage.dice.dice_count,
                dice_value=damage.dice.dice_value,
                modifier=damage.dice.modifier,
                advantage_status=AdvantageStatus.NONE
            )
            total_damage += dice.roll(is_critical=self.is_critical_fail)
        return total_damage

    def add_dc_bonus(self, source: str, bonus: ContextAwareBonus):
        self.dc_bonus.add_bonus(source, bonus)

    def remove_dc_bonus(self, source: str):
        self.dc_bonus.remove_effect(source)

    def action_docstring(self):
        attack_range = str(self.range)
        damage_strings = [
            f"{d.dice.dice_count}d{d.dice.dice_value} {d.type.value} damage"
            for d in self.damage
        ]
        damage_string = " plus ".join(damage_strings) if damage_strings else "No damage"
        success_conditions = ", ".join([c.name for c in self.conditions_on_success])
        failure_conditions = ", ".join([c.name for c in self.conditions_on_failure])
        return (f"DC Attack: DC {self.dc_bonus.get_value(self.stats_block)} {self.saving_throw.value} saving throw, {attack_range}, "
                f"{self.targeting.target_docstring()}. Failed Save: {damage_string}. "
                f"On success: {success_conditions if success_conditions else 'No conditions'}. "
                f"On failure: {failure_conditions if failure_conditions else 'No conditions'}. "
                f"Average damage: {self.average_damage:.1f}.")

    @computed_field
    def average_damage(self) -> float:
        return sum(d.dice.expected_value() for d in self.damage)
    
class SelfCondition(Action):
    conditions: List['Condition'] = Field(default_factory=list)

    def _apply(self, target: 'StatsBlock', context: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
        for condition in self.conditions:
            self.stats_block.apply_condition(condition)
        return True, f"Applied {', '.join([c.name for c in self.conditions])} to self."

    def action_docstring(self):
        conditions_str = ', '.join([c.name for c in self.conditions])
        return f"{self.name}: Applies {conditions_str} to self. {self.description}"


class MovementAction(Action):
    path: List[Tuple[int, int]]
    step_by_step: bool = False

    def __init__(self, **data):
        super().__init__(**data)
        self.add_prerequisite("Valid Path", check_valid_path)

    def _apply(self, target=None, context=None) -> Tuple[bool, str]:
        battlemap : Optional['BattleMap'] = RegistryHolder.get_instance(self.stats_block.battlemap_id)
        if not battlemap:
            return False, "Entity is not on a battlemap."

        start_position = self.stats_block.get_position()
        end_position = self.path[-1]
        movement_cost = len(self.path) - 1

        if self.step_by_step:
            for step in self.path[1:]:  # Skip the first step as it's the starting position
                battlemap.move_entity(self.stats_block, step)
                battlemap.update_entity_los(self.stats_block)
                # Here you could add additional logic for each step if needed
        else:
            battlemap.move_entity(self.stats_block, end_position)
            battlemap.update_entity_los(self.stats_block)

        self.stats_block.action_economy.movement.base_value -= movement_cost

        return True, f"Moved from {start_position} to {end_position}, using {movement_cost} movement points."

    def action_docstring(self):
        return f"{self.name}: Move along a specified path. Path length: {len(self.path) - 1} squares. {'Step-by-step movement.' if self.step_by_step else 'Direct movement to end position.'}"

    def apply(self, targets=None, context=None) -> List[Tuple[bool, str]]:
        if context is None:
            context = {}
        context['path'] = self.path
        return super().apply([self.stats_block], context)