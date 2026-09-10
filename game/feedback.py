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
from game.combat import actor_contact
from game.motion import MotionTimeline


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
    for node in bound.nodes:
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
    for condition in bound.conditions:
        if condition.feedback_text is None:
            continue
        identity = str(condition.target_uuid)
        contact = group_contacts.get(identity)
        if contact is None:
            contact = actor_contact(bound.before, bound.before.actors[condition.target_uuid], data)
        style = condition.badge_style
        tracks.append(FeedbackTrack(contact, absolute_start_ms + condition.start_ms, style.durationMs,
            None, condition.feedback_text, condition.feedback_color, style, kind="badge"))
    return tuple(sorted(tracks, key=lambda track: track.start_ms))


def motion_feedback(motion: MotionTimeline, data: AnimationData, absolute_start_ms: float) -> tuple[FeedbackTrack, ...]:
    """The original reaction-phase badge and the same nested action feedback."""
    tracks: list[FeedbackTrack] = []
    context, style = data.movement_reaction_context, data.badge_style
    for reaction in motion.reactions:
        start = absolute_start_ms + reaction.start_ms
        if context.feedbackEnabled:
            label = context.label if reaction.action_label is None else f"{context.label}: {reaction.action_label}"
            tracks.append(FeedbackTrack(reaction.source, start, style.durationMs, None, label,
                                        context.feedbackColor, style, kind="badge"))
        tracks.extend(choreography_feedback(reaction.choreography, data, start,
                                            contacts={reaction.contact.actor_uuid: reaction.contact}))
    return tuple(sorted(tracks, key=lambda track: track.start_ms))
