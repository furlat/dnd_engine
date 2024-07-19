from pydantic import BaseModel, Field, computed_field
from typing import List, Optional, Union, Dict, Any, Tuple, Set, Callable, TYPE_CHECKING
from enum import Enum
from dnd.contextual import ModifiableValue, AdvantageStatus, ContextAwareCondition, ContextAwareBonus
from dnd.core import (Dice, Ability,  AdvantageTracker, DurationType, RegistryHolder, Damage)
from dnd.equipment import Weapon, Armor, WeaponProperty, ArmorType
from dnd.dnd_enums import (DamageType,  RangeType, ShapeType, TargetType,
                               TargetRequirementType, UsageType,
                               RechargeType, ActionType, AttackType, SourceType)


from dnd.logger import PrerequisiteLog,ActionLog, ActionResultDetails, Logger, DamageRollLog, DiceRollLog, PrerequisiteDetails

from dnd.newlogs import (AttackLog, HitRollLog, DamageLog, DamageRollLog, 
                          HealthChangeLog, DiceRollLog, Modifier, EffectSource, 
                          ConditionInfo, DamageTypeEffect, AttackResult, AdvantageSource, DisadvantageSource)
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

# def add_default_prerequisites(action:'Action'):
#     action.add_prerequisite("Line of Sight", check_line_of_sight)
#     action.add_prerequisite("Range", check_range)





ContextAwarePrerequisite = Callable[['StatsBlock', 'StatsBlock', 'Action'], Tuple[bool, PrerequisiteDetails]]
def check_valid_path(stats_block: 'StatsBlock', target: 'StatsBlock', action: 'Action') -> Tuple[bool, PrerequisiteDetails]:
    details = PrerequisiteDetails()

    context = action.context if hasattr(action, 'context') else None
    if not context:
        details.failure_reason = "Context is missing"
        return False, details

    path = context.get('path', [])
    if not path:
        details.failure_reason = "Path is missing"
        return False, details

    movement_budget = stats_block.action_economy.movement.get_value(stats_block)
    path_length = len(path) - 1  # assuming path includes start and end points

    details.distance = path_length
    details.required_range = movement_budget

    all_visible = all(stats_block.sensory.fov.is_visible(pos) for pos in path)
    details.is_visible = all_visible

    if path_length > movement_budget:
        details.failure_reason = f"Path length exceeds movement budget. Path length: {path_length}, Movement budget: {movement_budget}"
        return False, details

    if not all_visible:
        details.failure_reason = "Not all positions in the path are visible"
        return False, details

    return True, details

def check_line_of_sight(stats_block: 'StatsBlock', target: 'StatsBlock', action: 'Action') -> Tuple[bool, PrerequisiteDetails]:
    is_visible = stats_block.is_visible(target.sensory.origin)
    details = PrerequisiteDetails(is_visible=is_visible)
    
    if not is_visible:
        details.failure_reason = "Target is not visible"
    
    return is_visible, details

def check_range(stats_block: 'StatsBlock', target: 'StatsBlock', action: 'Action') -> Tuple[bool, PrerequisiteDetails]:
    details = PrerequisiteDetails()

    if not hasattr(action, 'range'):
        details.failure_reason = "Action does not have range attribute"
        return False, details

    distance = stats_block.sensory.distance_matrix.get_distance(target.sensory.origin)
    distance = distance * 5  # in feet
    details.distance = distance
    details.required_range = action.range.normal
    
    if distance is None:
        details.failure_reason = "Distance could not be calculated"
        return False, details
    
    if distance > action.range.normal:
        details.failure_reason = f"Target is out of range. Distance: {distance}, Range: {action.range.normal}"
        return False, details

    return True, details

class Action(BaseModel):
    name: str
    description: str
    cost: List[ActionCost]
    limited_usage: Union[LimitedUsage, None]
    targeting: Targeting
    stats_block: 'StatsBlock'
    prerequisite_conditions: Dict[str, ContextAwarePrerequisite] = Field(default_factory=dict)

    def add_prerequisite(self, name: str, condition: ContextAwarePrerequisite):
        self.prerequisite_conditions[name] = condition

    def remove_prerequisite(self, name: str):
        self.prerequisite_conditions.pop(name, None)

    def prerequisite(self, stats_block: 'StatsBlock', target: 'StatsBlock') -> Tuple[bool, List[PrerequisiteLog]]:
        prerequisite_logs = []
        for condition_name, condition_check in self.prerequisite_conditions.items():
            passed, details = condition_check(stats_block, target, self)
            log = PrerequisiteLog(
                condition_name=condition_name,
                passed=passed,
                source_id=stats_block.id,
                target_id=target.id,
                details=details
                )
            
            prerequisite_logs.append(log)

        all_passed = all(log.passed for log in prerequisite_logs)
        return all_passed, prerequisite_logs

    def apply(self, targets: Union[List['StatsBlock'], 'StatsBlock']) -> List[ActionLog]:
        if not isinstance(targets, list):
            targets = [targets]
        
        action_logs = []
        for target in targets:
            prerequisites_passed, prerequisite_logs = self.prerequisite(self.stats_block, target)
            
            if not prerequisites_passed:
                action_log = ActionLog(
                    action_name=self.name,
                    source_id=self.stats_block.id,
                    target_id=target.id,
                    success=False,
                    prerequisite_logs=prerequisite_logs,
                    details=PrerequisiteDetails(
                        failure_reason="Prerequisites not met",
                        auto_failure=True
                    )
                )
            else:
                success, result_details, dice_rolls, damage_rolls = self._apply(target)
                action_log = ActionLog(
                    action_name=self.name,
                    source_id=self.stats_block.id,
                    target_id=target.id,
                    success=success,
                    prerequisite_logs=prerequisite_logs,
                    dice_rolls=dice_rolls,
                    damage_rolls=damage_rolls,
                    details=result_details
                )
            
            action_logs.append(action_log)
            Logger.log(action_log)
        
        return action_logs

    def _apply(self, target: 'StatsBlock') -> Tuple[bool, ActionResultDetails, List[DiceRollLog], List[DamageRollLog]]:
        raise NotImplementedError("Subclasses must implement this method")

def add_default_prerequisites(action: 'Action'):
    action.add_prerequisite("Line of Sight", check_line_of_sight)
    action.add_prerequisite("Range", check_range)



class Attack(Action):
    attack_type: AttackType
    ability: Ability
    range: Range
    damage: List[Damage]
    weapon: Optional[Weapon] = None
    is_critical_hit: bool = False
    weapon_hit_bonus: ModifiableValue = Field(default_factory=lambda: ModifiableValue(base_value=0))
    weapon_damage_bonus:  ModifiableValue = Field(default_factory=lambda: ModifiableValue(base_value=0))

    def __init__(self, **data):
        super().__init__(**data)
        self.update_hit_bonus()
        add_default_prerequisites(self)

    def _apply(self, target: 'StatsBlock') -> AttackLog:
        hit_roll_log = self.roll_to_hit(target)
        damage_log = None
        health_change_log = None

        if hit_roll_log.is_hit:
            damage_log = self.roll_damage()
            health_change_log = target.health.take_damage(damage_log.final_damage, self.damage[-1].type, target, self.stats_block)

        return AttackLog(
            entity_id=self.stats_block.id,
            source_entity_id=self.stats_block.id,
            target_entity_id=target.id,
            weapon_name=self.weapon.name if self.weapon else self.name,
            attack_type=self.attack_type,
            attacker_conditions=self._get_condition_infos(self.stats_block),
            target_conditions=self._get_condition_infos(target),
            hit_roll_log=hit_roll_log,
            damage_log=damage_log,
            health_change_log=health_change_log,
            final_result=self._determine_attack_result(hit_roll_log)
        )

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

    def add_contextual_advantage(self, source: str, condition: 'ContextAwareCondition'):
        self.hit_bonus.add_advantage_condition(source, condition)

    def add_contextual_disadvantage(self, source: str, condition: 'ContextAwareCondition'):
        self.hit_bonus.add_disadvantage_condition(source, condition)

    def add_contextual_bonus(self, source: str, bonus: 'ContextAwareBonus'):
        self.hit_bonus.add_bonus(source, bonus)

    def add_auto_fail_condition(self, source: str, condition: 'ContextAwareCondition'):
        self.hit_bonus.add_auto_fail_self_condition(source, condition)

    def add_auto_success_condition(self, source: str, condition: 'ContextAwareCondition'):
        self.hit_bonus.add_auto_success_self_condition(source, condition)

    def add_auto_critical_condition(self, source: str, condition: 'ContextAwareCondition'):
        self.hit_bonus.add_auto_critical_self_condition(source, condition)

    def roll_to_hit(self, target: 'StatsBlock', context: Optional[Dict[str, Any]] = None) -> HitRollLog:
        total_hit_bonus = self.hit_bonus.get_value(self.stats_block, target, context)
        advantage_status = self.hit_bonus.get_advantage_status(self.stats_block, target, context)
        target_ac = target.armor_class.get_value(target, self.stats_block, context)

        # Check for auto-fail conditions
        if self.hit_bonus.is_auto_fail(self.stats_block, target, context) or target.armor_class.gives_attacker_auto_fail(target, self.stats_block, context):
            return self._create_auto_fail_hit_roll_log(target_ac)

        # Check for auto-critical conditions
        if self.hit_bonus.is_auto_critical(self.stats_block, target, context) or target.armor_class.gives_attacker_auto_critical(target, self.stats_block, context):
            return self._create_auto_critical_hit_roll_log(target_ac)

        # Check for auto-success conditions
        if self.hit_bonus.is_auto_success(self.stats_block, target, context) or target.armor_class.gives_attacker_auto_success(target, self.stats_block, context):
            return self._create_auto_success_hit_roll_log(target_ac)

        # Check if the target's armor class affects advantage/disadvantage
        if target.armor_class.gives_attacker_advantage(target, self.stats_block, context):
            if advantage_status == AdvantageStatus.DISADVANTAGE:
                advantage_status = AdvantageStatus.NONE
            else:
                advantage_status = AdvantageStatus.ADVANTAGE
        if target.armor_class.gives_attacker_disadvantage(target, self.stats_block, context):
            if advantage_status == AdvantageStatus.ADVANTAGE:
                advantage_status = AdvantageStatus.NONE
            else:
                advantage_status = AdvantageStatus.DISADVANTAGE

        dice = Dice(dice_count=1, dice_value=20, modifier=total_hit_bonus, advantage_status=advantage_status)
        roll, is_critical, dice_roll_log = dice.roll_with_advantage()

        self.is_critical_hit = is_critical
        is_hit = roll >= target_ac

        return HitRollLog(
            entity_id=self.stats_block.id,
            dice_roll=DiceRollLog(
                entity_id=self.stats_block.id,
                dice_size=20,
                roll_results=dice_roll_log.rolls,
                modifiers=[Modifier(
                    value=total_hit_bonus,
                    effect_source=EffectSource(
                        source_type=SourceType.ABILITY,
                        responsible_entity_id=self.stats_block.id,
                        ability_name=self.ability.value,
                        description=f"{self.ability.value} modifier and proficiency"
                    )
                )],
                advantage_status=advantage_status,
                advantage_sources=self._get_advantage_sources(),
                disadvantage_sources=self._get_disadvantage_sources(),
                total_roll=roll,
                is_critical=is_critical,
                auto_success=False,
                auto_failure=False
            ),
            target_ac=target_ac,
            is_hit=is_hit,
            auto_hit_source=None,
            auto_miss_source=None,
            auto_critical_source=None
        )

    def roll_damage(self) -> DamageLog:
        damage_rolls = []
        total_damage_by_type = {}
        final_damage = 0

        for damage in self.damage:
            dice_count = damage.dice.dice_count * (2 if self.is_critical_hit else 1)
            dice = Dice(dice_count=dice_count, dice_value=damage.dice.dice_value, modifier=damage.dice.modifier)
            roll, dice_roll_log = dice.roll()
            
            damage_roll_log = DamageRollLog(
                entity_id=self.stats_block.id,
                damage_type=damage.type,
                dice_roll=dice_roll_log
            )
            damage_rolls.append(damage_roll_log)
            total_damage_by_type[damage.type] = total_damage_by_type.get(damage.type, 0) + roll
            final_damage += roll

        return DamageLog(
            entity_id=self.stats_block.id,
            damage_rolls=damage_rolls,
            total_damage_by_type=total_damage_by_type,
            final_damage=final_damage
        )

    def remove_effect(self, source: str):
        self.hit_bonus.remove_effect(source)

    def chance_to_hit(self, target: 'StatsBlock',context:Optional[Dict]=None) -> Tuple[Optional[int], float, str]:
        if self.hit_bonus.is_auto_fail(self.stats_block, target):
            return None, 0.0, "Auto-fail"
        if self.hit_bonus.is_auto_critical(self.stats_block, target) or self.hit_bonus.is_auto_success(self.stats_block, target):
            return 1, 1.0, "Auto-hit"

        total_hit_bonus = self.hit_bonus.get_value(self.stats_block, target)
        target_ac = target.armor_class.get_value(target, self.stats_block)
        min_roll_to_hit = max(1, target_ac - total_hit_bonus)

        if min_roll_to_hit > 20:
            return None, 0.0, "Impossible to hit"
        if min_roll_to_hit <= 1:
            return 1, 1.0, "Always hits"

        base_probability = (21 - min_roll_to_hit) / 20
        advantage_status = self.hit_bonus.get_advantage_status(self.stats_block, target)
        # Check if the target's armor class affects advantage/disadvantage
        if target.armor_class.gives_attacker_advantage(target, self.stats_block, context):
            if advantage_status == AdvantageStatus.DISADVANTAGE:
                advantage_status = AdvantageStatus.NONE
            else:
                advantage_status = AdvantageStatus.ADVANTAGE
        if target.armor_class.gives_attacker_disadvantage(target, self.stats_block, context):
            if advantage_status == AdvantageStatus.ADVANTAGE:
                advantage_status = AdvantageStatus.NONE
            else:
                advantage_status = AdvantageStatus.DISADVANTAGE

        
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

    def _get_condition_infos(self, entity: 'StatsBlock') -> List[ConditionInfo]:
        return [
            ConditionInfo(
                condition_name=condition.name,
                affected_entity_id=entity.id,
                source_entity_id=condition.source_entity_id,
                source_ability=condition.source_ability,
                duration=condition.duration.time if hasattr(condition.duration, 'time') else None,
            ) for condition in entity.active_conditions.values()
        ]

    def _get_advantage_sources(self) -> List[AdvantageSource]:
        return [AdvantageSource(
            effect_source=EffectSource(
                source_type=SourceType.CONDITION,
                responsible_entity_id=self.stats_block.id,
                description=source
            ),
            description=source
        ) for source, _ in self.hit_bonus.self_effects.advantage_conditions]

    def _get_disadvantage_sources(self) -> List[DisadvantageSource]:
        return [DisadvantageSource(
            effect_source=EffectSource(
                source_type=SourceType.CONDITION,
                responsible_entity_id=self.stats_block.id,
                description=source
            ),
            description=source
        ) for source, _ in self.hit_bonus.self_effects.disadvantage_conditions]

    def _get_auto_source(self, auto_type: str) -> EffectSource:
        return EffectSource(
            source_type=SourceType.CONDITION,
            responsible_entity_id=self.stats_block.id,
            description=f"Auto {auto_type.replace('auto_', '').replace('_', ' ')}"
        )

    def _determine_attack_result(self, hit_roll_log: HitRollLog) -> AttackResult:
        if not hit_roll_log.is_hit:
            return AttackResult.MISS
        elif hit_roll_log.dice_roll.is_critical:
            return AttackResult.CRITICAL_HIT
        else:
            return AttackResult.HIT

    def _create_auto_fail_hit_roll_log(self, target_ac: int) -> HitRollLog:
        return HitRollLog(
            entity_id=self.stats_block.id,
            dice_roll=DiceRollLog(
                entity_id=self.stats_block.id,
                dice_size=20,
                roll_results=[1],
                modifiers=[],
                advantage_status=AdvantageStatus.NONE,
                advantage_sources=[],
                disadvantage_sources=[],
                total_roll=1,
                is_critical=False,
                auto_success=False,
                auto_failure=True
            ),
            target_ac=target_ac,
            is_hit=False,
            auto_hit_source=None,
            auto_miss_source=self._get_auto_source("auto_fail"),
            auto_critical_source=None
        )

    def _create_auto_critical_hit_roll_log(self, target_ac: int) -> HitRollLog:
        self.is_critical_hit = True
        return HitRollLog(
            entity_id=self.stats_block.id,
            dice_roll=DiceRollLog(
                entity_id=self.stats_block.id,
                dice_size=20,
                roll_results=[20],
                modifiers=[],
                advantage_status=AdvantageStatus.NONE,
                advantage_sources=[],
                disadvantage_sources=[],
                total_roll=20,
                is_critical=True,
                auto_success=True,
                auto_failure=False
            ),
            target_ac=target_ac,
            is_hit=True,
            auto_hit_source=None,
            auto_miss_source=None,
            auto_critical_source=self._get_auto_source("auto_critical")
        )

    def _create_auto_success_hit_roll_log(self, target_ac: int) -> HitRollLog:
        return HitRollLog(
            entity_id=self.stats_block.id,
            dice_roll=DiceRollLog(
                entity_id=self.stats_block.id,
                dice_size=20,
                roll_results=[20],
                modifiers=[],
                advantage_status=AdvantageStatus.NONE,
                advantage_sources=[],
                disadvantage_sources=[],
                total_roll=20,
                is_critical=False,
                auto_success=True,
                auto_failure=False
            ),
            target_ac=target_ac,
            is_hit=True,
            auto_hit_source=self._get_auto_source("auto_success"),
            auto_miss_source=None,
            auto_critical_source=None
        )


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
        movement_cost = (len(self.path) - 1)*5  # Each step is 5 feet

        if self.step_by_step:
            for step in self.path[1:]:  # Skip the first step as it's the starting position
                battlemap.move_entity(self.stats_block, step)
                battlemap.update_entity_fov(self.stats_block)
                # Here you could add additional logic for each step if needed
        else:
            battlemap.move_entity(self.stats_block, end_position)
            battlemap.update_entity_fov(self.stats_block)

        self.stats_block.action_economy.movement.base_value -= movement_cost
        print(f"moved from {start_position} to {end_position} using {movement_cost} movement points")

        return True, f"Moved from {start_position} to {end_position}, using {movement_cost} movement points."

    def action_docstring(self):
        return f"{self.name}: Move along a specified path. Path length: {len(self.path) - 1} squares. {'Step-by-step movement.' if self.step_by_step else 'Direct movement to end position.'}"

    def apply(self, targets=None, context=None) -> List[Tuple[bool, str]]:
        if context is None:
            context = {}
        context['path'] = self.path
        return super().apply([self.stats_block], context)