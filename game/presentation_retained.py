"""Compose the six existing lifetime owners at one admitted presentation head."""

from dataclasses import dataclass, field
from typing import Literal, Mapping
from uuid import UUID
from pydantic import ConfigDict, FiniteFloat

from game.animation_types import AnimationData, Facing8, ItemAttachmentStart
from game.choreography import BoundChoreography, MotionTimeline
from game.condition_media_lifetime import ConditionMediaLifetime, register_condition_lifetimes
from game.construction_media_lifetime import register_construction_lifetimes
from game.construction_transitions import ConstructionMediaLifetime
from game.spatial_media_lifetime import SpatialMediaLifetime, register_spatial_lifetimes
from game.concentration_media import ConcentrationMediaLifetime, register_concentration_lifetimes
from game.item_attachment_lifetime import register_item_attachment_starts
from game.deposit_media import DepositStart, register_deposit_starts
from game.timing_evidence import DependencyScope, PresentationDependencies, validate_timing_evidence
from dnd.player.facts import PlayerLineage, PlayerState


@dataclass(frozen=True, slots=True)
class RetainedPresentation:
    conditions: Mapping[UUID, ConditionMediaLifetime] = field(default_factory=dict)
    spatial: Mapping[UUID, SpatialMediaLifetime] = field(default_factory=dict)
    items: Mapping[UUID, ItemAttachmentStart] = field(default_factory=dict)
    construction: Mapping[UUID, ConstructionMediaLifetime] = field(default_factory=dict)
    concentration: Mapping[UUID, ConcentrationMediaLifetime] = field(default_factory=dict)
    deposits: Mapping[UUID, DepositStart] = field(default_factory=dict)


def retain_presentation(previous: RetainedPresentation, before: PlayerState, data: AnimationData, *,
                        absolute_start_ms: float, lineage: PlayerLineage | None = None,
                        choreography: BoundChoreography | None = None, motion: MotionTimeline | None = None,
                        facings: Mapping[str, Facing8] | None = None) -> RetainedPresentation:
    """No clock policy: each original owner still registers and retires itself."""
    return RetainedPresentation(
        register_condition_lifetimes(previous.conditions, before, data, absolute_start_ms=absolute_start_ms,
            lineage=lineage, choreography=choreography, motion=motion, facings=facings or {}),
        register_spatial_lifetimes(previous.spatial, before, data, absolute_start_ms=absolute_start_ms,
            lineage=lineage, choreography=choreography, motion=motion),
        register_item_attachment_starts(previous.items, before, data, absolute_start_ms=absolute_start_ms,
            lineage=lineage, choreography=choreography, motion=motion),
        register_construction_lifetimes(previous.construction, before, data, absolute_start_ms=absolute_start_ms,
            choreography=choreography, motion=motion),
        register_concentration_lifetimes(previous.concentration, before, data, absolute_start_ms=absolute_start_ms,
            lineage=lineage, choreography=choreography, motion=motion),
        register_deposit_starts(previous.deposits, before, data, absolute_start_ms=absolute_start_ms,
            lineage=lineage, choreography=choreography, motion=motion),
    )


RetainedPhase = Literal['application', 'activation', 'consumption', 'removal', 'return', 'commit', 'cell_retirement', 'destruction']


@dataclass(frozen=True, slots=True)
class RetainedMilestone:
    __pydantic_config__ = ConfigDict(extra='forbid')

    owner_uuid: UUID
    family: Literal['condition', 'spatial', 'construction', 'concentration', 'item', 'deposit']
    phase: RetainedPhase
    at_ms: FiniteFloat
    position: tuple[int, int] | None = None


def retained_milestones(retained: RetainedPresentation) -> tuple[RetainedMilestone, ...]:
    """Absolute presentation clocks; unknown acquisition is never time zero."""
    result: list[RetainedMilestone] = []
    for identity, condition in retained.conditions.items():
        condition_clocks: tuple[tuple[RetainedPhase, float | None], ...] = (('application', condition.applied_ms), ('activation', condition.activated_ms),
                          ('consumption', condition.consumed_ms), ('removal', condition.removed_ms),
                          ('return', condition.returned_ms))
        for phase, at in condition_clocks:
            if at is not None:
                result.append(RetainedMilestone(identity, 'condition', phase, at))
    for identity, spatial in retained.spatial.items():
        spatial_clocks: tuple[tuple[RetainedPhase, float | None], ...] = (('application', spatial.applied_ms), ('commit', spatial.committed_ms),
                          ('removal', spatial.removed_ms))
        for phase, at in spatial_clocks:
            if at is not None:
                result.append(RetainedMilestone(identity, 'spatial', phase, at))
        result.extend(RetainedMilestone(identity, 'spatial', 'cell_retirement', at, position)
                      for position, at in spatial.retired_cells)
    for identity, construction in retained.construction.items():
        construction_clocks: tuple[tuple[RetainedPhase, float | None], ...] = (('application', construction.applied_ms), ('commit', construction.committed_ms),
                          ('destruction', construction.destroyed_ms), ('removal', construction.removed_ms))
        for phase, at in construction_clocks:
            if at is not None:
                result.append(RetainedMilestone(identity, 'construction', phase, at))
    for identity, concentration in retained.concentration.items():
        result.append(RetainedMilestone(identity, 'concentration', 'application', concentration.applied_ms))
        if concentration.removed_ms is not None:
            result.append(RetainedMilestone(identity, 'concentration', 'removal', concentration.removed_ms))
    result.extend(RetainedMilestone(identity, 'item', 'application', item.applied_ms)
                  for identity, item in retained.items.items() if item.applied_ms is not None)
    result.extend(RetainedMilestone(identity, 'deposit', 'application', start.at_ms) for identity, start in retained.deposits.items())
    return tuple(result)


def retained_dependencies(retained: RetainedPresentation) -> tuple[PresentationDependencies, ...]:
    """Expose original registration evidence; every retained clock is absolute."""
    result: list[PresentationDependencies] = []
    groups: tuple[tuple[DependencyScope, Mapping[UUID, ConditionMediaLifetime | SpatialMediaLifetime
        | ConstructionMediaLifetime | ConcentrationMediaLifetime | ItemAttachmentStart | DepositStart]], ...] = (
            ('condition', retained.conditions), ('spatial', retained.spatial),
            ('construction', retained.construction), ('concentration', retained.concentration),
            ('item', retained.items), ('deposit', retained.deposits))
    for scope, owners in groups:
        for identity, owner in owners.items():
            if not owner.timing_evidence:
                continue
            errors = validate_timing_evidence(owner.timing_evidence)
            if errors:
                raise ValueError(f'Invalid retained timing evidence for {identity}: {errors}')
            result.append(PresentationDependencies(identity, 0., owner.timing_evidence, scope))
    return tuple(result)
