"""Skeleton-specific abilities for specialized skeleton units.

Contains: Marked condition, MarkCooldown condition, MarkTargetAction.
"""

from typing import Any, Optional, List, Tuple
from uuid import UUID

from pydantic import Field

from dnd.core.base_actions import BaseAction, ActionEvent, TargetType, Cost
from dnd.core.base_conditions import (
    BaseCondition, ConditionCategory,
)
from dnd.core.events import (
    Event, EventPhase,
    RangeType, Range,
)
from dnd.core.modifiers import AdvantageModifier, AdvantageStatus
from dnd.entity import Entity
from dnd.actions import entity_action_economy_cost_evaluator, entity_action_economy_cost_applier
from dnd.conditions import Concentrating


# =============================================================================
# Mark Target Conditions
# =============================================================================

class Marked(BaseCondition):
    """Marked — target is marked by a skeleton archer.

    Effects:
    - Strips existing Invisible and Hidden conditions on application
    - Grants attackers advantage against the marked target
    - Prevents the target from gaining Invisible or Hidden while marked
    """
    name: str = "Marked"
    description: str = "Marked by an archer. Attackers have advantage, cannot hide or turn invisible."
    condition_category: ConditionCategory = ConditionCategory.CONDITION

    creation_lineage_uuid: Optional[UUID] = Field(
        default=None,
        description="Lineage UUID of the event that created this condition (prevents self-triggering)"
    )

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]
    ]:
        if not self.target_entity_uuid:
            return [], [], [], [], declaration_event.cancel(status_message="Target UUID not set")
        target = Entity.get(self.target_entity_uuid)
        if not target or not isinstance(target, Entity):
            return [], [], [], [], declaration_event.cancel(status_message="Target not found")

        outs: List[Tuple[UUID, UUID]] = []

        target_uuid: UUID = self.target_entity_uuid
        source_uuid: UUID = self.source_entity_uuid

        # 1. Strip existing Invisible and Hidden conditions
        if "Invisible" in target.active_conditions:
            target.remove_condition("Invisible", parent_event=declaration_event)
        if "Hidden" in target.active_conditions:
            target.remove_condition("Hidden", parent_event=declaration_event)

        # 2. Grant advantage to attackers via to_target_static on ac_bonus
        modifier = AdvantageModifier(
            name="Marked",
            value=AdvantageStatus.ADVANTAGE,
            source_entity_uuid=target_uuid,
            target_entity_uuid=source_uuid
        )
        mod_uuid = target.equipment.ac_bonus.to_target_static.add_advantage_modifier(modifier)
        outs.append((target.equipment.ac_bonus.uuid, mod_uuid))

        # 3. Add condition immunities to prevent future Invisible/Hidden
        target.add_condition_immunity("Invisible", immunity_name="Marked")
        target.add_condition_immunity("Hidden", immunity_name="Marked")

        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            update={"condition": self},
            status_message=f"{target.name} is marked"
        )

        return outs, [], [], [], effect_event

    def cleanup_own_state(self, expire: bool = False, parent_event: Optional[Event] = None) -> bool:
        """Remove condition immunities added by Marked, then do standard cleanup."""
        if self.target_entity_uuid:
            target = Entity.get(self.target_entity_uuid)
            if target and isinstance(target, Entity):
                target._remove_static_condition_immunity("Invisible", "Marked")
                target._remove_static_condition_immunity("Hidden", "Marked")
        return super().cleanup_own_state(expire=expire, parent_event=parent_event)


class MarkCooldown(BaseCondition):
    """Tracks that Mark Target has been used. Prevents reuse until short rest."""
    name: str = "Mark Cooldown"
    description: str = "Mark Target has been used"
    condition_category: ConditionCategory = ConditionCategory.INTERNAL

    def _apply(self, declaration_event: Event) -> Tuple[
        List[Tuple[UUID, UUID]], List[UUID], List[UUID], List[UUID], Optional[Event]
    ]:
        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            update={"condition": self},
            status_message="Mark Cooldown applied"
        )
        return [], [], [], [], effect_event


# =============================================================================
# Mark Target Action
# =============================================================================

class MarkTargetAction(BaseAction):
    """Mark Target — bonus action ability for Skeleton Archer.

    Marks a single target within 60ft, granting attackers advantage against it
    and preventing stealth. Requires concentration. One use per encounter
    (tracked via MarkCooldown condition).
    """
    name: str = Field(default="Mark Target")
    description: str = Field(default="Mark an enemy (60ft). Attackers gain advantage, target can't hide. Concentration.")
    target_type: TargetType = Field(default=TargetType.ENTITY)
    valid_target_filter: str = Field(default="enemies")
    spell_range: Range = Field(
        default_factory=lambda: Range(type=RangeType.RANGE, normal=60)
    )
    costs: List[Cost] = Field(default_factory=list)

    def model_post_init(self, __context: Any) -> None:
        super().model_post_init(__context)
        if not self.costs:
            self.costs = [Cost(
                name="Mark Target",
                cost_type="bonus_actions",
                cost=1,
                evaluator=entity_action_economy_cost_evaluator
            )]

    def get_range(self) -> Range:
        return self.spell_range

    def pre_validate(self) -> bool:
        """Returns False if caster already has Mark Cooldown (already used Mark)."""
        caster = Entity.get(self.source_entity_uuid)
        if not caster:
            return False
        if "Mark Cooldown" in caster.active_conditions:
            return False
        return True

    def _validate(self, declaration_event: ActionEvent) -> Optional[ActionEvent]:
        """Validate range and line of sight."""
        source = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not source or not target:
            return declaration_event.cancel(status_message="Source or target not found")

        # LOS check
        if target.uuid not in source.senses.entities:
            return declaration_event.cancel(status_message="Target not in line of sight")

        # Range check
        distance = source.senses.get_feet_distance(target.position)
        if distance > self.spell_range.normal:
            return declaration_event.cancel(
                status_message=f"Target out of range ({distance}ft > {self.spell_range.normal}ft)"
            )

        return declaration_event.phase_to(
            new_phase=EventPhase.EXECUTION,
            status_message=f"Validated {self.name}"
        )

    def _apply(self, execution_event: ActionEvent) -> Optional[ActionEvent]:
        """Apply Mark Target: mark the target, set up concentration."""
        caster = Entity.get(self.source_entity_uuid)
        target = Entity.get(self.target_entity_uuid) if self.target_entity_uuid else None

        if not caster or not target:
            return execution_event.cancel(status_message="Caster or target not found")

        # 1. Apply Concentrating on caster (breaks existing concentration)
        concentration = Concentrating(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid,
            spell_name="Mark Target"
        )
        caster.add_condition(concentration, parent_event=execution_event)

        # 2. Apply Marked condition on target
        marked = Marked(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=target.uuid,
            creation_lineage_uuid=execution_event.lineage_uuid
        )
        target.add_condition(marked, parent_event=execution_event)

        # 3. Link Concentrating → Marked (breaking concentration removes mark)
        concentration.add_linked_condition(target.uuid, marked.uuid)

        # 4. Apply cooldown on caster
        cooldown = MarkCooldown(
            source_entity_uuid=caster.uuid,
            target_entity_uuid=caster.uuid,
        )
        caster.add_condition(cooldown, parent_event=execution_event)

        effect_event = execution_event.phase_to(
            new_phase=EventPhase.EFFECT,
            status_message=f"{caster.name} marks {target.name}"
        )

        return effect_event.phase_to(
            new_phase=EventPhase.COMPLETION,
            status_message=f"{caster.name} marks {target.name} (concentration)"
        )

    def _apply_costs(self, completion_event: ActionEvent) -> Optional[ActionEvent]:
        """Apply bonus action cost."""
        return entity_action_economy_cost_applier(completion_event, self.source_entity_uuid)
