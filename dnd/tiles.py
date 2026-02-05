"""
Advanced tile factories for terrain with game effects.

This module contains factories for tiles that need access to higher-level
systems (Entity, events, damage). The basic Tile class stays in core/base_tiles.py.

Terrain Types:
- Spikes: 2d4 piercing damage on entry (no difficult terrain)
- Difficult Terrain: 2x movement cost (no damage) - see core/base_tiles.py

IMPORTANT: Terrain zones should use ONE handler for ALL positions in the zone,
not one handler per tile. This is critical for performance - creating N handlers
for N tiles causes O(N) event processing overhead.
"""

import random
from typing import List, Set, Tuple
from uuid import UUID, uuid4

from dnd.core.base_tiles import Tile
from dnd.core.events import (
    Event, EventPhase, EventType, EventHandler, Trigger, EventQueue
)
from dnd.core.modifiers import DamageType
from dnd.entity import Entity


def create_spike_zone(positions: Set[Tuple[int, int]]) -> Tuple[List[Tile], EventHandler]:
    """
    Create spike tiles with ONE shared damage handler for all positions.

    This is the correct pattern for permanent terrain - ONE handler monitors
    ALL positions in the zone, not one handler per tile.

    Args:
        positions: Set of (x, y) positions for spike tiles

    Returns:
        Tuple of (list of Tile objects, the shared EventHandler)

    Example:
        spike_positions = {(x, y) for x in range(5) for y in range(10, 15)}
        tiles, handler = create_spike_zone(spike_positions)
        for tile in tiles:
            grid._tiles[tile.position] = tile
    """
    # Create all tiles first
    tiles = []
    for pos in positions:
        tile = Tile.create(
            pos,
            walkable=True,
            visible=True,
            name="Spikes",
            sprite_name="spikes.png"
        )
        tiles.append(tile)

    # Create ONE handler for ALL positions
    zone_uuid = uuid4()

    def damage_processor(event: Event, _: UUID) -> Event | None:
        """Deal 2d4 piercing damage when entity enters any spike tile."""
        entity_uuid = getattr(event, 'entity_uuid', None)
        if not entity_uuid:
            return None

        entity = Entity.get(entity_uuid)
        if not entity:
            return None

        # Roll 2d4 piercing damage
        damage = sum(random.randint(1, 4) for _ in range(2))

        # Pass the spatial event's parent (StepMovement) so TakeDamage links to it
        parent = getattr(event, 'parent_event', None)
        entity.receive_damage(damage, DamageType.PIERCING, zone_uuid, parent_event=parent)

        return None

    handler = EventHandler(
        name="Spike Zone Damage",
        source_entity_uuid=zone_uuid,
        trigger_conditions=[Trigger(
            event_type=EventType.SPATIAL_ENTITY_ENTERED,
            event_phase=EventPhase.EFFECT
        )],
        event_processor=damage_processor
    )

    # Register ONE handler for ALL positions
    EventQueue.add_spatial_handler(
        handler=handler,
        positions=positions,
        event_type=EventType.SPATIAL_ENTITY_ENTERED,
        event_phase=EventPhase.EFFECT
    )

    # Store handler reference on first tile for inspection/cleanup
    if tiles:
        tiles[0].event_handlers[handler.uuid] = handler

    return tiles, handler


# Keep old factory for backward compatibility but mark as deprecated
def spikes_terrain_factory(position: Tuple[int, int]) -> Tile:
    """
    DEPRECATED: Use create_spike_zone() instead for better performance.

    Create a spikes terrain tile (2d4 piercing damage on entry).

    WARNING: This creates ONE handler PER tile which causes performance issues
    when used for many tiles. Use create_spike_zone() for permanent terrain.

    Args:
        position: The (x, y) position for this tile

    Returns:
        Configured Tile with entry damage handler registered
    """
    import warnings
    warnings.warn(
        "spikes_terrain_factory() creates one handler per tile. "
        "Use create_spike_zone() for better performance with multiple tiles.",
        DeprecationWarning,
        stacklevel=2
    )

    tile = Tile.create(
        position,
        walkable=True,
        visible=True,
        name="Spikes",
        sprite_name="spikes.png"
    )

    # Create the entry damage handler
    def damage_processor(event: Event, _: UUID) -> Event | None:
        """Deal 2d4 piercing damage when entity enters."""
        entity_uuid = getattr(event, 'entity_uuid', None)
        if not entity_uuid:
            return None

        entity = Entity.get(entity_uuid)
        if not entity:
            return None

        # Roll 2d4 piercing damage
        damage = sum(random.randint(1, 4) for _ in range(2))

        # Pass the spatial event's parent (StepMovement) so TakeDamage links to it
        parent = getattr(event, 'parent_event', None)
        entity.receive_damage(damage, DamageType.PIERCING, tile.uuid, parent_event=parent)

        return None

    handler = EventHandler(
        name="Spikes Entry Damage",
        source_entity_uuid=tile.uuid,
        trigger_conditions=[Trigger(
            event_type=EventType.SPATIAL_ENTITY_ENTERED,
            event_phase=EventPhase.EFFECT
        )],
        event_processor=damage_processor
    )

    # Store handler on tile for inspection/cleanup
    tile.event_handlers[handler.uuid] = handler

    # Register with spatial index for this position only
    EventQueue.add_spatial_handler(
        handler=handler,
        positions={position},
        event_type=EventType.SPATIAL_ENTITY_ENTERED,
        event_phase=EventPhase.EFFECT
    )

    return tile
