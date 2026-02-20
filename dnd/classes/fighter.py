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

from dnd.core.base_conditions import BaseCondition, ConditionCategory, DurationType
from dnd.core.base_actions import (
    BaseAction, ActionEvent, Cost, TargetType, BaseCost, ActionCategory
)
from dnd.core.events import (
    Event, EventPhase, EventType, EventQueue,
    Trigger, EventHandler, DamageRollResultEvent, RangeType, WeaponSlot, SavingThrowEvent
)
from dnd.core.dice import DiceRoll, Dice, RollType, AttackOutcome
from dnd.core.modifiers import NumericalModifier, AdvantageModifier, AdvantageStatus, ContextualNumericalModifier
from dnd.core.values import ModifiableValue
from dnd.blocks.equipment import WeaponProperty, Weapon, Shield, ArmorType
from dnd.blocks.action_economy import RechargeType
from dnd.entity import Entity, determine_attack_outcome
from dnd.actions import (
    entity_action_economy_cost_evaluator,
    entity_action_economy_cost_applier,
    entity_resource_cost_evaluator,
    AttackEvent,
    Attack
)
from typing import Any, Optional, List, Tuple, cast
from uuid import UUID
import random


# =============================================================================
# UTILITY FUNCTIONS: Dice Roll Manipulation
# =============================================================================

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


# =============================================================================
# LEVEL 1 FEATURES: Fighting Styles
# =============================================================================

# -----------------------------------------------------------------------------
# Archery Fighting Style
# -----------------------------------------------------------------------------

class FightingStyleArchery(BaseCondition):
    """
    Fighter Fighting Style: Archery

    You gain a +2 bonus to attack rolls you make with ranged weapons.
    """
    name: str = "Fighting Style: Archery"
    description: str = "+2 bonus to attack rolls with ranged weapons"

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]],  # (modifiable_value_uuid, modifier_uuid) pairs
        List[UUID],               # event_handler_uuids
        List[UUID],               # subcondition_uuids
        List[UUID],               # spatial_handler_uuids
        Optional[Event]           # completion event
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

        # Add +2 static modifier to ranged attack bonus
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


# -----------------------------------------------------------------------------
# Defense Fighting Style
# -----------------------------------------------------------------------------

def defense_ac_check(
    source_entity_uuid: UUID,
    target_entity_uuid: Optional[UUID] = None,
    context: Optional[dict] = None
) -> Optional[NumericalModifier]:
    """
    Contextual check for Defense fighting style.
    Returns +1 AC only if the entity is wearing armor.
    """
    # Suppress unused parameter warnings (required by callable signature)
    _ = target_entity_uuid
    _ = context

    entity = Entity.get(source_entity_uuid)
    if not entity:
        return None

    # Check if wearing armor (has body armor equipped that isn't cloth)
    body_armor = entity.equipment.body_armor
    if body_armor and body_armor.type != ArmorType.CLOTH:
        return NumericalModifier.create(
            source_entity_uuid=source_entity_uuid,
            name="Defense",
            value=1
        )

    return None


class FightingStyleDefense(BaseCondition):
    """
    Fighter Fighting Style: Defense

    While you are wearing armor, you gain a +1 bonus to AC.
    """
    name: str = "Fighting Style: Defense"
    description: str = "+1 AC while wearing armor"

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]],  # (modifiable_value_uuid, modifier_uuid) pairs
        List[UUID],               # event_handler_uuids
        List[UUID],               # subcondition_uuids
        List[UUID],               # spatial_handler_uuids
        Optional[Event]           # completion event
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

        # Add contextual +1 AC modifier (only applies when wearing armor)
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
            status_message=f"Applied Defense fighting style to {target.name}"
        )

        return outs, [], [], [], effect_event


# -----------------------------------------------------------------------------
# Dueling Fighting Style
# -----------------------------------------------------------------------------

def dueling_damage_check(
    source_entity_uuid: UUID,
    target_entity_uuid: Optional[UUID] = None,
    context: Optional[dict] = None
) -> Optional[NumericalModifier]:
    """
    Contextual check for Dueling fighting style.
    Returns +2 damage only if wielding a melee weapon in one hand with no other weapon.
    """
    # Suppress unused parameter warnings (required by callable signature)
    _ = target_entity_uuid
    _ = context

    entity = Entity.get(source_entity_uuid)
    if not entity:
        return None

    # Check: main hand has a melee weapon, off-hand is empty or has shield
    main_weapon = entity.equipment.weapon_melee_main
    off_hand = entity.equipment.weapon_melee_off

    if main_weapon is None:
        return None  # No weapon in main hand

    # Check if it's a one-handed weapon (not two-handed)
    if WeaponProperty.TWO_HANDED in main_weapon.properties:
        return None  # Two-handed weapon doesn't qualify

    # Check off-hand is empty or has a shield (not a weapon)
    if off_hand is not None and not isinstance(off_hand, Shield):
        return None  # Wielding two weapons doesn't qualify

    return NumericalModifier.create(
        source_entity_uuid=source_entity_uuid,
        name="Dueling",
        value=2
    )


class FightingStyleDueling(BaseCondition):
    """
    Fighter Fighting Style: Dueling

    When you are wielding a melee weapon in one hand and no other weapons,
    you gain a +2 bonus to damage rolls with that weapon.
    """
    name: str = "Fighting Style: Dueling"
    description: str = "+2 damage when wielding a melee weapon in one hand"

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]],  # (modifiable_value_uuid, modifier_uuid) pairs
        List[UUID],               # event_handler_uuids
        List[UUID],               # subcondition_uuids
        List[UUID],               # spatial_handler_uuids
        Optional[Event]           # completion event
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

        # Add contextual +2 melee damage modifier
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


# -----------------------------------------------------------------------------
# Great Weapon Fighting Style
# -----------------------------------------------------------------------------

def great_weapon_fighting_processor(
    event: DamageRollResultEvent,
    source_entity_uuid: UUID
) -> Optional[DamageRollResultEvent]:
    """
    Event processor for Great Weapon Fighting.

    Rerolls 1s and 2s on damage dice for two-handed melee weapons.
    Must use the new roll (cannot keep original).
    """
    # Only process own attacks
    if event.source_entity_uuid != source_entity_uuid:
        return None

    entity = Entity.get(source_entity_uuid)
    if not entity:
        return None

    # Check weapon is two-handed or versatile melee
    weapon = entity.equipment._get_weapon_by_slot(event.weapon_slot)
    if not weapon or isinstance(weapon, Shield):
        return None

    # Type narrowing: weapon is now known to be Weapon
    if not isinstance(weapon, Weapon):
        return None

    # Must be melee (REACH type)
    is_melee = weapon.range.type == RangeType.REACH
    has_two_handed = WeaponProperty.TWO_HANDED in weapon.properties
    has_versatile = WeaponProperty.VERSATILE in weapon.properties

    if not is_melee or not (has_two_handed or has_versatile):
        return None

    # Process each damage roll
    any_modified = False
    for i, original_roll in enumerate(event.final_rolls):
        results = original_roll.results if isinstance(original_roll.results, list) else [original_roll.results]

        # Check if any dice are 1 or 2
        needs_reroll = any(r <= 2 for r in results)
        if not needs_reroll:
            continue

        # Reroll 1s and 2s
        new_results = []
        rerolled_dice = []
        for r in results:
            if r <= 2:
                new_result = random.randint(1, weapon.damage_dice)
                new_results.append(new_result)
                rerolled_dice.append(f"{r}→{new_result}")
            else:
                new_results.append(r)

        # Create new roll and replace
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
    """
    Fighting Style: Great Weapon Fighting

    When you roll a 1 or 2 on a damage die for an attack you make with a melee
    weapon that you are wielding with two hands, you can reroll the die and
    must use the new roll, even if the new roll is a 1 or a 2. The weapon must
    have the two-handed or versatile property for you to gain this benefit.

    This condition registers an event handler that intercepts DAMAGE_ROLLED events
    and rerolls low damage dice.
    """
    name: str = "Fighting Style: Great Weapon Fighting"
    description: str = (
        "When you roll a 1 or 2 on a damage die for an attack with a two-handed "
        "melee weapon, you can reroll the die and must use the new roll."
    )

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]],  # (modifiable_value_uuid, modifier_uuid) pairs
        List[UUID],               # event_handler_uuids
        List[UUID],               # subcondition_uuids
        List[UUID],               # spatial_handler_uuids
        Optional[Event]           # completion event
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

        # Create event handler for DAMAGE_ROLL_RESULT events
        handler = EventHandler(
            name="Great Weapon Fighting",
            source_entity_uuid=target.uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.DAMAGE_ROLL_RESULT,
                    event_phase=EventPhase.EFFECT
                )
            ],
            event_processor=great_weapon_fighting_processor
        )

        # Register the handler (add_event_handler internally calls EventQueue.add_event_handler)
        target.add_event_handler(handler)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Applied Great Weapon Fighting to {target.name}"
        )

        # Return handler UUID so it gets cleaned up when condition is removed
        return [], [handler.uuid], [], [], effect_event


# -----------------------------------------------------------------------------
# Protection Fighting Style
# -----------------------------------------------------------------------------

def protection_processor(
    event: Event,
    source_entity_uuid: UUID  # The protector
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
    # Get the protector (handler owner)
    protector = Entity.get(source_entity_uuid)
    if not protector:
        return None

    # Check 1: Am I NOT the target? (can't protect self)
    if event.target_entity_uuid == source_entity_uuid:
        return None

    # Check 2: Is target within 5ft of me?
    target = Entity.get(event.target_entity_uuid) if event.target_entity_uuid else None
    if not target:
        return None
    distance = protector.senses.get_feet_distance(target.senses.position)
    if distance > 5:
        return None  # Target too far

    # Check 3: Can I see the attacker?
    if event.source_entity_uuid not in protector.senses.entities:
        return None  # Can't see attacker

    # Check 4: Do I have a shield equipped?
    # Shield is stored in the off-hand melee slot
    off_hand = protector.equipment.weapon_melee_off
    if not off_hand or not isinstance(off_hand, Shield):
        return None  # No shield

    # Check 5: Do I have a reaction available?
    if not protector.action_economy.can_afford("reactions", 1):
        return None  # No reaction

    # All checks passed - apply Protection!

    # Get the attack_bonus from the event
    if not isinstance(event, AttackEvent) or not event.attack_bonus:
        return None  # No attack_bonus to modify
    attack_bonus = event.attack_bonus

    # Check if Protection disadvantage already exists (prevent multiple protectors stacking)
    for modifier in attack_bonus.self_static.advantage_modifiers.values():
        if modifier.name == "Protection":
            return None  # Another protector already used Protection

    # Add disadvantage modifier to the attack
    attack_bonus.self_static.add_advantage_modifier(
        AdvantageModifier(
            name="Protection",
            value=AdvantageStatus.DISADVANTAGE,
            source_entity_uuid=source_entity_uuid,  # Protector
            target_entity_uuid=event.target_entity_uuid  # Protected ally
        )
    )

    # Consume the reaction
    protector.action_economy.consume("reactions", 1)

    # Return modified event
    return event.model_copy(update={
        "modified": True,
        "status_message": f"{protector.name} uses Protection to impose disadvantage"
    })


def create_protection_handler(source_entity_uuid: UUID) -> EventHandler:
    """Create an EventHandler for Protection fighting style."""
    return EventHandler(
        name="Protection",
        source_entity_uuid=source_entity_uuid,
        trigger_conditions=[
            Trigger(
                event_type=EventType.ATTACK,
                event_phase=EventPhase.EXECUTION
            )
        ],
        event_processor=protection_processor
    )


class FightingStyleProtection(BaseCondition):
    """
    Fighter Fighting Style: Protection

    When a creature you can see attacks a target other than you
    that is within 5 feet of you, you can use your reaction to
    impose disadvantage on the attack roll. You must be wielding a shield.
    """
    name: str = "Fighting Style: Protection"
    description: str = "Use reaction to impose disadvantage on attacks against nearby allies"

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]],  # (modifiable_value_uuid, modifier_uuid) pairs
        List[UUID],               # event_handler_uuids
        List[UUID],               # subcondition_uuids
        List[UUID],               # spatial_handler_uuids
        Optional[Event]           # completion event
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

        # Register the Protection event handler (add_event_handler internally calls EventQueue)
        handler = create_protection_handler(target.uuid)
        target.add_event_handler(handler)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Applied Protection fighting style to {target.name}"
        )

        # Track handler for auto-cleanup when condition is removed
        return [], [handler.uuid], [], [], effect_event


# -----------------------------------------------------------------------------
# Two-Weapon Fighting Style
# -----------------------------------------------------------------------------

def twf_off_hand_melee_ability_bonus(
    source_entity_uuid: UUID,
    target_entity_uuid: Optional[UUID] = None,
    context: Optional[dict] = None
) -> Optional[NumericalModifier]:
    """
    Contextual modifier for TWF off-hand melee damage.
    Evaluated at damage time - checks weapon properties to determine correct ability.
    """
    _ = target_entity_uuid, context  # Suppress unused warnings

    entity = Entity.get(source_entity_uuid)
    if not entity:
        return None

    off_hand = entity.equipment.weapon_melee_off
    if not off_hand or isinstance(off_hand, Shield):
        return None

    # Determine ability based on weapon properties AT EVALUATION TIME
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
    _ = target_entity_uuid, context  # Suppress unused warnings

    entity = Entity.get(source_entity_uuid)
    if not entity:
        return None

    off_hand = entity.equipment.weapon_ranged_off
    if not off_hand:
        return None

    # Ranged always uses DEX
    return NumericalModifier.create(
        source_entity_uuid=source_entity_uuid,
        name="Two-Weapon Fighting",
        value=entity.ability_scores.dexterity.modifier
    )


class FightingStyleTwoWeaponFighting(BaseCondition):
    """
    Fighter Fighting Style: Two-Weapon Fighting

    When you engage in two-weapon fighting, you can add your ability modifier
    to the damage of the second attack.

    This condition adds contextual modifiers to the off-hand ability bonus
    ModifiableValues that evaluate at damage time and return the appropriate
    ability modifier based on weapon properties.
    """
    name: str = "Fighting Style: Two-Weapon Fighting"
    description: str = "Add ability modifier to off-hand attack damage"

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]],  # (modifiable_value_uuid, modifier_uuid) pairs
        List[UUID],               # event_handler_uuids
        List[UUID],               # subcondition_uuids
        List[UUID],               # spatial_handler_uuids
        Optional[Event]           # completion event
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

        # Add contextual modifier to off-hand MELEE ability bonus
        melee_mod = ContextualNumericalModifier(
            name="Two-Weapon Fighting",
            source_entity_uuid=self.target_entity_uuid,
            target_entity_uuid=self.target_entity_uuid,
            callable=twf_off_hand_melee_ability_bonus
        )
        mod_uuid = target.equipment.off_hand_melee_ability_bonus.self_contextual.add_value_modifier(melee_mod)
        outs.append((target.equipment.off_hand_melee_ability_bonus.uuid, mod_uuid))

        # Add contextual modifier to off-hand RANGED ability bonus
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


# =============================================================================
# LEVEL 1 FEATURES: Second Wind
# =============================================================================

class SecondWind(BaseAction):
    """
    Fighter's Second Wind - heal 1d10 + fighter level as a bonus action.

    Uses the 'second_wind' resource (registered by SecondWindFeature).
    Can only use when damaged (not at full health).
    """
    name: str = "Second Wind"
    description: str = "Heal 1d10 + level as a bonus action"
    target_type: TargetType = TargetType.SELF
    fighter_level: int = 1

    # Cost: 1 bonus action + 1 second_wind resource
    costs: List[Cost] = []

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
        # Populate entity name for combat log generation
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

        # Check entity is damaged (has damage_taken > 0)
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

        # Roll healing: 1d10 + fighter level
        healing_dice = Dice(
            count=1,
            value=10,
            bonus=ModifiableValue.create(
                source_entity_uuid=self.source_entity_uuid,
                base_value=self.fighter_level,
                value_name="Fighter Level"
            ),
            roll_type=RollType.CHECK  # Using CHECK type for healing dice
        )
        healing_roll = healing_dice.roll
        total_healing = healing_roll.total

        # Build source description from roll for combat log
        roll_results = healing_roll.results
        roll_str = str(roll_results[0]) if isinstance(roll_results, list) and roll_results else "?"
        source_desc = f"Second Wind: d10({roll_str})+{self.fighter_level}"

        # Apply healing via event system
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
    """
    Fighter Level 1 Feature: Second Wind

    You have a limited well of stamina that you can draw on to protect yourself
    from harm. On your turn, you can use a bonus action to regain hit points
    equal to 1d10 + your fighter level.

    Once you use this feature, you must finish a short or long rest before you
    can use it again.

    This condition grants the 'second_wind' resource and registers the SecondWind action.
    """
    name: str = "Second Wind Feature"
    description: str = "Heal 1d10 + fighter level as a bonus action (1/short rest)"
    fighter_level: int = 1

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]],  # (modifiable_value_uuid, modifier_uuid) pairs
        List[UUID],               # event_handler_uuids
        List[UUID],               # subcondition_uuids
        List[UUID],               # spatial_handler_uuids
        Optional[Event]           # completion event
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

        # Add resource (recharges on short rest)
        target.action_economy.add_resource(
            name="second_wind",
            maximum=1,
            recharge_type=RechargeType.SHORT_REST
        )

        # Register Second Wind action template
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


# =============================================================================
# LEVEL 2 FEATURES: Action Surge
# =============================================================================

class ActionSurging(BaseCondition):
    """
    Temporary condition from Action Surge.

    Grants +1 action for the current turn. Expires at start of next turn.
    Also serves as a marker to prevent using Action Surge more than once per turn.
    """
    name: str = "ActionSurging"
    description: str = "+1 action this turn (Action Surge used)"
    condition_category: ConditionCategory = ConditionCategory.INTERNAL

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")

        target_entity = Entity.get(self.target_entity_uuid)
        if not target_entity:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} not found")

        # Set duration to 1 round (expires at start of next turn)
        self.duration.duration_type = DurationType.ROUNDS
        self.duration.duration = 1

        outs = []

        # Add +1 action modifier
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
    """
    Fighter Feature: Action Surge (Level 2)

    On your turn, take one additional action.
    Once used, must finish a short/long rest to use again.
    Level 17: Can use twice before a rest, but only once per turn.

    This is a free action (no action cost) - only costs the resource.
    """
    name: str = "Action Surge"
    description: str = "Take one additional action on your turn"
    target_type: TargetType = TargetType.SELF

    # Free action - only costs the resource
    costs: List[Cost] = []

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        self.costs = [
            Cost(
                name="Action Surge",
                cost_type="actions",
                cost=0,  # No action cost
                resource_name="action_surge",
                resource_cost=1,
                evaluator=None,
                resource_evaluator=entity_resource_cost_evaluator
            )
        ]

    def _create_declaration_event(self, parent_event: Optional[Event] = None, use_register: bool = True) -> Optional[ActionEvent]:
        """Create the declaration event for Action Surge."""
        # Populate entity name for combat log generation
        entity = Entity.get(self.source_entity_uuid)
        source_name = entity.name if entity else None

        return ActionEvent(
            name=self.name,
            parent_event=parent_event.uuid if parent_event else None,
            phase=EventPhase.DECLARATION,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.source_entity_uuid,  # Self-targeted
            costs=[BaseCost.model_validate(cost) for cost in self.costs],
            use_register=use_register,
            source_entity_name=source_name
        )

    def _validate(self, declaration_event: ActionEvent) -> ActionEvent:
        """Validate Action Surge can be used."""
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return declaration_event.cancel(status_message="Entity not found")

        # Check resource available
        if not entity.action_economy.can_afford_resource("action_surge", 1):
            return declaration_event.cancel(status_message="Action Surge not available")

        # Check not already used this turn (ActionSurging serves as the marker)
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

        # Apply ActionSurging (+1 action effect, also serves as once-per-turn marker)
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
    """
    Fighter Level 2 Feature: Action Surge

    On your turn, you can take one additional action on top of your regular
    action and a possible bonus action.

    Once you use this feature, you must finish a short or long rest before
    you can use it again. Starting at 17th level, you can use it twice before
    a rest, but only once on the same turn.

    This condition grants the Action Surge resource and registers the action.
    """
    name: str = "Action Surge Feature"
    description: str = "Take one additional action on your turn"
    num_uses: int = 1  # 1 at L2, 2 at L17

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]],  # (modifiable_value_uuid, modifier_uuid) pairs
        List[UUID],               # event_handler_uuids
        List[UUID],               # subcondition_uuids
        List[UUID],               # spatial_handler_uuids
        Optional[Event]           # completion event
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

        # Add resource (recharges on short rest)
        target.action_economy.add_resource(
            name="action_surge",
            maximum=self.num_uses,
            recharge_type=RechargeType.SHORT_REST
        )

        # Register action template
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

        # Call parent removal logic
        return super()._remove(event)


# =============================================================================
# LEVEL 3 FEATURES: Champion Archetype - Improved Critical
# =============================================================================

class ImprovedCritical(BaseCondition):
    """
    Champion Fighter (Level 3): Improved Critical

    Your weapon attacks score a critical hit on a roll of 19 or 20.

    This condition adds +1 to the general crit threshold modifier,
    lowering the natural roll needed for a critical hit from 20 to 19.
    """
    name: str = "Improved Critical"
    description: str = (
        "Your weapon attacks score a critical hit on a roll of 19 or 20."
    )

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]],  # (modifiable_value_uuid, modifier_uuid) pairs
        List[UUID],               # event_handler_uuids
        List[UUID],               # subcondition_uuids
        List[UUID],               # spatial_handler_uuids
        Optional[Event]           # completion event
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

        # Add +1 to general crit threshold (applies to all attacks)
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


# =============================================================================
# LEVEL 5 FEATURES: Extra Attack
# =============================================================================

# =============================================================================
# NOTE: HasAttacked is now a GENERIC condition in dnd/conditions.py
# It is applied by global handlers registered in setup_standard_actions().
# The processor below is FIGHTER-SPECIFIC: manages extra_attacks resource.
# =============================================================================


class ExtraAttacksGranted(BaseCondition):
    """
    Marker condition: Extra attacks have been granted this turn.

    Used by extra_attack_resource_processor to track whether extra attacks
    have already been granted this turn (for Action Surge compatibility).
    Expires at TURN_START.
    """
    name: str = "ExtraAttacksGranted"
    description: str = "Extra attacks have been granted this turn"
    condition_category: ConditionCategory = ConditionCategory.INTERNAL

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
    # Only trigger for the attacker's own attacks
    if event.source_entity_uuid != source_entity_uuid:
        return None

    # Only on non-canceled events
    if event.canceled:
        return None

    entity = Entity.get(source_entity_uuid)
    if not entity:
        return None

    # Only process FIRST event at EXECUTION phase for this attack
    if not EventQueue.is_first_at_phase(event):
        return None

    # Check if this attack cost an action (not OA reaction, not bonus action)
    if not isinstance(event, ActionEvent) or not event.costs:
        return None

    action_cost_attack = any(
        c.cost_type == "actions" and c.cost > 0
        for c in event.costs
    )
    if not action_cost_attack:
        return None  # Skip OA (reaction) and bonus action attacks

    # Get Extra Attack feature and resource
    extra_attack_feature = entity.active_conditions.get("Extra Attack")
    extra_attack_resource = entity.action_economy.resources.get("extra_attacks")

    if not extra_attack_resource or not extra_attack_feature:
        return None  # No Extra Attack feature

    num_extra = extra_attack_feature.extra_attacks if isinstance(extra_attack_feature, ExtraAttackFeature) else 1

    # Check ExtraAttacksGranted to determine first vs subsequent Attack action
    # This marker is applied BY THIS PROCESSOR after granting extras
    if "ExtraAttacksGranted" not in entity.active_conditions:
        # FIRST Attack action this turn - SET extra_attacks
        extra_attack_resource.current = num_extra

        # Apply marker so subsequent Attack actions ADD instead of SET
        marker = ExtraAttacksGranted(
            source_entity_uuid=source_entity_uuid,
            target_entity_uuid=source_entity_uuid
        )
        marker.duration.duration_type = DurationType.ROUNDS
        marker.duration.duration = 1
        entity.add_condition(marker)
    else:
        # SUBSEQUENT Attack action (via Action Surge) - ADD extra_attacks
        extra_attack_resource.current += num_extra

    return None  # Don't modify the attack event


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
    """
    Make an additional attack using Extra Attack feature (Fighter Level 5+).

    Prerequisites:
    - Must have the HasAttacked condition (meaning you've attacked this turn)
    - Must have extra_attacks resource available

    This action has no action cost (action was already spent on the first attack),
    but consumes 1 use of the extra_attacks resource.

    When used as a template (template=True), target_entity_uuid should be set via
    set_target_entity() before pre_validate() or instantiate().
    """
    name: str = "Extra Attack"
    description: str = "Make an additional weapon attack"
    target_type: TargetType = TargetType.ENTITY
    weapon_slot: WeaponSlot = WeaponSlot.MELEE_MAIN
    action_category: ActionCategory = ActionCategory.ATTACK

    # Cost: only resource, no action cost
    costs: List[Cost] = []

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        self.costs = [
            Cost(
                name="Extra Attack",
                cost_type="actions",
                cost=0,  # No action cost - already spent on first Attack
                resource_name="extra_attacks",
                resource_cost=1,
                evaluator=None,
                resource_evaluator=entity_resource_cost_evaluator
            )
        ]

    def _create_declaration_event(self, parent_event: Optional[Event] = None, use_register: bool = True) -> Optional[Event]:
        """Create the declaration event for the extra attack action."""
        # Populate entity names and weapon name for combat log generation
        source_entity = Entity.get(self.source_entity_uuid)
        target_entity = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        source_name = source_entity.name if source_entity else None
        target_name = target_entity.name if target_entity else None

        # Get weapon name
        weapon_name = None
        if source_entity:
            weapon = source_entity.equipment._get_weapon_by_slot(self.weapon_slot)
            weapon_name = weapon.name if weapon and hasattr(weapon, 'name') else "Unarmed"

        # Use clean name for combat log (e.g., "Extra Attack (Shortbow)")
        display_name = f"Extra Attack ({weapon_name})" if weapon_name else "Extra Attack"

        return AttackEvent(
            name=display_name,
            parent_event=parent_event.uuid if parent_event else None,
            phase=EventPhase.DECLARATION,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid,
            weapon_slot=self.weapon_slot,
            costs=[BaseCost.model_validate(cost) for cost in self.costs],
            use_register=use_register,
            source_entity_name=source_name,
            target_entity_name=target_name,
            weapon_name=weapon_name
        )

    def _validate(self, declaration_event: Event) -> Optional[Event]:
        """Validate the extra attack action."""
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return declaration_event.cancel(status_message="Entity not found")

        # PREREQUISITE: Must have used action to attack (ExtraAttacksGranted condition)
        # Note: We check ExtraAttacksGranted (not HasAttacked) because Extra Attack
        # requires an action-cost attack, while HasAttacked tracks ALL attacks for rage.
        if "ExtraAttacksGranted" not in entity.active_conditions:
            return declaration_event.cancel(
                status_message="Must attack first before using Extra Attack"
            )

        # Validate target exists
        if not self.target_entity_uuid:
            return declaration_event.cancel(status_message="No target specified")

        target = Entity.get(self.target_entity_uuid)
        if not target:
            return declaration_event.cancel(status_message="Target not found")

        # Validate line of sight
        if self.target_entity_uuid not in entity.senses.entities:
            return declaration_event.cancel(status_message="Target not visible")

        # Validate range (reuse Attack's range validation)
        # Cast to AttackEvent since _create_declaration_event creates an AttackEvent
        attack_event = cast(AttackEvent, declaration_event)
        range_validated = Attack.validate_range(attack_event, self.source_entity_uuid)
        if range_validated is None or range_validated.canceled:
            return range_validated

        # Check ranged conditions (threatened)
        ranged_conditions = Attack.check_ranged_conditions(range_validated, self.source_entity_uuid)
        if ranged_conditions is None or ranged_conditions.canceled:
            return ranged_conditions

        return ranged_conditions.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Extra Attack validated"
        )

    def _apply(self, execution_event) -> Optional[Event]:
        """Apply the extra attack - execute the actual attack logic."""
        # Reuse the Attack.attack_consequences method for the actual attack
        # Cast to AttackEvent since _create_declaration_event creates an AttackEvent
        attack_event = cast(AttackEvent, execution_event)
        return Attack.attack_consequences(attack_event, self.source_entity_uuid)

    def _apply_costs(self, completion_event) -> Optional[Event]:
        """Apply the costs (consume extra_attacks resource)."""
        return entity_action_economy_cost_applier(completion_event, self.source_entity_uuid)


class ExtraAttackFeature(BaseCondition):
    """
    Fighter (Level 5/11/20): Extra Attack

    Beginning at 5th level, you can attack twice, instead of once,
    whenever you take the Attack action on your turn.

    - Level 5: 1 extra attack (2 total)
    - Level 11: 2 extra attacks (3 total)
    - Level 20: 3 extra attacks (4 total)

    This condition:
    1. Adds the 'extra_attacks' resource to the entity's ActionEconomy
    2. Registers ExtraAttack action templates for each equipped weapon
    3. Registers the HasAttacked event handler to enable the Extra Attack flow
    """
    name: str = "Extra Attack"
    description: str = "Can make additional attacks when taking the Attack action"

    # Configuration
    extra_attacks: int = 1  # 1 at L5, 2 at L11, 3 at L20

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]],  # (modifiable_value_uuid, modifier_uuid) pairs
        List[UUID],               # event_handler_uuids
        List[UUID],               # subcondition_uuids
        List[UUID],               # spatial_handler_uuids
        Optional[Event]           # completion event
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

        # 1. Add the extra_attacks resource (recharges at turn start)
        target.action_economy.add_resource(
            name="extra_attacks",
            maximum=self.extra_attacks,
            recharge_type=RechargeType.TURN_START
        )

        # 2. Register ExtraAttack action templates for each equipped weapon
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

        # 3. Register the Extra Attack Resource handler (Fighter-specific)
        # Note: HasAttacked tracking is now handled globally by setup_standard_actions()
        handler = create_extra_attack_resource_handler(target.uuid)
        target.add_event_handler(handler)
        handler_uuids.append(handler.uuid)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Granted Extra Attack ({self.extra_attacks} extra) to {target.name}"
        )

        # Return handler UUID for cleanup when condition is removed
        return [], handler_uuids, [], [], effect_event

    def _remove(self, event: Optional[Event] = None) -> Optional[Event]:
        """
        Custom removal: clean up resources and action templates.
        """
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target:
            # Remove the resource
            target.action_economy.remove_resource("extra_attacks")

            # Unregister ExtraAttack templates
            for slot in [WeaponSlot.MELEE_MAIN, WeaponSlot.MELEE_OFF,
                         WeaponSlot.RANGED_MAIN, WeaponSlot.RANGED_OFF]:
                template_name = f"Extra Attack_{slot.value}"
                target.unregister_action(template_name)

        # Call parent removal logic
        return super()._remove(event)


# =============================================================================
# LEVEL 9 FEATURES: Indomitable
# =============================================================================

def indomitable_processor(
    event: Event,
    source_entity_uuid: UUID
) -> Optional[Event]:
    """
    Reroll failed saving throws.
    Triggers on SAVING_THROW at EFFECT phase.

    Per RAW: Must use the new roll, even if it's worse.
    """
    # Only process own saves (target of save is the one making it)
    if event.target_entity_uuid != source_entity_uuid:
        return None

    # Type check: must be a SavingThrowEvent
    if not isinstance(event, SavingThrowEvent):
        return None

    entity = Entity.get(source_entity_uuid)
    if not entity:
        return None

    # Check if save failed
    if event.result is not False:
        return None  # Save succeeded or not yet resolved

    # Check resource available
    if not entity.action_economy.can_afford_resource("indomitable", 1):
        return None

    # Consume resource
    entity.action_economy.consume_resource("indomitable", 1)

    # Reroll the save (must use new result per RAW)
    ability_name = event.ability_name
    save_bonus = entity.saving_throw_bonus(event.source_entity_uuid, ability_name)
    new_roll = entity.roll_d20(save_bonus, RollType.SAVE)

    # Determine new result
    dc = event.get_dc()
    if dc is None:
        return None

    new_outcome = determine_attack_outcome(new_roll, dc)
    new_success = new_outcome not in [AttackOutcome.MISS, AttackOutcome.CRIT_MISS]

    # Return modified event with new roll
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
                event_phase=EventPhase.EFFECT  # After roll, can see result
            )
        ],
        event_processor=indomitable_processor
    )


class Indomitable(BaseCondition):
    """
    Fighter Level 9 Feature: Indomitable

    You can reroll a saving throw that you fail. If you do so, you must use
    the new roll. You can use this feature once per long rest.

    Additional uses: Level 13 (2 uses), Level 17 (3 uses).
    """
    name: str = "Indomitable"
    description: str = "Reroll a failed saving throw (must use new roll)"
    num_uses: int = 1  # 1 at L9, 2 at L13, 3 at L17

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]],  # (modifiable_value_uuid, modifier_uuid) pairs
        List[UUID],               # event_handler_uuids
        List[UUID],               # subcondition_uuids
        List[UUID],               # spatial_handler_uuids
        Optional[Event]           # completion event
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

        # Add resource (recharges on long rest)
        target.action_economy.add_resource(
            name="indomitable",
            maximum=self.num_uses,
            recharge_type=RechargeType.LONG_REST
        )

        # Register event handler (add_event_handler internally calls EventQueue)
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

        # Call parent removal logic
        return super()._remove(event)


# =============================================================================
# LEVEL 15 FEATURES: Champion Archetype - Superior Critical
# =============================================================================

class SuperiorCritical(BaseCondition):
    """
    Champion Fighter (Level 15): Superior Critical

    Your weapon attacks score a critical hit on a roll of 18-20.

    This condition adds +2 to the general crit threshold modifier,
    lowering the natural roll needed for a critical hit from 20 to 18.

    Note: This should replace Improved Critical, not stack with it.
    The total modifier of +2 means crits on 18, 19, or 20.
    """
    name: str = "Superior Critical"
    description: str = (
        "Your weapon attacks score a critical hit on a roll of 18, 19, or 20."
    )

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]],  # (modifiable_value_uuid, modifier_uuid) pairs
        List[UUID],               # event_handler_uuids
        List[UUID],               # subcondition_uuids
        List[UUID],               # spatial_handler_uuids
        Optional[Event]           # completion event
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

        # Add +2 to general crit threshold (applies to all attacks)
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


# =============================================================================
# LEVEL 18 FEATURES: Champion Archetype - Survivor
# =============================================================================

def survivor_processor(
    event: Event,
    source_entity_uuid: UUID  # The entity with Survivor
) -> Optional[Event]:
    """
    Turn start handler for Survivor.
    Heals 5 + CON mod if HP <= 50% and HP > 0.
    Triggers at EXECUTION phase, before conditions advance.

    Per SRD: At the start of each of your turns, you regain hit points equal
    to 5 + your Constitution modifier if you have no more than half of your
    hit points left. You don't gain this benefit if you have 0 hit points.
    """
    # Only trigger on OUR turn start
    if event.source_entity_uuid != source_entity_uuid:
        return None

    entity = Entity.get(source_entity_uuid)
    if not entity:
        return None

    current_hp = entity.get_hp()
    # Max HP = current HP + damage taken (since get_hp() subtracts damage_taken)
    max_hp = current_hp + entity.health.damage_taken

    # Check conditions: HP > 0 AND HP <= 50%
    if current_hp <= 0:
        return None  # No benefit at 0 HP

    if current_hp > max_hp / 2:
        return None  # Above half HP, no benefit

    # Heal 5 + CON modifier
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
                event_phase=EventPhase.EXECUTION  # Triggers at EXECUTION phase
            )
        ],
        event_processor=survivor_processor
    )


class Survivor(BaseCondition):
    """
    Champion Fighter Level 18: Survivor

    At the start of each of your turns, you regain hit points equal to
    5 + your Constitution modifier if you have no more than half of your
    hit points left. You don't gain this benefit if you have 0 hit points.

    This condition registers an EventHandler that triggers at TURN_START
    at EXECUTION phase (before conditions expire and action economy resets).
    """
    name: str = "Survivor"
    description: str = "Heal 5 + CON mod at turn start when HP <= 50% max"

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]],  # (modifiable_value_uuid, modifier_uuid) pairs
        List[UUID],               # event_handler_uuids
        List[UUID],               # subcondition_uuids
        List[UUID],               # spatial_handler_uuids
        Optional[Event]           # completion event
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

        # Register turn start handler at EXECUTION phase
        # Note: target.add_event_handler() internally calls EventQueue.add_event_handler()
        handler = create_survivor_handler(target.uuid)
        target.add_event_handler(handler)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Granted Survivor to {target.name}"
        )

        # Return handler UUID for cleanup when condition is removed
        return [], [handler.uuid], [], [], effect_event
