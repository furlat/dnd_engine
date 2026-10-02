"""Offline registration of accepted eight-heading finite rays and paired impact."""

import argparse
import json
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory

from devtools.import_registered_media import DIRECTIONS, import_registered_bank

ROOT = Path(__file__).resolve().parents[1]


def import_scorching(source: Path, *, repo: Path = ROOT) -> tuple[str, ...]:
    rows=json.loads((source/'media.json').read_text())
    for name,frames,yaw in (('scorching_travel_cardinal_v23',14,-90),
                           ('scorching_travel_diagonal_v23',14,-135),('scorching_impact_v23',32,-90)):
        row=rows[name]
        if (row['fps'],row['frames'],row['cell'],row['ortho'],row['pivot'],row['yaw']) != (32,frames,384,9,[192,192],yaw):
            raise ValueError('Scorching requires the accepted isolated v23 registration')
        if row['has_baked_world_translation']:
            raise ValueError('Isolated rays cannot contain baked gameplay translation')
    cardinal,diagonal=(rows['scorching_travel_'+kind+'_v23'] for kind in ('cardinal','diagonal'))
    if cardinal['palette'] != diagonal['palette']:
        raise ValueError('Native ray headings must preserve one accepted palette')
    with TemporaryDirectory(prefix='scorching-registration-') as temporary:
        staging=Path(temporary)
        for name,program,frames in (('scorching_travel_cardinal_v23','scorching_cardinal',14),
                                  ('scorching_travel_diagonal_v23','scorching_diagonal',14),
                                  ('scorching_impact_v23','scorching',32)):
            import_registered_bank(source,rows[name],program,(('impact' if frames==32 else 'travel',0,frames),),
                staging,bundle='fire_media',default_scale=.5625)
        folder=staging/'game/data/fire_media'
        bindings=json.loads((folder/'bindings.json').read_text()); storage=bindings['projectileStorage']
        assets={r['assetId']:r for r in json.loads((folder/'projectile-assets.json').read_text())}
        card_id,diag_id='fire.scorching_cardinal.travel.front','fire.scorching_diagonal.travel.front'
        identity='fire.scorching.travel'
        asset=assets.pop(card_id); assets.pop(diag_id)
        asset.update(assetId=identity,displayName=identity,sheet='/fire_media/scorching/travel.png')
        asset['phases']={'travel':asset['phases']['impact']}; assets[identity]=asset
        card_views,diag_views=(storage.pop(key)['phases']['impact']['layers'][0]['partsByFacing'] for key in (card_id,diag_id))
        # Native +X is world SE. +X+Z is world S; camera bank reuse is q-k.
        views={facing:(diag_views if i%2==0 else card_views)[DIRECTIONS[2*(((i+7)//2)%4)]]
            for i,facing in enumerate(DIRECTIONS)}
        storage[identity]={'phases':{'travel':{'layers':[{'partsByFacing':views,'blendMode':'normal'}]}}}
        for kind in ('cardinal','diagonal'):
            empty=f'fire.scorching_{kind}.travel.back'
            assets.pop(empty); storage.pop(empty)
        back,front='fire.scorching.impact.back','fire.scorching.impact.front'
        identity='fire.scorching.impact'
        asset=assets.pop(front); assets.pop(back)
        asset.update(assetId=identity,displayName=identity,sheet='/fire_media/scorching/impact.png')
        assets[identity]=asset
        layers=[]
        for key,depth in ((back,'behind_body'),(front,'front_body')):
            layer=storage.pop(key)['phases']['impact']['layers'][0]
            layer['depth']=depth; layers.append(layer)
        storage[identity]={'phases':{'impact':{'layers':layers}}}
        destination=repo/'game/data/fire_media'
        old_bindings=json.loads((destination/'bindings.json').read_text()) if (destination/'bindings.json').exists() else {'resources':{},'spells':{}}
        old_assets={r['assetId']:r for r in json.loads((destination/'projectile-assets.json').read_text())} if (destination/'projectile-assets.json').exists() else {}
        old_bindings.setdefault('projectileStorage',{}).update(storage); old_assets.update(assets)
        for origin in (staging/'game/assets/fire_media').rglob('*.png'):
            target=repo/origin.relative_to(staging); target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(origin,target)
        destination.mkdir(parents=True,exist_ok=True)
        (destination/'bindings.json').write_text(json.dumps(old_bindings,indent=2)+'\n')
        (destination/'projectile-assets.json').write_text(json.dumps(list(old_assets.values()),indent=2)+'\n')
    return tuple(assets)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True); parser.add_argument('--repo',type=Path,default=ROOT)
    args=parser.parse_args()
    print(f'Registered {len(import_scorching(args.source,repo=args.repo))} Scorching Ray banks')
