"""Registered reaction media over the frozen, camera-independent cast sample."""

import pygame

from game.animation import (ProjectileSample, actor_point_offset, body_elevation_steps, body_rig,
                            projectile_contact, project_projectile, project_geometry_projectile)
from game.animation_draw import AnimationMedia, animation_draw_commands
from game.draw_commands import DrawCommand
from game.interruption import ReactionMediaCue
from game.projection import Camera, TILE_WIDTH, painter_key, project_screen
from game.registered_media import registered_media_blits


def reaction_media_draw_commands(cue: ReactionMediaCue, elapsed_ms: float,
                                 media: AnimationMedia | None, camera: Camera) -> tuple[DrawCommand, ...]:
    age = elapsed_ms - cue.start_ms
    if not 0 <= age < cue.recipe.durationMs:
        return ()
    timeline, recipe = cue.timeline, cue.recipe
    data = cue.data
    progress = age / recipe.durationMs
    asset_id = (recipe.successByCamera if cue.succeeded else recipe.failureByCamera)[camera.quadrant]
    asset = data.projectile_assets[asset_id]
    assert asset.phases.impact is not None
    frame = min(asset.phases.impact.frames - 1, int(progress * asset.phases.impact.frames))
    factor = TILE_WIDTH / data.rig.TILE_W * camera.zoom
    commands: list[DrawCommand] = []
    if cue.succeeded and cue.sample is not None and cue.sample.projectiles:
        assert timeline is not None and media is not None
        mask_asset = data.projectile_assets[recipe.dissipationMask]
        assert mask_asset.phases.impact is not None
        mask_frame = min(mask_asset.phases.impact.frames - 1, int(progress * mask_asset.phases.impact.frames))
        coverage = pygame.Surface((mask_asset.frame.width, mask_asset.frame.height), pygame.SRCALPHA)
        for image, destination, blend in registered_media_blits(data, recipe.dissipationMask,
                "impact", mask_frame, mask_asset.rowOrder[0], scale=1, anchor=(0, 0), rows={}):
            coverage.blit(image, destination, special_flags=blend)
        commands.extend(animation_draw_commands(timeline, cue.sample, media, camera,
            include_bodies=False, projectile_coverage=coverage))
    placements = []
    for effect in cue.sample.projectiles if cue.sample is not None else ():
        assert timeline is not None
        position, height = projectile_contact(timeline, effect, quadrant=camera.quadrant)
        projected = (project_projectile(timeline, effect, camera.quadrant) if isinstance(effect, ProjectileSample)
                     else project_geometry_projectile(timeline, effect, camera.quadrant))
        anchor = projected.point[0] * factor + camera.pan[0], projected.point[1] * factor + camera.pan[1]
        placements.append((position, height, anchor))
    if not placements:
        # With no emitted carrier, the opposing spell is broken at its source.
        # The existing rig body anchor gives a stable contact in every view;
        # the actor's authored hand sheet supplies the gesture's exact pixels.
        source = cue.source
        height = body_elevation_steps(source, data)
        anchor = project_screen(source.grid, camera, elevation_steps=height)
        socket = body_rig(data, source).body_anchor
        if socket is not None:
            dx, dy = actor_point_offset(data, source, (socket.x, socket.y))
            anchor = anchor[0] + dx * factor, anchor[1] + dy * factor
        placements.append((source.grid, height, anchor))
    for index, (position, height, anchor) in enumerate(placements):
        key = painter_key(position, elevation_steps=height, quadrant=camera.quadrant,
            role="projectile", identity=(str(cue.event_uuid), "reaction", str(index)))
        for image, destination, blend in registered_media_blits(data, asset_id, "impact",
                frame, asset.rowOrder[0], scale=recipe.scale * factor, anchor=anchor, rows={}):
            commands.append(DrawCommand(key, image, destination, blend,
                (str(cue.event_uuid), position, asset_id, "current", None, "authored",
                 "reaction_media", height, "impact", frame, index)))
    return tuple(commands)
