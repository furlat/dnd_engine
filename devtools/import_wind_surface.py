"""Pack the released Wind RGBA/closest XYZ into existing surface ZIP storage."""

import gzip
import hashlib
import json
from pathlib import Path
import struct
from zipfile import ZipFile, ZIP_STORED

import numpy as np
from PIL import Image

from devtools.import_assembly_media import SOURCE_CAMERAS, WINDOWS

CELL=2.121320344
FACINGS=('E','S','W','N')


def _canvas(source: Path, bank: dict, index: int, images: dict) -> np.ndarray:
    canvas=np.zeros((512,512,4),dtype=np.uint8)
    frame=bank['frames'][index]
    if frame is None:return canvas
    page=bank['pages'][frame['page']]
    relative=page['path'] if isinstance(page,dict) else page
    if relative not in images:
        with Image.open(source/relative) as image:images[relative]=np.array(image.convert('RGBA'))
    x,y,w,h=frame['source'];ox,oy=frame['offset']
    if min(x,y,w,h,ox,oy)<0 or w==0 or h==0 or ox+w>512 or oy+h>512:
        raise ValueError('Wind crop leaves its registered canvas')
    crop=images[relative][y:y+h,x:x+w]
    if crop.shape!=(h,w,4):raise ValueError('Wind crop leaves its source page')
    canvas[oy:oy+h,ox:ox+w]=crop
    return canvas


def surface_packet(color: np.ndarray, axes: tuple[np.ndarray,...], quadrant: int,
                   minimum: tuple[float,...], extent: tuple[float,...], pivot: tuple[float,float]):
    """RGBA is unchanged; one quantized native sample supplies depth/permission."""
    valid=np.logical_and.reduce([axis[:,:,3]!=0 for axis in axes]) & (color[:,:,3]!=0)
    coordinates=[]
    for axis,low,width in zip(axes,minimum,extent,strict=True):
        raw=axis[:,:,0].astype(np.uint16)*256+axis[:,:,1]
        coordinates.append(low+raw.astype(np.float64)*(width/65535))
    x,y,z=coordinates
    cx,cz=((x,z),(-z,x),(-x,-z),(z,-x))[quadrant]
    native=np.stack((cx,y,cz),axis=2)
    encoded=np.rint((native+40)*(65535/80)).clip(0,65535).astype('>u2')
    decoded=encoded.astype(np.float64)*(80/65535)-40
    # Quantization error projected into the exact source orthographic camera.
    delta=decoded-native
    error_x=(delta[:,:,0]-delta[:,:,2])*512/(12*2**.5)
    error_y=(delta[:,:,0]+delta[:,:,2])*512/(24*2**.5)-delta[:,:,1]*512*(3**.5/2)/12
    error=np.hypot(error_x,error_y)
    max_error=float(error[valid].max()) if valid.any() else 0.
    if max_error>.1:raise ValueError('Wind packet quantization exceeds .1 source pixel')
    visible=color[:,:,3]!=0
    yy,xx=np.nonzero(visible)
    if len(xx):x0,x1,y0,y1=int(xx.min()),int(xx.max())+1,int(yy.min()),int(yy.max())+1
    else:x0=x1=y0=y1=0;x1=y1=1
    rgba=color[y0:y1,x0:x1];xyz=encoded[y0:y1,x0:x1];ownership=valid[y0:y1,x0:x1].astype(np.uint8)
    header=struct.pack('<HHhh',x1-x0,y1-y0,x0-round(pivot[0]),y0-round(pivot[1]))
    return gzip.compress(header+rgba.tobytes()+xyz.tobytes()+ownership.tobytes(),mtime=0),int(valid.sum()),max_error


def pack_wind_surface(source: Path, output: Path) -> dict:
    receipt=json.loads((source/'SPATIAL_RELEASE_RECEIPT.json').read_text())
    if receipt['revision']!='nonempty-position-v2-release-20261002' or receipt['rgbaChanged']:
        raise ValueError('Wind coordinates are not the corrected unchanged-color release')
    for name,key in (('xyz-media.json','manifestSHA256'),('xyz-validation.json','validationSHA256')):
        if hashlib.sha256((source/name).read_bytes()).hexdigest()!=receipt[key]:raise ValueError('Unpinned Wind spatial release')
    spatial=json.loads((source/'xyz-media.json').read_text());colors=json.loads((source/'media.json').read_text())
    if spatial['fps']!=32 or spatial['canvas']!=[512,512]:raise ValueError('Wind registration differs')
    if spatial['boundsMin']!=[-40,-.5,-40] or spatial['boundsExtent']!=[80,8,80]:raise ValueError('Wind coordinate bounds differ')
    for bank in spatial['banks'].values():
        for axis in bank['axes']:
            for page in axis['pages']:
                path=(source/page['path']).resolve()
                if not path.is_relative_to(source.resolve()) or hashlib.sha256(path.read_bytes()).hexdigest()!=page['sha256']:
                    raise ValueError('Unverified Wind coordinate page')
    output.mkdir(parents=True,exist_ok=False)
    registrations={};samples=0;maximum=0.;indices=tuple(i for _,first,count in WINDOWS for i in range(first,first+count))
    for direction in range(8):
        name=f'wind_d{direction}';path=output/f'{name}.zip';images={}
        with ZipFile(path,'w',compression=ZIP_STORED) as archive:
            for q,original in enumerate(SOURCE_CAMERAS):
                bank=colors['banks'][f'module/d{direction}/q{original}'];positions=spatial['banks'][f'module/d{direction}/q{original}']
                for i in indices:
                    rgba=_canvas(source,bank,i,images)
                    axes=tuple(_canvas(source,axis,i,images) for axis in positions['axes'])
                    packet,nonempty,error=surface_packet(rgba,axes,q,tuple(spatial['boundsMin']),tuple(spatial['boundsExtent']),tuple(bank['pivot']))
                    archive.writestr(f'{FACINGS[q]}/{i:03d}.bin.gz',packet)
                    samples+=nonempty;maximum=max(maximum,error)
        registrations[name]={'file':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'bytes':path.stat().st_size}
    if samples==0:raise ValueError('Wind maps are empty')
    result={'release':receipt,'programs':registrations,'valid_samples':samples,'max_added_projection_error':maximum,
        'rgba':'unchanged','positionScale':1/CELL,'verticalScale':1.224744871391589,'bounds':[-40,40]}
    (output/'packing-receipt.json').write_text(json.dumps(result,indent=2)+'\n')
    return result
