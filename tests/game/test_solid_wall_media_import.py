"""Section preparation preserves real samples without replaying fixture breaks."""

import hashlib
import json

from PIL import Image
import pytest

from devtools.import_solid_wall_media import import_solid_sections, import_solid_retirement, normalize_solid_sections


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


def retirement_source(folder):
    folder.mkdir()
    page=folder/'packed/page.png';page.parent.mkdir()
    Image.new('RGBA',(1,1),(50,70,90,120)).save(page)
    digest=hashlib.sha256(page.read_bytes()).hexdigest()
    layer={'pages':['packed/page.png'],'frames':[{'page':0,'source':[0,0,1,1],'offset':[256,260]}]*28+[None]}
    row={'fps':32,'frames':29,'cell':512,'pivot':[256,311.425626],'palette':['383b34'],
        'cameras':{str(q):{'layers':{'back':layer,'front':layer}} for q in range(4)}}
    rows={f'{kind}_v{v}_d{d}':row for kind in ('stone','ice') for v in range(3) for d in range(4)}
    (folder/'media.json').write_text(json.dumps(rows))
    (folder/'SHA256SUMS').write_text(digest+'  packed/page.png\n')
    (folder/'validation.json').write_text(json.dumps({'durationMs':850,
        'samples':[{'intact_byte_exact':True,'final_empty':True}]*192}))


def test_intact_retirement_installs_separately_and_preserves_selected_recipe(tmp_path):
    source=tmp_path/'export';retirement_source(source)
    repo,production,preserved=tmp_path/'repo',tmp_path/'production',tmp_path/'preserved'
    bundle=repo/'game/data/wall_media';bundle.mkdir(parents=True)
    (bundle/'bindings.json').write_text('{"resources":{},"projectileStorage":{}}')
    (bundle/'projectile-assets.json').write_text('[]')
    recipe=bundle/'drafts.json';recipe.write_text('{"selected":"unchanged"}')
    production.mkdir();(production/'art-manifest.json').write_text('{"files":[],"total_bytes":0}')
    identities=import_solid_retirement(source,preserved=preserved,production=production,repo=repo)
    assert len(identities)==48 and all('.removal.' in identity for identity in identities)
    assert recipe.read_text()=='{"selected":"unchanged"}'
    for root in (repo,production):
        assert (root/'game/assets/wall_media/retirement/packed/page.png').read_bytes()==(source/'packed/page.png').read_bytes()
    assert (preserved/'validation.json').read_bytes()==(source/'validation.json').read_bytes()
    assert import_solid_retirement(source,preserved=preserved,production=production,repo=repo)==identities


def test_retirement_missing_proof_cannot_partly_install(tmp_path):
    source=tmp_path/'export';retirement_source(source)
    validation=json.loads((source/'validation.json').read_text())
    validation['samples'][-1]['intact_byte_exact']=False
    (source/'validation.json').write_text(json.dumps(validation))
    with pytest.raises(ValueError,match='preserve every intact'):
        import_solid_retirement(source,preserved=tmp_path/'archive',production=tmp_path/'production',repo=tmp_path/'repo')
    assert not (tmp_path/'archive').exists() and not (tmp_path/'production').exists() and not (tmp_path/'repo').exists()
