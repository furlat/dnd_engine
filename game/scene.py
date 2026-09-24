"""Draw the known historical encounter through the existing actor/map painter."""

from typing import Mapping
from uuid import UUID

import pygame

from dnd.core.life_types import LifeState
from dnd.core.condition_types import ConditionCategory
from game.animation import actor_rest_pose, sample_idle_body
from game.animation_data import resolve_player_layers
from game.animation_draw import (
    AnimationDrawCommand, BodyRows, LoadedBodyRows, actor_draw_commands, actor_screen_bounds,
    load_actor_media, place_feedback_rect,
)
from game.animation_types import AnimationData, Facing8
from game.combat import actor_contact
from game.condition_animation import ConditionAppearance, resolve_condition_appearance
from game.condition_draw import load_condition_layers
from game.player_facts import PlayerState
from game.projection import Camera, project_screen
from game.visual_position import VisualPosition, placed_contact


from game.body_pose_types import SceneActor as SceneActor


def scene_actors(target: PlayerState, data: AnimationData,
                 facings: Mapping[str, Facing8],
                 positions: Mapping[str, VisualPosition] | None = None) -> tuple[SceneActor, ...]:
    """Current visual contacts and witnessed corpses; no stale living positions."""
    if target.senses is None:
        return ()
    result = []
    for actor in target.actors.values():
        perceived = target.senses.entities.get(actor.uuid)
        if (actor.uuid != target.observer_uuid and (perceived is None or not perceived.visual)
                and not (actor.life_state == LifeState.DEAD and actor.last_visual_position is not None)):
            continue
        contact = actor_contact(target, actor, data, facings.get(str(actor.uuid), "S"))
        position = positions.get(contact.actor_uuid) if positions else None
        contact = placed_contact(contact, position)
        layers = resolve_player_layers(data, actor, rig_id=contact.rig_id)
        result.append(SceneActor(contact, layers,
            resolve_condition_appearance(actor.conditions, data.condition_recipes, data.condition_media)))
    return tuple(result)


def available_clips(actor: SceneActor, data: AnimationData) -> tuple[str, ...]:
    rig = data.rigs[actor.contact.rig_id]
    return tuple(name for name, clip in rig.clips.items()
                 if all(layer.category in clip.sheets and clip.sheets[layer.category] in data.resources
                        for layer in actor.layers))


def load_scene_media(actors: tuple[SceneActor, ...], data: AnimationData, *,
                     body_rows: LoadedBodyRows | None = None) -> BodyRows:
    """Preload the displayed standing poses; action heads request their own clips."""
    if body_rows is None:
        body_rows = {}
    load_condition_layers(tuple(layer for actor in actors for layer in actor.condition.layers), body_rows)
    return load_actor_media(data, tuple(
        (actor.contact, actor.layers,
         (actor_rest_pose(data, actor.contact) or "Idle",))
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
