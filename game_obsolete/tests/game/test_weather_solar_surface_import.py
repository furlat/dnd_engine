"""Failed coordinate companions cannot partially replace accepted media."""

import gzip
import hashlib
import json
from pathlib import Path
import struct
import zipfile

import pytest

from devtools.import_weather_solar_surfaces import import_surfaces

ROOT = Path(__file__).resolve().parents[2]


def delivery(tmp_path):
    source, repo, production, preserved = (tmp_path/name for name in ('source', 'repo', 'production', 'preserved'))
    source.mkdir(); production.mkdir()
    (production/'art-manifest.json').write_text('{"files":[],"total_bytes":0}')
    bundle = repo/'game/data/weather_solar_media';bundle.mkdir(parents=True)
    existing = json.loads((ROOT/'game/data/weather_solar_media/projectile-assets.json').read_text())
    assets = [row for row in existing if row['assetId'] in ('solar.sunburst.back', 'solar.sunburst.front')]
    (bundle/'projectile-assets.json').write_text(json.dumps(assets))
    (bundle/'bindings.json').write_text('{"resources":{},"spells":{},"projectileStorage":{}}')
    (bundle/'weather-draft.json').write_text('{"preserve":"existing recipe"}')
    banks = []
    for side in ('back', 'front'):
        path = source/('burst-'+side+'-surface.zip')
        with zipfile.ZipFile(path, 'w') as archive:
            packet = struct.pack('<HHhh',1,1,0,0)+bytes((255,200,100,255))+bytes(6)+bytes((1,))
            for frame in range(64): archive.writestr(f'{frame:03d}.bin.gz', gzip.compress(packet))
        banks.append({'bank':'burst-'+side,'file':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'frames':64,'worldPixels':512/29,'pivot':[256,237.8], 'checks':[{'frame':frame,'missingOwnership':0,
            'maxCameraErrorPixels':.1} for frame in range(64)]})
    (source/'burst-opaque').mkdir();(source/'burst-opaque/complete.json').write_text('{}')
    (source/'burst-ownership.json').write_text(json.dumps({'banks':banks,'bounds':[-64,64],
        'coordinateBasis':'camera_local_xyz','verticalScale':1.224744871391589,
        'production_rgba_recaptured':False,'accepted_rgba_byte_exact':True}))
    return source, repo, production, preserved


@pytest.mark.parametrize('fault', ['traversal', 'bad-owner', 'missing-provenance'])
def test_invalid_companion_leaves_original_install_unchanged(tmp_path, fault):
    source, repo, production, preserved = delivery(tmp_path)
    before = {path.relative_to(repo):path.read_bytes() for path in repo.rglob('*') if path.is_file()}
    receipt_path = source/'burst-ownership.json'; receipt = json.loads(receipt_path.read_text())
    if fault == 'traversal':
        receipt['banks'][-1]['file'] = '../escaped.zip'
    elif fault == 'bad-owner':
        row = receipt['banks'][-1]; path = source/row['file']
        with zipfile.ZipFile(path, 'w') as archive:
            for frame in range(64):
                packet = struct.pack('<HHhh',1,1,0,0)+bytes((255,200,100,255))+bytes(6)+bytes((0 if frame==63 else 1,))
                archive.writestr(f'{frame:03d}.bin.gz',gzip.compress(packet))
        row['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    else:
        (source/'burst-opaque/complete.json').unlink()
    receipt_path.write_text(json.dumps(receipt))
    with pytest.raises((ValueError, FileNotFoundError)):
        import_surfaces(source,'burst',preserved=preserved,production=production,repo=repo)
    assert before == {path.relative_to(repo):path.read_bytes() for path in repo.rglob('*') if path.is_file()}
    assert json.loads((production/'art-manifest.json').read_text())['files'] == []
    assert not preserved.exists()


def test_valid_companion_preserves_original_registration_and_recipe(tmp_path):
    source, repo, production, preserved = delivery(tmp_path)
    bundle = repo/'game/data/weather_solar_media'
    before = (bundle/'weather-draft.json').read_bytes()
    receipt = import_surfaces(source,'burst',preserved=preserved,production=production,repo=repo)
    assert len(receipt['files']) == 2 and receipt['accepted_rgba_byte_exact']
    assert (bundle/'weather-draft.json').read_bytes() == before
    assets = {row['assetId'] for row in json.loads((bundle/'projectile-assets.json').read_text())}
    assert assets == {'solar.sunburst.back','solar.sunburst.front','solar.sunburst.back.surface','solar.sunburst.front.surface'}
    for row in receipt['files']:
        assert (repo/row['path']).read_bytes() == (production/row['path']).read_bytes()
