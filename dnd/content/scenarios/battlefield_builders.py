"""Deterministic runtime builders for the cold authored battlefields."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from dnd.blocks.base_item import BaseItem
from dnd.blocks.inventory import Inventory
from dnd.core.base_block import BaseBlock
from dnd.core.base_conditions import BaseCondition
from dnd.core.base_tiles import Tile
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.content.items.environment_item_builders import (
    build_directional_door,
    build_directional_wall,
    build_cliff_face,
    build_fireball_cannon,
    build_storage_chest,
    build_wall_torch,
)
from dnd.content.scenarios.battlefield_definitions import (
    BattlefieldDefinition,
    BattlefieldElevationDefinition,
    BattlefieldLayoutDefinition,
    BattlefieldObjectDefinition,
    BattlefieldObjectKind,
    BattlefieldTerrain,
    BattlefieldTileDefinition,
    LightLevelName,
)
from dnd.types.world import CardinalDirection, MovementMode
from dnd.core.world_edges import ElevationSurfaceKind, SlopeAxis
from dnd.core.traversal_connectors import (
    ConnectorActionCostType,
    ConnectorProvocationPolicy,
    TraversalConnectorDefinition,
    TraversalConnectorKind,
)
from dnd.core.gridmap import GridMap, get_map
from dnd.core.events.events_registry import Event, EventPhase, EventQueue, EventType
from dnd.core.events.world_events import (
    SpatialChangeEvent,
    SpatialEffectInteractionEvent,
    WorldConnectorState,
    WorldInitializedEvent,
    WorldObjectState,
    WorldTileState,
)
from dnd.content.spike_trap_materialization import materialize_spike_trap_condition
from dnd.items.environment import DirectionalDoor, DirectionalWall
from dnd.items.environment_interactables import StorageChest
from dnd.items.torches import WallTorch
from dnd.maps.arena_layout import (
    DIFFICULT_TERRAIN_POSITIONS,
    DOOR_POSITION,
    HEALING_POTION_POSITIONS,
    SPIKE_ZONE_POSITIONS,
    STANDARD_BLOCKING_CHANNELS,
    TRAP_LEVER_POSITION,
    WALL_POSITIONS,
    WALL_TORCH_MOUNTS,
    WATER_POSITIONS,
    StandardArenaObjects,
    StandardBarrierObjects,
    build_standard_arena_environment,
    create_standard_arena_floor,
    darken_arena,
)
from dnd.types.items import ItemLocation
from dnd.types.spatial_effects import SpatialEffectInteractionOperation
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
        layout=_layout_for_battlefield(battlefield_id),
    )


def _terrain_cell(
    position: tuple[int, int],
    terrain: BattlefieldTerrain,
    *,
    walking_cost: int = 1,
    flying_cost: int = 1,
    swimming_cost: int = 0,
    burrowing_cost: int = 0,
    hazardous: bool = False,
) -> BattlefieldTileDefinition:
    """Create one non-default authored terrain cell."""
    return BattlefieldTileDefinition(
        position=position,
        terrain=terrain,
        walking_cost=walking_cost,
        flying_cost=flying_cost,
        swimming_cost=swimming_cost,
        burrowing_cost=burrowing_cost,
        hazardous=hazardous,
    )


def _object_definition(
    position: tuple[int, int],
    kind: BattlefieldObjectKind,
    label: str,
    *,
    boundary_direction: CardinalDirection | None = None,
    base_height_steps: int | None = None,
    orientation: CardinalDirection | None = None,
    is_open: bool | None = None,
) -> BattlefieldObjectDefinition:
    """Create one static authored object placement."""
    return BattlefieldObjectDefinition(
        position=position,
        kind=kind,
        label=label,
        boundary_direction=boundary_direction,
        base_height_steps=base_height_steps,
        orientation=orientation,
        is_open=is_open,
    )


def _standard_hazards_layout(*, open_door: bool) -> BattlefieldLayoutDefinition:
    """Project the shared standard hazard layout without constructing runtime objects."""
    cells = (
        *(
            _terrain_cell(
                position,
                "water",
                walking_cost=0,
                flying_cost=1,
                swimming_cost=1,
                burrowing_cost=0,
            )
            for position in WATER_POSITIONS
        ),
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
            _object_definition(
                position,
                "wall",
                "Wall",
                boundary_direction=CardinalDirection.WEST,
            )
            for position in WALL_POSITIONS
        ),
        _object_definition(
            DOOR_POSITION,
            "door",
            "Door",
            boundary_direction=CardinalDirection.WEST,
            is_open=open_door,
        ),
        *(
            _object_definition(
                position,
                "wall_torch",
                "Wall Torch",
                boundary_direction=boundary_direction,
                base_height_steps=base_height_steps,
                orientation=orientation,
            )
            for position, boundary_direction, base_height_steps, orientation
            in WALL_TORCH_MOUNTS
        ),
        *(
            _object_definition(position, "healing_potion", "Healing Potion")
            for position in HEALING_POTION_POSITIONS
        ),
        _object_definition(TRAP_LEVER_POSITION, "trap_lever", "Trap Lever"),
    )
    return BattlefieldLayoutDefinition(tiles=cells, objects=objects)


def _two_barrier_layout(*, first_door_y: int, second_door_y: int) -> BattlefieldLayoutDefinition:
    """Project the paired directional barriers used by dark room maps."""
    objects = []
    for column, door_y, label in ((5, first_door_y, "First"), (9, second_door_y, "Second")):
        for y in range(3, 12):
            if y == door_y:
                objects.append(_object_definition(
                    (column, y),
                    "door",
                    f"{label} Door",
                    boundary_direction=CardinalDirection.WEST,
                    is_open=False,
                ))
            else:
                objects.append(_object_definition(
                    (column, y),
                    "wall",
                    f"{label} Wall",
                    boundary_direction=CardinalDirection.WEST,
                ))
    return BattlefieldLayoutDefinition(objects=tuple(objects))


def _elevation_proving_layout() -> BattlefieldLayoutDefinition:
    """Project the maintained level, slope, cliff, and jump proving geometry."""
    return BattlefieldLayoutDefinition(
        tiles=(
            _terrain_cell(
                (10, 9),
                "gap",
                walking_cost=0,
                flying_cost=1,
                swimming_cost=0,
                burrowing_cost=0,
            ),
            _terrain_cell((11, 9), "spikes", hazardous=True),
        ),
        objects=tuple(
            _object_definition(
                (4, y),
                "door" if y == 7 else "wall",
                "Proving Door" if y == 7 else "Proving Wall",
                boundary_direction=CardinalDirection.WEST,
                is_open=False if y == 7 else None,
            )
            for y in range(3, 12)
        ) + (
            _object_definition(
                (11, 5),
                "cliff",
                "Cliff Face",
                boundary_direction=CardinalDirection.WEST,
                base_height_steps=0,
            ),
        ),
        elevation=(
            BattlefieldElevationDefinition(
                position=(5, 4),
                elevation_steps=0,
                surface_kind=ElevationSurfaceKind.STAIRS,
                slope_axis=SlopeAxis.EAST_WEST,
            ),
            BattlefieldElevationDefinition(
                position=(6, 4),
                elevation_steps=1,
                surface_kind=ElevationSurfaceKind.STAIRS,
                slope_axis=SlopeAxis.EAST_WEST,
            ),
            BattlefieldElevationDefinition(
                position=(7, 4),
                elevation_steps=2,
                surface_kind=ElevationSurfaceKind.STAIRS,
                slope_axis=SlopeAxis.EAST_WEST,
            ),
            BattlefieldElevationDefinition(position=(8, 4), elevation_steps=2),
            BattlefieldElevationDefinition(position=(5, 10), elevation_steps=2),
            BattlefieldElevationDefinition(
                position=(6, 10),
                elevation_steps=2,
                surface_kind=ElevationSurfaceKind.RAMP,
                slope_axis=SlopeAxis.EAST_WEST,
            ),
            BattlefieldElevationDefinition(
                position=(7, 10),
                elevation_steps=1,
                surface_kind=ElevationSurfaceKind.RAMP,
                slope_axis=SlopeAxis.EAST_WEST,
            ),
            BattlefieldElevationDefinition(
                position=(8, 10),
                elevation_steps=0,
                surface_kind=ElevationSurfaceKind.RAMP,
                slope_axis=SlopeAxis.EAST_WEST,
            ),
            BattlefieldElevationDefinition(position=(11, 5), elevation_steps=2),
            BattlefieldElevationDefinition(position=(11, 9), elevation_steps=1),
            BattlefieldElevationDefinition(position=(2, 12), elevation_steps=1),
            BattlefieldElevationDefinition(position=(4, 12), elevation_steps=1),
            BattlefieldElevationDefinition(position=(6, 12), elevation_steps=2),
            BattlefieldElevationDefinition(position=(8, 12), elevation_steps=1),
            BattlefieldElevationDefinition(position=(12, 13), elevation_steps=2),
        ),
        connectors=(
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
                provocation_policy=ConnectorProvocationPolicy.PROVOKES_SOURCE_EXIT,
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
                provocation_policy=ConnectorProvocationPolicy.PROVOKES_SOURCE_EXIT,
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
                provocation_policy=ConnectorProvocationPolicy.DOES_NOT_PROVOKE,
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
                provocation_policy=ConnectorProvocationPolicy.DOES_NOT_PROVOKE,
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
                provocation_policy=ConnectorProvocationPolicy.PROVOKES_SOURCE_EXIT,
            ),
        ),
    )


def _layout_for_battlefield(battlefield_id: str) -> BattlefieldLayoutDefinition:
    """Return the canonical compact layout for one registered builder."""
    builder_id = battlefield_id.removeprefix("battlefield.")
    if builder_id in {"open_floor_bright", "open_floor_dark"}:
        return BattlefieldLayoutDefinition()
    if builder_id == "standard_hazards_closed":
        return _standard_hazards_layout(open_door=False)
    if builder_id == "standard_hazards_open":
        return _standard_hazards_layout(open_door=True)
    if builder_id == "double_door_dark":
        return _two_barrier_layout(first_door_y=7, second_door_y=7)
    if builder_id == "reveal_labyrinth_dark":
        return _two_barrier_layout(first_door_y=6, second_door_y=8)
    if builder_id == "arcane_device_bright":
        return BattlefieldLayoutDefinition(objects=(
            _object_definition((7, 7), "fireball_cannon", "Fireball Cannon"),
            _object_definition((6, 7), "healing_potion", "Healing Potion"),
        ))
    if builder_id == "field_cache_bright":
        return BattlefieldLayoutDefinition(objects=(
            _object_definition((5, 7), "loot_chest", "Field Cache"),
        ))
    if builder_id == "multi_object_dark":
        standard = _standard_hazards_layout(open_door=True)
        return standard.model_copy(update={
            "objects": (
                *standard.objects,
                _object_definition(
                    (4, 10),
                    "wall_torch",
                    "Control-Room Torch",
                    boundary_direction=CardinalDirection.WEST,
                    base_height_steps=1,
                    orientation=CardinalDirection.EAST,
                ),
                _object_definition((6, 11), "fireball_cannon", "Fireball Cannon"),
                _object_definition((5, 10), "loot_chest", "Control Cache"),
            ),
        })
    if builder_id == "elevation_proving_ground":
        return _elevation_proving_layout()
    raise ValueError(f"Unknown battlefield layout builder: {builder_id}")


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
    _battlefield(
        "battlefield.elevation_proving_ground",
        "Elevation And Vertical Traversal Proving Ground",
        ("bright", "door", "stairs", "ramp", "cliff", "jump-gap", "spikes", "connectors"),
        "bright",
        (
            "bright-light",
            "closed-door",
            "progressive-stairs",
            "progressive-ramp",
            "cliff",
            "jump-gap",
            "landing-hazard",
            "ladder",
            "rope",
            "lift",
            "vertical-stairs",
            "passage",
        ),
    ),
)

BATTLEFIELDS_BY_ID = {spec.battlefield_id: spec for spec in BATTLEFIELDS}


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
        if y == door_y:
            door = build_directional_door(
                display_name=f"{label} Door",
                blocked_channels=STANDARD_BLOCKING_CHANNELS,
                is_open=False,
            )
            grid.place_object(
                door.uuid,
                position,
                boundary_direction=CardinalDirection.WEST,
            )
        else:
            wall = build_directional_wall(
                display_name=f"{label} Wall",
                blocked_channels=STANDARD_BLOCKING_CHANNELS,
            )
            grid.place_object(
                wall.uuid,
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
    potion = build_authored_item("consumable.healing_potion", uuid4())
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
        build_authored_item(
            "consumable.healing_potion",
            chest.uuid,
            parameters={"heal_amount": heal_amount},
        )
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
    torch_definition = next(
        row
        for row in definition.layout.objects
        if row.kind == "wall_torch" and row.position == (4, 10)
    )
    wall_torch = build_wall_torch()
    wall_torch.mount(
        torch_definition.position,
        boundary_direction=torch_definition.boundary_direction,
        base_height_steps=torch_definition.base_height_steps,
        orientation=torch_definition.orientation,
        lit=False,
    )
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


def _build_elevation_proving_ground(
    definition: BattlefieldDefinition,
    grid: GridMap,
) -> BuiltBattlefield:
    """Build the maintained non-connector elevation proving geometry."""
    layout = definition.layout
    elevation_by_position = {
        elevation.position: (
            elevation.elevation_steps,
            elevation.surface_kind,
            elevation.slope_axis,
        )
        for elevation in layout.elevation
    }
    create_standard_arena_floor(
        grid,
        gap_positions=tuple(
            cell.position for cell in layout.tiles if cell.terrain == "gap"
        ),
        elevation_by_position=elevation_by_position,
    )
    runtime_connectors = {}
    for connector_definition in layout.connectors:
        connector = grid.register_connector(connector_definition)
        if connector is None:
            raise ValueError(
                f"battlefield connector was vetoed: {connector_definition.authored_id}"
            )
        runtime_connectors[connector.authored_id] = connector.uuid
    barrier = _place_directional_barrier(
        grid,
        column=4,
        door_y=7,
        label="Proving",
    )
    cliff_definition = next(
        row for row in layout.objects if row.kind == "cliff"
    )
    cliff = build_cliff_face(display_name=cliff_definition.label)
    grid.place_object(
        cliff.uuid,
        cliff_definition.position,
        boundary_direction=cliff_definition.boundary_direction,
        base_height_steps=cliff_definition.base_height_steps,
        orientation=cliff_definition.orientation,
    )
    landing_hazard_uuid = uuid4()
    return BuiltBattlefield(
        definition=definition,
        environment=None,
        notable_positions={
            "door": (4, 7),
            "stairs_start": (5, 4),
            "stairs_top": (8, 4),
            "ramp_top": (5, 10),
            "ramp_end": (8, 10),
            "cliff_from": (10, 5),
            "cliff_top": (11, 5),
            "jump_takeoff": (9, 9),
            "jump_landing": (11, 9),
            **{
                f"{connector.kind.value}_start": connector.endpoint_positions[0]
                for connector in layout.connectors
            },
            **{
                f"{connector.kind.value}_end": connector.endpoint_positions[1]
                for connector in layout.connectors
            },
        },
        object_uuids={
            "door": barrier.door.uuid,
            "cliff": cliff.uuid,
            "landing_hazard": landing_hazard_uuid,
            **{
                authored_id: connector_uuid
                for authored_id, connector_uuid in runtime_connectors.items()
            },
        },
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
    """Construct one battlefield and publish its compact bootstrap fact."""
    definition = get_battlefield(battlefield_id)
    builder = _BUILDERS[battlefield_id]
    grid = get_map()
    cursor_before = EventQueue.event_cursor()
    if cursor_before != 0:
        raise ValueError("authored battlefield requires an empty EventQueue")
    if (
        grid.get_all_tiles()
        or grid.get_all_object_placements()
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
        _validate_cold_world(built, grid, world_event, cursor_before)
    except Exception:
        grid.enable_events(flush_pending=False)
        raise
    grid.enable_events(flush_pending=False)
    published_world_declaration = EventQueue.publish_preflighted(world_event)
    world_execution = published_world_declaration.phase_to(
        EventPhase.EXECUTION,
        use_register=False,
    )
    world_execution = EventQueue.publish_preflighted(world_execution)
    world_effect = world_execution.phase_to(
        EventPhase.EFFECT,
        use_register=False,
    )
    world_effect = EventQueue.publish_preflighted(world_effect)
    _materialize_authored_spike_traps(built, parent_event=world_effect)
    _settle_authored_wall_torches(grid, world_effect)
    world_effect.phase_to(EventPhase.COMPLETION)
    return built


def _materialize_authored_spike_traps(
    built: BuiltBattlefield,
    *,
    parent_event: Event,
) -> None:
    """Activate each reserved authored SpikeTrap after world publication."""
    reserved: list[tuple[UUID, set[tuple[int, int]]]] = []
    if built.environment is not None:
        reserved.append(
            (built.environment.spike_condition_uuid, set(SPIKE_ZONE_POSITIONS)),
        )
    if "landing_hazard" in built.object_uuids:
        reserved.append(
            (built.object_uuids["landing_hazard"], {(11, 9)}),
        )

    for condition_uuid, positions in reserved:
        condition = materialize_spike_trap_condition(
            positions,
            condition_uuid=condition_uuid,
            parent_event=parent_event,
        )
        if condition.uuid != condition_uuid or BaseCondition.get(condition_uuid) is not condition:
            raise RuntimeError(
                "authored SpikeTrap materialization changed its reserved identity",
            )


def _settle_authored_wall_torches(
    grid: GridMap,
    parent_event: Event,
) -> None:
    """Light authored WallTorches and publish their complete item facts."""
    placements = {
        placement.object_uuid: placement
        for placement in grid.get_all_object_placements()
    }
    torches: list[tuple[tuple[int, int], UUID, WallTorch]] = []
    for object_uuid, placement in placements.items():
        item = BaseItem.get(object_uuid)
        if isinstance(item, WallTorch):
            torches.append((placement.position, object_uuid, item))

    for _position, object_uuid, torch in sorted(torches, key=lambda row: (row[0], str(row[1]))):
        placement = placements[object_uuid]
        cursor = EventQueue.event_cursor()
        torch.light(parent_event=parent_event.uuid)
        synchronous_events = tuple(EventQueue.iter_events_since(cursor))
        light_completions = [
            (index, event)
            for index, event in synchronous_events
            if isinstance(event, SpatialChangeEvent)
            and event.event_type is EventType.SPATIAL_LIGHT_CHANGED
            and event.phase is EventPhase.COMPLETION
            and not event.canceled
        ]
        ignite_completions = [
            (index, event)
            for index, event in synchronous_events
            if isinstance(event, SpatialEffectInteractionEvent)
            and event.event_type is EventType.SPATIAL_EFFECT_INTERACTION
            and event.operation is SpatialEffectInteractionOperation.IGNITE
            and event.source_object_uuid == object_uuid
            and event.target_entity_uuid == object_uuid
            and event.phase is EventPhase.COMPLETION
            and not event.canceled
        ]
        if (
            not light_completions
            or not ignite_completions
            or light_completions[0][0] >= ignite_completions[0][0]
        ):
            raise RuntimeError(
                f"authored WallTorch {object_uuid} did not complete light and IGNITE setup",
            )
        torch.publish_location_state(
            ItemLocation.FLOOR,
            world_placement=placement,
            parent_event=parent_event,
        )


def _validate_cold_world(
    built: BuiltBattlefield,
    grid: GridMap,
    world_event: WorldInitializedEvent,
    cursor_before: int,
) -> None:
    """Validate the actor-free authored state before publishing its world fact."""
    if EventQueue.event_cursor() != cursor_before:
        raise RuntimeError("cold authored build advanced the EventQueue")

    current_tiles = grid.get_all_tiles()
    world_tiles = {row.position: row for row in world_event.tiles}
    if set(current_tiles) != set(world_tiles):
        raise RuntimeError("cold world Tile positions are not a closed set")
    current_tile_uuids = {tile.uuid: position for position, tile in current_tiles.items()}
    registered_tiles = {
        block_uuid: block
        for block_uuid, block in BaseBlock._registry.items()
        if isinstance(block, Tile)
    }
    current_tiles_by_uuid = {
        tile.uuid: tile
        for tile in current_tiles.values()
    }
    if (
        set(registered_tiles) != set(current_tiles_by_uuid)
        or any(
            registered_tiles[tile_uuid] is not tile
            for tile_uuid, tile in current_tiles_by_uuid.items()
        )
    ):
        raise RuntimeError("cold world registered Tile closure does not match GridMap")
    world_tile_uuids = {row.tile_uuid: row.position for row in world_event.tiles}
    if current_tile_uuids != world_tile_uuids:
        raise RuntimeError("cold world Tile UUID closure does not match the snapshot")
    for position, tile in current_tiles.items():
        if BaseBlock.get(tile.uuid) is not tile:
            raise RuntimeError("cold world Tile is not registry-identical")
        if tile.active_conditions_by_uuid or tile.get_spatial_condition_uuids():
            raise RuntimeError("cold world Tile has a direct condition footprint")
        if tile.get_entity_uuids():
            raise RuntimeError("cold world Tile has entity membership")
        if world_tiles[position].tile_uuid != tile.uuid:
            raise RuntimeError("cold world Tile row identity mismatch")

    if grid.get_spatial_conditions():
        raise RuntimeError("cold authored world owns a SpatialCondition")

    placements = grid.get_all_object_placements()
    placement_by_uuid = {placement.object_uuid: placement for placement in placements}
    world_objects = {row.placement.object_uuid: row for row in world_event.objects}
    if set(placement_by_uuid) != set(world_objects):
        raise RuntimeError("cold world object closure does not match the snapshot")
    authored_wall_torch_count = sum(
        row.kind == "wall_torch"
        for row in built.definition.layout.objects
    )
    placed_wall_torches = []
    for object_uuid, placement in placement_by_uuid.items():
        item = BaseItem.get(object_uuid)
        if item is None:
            raise RuntimeError(f"cold world object {object_uuid} is not a BaseItem")
        if world_objects[object_uuid].placement != placement:
            raise RuntimeError("cold world object placement mismatch")
        if isinstance(item, WallTorch):
            placed_wall_torches.append(item)
            if item.is_lit or item.get_attached_light_sources():
                raise RuntimeError("cold authored WallTorch is not unlit")
    if len(placed_wall_torches) != authored_wall_torch_count:
        raise RuntimeError("cold authored WallTorch classification is incomplete")

    connector_by_uuid = {connector.uuid: connector for connector in grid.get_all_connectors()}
    if set(connector_by_uuid) != {row.connector_uuid for row in world_event.connectors}:
        raise RuntimeError("cold world connector closure does not match the snapshot")
    for row in world_event.connectors:
        connector = connector_by_uuid[row.connector_uuid]
        if row.authored_id != connector.authored_id:
            raise RuntimeError("cold world connector identity mismatch")

    authored_spike_positions = {
        cell.position
        for cell in built.definition.layout.tiles
        if cell.terrain == "spikes"
    }
    reserved_condition_uuids = set()
    expected_spike_positions: set[tuple[int, int]] | None = None
    if built.environment is not None:
        reserved_condition_uuids.add(built.environment.spike_condition_uuid)
        expected_spike_positions = set(SPIKE_ZONE_POSITIONS)
        if authored_spike_positions != expected_spike_positions:
            raise RuntimeError("cold standard spike footprint is not exact")
    elif "landing_hazard" in built.object_uuids:
        reserved_condition_uuids.add(built.object_uuids["landing_hazard"])
        expected_spike_positions = {(11, 9)}
        if authored_spike_positions != expected_spike_positions:
            raise RuntimeError("cold proving landing footprint is not exact")
    elif authored_spike_positions:
        raise RuntimeError("cold authored spike positions have no reserved identity")
    if expected_spike_positions is not None and not expected_spike_positions.issubset(current_tiles):
        raise RuntimeError("cold authored spike footprint is outside current Tiles")
    if any(BaseCondition.get(condition_uuid) is not None for condition_uuid in reserved_condition_uuids):
        raise RuntimeError("cold authored SpikeTrap identity is already live")


def _world_initialized_event(
    built: BuiltBattlefield,
    grid: GridMap,
) -> WorldInitializedEvent:
    tiles = tuple(
        WorldTileState(
            tile_uuid=tile.uuid,
            position=position,
            surface=tile.surface,
            name=tile.name,
            blocks_optics=tile.blocks_optics,
            blocks_propagation=tile.blocks_propagation_field,
            walking_cost=tile.get_movement_cost(MovementMode.WALKING),
            flying_cost=tile.get_movement_cost(MovementMode.FLYING),
            swimming_cost=tile.get_movement_cost(MovementMode.SWIMMING),
            burrowing_cost=tile.get_movement_cost(MovementMode.BURROWING),
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
        grid.get_all_object_placements(),
        key=lambda row: (row.position, str(row.object_uuid)),
    ):
        item = BaseItem.get(placement.object_uuid)
        if item is None:
            raise RuntimeError(
                f"world object {placement.object_uuid} is not a BaseItem",
            )
        storage = item.get_storage_block()
        contained_items = (
            tuple(
                child.to_item_state()
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
            item=item.to_item_state(),
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
        phase=EventPhase.DECLARATION,
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
