"""Decorative FloatingText tracks keep their own fade and frozen launch anchor.

The application samples these with its presentation clock. They never extend
an action join, acquire a queue, or mutate historical actor facts.
"""

from dataclasses import dataclass
from math import isfinite
from typing import Literal, Mapping

from game.animation import ActorContact, NumberSample
from game.animation_types import AnimationData, FloatingFeedbackStyle
from game.attack import BoundAttack
from game.choreography import BoundChoreography
from game.combat import actor_contact, actor_is_visible
from game.forced_movement import forced_contact
from game.motion import MotionTimeline
from game.player_facts import HealFact
from game.player_reduction import observe_actors


@dataclass(frozen=True, slots=True)
class FeedbackTrack:
    contact: ActorContact
    start_ms: float
    duration_ms: float
    value: int | None
    label: str
    color: int
    style: FloatingFeedbackStyle
    application_id: str | None = None
    kind: Literal["number", "badge"] = "number"


def sample_feedback(track: FeedbackTrack, absolute_ms: float) -> NumberSample | None:
    """Original FloatingText progress/fade, independent of the parent join."""
    if not isfinite(absolute_ms) or absolute_ms < 0:
        raise ValueError("feedback sampling requires finite nonnegative time")
    if not track.start_ms <= absolute_ms < track.start_ms + track.duration_ms:
        return None
    progress = (absolute_ms - track.start_ms) / track.duration_ms
    fade = track.style.fadeStartFraction
    alpha = 1.0 if progress < fade or fade == 1 else (1 - progress) / (1 - fade)
    return NumberSample(track.contact.actor_uuid, track.value, track.label, track.color,
                        progress, alpha, track.application_id, track.kind)


def choreography_feedback(bound: BoundChoreography, data: AnimationData, absolute_start_ms: float,
                           *, contacts: Mapping[str, ActorContact] | None = None,
                           ) -> tuple[FeedbackTrack, ...]:
    """Extract existing anchored feedback; number duration belongs to its recipe."""
    if not isfinite(absolute_start_ms) or absolute_start_ms < 0:
        raise ValueError("feedback start requires finite nonnegative time")
    tracks: list[FeedbackTrack] = []
    group_contacts = dict(contacts or {})
    for cue in bound.movements:
        tracks.extend(motion_feedback(cue.timeline, data, absolute_start_ms + cue.start_ms))
    for cue in bound.body_actions:
        group_contacts[cue.contact.actor_uuid] = cue.contact
        if cue.feedback is not None:
            tracks.append(FeedbackTrack(cue.contact, absolute_start_ms + cue.effect_ms,
                data.badge_style.durationMs, None, cue.feedback.text, cue.feedback.color,
                data.badge_style, kind="badge"))
    for cue in bound.shoves:
        group_contacts.update((contact.actor_uuid, contact) for contact in (cue.source, cue.target))
        if cue.feedback.enabled:
            tracks.append(FeedbackTrack(cue.target, absolute_start_ms + cue.contact_ms,
                data.badge_style.durationMs, None, cue.feedback.text, cue.feedback.color,
                data.badge_style, kind="badge"))
    context = data.forced_movement_context
    if context.feedbackEnabled:
        for cue in bound.forced_movement:
            tracks.append(FeedbackTrack(cue.actor, absolute_start_ms + cue.start_ms, data.badge_style.durationMs,
                None, context.label, context.feedbackColor, data.badge_style, kind="badge"))
    for cue in bound.damage:
        number = cue.damage.floatingNumber
        if number.enabled:
            tracks.append(FeedbackTrack(cue.contact, absolute_start_ms + cue.timing.number_ms,
                number.durationMs, cue.applied_damage, number.label, number.color, data.number_style))
    for node in bound.nodes:
        if node.interrupted:
            continue
        start = absolute_start_ms + node.start_ms
        if isinstance(node.bound, BoundAttack):
            attack = node.bound.timeline
            group_contacts.update((contact.actor_uuid, contact) for contact in (attack.source, attack.target))
            timing, damage = attack.damage_timing, attack.damage
            if timing is not None and damage is not None and damage.floatingNumber.enabled and attack.damage_total is not None:
                number = damage.floatingNumber
                tracks.append(FeedbackTrack(attack.target, start + timing.number_ms, number.durationMs,
                    attack.damage_total, number.label, number.color, attack.data.number_style))
            if attack.feedback is not None:
                style = attack.data.badge_style
                tracks.append(FeedbackTrack(attack.target, start + attack.contact_ms, style.durationMs,
                    None, attack.feedback.text, attack.feedback.color, style, kind="badge"))
        else:
            cast = node.bound.timeline
            group_contacts[cast.source.caster.actor_uuid] = cast.source.caster
            for application in cast.applications:
                source, damage = application.source, application.damage
                group_contacts[source.target.actor_uuid] = source.target
                if (application.number_ms is not None and damage is not None
                        and damage.floatingNumber.enabled and source.damage_total is not None):
                    number = damage.floatingNumber
                    tracks.append(FeedbackTrack(source.target, start + application.number_ms, number.durationMs,
                        source.damage_total, number.label, number.color, cast.data.number_style, source.application_id))
    healing = data.healing_context
    if healing.feedbackEnabled:
        for cue in bound.healing:
            event = cue.event.fact
            assert isinstance(event, HealFact)
            identity = str(event.target_entity_uuid)
            contact = group_contacts.get(identity)
            if contact is None:
                contact = actor_contact(bound.before, bound.before.actors[event.target_entity_uuid], data)
            tracks.append(FeedbackTrack(contact, absolute_start_ms + cue.start_ms, healing.feedbackDurationMs,
                event.actual_healing, healing.feedbackLabel, healing.feedbackColor, data.number_style))
    for condition in bound.conditions:
        if condition.feedback_text is None:
            continue
        identity = str(condition.target_uuid)
        contact = group_contacts.get(identity)
        if contact is None:
            observed = observe_actors(bound.before, tuple(observation for at, observation in bound.observations
                                                        if at <= condition.start_ms))
            actor = observed.actors.get(condition.target_uuid)
            if actor is None or not actor_is_visible(observed, actor):
                continue
            contact = actor_contact(observed, actor, data)
        for cue in bound.forced_movement:
            if cue.actor.actor_uuid == identity and condition.start_ms >= cue.start_ms:
                contact = forced_contact(cue, data, condition.start_ms)
        style = condition.badge_style
        tracks.append(FeedbackTrack(contact, absolute_start_ms + condition.start_ms, style.durationMs,
            None, condition.feedback_text, condition.feedback_color, style, kind="badge"))
    for cue in bound.lifecycle:
        if cue.feedback is not None and cue.feedback.enabled:
            style = data.badge_style
            contact = group_contacts.get(cue.contact.actor_uuid, cue.contact)
            tracks.append(FeedbackTrack(contact, absolute_start_ms + cue.start_ms, style.durationMs,
                None, cue.feedback.text, cue.feedback.color, style, kind="badge"))
    return tuple(sorted(tracks, key=lambda track: track.start_ms))


def motion_feedback(motion: MotionTimeline, data: AnimationData, absolute_start_ms: float) -> tuple[FeedbackTrack, ...]:
    """The original reaction-phase badge and the same nested action feedback."""
    tracks: list[FeedbackTrack] = []
    context, style = data.movement_reaction_context, data.badge_style
    for reaction in motion.reactions:
        start = absolute_start_ms + reaction.start_ms
        if context.feedbackEnabled and reaction.source is not None:
            label = context.label if reaction.action_label is None else f"{context.label}: {reaction.action_label}"
            tracks.append(FeedbackTrack(reaction.source, start, style.durationMs, None, label,
                                        context.feedbackColor, style, kind="badge"))
        tracks.extend(choreography_feedback(reaction.choreography, data, start,
                                            contacts={reaction.contact.actor_uuid: reaction.contact}
                                            if reaction.contact is not None else {}))
    return tuple(sorted(tracks, key=lambda track: track.start_ms))
