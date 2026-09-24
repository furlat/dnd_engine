"""Decorative volume edges preserve genuine holes and subjective admission."""

from dataclasses import replace
import gzip
import json
import struct
from uuid import uuid4

import numpy as np
import pygame
import pytest

from dnd.core.events import EventQueue
from dnd.spells.conjuration import FogCloud
from game.animation import view_facing
from game.animation_types import ProjectileStorage, SpatialMediaBinding, SpatialMediaLayer
from game.player_reduction import decode_player_sequence
from game.projection import Camera, TILE_WIDTH, rotate_position, project_screen
from game.registered_media import registered_media_samples
from game.spatial_field_media import field_media_commands
from tests.game.test_spatial_field_movement import rendering as rendering
from tests.game.test_spell14_native_facts import actors, saved_views


@pytest.fixture(scope="module")
def retained_field():
    caster, _ = actors()
    cast = FogCloud(source_entity_uuid=caster.uuid, end_position=(7, 4), template=False).apply()
    assert cast is not None and not cast.canceled
    payload, = saved_views((caster,), EventQueue.event_cursor()).values()
    state, heads = decode_player_sequence(payload)
    assert not heads and state.senses is not None
    effect, = state.senses.spatial_effects.values()
    return state, effect


@pytest.mark.parametrize("quadrant", range(4))
@pytest.mark.parametrize("direction", (-1, 1))
@pytest.mark.parametrize("height", (0, 2))
def test_fractional_motion_keeps_original_owners_and_only_lends_disclosed_edges(
    rendering, retained_field, tmp_path, quadrant, direction, height,
):
    state, effect = retained_field
    center = effect.area_geometry.center
    adjacent = center[0] + 1, center[1]
    state = replace(state, world=replace(state.world,
        bounds=(*center, *adjacent), width=2, height=1),
        tiles={center: state.tiles[center].model_copy(update={"elevation_steps": height})})
    # Red/blue belong to the known center. Green is decorative fringe on the
    # one-row map, but an undisclosed interior cell on the wider map. Yellow
    # borrows the other map edge only when that edge has been disclosed.
    colors = ((255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255), (255, 255, 0, 255))
    world_points = ((.1, 0.), (.1, .51 * direction), (.1, -.4 * direction), (1.8, -.4 * direction))
    origin = np.array(rotate_position((0., 0.), quadrant))
    local = [np.array(rotate_position(point, quadrant)) - origin for point in world_points]
    xyz = np.array([(point[0], 1., point[1]) for point in local])
    encoded = np.rint((xyz + 4) * 65535 / 8).astype('>u2').tobytes()
    path = tmp_path / 'moving-probes.bin.gz'
    path.write_bytes(gzip.compress(struct.pack('<HHhh', 4, 1, 0, 0)
        + b''.join(bytes(color) for color in colors) + encoded + bytes([1]) * 4))
    identity = 'test.moving.volume.owners'
    original = rendering.projectile_assets['persistent.fog_cloud.hold']
    asset = original.model_copy(update={'assetId': identity})
    facing = view_facing('E', quadrant, rendering)
    storage = ProjectileStorage.model_validate_json(json.dumps({'phases': {'impact': {'surfaceFrames': {
        'frameIndices': [0], 'bounds': [-4, 4], 'verticalScale': 1,
        'componentsByFacing': {facing: [{'pattern': str(path), 'pivot': [448, 448], 'blendMode': 'normal'}]},
    }}}}))
    data = replace(rendering, projectile_assets={**rendering.projectile_assets, identity: asset},
        projectile_storage={**rendering.projectile_storage, identity: storage})
    layer = SpatialMediaLayer(assetId=identity, composition='xyz_volume')
    binding = SpatialMediaBinding(layers=(layer,), holdStartFrame=0, holdFrames=1, fps=32,
        scale=data.rig.TILE_W / TILE_WIDTH)
    camera = Camera(quadrant=quadrant, zoom=1).with_focus(center)

    def shown(owners, *, cold=False, wider=False):
        observed = replace(state, tiles={}) if cold else state
        if wider:
            observed = replace(observed, world=replace(observed.world,
                bounds=(center[0], center[1]-1, adjacent[0], center[1]+1), height=3))
        commands = field_media_commands(observed, data, uuid4(),
            effect.area_geometry, owners, binding, layer, 0, identity, 0, camera, 1,
            translation=(0., -.3 * direction), anchor_elevation_steps=height)
        assert all(row.evidence[1] in owners and row.evidence[7] == height for row in commands)
        return {tuple(pixel) for row in commands
            for pixel in np.frombuffer(pygame.image.tobytes(row.surface, 'RGBA'), dtype=np.uint8).reshape(-1, 4)
            if pixel[3]}

    assert shown((center,)) == {colors[0], colors[1], colors[2]}
    assert shown((center,), cold=True) == {colors[0], colors[1], colors[2]}
    assert shown((center, adjacent)) == set(colors)
    assert shown((center,), wider=True) == {colors[0], colors[2]}
    assert shown((center, adjacent), wider=True) == {colors[0], colors[2], colors[3]}
    assert not shown(())
    assert tuple(state.tiles) == (center,), 'The visual fringe never invents ground cells'


@pytest.mark.parametrize("quadrant", range(4))
@pytest.mark.parametrize("height", (0, 2))
def test_full_observed_cloud_preserves_authored_round_fringe(rendering, retained_field, quadrant, height):
    state, effect = retained_field
    center = effect.area_geometry.center
    state = replace(state, tiles={p: tile.model_copy(update={"elevation_steps": height})
                                  for p, tile in state.tiles.items()})
    binding = rendering.spatial_media["spatial_effect.spell.fog_cloud"]
    layer = binding.layers[0]
    assert layer.applicationAssetId is not None
    application = rendering.projectile_assets[layer.applicationAssetId].phases.impact
    assert application is not None
    frame = application.frames - 1
    camera = Camera(quadrant=quadrant, viewport=(900, 700)).with_focus(center)
    actual = pygame.Surface(camera.viewport, pygame.SRCALPHA)
    commands = field_media_commands(state, rendering, uuid4(), effect.area_geometry, effect.positions,
        binding, layer, 0, layer.applicationAssetId, frame, camera, 1., anchor_elevation_steps=height)
    assert commands, "The final formation frame must contain the authored cloud"
    for row in commands:
        actual.blit(row.surface, row.destination, special_flags=row.blend)
    expected = pygame.Surface(camera.viewport, pygame.SRCALPHA)
    for part in registered_media_samples(rendering, layer.applicationAssetId, binding.assetPhase,
            frame, view_facing("E", quadrant, rendering), rows={}, zoom=camera.zoom,
            scale=binding.scale*TILE_WIDTH/rendering.rig.TILE_W*camera.zoom,
            anchor=project_screen(center, camera, elevation_steps=height)):
        expected.blit(part.image, part.destination, special_flags=part.blend)
    assert pygame.image.tobytes(actual, "RGBA") == pygame.image.tobytes(expected, "RGBA")
    # Removing a received owner also removes its fringe. Ownership cannot move
    # to some other visible cell merely because the original cell is missing.
    removed = next(row.evidence[1] for row in commands)
    partial = field_media_commands(state, rendering, uuid4(), effect.area_geometry,
        tuple(p for p in effect.positions if p != removed), binding, layer, 0,
        layer.applicationAssetId, frame, camera, 1., anchor_elevation_steps=height)
    remaining = pygame.Surface(camera.viewport, pygame.SRCALPHA)
    reference = pygame.Surface(camera.viewport, pygame.SRCALPHA)
    for row in partial:
        remaining.blit(row.surface, row.destination, special_flags=row.blend)
    for row in commands:
        if row.evidence[1] != removed:
            reference.blit(row.surface, row.destination, special_flags=row.blend)
    assert pygame.image.tobytes(remaining, "RGBA") == pygame.image.tobytes(reference, "RGBA")
    assert pygame.image.tobytes(remaining, "RGBA") != pygame.image.tobytes(actual, "RGBA")
