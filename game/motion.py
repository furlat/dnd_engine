"""Retained movement with walking edge reactions and grounded jump reactions.

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
from game.presentation import (
    CompletedLineage, PresentationTarget, lineage_branch, reduce_lineage, stage_actors, stage_lineage,
)


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
    body_loops: bool = True
    states: tuple[tuple[float, PresentationTarget], ...] = ()


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


def _bind_jump(target: PresentationTarget, lineage: CompletedLineage, jump: JumpEvent,
               steps: tuple[StepMovementEvent, ...], data: AnimationData,
               actor: ActorContact, contacts: Mapping[str, ActorContact]) -> MotionTimeline | None:
    """Resolve retained reactions at launch, then traverse one authored flight."""
    requested = jump.requested_end_position or jump.end_position
    facing = facing_for_delta((requested[0] - actor.grid[0], requested[1] - actor.grid[1]), data)
    launch = replace(actor, facing=facing)
    working = target
    elapsed = 0.0
    reactions: list[MotionReaction] = []
    for step in steps:
        branch = lineage_branch(lineage, step)
        for event in branch.events:
            if not isinstance(event, (AttackEvent, SpellEvent)) or event.parent_lineage != step.lineage_uuid:
                continue
            reaction_context = data.movement_reaction_context
            if reaction_context.bodyEnabled or reaction_context.media or reaction_context.recovery.enabled:
                return None
            current = working.actors[step.source_entity_uuid]
            held = replace(launch, hp=current.normal_hp, life_state=current.life_state)
            group = bind_choreography(working, lineage_branch(lineage, event), data,
                facings={actor.actor_uuid: facing}, contacts={**contacts, actor.actor_uuid: held})
            source = contacts.get(str(event.source_entity_uuid)) or actor_contact(
                group.after, group.after.actors[event.source_entity_uuid], data)
            reactions.append(MotionReaction(group, held, source, elapsed, elapsed + group.complete_ms,
                                            held.body_lift_px, event.name))
            elapsed += group.complete_ms
            working = group.after
        working = reduce_lineage(working, branch)
        if not step.committed:
            break
    settled = actor_contact(working, working.actors[jump.source_entity_uuid], data, facing)
    context = data.movement_context
    if not steps[-1].committed:
        # Native earlier Steps may have committed. Preserve their legal facts;
        # the existing placement layer retains this unlaunched visual body.
        settled = replace(settled, grid=launch.grid, elevation_steps=launch.elevation_steps,
                          body_lift_px=launch.body_lift_px)
        return MotionTimeline(launch, (), context.jumpClip, 1, 0, elapsed, tuple(reactions),
                              settled, target, launch.body_lift_px, body_loops=False,
                              states=((elapsed, working),))
    distance = hypot(jump.end_position[0] - jump.start_position[0],
                     jump.end_position[1] - jump.start_position[1])
    duration = min(context.jumpMaxDurationMs, max(context.jumpMinDurationMs,
                   context.jumpBaseDurationMs + distance * context.jumpPerCellDurationMs))
    arc = min(context.jumpArcMaxPx, context.jumpArcBasePx + distance * context.jumpArcPerCellPx)
    leg = MotionLeg(launch.grid, settled.grid, launch.elevation_steps, settled.elevation_steps,
                    elapsed, elapsed + duration, elapsed, arc, initial_lift_px=launch.body_lift_px)
    return MotionTimeline(launch, (leg,), context.jumpClip, 1, arc, elapsed + duration,
                          tuple(reactions), settled, target, body_loops=False,
                          states=((elapsed + duration, working),))


def bind_motion(target: PresentationTarget, lineage: CompletedLineage,
                data: AnimationData, *, contacts: Mapping[str, ActorContact] | None = None) -> MotionTimeline | None:
    """Use native Step results and complete reaction subtrees for visual travel."""
    if not isinstance(lineage.root, (MovementEvent, JumpEvent)):
        return None
    steps = tuple(event for event in lineage.events if isinstance(event, StepMovementEvent)
                  and event.source_entity_uuid == lineage.root.source_entity_uuid
                  and event.parent_lineage == lineage.root.lineage_uuid)
    if not steps:
        return None
    staged = stage_lineage(target, lineage)
    actor = actor_contact(staged, staged.actors[lineage.root.source_entity_uuid], data)
    root_versions = {row.event_uuid for row in lineage.objective_rows
                     if row.lineage_uuid == lineage.root.lineage_uuid}
    target = stage_actors(target, tuple(admission for admission in lineage.admissions
                                      if admission.event_uuid in root_versions))
    contacts = contacts or {}
    actor = contacts.get(actor.actor_uuid, actor)
    context = data.movement_context
    reaction_context = data.movement_reaction_context
    if isinstance(lineage.root, JumpEvent):
        return _bind_jump(target, lineage, lineage.root, steps, data, actor, contacts)
    legs: list[MotionLeg] = []
    reactions: list[MotionReaction] = []
    elapsed = body_start = 0.0
    working = target
    states: list[tuple[float, PresentationTarget]] = []
    settled = actor
    settled_lift = 0.0
    for step_index, step in enumerate(steps):
        branch = lineage_branch(lineage, step)
        attacks = tuple(event for event in branch.events if isinstance(event, (AttackEvent, SpellEvent))
                        and event.parent_lineage == step.lineage_uuid)
        start, end = step.from_position, step.to_position
        height, end_height = step.from_elevation_feet / 5, step.to_elevation_feet / 5
        delta = end[0] - start[0], end[1] - start[1]
        distance = hypot(*delta)
        duration = context.walkStepDurationMs * distance
        arc = 0.0
        curve_from, curve_to = 0.0, 1.0
        initial_lift = actor.body_lift_px if step_index == 0 else 0
        if step_index == 0:
            start, height = actor.grid, actor.elevation_steps
            delta = end[0] - start[0], end[1] - start[1]
        fraction = 0.0
        continuation_curve = curve_from
        continuation: tuple[float, float] = start
        continuation_height = height
        if attacks:
            if (reaction_context.bodyEnabled or reaction_context.media or reaction_context.recovery.enabled):
                return None
            fraction = min(0.35, max(0.12, reaction_context.movementLeadInMs / context.walkStepDurationMs))
            continuation = start[0] + delta[0] * fraction, start[1] + delta[1] * fraction
            continuation_height = height + (end_height - height) * fraction
            continuation_curve = curve_from + (curve_to - curve_from) * fraction
            lead_end = elapsed + reaction_context.movementLeadInMs
            legs.append(MotionLeg(start, continuation, height, continuation_height,
                                  elapsed, lead_end, body_start, arc, curve_from, continuation_curve, initial_lift))
            elapsed = lead_end
            facing = facing_for_delta(delta, data)
            for attack_event in attacks:
                held = replace(actor_contact(working, working.actors[step.source_entity_uuid], data), grid=continuation,
                               elevation_steps=continuation_height, facing=facing,
                               body_lift_px=4 * arc * continuation_curve * (1 - continuation_curve)
                               + initial_lift * (1 - continuation_curve))
                group = bind_choreography(working, lineage_branch(lineage, attack_event), data,
                    facings={actor.actor_uuid: facing}, contacts={**contacts, actor.actor_uuid: held})
                source = contacts.get(str(attack_event.source_entity_uuid)) or actor_contact(
                    group.after, group.after.actors[attack_event.source_entity_uuid], data)
                reactions.append(MotionReaction(group, held, source, elapsed, elapsed + group.complete_ms,
                                                held.body_lift_px,
                                                attack_event.name))
                elapsed += group.complete_ms
                working = group.after
            body_start = elapsed  # beginBodyTravel(Walking) restarts after hit recovery.
            duration *= 1 - fraction
        if step.committed:
            legs.append(MotionLeg(continuation, end, continuation_height, end_height,
                                  elapsed, elapsed + duration, body_start, arc, continuation_curve, curve_to, initial_lift))
            elapsed += duration
        # Step results update the working retained contact for the next edge.
        # Its attack after-values are idempotent facts, not repeated mechanics.
        working = reduce_lineage(working, branch)
        states.append((elapsed, working))
        settled = actor_contact(working, working.actors[step.source_entity_uuid], data, facing_for_delta(delta, data))
        if not step.committed:
            # The legal Step stays at its origin. Playback keeps the position
            # where its reaction stopped; completion is not a return animation.
            settled_lift = 4 * arc * continuation_curve * (1 - continuation_curve) + initial_lift * (1 - continuation_curve)
            settled = replace(settled, grid=continuation, elevation_steps=continuation_height,
                              body_lift_px=settled_lift)
            break
    if not legs:
        return None
    return MotionTimeline(actor, tuple(legs), context.walkClip, context.walkPlaybackSpeed,
                          max(leg.arc_height_px for leg in legs), elapsed, tuple(reactions), settled, target, settled_lift,
                          states=tuple(states))


def sample_motion(timeline: MotionTimeline, data: AnimationData, elapsed_ms: float,
                  *, clip: str | None = None) -> MotionSample:
    """Changing view or intake progress cannot alter authored movement time."""
    elapsed = max(0.0, min(elapsed_ms, timeline.complete_ms))
    complete = elapsed_ms >= timeline.complete_ms
    vitals: dict[str, VitalsSample] = {}
    displayed = timeline.before
    state_ms = -1.0
    for at, state in timeline.states:
        if elapsed < at:
            break
        displayed, state_ms = state, at
    active: MotionReaction | None = None
    for reaction in timeline.reactions:
        if elapsed < reaction.start_ms:
            break
        sample = sample_choreography(reaction.choreography, elapsed - reaction.start_ms)
        if reaction.end_ms > state_ms:
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
    if not timeline.legs:
        contact = timeline.settled_contact
        return MotionSample(contact, sample_idle_body(data, contact, elapsed), contact.body_lift_px, complete,
                            displayed_vitals=tuple(vitals.values()), displayed=displayed)
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
    if not timeline.body_loops and selected == timeline.clip:
        frame = min(metadata.frames - 1, int(progress * metadata.frames))
    else:
        frame = body_frame(elapsed - leg.body_start_ms, metadata.fps * timeline.playback_speed,
                           metadata.frames, loop=True)
    return MotionSample(contact, BodySample(contact.actor_uuid, selected, frame, facing),
                        lift, complete, displayed_vitals=tuple(vitals.values()), displayed=displayed)
