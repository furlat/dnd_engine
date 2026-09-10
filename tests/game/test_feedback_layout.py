"""Authored feedback stays legible without covering visible actor pixels."""

from dataclasses import replace
from typing import Iterator

import pygame
import pytest

from game.animation import ActorContact, BodySample, NumberSample
from game.animation_data import load_animation_data
from game.animation_draw import (
    BodyRows, actor_draw_commands, actor_screen_bounds, arrange_feedback_commands,
    load_actor_media, number_draw_commands,
)
from game.animation_types import AnimationData, RigLayer
from game.projection import Camera


@pytest.fixture(scope="module")
def media() -> Iterator[tuple[AnimationData, BodyRows, pygame.font.Font, pygame.font.Font]]:
    with pytest.MonkeyPatch.context() as environment:
        environment.setenv("SDL_VIDEODRIVER", "dummy")
        environment.setenv("SDL_AUDIODRIVER", "dummy")
        pygame.init()
        pygame.display.set_mode((720, 480))
        data = load_animation_data()
        actor = ActorContact("actor", (6, 6), "E", .5)
        rows = load_actor_media(data, ((actor, (RigLayer("body", "NakedBody"), RigLayer("head", "Head22")), ("Idle",)),))
        fonts = tuple(pygame.font.SysFont(style.fontFamily, round(style.fontSizePx), bold=style.fontWeight == "bold")
                      for style in (data.number_style, data.badge_style))
        try:
            yield data, rows, fonts[0], fonts[1]
        finally:
            pygame.quit()


@pytest.mark.parametrize(("quadrant", "actor_top", "actor_x", "below"), [
    (0, 230, 40, False), (1, 54, 40, True),
    (2, 230, 680, False), (3, 54, 680, True),
])
def test_all_feedback_avoids_bodies_and_each_other_at_screen_edges(
    media: tuple[AnimationData, BodyRows, pygame.font.Font, pygame.font.Font],
    quadrant: int, actor_top: int, actor_x: int, below: bool,
) -> None:
    data, rows, font, badge_font = media
    actor = ActorContact("actor", (6, 6), "E", .5)
    neighbor = replace(actor, actor_uuid="neighbor", grid=(6.5, 6))
    layers = (RigLayer("body", "NakedBody"), RigLayer("head", "Head22"))
    camera = Camera(quadrant=quadrant, zoom=1, viewport=(720, 480)).with_focus(actor.grid)
    body = BodySample(actor.actor_uuid, "Idle", 0, "E")
    initial = actor_draw_commands(data, body, actor, layers, rows, camera)
    original_bounds = actor_screen_bounds(initial)[actor.actor_uuid]
    camera = camera.with_screen_pan((actor_x - original_bounds.centerx, actor_top - original_bounds.top))
    bodies = (*actor_draw_commands(data, body, actor, layers, rows, camera),
              *actor_draw_commands(data, replace(body, actor_uuid=neighbor.actor_uuid), neighbor, layers, rows, camera))
    bounds = actor_screen_bounds(bodies)
    # Cropped alpha bounds belong to visible art, not the 128px sprite canvas.
    canvas = bodies[0][1].get_rect(topleft=bodies[0][2])
    assert bounds[actor.actor_uuid].height < canvas.height
    numbers = (
        NumberSample(actor.actor_uuid, 7, "Slashing", 0xFF3030, 0, 1),
        NumberSample(actor.actor_uuid, None, "+Paralyzed", 0xEDDC88, .1, .8, kind="badge"),
        NumberSample(actor.actor_uuid, None, "Reaction: Opportunity Attack", 0xF0E080, 0, 1, kind="badge"),
    )
    feedback = number_draw_commands(data, numbers, {actor.actor_uuid: actor}, font, camera, badge_font=badge_font)
    viewport = pygame.Rect(16, 44, 688, 420)
    commands = arrange_feedback_commands((*bodies, *feedback), bounds, viewport)
    assert commands[:len(bodies)] == bodies
    placed = commands[len(bodies):]
    occupied = list(bounds.values())
    for original, command in zip(feedback, placed, strict=True):
        rect = command[1].get_rect(topleft=command[2])
        assert viewport.contains(rect)
        assert not any(rect.colliderect(obstacle) for obstacle in occupied)
        occupied.append(rect)
        if below:
            assert rect.top >= bounds[actor.actor_uuid].bottom
        else:
            assert rect.bottom <= bounds[actor.actor_uuid].top
        # Position alone changes. Exact authored glyph pixels, global opacity,
        # depth, value, label, progress and application metadata survive.
        assert command[1] is original[1]
        assert (command[0], command[3], command[4]) == (original[0], original[3], original[4])
    assert arrange_feedback_commands((*bodies, *feedback), bounds, viewport) == commands
