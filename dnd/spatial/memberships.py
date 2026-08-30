"""Exact occupant memberships owned by independent spatial conditions."""

from typing import Any, Optional, Set, Tuple
from uuid import UUID

from pydantic import Field

from dnd.core.base_conditions import BaseCondition
from dnd.core.condition_types import ConditionCategory, ConditionTag
from dnd.core.events import (
    Event,
    EventHandler,
    EventPhase,
    EventType,
    SpatialChangeEvent,
    SpatialEffectChangeEvent,
    Trigger,
)
from dnd.entity import Entity
from dnd.spatial.area_conditions import AreaCondition
from dnd.types.spatial_effects import SpatialEffectTriggerKind


class SpatialConditionMembershipSource(BaseCondition):
    """One internal creature condition leased by one spatial owner."""

    name: str = Field(default="Spatial Condition Membership")
    description: str = Field(
        default="Tracks one exact spatial condition on one creature.",
    )
    condition_category: ConditionCategory = Field(
        default=ConditionCategory.INTERNAL,
        frozen=True,
    )
    source_spatial_condition_uuid: UUID

    def model_post_init(self, context: object) -> None:
        """Keep simultaneous source memberships distinct by owner UUID."""
        super().model_post_init(context)
        self.name = f"{type(self).__name__}:{self.source_spatial_condition_uuid}"

    def create_manifestation(self, target: Entity) -> BaseCondition:
        """Build the public condition represented by this source lease."""
        raise NotImplementedError

    def after_manifestation_added(
        self,
        target: Entity,
        manifestation: BaseCondition,
    ) -> None:
        """Allow concrete sources to install their source-owned actions."""
        del target, manifestation

    def _apply(
        self,
        execution_event: Event,
    ) -> Tuple[list[Tuple[UUID, UUID]], list[UUID], list[UUID], list[UUID], Event]:
        """Apply the source lease and its direct public child condition."""
        if self.target_entity_uuid is None:
            return [], [], [], [], execution_event.cancel(
                status_message="Spatial membership target is absent",
            )
        target = Entity.get(self.target_entity_uuid)
        if not isinstance(target, Entity):
            return [], [], [], [], execution_event.cancel(
                status_message="Spatial membership target is unavailable",
            )
        manifestation = self.create_manifestation(target)
        manifestation.parent_condition = self.uuid
        result = target.add_condition(
            manifestation,
            parent_event=execution_event,
        )
        if result is None or result.canceled:
            return [], [], [], [], execution_event.cancel(
                status_message="Spatial membership manifestation was rejected",
            )
        self.after_manifestation_added(target, manifestation)
        effect = execution_event.phase_to(
            EventPhase.EFFECT,
            update={"condition": self},
        )
        return [], [], [manifestation.uuid], [], effect


def find_spatial_condition_membership(
    entity: Entity,
    *,
    spatial_condition_uuid: UUID,
    source_type: type[SpatialConditionMembershipSource],
) -> Optional[SpatialConditionMembershipSource]:
    """Resolve one exact membership without display-name lookup."""
    for condition in entity.active_conditions_by_uuid.values():
        if (
            isinstance(condition, source_type)
            and condition.source_spatial_condition_uuid == spatial_condition_uuid
        ):
            return condition
    return None


class MembershipAreaCondition(AreaCondition):
    """Area condition owning one exact source lease per occupant."""

    membership_trigger_kinds: frozenset[SpatialEffectTriggerKind] = frozenset()
    membership_tags: frozenset[ConditionTag] = frozenset({ConditionTag.MAGICAL})

    def membership_source_class(
        self,
    ) -> type[SpatialConditionMembershipSource]:
        raise NotImplementedError

    def membership_source_kwargs(self) -> dict[str, Any]:
        return {}

    def membership_applies_to(self, entity: Entity) -> bool:
        del entity
        return True

    def find_membership(
        self,
        entity: Entity,
    ) -> Optional[SpatialConditionMembershipSource]:
        """Return this condition's exact source lease on an occupant."""
        return find_spatial_condition_membership(
            entity,
            spatial_condition_uuid=self.uuid,
            source_type=self.membership_source_class(),
        )

    def apply_membership(
        self,
        entity: Entity,
        *,
        parent_event: Event,
    ) -> Optional[SpatialConditionMembershipSource]:
        """Apply one source lease, or return the already-live lease."""
        existing = self.find_membership(entity)
        if existing is not None:
            return existing
        membership = self.membership_source_class()(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=entity.uuid,
            source_spatial_condition_uuid=self.uuid,
            tags=set(self.membership_tags),
            **self.membership_source_kwargs(),
        )
        result = entity.add_condition(membership, parent_event=parent_event)
        if result is None or result.canceled:
            return None
        self.add_linked_condition(entity.uuid, membership.uuid)
        return membership

    def remove_membership(
        self,
        entity: Entity,
        *,
        parent_event: Optional[Event],
    ) -> bool:
        """Remove only this spatial owner's source lease."""
        membership = self.find_membership(entity)
        if membership is None:
            return False
        return entity.remove_condition_by_uuid(
            membership.uuid,
            parent_event=parent_event,
        )

    def _admit_trigger(
        self,
        kind: SpatialEffectTriggerKind,
        target_entity_uuid: UUID,
        event: Event,
    ) -> bool:
        """Maintain continuous membership before repeat-effect admission."""
        if kind in self.membership_trigger_kinds:
            entity = Entity.get(target_entity_uuid)
            if (
                not isinstance(entity, Entity)
                or not self.membership_applies_to(entity)
                or self.apply_membership(entity, parent_event=event) is None
            ):
                return False
        return super()._admit_trigger(kind, target_entity_uuid, event)

    def _create_zone_entry_handler(self) -> EventHandler:
        """Use admission itself to install the exact membership."""
        def membership_admitted(
            _event: Event,
            _source_uuid: UUID,
        ) -> Optional[Event]:
            return None

        return EventHandler(
            name=f"{self.name} Membership Entry",
            source_entity_uuid=self.source_entity_uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.SPATIAL_ENTITY_ENTERED,
                    event_phase=EventPhase.EFFECT,
                ),
            ],
            event_processor=membership_admitted,
        )

    def _create_zone_exit_handler(self) -> EventHandler:
        """Remove this exact membership when its occupant leaves."""
        condition = self

        def remove_departing_membership(
            event: Event,
            _source_uuid: UUID,
        ) -> Optional[Event]:
            if not isinstance(event, SpatialChangeEvent):
                return None
            if event.old_position in condition.affected_positions:
                return None
            entity_uuid = event.entity_uuid
            entity = Entity.get(entity_uuid) if entity_uuid is not None else None
            if isinstance(entity, Entity):
                condition.remove_membership(entity, parent_event=event)
            return None

        return EventHandler(
            name=f"{self.name} Membership Exit",
            source_entity_uuid=self.source_entity_uuid,
            trigger_conditions=[
                Trigger(
                    event_type=EventType.SPATIAL_ENTITY_LEFT,
                    event_phase=EventPhase.EFFECT,
                ),
            ],
            event_processor=remove_departing_membership,
        )

    def _apply_appearance_effect(
        self,
        entity: Entity,
        *,
        parent_event: Event,
    ) -> None:
        """Membership admission already performed the appearance work."""
        del entity, parent_event

    def _change_footprint(
        self,
        positions: Set[Tuple[int, int]],
        *,
        parent_event: Event,
    ) -> Optional[SpatialEffectChangeEvent]:
        """Release excluded memberships under the footprint-change effect."""
        removed = self.affected_positions - set(positions)
        retained = self.affected_positions & set(positions)
        change_effect = super()._change_footprint(
            positions,
            parent_event=parent_event,
        )
        if change_effect is None:
            return None
        for entity in self._occupants_at(removed):
            if entity.position not in retained:
                self.remove_membership(entity, parent_event=change_effect)
        return change_effect

    def _release_positions(
        self,
        positions: Set[Tuple[int, int]],
        *,
        parent_event: Event,
    ) -> None:
        """Release exact occupant leases after a successful displacement."""
        for entity in self._occupants_at(positions):
            self.remove_membership(entity, parent_event=parent_event)
        super()._release_positions(positions, parent_event=parent_event)


__all__ = [
    "MembershipAreaCondition",
    "SpatialConditionMembershipSource",
    "find_spatial_condition_membership",
]
