"""Maintained authored media on received spatial state, using the shared clock."""

from functools import lru_cache
from math import sqrt
from types import MappingProxyType
from typing import Mapping
from uuid import UUID

from dnd.core.presentation_geometry import LinePresentationGeometry, SpherePresentationGeometry
from dnd.core.events import WorldTileState
from dnd.types.world import WorldEdgeChannel
from dnd.types.world_placement import WorldObjectPlacement
from game.animation import facing_for_delta, view_facing
from game.animation_types import AnimationData
from game.area_media import AreaLayer, AreaMedia, AreaSolid
from game.draw_commands import DrawCommand
from game.player_facts import PlayerState
from game.projection import Camera, TILE_WIDTH, painter_key, project_screen, rotate_position, inverse_rotate_position
from game.registered_media import registered_media_samples
from game.spatial_field import field_cell, line_field_supports, line_owned_supports
from game.volume_media import ExcludedSphere, SurfaceVolume
from game.spatial_media_lifetime import SpatialMediaLifetime
from game.spatial_field_media import field_media_commands, spatial_origin
from game.world_animation import WorldTransitionSample
from game.maintained_media import maintained_media_alpha, maintained_media_frame, maintained_removal_duration


@lru_cache(maxsize=8)
def _observed_area(boundaries: tuple[WorldObjectPlacement, ...], solids: tuple[AreaSolid, ...],
                   supports: tuple[WorldTileState, ...]) -> AreaMedia:
    return AreaMedia(boundaries, solids, supports)


def spatial_media_draw_commands(state: PlayerState, data: AnimationData, presentation_ms: float,
                                 camera: Camera, transitions: tuple[WorldTransitionSample, ...] = (),
                                 lifetimes: Mapping[UUID, SpatialMediaLifetime] = MappingProxyType({}),
                                 ) -> tuple[DrawCommand, ...]:
    """Only observed zones exist; creation suppresses their own finite intro."""
    senses = state.senses
    if senses is None:
        return ()
    introducing = {sample.transition.identity for sample in transitions
        if sample.transition.field == "creation" and sample.transition.duration_ms is not None
        and sample.elapsed_ms < sample.transition.duration_ms}
    area = _observed_area(tuple(obj.placement for obj in state.objects.values()
        if obj.item.boundary_structure is not None
        and WorldEdgeChannel.PROPAGATION in obj.item.boundary_structure.blocked_channels),
        tuple(AreaSolid(position, obj.placement.base_height_steps, obj.placement.top_height_steps)
            for obj in state.objects.values() if obj.item.boundary_structure is None
            and obj.item.blocks_propagation for position in obj.placement.positions) + tuple(
                AreaSolid(tile.position, tile.elevation_steps) for tile in state.tiles.values() if tile.blocks_propagation),
        tuple(state.tiles.values()))
    visible = frozenset(senses.visible)
    commands = []
    effects = {**senses.spatial_effects, **{owner: record.effect for owner, record in lifetimes.items()
        if record.removed_ms is not None and record.removed_ms <= presentation_ms
        and presentation_ms < record.removed_ms + maintained_removal_duration(
            data, data.spatial_media[record.effect.content_ref.content_id])}}
    moving = {sample.transition.identity: sample for sample in transitions
              if sample.transition.spatial_motion is not None
              and 0 <= sample.elapsed_ms < sample.transition.spatial_motion.duration_ms}
    for identity, effect in effects.items():
        translation = (0., 0.)
        previous_suppressions = ()
        movement = moving.get(identity)
        if movement is not None:
            path = movement.transition.spatial_motion
            assert path is not None and path.before.area_geometry is not None and path.after.area_geometry is not None
            start_position, end_position = spatial_origin(path.before.area_geometry), spatial_origin(path.after.area_geometry)
            remaining = 1 - movement.elapsed_ms / path.duration_ms
            translation = ((start_position[0] - end_position[0]) * remaining,
                           (start_position[1] - end_position[1]) * remaining)
            previous_suppressions = path.before.suppressions
            effect = path.after
        binding = data.spatial_media.get(effect.content_ref.content_id)
        geometry = effect.area_geometry
        if binding is None or identity in introducing or geometry is None:
            continue
        lifetime = lifetimes.get(identity)
        start = lifetime.applied_ms if lifetime is not None else None
        removed = lifetime.removed_ms if lifetime is not None else None
        resolved_protections = {row.provider_uuid: row for row in (*previous_suppressions, *effect.suppressions)}
        protections = tuple(suppression for suppression in resolved_protections.values()
            if suppression.provider_content_ref is not None
            and suppression.provider_content_ref.content_id in data.spatial_media
            and isinstance(suppression.area_geometry, SpherePresentationGeometry)
            and suppression.anchor_elevation_steps is not None)
        exclusions = tuple(ExcludedSphere(str(suppression.provider_uuid),
            suppression.area_geometry.center, suppression.anchor_elevation_steps,
            suppression.area_geometry.radius_feet / 5,
            data.spatial_media[suppression.provider_content_ref.content_id].surfaceHeightScale)
            for suppression in protections
            if isinstance(suppression.area_geometry, SpherePresentationGeometry)
            and suppression.anchor_elevation_steps is not None and suppression.provider_content_ref is not None)
        for layer_index, layer in enumerate(binding.layers):
            field_layer = (layer.composition in ("floor", "xy_volume", "clump")
                or layer.composition == "xyz_volume" and isinstance(geometry, SpherePresentationGeometry))
            if not field_layer:
                continue
            alpha = maintained_media_alpha(binding, layer, presentation_ms, removed)
            if alpha <= 0:
                continue
            selected = maintained_media_frame(data, binding, layer, presentation_ms, start, removed)
            if selected is not None:
                asset_id, frame = selected
                admitted = (tuple(position for position in effect.positions
                    if position in visible or position in effect.visible_volume_positions)
                    if layer.composition in ("xy_volume", "xyz_volume") else effect.positions)
                if layer.composition == "xyz_volume":
                    # These cells were withheld by an observed native protection,
                    # not by missing visibility. Only the true sphere is removed;
                    # the authored cloud above/outside it remains drawable.
                    admitted = tuple(dict.fromkeys((*admitted,
                        *(position for suppression in effect.suppressions
                          if suppression in protections for position in suppression.positions))))
                commands.extend(field_media_commands(state, data, identity, geometry, admitted,
                    binding, layer, layer_index, asset_id, frame, camera, alpha, translation,
                    anchor_elevation_steps=effect.anchor_elevation_steps, area=area, exclusions=exclusions))
        if not isinstance(geometry, (LinePresentationGeometry, SpherePresentationGeometry)):
            continue
        origin = geometry.origin if isinstance(geometry, LinePresentationGeometry) else geometry.center
        origin_tile = state.tiles.get(origin)
        if isinstance(geometry, SpherePresentationGeometry):
            # Current surface observation is independent of sight of the center
            # ground/occupants. Remembered geometry alone is not permission.
            if not effect.visible_volume_positions and not visible.intersection(effect.positions):
                continue
            height = effect.anchor_elevation_steps
            if height is None:
                height = origin_tile.elevation_steps if origin_tile is not None else None
            if height is None:
                continue
        else:
            if origin_tile is None:
                continue
            height = origin_tile.elevation_steps
        facing = view_facing(facing_for_delta(geometry.direction, data) if isinstance(geometry, LinePresentationGeometry)
                             else "E", camera.quadrant, data)
        anchor = project_screen(origin, camera, elevation_steps=height)
        observed = frozenset(effect.positions)
        for layer_index, layer in enumerate(binding.layers):
            if (layer.composition in ("floor", "xy_volume", "clump")
                    or layer.composition == "xyz_volume" and isinstance(geometry, SpherePresentationGeometry)):
                continue
            alpha = maintained_media_alpha(binding, layer, presentation_ms, removed)
            if alpha <= 0:
                continue
            selected = maintained_media_frame(data, binding, layer, presentation_ms, start, removed)
            if selected is None:
                continue
            asset_id, frame = selected
            parts = registered_media_samples(data, asset_id, binding.assetPhase, frame, facing,
                scale=binding.scale * TILE_WIDTH / data.rig.TILE_W * camera.zoom, anchor=anchor, rows={}, alpha=alpha, zoom=camera.zoom)
            for index, part in enumerate(parts):
                image, destination, blend = part.image, part.destination, part.blend
                if layer.composition == "xyz_volume":
                    assert isinstance(geometry, LinePresentationGeometry)
                    assert part.positions is not None
                    assert part.ownership is not None
                    admitted = line_owned_supports(tuple(state.tiles), origin, geometry.direction,
                        geometry.length_feet // 5, geometry.width_feet // 5, observed, visible)
                    if not admitted:
                        continue
                    commands.append(DrawCommand(painter_key(origin, elevation_steps=height,
                        quadrant=camera.quadrant, role="projectile", identity=(str(identity), str(layer_index), str(index))),
                        image, destination, blend, (str(identity), origin, asset_id, "current", None,
                            "authored", "spatial_media", height, binding.assetPhase, frame),
                        volume=SurfaceVolume(origin, height, 0, part.positions, part.ownership,
                            part.vertical_scale, area.boundaries, solids=area.solids, supports=area.supports,
                            propagation="line_of_effect", admitted=admitted),
                        world_depth_group=(str(identity), "maintained-media")))
                    continue
                if isinstance(geometry, SpherePresentationGeometry):
                    rotated = rotate_position(origin, camera.quadrant)
                    depth_offset = {"rear": -1, "center": 0, "front": 1}[layer.side] * geometry.radius_feet / 5 / sqrt(2)
                    depth = inverse_rotate_position((rotated[0] + depth_offset, rotated[1] + depth_offset), camera.quadrant)
                    commands.append(DrawCommand(painter_key(depth, elevation_steps=height, quadrant=camera.quadrant,
                        role="projectile", identity=(str(identity), str(layer_index), str(index))), image, destination, blend,
                        (str(identity), origin, asset_id, "current", None, "authored", "spatial_media", height,
                         binding.assetPhase, frame)))
                    continue
                if layer.composition != "line_floor":
                    raise ValueError(f"line fields require line_floor or xyz_volume composition: {asset_id}")
                pivot = anchor[0] - destination[0], anchor[1] - destination[1]
                supports = line_field_supports(image.size, pivot, origin, geometry.direction,
                    geometry.length_feet // 5, geometry.width_feet // 5, observed, visible,
                    camera.quadrant, camera.zoom)
                for position in supports:
                    tile = state.tiles.get(position)
                    if tile is None:
                        continue
                    piece, offset = field_cell(image, pivot, (position[0] - origin[0], position[1] - origin[1]),
                                              camera.quadrant, camera.zoom)
                    point = project_screen(origin, camera, elevation_steps=tile.elevation_steps)
                    placed = (round(point[0] - pivot[0] + offset[0]), round(point[1] - pivot[1] + offset[1]))
                    commands.append(DrawCommand(painter_key(position, elevation_steps=tile.elevation_steps,
                        quadrant=camera.quadrant, role="projectile", identity=(str(identity), str(layer_index), str(index), str(position))),
                        piece, placed, blend, (str(identity), position, asset_id, "current", None,
                        "authored", "spatial_media", tile.elevation_steps, binding.assetPhase, frame),
                        AreaLayer(origin, tile.elevation_steps, area)))
    return tuple(commands)
