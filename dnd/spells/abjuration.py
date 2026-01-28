"""Abjuration spells - protection and defense.

Contains: MageArmor
"""
from typing import Optional

from pydantic import Field

from dnd.core.base_actions import TargetType
from dnd.core.events import EventPhase, RangeType, Range

from dnd.actions import SpellAction, SpellEvent


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
        from dnd.conditions import MageArmorCondition

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
