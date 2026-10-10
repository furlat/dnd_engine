"""Original triple-plane plasma, native spheres and exported source particles."""
from functools import lru_cache
from pathlib import Path
from math import pi

import numpy as np
from pydantic import BaseModel, ConfigDict

from game.directed_contacts import recorded_surface_contact
from game.animation import ActorContact, ApplicationTimeline, CastSample, CastTimeline, ObjectContact
from game.animation_types import StudioPlasmaTrailDelivery
from game.area_media import AreaMedia
from game.directed_surface import DirectedSurface, rasterize_surface, repeated_texture, surface_command
from game.draw_commands import DrawCommand
from game.projection import Camera


class PlasmaParticle(BaseModel):
    model_config = ConfigDict(extra='forbid',frozen=True)
    origin: tuple[float,float,float]
    velocity: tuple[float,float,float]


class PlasmaParticles(BaseModel):
    model_config = ConfigDict(extra='forbid',frozen=True)
    flight: tuple[tuple[float,float,float],...]
    impact: tuple[PlasmaParticle,...]


class PlasmaSphere(BaseModel):
    model_config = ConfigDict(extra='forbid',frozen=True)
    vertices: tuple[tuple[float,float,float],...]
    uv: tuple[tuple[float,float],...]
    indices: tuple[int,...]


@lru_cache(maxsize=4)
def plasma_particles(path: Path) -> PlasmaParticles:
    return PlasmaParticles.model_validate_json(path.read_text())


@lru_cache(maxsize=4)
def plasma_sphere(path: Path) -> PlasmaSphere:
    return PlasmaSphere.model_validate_json(path.read_text())


def _smooth(a: float,b: float,value: float | np.ndarray) -> np.ndarray:
    t=np.clip((value-a)/(b-a),0,1)
    return t*t*(3-2*t)


def _rgba(rgb: np.ndarray,alpha: np.ndarray,palette: tuple[int,...]) -> np.ndarray:
    # Original spatial framebuffer converts linear material RGB to sRGB before
    # the donor's nearest-colour two-pixel postprocess.
    rgb=np.where(rgb<=.0031308,rgb*12.92,1.055*np.maximum(rgb,0)**(1/2.4)-.055)
    rgb=np.clip(rgb,0,1)
    colors=np.array([((c>>16)&255,(c>>8)&255,c&255) for c in palette],dtype=np.float32)/255
    w,h=alpha.shape
    sample=rgb[np.minimum(np.arange(w)//2*2+1,w-1)[:,None],np.minimum(np.arange(h)//2*2+1,h-1)[None,:]]
    indices=((sample[...,None,:]-colors)**2).sum(axis=3).argmin(axis=2)
    rgba=np.concatenate((np.rint(colors[indices]*255).astype(np.uint8),
        np.rint(np.clip(alpha,0,1)*255).astype(np.uint8)[...,None]),axis=2)
    rgba[...,:3][alpha<.01]=0
    rgba[...,3][alpha<.01]=0
    return rgba


def _energy(spec: StudioPlasmaTrailDelivery,surface: DirectedSurface,noise: np.ndarray,
            age: float,opacity: float, *, rim: np.ndarray | float=0.,corona: bool=False) -> np.ndarray:
    n=repeated_texture(noise,surface.uv[...,0]*1.5+age*.14,surface.uv[...,1]*1.5-age*.18)[...,0]
    rgb=np.array((.08,.36,.10))+(np.array((.55,1.45,.67))-np.array((.08,.36,.10)))*n[...,None]
    alpha=(.70*_smooth(.40,.78,n)+.10*rim if corona else .14+.60*_smooth(.38,.62,n)+.25*rim)*opacity
    return _rgba(rgb,alpha*surface.owned,spec.palette)


def plasma_draw_commands(timeline: CastTimeline,sample: CastSample,camera: Camera,area: AreaMedia | None,
        source: np.ndarray,charge_source: np.ndarray | None,targets: tuple[tuple[ApplicationTimeline,np.ndarray],...],
        trail: np.ndarray,noise: np.ndarray) -> tuple[DrawCommand,...]:
    spec=timeline.recipe.directed
    assert spec is not None and spec.material=='plasma_trail'
    particles=plasma_particles(timeline.data.resources[spec.particles])
    sphere=plasma_sphere(timeline.data.resources[spec.sphere])
    scale=np.array((1.,spec.verticalScale,1.))/spec.nativeUnitsPerCell
    view=np.array(((1.,.816496580927726,1.),(1.,.816496580927726,-1.),
        (-1.,.816496580927726,-1.),(-1.,.816496580927726,1.))[camera.quadrant]);view/=np.linalg.norm(view)
    commands=[]
    quad_uv=np.array(((0.,0.),(1.,0.),(0.,1.),(1.,1.)))
    quad_indices=np.array(((0,1,2),(1,3,2)))
    owner=timeline.source.caster.grid

    def append(surface: DirectedSurface | None,rgba: np.ndarray | None,identity: str) -> None:
        if surface is not None and rgba is not None:
            command=surface_command(surface,rgba,camera,owner,area,identity)
            if command is not None:commands.append(command)

    def energy_quad(point: np.ndarray,width: float,height: float,right: np.ndarray,up: np.ndarray,
                    age: float,opacity: float,identity: str) -> None:
        vertices=np.array([point+(right*x*width+up*y*height)*scale
            for x,y in ((-.5,.5),(.5,.5),(-.5,-.5),(.5,-.5))])
        surface=rasterize_surface(vertices,quad_uv,quad_indices,camera)
        append(surface,_energy(spec,surface,noise,age,opacity) if surface else None,identity)

    def energy_sphere(point: np.ndarray,radius: float,age: float,opacity: float,identity: str) -> None:
        if radius<=0 or opacity<=0:return
        vertices=point+np.array(sphere.vertices)*radius*scale
        uv=np.array(sphere.uv);indices=np.array(sphere.indices).reshape(-1,3)
        for nearest in (False,True):
            surface=rasterize_surface(vertices,uv,indices,camera,nearest=nearest)
            if surface is None:continue
            normal=(surface.xyz-point)/scale
            normal/=np.maximum(np.linalg.norm(normal,axis=2)[...,None],.000001)
            rim=(1-np.abs((normal*view).sum(axis=2)))**2
            append(surface,_energy(spec,surface,noise,age,opacity,rim=rim),identity+str(nearest))

    for row,endpoint in targets:
        elapsed=sample.media_elapsed_ms
        start,end=row.travel_start_ms,row.travel_end_ms
        target=recorded_surface_contact(row.source.target,source,endpoint) if isinstance(row.source.target,ObjectContact) else endpoint
        prefix=f'{timeline.source.root_event_uuid}:{row.source.application_id}:plasma'
        duration=max(1.,end-start)
        progress=float(np.clip((elapsed-start)/duration,0,1))
        clock=(3.72+(elapsed-start)/1000 if elapsed<start else
            3.72+progress*.38 if elapsed<end else 4.10+(elapsed-end)/1000)
        direction=(target-source)/scale;direction/=max(float(np.linalg.norm(direction)),.000001)
        right=np.cross((0.,1.,0.),direction);right/=max(float(np.linalg.norm(right)),.000001)
        up=np.cross(direction,right)
        charge_age=(elapsed-start+520)/1000
        charge_alpha=float(_smooth(0,.5,charge_age)*(1-_smooth(0,.14,(elapsed-start)/1000)))
        if charge_source is not None:
            energy_sphere(charge_source,.42*(.2+.8*float(_smooth(0,.65,charge_age))),charge_age,charge_alpha,prefix+':charge')
        if start<=elapsed<end+60:
            phase=np.linspace(0,1,17);along=np.maximum(0,progress-.7)+(progress-np.maximum(0,progress-.7))*phase
            centers=source+along[:,None]*(target-source)
            for corona in (True,False):
                width=.52*(1.8 if corona else 1.)*phase**.65*(1-phase)**.25*min(1,progress/.14)
                for index,angle in enumerate((0.,pi/3,2*pi/3)):
                    across=right*np.cos(angle)+up*np.sin(angle)
                    vertices=(centers[:,None,:]+(across*scale)[None,None,:]*width[:,None,None]*np.array((-1,1))[None,:,None]).reshape(-1,3)
                    uv=np.column_stack((np.repeat(phase,2),np.tile((0.,1.),17)))
                    triangles=np.array([(j*2+a,j*2+b,j*2+c) for j in range(16) for a,b,c in ((0,1,2),(1,3,2))])
                    surface=rasterize_surface(vertices,uv,triangles,camera)
                    if surface is None:continue
                    if corona:
                        opacity=float(.60*_smooth(3.72,3.77,clock)*(1-_smooth(4.08,4.16,clock)))
                        rgba=_energy(spec,surface,noise,clock*2,opacity,corona=True)
                    else:
                        n=repeated_texture(trail,surface.uv[...,0]-clock*1.3*1.5,surface.uv[...,1])[...,0]
                        n=np.where(n<=.04045,n/12.92,((n+.055)/1.055)**2.4)
                        rgb=np.array((.18,.65,.24))+(np.array((.80,1.5,.89))-np.array((.18,.65,.24)))*n[...,None]
                        opacity=float(_smooth(3.72,3.76,clock)*(1-_smooth(4.10,4.16,clock)))
                        alpha=(.55+.45*n)*opacity*np.maximum(0,1-np.abs(surface.uv[...,1]-.5)*2)**1.2*surface.owned
                        rgba=_rgba(rgb,alpha,spec.palette)
                    append(surface,rgba,prefix+f':{corona}:{index}')
        for index,(angle,radial,forward) in enumerate(particles.flight):
            birth=start+index/48*duration;age=(elapsed-birth)/1000
            if not 0<=age<.40:continue
            velocity=(right*np.cos(angle)+up*np.sin(angle))*radial+direction*forward
            point=source+(target-source)*(index/48)+(velocity*age+np.array((0.,-.6*age*age,0.)))*scale
            across=np.cross(velocity,view);across/=max(float(np.linalg.norm(across)),.000001)
            vertical=np.cross(view,across)
            size=(1+index%4*.2)*(1-float(_smooth(.12,.40,age)))
            energy_quad(point,.10*size,.30*size,across,vertical,clock,.9,prefix+f':flight:{index}')
        contact_age=(elapsed-end)/1000
        if row.source.save_succeeded is True or contact_age<0:continue
        if contact_age<.6:
            opacity=float(_smooth(0,.04,contact_age)*(1-_smooth(.22,.60,contact_age)))
            energy_sphere(target,.85*(.45+contact_age*1.6),contact_age,opacity,prefix+':impact')
        if contact_age>=1.2:continue
        count=120 if isinstance(row.source.target,ActorContact) else 48
        across=np.cross((0.,1.,0.),view);across/=np.linalg.norm(across);vertical=np.cross(view,across)
        for index,particle in enumerate(particles.impact[:count]):
            opacity=float(_smooth(0,.025 if index<48 else .03,contact_age)*(1-_smooth(.20 if index<48 else .35,.80 if index<48 else 1.20,contact_age)))
            if opacity<=0:continue
            origin=np.array(particle.origin);velocity=np.array(particle.velocity)
            origin[1]=max(.02,(target[1]-row.source.target.elevation_steps)/scale[1]+origin[1])-(target[1]-row.source.target.elevation_steps)/scale[1]
            point=target+(origin+velocity*contact_age)*scale
            size=1+index%3*.25
            energy_quad(point,.065*size,.16*size,across,vertical,contact_age,opacity,prefix+f':impact:{index}')
    return tuple(commands)
