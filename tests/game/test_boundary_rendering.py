"""Finite wall, corner, door, light-face, and placement rendering proofs."""

from collections import Counter
from copy import deepcopy
from dataclasses import replace
import os
from uuid import UUID

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import pytest
import numpy as np

from dnd.core.events import SpatialChangeEvent
from dnd.runtime_reset import reset_engine_runtime
from dnd.types.materials import Material
from dnd.types.world import CardinalDirection, LightLevel
from game.app import (
    BACKGROUND,
    _authored_treatment,
    _display_sources,
    _treatment,
    build_demo_intervals,
    draw_frame,
)
from game.assets import SurfaceCache, load_catalog
from game.presentation import PresentationTarget, reduce_interval
from game.projection import Camera, MAP_CENTER, TILE_WIDTH, camera_pose, project_screen
from game.water import WaterSupportInput, render_water_batch, water_source_origin


OWNER = (20, 20)
DIRECTIONS = (
    CardinalDirection.NORTH,
    CardinalDirection.EAST,
    CardinalDirection.SOUTH,
    CardinalDirection.WEST,
)
ENTRY_SETS = tuple(
    tuple(direction for index, direction in enumerate(DIRECTIONS) if mask & (1 << index))
    for mask in range(16)
)
CORNER_POSES = {
    frozenset((CardinalDirection.NORTH, CardinalDirection.EAST)): ("e", "s", "w", "n"),
    frozenset((CardinalDirection.EAST, CardinalDirection.SOUTH)): ("n", "e", "s", "w"),
    frozenset((CardinalDirection.SOUTH, CardinalDirection.WEST)): ("w", "n", "e", "s"),
    frozenset((CardinalDirection.WEST, CardinalDirection.NORTH)): ("s", "w", "n", "e"),
}


@pytest.fixture(scope="module")
def rendering() -> tuple[pygame.Surface, object, SurfaceCache]:
    pygame.init()
    screen = pygame.display.set_mode((800, 600))
    catalog = load_catalog()
    cache = SurfaceCache(catalog)
    try:
        yield screen, catalog, cache
    finally:
        pygame.quit()


@pytest.fixture(scope="module")
def demo_intervals():
    intervals = build_demo_intervals()
    reset_engine_runtime()
    return intervals


@pytest.fixture(scope="module")
def base_target(demo_intervals) -> PresentationTarget:
    target, _ = reduce_interval(None, demo_intervals[0])
    return target


def _wall_target(
    base_target: PresentationTarget,
    directions: tuple[CardinalDirection, ...],
    *,
    heights: tuple[int, ...] | None = None,
    light_levels: dict[tuple[int, int], LightLevel] | None = None,
) -> tuple[PresentationTarget, tuple[UUID, ...]]:
    target = deepcopy(base_target)
    source_rows = [
        row
        for row in target.objects.values()
        if row.item.boundary_structure is not None
        and row.item.boundary_structure.structure.value == "wall"
        and row.item.boundary_structure.material is Material.STONE
    ]
    object_rows = {}
    object_uuids = []
    for index, direction in enumerate(directions):
        source = source_rows[index]
        object_uuid = source.item.item_uuid
        height = heights[index] if heights is not None else 0
        object_rows[object_uuid] = source.model_copy(update={
            "placement": source.placement.model_copy(update={
                "position": OWNER,
                "boundary_direction": direction,
                "base_height_steps": height,
                "top_height_steps": height + 1,
            }),
        })
        object_uuids.append(object_uuid)
    incident = {
        OWNER,
        (OWNER[0], OWNER[1] + 1),
        (OWNER[0] + 1, OWNER[1]),
        (OWNER[0], OWNER[1] - 1),
        (OWNER[0] - 1, OWNER[1]),
    }
    levels = light_levels or {
        position: LightLevel.BRIGHT_LIGHT
        for position in incident
    }
    target.objects = object_rows
    target.tiles = {
        position: tile
        for position, tile in target.tiles.items()
        if position in incident
    }
    target.door_uuid = None
    target.standing_torch_uuid = None
    target.standing_torch_state = None
    assert target.senses is not None
    target.senses = replace(
        target.senses,
        visible=set(levels),
        seen=set(levels),
        objects={},
        effective_light_levels=dict(levels),
    )
    return target, tuple(object_uuids)


def _boundary_rows(evidence) -> tuple[tuple[object, ...], ...]:
    return tuple(
        row
        for row in evidence.actual_draws
        if len(row) > 6 and row[6] in {"wall", "wall_corner", "door_frame", "door_leaf"}
    )


@pytest.mark.parametrize("quadrant", range(4))
@pytest.mark.parametrize("directions", ENTRY_SETS)
def test_every_owner_tile_wall_subset_has_exact_four_camera_composition(
    rendering,
    base_target,
    quadrant: int,
    directions: tuple[CardinalDirection, ...],
) -> None:
    screen, catalog, cache = rendering
    target, object_uuids = _wall_target(base_target, directions)
    evidence = draw_frame(
        screen,
        target,
        catalog,
        cache,
        Camera(quadrant=quadrant, viewport=screen.get_size()).with_focus(OWNER),
        0.2,
        show_grid=False,
        mouse_position=None,
    )
    rows = _boundary_rows(evidence)
    pair = frozenset(directions)
    is_corner = len(directions) == 2 and pair in CORNER_POSES

    if is_corner:
        assert len(rows) == 1
        assert rows[0][2] == f"stone.wall.corner.{CORNER_POSES[pair][quadrant]}"
        represented = tuple(rows[0][0])
    else:
        assert len(rows) == len(directions)
        assert all(str(row[2]).startswith("stone.wall.straight.") for row in rows)
        represented = tuple(str(row[0]) for row in rows)
    assert Counter(represented) == Counter(str(value) for value in object_uuids)


def test_corner_coalescing_ignores_support_light_but_requires_equal_base_height(
    rendering,
    base_target,
) -> None:
    screen, catalog, cache = rendering
    directions = (CardinalDirection.NORTH, CardinalDirection.EAST)
    one_current_side = {
        (OWNER[0], OWNER[1] + 1): LightLevel.BRIGHT_LIGHT,
    }
    treatment_target, treatment_uuids = _wall_target(
        base_target,
        directions,
        light_levels=one_current_side,
    )
    height_target, height_uuids = _wall_target(
        base_target,
        directions,
        heights=(0, 1),
    )

    treatment_evidence = draw_frame(
        screen,
        treatment_target,
        catalog,
        cache,
        Camera(viewport=screen.get_size()).with_focus(OWNER),
        0.2,
        show_grid=False,
        mouse_position=None,
    )
    treatment_rows = _boundary_rows(treatment_evidence)
    assert [row[6] for row in treatment_rows] == ["wall_corner"]
    assert treatment_rows[0][3:6] == ("current", None, "world.authored")
    assert Counter(treatment_rows[0][0]) == Counter(
        str(value) for value in treatment_uuids
    )

    height_evidence = draw_frame(
        screen,
        height_target,
        catalog,
        cache,
        Camera(viewport=screen.get_size()).with_focus(OWNER),
        0.2,
        show_grid=False,
        mouse_position=None,
    )
    height_rows = _boundary_rows(height_evidence)
    assert [row[6] for row in height_rows] == ["wall", "wall"]
    assert Counter(str(row[0]) for row in height_rows) == Counter(
        str(value) for value in height_uuids
    )


@pytest.mark.parametrize("quadrant", range(4))
def test_same_owner_mixed_materials_remain_two_identifiable_straights(
    rendering,
    base_target,
    quadrant: int,
) -> None:
    screen, catalog, cache = rendering
    directions = (CardinalDirection.NORTH, CardinalDirection.EAST)
    target, object_uuids = _wall_target(base_target, directions)
    wood_uuid = object_uuids[1]
    wood = target.objects[wood_uuid]
    structure = wood.item.boundary_structure
    assert structure is not None
    target.objects[wood_uuid] = wood.model_copy(update={
        "item": wood.item.model_copy(update={
            "boundary_structure": structure.model_copy(update={
                "material": Material.WOOD,
            }),
        }),
    })

    evidence = draw_frame(
        screen,
        target,
        catalog,
        cache,
        Camera(quadrant=quadrant, viewport=screen.get_size()).with_focus(OWNER),
        0.2,
        show_grid=False,
        mouse_position=None,
    )
    rows = _boundary_rows(evidence)

    assert [row[6] for row in rows] == ["wall", "wall"]
    assert Counter(str(row[0]) for row in rows) == Counter(
        str(value) for value in object_uuids
    )
    assert {row[2] for row in rows} == {
        catalog.bindings["stone_wall_straight"][camera_pose("north", quadrant)],
        catalog.bindings["wood_wall_straight"][camera_pose("east", quadrant)],
    }


@pytest.mark.parametrize("quadrant", range(4))
def test_real_lodge_and_storehouse_use_matching_corners_and_straights(
    rendering,
    base_target,
    quadrant: int,
) -> None:
    screen, catalog, cache = rendering
    evidence = draw_frame(
        screen,
        base_target,
        catalog,
        cache,
        Camera(
            quadrant=quadrant,
            zoom=0.15,
            viewport=screen.get_size(),
        ).with_focus(MAP_CENTER),
        0.2,
        show_grid=False,
        mouse_position=None,
    )
    rows_by_position = {
        row[1][0]: row
        for row in _boundary_rows(evidence)
        if row[6] in {"wall", "wall_corner"}
    }
    corner_references = {
        (24, 26): "west",
        (31, 26): "south",
        (24, 37): "north",
        (31, 37): "east",
    }
    for position, reference in corner_references.items():
        row = rows_by_position[position]
        assert row[6] == "wall_corner"
        assert row[2] == catalog.bindings["stone_wall_corner"][
            camera_pose(reference, quadrant)
        ]
    for position, reference in {
        (35, 38): "west",
        (42, 38): "south",
        (35, 44): "north",
        (42, 44): "east",
    }.items():
        row = rows_by_position[position]
        assert row[6] == "wall_corner"
        assert row[2] == catalog.bindings["wood_wall_corner"][
            camera_pose(reference, quadrant)
        ]
    assert rows_by_position[(31, 30)][2] == catalog.bindings[
        "stone_wall_straight"
    ][camera_pose("east", quadrant)]
    assert rows_by_position[(35, 41)][2] == catalog.bindings[
        "wood_wall_straight"
    ][camera_pose("west", quadrant)]


def test_current_composite_wall_uses_neutral_treatment_in_every_quadrant(
    rendering,
    base_target,
) -> None:
    screen, catalog, cache = rendering
    target, (wall_uuid,) = _wall_target(
        base_target,
        (CardinalDirection.EAST,),
        light_levels={OWNER: LightLevel.BRIGHT_LIGHT},
    )

    rows = []
    for quadrant in range(4):
        evidence = draw_frame(
            screen,
            target,
            catalog,
            cache,
            Camera(quadrant=quadrant, viewport=screen.get_size()).with_focus(OWNER),
            0.2,
            show_grid=False,
            mouse_position=None,
        )
        rows.append(_boundary_rows(evidence)[0])

    assert all(row[0] == wall_uuid for row in rows)
    assert {row[3:6] for row in rows} == {
        ("current", None, "world.authored")
    }
    assert target.senses is not None
    assert (OWNER[0] + 1, OWNER[1]) not in target.senses.visible


def test_memory_only_composite_wall_keeps_memory_treatment(
    rendering,
    base_target,
) -> None:
    screen, catalog, cache = rendering
    target, (wall_uuid,) = _wall_target(
        base_target,
        (CardinalDirection.EAST,),
        light_levels={OWNER: LightLevel.BRIGHT_LIGHT},
    )
    assert target.senses is not None
    target.senses = replace(
        target.senses,
        visible=set(),
        seen={OWNER},
        effective_light_levels={},
    )

    evidence = draw_frame(
        screen,
        target,
        catalog,
        cache,
        Camera(viewport=screen.get_size()).with_focus(OWNER),
        0.2,
        show_grid=False,
        mouse_position=None,
    )
    row = _boundary_rows(evidence)[0]
    assert row[0] == wall_uuid
    assert row[3:6] == ("memory", None, "memory.seen")


def test_door_frame_does_not_disclose_leaf_or_settle_state_without_contact(
    rendering,
    demo_intervals,
) -> None:
    screen, catalog, cache = rendering
    startup, opened, _ = demo_intervals
    target, _ = reduce_interval(None, startup)
    target, reduced = reduce_interval(target, opened)
    assert target.senses is not None
    target.senses = replace(
        target.senses,
        objects={
            object_uuid: contact
            for object_uuid, contact in target.senses.objects.items()
            if object_uuid != opened.door_uuid
        },
    )
    evidence = draw_frame(
        screen,
        target,
        catalog,
        cache,
        Camera(viewport=screen.get_size()).with_focus((31, 31)),
        0.7,
        show_grid=False,
        mouse_position=None,
    )
    rows = [row for row in _boundary_rows(evidence) if row[0] == opened.door_uuid]
    represented, hidden = _display_sources(reduced, evidence)
    door_event_index = next(
        index for index, event in opened.admitted if type(event) is SpatialChangeEvent
    )

    assert [row[6] for row in rows] == ["door_frame"]
    assert door_event_index not in represented
    assert door_event_index in hidden


@pytest.mark.parametrize("mismatch", ("position", "direction", "base_height"))
def test_stale_leaf_placement_cannot_settle_the_door_event(
    rendering,
    demo_intervals,
    mismatch: str,
) -> None:
    screen, catalog, cache = rendering
    startup, opened, _ = demo_intervals
    target, _ = reduce_interval(None, startup)
    target, reduced = reduce_interval(target, opened)
    evidence = draw_frame(
        screen,
        target,
        catalog,
        cache,
        Camera(viewport=screen.get_size()).with_focus((31, 31)),
        0.7,
        show_grid=False,
        mouse_position=None,
    )
    def stale_leaf(row: tuple) -> tuple:
        if len(row) <= 8 or row[6] != "door_leaf":
            return row
        if mismatch == "position":
            return row[:1] + (((30, 31), row[1][1]),) + row[2:]
        if mismatch == "direction":
            return row[:1] + ((row[1][0], "north"),) + row[2:]
        if mismatch == "base_height":
            return row[:7] + (row[7] + 1,) + row[8:]
        raise AssertionError(f"unhandled mismatch {mismatch}")

    stale_draws = tuple(stale_leaf(row) for row in evidence.actual_draws)
    represented, hidden = _display_sources(
        reduced,
        replace(evidence, actual_draws=stale_draws),
    )
    door_event_index = next(
        index for index, event in opened.admitted if type(event) is SpatialChangeEvent
    )

    assert door_event_index not in represented
    assert door_event_index in hidden


def test_standing_torch_body_and_flame_share_committed_placement_base(
    rendering,
    base_target,
) -> None:
    screen, catalog, cache = rendering
    target = deepcopy(base_target)
    fixture_uuid = target.standing_torch_uuid
    assert fixture_uuid is not None
    fixture = target.objects[fixture_uuid]
    target.objects = {
        fixture_uuid: fixture.model_copy(update={
            "placement": fixture.placement.model_copy(update={
                "base_height_steps": 2,
                "top_height_steps": 3,
            }),
        }),
    }
    evidence = draw_frame(
        screen,
        target,
        catalog,
        cache,
        Camera(viewport=screen.get_size()).with_focus(fixture.placement.position),
        0.2,
        show_grid=False,
        mouse_position=None,
    )
    fixture_rows = [row for row in evidence.actual_draws if row[0] == fixture_uuid]

    assert len(fixture_rows) == 2
    assert {row[8] for row in fixture_rows} == {2}
    assert target.tiles[fixture.placement.position].elevation_steps == 0


def test_real_q0_water_wall_overlap_uses_planar_then_spatial_pixel_order(
    rendering,
    base_target,
) -> None:
    screen, catalog, cache = rendering
    target = deepcopy(base_target)
    position = (34, 31)
    wall_uuid, wall = next(
        (object_uuid, world_object)
        for object_uuid, world_object in target.objects.items()
        if world_object.placement.position == (31, 33)
        and world_object.item.boundary_structure is not None
    )
    wall = wall.model_copy(update={
        "placement": wall.placement.model_copy(update={"position": position}),
    })
    target.tiles = {position: target.tiles[position]}
    target.objects = {wall_uuid: wall}
    target.door_uuid = None
    target.standing_torch_uuid = None
    target.standing_torch_state = None
    assert target.senses is not None
    target.senses = replace(
        target.senses,
        visible={position},
        seen={position},
        objects={},
        effective_light_levels={position: LightLevel.DIM_LIGHT},
    )
    camera = Camera(
        quadrant=0,
        zoom=0.75,
        viewport=screen.get_size(),
    ).with_focus(position).with_screen_pan((0.0, 180.0))
    evidence = draw_frame(
        screen,
        target,
        catalog,
        cache,
        camera,
        0.2,
        show_grid=False,
        mouse_position=None,
    )

    water_uuid = target.tiles[position].tile_uuid
    assert [row[0] for row in evidence.actual_draws] == [water_uuid, wall_uuid]

    water_spec = catalog.resources[catalog.water["mask"]]
    contact = project_screen(position, camera)
    water_destination = cache.blit_position(catalog.water["mask"], camera.zoom, contact)
    water_input = WaterSupportInput(
        source_origin_px=water_source_origin(
            position,
            pivot=water_spec.pivot,
            asset_scale=water_spec.scale,
        ),
        destination_px=water_destination,
        multiplier=_treatment(catalog, LightLevel.DIM_LIGHT)[1],
    )
    water_batch = render_water_batch(
        mask_surface=cache.scaled(catalog.water["mask"], camera.zoom),
        ripple_texture=cache.rgb(catalog.water["ripple"]),
        normal_texture=cache.rgb(catalog.water["normal"]),
        supports=(water_input,),
        framebuffer_size=screen.get_size(),
        tile_width_px=TILE_WIDTH,
        render_scale=camera.zoom,
        time_seconds=0.2,
        material=catalog.water,
    )
    water = water_batch.surfaces[0]
    water_destination = water_batch.destinations[0]
    wall_id = catalog.bindings["stone_wall_straight"]["e"]
    wall_surface = cache.cropped_treated(
        wall_id,
        camera.zoom,
        _authored_treatment(catalog)[1],
    )
    wall_destination = cache.blit_position(wall_id, camera.zoom, contact)
    wall_bounds = cache.alpha_bounds(wall_id, camera.zoom)
    wall_destination = (
        wall_destination[0] + wall_bounds[0],
        wall_destination[1] + wall_bounds[1],
    )

    def composite(*, reverse: bool) -> np.ndarray:
        canvas = pygame.Surface(screen.get_size())
        canvas.fill(BACKGROUND)
        layers = (
            ((wall_surface, wall_destination, 0),
             (water, water_destination, pygame.BLEND_PREMULTIPLIED))
            if reverse
            else ((water, water_destination, pygame.BLEND_PREMULTIPLIED),
                  (wall_surface, wall_destination, 0))
        )
        for surface, destination, flags in layers:
            canvas.blit(surface, destination, special_flags=flags)
        return pygame.surfarray.array3d(canvas)

    actual = pygame.surfarray.array3d(screen)
    expected = composite(reverse=False)
    reversed_order = composite(reverse=True)
    affected = np.any(expected != reversed_order, axis=2)
    assert int(affected.sum()) > 0
    assert np.array_equal(actual[affected], expected[affected])
