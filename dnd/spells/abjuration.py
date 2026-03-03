"""Abjuration spells - protection and defense.

Contains: Shield, MageArmor, ProtectionFromEnergy, Stoneskin, Counterspell,
          LesserRestoration, GreaterRestoration,
          ProtectionFromPoison, DeathWard, FreedomOfMovement,
          Resistance, ShieldOfFaith, Aid, Sanctuary, BeaconOfHope,
          AntimagicField
"""
import random
from typing import Dict, Optional, List, Set, Tuple, cast as type_cast
from uuid import UUID

from pydantic import Field

from dnd.core.base_actions import TargetType, spell_slot_cost_type, Cost
from dnd.core.base_conditions import BaseCondition, ConditionCategory, ConditionApplicationEvent, ConditionTag, SpellProtectionRegistry, SpellProtection, DurationType
from dnd.core.base_object import BaseObject
from dnd.core.events import Event, EventPhase, EventType, EventHandler, BaseHandler, Trigger, RangeType, Range, EventQueue, SpatialChangeEvent, TakeDamageEvent, D20RollResultEvent, HealRollResultEvent
from dnd.core.modifiers import DamageType, ResistanceModifier, ResistanceStatus, NumericalModifier, AutoHitStatus, AdvantageModifier, AdvantageStatus
from dnd.core.aoe import Sphere
from dnd.core.gridmap import get_map
from dnd.blocks.equipment import UnarmoredAc, ArmorEquipEvent

from dnd.core.dice import AttackOutcome, Dice
from dnd.entity import Entity
from dnd.actions import SpellAction, SpellEvent, AttackEvent, entity_action_economy_cost_evaluator
from dnd.conditions import Incapacitated
from dnd.spells.spell_utils import validate_line_of_sight
from dnd.spells.transmutation import HasteEffect


def _is_magic_missile_damage(event: Event) -> bool:
    """Check if a TakeDamageEvent originates from Magic Missile by tracing parent events."""
    parent_uuid = event.parent_event
    while parent_uuid is not None:
        parent = EventQueue.get_event_by_uuid(parent_uuid)
        if parent is None:
            break
        if isinstance(parent, SpellEvent) and parent.name == "Magic Missile":
            return True
        parent_uuid = parent.parent_event
    return False


# =============================================================================
# SHIELD SPELL (1st-level Abjuration, Reaction)
# =============================================================================

class ShieldBuff(BaseCondition):
    """Shield spell AC buff. +5 AC until start of caster's next turn.

    Applied by the Shield reaction handler when an attack targets the entity.
    Removed at turn start via a turn-start handler.
    """
    name: str = "Shield"
    description: str = "+5 AC until start of your next turn"
    condition_category: ConditionCategory = ConditionCategory.STATUS
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL})

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        if not self.target_entity_uuid:
            return [], [], [], [], declaration_event.cancel(status_message="Target entity UUID not set")

        target = Entity.get(self.target_entity_uuid)
        if not target or not isinstance(target, Entity):
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        target_uuid = self.target_entity_uuid
        outs: List[Tuple[UUID, UUID]] = []
        handler_uuids: List[UUID] = []

        # Add +5 AC modifier
        mod = NumericalModifier.create(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=target_uuid,
            name="Shield",
            value=5
        )
        mod_uuid = target.equipment.ac_bonus.self_static.add_value_modifier(mod)
        outs.append((target.equipment.ac_bonus.uuid, mod_uuid))

        # Magic Missile immunity handler (5e SRD: "you take no damage from magic missile")
        def shield_magic_missile_blocker(event: Event, handler_source_uuid: UUID) -> Optional[Event]:
            """Block Magic Missile damage while Shield is active."""
            _ = handler_source_uuid
            if event.target_entity_uuid != target_uuid:
                return None
            if not _is_magic_missile_damage(event):
                return None
            return event.cancel(status_message=f"Shield blocks Magic Missile dart")

        mm_handler = EventHandler(
            name="Shield: Magic Missile Block",
            source_entity_uuid=target_uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.TAKE_DAMAGE,
                    event_phase=EventPhase.EFFECT,
                    event_target_entity_uuid=target_uuid
                )
            ],
            event_processor=shield_magic_missile_blocker
        )
        target.add_event_handler(mm_handler)
        handler_uuids.append(mm_handler.uuid)

        # Turn-start handler to remove this condition
        def shield_turn_start_processor(event: Event, handler_source_uuid: UUID) -> Optional[Event]:
            """Remove Shield buff at the start of the caster's turn."""
            _ = handler_source_uuid
            if event.source_entity_uuid != target_uuid:
                return None
            entity = Entity.get(target_uuid)
            if entity and "Shield" in entity.active_conditions:
                entity.remove_condition("Shield", parent_event=event)
            return None

        handler = EventHandler(
            name="Shield: Turn Start Removal",
            source_entity_uuid=target_uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.TURN_START,
                    event_phase=EventPhase.EXECUTION,
                    event_source_entity_uuid=target_uuid
                )
            ],
            event_processor=shield_turn_start_processor
        )
        target.add_event_handler(handler)
        handler_uuids.append(handler.uuid)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Shield: +5 AC to {target.name}"
        )
        return outs, handler_uuids, [], [], effect_event


def shield_reaction_processor(event: Event, source_entity_uuid: UUID) -> Optional[Event]:
    """Shield reaction: when attacked or hit by Magic Missile, spend reaction + spell slot.

    Two trigger paths:
    - ATTACK @ EXECUTION: Adds +5 AC before roll/comparison, applies ShieldBuff.
    - TAKE_DAMAGE @ DECLARATION: Blocks Magic Missile darts, applies ShieldBuff.
    """
    # Only react to events targeting this entity
    if event.target_entity_uuid != source_entity_uuid:
        return None

    entity = Entity.get(source_entity_uuid)
    if not entity or not isinstance(entity, Entity):
        return None

    # Already have Shield buff active — skip
    if "Shield" in entity.active_conditions:
        return None

    # Need reaction
    if not entity.action_economy.can_afford("reactions", 1):
        return None

    # Need a spell slot (level 1+)
    slot_level = entity.get_lowest_spell_slot(1)
    if slot_level is None:
        return None

    # Branch 1: Attack event — 5e: react after seeing the roll, only if +5 helps
    if isinstance(event, AttackEvent) and event.ac:
        # Wait until the d20 roll and outcome are determined (fires twice at EXECUTION:
        # once before roll with ac set, once after roll via post() with dice_roll set)
        if event.dice_roll is None or event.attack_outcome is None:
            return None  # Roll not made yet — wait

        # Only react to normal hits (not crits, not auto-hits — can't Shield those)
        if event.attack_outcome != AttackOutcome.HIT:
            return None

        # Auto-hit bypasses AC entirely — Shield can't help
        if event.dice_roll.auto_hit_status == AutoHitStatus.AUTOHIT:
            return None

        # Only use Shield if +5 would actually turn the hit into a miss
        current_ac = event.ac.normalized_score
        if event.dice_roll.total >= current_ac + 5:
            return None  # Even with +5 AC, attack still hits — save the slot

        # Shield would help — apply it

        # 1. Add +5 AC to the event and change outcome to MISS
        event.ac.self_static.add_value_modifier(
            NumericalModifier.create(
                source_entity_uuid=source_entity_uuid,
                target_entity_uuid=source_entity_uuid,
                name="Shield (reaction)",
                value=5
            )
        )

        # 2. Consume reaction + spell slot
        entity.action_economy.consume("reactions", 1)
        entity.action_economy.consume(spell_slot_cost_type(slot_level), 1)

        # 3. Apply ShieldBuff condition for subsequent attacks until turn start
        buff = ShieldBuff(
            source_entity_uuid=source_entity_uuid,
            target_entity_uuid=source_entity_uuid
        )
        entity.add_condition(buff, parent_event=event)

        return event.model_copy(update={
            "modified": True,
            "attack_outcome": AttackOutcome.MISS,
            "status_message": f"{entity.name} casts Shield (+5 AC, attack blocked)"
        })

    # Branch 2: Magic Missile damage — block all darts (5e SRD)
    if _is_magic_missile_damage(event):
        # 1. Consume reaction + spell slot
        entity.action_economy.consume("reactions", 1)
        entity.action_economy.consume(spell_slot_cost_type(slot_level), 1)

        # 2. Apply ShieldBuff (includes MM blocker handler for subsequent darts)
        buff = ShieldBuff(
            source_entity_uuid=source_entity_uuid,
            target_entity_uuid=source_entity_uuid
        )
        entity.add_condition(buff, parent_event=event)

        # 3. Cancel THIS dart's damage directly (ShieldBuff's handler catches the rest)
        return event.cancel(status_message=f"{entity.name} casts Shield, blocking Magic Missile")

    return None


def create_shield_reaction_handler(source_entity_uuid: UUID) -> EventHandler:
    """Create a Shield reaction handler for an entity.

    Two triggers:
    - ATTACK @ EXECUTION: React to weapon/spell attacks (+5 AC)
    - TAKE_DAMAGE @ DECLARATION: React to Magic Missile (block all darts)
    """
    return EventHandler(
        name="Shield",
        source_entity_uuid=source_entity_uuid,
        trigger_conditions=[
            Trigger(
                event_type=EventType.ATTACK,
                event_phase=EventPhase.EXECUTION,
                event_target_entity_uuid=source_entity_uuid
            ),
            Trigger(
                event_type=EventType.TAKE_DAMAGE,
                event_phase=EventPhase.EFFECT,
                event_target_entity_uuid=source_entity_uuid
            )
        ],
        event_processor=shield_reaction_processor,
        player_toggleable=True
    )


def register_shield_reaction(entity: Entity) -> None:
    """Register the Shield reaction handler on an entity.

    The entity must be a spellcaster with spell slots.
    The handler can be toggled via entity.set_handler_enabled("Shield", enabled).
    """
    handler = create_shield_reaction_handler(entity.uuid)
    entity.add_event_handler(handler)


# =============================================================================
# MAGE ARMOR CONDITION
# =============================================================================

class MageArmorCondition(BaseCondition):
    """
    Mage Armor spell effect.

    Sets AC to 13 + DEX mod when unarmored (using UnarmoredAc.MAGIC_ARMOR).
    Ends if the target equips armor.

    Duration: 8 hours (but concentration-free, so just a long duration in rounds
    would be ~4800 rounds in 6-second increments - we use PERMANENT for simplicity
    and the armor equip handler ends it).
    """
    name: str = "Mage Armor"
    description: str = "AC equals 13 + DEX modifier when unarmored"
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL})

    # Track the old unarmored type to restore on removal
    _old_unarmored_type: Optional[str] = None  # Store as string for Pydantic serialization

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:

        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")

        target_entity = Entity.get(self.target_entity_uuid)
        if not target_entity:
            return [], [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} not found")

        if not isinstance(target_entity, Entity):
            return [], [], [], [], declaration_event.cancel(status_message=f"Target is not an Entity")

        # Check if target is wearing armor - Mage Armor doesn't work on armored targets
        if not target_entity.equipment.is_unarmored():
            return [], [], [], [], declaration_event.cancel(status_message="Target is wearing armor - Mage Armor has no effect")

        outs: List[Tuple[UUID, UUID]] = []
        handler_uuids: List[UUID] = []

        # Store old unarmored type and set to MAGIC_ARMOR
        self._old_unarmored_type = target_entity.equipment.unarmored_ac_type.value
        target_entity.equipment.unarmored_ac_type = UnarmoredAc.MAGIC_ARMOR

        # Create armor equip handler that ends the condition when armor is equipped
        # Capture target_entity_uuid in closure to avoid None issues
        condition_target_uuid = self.target_entity_uuid

        def mage_armor_equip_processor(event: Event, handler_source_uuid: UUID) -> Optional[Event]:
            """End Mage Armor if any armor is equipped."""
            _ = handler_source_uuid  # Unused but required by signature

            # Only care about the target's equipment changes
            if event.source_entity_uuid != condition_target_uuid:
                return None

            entity = Entity.get(condition_target_uuid)
            if not entity:
                return None

            # Must have Mage Armor
            if "Mage Armor" not in entity.active_conditions:
                return None

            # Check if armor was equipped (not a shield)
            if isinstance(event, ArmorEquipEvent):
                # Remove Mage Armor
                entity.remove_condition("Mage Armor", parent_event=event)
                return event.model_copy(update={
                    "modified": True,
                    "status_message": f"{entity.name}'s Mage Armor ends (equipped armor)"
                })

            return None

        # Create the handler
        handler = EventHandler(
            name="Mage Armor Watch",
            source_entity_uuid=self.target_entity_uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.ARMOR_EQUIP,
                    event_phase=EventPhase.EXECUTION
                )
            ],
            event_processor=mage_armor_equip_processor
        )

        # Register handler with entity (auto-registers with EventQueue)
        target_entity.add_event_handler(handler)
        handler_uuids.append(handler.uuid)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            update={"condition": self},
            status_message=f"Applied Mage Armor to {target_entity.name} (AC = 13 + DEX)"
        )

        return outs, handler_uuids, [], [], effect_event

    def _remove(self, _removal_event: Optional[Event] = None) -> None:
        """Restore the old unarmored AC type on removal."""

        if not self.target_entity_uuid:
            return

        target_entity = Entity.get(self.target_entity_uuid)
        if not target_entity or not isinstance(target_entity, Entity):
            return

        # Restore old unarmored type
        if self._old_unarmored_type:
            try:
                target_entity.equipment.unarmored_ac_type = UnarmoredAc(self._old_unarmored_type)
            except ValueError:
                target_entity.equipment.unarmored_ac_type = UnarmoredAc.NONE
        else:
            target_entity.equipment.unarmored_ac_type = UnarmoredAc.NONE


# =============================================================================
# MAGE ARMOR SPELL
# =============================================================================

class MageArmor(SpellAction):
    """Mage Armor - 1st level Abjuration

    You touch a willing creature who isn't wearing armor, and a protective magical
    force surrounds it until the spell ends. The target's base AC becomes 13 + DEX modifier.
    The spell ends if the target dons armor or if you dismiss the spell as an action.
    """
    name: str = Field(default="Mage Armor")
    description: str = Field(default="Target's AC becomes 13 + DEX modifier")
    spell_level: int = Field(default=1)
    spell_school: str = Field(default="abjuration")
    target_type: TargetType = Field(default=TargetType.ENTITY)  # Can target willing creature
    include_self: bool = Field(default=True)  # Buff spell - can target self
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.REACH, normal=5)  # Touch = 5ft reach
    )

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate target is unarmored and in range."""

        source_entity = Entity.get(self.source_entity_uuid)
        target_entity = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not source_entity:
            return declaration_event.cancel(status_message="Caster not found")

        # Can self-target
        if target_entity is None:
            target_entity = source_entity
            self.target_entity_uuid = source_entity.uuid

        # Validate range (touch = 5ft, or self)
        if target_entity.uuid != source_entity.uuid:
            distance = source_entity.senses.get_feet_distance(target_entity.position)
            if distance > self.effective_range:
                return declaration_event.cancel(status_message=f"Target out of range ({distance}ft > {self.effective_range}ft)")

        # Check if target is wearing armor
        if not target_entity.equipment.is_unarmored():
            return declaration_event.cancel(status_message="Target is wearing armor")

        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated {self.name}"
        )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Apply Mage Armor condition to target."""
        # MageArmorCondition is defined in this file

        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else caster

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        # Create and apply the condition
        condition = MageArmorCondition(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid
        )

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"Applying Mage Armor to {target.name}"
        )

        # Apply condition
        result = target.add_condition(condition, parent_event=effect_event)
        if result is None or result.canceled:
            return effect_event.cancel(status_message="Failed to apply Mage Armor")

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"{self.name} cast on {target.name} (AC = 13 + DEX)"
        )


# =============================================================================
# PROTECTION FROM ENERGY
# =============================================================================

class ProtectionFromEnergyEffect(BaseCondition):
    """
    Grants resistance to one energy type.

    This condition is applied to the target of Protection from Energy.
    When concentration breaks, this condition is automatically removed
    via the Concentrating condition's linked_conditions mechanism.
    """
    name: str = "Protection from Energy"
    description: str = "Resistant to one energy type"
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL})

    # The chosen energy type (set by spell)
    energy_type: DamageType = DamageType.FIRE

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:

        if not self.target_entity_uuid:
            return [], [], [], [], declaration_event.cancel(status_message="Target entity UUID not set")

        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        outs: List[Tuple[UUID, UUID]] = []

        # Add resistance modifier for the chosen energy type
        resist_mod = ResistanceModifier(
            name=f"Protection from Energy ({self.energy_type.value})",
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=target.uuid,
            value=ResistanceStatus.RESISTANCE,
            damage_type=self.energy_type
        )
        mod_uuid = target.health.damage_reduction.self_static.add_resistance_modifier(resist_mod)
        outs.append((target.health.damage_reduction.uuid, mod_uuid))

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Applied {self.energy_type.value} resistance to {target.name}"
        )

        return outs, [], [], [], effect_event


class ProtectionFromEnergy(SpellAction):
    """Protection from Energy - 3rd level Abjuration (Concentration)

    For the duration, the willing creature you touch has resistance to one
    damage type of your choice: acid, cold, fire, lightning, or thunder.

    Duration: Concentration, up to 1 hour
    """
    name: str = Field(default="Protection from Energy")
    description: str = Field(default="Grant resistance to one energy type (acid/cold/fire/lightning/thunder)")
    spell_level: int = Field(default=3)
    spell_school: str = Field(default="abjuration")
    concentration: bool = Field(default=True)
    target_type: TargetType = Field(default=TargetType.ENTITY)
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.REACH, normal=5))  # Touch

    # Target filtering - can target self or allies
    include_self: bool = Field(default=True)
    valid_target_filter: str = Field(default="self_or_allies")

    # User-selected energy type
    chosen_energy_type: DamageType = Field(default=DamageType.FIRE)

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate target and range."""

        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else caster

        if not caster:
            return declaration_event.cancel(status_message="Caster not found")

        # Default to self if no target
        if not target:
            target = caster
            self.target_entity_uuid = caster.uuid

        # Validate range (touch = 5ft, or self)
        if target.uuid != caster.uuid:
            distance = caster.senses.get_feet_distance(target.position)
            if distance > self.effective_range:
                return declaration_event.cancel(
                    status_message=f"Target out of range ({distance}ft > {self.effective_range}ft)"
                )

        # Validate energy type is one of the allowed types
        allowed_types = [DamageType.ACID, DamageType.COLD, DamageType.FIRE, DamageType.LIGHTNING, DamageType.THUNDER]
        if self.chosen_energy_type not in allowed_types:
            return declaration_event.cancel(
                status_message=f"Invalid energy type: {self.chosen_energy_type.value}. Must be acid, cold, fire, lightning, or thunder."
            )

        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated {self.name}"
        )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Apply Protection from Energy - grants resistance to chosen energy type."""

        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else caster

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        # 1. Apply Concentrating condition to caster
        concentration = self.ensure_concentration(execution_event)

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"Concentrating on {self.name}"
        )

        # 2. Apply protection effect to target
        protection = ProtectionFromEnergyEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            energy_type=self.chosen_energy_type
        )
        target.add_condition(protection, parent_event=effect_event)

        # 3. Link via linked_conditions for cleanup
        if protection.applied:
            concentration.add_linked_condition(target.uuid, protection.uuid)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"{self.name} ({self.chosen_energy_type.value}) cast on {target.name}"
        )


# =============================================================================
# STONESKIN
# =============================================================================

class StoneskinEffect(BaseCondition):
    """
    Grants resistance to bludgeoning, piercing, and slashing damage.

    Note: Per SRD, this should only apply to nonmagical attacks.
    We don't track magical vs nonmagical damage yet, so this applies
    to ALL B/P/S damage (same as Barbarian Rage).
    """
    name: str = "Stoneskin"
    description: str = "Resistant to bludgeoning, piercing, and slashing damage"
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL})

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:

        if not self.target_entity_uuid:
            return [], [], [], [], declaration_event.cancel(status_message="Target entity UUID not set")

        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        outs: List[Tuple[UUID, UUID]] = []

        # Add B/P/S resistance
        for damage_type in [DamageType.BLUDGEONING, DamageType.PIERCING, DamageType.SLASHING]:
            resist_mod = ResistanceModifier(
                name=f"Stoneskin ({damage_type.value})",
                source_entity_uuid=self.source_entity_uuid,
                target_entity_uuid=target.uuid,
                value=ResistanceStatus.RESISTANCE,
                damage_type=damage_type
            )
            mod_uuid = target.health.damage_reduction.self_static.add_resistance_modifier(resist_mod)
            outs.append((target.health.damage_reduction.uuid, mod_uuid))

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Applied physical resistance to {target.name}"
        )

        return outs, [], [], [], effect_event


class Stoneskin(SpellAction):
    """Stoneskin - 4th level Abjuration (Concentration)

    This spell turns the flesh of a willing creature you touch as hard as stone.
    Until the spell ends, the target has resistance to nonmagical bludgeoning,
    piercing, and slashing damage.

    Note: We don't track magical vs nonmagical damage, so this applies to ALL B/P/S.

    Duration: Concentration, up to 1 hour
    """
    name: str = Field(default="Stoneskin")
    description: str = Field(default="Grant resistance to B/P/S damage")
    spell_level: int = Field(default=4)
    spell_school: str = Field(default="abjuration")
    concentration: bool = Field(default=True)
    target_type: TargetType = Field(default=TargetType.ENTITY)
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.REACH, normal=5))  # Touch

    # Target filtering - can target self or allies
    include_self: bool = Field(default=True)
    valid_target_filter: str = Field(default="self_or_allies")

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate target and range."""

        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else caster

        if not caster:
            return declaration_event.cancel(status_message="Caster not found")

        # Default to self if no target
        if not target:
            target = caster
            self.target_entity_uuid = caster.uuid

        # Validate range (touch = 5ft, or self)
        if target.uuid != caster.uuid:
            distance = caster.senses.get_feet_distance(target.position)
            if distance > self.effective_range:
                return declaration_event.cancel(
                    status_message=f"Target out of range ({distance}ft > {self.effective_range}ft)"
                )

        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated {self.name}"
        )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Apply Stoneskin - grants B/P/S resistance."""

        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else caster

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        # 1. Apply Concentrating condition to caster
        concentration = self.ensure_concentration(execution_event)

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"Concentrating on {self.name}"
        )

        # 2. Apply stoneskin effect to target
        stoneskin = StoneskinEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid
        )
        target.add_condition(stoneskin, parent_event=effect_event)

        # 3. Link via linked_conditions for cleanup
        if stoneskin.applied:
            concentration.add_linked_condition(target.uuid, stoneskin.uuid)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"{self.name} cast on {target.name}"
        )


# =============================================================================
# COUNTERSPELL (REACTION)
# =============================================================================

def counterspell_reaction_processor(event: Event, source_entity_uuid: UUID) -> Optional[Event]:
    """Counterspell reaction: when an enemy within 60ft casts a spell, attempt to counter it.

    - Auto-success if slot level >= spell's cast level
    - Otherwise: ability check DC = 10 + spell's cast level
    """
    # Only react to CAST_SPELL events
    if event.event_type != EventType.CAST_SPELL:
        return None

    # Don't counter own spells
    if event.source_entity_uuid == source_entity_uuid:
        return None

    entity = Entity.get(source_entity_uuid)
    if not entity or not isinstance(entity, Entity):
        return None

    # Must be able to see the caster
    if event.source_entity_uuid not in entity.senses.entities:
        return None

    # Must be within 60ft
    spell_caster = Entity.get(event.source_entity_uuid)
    if not spell_caster:
        return None
    distance = entity.senses.get_feet_distance(spell_caster.position)
    if distance > 60:
        return None

    # Need reaction available
    if not entity.action_economy.can_afford("reactions", 1):
        return None

    # Need a spell slot level 3+
    if entity.get_lowest_spell_slot(3) is None:
        return None

    # Get the spell's cast level from the SpellEvent
    spell_cast_level = 0
    if isinstance(event, SpellEvent):
        spell_cast_level = event.cast_at_level or event.spell_level
    if spell_cast_level <= 0:
        return None  # Can't counter cantrips

    # Strategy: try to find a slot that auto-counters, else use cheapest slot
    auto_slot = entity.get_lowest_spell_slot(spell_cast_level)
    if auto_slot is not None:
        # Auto-success: slot >= spell level
        entity.action_economy.consume("reactions", 1)
        entity.action_economy.consume(spell_slot_cost_type(auto_slot), 1)
        return event.cancel(
            status_message=f"{entity.name} casts Counterspell (L{auto_slot} slot) - auto-counters L{spell_cast_level} spell!"
        )

    # Fall back to cheapest slot + ability check
    cheap_slot = entity.get_lowest_spell_slot(3)
    if cheap_slot is None:
        return None

    # Consume reaction + slot regardless of check outcome
    entity.action_economy.consume("reactions", 1)
    entity.action_economy.consume(spell_slot_cost_type(cheap_slot), 1)

    # Ability check: DC = 10 + spell's cast level
    dc = 10 + spell_cast_level
    ability_name = entity.spellcasting.spellcasting_ability or "intelligence"
    ability_mod = entity.ability_scores.get_ability(ability_name).modifier
    d20 = random.randint(1, 20)
    check_total = d20 + ability_mod
    if check_total >= dc:
        return event.cancel(
            status_message=f"{entity.name} casts Counterspell (L{cheap_slot} slot) - check {check_total} vs DC {dc} - countered!"
        )
    else:
        # Failed - spell goes through, slot wasted
        return event.model_copy(update={
            "status_message": f"{entity.name} casts Counterspell (L{cheap_slot} slot) - check {check_total} vs DC {dc} - FAILED"
        })


def create_counterspell_reaction_handler(source_entity_uuid: UUID) -> EventHandler:
    """Create a Counterspell reaction handler for an entity."""
    return EventHandler(
        name="Counterspell",
        source_entity_uuid=source_entity_uuid,
        trigger_conditions=[
            Trigger(
                event_type=EventType.CAST_SPELL,
                event_phase=EventPhase.EXECUTION,
            )
        ],
        event_processor=counterspell_reaction_processor,
        player_toggleable=True
    )


def register_counterspell_reaction(entity: Entity) -> None:
    """Register the Counterspell reaction handler on an entity."""
    handler = create_counterspell_reaction_handler(entity.uuid)
    entity.add_event_handler(handler)


# =============================================================================
# Globe of Invulnerability (Level 6, Concentration)
# =============================================================================

class GlobeZone(BaseCondition):
    """Zone marker condition for Globe of Invulnerability.

    Tracks affected positions around the caster. Not a full ZoneControlCondition
    since there are no entry/exit/turn_start effects — the spell-blocking is done
    via EventHandlers on CAST_SPELL and CONDITION_APPLICATION.

    SRD: Globe is IMMOBILE — stays at cast position, does not follow caster.
    Blocks spells by BASE level (not upcast level), including cantrips (level 0).
    Only blocks spells cast from OUTSIDE the barrier.
    """
    name: str = "Globe of Invulnerability Zone"
    description: str = "Immobile sphere blocks spells level 5 or lower"
    condition_category: ConditionCategory = ConditionCategory.STATUS
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL})

    zone_center: Tuple[int, int] = Field(default=(0, 0))
    zone_radius_feet: int = Field(default=10)
    affected_positions: set = Field(default_factory=set)
    max_blocked_level: int = Field(default=5)  # Blocks spells up to this level

    model_config = {"arbitrary_types_allowed": True}

    def _compute_positions(self) -> set:
        """Compute positions in the 10ft radius sphere around center."""
        shape = Sphere(
            source_entity_uuid=self.source_entity_uuid,
            target=self.zone_center,
            radius_feet=self.zone_radius_feet
        )
        shape.compute_objective(self.zone_center)
        return set(shape.affected_positions)

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        self.affected_positions = self._compute_positions()
        handler_uuids = []

        # Spell-blocking handler (Layer 1)
        blocker = self._create_spell_blocker()
        EventQueue.add_event_handler(blocker)
        handler_uuids.append(blocker.uuid)

        # Condition-blocking handler (Layer 2)
        cond_blocker = self._create_condition_blocker()
        EventQueue.add_event_handler(cond_blocker)
        handler_uuids.append(cond_blocker.uuid)

        # Register with SpellProtectionRegistry for zone spell filtering
        SpellProtectionRegistry.register(SpellProtection(
            uuid=self.uuid,
            positions=set(self.affected_positions),
            max_blocked_level=self.max_blocked_level,
        ))

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Globe of Invulnerability active"
        )
        return [], handler_uuids, [], [], effect_event

    def cleanup_own_state(self, expire: bool = False, parent_event: Optional[Event] = None) -> bool:
        """Unregister from SpellProtectionRegistry before standard cleanup."""
        SpellProtectionRegistry.unregister(self.uuid)
        return super().cleanup_own_state(expire=expire, parent_event=parent_event)

    def _create_spell_blocker(self) -> EventHandler:
        """Handler that cancels spells level <= max_blocked_level targeting inside the globe.

        Fixed bugs vs original:
        1. Uses spell_level (base), not cast_at_level (upcast) — Fireball upcast to L7 is still L3
        2. Position-based "outside" check — source position outside globe, not UUID comparison
        3. Cantrips (level 0) are blocked — 0 <= 5
        4. No follow handler — globe is immobile per SRD
        """
        globe = self

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            if event.event_type != EventType.CAST_SPELL:
                return None
            if not isinstance(event, SpellEvent):
                return None

            # Use BASE spell level (not upcast level)
            base_level = event.spell_level
            if base_level > globe.max_blocked_level:
                return None

            # Check if source is OUTSIDE the globe (position-based, not UUID)
            source = Entity.get(event.source_entity_uuid)
            if not source or source.position in globe.affected_positions:
                return None  # Source inside globe — spell passes through

            # Check if target entity is inside the globe
            if event.target_entity_uuid:
                target = Entity.get(event.target_entity_uuid)
                if target and target.position in globe.affected_positions:
                    return event.cancel(
                        status_message=f"Globe of Invulnerability blocks L{base_level} spell"
                    )

            return None

        return EventHandler(
            name="Globe Spell Blocker",
            source_entity_uuid=self.source_entity_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.CAST_SPELL,
                event_phase=EventPhase.EXECUTION
            )],
            event_processor=processor
        )

    def _create_condition_blocker(self) -> EventHandler:
        """Handler that blocks magical conditions applied to entities/tiles inside the globe.

        Catches zone spell effects, magical conditions from SpatialHandlers, etc.
        Walks the parent_event chain to find the originating SpellEvent and checks
        its base spell_level.
        """
        globe = self
        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            if not isinstance(event, ConditionApplicationEvent):
                return None

            condition = event.condition
            if not condition.magical_origin:
                return None

            # Get target position (entity or tile)
            target_pos: Optional[Tuple[int, int]] = None
            target_entity = Entity.get(event.target_entity_uuid) if event.target_entity_uuid else None
            if target_entity:
                target_pos = target_entity.position
            else:
                # Could be a tile — check GridMap
                grid = get_map()
                tile = grid.get_tile_by_uuid(event.target_entity_uuid) if event.target_entity_uuid else None
                if tile:
                    target_pos = tile.position

            if target_pos is None or target_pos not in globe.affected_positions:
                return None

            # Walk parent_event chain to find the SpellEvent
            spell_level: Optional[int] = None
            source_pos: Optional[Tuple[int, int]] = None
            current_uuid = event.parent_event
            visited = 0
            while current_uuid and visited < 20:
                parent = BaseObject.get(current_uuid)
                if parent is None:
                    break
                if isinstance(parent, SpellEvent):
                    spell_level = parent.spell_level
                    source = Entity.get(parent.source_entity_uuid)
                    if source:
                        source_pos = source.position
                    break
                if isinstance(parent, Event):
                    current_uuid = parent.parent_event
                else:
                    break
                visited += 1

            if spell_level is None or source_pos is None:
                return None

            if spell_level > globe.max_blocked_level:
                return None

            # Source must be outside the globe
            if source_pos in globe.affected_positions:
                return None

            return event.cancel(
                status_message=f"Globe of Invulnerability blocks magical condition (L{spell_level} spell)"
            )

        return EventHandler(
            name="Globe Condition Blocker",
            source_entity_uuid=self.source_entity_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.CONDITION_APPLICATION,
                event_phase=EventPhase.DECLARATION
            )],
            event_processor=processor
        )


class GlobeOfInvulnerability(SpellAction):
    """Globe of Invulnerability - 6th level Abjuration (Concentration)

    An immobile, faintly shimmering barrier springs into existence in a 10-foot
    radius around you and remains for the duration. Any spell of 5th level or
    lower cast from outside the barrier can't affect creatures or areas within it.
    The barrier doesn't prevent such spells from being cast, but it causes them
    to fail on targets within the sphere.

    At Higher Levels: blocked spell level increases by 1 per slot above 6th.
    """
    name: str = Field(default="Globe of Invulnerability")
    description: str = Field(default="10ft sphere blocks spells L5 or lower, concentration")
    spell_level: int = Field(default=6)
    spell_school: str = Field(default="abjuration")
    concentration: bool = Field(default=True)
    target_type: TargetType = Field(default=TargetType.SELF)
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.SELF))

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return declaration_event.cancel(status_message="Caster not found")
        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated {self.name}"
        )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return execution_event.cancel(status_message="Caster not found")

        upcast_bonus = self.get_upcast_bonus()
        max_blocked = 5 + upcast_bonus

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"{caster.name} casts Globe of Invulnerability (blocks L{max_blocked} and below)"
        )

        zone = GlobeZone(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid,
            zone_center=caster.senses.position,
            max_blocked_level=max_blocked
        )
        caster.add_condition(zone, parent_event=effect_event)

        concentration = self.ensure_concentration(effect_event)
        concentration.add_linked_condition(caster.uuid, zone.uuid)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"Globe of Invulnerability active — blocks spells L{max_blocked} and below"
        )


# =============================================================================
# Banishment (Level 4, Concentration)
# =============================================================================

class BanishedCondition(BaseCondition):
    """Condition applied to banished entities.

    Removes entity from GridMap spatial tracking (invisible to all, can't act).
    Stores original position for return when concentration breaks.
    Incapacitated is applied as a sub-condition.
    """
    name: str = "Banished"
    description: str = "Banished to another plane — removed from play"
    condition_category: ConditionCategory = ConditionCategory.STATUS
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL})

    original_position: Tuple[int, int] = Field(default=(0, 0))

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not target:
            return [], [], [], [], None

        # Store original position
        self.original_position = target.position

        # Apply Incapacitated sub-condition
        sub_conditions_uuids = []
        incap = Incapacitated(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.target_entity_uuid,
            parent_condition=self.uuid,
            tags={ConditionTag.MAGICAL}
        )
        target.add_condition(incap, parent_event=declaration_event)
        sub_conditions_uuids.append(incap.uuid)

        # Remove from GridMap spatial tracking
        grid = get_map()
        pos = self.original_position
        grid._entity_positions.pop(target.uuid, None)
        if pos in grid._entities_by_position:
            grid._entities_by_position[pos].discard(target.uuid)

        # Remove from Entity class-level position registry (keeps senses rebuild in sync)
        if target in Entity._entity_by_position[pos]:
            Entity._entity_by_position[pos].remove(target)

        # Fire ENTITY_LEFT so other entities' senses update
        if grid._events_enabled:
            spatial_event = SpatialChangeEvent.entity_left(pos, target.uuid, None)
            grid._fire_spatial_event(spatial_event)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"{target.name} banished from the battlefield"
        )
        return [], [], sub_conditions_uuids, [], effect_event

    def _remove(self, removal_event: Optional[Event] = None) -> Optional[Event]:
        """Return entity to original position when banishment ends."""
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target:
            grid = get_map()
            pos = self.original_position

            # Check if original position is occupied, try to displace
            occupants = grid.get_entities_at(pos) - {target.uuid}
            if occupants:
                for occ_uuid in occupants:
                    occ = Entity.get(occ_uuid)
                    if occ:
                        for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0), (1, 1), (-1, 1), (1, -1), (-1, -1)]:
                            adj = (pos[0] + dx, pos[1] + dy)
                            if grid.is_walkable_for(adj[0], adj[1], occ_uuid):
                                Entity.update_entity_position(occ, adj)
                                break
                    break  # Only displace one

            # Place banished entity back
            grid._entity_positions[target.uuid] = pos
            if pos not in grid._entities_by_position:
                grid._entities_by_position[pos] = set()
            grid._entities_by_position[pos].add(target.uuid)

            # Restore Entity class-level position registry
            if target not in Entity._entity_by_position[pos]:
                Entity._entity_by_position[pos].append(target)

            # Fire ENTITY_ENTERED
            if grid._events_enabled:
                spatial_event = SpatialChangeEvent.entity_entered(pos, target.uuid, None)
                grid._fire_spatial_event(spatial_event)

        return super()._remove(removal_event)


class Banishment(SpellAction):
    """Banishment - 4th level Abjuration (Concentration)

    You attempt to send one creature that you can see within range to another
    plane of existence. The target must succeed on a CHA saving throw or be
    banished. While banished, the target is incapacitated and removed from play.
    When the spell ends, the target reappears in the space it left.

    At Higher Levels: +1 target per slot level above 4th.
    """
    name: str = Field(default="Banishment")
    description: str = Field(default="CHA save or banished (removed from play), concentration")
    spell_level: int = Field(default=4)
    spell_school: str = Field(default="abjuration")
    concentration: bool = Field(default=True)
    target_type: TargetType = Field(default=TargetType.ENTITY)
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.RANGE, normal=60))
    valid_target_filter: str = Field(default="enemies")
    include_self: bool = Field(default=False)

    def get_multi_target_count(self) -> int:
        """1 target base + 1 per level above 4th."""
        return 1 + self.get_upcast_bonus()

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        los_event = validate_line_of_sight(declaration_event, self.source_entity_uuid)
        if los_event is None or los_event.canceled:
            return los_event

        source = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not source or not target:
            return declaration_event.cancel(status_message="Entity not found")

        distance = source.senses.get_feet_distance(target.position)
        if distance > self.effective_range:
            return declaration_event.cancel(status_message=f"Target out of range ({distance}ft)")

        return los_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated {self.name}"
        )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not caster or not target:
            return execution_event.cancel(status_message="Entity not found")

        # CHA saving throw
        dc = caster.spell_save_dc()
        save_request = caster.create_saving_throw_request(
            target_entity_uuid=target.uuid,
            ability_name="charisma",
            dc=dc,
            parent_event=execution_event.uuid
        )
        _, save_roll, success = target.saving_throw(save_request)

        save_bonus = target.saving_throw_bonus(caster.uuid, "charisma").normalized_score

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            save_ability="charisma",
            save_dc=dc,
            save_success=success,
            save_roll=save_roll,
            save_bonus=save_bonus,
            target_entity_name=target.name,
            status_message=f"CHA save: {save_roll.total} vs DC {dc} - {'Success' if success else 'Failure'}"
        )

        if success:
            return effect_event.phase_to(
                new_phase=EventPhase.COMPLETION,
                status_message=f"{target.name} resists Banishment (CHA save)"
            )

        # Failed save: apply BanishedCondition
        banished = BanishedCondition(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid
        )
        target.add_condition(banished, parent_event=effect_event)

        # Concentration
        concentration = self.ensure_concentration(effect_event)
        if banished.applied:
            concentration.add_linked_condition(target.uuid, banished.uuid)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"{target.name} banished!"
        )


# =============================================================================
# Restoration Spells
# =============================================================================


_LESSER_RESTORATION_CONDITIONS = {"Blinded", "Deafened", "Paralyzed", "Poisoned"}
_GREATER_RESTORATION_CONDITIONS = {
    "Charmed", "Poisoned", "Blinded", "Deafened", "Paralyzed", "Stunned", "Frightened"
}


class LesserRestoration(SpellAction):
    """Lesser Restoration - 2nd level Abjuration

    You touch a creature and can end either one disease or one condition
    afflicting it. The condition can be blinded, deafened, paralyzed, or poisoned.
    """
    name: str = Field(default="Lesser Restoration")
    description: str = Field(default="Touch: remove one of blinded, deafened, paralyzed, or poisoned")
    spell_level: int = Field(default=2)
    spell_school: str = Field(default="abjuration")
    target_type: TargetType = Field(default=TargetType.ENTITY)
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.REACH, normal=5)
    )
    include_self: bool = Field(default=True)
    valid_target_filter: str = Field(default="self_or_allies")

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not caster or not target:
            return declaration_event.cancel(status_message="Caster or target not found")

        if target.uuid not in caster.senses.entities and target.uuid != caster.uuid:
            return declaration_event.cancel(status_message="Target not in line of sight")

        distance = caster.senses.get_feet_distance(target.position)
        if distance > self.effective_range:
            return declaration_event.cancel(
                status_message=f"Out of range ({distance}ft > {self.effective_range}ft)"
            )

        parent_result = super()._validate(declaration_event)
        return type_cast(Optional[SpellEvent], parent_result)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            target_entity_name=target.name,
            status_message=f"Lesser Restoration on {target.name}"
        )

        removed = None
        for condition_name in _LESSER_RESTORATION_CONDITIONS:
            if condition_name in target.active_conditions:
                target.remove_condition(condition_name, parent_event=effect_event)
                removed = condition_name
                break

        status = f"Removed {removed}" if removed else "No removable condition found"
        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            total_damage=0,
            status_message=f"Lesser Restoration: {status}"
        )


class GreaterRestoration(SpellAction):
    """Greater Restoration - 5th level Abjuration

    You imbue a creature you touch with positive energy to undo a debilitating
    effect. You can reduce the target's exhaustion level by one, or end one of
    the following effects: charmed, petrified, cursed, ability score reduction,
    or HP maximum reduction.
    """
    name: str = Field(default="Greater Restoration")
    description: str = Field(default="Touch: remove one of charmed, poisoned, blinded, deafened, paralyzed, stunned, frightened")
    spell_level: int = Field(default=5)
    spell_school: str = Field(default="abjuration")
    target_type: TargetType = Field(default=TargetType.ENTITY)
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.REACH, normal=5)
    )
    include_self: bool = Field(default=True)
    valid_target_filter: str = Field(default="self_or_allies")

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not caster or not target:
            return declaration_event.cancel(status_message="Caster or target not found")

        if target.uuid not in caster.senses.entities and target.uuid != caster.uuid:
            return declaration_event.cancel(status_message="Target not in line of sight")

        distance = caster.senses.get_feet_distance(target.position)
        if distance > self.effective_range:
            return declaration_event.cancel(
                status_message=f"Out of range ({distance}ft > {self.effective_range}ft)"
            )

        parent_result = super()._validate(declaration_event)
        return type_cast(Optional[SpellEvent], parent_result)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            target_entity_name=target.name,
            status_message=f"Greater Restoration on {target.name}"
        )

        removed = None
        for condition_name in _GREATER_RESTORATION_CONDITIONS:
            if condition_name in target.active_conditions:
                target.remove_condition(condition_name, parent_event=effect_event)
                removed = condition_name
                break

        status = f"Removed {removed}" if removed else "No removable condition found"
        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            total_damage=0,
            status_message=f"Greater Restoration: {status}"
        )


# =============================================================================
# Remove Curse (Level 3, instantaneous)
# =============================================================================


class RemoveCurse(SpellAction):
    """Remove Curse - 3rd level Abjuration

    At your touch, all curses affecting one creature or object end.
    Finds first condition with ConditionTag.CURSE and removes it.
    """
    name: str = Field(default="Remove Curse")
    description: str = Field(default="Touch: remove one curse from a creature")
    spell_level: int = Field(default=3)
    spell_school: str = Field(default="abjuration")
    target_type: TargetType = Field(default=TargetType.ENTITY)
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.REACH, normal=5)
    )
    include_self: bool = Field(default=True)
    valid_target_filter: str = Field(default="self_or_allies")

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not caster or not target:
            return declaration_event.cancel(status_message="Caster or target not found")

        if target.uuid not in caster.senses.entities and target.uuid != caster.uuid:
            return declaration_event.cancel(status_message="Target not in line of sight")

        distance = caster.senses.get_feet_distance(target.position)
        if distance > self.effective_range:
            return declaration_event.cancel(
                status_message=f"Out of range ({distance}ft > {self.effective_range}ft)"
            )

        parent_result = super()._validate(declaration_event)
        return type_cast(Optional[SpellEvent], parent_result)

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            target_entity_name=target.name,
            status_message=f"Remove Curse on {target.name}"
        )

        removed = None
        for cond_name, cond in list(target.active_conditions.items()):
            if ConditionTag.CURSE in cond.tags:
                target.remove_condition(cond_name, parent_event=effect_event)
                removed = cond_name
                break

        status = f"Removed {removed}" if removed else "No curse found"
        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            total_damage=0,
            status_message=f"Remove Curse: {status}"
        )


# =============================================================================
# Protection from Poison (Level 2, NOT concentration)
# =============================================================================

class ProtectionFromPoisonEffect(BaseCondition):
    """Resistance to poison damage + immunity to Poisoned condition."""
    name: str = "Protection from Poison"
    description: str = "Resistant to poison damage, immune to Poisoned condition"
    condition_category: ConditionCategory = ConditionCategory.STATUS
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL})

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        if not self.target_entity_uuid:
            return [], [], [], [], declaration_event.cancel(status_message="Target entity UUID not set")

        target = Entity.get(self.target_entity_uuid)
        if not target or not isinstance(target, Entity):
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        outs: List[Tuple[UUID, UUID]] = []

        # Poison damage resistance
        resist_mod = ResistanceModifier(
            name="Protection from Poison",
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=target.uuid,
            value=ResistanceStatus.RESISTANCE,
            damage_type=DamageType.POISON
        )
        mod_uuid = target.health.damage_reduction.self_static.add_resistance_modifier(resist_mod)
        outs.append((target.health.damage_reduction.uuid, mod_uuid))

        # Immunity to Poisoned condition
        target.add_condition_immunity("Poisoned", immunity_name="Protection from Poison")

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Protection from Poison applied to {target.name}"
        )
        return outs, [], [], [], effect_event

    def _remove(self, event: Optional[Event] = None) -> Optional[Event]:
        """Clean up condition immunity on removal."""
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target:
            target._remove_static_condition_immunity("Poisoned", "Protection from Poison")
        return super()._remove(event)


class ProtectionFromPoison(SpellAction):
    """Protection from Poison - 2nd level Abjuration (NOT concentration)"""
    name: str = Field(default="Protection from Poison")
    description: str = Field(default="Touch: resist poison damage, immune to Poisoned")
    spell_level: int = Field(default=2)
    spell_school: str = Field(default="abjuration")
    concentration: bool = Field(default=False)
    target_type: TargetType = Field(default=TargetType.ENTITY)
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.REACH, normal=5))
    include_self: bool = Field(default=True)
    valid_target_filter: str = Field(default="self_or_allies")

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else caster
        if not caster:
            return declaration_event.cancel(status_message="Caster not found")
        if not target:
            target = caster
            self.target_entity_uuid = caster.uuid

        if target.uuid != caster.uuid:
            if target.uuid not in caster.senses.entities:
                return declaration_event.cancel(status_message="Target not in line of sight")
            distance = caster.senses.get_feet_distance(target.position)
            if distance > self.effective_range:
                return declaration_event.cancel(
                    status_message=f"Out of range ({distance}ft > {self.effective_range}ft)"
                )

        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated {self.name}"
        )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else caster
        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            target_entity_name=target.name,
            status_message=f"Protection from Poison on {target.name}"
        )

        condition = ProtectionFromPoisonEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid
        )
        target.add_condition(condition, parent_event=effect_event)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"{self.name} cast on {target.name}"
        )


# =============================================================================
# Death Ward (Level 4, NOT concentration)
# =============================================================================

class DeathWardEffect(BaseCondition):
    """First time target would drop to 0 HP, instead drops to 1 HP. One-use."""
    name: str = "Death Ward"
    description: str = "Once: survive lethal damage at 1 HP"
    condition_category: ConditionCategory = ConditionCategory.STATUS
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL})

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        if not self.target_entity_uuid:
            return [], [], [], [], declaration_event.cancel(status_message="Target entity UUID not set")

        target = Entity.get(self.target_entity_uuid)
        if not target or not isinstance(target, Entity):
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        target_uuid = self.target_entity_uuid
        handler_uuids: List[UUID] = []

        def death_ward_processor(event: Event, source_entity_uuid: UUID) -> Optional[Event]:
            _ = source_entity_uuid
            if not isinstance(event, TakeDamageEvent):
                return None
            entity = Entity.get(target_uuid)
            if not entity:
                return None
            current_hp = entity.get_hp()
            damage = event.total_damage
            # Only trigger if damage would drop to 0 or below
            if current_hp - damage > 0:
                return None
            # Cap damage to leave 1 HP
            new_damage = current_hp - 1
            # Remove Death Ward (one-use) — must be done before returning modified event
            if "Death Ward" in entity.active_conditions:
                entity.remove_condition("Death Ward", parent_event=event)
            return event.model_copy(update={
                "modified": True,
                "final_damage": max(0, new_damage),
                "status_message": f"Death Ward! {entity.name} survives with 1 HP"
            })

        handler = EventHandler(
            name="Death Ward",
            source_entity_uuid=target_uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.TAKE_DAMAGE,
                    event_phase=EventPhase.EFFECT,
                    event_target_entity_uuid=target_uuid
                )
            ],
            event_processor=death_ward_processor
        )
        target.add_event_handler(handler)
        handler_uuids.append(handler.uuid)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Death Ward applied to {target.name}"
        )
        return [], handler_uuids, [], [], effect_event


class DeathWard(SpellAction):
    """Death Ward - 4th level Abjuration (NOT concentration)"""
    name: str = Field(default="Death Ward")
    description: str = Field(default="Touch: once, survive lethal damage at 1 HP")
    spell_level: int = Field(default=4)
    spell_school: str = Field(default="abjuration")
    concentration: bool = Field(default=False)
    target_type: TargetType = Field(default=TargetType.ENTITY)
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.REACH, normal=5))
    include_self: bool = Field(default=True)
    valid_target_filter: str = Field(default="self_or_allies")

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else caster
        if not caster:
            return declaration_event.cancel(status_message="Caster not found")
        if not target:
            target = caster
            self.target_entity_uuid = caster.uuid

        if target.uuid != caster.uuid:
            if target.uuid not in caster.senses.entities:
                return declaration_event.cancel(status_message="Target not in line of sight")
            distance = caster.senses.get_feet_distance(target.position)
            if distance > self.effective_range:
                return declaration_event.cancel(
                    status_message=f"Out of range ({distance}ft > {self.effective_range}ft)"
                )

        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated {self.name}"
        )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else caster
        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            target_entity_name=target.name,
            status_message=f"Death Ward on {target.name}"
        )

        condition = DeathWardEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid
        )
        target.add_condition(condition, parent_event=effect_event)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"{self.name} cast on {target.name}"
        )


# =============================================================================
# Freedom of Movement (Level 4, NOT concentration)
# =============================================================================

class FreedomOfMovementEffect(BaseCondition):
    """Ignores difficult terrain, immune to Grappled and Restrained."""
    name: str = "Freedom of Movement"
    description: str = "Immune to difficult terrain, Grappled, and Restrained"
    condition_category: ConditionCategory = ConditionCategory.STATUS
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL})

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]]:
        if not self.target_entity_uuid:
            return [], [], [], [], declaration_event.cancel(status_message="Target entity UUID not set")

        target = Entity.get(self.target_entity_uuid)
        if not target or not isinstance(target, Entity):
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        # Ignore difficult terrain
        target.ignore_difficult_terrain = True
        target.senses._paths_dirty = True

        # Immune to Grappled and Restrained
        target.add_condition_immunity("Grappled", immunity_name="Freedom of Movement")
        target.add_condition_immunity("Restrained", immunity_name="Freedom of Movement")

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Freedom of Movement applied to {target.name}"
        )
        return [], [], [], [], effect_event

    def _remove(self, event: Optional[Event] = None) -> Optional[Event]:
        """Clean up flag and condition immunities on removal."""
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if target:
            target.ignore_difficult_terrain = False
            target.senses._paths_dirty = True
            target._remove_static_condition_immunity("Grappled", "Freedom of Movement")
            target._remove_static_condition_immunity("Restrained", "Freedom of Movement")
        return super()._remove(event)


class FreedomOfMovement(SpellAction):
    """Freedom of Movement - 4th level Abjuration (NOT concentration)"""
    name: str = Field(default="Freedom of Movement")
    description: str = Field(default="Touch: immune to difficult terrain, Grappled, Restrained")
    spell_level: int = Field(default=4)
    spell_school: str = Field(default="abjuration")
    concentration: bool = Field(default=False)
    target_type: TargetType = Field(default=TargetType.ENTITY)
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.REACH, normal=5))
    include_self: bool = Field(default=True)
    valid_target_filter: str = Field(default="self_or_allies")

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else caster
        if not caster:
            return declaration_event.cancel(status_message="Caster not found")
        if not target:
            target = caster
            self.target_entity_uuid = caster.uuid

        if target.uuid != caster.uuid:
            if target.uuid not in caster.senses.entities:
                return declaration_event.cancel(status_message="Target not in line of sight")
            distance = caster.senses.get_feet_distance(target.position)
            if distance > self.effective_range:
                return declaration_event.cancel(
                    status_message=f"Out of range ({distance}ft > {self.effective_range}ft)"
                )

        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated {self.name}"
        )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else caster
        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            target_entity_name=target.name,
            status_message=f"Freedom of Movement on {target.name}"
        )

        condition = FreedomOfMovementEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid
        )
        target.add_condition(condition, parent_event=effect_event)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"{self.name} cast on {target.name}"
        )


# =============================================================================
# Resistance (Cantrip) - Add 1d4 to one saving throw (Guidance clone)
# =============================================================================

def _resistance_processor(
    event: D20RollResultEvent,
    source_entity_uuid: UUID,
) -> Optional[D20RollResultEvent]:
    """Add 1d4 to saving throw roll. One-use: removes condition after firing."""
    if event.source_entity_uuid != source_entity_uuid:
        return None

    d4_value = random.randint(1, 4)
    effective = event.get_effective_roll()
    new_total = effective.total + d4_value
    new_roll = effective.model_copy(update={"total": new_total})
    event.replace_roll(new_roll, "Resistance", f"+{d4_value} (1d4)")

    target = Entity.get(source_entity_uuid)
    if target and "Resistance" in target.active_conditions:
        target.remove_condition("Resistance", parent_event=event)

    return event.model_copy(update={"modified": True})


class ResistanceEffect(BaseCondition):
    """Resistance condition — adds 1d4 to one saving throw, then expires."""
    name: str = "Resistance"
    description: str = "Add 1d4 to one saving throw"
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL})

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]
    ]:
        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        handler = EventHandler(
            name="Resistance",
            source_entity_uuid=self.target_entity_uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.SAVE_D20_ROLL_RESULT,
                    event_phase=EventPhase.EFFECT,
                    event_source_entity_uuid=self.target_entity_uuid,
                ),
            ],
            event_processor=_resistance_processor,
        )
        target.add_event_handler(handler)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Resistance applied to {target.name}"
        )
        return [], [handler.uuid], [], [], effect_event


class Resistance(SpellAction):
    """Resistance — Abjuration cantrip.

    Touch one willing creature. Once before the spell ends, the target can
    add 1d4 to one saving throw of its choice. Concentration, up to 1 minute.
    """
    name: str = Field(default="Resistance")
    description: str = Field(default="Add 1d4 to one saving throw (one use)")
    spell_level: int = Field(default=0)
    spell_school: str = Field(default="abjuration")
    concentration: bool = Field(default=True)
    target_type: TargetType = Field(default=TargetType.ENTITY)
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.REACH, normal=5))
    include_self: bool = Field(default=True)
    valid_target_filter: str = Field(default="self_or_allies")

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            target_entity_name=target.name,
            status_message=f"Resistance cast on {target.name}"
        )

        resistance_effect = ResistanceEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid
        )
        resistance_effect.duration.duration_type = DurationType.ROUNDS
        resistance_effect.duration.duration = 10
        target.add_condition(resistance_effect, parent_event=effect_event)

        concentration = self.ensure_concentration(effect_event)
        if resistance_effect.applied:
            concentration.add_linked_condition(target.uuid, resistance_effect.uuid)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"Resistance cast on {target.name}"
        )


# =============================================================================
# Shield of Faith (L1) - +2 AC, bonus action, concentration
# =============================================================================

class ShieldOfFaithEffect(BaseCondition):
    """Shield of Faith — +2 AC bonus."""
    name: str = "Shield of Faith"
    description: str = "+2 bonus to AC"
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL})

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]
    ]:
        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        outs: List[Tuple[UUID, UUID]] = []
        modifier_uuid = target.equipment.ac_bonus.self_static.add_value_modifier(
            NumericalModifier(
                name="Shield of Faith",
                value=2,
                source_entity_uuid=self.source_entity_uuid,
                target_entity_uuid=self.target_entity_uuid,
            )
        )
        outs.append((target.equipment.ac_bonus.uuid, modifier_uuid))

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Shield of Faith grants +2 AC to {target.name}"
        )
        return outs, [], [], [], effect_event


class ShieldOfFaith(SpellAction):
    """Shield of Faith — 1st-level abjuration.

    A shimmering field appears around a creature, granting +2 to AC.
    Bonus action, 60ft range, concentration up to 10 minutes.
    """
    name: str = Field(default="Shield of Faith")
    description: str = Field(default="+2 AC bonus (concentration)")
    spell_level: int = Field(default=1)
    spell_school: str = Field(default="abjuration")
    concentration: bool = Field(default=True)
    target_type: TargetType = Field(default=TargetType.ENTITY)
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.RANGE, normal=60))
    include_self: bool = Field(default=True)
    valid_target_filter: str = Field(default="self_or_allies")
    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(name="Shield of Faith Cost", cost_type="bonus_actions", cost=1,
             evaluator=entity_action_economy_cost_evaluator)
    ])

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            target_entity_name=target.name,
            status_message=f"Shield of Faith cast on {target.name}"
        )

        condition = ShieldOfFaithEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid
        )
        target.add_condition(condition, parent_event=effect_event)

        concentration = self.ensure_concentration(effect_event)
        if condition.applied:
            concentration.add_linked_condition(target.uuid, condition.uuid)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"Shield of Faith grants +2 AC to {target.name}"
        )


# =============================================================================
# Aid (L2) - +max HP bonus, 3 targets, NOT concentration
# =============================================================================

class AidEffect(BaseCondition):
    """Aid — increases max HP (and current HP) by 5 per spell level above 1st."""
    name: str = "Aid"
    description: str = "Max HP increased"
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL})
    hp_bonus: int = 5

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]
    ]:
        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        outs: List[Tuple[UUID, UUID]] = []
        modifier_uuid = target.health.max_hit_points_bonus.self_static.add_value_modifier(
            NumericalModifier(
                name="Aid",
                value=self.hp_bonus,
                source_entity_uuid=self.source_entity_uuid,
                target_entity_uuid=self.target_entity_uuid,
            )
        )
        outs.append((target.health.max_hit_points_bonus.uuid, modifier_uuid))

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Aid grants +{self.hp_bonus} max HP to {target.name}"
        )
        return outs, [], [], [], effect_event


class Aid(SpellAction):
    """Aid — 2nd-level abjuration.

    Choose up to three creatures within range. Each target's max HP and
    current HP increase by 5 for the duration. At higher levels: +5 per
    slot level above 2nd.
    """
    name: str = Field(default="Aid")
    description: str = Field(default="Increase max HP by 5 per level above 1st for 3 targets")
    spell_level: int = Field(default=2)
    spell_school: str = Field(default="abjuration")
    concentration: bool = Field(default=False)
    target_type: TargetType = Field(default=TargetType.MULTI_ENTITY)
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.RANGE, normal=30))
    include_self: bool = Field(default=True)
    valid_target_filter: str = Field(default="self_or_allies")

    def get_num_projectiles(self) -> int:
        return 3

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        hp_bonus = 5 * max(1, self.cast_at_level - 1)  # 5 at L2, 10 at L3, 15 at L4

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            target_entity_name=target.name,
            status_message=f"Aid grants +{hp_bonus} max HP to {target.name}"
        )

        condition = AidEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            hp_bonus=hp_bonus,
        )
        target.add_condition(condition, parent_event=effect_event)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            total_damage=0,
            status_message=f"Aid grants +{hp_bonus} max HP to {target.name}"
        )


# =============================================================================
# Sanctuary (L1) - Ward: force WIS save on attacker, self-break on offensive
# =============================================================================

class SanctuaryEffect(BaseCondition):
    """Sanctuary — warded creature can't be targeted by attacks unless attacker passes WIS save.
    Breaks when warded creature attacks or casts a spell affecting an enemy.
    """
    name: str = "Sanctuary"
    description: str = "Attackers must make WIS save to target this creature"
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL})
    spell_dc: int = 10
    duration_rounds: int = 10

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]
    ]:
        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        handler_uuids: List[UUID] = []

        # Handler 1: Ward — intercept attacks targeting this entity
        ward_handler = self._create_ward_handler()
        target.add_event_handler(ward_handler)
        handler_uuids.append(ward_handler.uuid)

        # Handler 2: Self-break — remove Sanctuary when warded entity acts offensively
        break_handler = self._create_break_handler()
        target.add_event_handler(break_handler)
        handler_uuids.append(break_handler.uuid)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Sanctuary protects {target.name}"
        )
        return [], handler_uuids, [], [], effect_event

    def _create_ward_handler(self) -> EventHandler:
        """Force WIS save on attackers targeting the warded entity."""
        warded_uuid = self.target_entity_uuid
        caster_uuid = self.source_entity_uuid
        dc = self.spell_dc

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            if event.target_entity_uuid != warded_uuid:
                return None
            if event.source_entity_uuid == warded_uuid:
                return None  # Can't block self-attacks

            attacker = Entity.get(event.source_entity_uuid)
            caster = Entity.get(caster_uuid)
            if not attacker or not caster:
                return None

            # Force WIS save
            save_request = caster.create_saving_throw_request(
                target_entity_uuid=attacker.uuid,
                ability_name="wisdom",
                dc=dc,
                parent_event=event.uuid
            )
            _, _, success = attacker.saving_throw(save_request)

            if success:
                return None  # Save passed — attack proceeds
            else:
                return event.cancel(status_message=f"{attacker.name} fails WIS save — Sanctuary blocks attack")

        return EventHandler(
            name="Sanctuary Ward",
            source_entity_uuid=warded_uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.ATTACK,
                    event_phase=EventPhase.DECLARATION,
                    event_target_entity_uuid=warded_uuid,
                ),
            ],
            event_processor=processor,
        )

    def _create_break_handler(self) -> EventHandler:
        """Remove Sanctuary when the warded entity attacks or casts an offensive spell."""
        warded_uuid = self.target_entity_uuid
        condition_uuid = self.uuid

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            if event.source_entity_uuid != warded_uuid:
                return None

            # For attacks: check that target is an enemy
            target = Entity.get(event.target_entity_uuid) if event.target_entity_uuid else None
            warded = Entity.get(warded_uuid)
            if not warded:
                return None

            if target and warded.is_enemy(target):
                if "Sanctuary" in warded.active_conditions:
                    active = warded.active_conditions.get("Sanctuary")
                    if active and active.uuid == condition_uuid:
                        warded.remove_condition("Sanctuary", parent_event=event)
            return None

        return EventHandler(
            name="Sanctuary Self-Break",
            source_entity_uuid=warded_uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.ATTACK,
                    event_phase=EventPhase.EFFECT,
                    event_source_entity_uuid=warded_uuid,
                ),
                Trigger(
                    event_type=EventType.CAST_SPELL,
                    event_phase=EventPhase.EFFECT,
                    event_source_entity_uuid=warded_uuid,
                ),
            ],
            event_processor=processor,
        )


class Sanctuary(SpellAction):
    """Sanctuary — 1st-level abjuration.

    You ward a creature. Any creature that targets the warded creature with
    an attack must first make a WIS save. On failure, the attack is wasted.
    If the warded creature attacks or casts a spell that affects an enemy,
    Sanctuary ends.
    """
    name: str = Field(default="Sanctuary")
    description: str = Field(default="Ward: attackers must WIS save; breaks on offensive action")
    spell_level: int = Field(default=1)
    spell_school: str = Field(default="abjuration")
    concentration: bool = Field(default=False)
    target_type: TargetType = Field(default=TargetType.ENTITY)
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.RANGE, normal=30))
    include_self: bool = Field(default=True)
    valid_target_filter: str = Field(default="self_or_allies")
    costs: List[Cost] = Field(default_factory=lambda: [
        Cost(name="Sanctuary Cost", cost_type="bonus_actions", cost=1,
             evaluator=entity_action_economy_cost_evaluator)
    ])

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        dc = caster.spell_save_dc()

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            target_entity_name=target.name,
            status_message=f"Sanctuary cast on {target.name}"
        )

        condition = SanctuaryEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            spell_dc=dc,
        )
        condition.duration.duration_type = DurationType.ROUNDS
        condition.duration.duration = 10
        target.add_condition(condition, parent_event=effect_event)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"Sanctuary protects {target.name} (DC {dc})"
        )


# =============================================================================
# Beacon of Hope (L3) - Advantage on WIS saves + maximize healing dice
# =============================================================================

class BeaconOfHopeEffect(BaseCondition):
    """Beacon of Hope — advantage on WIS saves and death saves,
    and all healing received is maximized.
    """
    name: str = "Beacon of Hope"
    description: str = "Advantage on WIS saves; healing dice maximized"
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL})

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]
    ]:
        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        outs: List[Tuple[UUID, UUID]] = []
        handler_uuids: List[UUID] = []

        # Advantage on WIS saves
        wis_save = target.saving_throws.get_saving_throw("wisdom")
        modifier_uuid = wis_save.bonus.self_static.add_advantage_modifier(
            AdvantageModifier(
                name="Beacon of Hope",
                value=AdvantageStatus.ADVANTAGE,
                source_entity_uuid=self.source_entity_uuid,
                target_entity_uuid=self.target_entity_uuid,
            )
        )
        outs.append((wis_save.bonus.uuid, modifier_uuid))

        # Handler to maximize healing dice
        heal_handler = self._create_heal_maximizer()
        target.add_event_handler(heal_handler)
        handler_uuids.append(heal_handler.uuid)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Beacon of Hope inspires {target.name}"
        )
        return outs, handler_uuids, [], [], effect_event

    def _create_heal_maximizer(self) -> EventHandler:
        """Maximize all healing dice received by this entity."""
        target_uuid = self.target_entity_uuid

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            if not isinstance(event, HealRollResultEvent):
                return None
            if event.target_entity_uuid != target_uuid:
                return None

            roll = event.final_roll
            # Maximize each die: replace results with max values
            if isinstance(roll.results, list) and len(roll.results) > 0:
                # Each die result becomes the max face value
                # We need to figure out the die value from the count and results
                # The bonus is stored separately in roll.bonus
                die_count = len(roll.results)
                # Get the die value from the original roll's dice
                original = event.original_roll
                if isinstance(original.results, list) and len(original.results) > 0:
                    # Die value = (total - bonus) could help but simpler:
                    # We know the Healing object, but we don't have it here.
                    # Instead, infer from the Dice: results are individual die values
                    # max value per die = max possible result, but we need the die size
                    # The DiceRoll has a dice_uuid referencing the Dice object
                    dice = Dice.get(roll.dice_uuid)
                    if dice:
                        max_per_die = dice.value
                        new_results = [max_per_die] * die_count
                        new_total = sum(new_results) + roll.bonus
                        new_roll = roll.model_copy(update={
                            "results": new_results,
                            "total": new_total,
                        })
                        event.replace_roll(new_roll, "Beacon of Hope", "maximize healing dice")

            return event

        return EventHandler(
            name="Beacon of Hope Heal Maximizer",
            source_entity_uuid=target_uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.HEAL_ROLL_RESULT,
                    event_phase=EventPhase.EFFECT,
                    event_target_entity_uuid=target_uuid,
                ),
            ],
            event_processor=processor,
        )


class BeaconOfHope(SpellAction):
    """Beacon of Hope — 3rd-level abjuration.

    Choose any number of creatures within range. Each target has advantage on
    WIS saves and death saves, and regains the maximum possible HP from healing.
    Concentration, up to 1 minute.
    """
    name: str = Field(default="Beacon of Hope")
    description: str = Field(default="Advantage on WIS saves; maximize healing received")
    spell_level: int = Field(default=3)
    spell_school: str = Field(default="abjuration")
    concentration: bool = Field(default=True)
    target_type: TargetType = Field(default=TargetType.MULTI_ENTITY)
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.RANGE, normal=30))
    include_self: bool = Field(default=True)
    valid_target_filter: str = Field(default="self_or_allies")

    def get_num_projectiles(self) -> int:
        return 6  # Reasonable cap for visible allies

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            target_entity_name=target.name,
            status_message=f"Beacon of Hope inspires {target.name}"
        )

        condition = BeaconOfHopeEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid
        )
        target.add_condition(condition, parent_event=effect_event)

        concentration = self.ensure_concentration(effect_event)
        if condition.applied:
            concentration.add_linked_condition(target.uuid, condition.uuid)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            total_damage=0,
            status_message=f"Beacon of Hope cast on {target.name}"
        )


# =============================================================================
# ANTIMAGIC FIELD (8th-level Abjuration, Concentration)
# =============================================================================

class AntimagicSuppression(BaseCondition):
    """Internal marker that holds a suppressed magical condition.

    When added to an entity, it stores a condition that was removed by an
    Antimagic Field zone. When this marker is removed (entity leaves zone or
    AMF ends), its _remove() re-adds the stored condition.

    Each marker has a unique name (e.g., "Antimagic Suppression: Haste") to
    avoid collision in active_conditions dict (keyed by name).
    """
    name: str = "Antimagic Suppression"
    condition_category: ConditionCategory = ConditionCategory.INTERNAL
    suppressed_condition: BaseCondition = Field(description="The condition object being suppressed")
    saved_parent_link: Optional[Tuple[UUID, UUID]] = Field(
        default=None,
        description="Saved (parent_block_uuid, parent_condition_uuid) for reconnection"
    )

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]
    ]:
        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"Antimagic Suppression stores {self.suppressed_condition.name}"
        )
        return [], [], [], [], effect_event

    def _remove(self, event: Optional[Event] = None) -> Optional[Event]:
        """Re-add the suppressed condition when the marker is removed."""
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        cond = self.suppressed_condition
        if target and target.is_active and not cond.duration.is_expired:
            # Check if parent still alive (concentration not broken while suppressed)
            if self.saved_parent_link:
                _, parent_cond_uuid = self.saved_parent_link
                parent_cond = BaseObject.get(parent_cond_uuid)
                if not isinstance(parent_cond, BaseCondition) or not parent_cond.applied:
                    return super()._remove(event)

            # Clear stale tracking from previous application
            cond.modifers_uuids.clear()
            cond.event_handlers_uuids.clear()
            cond.spatial_handler_uuids.clear()
            cond.sub_conditions.clear()
            cond.linked_conditions.clear()

            target.add_condition(cond, parent_event=event)

            # Reconnect parent_link if parent still exists
            if self.saved_parent_link and cond.applied:
                _, parent_cond_uuid = self.saved_parent_link
                parent_cond = BaseObject.get(parent_cond_uuid)
                if isinstance(parent_cond, BaseCondition) and parent_cond.applied:
                    parent_cond.add_linked_condition(target.uuid, cond.uuid)

        return super()._remove(event)


class AntimagicFieldZone(BaseCondition):
    """Zone condition for Antimagic Field, applied to the caster.

    Creates a 10ft sphere that follows the caster. Within the sphere:
    - All spells are blocked (caster included)
    - New magical conditions are blocked
    - Existing magical conditions are suppressed (removed, restored on leaving)

    Uses manual marker tracking (not linked_conditions) to control cleanup order.
    """
    name: str = "Antimagic Field Zone"
    description: str = "10ft sphere suppresses all magic"
    condition_category: ConditionCategory = ConditionCategory.STATUS
    tags: Set[ConditionTag] = Field(default_factory=lambda: {ConditionTag.MAGICAL})

    zone_center: Tuple[int, int] = Field(default=(0, 0))
    zone_radius_feet: int = Field(default=10)
    affected_positions: Set[Tuple[int, int]] = Field(default_factory=set)

    # entity_uuid → [marker condition UUIDs]
    suppression_markers: Dict[UUID, List[UUID]] = Field(default_factory=dict)

    model_config = {"arbitrary_types_allowed": True}

    def _compute_positions(self) -> Set[Tuple[int, int]]:
        """Compute positions in the 10ft radius sphere around center."""
        shape = Sphere(
            source_entity_uuid=self.source_entity_uuid,
            target=self.zone_center,
            radius_feet=self.zone_radius_feet
        )
        shape.compute_objective(self.zone_center)
        return set(shape.affected_positions)

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]
    ]:
        self.affected_positions = self._compute_positions()
        handler_uuids: List[UUID] = []

        # Handler 1: Block all spells (cast from/targeting inside zone)
        blocker = self._create_spell_blocker()
        EventQueue.add_event_handler(blocker)
        handler_uuids.append(blocker.uuid)

        # Handler 2: Follow caster
        follow = self._create_follow_caster_handler()
        EventQueue.add_event_handler(follow)
        handler_uuids.append(follow.uuid)

        # Handler 3: Entity enters zone → suppress magical conditions
        entry = self._create_entity_entry_handler()
        EventQueue.add_event_handler(entry)
        handler_uuids.append(entry.uuid)

        # Handler 4: Entity leaves zone → restore suppressed conditions
        exit_handler = self._create_entity_exit_handler()
        EventQueue.add_event_handler(exit_handler)
        handler_uuids.append(exit_handler.uuid)

        # Register with SpellProtectionRegistry (blocks zone spells from crossing in)
        SpellProtectionRegistry.register(SpellProtection(
            uuid=self.uuid,
            positions=set(self.affected_positions),
            max_blocked_level=9,  # Blocks all spell levels
        ))

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            status_message="Antimagic Field active"
        )

        # Suppress existing magical conditions on entities in zone
        grid = get_map()
        for pos in self.affected_positions:
            for entity_uuid in grid.get_entities_at(pos):
                self._suppress_entity(entity_uuid, parent_event=effect_event)

        return [], handler_uuids, [], [], effect_event

    def cleanup_own_state(self, expire: bool = False, parent_event: Optional[Event] = None) -> bool:
        """Override to control cleanup order: disable handlers, unsuppress, then standard cleanup."""
        if not self.applied:
            return False

        # 1. Disable all handlers so condition blocker can't interfere with re-adds
        for handler_uuid in self.event_handlers_uuids:
            handler = BaseObject.get(handler_uuid)
            if isinstance(handler, BaseHandler):
                handler.enabled = False

        # 2. Unregister spell protection
        SpellProtectionRegistry.unregister(self.uuid)

        # 3. Unsuppress all entities (markers removed → conditions restored)
        self._unsuppress_all_entities(parent_event=parent_event)

        # 4. Standard cleanup (removes disabled handlers, sets applied=False)
        return super().cleanup_own_state(expire=expire, parent_event=parent_event)

    # ---- Suppression logic ----

    def _suppress_entity(self, entity_uuid: UUID, parent_event: Optional[Event] = None) -> None:
        """Suppress all top-level magical conditions on an entity."""
        entity = Entity.get(entity_uuid)
        if not entity:
            return

        # Collect top-level magical conditions to suppress
        to_suppress: List[BaseCondition] = []
        for cond in list(entity.active_conditions.values()):
            if not cond.magical_origin:
                continue
            if cond.parent_condition is not None:
                continue  # Sub-condition, will be handled by parent's removal
            if cond.name == "Concentrating":
                continue  # Don't suppress Concentrating itself
            if cond.uuid == self.uuid:
                continue  # Don't suppress ourselves
            if not cond.applied:
                continue
            to_suppress.append(cond)

        for cond in to_suppress:
            if not cond.applied:
                continue  # May have been removed as sub-condition of a previous suppress

            # Save parent_link before detaching
            saved_parent_link: Optional[Tuple[UUID, UUID]] = None
            if cond.parent_link:
                saved_parent_link = cond.parent_link
                _, parent_cond_uuid = cond.parent_link
                parent_cond = BaseObject.get(parent_cond_uuid)
                if isinstance(parent_cond, BaseCondition):
                    # Remove from parent's linked_conditions list
                    parent_cond.linked_conditions = [
                        lc for lc in parent_cond.linked_conditions
                        if lc[1] != cond.uuid
                    ]
                cond.parent_link = None

            # Special-case: HasteEffect → disable lethargy on suppression removal
            if isinstance(cond, HasteEffect):
                cond.apply_lethargy = False

            # Full removal via standard path
            assert cond.name is not None
            entity.remove_condition(cond.name, parent_event=parent_event)

            # Re-enable lethargy for when condition is restored
            if isinstance(cond, HasteEffect):
                cond.apply_lethargy = True

            # Create suppression marker (unique name per suppressed condition)
            marker = AntimagicSuppression(
                name=f"Antimagic Suppression: {cond.name}",
                source_entity_uuid=type_cast(UUID, self.source_entity_uuid),
                target_entity_uuid=entity.uuid,
                suppressed_condition=cond,
                saved_parent_link=saved_parent_link
            )
            entity.add_condition(marker, parent_event=parent_event)

            if marker.applied:
                if entity.uuid not in self.suppression_markers:
                    self.suppression_markers[entity.uuid] = []
                self.suppression_markers[entity.uuid].append(marker.uuid)

    def _unsuppress_entity(self, entity_uuid: UUID, parent_event: Optional[Event] = None) -> None:
        """Remove all suppression markers from an entity, restoring conditions."""
        marker_uuids = self.suppression_markers.pop(entity_uuid, [])
        entity = Entity.get(entity_uuid)
        if not entity:
            return

        for marker_uuid in list(marker_uuids):
            entity.remove_condition_by_uuid(marker_uuid, parent_event=parent_event)

    def _unsuppress_all_entities(self, parent_event: Optional[Event] = None) -> None:
        """Unsuppress all tracked entities."""
        for entity_uuid in list(self.suppression_markers.keys()):
            self._unsuppress_entity(entity_uuid, parent_event=parent_event)

    # ---- Handler factories ----

    def _create_spell_blocker(self) -> EventHandler:
        """Block ALL spells when caster or target is in the zone."""
        zone = self

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            if not isinstance(event, SpellEvent):
                return None

            # Check if source is in the zone
            source = Entity.get(event.source_entity_uuid)
            if source and source.position in zone.affected_positions:
                return event.cancel(
                    status_message=f"Antimagic Field blocks {event.name}"
                )

            # Check if target entity is in the zone
            if event.target_entity_uuid:
                target = Entity.get(event.target_entity_uuid)
                if target and target.position in zone.affected_positions:
                    return event.cancel(
                        status_message=f"Antimagic Field blocks {event.name}"
                    )

            return None

        return EventHandler(
            name="Antimagic Spell Blocker",
            source_entity_uuid=type_cast(UUID, self.source_entity_uuid),
            trigger_conditions=[Trigger(
                event_type=EventType.CAST_SPELL,
                event_phase=EventPhase.EXECUTION
            )],
            event_processor=processor
        )

    def _create_follow_caster_handler(self) -> EventHandler:
        """Move zone to follow caster, suppress/unsuppress entity deltas."""
        caster_uuid = type_cast(UUID, self.source_entity_uuid)
        zone = self

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            if not isinstance(event, SpatialChangeEvent) or event.entity_uuid != caster_uuid:
                return None

            old_positions = set(zone.affected_positions)
            zone.zone_center = event.position
            new_positions = zone._compute_positions()
            zone.affected_positions = new_positions

            # Update SpellProtectionRegistry
            SpellProtectionRegistry.unregister(zone.uuid)
            SpellProtectionRegistry.register(SpellProtection(
                uuid=zone.uuid,
                positions=set(new_positions),
                max_blocked_level=9,
            ))

            # Entities that left the zone: unsuppress
            grid = get_map()
            left_positions = old_positions - new_positions
            for pos in left_positions:
                for entity_uuid in grid.get_entities_at(pos):
                    if entity_uuid in zone.suppression_markers:
                        zone._unsuppress_entity(entity_uuid, parent_event=event)

            # Entities that entered the zone: suppress
            entered_positions = new_positions - old_positions
            for pos in entered_positions:
                for entity_uuid in grid.get_entities_at(pos):
                    if entity_uuid != caster_uuid:
                        zone._suppress_entity(entity_uuid, parent_event=event)

            return None

        return EventHandler(
            name="Antimagic Follow Caster",
            source_entity_uuid=caster_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.SPATIAL_ENTITY_ENTERED,
                event_phase=EventPhase.EFFECT
            )],
            event_processor=processor
        )

    def _create_entity_entry_handler(self) -> EventHandler:
        """Suppress magical conditions when an entity enters the zone."""
        caster_uuid = type_cast(UUID, self.source_entity_uuid)
        zone = self

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            if not isinstance(event, SpatialChangeEvent) or not event.entity_uuid:
                return None
            # Skip caster (follow handler handles caster movement)
            if event.entity_uuid == caster_uuid:
                return None
            if event.position not in zone.affected_positions:
                return None
            zone._suppress_entity(event.entity_uuid, parent_event=event)
            return None

        return EventHandler(
            name="Antimagic Entry Suppress",
            source_entity_uuid=caster_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.SPATIAL_ENTITY_ENTERED,
                event_phase=EventPhase.EFFECT
            )],
            event_processor=processor
        )

    def _create_entity_exit_handler(self) -> EventHandler:
        """Restore suppressed conditions when an entity leaves the zone."""
        caster_uuid = type_cast(UUID, self.source_entity_uuid)
        zone = self

        def processor(event: Event, _source_entity_uuid: UUID) -> Optional[Event]:
            if not isinstance(event, SpatialChangeEvent) or not event.entity_uuid:
                return None
            if event.entity_uuid == caster_uuid:
                return None
            if event.entity_uuid in zone.suppression_markers:
                zone._unsuppress_entity(event.entity_uuid, parent_event=event)
            return None

        return EventHandler(
            name="Antimagic Exit Restore",
            source_entity_uuid=caster_uuid,
            trigger_conditions=[Trigger(
                event_type=EventType.SPATIAL_ENTITY_LEFT,
                event_phase=EventPhase.EFFECT
            )],
            event_processor=processor
        )


class AntimagicField(SpellAction):
    """Antimagic Field - 8th level Abjuration (Concentration)

    A 10-foot-radius invisible sphere of antimagic surrounds you. This area
    is divorced from the magical energy that suffuses the multiverse. Within
    the sphere, spells can't be cast, summoned creatures disappear, and even
    magic items become mundane.

    The sphere moves with the caster. Spells and magical effects are suppressed
    in the sphere and can't protrude into it. Slots expended to cast suppressed
    spells are consumed.
    """
    name: str = Field(default="Antimagic Field")
    description: str = Field(default="10ft sphere suppresses all magic, concentration")
    spell_level: int = Field(default=8)
    spell_school: str = Field(default="abjuration")
    concentration: bool = Field(default=True)
    target_type: TargetType = Field(default=TargetType.SELF)
    spell_range: Range = Field(default_factory=lambda: Range(type=RangeType.SELF))

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return declaration_event.cancel(status_message="Caster not found")
        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated {self.name}"
        )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return execution_event.cancel(status_message="Caster not found")

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"{caster.name} casts Antimagic Field"
        )

        zone = AntimagicFieldZone(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid,
            zone_center=caster.senses.position
        )
        caster.add_condition(zone, parent_event=effect_event)

        concentration = self.ensure_concentration(effect_event)
        if zone.applied:
            concentration.add_linked_condition(caster.uuid, zone.uuid)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            total_damage=0,
            status_message=f"Antimagic Field active around {caster.name}"
        )
