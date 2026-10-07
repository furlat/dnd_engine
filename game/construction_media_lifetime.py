"""Witnessed physical-section dates on the existing presentation frame pump."""

from dataclasses import replace
from typing import Mapping
from uuid import UUID
from game.timing_evidence import TimingEvidence, TimingOperand, TimingReference, TimingAnchor, TimingReason

from game.animation_types import AnimationData
from game.choreography import BoundChoreography, MotionTimeline, walk_bound_timelines
from game.construction_transitions import ConstructionMediaLifetime, construction_duration
from dnd.player.facts import PlayerState


def _timing(record: ConstructionMediaLifetime, anchor: TimingAnchor, at: float,
            source: TimingReference, reason: TimingReason) -> tuple[TimingEvidence, ...]:
    row = TimingEvidence(len(record.timing_evidence),
        TimingReference("object", record.object.item.item_uuid, anchor), reason, "offset",
        (TimingOperand(source, at),), at)
    if any(previous.target == row.target and previous.reason == row.reason and previous.inputs == row.inputs
            and previous.at_ms == row.at_ms for previous in record.timing_evidence):
        return record.timing_evidence
    return (*record.timing_evidence, row)


def register_construction_lifetimes(retained: Mapping[UUID, ConstructionMediaLifetime], before: PlayerState,
        data: AnimationData, *, absolute_start_ms: float, choreography: BoundChoreography | None = None,
        motion: MotionTimeline | None = None) -> dict[UUID, ConstructionMediaLifetime]:
    """Sight loss retains the clock, never a drawn foreign object or a break."""
    result = {identity: record for identity, record in retained.items()
        if (record.removed_ms is None or absolute_start_ms < record.removed_ms+construction_duration(
            data, data.construction_media[record.object.item.item_id], 'removal'))
        and (record.destroyed_ms is None or absolute_start_ms
            < record.destroyed_ms+construction_duration(data, data.construction_media[record.object.item.item_id], 'destruction'))}
    for visit in walk_bound_timelines(choreography, motion):
        timeline = visit.timeline
        states = timeline.states
        known = set(timeline.before.objects)
        for at, state in ((0., timeline.before), *states):
            for identity, obj in state.objects.items():
                if obj.item.item_id in data.construction_media and obj.item.construction_geometry is not None:
                    old = result.get(identity)
                    result[identity] = replace(old, object=obj) if old is not None else ConstructionMediaLifetime(obj)
                    if identity not in known and result[identity].committed_ms is None:
                        result[identity] = replace(result[identity],
                            committed_ms=absolute_start_ms + visit.offset_ms + at,
                            timing_evidence=_timing(result[identity], "committed", absolute_start_ms + visit.offset_ms + at,
                                TimingReference("object", identity, "admission"), "lifetime_commit"))
                    known.add(identity)
        transitions = timeline.world_transitions
        dust_owners = {row.identity for row in transitions if row.object_dust is not None}
        for transition in transitions:
            if transition.membrane_contact is not None:
                source = result.get(transition.identity)
                if source is not None:
                    at = absolute_start_ms + visit.offset_ms + transition.start_ms
                    impulse = (at, transition.membrane_contact)
                    for identity, record in tuple(result.items()):
                        if record.object.item.construction_owner_uuid == source.object.item.construction_owner_uuid:
                            impulses = tuple(row for row in record.membrane_impulses if at-row[0] < 10000)
                            result[identity] = replace(record, membrane_impulses=tuple(dict.fromkeys((*impulses, impulse))))
                continue
            if transition.construction_collapse is not None:
                collapse=transition.construction_collapse
                at=absolute_start_ms+visit.offset_ms+transition.start_ms
                for identity,record in tuple(result.items()):
                    if record.object.item.construction_owner_uuid==collapse.object.item.construction_owner_uuid:
                        result[identity]=replace(record,destroyed_ms=at,removed_ms=None,collapse_contacts=collapse.contacts,
                            timing_evidence=_timing(record, "destroyed", at,
                                TimingReference("object", transition.identity, "destroyed"), "lifetime_destruction"))
                continue
            record = result.get(transition.identity)
            if record is None:
                continue
            at = absolute_start_ms+visit.offset_ms+transition.start_ms
            if transition.field == 'removal' and record.destroyed_ms is None and record.removed_ms is None:
                result[transition.identity] = replace(record, removed_ms=at,
                    timing_evidence=_timing(record, "removed", at,
                        TimingReference("object", transition.identity, "start"), "lifetime_removal"))
            elif transition.field == 'creation' and record.applied_ms is None:
                result[transition.identity] = replace(record, applied_ms=at,
                    timing_evidence=_timing(record, "applied", at,
                        TimingReference("object", transition.identity, "start"), "lifetime_application"))
            elif transition.object_dust is not None:
                if not transition.object_dust.partial:
                    result.pop(transition.identity,None)
            elif transition.field == 'destruction' and record.destroyed_ms is None and transition.identity not in dust_owners:
                result[transition.identity] = replace(record, destroyed_ms=at, removed_ms=None,
                    timing_evidence=_timing(record, "destroyed", at,
                        TimingReference("object", transition.identity, "start"), "lifetime_destruction"))
        # Witnessed parent removal retires its actually removed section objects.
        # A merely unseen object remains in remembered world state and is not retired.
        if isinstance(timeline, BoundChoreography):
            removed = {t.identity for t in transitions if t.field == 'removal'}
            for identity in removed:
                at = next(t.start_ms for t in transitions if t.identity == identity and t.field == 'removal')
                for section, record in tuple(result.items()):
                    if (section not in timeline.after.objects and record.destroyed_ms is None
                            and record.object.item.construction_owner_uuid == identity):
                        result[section] = replace(record, removed_ms=absolute_start_ms+visit.offset_ms+at,
                            timing_evidence=_timing(record, "removed", absolute_start_ms+visit.offset_ms+at,
                                TimingReference("spatial", identity, "start"), "lifetime_removal"))
    return result
