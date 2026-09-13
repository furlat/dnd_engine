"""AI tile/object facts from recorded world and observer after-values."""

from collections.abc import Iterable, Mapping
from uuid import UUID

from dnd.ai.contracts.observation import (
    AdjacentOffset, KnowledgeState, ObservationObjectFact, ObservationTileFact,
    SpatialDomainKnowledge,
)
from dnd.core.world_edges import WorldEdgeStructuralContribution, world_edge_contribution_allows
from dnd.types.senses import SensesSnapshot
from dnd.types.world import MovementMode, WorldEdgeChannel
from dnd.world_facts import CARDINAL_DELTAS, OPPOSITE_DIRECTION, WorldFacts


def adjacent_domain(world: WorldFacts, position: tuple[int, int]) -> dict[AdjacentOffset, SpatialDomainKnowledge]:
    """Preserve the existing local boundary disclosure without terrain contents."""
    return {offset: (
        SpatialDomainKnowledge.UNKNOWN
        if (position[0] + offset.delta[0], position[1] + offset.delta[1]) in world.tiles
        else SpatialDomainKnowledge.INVALID
    ) for offset in AdjacentOffset}


def project_tile(
    world: WorldFacts,
    position: tuple[int, int],
    observer_ids: Iterable[str],
    senses_by_observer: Mapping[UUID, SensesSnapshot],
) -> ObservationTileFact:
    """Project current terrain using the first sorted observing actor's evidence."""
    observers = sorted(observer_ids)
    tile = world.tiles.get(position)
    if tile is None:
        return ObservationTileFact(
            key=f"{position[0]},{position[1]}", position=position,
            knowledge_state=KnowledgeState.VISIBLE, observer_uuids=observers,
            adjacent_domain=adjacent_domain(world, position),
        )
    senses = senses_by_observer.get(UUID(observers[0])) if observers else None
    directional = {
        channel.value: {direction.value: False for direction in CARDINAL_DELTAS}
        for channel in WorldEdgeChannel
    }
    for direction, (dx, dy) in CARDINAL_DELTAS.items():
        destination = (position[0] + dx, position[1] + dy)
        neighbor = world.tiles.get(destination)
        if neighbor is None:
            for channel in WorldEdgeChannel:
                directional[channel.value][direction.value] = True
            continue
        providers = world.boundaries.get((position, direction), set()) | world.boundaries.get(
            (destination, OPPOSITE_DIRECTION[direction]), set(),
        )
        for identity in providers:
            obj = world.objects[identity]
            structure = obj.item.boundary_structure
            if structure is None:
                continue
            contribution = WorldEdgeStructuralContribution(
                provider_uuid=identity,
                base_height_steps=obj.placement.base_height_steps,
                top_height_steps=obj.placement.top_height_steps,
                blocked_channels=structure.blocked_channels,
            )
            for channel in WorldEdgeChannel:
                if channel is WorldEdgeChannel.MOVEMENT and senses is not None and identity not in senses.objects:
                    continue
                if not world_edge_contribution_allows(
                    contribution, channel,
                    source_height=tile.elevation_steps,
                    destination_height=neighbor.elevation_steps,
                    movement_mode=MovementMode.WALKING,
                ):
                    directional[channel.value][direction.value] = True
    return ObservationTileFact(
        key=f"{position[0]},{position[1]}", position=position,
        knowledge_state=KnowledgeState.VISIBLE, observer_uuids=observers,
        name=tile.name, walkable=tile.walking_cost > 0, walking_cost=tile.walking_cost,
        is_hazardous=senses.hazardous_cells.get(position) if senses is not None else None,
        conditions=list(tile.condition_names), light_level=tile.resolved_light.value,
        directional_blocks_movement=directional["movement"],
        directional_blocks_vision=directional["optical"],
        directional_blocks_light=directional["optical"],
        directional_blocks_propagation=directional["propagation"],
        adjacent_domain=adjacent_domain(world, position),
    )


def project_object(
    world: WorldFacts, object_uuid: UUID, position: tuple[int, int] | None,
    observer_ids: Iterable[str],
) -> ObservationObjectFact | None:
    """Expose the recorded current item state, without raw-field introspection."""
    obj = world.objects.get(object_uuid)
    if obj is None:
        return None
    item = obj.item
    state: dict[str, object] = {
        "blocks_movement": item.blocks_movement, "blocks_optics_field": item.blocks_optics,
        "blocks_propagation_field": item.blocks_propagation,
        "is_pickable": item.is_pickable, "is_usable": item.is_usable,
        "stack_count": item.stack_count,
    }
    if item.is_open is not None:
        state["is_open"] = item.is_open
    if item.charges is not None:
        state["charges"] = item.charges
    return ObservationObjectFact(
        uuid=str(object_uuid), name=item.name, knowledge_state=KnowledgeState.VISIBLE,
        observer_uuids=sorted(observer_ids), position=position or obj.placement.position,
        map_char=item.map_char, state=state,
    )
