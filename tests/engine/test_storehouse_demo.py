"""A playable room is reachable through its usable door, not through walls."""

import pytest

from dnd.content.items.environment_item_builders import build_directional_wall
from dnd.core.content.encounters import EncounterCompatibilityCode
from dnd.core.events import EventQueue
from dnd.core.gridmap import get_map
from dnd.items.environment import DirectionalDoor
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import build_battlefield
from dnd.scenarios.encounter_catalog import encounter_recipe
from dnd.scenarios.encounter_compatibility import (
    check_built_encounter_compatibility, check_encounter_compatibility,
)
from dnd.types.world import CardinalDirection


def test_closed_storehouse_door_admits_encounter_without_opening_it() -> None:
    reset_engine_runtime()
    built = build_battlefield("battlefield.storehouse_demo")
    recipe = encounter_recipe("encounter.storehouse_demo")
    grid = get_map()
    door = DirectionalDoor.get(built.object_uuids["door"])
    assert isinstance(door, DirectionalDoor)
    cursor = EventQueue.event_cursor()
    static = check_encounter_compatibility(recipe, built.definition)
    report = check_built_encounter_compatibility(static, recipe, grid)
    assert report.admitted, report.issues
    assert not door.is_open
    assert not grid.can_transition((5, 4), (6, 4))
    assert EventQueue.event_cursor() == cursor


@pytest.mark.parametrize("obstruction", ("wall", "height"))
def test_usable_door_does_not_admit_a_sealed_or_unwalkable_room(obstruction: str) -> None:
    reset_engine_runtime()
    built = build_battlefield("battlefield.storehouse_demo")
    recipe = encounter_recipe("encounter.storehouse_demo")
    grid = get_map()
    if obstruction == "wall":
        wall = build_directional_wall()
        wall.place_on_grid((5, 4), boundary_direction=CardinalDirection.EAST)
    else:
        for y in range(built.definition.height):
            grid.set_tile(5, y, height=2)
    report = check_built_encounter_compatibility(
        check_encounter_compatibility(recipe, built.definition), recipe, grid,
    )
    assert not report.admitted
    assert any(issue.code is EncounterCompatibilityCode.UNREACHABLE_FACTIONS for issue in report.issues)
