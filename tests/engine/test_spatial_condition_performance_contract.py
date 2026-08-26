"""Scaling contracts for direct spatial-condition ownership."""

from uuid import UUID, uuid4

import pytest

from dnd.content.spatial_effect_materialization import (
    materialize_spatial_condition,
)
from dnd.content.spatial_effect_recipes import DAYLIGHT_FIELD_RECIPE, FIRE_SURFACE_RECIPE
from dnd.spatial.environmental_conditions import FireSurface
from dnd.core.events.events_registry import (
    Event,
    EventPhase,
    EventQueue,
    EventType,
)
from dnd.core.gridmap import get_map
from dnd.runtime_reset import reset_engine_runtime
from dnd.spatial.area_conditions import SpatialCondition


def _root_event(source_uuid: UUID) -> Event:
    completed = EventQueue.publish_lifecycle(Event(
        source_entity_uuid=source_uuid,
        event_type=EventType.BASE_ACTION,
        phase=EventPhase.DECLARATION,
        use_register=False,
    ))
    assert completed is not None
    return completed


def _square_footprint(side: int) -> set[tuple[int, int]]:
    return {(x, y) for x in range(side) for y in range(side)}


def _measure_condition_cycle(
    side: int,
    *,
    recipe=FIRE_SURFACE_RECIPE,
    condition_type=FireSurface,
) -> tuple[object, object, set[tuple[int, int]]]:
    """Record one public activation/removal cycle for a square footprint."""
    grid = get_map()
    source_uuid = uuid4()
    parent = _root_event(source_uuid)
    footprint = _square_footprint(side)
    condition = materialize_spatial_condition(
        recipe,
        source_uuid,
        position=(0, 0),
        faction=None,
        condition_type=condition_type,
        condition_fields={"affected_positions": footprint},
    )

    condition.activate(parent_event=parent)
    activation_work = condition.last_work_diagnostics

    assert grid.get_spatial_condition_positions(condition.uuid) == footprint
    assert grid.get_spatial_conditions_at((0, 0)) == [condition]
    if condition.spatial_handler_uuids:
        assert len(EventQueue.get_spatial_handlers_at(
            (0, 0),
            EventType.SPATIAL_EFFECT_INTERACTION,
            EventPhase.EFFECT,
        )) == 1

    condition.deactivate(parent_event=parent)
    deactivation_work = condition.last_work_diagnostics

    assert grid.get_spatial_condition_positions(condition.uuid) == set()
    assert grid.get_spatial_conditions_at((0, 0)) == []
    assert EventQueue.get_spatial_handlers_at(
        (0, 0),
        EventType.SPATIAL_EFFECT_INTERACTION,
        EventPhase.EFFECT,
    ) == []
    return activation_work, deactivation_work, footprint


@pytest.mark.parametrize(
    ("recipe", "condition_type", "expected_activation", "expected_deactivation"),
    (
        (DAYLIGHT_FIELD_RECIPE, SpatialCondition, 16, 12),
        (FIRE_SURFACE_RECIPE, FireSurface, 28, 16),
    ),
)
def test_condition_structured_work_counts_exact_owned_footprint_iterations(
    recipe,
    condition_type,
    expected_activation: int,
    expected_deactivation: int,
) -> None:
    """Both occupancy policies count their actual local footprint iterations."""
    reset_engine_runtime(grid_size=(24, 24))
    activation, deactivation, footprint = _measure_condition_cycle(
        2,
        recipe=recipe,
        condition_type=condition_type,
    )

    assert len(footprint) == 4
    assert activation.operation == "activate"
    assert deactivation.operation == "deactivate"
    assert activation.positions_visited == expected_activation
    assert deactivation.positions_visited == expected_deactivation


def test_spatial_condition_work_scales_with_covered_cells() -> None:
    """Owner-counted condition work grows with the changed footprint only."""
    reset_engine_runtime(grid_size=(48, 48))
    measurements = {
        side: _measure_condition_cycle(side)
        for side in (8, 32)
    }

    small_activation, small_deactivation, small_footprint = measurements[8]
    large_activation, large_deactivation, large_footprint = measurements[32]
    assert len(large_footprint) == len(small_footprint) * 16
    assert large_activation.operation == "activate"
    assert large_deactivation.operation == "deactivate"
    assert large_activation.positions_visited == (
        small_activation.positions_visited * 16
    )
    assert large_deactivation.positions_visited == (
        small_deactivation.positions_visited * 16
    )


def test_spatial_condition_work_does_not_scale_with_unused_world_area() -> None:
    """The same footprint has identical owner-counted work on larger maps."""
    work_by_world_size = {}
    for world_size in (24, 72):
        reset_engine_runtime(grid_size=(world_size, world_size))
        activation, deactivation, _ = _measure_condition_cycle(8)
        work_by_world_size[world_size] = (activation, deactivation)

    assert work_by_world_size[72] == work_by_world_size[24]
