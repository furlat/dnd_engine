"""Dates for observed maintained fields, registered once per received head."""

from dataclasses import dataclass, replace
from typing import Mapping
from uuid import UUID
from game.timing_evidence import TimingEvidence, TimingOperand, TimingReference, TimingAnchor, TimingReason, TimingMeasurement

from dnd.types.senses import PerceivedSpatialEffect
from dnd.types.spatial_effects import SpatialEffectChangeOperation
from game.animation_types import AnimationData, Facing8
from game.animation import ActorContact, media_target_applies, media_track_duration
from game.combat import BoundCast
from game.choreography import BoundChoreography, MotionTimeline, walk_bound_timelines
from game.player_facts import DamageResultFact, PlayerLineage, PlayerState, SpatialEffectStateFact
from game.maintained_media import maintained_removal_duration


@dataclass(frozen=True, slots=True)
class SpatialRecipientEndpoint:
    """One disclosed cast placement, retained only by its resulting area owner."""
    track_id: str
    position: tuple[float, float]
    elevation_steps: float
    start_ms: float


@dataclass(frozen=True, slots=True)
class SpatialDamageContact:
    """One committed packet's existing contact and presentation date."""
    event_uuid: UUID
    recipient: ActorContact
    at_ms: float
    formation: bool


@dataclass(frozen=True, slots=True)
class SpatialMediaLifetime:
    effect: PerceivedSpatialEffect
    applied_ms: float | None = None
    removed_ms: float | None = None
    recipient_endpoints: tuple[SpatialRecipientEndpoint, ...] = ()
    damage_contacts: tuple[SpatialDamageContact, ...] = ()
    facings: tuple[tuple[float, Facing8], ...] = ()
    retired_cells: tuple[tuple[tuple[int, int], float], ...] = ()
    committed_ms: float | None = None
    timing_evidence: tuple[TimingEvidence, ...] = ()


def _timing(record: SpatialMediaLifetime, owner: UUID, anchor: TimingAnchor, at: float,
            source: TimingReference, reason: TimingReason,
            measurements: tuple[TimingMeasurement, ...] = ()) -> tuple[TimingEvidence, ...]:
    row = TimingEvidence(len(record.timing_evidence),
        TimingReference("spatial", owner, anchor), reason, "offset",
        (TimingOperand(source, at, measurements=measurements),), at)
    if any(previous.target == row.target and previous.reason == row.reason and previous.inputs == row.inputs
            and previous.at_ms == row.at_ms for previous in record.timing_evidence):
        return record.timing_evidence
    return (*record.timing_evidence, row)


def _observed(state: PlayerState, data: AnimationData) -> dict[UUID, PerceivedSpatialEffect]:
    return {owner: effect for owner, effect in state.senses.spatial_effects.items()
            if (binding := data.spatial_media.get(effect.content_ref.content_id)) is not None
            and (binding.formationCommitMs or maintained_removal_duration(data, binding) or any(layer.applicationAssetId is not None
                 or layer.recipientTrackId is not None for layer in binding.layers))
            } if state.senses is not None else {}


def _edges(before: PlayerState, states: tuple[tuple[float, PlayerState], ...], data: AnimationData,
           offset: float) -> list[tuple[float, UUID, PerceivedSpatialEffect, bool]]:
    result = []
    prior = _observed(before, data)
    for at, state in states:
        current = _observed(state, data)
        result.extend((at + offset, owner, effect, True) for owner, effect in current.items() if owner not in prior)
        result.extend((at + offset, owner, effect, False) for owner, effect in prior.items() if owner not in current)
        prior = current
    return result


def register_spatial_lifetimes(
    retained: Mapping[UUID, SpatialMediaLifetime], before: PlayerState, data: AnimationData,
    *, absolute_start_ms: float, lineage: PlayerLineage | None = None,
    choreography: BoundChoreography | None = None, motion: MotionTimeline | None = None,
) -> dict[UUID, SpatialMediaLifetime]:
    """Cold acquisition sustains; only witnessed creation/removal animates."""
    observed = _observed(before, data)
    result = {owner: record for owner, record in retained.items()
        if owner in observed or (record.removed_ms is None and any(layer.wallAssembly is not None
            for layer in data.spatial_media[record.effect.content_ref.content_id].layers))
        or (record.removed_ms is not None and absolute_start_ms
            < record.removed_ms + maintained_removal_duration(data, data.spatial_media[record.effect.content_ref.content_id]))}
    for owner, effect in observed.items():
        result.setdefault(owner, SpatialMediaLifetime(effect))
    created, removed = set(), set()
    removed_cells: dict[UUID, set[tuple[int,int]]] = {}
    for node in lineage.events if lineage is not None else ():
        if node.canceled or not isinstance(node.fact, SpatialEffectStateFact):
            continue
        fact = node.fact
        if fact.removed_positions:
            removed_cells.setdefault(fact.spatial_effect_uuid,set()).update(fact.removed_positions)
        if fact.operation is SpatialEffectChangeOperation.CREATED:
            created.add(fact.spatial_effect_uuid)
        elif fact.operation is SpatialEffectChangeOperation.REMOVED:
            removed.add(fact.spatial_effect_uuid)
    visits = tuple(walk_bound_timelines(choreography, motion))
    created_recipients: dict[UUID, tuple[SpatialRecipientEndpoint, ...]] = {}
    if lineage is not None:
        by_lineage = {node.lineage_uuid: node for node in lineage.events}
        casts = {node.event_uuid: (visit.offset_ms + node.start_ms, node.bound.timeline)
                 for visit in visits if isinstance(visit.timeline, BoundChoreography)
                 for node in visit.timeline.nodes if isinstance(node.bound, BoundCast) and not node.interrupted}
        for node in lineage.events:
            if (node.canceled or not isinstance(node.fact, SpatialEffectStateFact)
                    or node.fact.operation is not SpatialEffectChangeOperation.CREATED):
                continue
            parent = by_lineage.get(node.parent_lineage) if node.parent_lineage is not None else None
            while parent is not None and parent.uuid not in casts:
                parent = by_lineage.get(parent.parent_lineage) if parent.parent_lineage is not None else None
            if parent is None:
                continue
            cast_start, timeline = casts[parent.uuid]
            created_recipients[node.fact.spatial_effect_uuid] = tuple(dict.fromkeys(
                SpatialRecipientEndpoint(track.id, application.target.grid, application.target.elevation_steps,
                    absolute_start_ms + cast_start + timeline.release_ms + track.startOffsetMs
                    + media_track_duration(data, track))
                for track in timeline.recipe.media if track.attachment == "target_ground"
                for application in timeline.source.applications
                if isinstance(application.target, ActorContact) and media_target_applies(track, application)))
    edges = [row for visit in visits
             for row in _edges(visit.timeline.before, visit.timeline.states, data, visit.offset_ms)]
    formation_starts = {row.identity: row.start_ms + visit.offset_ms for visit in visits
        for row in visit.timeline.world_transitions if row.field == "creation"}
    for at, owner, effect, added in sorted(edges, key=lambda row: row[0]):
        old = result.get(owner)
        if added and old is None:
            wanted = {layer.recipientTrackId for layer in data.spatial_media[effect.content_ref.content_id].layers}
            start = formation_starts.get(owner) if owner in created else None
            result[owner] = SpatialMediaLifetime(effect,
                absolute_start_ms + start if start is not None else None,
                recipient_endpoints=tuple(row for row in created_recipients.get(owner, ()) if row.track_id in wanted),
                committed_ms=absolute_start_ms + at)
            record = result[owner]
            record = replace(record, timing_evidence=_timing(record, owner, "committed", absolute_start_ms + at,
                TimingReference("spatial", owner, "admission"), "lifetime_commit"))
            if start is not None:
                record = replace(record, timing_evidence=_timing(record, owner, "applied", absolute_start_ms + start,
                    TimingReference("spatial", owner, "start"), "lifetime_application"))
            result[owner] = record
        elif not added and old is not None and old.removed_ms is None and owner in removed:
            result[owner] = replace(old, effect=effect, removed_ms=absolute_start_ms + at,
                timing_evidence=_timing(old, owner, "removed", absolute_start_ms + at,
                    TimingReference("spatial", owner, "admission"), "lifetime_removal"))
    # Reuse the already bound packet contacts and HP dates. An owner or actor
    # merely nearby cannot create a contact; the committed fact names both.
    for visit in visits:
        if not isinstance(visit.timeline, BoundChoreography):
            continue
        candidates = [(application.source.target, application.source.results,
            node.start_ms + application.hp_ms)
            for node in visit.timeline.nodes if isinstance(node.bound, BoundCast)
            for application in node.bound.timeline.applications
            if not node.interrupted and application.hp_ms is not None
            and isinstance(application.source.target, ActorContact)]
        candidates.extend((cue.contact, cue.results, cue.timing.hp_ms) for cue in visit.timeline.damage)
        for contact, packets, at in candidates:
            for packet in packets:
                fact = packet.fact
                if (packet.canceled or not isinstance(fact, DamageResultFact)
                        or fact.applied_damage <= 0):
                    continue
                owner = (fact.spatial_source.spatial_effect_uuid if fact.spatial_source is not None
                    else fact.source_condition_uuid)
                if owner is None:
                    continue
                record = result.get(owner)
                if (record is None or contact.actor_uuid != str(fact.target_entity_uuid)
                        or any(row.event_uuid == packet.uuid for row in record.damage_contacts)):
                    continue
                value = SpatialDamageContact(packet.uuid, contact, absolute_start_ms + visit.offset_ms + at,
                    owner in created and record.applied_ms is not None)
                result[owner] = replace(record, damage_contacts=(*record.damage_contacts, value))
    # A partial native transition retires only witnessed cells. Sight loss has
    # no matching removal fact and cannot manufacture a clear or quench.
    for visit in visits:
        prior = _observed(visit.timeline.before,data)
        for at,state in visit.timeline.states:
            current = _observed(state,data)
            for owner,admitted in removed_cells.items():
                old = result.get(owner)
                previous, following = prior.get(owner),current.get(owner)
                if old is None or previous is None or following is None:
                    continue
                removed_here = admitted.intersection(previous.positions).difference(following.positions)
                dates = dict(old.retired_cells)
                evidence = old.timing_evidence
                for cell in sorted(removed_here):
                    if cell not in dates:
                        evidence = _timing(replace(old, timing_evidence=evidence), owner, "removed",
                            absolute_start_ms+visit.offset_ms+at, TimingReference("spatial", owner, "admission"),
                            "lifetime_removal", (TimingMeasurement("cell.x", cell[0]), TimingMeasurement("cell.y", cell[1])))
                    dates.setdefault(cell,absolute_start_ms+visit.offset_ms+at)
                result[owner] = replace(old,retired_cells=tuple(sorted(dates.items())), timing_evidence=evidence)
            prior = current
    for owner,old in tuple(result.items()):
        duration = maintained_removal_duration(data,data.spatial_media[old.effect.content_ref.content_id])
        result[owner] = replace(old,retired_cells=tuple((cell,at) for cell,at in old.retired_cells
            if absolute_start_ms < at+duration))
    removals = ((row.start_ms + visit.offset_ms, row.identity) for visit in visits
                for row in visit.timeline.world_transitions if row.field == "removal")
    for at, owner in removals:
        if owner in result:
            result[owner] = replace(result[owner], removed_ms=absolute_start_ms + at,
                timing_evidence=_timing(result[owner], owner, "removed", absolute_start_ms + at,
                    TimingReference("spatial", owner, "start"), "lifetime_removal"))
    for visit in visits:
        if isinstance(visit.timeline, BoundChoreography):
            for response in visit.timeline.spatial_responses:
                record = result.get(response.owner_uuid)
                if record is not None:
                    result[response.owner_uuid] = replace(record, facings=(*record.facings,
                        (absolute_start_ms+visit.offset_ms+response.media.start_ms,response.media.facing)))
    return result
