"""Algorithmic call-count gates for Unit 4 elevation owners."""

import pytest

from dnd.types.world import MovementMode
from dnd.core.gridmap import get_map
from dnd.core.world_edges import ElevationSurfaceKind
from dnd.entities.entity import Entity
from dnd.runtime_reset import reset_engine_runtime
from dnd.content.scenarios.battlefield_builders import build_battlefield, get_battlefield
from tests.engine.test_combat_actions import reset_core_action_state, strong_entity


def test_final_tiles_preserve_authored_elevation_and_identity() -> None:
    """Authored elevation is present on each final Tile at first publication."""
    flat = get_battlefield("battlefield.open_floor_bright")
    reset_engine_runtime()
    build_battlefield(flat.battlefield_id)
    flat_tiles = get_map().get_all_tiles()
    assert len(flat_tiles) == flat.width * flat.height
    assert len({tile.uuid for tile in flat_tiles.values()}) == len(flat_tiles)

    elevated = get_battlefield("battlefield.elevation_proving_ground")
    reset_engine_runtime()
    build_battlefield(elevated.battlefield_id)

    grid = get_map()
    assert len(grid.get_all_tiles()) == elevated.width * elevated.height
    assert len({tile.uuid for tile in grid.get_all_tiles().values()}) == (
        elevated.width * elevated.height
    )
    assert all(
        (
            grid.get_tile(*cell.position).height,
            grid.get_tile(*cell.position).elevation_surface_kind,
            grid.get_tile(*cell.position).slope_axis,
        ) == (cell.elevation_steps, cell.surface_kind, cell.slope_axis)
        for cell in elevated.layout.elevation
    )


def test_warm_action_discovery_preserves_navigation_projection() -> None:
    """Repeated discovery preserves the already materialized public projection."""
    reset_core_action_state()
    actor = strong_entity("Discovery", (0, 0), "heroes")
    Entity.materialize_all_navigation(max_distance=20)
    actor.get_available_actions()
    cold_revision = actor.senses.path_revision
    cold_paths = dict(actor.senses.paths)

    actor.get_available_actions()
    assert actor.senses.path_revision == cold_revision
    assert dict(actor.senses.paths) == cold_paths


@pytest.mark.parametrize("elevated", (False, True))
def test_path_computation_edge_queries_are_linear_in_local_map_edges(
    elevated: bool,
) -> None:
    """Flat/elevated pathfinding reports positive work bounded by local edges."""
    observations = []
    for size in (20, 80):
        reset_engine_runtime(grid_size=(size, size))
        grid = get_map()
        start = (size // 2, size // 2)
        if elevated:
            grid.set_tile_elevation(
                (start[0] + 1, start[1]),
                height=2,
                surface_kind=ElevationSurfaceKind.ORDINARY,
                slope_axis=None,
            )
        assert grid.width == size
        assert grid.height == size
        distances, paths = grid.compute_paths(
            start,
            movement_mode=(
                MovementMode.FLYING if elevated else MovementMode.WALKING
            ),
            max_distance=6,
        )

        diagnostics = grid.last_operation_diagnostics
        assert diagnostics.operation == "compute_paths"
        assert diagnostics.path_edge_queries > 0
        assert diagnostics.path_edge_queries <= 8 * len(distances)
        assert set(distances) == set(paths)
        relative_distances = {
            (position[0] - start[0], position[1] - start[1]): distance
            for position, distance in distances.items()
        }
        observations.append((relative_distances, diagnostics.path_edge_queries))
        assert all(
            all(
                abs(next_position[0] - current_position[0]) <= 1
                and abs(next_position[1] - current_position[1]) <= 1
                for current_position, next_position in zip(path, path[1:])
            )
            for path in paths.values()
        )

    assert observations[0] == observations[1]
