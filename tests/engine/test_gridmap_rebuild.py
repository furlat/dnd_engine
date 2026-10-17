"""Rebuilding GridMap state never repeats old revisions or drops live light."""

from dnd.core.base_block import LightLevel
from dnd.core.gridmap import get_map
from dnd.runtime_reset import reset_engine_runtime


def _revisions(grid) -> dict[str, int]:
    return {"optical": grid.optical_revision, "occupancy": grid.occupancy_revision,
        "movement": grid.movement_revision, "connector": grid.connector_revision,
        "illumination": grid.illumination_revision, "propagation": grid.propagation_revision}


def test_clear_never_moves_a_revision_backwards() -> None:
    """Caches outside GridMap key on its revisions, so clear() must not repeat old values."""
    reset_engine_runtime(grid_size=(1, 1))
    grid = get_map()
    grid.create_rectangle(0, 0, 5, 1, walking_cost=1)
    grid.add_light_source((0, 0), bright_radius_feet=10, dim_radius_feet=0)
    before = _revisions(grid)

    grid.clear()
    after = _revisions(grid)
    assert {name: after[name] > before[name] for name in before} == {name: True for name in before}


def test_rebuilt_rectangle_keeps_the_light_of_existing_sources() -> None:
    """Replacing lit tiles keeps the illumination of a light source that still exists."""
    reset_engine_runtime(grid_size=(1, 1))
    grid = get_map()
    grid.clear()
    grid.create_rectangle(0, 0, 5, 1, default_light=LightLevel.DARKNESS)
    grid.add_light_source((0, 0), bright_radius_feet=10, dim_radius_feet=0)
    lit = grid.get_tile(1, 0)
    assert lit is not None and lit.resolved_light_level is LightLevel.BRIGHT_LIGHT

    grid.create_rectangle(1, 0, 1, 1, default_light=LightLevel.DARKNESS)
    rebuilt = grid.get_tile(1, 0)
    assert rebuilt is not None and rebuilt is not lit
    assert rebuilt.resolved_light_level is LightLevel.BRIGHT_LIGHT
