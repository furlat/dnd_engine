"""Reusable source ownership for spatial effects that restrain creatures."""

from typing import Any, ClassVar, List, Optional, Tuple
from uuid import UUID

from pydantic import Field

from dnd.actions.standard import (
    entity_action_economy_cost_evaluator,
)
from dnd.conditions import Restrained
from dnd.core.events.action_events import (
    ActionEvent,
    BaseCost,
)
from dnd.core.base_actions import (
    BaseAction,
    Cost,
    TargetType,
)
from dnd.core.base_conditions import BaseCondition
from dnd.types.conditions import ConditionTag
from dnd.types.abilities import AbilityName
from dnd.core.events.events_registry import (
    Event,
    EventPhase,
)
from dnd.entity import Entity
from dnd.spatial.effect_memberships import (
    SpatialEffectMembershipSource,
    SpatialMembershipAreaController,
    find_spatial_effect_membership,
)


class EscapeSpatialRestraintAction(BaseAction):
    """Base action for an exact ability check against one restraint source."""

    name: str = Field(default="Escape Restraint")
    description: str = Field(
        default="Use an action to attempt to escape one restraining effect.",
    )
    target_type: TargetType = Field(default=TargetType.SELF)
    restraint_source_uuid: UUID = Field(
        description="Exact source-membership condition removed on success.",
    )
    check_dc: int = Field(ge=0, description="Ability-check DC of this source.")
    ability_name: AbilityName = Field(
        default=AbilityName.STRENGTH,
        description="Raw ability used for this escape option.",
    )
    costs: List[Cost] = Field(
        default_factory=lambda: [
            Cost(
                name="Escape Restraint Cost",
                cost_type="actions",
                cost=1,
                evaluator=entity_action_economy_cost_evaluator,
            ),
        ],
    )

    def _create_declaration_event(
        self,
        parent_event: Optional[Event] = None,
        use_register: bool = True,
    ) -> ActionEvent:
        actor = Entity.get(self.source_entity_uuid)
        return ActionEvent(
            name=self.name,
            description=self.description,
            parent_event=parent_event.uuid if parent_event else None,
            phase=EventPhase.DECLARATION,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.source_entity_uuid,
            costs=[BaseCost.model_validate(cost) for cost in self.costs],
            use_register=use_register,
            source_entity_name=actor.name if actor else None,
        )

    def _source_membership(
        self,
        actor: Entity,
    ) -> Optional["SpatialRestraintSource"]:
        condition = actor.active_conditions_by_uuid.get(
            self.restraint_source_uuid,
        )
        if not isinstance(condition, SpatialRestraintSource):
            return None
        if condition.target_entity_uuid != actor.uuid:
            return None
        return condition

    def _validate(self, declaration_event: ActionEvent) -> ActionEvent:
        actor = Entity.get(self.source_entity_uuid)
        if actor is None:
            return declaration_event.cancel(status_message="Entity not found")
        if self._source_membership(actor) is None:
            return declaration_event.cancel(
                status_message="Restraining source is no longer active",
            )
        return declaration_event.phase_to(
            EventPhase.EXECUTION,
            status_message=f"Validated {self.name}",
        )

    def _apply(self, execution_event: ActionEvent) -> ActionEvent:
        actor = Entity.get(self.source_entity_uuid)
        if actor is None:
            return execution_event.cancel(status_message="Entity not found")
        membership = self._source_membership(actor)
        if membership is None:
            return execution_event.cancel(
                status_message="Restraining source is no longer active",
            )

        request = actor.create_ability_check_request(
            target_entity_uuid=actor.uuid,
            ability_name=self.ability_name,
            dc=self.check_dc,
            parent_event=execution_event.uuid,
        )
        _, roll, success, check_effect = actor.ability_check_effect(request)
        if success:
            actor.remove_condition_by_uuid(
                membership.uuid,
                parent_event=check_effect,
            )
        check_effect.phase_to(
            EventPhase.COMPLETION,
            dice_roll=roll,
            result=success,
            status_message=(
                f"{actor.name} {'escapes' if success else 'remains restrained'}"
            ),
        )
        return execution_event.phase_to(
            EventPhase.COMPLETION,
            status_message=(
                f"{actor.name} {'escapes' if success else 'fails to escape'} "
                f"using {self.ability_name}"
            ),
        )


class SpatialRestraintSource(SpatialEffectMembershipSource):
    """Internal source lease that owns one restraint and its escape actions."""

    name: str = Field(default="Spatial Restraint Source")
    description: str = Field(
        default="Tracks one independent spatial source of restraint.",
    )
    check_dc: int = Field(ge=0, description="Escape DC authored by the source.")
    restraint_potency: Tuple[int, ...] = Field(
        min_length=1,
        description="Strength rank used by the shared Restrained manifestation.",
    )
    escape_action_types: ClassVar[
        tuple[type[EscapeSpatialRestraintAction], ...]
    ] = ()

    def create_manifestation(self, target: Entity) -> BaseCondition:
        """Create the shared public Restrained manifestation."""
        return Restrained(
            source_entity_uuid=self.source_effect_uuid,
            target_entity_uuid=target.uuid,
            parent_condition=self.uuid,
            potency_rank=self.restraint_potency,
            tags={ConditionTag.MAGICAL},
        )

    def after_manifestation_added(
        self,
        target: Entity,
        manifestation: BaseCondition,
    ) -> None:
        """Register escape actions owned by this exact source membership."""
        del manifestation
        for action_type in self.escape_action_types:
            target.register_condition_action(
                self,
                action_type(
                    source_entity_uuid=target.uuid,
                    target_entity_uuid=target.uuid,
                    restraint_source_uuid=self.uuid,
                    check_dc=self.check_dc,
                    template=True,
                ),
            )


def find_spatial_restraint_source(
    entity: Entity,
    *,
    effect_uuid: UUID,
    source_type: type[SpatialRestraintSource],
) -> Optional[SpatialRestraintSource]:
    """Return one exact typed restraint membership without display-name lookup."""
    membership = find_spatial_effect_membership(
        entity,
        effect_uuid=effect_uuid,
        source_type=source_type,
    )
    return (
        membership
        if isinstance(membership, SpatialRestraintSource)
        else None
    )


class RestrainingAreaSpatialEffectController(SpatialMembershipAreaController):
    """Area controller that owns independent per-target restraint sources."""

    restraint_source_type: ClassVar[type[SpatialRestraintSource]]

    def restraint_check_dc(self) -> int:
        """Return the exact escape DC for this controller."""
        raise NotImplementedError

    def restraint_potency(self) -> Tuple[int, ...]:
        """Rank the manifested restraint without allowing a weaker downgrade."""
        effect_level = (
            self.effect_origin.effective_spell_level
            if self.effect_origin is not None
            and self.effect_origin.effective_spell_level is not None
            else 0
        )
        return (self.restraint_check_dc(), effect_level)

    def membership_source_class(
        self,
    ) -> type[SpatialEffectMembershipSource]:
        """Use the restraint subtype as the generic membership factory."""
        return self.restraint_source_type

    def membership_source_kwargs(self) -> dict[str, Any]:
        """Supply exact DC and no-downgrade potency to the source lease."""
        return {
            "check_dc": self.restraint_check_dc(),
            "restraint_potency": self.restraint_potency(),
        }

    def find_restraint(
        self,
        entity: Entity,
    ) -> Optional[SpatialRestraintSource]:
        """Return this exact effect's membership on one creature."""
        membership = self.find_membership(entity)
        return (
            membership
            if isinstance(membership, SpatialRestraintSource)
            else None
        )

    def apply_restraint(
        self,
        entity: Entity,
        *,
        parent_event: Event,
    ) -> Optional[SpatialRestraintSource]:
        """Apply one independent source membership if it is not already live."""
        membership = self.apply_membership(entity, parent_event=parent_event)
        return (
            membership
            if isinstance(membership, SpatialRestraintSource)
            else None
        )

    def remove_restraint(
        self,
        entity: Entity,
        *,
        parent_event: Optional[Event],
    ) -> bool:
        """Remove only this exact effect's membership from one creature."""
        return self.remove_membership(entity, parent_event=parent_event)
