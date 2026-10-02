"""Witnessed physical-section dates on the existing presentation frame pump."""

from dataclasses import replace
from typing import Mapping
from uuid import UUID

from game.animation_types import AnimationData
from game.choreography import BoundChoreography, MotionTimeline
from game.construction_media import ConstructionMediaLifetime, construction_duration
from game.player_facts import PlayerState


def register_construction_lifetimes(retained: Mapping[UUID, ConstructionMediaLifetime], before: PlayerState,
        data: AnimationData, *, absolute_start_ms: float, choreography: BoundChoreography | None = None,
        motion: MotionTimeline | None = None) -> dict[UUID, ConstructionMediaLifetime]:
    """Sight loss retains the clock, never a drawn foreign object or a break."""
    result = {identity: record for identity, record in retained.items()
        if record.removed_ms is None and (record.destroyed_ms is None or absolute_start_ms
            < record.destroyed_ms+construction_duration(data, data.construction_media[record.object.item.item_id], 'destruction'))}
    states = choreography.states if choreography is not None else motion.states if motion is not None else ()
    for state in (before, *(state for _, state in states)):
        for identity, obj in state.objects.items():
            if obj.item.item_id in data.construction_media and obj.item.construction_geometry is not None:
                old = result.get(identity)
                result[identity] = replace(old, object=obj) if old is not None else ConstructionMediaLifetime(obj)
    transitions = choreography.world_transitions if choreography is not None else motion.world_transitions if motion is not None else ()
    for transition in transitions:
        record = result.get(transition.identity)
        if record is None:
            continue
        at = absolute_start_ms+transition.start_ms
        if transition.field == 'creation' and record.applied_ms is None:
            result[transition.identity] = replace(record, applied_ms=at)
        elif transition.field == 'destruction' and record.destroyed_ms is None:
            result[transition.identity] = replace(record, destroyed_ms=at)
    # Witnessed parent removal retires its actually removed section objects.
    # A merely unseen object remains in remembered world state and is not retired.
    if choreography is not None:
        removed = {t.identity for t in transitions if t.field == 'removal'}
        for identity in removed:
            effect = before.senses.spatial_effects.get(identity) if before.senses is not None else None
            if effect is None:
                continue
            at = next(t.start_ms for t in transitions if t.identity == identity and t.field == 'removal')
            for section, record in tuple(result.items()):
                if (section not in choreography.after.objects and record.destroyed_ms is None
                        and record.object.item.construction_geometry in effect.construction_sections):
                    result[section] = replace(record, removed_ms=absolute_start_ms+at)
    if choreography is not None:
        for movement in choreography.movements:
            result = register_construction_lifetimes(result, movement.timeline.before, data,
                absolute_start_ms=absolute_start_ms+movement.start_ms, motion=movement.timeline)
    if motion is not None:
        for reaction in motion.reactions:
            result = register_construction_lifetimes(result, reaction.choreography.before, data,
                absolute_start_ms=absolute_start_ms+reaction.start_ms, choreography=reaction.choreography)
    return result
