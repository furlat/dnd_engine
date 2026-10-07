"""Resolve observer-permitted scene actors without loading raster resources."""

from typing import Mapping

from dnd.core.life_types import RemainsDisposition
from game.animation_data import resolve_player_layers
from game.animation_types import AnimationData, Facing8
from game.body_pose_types import SceneActor
from game.combat import actor_contact, actor_is_visible
from game.condition_animation import resolve_condition_appearance
from dnd.player.facts import PlayerState
from game.visual_position import VisualPosition, placed_contact


def scene_actors(target: PlayerState, data: AnimationData,
                 facings: Mapping[str, Facing8],
                 positions: Mapping[str, VisualPosition] | None = None) -> tuple[SceneActor, ...]:
    """Current visual contacts and witnessed corpses; no stale living positions."""
    if target.senses is None:
        return ()
    result = []
    for actor in target.actors.values():
        if not actor_is_visible(target, actor) or actor.remains_disposition is RemainsDisposition.DISINTEGRATED:
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
