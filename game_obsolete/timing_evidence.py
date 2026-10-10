"""Passive evidence of existing binder calculations, never a second scheduler."""

from dataclasses import dataclass, replace
from math import isclose, isfinite
from typing import Annotated, Literal
from uuid import UUID

from pydantic import ConfigDict, Field, FiniteFloat


TimingReason = Literal['formation', 'clearance', 'world_floor', 'spatial_cause',
                    'observed_source', 'sensory_owner', 'observation_floor',
                    'body_release', 'launch', 'contact', 'damage_start', 'hp_callback', 'hp_reentry',
                    'area_reach', 'staged_area_contact', 'staged_area_shift',
                    'body_effect', 'body_end', 'body_join', 'body_complete', 'equipment_commit', 'equipment_complete',
                    'subtree_join', 'reaction_alignment', 'interruption', 'child_start', 'child_effect',
                    'portal_open', 'portal_fall', 'portal_exit', 'portal_arrival', 'portal_settled',
                    'displacement_start', 'displacement_travel', 'displacement_complete', 'shove_contact',
                    'lifetime_application', 'lifetime_removal', 'lifetime_activation', 'lifetime_return',
                    'lifetime_commit', 'lifetime_destruction', 'lifetime_inheritance', 'lifetime_retention', 'condition_transition', 'motion_span', 'motion_dwell', 'motion_recovery']
DependencyScope = Literal['choreography', 'cast', 'attack', 'body', 'equipment', 'portal', 'displacement', 'shove',
                          'condition', 'spatial', 'construction', 'concentration', 'item', 'deposit', 'condition_transition', 'motion', 'damage', 'lifecycle']
TimingOperation = Literal['offset', 'maximum', 'minimum', 'fraction']


TimingAnchor = Literal['start', 'formation', 'clearance', 'admission', 'commit',
                       'release', 'launch', 'contact', 'prepare_end', 'damage_start', 'hp',
                       'effect', 'body_end', 'join', 'recovery', 'complete', 'disappear', 'exit_open', 'arrival', 'settled', 'cutoff',
                       'applied', 'removed', 'activated', 'returned', 'committed', 'destroyed', 'last_present', 'opening', 'fade_deadline', 'group_origin', 'prior_hp_floor']


@dataclass(frozen=True, slots=True)
class TimingReference:
    __pydantic_config__ = ConfigDict(extra='forbid')
    kind: Literal['event', 'spatial', 'object', 'observation', 'attack', 'condition', 'concentration', 'item_effect', 'deposit', 'lineage']
    identity: UUID
    anchor: TimingAnchor
    application_id: str | None = None


@dataclass(frozen=True, slots=True)
class CompiledTimingReference:
    """Detached cast/equipment inputs deliberately accept string identities."""
    __pydantic_config__ = ConfigDict(extra='forbid')
    kind: Literal['cast', 'equipment']
    identity: str
    anchor: TimingAnchor
    application_id: str | None = None


TimingTarget = Annotated[TimingReference | CompiledTimingReference, Field(discriminator='kind')]


@dataclass(frozen=True, slots=True)
class TimingMeasurement:
    __pydantic_config__ = ConfigDict(extra='forbid')
    field: str
    value: FiniteFloat


@dataclass(frozen=True, slots=True)
class TimingOperand:
    __pydantic_config__ = ConfigDict(extra='forbid')
    reference: TimingTarget
    at_ms: FiniteFloat
    producer_index: int | None = None
    offset_ms: FiniteFloat = 0.
    authored_field: str | None = None
    contributor_object_uuid: UUID | None = None
    contributor_event_uuid: UUID | None = None
    measurements: tuple[TimingMeasurement, ...] = ()
    offset_producers: tuple[int, int] | None = None


@dataclass(frozen=True, slots=True)
class TimingEvidence:
    __pydantic_config__ = ConfigDict(extra='forbid')
    # Index is local to this bound owner and identifies a calculation stage.
    index: int
    target: TimingTarget
    reason: TimingReason
    operation: TimingOperation
    inputs: tuple[TimingOperand, ...]
    at_ms: FiniteFloat
    fraction: FiniteFloat | None = None


def validate_timing_evidence(rows: tuple[TimingEvidence, ...]) -> tuple[str, ...]:
    """Validate recorded arithmetic/references; never calculate playback dates.

    Inputs without producer_index are measured or already-bound external anchors.
    This validates only this explicitly annotated subset of the binder DAG.
    """
    errors: list[str] = []
    producers: dict[int, TimingEvidence] = {}
    for row in rows:
        label = f'timing stage {row.index}'
        if row.index in producers:
            errors.append(f'{label}: duplicate producer')
        if not row.inputs or row.operation == 'offset' and len(row.inputs) != 1:
            errors.append(f'{label}: invalid operand count')
        if row.operation == 'fraction' and (len(row.inputs) != 2 or row.fraction is None):
            errors.append(f'{label}: fraction requires two endpoints and a fraction')
        if row.operation != 'fraction' and row.fraction is not None:
            errors.append(f'{label}: unexpected fraction')
        values = [source.at_ms + source.offset_ms for source in row.inputs]
        if not all(isfinite(value) for value in (row.at_ms, *values,
                *(source.at_ms for source in row.inputs), *(source.offset_ms for source in row.inputs),
                *(measurement.value for source in row.inputs for measurement in source.measurements),
                *((row.fraction,) if row.fraction is not None else ()))):
            errors.append(f'{label}: nonfinite clock')
        elif values:
            expected = (values[0] + (values[1] - values[0]) * row.fraction
                if row.operation == 'fraction' and len(values) == 2 and row.fraction is not None
                else min(values) if row.operation == 'minimum' else max(values))
            if not isclose(row.at_ms, expected, abs_tol=1e-7, rel_tol=1e-12):
                errors.append(f'{label}: recorded result disagrees with inputs')
        for source in row.inputs:
            if source.offset_producers is not None:
                later_index, earlier_index = source.offset_producers
                later, earlier = producers.get(later_index), producers.get(earlier_index)
                if later is None or earlier is None or max(later_index, earlier_index) >= row.index:
                    errors.append(f'{label}: missing, forward or cyclic offset producer')
                elif not isclose(source.offset_ms, later.at_ms - earlier.at_ms, abs_tol=1e-7, rel_tol=1e-12):
                    errors.append(f'{label}: offset disagrees with producer difference')
            if source.producer_index is None:
                continue
            producer = producers.get(source.producer_index)
            if producer is None or source.producer_index >= row.index:
                errors.append(f'{label}: missing, forward or cyclic producer {source.producer_index}')
            elif producer.target != source.reference or not isclose(producer.at_ms, source.at_ms,
                    abs_tol=1e-7, rel_tol=1e-12):
                errors.append(f'{label}: producer reference/value mismatch')
        producers[row.index] = row
    return tuple(errors)


def record_timing(evidence: list[TimingEvidence], target: TimingTarget,
                  reason: TimingReason, inputs: tuple[TimingOperand, ...], at_ms: float,
                  operation: TimingOperation = 'offset', *, fraction: float | None = None) -> TimingOperand:
    """Append an already-computed equation and return its passive producer ref."""
    index = len(evidence)
    evidence.append(TimingEvidence(index, target, reason, operation, inputs, at_ms, fraction))
    return TimingOperand(target, at_ms, index)


@dataclass(frozen=True, slots=True)
class PresentationDependencies:
    """One existing owner, with producer indices local to its evidence tuple."""
    __pydantic_config__ = ConfigDict(extra='forbid')
    owner_uuid: UUID
    offset_ms: FiniteFloat
    evidence: tuple[TimingEvidence, ...]
    scope: DependencyScope = 'choreography'
    admission_uuid: UUID | None = None



def translate_timing_evidence(rows: tuple[TimingEvidence, ...], offset_ms: float) -> tuple[TimingEvidence, ...]:
    """Translate an existing owner's clocks without changing durations or edges."""
    return tuple(replace(row, at_ms=row.at_ms + offset_ms,
        inputs=tuple(replace(source, at_ms=source.at_ms + offset_ms) for source in row.inputs))
        for row in rows)
