"""Draw the known historical encounter through the existing actor/map painter."""

from typing import Mapping
from uuid import UUID

import pygame

from dnd.core.condition_types import ConditionCategory
from game.animation import sample_idle_body
from game.animation_draw import (
    AnimationDrawCommand, BodyRows, LoadedBodyRows, actor_draw_commands, actor_screen_bounds,
    load_actor_media, place_feedback_rect,
)
from game.animation_types import AnimationData
from game.condition_animation import ConditionAppearance, condition_body_pose
from game.condition_draw import load_condition_layers
from dnd.player.facts import PlayerState
from game.projection import Camera, project_screen


from game.body_pose_types import SceneActor


def load_scene_media(actors: tuple[SceneActor, ...], data: AnimationData, *,
                     body_rows: LoadedBodyRows | None = None) -> BodyRows:
    """Preload the displayed standing poses; action heads request their own clips."""
    if body_rows is None:
        body_rows = {}
    load_condition_layers(tuple(layer for actor in actors for layer in actor.condition.layers), body_rows)
    return load_actor_media(data, tuple(
        (actor.contact, actor.layers,
         (condition_body_pose(data, sample_idle_body(data, actor.contact, 0), actor.contact, actor.condition).clip,))
        for actor in actors
    ), body_rows=body_rows, all_facings=True)


def scene_draw_commands(actors: tuple[SceneActor, ...], data: AnimationData,
                        media: BodyRows, camera: Camera, elapsed_ms: float,
                        *, exclude: frozenset[str] = frozenset(),
                        condition_appearances: Mapping[str, ConditionAppearance] | None = None,
                        ) -> tuple[AnimationDrawCommand, ...]:
    return tuple(command for actor in actors if actor.contact.actor_uuid not in exclude
                 for command in actor_draw_commands(
                     data, sample_idle_body(data, actor.contact, elapsed_ms),
                     actor.contact, actor.layers, media, camera,
                     condition=(condition_appearances.get(actor.contact.actor_uuid)
                                if condition_appearances is not None else actor.condition)))


def draw_actor_labels(screen: pygame.Surface, font: pygame.font.Font,
                      actors: tuple[SceneActor, ...], target: PlayerState,
                      camera: Camera, *, shown_hp: Mapping[str, int | None],
                      active_uuid: UUID | None,
                      commands: tuple[AnimationDrawCommand, ...] = (),
                      viewport: pygame.Rect | None = None) -> None:
    viewport = viewport if viewport is not None else screen.get_rect()
    bounds = actor_screen_bounds(commands)
    obstacles = [*bounds.values(), *(command.surface.get_rect(topleft=command.destination)
                 for command in commands if command.role == "floating_number")]
    for view in actors:
        contact = view.contact
        actor = target.actors[UUID(contact.actor_uuid)]
        x, y = project_screen(contact.grid, camera, elevation_steps=contact.elevation_steps)
        hp = shown_hp.get(contact.actor_uuid, actor.normal_hp)
        text = f"{actor.name}  {hp}/{actor.maximum_hp}"
        conditions = tuple(condition.name for condition in actor.conditions
                           if condition.category != ConditionCategory.INTERNAL)
        if conditions:
            text += "  " + ", ".join(conditions)
        color = (255, 223, 125) if actor.uuid == active_uuid else (234, 235, 237)
        label = font.render(text, True, color, (19, 23, 30))
        preferred = label.get_rect(midbottom=(round(x), round(y - 74 * camera.zoom)))
        placed = place_feedback_rect(preferred, bounds.get(contact.actor_uuid), obstacles, viewport)
        screen.blit(label, placed)
        obstacles.append(placed)
