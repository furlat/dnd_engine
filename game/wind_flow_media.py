"""Original joined Wind sheets on received paths, using the shared XYZ painter."""
from dataclasses import dataclass, replace
from functools import lru_cache
from math import atan2, ceil, cos, pi, sin
from pathlib import Path

import numpy as np
import pygame

from dnd.core.presentation_geometry import WallAssemblyPresentationGeometry, WallPolyline, WallSegment
from game.animation import ActorContact, body_elevation_steps
from game.animation_types import AnimationData, AuthoredRecord, WindFlowMaterial, Color, Positive
from game.area_media import AreaMedia
from game.directed_surface import (DirectedSurface, DonorTexture, DonorMesh, donor_texture,
    rasterize_surface, repeated_texture, surface_command, source_palette_rgba)
from game.draw_commands import DrawCommand
from game.projection import Camera
from game.volume_media import ExcludedSphere


class WindTextures(AuthoredRecord):
    Wind_1_texture: DonorTexture
    Wind_2_texture_subs: DonorTexture
    Color1DGradient: DonorTexture
    sprite_sheet: DonorTexture


class WindComponents(AuthoredRecord):
    textures: WindTextures
    contact: DonorMesh


@lru_cache(maxsize=2)
def wind_components(path: Path) -> WindComponents:
    return WindComponents.model_validate_json(path.read_bytes())


class WindBlockComponents(AuthoredRecord):
    mesh: DonorMesh
    texture: str
    palette: tuple[Color, ...]
    nativeUnitsPerCell: Positive
    verticalUnitsPerCell: Positive
    count: int
    staggerSeconds: float
    durationSeconds: Positive
    scale: tuple[Positive, Positive, Positive]
    yawStepRadians: float
    baseColor: tuple[float, float, float]
    opacity: float
    sheet: tuple[int, int]


@lru_cache(maxsize=2)
def wind_block_components(path: Path) -> WindBlockComponents:
    return WindBlockComponents.model_validate_json(path.read_bytes())


@lru_cache(maxsize=2)
def _block_texture(path: Path) -> np.ndarray:
    image = pygame.image.load(path)
    return pygame.surfarray.array_alpha(image).astype(float)[...,None]/255


def wind_interception_commands(data: AnimationData, components: str,
        position: tuple[float,float], height: float, tangent: tuple[float,float],
        incoming: tuple[float,float], age_ms: float, camera: Camera, owner: str) -> tuple[DrawCommand,...]:
    """Five original WindHit meshes at the retained missile intersection."""
    source = wind_block_components(data.resources[components])
    if age_ms < 0 or age_ms >= 1000*(source.durationSeconds+(source.count-1)*source.staggerSeconds):
        return ()
    texture = _block_texture(data.resources[source.texture])
    axis = np.asarray(tangent,dtype=float);axis /= np.linalg.norm(axis)
    direction = np.asarray(incoming,dtype=float);direction /= np.linalg.norm(direction)
    side = float(direction @ np.array((-axis[1],axis[0])))
    heading = atan2(axis[1],axis[0]) + (pi if side>1e-8 or abs(side)<=1e-8 and direction@axis>0 else 0)
    def rotation(angle):
        return np.array(((cos(angle),0,sin(angle)),(0,1,0),(-sin(angle),0,cos(angle))))
    root = rotation(heading)
    base = np.array((position[0],height,position[1]))
    conversion = np.array((1/source.nativeUnitsPerCell,1/source.verticalUnitsPerCell,1/source.nativeUnitsPerCell))
    fragments = []
    for i in range(source.count):
        u = float(np.clip((age_ms/1000-i*source.staggerSeconds)/source.durationSeconds,0,1))
        opacity = float(_smooth(0,.10,u)*(1-_smooth(.55,1,u)))*source.opacity
        if opacity <= 0:
            continue
        translation = np.array(((i-2)*.20*float(_smooth(0,.5,u)),-.22+u*.9,.10+sin(i)*.04))
        points = ((np.asarray(source.mesh.vertices)*np.array(source.scale)*(1+u*.35))
            @ rotation(-i*source.yawStepRadians)+translation) @ root
        frame = int(u*(source.sheet[0]*source.sheet[1]-1))
        uv = (np.asarray(source.mesh.uv)+np.array((frame%source.sheet[0],frame//source.sheet[0])))/np.array(source.sheet)
        triangles = np.asarray(source.mesh.indices).reshape(-1,3)
        # Native cross-plane particles draw both transparent quads without
        # depth writes. A nearest-only raster of the whole cross loses one.
        for plane in range(len(triangles)//2):
            surface = rasterize_surface(base+points*conversion,uv,triangles[plane*2:plane*2+2],camera)
            if surface is None:
                continue
            rgba = repeated_texture(texture,surface.uv[...,0],surface.uv[...,1])
            alpha = rgba[...,0]*opacity*surface.owned
            fragments.append((surface,np.broadcast_to(source.baseColor,(*alpha.shape,3)),alpha,f'{owner}:gust:{i}:{plane}'))
    return _palette_commands(fragments,source.palette,camera,position,None,None,(),owner)


@dataclass(frozen=True, slots=True)
class WindSheet:
    vertices: np.ndarray
    normals: np.ndarray
    uv: np.ndarray
    indices: np.ndarray
    layer: int


def _smooth(a: float, b: float, value):
    t=np.clip((value-a)/(b-a),0,1)
    return t*t*(3-2*t)


@lru_cache(maxsize=32)
def joined_sheets(points: tuple[tuple[float,float],...], cell: float) -> tuple[tuple[WindSheet,...],np.ndarray]:
    """The source's stations, shared boundary normals and full-path arclength UV."""
    source=np.array([(x*cell,0,z*cell) for x,z in points])
    vertices=[];arcs=[];distance=0.
    for a,b in zip(source,source[1:]):
        length=float(np.linalg.norm(b-a));steps=max(1,ceil(length/cell))
        for j in range(steps):
            vertices.append(a+(b-a)*j/steps);arcs.append(distance+length*j/steps)
        distance+=length
    vertices.append(source[-1]);arcs.append(distance)
    stations=np.array(vertices);closed=np.allclose(stations[0],stations[-1]);normals=[]
    for j,p in enumerate(stations):
        previous=p-stations[max(0,j-1)];following=stations[min(len(stations)-1,j+1)]-p
        if closed and j==0:previous=stations[-1]-stations[-2]
        if closed and j==len(stations)-1:following=stations[1]-stations[0]
        if np.linalg.norm(previous)<.01:previous=following
        if np.linalg.norm(following)<.01:following=previous
        n0=np.array((-previous[2],0,previous[0]));n0/=np.linalg.norm(n0)
        n1=np.array((-following[2],0,following[0]));n1/=np.linalg.norm(n1)
        n=n0+n1;size=np.linalg.norm(n)
        # Native paths never reverse through themselves; retain zero for the
        # original degenerate sum rather than inventing a turn direction.
        if size:n/=size
        normals.append(n/max(.5,float(n@n1)))
    sheets=[]
    indices=np.array([(k,k+25,k+1,k+1,k+25,k+26) for i in range(8)
        for j in range(24) for k in (i*25+j,)]).reshape(-1,3)
    u,y=np.meshgrid(np.arange(9)/8,np.arange(25)/24,indexing='ij');u=u.ravel();y=y.ravel()
    for index,(a,b) in enumerate(zip(stations,stations[1:])):
        side=(1-u[:,None])*normals[index]+u[:,None]*normals[index+1]
        normal=side/np.maximum(np.linalg.norm(side,axis=1)[:,None],1e-9)
        center=(1-u[:,None])*a+u[:,None]*b
        arc=(1-u)*arcs[index]+u*arcs[index+1]
        uv=np.column_stack((arc/distance*np.floor(distance/cell*1.7+.5),y))
        for layer in range(3):
            shape=np.sin(y*9+(index%3)*2.1)*np.sin(pi*u)**2*.025
            p=center+np.column_stack((np.zeros_like(y),y*6.363961032,np.zeros_like(y)))
            p+=side*((layer-1)*.424264069*.40+shape)[:,None]
            sheets.append(WindSheet(p,normal,uv,indices,layer))
    return tuple(sheets),stations


def _nearest_body(points: np.ndarray, bodies: np.ndarray) -> tuple[np.ndarray,np.ndarray]:
    if not len(bodies):
        return np.zeros_like(points),np.full(points.shape[:-1],np.inf)
    distances=((points[...,None,(0,2)]-bodies[:,(0,2)])**2).sum(axis=-1)
    indices=distances.argmin(axis=-1)
    return bodies[indices],np.sqrt(np.take_along_axis(distances,indices[...,None],axis=-1)[...,0])


def _palette_commands(fragments: list[tuple[DirectedSurface,np.ndarray,np.ndarray,str]], palette: tuple[int,...], camera: Camera, center, area,
                      admitted, exclusions, owner: str) -> tuple[DrawCommand,...]:
    if not fragments:return ()
    left=min(s.origin[0] for s,_,_,_ in fragments);top=min(s.origin[1] for s,_,_,_ in fragments)
    width=max(s.origin[0]+s.owned.shape[0] for s,_,_,_ in fragments)-left
    height=max(s.origin[1]+s.owned.shape[1] for s,_,_,_ in fragments)-top
    rgb=np.zeros((width,height,3))
    for surface,color,alpha,_ in fragments:
        x,y=surface.origin[0]-left,surface.origin[1]-top
        part=(slice(x,x+alpha.shape[0]),slice(y,y+alpha.shape[1]))
        rgb[part]=color*alpha[...,None]+rgb[part]*(1-alpha[...,None])
    colors=source_palette_rgba(rgb,np.ones((width,height)),palette,sample_pixels=2*camera.zoom)[...,:3]
    commands=[]
    for surface,_,alpha,identity in fragments:
        x,y=surface.origin[0]-left,surface.origin[1]-top
        rgba=np.concatenate((colors[x:x+alpha.shape[0],y:y+alpha.shape[1]],
            np.rint(np.clip(alpha,0,1)*255).astype(np.uint8)[...,None]),axis=2)
        rgba[...,:3][rgba[...,3]==0]=0
        command=surface_command(surface,rgba,camera,center,area,identity)
        if command is not None:
            assert command.volume is not None
            commands.append(command._replace(owner=owner,world_depth_group=(owner,identity),
                volume=replace(command.volume,admitted=admitted,exclusions=exclusions)))
    return tuple(commands)


@lru_cache(maxsize=32)
def _wind_fragments(points: tuple[tuple[float,float],...], cell: float, vertical_scale: float,
        base_height: float, resource: Path, age_ms: float, applied: bool, removal_fraction: float,
        camera: Camera, admitted: tuple[tuple[int,int],...], contact_positions: tuple[tuple[float,float,float],...],
        formation_positions: tuple[tuple[float,float,float],...]):
    """Bounded pure surface cache; owner identity/lifetime stay with the caller."""
    age=max(0.,age_ms/1000);clock=age%2
    source=wind_components(resource);folder=resource.parent
    noise1=donor_texture(folder,source.textures.Wind_1_texture)
    noise2=donor_texture(folder,source.textures.Wind_2_texture_subs)
    gradient=donor_texture(folder,source.textures.Color1DGradient)
    origin=points[0];scale=np.array((1.,vertical_scale,1.))/cell
    base=np.array((origin[0],base_height,origin[1]))
    sheets,stations=joined_sheets(tuple((x-origin[0],z-origin[1]) for x,z in points),cell)
    bodies=np.array([((x-origin[0])*cell,(y-base_height)/scale[1],
        (z-origin[1])*cell) for x,y,z in contact_positions]).reshape(-1,3)
    formation_bodies=np.array([((x-origin[0])*cell,(y-base_height)/scale[1],
        (z-origin[1])*cell) for x,y,z in formation_positions]).reshape(-1,3)
    reveal=1.12*float(_smooth(0,.75,age)) if applied else 1.12
    fade=1-float(_smooth(0,1,removal_fraction));pulse=np.exp(-((age-.70)/.13)**2) if applied else 0.
    fragments=[]

    def append(vertices,uv,indices,color,identity,nearest=True):
        surface=rasterize_surface(base+vertices*scale,uv,indices,camera,nearest=nearest)
        if surface is None:return
        points3=(surface.xyz-base)/scale
        rgb,alpha=color(surface,points3)
        cells=np.floor(surface.xyz[...,(0,2)]+.5).astype(int)
        allowed=np.zeros(alpha.shape,dtype=bool)
        for x,z in admitted:allowed|=(cells[...,0]==x)&(cells[...,1]==z)
        alpha=alpha*surface.owned*allowed
        if np.any(alpha>.01):fragments.append((surface,rgb,alpha,identity))

    for index,sheet in enumerate(sheets):
        uv=sheet.uv
        wave=(.045*np.sin(uv[:,0]*2*pi+uv[:,1]*3-clock*pi)
            +.018*np.sin(uv[:,0]*4*pi+uv[:,1]*7+clock*2*pi))*_smooth(0,.2,uv[:,1])
        vertices=sheet.vertices+sheet.normals*wave[:,None]
        nearest,distance=_nearest_body(vertices,bodies)
        offset=vertices[:,(0,2)]-nearest[:,(0,2)]
        local_y=vertices[:,1]-nearest[:,1]
        clear=(1-_smooth(.30,1.50,distance))*_smooth(0,.30,local_y)*(1-_smooth(2.15,3.1,local_y))
        vertices[:,(0,2)]+=offset/np.maximum(.12,distance)[:,None]*clear[:,None]*.32

        def material(surface,points3,layer=sheet.layer):
            u,v=surface.uv[...,0],surface.uv[...,1];shift=clock+layer*.19
            n1=repeated_texture(noise1,u,v-shift)[...,0]
            n2=repeated_texture(noise2,u,2*(v+shift*1.5))[...,0]
            coordinate=np.clip(n1-n2,0,1)
            # Clamp-to-edge gradient; reuse the original linear texture sampler.
            coordinate=np.clip(coordinate,.5/gradient.shape[0],1-.5/gradient.shape[0])
            alpha=repeated_texture(gradient,coordinate,np.zeros_like(v))[...,3]
            alpha*=fade*.36*_smooth(0,.035,v)*(1-_smooth(.79,1,v))*(1-_smooth(reveal-.10,reveal,v))
            rgb=np.array((.73,.83,.89))+.14*np.clip(alpha,0,1)[...,None]
            body,distance=_nearest_body(points3,bodies);y=points3[...,1]-body[...,1]
            clear=(1-_smooth(.35,1,distance))*_smooth(.15,.50,y)*(1-_smooth(2.1,2.8,y))
            hit_body,hit_distance=_nearest_body(points3,formation_bodies)
            local_hit=1-_smooth(.35,1.8,np.sqrt(hit_distance**2+(points3[...,1]-hit_body[...,1]-1.2)**2))
            return rgb,alpha*(1-.68*clear)*(1+pulse*local_hit*.65)
        append(vertices,uv,sheet.indices,material,f'sheet:{index}')
    # The source's twelve small triangular chips ride the same continuous path.
    for index in range(12):
        slot=index*7%max(1,len(stations)-1);fraction=(index*.618)%1
        point=stations[slot]*(1-fraction)+stations[slot+1]*fraction
        u=(age*.5+index/12)%1
        point=point+np.array((.08*sin(u*6.283+index),6.363961032*u,.07*cos(u*6.283+index)))
        size=float(_smooth(0,.08,u)*(1-_smooth(.75,1,u))*(_smooth(0,.3,age) if applied else 1))
        rx,ry,rz=u*5,u*9+index,u*6
        rotation=np.array(((cos(ry),0,sin(ry)),(0,1,0),(-sin(ry),0,cos(ry)))) @ np.array(((1,0,0),(0,cos(rx),-sin(rx)),(0,sin(rx),cos(rx)))) @ np.array(((cos(rz),-sin(rz),0),(sin(rz),cos(rz),0),(0,0,1)))
        vertices=np.array(((-.035,0,0),(.035,0,0),(.018,.085,.01)))@rotation.T*size+point
        append(vertices,np.zeros((3,2)),np.array(((0,1,2),)),
            lambda s,p:(np.array((.66,.68,.61)),np.full(s.owned.shape,.6*fade*float(_smooth(0,.35,age) if applied else 1))),f'chip:{index}')
    # Formation contact belongs only to an observed initial application. Passing
    # bodies retain the quiet parting above without inventing recurring impacts.
    hit_phase=float(np.clip((age-.48)/.65,0,1)) if applied else 1.
    envelope=float(_smooth(0,.10,hit_phase)*(1-_smooth(.55,1,hit_phase)))
    if envelope>0:
        texture=donor_texture(folder,source.textures.sprite_sheet);frame=int(np.floor(hit_phase*11))
        for body_index,body in enumerate(formation_bodies):
            for index in range(2):
                rx=.12*index;ry=index*1.9+hit_phase*.18
                rotation=np.array(((cos(ry),0,sin(ry)),(0,1,0),(-sin(ry),0,cos(ry))))@np.array(((1,0,0),(0,cos(rx),-sin(rx)),(0,sin(rx),cos(rx))))
                vertices=np.array(source.contact.vertices)@rotation.T*(.18+.30*hit_phase)+body+np.array((0,1+index*.35,0))
                uv=(np.array(source.contact.uv)+np.array((frame%4,frame//4)))/np.array((4,3))
                for nearest in (False,True):
                    append(vertices,uv,np.array(source.contact.indices).reshape(-1,3),
                        lambda s,p:(np.array((.78,.87,.91)),repeated_texture(texture,s.uv[...,0],s.uv[...,1])[...,3]*envelope*.72),
                        f'contact:{body_index}:{index}:{nearest}',nearest)
    return tuple(fragments)


def wind_flow_commands(geometry: WallAssemblyPresentationGeometry, spec: WindFlowMaterial,
        data: AnimationData, age_ms: float, applied: bool, removal_fraction: float,
        camera: Camera, area: AreaMedia | None, admitted: tuple[tuple[int,int],...],
        exclusions: tuple[ExcludedSphere,...], contacts: tuple[ActorContact,...],
        formation_contacts: tuple[ActorContact,...], owner: str,
        phase: str) -> tuple[DrawCommand,...]:
    path=geometry.path
    points=(path.start,path.end) if isinstance(path,WallSegment) else path.points if isinstance(path,WallPolyline) else ()
    if len(points)<2 or removal_fraction>=1:return ()
    # The source's mature flow and debris repeat every two seconds. The tiny
    # Gaussian formation pulse has no eight-bit contribution after two seconds.
    age_ms=age_ms if applied and age_ms<2000 else 2000+round(age_ms%2000,6)
    fragments=_wind_fragments(tuple(points),spec.nativeUnitsPerCell,spec.verticalScale,
        geometry.base_height_steps,data.resources[spec.components],age_ms,applied,removal_fraction,
        camera,admitted,tuple((c.grid[0],body_elevation_steps(c,data),c.grid[1]) for c in contacts),
        tuple((c.grid[0],body_elevation_steps(c,data),c.grid[1]) for c in formation_contacts))
    named=[(surface,rgb,alpha,f'{owner}:{identity}') for surface,rgb,alpha,identity in fragments]
    commands=_palette_commands(named,spec.palette,camera,points[0],area,admitted,exclusions,owner)
    return tuple(command._replace(evidence=(owner,points[0],f'wind.flow.{phase}.native',*command.evidence)) for command in commands)
