"""Retained movement with walking edge reactions and grounded jump reactions.

One motion head contains its actual Step children and their attack subtrees.
The engine owns committed endpoints; subcell lead-in exists only in playback.
"""

from dataclasses import dataclass, replace
from math import hypot
from typing import Mapping
from uuid import UUID

from dnd.core.events import MovementTrajectory
from game.animation import (
    ActorContact, BodySample, VitalsSample, body_clip, body_frame,
    facing_for_delta, sample_idle_body,
)
from game.animation_types import AnimationData, Facing8
from game.choreography import BoundChoreography, bind_choreography, sample_choreography
from game.attack import BoundAttack
from game.combat import actor_contact, actor_is_visible
from game.player_facts import AttackFact, MovementFact, PlayerActor, PlayerLineage, PlayerNode, PlayerState, SpellFact, StepFact
from game.player_projection import lineage_branch, reduce_lineage, observe_actors, stage_actors, stage_lineage


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
    source: ActorContact | None
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
    settled_contact: ActorContact | None
    before: PlayerState
    actor_state: PlayerActor
    settled_lift_px: float = 0
    body_loops: bool = True
    states: tuple[tuple[float, PlayerState], ...] = ()


@dataclass(frozen=True, slots=True)
class MotionSample:
    contact: ActorContact | None
    body: BodySample | None
    lift_px: float
    complete: bool
    reaction: BoundChoreography | None = None
    reaction_elapsed_ms: float = 0
    displayed_vitals: tuple[VitalsSample, ...] = ()
    displayed: PlayerState | None = None


def _bind_jump(target: PlayerState, lineage: PlayerLineage, jump: MovementFact,
               steps: tuple[PlayerNode, ...], data: AnimationData,
               actor: ActorContact, contacts: Mapping[str, ActorContact]) -> MotionTimeline | None:
    """Resolve retained reactions at launch, then traverse one authored flight."""
    requested = jump.requested_end_position or jump.end_position
    assert requested is not None and jump.start_position is not None and jump.end_position is not None
    facing = facing_for_delta((requested[0] - actor.grid[0], requested[1] - actor.grid[1]), data)
    launch = replace(actor, facing=facing)
    working = target
    elapsed = 0.0
    reactions: list[MotionReaction] = []
    for step_node in steps:
        step = step_node.fact
        assert isinstance(step, StepFact)
        branch = lineage_branch(lineage, step_node)
        for event in branch.events:
            if not isinstance(event.fact, (AttackFact, SpellFact)) or event.parent_lineage != step_node.lineage_uuid:
                continue
            reaction_context = data.movement_reaction_context
            if reaction_context.bodyEnabled or reaction_context.media or reaction_context.recovery.enabled:
                return None
            current = working.actors[step.source_entity_uuid]
            held = replace(launch, hp=current.normal_hp, life_state=current.life_state)
            group = bind_choreography(working, lineage_branch(lineage, event), data,
                facings={actor.actor_uuid: facing}, contacts={**contacts, actor.actor_uuid: held})
            source = contacts.get(str(event.fact.source_entity_uuid)) or _visible_contact(
                working, event.fact.source_entity_uuid, data)
            reactions.append(MotionReaction(group, held, source, elapsed, elapsed + group.complete_ms,
                                            held.body_lift_px, event.fact.name))
            elapsed += group.complete_ms
            working = group.after
        working = reduce_lineage(working, branch)
        if not step.committed:
            break
    settled = actor_contact(working, working.actors[jump.source_entity_uuid], data, facing)
    context = data.movement_context
    last_step = steps[-1].fact
    assert isinstance(last_step, StepFact)
    if not last_step.committed:
        # Native earlier Steps may have committed. Preserve their legal facts;
        # the existing placement layer retains this unlaunched visual body.
        settled = replace(settled, grid=launch.grid, elevation_steps=launch.elevation_steps,
                          body_lift_px=launch.body_lift_px)
        return MotionTimeline(launch, (), context.jumpClip, 1, 0, elapsed, tuple(reactions),
                              settled, target, target.actors[jump.source_entity_uuid], launch.body_lift_px, body_loops=False,
                              states=((elapsed, working),))
    distance = hypot(jump.end_position[0] - jump.start_position[0],
                     jump.end_position[1] - jump.start_position[1])
    duration = min(context.jumpMaxDurationMs, max(context.jumpMinDurationMs,
                   context.jumpBaseDurationMs + distance * context.jumpPerCellDurationMs))
    arc = min(context.jumpArcMaxPx, context.jumpArcBasePx + distance * context.jumpArcPerCellPx)
    leg = MotionLeg(launch.grid, settled.grid, launch.elevation_steps, settled.elevation_steps,
                    elapsed, elapsed + duration, elapsed, arc, initial_lift_px=launch.body_lift_px)
    return MotionTimeline(launch, (leg,), context.jumpClip, 1, arc, elapsed + duration,
                          tuple(reactions), settled, target, target.actors[jump.source_entity_uuid], body_loops=False,
                          states=((elapsed + duration, working),))


def _visible_contact(state: PlayerState, actor_uuid: UUID, data: AnimationData,
                     facing: Facing8 = "S") -> ActorContact | None:
    actor = state.actors.get(actor_uuid)
    return actor_contact(state, actor, data, facing) if actor is not None and actor_is_visible(state, actor) else None


def bind_motion(target: PlayerState, lineage: PlayerLineage,
                data: AnimationData, *, contacts: Mapping[str, ActorContact] | None = None) -> MotionTimeline | None:
    """Compile disclosed movement and ordered observation changes in one head.

    Hidden causal nodes supply no travel distance or duration. A received loss
    followed by reacquisition has one authored step of spacing; an isolated
    visible contact has the same dwell. Neither interval invents an edge.
    """
    root = lineage.root.fact
    if not isinstance(root, MovementFact):
        return None
    by_lineage = {event.lineage_uuid: event for event in lineage.events}
    children = tuple(by_lineage[identity] for identity in lineage.root.children_lineages)
    steps = tuple(event for event in children if isinstance(event.fact, StepFact))
    staged = stage_lineage(target, lineage)
    reference = _visible_contact(staged, root.source_entity_uuid, data)
    if reference is None:
        first = next((row for row in lineage.observations if row.actor.uuid == root.source_entity_uuid
                      and row.contact is not None and row.contact.visual), None)
        if first is None:
            return None
        staged = observe_actors(staged, (first,))
        reference = _visible_contact(staged, root.source_entity_uuid, data)
        assert reference is not None
    root_versions = {row.event_uuid for row in lineage.version_rows
                     if row.lineage_uuid == lineage.root.lineage_uuid}
    target = stage_actors(target, tuple(row for row in lineage.observations if row.event_uuid in root_versions))
    contacts = contacts or {}
    actor = contacts.get(reference.actor_uuid, reference)
    context = data.movement_context
    partial_jump = root.trajectory is MovementTrajectory.DIRECT_ARC
    if partial_jump and steps and root.start_position is not None and root.end_position is not None:
        return _bind_jump(target, lineage, root, steps, data, actor, contacts)
    reaction_context = data.movement_reaction_context
    legs: list[MotionLeg] = []
    reactions: list[MotionReaction] = []
    states: list[tuple[float, PlayerState]] = []
    elapsed = body_start = 0.0
    working = target
    settled = _visible_contact(working, root.source_entity_uuid, data)
    settled_lift = 0.0
    isolated_point = settled is not None
    hidden_transition = False
    uninterrupted = False
    for node in children:
        branch = lineage_branch(lineage, node)
        step = node.fact
        if not isinstance(step, StepFact) or partial_jump:
            # An opaque attempted edge still owns permitted action/effect
            # descendants. Play those at the known pose; absence of endpoint
            # authority never becomes an invented lead or flight.
            held = _visible_contact(working, root.source_entity_uuid, data)
            if held is not None and partial_jump:
                held = replace(held, grid=actor.grid, elevation_steps=actor.elevation_steps,
                               body_lift_px=actor.body_lift_px)
            overrides = dict(contacts)
            if held is not None:
                overrides[held.actor_uuid] = held
            group = bind_choreography(working, branch, data, contacts=overrides)
            if held is not None and group.complete_ms > 0:
                if hidden_transition:
                    elapsed += context.walkStepDurationMs
                    hidden_transition = False
                source = None
                label = None
                if group.nodes:
                    bound = group.nodes[0].bound
                    source = bound.timeline.source if isinstance(bound, BoundAttack) else bound.timeline.source.caster
                    action = next(row.fact for row in branch.events if row.uuid == group.nodes[0].event_uuid)
                    if isinstance(action, (AttackFact, SpellFact)):
                        label = action.name
                reactions.append(MotionReaction(group, held, source, elapsed,
                    elapsed + group.complete_ms, held.body_lift_px, label))
                elapsed += group.complete_ms
                isolated_point = False
                body_start = elapsed
            successor = group.after
            seen = _visible_contact(successor, root.source_entity_uuid, data)
            previous = _visible_contact(working, root.source_entity_uuid, data)
            if previous is not None and (seen is None or seen.grid != previous.grid):
                if isolated_point and not partial_jump:
                    elapsed += context.walkStepDurationMs
                isolated_point = False
                hidden_transition = seen is None
                uninterrupted = False
            if seen is not None and (previous is None or seen.grid != previous.grid):
                if hidden_transition:
                    elapsed += context.walkStepDurationMs
                    hidden_transition = False
                isolated_point = True
                body_start = elapsed
            working, settled = successor, seen
            states.append((elapsed, working))
            continue
        if step.source_entity_uuid != root.source_entity_uuid:
            # Other subjects retain their own causal state, never this path.
            working = reduce_lineage(working, branch)
            states.append((elapsed, working))
            continue
        if hidden_transition:
            elapsed += context.walkStepDurationMs
            hidden_transition = False
        # Both endpoints are explicit player facts. The projection has already
        # applied native identity and per-endpoint grants; no root path is used.
        start, end = step.from_position, step.to_position
        height, end_height = step.from_elevation_feet / 5, step.to_elevation_feet / 5
        current = working.actors.get(step.source_entity_uuid, staged.actors[step.source_entity_uuid])
        leg_actor = replace(actor, hp=current.normal_hp, life_state=current.life_state)
        initial_lift = 0.0
        if not legs and _visible_contact(target, root.source_entity_uuid, data) is not None:
            start, height, initial_lift = actor.grid, actor.elevation_steps, actor.body_lift_px
        delta = end[0] - start[0], end[1] - start[1]
        distance = hypot(step.to_position[0] - step.from_position[0], step.to_position[1] - step.from_position[1])
        duration = context.walkStepDurationMs * distance
        if not uninterrupted:
            body_start = elapsed
        isolated_point = False
        attacks = tuple(event for event in branch.events if isinstance(event.fact, (AttackFact, SpellFact))
                        and event.parent_lineage == node.lineage_uuid)
        fraction = 0.0
        continuation: tuple[float, float] = start
        continuation_height = height
        if attacks:
            if reaction_context.bodyEnabled or reaction_context.media or reaction_context.recovery.enabled:
                return None
            fraction = min(0.35, max(0.12, reaction_context.movementLeadInMs / context.walkStepDurationMs))
            continuation = start[0] + delta[0] * fraction, start[1] + delta[1] * fraction
            continuation_height = height + (end_height - height) * fraction
            lead_end = elapsed + reaction_context.movementLeadInMs
            legs.append(MotionLeg(start, continuation, height, continuation_height,
                                  elapsed, lead_end, body_start, curve_to=fraction, initial_lift_px=initial_lift))
            elapsed = lead_end
            facing = facing_for_delta(delta, data)
            for attack_node in attacks:
                attack = attack_node.fact
                assert isinstance(attack, (AttackFact, SpellFact))
                current = working.actors[step.source_entity_uuid]
                held = replace(leg_actor, hp=current.normal_hp, life_state=current.life_state,
                               grid=continuation, elevation_steps=continuation_height, facing=facing,
                               body_lift_px=initial_lift * (1 - fraction))
                group = bind_choreography(working, lineage_branch(lineage, attack_node), data,
                    facings={actor.actor_uuid: facing}, contacts={**contacts, actor.actor_uuid: held})
                source = contacts.get(str(attack.source_entity_uuid)) or _visible_contact(
                    working, attack.source_entity_uuid, data)
                reactions.append(MotionReaction(group, held, source, elapsed, elapsed + group.complete_ms,
                                                held.body_lift_px, attack.name))
                elapsed += group.complete_ms
                working = group.after
            body_start = elapsed
            duration *= 1 - fraction
        if step.committed:
            legs.append(MotionLeg(continuation, end, continuation_height, end_height,
                                  elapsed, elapsed + duration, body_start, curve_from=fraction,
                                  initial_lift_px=initial_lift))
            elapsed += duration
        working = reduce_lineage(working, branch)
        states.append((elapsed, working))
        settled = _visible_contact(working, step.source_entity_uuid, data, facing_for_delta(delta, data))
        uninterrupted = settled is not None
        if not step.committed:
            settled_lift = initial_lift * (1 - fraction)
            if settled is not None:
                settled = replace(settled, grid=continuation, elevation_steps=continuation_height,
                                  body_lift_px=settled_lift)
            break
    if isolated_point and not partial_jump:
        elapsed += context.walkStepDurationMs
    # Root completion can carry ordinary state without a direct child payload.
    working = reduce_lineage(working, lineage)
    states.append((elapsed, working))
    if partial_jump and settled is not None and reactions:
        settled = replace(settled, grid=actor.grid, elevation_steps=actor.elevation_steps,
                          body_lift_px=actor.body_lift_px)
    if not legs and not states and not reactions:
        return None
    return MotionTimeline(actor, tuple(legs), context.walkClip, context.walkPlaybackSpeed,
                          0, elapsed, tuple(reactions), settled, target,
                          staged.actors[root.source_entity_uuid], settled_lift, states=tuple(states))


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
    leg = next((leg for leg in timeline.legs if leg.start_ms <= elapsed < leg.end_ms), None)
    if (complete and timeline.settled_contact is not None and timeline.legs
            and timeline.legs[-1].end_ms == timeline.complete_ms):
        leg = timeline.legs[-1]
    if leg is None:
        contact = (timeline.settled_contact if complete else
                   _visible_contact(displayed, UUID(timeline.actor.actor_uuid), data, timeline.actor.facing))
        return MotionSample(contact, sample_idle_body(data, contact, elapsed) if contact is not None else None,
                            contact.body_lift_px if contact is not None else 0, complete,
                            displayed_vitals=tuple(vitals.values()), displayed=displayed)
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
    if complete and timeline.settled_contact is not None:
        contact = replace(timeline.settled_contact, facing=facing)
    selected = clip or timeline.clip
    metadata = body_clip(data, contact, selected)
    if not timeline.body_loops and selected == timeline.clip:
        frame = min(metadata.frames - 1, int(progress * metadata.frames))
    else:
        frame = body_frame(elapsed - leg.body_start_ms, metadata.fps * timeline.playback_speed,
                           metadata.frames, loop=True)
    return MotionSample(contact, BodySample(contact.actor_uuid, selected, frame, facing),
                        lift, complete, displayed_vitals=tuple(vitals.values()), displayed=displayed)
