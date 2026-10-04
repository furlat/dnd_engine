"""Authored orbit components and local wakes on a received spatial owner."""

from functools import lru_cache
from math import atan2, cos, floor, pi, sin
from uuid import UUID

import numpy as np
import pygame

from game.animation_types import AnimationData, GroundEllipse, OrbitMedia, SpatialMediaLayer
from game.area_media import AreaLayer, AreaMedia
from game.draw_commands import DrawCommand
from game.media_blend import SCREEN_BLEND
from game.player_facts import PlayerState
from game.projection import Camera, TILE_WIDTH, TILE_HEIGHT, painter_key, project_screen
from game.registered_media import registered_media_samples


def _smooth(value: float) -> float:
    value = min(1., max(0., value))
    return value*value*(3-2*value)


def _rgb(value: int) -> tuple[int, int, int]:
    return value >> 16, value >> 8 & 255, value & 255


def orbit_point(recipe: OrbitMedia, index: int, time_ms: float, formation: float = 1.,
                age_ms: float = 0, lane: float = 0) -> tuple[float, float, float]:
    time = time_ms-age_ms
    cycle = floor(time/recipe.periodMs)
    slot = (index+cycle*recipe.slotsPerCycle) % recipe.count
    theta = (slot/recipe.count+(time % recipe.periodMs)/recipe.periodMs*recipe.slotsPerCycle/recipe.count)*2*pi
    age = age_ms/1000
    spread = sin(min(1., age/.45)*pi/2)
    radius = recipe.radiusCells*formation+lane*.035*spread
    return cos(theta)*radius, sin(theta)*radius, recipe.heightCells-age*.045+lane*.025*spread


@lru_cache(maxsize=1)
def _noise_grid() -> np.ndarray:
    seed, values = 74921, []
    for _ in range(4096):
        seed = (seed*1664525+1013904223) & 0xffffffff
        values.append(seed/4294967296)
    result = np.array(values).reshape(64,64)
    result.setflags(write=False)
    return result


def _noise(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    ix, iy = np.floor(x).astype(int), np.floor(y).astype(int)
    u, v = x-ix, y-iy
    u, v = u*u*(3-2*u), v*v*(3-2*v)
    grid = _noise_grid()
    a, b = grid[iy & 63, ix & 63], grid[iy & 63, (ix+1) & 63]
    c, d = grid[(iy+1) & 63, ix & 63], grid[(iy+1) & 63, (ix+1) & 63]
    return (a+(b-a)*u)*(1-v)+(c+(d-c)*u)*v


@lru_cache(maxsize=128)
def _mist(radius: float, low: tuple[int,int,int], spread: tuple[int,int,int], frame: int, quadrant: int, zoom: float) -> pygame.Surface:
    width, height = round(radius*2*TILE_WIDTH*zoom), round(radius*2*TILE_HEIGHT*zoom)
    x, y = np.indices((width,height), dtype=np.float32)
    u, v = (x+.5-width/2)/(TILE_WIDTH*zoom), (y+.5-height/2)/(TILE_HEIGHT*zoom)
    dx, dz = u+v, v-u
    dx, dz = ((dx,dz), (dz,-dx), (-dx,-dz), (-dz,dx))[quadrant]
    nx, nz = dx/radius, dz/radius
    phase = frame/64*2*pi
    flow_x, flow_y = cos(phase)*.32, sin(phase)*.32
    warp = _noise(nx*3+12+flow_x,nz*3+8+flow_y)
    flow = _noise(nx*5.5+23+warp*.9-flow_x,nz*5.5+15+warp*.7-flow_y)
    fine = _noise(nx*14+4+flow_y,nz*14+32-flow_x)
    edge = np.clip((np.hypot(nx,nz)-(.78+warp*.08))/(.985-(.78+warp*.08)),0,1)
    edge = 1-edge*edge*(3-2*edge)
    wisps = np.clip((flow*.78+fine*.22-.29)/(.74-.29),0,1)
    wisps = wisps*wisps*(3-2*wisps)
    light = wisps*.8+fine*.2
    image = pygame.Surface((width,height),pygame.SRCALPHA)
    pygame.surfarray.blit_array(image, np.rint(np.array(low)+light[...,None]*np.array(spread)).astype(np.uint8))
    alpha = pygame.surfarray.pixels_alpha(image)
    alpha[:] = np.rint(edge*(.055+wisps*.29)*255).astype(np.uint8)
    del alpha
    return image


def ground_ellipse_command(identity: UUID, recipe: GroundEllipse, origin: tuple[float,float],
                           height: float, camera: Camera, alpha: float) -> DrawCommand:
    points = [project_screen((origin[0]+recipe.radiiCells[0]*cos(index*pi/32),
        origin[1]+recipe.radiiCells[1]*sin(index*pi/32)), camera, elevation_steps=height) for index in range(64)]
    left, top = floor(min(p[0] for p in points)), floor(min(p[1] for p in points))
    image = pygame.Surface((max(1,round(max(p[0] for p in points)-left)+1),
        max(1,round(max(p[1] for p in points)-top)+1)),pygame.SRCALPHA)
    pygame.draw.polygon(image,(*_rgb(recipe.color),round(255*recipe.alpha*alpha)),[(x-left,y-top) for x,y in points])
    return DrawCommand(painter_key(origin,elevation_steps=height,quadrant=camera.quadrant,
        role="ground_effect",identity=(str(identity),"shadow")),image,(left,top),0,(str(identity),"ground_shadow"))


def _overlaps_owned(point: tuple[float,float], cells: set[tuple[int,int]], radius: float) -> bool:
    """A sprite may overlap a disclosed cell although its center rounds outside it."""
    return any(max(0,abs(point[0]-x)-.5)**2+max(0,abs(point[1]-y)-.5)**2 <= radius*radius
        for x,y in cells)


def orbit_media_commands(state: PlayerState, data: AnimationData, identity: UUID,
                         layer: SpatialMediaLayer, origin: tuple[float,float], height: float,
                         time_ms: float, age_ms: float | None, alpha: float,
                         positions: tuple[tuple[int,int],...], camera: Camera,
                         area: AreaMedia, native_origin: tuple[float,float] | None = None,
                         suppressed: frozenset[tuple[int,int]] = frozenset()) -> tuple[DrawCommand,...]:
    recipe, senses = layer.orbit, state.senses
    assert recipe is not None
    if senses is None:
        return ()
    admitted = set(positions) & set(senses.visible)
    owner_origin = native_origin if native_origin is not None else origin
    delta = origin[0]-owner_origin[0], origin[1]-owner_origin[1]
    if not admitted:
        return ()
    formation = _smooth(age_ms/recipe.formationMs) if age_ms is not None else 1.
    alpha *= formation
    if alpha <= 0:
        return ()
    result = []
    mist = _mist(recipe.mistRadiusCells,recipe.mistLow,recipe.mistRange,floor(time_ms*32/1000)%64,camera.quadrant,camera.zoom).copy()
    if formation != 1:
        mist = pygame.transform.smoothscale(mist,(max(1,round(mist.width*formation)),max(1,round(mist.height*formation))))
    anchor = project_screen(origin,camera,elevation_steps=height+.015)
    destination = (round(anchor[0]-mist.width/2),round(anchor[1]-mist.height/2))
    # Each visible native cell grants only its own ground pixels.
    mask = pygame.Surface(mist.size,pygame.SRCALPHA)
    for x,y in admitted:
        corners = [project_screen((x+dx+delta[0],y+dy+delta[1]),camera,elevation_steps=height+.015)
            for dx,dy in ((-.5,-.5),(.5,-.5),(.5,.5),(-.5,.5))]
        pygame.draw.polygon(mask,(255,255,255,255),[(px-destination[0],py-destination[1]) for px,py in corners])
    visible_mask = pygame.Surface(mist.size,pygame.SRCALPHA)
    for x,y in senses.visible:
        if (x,y) in suppressed:
            continue
        corners = [project_screen((x+dx,y+dy),camera,elevation_steps=height+.015)
            for dx,dy in ((-.5,-.5),(.5,-.5),(.5,.5),(-.5,.5))]
        pygame.draw.polygon(visible_mask,(255,255,255,255),[(px-destination[0],py-destination[1]) for px,py in corners])
    mask.blit(visible_mask,(0,0),special_flags=pygame.BLEND_RGBA_MULT)
    mist.blit(mask,(0,0),special_flags=pygame.BLEND_RGBA_MULT)
    mist.set_alpha(round(alpha*255))
    result.append(DrawCommand(painter_key(origin,elevation_steps=height,quadrant=camera.quadrant,
        role="ground_effect",identity=(str(identity),"mist")),mist,destination,SCREEN_BLEND if recipe.blendMode == "screen" else 0,
        (str(identity),"orbit_mist"),area=AreaLayer(origin,height,area)))
    for index in range(recipe.count):
        local = orbit_point(recipe,index,time_ms,formation)
        world = origin[0]+local[0],origin[1]+local[1]
        local_owner = world[0]-delta[0],world[1]-delta[1]
        seen = floor(world[0]+.5),floor(world[1]+.5)
        if _overlaps_owned(local_owner,admitted,recipe.sizePixels/TILE_WIDTH) and seen in senses.visible and seen not in suppressed:
            theta = atan2(local[1],local[0])
            yaw = atan2(sin(theta),-cos(theta))
            bank = (floor(yaw/(pi/4)+.5)+2*camera.quadrant)%8
            facing = data.rig.AUTHORED_PROJECTILE_ROW_ORDER[bank]
            frame = floor(time_ms*32/1000+2*sin(theta))%16
            point = project_screen(world,camera,elevation_steps=height+local[2])
            for part in registered_media_samples(data,layer.assetId,"impact",frame,facing,
                    scale=recipe.sizePixels/160*camera.zoom,anchor=point,rows={},alpha=alpha):
                result.append(DrawCommand(painter_key(world,elevation_steps=height+local[2],quadrant=camera.quadrant,
                    role="actor",identity=(str(identity),"orbit",str(index))),part.image,part.destination,part.blend,
                    (str(identity),"orbit_component",index,world,frame)))
        for step in range(recipe.trailSamples):
            age = step*recipe.trailMs/recipe.trailSamples
            if age_ms is not None and age_ms < age:
                continue
            a = orbit_point(recipe,index,time_ms,formation,age)
            b = orbit_point(recipe,index,time_ms,formation,age+recipe.trailMs/recipe.trailSamples)
            middle = origin[0]+(a[0]+b[0])/2,origin[1]+(a[1]+b[1])/2
            if (not _overlaps_owned((middle[0]-delta[0],middle[1]-delta[1]),admitted,8/TILE_WIDTH)
                    or (floor(middle[0]+.5),floor(middle[1]+.5)) not in senses.visible
                    or (floor(middle[0]+.5),floor(middle[1]+.5)) in suppressed):
                continue
            points = [project_screen((origin[0]+p[0],origin[1]+p[1]),camera,elevation_steps=height+p[2]) for p in (a,b)]
            padding = max(2,round(8*camera.zoom))
            left,top = floor(min(p[0] for p in points))-padding,floor(min(p[1] for p in points))-padding
            image = pygame.Surface((round(abs(points[1][0]-points[0][0]))+padding*2+2,
                round(abs(points[1][1]-points[0][1]))+padding*2+2),pygame.SRCALPHA)
            fade = (1-age/recipe.trailMs)**1.6*alpha
            local_points = [(x-left,y-top) for x,y in points]
            for width,opacity,color in ((7+age/1000*8,.07,recipe.middle),(4+age/1000*4,.13,recipe.middle),
                                        ):
                pygame.draw.line(image,(*_rgb(color),round(255*fade*opacity)),local_points[0],local_points[1],max(1,round(width*camera.zoom)))
            for lane in (-1,0,1):
                lane_points = [orbit_point(recipe,index,time_ms,formation,t,lane) for t in (age,age+recipe.trailMs/recipe.trailSamples)]
                projected = [project_screen((origin[0]+p[0],origin[1]+p[1]),camera,elevation_steps=height+p[2]) for p in lane_points]
                theta = atan2(a[1],a[0])
                flow = .62+.38*sin(((time_ms-age)%recipe.periodMs)/recipe.periodMs*2*pi*3+theta+lane*.8)**2
                pygame.draw.line(image,(*_rgb(recipe.bright if lane == 0 else recipe.middle),round(255*fade*(.34 if lane == 0 else .20)*flow)),
                    (projected[0][0]-left,projected[0][1]-top),(projected[1][0]-left,projected[1][1]-top),max(1,round((1.3 if lane == 0 else 2.5)*camera.zoom)))
            if step % 7 == 0:
                theta = atan2(a[1],a[0])
                mote = orbit_point(recipe,index,time_ms,formation,age,sin(theta+step))
                px,py = project_screen((origin[0]+mote[0],origin[1]+mote[1]),camera,elevation_steps=height+mote[2])
                pygame.draw.rect(image,(*_rgb(recipe.bright),round(255*fade*.55)),
                    (round(px-left),round(py-top),max(1,round(1.2*camera.zoom)),max(1,round(1.2*camera.zoom))))
            result.append(DrawCommand(painter_key(middle,elevation_steps=height+(a[2]+b[2])/2,quadrant=camera.quadrant,
                role="projectile",identity=(str(identity),"wake",str(index),str(step))),image,(left,top),SCREEN_BLEND if recipe.blendMode == "screen" else 0,
                (str(identity),"orbit_wake",index,step,middle)))
    return tuple(result)
