"""Stateless authored reactions between spatial conditions."""

from typing import Tuple

from dnd.core.content.spatial_effect_definitions import (
    SpatialEffectTransitionDefinition,
)
from dnd.core.events.world_events import SpatialEffectInteractionEvent
from dnd.spatial.area_conditions import ReplacementBuilder, SpatialCondition
from dnd.types.spatial_effects import (
    SpatialEffectChangeOperation,
    SpatialEffectInteractionIntensity,
    SpatialEffectTransitionAction,
)


_INTENSITY_ORDER = {
    SpatialEffectInteractionIntensity.MINOR: 0,
    SpatialEffectInteractionIntensity.MODERATE: 1,
    SpatialEffectInteractionIntensity.STRONG: 2,
}

def apply_spatial_interaction(
    condition: SpatialCondition,
    event: SpatialEffectInteractionEvent,
    transitions: Tuple[SpatialEffectTransitionDefinition, ...],
    build_replacement: ReplacementBuilder,
) -> None:
    """Apply the strongest authored row to the intersecting condition cells."""
    affected_positions = set(event.positions) & condition.affected_positions
    if not affected_positions:
        return
    admitted = tuple(
        transition
        for transition in transitions
        if transition.operation is event.operation
        and _INTENSITY_ORDER[event.intensity]
        >= _INTENSITY_ORDER[transition.minimum_intensity]
    )
    if not admitted:
        return
    transition = max(
        admitted,
        key=lambda candidate: _INTENSITY_ORDER[
            candidate.minimum_intensity
        ],
    )
    if transition.delay_rounds is not None:
        condition.schedule_retirement(transition.delay_rounds)
        return

    if transition.action is SpatialEffectTransitionAction.REMOVE_AFFECTED:
        remaining = condition.affected_positions - affected_positions
        if remaining:
            condition.transition_footprint(remaining, parent_event=event)
        else:
            condition.deactivate(
                parent_event=event,
                operation=SpatialEffectChangeOperation.TRANSFORMED,
            )
        return

    replacement_recipe = transition.replacement_recipe
    if replacement_recipe is None:
        raise RuntimeError("Replacement transition has no authored recipe")
    replacement = build_replacement(
        replacement_recipe,
        condition,
        event,
        affected_positions,
    )
    replacement.activate(
        parent_event=event,
        replacing_condition_uuid=condition.uuid,
    )


__all__ = ["apply_spatial_interaction"]
