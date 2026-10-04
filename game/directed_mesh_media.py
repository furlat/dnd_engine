"""Original Darkness donor meshes, evaluated on received source/target geometry."""

from functools import lru_cache
from math import cos, pi, sin
from pathlib import Path
from typing import Annotated

import numpy as np
from pydantic import Field

from game.animation import CastTimeline, CastSample, body_elevation_steps
from game.animation_types import AuthoredRecord, StudioDarknessMeshDelivery
from game.area_media import AreaMedia
from game.directed_surface import (DirectedSurface, DonorTexture, DonorMesh, donor_texture,
    rasterize_surface, repeated_texture, surface_command)
from game.draw_commands import DrawCommand
from game.projection import Camera


class DonorParameters(AuthoredRecord):
    Fire_Scale: tuple[float, float]
    Fire_Speed: tuple[float, float]
    Color_Dissipation: float
    Dissapear_Step: float
    Proximity_Fade: float


class DonorTextures(AuthoredRecord):
    Fire_Texture: DonorTexture
    Gradient_Substract: DonorTexture
    Color_1D_Gradient: DonorTexture


class DonorLayer(DonorMesh):
    name: str
    transform: Annotated[tuple[tuple[float, float, float], ...], Field(min_length=4,max_length=4)]
    parameters: DonorParameters
    textures: DonorTextures


class DarknessGeometry(AuthoredRecord):
    scale: tuple[float, float, float]
    meshes: Annotated[tuple[DonorLayer, ...], Field(min_length=3,max_length=3)]


@lru_cache(maxsize=4)
def load_darkness_geometry(path: Path) -> tuple[DarknessGeometry, DonorMesh]:
    return (DarknessGeometry.model_validate_json(path.read_bytes()),
        DonorMesh.model_validate_json((path.parent/'splinter.json').read_bytes()))


def preload_darkness_media(path: Path) -> None:
    geometry,_=load_darkness_geometry(path)
    for layer in geometry.meshes:
        for texture in (layer.textures.Fire_Texture,layer.textures.Gradient_Substract,layer.textures.Color_1D_Gradient):
            donor_texture(path.parent,texture)


def _smooth(begin: float,end: float,value: float) -> float:
    t=max(0.,min(1.,(value-begin)/(end-begin)))
    return t*t*(3-2*t)


def _palette(energy: np.ndarray,alpha: np.ndarray,palette: tuple[int,...]) -> np.ndarray:
    """Finger's original lower-right sample per two-pixel palette block."""
    width,height=alpha.shape
    x=np.minimum(np.arange((width+1)//2)*2+1,width-1)
    y=np.minimum(np.arange((height+1)//2)*2+1,height-1)
    sampled=np.rint(np.clip(energy[np.ix_(x,y)],0,1)*255)/255
    index=np.clip(np.floor(sampled**1.15*(len(palette)-1)+.5).astype(int),0,len(palette)-1)
    colors=np.array([((v>>16)&255,(v>>8)&255,v&255) for v in palette],dtype=np.uint8)
    rgb=np.repeat(np.repeat(colors[index],2,axis=0),2,axis=1)[:width,:height]
    a=np.rint(np.clip(alpha,0,1)*255).astype(np.uint8)
    rgba=np.concatenate((rgb,a[...,None]),axis=2)
    rgba[...,:3][a==0]=0
    return rgba


def _material(layer:DonorLayer,surface:DirectedSurface,folder:Path,age:float,envelope:float)->tuple[np.ndarray,np.ndarray]:
    params=layer.parameters
    uv=surface.uv
    moving=uv*np.array(params.Fire_Scale)+age*np.array(params.Fire_Speed)
    fire=repeated_texture(donor_texture(folder,layer.textures.Fire_Texture),moving[...,0],moving[...,1])[...,0]
    subtract=repeated_texture(donor_texture(folder,layer.textures.Gradient_Substract),uv[...,0],uv[...,1])[...,0]
    difference=fire-subtract
    coordinate=np.maximum(0,difference)**params.Color_Dissipation
    color=repeated_texture(donor_texture(folder,layer.textures.Color_1D_Gradient),coordinate,np.zeros_like(coordinate))
    # The isolated accepted source has no opaque depth obstacle. Real world
    # obstruction remains the existing XYZ compositor's responsibility.
    alpha=color[...,3]*(difference>=params.Dissapear_Step)*envelope*surface.owned
    return np.maximum(color[...,:3].max(axis=2),0),alpha


def _composite_palette(fragments: list[tuple[DirectedSurface, np.ndarray, np.ndarray, str]],
                       palette: tuple[int, ...], camera: Camera, center: tuple[float, float],
                       area: AreaMedia | None) -> tuple[DrawCommand, ...]:
    """Apply the original postprocess once after the donor layers combine.

    Every emitted fragment keeps its own real XYZ and alpha. Sharing the final
    palette color preserves that composite while the ordinary world compositor
    can still clip each mesh surface against the received scene.
    """
    if not fragments:
        return ()
    left = min(row[0].origin[0] for row in fragments)
    top = min(row[0].origin[1] for row in fragments)
    width = max(row[0].origin[0]+row[0].owned.shape[0] for row in fragments)-left
    height = max(row[0].origin[1]+row[0].owned.shape[1] for row in fragments)-top
    energy = np.zeros((width, height))
    alpha = np.zeros((width, height))
    for surface, linear, opacity, _ in fragments:
        x, y = surface.origin[0]-left, surface.origin[1]-top
        slices = slice(x,x+opacity.shape[0]),slice(y,y+opacity.shape[1])
        energy[slices] = linear*opacity+energy[slices]*(1-opacity)
        alpha[slices] = opacity+alpha[slices]*(1-opacity)
    # The transparent Godot viewport stores the blended color before its
    # eight-bit sRGB image and the lower-right palette sample.
    encoded = np.where(energy<=.0031308,energy*12.92,1.055*energy**(1/2.4)-.055)
    rgba = _palette(encoded,alpha,palette)
    commands = []
    for surface, _, opacity, identity in fragments:
        x, y = surface.origin[0]-left, surface.origin[1]-top
        selected = rgba[x:x+opacity.shape[0],y:y+opacity.shape[1]].copy()
        selected[...,3] = np.rint(np.clip(opacity,0,1)*255).astype(np.uint8)
        command = surface_command(surface,selected,camera,center,area,identity)
        if command is not None:
            commands.append(command)
    return tuple(commands)


def _source(timeline:CastTimeline,spec:StudioDarknessMeshDelivery)->np.ndarray:
    row=timeline.data.rig.AUTHORED_PROJECTILE_ROW_ORDER.index(timeline.facing)
    yaw=3*pi/4-row*pi/4
    x,y,z=spec.sourceOffsetNativeXYZ
    owner=timeline.source.caster
    return np.array((owner.grid[0]+(x*cos(yaw)+z*sin(yaw))/spec.nativeUnitsPerCell,
        body_elevation_steps(owner,timeline.data)+y/spec.nativeUnitsPerCell*spec.verticalScale,
        owner.grid[1]+(-x*sin(yaw)+z*cos(yaw))/spec.nativeUnitsPerCell))


def darkness_mesh_commands(timeline:CastTimeline,sample:CastSample,camera:Camera,
                            area:AreaMedia|None,target_points:tuple[np.ndarray,...])->tuple[DrawCommand,...]:
    spec=timeline.recipe.directed
    assert spec is not None and spec.material=='darkness_mesh'
    path=timeline.data.resources[spec.geometry]
    geometry,splinter=load_darkness_geometry(path)
    source=_source(timeline,spec)
    native_scale=np.array((1.,spec.verticalScale,1.))/spec.nativeUnitsPerCell
    commands=[]
    for application,target in zip(timeline.applications,target_points,strict=True):
        elapsed=sample.media_elapsed_ms-application.travel_start_ms
        duration=max(1.,application.travel_end_ms-application.travel_start_ms)
        age=(1.10+elapsed/1000 if elapsed<0 else
            1.10+elapsed/duration*.65 if elapsed<=duration else 1.75+(elapsed-duration)/1000)
        if not 1.08<age<1.84:
            continue
        axis=(target-source)/native_scale
        axis/=max(float(np.linalg.norm(axis)),1e-9)
        right=np.cross(axis,np.array((0.,1.,0.)))
        if np.linalg.norm(right)<1e-9:
            right=np.array((1.,0.,0.))
        right/=np.linalg.norm(right)
        up=np.cross(right,axis)
        basis=np.array((right,up,-axis))
        head=source+(target-source)*np.clip((age-1.10)/.65,0,1)
        envelope=_smooth(1.08,1.12,age)*(1-_smooth(1.75,1.84,age))
        identity=f'{timeline.source.root_event_uuid}:{application.source.application_id}:darkness'
        fragments: list[tuple[DirectedSurface, np.ndarray, np.ndarray, str]] = []
        # Source render_priority places the noisy inner layer behind the two
        # zero-priority shells. Each cull-disabled shell keeps both surfaces.
        layers=(geometry.meshes[1],geometry.meshes[0],geometry.meshes[2])
        for layer in layers:
            transform=np.array(layer.transform)
            local=(np.array(layer.vertices)@transform[:3]+transform[3])*np.array(geometry.scale)
            vertices=head+(local@basis)*native_scale
            uv=np.array(layer.uv);triangles=np.array(layer.indices).reshape(-1,3)
            for nearest in (False,True):
                surface=rasterize_surface(vertices,uv,triangles,camera,nearest=nearest)
                if surface is None:
                    continue
                energy,alpha=_material(layer,surface,path.parent,age,envelope)
                fragments.append((surface,energy,alpha,identity+':'+layer.name+(':front' if nearest else ':back')))
        for index in range(30):
            lag=index*.012
            if not 1.10+lag<age<1.82:
                continue
            at=np.clip((age-1.10-lag)/.65,0,1)
            angle=index*2.399963+age*8
            radius=.06+(index%4)*.028
            center=source+(target-source)*at+(right*sin(angle)+up*cos(angle))*radius*native_scale
            local=np.array(splinter.vertices)
            # Godot look_at then rotate_object_local(RIGHT,PI/2).
            rotated=np.column_stack((local[:,0],-local[:,2],local[:,1]))
            vertices=center+(rotated@basis)*native_scale
            surface=rasterize_surface(vertices,np.array(splinter.uv),np.array(splinter.indices).reshape(-1,3),camera)
            if surface is None:
                continue
            linear=.55+.35*surface.uv[...,1]
            fragments.append((surface,linear,surface.owned*.90*envelope,identity+':splinter:'+str(index)))
        commands.extend(_composite_palette(fragments,spec.palette,camera,timeline.source.caster.grid,area))
    return tuple(commands)
