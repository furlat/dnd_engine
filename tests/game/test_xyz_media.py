"""Color/XYZ packets and actual spatial clipping, independent of asset artwork."""
from dataclasses import replace
import gzip
import struct
from uuid import uuid4

import numpy as np
import pygame
import pytest

from dnd.types.world import CardinalDirection
from dnd.types.world_placement import WorldObjectPlacement, WorldPlacementKind
from game.animation_types import PackedSurfaceFrames, ProjectileFrameStorage, ProjectileStorage
from game.area_media import AreaSolid, BoundarySprite
from game.draw_commands import DrawCommand
from game.fixture_depth import partition_world_depth, split_world_depth
from game.projectile_media import ProjectileFrameCache, frame_cache_usage, projectile_frame_layers
from game.projection import Camera, inverse_rotate_position, project_screen, rotate_position
from game.volume_media import ExcludedSphere, SurfaceVolume, compose_volume
from tests.game.test_projectile_media import display as display, original_data as original_data, sample_data


def wall(position, direction, top=2):
    return WorldObjectPlacement(object_uuid=uuid4(), tile_uuid=uuid4(), position=position,
        kind=WorldPlacementKind.BOUNDARY, occupies_bands=True, boundary_direction=direction,
        base_height_steps=0, top_height_steps=top)


def color_result(points, *, quadrant=0, center=(0, 0), walls=(), solids=(), spheres=(), owners=None):
    origin = rotate_position((0., 0.), quadrant)
    local = []
    for x, height, z in points:
        rotated = rotate_position((x-center[0], z-center[1]), quadrant)
        local.append((rotated[0]-origin[0], height, rotated[1]-origin[1]))
    positions = np.array(local, dtype=np.float32).reshape(len(points), 1, 3)
    image = pygame.Surface((len(points), 1), pygame.SRCALPHA)
    image.fill((100, 50, 25, 255))
    volume = SurfaceVolume(center, 0, 4, positions,
        np.array(owners if owners is not None else [1]*len(points), dtype=np.uint8).reshape(-1, 1),
        1, walls, spheres, solids)
    return compose_volume(image, volume, Camera(quadrant=quadrant))[0]


@pytest.mark.parametrize('quadrant', range(4))
def test_sphere_excludes_world_samples_and_unresolved_coverage_in_every_camera(quadrant):
    image = color_result([(8, 0, 7), (8, 3, 7), (11, 0, 7), (8, 0, 7)],
        quadrant=quadrant, center=(5, 7), spheres=(ExcludedSphere('globe', (8, 7), 0, 2, 1),),
        owners=[1, 2, 3, 0])
    assert [image.get_at((x, 0)).a for x in range(4)] == [0, 255, 255, 0]
    assert image.get_at((0, 0)) == (0, 0, 0, 0)  # additive must also disappear


@pytest.mark.parametrize('opening', [False, True])
def test_connected_doorway_admits_lateral_spread_without_a_center_ray(opening):
    barriers = tuple(wall((0, z), CardinalDirection.EAST) for z in range(-4, 5) if not opening or z != 0)
    image = color_result([(2, 5, 2)], walls=barriers)  # high sample avoids camera occlusion
    assert bool(image.get_at((0, 0)).a) == opening


def test_solid_cell_stops_spread_in_corridor_without_cell_stenciling():
    barriers = tuple(wall((x, 0), direction) for x in range(-5, 6)
        for direction in (CardinalDirection.NORTH, CardinalDirection.SOUTH))
    image = color_result([(2, 5, 0)], walls=barriers, solids=(AreaSolid((1, 0), 0),))
    assert image.get_at((0, 0)).a == 0


def test_camera_wall_occlusion_uses_sample_height_not_ground_silhouette():
    image = color_result([(-.1, .2, -.3), (-.1, 3, -.3)],
        walls=(wall((0, 0), CardinalDirection.EAST),))
    # Both lie on the reachable side; only the low sample is hidden by the wall.
    assert [image.get_at((x, 0)).a for x in range(2)] == [0, 255]



@pytest.mark.parametrize("quadrant", range(4))
@pytest.mark.parametrize("sample,covered", [
    ((.25, 2., 0.), True),       # ray passes above native top=2, through the art cap
    ((.5, 2.25, .25), False),   # contact with that cap
    ((.75, 2.5, .5), False),    # same screen pixel, on the camera side
    ((.25, 3., 0.), False),     # above the registered art itself
])
def test_registered_cap_owns_only_far_side_samples(quadrant, sample, covered):
    center = inverse_rotate_position((32., 32.), quadrant)
    direction = (CardinalDirection.EAST, CardinalDirection.SOUTH,
                 CardinalDirection.WEST, CardinalDirection.NORTH)[quadrant]
    boundary = wall(tuple(round(value) for value in center), direction)
    camera = Camera(quadrant=quadrant, zoom=1).with_focus(center)
    cap_point = inverse_rotate_position((32.5, 32.25), quadrant)
    cap_at = tuple(round(value) for value in project_screen(cap_point, camera, elevation_steps=2.25))
    art = pygame.Surface((1, 1), pygame.SRCALPHA); art.fill((20, 60, 100, 255))
    picture = BoundarySprite((boundary,), art, cap_at, (100, 2064., 0., 0, ('wall',)))
    point = inverse_rotate_position((32 + sample[0], 32 + sample[2]), quadrant)
    destination = tuple(round(value) for value in project_screen(point, camera, elevation_steps=sample[1]))
    image = pygame.Surface((1, 1), pygame.SRCALPHA); image.fill((100, 50, 25, 255))
    volume = SurfaceVolume(center, 0, 4, np.array([[sample]], dtype=np.float32),
                           np.ones((1, 1), dtype=np.uint8), 1)
    result, _ = compose_volume(image, volume, camera,
                               destination=destination, visual_boundaries=(picture,))
    assert bool(result.get_at((0, 0)).a) is not covered
    if covered:
        assert result.get_at((0, 0)) == (0, 0, 0, 0), "Additive RGB must be hidden too"
    assert boundary.top_height_steps == 2, "Art registration cannot raise the native wall"


@pytest.mark.parametrize("alpha", (0, 128, 255))
def test_registered_door_holes_and_edges_preserve_normal_compositing(alpha):
    image = pygame.Surface((1, 1), pygame.SRCALPHA); image.fill((100, 50, 25, 255))
    door = pygame.Surface((1, 1), pygame.SRCALPHA); door.fill((20, 60, 100, alpha))
    key = (100, 16., 0., 0, ('door',))
    boundary = BoundarySprite((wall((0, 0), CardinalDirection.EAST),), door, (0, 0), key)
    volume = SurfaceVolume((0, 0), 0, 4, np.array([[[.25, 2., 0.]]]), np.ones((1, 1)), 1)
    result, depth = compose_volume(image, volume, Camera(), visual_boundaries=(boundary,))
    effect = DrawCommand(key, result, (0, 0), 0, (), world_depth=depth)
    leaf = DrawCommand(key, door, (0, 0), 0, ())
    actual = pygame.Surface((1, 1)); actual.fill((0, 0, 0))
    for row in sorted(split_world_depth([effect, leaf]), key=lambda row: row.key):
        actual.blit(row.surface, row.destination)
    expected = pygame.Surface((1, 1)); expected.fill((0, 0, 0))
    expected.blit(image, (0, 0)); expected.blit(door, (0, 0))
    assert actual.get_at((0, 0)) == expected.get_at((0, 0))


def test_boundary_corner_segments_are_finite_and_openings_are_not_inferred_solid():
    art = pygame.Surface((3, 1), pygame.SRCALPHA); art.fill((20, 60, 100, 255))
    corner = BoundarySprite((wall((0, 0), CardinalDirection.EAST),
                             wall((0, 0), CardinalDirection.NORTH)), art, (0, 0),
                            (100, 16., 0., 0, ('corner',)))
    image = pygame.Surface((3, 1), pygame.SRCALPHA); image.fill((100, 50, 25, 255))
    # Behind the east arm, behind the north arm, outside both finite segments.
    xyz = np.array([[[.25, 2., 0.]], [[0., 2., .25]], [[.25, 2., 2.]]])
    result, _ = compose_volume(image, SurfaceVolume((0, 0), 0, 4, xyz,
        np.ones((3, 1)), 1), Camera(), visual_boundaries=(corner,))
    assert [result.get_at((i, 0)).a for i in range(3)] == [0, 0, 255]


@pytest.mark.parametrize("neighbor_row,hidden", ((1, True), (2, False)))
def test_neighboring_cap_sprites_share_only_connected_edge_coverage(neighbor_row, hidden):
    art = pygame.Surface((1, 1), pygame.SRCALPHA); art.fill((20, 60, 100, 255))
    key = (100, 16., 0., 0, ('wall',))
    boundary = BoundarySprite((wall((0, 0), CardinalDirection.EAST),), art, (0, 0), key)
    neighbor = BoundarySprite((wall((0, neighbor_row), CardinalDirection.EAST),), art, (1, 0), key)
    image = pygame.Surface((1, 1), pygame.SRCALPHA); image.fill((100, 50, 25, 255))
    # This cap pixel is drawn by one sprite, but its ray crosses the adjoining
    # edge segment at z=.55. An actual gap must not inherit that segment.
    volume = SurfaceVolume((0, 0), 0, 4, np.array([[[.25, 2., .3]]]), np.ones((1, 1)), 1)
    result, _ = compose_volume(image, volume, Camera(), visual_boundaries=(boundary, neighbor))
    assert bool(result.get_at((0, 0)).a) is not hidden

def test_depth_partition_does_not_duplicate_additive_rgb():
    surface = pygame.Surface((2, 1), pygame.SRCALPHA)
    surface.fill((40, 20, 10, 255))
    command = DrawCommand((1, 0., 0., 0, ('test',)), surface, (0, 0), pygame.BLEND_RGB_ADD, ())
    pieces = partition_world_depth(command, np.array([[0.], [2.]]), [1.])
    composed = pygame.Surface((2, 1)); composed.fill((0, 0, 0))
    for piece in pieces:
        composed.blit(piece.surface, piece.destination, special_flags=piece.blend)
    assert [composed.get_at((x, 0))[:3] for x in range(2)] == [(40, 20, 10)]*2


@pytest.mark.parametrize("smoke_depth,fire_depth", [((-2, 2), (-1, 1)), ((-1, 1), (-2, 2))])
@pytest.mark.parametrize("with_peer", [False, True])
def test_authored_material_order_survives_moving_depths(smoke_depth, fire_depth, with_peer):
    """Smoke/fire may move independently without blinking between blend orders."""
    smoke = pygame.Surface((2, 1), pygame.SRCALPHA)
    smoke.fill((40, 30, 20, 192))
    fire = pygame.Surface((2, 1), pygame.SRCALPHA)
    fire.fill((100, 80, 10, 255))
    layers = [DrawCommand((1, 0., 0., 0, ('z-smoke' if i == 0 else 'a-fire',)), surface, (0, 0), blend, (),
        world_depth=np.array(depth, dtype=float).reshape(2, 1), world_depth_group=('effect',))
        for i, (surface, blend, depth) in enumerate(((smoke, 0, smoke_depth),
                                                     (fire, pygame.BLEND_RGB_ADD, fire_depth)))]
    peer = pygame.Surface((2, 1), pygame.SRCALPHA)
    peer.fill((10, 60, 120, 255))
    commands = layers + ([DrawCommand((1, 0., 0., 0, ('actor',)), peer, (0, 0), 0, ())] if with_peer else [])
    actual = pygame.Surface((2, 1)); actual.fill((15, 15, 15))
    for piece in sorted(split_world_depth(commands), key=lambda c: c.key):
        actual.blit(piece.surface, piece.destination, special_flags=piece.blend)
    expected = pygame.Surface((2, 1)); expected.fill((15, 15, 15))
    if with_peer:
        expected.blit(peer, (0, 0))
    for layer in layers:
        expected.blit(layer.surface, (0, 0), special_flags=layer.blend)
    if with_peer:
        expected.set_at((0, 0), peer.get_at((0, 0)))
    np.testing.assert_array_equal(pygame.surfarray.array3d(actual), pygame.surfarray.array3d(expected))


def test_cropped_material_layers_share_external_depth_cuts():
    """A peer overlapping only the smoke must not reorder its cropped fire layer."""
    smoke = pygame.Surface((3, 1), pygame.SRCALPHA); smoke.fill((30, 20, 10, 192))
    fire = pygame.Surface((2, 1), pygame.SRCALPHA); fire.fill((100, 60, 10, 255))
    actor = pygame.Surface((1, 1), pygame.SRCALPHA); actor.fill((10, 60, 120, 255))
    layers = [DrawCommand((1, 0., 0., 0, (str(i),)), surface, position, blend, (),
        world_depth=np.full((surface.width, 1), depth), world_depth_group=('effect',))
        for i, (surface, position, blend, depth) in enumerate((
            (smoke, (0, 0), 0, 2.), (fire, (1, 0), pygame.BLEND_RGB_ADD, 3.)))]
    peer = DrawCommand((1, 0., 0., 0, ('actor',)), actor, (0, 0), 0, ())
    actual = pygame.Surface((3, 1)); actual.fill((15, 15, 15))
    for piece in sorted(split_world_depth([*layers, peer]), key=lambda c: c.key):
        actual.blit(piece.surface, piece.destination, special_flags=piece.blend)
    expected = pygame.Surface((3, 1)); expected.fill((15, 15, 15))
    for command in (peer, *layers):
        expected.blit(command.surface, command.destination, special_flags=command.blend)
    np.testing.assert_array_equal(pygame.surfarray.array3d(actual), pygame.surfarray.array3d(expected))


def test_paired_packet_keeps_color_coordinates_and_byte_bound(original_data, tmp_path):
    data, asset, visual = sample_data(original_data, tmp_path)
    raw = np.array([[[0, 32768, 65535]]]*4, dtype='>u2').tobytes()
    packet = struct.pack('<HHhh', 2, 2, -1, -1)
    for color in ((100, 80, 60, 128), (200, 100, 20, 128)):
        packet += bytes(color)*4 + raw + bytes([0, 1, 2, 3])
    (tmp_path/'0.bin.gz').write_bytes(gzip.compress(packet))
    (tmp_path/'1.bin.gz').write_bytes(gzip.compress(packet))
    storage = ProjectileStorage(phases={'impact': ProjectileFrameStorage(surfaceFrames=PackedSurfaceFrames(
        pattern='{frame}.bin.gz', frameIndices=tuple(range(asset.phases.impact.frames)),
        bounds=(-16., 16.), verticalScale=1.224744871391589, blendModes=('normal', 'add')))})
    data = replace(data, projectile_storage={asset.assetId: storage})
    cache = ProjectileFrameCache(limit_bytes=88)
    smoke, fire = projectile_frame_layers(data, asset, 'impact', 0, 'E', visual, {}, cache=cache)
    assert smoke.image.get_at((0, 0)) == (100, 80, 60, 128)
    assert fire.image.get_at((0, 0))[:3] == (100, 50, 10)
    assert smoke.positions is not None and smoke.positions.coordinates[0, 0].tolist() == [0, 32768, 65535]
    assert smoke.positions.ownership[:, 0].tolist() == [0, 1]
    assert frame_cache_usage(cache).decoded_bytes == 88
    cache.limit_bytes = 44
    # Eviction changes storage residency, never the returned paired sample.
    again = projectile_frame_layers(data, asset, 'impact', 1, 'W', visual, {}, cache=cache)
    assert pygame.image.tobytes(again[1].image, 'RGBA') == pygame.image.tobytes(fire.image, 'RGBA')
    assert frame_cache_usage(cache).decoded_bytes <= 44
