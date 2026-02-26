"""Abjuration spells - protection and defense.

Contains: Shield, MageArmor, ProtectionFromEnergy, Stoneskin
"""
from typing import Optional, List, Tuple
from uuid import UUID

from pydantic import Field

from dnd.core.base_actions import TargetType, spell_slot_cost_type
from dnd.core.base_conditions import BaseCondition, ConditionCategory
from dnd.core.events import Event, EventPhase, EventType, EventHandler, Trigger, RangeType, Range
from dnd.core.modifiers import DamageType, ResistanceModifier, ResistanceStatus, NumericalModifier
from dnd.blocks.equipment import UnarmoredAc, ArmorEquipEvent

from dnd.core.dice import AttackOutcome
from dnd.entity import Entity
from dnd.actions import SpellAction, SpellEvent, AttackEvent
from dnd.conditions import Concentrating


def _is_magic_missile_damage(event: Event) -> bool:
    """Check if a TakeDamageEvent originates from Magic Missile by tracing parent events."""
    from dnd.core.events import EventQueue
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
        from dnd.core.modifiers import AutoHitStatus
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
        concentration = Concentrating(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid,
            spell_name="Protection from Energy"
        )
        caster.add_condition(concentration, parent_event=execution_event)

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
        concentration = Concentrating(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid,
            spell_name="Stoneskin"
        )
        caster.add_condition(concentration, parent_event=execution_event)

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
        concentration.add_linked_condition(target.uuid, stoneskin.uuid)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"{self.name} cast on {target.name}"
        )
