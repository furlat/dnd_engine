"""Rasterize delivered solid geometry states into original material coordinates.

This is an offline coordinate export. It never shades or invents an RGBA pixel.
Original meshes, rigid transforms, spawn transforms and camera registration own
all coordinates; source alpha remains unchanged in the production packet.
"""
import argparse
import gzip
import hashlib
import json
from math import sqrt
from pathlib import Path
import struct
from zipfile import ZipFile,ZIP_STORED

import numpy as np

from devtools.import_wind_surface import _canvas,CELL
from devtools.import_assembly_media import SOURCE_CAMERAS
from devtools.media_delivery import contained_media_path

FACINGS=('E','S','W','N')


def _transform(vertices,transform):
    matrix=np.asarray(transform,float)
    return vertices@matrix[:3]+matrix[3]


def _camera(points: np.ndarray,direction:int,quadrant:int):
    x,y,z=points[:,0],points[:,1],points[:,2]
    x,z=((x,z),(z,-x),(-x,-z),(-z,x))[direction]
    x,z=((x,z),(-z,x),(-x,-z),(z,-x))[quadrant]
    return np.stack((x,y,z),axis=1)


def _rest_transforms(document):
    result={row['name']:row['ownerLocalTransform'] for row in document['states'][47]['objects']}
    first=next(state for state in document['states'] if len(state['objects'])>len(result))
    fragments=[row for row in first['objects'] if row['name'] not in result]
    if len(fragments)!=24:raise ValueError('Original fracture body count differs')
    for i,row in enumerate(fragments):
        vertices=np.concatenate([surface['vertices'] for surface in document['meshes'][row['mesh']]['surfaces']])
        low=vertices.min(axis=0);extent=vertices.max(axis=0)-low
        size=np.array((.28+(i%3)*.08,.26+(i%4)*.04,.12+(i%2)*.09))
        scale=size/extent
        # Literal source shatter(): six columns, four rows, unrotated rigid
        # body plus its centered donor mesh. No later physics state is a rest pose.
        spawn=np.array((((i%6)+.5)/6*CELL*2-CELL,((i//6)+.5)/4*CELL*2,CELL*.5))
        result[row['name']]=[*np.diag(scale),spawn-(low+extent*.5)*scale]
    return result


def raster_material(document,frame,direction,quadrant):
    rest=_rest_transforms(document)
    depth=np.full((512,512),-np.inf);coordinates=np.zeros((512,512,3),float)
    current=np.zeros_like(coordinates)
    for row in document['states'][frame]['objects']:
        if not row['visible'] or row['opacity']<=.001:continue
        for surface in document['meshes'][row['mesh']]['surfaces']:
            if surface['primitive']!=3:raise ValueError('Solid source is not native triangles')
            vertices=np.asarray(surface['vertices'],float)
            moved=_camera(_transform(vertices,row['ownerLocalTransform']),direction,quadrant)
            material=_camera(_transform(vertices,rest[row['name']]),direction,quadrant)
            pixels=np.stack((256+(moved[:,0]-moved[:,2])*512/(12*sqrt(2)),
                311.425626+(moved[:,0]+moved[:,2])*512/(24*sqrt(2))-moved[:,1]*512*sqrt(3)/24),axis=1)
            indices=surface['indices'] or list(range(len(vertices)))
            for ids in np.asarray(indices).reshape(-1,3):
                a,b,c=pixels[ids];area=(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
                if abs(area)<1e-8:continue
                low=np.maximum(0,np.floor(np.minimum.reduce((a,b,c))-.5).astype(int))
                high=np.minimum(512,np.ceil(np.maximum.reduce((a,b,c))+.5).astype(int))
                if np.any(high<=low):continue
                yy,xx=np.mgrid[low[1]:high[1],low[0]:high[0]]
                px,py=xx+.5-a[0],yy+.5-a[1]
                w1=(px*(c[1]-a[1])-py*(c[0]-a[0]))/area
                w2=((b[0]-a[0])*py-(b[1]-a[1])*px)/area
                weights=np.stack((1-w1-w2,w1,w2),axis=2)
                world=weights@moved[ids]
                distance=world[:,:,0]+world[:,:,2]+world[:,:,1]*sqrt(2)
                region=np.s_[low[1]:high[1],low[0]:high[0]]
                keep=(weights.min(axis=2)>=-1e-7)&(world[:,:,1]>=0)&(distance>depth[region])
                depth[region][keep]=distance[keep]
                coordinates[region][keep]=(weights@material[ids])[keep]
                current[region][keep]=world[keep]
    return coordinates,np.isfinite(depth),current


def pack_material(source:Path,output:Path,variant:int):
    manifest=json.loads((source/'media.json').read_text())
    geometry=json.loads((source/'geometry-source-media.json').read_text())['banks'][f'stone-v{variant}']
    path=contained_media_path(source,geometry['path'])
    if hashlib.sha256(path.read_bytes()).hexdigest()!=geometry['sha256']:raise ValueError('Changed original geometry states')
    document=json.loads(path.read_text())
    if any('void vertex(' in row['shader'] for row in document['materials'].values()):
        raise ValueError('This export requires the original unmodified solid vertices')
    output.mkdir(parents=True,exist_ok=True);banks=[]
    paths={(direction,side):output/f'stone_v{variant}_d{direction}_{side}.zip'
        for direction in range(4) for side in ('back','front')}
    archives={key:ZipFile(path,'w',compression=ZIP_STORED) for key,path in paths.items()}
    checks={key:[] for key in paths};images={}
    try:
        # Four owner/camera pairs share each exact relative view. Reuse the
        # source geometry raster, retaining each original bank's own RGBA.
        for orientation in range(4):
            for frame in range(83,224):
                rest,owned,_current=raster_material(document,frame,orientation,0)
                encoded=np.rint((rest+40)*65535/80).clip(0,65535).astype('>u2')
                for direction in range(4):
                    q=(direction-orientation)%4;original_q=SOURCE_CAMERAS[q]
                    for side in ('back','front'):
                        bank=manifest['banks'][f'stone-v{variant}-lifecycle/d{direction}/q{original_q}/{side}']
                        rgba=_canvas(source,bank,frame,images);visible=rgba[:,:,3]>0
                        yy,xx=np.nonzero(visible)
                        x0,x1,y0,y1=(int(xx.min()),int(xx.max())+1,int(yy.min()),int(yy.max())+1) if len(xx) else (0,1,0,1)
                        valid=owned&visible
                        header=struct.pack('<HHhh',x1-x0,y1-y0,x0-256,y0-round(311.425626))
                        packet=header+rgba[y0:y1,x0:x1].tobytes()+encoded[y0:y1,x0:x1].tobytes()+valid[y0:y1,x0:x1].astype(np.uint8).tobytes()
                        archives[direction,side].writestr(f'{FACINGS[q]}/{frame:03d}.bin.gz',gzip.compress(packet,mtime=0))
                        checks[direction,side].append({'camera':q,'frame':frame,'totalAlpha':int(rgba[:,:,3].sum()),
                            'unownedAlpha':int(rgba[:,:,3][~owned].sum()),'ownedPixels':int(valid.sum())})
            print('stone',variant,'relative view',orientation,'complete',flush=True)
            images.clear()
    finally:
        for archive in archives.values():archive.close()
    banks.extend({'name':f'stone_v{variant}_d{direction}','side':side,'file':path.name,
        'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'checks':checks[direction,side]}
        for (direction,side),path in paths.items())
    receipt={'geometrySource':geometry,'originalRGBA':'unchanged','coordinateBasis':'material_rest_xyz',
        'bounds':[-40,40],'positionScale':1/CELL,'banks':banks}
    (output/f'stone-v{variant}-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--variant',type=int,choices=range(3),required=True);args=parser.parse_args()
    pack_material(args.source,args.output,args.variant)
