"""Original intact XYZ, and its declared rigid retirement transform, for cuts."""

import argparse
import gzip
import struct
import hashlib
import json
from math import sqrt
from pathlib import Path
from zipfile import ZipFile, ZIP_STORED

import numpy as np
from PIL import Image

from devtools.import_assembly_media import SOURCE_CAMERAS
from devtools.import_wind_surface import _canvas, surface_packet, CELL
from devtools.media_delivery import contained_media_path, install_verified_payloads
from game.animation_types import ProjectileStorage

ROOT=Path(__file__).resolve().parents[1]
FACINGS=('E','S','W','N')


def _axes(source: Path, row: dict) -> tuple[np.ndarray,...]:
    result=[]
    for axis in row['axes']:
        path=contained_media_path(source,axis['path'])
        if hashlib.sha256(path.read_bytes()).hexdigest()!=axis['sha256']:
            raise ValueError('Changed original intact position map')
        with Image.open(path) as image:piece=np.array(image.convert('RGBA'))
        x,y=axis['offset'];w,h=axis['size']
        if piece.shape!=(h,w,4) or min(x,y)<0 or x+w>512 or y+h>512:
            raise ValueError('Intact coordinate registration differs')
        canvas=np.zeros((512,512,4),np.uint8);canvas[y:y+h,x:x+w]=piece;result.append(canvas)
    if len(result)!=3:raise ValueError('Intact position requires three native axes')
    return tuple(result)


def _translated_axes(axes: tuple[np.ndarray,...], frame: int, minimum, extent) -> tuple[np.ndarray,...]:
    # Literal accepted source retirement: one rigid root Y translation. Sample
    # the existing coordinate raster at the inverse orthographic translation;
    # this never backprojects RGBA or assigns coordinates to unowned fringes.
    u=min(1.,frame/32/.85);sink=CELL*2*u*u*(3-2*u)
    displacement=sink*512/12*sqrt(3)/2
    source_y=np.rint(np.arange(512)-displacement).astype(int)
    inside=(source_y>=0)&(source_y<512);source_y=np.clip(source_y,0,511)
    result=[]
    for axis,low,width,index in zip(axes,minimum,extent,range(3),strict=True):
        values=axis[source_y].copy();values[~inside,:,3]=0
        if index==1:
            native=low+(values[:,:,0].astype(float)*256+values[:,:,1])*width/65535-sink
            values[native<0,3]=0
            encoded=np.rint((native-low)*65535/width).clip(0,65535).astype(np.uint16)
            values[:,:,0]=encoded//256;values[:,:,1]=encoded%256
        result.append(values)
    return tuple(result)


def pack_solid(source: Path, retirement: Path, output: Path) -> dict:
    colors=json.loads((source/'media.json').read_text());xyz=json.loads((source/'xyz-media.json').read_text())
    clear=json.loads((retirement/'media.json').read_text())
    validation=json.loads((source/'xyz-validation.json').read_text())
    if (validation['errors'] or len(xyz['banks'])!=96 or xyz['boundsMin']!=[-40,-.5,-40]
            or xyz['boundsExtent']!=[80,6,80] or xyz['pivot']!=[256,311.425626]):
        raise ValueError('Unverified original solid coordinates')
    for check in validation['checks']:
        if check['projectionMaxPixels']>.05:raise ValueError('Source coordinate projection differs')
    output.mkdir(parents=True,exist_ok=False)
    banks=[];verified=set()
    for material in ('stone','ice'):
        for variant in range(3):
            for direction in range(4):
                name=f'{material}_v{variant}_d{direction}'
                for side in ('back','front'):
                    path=output/(name+'_'+side+'.zip');images={};checks=[]
                    with ZipFile(path,'w',compression=ZIP_STORED) as archive:
                        for q,source_q in enumerate(SOURCE_CAMERAS):
                            coordinate=xyz['banks'][f'{material}-v{variant}/d{direction}/q{source_q}']
                            if abs(coordinate['ownerYawRadians']-direction*np.pi/2)>1e-8 or coordinate['poseSeconds']!=1.5:
                                raise ValueError('Source owner rotation or held pose differs')
                            axes=_axes(source,coordinate)
                            original=colors['banks'][f'{material}-v{variant}-lifecycle/d{direction}/q{source_q}/{side}']
                            for page in original['pages']:
                                if page['path'] not in verified:
                                    if hashlib.sha256(contained_media_path(source,page['path']).read_bytes()).hexdigest()!=page['sha256']:
                                        raise ValueError('Changed accepted solid color')
                                    verified.add(page['path'])
                            for frame in range(30):
                                if frame==0:
                                    rgba=_canvas(source,original,47,images);positions=axes
                                else:
                                    rgba=_canvas(retirement,clear[name]['cameras'][str(q)]['layers'][side],frame-1,images)
                                    positions=_translated_axes(axes,frame-1,xyz['boundsMin'],xyz['boundsExtent'])
                                packet,owned,error=surface_packet(rgba,positions,q,tuple(xyz['boundsMin']),tuple(xyz['boundsExtent']),tuple(xyz['pivot']))
                                valid=np.logical_and.reduce([axis[:,:,3]!=0 for axis in positions])
                                total=int(rgba[:,:,3].sum());missing=int(rgba[:,:,3][~valid].sum())
                                checks.append({'camera':q,'frame':frame,'owned':owned,'unownedAlpha':missing,'totalAlpha':total,
                                    'maxAddedProjectionErrorPixels':error})
                                archive.writestr(f'{FACINGS[q]}/{frame:03d}.bin.gz',packet)
                    banks.append({'name':name,'side':side,'file':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'checks':checks})
                print('Packed',name,flush=True)
    result={'source':str(source),'retirementSource':str(retirement),'banks':banks,
        'sourceHashes':{name:hashlib.sha256((source/name).read_bytes()).hexdigest() for name in ('media.json','xyz-media.json','xyz-validation.json')},
        'retirementHashes':{name:hashlib.sha256((retirement/name).read_bytes()).hexdigest() for name in ('media.json','validation.json','SHA256SUMS')},
        'originalRGBA':'All selected held and retirement pixels retained byte-exact inside lossless packets',
        'coordinates':'Original closest XYZ at 1.5 s; retirement applies only original rigid root Y translation',
        'unownedCutPolicy':'Only cut objects omit source boundary pixels without genuine coordinates; uncut pixels unchanged',
        'holdFrame':0,'removalFrames':[1,30],'positionScale':1/CELL,'verticalScale':1.224744871391589}
    (output/'packing-receipt.json').write_text(json.dumps(result,indent=2)+'\n')
    return result



def _validate_packets(packed: Path, banks: list[dict]) -> float:
    """Check the actual stored surface, including the declared source transform."""
    maximum = 0.
    expected = {f'{facing}/{frame:03d}.bin.gz' for facing in FACINGS for frame in range(30)}
    for bank in banks:
        path = contained_media_path(packed, bank['file'])
        if hashlib.sha256(path.read_bytes()).hexdigest() != bank['sha256']:
            raise ValueError('Changed solid surface payload')
        with ZipFile(path) as archive:
            if set(archive.namelist()) != expected or len(archive.namelist()) != len(expected):
                raise ValueError('Solid surface members differ')
            for name in expected:
                raw = gzip.decompress(archive.read(name))
                if len(raw) < 8:
                    raise ValueError('Truncated solid surface header')
                width, height, ox, oy = struct.unpack_from('<HHhh', raw)
                count = width*height
                if not count or max(width,height)>512 or len(raw)!=8+count*11:
                    raise ValueError('Solid surface dimensions differ')
                xyz = np.frombuffer(raw,dtype='>u2',count=count*3,offset=8+count*4).reshape(height,width,3).astype(float)*80/65535-40
                ownership = np.frombuffer(raw,dtype=np.uint8,count=count,offset=8+count*10).reshape(height,width)
                if (ownership>1).any():
                    raise ValueError('Invalid solid surface ownership')
                y,x = np.indices((height,width))
                px = (xyz[:,:,0]-xyz[:,:,2])*512/(12*sqrt(2))
                py = (xyz[:,:,0]+xyz[:,:,2])*512/(24*sqrt(2))-xyz[:,:,1]*512*sqrt(3)/24
                error = np.hypot(px-(x+.5+ox),py-(y+.5+oy+round(311.425626)-311.425626))
                owned = ownership!=0
                value = float(error[owned].max()) if owned.any() else 0.
                # Inverse nearest sampling of the original rigid translation
                # adds at most half a pixel to the original position encoding.
                if value > .55:
                    raise ValueError('Solid coordinates no longer match their original pixels')
                maximum = max(maximum,value)
    return maximum


def _validate_retirement_pages(source: Path) -> None:
    expected = {}
    for line in (source/'SHA256SUMS').read_text().splitlines():
        digest,relative = line.split('  ',1)
        expected[relative] = digest
    media = json.loads((source/'media.json').read_text())
    pages = {page for bank in media.values() for camera in bank['cameras'].values()
        for layer in camera['layers'].values() for page in layer['pages']}
    for relative in pages:
        if relative not in expected or hashlib.sha256(contained_media_path(source,relative).read_bytes()).hexdigest()!=expected[relative]:
            raise ValueError('Changed accepted retirement color')


def install_solid(packed: Path, *, preserved: Path, production: Path, repo: Path=ROOT) -> dict:
    receipt=json.loads((packed/'packing-receipt.json').read_text());banks=receipt['banks']
    if len(banks)!=48 or len({(b['name'],b['side']) for b in banks})!=48:
        raise ValueError('Incomplete solid surface selection')
    for source_key,hash_key in (('source','sourceHashes'),('retirementSource','retirementHashes')):
        source=Path(receipt[source_key])
        for relative,expected in receipt[hash_key].items():
            if hashlib.sha256(contained_media_path(source,relative).read_bytes()).hexdigest()!=expected:
                raise ValueError('Original coordinate provenance changed')
    _validate_retirement_pages(Path(receipt['retirementSource']))
    receipt['maxStoredProjectionErrorPixels'] = _validate_packets(packed,banks)
    bundle=repo/'game/data/wall_media';bindings=json.loads((bundle/'bindings.json').read_text())
    assets={row['assetId']:row for row in json.loads((bundle/'projectile-assets.json').read_text())}
    updates={};payloads=[]
    for bank in banks:
        if len(bank['checks'])!=120 or any(c['maxAddedProjectionErrorPixels']>.1 for c in bank['checks']):
            raise ValueError('Incomplete or inaccurate solid packet checks')
        runtime='game/assets/wall_media/surfaces/'+bank['file'];payloads.append((bank['file'],runtime,bank['sha256']))
        for phase,frames in (('hold',[0]),('removal',list(range(1,30)))):
            identity=f"wall.{bank['name']}.{phase}.{bank['side']}"
            if assets[identity]['phases']['impact']['frames']!=len(frames):raise ValueError('Existing solid phase differs')
            storage={'phases':{'impact':{'surfaceFrames':{'componentsByFacing':{facing:[{'archive':{
                'file':runtime,'memberPattern':facing+'/{frame:03d}.bin.gz'},'pivot':[256,311.425626],'blendMode':'normal'}] for facing in FACINGS},
                'frameIndices':frames,'bounds':[-40,40],'verticalScale':receipt['verticalScale'],'positionScale':receipt['positionScale']}}}}
            ProjectileStorage.model_validate_json(json.dumps(storage));updates[identity]=storage
    metadata=(json.dumps(receipt,indent=2)+'\n').encode();target=preserved/'packing-receipt.json'
    if target.exists() and target.read_bytes()!=metadata:raise ValueError('Preserved surface receipt differs')
    installed=install_verified_payloads(packed,tuple(payloads),preserved=preserved,production=production,repo=repo)
    target.write_bytes(metadata);bindings['projectileStorage'].update(updates)
    (bundle/'bindings.json').write_text(json.dumps(bindings,indent=2)+'\n')
    public={**receipt,'preserved':str(preserved),'files':installed}
    (bundle/'solid-surfaces-source.json').write_text(json.dumps(public,indent=2)+'\n')
    return public


def install_fracture(packed: Path, *, preserved: Path, production: Path, repo: Path=ROOT) -> dict:
    receipts=[json.loads((packed/f'stone-v{variant}-receipt.json').read_text()) for variant in range(3)]
    banks=[bank for receipt in receipts for bank in receipt['banks']]
    if len(banks)!=24 or len({(b['name'],b['side']) for b in banks})!=24:
        raise ValueError('Incomplete Stone fracture material selection')
    source=Path('/home/tommaso/Dev/neurodragon_art/sources/solid-modular-55f231b700c1')
    colors=json.loads((source/'media.json').read_text());verified=set()
    for receipt in receipts:
        geometry=receipt['geometrySource']
        if hashlib.sha256(contained_media_path(source,geometry['path']).read_bytes()).hexdigest()!=geometry['sha256']:
            raise ValueError('Changed original fracture geometry')
        if receipt['coordinateBasis']!='material_rest_xyz' or receipt['originalRGBA']!='unchanged':
            raise ValueError('Fracture packet coordinate semantics differ')
    for name,bank in colors['banks'].items():
        if not name.startswith('stone-'):continue
        for page in bank['pages']:
            if page['path'] in verified:continue
            if hashlib.sha256(contained_media_path(source,page['path']).read_bytes()).hexdigest()!=page['sha256']:
                raise ValueError('Changed original Stone pixels')
            verified.add(page['path'])
    bundle=repo/'game/data/wall_media';bindings=json.loads((bundle/'bindings.json').read_text())
    assets={row['assetId']:row for row in json.loads((bundle/'projectile-assets.json').read_text())}
    expected={f'{facing}/{frame:03d}.bin.gz' for facing in FACINGS for frame in range(83,224)}
    updates={};payloads=[]
    for bank in banks:
        path=contained_media_path(packed,bank['file'])
        if hashlib.sha256(path.read_bytes()).hexdigest()!=bank['sha256'] or len(bank['checks'])!=564:
            raise ValueError('Fracture packet hash or checks differ')
        with ZipFile(path) as archive:
            if set(archive.namelist())!=expected or len(archive.namelist())!=len(expected):
                raise ValueError('Fracture packet phases differ')
            for member in expected:
                raw=gzip.decompress(archive.read(member))
                if len(raw)<8:raise ValueError('Truncated fracture packet')
                width,height,_,_=struct.unpack_from('<HHhh',raw)
                if not width*height or max(width,height)>512 or len(raw)!=8+width*height*11:
                    raise ValueError('Fracture packet dimensions differ')
        identity=f"wall.{bank['name']}.destruction.{bank['side']}"
        if assets[identity]['phases']['impact']['frames']!=141:raise ValueError('Original fracture duration differs')
        runtime='game/assets/wall_media/material-surfaces/'+bank['file']
        payloads.append((bank['file'],runtime,bank['sha256']))
        storage={'phases':{'impact':{'surfaceFrames':{'componentsByFacing':{facing:[{'archive':{
            'file':runtime,'memberPattern':facing+'/{frame:03d}.bin.gz'},'pivot':[256,311.425626],'blendMode':'normal'}] for facing in FACINGS},
            'frameIndices':list(range(83,224)),'bounds':[-40,40],'verticalScale':1.224744871391589,
            'positionScale':1/CELL,'coordinateBasis':'material_rest_xyz'}}}}
        ProjectileStorage.model_validate_json(json.dumps(storage));updates[identity]=storage
    metadata={f'stone-v{variant}-receipt.json':(packed/f'stone-v{variant}-receipt.json').read_bytes() for variant in range(3)}
    for name,raw in metadata.items():
        target=preserved/name
        if target.exists() and target.read_bytes()!=raw:raise ValueError('Preserved fracture receipt differs')
    installed=install_verified_payloads(packed,tuple(payloads),preserved=preserved,production=production,repo=repo)
    for name,raw in metadata.items():(preserved/name).write_bytes(raw)
    bindings['projectileStorage'].update(updates);(bundle/'bindings.json').write_text(json.dumps(bindings,indent=2)+'\n')
    public={'source':str(source),'preserved':str(preserved),'receipts':receipts,'files':installed,
        'adaptation':'Original triangle material positions, original rigid transforms and unchanged RGBA; unowned cut fringes omitted'}
    (bundle/'fracture-material-source.json').write_text(json.dumps(public,indent=2)+'\n')
    return public


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('operation',choices=('pack','install','install-fracture'))
    for name in ('source','retirement','packed','preserved','production'):parser.add_argument('--'+name,type=Path)
    args=parser.parse_args()
    if args.operation=='pack':pack_solid(args.source,args.retirement,args.packed)
    elif args.operation=='install':install_solid(args.packed,preserved=args.preserved,production=args.production)
    else:install_fracture(args.packed,preserved=args.preserved,production=args.production)
