"""Accepted electric ribbon material over recorded endpoints in the shared painter.

Geometry follows the delivered source equations. Sampled XYZ goes through the
existing volume compositor; this module neither selects recipients nor hits.
"""
from functools import lru_cache
from math import ceil, floor, hypot, pi
from pathlib import Path
import zlib

import numpy as np
import pygame

from dnd.core.presentation_geometry import LinePresentationGeometry
from game.animation import (ActorContact, ObjectContact, CastTimeline, CastSample, actor_point_offset,
    body_rig, body_elevation_steps, view_facing, rest_pose_offset, feedback_identity, sample_cast)
from game.area_media import AreaMedia
from game.animation_types import StudioNoiseRibbonDelivery
from game.draw_commands import DrawCommand
from game.directed_plasma_media import plasma_draw_commands, plasma_particles, plasma_sphere
from game.directed_contacts import directed_socket
from game.directed_mesh_media import darkness_mesh_commands, preload_darkness_media
from game.directed_surface import DirectedSurface, rasterize_surface, repeated_texture, palette_blocks, surface_command
from game.projection import Camera, TILE_WIDTH, project_screen, painter_key
from game.volume_media import SurfaceVolume


@lru_cache(maxsize=12)
def _texture(path: Path) -> np.ndarray:
    image = pygame.image.load(path).convert_alpha()
    return np.concatenate((pygame.surfarray.array3d(image),
        pygame.surfarray.array_alpha(image)[..., None]), axis=2).astype(np.float32) / 255


def preload_directed_media(timeline: CastTimeline) -> None:
    if (delivery := timeline.recipe.directed) is not None and delivery.material == "noise_ribbon":
        _texture(timeline.data.resources[delivery.texture])
    if delivery is not None and delivery.material == "plasma_trail":
        _texture(timeline.data.resources[delivery.trailTexture])
        _texture(timeline.data.resources[delivery.noiseTexture])
        plasma_particles(timeline.data.resources[delivery.particles])
        plasma_sphere(timeline.data.resources[delivery.sphere])
    if (delivery := timeline.recipe.directed) is not None and delivery.material == "darkness_mesh":
        preload_darkness_media(timeline.data.resources[delivery.geometry])
    spec = timeline.recipe.arcs
    if spec is not None:
        for key in (spec.texture, spec.glow, spec.star, spec.streak, spec.spark):
            _texture(timeline.data.resources[key])


def _bilinear(texture: np.ndarray, x: np.ndarray, y: np.ndarray) -> np.ndarray:
    x = np.clip(x, 0, texture.shape[0]-1)
    y = np.clip(y, 0, texture.shape[1]-1)
    ix, iy = x.astype(int), y.astype(int)
    jx, jy = np.minimum(ix+1, texture.shape[0]-1), np.minimum(iy+1, texture.shape[1]-1)
    fx, fy = (x-ix)[..., None], (y-iy)[..., None]
    return (texture[ix,iy]*(1-fx)+texture[jx,iy]*fx)*(1-fy)+(texture[ix,jy]*(1-fx)+texture[jx,jy]*fx)*fy


def _smooth(start: float, end: float, time: float) -> float:
    value = max(0., min(1., (time-start)/(end-start)))
    return value*value*(3-2*value)


def _point(timeline: CastTimeline, contact: ActorContact | ObjectContact, camera: Camera, *,
           hand: bool = False, body_frame: int | None = None,
           plane_height: float | None = None) -> np.ndarray:
    """Resolve the real authored socket back to the host world projection."""
    data = timeline.data
    height = contact.elevation_steps
    point = None
    if isinstance(contact, ActorContact):
        height = body_elevation_steps(contact, data)
        if hand:
            sockets = timeline.recipe.cast.sourceSockets
            if sockets is None:
                raise ValueError('Directed hand delivery requires authored sockets')
            facing = view_facing(timeline.facing, camera.quadrant, data)
            point = sockets.release[facing]
            if body_frame is not None and sockets.preparation is not None:
                point = sockets.preparation[facing][body_frame] or point
        else:
            point = body_rig(data, contact).body_anchor
    dx, dy = actor_point_offset(data, contact, (point.x, point.y)) if point is not None and isinstance(contact, ActorContact) else (0., 0.)
    if not hand and isinstance(contact, ActorContact):
        rx, ry = rest_pose_offset(data, contact, camera.quadrant)
        dx, dy = dx+rx, dy+ry
    factor = TILE_WIDTH/data.rig.TILE_W
    dx, dy = dx*factor, dy*factor
    # Pick the delivered source's contact plane; the socket's XY then follows
    # exactly from its current rendered pixel, including rig scale and posture.
    lift = plane_height if plane_height is not None else .95 if hand else .87
    sx, sy = dx/64, (dy+lift*64)/32
    x, z = (sx+sy)/2, (sy-sx)/2
    x, z = ((x,z),(z,-x),(-x,-z),(-z,x))[camera.quadrant]
    return np.array((contact.grid[0]+x, height+lift, contact.grid[1]+z), dtype=np.float64)


def _jagged(a: np.ndarray, b: np.ndarray, random: np.random.Generator, jag: float = .075) -> np.ndarray:
    vector = b-a
    length = float(np.linalg.norm(vector))
    axis = vector/max(length, .00001)
    reference = np.array((1.,0.,0.) if abs(axis[1]) > .9 else (0.,1.,0.))
    u = np.cross(axis, reference)
    u /= max(float(np.linalg.norm(u)), .00001)
    v = np.cross(axis, u)
    count = min(32, max(3, int(length/.3)+2))
    t = np.linspace(0, 1, count+1)
    points = a[None,:] + t[:,None]*vector
    offsets = random.uniform(-1, 1, (count+1,2))*min(.35,jag*length)
    points += offsets[:,0,None]*u + offsets[:,1,None]*v
    points[0], points[-1] = a, b
    return points


def _ribbon(points: np.ndarray, width: float, *, texture: np.ndarray, frame: int,
            energy: float, reveal: float, camera: Camera, center: tuple[float,float],
            area: AreaMedia | None, line: LinePresentationGeometry | None, identity: str,
            ) -> tuple[DrawCommand, ...]:
    if energy <= 0 or reveal <= 0:
        return ()
    lengths = np.linalg.norm(np.diff(points, axis=0), axis=1)
    distance = np.concatenate(([0.], np.cumsum(lengths)))
    total = max(float(distance[-1]), .00001)
    progress = distance/total
    screen = np.array([project_screen((point[0],point[2]), camera, elevation_steps=point[1]) for point in points])
    tangent = screen[np.minimum(np.arange(len(points))+1,len(points)-1)] - screen[np.maximum(np.arange(len(points))-1,0)]
    normals = np.column_stack((-tangent[:,1],tangent[:,0]))
    normals /= np.maximum(np.linalg.norm(normals,axis=1)[:,None], .00001)
    half_width = width*(.55+.45*np.sin(progress*pi))*.5*64*camera.zoom
    vertices = screen[:,None,:] + normals[:,None,:]*half_width[:,None,None]*np.array([-1,1])[None,:,None]
    commands = []
    origin = project_screen(center, camera)
    for index in range(len(points)-1):
        if progress[index] > reveal:
            break
        quad = np.array([vertices[index,0],vertices[index,1],vertices[index+1,0],vertices[index+1,1]])
        left, top = (int(value) for value in np.floor(quad.min(axis=0)))
        right, bottom = (int(value)+1 for value in np.ceil(quad.max(axis=0)))
        if right <= 0 or bottom <= 0 or left >= camera.viewport[0] or top >= camera.viewport[1]:
            continue
        left,top = max(0,left),max(0,top)
        right,bottom = min(camera.viewport[0],right),min(camera.viewport[1],bottom)
        x,y = np.meshgrid(np.arange(left,right)+.5,np.arange(top,bottom)+.5,indexing='ij')
        uv = np.zeros((*x.shape,2),dtype=np.float32)
        height = np.zeros(x.shape,dtype=np.float32)
        owned = np.zeros(x.shape,dtype=bool)
        attributes = np.array([(0,progress[index],points[index,1]),(1,progress[index],points[index,1]),
            (0,progress[index+1],points[index+1,1]),(1,progress[index+1],points[index+1,1])])
        for triangle in ((0,1,2),(2,1,3)):
            a,b,c = quad[list(triangle)]
            denominator = (b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
            if abs(denominator) < 1e-8:
                continue
            u = ((b[1]-c[1])*(x-c[0])+(c[0]-b[0])*(y-c[1]))/denominator
            v = ((c[1]-a[1])*(x-c[0])+(a[0]-c[0])*(y-c[1]))/denominator
            w = 1-u-v
            inside = (u>=0)&(v>=0)&(w>=0)
            values = u[...,None]*attributes[triangle[0]]+v[...,None]*attributes[triangle[1]]+w[...,None]*attributes[triangle[2]]
            uv[inside] = values[inside,:2]
            height[inside] = values[inside,2]
            owned |= inside
        along = .16+.66*(1-np.abs(np.mod(uv[...,1]*total/3,1)*2-1))
        tx = frame%4*520+4+along*511
        ty = frame//4*136+4+uv[...,0]*127
        baked = _bilinear(texture,tx,ty)
        raw = baked[...,:3]*baked[...,3,None]
        start = np.clip(uv[...,1]/.008,0,1)
        end = np.clip((1-uv[...,1])/.008,0,1)
        envelope = energy*(start*start*(3-2*start))*(end*end*(3-2*end))
        rgb = np.stack((raw[...,0]*.38,raw[...,1]*.84+raw[...,2]*.20,raw[...,2]*.82),axis=2)*envelope[...,None]
        owned &= uv[...,1] <= reveal
        rgb[~owned] = 0
        image = pygame.Surface(x.shape,pygame.SRCALPHA)
        pygame.surfarray.pixels3d(image)[:] = np.rint(np.clip(rgb,0,1)*255).astype(np.uint8)
        pygame.surfarray.pixels_alpha(image)[:] = np.rint(np.clip(rgb.max(axis=2),0,1)*255).astype(np.uint8)
        sx,sy = (x-origin[0])/camera.zoom/64,((y-origin[1])/camera.zoom+height*64)/32
        xyz = np.stack(((sx+sy)/2,height,(sy-sx)/2),axis=2)
        volume = SurfaceVolume(center,0,0,xyz,owned.astype(np.uint8),1,
            boundaries=area.boundaries if area else (), solids=area.solids if area else (),
            supports=area.supports if area else (), admitted=area.admitted if area and line is not None else None,
            resolved_occupancy=True,line_geometry=line)
        midpoint = (points[index]+points[index+1])/2
        key = painter_key((float(midpoint[0]),float(midpoint[2])),elevation_steps=float(midpoint[1]),
            quadrant=camera.quadrant,role='projectile',identity=(identity,str(index)))
        commands.append(DrawCommand(key,image,(left,top),pygame.BLEND_RGBA_ADD,
            (identity,'textured_arc',frame),volume=volume))
    return tuple(commands)


def _flare(point: np.ndarray, texture: np.ndarray, size: float, color: tuple[float,float,float],
           energy: float, camera: Camera, center: tuple[float,float], area: AreaMedia | None,
           identity: str) -> tuple[DrawCommand,...]:
    if energy <= 0:
        return ()
    px,py = project_screen((point[0],point[2]),camera,elevation_steps=point[1])
    radius = size*camera.zoom
    left,top = max(0,floor(px-radius)),max(0,floor(py-radius))
    right,bottom = min(camera.viewport[0],ceil(px+radius)),min(camera.viewport[1],ceil(py+radius))
    if right <= left or bottom <= top:
        return ()
    x,y = np.meshgrid(np.arange(left,right)+.5,np.arange(top,bottom)+.5,indexing='ij')
    mask = _bilinear(texture,(x-px+radius)/(2*radius)*texture.shape[0]-.5,
        (y-py+radius)/(2*radius)*texture.shape[1]-.5)[...,0]
    rgb = np.rint(np.clip(mask[...,None]*np.array(color)*energy,0,1)*255).astype(np.uint8)
    image = pygame.Surface(x.shape,pygame.SRCALPHA)
    pygame.surfarray.pixels3d(image)[:] = rgb
    pygame.surfarray.pixels_alpha(image)[:] = rgb.max(axis=2)
    origin = project_screen(center,camera)
    sx,sy = (x-origin[0])/camera.zoom/64,((y-origin[1])/camera.zoom+point[1]*64)/32
    xyz = np.stack(((sx+sy)/2,np.full(x.shape,point[1]),(sy-sx)/2),axis=2)
    volume = SurfaceVolume(center,0,0,xyz,(rgb.max(axis=2)>0).astype(np.uint8),1,
        boundaries=area.boundaries if area else (),solids=area.solids if area else (),
        supports=area.supports if area else (),resolved_occupancy=True)
    key = painter_key((float(point[0]),float(point[2])),elevation_steps=float(point[1]),
        quadrant=camera.quadrant,role='projectile',identity=(identity,))
    return (DrawCommand(key,image,(left,top),pygame.BLEND_RGBA_ADD,(identity,'flare'),volume=volume),)


def directed_draw_commands(timeline: CastTimeline, sample: CastSample, camera: Camera,
                          area: AreaMedia | None) -> tuple[DrawCommand,...]:
    if timeline.recipe.directed is not None and timeline.recipe.directed.material == "noise_ribbon":
        return _directed_ribbon_commands(timeline, sample, camera, area)
    delivery = timeline.recipe.directed
    if delivery is not None and delivery.material == "plasma_trail":
        source = directed_socket(timeline,sample_cast(timeline,timeline.release_ms),camera,delivery)
        if source is None:
            raise ValueError("Directed delivery requires a visible authored release socket")
        charge_source = directed_socket(timeline,sample_cast(timeline,min(sample.media_elapsed_ms,timeline.release_ms)),camera,delivery)
        targets = tuple((row, np.array((row.source.target.grid[0],row.source.target.elevation_steps,
            row.source.target.grid[1])) if isinstance(row.source.target,ObjectContact) else
            _point(timeline,row.source.target,camera,plane_height=delivery.targetPlaneHeightCells))
            for row in timeline.applications)
        return plasma_draw_commands(timeline,sample,camera,area,source,charge_source,targets,
            _texture(timeline.data.resources[delivery.trailTexture]),_texture(timeline.data.resources[delivery.noiseTexture]))
    if (delivery := timeline.recipe.directed) is not None and delivery.material == "darkness_mesh":
        targets=tuple(_point(timeline,row.source.target,camera,plane_height=delivery.targetPlaneHeightCells)
            for row in timeline.applications)
        return darkness_mesh_commands(timeline,sample,camera,area,targets)
    spec = timeline.recipe.arcs
    if spec is None:
        return ()
    time = sample.media_elapsed_ms
    seed = zlib.crc32(timeline.source.root_event_uuid.encode()) + floor(time/45)*191
    random = np.random.default_rng(seed)
    texture = _texture(timeline.data.resources[spec.texture])
    caster = timeline.source.caster
    contacts = {feedback_identity(row.target):row.target for row in timeline.source.applications}
    contacts[caster.actor_uuid] = caster
    body = next((body for body in sample.bodies if body.actor_uuid==caster.actor_uuid),None)
    source = _point(timeline,caster,camera,hand=True,
        body_frame=body.frame if time < timeline.release_ms and body is not None
        and body.clip==timeline.recipe.cast.actionClip else None)
    if spec.mode == 'ground_strike':
        return _ground_strike_contacts(timeline, sample, camera, area, source, texture, random)
    paths: list[tuple[np.ndarray,float,float,float]] = []
    fronts: list[np.ndarray] = []
    line = timeline.source.area_geometry if isinstance(timeline.source.area_geometry,LinePresentationGeometry) else None
    if spec.mode == 'area_line':
        assert line is not None and timeline.source.ground_target is not None
        dx,dz = line.direction
        axis = np.array((dx,0,dz),dtype=float)/hypot(dx,dz)
        side = np.array((-axis[2],0,axis[0]))
        length = line.length_feet/5
        end = np.array((line.origin[0],timeline.source.ground_target.elevation_steps+.87,line.origin[1]))+axis*length
        arrival = timeline.release_ms+min(spec.maximumTravelMs,spec.travelBaseMs+length*spec.travelPerCellMs)
        reveal = max(0.,min(1.,(time-timeline.release_ms)/max(1.,arrival-timeline.release_ms)))
        energy = (.85+.15*_smooth(timeline.release_ms,arrival,time))*(1-_smooth(arrival+spec.decayStartMs,arrival+spec.decayEndMs,time))
        for core in range(spec.coreCount):
            count = max(18,ceil(length/.23))
            t = np.linspace(0,1,count+1)
            spread = np.clip(t/.055,0,1)
            spread = spread*spread*(3-2*spread)*(1-.4*np.array([_smooth(.9,1,float(value)) for value in t]))
            band = (core-(spec.coreCount-1)/2)*.125
            points = source[None,:]+t[:,None]*(end-source)
            points += (band+random.uniform(-.085,.085,count+1))[:,None]*spread[:,None]*side
            points[:,1] += ((1 if core%2 else -1)*.15+random.uniform(-.115,.115,count+1))*spread
            points[0],points[-1] = source,end
            paths.append((points,spec.widthCells if core==0 else spec.secondaryWidthCells,
                energy*(.7 if core==0 else .64),reveal))
        for index in range(ceil(length*1.8)):
            count = len(paths[index%spec.coreCount][0])-1
            segment = 2+int(random.random()*(count-4))
            a = paths[index%spec.coreCount][0][segment]
            b = paths[(index+2)%spec.coreCount][0][min(count,segment+1)]
            paths.append((_jagged(a,b,random,.09),.2,energy*.58,
                max(0.,min(1.,(reveal-segment/count)*8))))
        if 0 < reveal < 1:
            front = source+(end-source)*reveal
            fronts.append(front)
            for k in range(5):
                theta = k*pi*2/5
                outer = front+side*np.cos(theta)*.40+np.array((0,np.sin(theta)*.32,0))
                paths.append((_jagged(outer-axis*.24,front+axis*.10,random,.10),.29,.75,1.))
    else:
        for row in timeline.applications:
            link = row.source.propagation
            if link is None:
                continue
            contact = contacts.get(str(link.source.uuid))
            if contact is None:
                continue
            a = source if str(link.source.uuid)==caster.actor_uuid else _point(timeline,contact,camera)
            b = _point(timeline,row.source.target,camera)
            reveal = max(0.,min(1.,(time-row.travel_start_ms)/max(1.,row.travel_end_ms-row.travel_start_ms)))
            energy = (.85+.15*_smooth(row.travel_start_ms,row.travel_end_ms,time))*(1-_smooth(
                row.travel_end_ms+spec.decayStartMs,row.travel_end_ms+spec.decayEndMs,time))
            points = _jagged(a,b,random)
            if 0 < reveal < 1:
                lengths = np.concatenate(([0.],np.cumsum(np.linalg.norm(np.diff(points,axis=0),axis=1))))
                fronts.append(np.array([np.interp(reveal*lengths[-1],lengths,points[:,axis]) for axis in range(3)]))
            paths.append((points,spec.widthCells if contact is caster else spec.secondaryWidthCells,energy,reveal))
            second = points+random.uniform(-1,1,points.shape)*np.array((.085,.07,.085))
            second[0],second[-1] = points[0],points[-1]
            paths.append((second,.15,energy,reveal))
            for _ in range(3):
                index = min(len(points)-2,2+int(random.random()*max(1,len(points)-4)))
                direction = np.array((random.random()*2-1, random.random()*1.5-.3,
                                      random.random()*2-1))
                direction /= max(float(np.linalg.norm(direction)),.00001)
                fork = _jagged(points[index],points[index]+direction*(.35+random.random()*.65),random,.09)
                paths.append((fork,.18+random.random()*.12,energy,max(0.,min(1.,(reveal-index/(len(points)-1))*8))))
    for row in timeline.applications:
        if row.source.propagation is None and spec.mode=='applications':
            continue
        arrival = row.travel_end_ms
        if time<arrival:
            continue
        energy = (.75+.25*_smooth(arrival,arrival+45,time))*(1-_smooth(
            arrival+spec.contactDecayStartMs,arrival+spec.contactDecayEndMs,time))
        center = _point(timeline,row.source.target,camera)
        # The accepted continuous corridor and linked discharge have distinct
        # source contact/charge equations (bolt.js versus spell.js).
        corridor = spec.mode == 'area_line'
        for k in range(6 if corridor else 4):
            theta = k*pi/(3 if corridor else 2)+random.random()*(.4 if corridor else .7)
            radius = .20+random.random()*(.12 if corridor else .09)
            a = center+np.array((np.cos(theta)*radius,-.55 if corridor else -.5,np.sin(theta)*radius))
            b = center+np.array((np.cos(theta+.6)*radius,.24 if corridor else .16,np.sin(theta+.6)*radius))
            paths.append((_jagged(a,b,random,.15 if corridor else .16),.23 if corridor else .19,
                energy*(.95 if corridor else 1),1.))
    charge = _smooth(spec.chargeStartMs,max(spec.chargeStartMs+1.,timeline.release_ms-50),time)*(1-_smooth(timeline.release_ms,timeline.release_ms+180,time))
    corridor = spec.mode == 'area_line'
    for k in range(7 if corridor else 5):
        angle, radius = (k,.30) if corridor else (k*1.27,.28)
        a = source+np.array((np.cos(angle)*radius,-.10,np.sin(angle)*radius))
        paths.append((_jagged(a,source,random,.15),.16 if corridor else .13,charge*.85,1.))
    commands = tuple(command for index,(points,width,energy,reveal) in enumerate(paths)
        for command in _ribbon(points,width*1.12,texture=texture,frame=(int(time*32/1000)+index*7)%32,
            energy=energy,reveal=reveal,camera=camera,center=caster.grid,
            area=area,line=line,identity=f'{timeline.source.root_event_uuid}:arc:{index}'))
    flares = [(source,charge,True)]
    for row in timeline.applications:
        if row.source.propagation is None and spec.mode == 'applications':
            continue
        arrival = row.travel_end_ms
        if time >= arrival:
            flares.append((_point(timeline,row.source.target,camera),(.75+.25*_smooth(arrival,arrival+45,time))
                *(1-_smooth(arrival+spec.contactDecayStartMs,arrival+spec.contactDecayEndMs,time)),False))
    textured_flares = []
    for index,(point,power,casting) in enumerate(flares):
        textured_flares.extend(((point,spec.glow,46,(.015,.18,.7),power*.7),
            (point,spec.star,36,(1.,.63,.055),power*1.2),(point,spec.streak,35,(.14,.49,.9),power*.6)))
        for k in range(5):
            phase = (time/1000*1.7+k*.193)%1
            travel = 1-phase if casting else phase
            angle = k*2.399+index*.7
            offset = np.array((np.cos(angle)*travel*.55,.2-travel*.28,np.sin(angle)*travel*.55))
            textured_flares.append((point+offset,spec.spark,3.8,(1.,.65,.06),power*(1-phase)*.9))
    for front in fronts:
        textured_flares.extend(((front,spec.glow,25,(.02,.35,.8),.8),(front,spec.star,19,(.8,.65,.12),.8)))
    return commands+tuple(command for index,(point,key,size,color,power) in enumerate(textured_flares)
        for command in _flare(point,_texture(timeline.data.resources[key]),size,color,power,camera,caster.grid,area,
            f'{timeline.source.root_event_uuid}:flare:{index}'))


def _ground_strike_contacts(timeline: CastTimeline, sample: CastSample, camera: Camera,
        area: AreaMedia | None, hand: np.ndarray, texture: np.ndarray,
        random: np.random.Generator) -> tuple[DrawCommand, ...]:
    """Accepted local electric-contact operator; recipients are retained facts."""
    spec = timeline.recipe.arcs
    assert spec is not None
    time = sample.media_elapsed_ms
    paths = []
    charge = _smooth(0, 500, time) * (1-_smooth(timeline.release_ms, timeline.release_ms+150, time))
    for k in range(5):
        angle = k*1.26
        start = hand + np.array((np.cos(angle)*.22, -.12, np.sin(angle)*.22))
        paths.append((_jagged(start, hand, random), .13, charge*.65))
    ground = timeline.ground_delivery
    if ground is not None:
        age = time-ground.travel_end_ms
        energy = (.75+.25*_smooth(0,45,age))*(1-_smooth(320,1120,age)) if age >= 0 else 0
        center = np.array((ground.target.grid[0],ground.target.elevation_steps+.06,ground.target.grid[1]))
        for k in range(9):
            angle = k*2.399
            radius = .65+random.random()*.52
            end = center + np.array((np.cos(angle)*radius,0,np.sin(angle)*radius))
            paths.append((_jagged(center,end,random),.16,energy*.36*(1-_smooth(100,480,age))))
    for row in timeline.applications:
        age = time-row.travel_end_ms
        if age < 0 or not row.source.damage_applied:
            continue
        energy = (.75+.25*_smooth(0,45,age))*(1-_smooth(320,1120,age))
        center = _point(timeline,row.source.target,camera,plane_height=.63)
        for k in range(5):
            angle = k*1.256
            radius = .21+random.random()*.07
            low = center + np.array((np.cos(angle)*radius,-.43,np.sin(angle)*radius))
            high = center + np.array((np.cos(angle+.7)*radius,.43,np.sin(angle+.7)*radius))
            paths.append((_jagged(low,high,random),.20,energy*.8))
    return tuple(command for index,(points,width,energy) in enumerate(paths) if energy > 0
        for command in _ribbon(points,width*1.12,texture=texture,frame=(int(time*32/1000)+index*7)%32,
            energy=energy,reveal=1.,camera=camera,center=timeline.source.caster.grid,area=area,line=None,
            identity=f'{timeline.source.root_event_uuid}:contact:{index}'))


def _smooth_array(begin: float, end: float, value: np.ndarray) -> np.ndarray:
    t = np.clip((value-begin)/(end-begin),0,1)
    return t*t*(3-2*t)


def _noise_ribbon_material(spec: StudioNoiseRibbonDelivery, surface: DirectedSurface,
                           texture: np.ndarray, age: float) -> np.ndarray:
    """Accepted moving-noise shader and source palette; no spell selection."""
    u,v = surface.uv[...,0],surface.uv[...,1]
    noise = repeated_texture(texture,u*8-age*.7,v*2)[...,0]
    along = np.clip((age-.30)/1.13,0,1)-u
    head = np.exp(-(along/.065)**2)
    tail = _smooth_array(-.015,.025,along)*(1-_smooth_array(.12,.42,along))
    bend = .12*np.sin(u*34-age*12+noise*3)
    across = np.abs(v-.5-bend)
    core = 1-_smooth_array(.08,.25,across)
    split = 1-_smooth_array(.025,.08,np.abs(across-.28))
    onset = _smooth(.25,.36,age)*(1-_smooth(1.40,1.50,age))
    energy = .13+.56*head+.26*core*noise
    alpha = np.maximum(core*(head+tail*.70),split*tail*.40)*onset*surface.owned
    return palette_blocks(energy,alpha,spec.palette)


def _eye_material(spec: StudioNoiseRibbonDelivery, surface: DirectedSurface,
                  texture: np.ndarray, age: float, aim: float) -> np.ndarray:
    """Original DreadEye kind-one shader, including its directed pupil shift."""
    uv = surface.uv
    x,y = uv[...,0]*2-1,uv[...,1]*2-1
    t = age+.7
    opened = _smooth(.08,.60,t)
    bow = .43*(1-(np.clip(x,-.78,.78)/.78)**2)
    d = np.where(np.abs(x)<.8,np.minimum(np.abs(y-bow),np.abs(y-bow*(1-2*opened))),10.)
    for a,b in (((.77,0.),(.96,-.17)),((-.77,0.),(-.95,-.12))):
        vx,vy = b[0]-a[0],b[1]-a[1]
        along = np.clip(((x-a[0])*vx+(y-a[1])*vy)/(vx*vx+vy*vy),0,1)
        d = np.minimum(d,np.hypot(x-a[0]-vx*along,y-a[1]-vy*along))
    interior = (np.abs(x)<.65)&(y<bow-.065)&(y>bow*(1-2*opened)+.065)
    phase = t*1.570796327
    iris = np.where(interior&(x>.035),np.abs(np.hypot(x-aim,y)-(.25+.014*np.sin(phase))),10.)
    edge = 1-_smooth_array(.065,.10,d)
    pattern = 1-_smooth_array(.045,.075,iris)
    brightness = .58+(.83-.58)*(.5+.5*np.sin(phase+x*3))
    leftcurve = -.57+.14*np.sin(y*4.5+phase)
    rightcurve = .60+.12*np.sin(y*4-phase+1)
    left = (1-_smooth_array(.065,.12,np.abs(x-leftcurve)))*_smooth_array(-.96,-.78,y)*(1-_smooth_array(-.30,-.20,y))
    right = (1-_smooth_array(.055,.10,np.abs(x-rightcurve)))*_smooth_array(.20,.30,y)*(1-_smooth_array(.75,.93,y))
    noise = repeated_texture(texture,uv[...,0]*2+np.sin(phase)*.20,uv[...,1]*3+np.cos(phase)*.20)[...,0]
    wisps = np.maximum(left,right)*(.55+(.92-.55)*noise)
    pupil = interior*(1-_smooth_array(.06,.10,np.abs(x-aim)))*(1-_smooth_array(.23,.29,np.abs(y)))
    energy = np.maximum(np.maximum(edge*brightness,pattern*.96),wisps*.20)
    energy = np.where(pupil>.5,.10,energy)
    alpha = np.maximum(np.maximum(edge,pattern),np.maximum(wisps,pupil))*surface.owned
    return palette_blocks(energy,alpha,spec.palette)


def directed_source_layer_replacements(timeline: CastTimeline, elapsed_ms: float) -> tuple[str,...]:
    spec = timeline.recipe.directed
    if spec is None or spec.material != "noise_ribbon" or spec.sourceEye is None:
        return ()
    return spec.sourceEye.replaceLayerIds if any(0 <= _directed_age(row.travel_start_ms,
        row.travel_end_ms,elapsed_ms) < 1.5 for row in timeline.applications) else ()


def _directed_age(start: float, end: float, elapsed: float) -> float:
    return .30+(elapsed-start)/max(1.,end-start)*1.13



def _directed_ribbon_commands(timeline: CastTimeline, sample: CastSample, camera: Camera,
                              area: AreaMedia | None) -> tuple[DrawCommand,...]:
    spec = timeline.recipe.directed
    assert spec is not None and spec.material == "noise_ribbon"
    texture = _texture(timeline.data.resources[spec.texture])
    source = directed_socket(timeline,sample,camera,spec)
    if source is None:
        return ()
    caster = timeline.source.caster
    # The donor's native camera is thirty degrees; host height steps are a
    # distinct unit. Transform native vectors after constructing the geometry.
    view = np.array(((1.,.816496580927726,1.),(1.,.816496580927726,-1.),
        (-1.,.816496580927726,-1.),(-1.,.816496580927726,1.))[camera.quadrant])
    view /= np.linalg.norm(view)
    scale = np.array((1.,spec.verticalScale,1.))
    commands = []
    for row in timeline.applications:
        age = _directed_age(row.travel_start_ms,row.travel_end_ms,sample.media_elapsed_ms)
        if not 0 <= age < 1.50:
            continue
        target = _point(timeline,row.source.target,camera,plane_height=spec.targetPlaneHeightCells)
        tangent = (target-source)/scale
        side = np.cross(tangent,view)
        side /= max(float(np.linalg.norm(side)),.000001)
        u = np.linspace(0,1,129)
        points = source[None,:]+u[:,None]*(target-source)
        points[:,1] += np.sin(u*pi)*spec.arcHeightCells
        vertices = (points[:,None,:]+(side*scale)[None,None,:]*np.array([-1,1])[None,:,None]*(spec.widthCells/2)).reshape(-1,3)
        uv = np.column_stack((np.repeat(u,2),np.tile((0.,1.),129)))
        triangles = np.array([(j*2+a,j*2+b,j*2+c) for j in range(128) for a,b,c in ((0,1,2),(1,3,2))])
        surface = rasterize_surface(vertices,uv,triangles,camera)
        if surface is not None:
            command = surface_command(surface,_noise_ribbon_material(spec,surface,texture,age),camera,
                caster.grid,area,f'{timeline.source.root_event_uuid}:{row.source.application_id}:ribbon')
            if command is not None:
                commands.append(command)
        eye = spec.sourceEye
        if eye is None:
            continue
        turn = _smooth(0,.32,age)*(1-_smooth(1.12,1.5,age))
        towards = tangent/max(float(np.linalg.norm(tangent)),.000001)
        normal = view*(1-.34*turn)+towards*(.34*turn)
        normal /= max(float(np.linalg.norm(normal)),.000001)
        right = np.cross((0.,1.,0.),normal)
        right /= max(float(np.linalg.norm(right)),.000001)
        up = np.cross(normal,right)
        vertices = np.array([source+(right*x*eye.sizeCells[0]+up*y*eye.sizeCells[1])*scale
            for x,y in ((-.5,.5),(.5,.5),(-.5,-.5),(.5,-.5))])
        surface = rasterize_surface(vertices,np.array(((0,0),(1,0),(0,1),(1,1))),np.array(((0,1,2),(1,3,2))),camera)
        if surface is not None:
            view_right = np.array((view[2],0,-view[0]))
            view_right /= np.linalg.norm(view_right)
            aim = float(np.dot(towards,view_right))*.20*turn
            command = surface_command(surface,_eye_material(spec,surface,texture,age,aim),camera,
                caster.grid,area,f'{timeline.source.root_event_uuid}:{row.source.application_id}:eye')
            if command is not None:
                commands.append(command)
    return tuple(commands)
