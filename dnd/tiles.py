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
from typing import List, Optional, Set, Tuple
from uuid import UUID, uuid4

from dnd.core.base_tiles import Tile
from dnd.core.events import (
    Event, EventPhase, EventType, EventHandler, Trigger, EventQueue, SpatialChangeEvent, SensesUpdateHint
)
from dnd.core.creature_types import DamageType
from dnd.core.gridmap import get_map
from dnd.entity import Entity
from dnd.tile_conditions import SpikeTrapCondition


def create_spike_zone(positions: Set[Tuple[int, int]],
                      stealth_dc: Optional[int] = None) -> Tuple[List[Tile], EventHandler]:
    """
    Create Floor tiles with SpikeTrapCondition markers + ONE shared damage handler.

    The SpikeTrapCondition is a pure marker for:
    - hazard_filter → pathfinding knows to avoid
    - condition_stealth_dc → perception check to detect hidden traps
    - API visibility → display/agent sees "Spike Trap" condition

    Args:
        positions: Set of (x, y) positions for spike tiles
        stealth_dc: Optional perception DC to detect the trap (None = always visible)

    Returns:
        Tuple of (list of Tile objects, the shared EventHandler)
    """

    tiles = []
    for pos in positions:
        tile = Tile.create(
            pos,
            walkable=True,
            visible=True,
            name="Floor",
        )
        tiles.append(tile)

    zone_uuid = uuid4()

    def damage_processor(event: Event, _: UUID) -> Event | None:
        """Deal 2d4 piercing damage when entity enters any spike tile."""
        if not isinstance(event, SpatialChangeEvent) or not event.entity_uuid:
            return None

        entity = Entity.get(event.entity_uuid)
        if not entity:
            return None

        damage = sum(random.randint(1, 4) for _ in range(2))

        entity.receive_damage(damage, DamageType.PIERCING, zone_uuid, parent_event=event.parent_event)

        grid = get_map()
        tile = grid.get_tile(event.position[0], event.position[1])
        if tile is not None:
            cond = tile.active_conditions.get("Spike Trap")
            if cond is not None and cond.condition_stealth_dc is not None:
                cond.condition_stealth_dc = None

                hint = SensesUpdateHint(requires_paths=True)
                reveal_event = SpatialChangeEvent.tile_changed(
                    event.position, walkable=True, visible=True,
                    senses_hint=hint,
                )
                reveal_event = reveal_event.phase_to(EventPhase.COMPLETION)
                EventQueue.register(reveal_event)

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

    EventQueue.add_spatial_handler(
        handler=handler,
        positions=positions,
        event_type=EventType.SPATIAL_ENTITY_ENTERED,
        event_phase=EventPhase.EFFECT
    )

    for tile in tiles:
        cond = SpikeTrapCondition(
            source_entity_uuid=tile.uuid,
            target_entity_uuid=tile.uuid,
            condition_stealth_dc=stealth_dc,
        )
        tile.add_condition(cond)

    if tiles:
        hint = SensesUpdateHint(requires_paths=True)
        event = SpatialChangeEvent.tile_changed(
            tiles[0].position, walkable=True, visible=True,
            senses_hint=hint,
        )
        event = event.phase_to(EventPhase.COMPLETION)
        EventQueue.register(event)

    return tiles, handler


def deactivate_spike_zone(tiles: List[Tile], handler: EventHandler) -> None:
    """Deactivate: remove shared handler + marker conditions from tiles."""
    EventQueue.remove_spatial_handler(handler.uuid)
    for tile in tiles:
        if "Spike Trap" in tile.active_conditions:
            tile.remove_condition("Spike Trap")

    if tiles:
        hint = SensesUpdateHint(requires_paths=True)
        event = SpatialChangeEvent.tile_changed(
            tiles[0].position, walkable=True, visible=True,
            senses_hint=hint,
        )
        event = event.phase_to(EventPhase.COMPLETION)
        EventQueue.register(event)
