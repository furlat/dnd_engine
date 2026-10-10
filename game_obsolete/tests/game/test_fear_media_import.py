"""Accepted eight-heading banks keep exact crops, finite windows and null layers."""

import hashlib
import json

import pytest

from devtools.import_fear_media import import_fear
from devtools.import_registered_media import DIRECTIONS
from game.animation_types import AuthoredProjectileAsset, ProjectileStorage


@pytest.fixture
def packet(tmp_path):
    source,repo = tmp_path/'source',tmp_path/'repo'
    source.mkdir()
    payload=b'original source atlas'
    (source/'atlas.png').write_bytes(payload)
    (source/'SHA256SUMS').write_text(hashlib.sha256(payload).hexdigest()+'  atlas.png\n')
    rows={}
    for name,frames,cell in (('fear_path_v7',144,896),('fear_path_v7_diagonal',144,896),('frightened_v5',96,384)):
        rows[name]={'fps':32,'frames':frames,'cell':cell,'pivot':[cell/2,cell/2+49],
            'palette':['242326','efe5d0'],'cameras':{str(q):{'layers':{side:{
                'pages':['atlas.png'],'frames':[None if side=='back' and q==0 else
                    {'page':0,'source':[n,q,1,1],'offset':[17,23]} for n in range(frames)]}
                for side in ('back','front')}} for q in range(4)}}
    (source/'media.json').write_text(json.dumps(rows))
    return source,repo,rows


def test_finite_heading_registration_and_condition_windows_preserve_source(packet):
    source,repo,_=packet
    folder=repo/'game/data/control_media'; folder.mkdir(parents=True)
    original={'spells':{'retained':{'author':'unchanged'}}}
    (folder/'bindings.json').write_text(json.dumps(original))
    recipe={'schema':'dnd.spellStudioDrafts','version':3,'spells':[]}
    (folder/'spell-studio-drafts.json').write_text(json.dumps(recipe))
    assert len(import_fear(source,repo=repo))==6
    assert json.loads((folder/'spell-studio-drafts.json').read_text())==recipe
    bindings=json.loads((folder/'bindings.json').read_text())
    assert bindings['spells']==original['spells']
    assets={r['assetId']:AuthoredProjectileAsset.model_validate_json(json.dumps(r))
        for r in json.loads((folder/'projectile-assets.json').read_text())}
    for side in ('back','front'):
        identity='control.fear.finite.'+side
        asset=assets[identity]; assert asset.phases.impact is not None
        assert asset.phases.impact.frames==144 and not asset.phases.impact.loop
        assert asset.anchor.y==pytest.approx(497/896)
        storage=bindings['projectileStorage'][identity]
        ProjectileStorage.model_validate_json(json.dumps(storage))
        views=storage['phases']['impact']['layers'][0]['partsByFacing']
        for i,facing in enumerate(DIRECTIONS):
            q=((i+6)//2)%4
            parts=views[facing]
            assert len(parts)==144
            if side=='back' and q==0:
                assert all(frame==[] for frame in parts)
            else:
                assert parts[-1][0]['rect']==[143,q,1,1]
                assert parts[0][0]['offset']==[17,23]
                assert (repo/parts[0][0]['file']).read_bytes()==(source/'atlas.png').read_bytes()
    for phase,start,count in (('apply',0,48),('hold',32,64)):
        identity=f'control.frightened.{phase}.front'
        parts=bindings['projectileStorage'][identity]['phases']['impact']['layers'][0]['partsByFacing']['E']
        assert len(parts)==count and parts[0][0]['rect'][0]==start
        assert parts[-1][0]['rect'][0]==start+count-1


def test_late_packet_failure_does_not_partially_install_fear(packet):
    source,repo,rows=packet
    rows['frightened_v5']['cameras']['3']['layers']['front']['frames'].pop()
    (source/'media.json').write_text(json.dumps(rows))
    with pytest.raises(ValueError,match='Incomplete'):
        import_fear(source,repo=repo)
    assert not repo.exists()
