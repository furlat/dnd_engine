"""Accepted Force/Ice source meshes and materials on received physical owners."""

from dataclasses import replace
from functools import lru_cache
from math import cos, pi
from pathlib import Path

import numpy as np

from dnd.core.presentation_geometry import WallAssemblyPresentationGeometry, WallDome, WallSegment
from game.animation_types import AnimationData, AuthoredRecord, ConstructionSurfaceMedia, ConstructionAirMedia
from game.area_media import AreaMedia
from game.directed_surface import (DonorTexture, DonorMesh, donor_texture, rasterize_surface,
    repeated_texture, source_palette_rgba, surface_command, DirectedSurface)
from game.draw_commands import DrawCommand
from game.projection import Camera
from game.volume_media import ExcludedSphere


class WallMesh(DonorMesh):
    normals: tuple[tuple[float,float,float],...]


class IcePiece(AuthoredRecord):
    mesh: WallMesh
    origin: tuple[float,float,float]


class IcePose(AuthoredRecord):
    tick: int
    poses: tuple[tuple[float,...],...]


class DomeSource(AuthoredRecord):
    radiusFeet: int
    whole: WallMesh
    force: DonorMesh
    pieces: tuple[IcePiece,...]
    poses: tuple[IcePose,...]


class ConstructionTextures(AuthoredRecord):
    force_overlay: DonorTexture
    ice_add: DonorTexture
    ice_details: DonorTexture
    ice_gradient: DonorTexture


class ForceMote(AuthoredRecord):
    origin: tuple[float,float,float]
    velocity: tuple[float,float,float]
    size: tuple[float,float]


class ForceMoteGroup(AuthoredRecord):
    form: str
    sizeFeet: int
    motes: tuple[ForceMote,...]


class ForceMotes(AuthoredRecord):
    groups: tuple[ForceMoteGroup,...]
    noise: DonorTexture


@lru_cache(maxsize=2)
def force_motes(path: Path) -> ForceMotes:
    return ForceMotes.model_validate_json(path.read_bytes())


class ConstructionComponents(AuthoredRecord):
    textures: ConstructionTextures
    domes: tuple[DomeSource,...]


@lru_cache(maxsize=2)
def construction_components(path: Path) -> ConstructionComponents:
    return ConstructionComponents.model_validate_json(path.read_bytes())


@lru_cache(maxsize=2)
def construction_air_mesh(path: Path) -> WallMesh:
    return WallMesh.model_validate_json(path.read_bytes())


def _smooth(a: float | np.ndarray,b: float | np.ndarray,value):
    fraction=np.clip((value-a)/(b-a),0,1)
    return fraction*fraction*(3-2*fraction)


def _clamped_texture(texture: np.ndarray,u: np.ndarray,v: np.ndarray) -> np.ndarray:
    return repeated_texture(texture,np.clip(u,.5/texture.shape[0],1-.5/texture.shape[0]),
        np.clip(v,.5/texture.shape[1],1-.5/texture.shape[1]))


@lru_cache(maxsize=16)
def force_panel(length: float,height: float,cell: float) -> tuple[np.ndarray,...]:
    """Literal source lattice density: 32 columns per original ten-foot panel."""
    nx=max(1,round(length/(2*cell)*32));ny=32
    x,y=np.meshgrid(np.linspace(-length/2,length/2,nx+1),np.linspace(0,height,ny+1))
    points=np.column_stack((x.ravel(),y.ravel(),np.zeros(x.size)))
    uv=np.column_stack(((x.ravel()/length+.5)*length/(2*cell),1-y.ravel()/height))
    ids=np.arange(nx*ny).reshape(ny,nx)+np.arange(ny)[:,None]
    indices=np.stack((ids,ids+1,ids+nx+1,ids+1,ids+nx+2,ids+nx+1),axis=-1).reshape(-1,3)
    normals=np.tile((0.,0.,1.),(len(points),1))
    return points,uv,indices,normals


@lru_cache(maxsize=32)
def _held_ice_surface(source: Path,radius: float,base: tuple[float,float,float],
        scale: tuple[float,float,float],camera: Camera,side: bool) -> DirectedSurface | None:
    """The accepted intact material has an explicitly frozen mesh and colour phase."""
    mesh=next(d.whole for d in construction_components(source).domes if d.radiusFeet==radius)
    return rasterize_surface(np.asarray(base)+np.asarray(mesh.vertices)*scale,np.asarray(mesh.uv),
        np.asarray(mesh.indices).reshape(-1,3),camera,nearest=side,normals=np.asarray(mesh.normals))


@lru_cache(maxsize=64)
def _force_impulse(mesh: tuple[tuple[float,float,float],...], indices: tuple[int,...],
        contact: tuple[float,float,float], steps: int, dome: bool) -> np.ndarray:
    """Original damped membrane at 144 Hz, evaluated as a pure source sample."""
    points=np.asarray(mesh,dtype=np.float32);triangles=np.asarray(indices).reshape(-1,3)
    edges=np.concatenate((triangles[:,(0,1)],triangles[:,(1,2)],triangles[:,(2,0)]))
    edges=np.unique(np.concatenate((edges,edges[:,::-1])),axis=0)
    if not dome:
        # The source panel lattice couples only its four axial neighbours.
        difference=points[edges[:,0]]-points[edges[:,1]]
        edges=edges[np.count_nonzero(np.abs(difference)>1e-5,axis=1)==1]
    row,col=edges.T;distances=np.maximum(.001,((points[row]-points[col])**2).sum(axis=1))
    weight=1/distances
    if dome:weight*=4/np.bincount(row,minlength=len(points))[row]
    field=np.zeros(len(points),dtype=np.float32)
    velocity=(1.2*np.exp(-((points-np.asarray(contact))**2).sum(axis=1)/.08)).astype(np.float32)
    for _ in range(steps):
        lap=np.bincount(row,weights=(field[col]-field[row])*weight,minlength=len(points)).astype(np.float32)
        velocity+=(25*lap-4*velocity-4*field)/144
        field+=velocity/144
    field.setflags(write=False)
    return field


def construction_surface_commands(geometry: WallAssemblyPresentationGeometry,
        spec: ConstructionSurfaceMedia,data: AnimationData,now_ms: float,camera: Camera,
        owner: str,applied_ms: float | None,removed_ms: float | None,destroyed_ms: float | None,
        *, area: AreaMedia | None=None,
        collapse_contact: tuple[float,float,float] | None = None,
        impulses: tuple[tuple[float,tuple[float,float,float]], ...] = ()) -> tuple[DrawCommand,...]:
    """No live physics: actual state selects original formation, hold, break or clear."""
    if spec.domeOnly and not isinstance(geometry.path,WallDome):
        return ()
    if removed_ms is not None and now_ms>=removed_ms+spec.removalMs:
        return ()
    if destroyed_ms is not None and now_ms>=destroyed_ms+spec.destructionMs:
        return ()
    source=construction_components(data.resources[spec.components])
    folder=data.resources[spec.components].parent
    age=max(0.,(now_ms-applied_ms)/1000) if applied_ms is not None else 2.
    break_age=(now_ms-destroyed_ms)/1000 if destroyed_ms is not None and now_ms>=destroyed_ms else None
    fade=1-float(_smooth(0,spec.removalMs,now_ms-removed_ms)) if removed_ms is not None else 1.
    cell=spec.nativeUnitsPerCell
    scale=np.array((1.,spec.verticalScale,1.))/cell
    path=geometry.path
    if isinstance(path,WallDome):
        original=next((d for d in source.domes if d.radiusFeet==path.radius_feet),None)
        if original is None:
            return ()
        center=path.center
        if spec.material=='ice_shell':
            mesh=original.whole
            if break_age is None:
                meshes=((np.asarray(mesh.vertices),np.asarray(mesh.uv),np.asarray(mesh.indices).reshape(-1,3),np.asarray(mesh.normals)),)
            else:
                # These are the original engine's recorded transforms, including
                # floor collisions. Runtime never invents a fragment simulation.
                sample=min(len(original.poses)-1,max(0,round(break_age*144)+1))
                transforms=original.poses[sample].poses
                meshes=tuple((np.asarray(piece.mesh.vertices)@np.asarray(pose[3:]).reshape(3,3)+np.asarray(pose[:3]),
                    np.asarray(piece.mesh.uv),np.asarray(piece.mesh.indices).reshape(-1,3),
                    np.asarray(piece.mesh.normals)@np.asarray(pose[3:]).reshape(3,3))
                    for piece,pose in zip(original.pieces,transforms,strict=True))
                fade*=1-float(_smooth(1.5,2.3,break_age))
        else:
            mesh=original.force;vertices=np.asarray(mesh.vertices)
            meshes=((vertices,np.asarray(mesh.uv),np.asarray(mesh.indices).reshape(-1,3),
                vertices/np.linalg.norm(vertices,axis=1)[:,None]),)
    elif isinstance(path,WallSegment) and spec.material=='force_membrane':
        center=((path.start[0]+path.end[0])/2,(path.start[1]+path.end[1])/2)
        delta=np.subtract(path.end,path.start);length=float(np.linalg.norm(delta));tangent=delta/length
        points,uv,triangles,normals=force_panel(length*cell,geometry.height_feet/5*cell,cell)
        rotation=np.array(((tangent[0],0,tangent[1]),(0,1,0),(-tangent[1],0,tangent[0])))
        meshes=((points@rotation,uv,triangles,normals@rotation),)
    else:
        return ()
    base=np.array((center[0],geometry.base_height_steps,center[1]))
    view=np.array(((1.,.816496580927726,1.),(1.,.816496580927726,-1.),
        (-1.,.816496580927726,-1.),(-1.,.816496580927726,1.))[camera.quadrant]);view/=np.linalg.norm(view)
    textures=source.textures
    overlay=donor_texture(folder,textures.force_overlay) if spec.material=='force_membrane' else None
    add=donor_texture(folder,textures.ice_add) if spec.material=='ice_shell' else None
    details=donor_texture(folder,textures.ice_details) if spec.material=='ice_shell' else None
    gradient=donor_texture(folder,textures.ice_gradient) if spec.material=='ice_shell' else None
    commands=[]
    for index,(vertices,uv,triangles,normals) in enumerate(meshes):
        colors=None
        if spec.material=='force_membrane':
            field=np.zeros(len(vertices),dtype=np.float32)
            active=tuple((at,point) for at,point in impulses if 0<=now_ms-at<10000)
            if active:
                # Evaluate in original material coordinates before owner rotation.
                original_vertices=vertices if isinstance(path,WallDome) else vertices@rotation.T
                mesh_key=tuple(map(tuple,original_vertices.tolist()));index_key=tuple(triangles.ravel().tolist())
                for at,point in active:
                    contact=(np.asarray(point)-base)/scale
                    if isinstance(path,WallSegment):contact=contact@rotation.T
                    field+=_force_impulse(mesh_key,index_key,tuple(contact.tolist()),round((now_ms-at)*144/1000),isinstance(path,WallDome))
                vertices=vertices+normals*np.clip(field*.2,-.015,.015)[:,None]
            colors=np.column_stack((np.abs(field),np.zeros(len(field)),np.zeros(len(field)),np.ones(len(field))))
        # The two original source layers retain the near and far shell faces.
        for side in ((False,True) if isinstance(path,WallDome) else (True,)):
            if spec.material=='ice_shell' and isinstance(path,WallDome) and break_age is None:
                surface=_held_ice_surface(data.resources[spec.components],path.radius_feet,
                    (float(base[0]),float(base[1]),float(base[2])),
                    (float(scale[0]),float(scale[1]),float(scale[2])),camera,side)
            else:
                surface=rasterize_surface(base+vertices*scale,uv,triangles,camera,nearest=side,normals=normals,colors=colors)
            if surface is None:
                continue
            assert surface.normals is not None
            normal=surface.normals/np.maximum(np.linalg.norm(surface.normals,axis=2)[...,None],1e-9)
            dot=np.clip(normal@view,-1,1);wp=(surface.xyz-base)/scale
            u,v=surface.uv[...,0],surface.uv[...,1]
            growth=float(_smooth(0,.85,age))
            if spec.material=='ice_shell':
                assert add is not None and details is not None and gradient is not None
                fresnel=(1-np.clip(dot,0,1))**1.36
                coordinate=fresnel+_clamped_texture(add,u,v)[...,0]+repeated_texture(details,u,v+.03)[...,0]
                rgb=_clamped_texture(gradient,coordinate,coordinate)[...,:3]*1.45
                alpha=fade*(.20+.28*(1-np.abs(dot))**1.6)
                admitted=surface.owned&(wp[...,1]>=0)&(wp[...,1]<=growth*4.6)
            else:
                assert overlay is not None
                line=np.clip(repeated_texture(overlay,u*2,v*2)[...,0]**1.335,0,1)
                rim=(1-np.abs(dot))**2
                height=geometry.height_feet/5*cell
                crest=np.exp(-((wp[...,1]-growth*height)/.14)**2)*(1-float(_smooth(.65,.95,age)))
                border=np.exp(-(wp[...,1]/.05)**2)
                if isinstance(path,WallSegment):
                    distance=(wp[...,0]*tangent[0]+wp[...,2]*tangent[1])
                    border=np.maximum(np.exp(-((np.abs(distance)-length*cell/2)/.045)**2),
                        np.maximum(np.exp(-(wp[...,1]/.045)**2),np.exp(-((wp[...,1]-height)/.045)**2)))
                strength=np.maximum(np.maximum(line*.65,rim),border*.4)
                rgb=np.array((.07,.26,.49))+(np.array((.38,.67,1.))-np.array((.07,.26,.49)))*strength[...,None]
                destabilize=np.zeros(crest.shape);dissolution=np.zeros(crest.shape)
                if break_age is not None:
                    if collapse_contact is not None:
                        contact=(np.asarray(collapse_contact)-base)/scale
                        distance=np.linalg.norm(wp-contact,axis=2)
                        dissolution=_smooth(distance*.035,distance*.035+.5,break_age)
                        destabilize=np.exp(-((distance-break_age*15)/.45)**2)
                    else:
                        # A hidden incoming source supplies no inferred impact.
                        # Clear the same material through its opacity uniform.
                        dissolution=np.full(crest.shape,float(_smooth(0,.8,break_age)))
                assert surface.colors is not None
                wave=_smooth(.0008,.009,np.abs(surface.colors[...,0]))
                energy=np.maximum(crest,np.maximum(wave,destabilize))
                rgb+=(np.array((.65,1.15,1.7))-rgb)*energy[...,None]
                alpha=(.065+.12*line+.10*rim+.30*border+.60*crest+.75*wave+.45*destabilize)*fade*growth*(1-dissolution)*(.94+.06*cos(2*pi*age/4))
                admitted=surface.owned&(wp[...,1]>=0)&(wp[...,1]<=growth*height)
            rgba=source_palette_rgba(rgb,alpha*admitted,spec.palette,sample_pixels=2*camera.zoom)
            command=surface_command(surface,rgba,camera,center,area,f'{owner}:{index}:{side}')
            if command is not None:
                commands.append(command._replace(owner=owner,world_depth_group=(owner,str(index),str(side))))
    if spec.material=='force_membrane' and spec.motes is not None and break_age is not None and 0<=break_age<1.2:
        motes_path=data.resources[spec.motes];motes=force_motes(motes_path)
        size=path.radius_feet if isinstance(path,WallDome) else round(length*5)
        form='dome' if isinstance(path,WallDome) else 'panels'
        group=next((row for row in motes.groups if row.form==form and row.sizeFeet==size),None)
        if group is not None:
            noise=donor_texture(motes_path.parent,motes.noise)
            opacity=float(_smooth(0,.03,break_age))*(1-float(_smooth(.35,1.2,break_age)))
            # Original look_at(camera_sign, .70710678, camera_sign) quad basis.
            normal=np.array(((1.,.70710678,1.),(1.,.70710678,-1.),(-1.,.70710678,-1.),(-1.,.70710678,1.))[camera.quadrant]);normal/=np.linalg.norm(normal)
            right=np.cross(np.array((0.,1.,0.)),normal);right/=np.linalg.norm(right)
            up=np.cross(normal,right)
            quad=np.array(((-.5,-.5),(.5,-.5),(.5,.5),(-.5,.5)))
            for i,mote in enumerate(group.motes):
                point=np.asarray(mote.origin)+np.asarray(mote.velocity)*break_age
                if isinstance(path,WallSegment):
                    point[2]-=cell*.5
                    point=point@rotation
                vertices=point+quad[:,0,None]*mote.size[0]*right+quad[:,1,None]*mote.size[1]*up
                sample=rasterize_surface(base+vertices*scale,np.array(((0,1),(1,1),(1,0),(0,0))),
                    np.array(((0,1,2),(0,2,3))),camera)
                if sample is None:continue
                n=repeated_texture(noise,sample.uv[...,0]*1.5+break_age*.14,sample.uv[...,1]*1.5-break_age*.18)[...,0]
                rgb=np.array((.08,.33,.64))+(np.array((.65,1.10,1.7))-np.array((.08,.33,.64)))*n[...,None]
                alpha=(.14+.60*_smooth(.38,.62,n))*opacity*sample.owned
                command=surface_command(sample,source_palette_rgba(rgb,alpha,spec.palette,sample_pixels=2*camera.zoom),camera,center,area,f'{owner}:mote:{i}')
                if command is not None:commands.append(command._replace(owner=owner,world_depth_group=(owner,'mote',str(i))))
    return tuple(commands)


def ice_air_commands(geometry: WallAssemblyPresentationGeometry,spec: ConstructionAirMedia,
        data: AnimationData,age_ms: float,applied: bool,alpha: float,camera: Camera,owner: str,
        admitted: tuple[tuple[int,int],...],area: AreaMedia | None,
        exclusions: tuple[ExcludedSphere,...]) -> tuple[DrawCommand,...]:
    """Literal source residual shell/flakes; admission comes only from FrigidAirZone."""
    path=geometry.path
    if not isinstance(path,(WallDome,WallSegment)) or alpha<=0:
        return ()
    mesh=construction_air_mesh(data.resources[spec.mesh]);cell=spec.nativeUnitsPerCell
    scale=np.array((1.,spec.verticalScale,1.))/cell
    center=path.center if isinstance(path,WallDome) else ((path.start[0]+path.end[0])/2,(path.start[1]+path.end[1])/2)
    base=np.array((center[0],geometry.base_height_steps,center[1]))
    formation=.4 if isinstance(path,WallDome) else .29
    age=max(0,age_ms/1000);opacity=alpha*(float(_smooth(0,formation,age)) if applied else 1.)
    view=np.array(((1.,.816496580927726,1.),(1.,.816496580927726,-1.),
        (-1.,.816496580927726,-1.),(-1.,.816496580927726,1.))[camera.quadrant]);view/=np.linalg.norm(view)
    commands=[]

    def append(vertices,uv,indices,normals,rgb,opacity_at,identity,nearest=True):
        surface=rasterize_surface(base+vertices*scale,uv,indices,camera,nearest=nearest,normals=normals)
        if surface is None:return
        values=opacity_at(surface)
        cells=np.floor(surface.xyz[...,(0,2)]+.5).astype(int);allowed=np.zeros(surface.owned.shape,dtype=bool)
        for x,z in admitted:allowed|=(cells[...,0]==x)&(cells[...,1]==z)
        rgba=source_palette_rgba(np.array(rgb),values*surface.owned*allowed,spec.palette,sample_pixels=2*camera.zoom)
        command=surface_command(surface,rgba,camera,center,area,identity)
        if command is not None:
            assert command.volume is not None
            commands.append(command._replace(owner=owner,world_depth_group=(owner,identity),
                volume=replace(command.volume,admitted=admitted,exclusions=exclusions)))

    if isinstance(path,WallSegment):
        delta=np.subtract(path.end,path.start);length=float(np.linalg.norm(delta));tangent=delta/length
        rotation=np.array(((tangent[0],0,tangent[1]),(0,1,0),(-tangent[1],0,tangent[0])))
        height=geometry.height_feet/5*cell;half=np.array((length*cell/2,height/2,cell*.4))
        local_center=np.array((0.,height/2,0.))
        vertices=np.array([(x,y,z) for x in (-1,1) for y in (-1,1) for z in (-1,1)])*half+local_center
        indices=np.array(((0,1,2),(1,3,2),(4,6,5),(5,6,7),(0,4,1),(1,4,5),
            (2,3,6),(3,7,6),(0,2,4),(2,6,4),(1,5,3),(3,5,7)))
        ray=-view@rotation.T
        safe=np.sign(ray)*np.maximum(np.abs(ray),.0001)
        def volume_opacity(surface):
            point=((surface.xyz-base)/scale)@rotation.T-local_center
            travel=np.maximum(0,((np.sign(safe)*half-point)/safe).min(axis=2));step=travel/16
            density=np.zeros(step.shape)
            for i in range(16):
                sample=point+ray*(i+.5)*step[...,None]
                edge=(half-np.abs(sample))/half
                boundary=_smooth(0,.22,edge[...,0])*_smooth(0,.20,edge[...,1])*_smooth(0,.32,edge[...,2])
                cloud=.62+.10*np.cos(sample[...,0]*.85+sample[...,1]*.40)+.08*np.cos(sample[...,2]*.72-sample[...,1]*.55)
                density+=boundary*cloud*step
            return .25*opacity*(1-np.exp(-density*.70))
        append(vertices@rotation,np.zeros((8,2)),indices,None,(.49,.76,.87),volume_opacity,f'{owner}:air')
        right=np.array((view[2],0,-view[0]));right/=np.linalg.norm(right);up=np.cross(view,right)
        uv=np.array(((0.,0.),(1.,0.),(0.,1.),(1.,1.)))
        for i in range(14):
            phase=(age/4+i*.61803398875)%1;u=(i*.754877666)%1;v=(i*.569840291)%1
            position=np.array(((u-.5)*length*cell*.80+.07*np.sin(2*pi*phase+i*1.7),height*(1-phase),
                (v-.5)*cell*.8*.68+.035*np.cos(2*pi*phase+i*2.1)))@rotation
            size=.065+.024*(i%3)
            flake=position+(uv[:,0,None]-.5)*right*size+(uv[:,1,None]-.5)*up*size
            amplitude=opacity*.34*float(_smooth(0,.16,phase)*(1-_smooth(.78,1,phase)))
            append(flake,uv,np.array(((0,1,2),(1,3,2))),None,(.67,.82,.89),
                lambda surface,a=amplitude:a*(1-_smooth(.15,1,np.linalg.norm(surface.uv*2-1,axis=2))),f'{owner}:flake:{i}')
        return tuple(commands)
    vertices=np.array(mesh.vertices)*path.radius_feet/spec.sourceRadiusFeet
    def shell_opacity(surface):
        assert surface.normals is not None
        normal=surface.normals/np.maximum(np.linalg.norm(surface.normals,axis=2)[...,None],1e-9)
        return (.02+.07*(1-np.abs(np.clip(normal@view,-1,1)))**1.8)*opacity*(surface.xyz[...,1]>=geometry.base_height_steps)
    for near in (False,True):
        append(vertices,np.asarray(mesh.uv),np.asarray(mesh.indices).reshape(-1,3),np.asarray(mesh.normals),
            (.45,.69,.80),shell_opacity,f'{owner}:air:{near}',nearest=near)
    right=np.array((view[2],0,-view[0]));right/=np.linalg.norm(right);up=np.cross(view,right)
    uv=np.array(((0.,0.),(1.,0.),(0.,1.),(1.,1.)))
    for i in range(24):
        phase=(age/4+i*.61803398875)%1;angle=i/24*2*pi;phi=.25+i%6/6*1.20
        radius=path.radius_feet/5*cell
        position=np.array((np.sin(phi)*np.cos(angle),np.cos(phi),np.sin(phi)*np.sin(angle)))*radius
        position[1]-=.25*phase
        flake=position+(uv[:,0,None]-.5)*right*.065+(uv[:,1,None]-.5)*up*.065
        amplitude=opacity*.36*float(_smooth(0,.14,phase)*(1-_smooth(.8,1,phase)))
        append(flake,uv,np.array(((0,1,2),(1,3,2))),None,(.67,.82,.89),
            lambda surface,a=amplitude:a*(1-_smooth(.15,1,np.linalg.norm(surface.uv*2-1,axis=2))),f'{owner}:flake:{i}')
    return tuple(commands)
