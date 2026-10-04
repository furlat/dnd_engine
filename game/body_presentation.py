"""Pure current/past actor poses from already-bound subjective playback inputs."""

from dataclasses import dataclass, replace
import zlib

from dnd.core.life_types import RemainsDisposition
from typing import Mapping

from game.animation import cast_actor_contacts, BodySample, sample_idle_body
from game.animation_data import resolve_player_layers
from game.animation_types import AnimationData, Facing8
from game.choreography import BoundChoreography, ChoreographySample, MotionTimeline, MotionSample, sample_choreography, sample_motion
from game.player_facts import PlayerState, LifeFact
from game.condition_animation import condition_contact, condition_transition_appearances, resolve_condition_appearance
from game.attack import attack_actor_contacts, BoundAttack
from game.scene import SceneActor, available_clips, scene_actors
from game.visual_position import VisualPosition, placed_contact
from game.entity_lifecycle import lifecycle_body_progress, retiring_pose
from game.body_pose_types import ActorPose as ActorPose


@dataclass(frozen=True, slots=True)
class BodyPresentation:
    displayed: PlayerState
    actors: tuple[SceneActor, ...]
    poses: tuple[ActorPose, ...]
    complete: bool
    shown_hp: Mapping[str, int | None]
    facings: Mapping[str, Facing8]
    positions: Mapping[str, VisualPosition]
    group: BoundChoreography | None
    group_sample: ChoreographySample | None
    group_elapsed: float
    movement_sample: MotionSample | None


def sample_body_presentation(before: PlayerState, after: PlayerState | None, data: AnimationData,
                             elapsed_ms: float, presentation_ms: float, facings: Mapping[str, Facing8], *,
                             choreography: BoundChoreography | None = None, motion: MotionTimeline | None = None,
                             positions: Mapping[str, VisualPosition] | None = None) -> BodyPresentation:
    displayed = before
    shown_hp: dict[str, int | None] = {}
    resulting_facings = dict(facings)
    complete = after is not None
    group = choreography
    group_elapsed = elapsed_ms
    movement_sample = None
    if motion is not None:
        mover = SceneActor(motion.actor, resolve_player_layers(data, motion.actor_state, rig_id=motion.actor.rig_id))
        clips = available_clips(mover, data)
        movement_sample = sample_motion(motion, data, elapsed_ms,
            clip=motion.clip if motion.clip in clips else "Idle")
        complete = movement_sample.complete
        displayed = movement_sample.displayed or before
        shown_hp = {value.actor_uuid: value.hp for value in movement_sample.displayed_vitals}
        group = movement_sample.reaction
        group_elapsed = movement_sample.reaction_elapsed_ms
    group_sample = (movement_sample.reaction_sample if movement_sample is not None
                    else sample_choreography(group, group_elapsed) if group is not None else None)
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
    settled_contacts = group_sample.contacts if group_sample is not None else ()
    if movement_sample is not None and movement_sample.contact is not None:
        settled_contacts = (*settled_contacts, movement_sample.contact)
    if complete:
        for moving in settled_contacts:
            legal = next((actor.contact for actor in legal_actors if actor.contact.actor_uuid == moving.actor_uuid), None)
            if legal is None:
                continue
            if (moving.grid, moving.elevation_steps, moving.body_lift_px) != (legal.grid, legal.elevation_steps, 0):
                resulting_positions[moving.actor_uuid] = VisualPosition(
                    legal.grid, moving.grid, moving.elevation_steps, moving.body_lift_px)
            else:
                resulting_positions.pop(moving.actor_uuid, None)
    actors = tuple(replace(actor, contact=placed_contact(
        actor.contact, resulting_positions.get(actor.contact.actor_uuid))) for actor in legal_actors)
    if group_sample is not None:
        placed = {contact.actor_uuid: contact for contact in group_sample.contacts}
        actors = tuple(replace(actor, contact=replace(actor.contact,
            grid=placed[actor.contact.actor_uuid].grid,
            elevation_steps=placed[actor.contact.actor_uuid].elevation_steps,
            body_lift_px=placed[actor.contact.actor_uuid].body_lift_px,
            facing=placed[actor.contact.actor_uuid].facing))
            if actor.contact.actor_uuid in placed else actor for actor in actors)
    if movement_sample is not None and movement_sample.contact is not None:
        moving_contact = movement_sample.contact
        actors = tuple(replace(actor, contact=moving_contact)
                       if actor.contact.actor_uuid == moving_contact.actor_uuid else actor for actor in actors)
    appearances = {actor.contact.actor_uuid: actor.condition for actor in actors}
    if group is not None:
        appearances = condition_transition_appearances(group.conditions, group_elapsed, appearances)
    actors = tuple(replace(actor, condition=appearances[actor.contact.actor_uuid],
        contact=condition_contact(actor.contact, appearances[actor.contact.actor_uuid])) for actor in actors)
    # Same active gesture precedence as the action compositor, followed by
    # explicit condition/equipment/movement bodies owned by the complete head.
    bodies: dict[str, BodySample] = {}
    ranks: dict[str, tuple[bool, float, int]] = {}
    clip_actors: dict[str, SceneActor] = {}
    clip_loadouts: set[str] = set()
    if group_sample is not None:
        for index, entry in enumerate(group_sample.clips):
            contacts = (attack_actor_contacts(entry.node.bound.timeline) if isinstance(entry.node.bound, BoundAttack)
                        else cast_actor_contacts(entry.node.bound.timeline.source))
            for body in entry.sample.bodies:
                rank = body.clip != "Idle", entry.node.start_ms, index
                if body.actor_uuid not in ranks or rank > ranks[body.actor_uuid]:
                    ranks[body.actor_uuid] = rank
                    bodies[body.actor_uuid] = body
                    clip_loadouts.add(body.actor_uuid)
                    contact = next(row for row in contacts if row.actor_uuid == body.actor_uuid)
                    retained = next(row for row in displayed.actors.values() if str(row.uuid) == body.actor_uuid)
                    clip_actors[body.actor_uuid] = SceneActor(contact,
                        entry.node.bound.appearances[body.actor_uuid],
                        resolve_condition_appearance(retained.conditions, data.condition_recipes, data.condition_media))
        for body in group_sample.bodies:
            bodies[body.actor_uuid] = body
            clip_loadouts.discard(body.actor_uuid)
    if movement_sample is not None and movement_sample.contact is not None:
        contact = movement_sample.contact
        selected = bodies.get(contact.actor_uuid)
        if selected is None or (contact.body_lift_px > 0 and selected.clip == "Idle"):
            body = sample_idle_body(data, contact, presentation_ms) if complete else movement_sample.body
            if body is not None:
                bodies[contact.actor_uuid] = body
    if complete:
        # Completed attacks/casts share the ordinary scene's idle clock, just
        # like completed movement and body gestures. Keep the settled facing.
        for actor in actors:
            identity = actor.contact.actor_uuid
            body = bodies.get(identity)
            if body is not None and body.clip == "Idle":
                bodies[identity] = sample_idle_body(data,
                    replace(actor.contact, facing=body.facing), presentation_ms)
    resulting_facings.update((identity, body.facing) for identity, body in bodies.items())
    # A bound finite clip already owns its admitted recipient contact. Preserve
    # that contact while its hit/death finishes even when its final observation
    # no longer supplies an ordinary idle-scene actor.
    present = {actor.contact.actor_uuid for actor in actors}
    # The active gesture binds its actual weapon set before its committed
    # Attack fact reaches the displayed state. Keep that gesture and loadout
    # together; explicit equipment/condition bodies above own their own layers.
    pose_actors = (*(replace(actor, layers=clip_actors[actor.contact.actor_uuid].layers)
        if actor.contact.actor_uuid in clip_loadouts else actor for actor in actors),
        *(actor for identity, actor in clip_actors.items() if identity not in present))
    poses = tuple(ActorPose(actor, bodies.get(actor.contact.actor_uuid)
                           or sample_idle_body(data, actor.contact, presentation_ms)) for actor in pose_actors)
    if group_sample is not None:
        visible_poses = {pose.actor.contact.actor_uuid: pose for pose in poses}
        for cue, age in group_sample.entity_lifecycle:
            identity = cue.actor.contact.actor_uuid
            if age < cue.start_ms or cue.phase == "bond":
                continue
            if cue.phase == "departure":
                # Replace any retained action body rather than drawing it twice.
                visible_poses.pop(identity, None)
                retiring = retiring_pose(cue, age)
                if retiring is not None:
                    visible_poses[identity] = retiring
            elif identity in visible_poses:
                visible_poses[identity] = replace(visible_poses[identity],
                                                  coverage=lifecycle_body_progress(cue, age))
        poses = tuple(visible_poses.values())
    if group is not None:
        # Sample this same value pipeline immediately before the native life
        # anchor. No second body clock or independently inferred death pose.
        visible_poses = {pose.actor.contact.actor_uuid: pose for pose in poses}
        for cue in group.lifecycle:
            fact = cue.event.fact
            if not isinstance(fact, LifeFact) or fact.remains_disposition is not RemainsDisposition.DISINTEGRATED:
                continue
            identity = str(fact.entity_uuid)
            if group_elapsed < cue.start_ms:
                continue
            visible_poses.pop(identity, None)
            dust = data.death_context.silhouetteDust
            if dust is None or group_elapsed >= cue.start_ms + dust.duration_ms:
                continue
            prior_time = max(0., cue.start_ms - .001)
            prior_frame = sample_body_presentation(before, after if cue.start_ms > 0 else None, data, prior_time,
                presentation_ms - (group_elapsed-prior_time), facings,
                choreography=group if cue.start_ms > 0 else None, positions=positions)
            prior_pose = next((pose for pose in prior_frame.poses if pose.actor.contact.actor_uuid == identity), None)
            if prior_pose is None:
                continue
            retained_actor = replace(prior_pose.actor, layers=tuple(layer for layer in prior_pose.actor.layers
                if layer.item_uuid not in fact.preserved_equipped_item_uuids))
            visible_poses[identity] = replace(prior_pose, actor=retained_actor,
                appearance_override=prior_pose.appearance_override or prior_pose.actor.condition,
                dust_elapsed_ms=group_elapsed-cue.start_ms,
                dust_seed=zlib.crc32(str(cue.event.uuid).encode()))
        poses = tuple(visible_poses.values())
    return BodyPresentation(displayed, actors, poses, complete, shown_hp, resulting_facings,
                            resulting_positions, group, group_sample, group_elapsed, movement_sample)
