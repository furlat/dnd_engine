"""Canonical battlefield definitions, builders, and deployment contracts."""

from __future__ import annotations

from dnd.core.base_block import LightLevel
from dnd.core.base_tiles import MovementMode
from dnd.core.content.battlefields import BattlefieldDefinition
from dnd.core.gridmap import get_map
from dnd.runtime_reset import reset_engine_runtime
from dnd.scenarios.battlefield_catalog import (
    BATTLEFIELDS,
    build_battlefield,
    get_battlefield,
)
from dnd.scenarios.encounter_catalog import (
    AUTHORED_DEPLOYMENTS,
    AUTHORED_ENCOUNTER_RECIPES,
)
from dnd.scenarios.encounter_compatibility import (
    check_built_encounter_compatibility,
    check_encounter_compatibility,
)


def test_battlefield_catalog_has_ten_exact_mechanical_states() -> None:
    assert len(BATTLEFIELDS) == 10
    assert len({row.battlefield_id for row in BATTLEFIELDS}) == 10
    assert len({row.content_digest for row in BATTLEFIELDS}) == 10
    assert all(row.preview is not None for row in BATTLEFIELDS)

    bright = get_battlefield("battlefield.open_floor_bright")
    dark = get_battlefield("battlefield.open_floor_dark")
    assert bright.light_level == "bright"
    assert dark.light_level == "darkness"
    assert bright.content_digest != dark.content_digest

    reset_engine_runtime()
    build_battlefield(bright.battlefield_id)
    bright_levels = {
        tile.default_light for tile in get_map().get_all_tiles().values()
    }
    reset_engine_runtime()
    build_battlefield(dark.battlefield_id)
    dark_levels = {
        tile.default_light for tile in get_map().get_all_tiles().values()
    }
    assert bright_levels == {LightLevel.BRIGHT_LIGHT}
    assert dark_levels == {LightLevel.DARKNESS}


def test_battlefield_previews_retain_terrain_barriers_and_objects() -> None:
    closed = get_battlefield("battlefield.standard_hazards_closed")
    terrain = {
        (cell.position, cell.terrain) for cell in closed.preview.cells
    }
    assert ((2, 0), "water") in terrain
    assert ((6, 0), "difficult_terrain") in terrain
    assert ((0, 11), "spikes") in terrain
    door = next(
        obj for obj in closed.preview.objects if obj.kind == "door"
    )
    assert door.position == (7, 7)
    assert door.blocked_directions == ("west",)
    assert door.is_open is False

    opened = get_battlefield("battlefield.standard_hazards_open")
    open_door = next(
        obj for obj in opened.preview.objects if obj.kind == "door"
    )
    assert open_door.position == door.position
    assert open_door.blocked_directions == ()
    assert open_door.is_open is True

    labyrinth = get_battlefield("battlefield.reveal_labyrinth_dark")
    assert {
        obj.position
        for obj in labyrinth.preview.objects
        if obj.kind == "door"
    } == {(5, 6), (9, 8)}

    control_room = get_battlefield("battlefield.multi_object_dark")
    assert {
        (obj.kind, obj.position) for obj in control_room.preview.objects
    } >= {
        ("fireball_cannon", (6, 11)),
        ("loot_chest", (5, 10)),
        ("trap_lever", (5, 12)),
    }


def test_every_battlefield_has_one_builder_and_preview_matches_runtime() -> None:
    for definition in BATTLEFIELDS:
        reset_engine_runtime(
            grid_size=(definition.width, definition.height),
        )
        built = build_battlefield(definition.battlefield_id)
        assert built.definition is definition
        grid = get_map()
        for cell in definition.preview.cells:
            tile = grid.get_tile(*cell.position)
            assert tile is not None, (definition.battlefield_id, cell.position)
            assert tile.walkable is cell.walkable
            if cell.walkable:
                assert (
                    tile.get_movement_cost(MovementMode.WALKING)
                    == cell.walking_cost
                )
    reset_engine_runtime()


def test_reusable_deployments_fit_every_authored_roster() -> None:
    largest = max(
        len(slot.roster.members)
        for encounter in AUTHORED_ENCOUNTER_RECIPES
        for slot in encounter.roster_slots
    )
    assert len(AUTHORED_DEPLOYMENTS) == 10
    for deployment in AUTHORED_DEPLOYMENTS:
        assert len(deployment.zones) == 2
        assert all(
            (zone.max_members or len(zone.ordered_slots)) >= largest
            for zone in deployment.zones
        )


def test_canonical_static_and_built_compatibility_agree() -> None:
    for recipe in AUTHORED_ENCOUNTER_RECIPES:
        definition = get_battlefield(recipe.battlefield_id)
        static = check_encounter_compatibility(recipe, definition)
        assert static.admitted, (recipe.encounter_id, static.issues)
        reset_engine_runtime(
            grid_size=(definition.width, definition.height),
        )
        build_battlefield(definition.battlefield_id)
        built = check_built_encounter_compatibility(
            static,
            recipe,
            get_map(),
        )
        assert built.admitted, (recipe.encounter_id, built.issues)
    reset_engine_runtime()


def test_battlefield_contract_is_fully_described() -> None:
    assert all(
        field.description
        for field in BattlefieldDefinition.model_fields.values()
    )
