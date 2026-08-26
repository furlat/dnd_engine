"""Canonical materialization seams for authored environmental spatial effects."""

from typing import Optional, Set, Tuple
from uuid import UUID, uuid4

from dnd.content.spatial_effect_materialization import (
    materialize_spatial_condition,
)
from dnd.core.events.events_registry import (
    Event,
    EventPhase,
    EventQueue,
    EventType,
)
from dnd.spatial.environmental_conditions import SpikeTrap
from dnd.content.spatial_effect_recipes import SPIKE_TRAP_EFFECT_RECIPE


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


def materialize_spike_trap_condition(
    positions: Set[Tuple[int, int]],
    *,
    condition_uuid: Optional[UUID] = None,
    stealth_dc: Optional[int] = None,
    source_entity_uuid: Optional[UUID] = None,
    parent_event: Optional[Event] = None,
) -> SpikeTrap:
    """Materialize and install one exact physical spike-trap network."""
    if not positions:
        raise ValueError("Spike trap effect requires at least one position")
    source_uuid = source_entity_uuid or uuid4()
    owns_root_event = parent_event is None
    causal_event = parent_event or _begin_environment_effect_event(
        source_uuid,
        name="Install Spike Trap",
    )
    condition_fields: dict[str, object] = {
        "affected_positions": set(positions),
        "condition_stealth_dc": stealth_dc,
    }
    if condition_uuid is not None:
        condition_fields["uuid"] = condition_uuid
    condition = materialize_spatial_condition(
        SPIKE_TRAP_EFFECT_RECIPE,
        source_uuid,
        position=min(positions),
        faction=None,
        condition_type=SpikeTrap,
        condition_fields=condition_fields,
    )
    result = condition.activate(parent_event=causal_event)
    if result is None or result.canceled or not condition.applied:
        raise RuntimeError("Spike trap condition activation failed")
    if owns_root_event:
        causal_event.phase_to(EventPhase.COMPLETION)
    return condition


def extend_spike_trap_condition(
    condition: SpikeTrap,
    positions: Set[Tuple[int, int]],
    *,
    source_entity_uuid: Optional[UUID] = None,
) -> SpikeTrap:
    """Extend an installed trap network under one causal lifecycle."""
    if not positions:
        return condition
    causal_event = _begin_environment_effect_event(
        source_entity_uuid or condition.source_entity_uuid,
        name="Extend Spike Trap",
    )
    condition.extend_footprint(positions, parent_event=causal_event)
    causal_event.phase_to(EventPhase.COMPLETION)
    return condition


__all__ = [
    "extend_spike_trap_condition",
    "materialize_spike_trap_condition",
]
