"""Dependency-neutral authored contracts for persistent spatial effects."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from dnd.core.content.recipes import ContentRecipe
from dnd.types.spatial_effects import (
    SpatialEffectAnchorKind,
    SpatialEffectBlockingPolicy,
    SpatialEffectInteractionIntensity,
    SpatialEffectInteractionOperation,
    SpatialEffectLayer,
    SpatialEffectOccupancyPolicy,
    SpatialEffectTriggerKind,
    SpatialEffectTransitionAction,
)


class SpatialEffectLifetimePolicy(str, Enum):
    """How an effect's independent lifetime is terminated."""

    CONTROLLER_DURATION = "controller_duration"
    PERMANENT_UNTIL_REMOVED = "permanent_until_removed"


class SpatialEffectTransitionDefinition(BaseModel):
    """One exact table-driven reaction owned by a spatial-effect definition."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    operation: SpatialEffectInteractionOperation
    minimum_intensity: SpatialEffectInteractionIntensity = (
        SpatialEffectInteractionIntensity.MINOR
    )
    action: SpatialEffectTransitionAction
    replacement_recipe: ContentRecipe | None = None
    delay_rounds: int | None = Field(default=None, ge=1)

    def model_post_init(self, __context: object) -> None:
        """Keep replacement payloads closed over the selected transition."""
        replacement = self.replacement_recipe
        if self.action in {
            SpatialEffectTransitionAction.REPLACE_AFFECTED,
            (
                SpatialEffectTransitionAction
                .REMOVE_AFFECTED_AND_CREATE_SECONDARY
            ),
        }:
            if replacement is None:
                raise ValueError(
                    "replacement-producing transition requires replacement_recipe",
                )
            replacement.verify_integrity()
            if self.delay_rounds is not None:
                raise ValueError(
                    "replacement-producing transition cannot be delayed",
                )
        elif replacement is not None:
            raise ValueError(
                "remove_affected transition cannot own replacement_recipe",
            )


class SpatialEffectDefinition(BaseModel):
    """Cold mechanics shared by every instance of one spatial phenomenon."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    anchor_kind: SpatialEffectAnchorKind = SpatialEffectAnchorKind.FIXED_POSITION
    layer: SpatialEffectLayer
    occupancy_policy: SpatialEffectOccupancyPolicy
    blocking_policy: SpatialEffectBlockingPolicy = (
        SpatialEffectBlockingPolicy.NONE
    )
    lifetime_policy: SpatialEffectLifetimePolicy
    trigger_kinds: frozenset[SpatialEffectTriggerKind] = frozenset()
    first_per_turn_trigger_kinds: frozenset[
        SpatialEffectTriggerKind
    ] = frozenset()
    transitions: tuple[SpatialEffectTransitionDefinition, ...] = ()

    @field_serializer(
        "trigger_kinds",
        "first_per_turn_trigger_kinds",
        when_used="always",
    )
    def _serialize_trigger_kinds(
        self,
        value: frozenset[SpatialEffectTriggerKind],
    ) -> tuple[str, ...]:
        """Authenticate unordered trigger membership in stable wire order."""
        return tuple(sorted(trigger.value for trigger in value))

    def model_post_init(self, __context: object) -> None:
        """Reject ambiguous operation/intensity transition rows."""
        if not self.first_per_turn_trigger_kinds.issubset(self.trigger_kinds):
            raise ValueError(
                "first-per-turn triggers must be declared trigger kinds",
            )
        keys = tuple(
            (transition.operation, transition.minimum_intensity)
            for transition in self.transitions
        )
        if len(keys) != len(set(keys)):
            raise ValueError("spatial-effect transitions must be unique")


__all__ = [
    "SpatialEffectDefinition",
    "SpatialEffectLifetimePolicy",
    "SpatialEffectTransitionDefinition",
]
