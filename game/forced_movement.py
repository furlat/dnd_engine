"""Studio shove/contact and forced body travel over retained native positions.

These passive cues own no mechanics, queue or clock. Spatial descendants keep
their native identity and receive anchors along the same displayed path.
"""

from dataclasses import dataclass, replace
from math import hypot
from typing import Mapping
from uuid import UUID

from dnd.core.events import SpatialChangeType
from game.animation import (
    ActorContact, BodySample, facing_for_delta,
    sample_idle_body, body_context, resolve_body_context, context_duration, context_anchor_ms,
    sample_context_body,
)
from game.animation_types import (AnimationData, LifecycleFeedback, BodyContext, ActionFrameAnchor,
                                  ContentBodyQualifier, RoleDefault)
from game.combat import actor_contact
from game.player_facts import ForcedMovementFact, PlayerLineage, PlayerNode, PlayerState, ShoveFact, SpatialFact
from game.player_reduction import reduce_lineage


@dataclass(frozen=True, slots=True)
class ShoveCue:
    event_uuid: UUID
    source: ActorContact
    target: ActorContact
    clip: str
    playback_speed: float
    start_ms: float
    contact_ms: float
    body_end_ms: float
    feedback: LifecycleFeedback
    data: AnimationData
    body_context: BodyContext | None = None


@dataclass(frozen=True, slots=True)
class DisplacementPoint:
    grid: tuple[float, float]
    elevation_steps: float
    progress: float


@dataclass(frozen=True, slots=True)
class ForcedMovementCue:
    event_uuid: UUID
    actor: ActorContact
    points: tuple[DisplacementPoint, ...]
    arrivals: tuple[tuple[UUID, float], ...]
    clip: str
    brace_frame: int
    playback_speed: float
    start_ms: float
    travel_start_ms: float
    travel_end_ms: float
    body_end_ms: float
    complete_ms: float
    data: AnimationData
    body_context: BodyContext | None = None
    recovery_body: BodyContext | None = None


def bind_shove(before: PlayerState, node: PlayerNode, data: AnimationData,
               start_ms: float, contacts: Mapping[str, ActorContact]) -> ShoveCue:
    event = node.fact
    assert isinstance(event, ShoveFact)
    if event.behavior_id is None or event.behavior_id not in data.shove_recipes:
        raise ValueError("Shove has no exact authored recipe")
    recipe = data.shove_recipes[event.behavior_id]
    if not recipe.actor.enabled or recipe.actor.hiddenSlots or recipe.actor.media:
        raise NotImplementedError("Shove actor media/hidden slots are not bound")
    assert event.target_entity_uuid is not None
    source = contacts.get(str(event.source_entity_uuid)) or actor_contact(
        before, before.actors[event.source_entity_uuid], data)
    target = contacts.get(str(event.target_entity_uuid)) or actor_contact(
        before, before.actors[event.target_entity_uuid], data)
    source = replace(source, facing=facing_for_delta(
        (target.grid[0] - source.grid[0], target.grid[1] - source.grid[1]), data))
    frame = next((row.frame for name in ("contact", "impact", "effect")
                  for row in recipe.anchors if row.name == name), None)
    if frame is None:
        raise ValueError("Shove contact anchor is absent or unreachable")
    selected = resolve_body_context(data, source, "shove", ContentBodyQualifier(contentRef=recipe.definitionRef),
        body_context(recipe.actor.clip, recipe.actor.playbackSpeed,
                     anchors=(ActionFrameAnchor(name="contact", frame=frame),)))
    outcome = ("resisted" if not event.contest_success else "succeeded_prone" if event.knocked_prone
               else "succeeded_blocked" if event.push_distance == 0 else "succeeded_push")
    return ShoveCue(node.uuid, source, target, selected.actor.clip, selected.actor.playbackSpeed,
        start_ms, start_ms + context_anchor_ms(data, source, selected, "contact"),
        start_ms + context_duration(data, source, selected), data.shove_feedback[outcome], data, selected)


def motion_progress(value: float, curve: str, *, inverse: bool = False) -> float:
    value = min(1.0, max(0.0, value))
    power = {"linear": 1, "ease_out_quad": 2, "ease_out_cubic": 3}[curve]
    return 1 - (1 - value) ** (1 / power if inverse else power)


def bind_forced_movement(before: PlayerState, lineage: PlayerLineage,
                         data: AnimationData, start_ms: float,
                         contacts: Mapping[str, ActorContact]) -> ForcedMovementCue:
    node = lineage.root
    event = node.fact
    assert isinstance(event, ForcedMovementFact) and event.target_entity_uuid is not None
    context, profile = data.forced_movement_context, data.forced_movement_profile
    if context.media or context.recovery.media:
        raise NotImplementedError("Forced movement media tracks are not bound")
    target = before.actors[event.target_entity_uuid]
    actor = contacts.get(str(target.uuid)) or actor_contact(before, target, data)
    direction = (event.end_position[0] - event.start_position[0],
                 event.end_position[1] - event.start_position[1])
    if context.facingPolicy != "preserve":
        facing_delta = (-direction[0], -direction[1])
        if (context.facingPolicy == "source_or_opposite_travel" and event.source_entity_uuid is not None
                and event.source_entity_uuid in before.actors):
            source = contacts.get(str(event.source_entity_uuid)) or actor_contact(
                before, before.actors[event.source_entity_uuid], data)
            facing_delta = source.grid[0] - actor.grid[0], source.grid[1] - actor.grid[1]
        actor = replace(actor, facing=facing_for_delta(facing_delta, data))
    selected = resolve_body_context(data, actor, "forced_movement", RoleDefault(), body_context(
        profile.target_clip, profile.playback_speed * context.playbackSpeedScale,
        anchors=(ActionFrameAnchor(name="brace", frame=profile.brace_frame),)))
    recovery = resolve_body_context(data, actor, "forced_movement_recovery", RoleDefault(), body_context(
        context.recovery.bodyClip, context.recovery.bodyPlaybackSpeed, enabled=context.recovery.enabled))
    after = reduce_lineage(before, lineage)
    spatial = tuple((row.uuid, row.fact) for row in lineage.events if isinstance(row.fact, SpatialFact)
                    and row.fact.entity_uuid == target.uuid and row.parent_lineage == node.lineage_uuid
                    and row.fact.change_type in (SpatialChangeType.ENTITY_ENTERED, SpatialChangeType.ENTITY_LEFT))
    entered = tuple(fact for _, fact in spatial if fact.change_type is SpatialChangeType.ENTITY_ENTERED)
    grids = [actor.grid, *(row.position for row in entered)]
    if grids[-1] != event.end_position:
        grids.append(event.end_position)
    lengths = [hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(grids, grids[1:])]
    total = sum(lengths)
    if total == 0:
        raise ValueError("Forced movement has no disclosed displacement")
    cumulative = [0.0]
    for length in lengths:
        cumulative.append(cumulative[-1] + length)
    points = tuple(DisplacementPoint(grid,
        actor.elevation_steps if index == 0 else after.tiles[grid].elevation_steps,
        cumulative[index] / total) for index, grid in enumerate(grids))
    speed = selected.actor.playbackSpeed
    brace_frame = next(row.frame for row in selected.anchors if row.name == "brace")
    travel_start = start_ms + context_anchor_ms(data, actor, selected, "brace")
    duration = profile.duration_ms * context.durationScale
    body_end = start_ms + context_duration(data, actor, selected) + duration
    complete = body_end + context_duration(data, actor, recovery)
    arrivals: list[tuple[UUID, float]] = []
    entered_index = 1
    for identity, row in spatial:
        # LEFT is published after committing its destination, immediately
        # before that destination's ENTERED fact. Both share the reached point.
        index = min(entered_index, len(points) - 1)
        at = travel_start + duration * motion_progress(points[index].progress, context.motionCurve, inverse=True)
        arrivals.append((identity, at))
        if row.change_type is SpatialChangeType.ENTITY_ENTERED:
            entered_index += 1
    return ForcedMovementCue(node.uuid, actor, points, tuple(arrivals), selected.actor.clip,
        brace_frame, speed, start_ms, travel_start, travel_start + duration, body_end, complete, data, selected, recovery)


def forced_contact(cue: ForcedMovementCue, data: AnimationData, elapsed_ms: float) -> ActorContact:
    progress = motion_progress((elapsed_ms - cue.travel_start_ms) / (cue.travel_end_ms - cue.travel_start_ms),
                               data.forced_movement_context.motionCurve)
    index = next((i for i in range(1, len(cue.points)) if progress < cue.points[i].progress), len(cue.points) - 1)
    first, last = cue.points[index - 1:index + 1]
    span = last.progress - first.progress
    local = (progress - first.progress) / span if span else 1
    return replace(cue.actor,
        grid=(first.grid[0] + (last.grid[0] - first.grid[0]) * local,
              first.grid[1] + (last.grid[1] - first.grid[1]) * local),
        elevation_steps=first.elevation_steps + (last.elevation_steps - first.elevation_steps) * local,
        body_lift_px=cue.actor.body_lift_px * (1 - progress))


def sample_forced_body(cue: ForcedMovementCue, data: AnimationData, elapsed_ms: float) -> BodySample:
    selected = cue.body_context or body_context(cue.clip, cue.playback_speed)
    if elapsed_ms < cue.travel_start_ms:
        return sample_context_body(data, cue.actor, selected, elapsed_ms - cue.start_ms)
    elif elapsed_ms < cue.travel_end_ms:
        frame = cue.brace_frame
    elif elapsed_ms < cue.body_end_ms:
        return sample_context_body(data, cue.actor, selected,
            elapsed_ms - cue.start_ms - (cue.travel_end_ms - cue.travel_start_ms))
    else:
        recovery = cue.recovery_body
        if recovery is not None and recovery.actor.enabled and elapsed_ms < cue.complete_ms:
            return sample_context_body(data, cue.actor, recovery, elapsed_ms - cue.body_end_ms)
        return sample_idle_body(data, cue.actor, elapsed_ms - cue.complete_ms)
    return BodySample(cue.actor.actor_uuid, cue.clip, frame, cue.actor.facing)


def sample_shove(cue: ShoveCue, data: AnimationData, elapsed_ms: float) -> BodySample:
    if elapsed_ms >= cue.body_end_ms:
        return sample_idle_body(data, cue.source, elapsed_ms - cue.body_end_ms)
    return sample_context_body(data, cue.source, cue.body_context or body_context(cue.clip, cue.playback_speed),
                               elapsed_ms - cue.start_ms)
