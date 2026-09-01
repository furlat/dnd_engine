"""Authored battlefields and their sole deterministic runtime builders."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, cast
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from dnd.content.items.authored_item_builders import build_authored_item
from dnd.content.items.environment_item_builders import (
    build_directional_door,
    build_directional_wall,
    build_fireball_cannon,
    build_storage_chest,
    build_wall_torch,
)
from dnd.core.content.battlefields import (
    BattlefieldDefinition,
    BattlefieldPreview,
    BattlefieldPreviewCell,
    BattlefieldPreviewDirection,
    BattlefieldPreviewObject,
    BattlefieldPreviewObjectKind,
    BattlefieldPreviewTerrain,
    LightLevelName,
)
from dnd.core.gridmap import GridMap, get_map
from dnd.core.base_block import BaseBlock, MovementMode
from dnd.core.base_conditions import BaseCondition
from dnd.core.base_tiles import Tile
from dnd.core.events import (
    EventPhase,
    EventQueue,
    WorldConnectorState,
    WorldInitializedEvent,
    WorldObjectState,
    WorldTileState,
)
from dnd.core.item_types import ItemLocation
from dnd.core.traversal_connectors import (
    ConnectorActionCostType,
    ConnectorProvocationPolicy,
    TraversalConnectorDefinition,
    TraversalConnectorKind,
)
from dnd.core.world_edges import ElevationSurfaceKind, SlopeAxis
from dnd.types.world import CardinalDirection
from dnd.items.consumables import build_healing_potion
from dnd.items.environment import DirectionalDoor, DirectionalWall
from dnd.items.environment_interactables import (
    StorageChest,
)
from dnd.blocks.base_item import BaseItem
from dnd.blocks.inventory import Inventory
from dnd.items.torches import WallTorch
from dnd.spatial.environmental_conditions import (
    materialize_spike_trap_condition,
)
from dnd.maps.arena_layout import (
    DIFFICULT_TERRAIN_POSITIONS,
    DOOR_DIRECTIONS,
    DOOR_POSITION,
    HEALING_POTION_POSITIONS,
    SPIKE_ZONE_POSITIONS,
    STANDARD_BLOCKING_CHANNELS,
    TRAP_LEVER_POSITION,
    WALL_DIRECTIONS,
    WALL_POSITIONS,
    WALL_TORCH_POSITIONS,
    WATER_POSITIONS,
    StandardArenaObjects,
    StandardBarrierObjects,
    build_standard_arena_environment,
    create_standard_arena_floor,
    darken_arena,
)
@dataclass(frozen=True)
class BuiltBattlefield:
    """Runtime objects created for one catalog battlefield."""

    definition: BattlefieldDefinition
    environment: StandardArenaObjects | None
    notable_positions: dict[str, tuple[int, int]]
    object_uuids: dict[str, UUID]


def _battlefield(
    battlefield_id: str,
    title: str,
    tags: tuple[str, ...],
    light_level: LightLevelName,
    capabilities: tuple[str, ...],
) -> BattlefieldDefinition:
    """Create one immutable battlefield catalog record."""
    return BattlefieldDefinition(
        battlefield_id=battlefield_id,
        title=title,
        tags=tags,
        light_level=light_level,
        capabilities=capabilities,
        preview=_preview_for_battlefield(battlefield_id),
    )


def _terrain_cell(
    position: tuple[int, int],
    terrain: BattlefieldPreviewTerrain,
    *,
    walkable: bool = True,
    walking_cost: int = 1,
    hazardous: bool = False,
) -> BattlefieldPreviewCell:
    """Create one non-default preview terrain cell."""
    return BattlefieldPreviewCell(
        position=position,
        terrain=terrain,
        walkable=walkable,
        walking_cost=walking_cost,
        hazardous=hazardous,
    )


def _preview_object(
    position: tuple[int, int],
    kind: BattlefieldPreviewObjectKind,
    label: str,
    *,
    blocked_directions: tuple[BattlefieldPreviewDirection, ...] = (),
    is_open: bool | None = None,
) -> BattlefieldPreviewObject:
    """Create one static preview object placement."""
    return BattlefieldPreviewObject(
        position=position,
        kind=kind,
        label=label,
        blocked_directions=blocked_directions,
        is_open=is_open,
    )


def _standard_hazards_preview(*, open_door: bool) -> BattlefieldPreview:
    """Project the shared standard hazard layout without constructing runtime objects."""
    cells = (
        *(_terrain_cell(position, "water", walkable=False) for position in WATER_POSITIONS),
        *(
            _terrain_cell(position, "difficult_terrain", walking_cost=2)
            for position in DIFFICULT_TERRAIN_POSITIONS
        ),
        *(
            _terrain_cell(position, "spikes", hazardous=True)
            for position in sorted(SPIKE_ZONE_POSITIONS)
        ),
    )
    objects = (
        *(
            _preview_object(
                position,
                "wall",
                "Wall",
                blocked_directions=cast(tuple[BattlefieldPreviewDirection, ...], WALL_DIRECTIONS),
            )
            for position in WALL_POSITIONS
        ),
        _preview_object(
            DOOR_POSITION,
            "door",
            "Door",
            blocked_directions=(
                ()
                if open_door
                else cast(tuple[BattlefieldPreviewDirection, ...], DOOR_DIRECTIONS)
            ),
            is_open=open_door,
        ),
        *(
            _preview_object(position, "wall_torch", "Wall Torch")
            for position in WALL_TORCH_POSITIONS
        ),
        *(
            _preview_object(position, "healing_potion", "Healing Potion")
            for position in HEALING_POTION_POSITIONS
        ),
        _preview_object(TRAP_LEVER_POSITION, "trap_lever", "Trap Lever"),
    )
    return BattlefieldPreview(cells=cells, objects=objects)


def _two_barrier_preview(*, first_door_y: int, second_door_y: int) -> BattlefieldPreview:
    """Project the paired directional barriers used by dark room maps."""
    objects = []
    for column, door_y, label in ((5, first_door_y, "First"), (9, second_door_y, "Second")):
        for y in range(3, 12):
            if y == door_y:
                objects.append(_preview_object(
                    (column, y),
                    "door",
                    f"{label} Door",
                    blocked_directions=("west",),
                    is_open=False,
                ))
            else:
                objects.append(_preview_object(
                    (column, y),
                    "wall",
                    f"{label} Wall",
                    blocked_directions=("west",),
                ))
    return BattlefieldPreview(objects=tuple(objects))


def _preview_for_battlefield(battlefield_id: str) -> BattlefieldPreview:
    """Return the canonical compact preview for one registered builder."""
    builder_id = battlefield_id.removeprefix("battlefield.")
    if builder_id in {"open_floor_bright", "open_floor_dark"}:
        return BattlefieldPreview()
    if builder_id == "standard_hazards_closed":
        return _standard_hazards_preview(open_door=False)
    if builder_id == "standard_hazards_open":
        return _standard_hazards_preview(open_door=True)
    if builder_id == "double_door_dark":
        return _two_barrier_preview(first_door_y=7, second_door_y=7)
    if builder_id == "reveal_labyrinth_dark":
        return _two_barrier_preview(first_door_y=6, second_door_y=8)
    if builder_id == "arcane_device_bright":
        return BattlefieldPreview(objects=(
            _preview_object((7, 7), "fireball_cannon", "Fireball Cannon"),
            _preview_object((6, 7), "healing_potion", "Healing Potion"),
        ))
    if builder_id == "field_cache_bright":
        return BattlefieldPreview(objects=(
            _preview_object((5, 7), "loot_chest", "Field Cache"),
        ))
    if builder_id == "multi_object_dark":
        standard = _standard_hazards_preview(open_door=True)
        return standard.model_copy(update={
            "objects": (
                *standard.objects,
                _preview_object((4, 10), "wall_torch", "Control-Room Torch"),
                _preview_object((6, 11), "fireball_cannon", "Fireball Cannon"),
                _preview_object((5, 10), "loot_chest", "Control Cache"),
            ),
        })
    if builder_id == "elevation_proving_ground":
        return BattlefieldPreview()
    raise ValueError(f"Unknown battlefield preview builder: {builder_id}")


BATTLEFIELDS: tuple[BattlefieldDefinition, ...] = (
    _battlefield(
        "battlefield.standard_hazards_closed",
        "Dark Standard Hazards With Closed Door",
        ("darkness", "door", "water", "difficult-terrain", "spikes", "objects"),
        "darkness",
        ("closed-door", "water", "difficult-terrain", "spike-zone", "trap-lever", "floor-loot", "wall-torches"),
    ),
    _battlefield(
        "battlefield.open_floor_bright",
        "Bright Open Floor",
        ("bright", "open-field"),
        "bright",
        ("open-floor", "bright-light"),
    ),
    _battlefield(
        "battlefield.standard_hazards_open",
        "Dark Standard Hazards With Open Door",
        ("darkness", "open-door", "water", "difficult-terrain", "spikes", "objects"),
        "darkness",
        ("open-door", "water", "difficult-terrain", "spike-zone", "trap-lever", "floor-loot", "wall-torches"),
    ),
    _battlefield(
        "battlefield.double_door_dark",
        "Dark Double-Door Rooms",
        ("darkness", "two-doors", "three-rooms"),
        "darkness",
        ("closed-door", "two-directional-barriers", "darkness"),
    ),
    _battlefield(
        "battlefield.arcane_device_bright",
        "Bright Arcane Device Floor",
        ("bright", "fireball-cannon", "floor-loot"),
        "bright",
        ("open-floor", "bright-light", "fireball-cannon", "floor-potion"),
    ),
    _battlefield(
        "battlefield.reveal_labyrinth_dark",
        "Dark Reveal Labyrinth",
        ("darkness", "two-doors", "offset-doors", "reveal"),
        "darkness",
        ("closed-door", "two-directional-barriers", "darkness"),
    ),
    _battlefield(
        "battlefield.field_cache_bright",
        "Bright Field Cache",
        ("bright", "loot-chest", "open-field"),
        "bright",
        ("open-floor", "bright-light", "loot-chest"),
    ),
    _battlefield(
        "battlefield.multi_object_dark",
        "Dark Multi-Object Control Room",
        ("darkness", "open-door", "chest", "cannon", "lever", "wall-torch"),
        "darkness",
        ("open-door", "water", "difficult-terrain", "spike-zone", "trap-lever", "loot-chest", "fireball-cannon", "wall-torches"),
    ),
    _battlefield(
        "battlefield.open_floor_dark",
        "Dark Open Floor",
        ("darkness", "open-field"),
        "darkness",
        ("open-floor", "darkness"),
    ),
)

_ELEVATION_PROVING_BATTLEFIELD = _battlefield(
    "battlefield.elevation_proving_ground",
    "Elevation And Vertical Traversal Proving Ground",
    ("bright", "stairs", "ramp", "connectors"),
    "bright",
    (
        "bright-light",
        "progressive-stairs",
        "progressive-ramp",
        "ladder",
        "rope",
        "lift",
        "vertical-stairs",
        "passage",
    ),
)

BATTLEFIELDS_BY_ID = {
    spec.battlefield_id: spec
    for spec in (*BATTLEFIELDS, _ELEVATION_PROVING_BATTLEFIELD)
}


def _empty_runtime(definition: BattlefieldDefinition) -> BuiltBattlefield:
    """Return a runtime result for an object-free floor."""
    return BuiltBattlefield(
        definition=definition,
        environment=None,
        notable_positions={},
        object_uuids={},
    )


def _build_open_floor_bright(definition: BattlefieldDefinition, grid: GridMap) -> BuiltBattlefield:
    """Build a bright object-free arena floor."""
    create_standard_arena_floor(grid)
    return _empty_runtime(definition)


def _build_open_floor_dark(definition: BattlefieldDefinition, grid: GridMap) -> BuiltBattlefield:
    """Build a dark object-free arena floor."""
    create_standard_arena_floor(grid)
    darken_arena(grid)
    return _empty_runtime(definition)


def _build_standard_hazards(
    definition: BattlefieldDefinition,
    grid: GridMap,
    *,
    open_door: bool,
) -> BuiltBattlefield:
    """Build the standard dark object and hazard package."""
    environment = build_standard_arena_environment(grid)
    if open_door:
        environment.barrier.door.open()
    door_position = grid.get_object_position(environment.barrier.door.uuid) or (7, 7)
    return BuiltBattlefield(
        definition=definition,
        environment=environment,
        notable_positions={"door": door_position},
        object_uuids={"door": environment.barrier.door.uuid},
    )


def _build_standard_hazards_closed(definition: BattlefieldDefinition, grid: GridMap) -> BuiltBattlefield:
    """Build the standard hazard package with its door closed."""
    return _build_standard_hazards(definition, grid, open_door=False)


def _build_standard_hazards_open(definition: BattlefieldDefinition, grid: GridMap) -> BuiltBattlefield:
    """Build the standard hazard package and open its door."""
    return _build_standard_hazards(definition, grid, open_door=True)


def _place_directional_barrier(
    grid: GridMap,
    *,
    column: int,
    door_y: int,
    label: str,
) -> StandardBarrierObjects:
    """Place the directional barrier shape used by the two legacy labyrinths."""
    walls: list[DirectionalWall] = []
    door: DirectionalDoor | None = None
    for y in range(3, 12):
        position = (column, y)
        grid.set_tile(column, y, name="Floor")
        if y == door_y:
            door = build_directional_door(
                display_name=f"{label} Door",
                blocked_channels=STANDARD_BLOCKING_CHANNELS,
                is_open=False,
            )
            door.place_on_grid(
                position,
                boundary_direction=CardinalDirection.WEST,
            )
        else:
            wall = build_directional_wall(
                display_name=f"{label} Wall",
                blocked_channels=STANDARD_BLOCKING_CHANNELS,
            )
            wall.place_on_grid(
                position,
                boundary_direction=CardinalDirection.WEST,
            )
            walls.append(wall)
    if door is None:
        raise ValueError("Directional barrier requires a door within rows 3 through 11.")
    return StandardBarrierObjects(door=door, walls=tuple(walls))


def _build_two_barriers(
    definition: BattlefieldDefinition,
    grid: GridMap,
    *,
    first_door_y: int,
    second_door_y: int,
    labels: tuple[str, str],
) -> BuiltBattlefield:
    """Build a dark floor with two independent directional barriers."""
    create_standard_arena_floor(grid)
    first = _place_directional_barrier(grid, column=5, door_y=first_door_y, label=labels[0])
    second = _place_directional_barrier(grid, column=9, door_y=second_door_y, label=labels[1])
    darken_arena(grid)
    first_position = grid.get_object_position(first.door.uuid) or (5, first_door_y)
    second_position = grid.get_object_position(second.door.uuid) or (9, second_door_y)
    return BuiltBattlefield(
        definition=definition,
        environment=None,
        notable_positions={"first_door": first_position, "second_door": second_position},
        object_uuids={"first_door": first.door.uuid, "second_door": second.door.uuid},
    )


def _build_double_door_dark(
    definition: BattlefieldDefinition,
    grid: GridMap,
) -> BuiltBattlefield:
    """Build the aligned two-door dark hunt floor."""
    return _build_two_barriers(
        definition,
        grid,
        first_door_y=7,
        second_door_y=7,
        labels=("First", "Second"),
    )


def _build_reveal_labyrinth_dark(
    definition: BattlefieldDefinition,
    grid: GridMap,
) -> BuiltBattlefield:
    """Build the offset-door darkness/reveal labyrinth."""
    return _build_two_barriers(
        definition,
        grid,
        first_door_y=6,
        second_door_y=8,
        labels=("Shadow", "Dawn"),
    )


def _build_arcane_device_bright(
    definition: BattlefieldDefinition,
    grid: GridMap,
) -> BuiltBattlefield:
    """Build the bright open floor with a Fireball cannon and healing potion."""
    create_standard_arena_floor(grid)
    cannon = build_fireball_cannon(charges=2)
    cannon.place_on_grid((7, 7))
    potion = build_healing_potion(uuid4(), heal_amount=12)
    potion.place_on_grid((6, 7))
    return BuiltBattlefield(
        definition=definition,
        environment=None,
        notable_positions={"fireball_cannon": (7, 7), "floor_potion": (6, 7)},
        object_uuids={"fireball_cannon": cannon.uuid, "floor_potion": potion.uuid},
    )


def _create_cache(name: str, *, heal_amount: int, include_full_loadout: bool) -> StorageChest:
    """Create one environment-owned loot chest."""
    chest = build_storage_chest(
        name,
        include_loot_all_action=True,
    )
    if include_full_loadout:
        chest.chest_inventory.add_item(build_authored_item(
            "spell_item.scroll_fireball",
            chest.uuid,
        ))
    chest.chest_inventory.add_item(build_authored_item(
        "spell_item.scroll_magic_missile",
        chest.uuid,
    ))
    chest.chest_inventory.add_item(build_authored_item(
        "consumable.acid_flask",
        chest.uuid,
    ))
    chest.chest_inventory.add_item(
        build_healing_potion(chest.uuid, heal_amount=heal_amount)
    )
    if include_full_loadout:
        chest.chest_inventory.add_item(
            build_authored_item("consumable.weapon_coat.fire", chest.uuid)
        )
    return chest


def _build_field_cache_bright(
    definition: BattlefieldDefinition,
    grid: GridMap,
) -> BuiltBattlefield:
    """Build the bright floor with the complete field-cache chest."""
    create_standard_arena_floor(grid)
    chest = _create_cache("Validation Field Cache", heal_amount=14, include_full_loadout=True)
    chest.place_on_grid((5, 7))
    return BuiltBattlefield(
        definition=definition,
        environment=None,
        notable_positions={"field_cache": (5, 7)},
        object_uuids={"field_cache": chest.uuid},
    )


def _build_multi_object_dark(
    definition: BattlefieldDefinition,
    grid: GridMap,
) -> BuiltBattlefield:
    """Build the standard floor plus the control-room object package."""
    environment = build_standard_arena_environment(grid)
    environment.barrier.door.open()
    wall_torch = build_wall_torch()
    wall_torch.mount((4, 10), lit=False)
    cannon = build_fireball_cannon(charges=2)
    cannon.place_on_grid((6, 11))
    chest = _create_cache("Validation Control Cache", heal_amount=12, include_full_loadout=False)
    chest.place_on_grid((5, 10))
    return BuiltBattlefield(
        definition=definition,
        environment=environment,
        notable_positions={
            "door": (7, 7),
            "control_cache": (5, 10),
            "wall_torch": (4, 10),
            "fireball_cannon": (6, 11),
        },
        object_uuids={
            "door": environment.barrier.door.uuid,
            "control_cache": chest.uuid,
            "wall_torch": wall_torch.uuid,
            "fireball_cannon": cannon.uuid,
        },
    )


_ELEVATION_PROVING_ROWS = (
    ((5, 4), 0, ElevationSurfaceKind.STAIRS, SlopeAxis.EAST_WEST),
    ((6, 4), 1, ElevationSurfaceKind.STAIRS, SlopeAxis.EAST_WEST),
    ((7, 4), 2, ElevationSurfaceKind.STAIRS, SlopeAxis.EAST_WEST),
    ((8, 4), 2, ElevationSurfaceKind.ORDINARY, None),
    ((5, 10), 2, ElevationSurfaceKind.ORDINARY, None),
    ((6, 10), 2, ElevationSurfaceKind.RAMP, SlopeAxis.EAST_WEST),
    ((7, 10), 1, ElevationSurfaceKind.RAMP, SlopeAxis.EAST_WEST),
    ((8, 10), 0, ElevationSurfaceKind.RAMP, SlopeAxis.EAST_WEST),
    ((2, 12), 1, ElevationSurfaceKind.ORDINARY, None),
    ((4, 12), 1, ElevationSurfaceKind.ORDINARY, None),
    ((6, 12), 2, ElevationSurfaceKind.ORDINARY, None),
    ((8, 12), 1, ElevationSurfaceKind.ORDINARY, None),
    ((12, 13), 2, ElevationSurfaceKind.ORDINARY, None),
)

_ELEVATION_PROVING_CONNECTORS = (
    TraversalConnectorDefinition(
        authored_id="connector.proving.ladder",
        kind=TraversalConnectorKind.LADDER,
        presentation_key="traversal.ladder",
        endpoint_positions=((1, 12), (2, 12)),
        movement_cost_feet=10,
        action_cost_type=None,
        action_cost_amount=0,
        bidirectional=True,
        enabled=True,
        provocation_policy=(
            ConnectorProvocationPolicy.PROVOKES_SOURCE_EXIT
        ),
    ),
    TraversalConnectorDefinition(
        authored_id="connector.proving.rope",
        kind=TraversalConnectorKind.ROPE,
        presentation_key="traversal.rope",
        endpoint_positions=((3, 12), (4, 12)),
        movement_cost_feet=10,
        action_cost_type=ConnectorActionCostType.ACTIONS,
        action_cost_amount=1,
        bidirectional=True,
        enabled=True,
        provocation_policy=(
            ConnectorProvocationPolicy.PROVOKES_SOURCE_EXIT
        ),
    ),
    TraversalConnectorDefinition(
        authored_id="connector.proving.lift",
        kind=TraversalConnectorKind.LIFT,
        presentation_key="traversal.lift",
        endpoint_positions=((5, 12), (6, 12)),
        movement_cost_feet=5,
        action_cost_type=ConnectorActionCostType.BONUS_ACTIONS,
        action_cost_amount=1,
        bidirectional=True,
        enabled=True,
        provocation_policy=(
            ConnectorProvocationPolicy.DOES_NOT_PROVOKE
        ),
    ),
    TraversalConnectorDefinition(
        authored_id="connector.proving.vertical_stairs",
        kind=TraversalConnectorKind.VERTICAL_STAIRS,
        presentation_key="traversal.vertical_stairs",
        endpoint_positions=((7, 12), (8, 12)),
        movement_cost_feet=10,
        action_cost_type=None,
        action_cost_amount=0,
        bidirectional=True,
        enabled=True,
        provocation_policy=(
            ConnectorProvocationPolicy.DOES_NOT_PROVOKE
        ),
    ),
    TraversalConnectorDefinition(
        authored_id="connector.proving.passage",
        kind=TraversalConnectorKind.PASSAGE,
        presentation_key="traversal.passage",
        endpoint_positions=((1, 13), (12, 13)),
        movement_cost_feet=15,
        action_cost_type=ConnectorActionCostType.ACTIONS,
        action_cost_amount=1,
        bidirectional=False,
        enabled=True,
        provocation_policy=(
            ConnectorProvocationPolicy.DOES_NOT_PROVOKE
        ),
    ),
)


def _build_elevation_proving_ground(
    definition: BattlefieldDefinition,
    grid: GridMap,
) -> BuiltBattlefield:
    """Build the maintained typed elevation and connector proving world."""
    create_standard_arena_floor(grid)
    for position, height, surface_kind, slope_axis in _ELEVATION_PROVING_ROWS:
        if not grid.set_tile_elevation(
            position,
            height=height,
            surface_kind=surface_kind,
            slope_axis=slope_axis,
        ):
            raise RuntimeError(
                f"battlefield elevation was rejected at {position}",
            )
    connector_uuids: dict[str, UUID] = {}
    for connector_definition in _ELEVATION_PROVING_CONNECTORS:
        connector = grid.register_connector(connector_definition)
        if connector is None:
            raise RuntimeError(
                "battlefield connector was rejected: "
                f"{connector_definition.authored_id}",
            )
        connector_uuids[connector.authored_id] = connector.uuid
    return BuiltBattlefield(
        definition=definition,
        environment=None,
        notable_positions={
            "stairs_start": (5, 4),
            "stairs_top": (8, 4),
            "ramp_top": (5, 10),
            "ramp_end": (8, 10),
        },
        object_uuids=connector_uuids,
    )


BattlefieldBuilder = Callable[
    [BattlefieldDefinition, GridMap],
    BuiltBattlefield,
]

_BUILDERS: dict[str, BattlefieldBuilder] = {
    "battlefield.standard_hazards_closed": _build_standard_hazards_closed,
    "battlefield.open_floor_bright": _build_open_floor_bright,
    "battlefield.standard_hazards_open": _build_standard_hazards_open,
    "battlefield.double_door_dark": _build_double_door_dark,
    "battlefield.arcane_device_bright": _build_arcane_device_bright,
    "battlefield.reveal_labyrinth_dark": _build_reveal_labyrinth_dark,
    "battlefield.field_cache_bright": _build_field_cache_bright,
    "battlefield.multi_object_dark": _build_multi_object_dark,
    "battlefield.open_floor_dark": _build_open_floor_dark,
    "battlefield.elevation_proving_ground": _build_elevation_proving_ground,
}


def get_battlefield(battlefield_id: str) -> BattlefieldDefinition:
    """Return one canonical battlefield by stable identifier."""
    try:
        return BATTLEFIELDS_BY_ID[battlefield_id]
    except KeyError as exc:
        raise ValueError(f"Unknown battlefield: {battlefield_id}") from exc


def build_battlefield(battlefield_id: str) -> BuiltBattlefield:
    """Construct one cold battlefield, publish it, then settle dynamics."""
    definition = get_battlefield(battlefield_id)
    builder = _BUILDERS[battlefield_id]
    grid = get_map()
    if EventQueue.event_cursor() != 0:
        raise ValueError("authored battlefield requires an empty EventQueue")
    if (
        grid.get_all_tiles()
        or grid.iter_object_placements()
        or grid.get_all_connectors()
        or grid.get_spatial_conditions()
    ):
        raise ValueError("authored battlefield requires an empty GridMap")
    if any(isinstance(block, Tile) for block in BaseBlock._registry.values()):
        raise ValueError("authored battlefield requires no registered Tile")

    grid.disable_events()
    try:
        built = builder(definition, grid)
        world_event = _world_initialized_event(built, grid)
        _validate_cold_world(built, grid, world_event)
    except Exception:
        grid.enable_events(flush_pending=False)
        raise

    grid.enable_events(flush_pending=False)
    published_world = EventQueue.publish_completed_fact(world_event)
    _materialize_authored_spike_traps(built, published_world)
    _settle_authored_wall_torches(grid, published_world)
    return built


def _movement_cost(tile: Tile, mode: MovementMode) -> int:
    """Return one exact integral authored movement multiplier."""
    cost = tile.get_movement_cost(mode)
    if int(cost) != cost:
        raise ValueError("authored Tile movement costs must be integral")
    return int(cost)


def _world_initialized_event(
    built: BuiltBattlefield,
    grid: GridMap,
) -> WorldInitializedEvent:
    """Snapshot the complete actor-free cold world."""
    tiles = tuple(
        WorldTileState(
            tile_uuid=tile.uuid,
            position=position,
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
        for position, tile in sorted(grid.get_all_tiles().items())
    )
    objects: list[WorldObjectState] = []
    for placement in sorted(
        grid.iter_object_placements(),
        key=lambda row: (row.position, str(row.object_uuid)),
    ):
        item = BaseBlock.get(placement.object_uuid)
        if not isinstance(item, BaseItem):
            raise RuntimeError(
                f"world object {placement.object_uuid} is not a BaseItem",
            )
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
        objects.append(WorldObjectState(
            placement=placement,
            item=item.to_item_presentation_state(),
            contained_items=contained_items,
        ))
    connectors = tuple(
        WorldConnectorState(
            connector_uuid=connector.uuid,
            authored_id=connector.authored_id,
            kind=connector.kind,
            endpoints=(
                connector.endpoints[0].position,
                connector.endpoints[1].position,
            ),
            endpoint_elevations_feet=(
                connector.endpoints[0].elevation_feet,
                connector.endpoints[1].elevation_feet,
            ),
            movement_cost_feet=connector.movement_cost_feet,
            action_cost_type=connector.action_cost_type,
            action_cost_amount=connector.action_cost_amount,
            bidirectional=connector.bidirectional,
            enabled=connector.enabled,
            provocation_policy=connector.provocation_policy,
        )
        for connector in grid.get_all_connectors()
    )
    return WorldInitializedEvent(
        source_entity_uuid=uuid5(
            NAMESPACE_URL,
            f"dnd-engine-world:{built.definition.battlefield_id}",
        ),
        source_entity_name="World",
        phase=EventPhase.COMPLETION,
        use_register=False,
        battlefield_id=built.definition.battlefield_id,
        battlefield_name=built.definition.title,
        bounds=grid.bounds,
        width=grid.width,
        height=grid.height,
        tiles=tiles,
        objects=tuple(objects),
        connectors=connectors,
    )


def _validate_cold_world(
    built: BuiltBattlefield,
    grid: GridMap,
    world_event: WorldInitializedEvent,
) -> None:
    """Reject a partial or dynamically contaminated cold world."""
    if EventQueue.event_cursor() != 0:
        raise RuntimeError("cold authored build advanced the EventQueue")
    live_tiles = grid.get_all_tiles()
    if {row.position: row.tile_uuid for row in world_event.tiles} != {
        position: tile.uuid for position, tile in live_tiles.items()
    }:
        raise RuntimeError("cold world Tile closure does not match GridMap")
    registered_tiles = {
        block_uuid: block
        for block_uuid, block in BaseBlock._registry.items()
        if isinstance(block, Tile)
    }
    if registered_tiles != {tile.uuid: tile for tile in live_tiles.values()}:
        raise RuntimeError("cold world registered Tile closure is not exact")
    if any(
        tile.get_entity_uuids()
        or tile.active_conditions_by_uuid
        or tile.get_spatial_condition_uuids()
        for tile in live_tiles.values()
    ):
        raise RuntimeError("cold world contains occupancy or conditions")
    if grid.get_spatial_conditions():
        raise RuntimeError("cold world owns a SpatialCondition")
    if {row.placement for row in world_event.objects} != set(
        grid.iter_object_placements()
    ):
        raise RuntimeError("cold world object closure does not match GridMap")
    for row in world_event.objects:
        item = BaseBlock.get(row.item.item_uuid)
        if isinstance(item, WallTorch) and (
            item.is_lit or item.get_attached_light_sources()
        ):
            raise RuntimeError("cold authored WallTorch is lit")
    if built.environment is not None:
        condition_uuid = built.environment.spike_condition_uuid
        if BaseCondition.get(condition_uuid) is not None:
            raise RuntimeError("reserved SpikeTrap identity is already live")
        if (
            built.environment.trap_lever.to_item_presentation_state()
            .linked_spatial_condition_uuid
            != condition_uuid
        ):
            raise RuntimeError("TrapLever does not expose its reserved trap identity")


def _materialize_authored_spike_traps(
    built: BuiltBattlefield,
    parent_event: WorldInitializedEvent,
) -> None:
    """Activate each reserved authored trap through its ordinary lifecycle."""
    if built.environment is None:
        return
    condition_uuid = built.environment.spike_condition_uuid
    condition = materialize_spike_trap_condition(
        set(SPIKE_ZONE_POSITIONS),
        condition_uuid=condition_uuid,
        parent_event=parent_event,
    )
    if condition.uuid != condition_uuid:
        raise RuntimeError("SpikeTrap materialization changed reserved identity")


def _settle_authored_wall_torches(
    grid: GridMap,
    parent_event: WorldInitializedEvent,
) -> None:
    """Light cold-authored torches and publish their complete live facts."""
    for placement in sorted(
        grid.iter_object_placements(),
        key=lambda row: (row.position, str(row.object_uuid)),
    ):
        item = BaseBlock.get(placement.object_uuid)
        if not isinstance(item, WallTorch):
            continue
        ignite = item.light(parent_event=parent_event.uuid)
        attached_light_sources = item.get_attached_light_sources()
        if (
            ignite is None
            or ignite.canceled
            or ignite.phase is not EventPhase.COMPLETION
            or not item.is_lit
            or len(attached_light_sources) != 1
            or grid.get_light_source_position(next(iter(attached_light_sources)))
            != placement.position
        ):
            raise RuntimeError("authored WallTorch did not publish IGNITE")
        item.publish_location_state(
            ItemLocation.FLOOR,
            world_placement=placement,
            parent_event=ignite,
        )
