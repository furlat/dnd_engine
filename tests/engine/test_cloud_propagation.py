"""Real cloud casts own a connected footprint independent of later door state."""

import pytest

from dnd.actions import SpellEvent
from dnd.content.items.environment_item_builders import build_directional_door, build_directional_wall
from dnd.core.events import EventQueue, SpatialEffectChangeEvent, TakeDamageEvent
from dnd.core.dice import fixed_dice_faces
from dnd.core.gridmap import get_map
from dnd.core.world_edges import ElevationSurfaceKind
from dnd.entity import Entity
from dnd.items.environment import DirectionalDoor
from dnd.types.senses import PerceivedSpatialEffect
from dnd.runtime_reset import reset_engine_runtime
from dnd.spatial.area_conditions import AreaCondition
from dnd.spells.conjuration import (
    Cloudkill, Darkness, FogCloud, IncendiaryCloud, InsectPlague, StinkingCloud,
)
from tests.manual.spell_regression_support import create_spell_regression_actor, reset_spell_regression_arena
from dnd.types.world import CardinalDirection


CLOUDS = (FogCloud, Darkness, StinkingCloud, Cloudkill, IncendiaryCloud, InsectPlague)


@pytest.fixture(autouse=True)
def arena():
    reset_spell_regression_arena(15, 17)
    yield
    reset_engine_runtime()


def cast_beside_door(spell_type, *, opened, level=None):
    caster = create_spell_regression_actor('Caster', (0, 8), 'heroes',
        spell_slots={slot: 2 for slot in range(1, 10)})
    door = build_directional_door(is_open=opened)
    door.place_on_grid((6, 8), boundary_direction=CardinalDirection.EAST)
    for y in range(17):
        if y != 8:
            build_directional_wall().place_on_grid((6, y), boundary_direction=CardinalDirection.EAST)
    Entity.update_all_entities_senses(max_distance=120)
    arguments = {'source_entity_uuid': caster.uuid, 'end_position': (5, 8)}
    if level is not None:
        arguments['cast_at_level'] = level
    spell = spell_type(**arguments)
    result = spell.apply()
    assert isinstance(result, SpellEvent) and not result.canceled, result
    zone, = (row for row in get_map().get_spatial_conditions() if isinstance(row, AreaCondition))
    return caster, door, zone


@pytest.mark.parametrize('spell_type', CLOUDS, ids=lambda kind: kind.__name__)
@pytest.mark.parametrize('opened', (False, True))
def test_cast_cloud_spreads_around_opening_within_native_radius(spell_type, opened):
    caster, _, zone = cast_beside_door(spell_type, opened=opened)
    reached = zone.affected_positions
    assert ((7, 10) in reached) is opened
    assert all((x-5)**2 + (y-8)**2 <= (zone.zone_radius_feet / 5)**2 for x, y in reached)
    if not opened:
        assert all(x <= 6 for x, _ in reached)
    observation = caster.senses.spatial_effects[zone.uuid]
    assert observation.area_propagation == 'connected'
    assert set(observation.positions) <= reached


def test_fog_cloud_retains_slot_scaled_radius():
    _, _, zone = cast_beside_door(FogCloud, opened=True, level=2)
    assert zone.zone_radius_feet == 40
    assert (11, 10) in zone.affected_positions
    assert all((x-5)**2 + (y-8)**2 <= 64 for x, y in zone.affected_positions)


def test_established_cloud_survives_door_close_open_and_destruction_without_retrigger():
    caster, door, zone = cast_beside_door(Cloudkill, opened=True)
    identity, positions = zone.uuid, set(zone.affected_positions)
    version = caster.senses.spatial_effects[identity].owner_revision
    assert (7, 10) in positions
    cursor = EventQueue.event_cursor()
    for transition in (door.close, door.open, door.close, door.destroy):
        transition()
        assert get_map().get_spatial_condition(identity) is zone
        assert zone.affected_positions == positions
        assert caster.senses.spatial_effects[identity].owner_revision == version
    events = [event for _, event in EventQueue.iter_events_since(cursor)]
    assert not any(isinstance(event, TakeDamageEvent) for event in events)
    assert not any(isinstance(event, SpatialEffectChangeEvent) and event.spatial_effect_uuid == identity
                   for event in events)


@pytest.mark.parametrize('opened', (False, True))
def test_creature_around_corner_takes_only_the_admitted_cloud_damage(opened):
    victim = create_spell_regression_actor('Behind corner', (7, 10), 'monsters')
    before = victim.get_hp()
    with fixed_dice_faces(*([4] * 40)):
        _, door, zone = cast_beside_door(Cloudkill, opened=opened)
        victim.on_turn_start(round_number=1, turn_index=1)
    assert (victim.get_hp() < before) is opened
    after_turn = victim.get_hp()
    if opened:
        door.close()
        assert victim.get_hp() == after_turn
        assert victim.position in zone.affected_positions
        with fixed_dice_faces(*([4] * 40)):
            victim.on_turn_start(round_number=2, turn_index=1)
        assert victim.get_hp() < after_turn, 'Closing the door does not cure an occupied cloud cell'


def test_real_cloud_turn_movement_resolves_connected_destination_after_door_closes():
    caster, door, zone = cast_beside_door(Cloudkill, opened=True)
    original = set(zone.affected_positions)
    original_revision = caster.senses.spatial_effects[zone.uuid].owner_revision
    door.close()
    assert zone.affected_positions == original
    caster.on_turn_start(round_number=2, turn_index=0)
    assert zone.position == (7, 8)
    assert zone.affected_positions != original
    assert zone.observation_revision > original_revision
    # The caster is behind the closed door: its remembered cloud must keep
    # the old revision until it sees the cloud's new position.
    assert caster.senses.spatial_effects[zone.uuid].owner_revision == original_revision
    door.open()
    assert caster.senses.spatial_effects[zone.uuid].owner_revision == zone.observation_revision
    assert all(x >= 7 for x, _ in zone.affected_positions)
    assert all((x-7)**2 + (y-8)**2 <= 16 for x, y in zone.affected_positions)


@pytest.mark.parametrize('height', (2, 12))
def test_known_cloud_upper_surface_clears_finite_wall_without_revealing_floor_or_creature(height):
    caster = create_spell_regression_actor('Observer', (0, 8), 'heroes', spell_slots={1: 2})
    victim = create_spell_regression_actor('Hidden', (7, 8), 'monsters')
    for y in range(7, 10):
        DirectionalDoor(source_entity_uuid=caster.uuid, item_id='test.cloud_boundary',
            vertical_extent_steps=height).place_on_grid((6, y), boundary_direction=CardinalDirection.EAST)
    cast = FogCloud(source_entity_uuid=caster.uuid, end_position=(5, 8)).apply()
    assert cast is not None and not cast.canceled
    zone, = get_map().get_spatial_conditions()
    assert (7, 8) in get_map().get_spatial_condition_positions(zone.uuid)
    observed = caster.senses.spatial_effects[zone.uuid]
    assert (7, 8) not in observed.visible_volume_positions
    assert (7, 8) not in caster.senses.visible and victim.uuid not in caster.senses.entities
    grants = {row.position: row for row in observed.upper_volume_surfaces}
    assert ((7, 8) in grants) is (height == 2)
    if height == 2:
        planes = grants[(7, 8)].lower_height_planes
        assert planes and all(3 > a*7 + b*8 + c > 2 for a,b,c in planes)
        assert PerceivedSpatialEffect.model_validate_json(observed.model_dump_json()) == observed
    # Native limited sight must revoke upper grants too, even for remembered fields.
    Entity.update_all_entities_senses(max_distance=3)
    remembered = caster.senses.spatial_effects[zone.uuid]
    assert not remembered.upper_volume_surfaces


def test_upper_surface_updates_when_a_door_behind_another_wall_closes_and_reopens():
    caster = create_spell_regression_actor('Observer', (0, 8), 'heroes', spell_slots={1: 2})
    for y in range(7, 10):
        build_directional_wall().place_on_grid((6, y), boundary_direction=CardinalDirection.EAST)
    door = DirectionalDoor(source_entity_uuid=caster.uuid, item_id='test.remote_cloud_door',
        vertical_extent_steps=12, is_open=True)
    door.place_on_grid((7, 8), boundary_direction=CardinalDirection.EAST)
    cast = FogCloud(source_entity_uuid=caster.uuid, end_position=(5, 8)).apply()
    assert cast is not None and not cast.canceled
    zone, = get_map().get_spatial_conditions()
    initial = caster.senses.spatial_effects[zone.uuid].upper_volume_surfaces
    assert any(row.position == (8, 8) for row in initial)
    door.close()
    assert not any(row.position == (8, 8) for row in caster.senses.spatial_effects[zone.uuid].upper_volume_surfaces)
    door.open()
    assert caster.senses.spatial_effects[zone.uuid].upper_volume_surfaces == initial
    assert (8, 8) not in caster.senses.visible


def test_observer_support_height_refreshes_cloud_surface_sight_without_revealing_ground():
    caster = create_spell_regression_actor('Observer', (0, 8), 'heroes', spell_slots={1: 2})
    for y in range(7, 10):
        build_directional_wall().place_on_grid((6, y), boundary_direction=CardinalDirection.EAST)
    cast = FogCloud(source_entity_uuid=caster.uuid, end_position=(5, 8)).apply()
    assert cast is not None and not cast.canceled
    grid = get_map()
    zone, = grid.get_spatial_conditions()
    initial = caster.senses.spatial_effects[zone.uuid].upper_volume_surfaces
    assert initial
    assert grid.set_tile_elevation(caster.position, height=2, surface_kind=ElevationSurfaceKind.ORDINARY, slope_axis=None)
    raised = caster.senses.spatial_effects[zone.uuid].upper_volume_surfaces
    assert raised != initial
    assert (8, 8) not in caster.senses.visible
    assert grid.set_tile_elevation(caster.position, height=0, surface_kind=ElevationSurfaceKind.ORDINARY, slope_axis=None)
    assert caster.senses.spatial_effects[zone.uuid].upper_volume_surfaces == initial
