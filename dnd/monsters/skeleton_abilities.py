"""Skeleton-specific ability conditions and actions."""

from typing import Any, List, Optional, Tuple
from uuid import UUID

from pydantic import Field

from dnd.core.base_actions import (
    BaseAction,
    TargetType,
    Cost,
)
from dnd.core.events.action_events import (
    ActionEvent,
)
from dnd.core.base_conditions import BaseCondition
from dnd.types.conditions import ConditionCategory
from dnd.core.events.events_registry import (
    Event,
    EventPhase,
)
from dnd.core.events.resolution_events import (
    RangeType,
    Range,
)
from dnd.core.modifiers import AdvantageModifier
from dnd.types.rolls import AdvantageStatus
from dnd.entity import Entity
from dnd.actions.standard import (
    entity_action_economy_cost_evaluator,
)
from dnd.conditions import Concentrating


class Marked(BaseCondition):
    """Target marker applied by a skeleton archer.

    The condition strips existing Invisible and Hidden states, grants attackers
    advantage against the marked target, and blocks future Invisible or Hidden
    applications while the mark remains active.

    Attributes:
        name: Condition registry key.
        description: Player-facing summary.
        condition_category: Classification used by condition filtering.
        creation_lineage_uuid: Event lineage that created this condition.
    """
    name: str = Field(default="Marked", description="Condition registry key.")
    description: str = Field(
        default="Marked by an archer. Attackers have advantage, cannot hide or turn invisible.",
        description="Player-facing summary for the marked condition.",
    )
    condition_category: ConditionCategory = Field(
        default=ConditionCategory.CONDITION,
        description="Classification used by condition filtering.",
    )

    creation_lineage_uuid: Optional[UUID] = Field(
        default=None,
        description="Lineage UUID of the event that created this condition.",
    )

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]
    ]:
        """Apply marker modifiers and stealth-blocking immunities.

        Args:
            declaration_event: Condition declaration event to advance or cancel.

        Returns:
            Condition bookkeeping with the completed effect event.
        """
        if not self.target_entity_uuid:
            return [], [], [], [], declaration_event.cancel(status_message="Target UUID not set")
        target = Entity.get(self.target_entity_uuid)
        if not target or not isinstance(target, Entity):
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        outs: List[Tuple[UUID, UUID]] = []

        target_uuid: UUID = self.target_entity_uuid
        source_uuid: UUID = self.source_entity_uuid

        if "Invisible" in target.active_conditions:
            target.remove_condition("Invisible", parent_event=declaration_event)
        if "Hidden" in target.active_conditions:
            target.remove_condition("Hidden", parent_event=declaration_event)

        modifier = AdvantageModifier(
            name="Marked",
            value=AdvantageStatus.ADVANTAGE,
            source_entity_uuid=target_uuid,
            target_entity_uuid=source_uuid,
        )
        mod_uuid = target.equipment.ac_bonus.to_target_static.add_advantage_modifier(modifier)
        outs.append((target.equipment.ac_bonus.uuid, mod_uuid))

        target.add_condition_immunity("Invisible", immunity_name="Marked")
        target.add_condition_immunity("Hidden", immunity_name="Marked")

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            update={"condition": self},
            status_message=f"{target.name} is marked",
        )

        return outs, [], [], [], effect_event

    def _release_owned_runtime_state(
        self,
        *,
        parent_event: Optional[Event] = None,
    ) -> None:
        """Release marker immunities on removal or failed application."""
        del parent_event
        if self.target_entity_uuid:
            target = Entity.get(self.target_entity_uuid)
            if target and isinstance(target, Entity):
                target._remove_static_condition_immunity("Invisible", "Marked")
                target._remove_static_condition_immunity("Hidden", "Marked")


class MarkCooldown(BaseCondition):
    """Internal marker that prevents repeated Mark Target use.

    Attributes:
        name: Condition registry key.
        description: Internal summary.
        condition_category: Internal condition classification.
    """
    name: str = Field(default="Mark Cooldown", description="Condition registry key.")
    description: str = Field(default="Mark Target has been used", description="Internal cooldown summary.")
    condition_category: ConditionCategory = Field(
        default=ConditionCategory.INTERNAL,
        description="Internal condition classification.",
    )

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]
    ]:
        """Advance the cooldown application to effect.

        Args:
            declaration_event: Condition declaration event.

        Returns:
            Empty condition bookkeeping with the effect event.
        """
        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            update={"condition": self},
            status_message="Mark Cooldown applied",
        )
        return [], [], [], [], effect_event


class MarkTargetAction(BaseAction):
    """Bonus-action marking ability for skeleton archers.

    The action marks one visible enemy within 60 feet, starts concentration on
    the archer, links the target condition to that concentration, and applies a
    cooldown condition to prevent repeated use.

    Attributes:
        name: Action discovery and combat-log label.
        description: Player-facing summary.
        target_type: Target routing type.
        valid_target_filter: Relationship filter for action discovery.
        spell_range: Range used by validation.
        costs: Runtime action-economy costs.
    """
    name: str = Field(default="Mark Target", description="Action discovery and combat-log label.")
    description: str = Field(
        default="Mark an enemy (60ft). Attackers gain advantage, target can't hide. Concentration.",
        description="Player-facing summary for the Mark Target action.",
    )
    target_type: TargetType = Field(default=TargetType.ENTITY, description="Target routing type.")
    valid_target_filter: str = Field(default="enemies", description="Relationship filter for action discovery.")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=60),
        description="Range used by Mark Target validation.",
    )
    costs: List[Cost] = Field(default_factory=list, description="Runtime action-economy costs.")

    def model_post_init(self, __context: Any) -> None:
        """Install the default bonus-action cost when none is provided.

        Args:
            __context: Pydantic post-init context.
        """
        super().model_post_init(__context)
        if not self.costs:
            self.costs = [
                Cost(
                    name="Mark Target",
                    cost_type="bonus_actions",
                    cost=1,
                    evaluator=entity_action_economy_cost_evaluator,
                )
            ]

    def get_range(self) -> Range:
        """Return Mark Target's validation range.

        Returns:
            Configured Mark Target range.
        """
        return self.spell_range

    def _validate(self, declaration_event: ActionEvent) -> Optional[ActionEvent]:
        """Validate Mark Target range and line of sight.

        Args:
            declaration_event: Action declaration event to advance or cancel.

        Returns:
            Execution event when the target is visible and in range, otherwise a
            canceled event.
        """
        source = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not source or not target:
            return declaration_event.cancel(status_message="Source or target not found")

        if "Mark Cooldown" in source.active_conditions:
            return declaration_event.cancel(
                status_message="Mark Target is unavailable until the cooldown ends"
            )

        if target.uuid not in source.senses.entities:
            return declaration_event.cancel(status_message="Target not in line of sight")

        distance = source.distance_to_entity(target)
        if distance > self.spell_range.normal:
            return declaration_event.cancel(
                status_message=f"Target out of range ({distance}ft > {self.spell_range.normal}ft)"
            )

        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated {self.name}",
        )

    def _apply(self, execution_event: ActionEvent) -> Optional[ActionEvent]:
        """Apply Mark Target's concentration, linked mark, and cooldown.

        Args:
            execution_event: Validated execution event.

        Returns:
            Completion event when the mark is applied, otherwise a canceled
            event.
        """
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        concentration = Concentrating(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid,
            spell_name="Mark Target",
        )
        caster.add_condition(concentration, parent_event=execution_event)

        marked = Marked(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            creation_lineage_uuid=execution_event.lineage_uuid,
        )
        target.add_condition(marked, parent_event=execution_event)

        concentration.add_linked_condition(target.uuid, marked.uuid)

        cooldown = MarkCooldown(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid,
        )
        caster.add_condition(cooldown, parent_event=execution_event)

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"{caster.name} marks {target.name}",
        )

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"{caster.name} marks {target.name} (concentration)",
        )
