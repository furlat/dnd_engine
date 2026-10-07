"""Finite directed gestures for disclosed spatial owners and admitted recipients."""

from dataclasses import dataclass
from typing import Mapping
from uuid import UUID


from dnd.types.senses import PerceivedSpatialEffect
from game.animation import ActorContact, facing_for_delta
from game.animation_types import AnimationData, DirectedSpatialResponse, MediaTimePoint, StudioMediaTrack
from dnd.player.facts import DamageRequestFact, DamageResultFact, PlayerState
from game.stationary_media import StationaryMediaCue


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
