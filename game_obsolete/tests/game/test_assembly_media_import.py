"""Released single-layer banks retain pixel registration and native lifecycle."""

import json
from pathlib import Path

from PIL import Image
import pytest

from devtools.import_assembly_media import import_assembly, normalize_assembly


def source_fixture(folder:Path):
    folder.mkdir();image=Image.new('RGBA',(4,4),(73,149,19,83));image.save(folder/'atlas.png')
    frames=[{'page':0,'source':[0,0,4,4],'offset':[222,277]} for _ in range(160)]
    row={'frames':frames,'pages':['atlas.png'],'ortho':12,'pivot':[256,311.42562584220406]}
    manifest={'fps':32,'canvas':[512,512],'nativeCell':2.121320344,
        'loop':{'first':63,'lastExclusive':127,'periodSeconds':2,'verificationEndpoint':127},
        'removal':{'first':128,'lastExclusive':160},
        'banks':{f'module/d{d}/q{q}':row for d in range(8) for q in range(4)}}
    (folder/'media.json').write_text(json.dumps(manifest));return manifest


def test_single_rgba_is_not_published_as_two_compositing_layers(tmp_path):
    source=tmp_path/'source';source_fixture(source)
    normal=tmp_path/'normalized';normalize_assembly(source,normal,'wind')
    repo=tmp_path/'installed';folder=repo/'game/data/wall_media';folder.mkdir(parents=True)
    (folder/'bindings.json').write_text(json.dumps({'resources':{},'spells':{'retained':{}},'projectileStorage':{'old':{}}}))
    (folder/'projectile-assets.json').write_text(json.dumps([{'assetId':'old'}]))
    identities=import_assembly(normal,repo=repo)
    assets={a['assetId']:a for a in json.loads((folder/'projectile-assets.json').read_text())}
    binding=json.loads((folder/'bindings.json').read_text())
    assert len(identities)==24 and all(not identity.endswith('.front') for identity in identities)
    assert binding['spells']=={'retained':{}} and 'old' in binding['projectileStorage']
    for phase,count,loop in [('application',63,False),('hold',64,True),('removal',32,False)]:
        identity=f'wall.wind_d0.{phase}.back';asset=assets[identity]
        assert asset['phases']['impact']['frames']==count
        assert asset['phases']['impact']['loop'] is loop
        assert asset['anchor']=={'x':.5,'y':311.42562584220406/512}
        crops=binding['projectileStorage'][identity]['phases']['impact']['layers'][0]['partsByFacing']
        for facing in ('E','S','W','N'):
            assert len(crops[facing])==count
            crop=crops[facing][0][0]
            assert crop['offset']==[222,277]
            assert Image.open(repo/crop['file']).convert('RGBA').getpixel((0,0))==(73,149,19,83)


def test_unaccepted_clock_fails_before_creating_registration(tmp_path):
    source=tmp_path/'source';manifest=source_fixture(source)
    manifest['loop']['lastExclusive']=128
    (source/'media.json').write_text(json.dumps(manifest))
    output=tmp_path/'bad'
    with pytest.raises(ValueError,match='two-second'):normalize_assembly(source,output,'wind')
    assert not output.exists()
