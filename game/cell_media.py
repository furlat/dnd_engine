"""Accepted source modules repeated only at disclosed native material cells."""

from uuid import UUID

import numpy as np
import pygame

from dnd.types.senses import PerceivedSpatialEffect
from game.animation import view_facing
from game.animation_types import AnimationData, SpatialMediaBinding
from game.area_media import AreaMedia
from game.draw_commands import DrawCommand
from game.maintained_media import maintained_media_alpha, maintained_media_samples
from game.player_facts import PlayerState
from game.projection import Camera, TILE_WIDTH, painter_key, project_screen
from game.registered_media import registered_media_samples
from game.spatial_media_lifetime import SpatialMediaLifetime
from game.volume_media import ExcludedSphere, SurfaceVolume


def cell_media_commands(state: PlayerState, data: AnimationData, effect: PerceivedSpatialEffect,
                        identity: UUID, binding: SpatialMediaBinding, now_ms: float, camera: Camera,
                        lifetime: SpatialMediaLifetime | None, area: AreaMedia,
                        exclusions: tuple[ExcludedSphere, ...]) -> tuple[DrawCommand, ...]:
    """Neither art bounds nor expired cells create native material occupancy."""
    if state.senses is None:
        return ()
    retired = dict(lifetime.retired_cells) if lifetime is not None else {}
    applied = lifetime.applied_ms if lifetime is not None else None
    removed = lifetime.removed_ms if lifetime is not None else None
    cells = tuple(sorted(set(effect.positions).union(retired)))
    visible = set(state.senses.visible)
    suppressed = {cell for row in effect.suppressions for cell in row.positions}
    admitted = tuple(cell for cell in cells if cell in visible and cell in state.tiles and cell not in suppressed)
    result = []
    for cell in admitted:
        support = state.tiles[cell].elevation_steps
        anchor = project_screen(cell,camera,elevation_steps=support)
        for layer_index,layer in enumerate(binding.layers):
            if not layer.cellVariants:
                continue
            # Stable visual variation is independent of simulation randomness and
            # shared by the original rear/front source pair at this owner/cell.
            variant = layer.cellVariants[(identity.int+cell[0]*73856093+cell[1]*19349663)%len(layer.cellVariants)]
            selected = layer.model_copy(update={'assetId':variant.assetId,
                'applicationAssetId':variant.applicationAssetId})
            clear_at = retired.get(cell,removed)
            alpha = maintained_media_alpha(binding,selected,now_ms,clear_at)
            if alpha <= 0:
                continue
            group = (str(identity),str(cell),str(layer_index))
            for asset_id,frame,weight in maintained_media_samples(data,binding,selected,now_ms,applied,clear_at):
                samples = registered_media_samples(data,asset_id,binding.assetPhase,frame,
                    view_facing(layer.worldFacing,camera.quadrant,data),
                    scale=binding.scale*TILE_WIDTH/data.rig.TILE_W*camera.zoom,
                    anchor=anchor,rows={},alpha=alpha*weight,zoom=camera.zoom)
                for sample in samples:
                    if sample.positions is None or sample.ownership is None:
                        raise ValueError(f'Cell media needs its delivered closest-surface coordinates: {asset_id}')
                    key = painter_key(cell,elevation_steps=support,quadrant=camera.quadrant,
                        role='actor',identity=(*group,str(frame)))
                    evidence = (str(identity),cell,asset_id,'current',None,'authored','spatial_media',
                        support,binding.assetPhase,frame)
                    owned = sample.ownership != 0
                    image = sample.image.copy()
                    pixels = pygame.surfarray.pixels_alpha(image);pixels[:] *= owned;del pixels
                    volume = SurfaceVolume(cell,support,0,sample.positions,owned,sample.vertical_scale,
                        area.boundaries,exclusions,area.solids,area.supports,admitted=admitted,resolved_occupancy=True)
                    result.append(DrawCommand(key,image,sample.destination,sample.blend,evidence,
                        volume=volume,world_depth_group=group,media_mix_group=(*group,'surface')))
                    # The delivered closest-surface map intentionally excludes
                    # translucent glow. Preserve those original pixels as an
                    # owner decoration; do not fabricate coordinates for them.
                    if np.any(~owned & (pygame.surfarray.array_alpha(sample.image)!=0)):
                        glow = sample.image.copy()
                        pixels = pygame.surfarray.pixels_alpha(glow);pixels[:] *= ~owned;del pixels
                        side = -1 if layer.side=='rear' else 1 if layer.side=='front' else 0
                        glow_key = (*key[:3],key[3]+side,key[4])
                        result.append(DrawCommand(glow_key,glow,sample.destination,sample.blend,evidence,
                            media_mix_group=(*group,'unowned-decoration')))
    return tuple(result)
