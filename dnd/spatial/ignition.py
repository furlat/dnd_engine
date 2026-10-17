"""Publish fire contact; existing material owners decide whether cells ignite."""

from collections.abc import Iterable

from dnd.core.creature_types import DamageType
from dnd.core.events import Event, EventPhase, EventQueue, SpatialEffectInteractionEvent
from dnd.types.event_facts import GroupEntryKind
from dnd.types.spatial_effects import SpatialEffectInteractionOperation
from dnd.types.world import OccupancyLayer


def resolve_interaction(interaction: SpatialEffectInteractionEvent) -> SpatialEffectInteractionEvent:
    """Run one declared material operation to completion as one simultaneous instant.

    Every condition it touches reacts at EFFECT; their spatial changes settle
    once, before the operation completes (plan §5.2).
    """
    if interaction.canceled:
        return interaction
    with EventQueue.group(GroupEntryKind.MATERIAL_INTERACTION, root=interaction):
        for phase in (EventPhase.EXECUTION, EventPhase.EFFECT):
            interaction = interaction.phase_to(phase)
            if interaction.canceled:
                return interaction
    return interaction.phase_to(EventPhase.COMPLETION)


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
    resolve_interaction(interaction)



def apply_elemental_surface_contacts(parent_event: Event,positions: Iterable[tuple[int,int]],damage_type: DamageType,
                                     *,occupancy_layer: OccupancyLayer | None=None) -> None:
    """Dispatch native freeze/electrify/vaporize/ignite transitions over resolved cells."""
    contacts=tuple(sorted(set(positions)))
    if not contacts or parent_event.canceled:
        return
    operations={DamageType.FIRE:(SpatialEffectInteractionOperation.IGNITE,SpatialEffectInteractionOperation.VAPORIZE),
        DamageType.COLD:(SpatialEffectInteractionOperation.FREEZE,),
        DamageType.LIGHTNING:(SpatialEffectInteractionOperation.IGNITE,SpatialEffectInteractionOperation.ELECTRIFY)}.get(damage_type,())
    # The operations of one elemental contact are one instant.
    with EventQueue.group(GroupEntryKind.MATERIAL_INTERACTION, root=parent_event):
        for operation in operations:
            resolve_interaction(EventQueue.publish_declaration(SpatialEffectInteractionEvent(
                source_entity_uuid=parent_event.source_entity_uuid,
                source_entity_name=parent_event.source_entity_name,positions=contacts,operation=operation,
                damage_type=damage_type,occupancy_layer=occupancy_layer,parent_event=parent_event.uuid,use_register=False)))
