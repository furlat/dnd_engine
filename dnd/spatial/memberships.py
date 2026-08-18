"""Exact source memberships for occupant-facing spatial conditions."""

from typing import Any, List, Optional, Set, Tuple
from uuid import UUID

from pydantic import Field

from dnd.core.base_conditions import BaseCondition
from dnd.types.conditions import ConditionCategory, ConditionTag
from dnd.core.events.events_registry import (
    Event,
    EventPhase,
)
from dnd.types.spatial_effects import SpatialEffectTriggerKind
from dnd.entities.entity import Entity
from dnd.spatial.area_conditions import AreaCondition


class SpatialConditionMembershipSource(BaseCondition):
    """Internal lease owning one public manifestation from one condition."""

    name: str = Field(default="Spatial Condition Membership")
    description: str = Field(
        default="Tracks one exact spatial condition on a creature.",
    )
    condition_category: ConditionCategory = Field(
        default=ConditionCategory.INTERNAL,
        frozen=True,
    )
    source_spatial_condition_uuid: UUID = Field(
        description="Exact spatial condition whose membership this lease owns.",
    )

    def model_post_init(self, context: object) -> None:
        """Give simultaneous source memberships collision-free private names."""
        super().model_post_init(context)
        self.name = f"{type(self).__name__}:{self.source_spatial_condition_uuid}"

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


def find_spatial_condition_membership(
    entity: Entity,
    *,
    spatial_condition_uuid: UUID,
    source_type: type[SpatialConditionMembershipSource],
) -> Optional[SpatialConditionMembershipSource]:
    """Return one exact typed membership without display-name lookup."""
    for condition in entity.active_conditions_by_uuid.values():
        if (
            isinstance(condition, source_type)
            and condition.source_spatial_condition_uuid == spatial_condition_uuid
        ):
            return condition
    return None


class MembershipAreaCondition(AreaCondition):
    """Area condition owning exact per-source occupant memberships."""

    membership_trigger_kinds: frozenset[SpatialEffectTriggerKind] = frozenset()
    membership_tags: frozenset[ConditionTag] = frozenset({
        ConditionTag.MAGICAL,
    })

    def membership_source_class(
        self,
    ) -> type[SpatialConditionMembershipSource]:
        """Return the exact internal source type owned by this condition."""
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
    ) -> Optional[SpatialConditionMembershipSource]:
        """Return this exact condition's membership on one creature."""
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
        """Apply one independent source membership if it is not already live."""
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
        """Remove only this exact effect's membership from one creature."""
        membership = self.find_membership(entity)
        if membership is None:
            return False
        return entity.remove_condition_by_uuid(
            membership.uuid,
            parent_event=parent_event,
        )

    def _remove_all_memberships(
        self,
        parent_event: Optional[Event],
    ) -> None:
        """Release every membership even after forced movement left the area."""
        for owner_uuid, membership_uuid in tuple(self.linked_conditions):
            membership = BaseCondition.get(membership_uuid)
            if membership is None:
                self.unlink_runtime_child(membership_uuid)
                continue
            if not isinstance(membership, SpatialConditionMembershipSource):
                continue
            entity = Entity.get(owner_uuid)
            if entity is None:
                continue
            if entity.remove_condition_by_uuid(
                membership_uuid,
                parent_event=parent_event,
            ):
                continue
            raise RuntimeError("Spatial membership rejected owner removal")

    def _release_memberships_from_positions(
        self,
        positions: Set[Tuple[int, int]],
        *,
        parent_event: Optional[Event],
    ) -> None:
        """Release memberships whose creatures are in removed footprint cells."""
        retained = self.affected_positions - positions
        for owner_uuid, membership_uuid in tuple(self.linked_conditions):
            membership = BaseCondition.get(membership_uuid)
            if membership is None:
                self.unlink_runtime_child(membership_uuid)
                continue
            if not isinstance(membership, SpatialConditionMembershipSource):
                continue
            entity = Entity.get(owner_uuid)
            if (
                entity is not None
                and entity.position in positions
                and entity.position not in retained
            ):
                if not self.remove_membership(
                    entity,
                    parent_event=parent_event,
                ):
                    raise RuntimeError(
                        "Spatial membership rejected footprint replacement",
                    )

    def _release_positions(self, positions: Set[Tuple[int, int]]) -> None:
        """Release memberships and positional mechanics during ordinary moves."""
        self._release_memberships_from_positions(
            positions,
            parent_event=None,
        )
        super()._release_positions(positions)

    def _release_positions_for_replacement(
        self,
        positions: Set[Tuple[int, int]],
    ) -> None:
        """Keep eventful memberships until replacement admission succeeds."""
        super()._release_positions(positions)

    def _finalize_replaced_positions(
        self,
        positions: Set[Tuple[int, int]],
        *,
        parent_event: Event,
    ) -> None:
        """Retire memberships from cells committed to another condition."""
        self._release_memberships_from_positions(
            positions,
            parent_event=parent_event,
        )

    def _release_owned_runtime_state(
        self,
        *,
        parent_event: Optional[Event] = None,
    ) -> None:
        """Release memberships only after removal reaches its accepted effect."""
        self._remove_all_memberships(parent_event)
        super()._release_owned_runtime_state(parent_event=parent_event)
