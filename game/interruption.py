"""Bounded prefixes of authored actions, selected by recorded cancellation facts."""

from dataclasses import dataclass, replace
from uuid import UUID

from game.animation import ActorContact, CastSample, CastTimeline, cast_deliveries, delivery_identity, sample_cast, projectile_contact, body_elevation_steps
from dnd.core.presentation_geometry import SpherePresentationGeometry
from game.animation_types import AnimationData, InterruptionRule, ReactionMedia
from game.attack import AttackSample, BoundAttack
from game.body_action import BodyActionCue
from game.combat import BoundCast
from game.player_facts import PlayerNode
from game.stationary_media import StationaryMediaCue
from game.timing_evidence import TimingEvidence, TimingOperand, TimingReference, CompiledTimingReference, TimingTarget, record_timing


@dataclass(frozen=True, slots=True)
class ReactionMediaCue:
    event_uuid: UUID
    incoming_event_uuid: UUID
    timeline: CastTimeline | None
    data: AnimationData
    source: ActorContact
    recipe: ReactionMedia
    succeeded: bool
    start_ms: float
    sample: CastSample | None
    source_point: tuple[float, float, float] | None = None

    @property
    def complete_ms(self) -> float:
        return self.start_ms + self.recipe.durationMs


def bind_reaction_media(event_uuid: UUID, incoming_event_uuid: UUID,
                        bound: BoundCast | BodyActionCue, recipe: ReactionMedia, succeeded: bool,
                        start_ms: float, cutoff_ms: float, *, reaction_id: str | None = None,
                        outcome_code: str | None = None) -> ReactionMediaCue:
    if isinstance(bound, BodyActionCue):
        return ReactionMediaCue(event_uuid, incoming_event_uuid, None, bound.data, bound.contact,
                                recipe, succeeded, start_ms, None)
    sample = sample_cast(bound.timeline, max(0., cutoff_ms - 1e-6))
    source_point = None
    profile = bound.timeline.recipe.cancellationMedia
    if profile is not None and reaction_id == profile.reactionId:
        source = bound.timeline.source.caster
        x,y,height = profile.reactionOffsetsByFacing[bound.timeline.facing]
        source_point = (source.grid[0]+x, source.grid[1]+y,
            body_elevation_steps(source, bound.timeline.data)+height)
        if succeeded and outcome_code == profile.outcomeCode:
            recipe = recipe.model_copy(update={"successByCamera": profile.successByCamera,
                "scale": profile.reactionScale})
    # Logical samples retain their original flight progress and registration.
    # Reprojection remains camera-local; no retained screenshot or new emission.
    sample = replace(sample, bodies=(), numbers=(), vitals=(), device_frame=None,
        projectiles=tuple(row for row in sample.projectiles if row.phase == "travel"),
        delivery_enabled=False)
    return ReactionMediaCue(event_uuid, incoming_event_uuid, bound.timeline, bound.timeline.data,
                            bound.timeline.source.caster, recipe,
                            succeeded, start_ms, sample, source_point)


def bind_cancellation_media(bound: BoundCast, event: PlayerNode,
                            start_ms: float) -> tuple[StationaryMediaCue, ...]:
    profile = bound.timeline.recipe.cancellationMedia
    if (profile is None or event.cancellation is None
            or event.cancellation.outcome_code != profile.outcomeCode):
        return ()
    source = bound.timeline.source.caster
    return tuple(StationaryMediaCue(event.uuid, track, source.grid, source.elevation_steps,
        bound.timeline.facing, start_ms+track.startOffsetMs, bound.timeline.data)
        for track in profile.media)


def interruption_rule(event: PlayerNode, data: AnimationData) -> InterruptionRule | None:
    cancellation = event.cancellation
    if (not event.canceled or cancellation is None
            or cancellation.outcome_code not in data.interruptions.outcomes
            or cancellation.phase is None):
        return None
    return next((rule for rule in data.interruptions.rules
        if cancellation.phase.value in rule.phases
        and cancellation.action_economy_spent == rule.actionEconomySpent), None)


def interrupt_body(cue: BodyActionCue, rule: InterruptionRule) -> BodyActionCue:
    stop = cue.start_ms + ((cue.body_end_ms - cue.start_ms) * rule.nonProjectileBodyFraction
        if rule.nonProjectileBodyFraction is not None
        else (cue.effect_ms - cue.start_ms) * rule.anticipationFraction)
    evidence: list[TimingEvidence] = []
    record_timing(evidence, TimingReference('event', cue.event_uuid, 'cutoff'), 'interruption',
        (TimingOperand(TimingReference('event', cue.event_uuid, 'start'), cue.start_ms),
         TimingOperand(TimingReference('event', cue.event_uuid,
            'body_end' if rule.nonProjectileBodyFraction is not None else 'effect'),
            cue.body_end_ms if rule.nonProjectileBodyFraction is not None else cue.effect_ms)),
        stop, 'fraction', fraction=rule.nonProjectileBodyFraction
            if rule.nonProjectileBodyFraction is not None else rule.anticipationFraction)
    return replace(cue, effect_ms=stop, body_end_ms=stop, join_ms=stop,
        complete_ms=stop, recovery=None, condition=None, feedback=None, timing_evidence=tuple(evidence))


def interrupt_delivery(bound: BoundAttack | BoundCast,
                       rule: InterruptionRule, *, outcome_code: str | None = None) -> BoundAttack | BoundCast:
    evidence: list[TimingEvidence] = []
    stop = interruption_ms(bound, rule, outcome_code=outcome_code, evidence=evidence)
    target = evidence[-1].target
    cutoff = TimingOperand(target, stop, evidence[-1].index)
    record_timing(evidence, replace(target, anchor='body_end'), 'interruption',
        (TimingOperand(replace(target, anchor='body_end'), bound.timeline.body_end_ms), cutoff),
        min(bound.timeline.body_end_ms, stop), 'minimum')
    record_timing(evidence, replace(target, anchor='complete'), 'interruption', (cutoff,), stop)
    return replace(bound, timeline=replace(bound.timeline,
        body_end_ms=min(bound.timeline.body_end_ms, stop), complete_ms=stop,
        timing_evidence=tuple(evidence)))


def interruption_ms(bound: BoundAttack | BoundCast, rule: InterruptionRule, *,
                    outcome_code: str | None = None, reaction_id: str | None = None,
                    evidence: list[TimingEvidence] | None = None) -> float:
    """A presentation anchor; a failed reaction uses it without cutting the cast."""
    timeline = bound.timeline
    target: TimingTarget = (CompiledTimingReference('cast', bound.timeline.source.root_event_uuid, 'cutoff')
        if isinstance(bound, BoundCast) else TimingReference('attack', UUID(bound.timeline.root_event_uuid), 'cutoff'))
    if isinstance(bound, BoundCast):
        profile = bound.timeline.recipe.cancellationMedia
        if profile is not None and (outcome_code == profile.outcomeCode or reaction_id == profile.reactionId):
            stop = max(0., bound.timeline.release_ms + profile.cutoffOffsetMs)
            if evidence is not None:
                record_timing(evidence, target, 'interruption',
                    (TimingOperand(replace(target, anchor='start'), 0.),
                     TimingOperand(replace(target, anchor='release'), bound.timeline.release_ms,
                        offset_ms=profile.cutoffOffsetMs, authored_field='cancellationMedia.cutoffOffsetMs')),
                    stop, 'maximum')
            return stop
    if isinstance(bound, BoundCast) and bound.timeline.source.protections:
        stop = protection_contact_ms(bound)
        if evidence is not None:
            record_timing(evidence, target, 'interruption',
                (TimingOperand(replace(target, anchor='contact'), stop,
                    authored_field='protection_contact_ms.trajectory_sample'),), stop)
        return stop
    if isinstance(bound, BoundAttack):
        timeline = bound.timeline
        release = timeline.release_ms if timeline.release_ms is not None else timeline.contact_ms
        travels = ((timeline.projectile.start_ms, timeline.projectile.end_ms),) if timeline.projectile else ()
        application_ids = (None,) if timeline.projectile else ()
    else:
        timeline = bound.timeline
        release = timeline.release_ms
        projectile = timeline.recipe.projectile
        travels = (tuple((delivery.travel_start_ms, delivery.travel_end_ms)
                         for delivery in cast_deliveries(timeline))
                   if projectile is not None and projectile.targetLocal is None and projectile.travel.enabled else ())
        application_ids = tuple(delivery_identity(delivery) for delivery in cast_deliveries(timeline)) if travels else ()
    stop = release * rule.anticipationFraction
    if not travels and rule.nonProjectileBodyFraction is not None:
        stop = bound.timeline.body_end_ms * rule.nonProjectileBodyFraction
    if rule.travelFraction is not None:
        stop = min((start + (end - start) * rule.travelFraction
                    for start, end in travels if end > start), default=stop)
    if evidence is not None:
        candidates: list[TimingOperand] = []
        if rule.travelFraction is not None:
            for (start, end), application_id in zip(travels, application_ids, strict=True):
                if end > start:
                    candidates.append(record_timing(evidence, target, 'interruption',
                        (TimingOperand(replace(target, anchor='launch', application_id=application_id), start),
                         TimingOperand(replace(target, anchor='contact', application_id=application_id), end)),
                        start + (end - start) * rule.travelFraction, 'fraction', fraction=rule.travelFraction))
        if candidates:
            record_timing(evidence, target, 'interruption', tuple(candidates), stop, 'minimum')
        else:
            endpoint = bound.timeline.body_end_ms if not travels and rule.nonProjectileBodyFraction is not None else release
            fraction = rule.nonProjectileBodyFraction if not travels and rule.nonProjectileBodyFraction is not None else rule.anticipationFraction
            record_timing(evidence, target, 'interruption',
                (TimingOperand(replace(target, anchor='start'), 0.),
                 TimingOperand(replace(target, anchor='body_end' if not travels and rule.nonProjectileBodyFraction is not None else 'release'), endpoint)),
                stop, 'fraction', fraction=fraction)
    return stop


def protection_contact_ms(bound: BoundCast) -> float:
    """Locate the admitted delivery's first contact with a disclosed protection.

    Sampling the existing trajectory keeps cannon arcs and authored attachments
    under their original owner. This chooses a visual cutoff, never a rule hit.
    """
    timeline = bound.timeline
    deliveries = cast_deliveries(timeline)
    fallback = min((delivery.travel_end_ms for delivery in deliveries), default=timeline.release_ms)
    projectile = timeline.recipe.projectile
    if projectile is None or not projectile.travel.enabled or projectile.targetLocal is not None:
        return fallback

    def inside(at: float) -> bool:
        for sample in sample_cast(timeline, at).projectiles:
            if sample.phase != "travel":
                continue
            position, height = projectile_contact(timeline, sample)
            for _, effect in timeline.source.protections:
                geometry = effect.area_geometry
                binding = timeline.data.spatial_media.get(effect.content_ref.content_id)
                if not isinstance(geometry, SpherePresentationGeometry) or binding is None:
                    continue
                dx, dz = position[0] - geometry.center[0], position[1] - geometry.center[1]
                dy = (height - (effect.anchor_elevation_steps or 0)) / binding.surfaceHeightScale
                if dx * dx + dz * dz + dy * dy <= (geometry.radius_feet / 5) ** 2:
                    return True
        return False

    for delivery in deliveries:
        start, end = delivery.travel_start_ms, delivery.travel_end_ms
        previous = start
        for index in range(1, 33):
            current = start + (end - start) * index / 32 - 1e-6
            if inside(current):
                for _ in range(16):
                    middle = (previous + current) / 2
                    if inside(middle):
                        current = middle
                    else:
                        previous = middle
                return current
            previous = current
    return fallback


def interrupt_sample(sample: AttackSample | CastSample, source_uuid: str) -> AttackSample | CastSample:
    """Never display destination effects from a canceled action's ordinary recipe.

    Target-local exports can begin their impact interval at time zero. Cutting
    the clock alone is therefore insufficient: retain only attempt/travel tracks.
    Actual completed children are sampled separately by the causal compositor.
    """
    common = dict(bodies=tuple(body for body in sample.bodies if body.actor_uuid == source_uuid),
        projectiles=tuple(projectile for projectile in sample.projectiles if projectile.phase != "impact"),
        numbers=(), vitals=())
    return replace(sample, **common, delivery_enabled=False) if isinstance(sample, CastSample) else replace(sample, **common)
