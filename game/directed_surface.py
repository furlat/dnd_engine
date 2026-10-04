"""Pure native XYZ/UV triangles for the existing pixel-depth compositor."""
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal
from typing import Callable

import numpy as np
import pygame

from game.area_media import AreaMedia
from game.animation_types import AuthoredRecord
from game.draw_commands import DrawCommand
from game.volume_media import SurfaceVolume

from game.projection import Camera, project_screen, painter_key


class DonorTexture(AuthoredRecord):
    file: str
    size: tuple[int, int]
    original_format: int


class DonorMesh(AuthoredRecord):
    vertices: tuple[tuple[float, float, float], ...]
    uv: tuple[tuple[float, float], ...]
    indices: tuple[int, ...]


@lru_cache(maxsize=24)
def donor_texture_pixels(path: Path, size: tuple[int,int], original_format: int) -> np.ndarray:
    """Original base mip with source-color decoding; float gradients stay linear."""
    width,height=size
    image=np.frombuffer(path.read_bytes(),dtype='<f4',count=width*height*4).reshape(height,width,4).transpose(1,0,2).copy()
    if original_format not in (8,9,10,11,12,13,14,15,16):
        rgb=image[...,:3]
        image[...,:3]=np.where(rgb<=.04045,rgb/12.92,((rgb+.055)/1.055)**2.4)
    return image


def donor_texture(folder: Path, source: DonorTexture) -> np.ndarray:
    path=(folder/source.file).resolve()
    if not path.is_relative_to(folder.resolve()):
        raise ValueError('Donor texture leaves its registered resource folder')
    return donor_texture_pixels(path,source.size,source.original_format)


@dataclass(frozen=True, slots=True)
class DirectedSurface:
    origin: tuple[int, int]
    xyz: np.ndarray
    uv: np.ndarray
    owned: np.ndarray
    normals: np.ndarray | None = None
    colors: np.ndarray | None = None


def rasterize_surface(vertices: np.ndarray, uv: np.ndarray, triangles: np.ndarray,
                      camera: Camera, *, nearest: bool = True,
                      normals: np.ndarray | None = None,
                      colors: np.ndarray | None = None,
                      admit_uv: Callable[[np.ndarray], np.ndarray] | None = None) -> DirectedSurface | None:
    screen = np.array([project_screen((p[0], p[2]), camera, elevation_steps=p[1]) for p in vertices])
    # Even pixel registration preserves the original two-by-two palette pass.
    left, top = (max(0, int(v)//2*2) for v in np.floor(screen.min(axis=0)))
    right, bottom = (int(v)+2 for v in np.ceil(screen.max(axis=0)))
    right, bottom = min(camera.viewport[0], right), min(camera.viewport[1], bottom)
    if right <= left or bottom <= top:
        return None
    shape = right-left, bottom-top
    xyz = np.zeros((*shape, 3), dtype=np.float32)
    mapped = np.zeros((*shape, 2), dtype=np.float32)
    owned = np.zeros(shape, dtype=bool)
    normal_map = np.zeros((*shape,3),dtype=np.float32) if normals is not None else None
    color_map = np.zeros((*shape,colors.shape[1]),dtype=np.float32) if colors is not None else None
    attributes = np.column_stack((vertices, uv, normals)) if normals is not None else np.column_stack((vertices,uv))
    color_offset = attributes.shape[1]
    if colors is not None:attributes = np.column_stack((attributes,colors))
    depths = np.full(shape, -np.inf if nearest else np.inf)
    signs = ((1,1),(1,-1),(-1,-1),(-1,1))[camera.quadrant]
    offset=0
    while offset<len(triangles):
        stop=min(offset+512,len(triangles))
        # Flatten each triangle's own pixel rectangle. A union rectangle would
        # multiply work for separated triangles and thin joined sheets.
        while True:
            indices=triangles[offset:stop]
            triangle=screen[indices]
            lo=np.maximum(np.floor(triangle.min(axis=1)).astype(int),(left,top))
            hi=np.minimum(np.ceil(triangle.max(axis=1)).astype(int)+1,(right,bottom))
            sizes=np.maximum(hi-lo,0);counts=sizes.prod(axis=1)
            if stop-offset>1 and counts.mean()>512:
                stop=offset+1
                continue
            if stop-offset<=1 or counts.sum()<=262144:break
            stop=offset+max(1,(stop-offset)//2)
        offset=stop
        a,b,c=triangle[:,0],triangle[:,1],triangle[:,2]
        denominator=(b[:,1]-c[:,1])*(a[:,0]-c[:,0])+(c[:,0]-b[:,0])*(a[:,1]-c[:,1])
        valid=(np.abs(denominator)>=1e-8)&(counts>0)
        if not np.any(valid):continue
        indices=indices[valid];lo=lo[valid];sizes=sizes[valid];counts=counts[valid]
        a=a[valid];b=b[valid];c=c[valid];denominator=denominator[valid]
        owners=np.repeat(np.arange(len(indices)),counts)
        starts=np.cumsum(counts)-counts
        local=np.arange(int(counts.sum()))-starts[owners]
        px=lo[owners,0]+local//sizes[owners,1]
        py=lo[owners,1]+local%sizes[owners,1]
        x,y=px+.5,py+.5
        a=a[owners];b=b[owners];c=c[owners];denominator=denominator[owners]
        u=((b[:,1]-c[:,1])*(x-c[:,0])+(c[:,0]-b[:,0])*(y-c[:,1]))/denominator
        v=((c[:,1]-a[:,1])*(x-c[:,0])+(a[:,0]-c[:,0])*(y-c[:,1]))/denominator
        w=1-u-v
        inside=(u>=0)&(v>=0)&(w>=0)
        if not np.any(inside):continue
        owners=owners[inside];u=u[inside];v=v[inside];w=w[inside]
        selected_indices=indices[owners]
        values=(u[:,None]*attributes[selected_indices[:,0]]
            +v[:,None]*attributes[selected_indices[:,1]]+w[:,None]*attributes[selected_indices[:,2]])
        pixels=(px[inside]-left)*shape[1]+py[inside]-top
        if admit_uv is not None:
            # Original cutout shaders discard fragments before writing depth.
            # Their pure UV predicate cannot alter geometry or winner ordering.
            admitted=admit_uv(values[:,3:5])
            if not np.any(admitted):continue
            values=values[admitted];pixels=pixels[admitted]
        depth=values[:,0]*signs[0]+values[:,2]*signs[1]+values[:,1]
        flat_depth=depths.ravel()
        if len(indices)==1:
            chosen=np.flatnonzero(depth>=flat_depth[pixels] if nearest else depth<=flat_depth[pixels])
            flat_depth[pixels[chosen]]=depth[chosen]
        else:
            if nearest:np.maximum.at(flat_depth,pixels,depth)
            else:np.minimum.at(flat_depth,pixels,depth)
            winners=np.flatnonzero(depth==flat_depth[pixels])
            # Reverse unique selects the original last triangle at equal depth.
            _,last=np.unique(pixels[winners][::-1],return_index=True)
            chosen=winners[::-1][last]
        pixels=pixels[chosen];values=values[chosen]
        xyz.reshape(-1,3)[pixels]=values[:,:3]
        mapped.reshape(-1,2)[pixels]=values[:,3:5]
        if normal_map is not None:normal_map.reshape(-1,3)[pixels]=values[:,5:8]
        if color_map is not None:color_map.reshape(-1,color_map.shape[2])[pixels]=values[:,color_offset:]
        owned.ravel()[pixels]=True
    return DirectedSurface((left,top),xyz,mapped,owned,normal_map,color_map)


def repeated_texture(texture: np.ndarray, u: np.ndarray, v: np.ndarray) -> np.ndarray:
    """Original repeat+linear sampler, including texels across the wrap edge."""
    x,y = u*texture.shape[0]-.5,v*texture.shape[1]-.5
    ix,iy = np.floor(x).astype(int),np.floor(y).astype(int)
    fx,fy = (x-ix)[...,None],(y-iy)[...,None]
    a,b = ix%texture.shape[0],iy%texture.shape[1]
    c,d = (ix+1)%texture.shape[0],(iy+1)%texture.shape[1]
    return (texture[a,b]*(1-fx)+texture[c,b]*fx)*(1-fy)+(texture[a,d]*(1-fx)+texture[c,d]*fx)*fy


def palette_blocks(energy: np.ndarray, alpha: np.ndarray, palette: tuple[int,...]) -> np.ndarray:
    """Original alpha-weighted two-pixel source palette quantization."""
    width,height = alpha.shape
    # Source render buffers are eight-bit before the authored palette pass.
    a = np.rint(np.clip(alpha,0,1)*255)
    linear = np.maximum(energy,0)
    framebuffer = np.where(linear<=.0031308,linear*12.92,1.055*linear**(1/2.4)-.055)
    e = np.rint(np.clip(framebuffer,0,1)*255)/255
    padding = ((0,width%2),(0,height%2))
    weights = np.pad(a,padding).reshape((width+1)//2,2,(height+1)//2,2).sum(axis=(1,3))
    sums = np.pad(a*e,padding).reshape((width+1)//2,2,(height+1)//2,2).sum(axis=(1,3))
    average = np.divide(sums,weights,out=np.zeros_like(sums),where=weights>0)
    selected = np.clip(np.floor(average**1.15*(len(palette)-1)+.5).astype(int),0,len(palette)-1)
    colors = np.array([((c>>16)&255,(c>>8)&255,c&255) for c in palette],dtype=np.uint8)
    rgb = np.repeat(np.repeat(colors[selected],2,axis=0),2,axis=1)[:width,:height]
    rgba = np.concatenate((rgb,a.astype(np.uint8)[...,None]),axis=2)
    rgba[...,:3][a==0]=0
    return rgba


def surface_command(surface: DirectedSurface, rgba: np.ndarray, camera: Camera,
                     center: tuple[float,float], area: AreaMedia | None, identity: str) -> DrawCommand | None:
    if not np.any(rgba[...,3]):
        return None
    image = pygame.Surface(rgba.shape[:2],pygame.SRCALPHA)
    pygame.surfarray.pixels3d(image)[:] = rgba[...,:3]
    pygame.surfarray.pixels_alpha(image)[:] = rgba[...,3]
    dx,dz = surface.xyz[...,0]-center[0],surface.xyz[...,2]-center[1]
    rx,rz = ((dx,dz),(-dz,dx),(-dx,-dz),(dz,-dx))[camera.quadrant]
    local = np.stack((rx,surface.xyz[...,1],rz),axis=2)
    volume = SurfaceVolume(center,0,0,local,surface.owned.astype(np.uint8),1,
        boundaries=area.boundaries if area else (),solids=area.solids if area else (),
        supports=area.supports if area else (),resolved_occupancy=True)
    midpoint = surface.xyz[surface.owned].mean(axis=0)
    key = painter_key((float(midpoint[0]),float(midpoint[2])),elevation_steps=float(midpoint[1]),
        quadrant=camera.quadrant,role='projectile',identity=identity)
    return DrawCommand(key,image,surface.origin,0,(identity,'native_directed_surface'),volume=volume)


def _srgb_lab(rgb: np.ndarray) -> np.ndarray:
    """Original Godot CIE76 postprocess conversion, with its D65 white point."""
    linear=np.where(rgb<=.04045,rgb/12.92,((rgb+.055)/1.055)**2.4)
    xyz=linear @ np.array(((.4124564,.2126729,.0193339),
        (.3575761,.7151522,.1191920),(.1804375,.0721750,.9503041)))
    xyz/=np.array((.95047,1.,1.08883))
    f=np.where(xyz>.00885645167,np.cbrt(xyz),7.78703703704*xyz+16/116)
    return np.stack((116*f[...,1]-16,500*(f[...,0]-f[...,1]),200*(f[...,1]-f[...,2])),axis=-1)


def source_palette_rgba(rgb: np.ndarray, alpha: np.ndarray, palette: tuple[int,...], *,
        sample_pixels: float = 2, space: Literal['rgb','cie76'] = 'rgb', boost: float = 1.,
        alpha_energy_ceiling: float | None = None) -> np.ndarray:
    """Sample the original palette in the distance space declared by its source."""
    rgb=np.broadcast_to(rgb,(*alpha.shape,3))
    framebuffer=np.where(rgb<=.0031308,rgb*12.92,1.055*np.maximum(rgb,0)**(1/2.4)-.055)
    framebuffer=np.rint(np.clip(framebuffer,0,1)*255)/255
    width,height=alpha.shape
    step=max(1.,sample_pixels)
    xs=np.minimum((np.floor(np.arange(width)/step)*step+step/2).astype(int),width-1)
    ys=np.minimum((np.floor(np.arange(height)/step)*step+step/2).astype(int),height-1)
    sample=framebuffer[xs[:,None],ys[None,:]]
    colors=np.array([((c>>16)&255,(c>>8)&255,c&255) for c in palette],dtype=np.uint8)
    quantized=np.clip(sample*boost,0,1)
    values=colors/255
    if space=='cie76':
        quantized=_srgb_lab(quantized)
        values=_srgb_lab(values)
    indices=((quantized[...,None,:]-values)**2).sum(axis=3).argmin(axis=2)
    if alpha_energy_ceiling is not None:
        energy=np.clip(sample.max(axis=2)/alpha_energy_ceiling,0,1)
        alpha=alpha*energy*energy*(3-2*energy)
    rgba=np.concatenate((colors[indices],np.rint(np.clip(alpha,0,1)*255).astype(np.uint8)[...,None]),axis=2)
    rgba[alpha<=.01 if alpha_energy_ceiling is not None else alpha<.01]=0
    return rgba

