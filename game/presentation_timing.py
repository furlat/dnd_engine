"""Portable references to clocks already produced by family binders.

This is a view, not a scheduler: it cannot change a date or invent a causal edge.
Snapshot reconciliation is explicitly distinct from an occurrence's admission.
"""

from dataclasses import dataclass, replace
from math import isfinite
from typing import Literal
from uuid import UUID

from pydantic import ConfigDict, FiniteFloat

from game.timing_evidence import DependencyScope, PresentationDependencies, TimingEvidence, validate_timing_evidence
from game.attack import BoundAttack
from game.choreography import (BoundChoreography, MotionTimeline, MotionGroupSource,
    StateCommitEvidence, bound_action_dependencies, walk_bound_timelines)


MilestoneAnchor = Literal['commit', 'reconciliation', 'start', 'release', 'contact',
                          'body_end', 'recovery', 'complete', 'effect', 'hp', 'flash', 'number', 'join']


@dataclass(frozen=True, slots=True)
class PresentationMilestone:
    __pydantic_config__ = ConfigDict(extra='forbid')
    owner_uuid: UUID | None
    family: Literal['state', 'action', 'body', 'equipment', 'motion', 'application', 'ground_delivery', 'damage', 'healing', 'life', 'turn']
    index: int
    anchor: MilestoneAnchor
    at_ms: FiniteFloat
    event_uuids: tuple[UUID, ...] = ()
    observation_event_uuids: tuple[UUID, ...] = ()
    world_event_uuids: tuple[UUID, ...] = ()
    application_id: str | None = None


def presentation_milestones(choreography: BoundChoreography | None = None,
                           motion: MotionTimeline | None = None,
                           ) -> tuple[PresentationMilestone, ...]:
    """Normalize local clocks to one head without changing native ordering."""
    result: list[PresentationMilestone] = []

    def commits(owner: UUID, rows: tuple[StateCommitEvidence, ...], offset: float) -> None:
        for index, row in enumerate(rows):
            result.append(PresentationMilestone(owner, 'state', index, 'commit', offset + row.at_ms,
                tuple(node.uuid for node in row.nodes), row.observation_event_uuids, row.world_event_uuids))

    for visit in walk_bound_timelines(choreography, motion):
        timeline, offset = visit.timeline, visit.offset_ms
        if isinstance(timeline, BoundChoreography):
            commits(timeline.root_uuid, timeline.state_commits, offset)
            for index, (at, _, event_uuid) in enumerate(timeline.turn_starts):
                result.append(PresentationMilestone(event_uuid, 'turn', index,
                    'start', offset + at, (event_uuid,)))
            for index, action in enumerate(timeline.nodes):
                bound = action.bound.timeline
                clocks: list[tuple[MilestoneAnchor, float]] = [('start', 0.), ('body_end', bound.body_end_ms), ('complete', bound.complete_ms)]
                if isinstance(action.bound, BoundAttack):
                    clocks.append(('contact', action.bound.timeline.contact_ms))
                    if action.bound.timeline.release_ms is not None:
                        clocks.append(('release', action.bound.timeline.release_ms))
                else:
                    clocks.extend((('release', action.bound.timeline.release_ms),
                                   ('recovery', action.bound.timeline.recovery_start_ms)))
                for anchor, at in clocks:
                    if action.interrupted and (at > bound.complete_ms or anchor == 'contact'):
                        continue
                    result.append(PresentationMilestone(action.event_uuid, 'action', index,
                        anchor, offset + action.start_ms + at, (action.event_uuid,)))
                if not isinstance(action.bound, BoundAttack) and not action.interrupted:
                    for application_index, application in enumerate(action.bound.timeline.applications):
                        application_clocks: tuple[tuple[MilestoneAnchor, float | None], ...] = (
                            ('start', application.travel_start_ms), ('contact', application.travel_end_ms),
                            ('hp', application.hp_ms), ('flash', application.flash_ms),
                            ('number', application.number_ms), ('complete', application.damage_end_ms))
                        for anchor, at in application_clocks:
                            if at is not None:
                                result.append(PresentationMilestone(action.event_uuid, 'application',
                                    application_index, anchor, offset + action.start_ms + at,
                                    tuple(node.uuid for node in application.source.results),
                                    application_id=application.source.application_id))
                    ground = action.bound.timeline.ground_delivery
                    if ground is not None:
                        ground_clocks: tuple[tuple[MilestoneAnchor, float], ...] = (('start', ground.travel_start_ms), ('contact', ground.travel_end_ms))
                        for anchor, at in ground_clocks:
                            result.append(PresentationMilestone(action.event_uuid, 'ground_delivery', 0,
                                anchor, offset + action.start_ms + at))
            for index, body in enumerate(timeline.body_actions):
                body_clocks: tuple[tuple[MilestoneAnchor, float], ...] = (('start', body.start_ms),
                    ('effect', body.effect_ms), ('body_end', body.body_end_ms), ('join', body.join_ms), ('complete', body.complete_ms))
                for anchor, at in body_clocks:
                    result.append(PresentationMilestone(body.event_uuid, 'body', index, anchor,
                        offset + at, (body.event_uuid,)))
            for index, equipment in enumerate(timeline.equipment):
                result.append(PresentationMilestone(equipment.event_uuid, 'equipment', index,
                    'complete', offset + equipment.start_ms + equipment.bound.timeline.complete_ms,
                    (equipment.event_uuid,)))
            for index, damage in enumerate(timeline.damage):
                damage_clocks: tuple[tuple[MilestoneAnchor, float], ...] = (
                    ('start', damage.timing.start_ms), ('hp', damage.timing.hp_ms),
                    ('flash', damage.timing.flash_ms), ('number', damage.timing.number_ms),
                    ('complete', damage.timing.end_ms))
                for anchor, at in damage_clocks:
                    result.append(PresentationMilestone(damage.event_uuid, 'damage', index,
                        anchor, offset + at, tuple(node.uuid for node in damage.results)))
            for index, healing in enumerate(timeline.healing):
                result.append(PresentationMilestone(healing.event.uuid, 'healing', index,
                    'start', offset + healing.start_ms, (healing.event.uuid,)))
                if healing.end_ms is not None:
                    result.append(PresentationMilestone(healing.event.uuid, 'healing', index,
                        'complete', offset + healing.end_ms, (healing.event.uuid,)))
            for index, lifecycle in enumerate(timeline.lifecycle):
                result.append(PresentationMilestone(lifecycle.event.uuid, 'life', index,
                    'start', offset + lifecycle.start_ms, (lifecycle.event.uuid,)))
        else:
            for index, leg in enumerate(timeline.legs):
                leg_clocks: tuple[tuple[MilestoneAnchor, float], ...] = (('start', leg.start_ms), ('complete', leg.end_ms))
                for anchor, at in leg_clocks:
                    result.append(PresentationMilestone(visit.event_uuid, 'motion', index, anchor, offset + at))
            for row in timeline.state_provenance:
                for source in row.sources:
                    if isinstance(source, MotionGroupSource):
                        commits(source.root_uuid, source.commits, offset + source.offset_ms)
                    else:
                        result.append(PresentationMilestone(visit.event_uuid, 'motion', row.state_index,
                            'reconciliation' if row.origin in ('root_reconciliation', 'landing_prefix') else 'commit',
                            offset + row.at_ms, source.event_uuids, source.observation_event_uuids,
                            source.world_event_uuids))
    # A nested group can be present both in the visited graphics tree and in
    # motion provenance. Equality includes its normalized date and exact inputs.
    if any(not isfinite(row.at_ms) for row in result):
        raise ValueError('Nonfinite presentation milestone clock')
    return tuple(dict.fromkeys(result))


def presentation_dependencies(choreography: BoundChoreography | None = None,
                              motion: MotionTimeline | None = None,
                              *, offset_ms: float = 0.,
                              ) -> tuple[PresentationDependencies, ...]:
    """Export only producer-recorded relations; clocks are normalized, not solved."""
    result: list[PresentationDependencies] = []

    def append(owner: UUID, rows: tuple[TimingEvidence, ...], offset: float,
               scope: DependencyScope = 'choreography') -> None:
        if not rows:
            return
        if not isfinite(offset):
            raise ValueError('Nonfinite presentation dependency offset')
        errors = validate_timing_evidence(rows)
        if errors:
            raise ValueError(f'Invalid timing evidence for {owner}: {errors}')
        result.append(PresentationDependencies(owner, offset, tuple(replace(row,
            at_ms=row.at_ms + offset,
            inputs=tuple(replace(source, at_ms=source.at_ms + offset) for source in row.inputs))
            for row in rows), scope))

    for visit in walk_bound_timelines(choreography, motion, offset_ms=offset_ms):
        timeline = visit.timeline
        if isinstance(timeline, BoundChoreography):
            append(timeline.root_uuid, timeline.timing_evidence, visit.offset_ms)
            for cue in timeline.portals:
                append(cue.event_uuid, cue.timing_evidence, visit.offset_ms, 'portal')
            for cue in timeline.forced_movement:
                append(cue.event_uuid, cue.timing_evidence, visit.offset_ms, 'displacement')
            for cue in timeline.shoves:
                append(cue.event_uuid, cue.timing_evidence, visit.offset_ms, 'shove')
            for action in bound_action_dependencies(timeline):
                append(action.owner_uuid, action.evidence, visit.offset_ms + action.offset_ms, action.scope)
        else:
            if visit.event_uuid is not None:
                append(visit.event_uuid, timeline.timing_evidence, visit.offset_ms, 'motion')
            for row in timeline.state_provenance:
                for source in row.sources:
                    if isinstance(source, MotionGroupSource):
                        append(source.root_uuid, source.timing_evidence, visit.offset_ms + source.offset_ms)
                        for action in source.action_timing:
                            append(action.owner_uuid, action.evidence,
                                visit.offset_ms + source.offset_ms + action.offset_ms, action.scope)
    return tuple(dict.fromkeys(result))
