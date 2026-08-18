"""Algorithmic call-count gates for Unit 4 elevation owners."""

from time import perf_counter

import pytest

from dnd.types.world import MovementMode
from dnd.core.gridmap import GridMap, get_map
from dnd.core.world_edges import ElevationSurfaceKind
from dnd.core.traversal_connectors import (
    ConnectorProvocationPolicy,
    TraversalConnectorDefinition,
    TraversalConnectorKind,
)
from dnd.actions.standard import (
    TraverseConnector,
)
from dnd.entities.entity import Entity
from dnd.runtime_reset import reset_engine_runtime
from dnd.content.scenarios.battlefield_builders import build_battlefield, get_battlefield
from tests.engine.test_combat_actions import reset_core_action_state, strong_entity


def test_battlefield_composition_work_tracks_authored_elevation_cells(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Flat and elevated builds do no map-wide elevation precomputation."""
    original = GridMap.set_tile_elevation
    elevation_calls: list[tuple[int, int]] = []

    def track(
        grid: GridMap,
        position: tuple[int, int],
        **kwargs,
    ):
        elevation_calls.append(position)
        return original(grid, position, **kwargs)

    monkeypatch.setattr(GridMap, "set_tile_elevation", track)
    flat = get_battlefield("battlefield.open_floor_bright")
    reset_engine_runtime(grid_size=(flat.width, flat.height))
    flat_started = perf_counter()
    build_battlefield(flat.battlefield_id)
    flat_elapsed = perf_counter() - flat_started
    assert elevation_calls == []

    elevated = get_battlefield("battlefield.elevation_proving_ground")
    reset_engine_runtime(grid_size=(elevated.width, elevated.height))
    elevated_started = perf_counter()
    build_battlefield(elevated.battlefield_id)
    elevated_elapsed = perf_counter() - elevated_started

    assert elevation_calls == [
        cell.position for cell in elevated.preview.elevation_cells
    ]
    assert flat_elapsed >= 0
    assert elevated_elapsed >= 0


def test_cold_and_warm_action_discovery_have_bounded_pathfinder_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A warm query never adds a map- or target-proportional path rebuild."""
    reset_core_action_state()
    actor = strong_entity("Discovery", (0, 0), "heroes")
    Entity.update_all_entities_senses(max_distance=20)
    grid = get_map()
    original = grid.compute_paths
    calls: list[MovementMode] = []

    def track(*args, **kwargs):
        calls.append(kwargs.get("movement_mode", MovementMode.WALKING))
        return original(*args, **kwargs)

    monkeypatch.setattr(grid, "compute_paths", track)
    actor.senses._paths_dirty = True
    cold_started = perf_counter()
    actor.get_available_actions()
    cold_elapsed = perf_counter() - cold_started
    cold_calls = len(calls)

    warm_started = perf_counter()
    actor.get_available_actions()
    warm_elapsed = perf_counter() - warm_started
    warm_calls = len(calls) - cold_calls

    assert cold_calls <= 2
    assert warm_calls <= 1
    assert cold_elapsed >= 0
    assert warm_elapsed >= 0


@pytest.mark.parametrize("elevated", (False, True))
def test_path_computation_edge_queries_are_linear_in_local_map_edges(
    monkeypatch: pytest.MonkeyPatch,
    elevated: bool,
) -> None:
    """Flat/elevated Dijkstra consults directed local edges, never all pairs."""
    reset_core_action_state()
    actor = strong_entity("Pathfinder", (0, 0), "heroes")
    grid = get_map()
    if elevated:
        grid.set_tile_elevation(
            (1, 0),
            height=2,
            surface_kind=ElevationSurfaceKind.ORDINARY,
            slope_axis=None,
        )
    original = grid.movement_edge_cost_units
    edge_calls: list[
        tuple[tuple[int, int], tuple[int, int]]
    ] = []

    def track(from_position, to_position, movement_mode, **kwargs):
        edge_calls.append((from_position, to_position))
        return original(
            from_position,
            to_position,
            movement_mode,
            **kwargs,
        )

    monkeypatch.setattr(grid, "movement_edge_cost_units", track)
    started = perf_counter()
    grid.compute_paths(
        actor.position,
        requesting_entity_uuid=actor.uuid,
        movement_mode=(
            MovementMode.FLYING if elevated else MovementMode.WALKING
        ),
        max_distance=6,
    )
    elapsed = perf_counter() - started

    assert len(edge_calls) <= 8 * len(grid.get_all_tiles())
    assert len(set(edge_calls)) <= len(edge_calls)
    assert elapsed >= 0


def test_connector_discovery_is_one_endpoint_lookup_at_and_away_from_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reset_core_action_state()
    actor = strong_entity("Connector Discovery", (0, 0), "heroes")
    grid = get_map()
    grid.set_tile_elevation(
        (1, 0),
        height=1,
        surface_kind=ElevationSurfaceKind.ORDINARY,
        slope_axis=None,
    )
    connector = grid.register_connector(TraversalConnectorDefinition(
        authored_id="connector.performance.ladder",
        kind=TraversalConnectorKind.LADDER,
        presentation_key="traversal.ladder",
        endpoint_positions=((0, 0), (1, 0)),
        movement_cost_feet=10,
        action_cost_type=None,
        action_cost_amount=0,
        bidirectional=True,
        enabled=True,
        provocation_policy=ConnectorProvocationPolicy.PROVOKES_SOURCE_EXIT,
    ))
    assert connector is not None
    template = TraverseConnector(source_entity_uuid=actor.uuid)
    original = grid.get_connectors_at
    endpoint_queries: list[tuple[int, int]] = []

    def track(position: tuple[int, int]):
        endpoint_queries.append(position)
        return original(position)

    monkeypatch.setattr(grid, "get_connectors_at", track)
    monkeypatch.setattr(
        grid,
        "get_all_connectors",
        lambda: (_ for _ in ()).throw(AssertionError("global connector scan")),
    )

    assert len(template.get_discovery_variants(actor)) == 1
    Entity.update_entity_position(actor, (0, 1))
    assert template.get_discovery_variants(actor) == []
    assert endpoint_queries == [(0, 0), (0, 1)]
