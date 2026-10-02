"""Publish fire contact; existing material owners decide whether cells ignite."""

from collections.abc import Iterable

from dnd.core.creature_types import DamageType
from dnd.core.events import Event, EventPhase, EventQueue, SpatialEffectInteractionEvent
from dnd.types.spatial_effects import SpatialEffectInteractionOperation
from dnd.types.world import OccupancyLayer


def ignite_surface_contacts(parent_event: Event, positions: Iterable[tuple[int, int]],
                            *, occupancy_layer: OccupancyLayer | None = None) -> None:
    """One causal operation over resolved fire cells, without guessing adjacent spread."""
    contacts = tuple(sorted(set(positions)))
    if not contacts or parent_event.canceled:
        return
    interaction = EventQueue.publish_declaration(SpatialEffectInteractionEvent(
        source_entity_uuid=parent_event.source_entity_uuid,
        source_entity_name=parent_event.source_entity_name,
        operation=SpatialEffectInteractionOperation.IGNITE,
        positions=contacts,
        damage_type=DamageType.FIRE,
        occupancy_layer=occupancy_layer,
        parent_event=parent_event.uuid,
        use_register=False,
    ))
    if interaction.canceled:
        return
    interaction = interaction.phase_to(EventPhase.EXECUTION)
    if interaction.canceled:
        return
    interaction = interaction.phase_to(EventPhase.EFFECT)
    if not interaction.canceled:
        interaction.phase_to(EventPhase.COMPLETION)
