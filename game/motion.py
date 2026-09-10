"""Retained movement with original pre-edge reaction/body timing.

One motion head contains its actual Step children and their attack subtrees.
The engine owns committed endpoints; subcell lead-in exists only in playback.
"""

from dataclasses import dataclass, replace
from math import hypot
from typing import Mapping

from dnd.actions import AttackEvent, JumpEvent, MovementEvent, SpellEvent
from dnd.core.events import StepMovementEvent
from game.animation import (
    ActorContact, BodySample, VitalsSample, body_clip, body_frame,
    facing_for_delta, sample_idle_body,
)
from game.animation_types import AnimationData
from game.choreography import BoundChoreography, bind_choreography, sample_choreography
from game.combat import actor_contact
from game.presentation import CompletedLineage, PresentationTarget, lineage_branch, reduce_lineage


@dataclass(frozen=True, slots=True)
class MotionLeg:
    start: tuple[float, float]
    end: tuple[float, float]
    start_height: float
    end_height: float
    start_ms: float
    end_ms: float
    body_start_ms: float = 0
    arc_height_px: float = 0
    curve_from: float = 0
    curve_to: float = 1
    initial_lift_px: float = 0


@dataclass(frozen=True, slots=True)
class MotionReaction:
    choreography: BoundChoreography
    contact: ActorContact
    source: ActorContact
    start_ms: float
    end_ms: float
    lift_px: float = 0
    action_label: str | None = None


@dataclass(frozen=True, slots=True)
class MotionTimeline:
    actor: ActorContact
    legs: tuple[MotionLeg, ...]
    clip: str
    playback_speed: float
    arc_height_px: float
    complete_ms: float
    reactions: tuple[MotionReaction, ...]
    settled_contact: ActorContact
    before: PresentationTarget
    settled_lift_px: float = 0


@dataclass(frozen=True, slots=True)
class MotionSample:
    contact: ActorContact
    body: BodySample
    lift_px: float
    complete: bool
    reaction: BoundChoreography | None = None
    reaction_elapsed_ms: float = 0
    displayed_vitals: tuple[VitalsSample, ...] = ()
    displayed: PresentationTarget | None = None


def bind_motion(target: PresentationTarget, lineage: CompletedLineage,
                data: AnimationData, *, contacts: Mapping[str, ActorContact] | None = None) -> MotionTimeline | None:
    """Use actual committed steps and complete melee subtrees on their edge."""
    if not isinstance(lineage.root, (MovementEvent, JumpEvent)):
        return None
    steps = tuple(event for event in lineage.events if isinstance(event, StepMovementEvent)
                  and event.source_entity_uuid == lineage.root.source_entity_uuid
                  and event.parent_lineage == lineage.root.lineage_uuid)
    if not steps:
        return None
    actor = actor_contact(target, target.actors[lineage.root.source_entity_uuid], data)
    contacts = contacts or {}
    actor = contacts.get(actor.actor_uuid, actor)
    context = data.movement_context
    jumping = isinstance(lineage.root, JumpEvent)
    legs: list[MotionLeg] = []
    reactions: list[MotionReaction] = []
    elapsed = body_start = 0.0
    working = target
    settled = actor
    settled_lift = 0.0
    reaction_context = data.movement_reaction_context
    for step_index, step in enumerate(steps):
        branch = lineage_branch(lineage, step)
        attacks = tuple(event for event in branch.events if isinstance(event, (AttackEvent, SpellEvent))
                        and event.parent_lineage == step.lineage_uuid)
        start, end = step.from_position, step.to_position
        height, end_height = step.from_elevation_feet / 5, step.to_elevation_feet / 5
        delta = end[0] - start[0], end[1] - start[1]
        distance = hypot(*delta)
        duration = (min(context.jumpMaxDurationMs, max(context.jumpMinDurationMs,
                    context.jumpBaseDurationMs + distance * context.jumpPerCellDurationMs))
                    if jumping else context.walkStepDurationMs * distance)
        arc = min(context.jumpArcMaxPx, context.jumpArcBasePx + distance * context.jumpArcPerCellPx) if jumping else 0
        initial_lift = actor.body_lift_px if step_index == 0 else 0
        if step_index == 0:
            start, height = actor.grid, actor.elevation_steps
            delta = end[0] - start[0], end[1] - start[1]
        fraction = 0.0
        continuation: tuple[float, float] = start
        continuation_height = height
        if attacks:
            if (reaction_context.bodyEnabled or reaction_context.media or reaction_context.recovery.enabled):
                return None
            fraction = min(0.35, max(0.12, reaction_context.movementLeadInMs /
                                   (duration if jumping else context.walkStepDurationMs)))
            continuation = start[0] + delta[0] * fraction, start[1] + delta[1] * fraction
            continuation_height = height + (end_height - height) * fraction
            lead_end = elapsed + (duration * fraction if jumping else reaction_context.movementLeadInMs)
            legs.append(MotionLeg(start, continuation, height, continuation_height,
                                  elapsed, lead_end, body_start, arc, 0, fraction, initial_lift))
            elapsed = lead_end
            facing = facing_for_delta(delta, data)
            for attack_event in attacks:
                held = replace(actor_contact(working, working.actors[step.source_entity_uuid], data), grid=continuation,
                               elevation_steps=continuation_height, facing=facing,
                               body_lift_px=4 * arc * fraction * (1 - fraction) + initial_lift * (1 - fraction))
                group = bind_choreography(working, lineage_branch(lineage, attack_event), data,
                    facings={actor.actor_uuid: facing}, contacts={**contacts, actor.actor_uuid: held})
                source = contacts.get(str(attack_event.source_entity_uuid)) or actor_contact(
                    working, working.actors[attack_event.source_entity_uuid], data)
                reactions.append(MotionReaction(group, held, source, elapsed, elapsed + group.complete_ms,
                                                4 * arc * fraction * (1 - fraction) + initial_lift * (1 - fraction),
                                                attack_event.name))
                elapsed += group.complete_ms
                working = group.after
            body_start = elapsed  # beginBodyTravel(Walking) restarts after hit recovery.
            duration *= 1 - fraction
        if step.committed:
            legs.append(MotionLeg(continuation, end, continuation_height, end_height,
                                  elapsed, elapsed + duration, body_start, arc, fraction, 1, initial_lift))
            elapsed += duration
        # Step results update the working retained contact for the next edge.
        # Its attack after-values are idempotent facts, not repeated mechanics.
        working = reduce_lineage(working, branch)
        settled = actor_contact(working, working.actors[step.source_entity_uuid], data, facing_for_delta(delta, data))
        if not step.committed:
            # The legal Step stays at its origin. Playback keeps the position
            # where its reaction stopped; completion is not a return animation.
            settled_lift = 4 * arc * fraction * (1 - fraction) + initial_lift * (1 - fraction)
            settled = replace(settled, grid=continuation, elevation_steps=continuation_height,
                              body_lift_px=settled_lift)
            break
    if not legs:
        return None
    return MotionTimeline(actor, tuple(legs), context.jumpClip if jumping else context.walkClip,
                          1 if jumping else context.walkPlaybackSpeed,
                          max(leg.arc_height_px for leg in legs), elapsed, tuple(reactions), settled, target, settled_lift)


def sample_motion(timeline: MotionTimeline, data: AnimationData, elapsed_ms: float,
                  *, clip: str | None = None) -> MotionSample:
    """Changing view or intake progress cannot alter authored movement time."""
    elapsed = max(0.0, min(elapsed_ms, timeline.complete_ms))
    complete = elapsed_ms >= timeline.complete_ms
    vitals: dict[str, VitalsSample] = {}
    displayed = timeline.before
    active: MotionReaction | None = None
    for reaction in timeline.reactions:
        if elapsed < reaction.start_ms:
            break
        sample = sample_choreography(reaction.choreography, elapsed - reaction.start_ms)
        displayed = sample.displayed
        vitals.update((value.actor_uuid, value) for value in sample.vitals)
        if elapsed < reaction.end_ms:
            active = reaction
            break
    if active is not None:
        contact = active.contact
        sample = sample_choreography(active.choreography, elapsed - active.start_ms)
        bodies = [body for clip_sample in sample.clips for body in clip_sample.sample.bodies
                  if body.actor_uuid == contact.actor_uuid]
        body = bodies[-1] if bodies else sample_idle_body(data, contact, elapsed)
        return MotionSample(contact, body, active.lift_px, False, active.choreography,
                            elapsed - active.start_ms, tuple(vitals.values()), displayed)
    leg = next((leg for leg in timeline.legs if elapsed < leg.end_ms), timeline.legs[-1])
    progress = min(1.0, max(0.0, (elapsed - leg.start_ms) / (leg.end_ms - leg.start_ms)))
    delta = leg.end[0] - leg.start[0], leg.end[1] - leg.start[1]
    facing = facing_for_delta(delta, data)
    curve = leg.curve_from + (leg.curve_to - leg.curve_from) * progress
    lift = 4 * leg.arc_height_px * curve * (1 - curve) + leg.initial_lift_px * (1 - curve)
    contact = replace(timeline.actor, grid=(leg.start[0] + delta[0] * progress,
                                           leg.start[1] + delta[1] * progress), facing=facing,
                      elevation_steps=leg.start_height + (leg.end_height - leg.start_height) * progress,
                      body_lift_px=lift)
    current = vitals.get(contact.actor_uuid)
    if current is not None:
        contact = replace(contact, hp=current.hp, life_state=current.life_state)
    if complete:
        contact = replace(timeline.settled_contact, facing=facing)
        if timeline.reactions and timeline.legs[-1].end_ms != timeline.complete_ms:
            return MotionSample(contact, sample_idle_body(data, contact, elapsed), timeline.settled_lift_px, True,
                                displayed_vitals=tuple(vitals.values()), displayed=displayed)
    selected = clip or timeline.clip
    metadata = body_clip(data, contact, selected)
    frame = body_frame(elapsed - leg.body_start_ms, metadata.fps * timeline.playback_speed,
                       metadata.frames, loop=True)
    if leg.arc_height_px and selected == timeline.clip:
        frame = min(metadata.frames - 1, int(curve * metadata.frames))
    return MotionSample(contact, BodySample(contact.actor_uuid, selected, frame, facing),
                        lift, complete, displayed_vitals=tuple(vitals.values()), displayed=displayed)
