"""Selected spell recipes reach the delivered dense frames through live media."""

from dataclasses import replace
from math import cos, hypot, sin

import pygame
import pytest

from game.animation import (
    ActorContact, CastApplication, CastInput, GroundContact, cast_deliveries,
    compile_cast, project_projectile, sample_cast,
)
from game.animation_data import load_animation_data
from game.animation_draw import AnimationMedia, projectile_layer_blits
from game.projectile_media import ProjectileFrameCache, frame_cache_usage, projectile_frame_layers
from game.projection import Camera


@pytest.fixture(scope="module")
def imported_media():
    with pytest.MonkeyPatch.context() as environment:
        environment.setenv("SDL_VIDEODRIVER", "dummy")
        environment.setenv("SDL_AUDIODRIVER", "dummy")
        pygame.init()
        pygame.display.set_mode((8, 8))
        yield load_animation_data()
        pygame.quit()


@pytest.mark.parametrize("spell,phase_counts", [
    ("acid_splash", {"travel": (12, 24), "impact": (115, 144)}),
    ("guiding_bolt", {"travel": (12, 24), "impact": (63, 144)}),
    ("eldritch_blast", {"prepare": (72, 144), "travel": (144, 144), "impact": (116, 144)}),
    ("fireball", {"travel": (12, 24), "impact": (48, 24)}),
])
def test_selected_cast_reaches_dense_phase_frames_and_layered_fireball(imported_media, spell, phase_counts):
    data = imported_media
    source = CastInput(
        "selected-media", ActorContact("caster", (0, 0), "E", 0.9),
        () if spell == "fireball" else (
            CastApplication("hit", ActorContact("target", (4, -4), "W", 0.9), False, None, None),),
        GroundContact((4, -4)) if spell == "fireball" else None,
    )
    timeline = compile_cast(data, "spell." + spell, source)
    delivery, = cast_deliveries(timeline)
    assert {row.name: (row.phase.frames, row.fps) for row in delivery.projectile_intervals} == phase_counts
    assert timeline.recipe.projectile is not None
    sprite = timeline.recipe.projectile.sprite
    assert sprite is not None
    cache = ProjectileFrameCache(limit_bytes=40 * 1024 * 1024)
    for interval in delivery.projectile_intervals:
        phase = "cast" if interval.name == "prepare" else interval.name
        for direction in ("E", "NW"):
            for frame in (0, interval.phase.frames - 1):
                layers = projectile_frame_layers(data, interval.asset, phase, frame, direction, sprite, {}, cache=cache)
                for layer in layers:
                    if layer.positions is None:
                        assert layer.image.get_size() == (interval.asset.frame.width, interval.asset.frame.height)
                        continue
                    # Cropped packets retain their position in the authored
                    # canvas, and color/XYZ/ownership must remain one raster.
                    width, height = layer.image.get_size()
                    assert 0 < width <= interval.asset.frame.width
                    assert 0 < height <= interval.asset.frame.height
                    assert 0 <= layer.offset[0] <= interval.asset.frame.width - width
                    assert 0 <= layer.offset[1] <= interval.asset.frame.height - height
                    assert layer.positions.coordinates.shape == (width, height, 3)
                    assert layer.positions.ownership.shape == (width, height)
                if spell == "fireball" and phase == "impact":
                    assert all(layer.positions is not None for layer in layers)
                    assert layers[0].offset == layers[1].offset
                    assert layers[0].image.get_size() == layers[1].image.get_size()
                assert [layer.blend for layer in layers] == (
                    [0, pygame.BLEND_RGB_ADD] if spell == "fireball" and phase == "impact" else [pygame.BLEND_RGB_ADD])
                assert frame_cache_usage(cache).decoded_bytes <= cache.limit_bytes


@pytest.mark.parametrize("spell", ("eldritch_blast", "guiding_bolt", "acid_splash"))
@pytest.mark.parametrize("quadrant", range(4))
@pytest.mark.parametrize("target_grid,target_height", (((6, -2), 0), ((3, -3), 0), ((6, -2), 2)))
def test_selected_point_art_aims_along_actual_hand_to_body_path(
    imported_media, spell, quadrant, target_grid, target_height,
):
    """Eight authored rows need the original residual turn, including socket offsets."""
    data = imported_media
    timeline = compile_cast(data, "spell." + spell, CastInput(
        "off-axis", ActorContact("caster", (0, 0), "E", .9), (
            CastApplication("beam", ActorContact("target", target_grid, "W", .9,
                                                 elevation_steps=target_height), False, None, None),
    )))
    travel = next(row for row in timeline.applications[0].projectile_intervals if row.name == "travel")
    views = []
    for progress in (.25, .75):
        sample = sample_cast(timeline, travel.start_ms + progress * (travel.end_ms - travel.start_ms))
        effect = next(row for row in sample.projectiles if row.phase == "travel")
        views.append(project_projectile(timeline, effect, quadrant))
    first, last = views
    # Original NeuroClient FACING_GRID_VECTOR projected into its 2:1 screen plane.
    authored_axes = {"E": (1, 0), "SE": (1, .5), "S": (0, 1), "SW": (-1, .5),
                     "W": (-1, 0), "NW": (-1, -.5), "N": (0, -1), "NE": (1, -.5)}
    row = data.projectile_assets[first.asset_id].rowOrder[first.row]
    x, y = authored_axes[row]
    angle = first.rotation_radians
    aimed = (x * cos(angle) - y * sin(angle), x * sin(angle) + y * cos(angle))
    path = (last.point[0] - first.point[0], last.point[1] - first.point[1])
    length = hypot(*path) * hypot(*aimed)
    assert (aimed[0] * path[1] - aimed[1] * path[0]) / length == pytest.approx(0, abs=1e-10)
    assert (aimed[0] * path[0] + aimed[1] * path[1]) / length == pytest.approx(1)
    impact = next(row for row in sample_cast(timeline, travel.end_ms).projectiles if row.phase == "impact")
    impact = project_projectile(timeline, impact, quadrant)
    assert impact.row == first.row
    assert impact.rotation_radians == pytest.approx(first.rotation_radians)


def test_fireball_travel_is_twice_as_fast_and_twenty_percent_larger_without_resizing_blast(imported_media):
    data = imported_media
    recipe = data.drafts["spell.fireball"]
    projectile = recipe.projectile
    assert projectile is not None
    prior = recipe.model_copy(update={"projectile": projectile.model_copy(update={
        "speedPxPerSecond": 180,
        "travel": projectile.travel.model_copy(update={"scale": None}),
    })})
    previous_data = replace(data, drafts={**data.drafts, "spell.fireball": prior})
    source = CastInput("phase-size", ActorContact("caster", (0, 0), "E", .9), (), GroundContact((6, -2)))
    old = compile_cast(previous_data, "spell.fireball", source)
    new = compile_cast(data, "spell.fireball", source)
    assert old.ground_delivery is not None and new.ground_delivery is not None
    assert new.ground_delivery.travel_end_ms - new.release_ms == pytest.approx(
        (old.ground_delivery.travel_end_ms - old.release_ms) / 2)
    camera = Camera(zoom=1)
    media = AnimationMedia({}, {}, {}, pygame.font.Font(None, 12))
    for phase in ("travel", "impact"):
        rendered = []
        for timeline in (old, new):
            assert timeline.ground_delivery is not None
            interval = next(row for row in timeline.ground_delivery.projectile_intervals if row.name == phase)
            effect = next(row for row in sample_cast(timeline, interval.start_ms).projectiles if row.phase == phase)
            effect = project_projectile(timeline, effect, 0)
            rendered.append(projectile_layer_blits(timeline, effect, media, camera))
        assert len(rendered[0]) == len(rendered[1])
        for (first, first_at, blend), (last, last_at, last_blend) in zip(*rendered):
            factor = 1.2 if phase == "travel" else 1
            assert last.get_size() == tuple(round(value * factor) for value in first.get_size())
            assert (last_at[0] + last.width / 2, last_at[1] + last.height / 2) == pytest.approx(
                (first_at[0] + first.width / 2, first_at[1] + first.height / 2), abs=.5)
            assert blend == last_blend
