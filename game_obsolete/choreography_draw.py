"""Pygame adapter for the shared action/child group, including movement holds."""

from dataclasses import dataclass, field, replace
from typing import Mapping
from uuid import UUID

import pygame

from dnd.core.life_types import LifeState
from dnd.types.world import WorldEdgeChannel
from game.area_media import AreaMedia
from game.animation_types import AreaSolid
from game.animation import cast_actor_contacts, ActorContact, CastSample, actor_rest_pose, BodySample, death_body_context, sample_idle_body
from game.animation_data import resolve_player_layers
from game.animation_types import AnimationData, RigLayer
from game.animation_draw import (
    AnimationDrawCommand, AnimationMedia, BodyRows, LoadedBodyRows, animation_draw_commands,
    attack_draw_commands, load_actor_media, load_animation_media, load_attack_media,
    action_media_draw_commands, load_action_strip_media, load_cast_rows,
)
from game.attack import AttackSample, BoundAttack, attack_actor_contacts, attack_projectile_height
from game.choreography import BoundChoreography, ChoreographySample
from game.combat import BoundCast
from game.condition_animation import ConditionAppearance, condition_body_pose
from game.condition_draw import load_condition_layers
from game.motion import MotionTimeline
from game.projection import Camera
from game.portal_animation import portal_body
from game.body_pose_types import SceneActor
from game.scene_actors import available_clips, scene_actors
from game.scene import load_scene_media
from game.stationary_draw import stationary_media_draw_commands
from game.interruption_draw import reaction_media_draw_commands
from game.wind_flow_media import wind_interception_commands


@dataclass(frozen=True, slots=True)
class ChoreographyMedia:
    attacks: Mapping[UUID, BodyRows]
    casts: Mapping[UUID, AnimationMedia]
    strips: Mapping[str, pygame.Surface]
    staged_areas: dict[UUID, AreaMedia] = field(default_factory=dict)


def load_choreography_media(bound: BoundChoreography, *,
                             body_rows: LoadedBodyRows | None = None) -> ChoreographyMedia:
    """Load this head's typed body cues into the caller's shared pixel rows."""
    if body_rows is None:
        body_rows = {}
    attacks: dict[UUID, BodyRows] = {}
    casts: dict[UUID, AnimationMedia] = {}
    strips = load_action_strip_media(bound.strips)
    poses: dict[str, list[ConditionAppearance]] = {}
    for condition in bound.conditions:
        for appearance in (condition.before_appearance, condition.after_appearance):
            load_condition_layers(appearance.layers, body_rows)
            if appearance.body_pose is not None or appearance.frozen_pose is not None:
                poses.setdefault(str(condition.target_uuid), []).append(appearance)
    for node in bound.nodes:
        if isinstance(node.bound, BoundAttack):
            timeline = node.bound.timeline
            attacks[node.event_uuid] = load_attack_media(node.bound.timeline, node.bound.appearances,
                                                         body_rows=body_rows)
            contacts = attack_actor_contacts(timeline)
        else:
            timeline = node.bound.timeline
            casts[node.event_uuid] = load_animation_media(node.bound.timeline, node.bound.appearances,
                                                          body_rows=body_rows,
                                                          area_boundaries=node.bound.area_boundaries, area_solids=node.bound.area_solids,
                                                          area_supports=node.bound.area_supports)
            contacts = cast_actor_contacts(timeline.source)
        # Include intermediate condition poses, even if another child removes
        # that condition before the complete lineage settles.
        load_actor_media(timeline.data, tuple(
            (contact, node.bound.appearances[contact.actor_uuid], tuple(condition_body_pose(timeline.data,
                BodySample(contact.actor_uuid, "Idle", 0, contact.facing), contact, appearance).clip
                for appearance in poses[contact.actor_uuid]))
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
        selected = cue.timeline.body_context
        clips = ((selected.actor.clip,) if selected is not None and selected.actor.enabled else ())
        load(cue.timeline.actor, (*clips, "Idle"), cue.timeline.data,
             (cue.appearances[cue.timeline.actor.actor_uuid], cue.replacement))
    for condition in bound.conditions:
        if condition.body is not None:
            cue = condition.body
            clips = tuple(condition_body_pose(cue.data, BodySample(cue.contact.actor_uuid, "Idle", 0, cue.contact.facing),
                cue.contact, appearance).clip for appearance in poses.get(cue.contact.actor_uuid, ()))
            load(cue.contact, (cue.clip, "Idle", *clips), cue.data)
    for body_action in bound.body_actions:
        recovery = body_action.recovery_body
        clips = (*((body_action.clip, "Idle") if body_action.enabled else ()),
                 *((recovery.actor.clip,) if recovery and recovery.actor.enabled else ()))
        if clips:
            load(body_action.contact, clips, body_action.data)
        if body_action.enabled:
            load_cast_rows(body_action.data, body_action.contact, body_action.clip,
                body_action.contact.facing, body_action.cast_layers, body_rows)
    for shove in bound.shoves:
        load(shove.source, (shove.clip, "Idle"), shove.data)
    for hop in bound.body_hops:
        load(hop.contact, (hop.body_clip, "Idle"), hop.data)
    for forced in bound.forced_movement:
        recovery = forced.recovery_body
        clips = (forced.clip, "Idle", *((recovery.actor.clip,) if recovery and recovery.actor.enabled else ()),
                 *((forced.flight_body.actor.clip,) if forced.flight_body is not None else ()))
        load(forced.actor, clips, forced.data)
    for portal in bound.portals:
        contact = portal.departure or portal.arrival
        if contact is not None:
            body = portal_body(portal, portal.fall_start_ms + 1)
            if body is None:
                body = portal_body(portal, portal.arrival_ms + 1)
            load(contact, ('Idle', body.clip) if body is not None else ('Idle',), portal.data)
    for healing in bound.healing:
        if healing.contact is not None and healing.body_context is not None and healing.body_context.actor.enabled and healing.data is not None:
            load(healing.contact, (healing.body_context.actor.clip, "Idle"), healing.data)
    for damage in bound.damage:
        clips = {"Idle", death_body_context(damage.data, damage.contact).actor.clip if damage.resulting_life_state is LifeState.DEAD
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
            load(life.contact, (death_body_context(life.data, life.contact).actor.clip,), life.data)
        if life.body is not None:
            load(life.contact, (life.body.clip, "Idle"), life.data)
    for cue in bound.entity_lifecycle:
        contact = cue.actor.contact
        resting = condition_body_pose(cue.data, sample_idle_body(cue.data, contact, 0.),
                                      contact, cue.actor.condition)
        load_actor_media(cue.data, ((contact, cue.actor.layers,
            ("Idle", resting.clip, death_body_context(cue.data, contact).actor.clip)),), body_rows=body_rows, all_facings=True)
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
        recovery = timeline.recovery_body
        clips = (clip, *((recovery.actor.clip,) if recovery and recovery.actor.enabled else ()))
        load_actor_media(data, tuple(
            (actor.contact, actor.layers, clips) for actor in (*appearances, mover)
            if actor.contact.actor_uuid == timeline.actor.actor_uuid
        ), body_rows=body_rows, all_facings=True)
    return {reaction.choreography.root_uuid: load_choreography_media(
        reaction.choreography, body_rows=body_rows) for reaction in timeline.reactions}


def choreography_draw_commands(bound: BoundChoreography, sample: ChoreographySample,
                               media: ChoreographyMedia, font: pygame.font.Font,
                               badge_font: pygame.font.Font, camera: Camera, *,
                               condition_appearances: Mapping[str, ConditionAppearance] | None = None,
                               include_bodies: bool = True,
                               actor_bounds: Mapping[str, pygame.Rect] | None = None,
                               body_samples: Mapping[str, BodySample] | None = None,
                               actor_contacts: Mapping[str, ActorContact] | None = None,
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
            timeline = node.bound.timeline
            projectile = timeline.projectile
            if projectile is not None and projectile.interception is not None:
                contact = projectile.interception
                drawn = (*drawn,*wind_interception_commands(timeline.data,contact.components,
                    contact.position,attack_projectile_height(timeline,1.,camera.quadrant),contact.tangent,
                    (timeline.target.grid[0]-timeline.source.grid[0],timeline.target.grid[1]-timeline.source.grid[1]),
                    current.elapsed_ms-projectile.end_ms,camera,timeline.root_event_uuid))
        elif isinstance(node.bound, BoundCast) and isinstance(current, CastSample):
            cast_media = media.casts[node.event_uuid]
            if node.bound.staged_area:
                # Topology is retained at authored destruction clearance, not
                # taken from the final native map at frame zero.
                objects = sample.displayed.objects.values()
                boundaries = tuple(obj.placement for obj in objects
                    if obj.item.boundary_structure is not None
                    and WorldEdgeChannel.PROPAGATION in obj.item.boundary_structure.blocked_channels)
                solids = tuple(AreaSolid(position, obj.placement.base_height_steps, obj.placement.top_height_steps)
                    for obj in objects if obj.item.boundary_structure is None and obj.item.blocks_propagation
                    for position in obj.placement.positions) + tuple(
                    AreaSolid(tile.position, tile.elevation_steps) for tile in sample.displayed.tiles.values()
                    if tile.blocks_propagation)
                admitted = tuple(sorted({position for at, positions in node.bound.area_reach
                    if current.media_elapsed_ms >= at for position in positions}))
                area = media.staged_areas.get(node.event_uuid, cast_media.area)
                if area is None or area.boundaries != boundaries or area.solids != solids or area.admitted != admitted:
                    area = AreaMedia(boundaries, solids, tuple(sample.displayed.tiles.values()), admitted=admitted)
                    media.staged_areas[node.event_uuid] = area
                cast_media = replace(cast_media, area=area)
            drawn = animation_draw_commands(node.bound.timeline, current, cast_media, camera,
                                             condition_appearances=condition_appearances, include_bodies=include_bodies,
                                             actor_bounds=actor_bounds, body_samples=body_samples,
                                             actor_contacts=actor_contacts)
        else:
            raise ValueError("choreography sample does not match its bound primitive")
        for body in current.bodies:
            rank = body.clip != "Idle", node.start_ms, index
            if body.actor_uuid not in owners or rank > owners[body.actor_uuid]:
                owners[body.actor_uuid] = rank
        commands.extend((index, command) for command in drawn)
    result = [command for index, command in commands
              if command.role not in ("actor", "actor_shadow", "body_copy", "body_contour")
              or owners[command.owner][2] == index]
    # The shared frame draws condition feedback from retained FloatingText
    # tracks, whose launch contact survives the actor leaving sight.
    return (*result, *(command for cue, elapsed in sample.stationary_media
                      for command in stationary_media_draw_commands((cue,), elapsed, camera,
                          actor_contacts=actor_contacts, body_samples=body_samples)),
            *(command for cue, elapsed in sample.reaction_media
                      for command in reaction_media_draw_commands(cue, elapsed, media.casts.get(cue.incoming_event_uuid), camera)),
            *(command for strip in sample.strips
                      for command in action_media_draw_commands(strip, media.strips, camera)))
