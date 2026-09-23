"""Exact authored formation/hold and registered clear coverage preserve phase."""

from dataclasses import replace

import pygame
import pytest

from game.animation_data import load_animation_data
from game.condition_draw import compose_condition_layers
from game.condition_media import ConditionLayerMedia, ResolvedConditionLayer
from game.condition_sampling import sample_condition_media
from game.condition_types import ConditionColors, ConditionLayer


@pytest.fixture(scope="module")
def data():
    pygame.init()
    pygame.display.set_mode((1, 1))
    yield load_animation_data()
    pygame.quit()


def shield(side):
    layer = ConditionLayer(id=side, assetId="shell", category="shield", animation="loop", fps=144.,
        attachment="body", activeDuring=("idle",), priority=0,
        colors=ConditionColors(primary=0xFFFFFF, secondary=0xFFFFFF, tertiary=0xFFFFFF),
        drawOrder="behind_body" if side == "back" else "in_front_of_body")
    media = ConditionLayerMedia("shield", "loop", asset_id=f"persistent.shield.{side}.hold",
        application_asset_id=f"persistent.shield.{side}.apply", application_mode="sequence",
        removal_mask_asset_id=f"persistent.shield.{side}.clear_mask", world_basis="E")
    return ResolvedConditionLayer(layer, media, application=True)


@pytest.mark.parametrize("side", ("back", "front"))
def test_exact_formation_seam_and_clear_do_not_restart_current_hold(data, side):
    resolved = shield(side)
    for age, phase, frame in ((0., "apply", 0), (999., "apply", 143),
                              (1000., "hold", 0), (1250., "hold", 36), (13500., "hold", 0)):
        sample, = sample_condition_media(data, replace(resolved, age_ms=age))
        assert sample.asset_id == f"persistent.shield.{side}.{phase}"
        assert sample.frame == frame and sample.alpha == 1. and sample.removal_mask is None
    for age in (0., 125., 500.):
        continued, = sample_condition_media(data, replace(resolved, age_ms=4000 + age, removal_age_ms=age))
        ordinary, = sample_condition_media(data, replace(resolved, age_ms=4000 + age))
        assert (continued.asset_id, continued.frame, continued.alpha) == (ordinary.asset_id, ordinary.frame, ordinary.alpha)
        assert continued.removal_mask == (f"persistent.shield.{side}.clear_mask", int(age * .144))
    assert not sample_condition_media(data, replace(resolved, age_ms=5000., removal_age_ms=87 * 1000 / 144))
    cold, = sample_condition_media(data, replace(resolved, age_ms=1250., application=False))
    assert cold.asset_id.endswith(".hold") and cold.frame == 180


@pytest.mark.parametrize("quadrant", range(4))
def test_registered_clear_masks_only_existing_shell_pixels_and_replays_exactly(data, quadrant):
    empty = pygame.Surface((1, 1), pygame.SRCALPHA)

    def pixels(layer):
        image, point = compose_condition_layers(empty, (256, 256), (256., 256.), "E", 1., 1.,
            (layer,), {}, data=data, quadrant=quadrant)
        canvas = pygame.Surface((512, 512), pygame.SRCALPHA)
        canvas.blit(image, point)
        return pygame.surfarray.array_alpha(canvas), pygame.image.tobytes(canvas, "RGBA")

    for side in ("back", "front"):
        resolved = shield(side)
        decreased = False
        for age in (0., 125., 300., 500.):
            ordinary, _ = pixels(replace(resolved, age_ms=4000 + age))
            faded, encoded = pixels(replace(resolved, age_ms=4000 + age, removal_age_ms=age))
            assert (faded <= ordinary).all(), "Coverage cannot add pixels outside the ongoing registered shell"
            decreased |= bool((faded < ordinary).any())
            assert pixels(replace(resolved, age_ms=4000 + age, removal_age_ms=age))[1] == encoded
        assert decreased
        gone, _ = pixels(replace(resolved, age_ms=5000., removal_age_ms=700.))
        assert not gone.any()
