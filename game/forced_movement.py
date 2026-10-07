"""Studio shove/contact and forced body travel over retained native positions.

These passive cues own no mechanics, queue or clock. Spatial descendants keep
their native identity and receive anchors along the same displayed path.
"""

from dataclasses import dataclass, replace
from math import hypot
from typing import Mapping
from uuid import UUID

from dnd.types.event_facts import SpatialChangeType
from dnd.types.event_facts import LandingKind, MovementTrajectory
from dnd.types.world import MovementMode, OccupancyLayer
from game.animation import (
    ActorContact, BodySample, facing_for_delta,
    sample_idle_body, body_context, resolve_body_context, context_duration, context_anchor_ms,
    sample_context_body, airborne_weight, body_clip, body_rig, context_frame,
)
from game.animation_types import (AnimationData, LifecycleFeedback, BodyContext, ActionFrameAnchor,
                                  ContentBodyQualifier, RoleDefault, MovementBodyQualifier, FlightMovementProfile)
from game.combat import actor_contact
from dnd.player.facts import ForcedMovementFact, PlayerLineage, PlayerNode, PlayerState, ShoveFact, SpatialFact
from dnd.player.reduction import reduce_lineage
from game.condition_media import ResolvedConditionLayer
from game.condition_types import ConditionLayer
from game.timing_evidence import TimingEvidence, TimingOperand, TimingReference, TimingMeasurement, record_timing


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
    timing_evidence: tuple[TimingEvidence, ...] = ()


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
    flight: FlightMovementProfile | None = None
    flight_body: BodyContext | None = None
    layers: tuple[ConditionLayer, ...] = ()
    timing_evidence: tuple[TimingEvidence, ...] = ()


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
    evidence: list[TimingEvidence] = []
    contact_offset = context_anchor_ms(data, source, selected, "contact")
    record_timing(evidence, TimingReference('event', node.uuid, 'contact'), 'shove_contact',
        (TimingOperand(TimingReference('event', node.uuid, 'start'), start_ms, offset_ms=contact_offset,
            authored_field='shove.selected_body.contact'),), start_ms + contact_offset)
    return ShoveCue(node.uuid, source, target, selected.actor.clip, selected.actor.playbackSpeed,
        start_ms, start_ms + context_anchor_ms(data, source, selected, "contact"),
        start_ms + context_duration(data, source, selected), data.shove_feedback[outcome], data, selected, tuple(evidence))


def motion_progress(value: float, curve: str, *, inverse: bool = False) -> float:
    value = min(1.0, max(0.0, value))
    power = {"linear": 1, "ease_out_quad": 2, "ease_out_cubic": 3}[curve]
    return 1 - (1 - value) ** (1 / power if inverse else power)


def bind_forced_movement(before: PlayerState, lineage: PlayerLineage,
                         data: AnimationData, start_ms: float,
                         contacts: Mapping[str, ActorContact], *,
                         layers: tuple[ConditionLayer, ...] = ()) -> ForcedMovementCue:
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
    finite_transfer = event.landing_kind in (LandingKind.CONTROLLED, LandingKind.IMPACT)
    flight = data.movement_context.flight if finite_transfer else None
    flight_body = (resolve_body_context(data, actor, "movement",
        MovementBodyQualifier(movement_mode=MovementMode.FLYING, trajectory=MovementTrajectory.PATH,
            connector_presentation_key=None),
        flight.body) if flight is not None else None)
    # Finite transfers traverse the admitted straight segment. Its disclosed
    # supercover cells certify clearance; their centres are not zigzag waypoints.
    path = ((event.end_position,) if finite_transfer else
            event.disclosed_path[1:] if event.disclosed_path else tuple(row.position for row in entered))
    grids = [event.start_position]
    for grid in path:
        if grid != grids[-1]:
            grids.append(grid)
    if grids[-1] != event.end_position:
        grids.append(event.end_position)
    lengths = [hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(grids, grids[1:])]
    total = sum(lengths)
    if total == 0:
        raise ValueError("Forced movement has no disclosed displacement")
    cumulative = [0.0]
    for length in lengths:
        cumulative.append(cumulative[-1] + length)
    first_height = (event.start_elevation_feet / 5 if event.start_elevation_feet is not None
                    else actor.elevation_steps)
    last_height = (event.end_elevation_feet / 5 if event.end_elevation_feet is not None
                   else after.tiles[event.end_position].elevation_steps)
    points = tuple(DisplacementPoint(grid,
        first_height + (last_height - first_height) * cumulative[index] / total if finite_transfer else
        first_height if index == 0 else last_height if index == len(grids) - 1 else after.tiles[grid].elevation_steps,
        cumulative[index] / total) for index, grid in enumerate(grids))
    speed = selected.actor.playbackSpeed
    brace_frame = next(row.frame for row in selected.anchors if row.name == "brace")
    evidence: list[TimingEvidence] = []
    brace_delay = context_anchor_ms(data, actor, selected, "brace")
    travel_start = start_ms + brace_delay
    start_source = TimingOperand(TimingReference('event', node.uuid, 'start'), start_ms)
    travel_source = record_timing(evidence, TimingReference('event', node.uuid, 'launch'), 'displacement_start',
        (replace(start_source, offset_ms=brace_delay, authored_field='forced_movement.selected_body.brace'),), travel_start)
    for layer in layers:
        media = data.condition_media[layer.assetId]
        if media.application_asset_id is not None:
            asset = data.projectile_assets[media.application_asset_id]
            phase = asset.phases.impact
            assert phase is not None
            opening_duration = phase.frames * 1000 / (phase.fps or asset.fps)
            travel_start = max(travel_start, start_ms + opening_duration)
            travel_source = record_timing(evidence, travel_source.reference, 'displacement_start',
                (travel_source, replace(start_source, offset_ms=opening_duration,
                    authored_field=f'condition_media.{layer.assetId}.application', measurements=(
                        TimingMeasurement('impact.frames', phase.frames), TimingMeasurement('impact.fps', phase.fps or asset.fps)))),
                travel_start, 'maximum')
    duration = profile.duration_ms * context.durationScale
    body_end = travel_start + duration + context_duration(data, actor, selected) - context_anchor_ms(data, actor, selected, "brace")
    travel_end_source = record_timing(evidence, TimingReference('event', node.uuid, 'contact'), 'displacement_travel',
        (replace(travel_source, offset_ms=duration, authored_field='forced_movement.duration', measurements=(
            TimingMeasurement('profile.duration_ms', profile.duration_ms), TimingMeasurement('context.durationScale', context.durationScale))),),
        travel_start + duration)
    body_end_source = record_timing(evidence, TimingReference('event', node.uuid, 'body_end'), 'displacement_complete',
        (replace(travel_end_source, offset_ms=context_duration(data, actor, selected)-brace_delay,
            authored_field='forced_movement.selected_body.remaining'),), body_end)
    complete = body_end + context_duration(data, actor, recovery)
    complete_source = record_timing(evidence, TimingReference('event', node.uuid, 'complete'), 'displacement_complete',
        (replace(body_end_source, offset_ms=context_duration(data, actor, recovery), authored_field='forced_movement.recovery'),), complete)
    for layer in layers:
        media = data.condition_media[layer.assetId]
        if media.removal_asset_id is not None:
            asset = data.projectile_assets[media.removal_asset_id]
            phase = asset.phases.impact
            assert phase is not None
            closing_duration = phase.frames * 1000 / (phase.fps or asset.fps)
            complete = max(complete, travel_start + duration + closing_duration)
            complete_source = record_timing(evidence, complete_source.reference, 'displacement_complete',
                (complete_source, replace(travel_end_source, offset_ms=closing_duration,
                    authored_field=f'condition_media.{layer.assetId}.removal', measurements=(
                        TimingMeasurement('impact.frames', phase.frames), TimingMeasurement('impact.fps', phase.fps or asset.fps)))), complete, 'maximum')
    arrivals: list[tuple[UUID, float]] = []
    entered_index = 0
    for identity, row in spatial:
        # LEFT is published after committing its destination, immediately
        # before that destination's ENTERED fact. Both share the reached point.
        destination = entered[min(entered_index, len(entered) - 1)].position if entered else event.end_position
        progress = next(point.progress for point in points if point.grid == destination)
        if finite_transfer:
            progress = 0. if row.occupancy_layer is OccupancyLayer.AIR else 1.
        at = travel_start + duration * motion_progress(progress, context.motionCurve, inverse=True)
        record_timing(evidence, TimingReference('event', identity, 'admission'), 'displacement_travel',
            (replace(travel_source, offset_ms=duration * motion_progress(progress, context.motionCurve, inverse=True),
                authored_field='forced_movement.motionCurve', measurements=(TimingMeasurement('path.progress', progress),
                    TimingMeasurement('travel.duration_ms', duration))),), at)
        arrivals.append((identity, at))
        if row.change_type is SpatialChangeType.ENTITY_ENTERED:
            entered_index += 1
    return ForcedMovementCue(node.uuid, actor, points, tuple(arrivals), selected.actor.clip,
        brace_frame, speed, start_ms, travel_start, travel_start + duration, body_end, complete,
        data, selected, recovery, flight, flight_body, layers, tuple(evidence))


def sample_displacement_layers(cue: ForcedMovementCue, elapsed_ms: float) -> tuple[ResolvedConditionLayer, ...]:
    """Reuse registered body attachments over this finite motion's own dates."""
    if not cue.start_ms <= elapsed_ms < cue.complete_ms:
        return ()
    return tuple(ResolvedConditionLayer(layer, cue.data.condition_media[layer.assetId], cue.event_uuid,
        min(elapsed_ms, cue.travel_end_ms) - cue.start_ms, application=True,
        alpha=min(1., (cue.complete_ms - elapsed_ms) / fade) if
            (fade := cue.data.condition_media[layer.assetId].removal_fade_ms) else 1.,
        removal_age_ms=elapsed_ms - cue.travel_end_ms if elapsed_ms >= cue.travel_end_ms else None)
        for layer in cue.layers)


def forced_contact(cue: ForcedMovementCue, data: AnimationData, elapsed_ms: float) -> ActorContact:
    progress = motion_progress((elapsed_ms - cue.travel_start_ms) / (cue.travel_end_ms - cue.travel_start_ms),
                               data.forced_movement_context.motionCurve)
    index = next((i for i in range(1, len(cue.points)) if progress < cue.points[i].progress), len(cue.points) - 1)
    first, last = cue.points[index - 1:index + 1]
    span = last.progress - first.progress
    local = (progress - first.progress) / span if span else 1
    lift = (cue.flight.clearancePx * airborne_weight(progress, cue.flight.takeoffFraction,
            1 - cue.flight.landingFraction) if cue.flight is not None else 0.)
    return replace(cue.actor,
        grid=(first.grid[0] + (last.grid[0] - first.grid[0]) * local,
              first.grid[1] + (last.grid[1] - first.grid[1]) * local),
        elevation_steps=first.elevation_steps + (last.elevation_steps - first.elevation_steps) * local,
        body_lift_px=lift + cue.actor.body_lift_px * (1 - progress))


def sample_forced_body(cue: ForcedMovementCue, data: AnimationData, elapsed_ms: float) -> BodySample:
    selected = cue.body_context or body_context(cue.clip, cue.playback_speed)
    if elapsed_ms < cue.travel_start_ms:
        return sample_context_body(data, cue.actor, selected, min(elapsed_ms - cue.start_ms,
            context_anchor_ms(data, cue.actor, selected, "brace")))
    elif elapsed_ms < cue.travel_end_ms:
        if cue.flight is not None and cue.flight_body is not None:
            progress = (elapsed_ms - cue.travel_start_ms) / (cue.travel_end_ms - cue.travel_start_ms)
            flight_body = cue.flight_body
            frame = context_frame(flight_body, body_clip(data, cue.actor, flight_body.actor.clip),
                elapsed_ms - cue.travel_start_ms, progress=progress)
            registered = "airborne_support" in body_rig(data, cue.actor).pose_sockets
            return BodySample(cue.actor.actor_uuid, flight_body.actor.clip, frame, cue.actor.facing,
                registration_socket="airborne_support" if registered else None,
                registration_weight=airborne_weight(progress, cue.flight.takeoffFraction,
                    1 - cue.flight.landingFraction) if registered else 0.)
        frame = cue.brace_frame
    elif elapsed_ms < cue.body_end_ms:
        return sample_context_body(data, cue.actor, selected,
            elapsed_ms - cue.travel_end_ms + context_anchor_ms(data, cue.actor, selected, "brace"))
    else:
        recovery = cue.recovery_body
        recovery_end = cue.body_end_ms + (context_duration(data, cue.actor, recovery)
            if recovery is not None and recovery.actor.enabled else 0.)
        if recovery is not None and recovery.actor.enabled and elapsed_ms < recovery_end:
            return sample_context_body(data, cue.actor, recovery, elapsed_ms - cue.body_end_ms)
        return sample_idle_body(data, cue.actor, elapsed_ms - recovery_end)
    return BodySample(cue.actor.actor_uuid, cue.clip, frame, cue.actor.facing)


def sample_shove(cue: ShoveCue, data: AnimationData, elapsed_ms: float) -> BodySample:
    if elapsed_ms >= cue.body_end_ms:
        return sample_idle_body(data, cue.source, elapsed_ms - cue.body_end_ms)
    return sample_context_body(data, cue.source, cue.body_context or body_context(cue.clip, cue.playback_speed),
                               elapsed_ms - cue.start_ms)
