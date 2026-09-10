"""Pygame adapter for the shared action/child group, including movement holds."""

from dataclasses import dataclass
from typing import Mapping
from uuid import UUID

import pygame

from game.animation import ActorContact, CastSample
from game.animation_draw import (
    AnimationDrawCommand, AnimationMedia, BodyRows, animation_draw_commands,
    attack_draw_commands, load_animation_media, load_attack_media, number_draw_commands,
)
from game.animation_types import AnimationData
from game.attack import AttackSample, BoundAttack
from game.choreography import BoundChoreography, ChoreographySample
from game.combat import BoundCast
from game.condition_animation import ConditionAppearance
from game.projection import Camera


@dataclass(frozen=True, slots=True)
class ChoreographyMedia:
    attacks: Mapping[UUID, BodyRows]
    casts: Mapping[UUID, AnimationMedia]


def load_choreography_media(bound: BoundChoreography) -> ChoreographyMedia:
    attacks: dict[UUID, BodyRows] = {}
    casts: dict[UUID, AnimationMedia] = {}
    for node in bound.nodes:
        if isinstance(node.bound, BoundAttack):
            attacks[node.event_uuid] = load_attack_media(node.bound.timeline, node.bound.appearances)
        else:
            casts[node.event_uuid] = load_animation_media(node.bound.timeline, node.bound.appearances)
    return ChoreographyMedia(attacks, casts)


def choreography_draw_commands(bound: BoundChoreography, sample: ChoreographySample,
                               media: ChoreographyMedia, data: AnimationData,
                               contacts: Mapping[str, ActorContact], font: pygame.font.Font,
                               badge_font: pygame.font.Font, camera: Camera, *,
                               condition_appearances: Mapping[str, ConditionAppearance] | None = None,
                               ) -> tuple[AnimationDrawCommand, ...]:
    commands: list[tuple[int, AnimationDrawCommand]] = []
    # There is one displayed body per actor. A child's active gesture replaces
    # the parent's idle sample; concurrent projectile and feedback tracks survive.
    owners: dict[str, tuple[bool, float, int]] = {}
    for index, entry in enumerate(sample.clips):
        node, current = entry.node, entry.sample
        if isinstance(node.bound, BoundAttack) and isinstance(current, AttackSample):
            drawn = attack_draw_commands(node.bound.timeline, current, node.bound.appearances,
                media.attacks[node.event_uuid], font, badge_font, camera,
                condition_appearances=condition_appearances)
        elif isinstance(node.bound, BoundCast) and isinstance(current, CastSample):
            drawn = animation_draw_commands(node.bound.timeline, current, media.casts[node.event_uuid], camera,
                                             condition_appearances=condition_appearances)
        else:
            raise ValueError("choreography sample does not match its bound primitive")
        for body in current.bodies:
            rank = body.clip != "Idle", node.start_ms, index
            if body.actor_uuid not in owners or rank > owners[body.actor_uuid]:
                owners[body.actor_uuid] = rank
        commands.extend((index, command) for command in drawn)
    result = [command for index, command in commands
              if command[4][6] not in ("actor", "actor_shadow")
              or owners[str(command[4][0])][2] == index]
    numbers = tuple(condition.feedback for condition in sample.conditions if condition.feedback is not None)
    result.extend(number_draw_commands(data, numbers, contacts, font, camera, badge_font=badge_font))
    return tuple(result)
