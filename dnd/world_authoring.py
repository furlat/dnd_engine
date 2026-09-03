"""Explicit live-world authoring composition and cold state projections."""

from typing import Optional
from uuid import UUID, uuid4

from dnd.blocks.base_item import BaseItem
from dnd.blocks.inventory import Inventory
from dnd.core.base_block import BaseBlock, LightLevel, MovementMode
from dnd.core.base_tiles import (
    Tile,
    validate_elevation_surface_tuple,
    validate_tile_creation_inputs,
)
from dnd.core.events import (
    EventPhase,
    EventQueue,
    WorldConnectorState,
    WorldMaterializedState,
    WorldModifiedEvent,
    WorldObjectState,
    WorldTileState,
)
from dnd.core.gridmap import get_map
from dnd.core.traversal_connectors import (
    TraversalConnector,
    TraversalConnectorDefinition,
)
from dnd.core.values import ModifiableValue
from dnd.core.world_edges import ElevationSurfaceKind, SlopeAxis
from dnd.spatial.area_conditions import SpatialCondition
from dnd.types.materials import Material, TileSurface
from dnd.types.spatial_effects import SpatialEffectAnchorKind
from dnd.types.world import CardinalDirection
from dnd.types.world_placement import WorldObjectPlacement


def _movement_cost(tile: Tile, mode: MovementMode) -> int:
    """Return one exact integral authored movement multiplier."""
    cost = tile.get_movement_cost(mode)
    if int(cost) != cost:
        raise ValueError("authored Tile movement costs must be integral")
    return int(cost)


def _authored_cost(value: ModifiableValue) -> int:
    """Return the exact base cost owned by one Tile movement value."""
    modifier = value.get_base_modifier()
    if modifier is None or type(modifier.value) is not int:
        raise RuntimeError("Tile movement value has no exact base modifier")
    return modifier.value


def _validate_author(author_uuid: UUID, author_name: Optional[str]) -> None:
    """Validate root audit identity before any event is declared."""
    if type(author_uuid) is not UUID:
        raise TypeError("author_uuid must be a UUID")
    if author_name is not None and type(author_name) is not str:
        raise TypeError("author_name must be a string or None")


def _validate_position(position: tuple[int, int]) -> None:
    """Validate one exact objective Tile address."""
    if (
        type(position) is not tuple
        or len(position) != 2
        or any(type(coordinate) is not int for coordinate in position)
    ):
        raise TypeError("position must be a pair of exact integers")


def _begin_world_edit(event: WorldModifiedEvent) -> WorldModifiedEvent:
    """Advance one already-constructed authoring root to accepted EFFECT."""
    current = EventQueue.publish_declaration(event)
    if current.canceled:
        raise ValueError("world modification was canceled at declaration")
    current = current.phase_to(EventPhase.EXECUTION)
    if current.canceled:
        raise ValueError("world modification was canceled at execution")
    current = current.phase_to(EventPhase.EFFECT)
    if current.canceled:
        raise ValueError("world modification was canceled at effect")
    return current


def _complete_world_edit(
    effect: WorldModifiedEvent,
    after: Optional[WorldMaterializedState],
) -> WorldModifiedEvent:
    """Complete one accepted root with its detached authoritative after-state."""
    return effect.phase_to(EventPhase.COMPLETION, after=after)


def project_world_tile(tile: Tile) -> WorldTileState:
    """Project one live support Tile into its detached materialized state."""
    return WorldTileState(
        tile_uuid=tile.uuid,
        position=tile.position,
        surface=tile.surface,
        name=tile.name,
        blocks_optics=tile.blocks_optics,
        blocks_propagation=tile.blocks_propagation_field,
        walking_cost=_movement_cost(tile, MovementMode.WALKING),
        flying_cost=_movement_cost(tile, MovementMode.FLYING),
        swimming_cost=_movement_cost(tile, MovementMode.SWIMMING),
        burrowing_cost=_movement_cost(tile, MovementMode.BURROWING),
        elevation_steps=tile.height,
        surface_kind=tile.elevation_surface_kind,
        slope_axis=tile.slope_axis,
        default_light=tile.default_light,
        resolved_light=tile.resolved_light_level,
    )


def project_world_object(
    item: BaseItem,
    placement: WorldObjectPlacement,
) -> WorldObjectState:
    """Project one placed BaseItem and its direct Inventory contents."""
    if placement.object_uuid != item.uuid:
        raise ValueError("placement does not identify the projected BaseItem")
    storage = item.get_storage_block()
    contained_items = (
        tuple(
            child.to_item_presentation_state()
            for child in sorted(
                storage.items.values(),
                key=lambda child: str(child.uuid),
            )
        )
        if isinstance(storage, Inventory)
        else ()
    )
    return WorldObjectState(
        placement=placement,
        item=item.to_item_presentation_state(),
        contained_items=contained_items,
    )


def project_world_connector(
    connector: TraversalConnector,
) -> WorldConnectorState:
    """Project one live connector without runtime integrity derivations."""
    return WorldConnectorState(
        connector_uuid=connector.uuid,
        authored_id=connector.authored_id,
        kind=connector.kind,
        presentation_key=connector.presentation_key,
        endpoints=tuple(endpoint.position for endpoint in connector.endpoints),
        support_tile_uuids=tuple(
            endpoint.support_tile_uuid for endpoint in connector.endpoints
        ),
        endpoint_elevations_feet=tuple(
            endpoint.elevation_feet for endpoint in connector.endpoints
        ),
        movement_cost_feet=connector.movement_cost_feet,
        action_cost_type=connector.action_cost_type,
        action_cost_amount=connector.action_cost_amount,
        bidirectional=connector.bidirectional,
        enabled=connector.enabled,
        provocation_policy=connector.provocation_policy,
    )


def _validate_registered_world_item(item: BaseItem) -> None:
    """Require the exact registered BaseItem supported by cold projection."""
    if not isinstance(item, BaseItem):
        raise TypeError("world object authoring requires a BaseItem")
    if BaseBlock.get(item.uuid) is not item:
        raise ValueError("world object authoring requires the registered BaseItem")


def _validate_unowned_world_item(item: BaseItem) -> None:
    """Reject inventory, equipment, and owner authority at this boundary."""
    if item.owner_uuid is not None:
        raise ValueError("world item has owner authority")
    if item.stored_in_uuid is not None:
        raise ValueError("world item has container authority")
    if item.is_equipped or item.equipped_slot is not None:
        raise ValueError("world item has equipment authority")


def _validate_new_floor_item(item: BaseItem) -> None:
    """Require one item with no existing or mirrored floor placement."""
    _validate_registered_world_item(item)
    _validate_unowned_world_item(item)
    if item.tile_uuid is not None:
        raise ValueError("world item already has floor authority")
    if get_map().get_object_placement(item.uuid) is not None:
        raise ValueError("world item is already placed")


def _validate_live_floor_item(item: BaseItem) -> WorldObjectPlacement:
    """Return the exact live placement agreeing with the BaseItem mirror."""
    _validate_registered_world_item(item)
    _validate_unowned_world_item(item)
    placement = get_map().get_object_placement(item.uuid)
    if placement is None:
        raise ValueError("world item is not placed")
    if item.position != placement.position or item.tile_uuid != placement.tile_uuid:
        raise ValueError("world item floor mirror disagrees with GridMap")
    tile = get_map().get_tile(*placement.position)
    if tile is None or tile.uuid != placement.tile_uuid:
        raise ValueError("world item support Tile is no longer current")
    return placement


def _reject_attached_spatial_condition(item_uuid: UUID) -> None:
    """Reject position-changing edits while one live condition uses the anchor."""
    for condition in get_map().get_spatial_conditions():
        if (
            isinstance(condition, SpatialCondition)
            and condition.anchor_kind is SpatialEffectAnchorKind.WORLD_OBJECT
            and condition.anchor_uuid == item_uuid
        ):
            raise ValueError("world item anchors an active spatial condition")


def place_world_item(
    item: BaseItem,
    position: tuple[int, int],
    *,
    author_uuid: UUID,
    author_name: Optional[str] = None,
    boundary_direction: Optional[CardinalDirection] = None,
    base_height_steps: Optional[int] = None,
    orientation: Optional[CardinalDirection] = None,
) -> WorldModifiedEvent:
    """Place one unowned registered BaseItem through its existing owner."""
    _validate_author(author_uuid, author_name)
    _validate_new_floor_item(item)
    _validate_position(position)
    grid = get_map()
    candidate = grid.validate_object_placement(
        item.uuid,
        position,
        boundary_direction=boundary_direction,
        base_height_steps=base_height_steps,
        orientation=orientation,
    )
    _reject_attached_spatial_condition(item.uuid)
    effect = _begin_world_edit(
        WorldModifiedEvent(
            source_entity_uuid=author_uuid,
            source_entity_name=author_name,
            object_uuid=item.uuid,
            before=None,
            phase=EventPhase.DECLARATION,
            use_register=False,
        )
    )
    try:
        placement = item.place_on_grid(
            candidate.position,
            boundary_direction=candidate.boundary_direction,
            base_height_steps=candidate.base_height_steps,
            orientation=candidate.orientation,
            parent_event=effect.uuid,
        )
    except ValueError as error:
        effect.cancel(str(error))
        raise
    return _complete_world_edit(effect, project_world_object(item, placement))


def move_world_item(
    item: BaseItem,
    position: tuple[int, int],
    *,
    author_uuid: UUID,
    author_name: Optional[str] = None,
    boundary_direction: Optional[CardinalDirection] = None,
    base_height_steps: Optional[int] = None,
    orientation: Optional[CardinalDirection] = None,
) -> Optional[WorldModifiedEvent]:
    """Move one exact floor item without creating another location authority."""
    _validate_author(author_uuid, author_name)
    previous = _validate_live_floor_item(item)
    _validate_position(position)
    grid = get_map()
    candidate = grid.validate_object_placement(
        item.uuid,
        position,
        boundary_direction=boundary_direction,
        base_height_steps=base_height_steps,
        orientation=orientation,
    )
    if candidate == previous:
        return None
    _reject_attached_spatial_condition(item.uuid)
    before = project_world_object(item, previous)
    effect = _begin_world_edit(
        WorldModifiedEvent(
            source_entity_uuid=author_uuid,
            source_entity_name=author_name,
            object_uuid=item.uuid,
            before=before,
            phase=EventPhase.DECLARATION,
            use_register=False,
        )
    )
    try:
        placement = grid.move_object(
            item.uuid,
            candidate.position,
            parent_event=effect.uuid,
            boundary_direction=candidate.boundary_direction,
            base_height_steps=candidate.base_height_steps,
            orientation=candidate.orientation,
        )
    except ValueError as error:
        effect.cancel(str(error))
        raise
    item.synchronize_floor_placement(placement)
    return _complete_world_edit(effect, project_world_object(item, placement))


def orient_world_item(
    item: BaseItem,
    orientation: Optional[CardinalDirection],
    *,
    author_uuid: UUID,
    author_name: Optional[str] = None,
) -> Optional[WorldModifiedEvent]:
    """Change one floor item's facing without disturbing its anchored mechanics."""
    _validate_author(author_uuid, author_name)
    previous = _validate_live_floor_item(item)
    grid = get_map()
    candidate = grid.validate_object_placement(
        item.uuid,
        previous.position,
        boundary_direction=previous.boundary_direction,
        base_height_steps=previous.base_height_steps,
        orientation=orientation,
    )
    if candidate == previous:
        return None
    before = project_world_object(item, previous)
    effect = _begin_world_edit(
        WorldModifiedEvent(
            source_entity_uuid=author_uuid,
            source_entity_name=author_name,
            object_uuid=item.uuid,
            before=before,
            phase=EventPhase.DECLARATION,
            use_register=False,
        )
    )
    try:
        placement = grid.orient_object(
            item.uuid,
            orientation,
            parent_event=effect.uuid,
        )
    except ValueError as error:
        effect.cancel(str(error))
        raise
    item.synchronize_floor_placement(placement)
    return _complete_world_edit(effect, project_world_object(item, placement))


def remove_world_item(
    item: BaseItem,
    *,
    author_uuid: UUID,
    author_name: Optional[str] = None,
) -> WorldModifiedEvent:
    """Remove one world placement without destroying or unregistering its item."""
    _validate_author(author_uuid, author_name)
    previous = _validate_live_floor_item(item)
    _reject_attached_spatial_condition(item.uuid)
    before = project_world_object(item, previous)
    effect = _begin_world_edit(
        WorldModifiedEvent(
            source_entity_uuid=author_uuid,
            source_entity_name=author_name,
            object_uuid=item.uuid,
            before=before,
            phase=EventPhase.DECLARATION,
            use_register=False,
        )
    )
    removed = get_map().remove_object(
        item.uuid,
        parent_event=effect.uuid,
        clear_object_location=False,
    )
    if not removed:
        message = "world item removal was canceled"
        effect.cancel(message)
        raise ValueError(message)
    item.synchronize_floor_placement(None)
    return _complete_world_edit(effect, None)


def register_world_connector(
    definition: TraversalConnectorDefinition,
    *,
    author_uuid: UUID,
    author_name: Optional[str] = None,
    connector_uuid: Optional[UUID] = None,
) -> WorldModifiedEvent:
    """Register one supported immutable connector under a structural root."""
    _validate_author(author_uuid, author_name)
    if not isinstance(definition, TraversalConnectorDefinition):
        raise TypeError("definition must be a TraversalConnectorDefinition")
    if connector_uuid is not None and type(connector_uuid) is not UUID:
        raise TypeError("connector_uuid must be a UUID or None")
    grid = get_map()
    if grid.get_connector_by_authored_id(definition.authored_id) is not None:
        raise ValueError(f"duplicate connector authored_id {definition.authored_id}")
    runtime_uuid = connector_uuid or uuid4()
    if grid.get_connector(runtime_uuid) is not None:
        raise ValueError(f"duplicate connector UUID {runtime_uuid}")
    grid.validate_connector_candidate(
        definition,
        connector_uuid=runtime_uuid,
    )
    effect = _begin_world_edit(
        WorldModifiedEvent(
            source_entity_uuid=author_uuid,
            source_entity_name=author_name,
            connector_uuid=runtime_uuid,
            before=None,
            phase=EventPhase.DECLARATION,
            use_register=False,
        )
    )
    connector = grid.register_connector(
        definition,
        connector_uuid=runtime_uuid,
        parent_event=effect.uuid,
    )
    if connector is None:
        message = "world connector registration was canceled"
        effect.cancel(message)
        raise ValueError(message)
    return _complete_world_edit(effect, project_world_connector(connector))


def replace_world_connector(
    connector_uuid: UUID,
    definition: TraversalConnectorDefinition,
    *,
    author_uuid: UUID,
    author_name: Optional[str] = None,
) -> Optional[WorldModifiedEvent]:
    """Replace connector mechanics while preserving its two authored identities."""
    _validate_author(author_uuid, author_name)
    if type(connector_uuid) is not UUID:
        raise TypeError("connector_uuid must be a UUID")
    if not isinstance(definition, TraversalConnectorDefinition):
        raise TypeError("definition must be a TraversalConnectorDefinition")
    grid = get_map()
    previous = grid.get_connector(connector_uuid)
    if previous is None:
        raise ValueError(f"unknown connector {connector_uuid}")
    if definition.authored_id != previous.authored_id:
        raise ValueError("connector replacement must preserve authored_id")
    if definition == previous.definition():
        return None
    grid.validate_connector_candidate(
        definition,
        connector_uuid=connector_uuid,
        revision=previous.revision + 1,
    )
    before = project_world_connector(previous)
    effect = _begin_world_edit(
        WorldModifiedEvent(
            source_entity_uuid=author_uuid,
            source_entity_name=author_name,
            connector_uuid=connector_uuid,
            before=before,
            phase=EventPhase.DECLARATION,
            use_register=False,
        )
    )
    replacement = grid.replace_connector(
        connector_uuid,
        definition,
        parent_event=effect.uuid,
    )
    if replacement is None:
        message = "world connector replacement was canceled"
        effect.cancel(message)
        raise ValueError(message)
    return _complete_world_edit(
        effect,
        project_world_connector(replacement),
    )


def set_world_connector_enabled(
    connector_uuid: UUID,
    enabled: bool,
    *,
    author_uuid: UUID,
    author_name: Optional[str] = None,
) -> Optional[WorldModifiedEvent]:
    """Enable or disable one connector through its existing typed owner."""
    _validate_author(author_uuid, author_name)
    if type(connector_uuid) is not UUID:
        raise TypeError("connector_uuid must be a UUID")
    if type(enabled) is not bool:
        raise TypeError("enabled must be an exact bool")
    grid = get_map()
    previous = grid.get_connector(connector_uuid)
    if previous is None:
        raise ValueError(f"unknown connector {connector_uuid}")
    if previous.enabled is enabled:
        return None
    definition = previous.definition().model_copy(update={"enabled": enabled})
    grid.validate_connector_candidate(
        definition,
        connector_uuid=connector_uuid,
        revision=previous.revision + 1,
    )
    before = project_world_connector(previous)
    effect = _begin_world_edit(
        WorldModifiedEvent(
            source_entity_uuid=author_uuid,
            source_entity_name=author_name,
            connector_uuid=connector_uuid,
            before=before,
            phase=EventPhase.DECLARATION,
            use_register=False,
        )
    )
    replacement = grid.set_connector_enabled(
        connector_uuid,
        enabled,
        parent_event=effect.uuid,
    )
    if replacement is None:
        message = "world connector state change was canceled"
        effect.cancel(message)
        raise ValueError(message)
    return _complete_world_edit(
        effect,
        project_world_connector(replacement),
    )


def remove_world_connector(
    connector_uuid: UUID,
    *,
    author_uuid: UUID,
    author_name: Optional[str] = None,
) -> Optional[WorldModifiedEvent]:
    """Remove one connector and its existing GridMap indexes."""
    _validate_author(author_uuid, author_name)
    if type(connector_uuid) is not UUID:
        raise TypeError("connector_uuid must be a UUID")
    grid = get_map()
    previous = grid.get_connector(connector_uuid)
    if previous is None:
        return None
    before = project_world_connector(previous)
    effect = _begin_world_edit(
        WorldModifiedEvent(
            source_entity_uuid=author_uuid,
            source_entity_name=author_name,
            connector_uuid=connector_uuid,
            before=before,
            phase=EventPhase.DECLARATION,
            use_register=False,
        )
    )
    if not grid.remove_connector(
        connector_uuid,
        parent_event=effect.uuid,
    ):
        message = "world connector removal was canceled"
        effect.cancel(message)
        raise ValueError(message)
    return _complete_world_edit(effect, None)


def set_world_tile(
    position: tuple[int, int],
    *,
    author_uuid: UUID,
    author_name: Optional[str] = None,
    surface: Optional[TileSurface] = None,
    name: str = "Floor",
    blocks_optics: bool = False,
    blocks_propagation: bool = False,
    walking_cost: int = 1,
    flying_cost: int = 1,
    swimming_cost: int = 0,
    burrowing_cost: int = 0,
    default_light: LightLevel = LightLevel.BRIGHT_LIGHT,
    height: int = 0,
    elevation_surface_kind: ElevationSurfaceKind = ElevationSurfaceKind.ORDINARY,
    slope_axis: Optional[SlopeAxis] = None,
) -> Optional[WorldModifiedEvent]:
    """Add or replace one semantic support Tile through its existing owner."""
    _validate_author(author_uuid, author_name)
    resolved_surface = (
        surface
        if surface is not None
        else TileSurface(base_material=Material.STONE)
    )
    validate_tile_creation_inputs(
        position,
        blocks_optics=blocks_optics,
        blocks_propagation=blocks_propagation,
        name=name,
        sprite_name=None,
        height=height,
        surface=resolved_surface,
        walking_cost=walking_cost,
        flying_cost=flying_cost,
        swimming_cost=swimming_cost,
        burrowing_cost=burrowing_cost,
        elevation_surface_kind=elevation_surface_kind,
        slope_axis=slope_axis,
        default_light=default_light,
    )
    grid = get_map()
    previous = grid.get_tile(*position)
    before = project_world_tile(previous) if previous is not None else None
    requested = (
        resolved_surface,
        name,
        blocks_optics,
        blocks_propagation,
        walking_cost,
        flying_cost,
        swimming_cost,
        burrowing_cost,
        default_light,
        height,
        elevation_surface_kind,
        slope_axis,
    )
    if previous is not None:
        current = (
            previous.surface,
            previous.name,
            previous.blocks_optics,
            previous.blocks_propagation_field,
            _authored_cost(previous.walking_cost),
            _authored_cost(previous.flying_cost),
            _authored_cost(previous.swimming_cost),
            _authored_cost(previous.burrowing_cost),
            previous.default_light,
            previous.height,
            previous.elevation_surface_kind,
            previous.slope_axis,
        )
        if current == requested:
            return None
        grid.validate_tile_detachment(position)

    effect = _begin_world_edit(
        WorldModifiedEvent(
            source_entity_uuid=author_uuid,
            source_entity_name=author_name,
            tile_position=position,
            before=before,
            phase=EventPhase.DECLARATION,
            use_register=False,
        )
    )
    try:
        tile = grid.set_tile(
            *position,
            blocks_optics=blocks_optics,
            blocks_propagation=blocks_propagation,
            name=name,
            surface=resolved_surface,
            walking_cost=walking_cost,
            flying_cost=flying_cost,
            swimming_cost=swimming_cost,
            burrowing_cost=burrowing_cost,
            height=height,
            elevation_surface_kind=elevation_surface_kind,
            slope_axis=slope_axis,
            default_light=default_light,
            parent_event=effect.uuid,
        )
    except ValueError as error:
        effect.cancel(str(error))
        raise
    return _complete_world_edit(effect, project_world_tile(tile))


def remove_world_tile(
    position: tuple[int, int],
    *,
    author_uuid: UUID,
    author_name: Optional[str] = None,
) -> Optional[WorldModifiedEvent]:
    """Remove one unreferenced support Tile through GridMap ownership."""
    _validate_author(author_uuid, author_name)
    _validate_position(position)
    grid = get_map()
    tile = grid.get_tile(*position)
    if tile is None:
        return None
    grid.validate_tile_detachment(position)
    before = project_world_tile(tile)
    effect = _begin_world_edit(
        WorldModifiedEvent(
            source_entity_uuid=author_uuid,
            source_entity_name=author_name,
            tile_position=position,
            before=before,
            phase=EventPhase.DECLARATION,
            use_register=False,
        )
    )
    if not grid.remove_tile(*position, parent_event=effect.uuid):
        message = "Tile removal was canceled"
        effect.cancel(message)
        raise ValueError(message)
    return _complete_world_edit(effect, None)


def set_world_tile_elevation(
    position: tuple[int, int],
    *,
    height: int,
    surface_kind: ElevationSurfaceKind,
    slope_axis: Optional[SlopeAxis],
    author_uuid: UUID,
    author_name: Optional[str] = None,
) -> Optional[WorldModifiedEvent]:
    """Edit one Tile's support tuple through its existing typed lifecycle."""
    _validate_author(author_uuid, author_name)
    _validate_position(position)
    validate_elevation_surface_tuple(height, surface_kind, slope_axis)
    grid = get_map()
    tile = grid.validate_tile_elevation_change(
        position,
        height=height,
        surface_kind=surface_kind,
        slope_axis=slope_axis,
    )
    if (
        tile.height,
        tile.elevation_surface_kind,
        tile.slope_axis,
    ) == (height, surface_kind, slope_axis):
        return None
    before = project_world_tile(tile)
    effect = _begin_world_edit(
        WorldModifiedEvent(
            source_entity_uuid=author_uuid,
            source_entity_name=author_name,
            tile_position=position,
            before=before,
            phase=EventPhase.DECLARATION,
            use_register=False,
        )
    )
    try:
        changed = grid.set_tile_elevation(
            position,
            height=height,
            surface_kind=surface_kind,
            slope_axis=slope_axis,
            parent_event=effect.uuid,
        )
    except ValueError as error:
        effect.cancel(str(error))
        raise
    if not changed:
        message = "Tile elevation change was canceled"
        effect.cancel(message)
        raise ValueError(message)
    return _complete_world_edit(effect, project_world_tile(tile))


def set_world_tile_base_light(
    position: tuple[int, int],
    *,
    level: LightLevel,
    author_uuid: UUID,
    author_name: Optional[str] = None,
) -> Optional[WorldModifiedEvent]:
    """Edit one Tile's authored ambient light without fake masked deltas."""
    _validate_author(author_uuid, author_name)
    _validate_position(position)
    if type(level) is not LightLevel:
        raise TypeError("level must be a LightLevel")
    grid = get_map()
    tile = grid.get_tile(*position)
    if tile is None:
        raise ValueError(f"light Tile not found at {position}")
    if tile.default_light is level:
        return None
    before = project_world_tile(tile)
    effect = _begin_world_edit(
        WorldModifiedEvent(
            source_entity_uuid=author_uuid,
            source_entity_name=author_name,
            tile_position=position,
            before=before,
            phase=EventPhase.DECLARATION,
            use_register=False,
        )
    )
    if not grid.set_tile_base_light(
        position,
        level,
        parent_event=effect.uuid,
    ):
        message = "Tile base-light change was canceled"
        effect.cancel(message)
        raise ValueError(message)
    return _complete_world_edit(effect, project_world_tile(tile))
