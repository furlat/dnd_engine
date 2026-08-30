"""Exact restraint memberships owned by independent spatial conditions."""

from typing import ClassVar, List, Optional, Tuple
from uuid import UUID

from pydantic import Field

from dnd.actions import (
    entity_action_economy_cost_applier,
    entity_action_economy_cost_evaluator,
)
from dnd.conditions import Restrained
from dnd.core.base_actions import (
    ActionEvent,
    BaseAction,
    BaseCost,
    Cost,
    TargetType,
)
from dnd.core.base_conditions import BaseCondition
from dnd.core.condition_types import ConditionTag
from dnd.core.events import Event, EventPhase, SkillCheckEvent
from dnd.entity import Entity
from dnd.spatial.memberships import (
    MembershipAreaCondition,
    SpatialConditionMembershipSource,
)


class EscapeSpatialRestraintAction(BaseAction):
    """Action against one exact spatial restraint membership."""

    name: str = Field(default="Escape Restraint")
    description: str = Field(
        default="Use an action to attempt to escape one restraining effect.",
    )
    target_type: TargetType = Field(default=TargetType.SELF)
    restraint_source_uuid: UUID
    check_dc: int = Field(ge=0)
    skill_name: str = Field(default="athletics")
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

    def _source_membership(
        self,
        entity: Entity,
    ) -> Optional["SpatialRestraintSource"]:
        condition = entity.active_conditions_by_uuid.get(
            self.restraint_source_uuid,
        )
        if (
            not isinstance(condition, SpatialRestraintSource)
            or condition.target_entity_uuid != entity.uuid
        ):
            return None
        return condition

    def _create_declaration_event(
        self,
        parent_event: Optional[Event] = None,
        use_register: bool = True,
    ) -> ActionEvent:
        entity = Entity.get(self.source_entity_uuid)
        return ActionEvent(
            name=self.name,
            description=self.description,
            parent_event=parent_event.uuid if parent_event else None,
            phase=EventPhase.DECLARATION,
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=self.source_entity_uuid,
            costs=[BaseCost.model_validate(cost) for cost in self.costs],
            use_register=use_register,
            source_entity_name=entity.name if entity else None,
        )

    def _validate(self, declaration_event: ActionEvent) -> ActionEvent:
        entity = Entity.get(self.source_entity_uuid)
        if not isinstance(entity, Entity):
            return declaration_event.cancel(status_message="Entity not found")
        if self._source_membership(entity) is None:
            return declaration_event.cancel(
                status_message="Restraining source is no longer active",
            )
        return declaration_event.phase_to(
            EventPhase.EXECUTION,
            status_message=f"Validated {self.name}",
        )

    def _apply(self, execution_event: ActionEvent) -> ActionEvent:
        entity = Entity.get(self.source_entity_uuid)
        if not isinstance(entity, Entity):
            return execution_event.cancel(status_message="Entity not found")
        membership = self._source_membership(entity)
        if membership is None:
            return execution_event.cancel(
                status_message="Restraining source is no longer active",
            )
        check_event = SkillCheckEvent(
            source_entity_uuid=entity.uuid,
            target_entity_uuid=entity.uuid,
            skill_name=self.skill_name,
            dc=self.check_dc,
            source_entity_name=entity.name,
            parent_event=execution_event.uuid,
        )
        _, _, success = entity.skill_check(check_event)
        if success:
            entity.remove_condition_by_uuid(
                membership.uuid,
                parent_event=execution_event,
            )
        return execution_event.phase_to(
            EventPhase.EFFECT,
            status_message=(
                f"{entity.name} escapes {membership.name}"
                if success
                else f"{entity.name} fails to escape {membership.name}"
            ),
        )

    def _apply_costs(self, execution_event: ActionEvent) -> ActionEvent:
        return entity_action_economy_cost_applier(
            execution_event,
            self.source_entity_uuid,
        )


class SpatialRestraintSource(SpatialConditionMembershipSource):
    """One source lease sharing the public Restrained mechanics."""

    check_dc: int = Field(ge=0)
    restraint_manifestation_uuid: Optional[UUID] = Field(
        default=None,
        exclude=True,
    )
    escape_action_uuids: List[UUID] = Field(default_factory=list, exclude=True)
    escape_action_types: ClassVar[
        Tuple[type[EscapeSpatialRestraintAction], ...]
    ] = ()

    def create_manifestation(self, target: Entity) -> Restrained:
        return Restrained(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=target.uuid,
            tags={ConditionTag.MAGICAL},
        )

    @staticmethod
    def _find_manifestation(target: Entity) -> Optional[Restrained]:
        for condition in target.active_conditions_by_uuid.values():
            if isinstance(condition, Restrained):
                return condition
        return None

    def _other_sources(self, target: Entity) -> list["SpatialRestraintSource"]:
        return [
            condition
            for condition in target.active_conditions_by_uuid.values()
            if (
                isinstance(condition, SpatialRestraintSource)
                and condition.uuid != self.uuid
            )
        ]

    def _apply(
        self,
        execution_event: Event,
    ) -> Tuple[list[Tuple[UUID, UUID]], list[UUID], list[UUID], list[UUID], Event]:
        target = (
            Entity.get(self.target_entity_uuid)
            if self.target_entity_uuid is not None
            else None
        )
        if not isinstance(target, Entity):
            return [], [], [], [], execution_event.cancel(
                status_message="Spatial restraint target is unavailable",
            )

        manifestation = self._find_manifestation(target)
        other_sources = self._other_sources(target)
        if manifestation is None:
            manifestation = self.create_manifestation(target)
            applied = target.add_condition(
                manifestation,
                parent_event=execution_event,
            )
            if applied is None or applied.canceled:
                return [], [], [], [], execution_event.cancel(
                    status_message="Restrained manifestation was rejected",
                )
            self.restraint_manifestation_uuid = manifestation.uuid
        elif other_sources:
            self.restraint_manifestation_uuid = manifestation.uuid

        for action_type in self.escape_action_types:
            action = action_type(
                source_entity_uuid=target.uuid,
                target_entity_uuid=target.uuid,
                restraint_source_uuid=self.uuid,
                check_dc=self.check_dc,
                template=True,
            )
            target.register_action(action)
            self.escape_action_uuids.append(action.uuid)

        return [], [], [], [], execution_event.phase_to(
            EventPhase.EFFECT,
            update={"condition": self},
        )

    def _remove(self, event: Optional[Event] = None) -> Optional[Event]:
        target = (
            Entity.get(self.target_entity_uuid)
            if self.target_entity_uuid is not None
            else None
        )
        if not isinstance(target, Entity):
            return event
        for action_uuid in self.escape_action_uuids:
            target.unregister_action_by_uuid(action_uuid)
        self.escape_action_uuids.clear()
        if not self._other_sources(target):
            manifestation_uuid = self.restraint_manifestation_uuid
            if (
                manifestation_uuid is not None
                and manifestation_uuid in target.active_conditions_by_uuid
            ):
                target.remove_condition_by_uuid(
                    manifestation_uuid,
                    parent_event=event,
                )
        return event


class RestrainingAreaCondition(MembershipAreaCondition):
    """Area condition owning exact per-target restraint memberships."""

    restraint_source_type: ClassVar[type[SpatialRestraintSource]]

    def restraint_check_dc(self) -> int:
        raise NotImplementedError

    def membership_source_class(
        self,
    ) -> type[SpatialConditionMembershipSource]:
        return self.restraint_source_type

    def membership_source_kwargs(self) -> dict[str, object]:
        return {"check_dc": self.restraint_check_dc()}

    def find_restraint(
        self,
        entity: Entity,
    ) -> Optional[SpatialRestraintSource]:
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
        return self.remove_membership(entity, parent_event=parent_event)


__all__ = [
    "EscapeSpatialRestraintAction",
    "RestrainingAreaCondition",
    "SpatialRestraintSource",
]
