"""Exact copied-asset catalog, decoding, binding, and animation proofs."""

import json
import os
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import pytest
import numpy as np

import game.assets as assets_module
from game.assets import SurfaceCache, flame_frame_index, load_catalog
from game.projection import Camera, ZOOM_LEVELS, camera_pose, project_screen


@pytest.fixture
def surface_cache() -> SurfaceCache:
    pygame.init()
    pygame.display.set_mode((32, 32))
    try:
        yield SurfaceCache(load_catalog())
    finally:
        pygame.quit()


def test_catalog_loads_the_exact_finite_visual_set(surface_cache: SurfaceCache) -> None:
    catalog = surface_cache.catalog
    assert len(catalog.resources) == 72
    assert len(catalog.flame_frames) == 16
    assert catalog.flame_fps == 10
    assert all(surface_cache.canonical[key].get_size() == spec.native_size for key, spec in catalog.resources.items())
    assert catalog.bindings["terrain"] == {
        "earth": {pose: f"terrain.earth.{pose}" for pose in "ensw"},
        "wood": {pose: f"terrain.wood.{pose}" for pose in "ensw"},
        "stone": {pose: f"terrain.stone.{pose}" for pose in "ensw"},
        "water": "water.unity",
    }
    assert {
        table: {
            pose: catalog.resources[asset_id].path.name
            for pose, asset_id in catalog.bindings[table].items()
        }
        for table in (
            "stone_wall_straight",
            "stone_wall_corner",
            "wood_wall_straight",
            "wood_wall_corner",
            "stone_door_frame",
            "wood_door_closed",
            "wood_door_open",
        )
    } == {
        "stone_wall_straight": {pose: f"wall-d1-{pose}.png" for pose in "ensw"},
        "stone_wall_corner": {pose: f"wall-d2-{pose}.png" for pose in "ensw"},
        "wood_wall_straight": {pose: f"wall-c1-{pose}.png" for pose in "ensw"},
        "wood_wall_corner": {pose: f"wall-c2-{pose}.png" for pose in "ensw"},
        "stone_door_frame": {pose: f"wall-d6-{pose}.png" for pose in "ensw"},
        "wood_door_closed": {pose: f"door-a1-{pose}.png" for pose in "ensw"},
        "wood_door_open": {pose: f"door-a2-{pose}.png" for pose in "ensw"},
    }
    for table in ("stone_wall_straight", "stone_wall_corner", "stone_door_frame"):
        for asset_id in catalog.bindings[table].values():
            assert catalog.resources[asset_id].pivot == (128.0, 207.36)
            assert catalog.resources[asset_id].scale == pytest.approx(128 / 127)
    for table in ("wood_door_closed", "wood_door_open"):
        for asset_id in catalog.bindings[table].values():
            assert catalog.resources[asset_id].pivot == (128.0, 209.92)
            assert catalog.resources[asset_id].scale == pytest.approx(128 / 127)
    for material, family in (("earth", "a1"), ("wood", "f1")):
        for pose, asset_id in catalog.bindings["terrain"][material].items():
            spec = catalog.resources[asset_id]
            assert spec.path.name == f"ground-{family}-{pose}.png"
            assert spec.pivot == (128.0, 208.0)
            assert spec.scale == 1.0
    for table in ("wood_wall_straight", "wood_wall_corner"):
        for asset_id in catalog.bindings[table].values():
            assert catalog.resources[asset_id].pivot == (128.0, 208.0)
            assert catalog.resources[asset_id].scale == 1.0
    assert not any(
        (assets_module.ASSET_ROOT / "environment" / f"wall-{family}-{pose}.png").exists()
        for family in ("b1", "b4", "d8")
        for pose in "ensw"
    )


def test_static_scaling_and_treatment_preserve_alpha(surface_cache: SurfaceCache) -> None:
    source = surface_cache.scaled("terrain.earth.e", 0.5)
    treated = surface_cache.treated("terrain.earth.e", 0.5, (0.34, 0.38, 0.50))
    assert source.get_size() == treated.get_size() == (128, 128)
    assert pygame.surfarray.array_alpha(source).tolist() == pygame.surfarray.array_alpha(treated).tolist()
    assert surface_cache.treated("terrain.earth.e", 0.5, (0.34, 0.38, 0.50)) is treated


def test_every_bound_static_raster_has_lossless_alpha_cropped_submission(
    surface_cache: SurfaceCache,
) -> None:
    catalog = surface_cache.catalog
    asset_ids = {
        asset_id
        for table_name in (
            "stone_wall_straight",
            "stone_wall_corner",
            "wood_wall_straight",
            "wood_wall_corner",
            "stone_door_frame",
            "wood_door_closed",
            "wood_door_open",
            "items",
        )
        for asset_id in catalog.bindings[table_name].values()
    }
    asset_ids.update(
        asset_id
        for material in ("earth", "wood")
        for asset_id in catalog.bindings["terrain"][material].values()
    )
    multiplier = (0.62, 0.62, 0.62)
    for asset_id in sorted(asset_ids):
        for zoom in ZOOM_LEVELS:
            full = surface_cache.treated(asset_id, zoom, multiplier)
            cropped = surface_cache.cropped_treated(asset_id, zoom, multiplier)
            x, y, width, height = surface_cache.alpha_bounds(asset_id, zoom)
            assert cropped.get_size() == (width, height)
            restored = pygame.Surface(full.get_size(), pygame.SRCALPHA, 32).convert_alpha()
            restored.blit(cropped, (x, y))
            assert np.array_equal(
                pygame.surfarray.array3d(restored),
                pygame.surfarray.array3d(full),
            )
            assert np.array_equal(
                pygame.surfarray.array_alpha(restored),
                pygame.surfarray.array_alpha(full),
            )


def test_cropped_static_submission_is_identical_at_every_viewport_fringe(
    surface_cache: SurfaceCache,
) -> None:
    asset_id = "stone.wall.corner.e"
    zoom = 0.5
    multiplier = (0.65, 0.68, 0.78)
    full = surface_cache.treated(asset_id, zoom, multiplier)
    cropped = surface_cache.cropped_treated(asset_id, zoom, multiplier)
    x, y, _, _ = surface_cache.alpha_bounds(asset_id, zoom)
    viewport = (96, 72)
    placements = (
        (-full.get_width() + 1, 8),
        (viewport[0] - 1, 8),
        (8, -full.get_height() + 1),
        (8, viewport[1] - 1),
    )
    for destination in placements:
        uncropped_canvas = pygame.Surface(viewport, pygame.SRCALPHA, 32).convert_alpha()
        cropped_canvas = pygame.Surface(viewport, pygame.SRCALPHA, 32).convert_alpha()
        uncropped_canvas.blit(full, destination)
        cropped_canvas.blit(cropped, (destination[0] + x, destination[1] + y))
        assert np.array_equal(
            pygame.surfarray.array3d(uncropped_canvas),
            pygame.surfarray.array3d(cropped_canvas),
        )
        assert np.array_equal(
            pygame.surfarray.array_alpha(uncropped_canvas),
            pygame.surfarray.array_alpha(cropped_canvas),
        )


def test_raster_terrain_pose_follows_the_same_four_camera_law(
    surface_cache: SurfaceCache,
) -> None:
    terrain = surface_cache.catalog.bindings["terrain"]
    assert tuple(camera_pose("east", quadrant) for quadrant in range(4)) == (
        "e", "s", "w", "n"
    )
    for material, family in (("earth", "a1"), ("wood", "f1")):
        assert tuple(
            surface_cache.catalog.resources[
                terrain[material][camera_pose("east", quadrant)]
            ].path.name
            for quadrant in range(4)
        ) == tuple(f"ground-{family}-{pose}.png" for pose in ("e", "s", "w", "n"))


@pytest.mark.parametrize("direction", ("north", "east", "south", "west"))
@pytest.mark.parametrize("quadrant", range(4))
@pytest.mark.parametrize("door_table", ("wood_door_closed", "wood_door_open"))
def test_door_frame_and_leaf_share_the_authored_contact_in_every_camera_view(
    surface_cache: SurfaceCache,
    direction: str,
    quadrant: int,
    door_table: str,
) -> None:
    catalog = surface_cache.catalog
    pose = camera_pose(direction, quadrant)
    camera = Camera(
        quadrant=quadrant,
        zoom=1.0,
        viewport=(1600, 1000),
    ).with_focus((31, 31))

    contact = project_screen((31, 31), camera)
    frame_id = catalog.bindings["stone_door_frame"][pose]
    leaf_id = catalog.bindings[door_table][pose]
    frame_destination = surface_cache.blit_position(frame_id, 1.0, contact)
    leaf_destination = surface_cache.blit_position(leaf_id, 1.0, contact)

    assert frame_destination[0] == leaf_destination[0]
    assert frame_destination[1] - leaf_destination[1] in {2, 3}
    canvas = pygame.Surface(camera.viewport, pygame.SRCALPHA, 32).convert_alpha()
    canvas.blit(surface_cache.scaled(frame_id, 1.0), frame_destination)
    canvas.blit(surface_cache.scaled(leaf_id, 1.0), leaf_destination)
    assert pygame.mask.from_surface(canvas, 127).count() > 0


@pytest.mark.parametrize(
    ("time_seconds", "expected"),
    ((-1.0, 0), (0.0, 0), (0.099, 0), (0.1, 1), (1.599, 15), (1.6, 0)),
)
def test_flame_frame_boundaries(time_seconds: float, expected: int) -> None:
    assert flame_frame_index(time_seconds) == expected


@pytest.mark.parametrize(
    ("case", "message"),
    (
        ("unknown_binding", "unknown bound asset"),
        ("escaping_path", "escapes game/assets"),
        ("wrong_dimension", "native_size"),
        ("missing_pose", "four exact poses"),
        ("missing_frame", "16 unique ordered frames"),
    ),
)
def test_catalog_rejects_invalid_direct_data(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    case: str,
    message: str,
) -> None:
    assets = json.loads((assets_module.DATA_ROOT / "assets.json").read_text(encoding="utf-8"))
    bindings = json.loads(
        (assets_module.DATA_ROOT / "world_bindings.json").read_text(encoding="utf-8")
    )
    if case == "unknown_binding":
        bindings["terrain"]["earth"]["e"] = "terrain.unknown"
    elif case == "escaping_path":
        assets["resources"]["terrain.earth.e"]["path"] = "../data/assets.json"
    elif case == "wrong_dimension":
        assets["resources"]["terrain.earth.e"]["native_size"] = [256.5, 256]
    elif case == "missing_pose":
        bindings["stone_wall_straight"].pop("e")
    elif case == "missing_frame":
        assets["animations"]["torch.flame"]["frames"].pop()
    else:
        raise AssertionError(f"unhandled test case {case}")
    (tmp_path / "assets.json").write_text(json.dumps(assets), encoding="utf-8")
    (tmp_path / "world_bindings.json").write_text(json.dumps(bindings), encoding="utf-8")
    monkeypatch.setattr(assets_module, "DATA_ROOT", tmp_path)

    with pytest.raises(ValueError, match=message):
        load_catalog()


def test_catalog_rejects_malformed_json_and_decode_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "assets.json").write_text("{", encoding="utf-8")
    (tmp_path / "world_bindings.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(assets_module, "DATA_ROOT", tmp_path)
    with pytest.raises(ValueError, match="cannot read asset data"):
        load_catalog()

    monkeypatch.setattr(assets_module, "DATA_ROOT", assets_module.PACKAGE_ROOT / "data")
    pygame.init()
    pygame.display.set_mode((1, 1))
    try:
        catalog = load_catalog()

        def fail_decode(_path: Path) -> pygame.Surface:
            raise pygame.error("injected decode failure")

        monkeypatch.setattr(pygame.image, "load", fail_decode)
        with pytest.raises(ValueError, match="cannot decode asset"):
            SurfaceCache(catalog)
    finally:
        pygame.quit()
