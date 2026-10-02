"""Section preparation preserves real samples without replaying fixture breaks."""

import hashlib
import json

from PIL import Image
import pytest

from devtools.import_solid_wall_media import import_solid_sections, normalize_solid_sections


def solid_source(folder):
    folder.mkdir()
    pixels = Image.new('RGBA', (224, 1))
    pixels.putdata([(i, 49, 71, 100) for i in range(224)])
    pixels.save(folder / 'page.png')
    page = {'path': 'page.png', 'sha256': hashlib.sha256((folder / 'page.png').read_bytes()).hexdigest()}
    banks = {}
    for material in ('stone', 'ice'):
        for variant in range(3):
            for direction in range(4):
                for camera in range(4):
                    for side in ('back', 'front'):
                        banks[f'{material}-v{variant}-lifecycle/d{direction}/q{camera}/{side}'] = {
                            'pages': [page], 'frames': [{'page': 0, 'source': [i, 0, 1, 1], 'offset': [260, 270]}
                                for i in range(224)], 'times': [(i+1)/32 for i in range(224)],
                            'registration': {'variant': variant, 'viewport': [512, 512], 'ortho': 12,
                                'worldHeadingRadians': direction*3.141592653589793/2}}
    manifest = {'fps': 32, 'canvas': [512, 512], 'nativeCell': 2.121320344,
        'pivot': [256, 311.425626], 'ortho': 12, 'banks': banks}
    (folder / 'media.json').write_text(json.dumps(manifest))
    return manifest


def test_independent_section_phases_retain_one_intact_pose_and_witnessed_break(tmp_path):
    source = tmp_path / 'source'
    solid_source(source)
    normalized = tmp_path / 'normalized'
    assert len(normalize_solid_sections(source, normalized)) == 24
    installed = tmp_path / 'installed'
    identities = import_solid_sections(normalized, installed)
    assert len(identities) == 144
    folder = installed / 'game/data/wall_media'
    assets = {a['assetId']: a for a in json.loads((folder / 'projectile-assets.json').read_text())}
    storage = json.loads((folder / 'bindings.json').read_text())['projectileStorage']
    assert not any('removal' in identity for identity in identities)
    for phase, count, first, loop in [('application', 32, 0, False), ('hold', 1, 47, True),
                                      ('destruction', 141, 83, False)]:
        identity = f'wall.ice_v2_d3.{phase}.front'
        assert assets[identity]['phases']['impact']['frames'] == count
        assert assets[identity]['phases']['impact']['loop'] is loop
        views = storage[identity]['phases']['impact']['layers'][0]['partsByFacing']
        for facing in ('E', 'S', 'W', 'N'):
            frames = views[facing]
            assert len(frames) == count
            for i in (0, count-1):
                part = frames[i][0]
                x, y, _, _ = part['rect']
                assert part['offset'] == [260, 270]
                with Image.open(installed / part['file']) as image:
                    assert image.convert('RGBA').getpixel((x, y)) == (first+i, 49, 71, 100)


def test_corrupted_solid_source_fails_before_creating_output(tmp_path):
    source = tmp_path / 'source'
    solid_source(source)
    (source / 'page.png').write_bytes(b'wrong payload')
    output = tmp_path / 'normalized'
    with pytest.raises(ValueError, match='checksum'):
        normalize_solid_sections(source, output)
    assert not output.exists()
