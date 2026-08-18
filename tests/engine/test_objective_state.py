"""Focused contract for reusable objective runtime-state serialization."""

from collections.abc import Iterator
from uuid import uuid4

import pytest

from dnd.blocks.equipment import (
    Weapon,
)
from dnd.content_system.item_bindings import ItemRuntimeOrigin
from dnd.content_system.item_materialization import materialize_item
from dnd.types.senses import SenseMode, SensesType
from dnd.core.gridmap import GridMap
from dnd.entities.entity import Entity, EntityConfig
from dnd.items.torches import TORCH_RECIPE, Torch
from dnd.items.weapons import DAGGER_RECIPE
from dnd.monsters.bestiary_content import (
    BESTIARY_CREATURE_DECLARATIONS_BY_ID,
)
from dnd.runtime_reset import reset_engine_runtime
from server.objective_state import (
    build_current_objective_game_state,
    build_current_objective_world,
    build_current_objective_visibility,
    build_objective_equipment,
    build_objective_game_state,
    build_objective_world,
    build_objective_visibility,
    get_floor_object_state,
)


@pytest.fixture
def objective_scene() -> Iterator[tuple[GridMap, Entity, Entity, Torch]]:
    """Create a small deterministic runtime with actors and one floor item."""
    grid = reset_engine_runtime(grid_size=(3, 2))
    observer = Entity.create(
        source_entity_uuid=uuid4(),
        name="Observer",
        config=EntityConfig(position=(0, 0), faction="heroes"),
        content_ref=BESTIARY_CREATURE_DECLARATIONS_BY_ID["goblin"].ref,
    )
    target = Entity.create(
        source_entity_uuid=uuid4(),
        name="Target",
        config=EntityConfig(position=(1, 0), faction="monsters"),
        content_ref=BESTIARY_CREATURE_DECLARATIONS_BY_ID["skeleton"].ref,
    )
    torch = materialize_item(
        TORCH_RECIPE,
        observer.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=Torch,
    )
    torch.name = "Debug Torch"
    torch.is_lit = True
    grid.place_object(torch.uuid, (1, 1))

    observer.senses.visible = {
        (0, 0): True,
        (1, 0): True,
        (2, 0): False,
    }
    observer.senses.entities = {target.uuid: target.position}
    observer.senses.objects = {torch.uuid: (1, 1)}
    observer.senses.seen = {(0, 0), (1, 0), (2, 0)}
    observer.senses.sense_modes = [
        SenseMode(sense_type=SensesType.DARKVISION, range_feet=60),
    ]

    try:
        yield grid, observer, target, torch
    finally:
        reset_engine_runtime()


def test_objective_game_state_preserves_entities_tiles_and_floor_object_state(
    objective_scene: tuple[GridMap, Entity, Entity, Torch],
) -> None:
    """The explicit builder reproduces the legacy objective state shape."""
    grid, observer, target, torch = objective_scene

    state = build_objective_game_state(
        grid=grid,
        entities=[observer, target],
        encounter=None,
    )

    assert state.grid.model_dump(exclude={"tiles"}) == {
        "min_x": 0,
        "min_y": 0,
        "max_x": 2,
        "max_y": 1,
        "connectors": [],
    }
    assert {(tile.x, tile.y) for tile in state.grid.tiles} == {
        (0, 0),
        (1, 0),
        (2, 0),
        (0, 1),
        (1, 1),
        (2, 1),
    }
    assert [(entity.uuid, entity.name, entity.position) for entity in state.entities] == [
        (str(observer.uuid), "Observer", (0, 0)),
        (str(target.uuid), "Target", (1, 0)),
    ]
    assert state.encounter is None
    assert len(state.floor_objects) == 1
    floor_object = state.floor_objects[0]
    assert floor_object.uuid == str(torch.uuid)
    assert floor_object.name == "Debug Torch"
    assert floor_object.position == (1, 1)
    assert floor_object.map_char == "\u2666"
    assert floor_object.state["is_lit"] is True
    assert floor_object.state["bright_radius_feet"] == 20
    assert "uuid" not in floor_object.state
    assert "name" not in floor_object.state
    assert "map_char" not in floor_object.state
    assert "blocks" not in floor_object.state

    assert get_floor_object_state(torch) == floor_object.state
    assert build_current_objective_game_state(encounter=None) == state


def test_objective_visibility_preserves_every_observer_cache_field(
    objective_scene: tuple[GridMap, Entity, Entity, Torch],
) -> None:
    """Visibility retains current, remembered, entity, object, and light facts."""
    _, observer, target, torch = objective_scene

    visibility = build_objective_visibility(entities=[observer, target])

    assert set(visibility.root) == {str(observer.uuid), str(target.uuid)}
    observer_row = visibility.root[str(observer.uuid)]
    assert observer_row.name == "Observer"
    assert observer_row.position == (0, 0)
    assert observer_row.visible_cells == [(0, 0), (1, 0)]
    assert observer_row.visible_entities == [str(target.uuid)]
    assert observer_row.visible_objects == [str(torch.uuid)]
    assert set(observer_row.seen_cells) == {(0, 0), (1, 0), (2, 0)}
    assert observer_row.sense_modes == [
        SenseMode(sense_type=SensesType.DARKVISION, range_feet=60),
    ]
    assert observer_row.effective_light_levels == {"0,0": 3, "1,0": 3}

    target_row = visibility.root[str(target.uuid)]
    assert target_row.name == "Target"
    assert target_row.visible_cells == []
    assert target_row.visible_entities == []
    assert target_row.visible_objects == []
    assert build_current_objective_visibility() == visibility


def test_objective_game_state_ignores_unresolved_floor_registry_entries(
    objective_scene: tuple[GridMap, Entity, Entity, Torch],
) -> None:
    """A stale grid index cannot manufacture a misleading object DTO."""
    grid, observer, target, _ = objective_scene
    grid._object_positions[uuid4()] = (2, 1)

    state = build_objective_game_state(
        grid=grid,
        entities=[observer, target],
        encounter=None,
    )

    assert len(state.floor_objects) == 1
    assert state.floor_objects[0].name == "Debug Torch"


def test_objective_world_includes_one_equipment_reducer_seed_per_entity(
    objective_scene: tuple[GridMap, Entity, Entity, Torch],
) -> None:
    """World capture keeps equipment in the same live/replay reducer seed."""
    grid, observer, target, _ = objective_scene
    dagger = materialize_item(
        DAGGER_RECIPE,
        observer.uuid,
        origin=ItemRuntimeOrigin.STARTER,
        expected_type=Weapon,
    )
    assert observer.loot_item(dagger)

    equipment = build_objective_equipment(entities=[observer, target])
    world = build_objective_world(
        grid=grid,
        entities=[observer, target],
        encounter=None,
    )

    assert world.equipment_by_entity == equipment
    assert set(world.equipment_by_entity) == {str(observer.uuid), str(target.uuid)}
    assert [item.uuid for item in world.equipment_by_entity[str(observer.uuid)].inventory] == [
        str(dagger.uuid)
    ]
    assert world.state == build_objective_game_state(
        grid=grid,
        entities=[observer, target],
        encounter=None,
    )
    assert world.visibility == build_objective_visibility(entities=[observer, target])
    assert build_current_objective_world(encounter=None) == world
