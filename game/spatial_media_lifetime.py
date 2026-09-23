"""Dates for observed maintained fields, registered once per received head."""

from dataclasses import dataclass, replace
from typing import Mapping
from uuid import UUID

from dnd.types.senses import PerceivedSpatialEffect
from dnd.types.spatial_effects import SpatialEffectChangeOperation
from game.animation_types import AnimationData
from game.choreography import BoundChoreography, MotionTimeline
from game.player_facts import PlayerLineage, PlayerState, SpatialEffectStateFact
from game.maintained_media import maintained_removal_duration


@dataclass(frozen=True, slots=True)
class SpatialMediaLifetime:
    effect: PerceivedSpatialEffect
    applied_ms: float | None = None
    removed_ms: float | None = None


def _observed(state: PlayerState, data: AnimationData) -> dict[UUID, PerceivedSpatialEffect]:
    return {owner: effect for owner, effect in state.senses.spatial_effects.items()
            if (binding := data.spatial_media.get(effect.content_ref.content_id)) is not None
            and (maintained_removal_duration(data, binding) or any(layer.applicationAssetId is not None for layer in binding.layers))
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


def _group_edges(group: BoundChoreography, data: AnimationData,
                 offset: float = 0) -> list[tuple[float, UUID, PerceivedSpatialEffect, bool]]:
    result = _edges(group.before, group.states, data, offset)
    for movement in group.movements:
        result.extend(_motion_edges(movement.timeline, data, offset + movement.start_ms))
    return result


def _motion_edges(motion: MotionTimeline, data: AnimationData,
                  offset: float = 0) -> list[tuple[float, UUID, PerceivedSpatialEffect, bool]]:
    result = _edges(motion.before, motion.states, data, offset)
    for reaction in motion.reactions:
        result.extend(_group_edges(reaction.choreography, data, offset + reaction.start_ms))
    return result


def _group_removals(group: BoundChoreography, offset: float = 0) -> list[tuple[float, UUID]]:
    return [(row.start_ms + offset, row.identity) for row in group.world_transitions if row.field == "removal"] + [
        row for movement in group.movements for row in _motion_removals(movement.timeline, offset + movement.start_ms)]


def _motion_removals(motion: MotionTimeline, offset: float = 0) -> list[tuple[float, UUID]]:
    return [(row.start_ms + offset, row.identity) for row in motion.world_transitions if row.field == "removal"] + [
        row for reaction in motion.reactions for row in _group_removals(reaction.choreography, offset + reaction.start_ms)]


def register_spatial_lifetimes(
    retained: Mapping[UUID, SpatialMediaLifetime], before: PlayerState, data: AnimationData,
    *, absolute_start_ms: float, lineage: PlayerLineage | None = None,
    choreography: BoundChoreography | None = None, motion: MotionTimeline | None = None,
) -> dict[UUID, SpatialMediaLifetime]:
    """Cold acquisition sustains; only witnessed creation/removal animates."""
    observed = _observed(before, data)
    result = {owner: record for owner, record in retained.items()
        if owner in observed or (record.removed_ms is not None and absolute_start_ms
            < record.removed_ms + maintained_removal_duration(data, data.spatial_media[record.effect.content_ref.content_id]))}
    for owner, effect in observed.items():
        result.setdefault(owner, SpatialMediaLifetime(effect))
    created, removed = set(), set()
    for node in lineage.events if lineage is not None else ():
        if node.canceled or not isinstance(node.fact, SpatialEffectStateFact):
            continue
        fact = node.fact
        if fact.operation is SpatialEffectChangeOperation.CREATED:
            created.add(fact.spatial_effect_uuid)
        elif fact.operation is SpatialEffectChangeOperation.REMOVED:
            removed.add(fact.spatial_effect_uuid)
    edges = (_motion_edges(motion, data) if motion is not None else
             _group_edges(choreography, data) if choreography is not None else [])
    for at, owner, effect, added in sorted(edges, key=lambda row: row[0]):
        old = result.get(owner)
        if added and old is None:
            result[owner] = SpatialMediaLifetime(effect, absolute_start_ms + at if owner in created else None)
        elif not added and old is not None and old.removed_ms is None and owner in removed:
            result[owner] = replace(old, effect=effect, removed_ms=absolute_start_ms + at)
    removals = (_motion_removals(motion) if motion is not None else
                _group_removals(choreography) if choreography is not None else [])
    for at, owner in removals:
        if owner in result:
            result[owner] = replace(result[owner], removed_ms=absolute_start_ms + at)
    return result
