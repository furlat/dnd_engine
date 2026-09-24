"""Paired delivery at the saved-fact, registered-image and physical-mask boundaries.

Input: authored packets and disclosed historical supports, never a live grid.
Output: registered source color, correct bank/clock, and no below-floor leakage.
"""

from dataclasses import replace
import gzip
import struct
from uuid import uuid4

import numpy as np
import pygame
from pydantic import TypeAdapter
import pytest

from dnd.core.events import WorldTileState
from dnd.core.world_edges import ElevationSurfaceKind, SlopeAxis
from dnd.types.materials import TileSurface, Material
from dnd.types.world import LightLevel, CardinalDirection
from game.animation_types import PackedSurfaceFrames, PackedSurfaceComponent, ProjectileFrameStorage, ProjectileStorage
from game.animation_data import load_animation_data
from game.player_facts import PlayerFact, SpellFact
from game.projection import Camera
from game.registered_media import registered_media_samples
from game.volume_media import SurfaceVolume, compose_volume, observed_support_heights
from tests.game.test_projectile_media import display as display, original_data as original_data, sample_data
from tests.game.test_xyz_media import wall


def support(position, height=0, kind=ElevationSurfaceKind.ORDINARY, axis=None):
    return WorldTileState(tile_uuid=uuid4(), position=position,
        surface=TileSurface(base_material=Material.STONE), name="Floor",
        blocks_optics=False, blocks_propagation=False, walking_cost=5, flying_cost=5,
        swimming_cost=5, burrowing_cost=5, elevation_steps=height, surface_kind=kind,
        slope_axis=axis, default_light=LightLevel.BRIGHT_LIGHT, resolved_light=LightLevel.BRIGHT_LIGHT)


def test_component_pivots_scale_color_and_geometry_together(original_data, tmp_path):
    data, asset, _ = sample_data(original_data, tmp_path)
    parts = []
    for i, color in enumerate(((90, 40, 20, 128), (40, 90, 20, 128))):
        xyz = np.rint((np.array([2, 4, 6]) + 16) * 65535 / 32).astype('>u2').tobytes()
        (tmp_path / f'{i}.gz').write_bytes(gzip.compress(struct.pack('<HHhh', 2, 2, -1, -1)
            + bytes(color)*4 + xyz*4 + bytes([1])*4))
        parts.append(PackedSurfaceComponent(pattern=f'{i}.gz', pivot=(1.25, 1.25), blendMode='normal'))
    packet = PackedSurfaceFrames(frameIndices=(0,), bounds=(-16., 16.), verticalScale=1.,
        positionScale=.5, referencePixelScale=.5, componentsByFacing={'E': tuple(parts)})
    data = replace(data, projectile_storage={asset.assetId: ProjectileStorage(phases={
        'impact': ProjectileFrameStorage(surfaceFrames=packet)})})
    samples = registered_media_samples(data, asset.assetId, 'impact', 0, 'E',
        scale=.5, anchor=(20, 20), rows={})
    assert [s.image.get_at((0, 0)) for s in samples] == [(90, 40, 20, 128), (40, 90, 20, 128)]
    assert all(s.destination == (19, 19) and s.image.size == (1, 1) for s in samples)
    np.testing.assert_allclose(samples[0].positions[0, 0], [1, 2, 3], atol=.001)
    # Doubling authored size scales world coordinates too; camera zoom does not.
    for zoom in (1., .5):
        enlarged = registered_media_samples(data, asset.assetId, 'impact', 0, 'E',
            scale=zoom, zoom=zoom, anchor=(20, 20), rows={})
        np.testing.assert_allclose(enlarged[0].positions[0, 0], [2, 4, 6], atol=.001)



@pytest.mark.parametrize('height', [0, 3, -2])
def test_floor_uses_disclosed_support_height_and_retains_unknown_terrain(height):
    positions = np.array([[[0, height-.2, 0]], [[0, height+.2, 0]], [[2, -8, 0]]], dtype=float)
    image = pygame.Surface((3, 1), pygame.SRCALPHA); image.fill((90, 50, 20, 255))
    volume = SurfaceVolume((0, 0), 0, 4, positions, np.ones((3, 1)), 1,
                           supports=(support((0, 0), height),))
    shown, _ = compose_volume(image, volume, Camera())
    assert [shown.get_at((i, 0)).a for i in range(3)] == [0, 255, 255]
    assert shown.get_at((0, 0)) == (0, 0, 0, 0), 'Additive RGB must be clipped too'
    assert image.get_at((0, 0)).a == 255, 'Never mutate cached source pixels'


def test_progressive_support_uses_observed_slope_not_global_floor():
    supports = tuple(support((x, 0), x, ElevationSurfaceKind.RAMP, SlopeAxis.EAST_WEST) for x in (0, 1))
    image = pygame.Surface((2, 1), pygame.SRCALPHA); image.fill('white')
    positions = np.array([[[.4, .2, 0]], [[.4, .6, 0]]])
    shown, _ = compose_volume(image, SurfaceVolume((0, 0), 0, 2, positions, np.ones((2, 1)), 1,
                                                  supports=supports), Camera())
    assert [shown.get_at((i, 0)).a for i in range(2)] == [0, 255]


def test_unknown_owner_preserves_reference_color_but_cannot_bypass_floor():
    image = pygame.Surface((1, 1), pygame.SRCALPHA); image.fill((30, 40, 50, 200))
    volume = SurfaceVolume((0, 0), 0, 2, np.zeros((1, 1, 3)), np.zeros((1, 1)), 1)
    assert compose_volume(image, volume, Camera())[0].get_at((0, 0)) == (30, 40, 50, 200)
    assert compose_volume(image, replace(volume, supports=(support((0, 0)),)), Camera())[0].get_at((0, 0)) == (0, 0, 0, 0)


def test_ramp_crest_and_unobserved_edge_do_not_extrapolate_the_opposite_slope():
    supports = tuple(support((x, 0), height, ElevationSurfaceKind.RAMP, SlopeAxis.EAST_WEST)
                     for x, height in enumerate((1, 2, 1)))
    np.testing.assert_allclose(observed_support_heights(np.array([.6, 1, 1.4]), np.zeros(3), supports),
                               [1.6, 2, 1.6])
    np.testing.assert_allclose(observed_support_heights(np.array([1.4]), np.zeros(1), supports[:2]), [2])


def test_spell_propagation_policy_changes_open_door_admission_not_geometry():
    walls = tuple(wall((0, z), CardinalDirection.EAST) for z in range(-4, 5) if z != 0)
    image = pygame.Surface((1, 1), pygame.SRCALPHA); image.fill('white')
    volume = SurfaceVolume((0, 0), 0, 4, np.array([[[2, 5, 3]]], dtype=float), np.ones((1, 1)), 1, walls)
    assert compose_volume(image, volume, Camera())[0].get_at((0, 0)).a == 255
    assert compose_volume(image, replace(volume, propagation='line_of_effect'), Camera())[0].get_at((0, 0)).a == 0


def test_attachment_translation_moves_geometry_with_the_image_without_moving_propagation_origin():
    image = pygame.Surface((1, 1), pygame.SRCALPHA); image.fill('white')
    volume = SurfaceVolume((0, 0), 0, 2, np.array([[[0., -1., 0.]]]), np.ones((1, 1)), 1,
                           supports=(support((0, 0)),))
    assert compose_volume(image, volume, Camera())[0].get_at((0, 0)).a == 0
    assert compose_volume(image, replace(volume, translation=(0, 2, 0)), Camera())[0].get_at((0, 0)).a == 255


@pytest.fixture(scope='module')
def production_data():
    return load_animation_data()


@pytest.mark.parametrize('quadrant', range(4))
def test_actual_ice_knife_late_tail_cannot_shine_through_the_floor(production_data, quadrant):
    below_seen = False
    supports = tuple(support((x, z)) for x in range(-8, 9) for z in range(-8, 9))
    asset = production_data.projectile_assets['ice.v8.ice_knife.impact']
    phase = asset.phases.impact
    assert phase is not None
    for seconds in (1.25, 2., 2.5, 35 / 12):
        frame = int(seconds * (phase.fps or asset.fps))
        for sample in registered_media_samples(production_data, 'ice.v8.ice_knife.impact', 'impact', frame,
                ('SE', 'SW', 'NW', 'NE')[quadrant], scale=1, anchor=(0, 0), rows={}):
            assert sample.positions is not None and sample.ownership is not None
            below = (sample.positions[:, :, 1]*sample.vertical_scale < -.001) & (sample.ownership != 0)
            before = pygame.surfarray.array_alpha(sample.image)
            below_seen |= bool(np.any(below & (before > 0)))
            volume = SurfaceVolume((0, 0), 0, 1, sample.positions, sample.ownership, sample.vertical_scale,
                                   supports=supports, propagation='line_of_effect')
            shown, _ = compose_volume(sample.image, volume, Camera(quadrant=quadrant))
            assert not np.any(pygame.surfarray.array_alpha(shown)[below])
            assert not np.any(pygame.surfarray.array3d(shown)[below])
    assert below_seen, 'This proof must exercise the real exported falling-tail failure'


@pytest.mark.parametrize('spell,policy', [('fireball','connected'), ('shatter','line_of_effect')])
def test_old_player_archives_keep_their_declared_spell_propagation(spell, policy):
    value = dict(kind='spell', source_entity_uuid=str(uuid4()), target_entity_uuid=None,
        behavior_id='spell.'+spell, name=spell, source_position=[0, 0], declared_target_entity_uuids=[],
        application_id=None, application_index=None)
    adapter = TypeAdapter(PlayerFact)
    fact = adapter.validate_python(value)
    assert isinstance(fact, SpellFact) and fact.area_propagation == policy
    assert adapter.validate_json(adapter.dump_json(fact)) == fact
    assert adapter.validate_python({**value, 'area_propagation': 'line_of_effect'}).area_propagation == 'line_of_effect'
