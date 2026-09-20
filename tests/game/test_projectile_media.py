"""Authored phase samples retain their pixels with bounded decoded storage."""

from dataclasses import replace
from pathlib import Path
from types import MappingProxyType

import pygame
import pytest

from game.animation import ActorContact, CastApplication, CastInput, ProjectileSample, compile_cast
from game.animation_data import load_animation_data
from game.animation_draw import AnimationMedia, projectile_layer_blits
from game.animation_types import (
    AuthoredProjectilePhase, AuthoredProjectilePhases, ProjectileFrameLayer,
    ProjectileFrameStorage, ProjectileStorage,
)
from game.projectile_media import ProjectileFrameCache, frame_cache_usage, projectile_frame_layers
from game.projection import Camera


@pytest.fixture(scope="module", autouse=True)
def display():
    with pytest.MonkeyPatch.context() as environment:
        environment.setenv("SDL_VIDEODRIVER", "dummy")
        environment.setenv("SDL_AUDIODRIVER", "dummy")
        pygame.init()
        pygame.display.set_mode((8, 8))
        yield
        pygame.quit()


@pytest.fixture(scope="module")
def original_data():
    return load_animation_data(authored_bundles=())


def sample_data(original_data, root: Path, *, layered: bool = False):
    """Small pixels, using the actual recovered Eldritch phase addresses."""
    recipe = original_data.drafts["spell.fire_bolt"]
    visual = recipe.projectile.sprite.model_copy(update={"tint": 0xFFFFFF, "alpha": 1.0})
    original = original_data.projectile_assets[visual.assetId]
    asset = original.model_copy(update={
        "frame": original.frame.model_copy(update={"width": 2, "height": 2, "cols": 332}),
        "phases": AuthoredProjectilePhases(
            cast=AuthoredProjectilePhase(start=260, frames=72, fps=144, loop=False),
            travel=AuthoredProjectilePhase(start=0, frames=144, fps=144, loop=True),
            impact=AuthoredProjectilePhase(start=144, frames=116, fps=144, loop=False),
        ),
    })
    storage = ProjectileStorage(phases={phase: ProjectileFrameStorage(layers=(
        (ProjectileFrameLayer(pattern=f"{phase}/smoke/{{direction}}/{{frame:02}}.png", blendMode="normal"),
         ProjectileFrameLayer(pattern=f"{phase}/fire/{{direction}}/{{frame:02}}.png", blendMode="add"))
        if layered else
        (ProjectileFrameLayer(pattern=f"{phase}/{{direction}}/{{frame:02}}.png", blendMode="normal"),)
    )) for phase in ("cast", "travel", "impact")})
    data = replace(original_data, media_root=root,
                   projectile_assets=MappingProxyType({**original_data.projectile_assets, asset.assetId: asset}),
                   projectile_storage=MappingProxyType({asset.assetId: storage}))
    return data, asset, visual


def save_frame(path: Path, color: tuple[int, int, int, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = pygame.Surface((2, 2), pygame.SRCALPHA)
    image.fill(color)
    pygame.image.save(image, path)


@pytest.mark.parametrize("phase, column, frame", [
    ("prepare", 331, 71), ("travel", 143, 143), ("impact", 259, 115),
])
@pytest.mark.parametrize("direction", ["E", "NW"])
def test_final_phase_sample_uses_local_frame_and_selected_direction(
    original_data, tmp_path, phase, column, frame, direction,
):
    data, asset, _ = sample_data(original_data, tmp_path)
    stored_phase = "cast" if phase == "prepare" else phase
    color = (31, 82, 147, 193)
    save_frame(tmp_path / stored_phase / direction / f"{frame:02}.png", color)
    source = CastInput("phase-sample", ActorContact("caster", (0, 0), "E", 0.5), (
        CastApplication("hit", ActorContact("target", (3, -3), "W", 0.5), False, None, None),
    ))
    timeline = compile_cast(data, "spell.fire_bolt", source)
    # Only this frame exists. Other directions, phases and the giant atlas
    # must remain unnecessary for drawing the requested sample.
    effect = ProjectileSample("hit", phase, asset.assetId, column,
                              asset.rowOrder.index(direction), (0, 0), 0, 0)
    media = AnimationMedia({}, {}, {}, pygame.font.Font(None, 12))
    layer, = projectile_layer_blits(timeline, effect, media, Camera())
    assert tuple(layer[0].get_at((0, 0))) == color
    assert layer[2] == 0


def test_smoke_and_fire_keep_order_alpha_and_shared_cached_pixels(original_data, tmp_path):
    data, asset, visual = sample_data(original_data, tmp_path, layered=True)
    smoke, fire = (tmp_path / "impact" / layer / "E" / "00.png" for layer in ("smoke", "fire"))
    save_frame(smoke, (100, 80, 60, 128))
    save_frame(fire, (200, 100, 20, 128))
    cache = ProjectileFrameCache(limit_bytes=32)
    layers = projectile_frame_layers(data, asset, "impact", 0, "E", visual, {}, cache=cache)
    output = pygame.Surface((2, 2))
    output.fill((0, 0, 0))
    for layer in layers:
        output.blit(layer.image, (0, 0), special_flags=layer.blend)
    assert tuple(output.get_at((0, 0)))[:3] == (150, 90, 40)
    assert layers[0].image.get_at((0, 0)).a == 128
    assert frame_cache_usage(cache).decoded_bytes == 32
    # A second timeline can keep rendering retained frames without reopening
    # files or storing a second copy of the same smoke/fire sources.
    smoke.unlink()
    fire.unlink()
    again = projectile_frame_layers(replace(data), asset, "impact", 0, "E", visual, {}, cache=cache)
    assert [pygame.image.tobytes(layer.image, "RGBA") for layer in again] == [
        pygame.image.tobytes(layer.image, "RGBA") for layer in layers]
    assert frame_cache_usage(cache).decoded_bytes == 32


def test_evicted_samples_seek_back_identically_within_decoded_byte_limit(original_data, tmp_path):
    data, asset, visual = sample_data(original_data, tmp_path)
    colors = ((22, 10, 9, 255), (54, 22, 18, 255), (85, 40, 31, 128), (112, 91, 47, 64))
    for frame, color in enumerate(colors):
        save_frame(tmp_path / "impact" / "E" / f"{frame:02}.png", color)
    cache = ProjectileFrameCache(limit_bytes=32)
    for frame in (0, 1, 2, 3, 0, 2):
        layer, = projectile_frame_layers(data, asset, "impact", frame, "E", visual, {}, cache=cache)
        assert tuple(layer.image.get_at((0, 0))) == colors[frame]
        usage = frame_cache_usage(cache)
        assert usage.decoded_bytes <= usage.limit_bytes == 32


def test_missing_fire_does_not_return_an_incomplete_smoke_only_sample(original_data, tmp_path):
    data, asset, visual = sample_data(original_data, tmp_path, layered=True)
    save_frame(tmp_path / "impact/smoke/E/00.png", (100, 80, 60, 128))
    with pytest.raises(FileNotFoundError):
        projectile_frame_layers(data, asset, "impact", 0, "E", visual, {}, cache=ProjectileFrameCache())
