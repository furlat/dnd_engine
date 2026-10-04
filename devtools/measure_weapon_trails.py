"""Apply the accepted StrikePaths source-pixel measurement to installed weapons."""
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image,ImageDraw

from devtools.import_registered_media import DIRECTIONS
from game.animation_data import load_animation_data

ROOT=Path(__file__).resolve().parents[1]
SOURCE=Path('/home/tommaso/Dev/neurodragon_art/sources/class-actions-roar-cast-v5-20261004')


def measure():
    data=load_animation_data();rig=data.rigs[data.root_rig]
    original=json.loads((SOURCE/'authoring/project/StrikePaths.json').read_text())
    poses=[];sources=[];proof=ROOT/'.runtime/class-weapon-paths-20261004';proof.mkdir(parents=True,exist_ok=True)
    for clip in ('Attack1','Attack2','Attack4','Attack5','Attack6'):
        for category,resource in sorted(rig.clips[clip].sheets.items()):
            if not (category.startswith('Melee') or category.startswith('Offhand')):continue
            path=data.resources[resource];sheet=np.asarray(Image.open(path).convert('RGBA'));points={}
            contact=Image.new('RGBA',(8*128,3*146),(29,33,39,255));draw=ImageDraw.Draw(contact)
            for heading,direction in enumerate(DIRECTIONS):
                points[direction]=[]
                for frame in range(15):
                    cell=sheet[heading*128:(heading+1)*128,frame*128:(frame+1)*128]
                    ys,xs=np.where(cell[...,3]>120)
                    if len(xs):
                        distance=(xs-64)**2+(ys-66)**2
                        far=distance>=np.quantile(distance,.84)
                        point=dict(x=round(float(xs[far].mean()),3),y=round(float(ys[far].mean()),3))
                    else:point=None
                    if category=='Melee1' and clip=='Attack1':
                        assert point is not None
                        expected=original['paths'][heading][frame]
                        assert [point['x'],point['y']]==expected,('original source mismatch',direction,frame)
                    points[direction].append(point)
                    if frame in (2,5,8):
                        row=(2,5,8).index(frame);contact.alpha_composite(Image.fromarray(cell),(heading*128,row*146))
                        if point:
                            x,y=heading*128+point['x'],row*146+point['y'];draw.ellipse((x-2,y-2,x+2,y+2),outline='yellow')
                        draw.text((heading*128,row*146+128),f'{direction} {frame}',fill='white')
            poses.append(dict(rigId=data.root_rig,category=category,clip=clip,pointsByFacing=points))
            sources.append(dict(category=category,clip=clip,file=str(path.relative_to(ROOT)),sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
            contact.save(proof/f'{category}-{clip}.png')
    p=ROOT/'game/data/neuroclient/attack-profiles.json';profiles=json.loads(p.read_text())
    selection=dict(poses=poses,impactAssetId='class.martial.impact',palette=[0x642b2b,0xbf5745,0xe4ccb1],
        behaviorIds=['action.class.barbarian.frenzied_strike','action.feature.extra_attack'],
        handlerIds=['reaction.class_feature.barbarian.retaliation'],outcomes=['critical'])
    (ROOT/'game/data/class_media/weapon-trails.json').write_text(json.dumps(dict(behaviors=profiles['behaviors'],presentation=selection),separators=(',',':'))+'\n')
    receipt=dict(source=str(SOURCE/'authoring/prepare_strike.py'),source_sha256=hashlib.sha256((SOURCE/'authoring/prepare_strike.py').read_bytes()).hexdigest(),
        method='Original alpha>120; outer 16 percent of squared source-pixel distance from (64,66), mean and round to 3 decimals; same accepted method for each actual category/pose. Empty cells remain null.',
        original_Melee1_Attack1_all_120_points_exact=True,source_sheets=sources,poses=len(poses),
        unmeasured='Fixed sheets have no separable weapon pixels and retain existing authored attack layers.')
    (ROOT/'game/data/class_media/weapon-trails-source.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print('Measured',len(poses),'weapon/clip records',len(poses)*120,'cells',flush=True)


if __name__=='__main__':measure()
