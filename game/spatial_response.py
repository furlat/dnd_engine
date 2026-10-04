"""Finite directed gestures for disclosed spatial owners and admitted recipients."""

from dataclasses import dataclass
from math import atan2, cos, floor, pi, sin
from typing import Mapping
from uuid import UUID

import pygame

from dnd.types.senses import PerceivedSpatialEffect
from game.animation import ActorContact, facing_for_delta
from game.animation_types import AnimationData, DirectedSpatialResponse, MediaTimePoint, StudioMediaTrack
from game.draw_commands import DrawCommand
from game.media_blend import SCREEN_BLEND
from game.player_facts import DamageRequestFact, DamageResultFact, PlayerState
from game.projection import Camera, painter_key, project_screen
from game.stationary_media import StationaryMediaCue, stationary_media_draw_commands


@dataclass(frozen=True, slots=True)
class SpatialResponseCue:
    owner_uuid: UUID
    recipient: ActorContact
    recipe: DirectedSpatialResponse
    media: StationaryMediaCue

    @property
    def contact_ms(self) -> float:
        return self.media.start_ms+self.recipe.contactFrame*1000/self.recipe.fps


def damage_spatial_owner(state: PlayerState, fact: DamageRequestFact | DamageResultFact,
                         created: Mapping[UUID, tuple[PerceivedSpatialEffect,...]]) -> PerceivedSpatialEffect | None:
    identity = fact.source_condition_uuid
    if identity is None:
        return None
    return (state.senses.spatial_effects.get(identity) if state.senses is not None else None) or next(iter(created.get(identity,())),None)


def bind_spatial_response(event_uuid: UUID, owner_uuid: UUID, effect: PerceivedSpatialEffect,
                          recipient: ActorContact, recipe: DirectedSpatialResponse,
                          data: AnimationData, start_ms: float, *, retired: bool) -> SpatialResponseCue | None:
    origin, height = effect.anchor_position, effect.anchor_elevation_steps
    if origin is None or height is None:
        return None
    facing = facing_for_delta((recipient.grid[0]-origin[0],recipient.grid[1]-origin[1]),data)
    duration = recipe.frames*1000/recipe.fps
    points = [MediaTimePoint(elapsedMs=0,sourceFrame=float(recipe.firstFrame)),
        MediaTimePoint(elapsedMs=(recipe.frames-1)*1000/recipe.fps,sourceFrame=float(recipe.firstFrame+recipe.frames-1))]
    end = duration+1150 if retired else duration
    points.append(MediaTimePoint(elapsedMs=end,sourceFrame=float(recipe.firstFrame+recipe.frames-1)))
    track = StudioMediaTrack(id="directed-owner-response",assetId=recipe.assetId,attachment="area_ground",
        durationMs=end,scale=recipe.scale,timeMap=tuple(points))
    media = StationaryMediaCue(event_uuid,track,origin,height,facing,start_ms,data,
        fade_out_ms=(duration,end) if retired else None)
    return SpatialResponseCue(owner_uuid,recipient,recipe,media)


def spatial_response_draw_commands(cues: tuple[SpatialResponseCue,...], elapsed_ms: float,
                                   camera: Camera) -> tuple[DrawCommand,...]:
    result = []
    for cue in cues:
        media, recipe = cue.media, cue.recipe
        result.extend(stationary_media_draw_commands((media,),elapsed_ms,camera))
        age = elapsed_ms-media.start_ms
        frame = floor(age*recipe.fps/1000)
        if not recipe.bladeMotion or not 9 <= frame <= 20:
            continue
        dx,dy = cue.recipient.grid[0]-media.position[0],cue.recipient.grid[1]-media.position[1]
        heading = floor(atan2(-dx,-dy)/(pi/4)+.5)*pi/4
        c,s,k = cos(heading),sin(heading),recipe.bladeWorldScale
        def point(value: tuple[float,float,float]) -> tuple[float,float]:
            x,y,z = value
            return project_screen((media.position[0]+(x*c+z*s)*k,
                media.position[1]+(-x*s+z*c)*k),camera,elevation_steps=media.elevation_steps+y*k)
        polygons = []
        for back in range(3,-1,-1):
            index = max(0,min(recipe.frames-1,frame-back))
            grip,tip = recipe.bladeMotion[index]
            old_grip,old_tip = recipe.bladeMotion[max(0,index-1)]
            inner = (grip[0]+(tip[0]-grip[0])*.8,grip[1]+(tip[1]-grip[1])*.8,grip[2]+(tip[2]-grip[2])*.8)
            old_inner = (old_grip[0]+(old_tip[0]-old_grip[0])*.8,old_grip[1]+(old_tip[1]-old_grip[1])*.8,old_grip[2]+(old_tip[2]-old_grip[2])*.8)
            polygons.append((back,(point(inner),point(tip),point(old_tip),point(old_inner))))
        points = [point for _,polygon in polygons for point in polygon]
        contact_age = (elapsed_ms-cue.contact_ms)/1000
        continuation = []
        if -.07 <= contact_age < .2:
            tip = point(recipe.bladeMotion[recipe.contactFrame][1])
            target = project_screen(cue.recipient.grid,camera,elevation_steps=cue.recipient.elevation_steps+.95)
            control = ((tip[0]+target[0])/2,(tip[1]+target[1])/2-16*camera.zoom)
            continuation = [((1-t)**2*tip[0]+2*(1-t)*t*control[0]+t*t*target[0],
                (1-t)**2*tip[1]+2*(1-t)*t*control[1]+t*t*target[1]) for t in (i/16 for i in range(17))]
            points.extend(continuation)
        left,top = floor(min(p[0] for p in points))-4,floor(min(p[1] for p in points))-4
        image = pygame.Surface((round(max(p[0] for p in points)-left)+5,
            round(max(p[1] for p in points)-top)+5),pygame.SRCALPHA)
        def color(value: int,alpha: float) -> tuple[int,int,int,int]:
            return value>>16,value>>8&255,value&255,round(max(0,min(1,alpha))*255)
        taper = max(0,min(1,(21-frame)/5))
        for back,polygon in polygons:
            local = [(x-left,y-top) for x,y in polygon]
            pygame.draw.polygon(image,color(recipe.palette[0],(1-back/4)*.16*taper),local)
            pygame.draw.line(image,color(recipe.palette[1],(1-back/4)*.6*taper),local[1],local[2],max(1,round(2.5*camera.zoom)))
        if continuation:
            amp = min(1,max(0,(contact_age+.07)/.07))*(1-min(1,max(0,(contact_age-.04)/.16)))
            pygame.draw.lines(image,color(recipe.palette[2],amp*.85),False,
                [(x-left,y-top) for x,y in continuation],max(1,round(4*camera.zoom)))
        result.append(DrawCommand(painter_key(media.position,elevation_steps=media.elevation_steps,
            quadrant=camera.quadrant,role="projectile",identity=(str(media.event_uuid),"blade")),
            image,(left,top),SCREEN_BLEND if recipe.blendMode == "screen" else 0,(str(media.event_uuid),"directed_blade",str(cue.owner_uuid),frame)))
    return tuple(result)
