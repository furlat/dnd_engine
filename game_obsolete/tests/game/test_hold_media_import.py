"""Holds preserve the one quiet sample and the complete finite release."""

import hashlib
import json

import pytest

from devtools.import_hold_media import import_humanoid_holds
from game.animation_types import AuthoredProjectileAsset, ProjectileStorage


def test_original_chain_phases_preserve_still_registration_and_existing_recipe(tmp_path):
    source, repo = tmp_path / 'source', tmp_path / 'repo'
    source.mkdir()
    payload = b'original unchanged chain atlas'
    (source / 'atlas.png').write_bytes(payload)
    (source / 'SHA256SUMS').write_text(hashlib.sha256(payload).hexdigest() + '  atlas.png\n')
    row = {'fps': 32, 'frames': 141, 'cell': 384, 'pivot': [192, 241.883063257728],
        'palette': ['d68726', 'ffd47c'], 'cameras': {str(q): {'layers': {side: {
            'pages': ['atlas.png'], 'frames': [{'page': 0, 'source': [n, q, 1, 1],
                'offset': [120, 80]} for n in range(141)]}
            for side in ('back', 'front')}} for q in range(4)}}
    (source / 'media.json').write_text(json.dumps({'hold_human': row}))
    folder = repo / 'game/data/control_media'
    folder.mkdir(parents=True)
    original = {'spells': {'retained': {'author': 'unchanged'}}}
    (folder / 'bindings.json').write_text(json.dumps(original))
    recipe = {'schema': 'dnd.spellStudioDrafts', 'version': 3, 'spells': []}
    (folder / 'spell-studio-drafts.json').write_text(json.dumps(recipe))
    assert len(import_humanoid_holds(source, repo=repo)) == 6
    assert json.loads((folder / 'spell-studio-drafts.json').read_text()) == recipe
    bindings = json.loads((folder / 'bindings.json').read_text())
    assert bindings['spells'] == original['spells']
    assets = {r['assetId']: AuthoredProjectileAsset.model_validate_json(json.dumps(r))
        for r in json.loads((folder / 'projectile-assets.json').read_text())}
    for phase, first, count in (('apply', 0, 53), ('hold', 53, 1), ('release', 54, 87)):
        for side in ('back', 'front'):
            identity = f'control.hold_human.{phase}.{side}'
            asset = assets[identity]
            assert asset.phases.impact is not None
            assert (asset.phases.impact.frames, asset.phases.impact.loop) == (count, phase == 'hold')
            assert asset.anchor.y == pytest.approx(241.883063257728 / 384)
            stored = bindings['projectileStorage'][identity]
            ProjectileStorage.model_validate_json(json.dumps(stored))
            for q, facing in enumerate(('E', 'S', 'W', 'N')):
                frames = stored['phases']['impact']['layers'][0]['partsByFacing'][facing]
                assert len(frames) == count
                assert frames[0][0]['rect'] == [first, q, 1, 1]
                assert frames[-1][0]['rect'] == [first + count - 1, q, 1, 1]
                assert frames[0][0]['offset'] == [120, 80]
                assert (repo / frames[0][0]['file']).read_bytes() == payload
