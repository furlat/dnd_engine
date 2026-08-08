"""Aegis Spark spell and condition extension content."""

from typing import Optional

from pydantic import Field

from dnd.actions import SpellAction, SpellEvent
from dnd.core.base_actions import TargetType
from dnd.core.base_conditions import BaseCondition
from dnd.core.condition_types import ConditionCategory
from dnd.core.events import Event, EventPhase, Range, RangeType
from dnd.core.modifiers import NumericalModifier
from dnd.entity import Entity


class AegisSparkEffect(BaseCondition):
    """Condition that grants a temporary Armor Class ward."""

    name: str = Field(default="Aegis Spark", description="Condition registry key.")
    description: str = Field(
        default="A visible ward that raises Armor Class.",
        description="Rules summary.",
    )
    condition_category: ConditionCategory = Field(
        default=ConditionCategory.CONDITION,
        description="Public condition category.",
    )
    armor_bonus: int = Field(default=2, description="Armor Class bonus while the ward is active.")

    def _apply(self, declaration_event: Event):
        """Apply the ward's Armor Class modifier.

        Args:
            declaration_event: Condition application event currently being resolved.

        Returns:
            Condition application tuple containing the owned Armor Class
            modifier and the effect event.
        """
        if self.target_entity_uuid is None:
            return [], [], [], [], declaration_event.cancel(status_message="Aegis Spark target missing")
        target = Entity.get(self.target_entity_uuid)
        if target is None:
            return [], [], [], [], declaration_event.cancel(status_message="Aegis Spark target not found")

        armor_modifier = NumericalModifier.create(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=target.uuid,
            name="Aegis Spark Armor",
            value=self.armor_bonus,
        )
        armor_uuid = target.equipment.ac_bonus.self_static.add_value_modifier(armor_modifier)

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            update={"condition": self},
            status_message=f"{target.name} gains Aegis Spark",
        )
        return [(target.equipment.ac_bonus.uuid, armor_uuid)], [], [], [], effect_event


class AegisSpark(SpellAction):
    """Cantrip that wards the caster or a visible ally."""

    name: str = Field(default="Aegis Spark", description="Action discovery label.")
    description: str = Field(
        default="Cantrip ward that grants +2 Armor Class to self or an ally.",
        description="Action summary.",
    )
    spell_level: int = Field(default=0, description="Cantrips use spell level 0.")
    spell_school: str = Field(default="abjuration", description="Protective magic belongs to abjuration.")
    target_type: TargetType = Field(default=TargetType.ENTITY, description="Aegis Spark targets one entity.")
    include_self: bool = Field(default=True, description="The caster may ward themself.")
    valid_target_filter: str = Field(default="self_or_allies", description="Only self and allies are valid targets.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=30),
        description="Range contract for the ward.",
    )

    def _validate(self, declaration_event: SpellEvent) -> Optional[SpellEvent]:
        """Validate range, visibility, and ally targeting.

        Args:
            declaration_event: Spell declaration event.

        Returns:
            Execution event when valid, or a canceled declaration event.
        """
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if caster is None or target is None:
            return declaration_event.cancel(status_message="Aegis Spark caster or target not found")
        if target.uuid != caster.uuid and target.uuid not in caster.senses.entities:
            return declaration_event.cancel(status_message="Aegis Spark target is not visible")
        if caster.distance_to_entity(target) > self.effective_range:
            return declaration_event.cancel(status_message="Aegis Spark target is out of range")
        if not caster.is_ally(target):
            return declaration_event.cancel(status_message="Aegis Spark can only target allies")
        return declaration_event.phase_to(
            EventPhase.EXECUTION,
            status_message=f"Validated {self.name}",
        )

    def _apply(self, execution_event: SpellEvent) -> Optional[SpellEvent]:
        """Apply the Aegis Spark condition to the selected target.

        Args:
            execution_event: Spell execution event.

        Returns:
            Completion event after the ward is applied.
        """
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None
        if caster is None or target is None:
            return execution_event.cancel(status_message="Aegis Spark caster or target not found")

        if "Aegis Spark" in target.active_conditions:
            target.remove_condition("Aegis Spark", parent_event=execution_event)
        target.add_condition(
            AegisSparkEffect(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid),
            parent_event=execution_event,
        )

        effect_event = execution_event.phase_to(
            EventPhase.EFFECT,
            status_message=f"{caster.name} wards {target.name}",
        )
        return effect_event.phase_to(
            EventPhase.COMPLETION,
            status_message=f"{target.name} is protected by Aegis Spark",
        )
