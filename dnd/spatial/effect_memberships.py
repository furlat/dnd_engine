"""Reusable exact source memberships for occupant-facing spatial effects."""

from typing import Any, List, Optional, Tuple
from uuid import UUID

from pydantic import Field, PrivateAttr

from dnd.core.base_conditions import BaseCondition
from dnd.types.conditions import ConditionCategory, ConditionTag
from dnd.core.events.events_registry import (
    Event,
    EventPhase,
)
from dnd.types.spatial_effects import SpatialEffectTriggerKind
from dnd.entity import Entity
from dnd.spatial.effect_controllers import AreaSpatialEffectController


class SpatialEffectMembershipSource(BaseCondition):
    """Internal lease owning one public manifestation from one exact effect."""

    name: str = Field(default="Spatial Effect Membership")
    description: str = Field(
        default="Tracks one exact source effect's membership on a creature.",
    )
    condition_category: ConditionCategory = Field(
        default=ConditionCategory.INTERNAL,
        frozen=True,
    )
    source_effect_uuid: UUID = Field(
        description="Exact spatial effect whose membership this condition owns.",
    )

    def model_post_init(self, context: object) -> None:
        """Give simultaneous source memberships collision-free private names."""
        super().model_post_init(context)
        self.name = f"{type(self).__name__}:{self.source_effect_uuid}"

    def create_manifestation(self, target: Entity) -> BaseCondition:
        """Build the player-facing condition manifested by this source."""
        raise NotImplementedError

    def after_manifestation_added(
        self,
        target: Entity,
        manifestation: BaseCondition,
    ) -> None:
        """Install optional source-owned actions after the child is admitted."""
        del target, manifestation

    def _apply(
        self,
        declaration_event: Event,
    ) -> Tuple[
        List[Tuple[UUID, UUID]],
        List[UUID],
        List[UUID],
        List[UUID],
        Optional[Event],
    ]:
        if self.target_entity_uuid is None:
            return [], [], [], [], declaration_event.cancel(
                status_message="Spatial membership target is absent",
            )
        target = Entity.get(self.target_entity_uuid)
        if target is None:
            return [], [], [], [], declaration_event.cancel(
                status_message="Spatial membership target is unavailable",
            )
        manifestation = self.create_manifestation(target)
        result = target.add_condition(
            manifestation,
            parent_event=declaration_event,
        )
        if result is None or result.canceled:
            return [], [], [], [], declaration_event.cancel(
                status_message="Spatial membership manifestation was rejected",
            )
        self.after_manifestation_added(target, manifestation)
        effect_event = declaration_event.phase_to(
            EventPhase.EFFECT,
            update={"condition": self},
            status_message=(
                f"{target.name} enters an exact spatial-effect membership"
            ),
        )
        return [], [], [manifestation.uuid], [], effect_event


def find_spatial_effect_membership(
    entity: Entity,
    *,
    effect_uuid: UUID,
    source_type: type[SpatialEffectMembershipSource],
) -> Optional[SpatialEffectMembershipSource]:
    """Return one exact typed membership without display-name lookup."""
    for condition in entity.active_conditions_by_uuid.values():
        if (
            isinstance(condition, source_type)
            and condition.source_effect_uuid == effect_uuid
        ):
            return condition
    return None


class SpatialMembershipAreaController(AreaSpatialEffectController):
    """Area controller owning exact per-effect membership conditions."""

    _membership_source_uuids: set[UUID] = PrivateAttr(default_factory=set)
    membership_trigger_kinds: frozenset[SpatialEffectTriggerKind] = frozenset()
    membership_tags: frozenset[ConditionTag] = frozenset({
        ConditionTag.MAGICAL,
    })

    def membership_source_class(
        self,
    ) -> type[SpatialEffectMembershipSource]:
        """Return the exact internal source type owned by this controller."""
        raise NotImplementedError

    def membership_source_kwargs(self) -> dict[str, Any]:
        """Return subclass-authored fields for a new membership source."""
        return {}

    def membership_applies_to(self, entity: Entity) -> bool:
        """Return whether this exact effect should manifest on one occupant."""
        del entity
        return True

    def _admit_trigger(
        self,
        trigger_kind: SpatialEffectTriggerKind,
        target_entity_uuid: UUID,
        event: Event,
    ) -> bool:
        """Maintain continuous membership before fencing repeat consequences."""
        if trigger_kind in self.membership_trigger_kinds:
            entity = Entity.get(target_entity_uuid)
            if entity is None or not self.membership_applies_to(entity):
                return False
            if self.apply_membership(entity, parent_event=event) is None:
                return False
        return super()._admit_trigger(
            trigger_kind,
            target_entity_uuid,
            event,
        )

    def find_membership(
        self,
        entity: Entity,
    ) -> Optional[SpatialEffectMembershipSource]:
        """Return this exact effect's membership on one creature."""
        if self.target_entity_uuid is None:
            raise RuntimeError("Membership controller has no spatial-effect owner")
        return find_spatial_effect_membership(
            entity,
            effect_uuid=self.target_entity_uuid,
            source_type=self.membership_source_class(),
        )

    def apply_membership(
        self,
        entity: Entity,
        *,
        parent_event: Event,
    ) -> Optional[SpatialEffectMembershipSource]:
        """Apply one independent source membership if it is not already live."""
        existing = self.find_membership(entity)
        if existing is not None:
            return existing
        if self.target_entity_uuid is None:
            raise RuntimeError("Membership controller has no spatial-effect owner")
        membership = self.membership_source_class()(
            source_entity_uuid=self.source_entity_uuid,
            target_entity_uuid=entity.uuid,
            source_effect_uuid=self.target_entity_uuid,
            tags=set(self.membership_tags),
            **self.membership_source_kwargs(),
        )
        result = entity.add_condition(membership, parent_event=parent_event)
        if result is None or result.canceled:
            return None
        self._membership_source_uuids.add(membership.uuid)
        return membership

    def remove_membership(
        self,
        entity: Entity,
        *,
        parent_event: Optional[Event],
    ) -> bool:
        """Remove only this exact effect's membership from one creature."""
        membership = self.find_membership(entity)
        if membership is None:
            return False
        removed = entity.remove_condition_by_uuid(
            membership.uuid,
            parent_event=parent_event,
        )
        if removed:
            self._membership_source_uuids.discard(membership.uuid)
        return removed

    def _remove_all_memberships(
        self,
        parent_event: Optional[Event],
    ) -> None:
        """Release every membership even after forced movement left the area."""
        for membership_uuid in tuple(self._membership_source_uuids):
            membership = BaseCondition.get(membership_uuid)
            if not isinstance(membership, SpatialEffectMembershipSource):
                self._membership_source_uuids.discard(membership_uuid)
                continue
            if membership.target_entity_uuid is None:
                self._membership_source_uuids.discard(membership_uuid)
                continue
            entity = Entity.get(membership.target_entity_uuid)
            if entity is not None:
                entity.remove_condition_by_uuid(
                    membership_uuid,
                    parent_event=parent_event,
                )
            self._membership_source_uuids.discard(membership_uuid)

    def _remove(self, event: Optional[Event] = None) -> Optional[Event]:
        """Release memberships before shared area mechanics retire."""
        self._remove_all_memberships(event)
        return super()._remove(event)
