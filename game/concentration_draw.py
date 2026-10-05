"""Raster composition for retained, observer-permitted concentration areas."""

from typing import Mapping
from uuid import UUID

from game.animation_types import AnimationData
from game.concentration_media import ConcentrationMediaLifetime
from game.draw_commands import DrawCommand
from game.maintained_media import maintained_media_alpha, maintained_media_frame
from game.player_facts import PlayerState
from game.projection import Camera
from game.spatial_field_media import field_media_commands


def concentration_media_draw_commands(state: PlayerState, data: AnimationData, now_ms: float,
                                      camera: Camera, retained: Mapping[UUID, ConcentrationMediaLifetime],
                                      ) -> tuple[DrawCommand, ...]:
    commands = []
    for owner, record in retained.items():
        binding = data.concentration_media[record.spell_id]
        if now_ms < record.applied_ms:
            continue
        for index, layer in enumerate(binding.layers):
            alpha = maintained_media_alpha(binding, layer, now_ms, record.removed_ms)
            if binding.formationFadeMs:
                alpha *= min(1., (now_ms - record.applied_ms) / binding.formationFadeMs)
            frame = maintained_media_frame(data, binding, layer, now_ms, record.applied_ms, record.removed_ms)
            if alpha <= 0 or frame is None:
                continue
            commands.extend(field_media_commands(state, data, owner, record.geometry, record.positions,
                binding, layer, index, *frame, camera, alpha, anchor_elevation_steps=record.elevation_steps))
    return tuple(commands)
