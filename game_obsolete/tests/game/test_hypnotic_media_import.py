"""Offline import admits original rear-only frames without replaying endpoint128."""

import hashlib
import json

import pytest

from devtools.import_hypnotic_media import import_hypnotic
from game.animation_types import AuthoredProjectileAsset, ProjectileStorage


def packet(source):
    source.mkdir()
    payload=b'exact original source atlas'
    (source/'atlas.png').write_bytes(payload)
    (source/'SHA256SUMS').write_text(hashlib.sha256(payload).hexdigest()+'  atlas.png\n')
    rows={}
    for name,count in (('hypnotic_circle_ground',96),('hypnotic_spiral_loop',129)):
        rows[name]={'fps':32,'frames':count,'loopFrames':128,'cell':768,'ortho':16,
            'pivot':[384,433.883063257728],'palette':['e98caa','ffedd6'],
            'cameras':{str(q):{'layers':{
                'front':{'pages':[],'frames':[None]*count},
                'back':{'pages':['atlas.png'],'frames':[{'page':0,'source':[n,q,1,1],
                    'offset':[20,30]} for n in range(count)]}}} for q in range(4)}}
    (source/'media.json').write_text(json.dumps(rows))
    return rows,payload


def test_original_pixels_pivot_loop_window_and_authoring_preserved(tmp_path):
    source,repo=tmp_path/'source',tmp_path/'repo'
    _,payload=packet(source)
    folder=repo/'game/data/control_media';folder.mkdir(parents=True)
    recipe={'spells':['retained authored recipe']}
    (folder/'spell-studio-drafts.json').write_text(json.dumps(recipe))
    (folder/'bindings.json').write_text(json.dumps({'resources':{},'spells':{'retained':'authored'}}))
    assert set(import_hypnotic(source,repo=repo))=={
        'control.hypnotic_rosette.finite.back','control.hypnotic_spiral.hold.back'}
    assert json.loads((folder/'spell-studio-drafts.json').read_text())==recipe
    bindings=json.loads((folder/'bindings.json').read_text())
    assert bindings['spells']=={'retained':'authored'}
    assets={row['assetId']:AuthoredProjectileAsset.model_validate_json(json.dumps(row))
        for row in json.loads((folder/'projectile-assets.json').read_text())}
    for identity,count in (('control.hypnotic_rosette.finite.back',96),('control.hypnotic_spiral.hold.back',128)):
        asset=assets[identity]
        assert asset.anchor.y==pytest.approx(433.883063257728/768)
        assert asset.phases.impact is not None and asset.phases.impact.frames==count
        storage=bindings['projectileStorage'][identity]
        ProjectileStorage.model_validate_json(json.dumps(storage))
        for facing in ('E','S','W','N'):
            frames=storage['phases']['impact']['layers'][0]['partsByFacing'][facing]
            assert len(frames)==count and frames[-1][0]['rect'][0]==count-1
            assert (repo/frames[0][0]['file']).read_bytes()==payload


def test_unapproved_nonempty_front_rejected_before_install(tmp_path):
    source,repo=tmp_path/'source',tmp_path/'repo'
    rows,_=packet(source)
    rows['hypnotic_spiral_loop']['cameras']['0']['layers']['front']['frames'][0]={'page':0}
    (source/'media.json').write_text(json.dumps(rows))
    with pytest.raises(ValueError,match='rear-only'):
        import_hypnotic(source,repo=repo)
    assert not repo.exists()
