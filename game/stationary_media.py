"""Finite registered media at a disclosed, immutable world contact."""

from dataclasses import dataclass
from typing import Mapping
from uuid import UUID

from game.animation import (ActorContact, BodySample, body_elevation_steps, body_rig,
    media_track_duration, media_track_frame, media_track_opacity, pose_attachment_anchors, view_facing)
from game.animation_types import AnimationData, Facing8, StudioMediaTrack
from game.draw_commands import DrawCommand
from game.media_blend import SCREEN_BLEND
from game.projection import Camera, TILE_WIDTH, painter_key, project_screen, rotate_position, inverse_rotate_position
from game.registered_media import registered_media_blits


def stationary_media_limitations(track: StudioMediaTrack) -> tuple[str, ...]:
    """Check transforms still owned by this sampler, after attachment resolution.

    The producer supplies the immutable contact and height, including body
    attachment heights for condition reactions. Attachment is no longer a
    sampling decision here.
    """
    unsupported = []
    if track.composition != "billboard":
        unsupported.append("world contact media supports billboard composition")
    if track.scaleWithActor or track.orientation != "authored":
        unsupported.append("world contact media has a fixed authored size and orientation")
    if any(value is not None for value in (track.worldOffsetsByFacing,
            track.bodyOffsetsByFacing)):
        unsupported.append("world contact media uses its received contact without socket offsets")
    return tuple(unsupported)


@dataclass(frozen=True, slots=True)
class StationaryMediaCue:
    event_uuid: UUID
    track: StudioMediaTrack
    position: tuple[float, float]
    elevation_steps: float
    facing: Facing8
    start_ms: float
    data: AnimationData
    depth_offset_cells: float = 0
    native_pixels: bool = False
    fade_out_ms: tuple[float, float] | None = None
    actor_uuid: str | None = None

    def __post_init__(self) -> None:
        if limitations := stationary_media_limitations(self.track):
            raise ValueError(f"{self.track.id}: {'; '.join(limitations)}")

    @property
    def end_ms(self) -> float:
        duration = media_track_duration(self.data, self.track)
        return self.start_ms + (min(duration, self.fade_out_ms[1]) if self.fade_out_ms else duration)


def stationary_media_draw_commands(cues: tuple[StationaryMediaCue, ...], elapsed_ms: float,
                                    camera: Camera, *,
                                    actor_contacts: Mapping[str, ActorContact] | None = None,
                                    body_samples: Mapping[str, BodySample] | None = None,
                                    ) -> tuple[DrawCommand, ...]:
    commands = []
    for cue in cues:
        if not cue.start_ms <= elapsed_ms < cue.end_ms:
            continue
        data, track = cue.data, cue.track
        position, height, direction = cue.position, cue.elevation_steps, cue.facing
        contact = (actor_contacts.get(cue.actor_uuid) if actor_contacts is not None
            and cue.actor_uuid is not None else None)
        body = (body_samples.get(cue.actor_uuid) if body_samples is not None
            and cue.actor_uuid is not None else None)
        if cue.actor_uuid is not None:
            if contact is None or body is None:
                continue
            position, direction = contact.grid, body.facing
            height = body_elevation_steps(contact, data)
        asset_id = track.assetIdsByCamera[camera.quadrant] if track.assetIdsByCamera else track.assetId
        alpha = media_track_opacity(data, track, elapsed_ms-cue.start_ms)
        if cue.fade_out_ms is not None:
            begin, end = cue.fade_out_ms
            progress = min(1., max(0., (elapsed_ms-cue.start_ms-begin)/(end-begin)))
            alpha *= 1 - progress*progress*(3-2*progress)
        facing = view_facing(track.viewFacing or direction, camera.quadrant, data)
        frame = media_track_frame(data, track, elapsed_ms-cue.start_ms, facing)
        anchor = project_screen(position, camera, elevation_steps=height)
        socket = track.poseSocket or ('hand' if track.attachment == 'source_hand' else None)
        if socket is not None:
            if body is None or contact is None:
                continue
            rig = body_rig(data, contact)
            scale = contact.visual_scale * TILE_WIDTH/data.rig.TILE_W * camera.zoom
            viewed_body = BodySample(body.actor_uuid, body.clip, body.frame,
                view_facing(body.facing, camera.quadrant, data))
            measured = pose_attachment_anchors(rig, viewed_body, anchor, scale, contact.visual_scale_x)
            if socket not in measured:
                continue
            anchor = measured[socket]
        if track.emissionPointByFacing is not None:
            point = track.emissionPointByFacing[facing]
            factor = track.scale*(1 if cue.native_pixels else TILE_WIDTH/data.rig.TILE_W)*camera.zoom
            anchor = anchor[0]-point.x*factor,anchor[1]-point.y*factor
        rotated = rotate_position(position, camera.quadrant)
        depth_position = inverse_rotate_position((rotated[0] + cue.depth_offset_cells,
                                                  rotated[1] + cue.depth_offset_cells), camera.quadrant)
        key = painter_key(depth_position, elevation_steps=height, quadrant=camera.quadrant,
            role="ground_effect" if track.depth == "ground" else "actor",
            identity=(str(cue.event_uuid), track.id))
        if track.depth in ("behind_body", "front_body"):
            key = (*key[:3], key[3]+(-1 if track.depth == "behind_body" else 1), key[4])
        for image, destination, blend in registered_media_blits(data, asset_id, track.assetPhase,
                frame, facing, scale=track.scale*(1 if cue.native_pixels else TILE_WIDTH/data.rig.TILE_W)*camera.zoom,
                anchor=anchor, rows={}, alpha=alpha):
            commands.append(DrawCommand(key, image, destination, SCREEN_BLEND if track.blendMode == "screen" else blend,
                (str(cue.event_uuid), position, asset_id, "current", None, "authored",
                 "stationary_media", height, track.id, frame)))
    return tuple(commands)
