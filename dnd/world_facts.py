"""Fold recorded world after-values without consulting native world owners."""

from dataclasses import dataclass, field, replace
from uuid import UUID

from dnd.blocks.base_item import ItemResourceChangeEvent, ItemLocationStateEvent, ItemHoldingsReleasedEvent
from dnd.core.base_conditions import ConditionApplicationEvent, ConditionRemovalEvent
from dnd.core.events import (
    Event, SpatialChangeEvent, SpatialChangeType, SpatialEffectChangeEvent, TileElevationChangeEvent,
    WorldConnectorState, WorldInitializedEvent, WorldModifiedEvent, WorldObjectState,
    WorldTileState, SensoryUpdateEvent,
)
from dnd.types.event_facts import KeyedTileChange
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
    # Query membership includes the opposite incident support of each boundary.
    objects_by_position: dict[tuple[int, int], set[UUID]] = field(default_factory=dict)
    containers_by_item: dict[UUID, set[UUID]] = field(default_factory=dict)
    remnants_by_item: dict[UUID, set[UUID]] = field(default_factory=dict)
    constructions_by_provider: dict[UUID, set[UUID]] = field(default_factory=dict)
    constructions_by_position: dict[tuple[int, int], set[UUID]] = field(default_factory=dict)


def copy_world_facts(world: WorldFacts) -> WorldFacts:
    """Detach mutable recorded indexes while sharing their immutable after-values."""
    return replace(world, tiles=dict(world.tiles), objects=dict(world.objects),
        connectors=dict(world.connectors),
        boundaries={key: set(value) for key, value in world.boundaries.items()},
        objects_by_position={key: set(value) for key, value in world.objects_by_position.items()},
        containers_by_item={key: set(value) for key, value in world.containers_by_item.items()},
        remnants_by_item={key: set(value) for key, value in world.remnants_by_item.items()},
        constructions_by_provider={key: set(value) for key, value in world.constructions_by_provider.items()},
        constructions_by_position={key: set(value) for key, value in world.constructions_by_position.items()})


def world_objects_at(world: WorldFacts, positions: set[tuple[int, int]]) -> set[UUID]:
    """Objects on touched supports, including either incident side of a boundary."""
    identities: set[UUID] = set()
    for position in positions & world.objects_by_position.keys():
        identities.update(world.objects_by_position[position])
    return identities


def _index_object(world: WorldFacts, identity: UUID, value: WorldObjectState, *, remove: bool) -> None:
    positions = set(value.placement.positions)
    memberships = []
    if value.placement.kind is WorldPlacementKind.BOUNDARY:
        assert value.placement.boundary_direction is not None
        dx, dy = CARDINAL_DELTAS[value.placement.boundary_direction]
        x, y = value.placement.position
        positions.add((x + dx, y + dy))
        memberships.append((world.boundaries, ((value.placement.position, value.placement.boundary_direction),)))
    memberships.append((world.objects_by_position, positions))
    memberships.append((world.containers_by_item, tuple(item.item_uuid for item in value.contained_items or ())))
    memberships.append((world.remnants_by_item, value.item.remnant_state.intact_supported_items
        if value.item.remnant_state is not None else ()))
    memberships.append((world.constructions_by_provider, tuple(
        row.provider_uuid for row in value.item.construction_suppressions)))
    memberships.append((world.constructions_by_position, tuple(
        position for row in value.item.construction_suppressions for position in row.positions)))
    for index, keys in memberships:
        for key in set(keys):
            if remove:
                members = index[key]
                members.remove(identity)
                if not members:
                    del index[key]
            else:
                index.setdefault(key, set()).add(identity)


def _put_object(world: WorldFacts, identity: UUID, value: WorldObjectState | None) -> None:
    previous = world.objects.pop(identity, None)
    if previous is not None:
        _index_object(world, identity, previous, remove=True)
    if value is not None:
        world.objects[identity] = value
        _index_object(world, identity, value, remove=False)


def _remove_contained_item(world: WorldFacts, identity: UUID) -> bool:
    """Recorded membership identifies the source, including older owner stamps."""
    changed = False
    for owner in tuple(world.containers_by_item.get(identity, ())):
        obj = world.objects[owner]
        assert obj.contained_items is not None
        retained = tuple(item for item in obj.contained_items if item.item_uuid != identity)
        if retained != obj.contained_items:
            _put_object(world, owner, obj.model_copy(update={"contained_items": retained}))
            changed = True
    return changed


def world_event_objects(
    world: WorldFacts, event: Event, condition: ConditionFact | None = None,
) -> set[UUID]:
    """Explicit subjects and containing owners, including objects with no surviving bands."""
    identities: set[UUID] = set()
    if condition is not None and condition.resulting_item is not None:
        identities.add(condition.resulting_item.item_uuid)
    match event:
        case WorldInitializedEvent():
            return set(world.objects) | {obj.item.item_uuid for obj in event.objects}
        case WorldModifiedEvent() | SpatialChangeEvent():
            if event.object_uuid is not None:
                identities.add(event.object_uuid)
        case ItemLocationStateEvent():
            identities.add(event.item_state.item_uuid)
            if event.owner_uuid is not None:
                identities.add(event.owner_uuid)
        case ItemHoldingsReleasedEvent() | ItemResourceChangeEvent():
            identities.add(event.item_uuid)
        case ConditionApplicationEvent() | ConditionRemovalEvent():
            if event.resulting_item is not None:
                identities.add(event.resulting_item.item_uuid)
    for identity in tuple(identities):
        identities.update(world.containers_by_item.get(identity, ()))
    return identities


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
            if event.owner_uuid is not None and (owner := world.objects.get(event.owner_uuid)) is not None:
                positions.update(owner.placement.positions)
        case ItemHoldingsReleasedEvent():
            identity = event.item_uuid
        case ItemResourceChangeEvent():
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
            # Every tile a TILES_CHANGED fact changes (residues, terrain) is a changed cell.
            positions.update(change.position for change in event.keyed_tile_changes)
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
    if identity is not None:
        if (obj := world.objects.get(identity)) is not None:
            positions.update(obj.placement.positions)
        for owner in world.containers_by_item.get(identity, ()):
            positions.update(world.objects[owner].placement.positions)
    return positions | {
        (x + dx, y + dy) for x, y in positions for dx, dy in CARDINAL_DELTAS.values()
    }


def world_event_footprints(
    world: WorldFacts, event: Event, condition: ConditionFact | None = None,
) -> tuple[set[tuple[int, int]], set[tuple[int, int]]]:
    """Separate Tile after-values from object/incident-support observation inputs."""
    if isinstance(event, SensoryUpdateEvent):
        return set(), set()
    if (isinstance(event, SpatialChangeEvent)
            and event.change_type is SpatialChangeType.LIGHT_CHANGED
            and (condition is None or condition.resulting_tile is None and condition.resulting_item is None)):
        positions = {tuple(map(int, key.split(",", maxsplit=1))) for key in event.light_level_map or {}}
        if event.new_light_level is not None:
            positions.add(event.position)
        # This fact changes no placement, object value or observation grant.
        return positions, set()
    positions = world_event_positions(world, event, condition)
    return positions, set(positions)


def apply_keyed_tile_change(previous: WorldTileState, change: KeyedTileChange) -> WorldTileState:
    """One Tile's keyed change applied to its recorded value: the changed fields, the changed materials."""
    update: dict[str, object] = dict(change.fields)
    if change.residues:
        materials = {row.residue_id: row for row in previous.residues}
        for row in change.residues:
            if row.state is None:
                materials.pop(row.residue_id, None)
            else:
                materials[row.residue_id] = row.state
        # The tile lists its materials in residue order (`Tile.residue_states`).
        update["residues"] = tuple(materials[key] for key in sorted(materials))
    return previous.model_copy(update=update)


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
            world.objects_by_position.clear()
            world.containers_by_item.clear()
            world.remnants_by_item.clear()
            world.constructions_by_provider.clear()
            world.constructions_by_position.clear()
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
        case ItemHoldingsReleasedEvent():
            return _remove_contained_item(world, event.item_uuid)
        case ItemLocationStateEvent():
            identity = event.item_state.item_uuid
            _remove_contained_item(world, identity)
            owner = world.objects.get(event.owner_uuid) if event.owner_uuid is not None else None
            if (owner is not None and owner.contained_items is not None
                    and event.location is ItemLocation.INVENTORY):
                _put_object(world, owner.item.item_uuid, owner.model_copy(update={
                    "contained_items": tuple(sorted((*owner.contained_items, event.item_state),
                        key=lambda item: str(item.item_uuid))),
                }))
            if event.location is ItemLocation.FLOOR:
                if event.world_placement is None:
                    raise ValueError("floor item fact requires its recorded placement")
                previous = world.objects.get(identity)
                _put_object(world, identity, WorldObjectState(
                    placement=event.world_placement, item=event.item_state,
                    contained_items=previous.contained_items if previous is not None else None,
                ))
            else:
                _put_object(world, identity, None)
        case ItemResourceChangeEvent():
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
            if event.change_type is SpatialChangeType.TILES_CHANGED:
                if not event.keyed_tile_changes:
                    return False
                for change in event.keyed_tile_changes:
                    previous = world.tiles.get(change.position)
                    if previous is None:
                        raise ValueError(f"A keyed tile change requires its recorded tile {change.position}")
                    world.tiles[change.position] = apply_keyed_tile_change(previous, change)
            elif event.change_type is SpatialChangeType.TILE_CHANGED:
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
                        resolved = LightLevel(level)
                        if previous.resolved_light is not resolved:
                            world.tiles[position] = previous.model_copy(update={"resolved_light": resolved})
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
                    contained_items=previous.contained_items if previous is not None else None,
                ))
            else:
                return False
        case _:
            return False
    return True
