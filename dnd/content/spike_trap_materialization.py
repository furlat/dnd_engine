"""Canonical materialization seams for authored environmental spatial effects."""

from typing import Optional, Set, Tuple
from uuid import UUID, uuid4

from dnd.content.spatial_effect_materialization import (
    materialize_spatial_effect,
)
from dnd.core.events.events_registry import (
    Event,
    EventPhase,
    EventQueue,
    EventType,
)
from dnd.spatial.environmental_effects import (
    SpikeTrapController,
    SpikeTrapGroundEffect,
)
from dnd.content.spatial_effect_recipes import spike_trap_effect_recipe


def _begin_environment_effect_event(
    source_entity_uuid: UUID,
    *,
    name: str,
) -> Event:
    """Begin one root lifecycle while an authored environment effect installs."""
    declaration = Event(
        name=name,
        source_entity_uuid=source_entity_uuid,
        source_entity_name="Environment",
        event_type=EventType.BASE_ACTION,
        phase=EventPhase.DECLARATION,
        use_register=False,
    )
    accepted = EventQueue.publish_declaration(declaration)
    if accepted.canceled:
        raise RuntimeError(f"{name} declaration was canceled")
    execution = accepted.phase_to(EventPhase.EXECUTION)
    if execution.canceled:
        raise RuntimeError(f"{name} execution was canceled")
    effect = execution.phase_to(EventPhase.EFFECT)
    if effect.canceled:
        raise RuntimeError(f"{name} effect was canceled")
    return effect


def materialize_spike_trap_effect(
    positions: Set[Tuple[int, int]],
    *,
    stealth_dc: Optional[int] = None,
    source_entity_uuid: Optional[UUID] = None,
    parent_event: Optional[Event] = None,
) -> SpikeTrapGroundEffect:
    """Materialize and install one exact physical spike-trap network."""
    if not positions:
        raise ValueError("Spike trap effect requires at least one position")
    source_uuid = source_entity_uuid or uuid4()
    owns_root_event = parent_event is None
    causal_event = parent_event or _begin_environment_effect_event(
        source_uuid,
        name="Install Spike Trap",
    )
    effect = materialize_spatial_effect(
        spike_trap_effect_recipe(stealth_dc=stealth_dc),
        source_uuid,
        position=min(positions),
        faction=None,
        expected_type=SpikeTrapGroundEffect,
    )
    result = effect.install_default_controller(
        positions=set(positions),
        duration_rounds=None,
        parent_event=causal_event,
    )
    if result is None or result.canceled:
        raise RuntimeError("Spike trap controller installation failed")
    if owns_root_event:
        completed = causal_event.phase_to(EventPhase.COMPLETION)
        if completed.canceled:
            raise RuntimeError("Spike trap installation did not complete")
    return effect


def extend_spike_trap_effect(
    effect: SpikeTrapGroundEffect,
    positions: Set[Tuple[int, int]],
    *,
    source_entity_uuid: Optional[UUID] = None,
) -> SpikeTrapGroundEffect:
    """Extend an installed trap network under one causal lifecycle."""
    if not positions:
        return effect
    controller = effect.active_conditions.get("Spike Trap")
    if not isinstance(controller, SpikeTrapController):
        raise RuntimeError("Spike trap effect has no active controller")
    causal_event = _begin_environment_effect_event(
        source_entity_uuid or effect.source_entity_uuid,
        name="Extend Spike Trap",
    )
    controller.extend_footprint(positions, parent_event=causal_event)
    completed = causal_event.phase_to(EventPhase.COMPLETION)
    if completed.canceled:
        raise RuntimeError("Spike trap extension did not complete")
    return effect


__all__ = [
    "extend_spike_trap_effect",
    "materialize_spike_trap_effect",
]
