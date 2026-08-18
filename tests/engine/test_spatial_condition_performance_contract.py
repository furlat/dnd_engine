"""Scaling contracts for direct spatial-condition ownership."""

from statistics import median
from time import perf_counter
from uuid import UUID, uuid4

from dnd.content.spatial_effect_materialization import (
    materialize_spatial_condition,
)
from dnd.content.spatial_effect_recipes import FIRE_SURFACE_RECIPE
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


def _measure_condition_cycle(side: int) -> float:
    """Measure one public activation/removal cycle for a square footprint."""
    grid = get_map()
    source_uuid = uuid4()
    parent = _root_event(source_uuid)
    footprint = _square_footprint(side)
    condition = materialize_spatial_condition(
        FIRE_SURFACE_RECIPE,
        source_uuid,
        position=(0, 0),
        faction=None,
        condition_type=SpatialCondition,
        condition_fields={"affected_positions": footprint},
    )

    started = perf_counter()
    condition.activate(parent_event=parent)
    activation_elapsed = perf_counter() - started

    assert grid.get_spatial_condition_positions(condition.uuid) == footprint
    assert grid.get_spatial_conditions_at((0, 0)) == [condition]
    assert len(EventQueue.get_spatial_handlers_at(
        (0, 0),
        EventType.SPATIAL_EFFECT_INTERACTION,
        EventPhase.EFFECT,
    )) == 1

    started = perf_counter()
    condition.deactivate(parent_event=parent)
    deactivation_elapsed = perf_counter() - started

    assert grid.get_spatial_condition_positions(condition.uuid) == set()
    assert grid.get_spatial_conditions_at((0, 0)) == []
    assert EventQueue.get_spatial_handlers_at(
        (0, 0),
        EventType.SPATIAL_EFFECT_INTERACTION,
        EventPhase.EFFECT,
    ) == []
    return activation_elapsed + deactivation_elapsed


def test_spatial_condition_time_scales_with_covered_cells() -> None:
    """A sixteen-fold footprint increase remains bounded linear work."""
    reset_engine_runtime(grid_size=(48, 48))
    elapsed_by_size = {
        side: median(_measure_condition_cycle(side) for _ in range(3))
        for side in (8, 32)
    }

    assert elapsed_by_size[32] < 3.0
    assert elapsed_by_size[32] <= max(0.05, elapsed_by_size[8] * 40)


def test_spatial_condition_time_does_not_scale_with_unused_world_area() -> None:
    """The same footprint stays local when the surrounding map is nine times larger."""
    elapsed_by_world_size: dict[int, float] = {}
    for world_size in (24, 72):
        reset_engine_runtime(grid_size=(world_size, world_size))
        elapsed_by_world_size[world_size] = median(
            _measure_condition_cycle(8) for _ in range(3)
        )

    assert elapsed_by_world_size[72] < 1.0
    assert elapsed_by_world_size[72] <= max(
        0.05,
        elapsed_by_world_size[24] * 4,
    )
