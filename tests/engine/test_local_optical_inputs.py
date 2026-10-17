"""Bounded optical query inputs and subscriber-local mutation diagnostics.

GridMap callers must see the same native optical facts in a detached solve input;
its public revision diagnostics must change only for intersecting subscriptions.
"""
from uuid import uuid4

import pytest

from dnd.core.aoe import Sphere
from dnd.blocks.base_item import BaseItem, WorldItem
from dnd.core.base_block import LightLevel
from dnd.core.base_tiles import resolve_tile_light_level
from dnd.core.base_conditions import SpellProtection, SpellProtectionRegistry
from dnd.core.events import Event, EventHandler, EventPhase, EventQueue, EventType, Trigger
from dnd.core.gridmap import get_map
from dnd.core.creature_types import DamageType
from dnd.core.item_types import ItemDestructionProfile, ItemIntegrity
from dnd.entity import Entity
from dnd.items.environment import DirectionalWall
from dnd.types.world import (
    CardinalDirection, ObserverRevisions, SpatialChannel, WorldEdgeChannel, edge_revision_channels,
)
from dnd.types.materials import Material
from dnd.types.world_placement import (
    BoundaryStructure, BoundaryStructureKind, WorldPlacementKind, WorldPlacementSpec,
)
from dnd.spells.conjuration import DarknessZone, FogCloudZone
from dnd.types.senses import OpticalObscurement
from tests.engine.test_senses_light_stealth import create_skeleton, reset_senses_state



def _force_cold_queries(grid, channel: WorldEdgeChannel) -> None:
    """Drop warm query caches through a public write: toggle an empty Tile's matching blocker."""
    corner = next(position for position in sorted(grid.get_all_tiles())
        if not grid.get_objects_at(position) and not grid.get_entities_at(position))
    tile = grid.get_tile(*corner)
    assert tile is not None
    optics = channel is WorldEdgeChannel.OPTICAL
    for blocked in (True, False):
        grid.set_tile(*corner, blocks_optics=blocked if optics else tile.blocks_optics,
            blocks_propagation=tile.blocks_propagation_field if optics else blocked,
            default_light=tile.default_light)

def cause(source_uuid):
    return Event(event_type=EventType.BASE_ACTION, source_entity_uuid=source_uuid,
                 phase=EventPhase.EFFECT)


def test_optical_snapshot_preserves_native_owner_exclusion_and_detachment():
    reset_senses_state(width=9, height=3)
    grid = get_map()
    source = uuid4()
    fog = FogCloudZone(source_entity_uuid=source, position=(1, 1), area=Sphere(radius_feet=0, propagation="connected"))
    fog.activate(parent_event=None)
    remote = FogCloudZone(source_entity_uuid=source, position=(8, 1), area=Sphere(radius_feet=0, propagation="connected"))
    remote.activate(parent_event=None)
    grid.apply_optical_obscurement(fog.uuid, {(1, 1)}, OpticalObscurement.MAGICAL_DARKNESS)
    snapshot = grid.capture_optical_obscurements((0, 0), 2)
    assert set(snapshot) == {(1, 1)}
    assert snapshot[(1, 1)][fog.uuid] == frozenset({
        OpticalObscurement.HEAVY, OpticalObscurement.MAGICAL_DARKNESS})
    for excluded in (None, fog.uuid):
        assert grid.get_optical_obscurements_on_route((0, 0), (2, 2),
            excluded_owner_uuid=excluded, snapshot=snapshot) == grid.get_optical_obscurements_on_route(
                (0, 0), (2, 2), excluded_owner_uuid=excluded)
    fog.deactivate()
    grid.remove_optical_obscurement(fog.uuid)
    assert not grid.get_optical_obscurements_at((1, 1))
    assert grid.get_optical_obscurements_at((1, 1), snapshot=snapshot) == {
        OpticalObscurement.HEAVY, OpticalObscurement.MAGICAL_DARKNESS}
    assert grid.get_optical_obscurements_on_route((0, 1), (8, 1), snapshot={}) == set()


def test_snapshot_keeps_explicit_optics_on_removed_support_and_tracks_removal():
    reset_senses_state(width=3, height=1)
    grid = get_map()
    owner, observer = uuid4(), uuid4()
    grid.subscribe_to_cells(observer, {(1, 0)})
    grid.apply_optical_obscurement(owner, {(1, 0)}, OpticalObscurement.MAGICAL_DARKNESS)
    grid.remove_tile(1, 0)
    snapshot = grid.capture_optical_obscurements((0, 0), 2)
    assert grid.get_optical_obscurements_at((1, 0), snapshot=snapshot) == {
        OpticalObscurement.MAGICAL_DARKNESS}
    before = grid.observer_spatial_revisions(observer)
    grid.remove_optical_obscurement(owner)
    assert not grid.capture_optical_obscurements((0, 0), 2)
    assert grid.observer_spatial_revisions(observer).optical > before.optical


def test_subscriber_revisions_follow_local_geometry_light_and_occupancy():
    reset_senses_state(width=33, height=1)
    grid = get_map()
    mover = create_skeleton(name="Mover", position=(0, 0), darkvision=False)
    near, far = uuid4(), uuid4()
    grid.subscribe_to_cells(near, {(-1, 0), (0, 0), (1, 0)})
    grid.subscribe_to_cells(far, {(32, 0)})
    initial = grid.observer_spatial_revisions(near)
    remote_initial = grid.observer_spatial_revisions(far)
    grid.set_tile_base_light((1, 0), LightLevel.DIM_LIGHT)
    after_light = grid.observer_spatial_revisions(near)
    assert after_light.illumination > initial.illumination
    assert ((after_light.optical, after_light.propagation, after_light.occupancy)
            == (initial.optical, initial.propagation, initial.occupancy))
    Entity.update_entity_position(mover, (1, 0))
    after_move = grid.observer_spatial_revisions(near)
    assert after_move.occupancy > after_light.occupancy
    grid.set_tile(-1, 0)
    assert grid.observer_spatial_revisions(near).optical > after_move.optical
    assert grid.observer_spatial_revisions(far) == remote_initial
    # A presence change has unknown coverage (attached contributions), so it
    # reaches subscribers far from the anchor.
    mover.suspend_spatial_presence()
    assert grid.observer_spatial_revisions(far).optical > remote_initial.optical
    grid.unsubscribe_entity(near)
    grid.subscribe_to_cells(near, {(0, 0)})
    assert grid.observer_spatial_revisions(near) == ObserverRevisions()


def test_area_move_and_footprint_change_commit_optics_before_light_children():
    reset_senses_state(width=6, height=1)
    grid = get_map()
    source, observer = uuid4(), uuid4()
    darkness = DarknessZone(source_entity_uuid=source, position=(1, 0), area=Sphere(radius_feet=0, propagation="connected"))
    darkness.activate(parent_event=None)
    grid.subscribe_to_cells(observer, {(1, 0), (3, 0)})
    initial = grid.observer_spatial_revisions(observer).optical
    observations = []

    def observe_light(event, _source_uuid):
        observations.append((set(darkness.affected_positions),
            grid.get_optical_obscurements_at((3, 0)),
            grid.observer_spatial_revisions(observer).optical))
        return None

    EventQueue.add_event_handler(EventHandler(source_entity_uuid=source,
        trigger_conditions=[Trigger(event_type=EventType.SPATIAL_LIGHT_CHANGED,
                                    event_phase=EventPhase.EFFECT)],
        event_processor=observe_light))
    darkness.move_zone((3, 0), parent_event=cause(source))
    added = [row for row in observations if row[0] == {(3, 0)}]
    assert added and all(row[1] == {OpticalObscurement.MAGICAL_DARKNESS} and row[2] > initial
                         for row in added)
    observations.clear()
    initial = grid.observer_spatial_revisions(observer).optical
    darkness.change_footprint({(4, 0)}, parent_event=cause(source))
    assert observations and all(not row[1] and row[2] > initial for row in observations)
    assert not grid.capture_optical_obscurements((3, 0), 0)
    darkness.change_footprint({(3, 0)}, parent_event=cause(source))
    assert grid.get_optical_obscurements_at((3, 0), snapshot=grid.capture_optical_obscurements((3, 0), 0)) == {
        OpticalObscurement.MAGICAL_DARKNESS}


def test_creator_candidates_follow_placement_source_and_reset_without_granting_knowledge():
    reset_senses_state(width=4, height=1)
    grid = get_map()
    first = uuid4()
    receiver = create_skeleton(name="Recipient", position=(3, 0), darkvision=False)
    second = receiver.uuid
    item = BaseItem(source_entity_uuid=first, item_id="test.creator_item", known_to_creator=False)
    item.place_on_grid((1, 0))
    assert grid.get_known_object_candidates(first) == (item.uuid,)
    assert not item.is_object_known_to(first)
    item.known_to_creator = True
    assert item.is_object_known_to(first)
    assert receiver.loot_item(item)
    assert item.source_entity_uuid == second
    assert grid.get_known_object_candidates(first) == ()
    assert grid.get_known_object_candidates(second) == ()
    assert receiver.drop_item(item.uuid, (1, 0)) is item
    assert grid.get_known_object_candidates(second) == (item.uuid,)
    grid.move_object(item.uuid, (2, 0))
    assert grid.get_known_object_candidates(second) == (item.uuid,)
    grid.remove_object(item.uuid)
    assert grid.get_known_object_candidates(second) == ()
    item.place_on_grid((1, 0))
    grid.subscribe_to_cells(first, {(1, 0)})
    reset_senses_state(width=4, height=1)
    grid = get_map()
    assert grid.get_known_object_candidates(second) == ()
    assert grid.observer_spatial_revisions(first) == ObserverRevisions()
    assert not grid.capture_optical_obscurements((1, 0), 1)


def test_dependency_bounds_never_expand_grants_and_replacement_releases_old_chunks():
    reset_senses_state(width=2, height=1)
    grid = get_map()
    observer = uuid4()
    grid.subscribe_to_cells(observer, {(0, 0)}, dependency_cells={(-17, 0)},
                            dependency_bounds=(-1, -1, 16, 16))
    assert grid.get_subscribers_at((16, 16)) == set()
    assert grid.get_subscribers_for_cells({(-17, 0), (16, 16)}) == set()
    assert grid.get_entity_subscriptions(observer) == {(0, 0)}
    assert observer in grid.get_dependent_observers_at((16, 16))
    assert observer in grid.get_dependent_observers_at((-17, 0))
    grid.subscribe_to_cells(observer, {(0, 0)}, dependency_bounds=(0, 0, 0, 0))
    assert observer not in grid.get_dependent_observers_at((16, 16))
    assert observer not in grid.get_dependent_observers_at((-17, 0))
    grid.unsubscribe_entity(observer)
    assert observer not in grid.get_dependent_observers_at((0, 0))
    assert observer not in grid.get_subscribers_at((0, 0))


def test_optical_candidates_follow_overlap_relocation_and_negative_chunks():
    reset_senses_state(width=1, height=1)
    grid = get_map()
    for position in ((-17, 0), (-16, 0), (16, 0)):
        grid.set_tile(*position)
    first = FogCloudZone(source_entity_uuid=uuid4(), position=(-17, 0), area=Sphere(radius_feet=0, propagation="connected"))
    second = DarknessZone(source_entity_uuid=uuid4(), position=(-17, 0), area=Sphere(radius_feet=0, propagation="connected"))
    first.activate(parent_event=None)
    second.activate(parent_event=None)
    first.move_zone((-16, 0), parent_event=cause(first.source_entity_uuid))
    snapshot = grid.capture_optical_obscurements((-16, 0), 1)
    assert grid.get_optical_obscurements_at((-17, 0), snapshot=snapshot) == {OpticalObscurement.MAGICAL_DARKNESS}
    assert grid.get_optical_obscurements_at((-16, 0), snapshot=snapshot) == {OpticalObscurement.HEAVY}
    second.deactivate()
    first.move_zone((16, 0), parent_event=cause(first.source_entity_uuid))
    assert not grid.capture_optical_obscurements((-16, 0), 1)
    assert grid.get_optical_obscurements_at((16, 0), snapshot=grid.capture_optical_obscurements((0, 0), 16)) == {
        OpticalObscurement.HEAVY}


def test_boundary_batch_preserves_ordered_incident_faces_and_upper_planes():
    reset_senses_state(width=5, height=3)
    grid = get_map()
    exit_wall = DirectionalWall(source_entity_uuid=uuid4(), item_id="test.exit_wall",
        blocked_channels=(WorldEdgeChannel.OPTICAL,))
    entry_wall = DirectionalWall(source_entity_uuid=uuid4(), item_id="test.entry_wall",
        blocked_channels=(WorldEdgeChannel.PROPAGATION,))
    exit_wall.place_on_grid((1, 1), boundary_direction=CardinalDirection.EAST)
    entry_wall.place_on_grid((2, 1), boundary_direction=CardinalDirection.WEST)
    snapshot = grid.capture_boundary_snapshot({(1, 1), (2, 1)})
    for position in ((1, 1), (2, 1), (4, 1)):
        for direction in CardinalDirection:
            for channel in (WorldEdgeChannel.OPTICAL, WorldEdgeChannel.PROPAGATION):
                assert grid.get_boundary_route_layers(position, direction, channel, snapshot=snapshot) == (
                    grid.get_boundary_route_layers(position, direction, channel))
    assert grid.get_boundary_route_layers((1, 1), CardinalDirection.EAST,
        WorldEdgeChannel.OPTICAL, snapshot=snapshot) == ((exit_wall.uuid,), ())
    assert grid.get_boundary_route_layers((1, 1), CardinalDirection.EAST,
        WorldEdgeChannel.PROPAGATION, snapshot=snapshot) == ((exit_wall.uuid,), (entry_wall.uuid,))
    planes = grid.upper_volume_sight_planes((0, 1), (3, 1), snapshot=snapshot)
    assert planes and planes == grid.upper_volume_sight_planes((0, 1), (3, 1))
    grid.remove_object(exit_wall.uuid)
    assert grid.get_boundary_route_layers((1, 1), CardinalDirection.EAST,
        WorldEdgeChannel.OPTICAL) == ((), (entry_wall.uuid,))
    assert grid.get_boundary_route_layers((1, 1), CardinalDirection.EAST,
        WorldEdgeChannel.OPTICAL, snapshot=snapshot) == ((exit_wall.uuid,), ())
    assert grid.upper_volume_sight_planes((0, 1), (3, 1), snapshot=snapshot) == planes
    grid.move_object(entry_wall.uuid, (3, 1), boundary_direction=CardinalDirection.WEST)
    moved = grid.capture_boundary_snapshot({(1, 1), (2, 1), (3, 1)})
    assert grid.get_boundary_route_layers((1, 1), CardinalDirection.EAST,
        WorldEdgeChannel.PROPAGATION, snapshot=moved) == ((), ())
    assert grid.get_boundary_route_layers((2, 1), CardinalDirection.EAST,
        WorldEdgeChannel.PROPAGATION, snapshot=moved) == ((), (entry_wall.uuid,))
    grid.remove_object(entry_wall.uuid)
    grid.remove_tile(3, 1)
    grid.set_tile(3, 1)
    empty = grid.capture_boundary_snapshot({(1, 1), (2, 1), (3, 1)})
    assert grid.get_boundary_route_layers((2, 1), CardinalDirection.EAST,
        WorldEdgeChannel.PROPAGATION, snapshot=empty) == ((), ())


@pytest.mark.parametrize("origin", [(-17, -17), (-16, -16), (15, 15), (16, 16)])
def test_boundary_batch_preserves_empty_halo_and_native_outside_queries(origin):
    """Captured empty cardinal cells stay empty; diagonal outsiders read live."""
    reset_senses_state(width=1, height=1)
    grid = get_map()
    for dx in range(-2, 3):
        for dy in range(-2, 3):
            grid.set_tile(origin[0] + dx, origin[1] + dy)
    snapshot = grid.capture_boundary_snapshot({origin})
    for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1)):
        position = origin[0] + dx, origin[1] + dy
        wall = DirectionalWall(source_entity_uuid=uuid4(), item_id="test.snapshot_halo")
        wall.place_on_grid(position, boundary_direction=CardinalDirection.NORTH)
        expected = () if abs(dx) + abs(dy) <= 1 else (wall.uuid,)
        assert grid.get_boundary_route_layers(position, CardinalDirection.NORTH,
            WorldEdgeChannel.OPTICAL, snapshot=snapshot)[0] == expected
        assert grid.get_boundary_route_layers(position, CardinalDirection.NORTH,
            WorldEdgeChannel.OPTICAL)[0] == (wall.uuid,)
    fresh = grid.capture_boundary_snapshot({origin})
    fresh.layers[origin].clear()
    later = grid.capture_boundary_snapshot({origin})
    assert grid.get_boundary_route_layers(origin, CardinalDirection.NORTH,
        WorldEdgeChannel.OPTICAL, snapshot=later) == grid.get_boundary_route_layers(
            origin, CardinalDirection.NORTH, WorldEdgeChannel.OPTICAL)


def test_fov_queries_remain_detached_across_ranges_origins_and_topology_changes():
    reset_senses_state(width=74, height=3)
    grid = get_map()
    wall = DirectionalWall(source_entity_uuid=uuid4(), item_id="test.fov_wall",
                           blocked_channels=(WorldEdgeChannel.OPTICAL,))
    wall.place_on_grid((2, 1), boundary_direction=CardinalDirection.EAST)
    origin = (0, 1)
    nearby = grid.compute_fov(origin, 2)
    blocked = grid.compute_fov(origin, 6)
    assert grid.compute_fov(origin, 2) == nearby
    assert (3, 1) not in blocked
    for x in range(1, 72):
        grid.compute_fov((x, 1), 2)
        grid.compute_propagation_fov((x, 1), 2)
    assert grid.compute_fov(origin, 6) == blocked
    grid.remove_object(wall.uuid)
    assert (3, 1) in grid.compute_fov(origin, 6)
    assert (3, 1) not in blocked
    current_nearby = grid.compute_fov(origin, 2)
    grid.compute_fov(origin)
    assert grid.compute_fov(origin, 2) == current_nearby


@pytest.mark.parametrize("channel", [WorldEdgeChannel.OPTICAL, WorldEdgeChannel.PROPAGATION])
def test_batched_fov_matches_native_rays_for_each_target_path(channel):
    reset_senses_state(width=1, height=1)
    grid = get_map()
    cells = {(x, y) for x in range(-4, 5) for y in range(-4, 5)} - {(-2, 1), (2, 2)}
    for position in cells:
        grid.set_tile(*position, blocks_optics=position == (1, 0),
                      blocks_propagation=position == (0, -1))
    for position, direction, channels in (
        ((4, 4), CardinalDirection.NORTH, (WorldEdgeChannel.OPTICAL, WorldEdgeChannel.PROPAGATION)),
        ((-1, 1), CardinalDirection.EAST, (WorldEdgeChannel.OPTICAL,)),
        ((2, -1), CardinalDirection.NORTH, (WorldEdgeChannel.PROPAGATION,)),
        ((-1, -1), CardinalDirection.EAST, (WorldEdgeChannel.OPTICAL, WorldEdgeChannel.PROPAGATION)),
    ):
        wall = DirectionalWall(source_entity_uuid=uuid4(), item_id="test.ray_parity_wall",
                               blocked_channels=channels)
        wall.place_on_grid(position, boundary_direction=direction)
    query = grid.compute_fov if channel is WorldEdgeChannel.OPTICAL else grid.compute_propagation_fov
    for origin in ((0, 0), (-3, -2), (3, 2), (1, 0), (0, -1)):
        for radius in (2.5, 6, 0, 1.41, 1.42, None, 3, 1_000_000, 1e200):
            expected = [position for position in sorted(cells)
                if (radius is None or sum((a-b)**2 for a, b in zip(position, origin)) <= radius * radius)
                and grid.raycast_clear(origin, position, channel)]
            assert query(origin, radius) == expected, (channel, origin, radius)
    visible = query((0, 0), 4)
    terminal = (1, 0) if channel is WorldEdgeChannel.OPTICAL else (0, -1)
    descendant = (2, 0) if channel is WorldEdgeChannel.OPTICAL else (0, -2)
    assert terminal in visible
    assert descendant not in visible


@pytest.mark.parametrize("channel", [WorldEdgeChannel.OPTICAL, WorldEdgeChannel.PROPAGATION])
@pytest.mark.parametrize("holes", [(), ((1, 0),), ((1, 0), (0, 1))])
def test_directional_visibility_matches_every_small_scene_native_ray(channel, holes):
    reset_senses_state(width=1, height=1)
    grid = get_map()
    cells = sorted({(x, y) for x in range(-2, 3) for y in range(-2, 3)} - set(holes))
    for position in cells:
        grid.set_tile(*position, blocks_optics=position == (-1, 1),
                      blocks_propagation=position == (-1, -1))
    for position, side, channels in (
        ((2, 2), CardinalDirection.NORTH, (WorldEdgeChannel.OPTICAL, WorldEdgeChannel.PROPAGATION)),
        ((-1, 0), CardinalDirection.EAST, (WorldEdgeChannel.OPTICAL,)),
        ((0, -1), CardinalDirection.NORTH, (WorldEdgeChannel.PROPAGATION,)),
    ):
        wall = DirectionalWall(source_entity_uuid=uuid4(), item_id="test.all_rays_wall",
                               blocked_channels=channels)
        wall.place_on_grid(position, boundary_direction=side)
    query = grid.compute_fov if channel is WorldEdgeChannel.OPTICAL else grid.compute_propagation_fov
    for origin in cells:
        expected = [position for position in cells if grid.raycast_clear(origin, position, channel)]
        assert query(origin) == expected, (channel, holes, origin)


def zero_band_boundary():
    """Authored retained boundary with every occupied band already removed."""
    identity = uuid4()
    placement = WorldPlacementSpec(kind=WorldPlacementKind.BOUNDARY,
        occupies_bands=False, vertical_extent_steps=1, removed_local_bands=((0, 0, 0),))
    return WorldItem(uuid=identity, source_entity_uuid=uuid4(),
        item_id="test.zero_band_boundary", name="Retained boundary", is_targetable=True,
        world_placement_spec=placement, removed_local_bands=((0, 0, 0),),
        health=BaseItem.create_item_health(identity, 1),
        boundary_structure=BoundaryStructure(structure=BoundaryStructureKind.WALL,
            material=Material.STONE,
            blocked_channels=(WorldEdgeChannel.OPTICAL, WorldEdgeChannel.PROPAGATION)),
        destruction_profile=ItemDestructionProfile(name="Cleared boundary", outcome="clear",
            placement_spec=placement, boundary_structure=BoundaryStructure(
                structure=BoundaryStructureKind.WALL, material=Material.STONE, blocked_channels=())))


@pytest.mark.parametrize("channel", [WorldEdgeChannel.OPTICAL, WorldEdgeChannel.PROPAGATION])
@pytest.mark.parametrize("clear_structure", [False, True])
def test_zero_band_boundary_lifecycle_preserves_native_visibility_choice(channel, clear_structure):
    reset_senses_state(width=7, height=7)
    grid = get_map()
    grid.set_tile(2, 3, blocks_optics=True, blocks_propagation=True)
    origin, radius, witness = (1, 3), 5, (3, 2)
    query = grid.compute_fov if channel is WorldEdgeChannel.OPTICAL else grid.compute_propagation_fov
    before = set(query(origin, radius))
    expected = {position for position in grid.get_all_tiles()
        if sum((a-b)**2 for a, b in zip(position, origin)) <= radius**2
        and grid.raycast_clear(origin, position, channel)}
    assert witness not in expected
    # Sight shadowcasts until a boundary exists; propagation is always the native ray.
    assert (witness in before) is (channel is WorldEdgeChannel.OPTICAL)

    boundary = zero_band_boundary()
    boundary.place_on_grid((6, 6), boundary_direction=CardinalDirection.NORTH)
    placement = grid.get_object_placement(boundary.uuid)
    assert placement is not None and placement.positions == ()
    assert not grid.get_boundary_objects_at((6, 6), CardinalDirection.NORTH, 0)
    assert set(query(origin, radius)) == expected
    # A cold query must discover retained structural ownership without requiring
    # any surviving tile band, just as the warm placement update does.
    _force_cold_queries(grid, channel)
    assert set(query(origin, radius)) == expected

    if clear_structure:
        boundary.receive_damage(100, DamageType.BLUDGEONING, uuid4())
        assert boundary.integrity is ItemIntegrity.DESTROYED
        assert boundary.get_boundary_structure().blocked_channels == ()
        assert grid.get_object_placement(boundary.uuid).positions == ()
    else:
        grid.remove_object(boundary.uuid)
        assert grid.get_object_placement(boundary.uuid) is None
    assert set(query(origin, radius)) == before
    _force_cold_queries(grid, channel)
    assert set(query(origin, radius)) == before


@pytest.mark.parametrize("channel", [WorldEdgeChannel.OPTICAL, WorldEdgeChannel.PROPAGATION])
@pytest.mark.parametrize("offset", [(0, 0), (-16, -16)])
def test_directional_visibility_tracks_hole_creation_fill_and_rectangle_fill(channel, offset):
    reset_senses_state(width=1, height=1)
    grid = get_map()
    ox, oy = offset
    grid.create_rectangle(ox - 3, oy - 3, 7, 7)
    wall = DirectionalWall(source_entity_uuid=uuid4(), item_id="test.frontier_wall",
        blocked_channels=(WorldEdgeChannel.OPTICAL, WorldEdgeChannel.PROPAGATION))
    wall.place_on_grid((ox + 3, oy + 3), boundary_direction=CardinalDirection.NORTH)
    query = grid.compute_fov if channel is WorldEdgeChannel.OPTICAL else grid.compute_propagation_fov
    cells = {(ox + x, oy + y) for x in range(-3, 4) for y in range(-3, 4)}

    def check():
        for origin in (offset, (ox - 2, oy - 1), (ox + 2, oy + 1)):
            expected = [position for position in sorted(cells)
                if sum((a-b)**2 for a, b in zip(position, origin)) <= 9
                and grid.raycast_clear(origin, position, channel)]
            assert query(origin, 3) == expected, (channel, offset, origin)

    check()
    for position in ((ox+1, oy), (ox, oy+1), (ox+1, oy+1), (ox-1, oy-1)):
        assert grid.remove_tile(*position)
        cells.remove(position)
        check()
    grid.set_tile(ox+1, oy)
    cells.add((ox+1, oy))
    check()
    grid.create_rectangle(ox, oy+1, 2, 1)
    cells.update({(ox, oy+1), (ox+1, oy+1)})
    check()


@pytest.mark.parametrize("channel", [WorldEdgeChannel.OPTICAL, WorldEdgeChannel.PROPAGATION])
def test_visibility_follows_support_committed_after_acceptance_callbacks(channel):
    """Nested accepted Tile edits and cancellation leave exact current support."""
    reset_senses_state(width=3, height=1)
    grid = get_map()
    wall = DirectionalWall(source_entity_uuid=uuid4(), item_id="test.support_commit",
        blocked_channels=(WorldEdgeChannel.OPTICAL, WorldEdgeChannel.PROPAGATION))
    wall.place_on_grid((2, 0), boundary_direction=CardinalDirection.NORTH)
    query = grid.compute_fov if channel is WorldEdgeChannel.OPTICAL else grid.compute_propagation_fov
    grid.remove_tile(1, 0, fire_event=False)
    operation = "add"

    def change_during_acceptance(event, _source):
        if event.position == (1, 0):
            if operation == "add":
                grid.set_tile(1, 0, fire_event=False)
            elif operation == "remove":
                grid.remove_tile(1, 0, fire_event=False)
            else:
                return event.cancel(status_message="Keep the current support")
        return event

    handler = EventHandler(source_entity_uuid=uuid4(), name="Nested support change",
        trigger_conditions=[Trigger(event_type=EventType.SPATIAL_TILE_CHANGED,
            event_phase=EventPhase.EFFECT)], event_processor=change_during_acceptance)
    EventQueue.add_event_handler(handler)
    expected = [(0, 0), (1, 0), (2, 0)]
    grid.set_tile(1, 0)
    assert query((0, 0), 3) == expected
    operation = "remove"
    # Replacement commits before native cleanup rejects the old Tile that
    # the nested removal already released. Query the restored support itself:
    # the interrupted replacement does not promise refreshed neighboring routes.
    with pytest.raises(ValueError, match="Tile registry ownership is not current"):
        grid.set_tile(1, 0, walking_cost=2)
    assert grid.get_tile(1, 0) is not None
    assert query((1, 0), 0) == [(1, 0)]
    operation = "cancel"
    with pytest.raises(ValueError, match="tile change was canceled"):
        grid.set_tile(1, 0, blocks_optics=True, blocks_propagation=True)
    assert query((1, 0), 0) == [(1, 0)]
    EventQueue.remove_event_handler(handler)

    assert grid.remove_tile(1, 0)
    assert query((0, 0), 3) == [(0, 0)]
    grid.create_rectangle(0, 0, 2, 1)
    assert query((0, 0), 3) == expected
    grid.clear()
    assert grid.get_all_tiles() == {}
    grid.create_rectangle(-1, -1, 3, 3)
    grid.set_tile(3, 0)
    wall.place_on_grid((1, 1), boundary_direction=CardinalDirection.NORTH)
    assert query((0, 0), 2) == [(x, y) for x in range(-1, 2) for y in range(-1, 2)]


def test_objective_light_tracks_overlapping_sources_caps_and_replacement():
    """Map-owned light mutations publish their exact settled objective result."""
    reset_senses_state(width=2, height=1, default_light=LightLevel.DARKNESS)
    grid = get_map()
    position = (1, 0)
    tile = grid.get_tile(*position)
    bright, dim, cap = uuid4(), uuid4(), uuid4()
    assert grid.apply_light_modifier(dim, {position}, LightLevel.DIM_LIGHT) == {position}
    assert grid.apply_light_modifier(bright, {position}, LightLevel.BRIGHT_LIGHT) == {position}
    assert grid.apply_light_modifier(cap, {position}, LightLevel.DIM_LIGHT, cap=True) == {position}
    assert grid.apply_light_modifier(bright, {position}, LightLevel.DARKNESS, cap=True) == {position}
    assert tile.to_world_tile_state().resolved_light is LightLevel.DARKNESS
    # One owner may contribute both illumination and a cap; removal clears both.
    assert grid.remove_light_modifier(bright, {position}) == {position}
    assert tile.to_world_tile_state().resolved_light is LightLevel.DIM_LIGHT
    replacement = grid.set_tile(*position, default_light=LightLevel.BRIGHT_LIGHT)
    assert replacement.to_world_tile_state().resolved_light is LightLevel.DIM_LIGHT
    assert grid.remove_light_modifier(cap, {position}) == {position}
    assert replacement.to_world_tile_state().resolved_light is LightLevel.BRIGHT_LIGHT
    assert tile.to_world_tile_state().resolved_light is LightLevel.DIM_LIGHT
    assert grid.set_tile_base_light(position, LightLevel.DARKNESS)
    assert replacement.to_world_tile_state().resolved_light is LightLevel.DIM_LIGHT
    assert grid.remove_light_modifier(dim, {position}) == {position}
    assert replacement.to_world_tile_state().resolved_light is LightLevel.DARKNESS


def test_objective_light_preview_and_detached_tile_preserve_live_value():
    """A preview or detached copy cannot replace the live light inputs."""
    reset_senses_state(width=1, height=1, default_light=LightLevel.DARKNESS)
    grid = get_map()
    tile = grid.get_tile(0, 0)
    source = uuid4()
    grid.apply_light_modifier(source, {(0, 0)}, LightLevel.DIM_LIGHT)
    detached = tile.model_copy(deep=True)
    assert resolve_tile_light_level(tile, LightLevel.BRIGHT_LIGHT) is LightLevel.BRIGHT_LIGHT
    assert tile.resolved_light_level is LightLevel.DIM_LIGHT
    grid.remove_light_modifier(source, {(0, 0)})
    assert detached.resolved_light_level is LightLevel.DIM_LIGHT
    assert tile.resolved_light_level is LightLevel.DARKNESS
    tile.default_light = LightLevel.BRIGHT_LIGHT
    assert tile.resolved_light_level is LightLevel.BRIGHT_LIGHT
    assert resolve_tile_light_level(tile, LightLevel.DARKNESS) is LightLevel.DARKNESS
    assert tile.resolved_light_level is LightLevel.BRIGHT_LIGHT
    tile.default_light = LightLevel.BRIGHT_LIGHT.value
    with pytest.raises(TypeError, match='default_light must be a LightLevel'):
        tile.resolved_light_level


def test_boundary_snapshot_shift_preserves_native_routes_and_detached_halos():
    reset_senses_state(width=18, height=4)
    grid = get_map()
    walls = []
    for x, side in ((1, CardinalDirection.EAST), (4, CardinalDirection.WEST),
                    (5, CardinalDirection.NORTH), (12, CardinalDirection.WEST)):
        wall = DirectionalWall(source_entity_uuid=uuid4(), item_id="test.moving_boundary_snapshot")
        wall.place_on_grid((x, 1), boundary_direction=side)
        walls.append(wall)
    previous = grid.capture_boundary_snapshot({(2, 1), (3, 1)})
    for cells in ({(3, 1), (4, 1)}, {(3, 1), (4, 1), (3, 2)},
                  {(11, 1), (12, 1)}, {(12, 1)}):
        current = grid.capture_boundary_snapshot(cells, previous=previous)
        # Both changed and unchanged occupied halos own detached mappings.
        for sides in previous.layers.values():
            sides.clear()
        previous.layers.clear()
        previous.structures.clear()
        previous.placements.clear()
        previous.routes.clear()
        for position in ((x, y) for x in range(18) for y in range(4)):
            for direction in CardinalDirection:
                for channel in (WorldEdgeChannel.OPTICAL, WorldEdgeChannel.PROPAGATION):
                    assert grid.get_boundary_route_layers(position, direction, channel, snapshot=current) == (
                        grid.get_boundary_route_layers(position, direction, channel))
        previous = current
    # A departed halo must no longer supply old side membership to live queries.
    grid.remove_object(walls[0].uuid)
    assert grid.get_boundary_route_layers((1, 1), CardinalDirection.EAST,
        WorldEdgeChannel.OPTICAL, snapshot=current) == ((), ())
