"""Light-aware battlefield catalog and deterministic map builders."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, cast
from uuid import UUID, uuid4

from dnd.core.gridmap import GridMap, get_map
from dnd.items.environment import DirectionalDoor, DirectionalWall
from dnd.items.test_items import (
    LootAllAction,
    StorageChest,
    create_acid_flask,
    create_fireball_cannon,
    create_healing_potion,
    create_scroll_of_fireball,
    create_scroll_of_magic_missile,
    create_wall_torch,
    create_weapon_coat,
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
from dnd.scenarios.evaluation.models import (
    BattlefieldPreview,
    BattlefieldPreviewCell,
    BattlefieldPreviewDirection,
    BattlefieldPreviewObject,
    BattlefieldPreviewObjectKind,
    BattlefieldPreviewTerrain,
    BattlefieldSpec,
    LightLevelName,
)


@dataclass(frozen=True)
class BuiltBattlefield:
    """Runtime objects created for one catalog battlefield."""

    spec: BattlefieldSpec
    environment: StandardArenaObjects | None
    notable_positions: dict[str, tuple[int, int]]
    object_uuids: dict[str, UUID]


def _deployment_ids(battlefield_id: str, source_arena_ids: tuple[str, ...]) -> tuple[str, ...]:
    """Return the neutral deployment followed by all legacy formations."""
    return (f"neutral.{battlefield_id}", *(f"legacy.{arena_id}" for arena_id in source_arena_ids))


def _battlefield(
    battlefield_id: str,
    title: str,
    builder_id: str,
    source_arena_ids: tuple[str, ...],
    tags: tuple[str, ...],
    light_level: LightLevelName,
    capabilities: tuple[str, ...],
) -> BattlefieldSpec:
    """Create one immutable battlefield catalog record."""
    return BattlefieldSpec(
        battlefield_id=battlefield_id,
        title=title,
        builder_id=builder_id,
        deployment_ids=_deployment_ids(battlefield_id, source_arena_ids),
        source_arena_ids=source_arena_ids,
        tags=tags,
        light_level=light_level,
        capabilities=capabilities,
        preview=_preview_for_builder(builder_id),
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


def _preview_for_builder(builder_id: str) -> BattlefieldPreview:
    """Return the canonical compact preview for one registered builder."""
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


_BRIGHT_OPEN_ARENAS = (
    "skeleton_anti_aoe_split",
    "item_resource_gauntlet",
    "skeleton_mark_focus_fire",
    "line_aoe_corridor",
    "support_attrition_cache",
    "high_level_spell_resource_duel",
    "sorcerer_barbarian_duel",
    "class_party_mirror_scramble",
    "concentration_control_crossroads",
    "guardian_zone_shrine",
    "condition_lock_sanctum",
    "necrotic_anti_healing_duel",
    "damage_affinity_weapon_lab",
    "resistance_weapon_counterplay",
    "cleanse_support_triage",
    "multi_target_missile_allocation",
    "multi_projectile_no_aoe_lab",
    "reaction_counterspell_lab",
    "srd_low_cr_patrol",
    "srd_divine_cult_cell",
    "srd_elite_mercenary_contract",
)

_STANDARD_OPEN_ARENAS = (
    "caster_crossfire",
    "buff_consumable_ambush",
    "forced_movement_hazard_bridge",
    "zone_control_web_gauntlet",
    "ranged_loadout_kiting_ring",
    "teleport_escape_skirmish",
    "trap_lever_killzone",
    "guardian_choke_body_block",
    "srd_goblinoid_warband",
)


BATTLEFIELDS: tuple[BattlefieldSpec, ...] = (
    _battlefield(
        "battlefield.standard_hazards_closed",
        "Dark Standard Hazards With Closed Door",
        "standard_hazards_closed",
        ("standard_skeleton_doors", "goblin_water_skirmish"),
        ("darkness", "door", "water", "difficult-terrain", "spikes", "objects"),
        "darkness",
        ("closed-door", "water", "difficult-terrain", "spike-zone", "trap-lever", "floor-loot", "wall-torches"),
    ),
    _battlefield(
        "battlefield.open_floor_bright",
        "Bright Open Floor",
        "open_floor_bright",
        _BRIGHT_OPEN_ARENAS,
        ("bright", "open-field"),
        "bright",
        ("open-floor", "bright-light"),
    ),
    _battlefield(
        "battlefield.standard_hazards_open",
        "Dark Standard Hazards With Open Door",
        "standard_hazards_open",
        _STANDARD_OPEN_ARENAS,
        ("darkness", "open-door", "water", "difficult-terrain", "spikes", "objects"),
        "darkness",
        ("open-door", "water", "difficult-terrain", "spike-zone", "trap-lever", "floor-loot", "wall-torches"),
    ),
    _battlefield(
        "battlefield.double_door_dark",
        "Dark Double-Door Rooms",
        "double_door_dark",
        ("double_door_dark_hunt",),
        ("darkness", "two-doors", "three-rooms"),
        "darkness",
        ("closed-door", "two-directional-barriers", "darkness"),
    ),
    _battlefield(
        "battlefield.arcane_device_bright",
        "Bright Arcane Device Floor",
        "arcane_device_bright",
        ("arcane_device_control",),
        ("bright", "fireball-cannon", "floor-loot"),
        "bright",
        ("open-floor", "bright-light", "fireball-cannon", "floor-potion"),
    ),
    _battlefield(
        "battlefield.reveal_labyrinth_dark",
        "Dark Reveal Labyrinth",
        "reveal_labyrinth_dark",
        ("darkness_reveal_labyrinth",),
        ("darkness", "two-doors", "offset-doors", "reveal"),
        "darkness",
        ("closed-door", "two-directional-barriers", "darkness"),
    ),
    _battlefield(
        "battlefield.field_cache_bright",
        "Bright Field Cache",
        "field_cache_bright",
        ("field_cache_loot_race",),
        ("bright", "loot-chest", "open-field"),
        "bright",
        ("open-floor", "bright-light", "loot-chest"),
    ),
    _battlefield(
        "battlefield.multi_object_dark",
        "Dark Multi-Object Control Room",
        "multi_object_dark",
        ("multi_object_control_room",),
        ("darkness", "open-door", "chest", "cannon", "lever", "wall-torch"),
        "darkness",
        ("open-door", "water", "difficult-terrain", "spike-zone", "trap-lever", "loot-chest", "fireball-cannon", "wall-torches"),
    ),
    _battlefield(
        "battlefield.open_floor_dark",
        "Dark Open Floor",
        "open_floor_dark",
        ("srd_undead_crypt",),
        ("darkness", "open-field"),
        "darkness",
        ("open-floor", "darkness"),
    ),
)

BATTLEFIELDS_BY_ID = {spec.battlefield_id: spec for spec in BATTLEFIELDS}


def _empty_runtime(spec: BattlefieldSpec) -> BuiltBattlefield:
    """Return a runtime result for an object-free floor."""
    return BuiltBattlefield(spec=spec, environment=None, notable_positions={}, object_uuids={})


def _build_open_floor_bright(spec: BattlefieldSpec, grid: GridMap) -> BuiltBattlefield:
    """Build a bright object-free arena floor."""
    create_standard_arena_floor(grid)
    return _empty_runtime(spec)


def _build_open_floor_dark(spec: BattlefieldSpec, grid: GridMap) -> BuiltBattlefield:
    """Build a dark object-free arena floor."""
    create_standard_arena_floor(grid)
    darken_arena(grid)
    return _empty_runtime(spec)


def _build_standard_hazards(spec: BattlefieldSpec, grid: GridMap, *, open_door: bool) -> BuiltBattlefield:
    """Build the standard dark object and hazard package."""
    environment = build_standard_arena_environment(grid)
    if open_door:
        environment.barrier.door.open()
    door_position = grid.get_object_position(environment.barrier.door.uuid) or (7, 7)
    return BuiltBattlefield(
        spec=spec,
        environment=environment,
        notable_positions={"door": door_position},
        object_uuids={"door": environment.barrier.door.uuid},
    )


def _build_standard_hazards_closed(spec: BattlefieldSpec, grid: GridMap) -> BuiltBattlefield:
    """Build the standard hazard package with its door closed."""
    return _build_standard_hazards(spec, grid, open_door=False)


def _build_standard_hazards_open(spec: BattlefieldSpec, grid: GridMap) -> BuiltBattlefield:
    """Build the standard hazard package and open its door."""
    return _build_standard_hazards(spec, grid, open_door=True)


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
            door = DirectionalDoor(
                source_entity_uuid=uuid4(),
                name=f"{label} Door",
                blocked_directions=("west",),
                blocked_channels=STANDARD_BLOCKING_CHANNELS,
                is_open=False,
            )
            door.place_on_grid(position)
        else:
            wall = DirectionalWall(
                source_entity_uuid=uuid4(),
                name=f"{label} Wall",
                blocked_directions=("west",),
                blocked_channels=STANDARD_BLOCKING_CHANNELS,
            )
            wall.place_on_grid(position)
            walls.append(wall)
    if door is None:
        raise ValueError("Directional barrier requires a door within rows 3 through 11.")
    return StandardBarrierObjects(door=door, walls=tuple(walls))


def _build_two_barriers(
    spec: BattlefieldSpec,
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
        spec=spec,
        environment=None,
        notable_positions={"first_door": first_position, "second_door": second_position},
        object_uuids={"first_door": first.door.uuid, "second_door": second.door.uuid},
    )


def _build_double_door_dark(spec: BattlefieldSpec, grid: GridMap) -> BuiltBattlefield:
    """Build the aligned two-door dark hunt floor."""
    return _build_two_barriers(spec, grid, first_door_y=7, second_door_y=7, labels=("First", "Second"))


def _build_reveal_labyrinth_dark(spec: BattlefieldSpec, grid: GridMap) -> BuiltBattlefield:
    """Build the offset-door darkness/reveal labyrinth."""
    return _build_two_barriers(spec, grid, first_door_y=6, second_door_y=8, labels=("Shadow", "Dawn"))


def _build_arcane_device_bright(spec: BattlefieldSpec, grid: GridMap) -> BuiltBattlefield:
    """Build the bright open floor with a Fireball cannon and healing potion."""
    create_standard_arena_floor(grid)
    cannon = create_fireball_cannon(uuid4(), position=(7, 7), charges=2)
    potion = create_healing_potion(uuid4(), heal_amount=12)
    potion.place_on_grid((6, 7))
    return BuiltBattlefield(
        spec=spec,
        environment=None,
        notable_positions={"fireball_cannon": (7, 7), "floor_potion": (6, 7)},
        object_uuids={"fireball_cannon": cannon.uuid, "floor_potion": potion.uuid},
    )


def _create_cache(name: str, *, heal_amount: int, include_full_loadout: bool) -> StorageChest:
    """Create one environment-owned loot chest."""
    chest = StorageChest(
        source_entity_uuid=uuid4(),
        name=name,
        use_action_templates=[LootAllAction(source_entity_uuid=uuid4(), template=True)],
    )
    if include_full_loadout:
        chest.chest_inventory.add_item(create_scroll_of_fireball(chest.uuid))
    chest.chest_inventory.add_item(create_scroll_of_magic_missile(chest.uuid))
    chest.chest_inventory.add_item(create_acid_flask(chest.uuid))
    chest.chest_inventory.add_item(create_healing_potion(chest.uuid, heal_amount=heal_amount))
    if include_full_loadout:
        chest.chest_inventory.add_item(create_weapon_coat(chest.uuid))
    return chest


def _build_field_cache_bright(spec: BattlefieldSpec, grid: GridMap) -> BuiltBattlefield:
    """Build the bright floor with the complete field-cache chest."""
    create_standard_arena_floor(grid)
    chest = _create_cache("Validation Field Cache", heal_amount=14, include_full_loadout=True)
    chest.place_on_grid((5, 7))
    return BuiltBattlefield(
        spec=spec,
        environment=None,
        notable_positions={"field_cache": (5, 7)},
        object_uuids={"field_cache": chest.uuid},
    )


def _build_multi_object_dark(spec: BattlefieldSpec, grid: GridMap) -> BuiltBattlefield:
    """Build the standard floor plus the control-room object package."""
    environment = build_standard_arena_environment(grid)
    environment.barrier.door.open()
    wall_torch = create_wall_torch(position=(4, 10), owner_uuid=uuid4(), lit=True)
    cannon = create_fireball_cannon(uuid4(), position=(6, 11), charges=2)
    chest = _create_cache("Validation Control Cache", heal_amount=12, include_full_loadout=False)
    chest.place_on_grid((5, 10))
    return BuiltBattlefield(
        spec=spec,
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


BattlefieldBuilder = Callable[[BattlefieldSpec, GridMap], BuiltBattlefield]

_BUILDERS: dict[str, BattlefieldBuilder] = {
    "standard_hazards_closed": _build_standard_hazards_closed,
    "open_floor_bright": _build_open_floor_bright,
    "standard_hazards_open": _build_standard_hazards_open,
    "double_door_dark": _build_double_door_dark,
    "arcane_device_bright": _build_arcane_device_bright,
    "reveal_labyrinth_dark": _build_reveal_labyrinth_dark,
    "field_cache_bright": _build_field_cache_bright,
    "multi_object_dark": _build_multi_object_dark,
    "open_floor_dark": _build_open_floor_dark,
}


def get_battlefield(battlefield_id: str) -> BattlefieldSpec:
    """Return one canonical battlefield by stable identifier."""
    try:
        return BATTLEFIELDS_BY_ID[battlefield_id]
    except KeyError as exc:
        raise ValueError(f"Unknown battlefield: {battlefield_id}") from exc


def build_battlefield(battlefield_id: str) -> BuiltBattlefield:
    """Construct one battlefield in the current global map."""
    spec = get_battlefield(battlefield_id)
    builder = _BUILDERS[spec.builder_id]
    return builder(spec, get_map())
