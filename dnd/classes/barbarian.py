"""
Barbarian Class Features

Implements Barbarian-specific features as conditions that can be applied to entities.
Organized by D&D 5e level progression.

Level 1: Rage (Unarmored Defense handled via EquipmentConfig)
Level 2: Reckless Attack, Danger Sense
Level 3: Berserker Path - Frenzy (BG3 version - no exhaustion)
Level 5: Extra Attack (reuses Fighter's ExtraAttackFeature), Fast Movement
Level 6: Mindless Rage
Level 7: Feral Instinct
Level 9/13/17: Brutal Critical
Level 10: Intimidating Presence
Level 11: Relentless Rage
Level 14: Retaliation
Level 15: Persistent Rage
Level 18: Indomitable Might
Level 20: Primal Champion
"""

from dnd.core.base_conditions import BaseCondition, DurationType
from dnd.core.base_block import BaseBlock
from dnd.core.base_actions import (
    BaseAction, ActionEvent, Cost, TargetType, BaseCost
)
from dnd.core.events import (
    Event, EventPhase, EventType,
    Trigger, EventHandler,
    WeaponSlot,
    TakeDamageEvent, SkillCheckEvent
)
from dnd.core.modifiers import (
    NumericalModifier, AdvantageModifier, AdvantageStatus,
    ContextualNumericalModifier, ContextualAdvantageModifier,
)
from dnd.blocks.equipment import ArmorType
from dnd.blocks.action_economy import RechargeType
from dnd.core.dice import RollType
from dnd.entity import Entity
from dnd.actions import (
    entity_action_economy_cost_evaluator,
    entity_action_economy_cost_applier,
    Attack,
)
from dnd.conditions import Frightened
from typing import Any, Optional, List, Tuple
from uuid import UUID
from functools import partial

# Import rage/frenzy system from rage.py
from dnd.classes.rage import (
    # Rage system
    rage_damage_check,
    rage_maintenance_processor,
    rage_armor_equip_handler,
    create_rage_maintenance_handler,
    create_rage_armor_handler,
    rage_death_processor,
    create_rage_death_handler,
    Raging,
    Rage,
    EndRage,
    RageFeature,
    # Frenzy system
    Frenzied,
    FrenziedStrike,
    Frenzy,
    FrenzyFeature,
)

# Re-export for backward compatibility
__all__ = [
    # Rage system (from rage.py)
    "rage_damage_check",
    "rage_maintenance_processor",
    "rage_armor_equip_handler",
    "create_rage_maintenance_handler",
    "create_rage_armor_handler",
    "rage_death_processor",
    "create_rage_death_handler",
    "Raging",
    "Rage",
    "EndRage",
    "RageFeature",
    # Frenzy system (from rage.py)
    "Frenzied",
    "FrenziedStrike",
    "Frenzy",
    "FrenzyFeature",
    # Level 2
    "RecklessAttacking",
    "RecklessAttack",
    "RecklessAttackFeature",
    "danger_sense_check",
    "DangerSense",
    # Level 5
    "fast_movement_check",
    "FastMovement",
    # Level 6
    "mindless_rage_immunity_check",
    "MindlessRage",
    # Level 7
    "FeralInstinct",
    # Level 9/13/17
    "BrutalCritical",
    # Level 10 (Berserker)
    "IntimidatingPresenceImmunity",
    "intimidating_presence_end_check_processor",
    "create_intimidating_presence_end_handler",
    "IntimidatingPresence",
    "ExtendIntimidatingPresence",
    "IntimidatingPresenceFeature",
    # Level 11
    "relentless_rage_processor",
    "RelentlessRage",
    # Level 14 (Berserker)
    "retaliation_processor",
    "create_retaliation_handler",
    "Retaliation",
    # Level 15
    "PersistentRage",
    # Level 18
    "indomitable_might_processor",
    "create_indomitable_might_handler",
    "IndomitableMight",
    # Level 20
    "PrimalChampion",
]


# =============================================================================
# LEVEL 1: Unarmored Defense
# =============================================================================

# =============================================================================
# LEVEL 2: Reckless Attack
# =============================================================================

class RecklessAttacking(BaseCondition):
    """
    Marker + effects for Reckless Attack.

    When activated (typically at the start of your turn or before your first attack):
    - You gain advantage on melee weapon attack rolls using STR this turn
    - Attack rolls against you have advantage until your next turn

    Duration: 1 round (expires at start of next turn).

    Note: This is a simplified version. In D&D 5e, Reckless Attack is declared
    when making the first attack, not as a separate action.
    """
    name: str = "Reckless Attacking"
    description: str = "Advantage on melee STR attacks, but attackers have advantage against you"

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

        # Set duration to 1 round
        self.duration.duration_type = DurationType.ROUNDS
        self.duration.duration = 1

        outs: List[Tuple[UUID, UUID]] = []

        # 1. Advantage on own melee attacks
        melee_adv_mod = AdvantageModifier(
            name="Reckless Attack",
            value=AdvantageStatus.ADVANTAGE,
            source_entity_uuid=self.target_entity_uuid,
            target_entity_uuid=self.target_entity_uuid
        )
        mod_uuid = target.equipment.melee_attack_bonus.self_static.add_advantage_modifier(melee_adv_mod)
        outs.append((target.equipment.melee_attack_bonus.uuid, mod_uuid))

        # 2. Attackers have advantage against us (to_target channel)
        # This gives advantage to entities attacking us
        attacker_adv_mod = AdvantageModifier(
            name="Reckless (Exposed)",
            value=AdvantageStatus.ADVANTAGE,
            source_entity_uuid=self.target_entity_uuid,
            target_entity_uuid=self.target_entity_uuid
        )
        mod_uuid = target.equipment.ac_bonus.to_target_static.add_advantage_modifier(attacker_adv_mod)
        outs.append((target.equipment.ac_bonus.uuid, mod_uuid))

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"{target.name} attacks recklessly!"
        )

        return outs, [], [], [], effect_event


class RecklessAttack(BaseAction):
    """
    Barbarian Level 2: Reckless Attack Action

    Activate reckless attack mode for this turn.
    This is a free action (costs nothing) that applies the RecklessAttacking condition.
    """
    name: str = "Reckless Attack"
    description: str = "Attack recklessly - advantage on attacks, but exposed to counter-attacks"
    target_type: TargetType = TargetType.SELF

    # Free action - no cost
    costs: List[Cost] = []

    def _create_declaration_event(self, parent_event: Optional[Event] = None, use_register: bool = True) -> Optional[ActionEvent]:
        entity = Entity.get(self.source_entity_uuid)
        source_name = entity.name if entity else None

        return ActionEvent(
            name=self.name,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.source_entity_uuid,
            costs=[],
            parent_event=parent_event.uuid if parent_event else None,
            use_register=use_register,
            source_entity_name=source_name
        )

    def _validate(self, declaration_event: ActionEvent) -> Optional[ActionEvent]:
        entity = Entity.get(self.source_entity_uuid)
        if entity is None:
            return declaration_event.cancel(status_message="Entity not found")

        # Already reckless this turn?
        if "Reckless Attacking" in entity.active_conditions:
            return declaration_event.cancel(status_message="Already attacking recklessly")

        return declaration_event.phase_to(
            EventPhase.EXECUTION,
            status_message="Reckless Attack ready"
        )

    def _apply(self, execution_event: ActionEvent) -> Optional[ActionEvent]:
        entity = Entity.get(self.source_entity_uuid)
        if entity is None:
            return execution_event.cancel(status_message="Entity not found")

        # Apply RecklessAttacking condition
        reckless = RecklessAttacking(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.source_entity_uuid
        )
        entity.add_condition(reckless, parent_event=execution_event)

        return execution_event.phase_to(
            EventPhase.COMPLETION,
            status_message=f"{entity.name} attacks recklessly!"
        )

    def _apply_costs(self, completion_event: ActionEvent) -> ActionEvent:
        return completion_event  # No costs


class RecklessAttackFeature(BaseCondition):
    """
    Barbarian Level 2 Feature: Reckless Attack

    When you make your first attack on your turn, you can decide to attack
    recklessly. Doing so gives you advantage on melee weapon attack rolls
    using Strength during this turn, but attack rolls against you have
    advantage until your next turn.

    This condition grants the Reckless Attack action.
    """
    name: str = "Reckless Attack Feature"
    description: str = "Can attack recklessly for advantage at cost of being easier to hit"

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

        # Register Reckless Attack action template
        reckless_action = RecklessAttack(
            source_entity_uuid=target.uuid,
            template=True
        )
        target.register_action(reckless_action)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Granted Reckless Attack to {target.name}"
        )

        return [], [], [], [], effect_event

    def _remove(self, event: Optional[Event] = None) -> Optional[Event]:
        """Clean up action on removal."""
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target:
            target.unregister_action("Reckless Attack")

        return super()._remove(event)


# =============================================================================
# LEVEL 2: Danger Sense
# =============================================================================

def danger_sense_check(
    source_entity_uuid: UUID,
    target_entity_uuid: Optional[UUID] = None,
    context: Optional[dict] = None
) -> Optional[AdvantageModifier]:
    """
    Contextual check for Danger Sense.

    Grants advantage on DEX saves against effects you can see,
    as long as you're not blinded, deafened, or incapacitated.
    """
    _ = context  # Suppress unused warning

    entity = Entity.get(source_entity_uuid)
    if not entity:
        return None

    # Disabled conditions
    disabled_conditions = ["Blinded", "Deafened", "Incapacitated"]
    if any(c in entity.active_conditions for c in disabled_conditions):
        return None  # Can't use Danger Sense

    # Check can see source of effect (target_uuid is effect source)
    # If no target specified, assume the effect is visible
    if target_entity_uuid and target_entity_uuid not in entity.senses.entities:
        return None  # Can't see the source

    return AdvantageModifier(
        name="Danger Sense",
        value=AdvantageStatus.ADVANTAGE,
        source_entity_uuid=source_entity_uuid,
        target_entity_uuid=target_entity_uuid
    )


class DangerSense(BaseCondition):
    """
    Barbarian Level 2: Danger Sense

    You have advantage on Dexterity saving throws against effects that you
    can see, such as traps and spells. To gain this benefit, you can't be
    blinded, deafened, or incapacitated.
    """
    name: str = "Danger Sense"
    description: str = "Advantage on DEX saves vs effects you can see"

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

        # Add contextual advantage on DEX saves
        # Only applies when NOT blinded, deafened, or incapacitated
        dex_save = target.saving_throws.get_saving_throw("dexterity")
        danger_mod = ContextualAdvantageModifier(
            name="Danger Sense",
            source_entity_uuid=self.target_entity_uuid,
            target_entity_uuid=self.target_entity_uuid,
            callable=danger_sense_check
        )
        mod_uuid = dex_save.bonus.self_contextual.add_advantage_modifier(danger_mod)
        outs.append((dex_save.bonus.uuid, mod_uuid))

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Applied Danger Sense to {target.name}"
        )

        return outs, [], [], [], effect_event


# =============================================================================
# LEVEL 5: Fast Movement
# =============================================================================

def fast_movement_check(
    source_entity_uuid: UUID,
    target_entity_uuid: Optional[UUID] = None,
    context: Optional[dict] = None
) -> Optional[NumericalModifier]:
    """
    Contextual check for Fast Movement.

    Returns +10 ft speed if not wearing heavy armor.
    """
    _ = target_entity_uuid, context

    entity = Entity.get(source_entity_uuid)
    if not entity:
        return None

    # No bonus if wearing heavy armor
    body_armor = entity.equipment.body_armor
    if body_armor and body_armor.type == ArmorType.HEAVY:
        return None

    return NumericalModifier.create(
        source_entity_uuid=source_entity_uuid,
        name="Fast Movement",
        value=10
    )


class FastMovement(BaseCondition):
    """
    Barbarian Level 5: Fast Movement

    Your speed increases by 10 feet while you aren't wearing heavy armor.
    """
    name: str = "Fast Movement"
    description: str = "+10 ft speed when not in heavy armor"

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

        # Add contextual +10 speed (only when not in heavy armor)
        speed_mod = ContextualNumericalModifier(
            name="Fast Movement",
            source_entity_uuid=self.target_entity_uuid,
            target_entity_uuid=self.target_entity_uuid,
            callable=fast_movement_check
        )
        mod_uuid = target.action_economy.movement.self_contextual.add_value_modifier(speed_mod)
        outs.append((target.action_economy.movement.uuid, mod_uuid))

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Applied Fast Movement to {target.name}"
        )

        return outs, [], [], [], effect_event


# =============================================================================
# LEVEL 6: Mindless Rage (Berserker)
# =============================================================================

def mindless_rage_immunity_check(
    entity: 'BaseBlock',
    target_entity: Optional['BaseBlock'],
    context: Optional[dict]
) -> bool:
    """
    Contextual immunity check for Mindless Rage.

    Returns True (immune) only if the entity is currently raging.
    """
    _ = target_entity, context  # Suppress unused warnings

    # Only immune while raging
    if "Raging" in entity.active_conditions or "Frenzied" in entity.active_conditions:
        return True

    return False


class MindlessRage(BaseCondition):
    """
    Berserker Path Level 6: Mindless Rage

    You can't be charmed or frightened while raging.
    If you are charmed or frightened when you enter your rage,
    the effect is suspended for the duration of the rage.

    Implementation: Uses contextual condition immunity that checks if raging.
    """
    name: str = "Mindless Rage"
    description: str = "Cannot be charmed or frightened while raging"

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

        # Add contextual condition immunities for Charmed and Frightened
        # These only block conditions when raging
        target.add_condition_immunity(
            "Charmed",
            immunity_name="Mindless Rage",
            immunity_check=mindless_rage_immunity_check
        )
        target.add_condition_immunity(
            "Frightened",
            immunity_name="Mindless Rage",
            immunity_check=mindless_rage_immunity_check
        )

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Applied Mindless Rage to {target.name}"
        )

        return [], [], [], [], effect_event

    def _remove(self, event: Optional[Event] = None) -> Optional[Event]:
        """Clean up condition immunities on removal."""
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target:
            target._remove_contextual_condition_immunity("Charmed", "Mindless Rage")
            target._remove_contextual_condition_immunity("Frightened", "Mindless Rage")
        return super()._remove(event)


# =============================================================================
# LEVEL 7: Feral Instinct
# =============================================================================

class FeralInstinct(BaseCondition):
    """
    Barbarian Level 7: Feral Instinct

    You have advantage on initiative rolls.

    Additionally, if you are surprised at the beginning of combat and aren't
    incapacitated, you can act normally on your first turn, but only if you
    enter your rage before doing anything else on that turn.
    (Note: Surprise handling is not yet implemented)
    """
    name: str = "Feral Instinct"
    description: str = "Advantage on initiative rolls"

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

        # Add advantage on initiative
        # Initiative is typically a DEX check, but some systems track it separately
        # For now, we'll add it to the initiative ModifiableValue if it exists
        # Otherwise, DEX checks will have advantage
        init_adv = AdvantageModifier(
            name="Feral Instinct",
            value=AdvantageStatus.ADVANTAGE,
            source_entity_uuid=self.target_entity_uuid,
            target_entity_uuid=self.target_entity_uuid
        )

        # Add advantage on initiative rolls
        mod_uuid = target.initiative.self_static.add_advantage_modifier(init_adv)
        outs.append((target.initiative.uuid, mod_uuid))

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Applied Feral Instinct to {target.name}"
        )

        return outs, [], [], [], effect_event


# =============================================================================
# LEVEL 9/13/17: Brutal Critical
# =============================================================================

class BrutalCritical(BaseCondition):
    """
    Barbarian Level 9/13/17: Brutal Critical

    You can roll one additional weapon damage die when determining the
    extra damage for a critical hit with a melee attack.

    This increases to 2 at 13th level and 3 at 17th level.

    Per SRD: "critical hit with a melee attack" - only applies to melee weapons,
    so we add the modifier to crit_extra_dice_melee (not the general crit_extra_dice).
    """
    name: str = "Brutal Critical"
    description: str = "Extra damage dice on critical melee hits"
    extra_dice: int = 1  # 1 at L9, 2 at L13, 3 at L17

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

        # Add extra dice modifier to MELEE crit extra dice
        # This uses the crit_extra_dice_melee ModifiableValue which is checked
        # by Entity.get_crit_extra_dice() when rolling damage on crits
        brutal_mod = NumericalModifier.create(
            source_entity_uuid=self.target_entity_uuid,
            name="Brutal Critical",
            value=self.extra_dice
        )
        mod_uuid = target.equipment.crit_extra_dice_melee.self_static.add_value_modifier(brutal_mod)
        outs.append((target.equipment.crit_extra_dice_melee.uuid, mod_uuid))

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Applied Brutal Critical ({self.extra_dice} dice) to {target.name}"
        )

        return outs, [], [], [], effect_event


# =============================================================================
# LEVEL 11: Relentless Rage
# =============================================================================

def relentless_rage_processor(event: Event, source_entity_uuid: UUID) -> Optional[Event]:
    """
    Drop to 1 HP instead of 0 while raging (CON save).

    Triggers on TAKE_DAMAGE at EFFECT phase.
    DC starts at 10 and increases by 5 each time used.
    DC is calculated from resource: DC = 10 + (uses_consumed * 5)
    Resource resets on short rest, automatically resetting DC.
    """
    # Only when we take damage
    if event.target_entity_uuid != source_entity_uuid:
        return None

    entity = Entity.get(source_entity_uuid)
    if not entity:
        return None

    # Must be raging
    if "Raging" not in entity.active_conditions and "Frenzied" not in entity.active_conditions:
        return None

    # Only triggers when dropping to 0 or below
    if not isinstance(event, TakeDamageEvent):
        return None

    current_hp = entity.get_hp()
    damage = event.total_damage

    # Would this damage drop us to 0?
    if current_hp - damage > 0:
        return None  # Not dropping to 0, no trigger

    # Check resource availability
    resource = entity.action_economy.resources.get("relentless_rage")
    if not resource or resource.current <= 0:
        return None  # No uses left

    # Calculate DC from uses consumed: DC = 10 + (uses_consumed * 5)
    uses_consumed = resource.maximum - resource.current
    current_dc = 10 + (uses_consumed * 5)

    # Make CON save using proper dice roll
    # Use direct save bonus (no cross-entity propagation needed for self-save)
    con_save = entity.saving_throws.get_saving_throw("constitution")
    dice_roll = entity.roll_d20(con_save.bonus, RollType.SAVE, parent_event=event.uuid)
    total = dice_roll.total

    if total >= current_dc:
        # Success! Drop to 1 HP instead
        # Consume a use (increases DC for next time via calculation)
        entity.action_economy.consume_resource("relentless_rage", 1)

        # Modify damage to leave 1 HP
        # Use final_damage (not total_damage) so the modification takes effect
        new_damage = current_hp - 1
        return event.model_copy(update={
            "modified": True,
            "final_damage": max(0, new_damage),
            "status_message": f"Relentless Rage! (CON save {total} vs DC {current_dc}) - survives with 1 HP"
        })
    else:
        # Failed save - damage proceeds normally
        return event.model_copy(update={
            "status_message": f"Relentless Rage failed (CON save {total} vs DC {current_dc})"
        })


class RelentlessRage(BaseCondition):
    """
    Barbarian Level 11: Relentless Rage

    Your rage can keep you fighting despite grievous wounds.
    If you drop to 0 hit points while you're raging and don't die outright,
    you can make a DC 10 Constitution saving throw. If you succeed, you
    drop to 1 hit point instead.

    Each time you use this feature after the first, the DC increases by 5.
    The DC resets to 10 when you finish a short or long rest.

    Implementation: Uses a resource "relentless_rage" with SHORT_REST recharge.
    DC is calculated from uses consumed: DC = 10 + (uses_consumed * 5).
    This automatically resets DC on short rest when the resource recharges.
    """
    name: str = "Relentless Rage"
    description: str = "CON save to drop to 1 HP instead of 0 while raging"

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

        # Add resource for tracking uses (resets on short rest)
        # 5 uses max - after 5 uses, DC would be 30 which is effectively impossible
        target.action_economy.add_resource(
            name="relentless_rage",
            maximum=5,
            recharge_type=RechargeType.SHORT_REST
        )

        handler = EventHandler(
            name="Relentless Rage",
            source_entity_uuid=target.uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.TAKE_DAMAGE,
                    event_phase=EventPhase.EFFECT
                )
            ],
            event_processor=relentless_rage_processor
        )
        target.add_event_handler(handler)
        handler_uuids.append(handler.uuid)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Applied Relentless Rage to {target.name}"
        )

        return [], handler_uuids, [], [], effect_event

    def _remove(self, event: Optional[Event] = None) -> Optional[Event]:
        """Clean up resource on removal."""
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target:
            target.action_economy.remove_resource("relentless_rage")
        return super()._remove(event)


# =============================================================================
# LEVEL 15: Persistent Rage
# =============================================================================

class PersistentRage(BaseCondition):
    """
    Barbarian Level 15: Persistent Rage

    Your rage is so fierce that it ends early only if you fall unconscious
    or if you choose to end it.

    This is a marker condition checked by the rage maintenance handler.
    When present, rage doesn't end from lack of attacks/damage.
    """
    name: str = "PersistentRage"
    description: str = "Rage only ends if unconscious or chosen"

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]],
        List[UUID],
        List[UUID],
        List[UUID],
        Optional[Event]
    ]:
        # Pure marker condition - no modifiers or handlers
        # The rage maintenance handler checks for this condition

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message="Persistent Rage active"
        )

        return [], [], [], [], effect_event


# =============================================================================
# LEVEL 18: Indomitable Might
# =============================================================================

def indomitable_might_processor(event: Event, source_entity_uuid: UUID) -> Optional[Event]:
    """
    If STR check total is less than STR score, use STR score instead.

    Triggers on SKILL_CHECK at EFFECT phase.
    Only applies to STR-based skill checks (Athletics).
    """
    # Only our own skill checks
    if event.source_entity_uuid != source_entity_uuid:
        return None

    if not isinstance(event, SkillCheckEvent):
        return None

    # Only Athletics (the only STR-based skill)
    if event.skill_name != "athletics":
        return None

    entity = Entity.get(source_entity_uuid)
    if not entity:
        return None

    str_score = entity.ability_scores.strength.ability_score.score

    # Get the total from the dice roll
    if not event.dice_roll:
        return None

    total = event.dice_roll.total

    if total < str_score:
        # Replace the total with STR score
        new_dice_roll = event.dice_roll.model_copy(update={"total": str_score})
        return event.model_copy(update={
            "dice_roll": new_dice_roll,
            "modified": True,
            "status_message": f"Indomitable Might: using STR score {str_score} instead of {total}"
        })

    return None


def create_indomitable_might_handler(source_entity_uuid: UUID) -> EventHandler:
    """Create handler for Indomitable Might."""
    return EventHandler(
        name="Indomitable Might",
        source_entity_uuid=source_entity_uuid,
        trigger_conditions=[
            Trigger(
                event_type=EventType.SKILL_CHECK,
                event_phase=EventPhase.EFFECT
            )
        ],
        event_processor=indomitable_might_processor
    )


class IndomitableMight(BaseCondition):
    """
    Barbarian Level 18: Indomitable Might

    If your total for a Strength check is less than your Strength score,
    you can use that score in place of the total.
    """
    name: str = "Indomitable Might"
    description: str = "STR checks can't be lower than STR score"

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

        # Register handler to modify STR checks
        handler = create_indomitable_might_handler(target.uuid)
        target.add_event_handler(handler)
        handler_uuids.append(handler.uuid)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Applied Indomitable Might to {target.name}"
        )

        return [], handler_uuids, [], [], effect_event


# =============================================================================
# LEVEL 20: Primal Champion
# =============================================================================

class PrimalChampion(BaseCondition):
    """
    Barbarian Level 20: Primal Champion

    Your Strength and Constitution scores increase by 4.
    Your maximum for those scores is now 24.

    Note: The engine doesn't enforce a 20 max on ability scores,
    so we just add the +4 modifiers.
    """
    name: str = "Primal Champion"
    description: str = "+4 STR and CON (max 24)"

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

        # +4 to STR ability_score
        str_mod = NumericalModifier.create(
            source_entity_uuid=self.target_entity_uuid,
            name="Primal Champion (STR)",
            value=4
        )
        mod_uuid = target.ability_scores.strength.ability_score.self_static.add_value_modifier(str_mod)
        outs.append((target.ability_scores.strength.ability_score.uuid, mod_uuid))

        # +4 to CON ability_score
        con_mod = NumericalModifier.create(
            source_entity_uuid=self.target_entity_uuid,
            name="Primal Champion (CON)",
            value=4
        )
        mod_uuid = target.ability_scores.constitution.ability_score.self_static.add_value_modifier(con_mod)
        outs.append((target.ability_scores.constitution.ability_score.uuid, mod_uuid))

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Applied Primal Champion to {target.name}: +4 STR, +4 CON"
        )

        return outs, [], [], [], effect_event


# =============================================================================
# LEVEL 14 (BERSERKER): Retaliation
# =============================================================================

def retaliation_processor(event: Event, source_entity_uuid: UUID) -> Optional[Event]:
    """
    When taking damage from a creature within 5ft, make a reaction melee attack.

    Triggers on TAKE_DAMAGE at EFFECT phase (when damage is being applied).
    Note: COMPLETION phase handlers are skipped by EventQueue, so we use EFFECT.
    """
    # Only when WE take damage
    if event.target_entity_uuid != source_entity_uuid:
        return None

    # Must have a source (the attacker)
    if not event.source_entity_uuid:
        return None

    entity = Entity.get(source_entity_uuid)
    if not entity:
        return None

    attacker = Entity.get(event.source_entity_uuid)
    if not attacker:
        return None

    # Check attacker within 5ft
    distance = entity.senses.get_feet_distance(attacker.senses.position)
    if distance > 5:
        return None

    # Check reaction available
    if not entity.action_economy.can_afford("reactions", 1):
        return None

    # Check we have a melee weapon
    weapon = entity.equipment._get_weapon_by_slot(WeaponSlot.MELEE_MAIN)
    if weapon is None:
        return None

    # Make melee attack as reaction
    attack = Attack(
        source_entity_uuid=source_entity_uuid,
        target_entity_uuid=event.source_entity_uuid,
        weapon_slot=WeaponSlot.MELEE_MAIN,
        parent_event=event  # Link to triggering damage event
    )
    attack.apply(parent_event=event)

    # Consume reaction
    entity.action_economy.consume("reactions", 1)

    return None  # Don't modify the damage event


def create_retaliation_handler(source_entity_uuid: UUID) -> EventHandler:
    """Create handler for Retaliation."""
    return EventHandler(
        name="Retaliation",
        source_entity_uuid=source_entity_uuid,
        trigger_conditions=[
            Trigger(
                event_type=EventType.TAKE_DAMAGE,
                event_phase=EventPhase.EFFECT
            )
        ],
        event_processor=retaliation_processor,
        player_toggleable=True
    )


class Retaliation(BaseCondition):
    """
    Berserker Path Level 14: Retaliation

    When you take damage from a creature that is within 5 feet of you,
    you can use your reaction to make a melee weapon attack against
    that creature.
    """
    name: str = "Retaliation"
    description: str = "Reaction melee attack when hit by adjacent creature"

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

        # Register handler to react to damage
        handler = create_retaliation_handler(target.uuid)
        target.add_event_handler(handler)
        handler_uuids.append(handler.uuid)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Applied Retaliation to {target.name}"
        )

        return [], handler_uuids, [], [], effect_event


# =============================================================================
# LEVEL 10 (BERSERKER): Intimidating Presence
# =============================================================================

class IntimidatingPresenceImmunity(BaseCondition):
    """
    Marker condition: Target is immune to a specific creature's Intimidating Presence.

    Applied when a creature succeeds on the WIS save against Intimidating Presence.
    The source_entity_uuid is the barbarian whose Intimidating Presence was resisted.

    Duration: 24 hours (in practice, until long rest or end of encounter).
    This condition has no modifiers - it's purely a marker for immunity checking.
    """
    name: str = "Intimidating Presence Immunity"
    description: str = "Immune to a specific creature's Intimidating Presence"

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]],  # (modifiable_value_uuid, modifier_uuid) pairs
        List[UUID],               # event_handler_uuids
        List[UUID],               # subcondition_uuids
        List[UUID],               # spatial_handler_uuids
        Optional[Event]           # completion event
    ]:
        # Pure marker condition - no modifiers or handlers
        # The source_entity_uuid identifies which barbarian's Intimidating Presence
        # this creature is immune to

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message="Intimidating Presence immunity applied"
        )

        return [], [], [], [], effect_event


def intimidating_presence_end_check_processor(
    event: Event, source_entity_uuid: UUID, barbarian_uuid: UUID
) -> Optional[Event]:
    """
    Check if Frightened from Intimidating Presence should end at turn end.

    SRD: "This effect ends if the creature ends its turn out of line of sight
    or more than 60 feet away from you."

    Triggers on TURN_END at EXECUTION phase for the frightened creature.
    """
    # Only when the frightened creature ends their turn
    if event.source_entity_uuid != source_entity_uuid:
        return None

    creature = Entity.get(source_entity_uuid)
    barbarian = Entity.get(barbarian_uuid)

    if not creature or not barbarian:
        return None

    # Check if creature is still frightened by this barbarian
    frightened = creature.active_conditions.get("Frightened")
    if not frightened or frightened.source_entity_uuid != barbarian_uuid:
        return None  # No longer frightened by this barbarian

    # Check distance > 60ft
    distance = creature.senses.get_feet_distance(barbarian.senses.position)
    should_end = distance > 60

    # Check line of sight (barbarian not in creature's visible entities)
    if not should_end and barbarian_uuid not in creature.senses.entities:
        should_end = True

    if should_end:
        # Remove Frightened condition
        creature.remove_condition("Frightened", parent_event=event)
        reason = "out of range" if distance > 60 else "out of line of sight"
        return event.model_copy(update={
            "modified": True,
            "status_message": f"{creature.name} is no longer frightened ({reason} from {barbarian.name})"
        })

    return None


def create_intimidating_presence_end_handler(
    source_entity_uuid: UUID, barbarian_uuid: UUID
) -> EventHandler:
    """
    Create handler that checks if Frightened from Intimidating Presence should end.

    Uses functools.partial to bind the barbarian_uuid to the processor.
    """
    bound_processor = partial(
        intimidating_presence_end_check_processor,
        barbarian_uuid=barbarian_uuid
    )

    return EventHandler(
        name="Intimidating Presence End Check",
        source_entity_uuid=source_entity_uuid,
        trigger_conditions=[
            Trigger(
                event_type=EventType.TURN_END,
                event_phase=EventPhase.EXECUTION
            )
        ],
        event_processor=bound_processor
    )


class IntimidatingPresence(BaseAction):
    """
    Berserker Path Level 10: Intimidating Presence Action

    Use your action to frighten one creature you can see within 30 feet.
    Target makes a WIS save (DC = 8 + prof + CHA mod) or is Frightened
    until end of your next turn.

    A creature that succeeds is immune for 24 hours (tracked via condition).

    SRD: "This effect ends if the creature ends its turn out of line of sight
    or more than 60 feet away from you."
    """
    name: str = "Intimidating Presence"
    description: str = "Frighten a creature within 30ft (WIS save)"
    target_type: TargetType = TargetType.ENTITY

    costs: List[Cost] = []

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        self.costs = [
            Cost(
                name="Intimidating Presence",
                cost_type="actions",
                cost=1,
                evaluator=entity_action_economy_cost_evaluator
            )
        ]

    def _create_declaration_event(self, parent_event: Optional[Event] = None, use_register: bool = True) -> Optional[ActionEvent]:
        entity = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        source_name = entity.name if entity else None
        target_name = target.name if target else None

        return ActionEvent(
            name=self.name,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid,
            costs=[BaseCost.model_validate(c) for c in self.costs],
            parent_event=parent_event.uuid if parent_event else None,
            use_register=use_register,
            source_entity_name=source_name,
            target_entity_name=target_name
        )

    def pre_validate(self) -> bool:
        """Check if intimidating presence can be used."""
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return False

        # Must have action available
        if not entity.action_economy.can_afford("actions", 1):
            return False

        return True

    def _is_target_immune(self, target: Entity) -> bool:
        """Check if target has immunity to this barbarian's Intimidating Presence."""
        # Look for IntimidatingPresenceImmunity condition where source is this barbarian
        for condition in target.active_conditions.values():
            if (condition.name == "Intimidating Presence Immunity" and
                    condition.source_entity_uuid == self.source_entity_uuid):
                return True
        return False

    def _validate(self, declaration_event: ActionEvent) -> Optional[ActionEvent]:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return declaration_event.cancel(status_message="Entity not found")

        if not self.target_entity_uuid:
            return declaration_event.cancel(status_message="No target specified")

        target = Entity.get(self.target_entity_uuid)
        if not target:
            return declaration_event.cancel(status_message="Target not found")

        # Check target within 30ft
        distance = entity.senses.get_feet_distance(target.senses.position)
        if distance > 30:
            return declaration_event.cancel(status_message="Target beyond 30ft")

        # Check target visible
        if self.target_entity_uuid not in entity.senses.entities:
            return declaration_event.cancel(status_message="Target not visible")

        # Check target not immune (has IntimidatingPresenceImmunity from this barbarian)
        if self._is_target_immune(target):
            return declaration_event.cancel(status_message="Target is immune (saved within 24h)")

        return declaration_event.phase_to(EventPhase.EXECUTION)

    def _apply(self, execution_event: ActionEvent) -> Optional[ActionEvent]:
        entity = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not entity or not target or not self.target_entity_uuid:
            return execution_event.cancel(status_message="Entity or target not found")

        # Calculate DC = 8 + proficiency + CHA mod
        proficiency = entity.proficiency_bonus.normalized_score
        cha_mod = entity.ability_scores.charisma.modifier
        dc = 8 + proficiency + cha_mod

        # Target makes WIS save using the full event system
        # This allows event handlers like Indomitable to intercept
        request = entity.create_saving_throw_request(
            target_entity_uuid=self.target_entity_uuid,
            ability_name="wisdom",
            dc=dc
        )
        _, dice_roll, success = target.saving_throw(request)

        if success:
            # Success - apply immunity condition to target
            # Source is this barbarian, target is the creature who saved
            immunity = IntimidatingPresenceImmunity(
                source_entity_uuid=self.source_entity_uuid,
                target_entity_uuid=self.target_entity_uuid
            )
            target.add_condition(immunity, parent_event=execution_event)

            return execution_event.phase_to(
                EventPhase.COMPLETION,
                status_message=f"{target.name} resists Intimidating Presence (WIS save {dice_roll.total} vs DC {dc})"
            )
        else:
            # Failure - apply Frightened condition
            # Duration: until end of your next turn (approximately 1 round)
            frightened = Frightened(
                source_entity_uuid=self.source_entity_uuid,  # Barbarian is the frightener
                target_entity_uuid=self.target_entity_uuid
            )
            # Set duration to 1 round
            frightened.duration.duration_type = DurationType.ROUNDS
            frightened.duration.duration = 1

            target.add_condition(frightened, parent_event=execution_event)

            # Register handler to end Frightened if target moves >60ft or breaks LOS (SRD)
            # Handler checks at target's TURN_END if they should no longer be frightened
            end_handler = create_intimidating_presence_end_handler(
                source_entity_uuid=self.target_entity_uuid,  # Handler triggers on target's turn
                barbarian_uuid=self.source_entity_uuid  # To check distance/LOS against
            )
            target.add_event_handler(end_handler)
            # Track handler UUID in frightened condition for cleanup
            frightened.event_handlers_uuids.append(end_handler.uuid)

            return execution_event.phase_to(
                EventPhase.COMPLETION,
                status_message=f"{target.name} is frightened by {entity.name}! (WIS save {dice_roll.total} vs DC {dc})"
            )

    def _apply_costs(self, completion_event: ActionEvent) -> ActionEvent:
        return entity_action_economy_cost_applier(completion_event, self.source_entity_uuid)


class ExtendIntimidatingPresence(BaseAction):
    """
    Extend Intimidating Presence duration.

    SRD: "On subsequent turns, you can use your action to extend the duration
    of this effect on the frightened creature until the end of your next turn."

    Costs 1 action.
    Target must be within 30ft, visible, and Frightened by THIS barbarian.
    """
    name: str = "Extend Intimidating Presence"
    description: str = "Extend the Frightened effect on a creature"
    target_type: TargetType = TargetType.ENTITY

    costs: List[Cost] = []

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        self.costs = [
            Cost(
                name="Extend Intimidating Presence",
                cost_type="actions",
                cost=1,
                evaluator=entity_action_economy_cost_evaluator
            )
        ]

    def _create_declaration_event(self, parent_event: Optional[Event] = None, use_register: bool = True) -> Optional[ActionEvent]:
        entity = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        source_name = entity.name if entity else None
        target_name = target.name if target else None

        return ActionEvent(
            name=self.name,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid,
            costs=[BaseCost.model_validate(c) for c in self.costs],
            parent_event=parent_event.uuid if parent_event else None,
            use_register=use_register,
            source_entity_name=source_name,
            target_entity_name=target_name
        )

    def pre_validate(self) -> bool:
        """Check if extend intimidating presence can be used."""
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return False

        # Must have action available
        if not entity.action_economy.can_afford("actions", 1):
            return False

        return True

    def _is_frightened_by_me(self, target: Entity) -> bool:
        """Check if target is Frightened by this barbarian."""
        frightened = target.active_conditions.get("Frightened")
        if not frightened:
            return False
        # Check source is this barbarian
        return frightened.source_entity_uuid == self.source_entity_uuid

    def _validate(self, declaration_event: ActionEvent) -> Optional[ActionEvent]:
        entity = Entity.get(self.source_entity_uuid)
        if not entity:
            return declaration_event.cancel(status_message="Entity not found")

        if not self.target_entity_uuid:
            return declaration_event.cancel(status_message="No target specified")

        target = Entity.get(self.target_entity_uuid)
        if not target:
            return declaration_event.cancel(status_message="Target not found")

        # Check target within 30ft (same range as initial use)
        distance = entity.senses.get_feet_distance(target.senses.position)
        if distance > 30:
            return declaration_event.cancel(status_message="Target beyond 30ft")

        # Check target visible
        if self.target_entity_uuid not in entity.senses.entities:
            return declaration_event.cancel(status_message="Target not visible")

        # Check target is Frightened by THIS barbarian
        if not self._is_frightened_by_me(target):
            return declaration_event.cancel(status_message="Target not frightened by you")

        return declaration_event.phase_to(EventPhase.EXECUTION)

    def _apply(self, execution_event: ActionEvent) -> Optional[ActionEvent]:
        entity = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not entity or not target:
            return execution_event.cancel(status_message="Entity or target not found")

        # Get the Frightened condition and reset its duration
        frightened = target.active_conditions.get("Frightened")
        if frightened and frightened.source_entity_uuid == self.source_entity_uuid:
            # Reset duration to 1 round (until end of your next turn)
            frightened.duration.duration = 1

        return execution_event.phase_to(
            EventPhase.COMPLETION,
            status_message=f"{entity.name} extends Intimidating Presence on {target.name}"
        )

    def _apply_costs(self, completion_event: ActionEvent) -> ActionEvent:
        return entity_action_economy_cost_applier(completion_event, self.source_entity_uuid)


class IntimidatingPresenceFeature(BaseCondition):
    """
    Berserker Path Level 10: Intimidating Presence Feature

    Grants the Intimidating Presence action and Extend Intimidating Presence action.
    """
    name: str = "Intimidating Presence Feature"
    description: str = "Can use action to frighten creatures within 30ft"

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

        # Register Intimidating Presence action template
        intimidate_action = IntimidatingPresence(
            source_entity_uuid=target.uuid,
            template=True
        )
        target.register_action(intimidate_action)

        # Register Extend Intimidating Presence action template (SRD)
        extend_action = ExtendIntimidatingPresence(
            source_entity_uuid=target.uuid,
            template=True
        )
        target.register_action(extend_action)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Granted Intimidating Presence to {target.name}"
        )

        return [], [], [], [], effect_event

    def _remove(self, event: Optional[Event] = None) -> Optional[Event]:
        """Clean up actions on removal."""
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target:
            target.unregister_action("Intimidating Presence")
            target.unregister_action("Extend Intimidating Presence")

        return super()._remove(event)
