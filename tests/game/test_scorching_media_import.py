"""The isolated source registers eight native rays and one paired impact."""

import hashlib
import json

import pytest

from devtools.import_scorching_media import import_scorching
from game.animation_types import AuthoredProjectileAsset,ProjectileStorage


def test_original_heading_samples_and_layer_depth_survive_registration(tmp_path):
    source,repo=tmp_path/'source',tmp_path/'repo';source.mkdir()
    payload=b'original isolated atlas';(source/'atlas.png').write_bytes(payload)
    (source/'SHA256SUMS').write_text(hashlib.sha256(payload).hexdigest()+'  atlas.png\n')
    rows={}
    for name,count,yaw in (('scorching_travel_cardinal_v23',14,-90),('scorching_travel_diagonal_v23',14,-135),('scorching_impact_v23',32,-90)):
        rows[name]={'fps':32,'frames':count,'cell':384,'ortho':9,'pivot':[192,192],
            'yaw':yaw,'has_baked_world_translation':False,'palette':['4b0200','ffb777'],
            'cameras':{str(q):{'layers':{side:{'pages':['atlas.png'],
                'frames':[None if 'travel' in name and side=='back' else {'page':0,'source':[n,q,1,1],
                    'offset':[yaw,23]} for n in range(count)]} for side in ('back','front')}} for q in range(4)}}
    (source/'media.json').write_text(json.dumps(rows))
    folder=repo/'game/data/fire_media';folder.mkdir(parents=True)
    retained={'spells':{'other':{'author':'unchanged'}}};(folder/'bindings.json').write_text(json.dumps(retained))
    recipe={'schema':'dnd.spellStudioDrafts','version':3,'spells':[]};(folder/'spell-studio-drafts.json').write_text(json.dumps(recipe))
    assert import_scorching(source,repo=repo)==('fire.scorching.travel','fire.scorching.impact')
    assert json.loads((folder/'spell-studio-drafts.json').read_text())==recipe
    bindings=json.loads((folder/'bindings.json').read_text());assert bindings['spells']==retained['spells']
    for storage in bindings['projectileStorage'].values(): ProjectileStorage.model_validate_json(json.dumps(storage))
    assets={r['assetId']:AuthoredProjectileAsset.model_validate_json(json.dumps(r))
        for r in json.loads((folder/'projectile-assets.json').read_text())}
    asset=assets['fire.scorching.travel']; assert asset.phases.travel is not None
    assert asset.phases.travel.frames==14 and not asset.phases.travel.loop
    assert asset.anchor.x==asset.anchor.y==.5
    parts=bindings['projectileStorage'][asset.assetId]['phases']['travel']['layers'][0]['partsByFacing']
    for facing,q,yaw in (('SE',0,-90),('S',0,-135),('E',3,-135),('SW',1,-90),('N',2,-135)):
        assert len(parts[facing])==14
        assert parts[facing][-1][0]['rect']==[13,q,1,1]
        assert parts[facing][0][0]['offset']==[yaw,23]
    layers=bindings['projectileStorage']['fire.scorching.impact']['phases']['impact']['layers']
    assert [layer['depth'] for layer in layers]==['behind_body','front_body']
    assert all(len(layer['partsByFacing']['E'])==32 for layer in layers)
    assert (repo/'game/assets/fire_media/atlas.png').read_bytes()==payload
    rows['scorching_impact_v23']['has_baked_world_translation']=True
    (source/'media.json').write_text(json.dumps(rows))
    before=(folder/'bindings.json').read_bytes()
    with pytest.raises(ValueError,match='translation'): import_scorching(source,repo=repo)
    assert (folder/'bindings.json').read_bytes()==before
