"""Frozen authored contracts for persistent spatial-condition reactions."""

from pydantic import BaseModel, ConfigDict, Field

from dnd.core.content.recipes import ContentRecipe
from dnd.types.spatial_effects import (
    SpatialEffectInteractionIntensity,
    SpatialEffectInteractionOperation,
    SpatialEffectTransitionAction,
)


class SpatialEffectTransitionDefinition(BaseModel):
    """One exact operation-to-transition row."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    operation: SpatialEffectInteractionOperation
    minimum_intensity: SpatialEffectInteractionIntensity = (
        SpatialEffectInteractionIntensity.MINOR
    )
    action: SpatialEffectTransitionAction
    replacement_recipe: ContentRecipe | None = None
    delay_rounds: int | None = Field(default=None, ge=1)

    def model_post_init(self, context: object) -> None:
        """Require replacement data only for replacement-producing rows."""
        del context
        replacement_action = self.action in {
            SpatialEffectTransitionAction.REPLACE_AFFECTED,
            SpatialEffectTransitionAction.REMOVE_AFFECTED_AND_CREATE_SECONDARY,
        }
        if replacement_action and self.replacement_recipe is None:
            raise ValueError(
                "replacement-producing transition requires replacement_recipe",
            )
        if replacement_action and self.delay_rounds is not None:
            raise ValueError("replacement-producing transition cannot be delayed")
        if not replacement_action and self.replacement_recipe is not None:
            raise ValueError(
                "remove-affected transition cannot own replacement_recipe",
            )


__all__ = ["SpatialEffectTransitionDefinition"]
