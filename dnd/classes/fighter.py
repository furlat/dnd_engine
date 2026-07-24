"""
Fighter Class Features and Fighting Styles

Implements Fighter-specific features as conditions that can be applied to entities.
Organized by D&D 5e level progression.

Level 1: Fighting Styles, Second Wind
Level 2: Action Surge
Level 3: Champion - Improved Critical
Level 5: Extra Attack
Level 9: Indomitable
Level 15: Champion - Superior Critical
Level 18: Champion - Survivor (DEFERRED)
"""

from typing import Any, Dict
from dnd.core.base_conditions import BaseCondition
from dnd.core.condition_types import ConditionCategory, DurationType
from dnd.core.base_actions import (
    ActionOutcomeProfile, BaseAction, ActionEvent, Cost, TargetType, BaseCost, ActionCategory
)
from dnd.core.content import ContentKind
from dnd.core.events import (
    Event, EventPhase, EventType, EventQueue,
    Trigger, EventHandler, DamageRollResultEvent, RangeType, SavingThrowEvent
)
from dnd.core.equipment_types import ArmorType, WeaponProperty, WeaponSlot
from dnd.core.dice import DiceRoll, Dice, RollType, AttackOutcome
from dnd.core.modifiers import NumericalModifier, AdvantageModifier, AdvantageStatus, ContextualNumericalModifier
from dnd.core.values import ModifiableValue
from dnd.blocks.equipment import Weapon, Shield
from dnd.blocks.action_economy import RechargeType
from dnd.entity import Entity, determine_attack_outcome
from dnd.actions import (
    entity_action_economy_cost_evaluator,
    entity_action_economy_cost_applier,
    entity_resource_cost_evaluator,
    AttackEvent,
    Attack,
    build_weapon_attack_outcome_profile,
    create_weapon_attack_declaration_event,
)
from pydantic import Field
from typing import Any, Optional, List, Tuple, cast
from uuid import UUID
import random


def create_modified_dice_roll(original: DiceRoll, new_results: List[int]) -> DiceRoll:
    """
    Create a new DiceRoll with different results but same metadata.

    Original rolls are immutable - this creates a new version with modified results.
    The bonus is preserved and added to the new total.

    Note: Additional dice processors (maximize_all, minimize_all, etc.) are in
    dnd/classes/dice_processor_utils.py for test/reference use.
    """
    return DiceRoll(
        dice_uuid=original.dice_uuid,
        roll_type=original.roll_type,
        results=new_results,
        total=sum(new_results) + original.bonus,
        bonus=original.bonus,
        advantage_status=original.advantage_status,
        critical_status=original.critical_status,
        auto_hit_status=original.auto_hit_status,
        source_entity_uuid=original.source_entity_uuid,
        target_entity_uuid=original.target_entity_uuid,
        attack_outcome=original.attack_outcome
    )


class FightingStyleArchery(BaseCondition):
    """Fighter fighting style that improves ranged weapon attacks.

    Attributes:
        name: Condition name used for Archery fighting style lookup and cleanup.
        description: Short rules-facing summary of the Archery fighting style hook.
    """
    name: str = Field(
        default="Fighting Style: Archery",
        description="Condition name used for Archery fighting style lookup and cleanup.",
    )
    description: str = Field(
        default="+2 bonus to attack rolls with ranged weapons",
        description="Short rules-facing summary of the Archery fighting style hook.",
    )

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]],
        List[UUID],
        List[UUID],
        List[UUID],
        Optional[Event]
    ]:
        if not self.target_entity_uuid:
            return [], [], [], [], declaration_event.cancel(
                status_message="Target entity UUID is not set"
            )

        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], declaration_event.cancel(
                status_message=f"Target entity {self.target_entity_uuid} not found"
            )

        outs: List[Tuple[UUID, UUID]] = []

        archery_mod = NumericalModifier.create(
            source_entity_uuid=self.target_entity_uuid,
            name="Archery",
            value=2
        )
        mod_uuid = target.equipment.ranged_attack_bonus.self_static.add_value_modifier(archery_mod)
        outs.append((target.equipment.ranged_attack_bonus.uuid, mod_uuid))

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Applied Archery fighting style to {target.name}"
        )

        return outs, [], [], [], effect_event


def defense_ac_check(
    source_entity_uuid: UUID,
    target_entity_uuid: Optional[UUID] = None,
    context: Optional[dict] = None
) -> Optional[NumericalModifier]:
    """
    Contextual check for Defense fighting style.
    Returns +1 AC only if the entity is wearing armor.
    """
    _ = target_entity_uuid
    _ = context

    entity = Entity.get(source_entity_uuid)
    if not entity:
        return None

    body_armor = entity.equipment.body_armor
    if body_armor and body_armor.type != ArmorType.CLOTH:
        return NumericalModifier.create(
            source_entity_uuid=source_entity_uuid,
            name="Defense",
            value=1
        )

    return None


class FightingStyleDefense(BaseCondition):
    """Fighter fighting style that improves AC while armored.

    Attributes:
        name: Condition name used for Defense fighting style lookup and cleanup.
        description: Short rules-facing summary of the Defense fighting style hook.
    """
    name: str = Field(
        default="Fighting Style: Defense",
        description="Condition name used for Defense fighting style lookup and cleanup.",
    )
    description: str = Field(
        default="+1 AC while wearing armor",
        description="Short rules-facing summary of the Defense fighting style hook.",
    )

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]],
        List[UUID],
        List[UUID],
        List[UUID],
        Optional[Event]
    ]:
        if not self.target_entity_uuid:
            return [], [], [], [], declaration_event.cancel(
                status_message="Target entity UUID is not set"
            )

        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], declaration_event.cancel(
                status_message=f"Target entity {self.target_entity_uuid} not found"
            )

        outs: List[Tuple[UUID, UUID]] = []

        defense_mod = ContextualNumericalModifier(
            name="Defense",
            source_entity_uuid=self.target_entity_uuid,
            target_entity_uuid=self.target_entity_uuid,
            callable=defense_ac_check
        )
        mod_uuid = target.equipment.ac_bonus.self_contextual.add_value_modifier(defense_mod)
        outs.append((target.equipment.ac_bonus.uuid, mod_uuid))

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Applied Defense fighting style to {target.name}",
            resulting_ac=target.ac_bonus().normalized_score
        )

        return outs, [], [], [], effect_event

    def _post_removal_stats(self) -> Dict[str, Any]:
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target and isinstance(target, Entity):
            return {"resulting_ac": target.ac_bonus().normalized_score}
        return {}


def dueling_damage_check(
    source_entity_uuid: UUID,
    target_entity_uuid: Optional[UUID] = None,
    context: Optional[dict] = None
) -> Optional[NumericalModifier]:
    """
    Contextual check for Dueling fighting style.
    Returns +2 damage only if wielding a melee weapon in one hand with no other weapon.
    """
    _ = target_entity_uuid
    _ = context

    entity = Entity.get(source_entity_uuid)
    if not entity:
        return None

    main_weapon = entity.equipment.weapon_melee_main
    off_hand = entity.equipment.weapon_melee_off

    if main_weapon is None:
        return None

    if WeaponProperty.TWO_HANDED in main_weapon.properties:
        return None

    if off_hand is not None and not isinstance(off_hand, Shield):
        return None

    return NumericalModifier.create(
        source_entity_uuid=source_entity_uuid,
        name="Dueling",
        value=2
    )


class FightingStyleDueling(BaseCondition):
    """Fighter fighting style that improves one-handed melee damage.

    Attributes:
        name: Condition name used for Dueling fighting style lookup and cleanup.
        description: Short rules-facing summary of the Dueling fighting style hook.
    """
    name: str = Field(
        default="Fighting Style: Dueling",
        description="Condition name used for Dueling fighting style lookup and cleanup.",
    )
    description: str = Field(
        default="+2 damage when wielding a melee weapon in one hand",
        description="Short rules-facing summary of the Dueling fighting style hook.",
    )

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]],
        List[UUID],
        List[UUID],
        List[UUID],
        Optional[Event]
    ]:
        if not self.target_entity_uuid:
            return [], [], [], [], declaration_event.cancel(
                status_message="Target entity UUID is not set"
            )

        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], declaration_event.cancel(
                status_message=f"Target entity {self.target_entity_uuid} not found"
            )

        outs: List[Tuple[UUID, UUID]] = []

        dueling_mod = ContextualNumericalModifier(
            name="Dueling",
            source_entity_uuid=self.target_entity_uuid,
            target_entity_uuid=self.target_entity_uuid,
            callable=dueling_damage_check
        )
        mod_uuid = target.equipment.melee_damage_bonus.self_contextual.add_value_modifier(dueling_mod)
        outs.append((target.equipment.melee_damage_bonus.uuid, mod_uuid))

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Applied Dueling fighting style to {target.name}"
        )

        return outs, [], [], [], effect_event


def great_weapon_fighting_processor(
    event: DamageRollResultEvent,
    source_entity_uuid: UUID
) -> Optional[DamageRollResultEvent]:
    """Reroll low primary weapon dice for Great Weapon Fighting.

    Args:
        event: Damage-roll result event before damage is applied.
        source_entity_uuid: Entity that owns the GWF handler.

    Returns:
        Modified damage-roll event when primary weapon dice were rerolled, or
        ``None`` when the event is not eligible.
    """
    if event.source_entity_uuid != source_entity_uuid:
        return None

    entity = Entity.get(source_entity_uuid)
    if not entity:
        return None

    weapon = entity.equipment._get_weapon_by_slot(event.weapon_slot)
    if not weapon or isinstance(weapon, Shield):
        return None

    if not isinstance(weapon, Weapon):
        return None

    is_melee = weapon.range.type == RangeType.REACH
    has_two_handed = WeaponProperty.TWO_HANDED in weapon.properties
    versatile_wielded_two_handed = (
        WeaponProperty.VERSATILE in weapon.properties
        and event.weapon_slot == WeaponSlot.MELEE_MAIN
        and entity.equipment.weapon_melee_off is None
    )

    if not is_melee or not (has_two_handed or versatile_wielded_two_handed):
        return None

    any_modified = False
    for i, original_roll in enumerate(event.final_rolls):
        if i != 0:
            continue
        results = original_roll.results if isinstance(original_roll.results, list) else [original_roll.results]

        needs_reroll = any(r <= 2 for r in results)
        if not needs_reroll:
            continue

        new_results = []
        rerolled_dice = []
        for r in results:
            if r <= 2:
                new_result = random.randint(1, weapon.damage_dice)
                new_results.append(new_result)
                rerolled_dice.append(f"{r}→{new_result}")
            else:
                new_results.append(r)

        new_roll = create_modified_dice_roll(original_roll, new_results)
        event.replace_roll(
            i,
            new_roll,
            "Great Weapon Fighting",
            f"Rerolled: {', '.join(rerolled_dice)}"
        )
        any_modified = True

    if any_modified:
        return event.model_copy(update={"modified": True})
    return None


class GreatWeaponFighting(BaseCondition):
    """Fighter fighting style that rerolls low two-handed weapon damage dice.

    Attributes:
        name: Condition name used for Great Weapon Fighting handler lookup and cleanup.
        description: Short rules-facing summary of the Great Weapon Fighting handler.
    """
    name: str = Field(
        default="Fighting Style: Great Weapon Fighting",
        description="Condition name used for Great Weapon Fighting handler lookup and cleanup.",
    )
    description: str = Field(
        default=(
            "When you roll a 1 or 2 on a damage die for an attack with a two-handed "
            "melee weapon, you can reroll the die and must use the new roll."
        ),
        description="Short rules-facing summary of the Great Weapon Fighting handler.",
    )

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]],
        List[UUID],
        List[UUID],
        List[UUID],
        Optional[Event]
    ]:
        if not self.target_entity_uuid:
            return [], [], [], [], declaration_event.cancel(
                status_message="Target entity UUID is not set"
            )

        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], declaration_event.cancel(
                status_message=f"Target entity {self.target_entity_uuid} not found"
            )

        handler = EventHandler(
            name="Great Weapon Fighting",
            source_entity_uuid=target.uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.DAMAGE_ROLL_RESULT,
                    event_phase=EventPhase.EFFECT
                )
            ],
            event_processor=great_weapon_fighting_processor,
            player_toggleable=True
        )

        target.add_event_handler(handler)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Applied Great Weapon Fighting to {target.name}"
        )

        return [], [handler.uuid], [], [], effect_event


def protection_processor(
    event: Event,
    source_entity_uuid: UUID
) -> Optional[Event]:
    """
    Event processor for Protection fighting style.

    Imposes disadvantage on attacks against nearby allies when:
    - Protector is NOT the target
    - Target is within 5ft of protector
    - Protector can see the attacker
    - Protector has a shield equipped
    - Protector has a reaction available

    Triggers on ATTACK events at EXECUTION phase.
    """
    protector = Entity.get(source_entity_uuid)
    if not protector:
        return None

    if event.target_entity_uuid == source_entity_uuid:
        return None

    target = Entity.get(event.target_entity_uuid) if event.target_entity_uuid else None
    if not target:
        return None
    distance = protector.senses.get_feet_distance(target.senses.position)
    if distance > 5:
        return None

    if event.source_entity_uuid not in protector.senses.entities:
        return None

    off_hand = protector.equipment.weapon_melee_off
    if not off_hand or not isinstance(off_hand, Shield):
        return None

    if not protector.action_economy.can_afford("reactions", 1):
        return None

    if not isinstance(event, AttackEvent) or not event.attack_bonus:
        return None
    attack_bonus = event.attack_bonus

    for modifier in attack_bonus.self_static.advantage_modifiers.values():
        if modifier.name == "Protection":
            return None

    attack_bonus.self_static.add_advantage_modifier(
        AdvantageModifier(
            name="Protection",
            value=AdvantageStatus.DISADVANTAGE,
            source_entity_uuid=source_entity_uuid,
            target_entity_uuid=event.target_entity_uuid
        )
    )

    protector.action_economy.consume("reactions", 1)

    return event.model_copy(update={
        "modified": True,
        "status_message": f"{protector.name} uses Protection to impose disadvantage"
    })


def create_protection_handler(source_entity_uuid: UUID) -> EventHandler:
    """Create an EventHandler for Protection fighting style."""
    return EventHandler(
        name="Protection",
        semantic_key="feature.fighter.protection",
        content_kind=ContentKind.REACTION,
        source_entity_uuid=source_entity_uuid,
        trigger_conditions=[
            Trigger(
                event_type=EventType.ATTACK,
                event_phase=EventPhase.EXECUTION
            )
        ],
        event_processor=protection_processor,
        player_toggleable=True
    )


class FightingStyleProtection(BaseCondition):
    """Fighter fighting style that protects nearby allies with a reaction.

    Attributes:
        name: Condition name used for Protection fighting style lookup and cleanup.
        description: Short rules-facing summary of the Protection reaction handler.
    """
    name: str = Field(
        default="Fighting Style: Protection",
        description="Condition name used for Protection fighting style lookup and cleanup.",
    )
    description: str = Field(
        default="Use reaction to impose disadvantage on attacks against nearby allies",
        description="Short rules-facing summary of the Protection reaction handler.",
    )

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]],
        List[UUID],
        List[UUID],
        List[UUID],
        Optional[Event]
    ]:
        if not self.target_entity_uuid:
            return [], [], [], [], declaration_event.cancel(
                status_message="Target entity UUID is not set"
            )

        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], declaration_event.cancel(
                status_message=f"Target entity {self.target_entity_uuid} not found"
            )

        handler = create_protection_handler(target.uuid)
        target.add_event_handler(handler)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Applied Protection fighting style to {target.name}"
        )

        return [], [handler.uuid], [], [], effect_event


def twf_off_hand_melee_ability_bonus(
    source_entity_uuid: UUID,
    target_entity_uuid: Optional[UUID] = None,
    context: Optional[dict] = None
) -> Optional[NumericalModifier]:
    """
    Contextual modifier for TWF off-hand melee damage.
    Evaluated at damage time - checks weapon properties to determine correct ability.
    """
    _ = target_entity_uuid, context

    entity = Entity.get(source_entity_uuid)
    if not entity:
        return None

    off_hand = entity.equipment.weapon_melee_off
    if not off_hand or isinstance(off_hand, Shield):
        return None

    if WeaponProperty.FINESSE in off_hand.properties:
        str_mod = entity.ability_scores.strength.modifier
        dex_mod = entity.ability_scores.dexterity.modifier
        bonus = max(str_mod, dex_mod)
    else:
        bonus = entity.ability_scores.strength.modifier

    return NumericalModifier.create(
        source_entity_uuid=source_entity_uuid,
        name="Two-Weapon Fighting",
        value=bonus
    )


def twf_off_hand_ranged_ability_bonus(
    source_entity_uuid: UUID,
    target_entity_uuid: Optional[UUID] = None,
    context: Optional[dict] = None
) -> Optional[NumericalModifier]:
    """Contextual modifier for TWF off-hand ranged damage."""
    _ = target_entity_uuid, context

    entity = Entity.get(source_entity_uuid)
    if not entity:
        return None

    off_hand = entity.equipment.weapon_ranged_off
    if not off_hand:
        return None

    return NumericalModifier.create(
        source_entity_uuid=source_entity_uuid,
        name="Two-Weapon Fighting",
        value=entity.ability_scores.dexterity.modifier
    )


class FightingStyleTwoWeaponFighting(BaseCondition):
    """Fighter fighting style that adds ability modifiers to off-hand damage.

    Attributes:
        name: Condition name used for Two-Weapon Fighting lookup and cleanup.
        description: Short rules-facing summary of the Two-Weapon Fighting modifier hook.
    """
    name: str = Field(
        default="Fighting Style: Two-Weapon Fighting",
        description="Condition name used for Two-Weapon Fighting lookup and cleanup.",
    )
    description: str = Field(
        default="Add ability modifier to off-hand attack damage",
        description="Short rules-facing summary of the Two-Weapon Fighting modifier hook.",
    )

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]],
        List[UUID],
        List[UUID],
        List[UUID],
        Optional[Event]
    ]:
        if not self.target_entity_uuid:
            return [], [], [], [], declaration_event.cancel(
                status_message="Target entity UUID is not set"
            )

        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], declaration_event.cancel(
                status_message=f"Target entity {self.target_entity_uuid} not found"
            )

        outs: List[Tuple[UUID, UUID]] = []

        melee_mod = ContextualNumericalModifier(
            name="Two-Weapon Fighting",
            source_entity_uuid=self.target_entity_uuid,
            target_entity_uuid=self.target_entity_uuid,
            callable=twf_off_hand_melee_ability_bonus
        )
        mod_uuid = target.equipment.off_hand_melee_ability_bonus.self_contextual.add_value_modifier(melee_mod)
        outs.append((target.equipment.off_hand_melee_ability_bonus.uuid, mod_uuid))

        ranged_mod = ContextualNumericalModifier(
            name="Two-Weapon Fighting",
            source_entity_uuid=self.target_entity_uuid,
            target_entity_uuid=self.target_entity_uuid,
            callable=twf_off_hand_ranged_ability_bonus
        )
        mod_uuid = target.equipment.off_hand_ranged_ability_bonus.self_contextual.add_value_modifier(ranged_mod)
        outs.append((target.equipment.off_hand_ranged_ability_bonus.uuid, mod_uuid))

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Applied Two-Weapon Fighting to {target.name}"
        )

        return outs, [], [], [], effect_event


class SecondWind(BaseAction):
    """Fighter self-heal action that spends the Second Wind resource.

    Attributes:
        name: Action name displayed for the Fighter self-heal.
        description: Short rules-facing summary of the Second Wind action.
        target_type: Second Wind always targets the acting fighter.
        fighter_level: Fighter level added to the Second Wind healing roll.
        costs: Bonus-action and second-wind resource costs rebuilt after model initialization.
    """
    name: str = Field(default="Second Wind", description="Action name displayed for the Fighter self-heal.")
    description: str = Field(
        default="Heal 1d10 + level as a bonus action",
        description="Short rules-facing summary of the Second Wind action.",
    )
    target_type: TargetType = Field(
        default=TargetType.SELF,
        description="Second Wind always targets the acting fighter.",
    )
    fighter_level: int = Field(
        default=1,
        description="Fighter level added to the Second Wind healing roll.",
    )

    costs: List[Cost] = Field(
        default_factory=list,
        description="Bonus-action and second-wind resource costs rebuilt after model initialization.",
    )

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        self.costs = [
            Cost(
                name="Second Wind Cost",
                cost_type="bonus_actions",
                cost=1,
                evaluator=entity_action_economy_cost_evaluator,
                resource_name="second_wind",
                resource_cost=1,
                resource_evaluator=entity_resource_cost_evaluator
            )
        ]

    def _create_declaration_event(self, parent_event: Optional[Event] = None, use_register: bool = True) -> Optional[ActionEvent]:
        entity = Entity.get(self.source_entity_uuid)
        source_name = entity.name if entity else None

        return ActionEvent(
            name=self.name,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.source_entity_uuid,
            costs=[BaseCost.model_validate(c) for c in self.costs],
            parent_event=parent_event.uuid if parent_event else None,
            use_register=use_register,
            source_entity_name=source_name
        )

    def _validate(self, declaration_event: ActionEvent) -> Optional[ActionEvent]:
        entity = Entity.get(self.source_entity_uuid)
        if entity is None:
            return declaration_event.cancel(status_message="Entity not found")

        if entity.health.damage_taken == 0:
            return declaration_event.cancel(status_message="Already at full health")

        return declaration_event.phase_to(
            EventPhase.EXECUTION,
            status_message="Second Wind ready"
        )

    def _apply(self, execution_event: ActionEvent) -> Optional[ActionEvent]:
        entity = Entity.get(self.source_entity_uuid)
        if entity is None:
            return execution_event.cancel(status_message="Entity not found")

        healing_dice = Dice(
            count=1,
            value=10,
            bonus=ModifiableValue.create(
                source_entity_uuid=self.source_entity_uuid,
                base_value=self.fighter_level,
                value_name="Fighter Level"
            ),
            roll_type=RollType.CHECK
        )
        healing_roll = healing_dice.roll
        total_healing = healing_roll.total

        roll_results = healing_roll.results
        roll_str = str(roll_results[0]) if isinstance(roll_results, list) and roll_results else "?"
        source_desc = f"Second Wind: d10({roll_str})+{self.fighter_level}"

        actual_healing = entity.receive_healing(
            total_healing, entity.uuid,
            source_description=source_desc,
            parent_event=execution_event.uuid
        )

        effect_event = execution_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Second Wind heals {actual_healing} HP (d10+{self.fighter_level}={total_healing})"
        )
        return effect_event.phase_to(
            EventPhase.COMPLETION,
            status_message=f"Second Wind complete - healed {actual_healing} HP"
        )

    def _apply_costs(self, completion_event: ActionEvent) -> ActionEvent:
        return entity_action_economy_cost_applier(completion_event, self.source_entity_uuid)


class SecondWindFeature(BaseCondition):
    """Fighter feature that grants the Second Wind resource and action.

    Attributes:
        name: Feature condition name for Second Wind lookup and cleanup.
        description: Short rules-facing summary of the Second Wind feature.
        fighter_level: Fighter level passed into the registered Second Wind action.
    """
    name: str = Field(
        default="Second Wind Feature",
        description="Feature condition name for Second Wind lookup and cleanup.",
    )
    description: str = Field(
        default="Heal 1d10 + fighter level as a bonus action (1/short rest)",
        description="Short rules-facing summary of the Second Wind feature.",
    )
    fighter_level: int = Field(
        default=1,
        description="Fighter level passed into the registered Second Wind action.",
    )

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]],
        List[UUID],
        List[UUID],
        List[UUID],
        Optional[Event]
    ]:
        if not self.target_entity_uuid:
            return [], [], [], [], declaration_event.cancel(
                status_message="Target entity UUID is not set"
            )

        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], declaration_event.cancel(
                status_message=f"Target entity {self.target_entity_uuid} not found"
            )

        target.action_economy.add_resource(
            name="second_wind",
            maximum=1,
            recharge_type=RechargeType.SHORT_REST
        )

        second_wind = SecondWind(
            source_entity_uuid=target.uuid,
            fighter_level=self.fighter_level,
            template=True
        )
        target.register_action(second_wind)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Granted Second Wind to {target.name}"
        )

        return [], [], [], [], effect_event

    def _remove(self, event: Optional[Event] = None) -> Optional[Event]:
        """Clean up resource and action on removal."""
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target:
            target.action_economy.remove_resource("second_wind")
            target.unregister_action("Second Wind")

        return super()._remove(event)


class ActionSurging(BaseCondition):
    """Temporary internal state granted by Action Surge.

    Attributes:
        name: Internal marker condition name for active Action Surge state.
        description: Short rules-facing summary of the temporary Action Surge state.
        condition_category: Marks ActionSurging as an internal lifecycle condition.
    """
    name: str = Field(
        default="ActionSurging",
        description="Internal marker condition name for active Action Surge state.",
    )
    description: str = Field(
        default="+1 action this turn (Action Surge used)",
        description="Short rules-facing summary of the temporary Action Surge state.",
    )
    condition_category: ConditionCategory = Field(
        default=ConditionCategory.INTERNAL,
        description="Marks ActionSurging as an internal lifecycle condition.",
    )

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")

        target_entity = Entity.get(self.target_entity_uuid)
        if not target_entity:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} not found")

        self.duration.duration_type = DurationType.ROUNDS
        self.duration.duration = 1

        outs = []

        modifier = NumericalModifier(
            name="Action Surge",
            value=1,
            source_entity_uuid=self.target_entity_uuid,
            target_entity_uuid=self.target_entity_uuid
        )
        mod_uuid = target_entity.action_economy.actions.self_static.add_value_modifier(modifier)
        outs.append((target_entity.action_economy.actions.uuid, mod_uuid))

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            update={"condition": self},
            status_message=f"{target_entity.name} surges with extra action!"
        )

        return outs, [], [], [], effect_event


class ActionSurge(BaseAction):
    """Fighter action that spends Action Surge for one extra action.

    Attributes:
        name: Action name displayed for Action Surge.
        description: Short rules-facing summary of the Action Surge action.
        target_type: Action Surge always targets the acting fighter.
        costs: Action-surge resource cost rebuilt after model initialization.
    """
    name: str = Field(default="Action Surge", description="Action name displayed for Action Surge.")
    description: str = Field(
        default="Take one additional action on your turn",
        description="Short rules-facing summary of the Action Surge action.",
    )
    target_type: TargetType = Field(
        default=TargetType.SELF,
        description="Action Surge always targets the acting fighter.",
    )

    costs: List[Cost] = Field(
        default_factory=list,
        description="Action-surge resource cost rebuilt after model initialization.",
    )

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        self.costs = [
            Cost(
                name="Action Surge",
                cost_type="actions",
                cost=0,
                resource_name="action_surge",
                resource_cost=1,
                evaluator=None,
                resource_evaluator=entity_resource_cost_evaluator
            )
        ]

    def _create_declaration_event(self, parent_event: Optional[Event] = None, use_register: bool = True) -> Optional[ActionEvent]:
        """Create the declaration event for Action Surge."""
        entity = Entity.get(self.source_entity_uuid)
        source_name = entity.name if entity else None

        return ActionEvent(
            name=self.name,
            parent_event=parent_event.uuid if parent_event else None,
            phase=EventPhase.DECLARATION,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.source_entity_uuid,
            costs=[BaseCost.model_validate(cost) for cost in self.costs],
            use_register=use_register,
            source_entity_name=source_name
        )

    def _validate(self, declaration_event: ActionEvent) -> ActionEvent:
        """Validate Action Surge can be used."""
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return declaration_event.cancel(status_message="Entity not found")

        if not entity.action_economy.can_afford_resource("action_surge", 1):
            return declaration_event.cancel(status_message="Action Surge not available")

        if "ActionSurging" in entity.active_conditions:
            return declaration_event.cancel(status_message="Already used Action Surge this turn")

        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated {self.name}"
        )

    def _apply(self, execution_event: ActionEvent) -> ActionEvent:
        """Apply Action Surge - grant extra action."""
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return execution_event.cancel(status_message="Entity not found")

        surging = ActionSurging(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.source_entity_uuid
        )
        entity.add_condition(surging)

        return execution_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"{entity.name} uses Action Surge!"
        )

    def _apply_costs(self, completion_event: ActionEvent) -> ActionEvent:
        """Apply the costs (consume action_surge resource)."""
        return entity_action_economy_cost_applier(completion_event, self.source_entity_uuid)


class ActionSurgeFeature(BaseCondition):
    """Fighter feature that grants Action Surge uses and action access.

    Attributes:
        name: Feature condition name for Action Surge lookup and cleanup.
        description: Short rules-facing summary of the Action Surge feature.
        num_uses: Maximum Action Surge resource uses granted by this feature.
    """
    name: str = Field(
        default="Action Surge Feature",
        description="Feature condition name for Action Surge lookup and cleanup.",
    )
    description: str = Field(
        default="Take one additional action on your turn",
        description="Short rules-facing summary of the Action Surge feature.",
    )
    num_uses: int = Field(
        default=1,
        description="Maximum Action Surge resource uses granted by this feature.",
    )

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]],
        List[UUID],
        List[UUID],
        List[UUID],
        Optional[Event]
    ]:
        if not self.target_entity_uuid:
            return [], [], [], [], declaration_event.cancel(
                status_message="Target entity UUID is not set"
            )

        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], declaration_event.cancel(
                status_message=f"Target entity {self.target_entity_uuid} not found"
            )

        target.action_economy.add_resource(
            name="action_surge",
            maximum=self.num_uses,
            recharge_type=RechargeType.SHORT_REST
        )

        action_surge = ActionSurge(
            source_entity_uuid=target.uuid,
            template=True
        )
        target.register_action(action_surge)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Applied Action Surge feature ({self.num_uses} uses) to {target.name}"
        )

        return [], [], [], [], effect_event

    def _remove(self, event: Optional[Event] = None) -> Optional[Event]:
        """Clean up resource and action on removal."""
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target:
            target.action_economy.remove_resource("action_surge")
            target.unregister_action("Action Surge")

        return super()._remove(event)


class ImprovedCritical(BaseCondition):
    """Champion feature that expands weapon critical hits to 19-20.

    Attributes:
        name: Condition name used for Champion Improved Critical lookup and cleanup.
        description: Short rules-facing summary of the Improved Critical feature.
    """
    name: str = Field(
        default="Improved Critical",
        description="Condition name used for Champion Improved Critical lookup and cleanup.",
    )
    description: str = Field(
        default="Your weapon attacks score a critical hit on a roll of 19 or 20.",
        description="Short rules-facing summary of the Improved Critical feature.",
    )

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]],
        List[UUID],
        List[UUID],
        List[UUID],
        Optional[Event]
    ]:
        if not self.target_entity_uuid:
            return [], [], [], [], declaration_event.cancel(
                status_message="Target entity UUID is not set"
            )

        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], declaration_event.cancel(
                status_message=f"Target entity {self.target_entity_uuid} not found"
            )

        outs: List[Tuple[UUID, UUID]] = []

        crit_mod = NumericalModifier.create(
            source_entity_uuid=self.target_entity_uuid,
            name="Improved Critical",
            value=1
        )
        mod_uuid = target.equipment.crit_threshold.self_static.add_value_modifier(crit_mod)
        outs.append((target.equipment.crit_threshold.uuid, mod_uuid))

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Applied Improved Critical to {target.name} - crits on 19-20"
        )

        return outs, [], [], [], effect_event


class ExtraAttacksGranted(BaseCondition):
    """Internal marker for extra attacks granted during the current turn.

    Attributes:
        name: Internal marker condition name for Extra Attack resource grants this turn.
        description: Short lifecycle summary for the Extra Attack grant marker.
        condition_category: Marks ExtraAttacksGranted as an internal lifecycle condition.
    """
    name: str = Field(
        default="ExtraAttacksGranted",
        description="Internal marker condition name for Extra Attack resource grants this turn.",
    )
    description: str = Field(
        default="Extra attacks have been granted this turn",
        description="Short lifecycle summary for the Extra Attack grant marker.",
    )
    condition_category: ConditionCategory = Field(
        default=ConditionCategory.INTERNAL,
        description="Marks ExtraAttacksGranted as an internal lifecycle condition.",
    )

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]],
        List[UUID],
        List[UUID],
        List[UUID],
        Optional[Event]
    ]:
        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message="Marked as ExtraAttacksGranted"
        )
        return [], [], [], [], effect_event


def extra_attack_resource_processor(
    event: Event,
    source_entity_uuid: UUID
) -> Optional[Event]:
    """
    Fighter-specific processor: manages extra_attacks resource for Extra Attack.

    This processor handles Action Surge compatibility:
    - First Attack action this turn: Set extra_attacks = num_extra_attacks
    - Subsequent Attack actions (via Action Surge): ADD num_extra_attacks

    This ensures that each Attack action grants the full number of extra attacks,
    even when Action Surge grants additional actions mid-turn.

    Triggers on ATTACK at EXECUTION phase (for action-cost attacks only).
    Uses ExtraAttacksGranted marker (not HasAttacked) to track first vs subsequent.
    """
    if event.source_entity_uuid != source_entity_uuid:
        return None

    if event.canceled:
        return None

    entity = Entity.get(source_entity_uuid)
    if not entity:
        return None

    if not EventQueue.is_first_at_phase(event):
        return None

    if not isinstance(event, ActionEvent) or not event.costs:
        return None

    action_cost_attack = any(
        c.cost_type == "actions" and c.cost > 0
        for c in event.costs
    )
    if not action_cost_attack:
        return None

    extra_attack_feature = entity.active_conditions.get("Extra Attack")
    extra_attack_resource = entity.action_economy.resources.get("extra_attacks")

    if not extra_attack_resource or not extra_attack_feature:
        return None

    num_extra = extra_attack_feature.extra_attacks if isinstance(extra_attack_feature, ExtraAttackFeature) else 1

    if "ExtraAttacksGranted" not in entity.active_conditions:
        extra_attack_resource.current = num_extra

        marker = ExtraAttacksGranted(
            source_entity_uuid=source_entity_uuid,
            target_entity_uuid=source_entity_uuid
        )
        marker.duration.duration_type = DurationType.ROUNDS
        marker.duration.duration = 1
        entity.add_condition(marker)
    else:
        extra_attack_resource.current += num_extra

    return None


def create_extra_attack_resource_handler(source_entity_uuid: UUID) -> EventHandler:
    """Create an EventHandler that manages extra_attacks resource for Fighter."""
    return EventHandler(
        name="Extra Attack Resource",
        source_entity_uuid=source_entity_uuid,
        trigger_conditions=[
            Trigger(
                event_type=EventType.ATTACK,
                event_phase=EventPhase.EXECUTION
            )
        ],
        event_processor=extra_attack_resource_processor
    )


class ExtraAttack(BaseAction):
    """Fighter action that spends the extra-attacks resource for another attack.

    Attributes:
        name: Action name displayed for Fighter extra attacks.
        description: Short rules-facing summary of the Extra Attack action.
        target_type: Extra Attack targets a visible entity in weapon reach or range.
        weapon_slot: Weapon slot used to resolve the additional attack.
        action_category: Marks Extra Attack as an attack action for discovery and reactions.
        costs: Extra-attack resource cost rebuilt after model initialization.
    """
    name: str = Field(default="Extra Attack", description="Action name displayed for Fighter extra attacks.")
    description: str = Field(
        default="Make an additional weapon attack",
        description="Short rules-facing summary of the Extra Attack action.",
    )
    target_type: TargetType = Field(
        default=TargetType.ENTITY,
        description="Extra Attack targets a visible entity in weapon reach or range.",
    )
    weapon_slot: WeaponSlot = Field(
        default=WeaponSlot.MELEE_MAIN,
        description="Weapon slot used to resolve the additional attack.",
    )
    action_category: ActionCategory = Field(
        default=ActionCategory.ATTACK,
        description="Marks Extra Attack as an attack action for discovery and reactions.",
    )

    costs: List[Cost] = Field(
        default_factory=list,
        description="Extra-attack resource cost rebuilt after model initialization.",
    )

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        self.costs = [
            Cost(
                name="Extra Attack",
                cost_type="actions",
                cost=0,
                resource_name="extra_attacks",
                resource_cost=1,
                evaluator=None,
                resource_evaluator=entity_resource_cost_evaluator
            )
        ]

    def get_outcome_profile(self, actor: Any) -> Optional[ActionOutcomeProfile]:
        """Return the same actor-baseline weapon profile as a normal attack."""
        return build_weapon_attack_outcome_profile(actor, self.weapon_slot)

    def _create_declaration_event(self, parent_event: Optional[Event] = None, use_register: bool = True) -> Optional[Event]:
        """Create the declaration event for the extra attack action."""
        return create_weapon_attack_declaration_event(
            action_name="Extra Attack",
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid,
            weapon_slot=self.weapon_slot,
            costs=self.costs,
            parent_event=parent_event,
            use_register=use_register,
            append_weapon_to_name=True,
        )

    def _validate(self, declaration_event: Event) -> Optional[Event]:
        """Validate the extra attack action."""
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return declaration_event.cancel(status_message="Entity not found")

        if "ExtraAttacksGranted" not in entity.active_conditions:
            return declaration_event.cancel(
                status_message="Must attack first before using Extra Attack"
            )

        if not self.target_entity_uuid:
            return declaration_event.cancel(status_message="No target specified")

        target = Entity.get(self.target_entity_uuid)
        if not target:
            return declaration_event.cancel(status_message="Target not found")

        if self.target_entity_uuid not in entity.senses.entities:
            return declaration_event.cancel(status_message="Target not visible")

        attack_event = cast(AttackEvent, declaration_event)
        range_validated = Attack.validate_range(attack_event, self.source_entity_uuid)
        if range_validated is None or range_validated.canceled:
            return range_validated

        ranged_conditions = Attack.check_ranged_conditions(range_validated, self.source_entity_uuid)
        if ranged_conditions is None or ranged_conditions.canceled:
            return ranged_conditions

        return ranged_conditions.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Extra Attack validated"
        )

    def _apply(self, execution_event) -> Optional[Event]:
        """Apply the extra attack - execute the actual attack logic."""
        attack_event = cast(AttackEvent, execution_event)
        return Attack.attack_consequences(attack_event, self.source_entity_uuid)

    def _apply_costs(self, completion_event) -> Optional[Event]:
        """Apply the costs (consume extra_attacks resource)."""
        return entity_action_economy_cost_applier(completion_event, self.source_entity_uuid)


class ExtraAttackFeature(BaseCondition):
    """Fighter feature that grants extra attacks after action-cost attacks.

    Attributes:
        name: Feature condition name for Fighter Extra Attack.
        description: Short rules-facing summary of the Extra Attack feature.
        extra_attacks: Number of extra attacks granted after each action-cost Attack action.
    """
    name: str = Field(default="Extra Attack", description="Feature condition name for Fighter Extra Attack.")
    description: str = Field(
        default="Can make additional attacks when taking the Attack action",
        description="Short rules-facing summary of the Extra Attack feature.",
    )

    extra_attacks: int = Field(
        default=1,
        description="Number of extra attacks granted after each action-cost Attack action.",
    )

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]],
        List[UUID],
        List[UUID],
        List[UUID],
        Optional[Event]
    ]:
        if not self.target_entity_uuid:
            return [], [], [], [], declaration_event.cancel(
                status_message="Target entity UUID is not set"
            )

        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], declaration_event.cancel(
                status_message=f"Target entity {self.target_entity_uuid} not found"
            )

        handler_uuids: List[UUID] = []

        target.action_economy.add_resource(
            name="extra_attacks",
            maximum=self.extra_attacks,
            recharge_type=RechargeType.TURN_START
        )

        for slot in [WeaponSlot.MELEE_MAIN, WeaponSlot.MELEE_OFF,
                     WeaponSlot.RANGED_MAIN, WeaponSlot.RANGED_OFF]:
            weapon = target.equipment._get_weapon_by_slot(slot)
            if weapon and not isinstance(weapon, Shield):
                extra_attack = ExtraAttack(
                    source_entity_uuid=target.uuid,
                    weapon_slot=slot,
                    name=f"Extra Attack_{slot.value}",
                    template=True
                )
                target.register_action(extra_attack)

        handler = create_extra_attack_resource_handler(target.uuid)
        target.add_event_handler(handler)
        handler_uuids.append(handler.uuid)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Granted Extra Attack ({self.extra_attacks} extra) to {target.name}"
        )

        return [], handler_uuids, [], [], effect_event

    def _remove(self, event: Optional[Event] = None) -> Optional[Event]:
        """
        Custom removal: clean up resources and action templates.
        """
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target:
            target.action_economy.remove_resource("extra_attacks")

            for slot in [WeaponSlot.MELEE_MAIN, WeaponSlot.MELEE_OFF,
                         WeaponSlot.RANGED_MAIN, WeaponSlot.RANGED_OFF]:
                template_name = f"Extra Attack_{slot.value}"
                target.unregister_action(template_name)

        return super()._remove(event)


def indomitable_processor(
    event: Event,
    source_entity_uuid: UUID
) -> Optional[Event]:
    """
    Reroll failed saving throws.
    Triggers on SAVING_THROW at EFFECT phase.

    Per RAW: Must use the new roll, even if it's worse.
    """
    if event.target_entity_uuid != source_entity_uuid:
        return None

    if not isinstance(event, SavingThrowEvent):
        return None

    entity = Entity.get(source_entity_uuid)
    if not entity:
        return None

    if event.result is not False:
        return None

    if not entity.action_economy.can_afford_resource("indomitable", 1):
        return None

    entity.action_economy.consume_resource("indomitable", 1)

    ability_name = event.ability_name
    save_bonus = entity.saving_throw_bonus(event.source_entity_uuid, ability_name)
    new_roll = entity.roll_d20(save_bonus, RollType.SAVE, parent_event=event.uuid)

    dc = event.get_dc()
    if dc is None:
        return None

    new_outcome = determine_attack_outcome(new_roll, dc)
    new_success = new_outcome not in [AttackOutcome.MISS, AttackOutcome.CRIT_MISS]

    return event.model_copy(update={
        "dice_roll": new_roll,
        "result": new_success,
        "modified": True,
        "status_message": f"{entity.name} uses Indomitable! Reroll: {new_roll.total} vs DC {dc} - {'Success' if new_success else 'Failure'}"
    })


def create_indomitable_handler(source_entity_uuid: UUID) -> EventHandler:
    """Create EventHandler for Indomitable."""
    return EventHandler(
        name="Indomitable",
        source_entity_uuid=source_entity_uuid,
        trigger_conditions=[
            Trigger(
                event_type=EventType.SAVING_THROW,
                event_phase=EventPhase.EFFECT
            )
        ],
        event_processor=indomitable_processor,
        player_toggleable=True
    )


class Indomitable(BaseCondition):
    """Fighter feature that grants failed saving throw rerolls.

    Attributes:
        name: Feature condition name for Indomitable.
        description: Short rules-facing summary of the Indomitable feature.
        num_uses: Maximum Indomitable resource uses granted by this feature.
    """
    name: str = Field(default="Indomitable", description="Feature condition name for Indomitable.")
    description: str = Field(
        default="Reroll a failed saving throw (must use new roll)",
        description="Short rules-facing summary of the Indomitable feature.",
    )
    num_uses: int = Field(
        default=1,
        description="Maximum Indomitable resource uses granted by this feature.",
    )

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]],
        List[UUID],
        List[UUID],
        List[UUID],
        Optional[Event]
    ]:
        if not self.target_entity_uuid:
            return [], [], [], [], declaration_event.cancel(
                status_message="Target entity UUID is not set"
            )

        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], declaration_event.cancel(
                status_message=f"Target entity {self.target_entity_uuid} not found"
            )

        target.action_economy.add_resource(
            name="indomitable",
            maximum=self.num_uses,
            recharge_type=RechargeType.LONG_REST
        )

        handler = create_indomitable_handler(target.uuid)
        target.add_event_handler(handler)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Applied Indomitable ({self.num_uses} uses) to {target.name}"
        )

        return [], [handler.uuid], [], [], effect_event

    def _remove(self, event: Optional[Event] = None) -> Optional[Event]:
        """Custom removal: clean up resource."""
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target:
            target.action_economy.remove_resource("indomitable")

        return super()._remove(event)


class SuperiorCritical(BaseCondition):
    """Champion feature that expands weapon critical hits to 18-20.

    Attributes:
        name: Condition name used for Champion Superior Critical lookup and cleanup.
        description: Short rules-facing summary of the Superior Critical feature.
    """
    name: str = Field(
        default="Superior Critical",
        description="Condition name used for Champion Superior Critical lookup and cleanup.",
    )
    description: str = Field(
        default="Your weapon attacks score a critical hit on a roll of 18, 19, or 20.",
        description="Short rules-facing summary of the Superior Critical feature.",
    )

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]],
        List[UUID],
        List[UUID],
        List[UUID],
        Optional[Event]
    ]:
        if not self.target_entity_uuid:
            return [], [], [], [], declaration_event.cancel(
                status_message="Target entity UUID is not set"
            )

        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], declaration_event.cancel(
                status_message=f"Target entity {self.target_entity_uuid} not found"
            )

        outs: List[Tuple[UUID, UUID]] = []

        crit_mod = NumericalModifier.create(
            source_entity_uuid=self.target_entity_uuid,
            name="Superior Critical",
            value=2
        )
        mod_uuid = target.equipment.crit_threshold.self_static.add_value_modifier(crit_mod)
        outs.append((target.equipment.crit_threshold.uuid, mod_uuid))

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Applied Superior Critical to {target.name} - crits on 18-20"
        )

        return outs, [], [], [], effect_event


def survivor_processor(
    event: Event,
    source_entity_uuid: UUID
) -> Optional[Event]:
    """
    Turn start handler for Survivor.
    Heals 5 + CON mod if HP <= 50% and HP > 0.
    Triggers at EXECUTION phase, before conditions advance.

    Per SRD: At the start of each of your turns, you regain hit points equal
    to 5 + your Constitution modifier if you have no more than half of your
    hit points left. You don't gain this benefit if you have 0 hit points.
    """
    if event.source_entity_uuid != source_entity_uuid:
        return None

    entity = Entity.get(source_entity_uuid)
    if not entity:
        return None

    current_hp = entity.get_hp()
    max_hp = current_hp + entity.health.damage_taken

    if current_hp <= 0:
        return None

    if current_hp > max_hp / 2:
        return None

    con_mod = entity.ability_scores.constitution.modifier
    healing = 5 + con_mod

    actual_healed = entity.receive_healing(
        healing, entity.uuid,
        source_description=f"Survivor: 5+{con_mod}",
        parent_event=event.uuid
    )

    return event.model_copy(update={
        "modified": True,
        "status_message": f"Survivor heals {actual_healed} HP (5+{con_mod})"
    })


def create_survivor_handler(source_entity_uuid: UUID) -> EventHandler:
    """Create EventHandler for Survivor turn start healing."""
    return EventHandler(
        name="Survivor",
        source_entity_uuid=source_entity_uuid,
        trigger_conditions=[
            Trigger(
                event_type=EventType.TURN_START,
                event_phase=EventPhase.EXECUTION
            )
        ],
        event_processor=survivor_processor
    )


class Survivor(BaseCondition):
    """Champion feature that heals the fighter at turn start when wounded.

    Attributes:
        name: Feature condition name for Champion Survivor.
        description: Short rules-facing summary of the Survivor turn-start healing feature.
    """
    name: str = Field(default="Survivor", description="Feature condition name for Champion Survivor.")
    description: str = Field(
        default="Heal 5 + CON mod at turn start when HP <= 50% max",
        description="Short rules-facing summary of the Survivor turn-start healing feature.",
    )

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]],
        List[UUID],
        List[UUID],
        List[UUID],
        Optional[Event]
    ]:
        if not self.target_entity_uuid:
            return [], [], [], [], declaration_event.cancel(
                status_message="Target entity UUID is not set"
            )

        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], declaration_event.cancel(
                status_message=f"Target entity {self.target_entity_uuid} not found"
            )

        handler = create_survivor_handler(target.uuid)
        target.add_event_handler(handler)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Granted Survivor to {target.name}"
        )

        return [], [handler.uuid], [], [], effect_event
