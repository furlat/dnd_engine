"""Authored battlefields and their sole deterministic runtime builders."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, cast
from uuid import UUID, uuid4

from dnd.content_system.item_bindings import ItemRuntimeOrigin
from dnd.content_system.item_materialization import materialize_item
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
from dnd.items.consumables import (
    FIRE_WEAPON_COAT_RECIPE,
    healing_potion_recipe,
)
from dnd.items.environment import DirectionalDoor, DirectionalWall
from dnd.items.environment_content import (
    WALL_TORCH_RECIPE,
    directional_door_recipe,
    directional_wall_recipe,
    fireball_cannon_recipe,
    storage_chest_recipe,
)
from dnd.items.spell_items import (
    ACID_FLASK_RECIPE,
    FIREBALL_SCROLL_RECIPE,
    MAGIC_MISSILE_SCROLL_RECIPE,
)
from dnd.items.environment_interactables import (
    StorageChest,
)
from dnd.items.torches import WallTorch
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
        grid.set_tile(column, y, walkable=True, visible=True, name="Floor")
        if y == door_y:
            door = materialize_item(
                directional_door_recipe(
                    display_name=f"{label} Door",
                    blocked_directions=("west",),
                    blocked_channels=STANDARD_BLOCKING_CHANNELS,
                    is_open=False,
                ),
                uuid4(),
                origin=ItemRuntimeOrigin.ENVIRONMENT,
                expected_type=DirectionalDoor,
            )
            door.place_on_grid(position)
        else:
            wall = materialize_item(
                directional_wall_recipe(
                    display_name=f"{label} Wall",
                    blocked_directions=("west",),
                    blocked_channels=STANDARD_BLOCKING_CHANNELS,
                ),
                uuid4(),
                origin=ItemRuntimeOrigin.ENVIRONMENT,
                expected_type=DirectionalWall,
            )
            wall.place_on_grid(position)
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
    cannon = materialize_item(
        fireball_cannon_recipe(charges=2),
        uuid4(),
        origin=ItemRuntimeOrigin.ENVIRONMENT,
    )
    cannon.place_on_grid((7, 7))
    potion = materialize_item(
        healing_potion_recipe(heal_amount=12),
        uuid4(),
        origin=ItemRuntimeOrigin.LOOT,
    )
    potion.place_on_grid((6, 7))
    return BuiltBattlefield(
        definition=definition,
        environment=None,
        notable_positions={"fireball_cannon": (7, 7), "floor_potion": (6, 7)},
        object_uuids={"fireball_cannon": cannon.uuid, "floor_potion": potion.uuid},
    )


def _create_cache(name: str, *, heal_amount: int, include_full_loadout: bool) -> StorageChest:
    """Create one environment-owned loot chest."""
    chest = materialize_item(
        storage_chest_recipe(
            display_name=name,
            include_loot_all_action=True,
        ),
        uuid4(),
        origin=ItemRuntimeOrigin.ENVIRONMENT,
        expected_type=StorageChest,
    )
    if include_full_loadout:
        chest.chest_inventory.add_item(materialize_item(
            FIREBALL_SCROLL_RECIPE,
            chest.uuid,
            origin=ItemRuntimeOrigin.LOOT,
        ))
    chest.chest_inventory.add_item(materialize_item(
        MAGIC_MISSILE_SCROLL_RECIPE,
        chest.uuid,
        origin=ItemRuntimeOrigin.LOOT,
    ))
    chest.chest_inventory.add_item(materialize_item(
        ACID_FLASK_RECIPE,
        chest.uuid,
        origin=ItemRuntimeOrigin.LOOT,
    ))
    chest.chest_inventory.add_item(
        materialize_item(
            healing_potion_recipe(heal_amount=heal_amount),
            chest.uuid,
            origin=ItemRuntimeOrigin.LOOT,
        )
    )
    if include_full_loadout:
        chest.chest_inventory.add_item(
            materialize_item(
                FIRE_WEAPON_COAT_RECIPE,
                chest.uuid,
                origin=ItemRuntimeOrigin.LOOT,
            )
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
    wall_torch = materialize_item(
        WALL_TORCH_RECIPE,
        uuid4(),
        origin=ItemRuntimeOrigin.ENVIRONMENT,
        expected_type=WallTorch,
    )
    wall_torch.mount((4, 10), lit=True)
    cannon = materialize_item(
        fireball_cannon_recipe(charges=2),
        uuid4(),
        origin=ItemRuntimeOrigin.ENVIRONMENT,
    )
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
}


def get_battlefield(battlefield_id: str) -> BattlefieldDefinition:
    """Return one canonical battlefield by stable identifier."""
    try:
        return BATTLEFIELDS_BY_ID[battlefield_id]
    except KeyError as exc:
        raise ValueError(f"Unknown battlefield: {battlefield_id}") from exc


def build_battlefield(battlefield_id: str) -> BuiltBattlefield:
    """Construct one battlefield in the current global map."""
    definition = get_battlefield(battlefield_id)
    builder = _BUILDERS[battlefield_id]
    return builder(definition, get_map())
