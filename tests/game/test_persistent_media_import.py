"""Delivered camera registration and phase windows survive storage import."""

from dataclasses import replace
import gzip
import json
import struct
from zipfile import ZipFile

import numpy as np
import pygame
import pytest

from devtools.import_persistent_spells import import_protection, import_terrain, import_volume
from game.animation_data import load_animation_data
from game.animation import view_facing
from game.animation_types import AuthoredProjectileAsset, ProjectileStorage
from game.registered_media import registered_media_samples


@pytest.fixture(scope='module')
def rendering():
    pygame.init()
    pygame.display.set_mode((1, 1))
    yield load_animation_data()
    pygame.quit()


def test_imported_source_pixels_keep_camera_identity_registration_and_phase(rendering, tmp_path):
    source, repo = tmp_path / 'source', tmp_path / 'repo'
    source.mkdir()
    original = source / 'original'
    (original / 'actors').mkdir(parents=True)
    (original / 'actors.json').write_text(json.dumps({key: {'palette': [[10, 20, 30]]}
        for key in ('grease', 'spike_growth')}))
    pixel = pygame.Surface((2, 2), pygame.SRCALPHA)
    for key in ('grease', 'spike_growth'):
        pygame.image.save(pixel, original / 'actors' / f'{key}-hands.png')
    # Intentionally shuffled names: the numerical bases own camera mapping.
    bases = (((64, 32), (-64, 32)), ((-64, 32), (-64, -32)),
             ((-64, -32), (64, -32)), ((64, -32), (64, 32)))
    colors = ((255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255), (255, 255, 0, 255))
    views = {}
    for index, (basis, color) in enumerate(zip(bases, colors)):
        pixel.fill(color)
        filename = f'camera-{index}.png'
        pygame.image.save(pixel, source / filename)
        views[f'label-{3-index}'] = {'pivot': [128., 128.], 'fps': 144,
            'groundBasis': dict(zip(('X', 'Z'), basis)), 'pages': [filename],
            'rects': [None, {'page': 0, 'source': [0, 0, 2, 2], 'offset': [-2, -3]}, None]}
    (source / 'manifest.json').write_text(json.dumps({'originalPackage': str(original),
        'components': {'grease_fixture': {'views': views, 'phases': {'apply': [0, 1], 'hold': [1, 2], 'clear': [2, 3]}}}}))
    folder = repo / 'game/data/persistent_spells'
    folder.mkdir(parents=True)
    authored = folder / 'spell-studio-drafts.json'
    authored.write_text('Authored behavior must remain independent.\n')
    import_terrain(source, repo=repo)
    assets = {row['assetId']: AuthoredProjectileAsset.model_validate_json(json.dumps(row))
              for row in json.loads((folder / 'projectile-assets.json').read_text())}
    storage = {key: ProjectileStorage.model_validate_json(json.dumps(value))
               for key, value in json.loads((folder / 'bindings.json').read_text())['projectileStorage'].items()}
    data = replace(rendering, media_root=repo, projectile_assets=assets, projectile_storage=storage)
    for quadrant, color in enumerate(colors):
        facing = view_facing('E', quadrant, data)
        result, = registered_media_samples(data, 'persistent.grease_fixture.hold', 'impact', 0,
            facing, scale=1, anchor=(40, 50), rows={})
        assert result.destination == (38, 47)
        assert result.image.get_at((0, 0)) == color
        assert not registered_media_samples(data, 'persistent.grease_fixture.clear', 'impact', 0,
            facing, scale=1, anchor=(40, 50), rows={})
    import_terrain(source, repo=repo)
    assert authored.read_text() == 'Authored behavior must remain independent.\n'


def test_padded_actor_export_keeps_body_registration_and_event_clear(rendering, tmp_path):
    source, repo = tmp_path / 'source', tmp_path / 'repo'
    source.mkdir()
    pixels = pygame.Surface((4, 2), pygame.SRCALPHA)
    pixels.fill((50, 100, 150, 255), (0, 0, 2, 2))
    pixels.fill((90, 140, 190, 255), (2, 0, 2, 2))
    pygame.image.save(pixels, source / 'shell.png')
    mask = pygame.Surface((2, 2), pygame.SRCALPHA)
    mask.fill((255, 255, 255, 128))
    pygame.image.save(mask, source / 'clear.png')
    bases = (((64, 32), (-64, 32)), ((-64, 32), (-64, -32)),
             ((-64, -32), (64, -32)), ((64, -32), (64, 32)))
    bank = {'pages': ['shell.png'], 'frames': [
        {'page': 0, 'source': [x, 0, 2, 2], 'offset': [150, 170]} for x in (0, 2)]}
    document = {'canvasSize': [320, 320], 'pivot': [160, 197], 'palette': ['326496'],
        'fps': 144, 'apply': [0, 1], 'hold': [1, 2],
        'clear': {'frames': 2, 'sharedAcrossCamerasAndLayers': True, 'mask': {
            'pages': ['clear.png'], 'frames': [
                {'page': 0, 'source': [0, 0, 2, 2], 'offset': [150, 170]}, None]}},
        'views': {str(index): {'camera': {'basisX': [v * .5 for v in x],
            'basisZ': [v * .5 for v in z]}, 'back': bank, 'front': bank}
            for index, (x, z) in enumerate(bases)}}
    manifest = source / 'manifest.json'
    manifest.write_text(json.dumps(document))
    import_protection(manifest, name='fixture', repo=repo)
    folder = repo / 'game/data/persistent_spells'
    assets = {row['assetId']: AuthoredProjectileAsset.model_validate_json(json.dumps(row))
              for row in json.loads((folder / 'projectile-assets.json').read_text())}
    storage = {key: ProjectileStorage.model_validate_json(json.dumps(value))
               for key, value in json.loads((folder / 'bindings.json').read_text())['projectileStorage'].items()}
    data = replace(rendering, media_root=repo, projectile_assets=assets, projectile_storage=storage)
    for quadrant in range(4):
        for side in ('back', 'front'):
            for phase, color in (('apply', (50, 100, 150, 255)), ('hold', (90, 140, 190, 255)),
                                 ('clear_mask', (255, 255, 255, 128))):
                result, = registered_media_samples(data, f'persistent.fixture.{side}.{phase}',
                    'impact', 0, view_facing('E', quadrant, data), scale=1, anchor=(100, 100), rows={})
                assert result.destination == (90, 73)
                assert result.image.get_at((0, 0)) == color
            assert not registered_media_samples(data, f'persistent.fixture.{side}.clear_mask',
                'impact', 1, view_facing('E', quadrant, data), scale=1, anchor=(100, 100), rows={})


@pytest.fixture
def volume_source(rendering, tmp_path):
    source = tmp_path / 'volume'
    source.mkdir()
    bases = (((64, 32), (-64, 32)), ((-64, 32), (-64, -32)),
             ((-64, -32), (64, -32)), ((64, -32), (64, 32)))
    colors = ((255, 40, 20, 255), (40, 255, 20, 255), (40, 20, 255, 255), (255, 255, 20, 255))
    views = {}
    coordinate = pygame.Surface((4, 2), pygame.SRCALPHA)
    # A=0 encodes the low Z byte, not transparency. X is approximately +1, Z=-4.
    coordinate.fill((159, 255, 0, 0), (0, 0, 2, 2))
    coordinate.fill((128, 0, 255, 255), (2, 0, 2, 2))
    pygame.image.save(coordinate, source / 'position.png')
    for index, ((x, z), color) in enumerate(zip(bases, colors)):
        image = pygame.Surface((4, 2), pygame.SRCALPHA)
        image.fill(color, (0, 0, 2, 2))
        image.fill(tuple(255-channel for channel in color[:3]) + (255,), (2, 0, 2, 2))
        pygame.image.save(image, source / f'color-{index}.png')
        rects = [None, {'page': 0, 'source': [0, 0, 2, 2], 'offset': [-2, -3]},
                 {'page': 0, 'source': [2, 0, 2, 2], 'offset': [3, -4]}, None]
        views[str(3-index)] = {'camera': {'basisX': x, 'basisZ': z},
            'color': {'pages': [f'color-{index}.png'], 'rects': rects},
            'position': {'pages': ['position.png'], 'rects': rects}}
    manifest = source / 'manifest.json'
    manifest.write_text(json.dumps({'complete': True, 'spell': 'fixture', 'views': views, 'fps': 144,
        'canvasSize': [896, 896], 'pivot': [448, 448], 'palette': ['ff2814'],
        'apply': [0, 2], 'hold': [2, 4],
        'positionEncoding': {'format': 'RGBA8_RAW_XZ_UNORM16', 'min': -4, 'max': 4}}))
    return manifest, colors


@pytest.mark.parametrize('fps', (32, 144))
def test_volume_import_preserves_raw_coordinate_alpha_byte_and_camera_basis(rendering, tmp_path, volume_source, fps):
    manifest, colors = volume_source
    document = json.loads(manifest.read_text())
    document['fps'] = fps
    manifest.write_text(json.dumps(document))
    repo = tmp_path / 'repo'
    import_volume(manifest, repo=repo)
    folder = repo / 'game/data/persistent_spells'
    assets = {row['assetId']: AuthoredProjectileAsset.model_validate_json(json.dumps(row))
              for row in json.loads((folder / 'projectile-assets.json').read_text())}
    storage = {key: ProjectileStorage.model_validate_json(json.dumps(value))
               for key, value in json.loads((folder / 'bindings.json').read_text())['projectileStorage'].items()}
    data = replace(rendering, media_root=repo, projectile_assets=assets, projectile_storage=storage)
    for quadrant, color in enumerate(colors):
        result, = registered_media_samples(data, 'persistent.fixture.apply', 'impact', 1,
            view_facing('E', quadrant, data), scale=1, anchor=(100, 100), rows={})
        assert result.destination == (98, 97)
        assert result.image.get_at((0, 0)) == color
        assert result.footpoints is not None
        assert result.footpoints[0, 0].tolist() == pytest.approx([-4 + 40959 * 8 / 65535, -4])
        held, = registered_media_samples(data, 'persistent.fixture.hold', 'impact', 0,
            view_facing('E', quadrant, data), scale=1, anchor=(100, 100), rows={})
        assert held.destination == (103, 96)
        assert held.image.get_at((0, 0)) == tuple(255-channel for channel in color[:3]) + (255,)
        assert held.footpoints is not None
        assert held.footpoints[0, 0].tolist() == pytest.approx([-4 + 32768 * 8 / 65535, 4], abs=3e-7)
        for phase, empty in (('apply', 0), ('hold', 1)):
            window = assets[f'persistent.fixture.{phase}'].phases.impact
            assert window is not None and window.frames == 2
            assert window.fps == assets[f'persistent.fixture.{phase}'].fps == fps
            assert not registered_media_samples(data, f'persistent.fixture.{phase}', 'impact', empty,
                view_facing('E', quadrant, data), scale=1, anchor=(100, 100), rows={})


@pytest.mark.parametrize('partial', ('marked_incomplete', 'unpublished', 'q0_only', 'short_view',
                                   'empty_window', 'unpaired_coordinates'))
def test_volume_import_rejects_incomplete_delivery_before_writing(tmp_path, volume_source, partial):
    manifest, _ = volume_source
    document = json.loads(manifest.read_text())
    if partial == 'marked_incomplete':
        document['complete'] = False
    elif partial == 'unpublished':
        del document['complete']
    elif partial == 'q0_only':
        document['views'] = {'3': document['views']['3']}
    elif partial == 'short_view':
        for stream in ('color', 'position'):
            document['views']['0'][stream]['rects'].pop()
    elif partial == 'empty_window':
        document['hold'] = [4, 4]
    else:
        document['views']['0']['position']['rects'][1]['offset'][0] += 1
    manifest.write_text(json.dumps(document))
    repo = tmp_path / 'repo'
    with pytest.raises(ValueError):
        import_volume(manifest, repo=repo)
    assert not repo.exists()


@pytest.fixture
def surface_volume_source(volume_source):
    original, colors = volume_source
    document = json.loads(original.read_text())
    views = {}
    for label, old_view in document['views'].items():
        index = 3 - int(label)
        relative = f'camera-{label}.zip'
        # Native sample indices need not coincide with local phase indices.
        with ZipFile(original.parent / relative, 'w') as archive:
            for frame, offset, color, xyz, owner in (
                (7, (0, 0), (0, 0, 0, 0), (0, 0, 0), 0),
                (11, (-2, -3), colors[index], (32768, 40959, 0), 1),
                (13, (3, -4), (30, 60, 90, 128), (65535, 49151, 32768), 1),
                (17, (0, 0), (0, 0, 0, 0), (0, 0, 0), 0),
            ):
                payload = (struct.pack('<HHhh', 2, 2, *offset) + bytes(color) * 4
                    + struct.pack('>HHH', *xyz) * 4 + bytes([owner]) * 4)
                archive.writestr(f'{frame:03d}.bin.gz', gzip.compress(payload))
        views[label] = {key: document[key] for key in
            ('complete', 'spell', 'fps', 'apply', 'hold', 'canvasSize', 'pivot')}
        views[label].update(cameraProjection=old_view['camera'], surfaceFrames={
            'archive': {'file': relative, 'memberPattern': '{frame:03d}.bin.gz'},
            'frameIndices': [7, 11, 13, 17], 'bounds': [-4, 4],
            'verticalScale': 1.224744871391589, 'positionScale': 1,
            'referencePixelScale': 1, 'coordinateBasis': 'camera_local_xyz',
            'blendModes': ['normal']})
    path = original.parent / 'surface-manifest.json'
    path.write_text(json.dumps({'complete': True, 'spell': 'fixture', 'fps': 144,
        'sourceManifest': original.name, 'views': views}))
    return path, colors


@pytest.mark.parametrize('fps', (32, 144))
def test_surface_volume_import_preserves_registered_rgba_xyz_and_phase_indices(
    rendering, tmp_path, surface_volume_source, fps,
):
    manifest, colors = surface_volume_source
    delivery = json.loads(manifest.read_text())
    original = manifest.parent / delivery['sourceManifest']
    document = json.loads(original.read_text())
    delivery['fps'] = document['fps'] = fps
    for view in delivery['views'].values():
        view['fps'] = fps
    manifest.write_text(json.dumps(delivery))
    original.write_text(json.dumps(document))
    repo = tmp_path / 'repo'
    folder = repo / 'game/data/persistent_spells'
    folder.mkdir(parents=True)
    authored = folder / 'spell-studio-drafts.json'
    authored.write_text('Keep independently authored behavior unchanged.\n')
    (folder / 'bindings.json').write_text(json.dumps({'resources': {'unrelated': 'retained'},
        'projectileStorage': {'unrelated': {'retained': True}}}))
    import_volume(manifest, repo=repo)
    assert authored.read_text() == 'Keep independently authored behavior unchanged.\n'
    bindings = json.loads((folder / 'bindings.json').read_text())
    assert bindings['resources'] == {'unrelated': 'retained'}
    assert bindings['projectileStorage'].pop('unrelated') == {'retained': True}
    assets = {row['assetId']: AuthoredProjectileAsset.model_validate_json(json.dumps(row))
              for row in json.loads((folder / 'projectile-assets.json').read_text())}
    storage = {key: ProjectileStorage.model_validate_json(json.dumps(value))
               for key, value in bindings['projectileStorage'].items()}
    data = replace(rendering, media_root=repo, projectile_assets=assets, projectile_storage=storage)
    for quadrant, color in enumerate(colors):
        facing = view_facing('E', quadrant, data)
        for phase, frame, expected_color, destination, coordinates in (
            ('apply', 1, color, (98, 97), (-4+32768*8/65535, -4+40959*8/65535, -4)),
            ('hold', 0, (30, 60, 90, 128), (103, 96), (4, -4+49151*8/65535, -4+32768*8/65535)),
        ):
            identity = f'persistent.fixture.{phase}'
            result, = registered_media_samples(data, identity, 'impact', frame, facing,
                scale=1, anchor=(100, 100), rows={})
            assert result.destination == destination
            assert pygame.image.tobytes(result.image, 'RGBA') == bytes(expected_color) * 4
            assert result.positions is not None and result.ownership is not None
            np.testing.assert_allclose(result.positions, np.tile(coordinates, (2, 2, 1)), atol=3e-7)
            np.testing.assert_array_equal(result.ownership, np.ones((2, 2)))
            assert result.vertical_scale == 1.224744871391589
            assert result.footpoints is None
            window = assets[identity].phases.impact
            assert window is not None and window.frames == 2 and window.fps == fps
            assert window.loop == (phase == 'hold')
        for phase, frame in (('apply', 0), ('hold', 1)):
            result, = registered_media_samples(data, f'persistent.fixture.{phase}', 'impact', frame,
                facing, scale=1, anchor=(100, 100), rows={})
            assert not pygame.surfarray.array_alpha(result.image).any()
    installed = tuple((repo / 'game/assets').rglob('*.*'))
    assert len(installed) == 4, 'Install the paired archives only, not retired color/XZ pages'
    for path in installed:
        assert path.read_bytes() == (manifest.parent / path.name).read_bytes()


@pytest.mark.parametrize('partial', ('incomplete', 'q0_only', 'short_view', 'different_clock',
                                   'different_pivot', 'different_encoding'))
def test_surface_volume_import_rejects_mismatched_delivery_before_writing(
    tmp_path, surface_volume_source, partial,
):
    manifest, _ = surface_volume_source
    document = json.loads(manifest.read_text())
    view = document['views']['0']
    if partial == 'incomplete':
        view['complete'] = False
    elif partial == 'q0_only':
        document['views'] = {'0': view}
    elif partial == 'short_view':
        view['surfaceFrames']['frameIndices'].pop()
    elif partial == 'different_clock':
        view['fps'] = 32
    elif partial == 'different_pivot':
        view['pivot'][0] += 1
    else:
        view['surfaceFrames']['bounds'] = [-8, 8]
    manifest.write_text(json.dumps(document))
    repo = tmp_path / 'repo'
    with pytest.raises(ValueError):
        import_volume(manifest, repo=repo)
    assert not repo.exists()
