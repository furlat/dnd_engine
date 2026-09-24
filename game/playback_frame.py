"""One scene composition for live historical playback and recorded review.

The caller owns the head, clocks and decorative-track lifetime. This adapter
only samples retained values and builds commands for the existing map painter.
"""

from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import Mapping, Sequence
from uuid import UUID

import pygame

from dnd.core.life_types import LifeState
from dnd.core.item_types import ItemIntegrity

from game.animation import NumberSample
from game.animation_draw import (
    AnimationDrawCommand, BodyRows, actor_draw_commands, actor_screen_bounds,
    arrange_feedback_commands, number_draw_commands,
    body_trail_draw_command,
)
from game.animation_types import AnimationData, Facing8
from game.choreography import BoundChoreography
from game.choreography_draw import ChoreographyMedia, choreography_draw_commands
from game.condition_animation import condition_transition_appearances, resolve_condition_appearance
from game.condition_media_lifetime import ConditionMediaLifetime, extra_media_members, sample_condition_lifetimes
from game.condition_types import Activity
from game.attack import BoundAttack
from game.feedback import FeedbackTrack, sample_feedback
from game.motion import MotionTimeline
from game.motion_media import MotionMediaCue, motion_media_draw_commands
from game.player_facts import PlayerState
from game.projection import Camera
from game.scene import SceneActor
from game.visual_position import VisualPosition
from game.residue_media import ResidueRevealSample, sample_residue_reveals
from game.world_animation import WorldTransitionSample, sample_world_transitions
from game.device_art import DeviceEmission, device_bank
from game.device_draw import device_draw_command, device_wreck_draw_command
from game.combat import BoundCast
from game.spatial_media_draw import spatial_media_draw_commands
from game.spatial_media_lifetime import SpatialMediaLifetime
from game.portal_draw import portal_draw_commands, clip_portal_bodies
from game.deposit_media import observed_deposits
from game.deposit_draw import deposit_draw_commands
from game.body_presentation import sample_body_presentation
from game.body_history import BodyHistoryHead, sample_body_trails


@dataclass(frozen=True, slots=True)
class PlaybackFrame:
    displayed: PlayerState
    actors: tuple[SceneActor, ...]
    commands: tuple[AnimationDrawCommand, ...]
    complete: bool
    shown_hp: Mapping[str, int | None]
    facings: Mapping[str, Facing8]
    positions: Mapping[str, VisualPosition]
    world_transitions: tuple[WorldTransitionSample, ...] = ()
    residue_reveals: tuple[ResidueRevealSample, ...] = ()
    deposited_materials: frozenset[tuple[UUID, str]] = frozenset()


def sample_playback_frame(
    before: PlayerState, after: PlayerState | None, data: AnimationData,
    elapsed_ms: float, presentation_ms: float, camera: Camera, facings: Mapping[str, Facing8],
    body_media: BodyRows, number_font: pygame.font.Font, badge_font: pygame.font.Font, *,
    choreography: BoundChoreography | None = None, choreography_media: ChoreographyMedia | None = None,
    motion: MotionTimeline | None = None, reaction_media: Mapping[UUID, ChoreographyMedia] | None = None,
    feedback: Sequence[FeedbackTrack] = (),
    motion_media: Sequence[MotionMediaCue] = (),
    condition_lifetimes: Mapping[UUID, ConditionMediaLifetime] = MappingProxyType({}),
    spatial_lifetimes: Mapping[UUID, SpatialMediaLifetime] = MappingProxyType({}),
    deposit_starts: Mapping[UUID, float] = MappingProxyType({}),
    positions: Mapping[str, VisualPosition] | None = None,
    feedback_viewport: pygame.Rect | None = None,
    body_history: tuple[BodyHistoryHead, ...] = (),
) -> PlaybackFrame:
    """Sample one head; ``after=None`` represents an idle scene without a head."""
    body_frame = sample_body_presentation(before, after, data, elapsed_ms, presentation_ms, facings,
        choreography=choreography, motion=motion, positions=positions)
    displayed, actors, complete = body_frame.displayed, body_frame.actors, body_frame.complete
    shown_hp = dict(body_frame.shown_hp)
    resulting_facings, resulting_positions = dict(body_frame.facings), dict(body_frame.positions)
    group, group_sample, group_elapsed = body_frame.group, body_frame.group_sample, body_frame.group_elapsed
    group_media = (reaction_media[group.root_uuid] if motion is not None and group is not None
                   and reaction_media is not None else choreography_media)
    extra: tuple[AnimationDrawCommand, ...] = ()
    condition_appearances = {str(actor.uuid): resolve_condition_appearance(
        actor.conditions, data.condition_recipes, data.condition_media, extra_members=extra_media_members(actor))
                             for actor in displayed.actors.values()}
    activities: dict[str, Activity] = {}
    if motion is not None and any(leg.start_ms <= elapsed_ms < leg.end_ms for leg in motion.legs):
        activities[motion.actor.actor_uuid] = "move" if motion.body_loops else "jump"
    if group is not None:
        for movement in group.movements:
            local = group_elapsed - movement.start_ms
            if any(leg.start_ms <= local < leg.end_ms for leg in movement.timeline.legs):
                activities[movement.timeline.actor.actor_uuid] = "move" if movement.timeline.body_loops else "jump"
        for cue in group.forced_movement:
            if cue.travel_start_ms <= group_elapsed < cue.travel_end_ms:
                activities[cue.actor.actor_uuid] = "forced_move"
        for cue in group.body_actions:
            if cue.start_ms <= group_elapsed < cue.body_end_ms:
                activities[cue.contact.actor_uuid] = "cast" if cue.recipe_id in data.drafts else "act"
        for node in group.nodes:
            if node.start_ms <= group_elapsed < node.start_ms + node.bound.timeline.body_end_ms:
                if isinstance(node.bound, BoundAttack):
                    activities[node.bound.timeline.source.actor_uuid] = "attack"
                else:
                    activities[node.bound.timeline.source.caster.actor_uuid] = "cast"
        for node in group.nodes:
            local = group_elapsed - node.start_ms
            if isinstance(node.bound, BoundAttack):
                timing = node.bound.timeline.damage_timing
                if timing is not None and timing.start_ms <= local < timing.end_ms:
                    activities[node.bound.timeline.target.actor_uuid] = "hit"
            else:
                for application in node.bound.timeline.applications:
                    start, end = application.damage_start_ms, application.damage_end_ms
                    if start is not None and end is not None and start <= local < end:
                        activities[application.source.target.actor_uuid] = "hit"
        for hop in group.body_hops:
            if hop.start_ms <= group_elapsed < hop.end_ms:
                activities[hop.contact.actor_uuid] = "forced_move"
        for cue in group.damage:
            if cue.timing.start_ms <= group_elapsed < cue.timing.end_ms:
                activities[cue.contact.actor_uuid] = "hit"
    condition_appearances = sample_condition_lifetimes(condition_appearances, condition_lifetimes, data, presentation_ms)
    condition_appearances = {identity: replace(appearance, activity=activities.get(identity, "idle"))
                             for identity, appearance in condition_appearances.items()}
    if group is not None and group_sample is not None:
        condition_appearances = condition_transition_appearances(group.conditions, group_elapsed, condition_appearances)
        assert group_media is not None
        extra = choreography_draw_commands(group, group_sample, group_media,
            number_font, badge_font, camera, condition_appearances=condition_appearances, include_bodies=False)
    for pose in body_frame.poses:
        actor, body = pose.actor, pose.body
        appearance = condition_appearances[body.actor_uuid]
        flash = next((value.flash for value in group_sample.vitals if value.actor_uuid == body.actor_uuid), None
                     ) if group_sample is not None else None
        extra = (*extra, *actor_draw_commands(data, body, actor.contact, actor.layers, body_media,
                                              camera, flash=flash, condition=appearance))
    extra = (*extra, *(body_trail_draw_command(trail, data, body_media, camera)
        for trail in sample_body_trails(body_history, body_frame, condition_appearances, data, presentation_ms)))
    # The caller retains each FloatingText track independently of this head.
    extra = tuple(command for command in extra if command.role != "floating_number")
    overlays = tuple(command for track in feedback
                     for number in (sample_feedback(track, presentation_ms),) if number is not None
                     for command in number_draw_commands(data, (number,),
                         {track.contact.actor_uuid: track.contact}, number_font, camera, badge_font=badge_font))
    hidden = group_sample.hidden_actors if group_sample is not None else frozenset()
    labels = tuple(NumberSample(actor.contact.actor_uuid, None, appearance.label.text,
                                appearance.label.color, 0, appearance.alpha, kind="badge")
                   for actor in actors if actor.contact.life_state is not LifeState.DEAD and actor.contact.actor_uuid not in hidden
                   for appearance in (condition_appearances[actor.contact.actor_uuid],)
                   if appearance.label is not None)
    overlays = (*overlays, *number_draw_commands(data, labels,
        {actor.contact.actor_uuid: actor.contact for actor in actors}, number_font, camera,
        badge_font=badge_font))
    # Reuse historical visual facings for objects as well as actors. A completed
    # shot keeps its last body pose without inventing a native firing state.
    devices = {command.owner: command for command in extra
               if command.role in ("device", "device_wreck")}
    if group_sample is not None:
        for clip in group_sample.clips:
            if isinstance(clip.node.bound, BoundCast):
                emitter = clip.node.bound.timeline.source.emitter
                if emitter is not None:
                    resulting_facings[emitter.item_uuid] = emitter.facing
    transitions = sample_world_transitions(motion.world_transitions, elapsed_ms) if motion is not None else ()
    if group is not None and motion is None:
        transitions = (*transitions, *sample_world_transitions(group.world_transitions, group_elapsed))
    for sample in transitions:
        contact = sample.transition.destruction
        if contact is not None:
            resulting_facings[str(contact.body_uuid)] = contact.facing
    for identity, obj in displayed.objects.items():
        art = data.devices.get(obj.item.item_id) or data.device_wrecks.get(obj.item.item_id)
        if art is None or displayed.senses is None or identity not in displayed.senses.objects:
            continue
        key = str(identity)
        if key not in devices:
            facing = resulting_facings.get(key, art.rows[art.rows.index(
                obj.placement.orientation.value.upper() if obj.placement.orientation else "E")])
            if obj.item.integrity is ItemIntegrity.DESTROYED or obj.item.item_id in data.device_wrecks:
                extra = (*extra, device_wreck_draw_command(key, obj.placement.position,
                    obj.placement.base_height_steps, facing, art, camera))
            else:
                emitter = DeviceEmission(key, obj.placement.position, obj.placement.base_height_steps,
                                         facing, art, device_bank(art))
                extra = (*extra, device_draw_command(emitter, 0, camera))
    deposits = observed_deposits(displayed, data)
    extra = (*extra, *deposit_draw_commands(displayed, deposits, deposit_starts, data, presentation_ms, camera),
             *spatial_media_draw_commands(displayed, data, presentation_ms, camera, transitions, spatial_lifetimes),
             *motion_media_draw_commands(motion_media, presentation_ms, camera))
    portals = group_sample.portals if group_sample is not None else ()
    extra = (*extra, *portal_draw_commands(displayed, data, presentation_ms, camera, transitions, portals))
    commands = (*extra, *overlays)
    commands = clip_portal_bodies(commands, camera, portals, hidden)
    commands = arrange_feedback_commands(commands, actor_screen_bounds(commands),
        feedback_viewport if feedback_viewport is not None else pygame.Rect((0, 0), camera.viewport))
    reveals = (sample_residue_reveals(motion.residue_reveals, elapsed_ms) if motion is not None
               else sample_residue_reveals(group.residue_reveals, group_elapsed) if group is not None else ())
    return PlaybackFrame(displayed, tuple(actor for actor in actors if actor.contact.actor_uuid not in hidden), commands, complete,
                         MappingProxyType(shown_hp), MappingProxyType(resulting_facings),
                         MappingProxyType(resulting_positions), transitions, reveals,
                         frozenset((row.source.deposit_uuid, row.material_id) for row in deposits))
