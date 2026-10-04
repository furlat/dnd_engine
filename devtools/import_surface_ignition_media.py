"""Pack accepted ignition color/closest XYZ and install native material phases."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
from zipfile import ZipFile, ZIP_STORED

from devtools.import_registered_media import DIRECTIONS, validate_billboard_bank
from devtools.import_surface_contacts import BANKS
from devtools.import_wind_surface import _canvas, surface_packet, CELL
from devtools.media_delivery import contained_media_path, install_verified_payloads
from game.animation_types import AuthoredProjectileAsset, ProjectileStorage

ROOT = Path(__file__).resolve().parents[1]
NAMES = tuple(name for pair in BANKS for name in pair)


def _read(source: Path) -> tuple[dict,dict,dict[str,str]]:
    colors=json.loads((source/'surface-assets.json').read_text())
    xyz=json.loads((source/'xyz-completion/xyz-media.json').read_text())
    if (xyz['fps']!=32 or xyz['canvas']!=[512,512] or xyz['boundsMin']!=[-16,-.5,-16]
            or xyz['boundsExtent']!=[32,16,32] or not xyz['noBackprojection']):
        raise ValueError('Ignition closest-surface contract differs')
    checks={line.split(maxsplit=1)[1].removeprefix('./'):line.split(maxsplit=1)[0]
        for line in (source/'SHA256SUMS').read_text().splitlines() if line}
    for name in (*NAMES,*(f'quench_wisp_{i}' for i in range(3))):
        row=colors['assets'][name]['media']
        expected=112 if name in NAMES else 80
        if row['frames']!=expected or row['fps']!=32 or set(row['cameras'])!={'0','1','2','3'}:
            raise ValueError('Incomplete ignition native views/clock')
        for camera in row['cameras'].values():
            validate_billboard_bank({**row,'layers':camera['layers']})
    if set(xyz['banks'])!={f'{name}/q{q}/{side}' for name in NAMES for q in range(4) for side in ('back','front')}:
        raise ValueError('Incomplete ignition closest-surface banks')
    for bank in xyz['banks'].values():
        if len(bank['axes'])!=3 or any(len(axis['frames'])!=112 for axis in bank['axes']):
            raise ValueError('Incomplete XYZ phases')
        for axis in bank['axes']:
            checks.update({'xyz-completion/'+p['path']:p['sha256'] for p in axis['pages']})
    for relative,expected in checks.items():
        actual=hashlib.sha256(contained_media_path(source,relative).read_bytes()).hexdigest()
        if actual!=expected:
            if relative not in ('HANDOFF.md','SAFE_BASE_MASK_CONTRACT.md'):
                raise ValueError('Changed accepted source: '+relative)
            # These two delivery notes were amended after the source checksum
            # list. Preserve both current notes and the original list below.
            checks[relative]=actual
    return colors,xyz,checks


def pack_ignition(source: Path, output: Path) -> dict:
    colors,xyz,checks=_read(source)
    output.mkdir(parents=True,exist_ok=False)
    banks=[]
    for name in NAMES:
        media=colors['assets'][name]['media']
        for side in ('back','front'):
            path=output/f'{name}-{side}.zip';images={};owned=0;glow=0;maximum=0.
            with ZipFile(path,'w',compression=ZIP_STORED) as archive:
                for q in range(4):
                    rgba=media['cameras'][str(q)]['layers'][side]
                    positions=xyz['banks'][f'{name}/q{q}/{side}']
                    for frame in range(112):
                        color=_canvas(source,rgba,frame,images)
                        axes=tuple(_canvas(source/'xyz-completion',axis,frame,images) for axis in positions['axes'])
                        packet,count,error=surface_packet(color,axes,q,tuple(xyz['boundsMin']),tuple(xyz['boundsExtent']),tuple(media['pivot']))
                        archive.writestr(f'{DIRECTIONS[q*2]}/{frame:03d}.bin.gz',packet)
                        owned+=count;glow+=int((color[:,:,3]!=0).sum())-count;maximum=max(maximum,error)
            banks.append({'name':name,'side':side,'file':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                'ownedPixels':owned,'unownedDecorationPixels':glow,'maxAddedProjectionErrorPixels':maximum})
            print('Packed',name,side,flush=True)
    result={'banks':banks,'sourceFiles':checks,'rgba':'unchanged original RGBA per frame',
        'coordinates':'delivered closest surface only; unowned translucent glow retains owner decoration',
        'amendedDocumentation':['HANDOFF.md','SAFE_BASE_MASK_CONTRACT.md'],
        'cameraOrder':[0,1,2,3],'fps':32,'onsetFrames':[0,48],'holdFrames':[48,112],
        'loopLaunchMs':1500,'loopCrossfadeMs':500,'removalMs':650,'quenchMs':2500}
    (output/'packing-receipt.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


def install_ignition(source: Path, packed: Path, *, preserved: Path, production: Path, repo: Path=ROOT) -> dict:
    colors,_xyz,checks=_read(source)
    receipt=json.loads((packed/'packing-receipt.json').read_text())
    if receipt['sourceFiles']!=checks or len(receipt['banks'])!=16:
        raise ValueError('Packed ignition provenance differs')
    banks={(b['name'],b['side']):b for b in receipt['banks']}
    if set(banks)!={(name,side) for name in NAMES for side in ('back','front')}:
        raise ValueError('Packed ignition selection differs')
    # Every preserved source (including raw accepted color pages) is pre-read
    # before production installation. Paired packing never replaces originals.
    metadata={relative:contained_media_path(source,relative).read_bytes() for relative in checks}
    for relative in ('surface-assets.json','SHA256SUMS','HANDOFF.md','FireCapture.gd','capture.py',
            'xyz-completion/xyz-media.json','xyz-completion/xyz-validation.json','xyz-completion/HANDOFF.md',
            'xyz-completion/capture.py','loop-completion/loop-player.js','loop-completion/README.md'):
        metadata[relative]=contained_media_path(source,relative).read_bytes()
    for relative,value in metadata.items():
        destination=contained_media_path(preserved,relative)
        if destination.exists() and destination.read_bytes()!=value:
            raise ValueError('Preserved ignition source differs: '+relative)
    bundle=repo/'game/data/surface_ignition_media'
    assets=[];storage={};payloads=[]
    runtime='game/assets/surface_ignition_media/'
    for name in (*NAMES,*(f'quench_wisp_{i}' for i in range(3))):
        media=colors['assets'][name]['media']
        for side in ('back','front'):
            windows=(('application',0,48),('hold',48,64)) if name in NAMES else (('quench',0,80),)
            for phase,first,count in windows:
                identity=f'surface.ignition.{name}.{phase}.{side}'
                asset={'assetId':identity,'displayName':identity,'kind':'projectile','sheet':'/'+identity+'.png',
                    'frame':{'width':512,'height':512,'rows':8,'cols':count},'rowOrder':DIRECTIONS,'fps':32,
                    'phases':{'impact':{'start':0,'frames':count,'fps':32,'loop':phase=='hold'}},
                    'anchor':{'x':media['pivot'][0]/512,'y':media['pivot'][1]/512},'defaultScale':1,
                    'palettePreview':{'colors':[int(c,16) for c in media['palette']]}}
                if name in NAMES:
                    bank=banks[name,side]
                    packet={'componentsByFacing':{DIRECTIONS[q*2]:[{'archive':{'file':runtime+bank['file'],
                        'memberPattern':DIRECTIONS[q*2]+'/{frame:03d}.bin.gz'},'pivot':media['pivot'],'blendMode':'normal'}] for q in range(4)},
                        'frameIndices':list(range(first,first+count)),'bounds':[-40,40],
                        'positionScale':1/CELL,'verticalScale':1.224744871391589,'referencePixelScale':1}
                    selected={'phases':{'impact':{'surfaceFrames':packet}}}
                    if phase=='application':payloads.append((bank['file'],runtime+bank['file'],bank['sha256']))
                else:
                    views={}
                    for q in range(4):
                        layer=media['cameras'][str(q)]['layers'][side]
                        views[DIRECTIONS[q*2]]=[[] if f is None else [{'file':runtime+layer['pages'][f['page']],
                            'rect':f['source'],'offset':f['offset']}] for f in layer['frames']]
                    selected={'phases':{'impact':{'layers':[{'blendMode':'normal','partsByFacing':views}]}}}
                AuthoredProjectileAsset.model_validate_json(json.dumps(asset));ProjectileStorage.model_validate_json(json.dumps(selected))
                assets.append(asset);storage[identity]=selected
    # A staging root unifies original quench pages and packed ignition archives.
    for name in (f'quench_wisp_{i}' for i in range(3)):
        for camera in colors['assets'][name]['media']['cameras'].values():
            for layer in camera['layers'].values():
                for relative in layer['pages']:
                    target=contained_media_path(packed,relative);target.parent.mkdir(parents=True,exist_ok=True)
                    if target.exists() and target.read_bytes()!=metadata[relative]:raise ValueError('Changed staged quench')
                    target.write_bytes(metadata[relative]);payloads.append((relative,runtime+relative,checks[relative]))
    installed=install_verified_payloads(packed,tuple(dict.fromkeys(payloads)),preserved=preserved/'packed',production=production,repo=repo)
    for relative,value in metadata.items():
        path=contained_media_path(preserved,relative);path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(value)
    shutil.copyfile(packed/'packing-receipt.json',preserved/'packing-receipt.json')
    bundle.mkdir(parents=True,exist_ok=True)
    (bundle/'projectile-assets.json').write_text(json.dumps(assets,indent=2)+'\n')
    (bundle/'bindings.json').write_text(json.dumps({'resources':{},'projectileStorage':storage},indent=2)+'\n')
    public={**receipt,'preserved':str(preserved),'files':installed}
    (bundle/'source.json').write_text(json.dumps(public,indent=2)+'\n')
    return public


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation',choices=('pack','install'))
    for name in ('source','packed','preserved','production'):parser.add_argument('--'+name,type=Path)
    args=parser.parse_args()
    if args.operation=='pack':pack_ignition(args.source,args.packed)
    else:install_ignition(args.source,args.packed,preserved=args.preserved,production=args.production)
