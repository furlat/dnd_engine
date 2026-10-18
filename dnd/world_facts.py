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
from dnd.types.event_facts import AppliedWorldFact, KeyedTileChange, KeyedTileFields
from dnd.core.item_types import ItemLocation
from dnd.types.world import CardinalDirection, LightLevel
from dnd.types.actor_facts import ConditionFact
from dnd.types.world_placement import CARDINAL_DELTAS, WorldPlacementKind, placement_support_cells


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
    memberships = []
    if value.placement.kind is WorldPlacementKind.BOUNDARY:
        assert value.placement.boundary_direction is not None
        memberships.append((world.boundaries, ((value.placement.position, value.placement.boundary_direction),)))
    memberships.append((world.objects_by_position, placement_support_cells(value.placement)))
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


@dataclass(slots=True)
class _Written:
    """One fold's writes as it makes them: the parts of its `AppliedWorldFact` a case fills."""

    tiles: list[KeyedTileChange] = field(default_factory=list)
    tile_fields: list[tuple[tuple[int, int], KeyedTileFields]] = field(default_factory=list)
    new_residues: set[tuple[tuple[int, int], str]] = field(default_factory=set)
    light: dict[tuple[int, int], LightLevel] = field(default_factory=dict)
    tile_conditions: dict[tuple[int, int], tuple[str, ...]] = field(default_factory=dict)
    replaced: set[tuple[int, int]] = field(default_factory=set)
    objects: set[UUID] = field(default_factory=set)
    moved: set[UUID] = field(default_factory=set)
    contents: dict[UUID, tuple[list[UUID], list[UUID]]] = field(default_factory=dict)
    connectors: list[tuple[UUID, WorldConnectorState | None, WorldConnectorState | None]] = field(default_factory=list)

    def applied(self) -> AppliedWorldFact:
        return AppliedWorldFact(tiles=tuple(self.tiles), tile_fields=tuple(self.tile_fields),
            new_residues=frozenset(self.new_residues),
            light=tuple(self.light.items()), tile_conditions=tuple(self.tile_conditions.items()),
            replaced=frozenset(self.replaced), objects=frozenset(self.objects), moved=frozenset(self.moved),
            contents=tuple((owner, tuple(added), tuple(removed)) for owner, (added, removed) in self.contents.items()),
            connectors=tuple(self.connectors))


def _put_object(world: WorldFacts, identity: UUID, value: WorldObjectState | None, written: _Written, *,
                placed: bool = False) -> None:
    """An object's after-value (None: removed). `placed`: the event wrote its placement; a new object is placed."""
    previous = world.objects.pop(identity, None)
    if previous is not None:
        _index_object(world, identity, previous, remove=True)
    if value is not None:
        world.objects[identity] = value
        _index_object(world, identity, value, remove=False)
    written.objects.add(identity)
    if value is not None and (placed or previous is None):
        written.moved.add(identity)


def _contents(written: _Written, owner: UUID) -> tuple[list[UUID], list[UUID]]:
    return written.contents.setdefault(owner, ([], []))


def _remove_contained_item(world: WorldFacts, identity: UUID, written: _Written) -> bool:
    """Recorded membership identifies the source, including older owner stamps."""
    changed = False
    for owner in tuple(world.containers_by_item.get(identity, ())):
        obj = world.objects[owner]
        assert obj.contained_items is not None
        retained = tuple(item for item in obj.contained_items if item.item_uuid != identity)
        if retained != obj.contained_items:
            _put_object(world, owner, obj.model_copy(update={"contained_items": retained}), written)
            _contents(written, owner)[1].append(identity)
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
                del materials[row.residue_id]
            else:
                materials[row.residue_id] = row.state
        # The tile lists its materials in residue order (`Tile.residue_states`).
        update["residues"] = tuple(materials[key] for key in sorted(materials))
    return previous.model_copy(update=update)


def apply_world_fact(
    world: WorldFacts, event: Event, condition: ConditionFact | None = None,
) -> AppliedWorldFact | None:
    """Apply only recorded after-values, returning what they changed (None: nothing applied); callers own
    phase/source ordering."""
    if event.canceled:
        return None
    written = _Written()
    if condition is not None and condition.resulting_tile is not None:
        _resulting_tile(world, condition.resulting_tile, written)
        return written.applied()
    if condition is not None and condition.resulting_item is not None:
        previous = world.objects.get(condition.resulting_item.item_uuid)
        if previous is None:
            return None
        _put_object(world, condition.resulting_item.item_uuid,
                    previous.model_copy(update={"item": condition.resulting_item}), written)
        return written.applied()
    match event:
        case WorldInitializedEvent():
            world.world = event
            world.tiles = {row.position: row for row in event.tiles}
            written.replaced.update(world.tiles)
            world.objects.clear()
            world.boundaries.clear()
            world.objects_by_position.clear()
            world.containers_by_item.clear()
            world.remnants_by_item.clear()
            world.constructions_by_provider.clear()
            world.constructions_by_position.clear()
            for obj in event.objects:
                _put_object(world, obj.item.item_uuid, obj, written)
            world.connectors = {row.connector_uuid: row for row in event.connectors}
            written.connectors.extend((row.connector_uuid, None, row) for row in event.connectors)
        case WorldModifiedEvent():
            if event.tile_position is not None:
                if isinstance(event.after, WorldTileState):
                    _put_tile(world, event.after, written)
                elif event.after is None:
                    world.tiles.pop(event.tile_position, None)
                    written.replaced.add(event.tile_position)
            elif event.object_uuid is not None:
                if isinstance(event.after, WorldObjectState) or event.after is None:
                    _put_object(world, event.object_uuid, event.after, written, placed=True)
            elif event.connector_uuid is not None:
                if isinstance(event.after, WorldConnectorState):
                    world.connectors[event.connector_uuid] = event.after
                    written.connectors.append((event.connector_uuid, event.before
                        if isinstance(event.before, WorldConnectorState) else None, event.after))
                elif event.after is None:
                    world.connectors.pop(event.connector_uuid, None)
                    written.connectors.append((event.connector_uuid, event.before
                        if isinstance(event.before, WorldConnectorState) else None, None))
        case ItemHoldingsReleasedEvent():
            return written.applied() if _remove_contained_item(world, event.item_uuid, written) else None
        case ItemLocationStateEvent():
            identity = event.item_state.item_uuid
            _remove_contained_item(world, identity, written)
            owner = world.objects.get(event.owner_uuid) if event.owner_uuid is not None else None
            if (owner is not None and owner.contained_items is not None
                    and event.location is ItemLocation.INVENTORY):
                _put_object(world, owner.item.item_uuid, owner.model_copy(update={
                    "contained_items": tuple(sorted((*owner.contained_items, event.item_state),
                        key=lambda item: str(item.item_uuid))),
                }), written)
                _contents(written, owner.item.item_uuid)[0].append(identity)
            if event.location is ItemLocation.FLOOR:
                if event.world_placement is None:
                    raise ValueError("floor item fact requires its recorded placement")
                previous = world.objects.get(identity)
                _put_object(world, identity, WorldObjectState(
                    placement=event.world_placement, item=event.item_state,
                    contained_items=previous.contained_items if previous is not None else None,
                ), written, placed=True)
            else:
                _put_object(world, identity, None, written)
        case ItemResourceChangeEvent():
            previous = world.objects.get(event.item_uuid)
            if previous is None:
                return None
            value = None if event.item_destroyed else previous.model_copy(update={
                "item": previous.item.model_copy(update={
                    "charges": event.charges_after, "stack_count": event.stack_count_after,
                }),
            })
            _put_object(world, event.item_uuid, value, written)
        case ConditionApplicationEvent() | ConditionRemovalEvent():
            if event.resulting_tile is not None:
                _resulting_tile(world, event.resulting_tile, written)
            elif event.resulting_item is not None:
                previous = world.objects.get(event.resulting_item.item_uuid)
                if previous is None:
                    return None
                _put_object(world, event.resulting_item.item_uuid,
                            previous.model_copy(update={"item": event.resulting_item}), written)
            else:
                return None
        case TileElevationChangeEvent():
            previous = world.tiles.get(event.position)
            if previous is None:
                return None
            fields = KeyedTileFields(elevation_steps=event.new_height_steps, surface_kind=event.new_surface_kind,
                slope_axis=event.new_slope_axis)
            world.tiles[event.position] = previous.model_copy(update=dict(fields))
            written.tile_fields.append((event.position, fields))
        case SpatialChangeEvent():
            if event.change_type is SpatialChangeType.TILES_CHANGED:
                if not event.keyed_tile_changes:
                    return None
                for change in event.keyed_tile_changes:
                    previous = world.tiles.get(change.position)
                    if previous is None:
                        raise ValueError(f"A keyed tile change requires its recorded tile {change.position}")
                    held = {row.residue_id for row in previous.residues}
                    written.new_residues.update((change.position, row.residue_id) for row in change.residues
                        if row.state is not None and row.residue_id not in held)
                    world.tiles[change.position] = apply_keyed_tile_change(previous, change)
                    written.tiles.append(change)
            elif event.change_type is SpatialChangeType.TILE_CHANGED:
                if event.tile_present is False:
                    world.tiles.pop(event.position, None)
                    written.replaced.add(event.position)
                elif event.tile_state is not None:
                    _put_tile(world, event.tile_state, written)
                elif (previous := world.tiles.get(event.position)) is not None:
                    fields = KeyedTileFields()
                    if event.tile_walking_cost is not None:
                        fields["walking_cost"] = event.tile_walking_cost
                    if event.tile_flying_cost is not None:
                        fields["flying_cost"] = event.tile_flying_cost
                    if event.tile_swimming_cost is not None:
                        fields["swimming_cost"] = event.tile_swimming_cost
                    if event.tile_burrowing_cost is not None:
                        fields["burrowing_cost"] = event.tile_burrowing_cost
                    if event.tile_blocks_optics is not None:
                        fields["blocks_optics"] = event.tile_blocks_optics
                    if event.tile_blocks_propagation is not None:
                        fields["blocks_propagation"] = event.tile_blocks_propagation
                    tile_updates: dict[str, object] = dict(fields)
                    if event.new_light_level is not None:
                        tile_updates["resolved_light"] = LightLevel(event.new_light_level)
                        written.light[event.position] = LightLevel(event.new_light_level)
                    world.tiles[event.position] = previous.model_copy(update=tile_updates)
                    if fields:
                        written.tile_fields.append((event.position, fields))
                else:
                    return None
            elif event.change_type is SpatialChangeType.TILE_REMOVED:
                world.tiles.pop(event.position, None)
                written.replaced.add(event.position)
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
                        # The event's after-value, whether or not an earlier version already wrote it.
                        written.light[position] = resolved
            elif event.change_type is SpatialChangeType.OBJECT_REMOVED and event.object_uuid is not None:
                _put_object(world, event.object_uuid, None, written)
            elif event.change_type in (SpatialChangeType.OBJECT_PLACED, SpatialChangeType.OBJECT_CHANGED):
                if event.object_uuid is None:
                    return None
                previous = world.objects.get(event.object_uuid)
                item = event.object_state or (previous.item if previous is not None else None)
                placement = event.placement or (previous.placement if previous is not None else None)
                if item is None or placement is None:
                    return None
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
                ), written, placed=event.placement is not None)
            else:
                return None
        case _:
            return None
    return written.applied()


def _put_tile(world: WorldFacts, tile: WorldTileState, written: _Written) -> None:
    """A tile written whole. Its surface and name never change for its uuid (a replaced tile has a new one), which
    is what lets a seat hold them as the tile's static row."""
    previous = world.tiles.get(tile.position)
    if (previous is not None and previous.tile_uuid == tile.tile_uuid
            and (previous.surface != tile.surface or previous.name != tile.name)):
        raise ValueError(f"A tile's surface and name never change for its uuid {tile.tile_uuid}")
    world.tiles[tile.position] = tile
    written.replaced.add(tile.position)


def _resulting_tile(world: WorldFacts, tile: WorldTileState, written: _Written) -> None:
    """A condition fact's tile after-value: the tile's own condition names change (its residues' follow them)."""
    world.tiles[tile.position] = tile
    written.tile_conditions[tile.position] = tile.condition_names[:len(tile.condition_names) - len(tile.residues)]
