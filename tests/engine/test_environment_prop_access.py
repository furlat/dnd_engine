"""Authored furniture obstructs bodies and shots independently of visibility."""

from collections.abc import Iterator
from uuid import uuid4

import pytest

from dnd.actions import Attack, Move
from dnd.actions_functional import setup_standard_actions
from dnd.blocks.health import HealthConfig, HitDiceConfig
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.core.base_block import LightLevel
from dnd.core.creature_types import DamageType
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import WeaponSlot
from dnd.core.gridmap import get_map
from dnd.core.item_types import ItemIntegrity
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.spells.evocation import FireBolt
from dnd.types.physical_access import PhysicalAccess
from dnd.types.world import CardinalDirection


@pytest.fixture
def arena() -> Iterator[Game]:
    reset_engine_runtime(grid_size=(9, 9))
    game = Game()
    yield game
    game.close()
    reset_engine_runtime()


def actor(game: Game, name: str, position: tuple[int, int]) -> Entity:
    entity = Entity.create(uuid4(), name, config=EntityConfig(position=position,
        faction=name, health=HealthConfig(hit_dices=[HitDiceConfig(
            hit_dice_value=10, hit_dice_count=8, mode="maximums")])))
    setup_standard_actions(entity)
    entity.install_initial_items((
        (build_authored_item("weapon.longsword", entity.uuid), WeaponSlot.MELEE_MAIN),
        (build_authored_item("weapon.longbow", entity.uuid), WeaponSlot.RANGED_MAIN),
    ))
    entity.compose_entity()
    game.deploy_entity(entity, position)
    return entity


@pytest.mark.parametrize("spell", (False, True), ids=("longbow", "fire-bolt"))
def test_low_stove_blocks_shots_and_entry_until_actually_broken(arena: Game, spell: bool):
    source = actor(arena, "Archer", (2, 3))
    target = actor(arena, "Target", (4, 3))
    stove = build_authored_item("environment.furniture.clay_stove", source.uuid)
    stove.place_on_grid((3, 3))
    identity = stove.uuid
    Entity.update_all_entities_senses()
    assert target.uuid in source.senses.entities
    action = (FireBolt(source_entity_uuid=source.uuid, target_entity_uuid=target.uuid)
              if spell else Attack(source_entity_uuid=source.uuid,
                  target_entity_uuid=target.uuid, weapon_slot=WeaponSlot.RANGED_MAIN))
    assert not action.validate_requirements_for_discovery()
    hp, budget = target.get_hp(), source.action_economy.actions.normalized_score
    result = action.apply()
    assert result is not None and result.canceled
    assert target.get_hp() == hp
    assert source.action_economy.actions.normalized_score == budget
    movement = source.action_economy.movement_remaining()
    step = Move(source_entity_uuid=source.uuid, path=[(2, 3), (3, 3)],
                end_position=(3, 3), prefer_safe=False).apply()
    assert step is not None and source.position == (2, 3)
    assert source.action_economy.movement_remaining() == movement
    # The blocking item remains a legitimate target; its own collision cannot
    # stop contact with its near surface.
    for _ in range(2):
        source.action_economy.reset_all_costs()
        with fixed_dice_faces(19, 8):
            source.update_entity_senses()
            broken = Attack(weapon_slot=WeaponSlot.MELEE_MAIN, source_entity_uuid=source.uuid,
                                  target_entity_uuid=identity).apply()
        assert broken is not None and not broken.canceled
    assert stove.uuid == identity and stove.integrity is ItemIntegrity.DESTROYED
    source.action_economy.reset_all_costs()
    Entity.update_all_entities_senses()
    assert action.validate_requirements_for_discovery()
    with fixed_dice_faces(20, 4, 4, 4):
        shot = action.apply()
    assert shot is not None and not shot.canceled and target.get_hp() < hp
    step = Move(source_entity_uuid=source.uuid, path=[(2, 3), (3, 3)],
                end_position=(3, 3), prefer_safe=False).apply()
    assert step is not None and not step.canceled and source.position == (3, 3)


@pytest.mark.parametrize("suffix,opaque", (("clay_stove", False), ("clay_oven", True)))
def test_prop_blocks_propagation_and_only_opaque_body_blocks_light(arena: Game, suffix: str, opaque: bool):
    prop = build_authored_item(f"environment.furniture.{suffix}", uuid4())
    prop.place_on_grid((3, 3))
    grid = get_map()
    grid.set_tile_base_light((4, 3), LightLevel.DARKNESS)
    grid.add_light_source((2, 3), bright_radius_feet=20, dim_radius_feet=0)
    tile = grid.get_tile(4, 3)
    assert tile is not None
    assert ((4, 3) in grid.compute_fov((2, 3), 5)) is not opaque
    assert (4, 3) not in grid.compute_propagation_fov((2, 3), 5)
    assert tile.resolved_light_level is (LightLevel.DARKNESS if opaque else LightLevel.BRIGHT_LIGHT)
    prop.destroy()
    assert (4, 3) in grid.compute_fov((2, 3), 5)
    assert (4, 3) in grid.compute_propagation_fov((2, 3), 5)
    assert tile.resolved_light_level is LightLevel.BRIGHT_LIGHT


# Independent content expectations: these are gameplay policies, not values
# read back from the production profile under test.
FLOOR_DRESSING = (
    'spent_ashes',
    'red_rug',
    'pale_rug',
    'loose_straw_1',
    'loose_straw_2',
    'loose_straw_3',
    'loose_straw_4',
    'loose_straw_5',
    'loose_straw_6',
    'loose_straw_7',
    'cold_fire_pit',
)
LOW_OR_OPEN_SOLIDS = (
    'clay_stove',
    'lidded_vessel',
    'parked_cart',
    'timber_pile',
    'wheelbarrow',
    'covered_market_counter',
    'covered_handcart',
    'pale_market_stall',
    'training_dummy',
    'grindstone',
    'red_produce_stall',
    'rough_market_stall',
    'green_market_stall',
    'produce_tub',
    'hide_drying_rack',
    'feed_trough',
    'notice_board',
    'wooden_crib',
    'small_wooden_table',
    'red_covered_table',
    'pale_covered_table',
    'short_red_banner',
    'tall_red_banner',
    'wooden_signpost',
    'framed_notice_board',
    'archery_target',
    'felled_log',
    'workshop_apparatus',
    'alchemy_bench',
    'anvil',
    'cannonball_pile',
    'unlit_crucible',
    'grave_marker',
    'slender_monument',
    'hay_bale',
    'hay_bales_leaning',
    'unlit_candlesticks',
)
OPAQUE_SOLIDS = (
    'loaded_wagon',
    'clay_oven',
    'hay_bales_stacked',
    'hay_bales_upright',
)


@pytest.mark.parametrize("suffix,solid,opaque", [
    *((suffix, False, False) for suffix in FLOOR_DRESSING),
    *((suffix, True, False) for suffix in LOW_OR_OPEN_SOLIDS),
    *((suffix, True, True) for suffix in OPAQUE_SOLIDS),
])
def test_environment_batch_has_authored_channels_and_clears_every_support(arena: Game, suffix: str, solid: bool, opaque: bool):
    prop = build_authored_item(f"environment.furniture.{suffix}", uuid4())
    placement = prop.place_on_grid((4, 4))
    grid = get_map()
    for y in {y for _, y in placement.positions}:
        xs = [x for x, row_y in placement.positions if row_y == y]
        start, end = (min(xs) - 1, y), (max(xs) + 1, y)
        assert (end in grid.compute_fov(start, 8)) is not opaque
        assert grid.can_reach_between(start, end, PhysicalAccess.PROJECTILE, prop.uuid) is not solid
    for point in placement.positions:
        assert grid.is_walkable_for(*point) is not solid
        assert prop.uuid in grid.get_center_objects_at(point)
    prop.receive_damage(prop.get_hp(), DamageType.BLUDGEONING, prop.uuid)
    after = grid.get_object_placement(prop.uuid)
    assert after is not None and after.positions == placement.positions
    for point in placement.positions:
        assert grid.is_walkable_for(*point)
    for y in {y for _, y in placement.positions}:
        xs = [x for x, row_y in placement.positions if row_y == y]
        start, end = (min(xs) - 1, y), (max(xs) + 1, y)
        assert end in grid.compute_fov(start, 8)
        assert grid.can_reach_between(start, end, PhysicalAccess.PROJECTILE, prop.uuid)


@pytest.mark.parametrize("suffix", ("parked_cart", "loaded_wagon", "felled_log"))
@pytest.mark.parametrize("orientation,far", (
    (CardinalDirection.EAST, (5, 4)), (CardinalDirection.SOUTH, (4, 3)),
    (CardinalDirection.WEST, (3, 4)), (CardinalDirection.NORTH, (4, 5)),
))
def test_large_prop_far_cell_blocks_and_can_be_attacked_then_entered(arena: Game, suffix, orientation, far):
    prop = build_authored_item(f"environment.furniture.{suffix}", uuid4())
    placement = prop.place_on_grid((4, 4), orientation=orientation)
    assert set(placement.positions) == {(4, 4), far}
    dx, dy = ((0, 1) if far[0] != 4 else (1, 0))
    origin, beyond = (far[0] - dx, far[1] - dy), (far[0] + dx, far[1] + dy)
    source = actor(arena, "Far-end attacker", origin)
    Entity.update_all_entities_senses()
    assert not get_map().can_reach_between(origin, beyond, PhysicalAccess.PROJECTILE, source.uuid)
    budget = source.action_economy.movement_remaining()
    denied = Move(source_entity_uuid=source.uuid, path=[origin, far], end_position=far, prefer_safe=False).apply()
    assert denied is not None and source.position == origin
    assert source.action_economy.movement_remaining() == budget
    for _ in range(4):
        if prop.integrity is ItemIntegrity.DESTROYED:
            break
        source.action_economy.reset_all_costs()
        with fixed_dice_faces(19, 8):
            source.update_entity_senses()
            hit = Attack(weapon_slot=WeaponSlot.MELEE_MAIN, source_entity_uuid=source.uuid, target_entity_uuid=prop.uuid).apply()
        assert hit is not None and not hit.canceled
    assert prop.integrity is ItemIntegrity.DESTROYED
    after = get_map().get_object_placement(prop.uuid)
    assert after is not None and set(after.positions) == {(4, 4), far}
    assert get_map().is_walkable_for(4, 4) and get_map().is_walkable_for(*far)
    assert get_map().can_reach_between(origin, beyond, PhysicalAccess.PROJECTILE, source.uuid)
    step = Move(source_entity_uuid=source.uuid, path=[origin, far], end_position=far, prefer_safe=False).apply()
    assert step is not None and not step.canceled and source.position == far
