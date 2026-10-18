"""The one shared reducer of recorded sensory deltas into observer snapshots.

Native events and public player facts expose the same after-values
(`dnd.types.senses.SensoryDelta`); their cell sets are packed values, folded
with the array operations of `dnd.core.cells`.
"""

from collections.abc import Sequence
from dataclasses import dataclass, replace
from uuid import UUID

from dnd.core.cells import mask_union, update_cells
from dnd.types.cells import EMPTY_CELLS, EMPTY_VALUES
from dnd.types.senses import SenseMode, SenseModesKey, SensesSnapshot, SensoryDelta


@dataclass(frozen=True, slots=True)
class PreparedSensoryDelta:
    """Validated delta values; preparation never mutates a current fold."""

    sense_modes: tuple[SenseMode, ...] | None
    sense_modes_key: SenseModesKey | None


def prepare_sensory_delta(expected_observer_uuid: UUID, previous: SensesSnapshot | None,
                          event: SensoryDelta) -> PreparedSensoryDelta:
    if event.observer_uuid != expected_observer_uuid:
        raise ValueError("sensory update belongs to a different observer")
    if event.initial:
        if event.passive_perception is None or event.visual_access is None:
            raise ValueError("initial sensory update requires capability after-values")
    elif previous is None:
        raise ValueError("sensory delta requires a previously recorded initial state")
    modes, modes_key = None, None
    if event.sense_modes_changed and event.sense_modes is not None:
        modes = tuple(mode.model_copy(deep=True) for mode in event.sense_modes)
        modes_key = sense_modes_key(modes)
    return PreparedSensoryDelta(modes, modes_key)


def sense_modes_key(modes: Sequence[SenseMode]) -> SenseModesKey:
    """Sense modes as one comparable value, the same in every process: each mode's type and range, sorted."""
    return tuple(sorted((mode.sense_type.value, mode.range_feet) for mode in modes))


def apply_current_senses(previous: SensesSnapshot | None, event: SensoryDelta,
                         prepared: PreparedSensoryDelta) -> SensesSnapshot:
    """Advance containers owned exclusively by a current-state fold.

    Retained public snapshots must use reduce_senses_snapshot instead.
    """
    if event.initial:
        previous = SensesSnapshot(
            position=event.observer_position, visible=EMPTY_CELLS, seen=EMPTY_CELLS,
            entities={}, objects={}, effective_light_levels=EMPTY_VALUES, paths_dirty=False,
            passive_perception=event.passive_perception,
            sense_modes_key=sense_modes_key(()), sense_modes=(), visual_access=event.visual_access)
    assert previous is not None
    visible, light, hazards = update_cells(previous.visible, previous.effective_light_levels, previous.hazardous_cells,
        event.visible_cells_removed, event.visible_cells_added, event.effective_light_levels_changed,
        event.hazardous_cells_changed)
    for identity in event.entity_contacts_removed:
        previous.entities.pop(identity, None)
    previous.entities.update(event.entity_contacts_changed)
    for identity in event.object_contacts_removed:
        previous.objects.pop(identity, None)
    previous.objects.update(event.object_contacts_changed)
    for identity in event.spatial_effects_removed:
        previous.spatial_effects.pop(identity, None)
    previous.spatial_effects.update(event.spatial_effects_changed)
    for identity, revision in event.light_sources_removed.items():
        previous.light_sources.pop(identity, None)
        previous.light_source_removals[identity] = revision
    for identity, source in event.light_sources_changed.items():
        previous.light_sources[identity] = source
        previous.light_source_removals.pop(identity, None)
    return replace(previous, visible=visible, seen=mask_union(previous.seen, event.seen_cells_added),
        effective_light_levels=light, hazardous_cells=hazards,
        position=event.observer_position if event.observer_position_changed else previous.position,
        paths_dirty=previous.paths_dirty or event.paths_dirty,
        passive_perception=(event.passive_perception if event.passive_perception_changed
            and event.passive_perception is not None else previous.passive_perception),
        sense_modes=prepared.sense_modes if prepared.sense_modes is not None else previous.sense_modes,
        sense_modes_key=(prepared.sense_modes_key if prepared.sense_modes_key is not None
            else previous.sense_modes_key),
        visual_access=(event.visual_access if event.visual_access_changed
            and event.visual_access is not None else previous.visual_access))


def copy_senses_snapshot(value: SensesSnapshot) -> SensesSnapshot:
    """Detach mutable member containers at a retained/public boundary; packed cell sets are values."""
    return replace(value, entities=dict(value.entities), objects=dict(value.objects),
        spatial_effects=dict(value.spatial_effects), light_sources=dict(value.light_sources),
        light_source_removals=dict(value.light_source_removals),
        sense_modes=tuple(mode.model_copy(deep=True) for mode in value.sense_modes))


def reduce_senses_snapshot(expected_observer_uuid: UUID, previous: SensesSnapshot | None,
                           event: SensoryDelta) -> SensesSnapshot:
    """Reduce recorded observer after-values into a fresh sensory snapshot."""
    prepared = prepare_sensory_delta(expected_observer_uuid, previous, event)
    current = copy_senses_snapshot(previous) if previous is not None and not event.initial else None
    return apply_current_senses(current, event, prepared)


__all__ = ["PreparedSensoryDelta", "prepare_sensory_delta", "apply_current_senses", "copy_senses_snapshot",
           "reduce_senses_snapshot", "sense_modes_key"]
