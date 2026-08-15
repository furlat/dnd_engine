"""Pure elevation distance rules introduced by Unit 4."""

import pytest

from dnd.types.creatures import Size
from dnd.core.world_edges import ElevationSurfaceKind
from dnd.core.gridmap import get_map
from dnd.core.elevation import (
    creature_volume_distance_feet,
    support_distance_feet,
    tactical_vertical_extent_feet,
)
from dnd.entity import Entity
from tests.engine.test_combat_actions import reset_core_action_state, strong_entity


@pytest.mark.parametrize(
    ("first", "second", "expected"),
    [
        ((0, 0), (1, 1), 5),
        ((0, 0), (4, 0), 20),
        ((0, 0), (4, 3), 25),
    ],
)
def test_support_distance_preserves_the_flat_planar_metric(
    first: tuple[int, int],
    second: tuple[int, int],
    expected: int,
) -> None:
    assert support_distance_feet(first, 0, second, 0) == expected


def test_support_distance_uses_the_hybrid_vertical_rule_symmetrically() -> None:
    assert support_distance_feet((0, 0), 0, (4, 0), 15) == 20
    assert support_distance_feet((4, 0), 15, (0, 0), 0) == 20
    assert support_distance_feet((0, 0), -10, (0, 0), 15) == 25


def test_creature_volume_distance_uses_closed_tactical_intervals() -> None:
    assert tactical_vertical_extent_feet(Size.TINY) == 2.5
    assert tactical_vertical_extent_feet(Size.GARGANTUAN) == 20
    assert creature_volume_distance_feet(
        (0, 0),
        0,
        Size.MEDIUM,
        (1, 0),
        5,
        Size.MEDIUM,
    ) == 5
    assert creature_volume_distance_feet(
        (0, 0),
        0,
        Size.MEDIUM,
        (0, 0),
        15,
        Size.SMALL,
    ) == 10


def test_elevation_distance_rejects_bool_coordinates_and_elevations() -> None:
    with pytest.raises(TypeError):
        support_distance_feet((True, 0), 0, (0, 0), 0)
    with pytest.raises(TypeError):
        support_distance_feet((0, 0), False, (0, 0), 0)


def test_entity_distance_and_threat_use_creature_volume_not_support_points() -> None:
    reset_core_action_state()
    source = strong_entity("Source", (0, 0), "heroes")
    target = strong_entity("Target", (1, 0), "enemies")
    grid = get_map()
    grid.set_tile_elevation(
        (1, 0),
        height=2,
        surface_kind=ElevationSurfaceKind.ORDINARY,
        slope_axis=None,
    )
    Entity.update_all_entities_senses(max_distance=20)

    assert source.distance_to_position(target.position) == 10
    assert source.distance_to_entity(target) == 5
    assert source.threatens_entity_at(target)

    grid.set_tile_elevation(
        (1, 0),
        height=4,
        surface_kind=ElevationSurfaceKind.ORDINARY,
        slope_axis=None,
    )
    assert source.distance_to_position(target.position) == 20
    assert source.distance_to_entity(target) == 15
    assert not source.threatens_entity_at(target)


def test_entity_action_discovery_reports_creature_volume_distance() -> None:
    reset_core_action_state()
    source = strong_entity("Source", (0, 0), "heroes")
    target = strong_entity("Target", (1, 0), "enemies")
    get_map().set_tile_elevation(
        target.position,
        height=2,
        surface_kind=ElevationSurfaceKind.ORDINARY,
        slope_axis=None,
    )
    Entity.update_all_entities_senses(max_distance=20)

    shove = next(
        action
        for action in source.get_available_actions(legal_only=True).entity_actions
        if action.template_name == "Shove"
    )
    discovered = next(
        candidate
        for candidate in shove.valid_targets
        if candidate.target_uuid == target.uuid
    )

    assert source.distance_to_position(target.position) == 10
    assert source.distance_to_entity(target) == 5
    assert discovered.distance == 5


def test_senses_support_distance_has_no_missing_tile_fallback() -> None:
    reset_core_action_state()
    source = strong_entity("Source", (0, 0), "heroes")
    grid = get_map()
    grid.remove_tile(1, 0)

    with pytest.raises(ValueError, match="both support tiles"):
        source.senses.get_feet_distance((1, 0))
    with pytest.raises(ValueError, match="support tile"):
        source.distance_to_position((1, 0))
