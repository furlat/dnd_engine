"""Stateless direct reactions between independent spatial conditions."""

from collections.abc import Callable
from typing import Optional, Set, Tuple
from uuid import UUID

from dnd.core.content.recipes import ContentRecipe
from dnd.core.content.spatial_effect_definitions import (
    SpatialEffectTransitionDefinition,
)
from dnd.core.events import (
    Event,
    EventHandler,
    EventPhase,
    EventQueue,
    EventType,
    SpatialEffectInteractionEvent,
    Trigger,
)
from dnd.spatial.area_conditions import SpatialCondition
from dnd.types.spatial_effects import (
    SpatialEffectInteractionIntensity,
    SpatialEffectTransitionAction,
)


ReplacementBuilder = Callable[
    [ContentRecipe, SpatialCondition, SpatialEffectInteractionEvent, Set[Tuple[int, int]]],
    SpatialCondition,
]

_INTENSITY_ORDER = {
    SpatialEffectInteractionIntensity.MINOR: 0,
    SpatialEffectInteractionIntensity.MODERATE: 1,
    SpatialEffectInteractionIntensity.STRONG: 2,
}


def apply_spatial_interaction(
    *,
    condition: SpatialCondition,
    event: SpatialEffectInteractionEvent,
    transitions: tuple[SpatialEffectTransitionDefinition, ...],
    build_replacement: Optional[ReplacementBuilder] = None,
) -> None:
    """Apply the strongest admitted authored row to intersecting cells."""
    affected = set(event.positions) & condition.affected_positions
    if not affected:
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
        key=lambda candidate: _INTENSITY_ORDER[candidate.minimum_intensity],
    )
    if transition.delay_rounds is not None:
        condition.schedule_retirement(transition.delay_rounds)
        return
    if transition.action is SpatialEffectTransitionAction.REMOVE_AFFECTED:
        remaining = condition.affected_positions - affected
        if remaining:
            condition.change_footprint(remaining, parent_event=event)
        else:
            condition.deactivate(parent_event=event)
        return

    recipe = transition.replacement_recipe
    if recipe is None or build_replacement is None:
        raise RuntimeError("Replacement transition has no direct builder")
    replacement = build_replacement(recipe, condition, event, affected)
    if (
        transition.action
        is SpatialEffectTransitionAction.REMOVE_AFFECTED_AND_CREATE_SECONDARY
    ):
        activation = replacement.activate(parent_event=event)
        if activation is None or activation.canceled or not replacement.applied:
            return
        remaining = condition.affected_positions - affected
        if remaining:
            condition.change_footprint(remaining, parent_event=event)
        else:
            condition.deactivate(parent_event=event)
        return

    replacement.activate(
        parent_event=event,
        replacing_condition_uuid=condition.uuid,
    )


def bind_spatial_interactions(
    *,
    condition: SpatialCondition,
    transitions: tuple[SpatialEffectTransitionDefinition, ...],
    build_replacement: Optional[ReplacementBuilder] = None,
) -> EventHandler:
    """Install one position-indexed handler owned by a concrete condition."""
    if not transitions:
        raise ValueError("Spatial interaction binding requires transition rows")

    def react(
        event: Event,
        _source_entity_uuid: UUID,
    ) -> Optional[Event]:
        if isinstance(event, SpatialEffectInteractionEvent):
            apply_spatial_interaction(
                condition=condition,
                event=event,
                transitions=transitions,
                build_replacement=build_replacement,
            )
        return None

    handler = EventHandler(
        name=f"{condition.name} Environmental Reactions",
        source_entity_uuid=condition.source_entity_uuid,
        trigger_conditions=[
            Trigger(
                event_type=EventType.SPATIAL_EFFECT_INTERACTION,
                event_phase=EventPhase.EFFECT,
            ),
        ],
        event_processor=react,
    )
    EventQueue.add_spatial_handler(
        handler,
        set(condition.affected_positions),
        EventType.SPATIAL_EFFECT_INTERACTION,
        EventPhase.EFFECT,
    )
    return handler


__all__ = [
    "ReplacementBuilder",
    "apply_spatial_interaction",
    "bind_spatial_interactions",
]
