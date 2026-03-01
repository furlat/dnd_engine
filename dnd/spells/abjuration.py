"""Abjuration spells - protection and defense.

Contains: Shield, MageArmor, ProtectionFromEnergy, Stoneskin, Counterspell,
          LesserRestoration, GreaterRestoration
"""
import random
from typing import Optional, List, Tuple, cast as type_cast
from uuid import UUID

from pydantic import Field

from dnd.core.base_actions import TargetType, spell_slot_cost_type
from dnd.core.base_conditions import BaseCondition, ConditionCategory, ConditionApplicationEvent, SpellProtectionRegistry, SpellProtection
from dnd.core.base_object import BaseObject
from dnd.core.events import Event, EventPhase, EventType, EventHandler, Trigger, RangeType, Range, EventQueue, SpatialChangeEvent
from dnd.core.modifiers import DamageType, ResistanceModifier, ResistanceStatus, NumericalModifier, AutoHitStatus
from dnd.core.aoe import Sphere
from dnd.core.gridmap import get_map
from dnd.blocks.equipment import UnarmoredAc, ArmorEquipEvent

from dnd.core.dice import AttackOutcome
from dnd.entity import Entity
from dnd.actions import SpellAction, SpellEvent, AttackEvent
from dnd.conditions import Incapacitated
from dnd.spells.spell_utils import validate_line_of_sight


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
    magical_origin: bool = True

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
    magical_origin: bool = True

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
    magical_origin: bool = True

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
    magical_origin: bool = True

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
    magical_origin: bool = True

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
    magical_origin: bool = True

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
            magical_origin=True
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
