"""Abjuration spells - protection and defense.

Contains: MageArmor, ProtectionFromEnergy, Stoneskin
"""
from typing import Optional, List, Tuple
from uuid import UUID

from pydantic import Field

from dnd.core.base_actions import TargetType
from dnd.core.base_conditions import BaseCondition
from dnd.core.events import Event, EventPhase, EventType, EventHandler, Trigger, RangeType, Range
from dnd.core.modifiers import DamageType, ResistanceModifier, ResistanceStatus

from dnd.actions import SpellAction, SpellEvent


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

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], Optional[Event]]:
        from dnd.entity import Entity
        from dnd.blocks.equipment import UnarmoredAc, ArmorEquipEvent

        if not self.target_entity_uuid:
            raise ValueError("Target entity UUID is not set")

        target_entity = Entity.get(self.target_entity_uuid)
        if not target_entity:
            return [], [], [], declaration_event.cancel(status_message=f"Target entity {self.target_entity_uuid} not found")

        if not isinstance(target_entity, Entity):
            return [], [], [], declaration_event.cancel(status_message=f"Target is not an Entity")

        # Check if target is wearing armor - Mage Armor doesn't work on armored targets
        if not target_entity.equipment.is_unarmored():
            return [], [], [], declaration_event.cancel(status_message="Target is wearing armor - Mage Armor has no effect")

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
                entity.remove_condition("Mage Armor")
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

        return outs, handler_uuids, [], effect_event

    def _remove(self, _removal_event: Optional[Event] = None) -> None:
        """Restore the old unarmored AC type on removal."""
        from dnd.entity import Entity
        from dnd.blocks.equipment import UnarmoredAc

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
        from dnd.entity import Entity

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
            if distance > self.spell_range.normal:
                return declaration_event.cancel(status_message=f"Target out of range ({distance}ft > {self.spell_range.normal}ft)")

        # Check if target is wearing armor
        if not target_entity.equipment.is_unarmored():
            return declaration_event.cancel(status_message="Target is wearing armor")

        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated {self.name}"
        )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Apply Mage Armor condition to target."""
        from dnd.entity import Entity
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
        result = target.add_condition(condition)
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
    via the Concentrating condition's external_conditions mechanism.
    """
    name: str = "Protection from Energy"
    description: str = "Resistant to one energy type"

    # The chosen energy type (set by spell)
    energy_type: DamageType = DamageType.FIRE

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], Optional[Event]]:
        from dnd.entity import Entity

        if not self.target_entity_uuid:
            return [], [], [], declaration_event.cancel(status_message="Target entity UUID not set")

        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], declaration_event.cancel(status_message="Target not found")

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

        return outs, [], [], effect_event


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
        from dnd.entity import Entity

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
            if distance > self.spell_range.normal:
                return declaration_event.cancel(
                    status_message=f"Target out of range ({distance}ft > {self.spell_range.normal}ft)"
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
        from dnd.entity import Entity
        from dnd.conditions import Concentrating

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
        caster.add_condition(concentration)

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
        target.add_condition(protection)

        # 3. Link via external_conditions for cleanup
        concentration.add_external_condition(target.uuid, protection.uuid)

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

    def _apply(self, declaration_event: Event) -> Tuple[List[Tuple[UUID, UUID]], List[UUID], List[UUID], Optional[Event]]:
        from dnd.entity import Entity

        if not self.target_entity_uuid:
            return [], [], [], declaration_event.cancel(status_message="Target entity UUID not set")

        target = Entity.get(self.target_entity_uuid)
        if not target:
            return [], [], [], declaration_event.cancel(status_message="Target not found")

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

        return outs, [], [], effect_event


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
        from dnd.entity import Entity

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
            if distance > self.spell_range.normal:
                return declaration_event.cancel(
                    status_message=f"Target out of range ({distance}ft > {self.spell_range.normal}ft)"
                )

        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated {self.name}"
        )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Apply Stoneskin - grants B/P/S resistance."""
        from dnd.entity import Entity
        from dnd.conditions import Concentrating

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
        caster.add_condition(concentration)

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"Concentrating on {self.name}"
        )

        # 2. Apply stoneskin effect to target
        stoneskin = StoneskinEffect(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid
        )
        target.add_condition(stoneskin)

        # 3. Link via external_conditions for cleanup
        concentration.add_external_condition(target.uuid, stoneskin.uuid)

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"{self.name} cast on {target.name}"
        )
