"""One scene composition for live historical playback and recorded review.

The caller owns the head, clocks and decorative-track lifetime. This adapter
only samples retained values and builds commands for the existing map painter.
"""

from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import Mapping, Sequence
from uuid import UUID

import pygame

from game.animation import sample_idle_body
from game.animation_draw import (
    AnimationDrawCommand, BodyRows, actor_draw_commands, actor_screen_bounds,
    arrange_feedback_commands, number_draw_commands,
)
from game.animation_types import AnimationData, Facing8
from game.choreography import BoundChoreography, sample_choreography
from game.choreography_draw import ChoreographyMedia, choreography_draw_commands
from game.condition_animation import condition_transition_appearances, resolve_condition_appearance
from game.feedback import FeedbackTrack, sample_feedback
from game.motion import MotionTimeline, sample_motion
from game.presentation import PresentationTarget
from game.projection import Camera
from game.scene import SceneActor, available_clips, scene_actors, scene_draw_commands
from game.visual_position import VisualPosition


@dataclass(frozen=True, slots=True)
class PlaybackFrame:
    displayed: PresentationTarget
    actors: tuple[SceneActor, ...]
    commands: tuple[AnimationDrawCommand, ...]
    complete: bool
    shown_hp: Mapping[str, int | None]
    facings: Mapping[str, Facing8]
    positions: Mapping[str, VisualPosition]


def sample_playback_frame(
    before: PresentationTarget, after: PresentationTarget | None, data: AnimationData,
    elapsed_ms: float, presentation_ms: float, camera: Camera, facings: Mapping[str, Facing8],
    body_media: BodyRows, number_font: pygame.font.Font, badge_font: pygame.font.Font, *,
    choreography: BoundChoreography | None = None, choreography_media: ChoreographyMedia | None = None,
    motion: MotionTimeline | None = None, reaction_media: Mapping[UUID, ChoreographyMedia] | None = None,
    feedback: Sequence[FeedbackTrack] = (),
    positions: Mapping[str, VisualPosition] | None = None,
    feedback_viewport: pygame.Rect | None = None,
) -> PlaybackFrame:
    """Sample one head; ``after=None`` represents an idle scene without a head."""
    displayed = before
    shown_hp: dict[str, int | None] = {}
    resulting_facings = dict(facings)
    complete = after is not None
    extra: tuple[AnimationDrawCommand, ...] = ()
    excluded: frozenset[str] = frozenset()
    group = choreography
    group_media = choreography_media
    group_elapsed = elapsed_ms
    movement_sample = None
    if motion is not None:
        mover = next(actor for actor in scene_actors(before, data, facings)
                     if actor.contact.actor_uuid == motion.actor.actor_uuid)
        clips = available_clips(mover, data)
        movement_sample = sample_motion(motion, data, elapsed_ms,
            clip=motion.clip if motion.clip in clips else "Idle")
        complete = movement_sample.complete
        displayed = movement_sample.displayed or before
        shown_hp = {value.actor_uuid: value.hp for value in movement_sample.displayed_vitals}
        group = movement_sample.reaction
        group_elapsed = movement_sample.reaction_elapsed_ms
        if group is not None:
            assert reaction_media is not None
            group_media = reaction_media[group.root_uuid]
        else:
            group_media = None
    group_sample = sample_choreography(group, group_elapsed) if group is not None else None
    if group_sample is not None:
        displayed = group_sample.displayed
        shown_hp.update((value.actor_uuid, value.hp) for value in group_sample.vitals)
        if motion is None:
            complete = group_sample.complete
    if complete and after is not None:
        displayed = after
    legal_actors = scene_actors(displayed, data, facings)
    resulting_positions = {actor.contact.actor_uuid: position for actor in legal_actors
                           if positions is not None
                           and (position := positions.get(actor.contact.actor_uuid)) is not None
                           and position.legal_grid == actor.contact.grid}
    if movement_sample is not None and complete:
        moving = movement_sample.contact
        legal = next(actor.contact for actor in legal_actors if actor.contact.actor_uuid == moving.actor_uuid)
        if (moving.grid, moving.elevation_steps, moving.body_lift_px) != (legal.grid, legal.elevation_steps, 0):
            resulting_positions[moving.actor_uuid] = VisualPosition(
                legal.grid, moving.grid, moving.elevation_steps, moving.body_lift_px)
        else:
            resulting_positions.pop(moving.actor_uuid, None)
    actors = scene_actors(displayed, data, facings, resulting_positions)
    if movement_sample is not None:
        actors = tuple(replace(actor, contact=movement_sample.contact)
                       if actor.contact.actor_uuid == movement_sample.contact.actor_uuid else actor for actor in actors)
    condition_appearances = {str(actor.uuid): resolve_condition_appearance(actor.conditions, data.condition_recipes)
                             for actor in displayed.actors.values()}
    if group is not None and group_sample is not None:
        condition_appearances = condition_transition_appearances(group.conditions, group_elapsed, condition_appearances)
        assert group_media is not None
        extra = choreography_draw_commands(group, group_sample, group_media, data,
            {actor.contact.actor_uuid: actor.contact for actor in actors},
            number_font, badge_font, camera, condition_appearances=condition_appearances)
        bodies = tuple(body for entry in group_sample.clips for body in entry.sample.bodies)
        excluded = frozenset(body.actor_uuid for body in bodies)
        resulting_facings.update((body.actor_uuid, body.facing) for body in bodies)
    if movement_sample is not None:
        moving = movement_sample.contact
        if moving.actor_uuid not in excluded:
            mover = next(actor for actor in actors if actor.contact.actor_uuid == moving.actor_uuid)
            body = sample_idle_body(data, moving, presentation_ms) if complete else movement_sample.body
            extra = (*extra, *actor_draw_commands(data, body, moving, mover.layers, body_media,
                                                 camera, condition=condition_appearances[moving.actor_uuid]))
        excluded = excluded | {moving.actor_uuid}
        resulting_facings[moving.actor_uuid] = moving.facing
    # The caller retains each FloatingText track independently of this head.
    extra = tuple(command for command in extra if command[4][6] != "floating_number")
    overlays = tuple(command for track in feedback
                     for number in (sample_feedback(track, presentation_ms),) if number is not None
                     for command in number_draw_commands(data, (number,),
                         {track.contact.actor_uuid: track.contact}, number_font, camera, badge_font=badge_font))
    commands = (*scene_draw_commands(actors, data, body_media, camera, presentation_ms, exclude=excluded,
                                    condition_appearances=condition_appearances), *extra, *overlays)
    commands = arrange_feedback_commands(commands, actor_screen_bounds(commands),
        feedback_viewport if feedback_viewport is not None else pygame.Rect((0, 0), camera.viewport))
    return PlaybackFrame(displayed, actors, commands, complete,
                         MappingProxyType(shown_hp), MappingProxyType(resulting_facings),
                         MappingProxyType(resulting_positions))
