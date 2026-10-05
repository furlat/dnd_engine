"""Creation cues require a witnessed construction owner, not mere acquisition."""

from dataclasses import dataclass
from math import hypot, isclose
from typing import Mapping
from uuid import UUID
from game.timing_evidence import TimingEvidence
from dnd.types.spatial_effects import SpatialEffectChangeOperation
from dnd.types.event_facts import SpatialChangeType
from game.animation_types import AnimationData, ConstructionMediaBinding
from dnd.core.presentation_geometry import WallAssemblyPresentationGeometry, WallDome, WallSegment
from game.player_facts import PlayerObject, PlayerLineage, PlayerState, SpatialEffectStateFact, SpatialFact
from game.world_animation import WorldTransition


@dataclass(frozen=True, slots=True)
class ConstructionMediaLifetime:
    object: PlayerObject
    applied_ms: float | None = None
    destroyed_ms: float | None = None
    removed_ms: float | None = None
    collapse_contacts: tuple[tuple[float,float,float], ...] = ()
    membrane_impulses: tuple[tuple[float, tuple[float,float,float]], ...] = ()
    timing_evidence: tuple[TimingEvidence, ...] = ()
    committed_ms: float | None = None


def construction_duration(data: AnimationData, binding: ConstructionMediaBinding, phase: str) -> float:
    source_duration = ({'application': binding.surface.applicationMs, 'destruction': binding.surface.destructionMs,
        'removal': binding.surface.removalMs}[phase] if binding.surface is not None else 0.)
    if phase == 'removal':
        return max(binding.removalDurationMs or 0., source_duration)
    banks = (v.application if phase == 'application' else v.destruction
        for direction in binding.directions for v in direction.variants)
    durations = []
    for pair in banks:
        for identity in pair:
            asset = data.projectile_assets[identity]
            selected = asset.phases.impact
            assert selected is not None
            durations.append(selected.frames*1000/(selected.fps or asset.fps))
    return max((*durations, source_duration))


def construction_media_limitation(obj: PlayerObject, binding: ConstructionMediaBinding) -> str | None:
    geometry = obj.item.construction_geometry
    if binding.surface is not None and isinstance(geometry, WallAssemblyPresentationGeometry):
        if isinstance(geometry.path, WallDome):
            return None if geometry.path.radius_feet in (5, 10) else 'Construction radius has no original operator'
        if not binding.surface.domeOnly and isinstance(geometry.path, WallSegment):
            return None
    if not isinstance(geometry, WallAssemblyPresentationGeometry) or not isinstance(geometry.path, WallSegment):
        return 'Construction geometry has no delivered section profile'
    if not isclose(geometry.height_feet, binding.heightFeet):
        return 'Construction height has no matched source bank'
    path = geometry.path
    dx, dy = path.end[0]-path.start[0], path.end[1]-path.start[1]
    length = hypot(dx, dy)*5
    if not isclose(length/binding.lengthFeet, round(length/binding.lengthFeet)):
        return 'Construction length is not an exact source-module multiple'
    if not any(dx*x+dy*y > 0 and abs(dx*y-dy*x) < 1e-8 for x, y in (d.tangent for d in binding.directions)):
        return 'Construction heading has no native source bank'
    return None


def construction_creation_transitions(before: PlayerState, states: list[tuple[float, PlayerState]],
        lineage: PlayerLineage, data: AnimationData, *,
        formation_starts: Mapping[UUID, float] | None = None) -> tuple[WorldTransition, ...]:
    created = {node.fact.spatial_effect_uuid for node in lineage.events if not node.canceled
        and isinstance(node.fact, SpatialEffectStateFact)
        and node.fact.operation is SpatialEffectChangeOperation.CREATED}
    sections = {node.fact.object_uuid for node in lineage.events if not node.canceled
        and isinstance(node.fact, SpatialFact) and node.fact.object_uuid is not None
        and node.fact.change_type is SpatialChangeType.OBJECT_PLACED}
    known = set(before.objects)
    result = []
    for at, state in states:
        owners = created & state.senses.spatial_effects.keys() if state.senses is not None else set()
        for identity, obj in state.objects.items():
            binding = data.construction_media.get(obj.item.item_id)
            if (identity in known or binding is None or construction_media_limitation(obj, binding) is not None
                    or identity not in sections and obj.item.construction_owner_uuid not in owners):
                continue
            owner = obj.item.construction_owner_uuid
            starts = formation_starts or {}
            start = starts.get(identity, starts.get(owner, at) if owner is not None else at)
            result.append(WorldTransition(identity, 'creation', None, None, start,
                duration_ms=construction_duration(data, binding, 'application')))
            known.add(identity)
    return tuple(result)
