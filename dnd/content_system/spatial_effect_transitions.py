"""Frozen content-authenticated transition authority for spatial effects."""

from __future__ import annotations

from uuid import UUID

from dnd.content_system.spatial_effect_registry_materialization import (
    materialize_spatial_effect_from_registry,
)
from dnd.core.content.registry import FrozenContentRegistry
from dnd.core.events import EventQueue
from dnd.core.spatial_effect_runtime import SpatialEffectInteractionContext
from dnd.core.spatial_effect_types import (
    SpatialEffectChangeOperation,
    SpatialEffectInteractionIntensity,
    SpatialEffectTransitionAction,
)
from dnd.spatial_effects import SpatialEffect


_INTENSITY_ORDER = {
    SpatialEffectInteractionIntensity.MINOR: 0,
    SpatialEffectInteractionIntensity.MODERATE: 1,
    SpatialEffectInteractionIntensity.STRONG: 2,
}


class FrozenSpatialEffectInteractionGateway:
    """Resolve exact authored transition rows against the active world index."""

    def __init__(self, registry: FrozenContentRegistry) -> None:
        self._registry = registry

    def apply(
        self,
        effect_uuid: UUID,
        context: SpatialEffectInteractionContext,
    ) -> None:
        """Apply the strongest admitted rule to the intersecting effect cells."""
        effect = SpatialEffect.get_effect(effect_uuid)
        if effect is None:
            return
        affected_positions = set(context.positions) & effect.affected_positions
        if not affected_positions:
            return

        declaration = self._registry.resolve_definition(effect.content_ref)
        definition = declaration.spatial_effect_definition
        if definition is None:
            raise ValueError(
                f"Active effect {effect.content_ref.identity_key} has no "
                "spatial-effect definition",
            )
        admitted = tuple(
            transition
            for transition in definition.transitions
            if (
                transition.operation is context.operation
                and _INTENSITY_ORDER[context.intensity]
                >= _INTENSITY_ORDER[transition.minimum_intensity]
            )
        )
        if not admitted:
            return
        transition = max(
            admitted,
            key=lambda candidate: _INTENSITY_ORDER[
                candidate.minimum_intensity
            ],
        )
        parent_event = EventQueue.get_event_by_uuid(context.parent_event_uuid)
        if parent_event is None:
            raise ValueError("Spatial interaction parent event is not registered")

        if transition.delay_rounds is not None:
            effect.schedule_retirement(
                transition.delay_rounds,
                parent_event=parent_event,
            )
            return

        remaining = effect.affected_positions - affected_positions
        if remaining:
            effect.transition_footprint(
                remaining,
                parent_event=parent_event,
            )
        else:
            effect.retire(
                parent_event=parent_event,
                operation=SpatialEffectChangeOperation.TRANSFORMED,
            )

        if transition.action is SpatialEffectTransitionAction.REMOVE_AFFECTED:
            return

        replacement_recipe = transition.replacement_recipe
        if replacement_recipe is None:
            raise AssertionError("replace transition lost replacement recipe")
        replacement = materialize_spatial_effect_from_registry(
            replacement_recipe,
            parent_event.source_entity_uuid,
            position=min(affected_positions),
            faction=effect.faction,
            registry=self._registry,
        )
        replacement.install_default_controller(
            positions=affected_positions,
            duration_rounds=context.duration_rounds,
            parent_event=parent_event,
        )


__all__ = ["FrozenSpatialEffectInteractionGateway"]
