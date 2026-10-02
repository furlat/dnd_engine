"""Object damage and attack contact use native components and exact placement."""

from collections.abc import Iterator
from uuid import uuid4

import pytest

from dnd.blocks.base_item import BaseItem, WorldItem
from dnd.content.items.environment_item_builders import build_authored_door, build_directional_wall
from dnd.content.items.window_builders import place_window
from dnd.content.items.world_prop_builders import build_world_prop
from dnd.core.aoe import Sphere
from dnd.core.creature_types import DamageType
from dnd.core.dice import AttackOutcome, fixed_dice_faces
from dnd.core.events import Damage, EventPhase, EventQueue, ItemDestructionEvent, TakeDamageEvent
from dnd.core.geometry import circle_positions
from dnd.core.gridmap import get_map
from dnd.core.item_types import ItemDestructionProfile
from dnd.core.values import ModifiableValue
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.types.physical_access import PhysicalAccess
from dnd.types.world import CardinalDirection
from dnd.types.world_placement import WorldPlacementKind, WorldPlacementSpec


@pytest.fixture
def arena() -> Iterator[Game]:
    reset_engine_runtime(grid_size=(8, 8))
    game = Game()
    yield game
    game.close()
    reset_engine_runtime()


def actor(game: Game, position: tuple[int, int]) -> Entity:
    entity = Entity.create(uuid4(), "Attacker", config=EntityConfig(position=position))
    entity.compose_entity()
    game.deploy_entity(entity, position)
    return entity


def prop(*, hp: int = 30, immune_fire: bool = False,
         offsets: tuple[tuple[int, int], ...] = ((0, 0),)) -> WorldItem:
    owner = uuid4()
    return WorldItem(source_entity_uuid=owner, item_id="test.attackable_prop", name="Prop",
        is_targetable=True, blocks_movement=True, blocks_propagation_field=True,
        health=BaseItem.create_item_health(owner, hp,
            immunities=[DamageType.FIRE] if immune_fire else []),
        world_placement_spec=WorldPlacementSpec(kind=WorldPlacementKind.CENTER,
            occupies_bands=True, vertical_extent_steps=1, footprint_offsets=offsets),
        destruction_profile=ItemDestructionProfile(name="Debris"))


@pytest.mark.parametrize("hp,expected_break", [(30, False), (6, True)])
def test_real_mixed_damage_retains_rolls_and_resolves_each_affinity_once(arena, hp, expected_break):
    item = prop(hp=hp, immune_fire=True)
    item.place_on_grid((2, 2))
    specs = [Damage(source_entity_uuid=item.uuid, target_entity_uuid=item.uuid,
        damage_type=damage_type, dice_numbers=1, damage_dice=6,
        damage_bonus=ModifiableValue.create(source_entity_uuid=item.uuid, base_value=0))
        for damage_type in (DamageType.SLASHING, DamageType.FIRE)]
    with fixed_dice_faces(6, 6):
        rolls = [damage.get_dice(AttackOutcome.HIT).roll for damage in specs]
    cursor = EventQueue.event_cursor()
    assert item.receive_damage(12, DamageType.SLASHING, item.uuid,
        damage_rolls=rolls, damages=specs, effect_id="test.mixed_hit") == 6
    events = [event for _, event in EventQueue.iter_events_since(cursor)
              if event.phase is EventPhase.COMPLETION]
    damage, = [event for event in events if isinstance(event, TakeDamageEvent)]
    assert [roll.roll_uuid for roll in damage.damage_rolls] == [roll.roll_uuid for roll in rolls]
    assert [spec.uuid for spec in damage.damages] == [spec.uuid for spec in specs]
    assert damage.resolution is not None
    assert [(component.damage_type, component.after_affinity_damage)
            for component in damage.resolution.components] == [(DamageType.SLASHING, 6), (DamageType.FIRE, 0)]
    assert damage.effect_id == "test.mixed_hit"
    assert damage.resulting_hp == hp - 6
    destruction = [event for event in events if isinstance(event, ItemDestructionEvent)]
    assert len(destruction) == int(expected_break)
    if destruction:
        assert destruction[0].parent_lineage == damage.lineage_uuid
        assert item.receive_damage(12, DamageType.SLASHING, item.uuid,
            damage_rolls=rolls, damages=specs) == 0


def test_ranged_contact_uses_rotated_far_support_and_manual_use_stays_five_feet(arena):
    attacker = actor(arena, (3, 6))
    item = prop(offsets=((0, 0), (1, 0)))
    item.place_on_grid((3, 2), orientation=CardinalDirection.NORTH)
    grid = get_map()
    assert grid.manual_object_contact(attacker.uuid, item.uuid) is None
    assert grid.attack_object_contact(attacker.uuid, item.uuid,
        range_feet=10, access=PhysicalAccess.WEAPON) is None
    assert grid.attack_object_contact(attacker.uuid, item.uuid,
        range_feet=15, access=PhysicalAccess.PROJECTILE) == (3, 3)
    blocker = prop()
    blocker.place_on_grid((3, 5))
    assert grid.attack_object_contact(attacker.uuid, item.uuid,
        range_feet=60, access=PhysicalAccess.PROJECTILE) is None


@pytest.mark.parametrize("position", [(1, 2), (6, 2)])
def test_boundary_target_is_contactable_from_either_side_without_exempting_other_walls(arena, position):
    attacker = actor(arena, position)
    door = build_authored_door("environment.door.desert_c7")
    door.place_on_grid((3, 2), boundary_direction=CardinalDirection.EAST)
    grid = get_map()
    contact = (3, 2) if position[0] < 3 else (4, 2)
    assert grid.attack_object_contact(attacker.uuid, door.uuid,
        range_feet=15, access=PhysicalAccess.PROJECTILE) == contact
    obstruction = build_directional_wall()
    obstruction.place_on_grid((2 if position[0] < 3 else 5, 2),
        boundary_direction=CardinalDirection.EAST)
    assert grid.attack_object_contact(attacker.uuid, door.uuid,
        range_feet=30, access=PhysicalAccess.PROJECTILE) is None


def test_parent_aperture_still_restricts_heavy_contact_with_its_insert(arena):
    attacker = actor(arena, (1, 2))
    assembly = place_window("environment.window.fantasy_g9", (3, 2), CardinalDirection.EAST)
    assert assembly.insert is not None
    # The observer contacts the near-side insert directly. Targeting something
    # beyond the assembly instead must obey both parent and insert providers.
    target = prop()
    target.place_on_grid((5, 2))
    grid = get_map()
    assert grid.attack_object_contact(attacker.uuid, assembly.insert.uuid,
        range_feet=15, access=PhysicalAccess.LIGHT_WEAPON) == (3, 2)
    assert grid.attack_object_contact(attacker.uuid, target.uuid,
        range_feet=30, access=PhysicalAccess.PROJECTILE) is None
    assembly.insert.receive_damage(100, DamageType.BLUDGEONING, attacker.uuid)
    assert grid.attack_object_contact(attacker.uuid, target.uuid,
        range_feet=30, access=PhysicalAccess.PROJECTILE) == (5, 2)
    assert grid.attack_object_contact(attacker.uuid, target.uuid,
        range_feet=30, access=PhysicalAccess.WEAPON) is None
    assert grid.attack_object_contact(attacker.uuid, target.uuid,
        range_feet=30, access=PhysicalAccess.LIGHT_WEAPON) == (5, 2)


def test_area_contact_finds_unreached_side_door_and_requeries_after_real_break(arena):
    grid = get_map()
    # Solid side walls form a narrow corridor using ordinary boundary providers.
    for x in range(6):
        for direction in (CardinalDirection.NORTH, CardinalDirection.SOUTH):
            wall = build_directional_wall()
            wall.place_on_grid((x, 2), boundary_direction=direction)
    door = build_authored_door("environment.door.desert_c7", hit_points=4)
    door.place_on_grid((3, 2), boundary_direction=CardinalDirection.WEST)
    beyond = prop()
    beyond.place_on_grid((4, 2))
    origin = (1, 2)
    area = Sphere(source_entity_uuid=door.uuid, target=origin, radius_feet=15, propagation="connected")
    area.compute_objective(origin)
    geometry = circle_positions(origin, 3, include_center=True)
    before = grid.area_object_contacts(area.affected_positions, geometric_positions=geometry, origin=origin)
    assert (3, 2) not in area.affected_positions
    assert before[door.uuid] == (2, 2)
    assert beyond.uuid not in before
    door.receive_damage(4, DamageType.FIRE, door.uuid)
    area.compute_objective(origin)
    after = grid.area_object_contacts(area.affected_positions, geometric_positions=geometry, origin=origin)
    assert after[beyond.uuid] == (4, 2)
    assert (5, 2) not in area.affected_positions  # No radius restart at the breach.


def test_authored_native_object_defenses_follow_material_and_assembly(arena):
    assert build_world_prop("environment.furniture.table").armor_class == 15
    assert build_authored_door("environment.door.desert_c7").armor_class == 15
    assert build_authored_door("environment.door.desert_c1").armor_class == 19
    assembly = place_window("environment.window.fantasy_a4", (3, 2), CardinalDirection.EAST)
    assert assembly.wall.armor_class == 17
    assert assembly.insert is not None and assembly.insert.armor_class == 19
