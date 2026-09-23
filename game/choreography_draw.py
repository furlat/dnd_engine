"""Pygame adapter for the shared action/child group, including movement holds."""

from dataclasses import dataclass
from typing import Mapping
from uuid import UUID

import pygame

from dnd.core.life_types import LifeState
from game.animation import ActorContact, CastSample, actor_rest_pose
from game.animation_data import resolve_player_layers
from game.animation_types import AnimationData, RigLayer
from game.animation_draw import (
    AnimationDrawCommand, AnimationMedia, BodyRows, LoadedBodyRows, animation_draw_commands,
    attack_draw_commands, load_actor_media, load_animation_media, load_attack_media,
    action_media_draw_commands, load_action_strip_media, load_cast_rows,
)
from game.attack import AttackSample, BoundAttack
from game.choreography import BoundChoreography, ChoreographySample
from game.combat import BoundCast
from game.condition_animation import ConditionAppearance
from game.condition_draw import load_condition_layers
from game.motion import MotionTimeline
from game.projection import Camera
from game.scene import SceneActor, available_clips, load_scene_media, scene_actors
from game.stationary_media import stationary_media_draw_commands
from game.interruption_draw import reaction_media_draw_commands


@dataclass(frozen=True, slots=True)
class ChoreographyMedia:
    attacks: Mapping[UUID, BodyRows]
    casts: Mapping[UUID, AnimationMedia]
    strips: Mapping[str, pygame.Surface]


def load_choreography_media(bound: BoundChoreography, *,
                             body_rows: LoadedBodyRows | None = None) -> ChoreographyMedia:
    """Load this head's typed body cues into the caller's shared pixel rows."""
    if body_rows is None:
        body_rows = {}
    attacks: dict[UUID, BodyRows] = {}
    casts: dict[UUID, AnimationMedia] = {}
    strips = load_action_strip_media(bound.strips)
    poses: dict[str, set[str]] = {}
    for condition in bound.conditions:
        for appearance in (condition.before_appearance, condition.after_appearance):
            load_condition_layers(appearance.layers, body_rows)
            if appearance.body_pose is not None:
                poses.setdefault(str(condition.target_uuid), set()).add(appearance.body_pose)
    for node in bound.nodes:
        if isinstance(node.bound, BoundAttack):
            timeline = node.bound.timeline
            attacks[node.event_uuid] = load_attack_media(node.bound.timeline, node.bound.appearances,
                                                         body_rows=body_rows)
            contacts = (timeline.source, timeline.target)
        else:
            timeline = node.bound.timeline
            casts[node.event_uuid] = load_animation_media(node.bound.timeline, node.bound.appearances,
                                                          body_rows=body_rows,
                                                          area_boundaries=node.bound.area_boundaries, area_solids=node.bound.area_solids,
                                                          area_supports=node.bound.area_supports)
            contacts = (timeline.source.caster, *(row.target for row in timeline.source.applications))
        # Include intermediate condition poses, even if another child removes
        # that condition before the complete lineage settles.
        load_actor_media(timeline.data, tuple(
            (contact, node.bound.appearances[contact.actor_uuid], tuple(poses[contact.actor_uuid]))
            for contact in contacts if contact.actor_uuid in poses
        ), body_rows=body_rows, all_facings=True)
    # These bodies use the ordinary scene drawer. Their retained appearances
    # can change at equipment commits or at an actual observation in this head.
    actors = [*bound.before.actors.values(), *bound.after.actors.values(),
              *(row.actor for _, row in bound.observations),
              *(cue.bound.after.actors[UUID(cue.bound.timeline.actor.actor_uuid)]
                for cue in bound.equipment)]

    def load(contact: ActorContact, clips: tuple[str, ...], data: AnimationData,
             extra_layers: tuple[tuple[RigLayer, ...], ...] = ()) -> None:
        appearances = dict.fromkeys((
            *(resolve_player_layers(data, actor, rig_id=contact.rig_id)
              for actor in actors if str(actor.uuid) == contact.actor_uuid), *extra_layers))
        load_actor_media(data, tuple((contact, layers, clips) for layers in appearances),
                         body_rows=body_rows, all_facings=True)

    for equipment in bound.equipment:
        cue = equipment.bound
        clips = ((cue.timeline.recipe.bodyClip,) if cue.timeline.recipe.bodyEnabled else ())
        load(cue.timeline.actor, (*clips, "Idle"), cue.timeline.data,
             (cue.appearances[cue.timeline.actor.actor_uuid], cue.replacement))
    for condition in bound.conditions:
        if condition.body is not None:
            cue = condition.body
            load(cue.contact, (cue.clip, "Idle"), cue.data)
    for body_action in bound.body_actions:
        if body_action.enabled:
            recovery = body_action.recovery
            clips = (body_action.clip, "Idle", *((recovery.bodyClip,) if recovery and recovery.enabled else ()))
            load(body_action.contact, clips, body_action.data)
            load_cast_rows(body_action.data, body_action.contact, body_action.clip,
                body_action.contact.facing, body_action.cast_layers, body_rows)
    for shove in bound.shoves:
        load(shove.source, (shove.clip, "Idle"), shove.data)
    for hop in bound.body_hops:
        load(hop.contact, (hop.body_clip, "Idle"), hop.data)
    for forced in bound.forced_movement:
        recovery = forced.data.forced_movement_context.recovery
        clips = (forced.clip, "Idle", *((recovery.bodyClip,) if recovery.enabled else ()))
        load(forced.actor, clips, forced.data)
    for damage in bound.damage:
        clips = {"Idle", damage.data.death_context.bodyClip if damage.resulting_life_state is LifeState.DEAD
                 else damage.data.damage_context.bodyClip}
        rest_pose = actor_rest_pose(damage.data, damage.contact)
        if rest_pose is not None:
            clips.add(rest_pose)
        if damage.timing.hp_ms > damage.timing.start_ms:
            clips.add(damage.data.damage_context.bodyClip)
        if damage.timing.life_body is not None:
            clips.add(damage.timing.life_body.clip)
        load(damage.contact, tuple(clips), damage.data)
    for life in bound.lifecycle:
        if not life.state_owned:
            load(life.contact, ("Idle",), life.data)
        if life.death_end_ms is not None and not life.state_owned:
            load(life.contact, (life.data.death_context.bodyClip,), life.data)
        if life.body is not None:
            load(life.contact, (life.body.clip, "Idle"), life.data)
    for cue in bound.movements:
        for child in load_motion_media(cue.timeline, cue.data, body_rows=body_rows).values():
            attacks.update(child.attacks)
            casts.update(child.casts)
            strips.update(child.strips)
    return ChoreographyMedia(attacks, casts, strips)


def load_motion_media(timeline: MotionTimeline, data: AnimationData, *,
                      body_rows: LoadedBodyRows | None = None) -> dict[UUID, ChoreographyMedia]:
    """Load a bound route and its reactions from existing retained states."""
    if body_rows is None:
        body_rows = {}
    appearances = tuple(actor for state in (timeline.before, *(state for _, state in timeline.states))
                        for actor in scene_actors(state, data, {}))
    load_scene_media(appearances, data, body_rows=body_rows)
    mover = SceneActor(timeline.actor, resolve_player_layers(
        data, timeline.actor_state, rig_id=timeline.actor.rig_id))
    clip = timeline.clip if timeline.clip in available_clips(mover, data) else "Idle"
    if timeline.legs:
        load_actor_media(data, tuple(
            (actor.contact, actor.layers, (clip,)) for actor in (*appearances, mover)
            if actor.contact.actor_uuid == timeline.actor.actor_uuid
        ), body_rows=body_rows, all_facings=True)
    return {reaction.choreography.root_uuid: load_choreography_media(
        reaction.choreography, body_rows=body_rows) for reaction in timeline.reactions}


def choreography_draw_commands(bound: BoundChoreography, sample: ChoreographySample,
                               media: ChoreographyMedia, font: pygame.font.Font,
                               badge_font: pygame.font.Font, camera: Camera, *,
                               condition_appearances: Mapping[str, ConditionAppearance] | None = None,
                               include_bodies: bool = True,
                               ) -> tuple[AnimationDrawCommand, ...]:
    commands: list[tuple[int, AnimationDrawCommand]] = []
    # There is one displayed body per actor. A child's active gesture replaces
    # the parent's idle sample; concurrent projectile and feedback tracks survive.
    owners: dict[str, tuple[bool, float, int]] = {}
    for index, entry in enumerate(sample.clips):
        node, current = entry.node, entry.sample
        if isinstance(node.bound, BoundAttack) and isinstance(current, AttackSample):
            drawn = attack_draw_commands(node.bound.timeline, current, node.bound.appearances,
                media.attacks[node.event_uuid], font, badge_font, camera,
                condition_appearances=condition_appearances, include_bodies=include_bodies)
        elif isinstance(node.bound, BoundCast) and isinstance(current, CastSample):
            drawn = animation_draw_commands(node.bound.timeline, current, media.casts[node.event_uuid], camera,
                                             condition_appearances=condition_appearances, include_bodies=include_bodies)
        else:
            raise ValueError("choreography sample does not match its bound primitive")
        for body in current.bodies:
            rank = body.clip != "Idle", node.start_ms, index
            if body.actor_uuid not in owners or rank > owners[body.actor_uuid]:
                owners[body.actor_uuid] = rank
        commands.extend((index, command) for command in drawn)
    result = [command for index, command in commands
              if command[4][6] not in ("actor", "actor_shadow", "body_copy", "body_contour")
              or owners[str(command[4][0])][2] == index]
    # The shared frame draws condition feedback from retained FloatingText
    # tracks, whose launch contact survives the actor leaving sight.
    return (*result, *(command for cue, elapsed in sample.stationary_media
                      for command in stationary_media_draw_commands((cue,), elapsed, camera)),
            *(command for cue, elapsed in sample.reaction_media
                      for command in reaction_media_draw_commands(cue, elapsed, media.casts.get(cue.incoming_event_uuid), camera)),
            *(command for strip in sample.strips
                      for command in action_media_draw_commands(strip, media.strips, camera)))
