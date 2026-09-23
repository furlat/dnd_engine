"""Liquid media preserves sampled RGBA, world registration and raw XY ownership."""

from dataclasses import replace
import json
from math import pi
from pathlib import Path
from typing import Iterator

import numpy as np
import pygame
import pytest

from devtools.import_liquid_media import CAMERA_ROWS, import_bundle
from game.animation_data import load_animation_data
from game.animation_types import AnimationData, AuthoredProjectileAsset, ProjectileStorage
from game.projectile_media import ProjectileFrameCache, projectile_frame_layers
from game.projection import project_world
from game.registered_media import registered_material, registered_media_blits, registered_media_samples


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


@pytest.fixture(scope="module", autouse=True)
def display() -> Iterator[None]:
    with pytest.MonkeyPatch.context() as environment:
        environment.setenv("SDL_VIDEODRIVER", "dummy")
        environment.setenv("SDL_AUDIODRIVER", "dummy")
        pygame.init()
        pygame.display.set_mode((32, 32))
        yield
        pygame.quit()


@pytest.fixture(scope="module")
def original() -> AnimationData:
    return load_animation_data(authored_bundles=())


@pytest.fixture
def source(tmp_path: Path) -> Path:
    root = tmp_path / "source"
    root.mkdir()
    views = {}
    # Exercise BA's zero and 255 low bytes: neither means transparent data.
    positions = ((0, 255, 1, 0), (128, 1, 255, 255),
                 (255, 255, 0, 255), (7, 11, 128, 0))
    for quadrant in range(4):
        streams = {}
        origin = project_world((0, 0), quadrant=quadrant)
        basis = {axis: [(value - origin[i]) / 2 for i, value in enumerate(
            project_world(point, quadrant=quadrant))] for axis, point in (("X", (1, 0)), ("Z", (0, 1)))}
        for channel in ("floor", "air", "position"):
            page = pygame.Surface((128, 144), pygame.SRCALPHA)
            rects = []
            for frame in range(1152):
                if (channel == "floor" and frame == 0) or (channel != "floor" and frame >= 68):
                    rects.append(None)
                    continue
                left, top = (frame % 32) * 4, (frame // 32) * 4
                for x in range(2):
                    for y in range(2):
                        color = positions[x * 2 + y] if channel == "position" else (
                            quadrant * 30 + x + 11, frame % 251, y + 71, 99 + x * 70 + y * 21)
                        page.set_at((left + x, top + y), color)
                rects.append({"page": 0, "source": [left, top, 2, 2], "offset": [-3 + frame % 2, -5]})
            name = f"view{quadrant}-{channel}.png"
            pygame.image.save(page, root / name)
            streams[channel] = {"pages": [name], "rects": rects}
        views[f"unrelated-label-{3-quadrant}"] = {"groundBasis": basis, "streams": streams}
    write_json(root / "media.json", {"fps": 144, "frames": 1152, "loop": [864, 1152],
        "pivot": [192, 192], "worldBounds": [-2, 2], "views": views})
    return root


def imported_data(source: Path, repo: Path, original: AnimationData) -> AnimationData:
    import_bundle(source, material="water", variant=0, palette=(0x293F49, 0x617F86, 0xA1B2AB), repo=repo)
    folder = repo / "game/data/liquid_media"
    assets = {row["assetId"]: AuthoredProjectileAsset.model_validate_json(json.dumps(row))
              for row in json.loads((folder / "projectile-assets.json").read_text())}
    storage = {name: ProjectileStorage.model_validate_json(json.dumps(value)) for name, value in json.loads(
        (folder / "bindings.json").read_text())["projectileStorage"].items()}
    return replace(original, media_root=repo, projectile_assets=assets, projectile_storage=storage)


def test_import_is_explicit_preserves_other_assets_and_does_not_author_behavior(source: Path, tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    folder = repo / "game/data/liquid_media"
    write_json(folder / "bindings.json", {"resources": {"old": "old.png"},
        "projectileStorage": {"old": {"retained": True}}})
    write_json(folder / "projectile-assets.json", [{"assetId": "old", "retained": True}])
    recipe = repo / "game/data/world_bindings.json"
    write_json(recipe, {"liquid_media": {"existing-authored-behavior": True}})
    before = recipe.read_bytes()
    first = import_bundle(source, material="water", variant=0, palette=(0x293F49,), repo=repo)
    assert len(first) == 4
    assert import_bundle(source, material="water", variant=0, palette=(0x293F49,), repo=repo) == first
    assert recipe.read_bytes() == before
    bindings = json.loads((folder / "bindings.json").read_text())
    assert bindings["resources"] == {"old": "old.png"}
    assert bindings["projectileStorage"]["old"] == {"retained": True}
    assert json.loads((folder / "projectile-assets.json").read_text())[0] == {"assetId": "old", "retained": True}
    assert not (folder / "spell-studio-drafts.json").exists()


def test_sampled_phase_windows_keep_pixels_empty_air_and_four_camera_registration(
    source: Path, tmp_path: Path, original: AnimationData,
) -> None:
    data = imported_data(source, tmp_path / "repo", original)
    raw = json.loads((source / "media.json").read_text())
    cache = ProjectileFrameCache()
    anchor = (121., 99.)
    for quadrant, facing in enumerate(CAMERA_ROWS):
        view = raw["views"][f"unrelated-label-{3-quadrant}"]
        for channel in ("floor", "air"):
            for phase, first, count in (("application", 0, 864), ("sustain", 864, 288)):
                identity = f"liquid.water.s0.{channel}.{phase}"
                asset = data.projectile_assets[identity]
                assert asset.phases.impact is not None and asset.phases.impact.frames == count
                for local in (0, 1, count - 1):
                    address = view["streams"][channel]["rects"][first + local]
                    layers = projectile_frame_layers(data, asset, "impact", local, facing,
                        registered_material(identity, 1), {}, cache=cache)
                    samples = registered_media_samples(data, identity, "impact", local, facing,
                        scale=2, anchor=anchor, rows={})
                    if address is None:
                        assert layers == samples == ()
                        continue
                    expected = pygame.image.load(source / view["streams"][channel]["pages"][0]).subsurface(address["source"])
                    assert pygame.image.tobytes(layers[0].image, "RGBA") == pygame.image.tobytes(expected, "RGBA")
                    sample, = samples
                    assert sample.destination == tuple(round(anchor[i] + address["offset"][i] * 2) for i in range(2))
                    assert pygame.image.tobytes(sample.image, "RGBA") == pygame.image.tobytes(pygame.transform.scale(expected, (4, 4)), "RGBA")
                    assert (sample.footpoints is None) == (channel == "floor")
                    legacy, = registered_media_blits(data, identity, "impact", local, facing, scale=2, anchor=anchor, rows={})
                    assert legacy[1:] == (sample.destination, sample.blend)
                    assert pygame.image.tobytes(legacy[0], "RGBA") == pygame.image.tobytes(sample.image, "RGBA")


@pytest.mark.parametrize("scale,rotation", ((1., 0.), (1.35, 0.), (2., pi / 2), (.7, -.35)))
def test_footpoint_low_bytes_are_data_and_follow_the_exact_color_pixel_transform(
    source: Path, tmp_path: Path, original: AnimationData, scale: float, rotation: float,
) -> None:
    data = imported_data(source, tmp_path / "repo", original)
    identity = "liquid.water.s0.air.application"
    sample, = registered_media_samples(data, identity, "impact", 0, "E",
        scale=scale, anchor=(40., 70.), rows={}, alpha=.4, rotation=rotation)
    assert sample.footpoints is not None
    raw = pygame.image.load(source / "view0-position.png").subsurface((0, 0, 2, 2)).copy()
    if rotation:
        size = max(1, round(2 * scale)), max(1, round(2 * scale))
    else:
        size = (round(40 - scale) - round(40 - 3 * scale),
                round(70 - 3 * scale) - round(70 - 5 * scale))
    expected = pygame.transform.rotate(pygame.transform.scale(raw, size), -rotation * 180 / pi)
    rgb, alpha = pygame.surfarray.array3d(expected).astype(np.uint16), pygame.surfarray.array_alpha(expected).astype(np.uint16)
    coordinates = np.stack((-2 + (rgb[:, :, 0] * 256 + rgb[:, :, 1]).astype(float) * 4 / 65535,
                            -2 + (rgb[:, :, 2] * 256 + alpha).astype(float) * 4 / 65535), axis=2)
    np.testing.assert_allclose(sample.footpoints, coordinates, atol=3e-7, rtol=0)
    assert sample.footpoints.shape == (*sample.image.size, 2)
    assert not sample.footpoints.flags.writeable
    assert pygame.surfarray.array_alpha(sample.image).any()
