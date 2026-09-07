"""Real pygame SDL-dummy and fresh-process application proofs."""

import asyncio
from copy import deepcopy
from dataclasses import replace
import os
from pathlib import Path
import subprocess
import sys
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import numpy as np
import pygame
import pytest

from dnd.core.events import WorldInitializedEvent
from dnd.runtime_reset import reset_engine_runtime
from dnd.items.environment import DirectionalDoor
from dnd.types.materials import Material
from dnd.types.world_placement import BoundaryStructureKind
from game.app import (
    BACKGROUND,
    _display_sources,
    _produce_intervals,
    build_demo_intervals,
    draw_frame,
    run,
)
from game.assets import SurfaceCache, load_catalog
from game.presentation import PresentationTarget, reduce_interval
from game.projection import Camera, pick_support, project_screen


def test_real_pygame_runs_all_three_intervals() -> None:
    summary = run(
        frame_deltas=(0.1,),
        display_hold_seconds=0.1,
        max_frames=12,
        window_size=(960, 540),
    )
    assert summary.settled
    assert summary.terminal_count == 3
    assert any(engine > reducer == displayed for engine, reducer, displayed in summary.revision_samples)
    assert any(engine == reducer > displayed for engine, reducer, displayed in summary.revision_samples)
    assert summary.engine_cursor == summary.reducer_cursor == summary.display_cursor
    assert summary.revision_samples[-3:] == (
        (summary.engine_cursor, summary.reducer_cursor, summary.display_cursor),
    ) * 3
    assert [terminal.name for terminal in summary.terminals] == ["startup", "open", "close"]
    assert all(
        terminal.settled and not terminal.failed and not terminal.cancelled
        for terminal in summary.terminals
    )


def test_real_frames_prove_disclosure_door_torch_memory_and_locality() -> None:
    intervals = build_demo_intervals()
    reset_engine_runtime()
    pygame.init()
    screen = pygame.display.set_mode((960, 540))
    catalog = load_catalog()
    cache = SurfaceCache(catalog)
    camera = Camera(viewport=screen.get_size()).with_focus((31, 31))
    target: PresentationTarget | None = None
    evidences = []
    exterior_patches = []
    exterior_x, exterior_y = map(round, project_screen((32, 31), camera))
    try:
        for envelope, time_seconds in zip(intervals, (0.2, 0.7, 1.2), strict=True):
            target, _ = reduce_interval(target, envelope)
            evidence = draw_frame(
                screen,
                target,
                catalog,
                cache,
                camera,
                time_seconds,
                show_grid=True,
                mouse_position=None,
            )
            assert evidence.matches
            assert evidence.candidate_coordinates == 4096
            assert evidence.static_draws < evidence.candidate_coordinates
            assert evidence.grid_candidates == 4096
            assert evidence.grid_draws < evidence.grid_candidates
            assert evidence.animated_fixtures == 1
            evidences.append(evidence)
            exterior_patches.append(pygame.surfarray.array3d(screen)[
                exterior_x - 2:exterior_x + 3,
                exterior_y - 2:exterior_y + 3,
            ].copy())

        startup, opened, closed = evidences
        later_closed = draw_frame(
            screen,
            target,
            catalog,
            cache,
            camera,
            1.3,
            show_grid=True,
            mouse_position=None,
        )
        assert later_closed.flame_frame != closed.flame_frame
        assert next(
            row[6]
            for row in later_closed.actual_draws
            if row[0] == intervals[0].standing_torch_uuid
            and str(row[6]).startswith("torch.flame.")
        ) != next(
            row[6]
            for row in closed.actual_draws
            if row[0] == intervals[0].standing_torch_uuid
            and str(row[6]).startswith("torch.flame.")
        )
        assert len(startup.actual_calculations) == 2
        assert {row[0] for row in startup.actual_calculations} == {(2, 1), (2, 2)}
        assert {row[3] for row in startup.actual_calculations} == {0.2}
        startup_water = tuple(
            row for row in startup.actual_draws if row[2] == "water.unity"
        )
        assert len(startup_water) == 72
        assert {(row[3], row[4], row[5]) for row in startup_water} == {
            ("authored", None, "world.authored")
        }
        floor_uuid = target.tiles[(31, 34)].tile_uuid
        wall_uuid = next(
            object_uuid
            for object_uuid, world_object in target.objects.items()
            if world_object.placement.position == (31, 34)
        )
        assert next(
            index for index, row in enumerate(startup.actual_draws)
            if row[0] == floor_uuid
        ) < next(
            index for index, row in enumerate(startup.actual_draws)
            if row[0] == wall_uuid
        )

        far_uuid = target.tiles[(32, 31)].tile_uuid
        far_startup = next(row for row in startup.actual_draws if row[0] == far_uuid)
        far_open = next(row for row in opened.actual_draws if row[0] == far_uuid)
        far_closed = next(row for row in closed.actual_draws if row[0] == far_uuid)
        assert far_startup[3:6] == ("authored", None, "world.authored")
        assert far_open[3:6] == ("current", 2, "light.dim")
        assert far_closed[3:6] == ("memory", None, "memory.seen")
        assert np.all(np.any(exterior_patches[0] != BACKGROUND, axis=2))
        assert np.array_equal(exterior_patches[0], exterior_patches[2]), (
            "reclosing the door must not paint a false shadow on remembered "
            "ground in the full-structural view"
        )
        assert not np.array_equal(exterior_patches[0], exterior_patches[1])

        door_uuid = intervals[0].door_uuid
        assert [
            (row[2], row[6], row[8] if len(row) > 8 else None)
            for row in startup.actual_draws
            if row[0] == door_uuid
        ] == [
            ("stone.door.frame.e", "door_frame", None),
            ("wood.door.closed.e", "door_leaf", False),
        ]
        assert [
            (row[2], row[6], row[8] if len(row) > 8 else None)
            for row in opened.actual_draws
            if row[0] == door_uuid
        ] == [
            ("stone.door.frame.e", "door_frame", None),
            ("wood.door.open.e", "door_leaf", True),
        ]
        assert {
            row[3:6]
            for row in opened.actual_draws
            if row[0] == door_uuid
        } == {("current", None, "world.authored")}
        assert [
            (row[2], row[6], row[8] if len(row) > 8 else None)
            for row in closed.actual_draws
            if row[0] == door_uuid
        ] == [
            ("stone.door.frame.e", "door_frame", None),
            ("wood.door.closed.e", "door_leaf", False),
        ]

        torch_uuid = intervals[0].standing_torch_uuid
        for evidence in evidences:
            assert any(
                row[0] == torch_uuid and row[2] == "torch.body"
                for row in evidence.actual_draws
            )
            assert any(
                row[0] == torch_uuid and str(row[6]).startswith("torch.flame.")
                for row in evidence.actual_draws
            )

        local_target = deepcopy(target)
        disclosed = local_target.senses.visible | local_target.senses.seen
        local_target.tiles = {
            position: tile
            for position, tile in local_target.tiles.items()
            if position in disclosed
        }
        local_evidence = draw_frame(
            screen,
            local_target,
            catalog,
            cache,
            camera,
            1.2,
            show_grid=False,
            mouse_position=None,
        )
        assert (
            local_evidence.candidate_coordinates,
            local_evidence.water_chunks,
            local_evidence.animated_fixtures,
        ) == (
            len(disclosed),
            0,
            closed.animated_fixtures,
        )
        assert local_evidence.candidate_coordinates < closed.candidate_coordinates

        remembered_target = deepcopy(target)
        remembered_position = (34, 31)
        remembered_target.tiles = {
            remembered_position: remembered_target.tiles[remembered_position]
        }
        remembered_target.objects = {}
        remembered_target.door_uuid = None
        remembered_target.standing_torch_uuid = None
        remembered_target.standing_torch_state = None
        remembered_target.senses = replace(
            remembered_target.senses,
            visible=set(),
            seen={remembered_position},
            objects={},
            effective_light_levels={},
        )
        memory_frames = []
        for time_seconds in (0.2, 1.2):
            memory_evidence = draw_frame(
                screen,
                remembered_target,
                catalog,
                cache,
                camera,
                time_seconds,
                show_grid=False,
                mouse_position=None,
            )
            assert memory_evidence.matches
            assert {row[3] for row in memory_evidence.actual_calculations} == {0.0}
            memory_frames.append(pygame.surfarray.array3d(screen)[:, 130:].copy())
        assert np.array_equal(*memory_frames)
    finally:
        pygame.quit()


def test_full_structural_pick_includes_an_undisclosed_authored_tile() -> None:
    startup = build_demo_intervals()[0]
    reset_engine_runtime()
    target, _ = reduce_interval(None, startup)
    assert target.senses is not None
    position = (0, 0)
    assert position not in target.senses.visible
    assert position not in target.senses.seen
    tile = target.tiles[position]
    camera = Camera(zoom=0.15).with_focus(position)

    chosen, tested = pick_support(
        project_screen(position, camera),
        camera,
        target.tiles.values(),
    )

    assert chosen is tile
    assert tested == (0, 1, 2)


def test_transparent_margin_fringe_preserves_world_draw_obligation() -> None:
    startup = build_demo_intervals()[0]
    reset_engine_runtime()
    target, reduced = reduce_interval(None, startup)
    position = (0, 0)
    target.tiles = {position: target.tiles[position]}
    target.objects = {}
    target.door_uuid = None
    target.standing_torch_uuid = None
    target.standing_torch_state = None
    assert target.senses is not None
    target.senses = replace(
        target.senses,
        visible=set(),
        seen=set(),
        objects={},
        effective_light_levels={},
    )
    pygame.init()
    screen = pygame.display.set_mode((100, 100))
    try:
        catalog = load_catalog()
        cache = SurfaceCache(catalog)
        camera = Camera(zoom=0.5, viewport=screen.get_size()).with_focus(position)
        asset_id = catalog.bindings["terrain"]["earth"]["e"]
        contact = project_screen(position, camera)
        initial = cache.blit_position(asset_id, camera.zoom, contact)
        full = cache.scaled(asset_id, camera.zoom)
        alpha_x, alpha_y, alpha_width, alpha_height = cache.alpha_bounds(
            asset_id, camera.zoom
        )
        desired = -full.get_width() + 1, 0
        camera = camera.with_screen_pan((
            desired[0] - initial[0],
            desired[1] - initial[1],
        ))
        full_rect = full.get_rect(topleft=desired)
        cropped_rect = pygame.Rect(
            desired[0] + alpha_x,
            desired[1] + alpha_y,
            alpha_width,
            alpha_height,
        )
        assert full_rect.colliderect(screen.get_rect())
        assert not cropped_rect.colliderect(screen.get_rect())

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
        represented, hidden = _display_sources(reduced, evidence)
        world_index = next(
            index
            for index, event in startup.admitted
            if type(event) is WorldInitializedEvent
        )
        assert evidence.static_draws == 1
        assert evidence.actual_draws[0][0] == target.tiles[position].tile_uuid
        assert world_index in represented
        assert world_index not in hidden
    finally:
        pygame.quit()


@pytest.mark.parametrize(
    ("structure_update", "message"),
    (
        ({"material": Material.METAL}, "unsupported boundary material"),
        (
            {"structure": BoundaryStructureKind.FENCE},
            "unsupported boundary structure",
        ),
    ),
)
def test_disclosed_unsupported_boundary_is_a_coverage_error(
    structure_update: dict[str, object],
    message: str,
) -> None:
    startup = build_demo_intervals()[0]
    reset_engine_runtime()
    pygame.init()
    screen = pygame.display.set_mode((960, 540))
    try:
        catalog = load_catalog()
        cache = SurfaceCache(catalog)
        target, _ = reduce_interval(None, startup)
        wall_uuid, wall = next(
            (object_uuid, world_object)
            for object_uuid, world_object in target.objects.items()
            if world_object.placement.position == (31, 34)
        )
        structure = wall.item.boundary_structure
        assert structure is not None
        target.objects[wall_uuid] = wall.model_copy(update={
            "item": wall.item.model_copy(update={
                "boundary_structure": structure.model_copy(update=structure_update),
            }),
        })
        camera = Camera(viewport=screen.get_size()).with_focus((31, 31))

        with pytest.raises(RuntimeError, match=message):
            draw_frame(
                screen,
                target,
                catalog,
                cache,
                camera,
                0.2,
                show_grid=False,
                mouse_position=None,
            )
    finally:
        pygame.quit()


def test_fresh_process_uses_the_same_public_entry() -> None:
    root = Path(__file__).parents[2]
    environment = dict(os.environ)
    environment["SDL_VIDEODRIVER"] = "dummy"
    environment["SDL_AUDIODRIVER"] = "dummy"
    started = time.perf_counter()
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; from game.app import run; "
                "run(frame_deltas=(0.1,), display_hold_seconds=0.0, "
                "max_frames=12, window_size=(960, 540)); "
                "assert 'dnd.content_system.builtin' not in sys.modules"
            ),
        ],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert time.perf_counter() - started <= 8.0
    assert "terminals=3 settled=True" in result.stdout


def test_engine_producer_yields_each_scripted_mechanic_incrementally() -> None:
    async def exercise() -> None:
        queue = asyncio.Queue(maxsize=3)
        producer = asyncio.create_task(_produce_intervals(queue))
        try:
            await asyncio.sleep(0)
            startup = queue.get_nowait()
            door = DirectionalDoor.get(startup.door_uuid)
            assert door is not None and not door.is_open
            assert startup.name == "startup"
            assert queue.empty()

            await asyncio.sleep(0)
            opened = queue.get_nowait()
            assert opened.name == "open"
            assert door.is_open
            assert queue.empty()

            await asyncio.sleep(0)
            closed = queue.get_nowait()
            assert closed.name == "close"
            assert not door.is_open
            assert queue.empty()

            await producer
        finally:
            if not producer.done():
                producer.cancel()
                await asyncio.gather(producer, return_exceptions=True)
            reset_engine_runtime()

    asyncio.run(exercise())


def test_fresh_import_stays_inside_the_in_process_game_lane() -> None:
    root = Path(__file__).parents[2]
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys,time; start=time.perf_counter(); import game.app; "
                "elapsed=time.perf_counter()-start; "
                "assert elapsed <= 4.0, elapsed; "
                "assert 'dnd.content_system.builtin' not in sys.modules; "
                "print(elapsed)"
            ),
        ],
        cwd=root,
        env=dict(os.environ),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
