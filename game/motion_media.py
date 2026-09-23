"""Decorative movement tracks sampled from disclosed historical motion legs."""

from dataclasses import dataclass, replace
from math import ceil
from uuid import UUID
from typing import Sequence

from game.animation import ActorContact, body_elevation_steps
from game.animation_types import AnimationData, StudioMediaTrack
from game.choreography import BoundChoreography, MotionLeg, MotionTimeline, motion_leg_contact
from game.draw_commands import DrawCommand
from game.projection import Camera
from game.stationary_media import StationaryMediaCue, stationary_media_draw_commands


@dataclass(frozen=True, slots=True)
class MotionMediaCue:
    media: StationaryMediaCue
    actor: ActorContact | None = None
    leg: MotionLeg | None = None
    motion_start_ms: float = 0


def bind_motion_media(timeline: MotionTimeline, data: AnimationData,
                      absolute_start_ms: float) -> tuple[MotionMediaCue, ...]:
    """Resolve finite emissions once; these tails never extend the action join."""
    cues = [MotionMediaCue(replace(media, start_ms=absolute_start_ms+media.start_ms))
            for media in timeline.contact_media]
    tracks = data.movement_context.walkMedia if timeline.body_loops else data.movement_context.jumpMedia
    for index, leg in enumerate(timeline.legs):
        state = next((state for at, state in reversed(timeline.states) if at <= leg.start_ms), timeline.before)
        actor = state.actors.get(UUID(timeline.actor.actor_uuid), timeline.actor_state)
        conditions = {member.behavior_id for member in actor.conditions}
        for track in tracks:
            if not set(track.whenConditions) <= conditions or set(track.unlessConditions) & conditions:
                continue
            if track.role == "takeoff" and index != 0 or track.role == "landing" and index != len(timeline.legs)-1:
                continue
            asset = data.projectile_assets[track.assetId]
            assert asset.phases.impact is not None
            duration = asset.phases.impact.frames*1000/track.fps
            if track.fitToMotion:
                duration = leg.end_ms-leg.start_ms
            authored = StudioMediaTrack(id=track.id, assetId=track.assetId,
                attachment="source_ground", fps=asset.phases.impact.frames*1000/duration,
                durationMs=duration, scale=track.scale, alpha=track.alpha, depth=track.depth,
                viewFacing=track.viewFacing)
            if track.role == "trail":
                assert track.emitIntervalMs is not None
                # Continue the emission cadence across corners, without emitting
                # at hidden path points or filling a reaction pause with motion.
                first = ceil(leg.start_ms/track.emitIntervalMs)*track.emitIntervalMs
                times = tuple(first+i*track.emitIntervalMs for i in range(
                    max(0, ceil((leg.end_ms-first)/track.emitIntervalMs))))
            else:
                times = (leg.end_ms if track.role == "landing" else leg.start_ms,)
            for at in times:
                contact = motion_leg_contact(timeline.actor, leg, data, at)
                attached = track.attachment == "body" and track.role != "trail"
                media = StationaryMediaCue(UUID(timeline.actor.actor_uuid), authored, contact.grid,
                    contact.elevation_steps, contact.facing,
                    absolute_start_ms+at-track.contactFrame*1000/track.fps, data)
                cues.append(MotionMediaCue(media, timeline.actor if attached else None,
                    leg if attached else None, absolute_start_ms))
    for reaction in timeline.reactions:
        cues.extend(choreography_motion_media(reaction.choreography, data, absolute_start_ms+reaction.start_ms))
    return tuple(cues)


def choreography_motion_media(group: BoundChoreography, data: AnimationData,
                               absolute_start_ms: float) -> tuple[MotionMediaCue, ...]:
    return (*(MotionMediaCue(replace(media, start_ms=absolute_start_ms+media.start_ms))
              for media in group.contact_media),
            *(cue for motion in group.movements for cue in bind_motion_media(
                motion.timeline, data, absolute_start_ms+motion.start_ms)))


def motion_media_draw_commands(cues: Sequence[MotionMediaCue],
                               presentation_ms: float, camera: Camera) -> tuple[DrawCommand, ...]:
    commands = []
    for cue in cues:
        media = cue.media
        if not media.start_ms <= presentation_ms < media.end_ms:
            continue
        if cue.actor is not None and cue.leg is not None:
            contact = motion_leg_contact(cue.actor, cue.leg, media.data, presentation_ms-cue.motion_start_ms)
            media = replace(media, position=contact.grid,
                elevation_steps=body_elevation_steps(contact, media.data), facing=contact.facing)
        commands.extend(stationary_media_draw_commands((media,), presentation_ms, camera))
    return tuple(commands)
