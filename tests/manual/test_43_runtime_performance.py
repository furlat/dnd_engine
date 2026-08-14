"""Observable contracts retained from the retired policy performance suite."""

import gc
import weakref
from uuid import uuid4

from dnd.core.dijkstra import dijkstra
from dnd.core.geometry import circle_positions, rectangle_positions, supercover_line
from dnd.core.gridmap import get_map
from server.runtime_performance import (
    MINIMUM_FULL_COLLECTION_INTERVAL,
    latency_sensitive_gc,
)
from tests.manual.authored_encounter_support import assemble_authored_encounter
from tests.manual.server_test_client import ServerTestClient, reset_server_test_runtime


class _RequestLocalMarker:
    """Weak-referenceable marker used to detect retained request callers."""


def test_latency_sensitive_gc_restores_process_defaults() -> None:
    """Runtime tuning is scoped and restores the caller's GC thresholds."""
    previous = gc.get_threshold()

    with latency_sensitive_gc():
        active = gc.get_threshold()
        assert active[:2] == previous[:2]
        assert active[2] >= MINIMUM_FULL_COLLECTION_INTERVAL

    assert gc.get_threshold() == previous


def _post_session_with_request_local() -> weakref.ReferenceType[_RequestLocalMarker]:
    """Issue one request while retaining a marker only in the caller frame."""
    marker = _RequestLocalMarker()
    reference = weakref.ref(marker)
    response = ServerTestClient().post(
        "/session/create",
        json={"player_type": "human", "name": "Request lifetime probe"},
    )
    response.raise_for_status()
    return reference


def test_completed_post_releases_its_caller_without_cyclic_gc() -> None:
    """A completed request does not retain its caller frame."""
    reset_server_test_runtime()
    gc.collect()
    was_enabled = gc.isenabled()
    gc.disable()
    try:
        reference = _post_session_with_request_local()
        retained_without_collection = reference() is not None
    finally:
        if was_enabled:
            gc.enable()
        gc.collect()
        reset_server_test_runtime()

    assert retained_without_collection is False


def test_circle_and_rectangle_results_are_independent_values() -> None:
    """Mutating one geometry result cannot corrupt a later result."""
    first_circle = circle_positions((0, 0), radius=4)
    second_circle = circle_positions((10, 10), radius=4)
    first_rectangle = rectangle_positions((0, 0), size=5, centered=True)
    second_rectangle = rectangle_positions((10, 10), size=5, centered=True)

    first_circle.add((999, 999))
    first_rectangle.add((999, 999))

    assert (999, 999) not in second_circle
    assert (999, 999) not in second_rectangle


def test_supercover_line_results_are_independent_values() -> None:
    """Mutating a returned ray cannot corrupt the next equal ray."""
    first = supercover_line((0, 0), (8, 5))
    second = supercover_line((0, 0), (8, 5))
    first.append((999, 999))

    assert (999, 999) not in second


def test_translated_supercover_rays_preserve_relative_geometry() -> None:
    """Equal ray deltas produce equal relative traversal cells."""
    first = supercover_line((0, 0), (8, 5))
    second = supercover_line((20, 30), (28, 35))

    assert first == [(x - 20, y - 30) for x, y in second]


def test_grid_path_results_are_isolated_between_callers() -> None:
    """Mutating one returned path cannot corrupt the next query."""
    arena = assemble_authored_encounter("srd_low_cr_patrol")
    actor = arena.hero
    grid = get_map()

    first_distances, first_paths = grid.compute_paths(
        actor.position,
        max_distance=20,
        requesting_entity_uuid=actor.uuid,
        subjective=True,
    )
    second_distances, second_paths = grid.compute_paths(
        actor.position,
        max_distance=20,
        requesting_entity_uuid=actor.uuid,
        subjective=True,
    )

    assert second_distances == first_distances
    assert second_paths == first_paths
    sample_destination = next(iter(second_paths))
    second_paths[sample_destination].append((999, 999))
    _, third_paths = grid.compute_paths(
        actor.position,
        max_distance=20,
        requesting_entity_uuid=actor.uuid,
        subjective=True,
    )
    assert third_paths[sample_destination] == first_paths[sample_destination]


def test_dijkstra_preserves_directional_costed_paths() -> None:
    """The pathfinder respects bounds, costs, obstacles, and directed edges."""
    distances, paths = dijkstra(
        (0, 0),
        lambda x, y: (x, y) != (1, 1),
        width=4,
        height=3,
        diagonal=True,
        max_distance=4,
        cost_func=lambda x, y: 2 if (x, y) == (2, 0) else 1,
        can_enter=lambda source, target: (source, target) != ((1, 0), (2, 0)),
    )

    assert distances[(3, 0)] == 3
    assert paths[(3, 0)][0] == (0, 0)
    assert paths[(3, 0)][-1] == (3, 0)
    assert (1, 1) not in paths
