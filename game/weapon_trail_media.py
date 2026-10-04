"""Accepted etched blade trail on measured equipped poses and native hit contacts."""
from math import floor,pi

import numpy as np

from game.animation import (ActorContact, actor_point_offset, body_elevation_steps,
    body_rig, rest_pose_offset, view_facing)
from game.attack import AttackTimeline
from game.directed_surface import rasterize_surface,surface_command
from game.draw_commands import DrawCommand
from game.projection import Camera,TILE_WIDTH,inverse_rotate_position,painter_key,project_screen
from game.registered_media import registered_media_blits


def source_trail_pixels(uv:np.ndarray,owned:np.ndarray,age:float,palette:tuple[int,int,int],*,sample_pixels:float=2,origin:tuple[float,float]=(0,0))->np.ndarray:
    """Strike.gdshader and pack_revision.py's eight-gray 2px palette pass."""
    edge=np.sin(uv[...,1]*pi);ridge=edge**6
    progress=np.clip((age-.67)/(.94-.67),0,1);fade=1-progress*progress*(3-2*progress)
    alpha=np.clip(edge*uv[...,0]*(.65+.35*np.sin(uv[...,0]*48+uv[...,1]*14))*fade*.92,0,1)*owned
    linear=.25+.60*ridge
    energy=(1.055*np.maximum(linear,0)**(1/2.4)-.055)*255
    width,height=alpha.shape;step=max(1.,sample_pixels)
    xs=np.floor((np.arange(width)+origin[0])/step).astype(int);xs-=xs.min()
    ys=np.floor((np.arange(height)+origin[1])/step).astype(int);ys-=ys.min()
    groups=xs[:,None]*(int(ys.max())+1)+ys[None,:]
    weights=np.bincount(groups.ravel(),weights=alpha.ravel())
    sums=np.bincount(groups.ravel(),weights=(energy*alpha).ravel())
    average=np.divide(sums,weights,out=np.zeros_like(sums),where=weights>0)
    levels=np.array((26,49,78,109,143,177,211,239))
    selected=levels[np.argmin(abs(average[:,None]-levels),axis=1)]
    source=selected[groups]
    colors=np.array([((color>>16)&255,(color>>8)&255,color&255) for color in palette])
    value=np.clip(source/239,0,1)*2;index=np.minimum(1,np.floor(value).astype(int));part=(value-index)[...,None]
    rgb=np.floor(colors[index]*(1-part)+colors[index+1]*part+.5).astype(np.uint8)
    a=np.rint(alpha*255).astype(np.uint8);rgba=np.concatenate((rgb,a[...,None]),axis=2);rgba[a<3]=0
    return rgba


def weapon_trail_draw_commands(timeline:AttackTimeline,elapsed_ms:float,camera:Camera)->tuple[DrawCommand,...]:
    media=timeline.weapon_trail
    if media is None:return ()
    data,source,pose=timeline.data,timeline.source,timeline.weapon_pose
    commands=[]
    # The original source samples 12Hz frames2..8. Use the real clip/contact
    # clock for other authored attacks; do not move their mechanics or body.
    contact_source=timeline.contact_ms*timeline.playback_speed/1000
    native_age=elapsed_ms*timeline.playback_speed/1000
    age=native_age*.67/contact_source if contact_source>0 else native_age
    if pose is not None and .16<=age<.94:
        points=pose.pointsByFacing[view_facing(timeline.facing,camera.quadrant,data)]
        fps=body_rig(data,source).clips[timeline.clip].fps
        def blade(t:float)->np.ndarray|None:
            sample=t*contact_source/.67*fps
            first=min(len(points)-1,max(0,int(floor(sample))));last=min(first+1,len(points)-1)
            a,b=points[first],points[last]
            if a is None or b is None:return None
            amount=sample-floor(sample)
            x=a.x*(1-amount)+b.x*amount;y=a.y*(1-amount)+b.y*amount
            sx=(x-64)*2*source.visual_scale_x;sy=(87-y)*2
            return np.array((sx/128-sy/192,sy/96,-sx/128-sy/192))*source.visual_scale
        vertices=[];uv=[];triangles=[];latest=min(age,.67);old=max(.14,latest-.20)
        for j in range(25):
            u=j/24;t=old+(latest-old)*u;p=blade(t);after=blade(t+.008);before=blade(t-.008)
            if p is None or after is None or before is None:break
            across=np.cross(after-before,(1,1,1));length=np.linalg.norm(across)
            if length>1e-10:across/=length
            for side in (0,1):
                v=p+across*(.03+.055*np.sin(u*pi))*(1 if side else -1)*source.visual_scale
                x,z=inverse_rotate_position((float(v[0]),float(v[2])),camera.quadrant)
                ox,oz=inverse_rotate_position((0,0),camera.quadrant)
                vertices.append((source.grid[0]+x-ox,body_elevation_steps(source,data)+v[1],source.grid[1]+z-oz));uv.append((u,side))
            if j:
                a=(j-1)*2;b=j*2;triangles.extend(((a,a+1,b+1),(a,b+1,b)))
        else:
            surface=rasterize_surface(np.array(vertices),np.array(uv),np.array(triangles),camera)
            if surface is not None:
                anchor=project_screen(source.grid,camera,elevation_steps=body_elevation_steps(source,data))
                pixel_scale=source.visual_scale*camera.zoom
                canvas_origin=(round(anchor[0]-192*pixel_scale),round(anchor[1]-249.6*pixel_scale))
                rgba=source_trail_pixels(surface.uv,surface.owned,age,media.palette,
                    sample_pixels=2*pixel_scale,origin=(surface.origin[0]-canvas_origin[0],surface.origin[1]-canvas_origin[1]))
                command=surface_command(surface,rgba,camera,source.grid,None,timeline.root_event_uuid+'.weapon_trail')
                if command is not None:commands.append(command)
    if timeline.show_contact:
        phase=data.projectile_assets[media.impactAssetId].phases.impact;age_ms=elapsed_ms-timeline.contact_ms
        if phase is None:raise ValueError('Weapon contact media requires an impact phase')
        fps=phase.fps or data.projectile_assets[media.impactAssetId].fps
        if 0<=age_ms<phase.frames*1000/fps:
            target=timeline.target;height=(body_elevation_steps(target,data) if isinstance(target,ActorContact) else target.elevation_steps)
            anchor=project_screen(target.grid,camera,elevation_steps=height)
            if isinstance(target,ActorContact):
                rig=body_rig(data,target)
                if rig.body_anchor is not None:
                    x,y=actor_point_offset(data,target,(rig.body_anchor.x,rig.body_anchor.y));rx,ry=rest_pose_offset(data,target,camera.quadrant)
                    factor=TILE_WIDTH/data.rig.TILE_W*camera.zoom;anchor=anchor[0]+(x+rx)*factor,anchor[1]+(y+ry)*factor
            key=painter_key(target.grid,elevation_steps=height,quadrant=camera.quadrant,role='actor',identity=timeline.root_event_uuid+'.weapon_contact')
            key=(*key[:3],key[3]+1,key[4])
            for image,destination,blend in registered_media_blits(data,media.impactAssetId,'impact',int(age_ms*fps/1000),
                    view_facing(timeline.facing,camera.quadrant,data),scale=timeline.contact_scale*camera.zoom,anchor=anchor,rows={}):
                commands.append(DrawCommand(key,image,destination,blend,(timeline.root_event_uuid,'weapon_contact')))
    return tuple(commands)
