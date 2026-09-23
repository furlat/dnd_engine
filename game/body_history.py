"""The short retained bound-input window needed by authored historical body trails.

No pixels, extra clocks or per-camera accumulation: sampling reads the same pure
pose resolver as the current frame, at an explicit earlier presentation time.
"""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from game.animation_types import AnimationData, Facing8
from game.body_presentation import BodyPresentation, sample_body_presentation
from game.body_pose_types import BodyTrailPose
from game.choreography import BoundChoreography, MotionTimeline
from game.combat import actor_is_visible
from game.condition_animation import ConditionAppearance
from game.player_facts import PlayerState
from game.visual_position import VisualPosition


@dataclass(frozen=True, slots=True)
class BodyHistoryHead:
    start_ms: float
    before: PlayerState
    after: PlayerState | None
    facings: Mapping[str, Facing8]
    positions: Mapping[str, VisualPosition]
    choreography: BoundChoreography | None = None
    motion: MotionTimeline | None = None
    cuts: tuple[tuple[float, str], ...] = ()


def _state_cuts(before: PlayerState, states: tuple[tuple[float, PlayerState], ...],
                offset: float) -> tuple[tuple[float, str], ...]:
    result = []
    prior = {str(actor.uuid) for actor in before.actors.values() if actor_is_visible(before, actor)}
    for at, state in states:
        visible = {str(actor.uuid) for actor in state.actors.values() if actor_is_visible(state, actor)}
        result.extend((offset + at, actor) for actor in prior - visible)
        prior = visible
    return tuple(result)


def _group_cuts(group: BoundChoreography, offset: float = 0) -> tuple[tuple[float, str], ...]:
    return (*_state_cuts(group.before, group.states, offset),
            *((offset + cue.effect_ms, cue.contact.actor_uuid) for cue in group.body_actions if cue.relocates),
            *((offset + cue.arrival_ms, cue.actor_uuid) for cue in group.portals),
            *(row for cue in group.movements for row in _motion_cuts(cue.timeline, offset + cue.start_ms)))


def _motion_cuts(motion: MotionTimeline, offset: float = 0) -> tuple[tuple[float, str], ...]:
    return (*_state_cuts(motion.before, motion.states, offset),
            *(row for reaction in motion.reactions
              for row in _group_cuts(reaction.choreography, offset + reaction.start_ms)))


def retain_body_head(previous: tuple[BodyHistoryHead, ...], before: PlayerState, after: PlayerState | None,
                     *, start_ms: float, facings: Mapping[str, Facing8],
                     positions: Mapping[str, VisualPosition], choreography: BoundChoreography | None = None,
                     motion: MotionTimeline | None = None) -> tuple[BodyHistoryHead, ...]:
    # One predecessor covers an idle interval, including a completed head.
    last_old = max((index for index, head in enumerate(previous) if head.start_ms < start_ms - 240), default=0)
    cuts = _motion_cuts(motion) if motion is not None else _group_cuts(choreography) if choreography else ()
    head = BodyHistoryHead(start_ms, before, after, MappingProxyType(dict(facings)),
        MappingProxyType(dict(positions)), choreography, motion,
        tuple((start_ms + at, actor) for at, actor in cuts))
    return (*previous[last_old:], head)


def sample_body_trails(history: tuple[BodyHistoryHead, ...], current: BodyPresentation,
                       appearances: Mapping[str, ConditionAppearance], data: AnimationData,
                       now: float) -> tuple[BodyTrailPose, ...]:
    sampled: dict[float, BodyPresentation | None] = {}

    def at(when: float) -> BodyPresentation | None:
        if when not in sampled:
            head = next((row for row in reversed(history) if row.start_ms <= when), None)
            if head is None:
                sampled[when] = None
            else:
                duration = (head.motion.complete_ms if head.motion is not None else
                            head.choreography.complete_ms if head.choreography is not None else 0.)
                elapsed = when - head.start_ms
                pose = sample_body_presentation(head.before, head.after, data, min(elapsed, duration),
                    head.start_ms + min(elapsed, duration), head.facings,
                    choreography=head.choreography, motion=head.motion, positions=head.positions)
                sampled[when] = (sample_body_presentation(pose.displayed, None, data, 0., when,
                    pose.facings, positions=pose.positions) if elapsed > duration else pose)
        return sampled[when]

    result = []
    for pose in current.poses:
        identity = pose.body.actor_uuid
        appearance = appearances[identity]
        distortion = appearance.distortion
        if distortion is None or appearance.activity not in ("move", "jump", "forced_move"):
            continue
        for trail in distortion.trails:
            when = now - trail.ageMs
            if any(when < time <= now and actor == identity for head in history for time, actor in head.cuts):
                continue
            past = at(when)
            old = next((row for row in past.poses if row.body.actor_uuid == identity), None) if past else None
            if (old is None or old.actor.condition.distortion is None
                    or old.actor.contact.grid == pose.actor.contact.grid
                    and old.actor.contact.body_lift_px == pose.actor.contact.body_lift_px):
                continue
            result.append(BodyTrailPose(old, trail.opacity, trail.ageMs))
    return tuple(result)
