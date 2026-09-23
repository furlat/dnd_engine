"""Fold recorded world after-values without consulting native world owners."""

from dataclasses import dataclass, field
from uuid import UUID

from dnd.blocks.base_item import ItemChargeConsumptionEvent, ItemLocationStateEvent
from dnd.core.base_conditions import ConditionApplicationEvent, ConditionRemovalEvent
from dnd.core.events import (
    Event, SpatialChangeEvent, SpatialChangeType, SpatialEffectChangeEvent, TileElevationChangeEvent,
    WorldConnectorState, WorldInitializedEvent, WorldModifiedEvent, WorldObjectState,
    WorldTileState,
)
from dnd.core.item_types import ItemLocation
from dnd.types.world import CardinalDirection, LightLevel
from dnd.types.actor_facts import ConditionFact
from dnd.types.world_placement import WorldPlacementKind


CARDINAL_DELTAS = {
    CardinalDirection.NORTH: (0, 1), CardinalDirection.SOUTH: (0, -1),
    CardinalDirection.EAST: (1, 0), CardinalDirection.WEST: (-1, 0),
}
OPPOSITE_DIRECTION = {
    CardinalDirection.NORTH: CardinalDirection.SOUTH,
    CardinalDirection.SOUTH: CardinalDirection.NORTH,
    CardinalDirection.EAST: CardinalDirection.WEST,
    CardinalDirection.WEST: CardinalDirection.EAST,
}


@dataclass(slots=True)
class WorldFacts:
    """Current cold world values; boundary membership indexes those same objects."""

    world: WorldInitializedEvent | None = None
    tiles: dict[tuple[int, int], WorldTileState] = field(default_factory=dict)
    objects: dict[UUID, WorldObjectState] = field(default_factory=dict)
    connectors: dict[UUID, WorldConnectorState] = field(default_factory=dict)
    boundaries: dict[tuple[tuple[int, int], CardinalDirection], set[UUID]] = field(default_factory=dict)


def _put_object(world: WorldFacts, identity: UUID, value: WorldObjectState | None) -> None:
    previous = world.objects.pop(identity, None)
    if previous is not None and previous.placement.boundary_direction is not None:
        key = (previous.placement.position, previous.placement.boundary_direction)
        members = world.boundaries.get(key)
        if members is not None:
            members.discard(identity)
            if not members:
                world.boundaries.pop(key)
    if value is not None:
        world.objects[identity] = value
        if value.placement.kind is WorldPlacementKind.BOUNDARY:
            direction = value.placement.boundary_direction
            assert direction is not None
            world.boundaries.setdefault((value.placement.position, direction), set()).add(identity)


def world_event_positions(
    world: WorldFacts, event: Event, condition: ConditionFact | None = None,
) -> set[tuple[int, int]]:
    """Return changed cells and incident sides before applying a recorded fact."""
    positions: set[tuple[int, int]] = set()
    identity: UUID | None = None
    if condition is not None and condition.resulting_tile is not None:
        positions.add(condition.resulting_tile.position)
    if condition is not None and condition.resulting_item is not None:
        identity = condition.resulting_item.item_uuid
    match event:
        case WorldInitializedEvent():
            return {row.position for row in event.tiles} | set(world.tiles)
        case WorldModifiedEvent():
            if event.tile_position is not None:
                positions.add(event.tile_position)
            identity = event.object_uuid
            if isinstance(event.after, WorldObjectState):
                positions.update(event.after.placement.positions)
        case ItemLocationStateEvent():
            identity = event.item_state.item_uuid
            if event.world_placement is not None:
                positions.update(event.world_placement.positions)
        case ItemChargeConsumptionEvent():
            identity = event.item_uuid
        case TileElevationChangeEvent():
            positions.add(event.position)
        case SpatialEffectChangeEvent():
            positions.update(event.get_affected_positions())
        case SpatialChangeEvent():
            positions.add(event.position)
            identity = event.object_uuid
            if event.old_position is not None:
                positions.add(event.old_position)
            for placement in (event.placement, event.previous_placement):
                if placement is not None:
                    positions.update(placement.positions)
            for key in event.light_level_map or {}:
                x, y = key.split(",", maxsplit=1)
                positions.add((int(x), int(y)))
        case ConditionApplicationEvent() | ConditionRemovalEvent():
            if event.resulting_tile is not None:
                positions.add(event.resulting_tile.position)
            if event.resulting_item is not None:
                identity = event.resulting_item.item_uuid
    if identity is not None and (obj := world.objects.get(identity)) is not None:
        positions.update(obj.placement.positions)
    return positions | {
        (x + dx, y + dy) for x, y in positions for dx, dy in CARDINAL_DELTAS.values()
    }


def apply_world_fact(
    world: WorldFacts, event: Event, condition: ConditionFact | None = None,
) -> bool:
    """Apply only recorded after-values; callers own phase/source ordering."""
    if event.canceled:
        return False
    if condition is not None and condition.resulting_tile is not None:
        world.tiles[condition.resulting_tile.position] = condition.resulting_tile
        return True
    if condition is not None and condition.resulting_item is not None:
        previous = world.objects.get(condition.resulting_item.item_uuid)
        if previous is None:
            return False
        _put_object(world, condition.resulting_item.item_uuid,
                    previous.model_copy(update={"item": condition.resulting_item}))
        return True
    match event:
        case WorldInitializedEvent():
            world.world = event
            world.tiles = {row.position: row for row in event.tiles}
            world.objects.clear()
            world.boundaries.clear()
            for obj in event.objects:
                _put_object(world, obj.item.item_uuid, obj)
            world.connectors = {row.connector_uuid: row for row in event.connectors}
        case WorldModifiedEvent():
            if event.tile_position is not None:
                if isinstance(event.after, WorldTileState):
                    world.tiles[event.tile_position] = event.after
                elif event.after is None:
                    world.tiles.pop(event.tile_position, None)
            elif event.object_uuid is not None:
                if isinstance(event.after, WorldObjectState) or event.after is None:
                    _put_object(world, event.object_uuid, event.after)
            elif event.connector_uuid is not None:
                if isinstance(event.after, WorldConnectorState):
                    world.connectors[event.connector_uuid] = event.after
                elif event.after is None:
                    world.connectors.pop(event.connector_uuid, None)
        case ItemLocationStateEvent():
            identity = event.item_state.item_uuid
            if event.location is ItemLocation.FLOOR:
                if event.world_placement is None:
                    raise ValueError("floor item fact requires its recorded placement")
                previous = world.objects.get(identity)
                _put_object(world, identity, WorldObjectState(
                    placement=event.world_placement, item=event.item_state,
                    contained_items=previous.contained_items if previous is not None else (),
                ))
            else:
                _put_object(world, identity, None)
        case ItemChargeConsumptionEvent():
            previous = world.objects.get(event.item_uuid)
            if previous is None:
                return False
            value = None if event.item_destroyed else previous.model_copy(update={
                "item": previous.item.model_copy(update={
                    "charges": event.charges_after, "stack_count": event.stack_count_after,
                }),
            })
            _put_object(world, event.item_uuid, value)
        case ConditionApplicationEvent() | ConditionRemovalEvent():
            if event.resulting_tile is not None:
                world.tiles[event.resulting_tile.position] = event.resulting_tile
            elif event.resulting_item is not None:
                previous = world.objects.get(event.resulting_item.item_uuid)
                if previous is None:
                    return False
                _put_object(world, event.resulting_item.item_uuid,
                            previous.model_copy(update={"item": event.resulting_item}))
            else:
                return False
        case TileElevationChangeEvent():
            previous = world.tiles.get(event.position)
            if previous is None:
                return False
            world.tiles[event.position] = previous.model_copy(update={
                "elevation_steps": event.new_height_steps,
                "surface_kind": event.new_surface_kind, "slope_axis": event.new_slope_axis,
            })
        case SpatialChangeEvent():
            if event.change_type is SpatialChangeType.TILE_CHANGED:
                if event.tile_present is False:
                    world.tiles.pop(event.position, None)
                elif event.tile_state is not None:
                    world.tiles[event.position] = event.tile_state
                elif (previous := world.tiles.get(event.position)) is not None:
                    tile_updates: dict[str, object] = {key: value for key, value in (
                        ("walking_cost", event.tile_walking_cost), ("flying_cost", event.tile_flying_cost),
                        ("swimming_cost", event.tile_swimming_cost), ("burrowing_cost", event.tile_burrowing_cost),
                        ("blocks_optics", event.tile_blocks_optics),
                        ("blocks_propagation", event.tile_blocks_propagation),
                    ) if value is not None}
                    if event.new_light_level is not None:
                        tile_updates["resolved_light"] = LightLevel(event.new_light_level)
                    world.tiles[event.position] = previous.model_copy(update=tile_updates)
                else:
                    return False
            elif event.change_type is SpatialChangeType.TILE_REMOVED:
                world.tiles.pop(event.position, None)
            elif event.change_type is SpatialChangeType.LIGHT_CHANGED:
                levels = dict(event.light_level_map or {})
                if event.new_light_level is not None:
                    levels[f"{event.position[0]},{event.position[1]}"] = event.new_light_level
                for key, level in levels.items():
                    x, y = key.split(",", maxsplit=1)
                    position = (int(x), int(y))
                    if (previous := world.tiles.get(position)) is not None:
                        world.tiles[position] = previous.model_copy(update={"resolved_light": LightLevel(level)})
            elif event.change_type is SpatialChangeType.OBJECT_REMOVED and event.object_uuid is not None:
                _put_object(world, event.object_uuid, None)
            elif event.change_type in (SpatialChangeType.OBJECT_PLACED, SpatialChangeType.OBJECT_CHANGED):
                if event.object_uuid is None:
                    return False
                previous = world.objects.get(event.object_uuid)
                item = event.object_state or (previous.item if previous is not None else None)
                placement = event.placement or (previous.placement if previous is not None else None)
                if item is None or placement is None:
                    return False
                if event.object_state is None:
                    item_updates: dict[str, object] = {"boundary_structure": event.object_boundary_structure}
                    for key, value in (
                        ("name", event.object_name), ("map_char", event.object_map_char),
                        ("is_open", event.object_is_open), ("blocks_movement", event.object_blocks_movement),
                        ("blocks_optics", event.object_blocks_optics),
                        ("blocks_propagation", event.object_blocks_propagation),
                    ):
                        if value is not None:
                            item_updates[key] = value
                    item = item.model_copy(update=item_updates)
                _put_object(world, event.object_uuid, WorldObjectState(
                    item=item, placement=placement,
                    contained_items=previous.contained_items if previous is not None else (),
                ))
            else:
                return False
        case _:
            return False
    return True
