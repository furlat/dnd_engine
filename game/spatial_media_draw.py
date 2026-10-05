"""Maintained authored media on received spatial state, using the shared clock."""

from functools import lru_cache
from math import sqrt
from types import MappingProxyType
from typing import Mapping
from uuid import UUID

from dnd.core.presentation_geometry import CylinderPresentationGeometry, LinePresentationGeometry, SpherePresentationGeometry
from dnd.types.event_facts import WorldTileState
from dnd.core.geometry import circle_positions
from dnd.types.world import WorldEdgeChannel
from dnd.types.world_placement import WorldObjectPlacement
from game.animation import ActorContact, facing_for_delta, view_facing
from game.animation_types import AnimationData, Facing8
from game.area_media import AreaLayer, AreaMedia
from game.animation_types import AreaSolid
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
from game.wall_media import wall_media_draw_commands
from game.wall_assembly_media import assembly_media_draw_commands
from game.orbit_media import orbit_media_commands, ground_ellipse_command
from game.component_particles import rising_mote_commands
from game.cell_media import cell_media_commands


@lru_cache(maxsize=8)
def _observed_area(boundaries: tuple[WorldObjectPlacement, ...], solids: tuple[AreaSolid, ...],
                   supports: tuple[WorldTileState, ...]) -> AreaMedia:
    return AreaMedia(boundaries, solids, supports)


def spatial_media_draw_commands(state: PlayerState, data: AnimationData, presentation_ms: float,
                                 camera: Camera, transitions: tuple[WorldTransitionSample, ...] = (),
                                 lifetimes: Mapping[UUID, SpatialMediaLifetime] = MappingProxyType({}),
                                 anchors: Mapping[UUID, ActorContact] = MappingProxyType({}),
                                 responding: frozenset[UUID] = frozenset(),
                                 response_facings: Mapping[UUID, Facing8] = MappingProxyType({}),
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
    effects = dict(senses.spatial_effects)
    pending_grants = {}
    for owner, record in lifetimes.items():
        if (record.applied_ms is not None and record.committed_ms is not None
                and record.applied_ms <= presentation_ms < record.committed_ms):
            # Retained future shape is not a future sight grant. Each formation
            # sample borrows only currently disclosed supports for this frame.
            positions = tuple(position for position in record.effect.positions if position in visible)
            current = senses.spatial_effects.get(owner)
            if positions:
                pending_grants[owner] = visible
                effects[owner] = record.effect.model_copy(update={"positions": positions,
                    "visible_volume_positions": positions,
                    "upper_volume_surfaces": current.upper_volume_surfaces if current is not None else ()})
        elif (record.removed_ms is not None and record.removed_ms <= presentation_ms
                < record.removed_ms + maintained_removal_duration(
                    data, data.spatial_media[record.effect.content_ref.content_id])):
            effects[owner] = record.effect
    moving = {sample.transition.identity: sample for sample in transitions
              if sample.transition.spatial_motion is not None
              and 0 <= sample.elapsed_ms < sample.transition.spatial_motion.duration_ms}
    for identity, effect in effects.items():
        translation = (0., 0.)
        previous_suppressions = ()
        previous_effect = None
        movement = moving.get(identity)
        if movement is not None:
            path = movement.transition.spatial_motion
            assert path is not None and path.before.area_geometry is not None and path.after.area_geometry is not None
            start_position, end_position = spatial_origin(path.before.area_geometry), spatial_origin(path.after.area_geometry)
            remaining = 1 - movement.elapsed_ms / path.duration_ms
            translation = ((start_position[0] - end_position[0]) * remaining,
                           (start_position[1] - end_position[1]) * remaining)
            previous_suppressions = path.before.suppressions
            if movement.elapsed_ms == 0:
                effect = path.before
                translation = (0., 0.)
            else:
                previous_effect = path.before
                effect = path.after
        binding = data.spatial_media.get(effect.content_ref.content_id)
        geometry = effect.area_geometry
        if (binding is None or identity in introducing
                or geometry is None and not any(layer.composition in ("clump", "cell_modules") for layer in binding.layers)):
            continue
        anchor = anchors.get(effect.anchor_entity_uuid) if effect.anchor_entity_uuid is not None else None
        if anchor is not None and effect.anchor_position is not None and any(layer.composition == 'clump' for layer in binding.layers):
            translation = (anchor.grid[0]-effect.anchor_position[0],anchor.grid[1]-effect.anchor_position[1])
        lifetime = lifetimes.get(identity)
        start = lifetime.applied_ms if lifetime is not None else None
        removed = lifetime.removed_ms if lifetime is not None else None
        if any(layer.orbit is not None for layer in binding.layers):
            anchor = anchors.get(effect.anchor_entity_uuid) if effect.anchor_entity_uuid is not None else None
            origin = anchor.grid if anchor is not None else (spatial_origin(geometry) if geometry is not None else effect.anchor_position)
            height = anchor.elevation_steps if anchor is not None else effect.anchor_elevation_steps
            if origin is not None and height is not None:
                for layer in binding.layers:
                    if layer.orbit is None or layer.whenEnergyType is not None and layer.whenEnergyType is not effect.energy_type:
                        continue
                    alpha = maintained_media_alpha(binding, layer, presentation_ms, removed)
                    allowed = tuple(position for position in effect.positions
                        if not any(position in suppression.positions for suppression in effect.suppressions))
                    commands.extend(orbit_media_commands(state, data, identity, layer, origin, height,
                        presentation_ms-(start or 0), None if start is None else presentation_ms-start,
                        alpha, allowed, camera, area, effect.anchor_position,
                        frozenset(position for row in (*previous_suppressions,*effect.suppressions) for position in row.positions)))
            continue
        if any(layer.composition == "wall_modules" for layer in binding.layers):
            commands.extend(wall_media_draw_commands(effect, identity, data, binding,
                presentation_ms, camera, start, removed))
            continue
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
        if any(layer.cellVariants for layer in binding.layers):
            commands.extend(cell_media_commands(state,data,effect,identity,binding,presentation_ms,camera,lifetime,area,exclusions))
            continue
        if any(layer.wallAssembly is not None for layer in binding.layers):
            commands.extend(assembly_media_draw_commands(effect, identity, data, binding,
                presentation_ms, camera, start, removed, area, exclusions,
                tuple(position for suppression in protections for position in suppression.positions
                      if identity not in pending_grants or position in pending_grants[identity]),
                tuple(anchors.values()), tuple(row.recipient for row in lifetime.damage_contacts
                    if row.formation and UUID(row.recipient.actor_uuid) in anchors) if lifetime is not None else (),
                tuple((row.recipient, row.at_ms) for row in lifetime.damage_contacts)
                    if lifetime is not None else ()))
            continue
        for layer_index, layer in enumerate(binding.layers):
            if layer.whenPresenceMode is not None and layer.whenPresenceMode != effect.presence_mode:
                continue
            if layer.whenEnergyType is not None and layer.whenEnergyType is not effect.energy_type:
                continue
            facing = response_facings.get(identity) or (next((facing for at,facing in reversed(lifetime.facings)
                if at <= presentation_ms),None) if lifetime is not None else None)
            if facing is not None:
                layer = layer.model_copy(update={"worldFacing": facing})
            if (layer.groundShadow is not None and effect.anchor_position is not None and effect.anchor_position in visible
                    and not any(effect.anchor_position in row.positions for row in effect.suppressions)):
                support = state.tiles.get(effect.anchor_position)
                if support is not None:
                    commands.append(ground_ellipse_command(identity, layer.groundShadow, effect.anchor_position,
                        support.elevation_steps, camera, maintained_media_alpha(binding,layer,presentation_ms,removed)))
            if layer.motes is not None and effect.anchor_position is not None and effect.anchor_position in visible:
                support = state.tiles.get(effect.anchor_position)
                age = presentation_ms-(start or 0)
                alpha = maintained_media_alpha(binding,layer,presentation_ms,removed)
                if layer.motes.formationOnlyMs is not None:
                    if start is None:
                        alpha = 0
                    else:
                        duration = layer.motes.formationOnlyMs
                        alpha *= max(0,min(1,(age-.1*duration)/(.25*duration)))
                        alpha *= max(0,min(1,(duration-age)/(.35*duration)))
                if support is not None and not any(effect.anchor_position in row.positions for row in effect.suppressions):
                    commands.extend(rising_mote_commands(str(identity),layer.motes,effect.anchor_position,
                        support.elevation_steps,age,alpha,camera))
            if identity in responding:
                continue
            field_layer = (layer.composition in ("floor", "xy_volume", "clump")
                or layer.composition == "xyz_volume" and isinstance(geometry, (SpherePresentationGeometry, CylinderPresentationGeometry)))
            if not field_layer:
                continue
            if layer.recipientTrackId is not None:
                if lifetime is None or geometry is None:
                    continue
                origin = spatial_origin(geometry)
                for endpoint in lifetime.recipient_endpoints:
                    if endpoint.track_id != layer.recipientTrackId or presentation_ms < endpoint.start_ms:
                        continue
                    placed = layer.model_copy(update={"offsetCells": (
                        endpoint.position[0] - origin[0], endpoint.position[1] - origin[1])})
                    alpha = maintained_media_alpha(binding, placed, presentation_ms, removed)
                    selected = maintained_media_frame(data, binding, placed, presentation_ms, endpoint.start_ms, removed)
                    if alpha <= 0 or selected is None:
                        continue
                    asset_id, frame = selected
                    commands.extend(field_media_commands(state, data, identity, geometry, effect.positions,
                        binding, placed, layer_index, asset_id, frame, camera, alpha, translation,
                        anchor_elevation_steps=endpoint.elevation_steps, area=area, exclusions=exclusions,
                        anchor_position=effect.anchor_position))
                continue
            alpha = maintained_media_alpha(binding, layer, presentation_ms, removed)
            if binding.formationFadeMs and start is not None:
                alpha *= max(0., min(1., (presentation_ms-start)/binding.formationFadeMs))
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
                          if suppression in protections for position in suppression.positions
                          if identity not in pending_grants or position in pending_grants[identity]))))
                commands.extend(field_media_commands(state, data, identity, geometry, admitted,
                    binding, layer, layer_index, asset_id, frame, camera, alpha, translation,
                    anchor_elevation_steps=effect.anchor_elevation_steps, area=area, exclusions=exclusions,
                    upper_surfaces=effect.upper_volume_surfaces, previous_effect=previous_effect,
                    anchor_position=effect.anchor_position))
        if not isinstance(geometry, (LinePresentationGeometry, SpherePresentationGeometry)):
            continue
        origin = geometry.origin if isinstance(geometry, LinePresentationGeometry) else geometry.center
        origin_tile = state.tiles.get(origin)
        if isinstance(geometry, SpherePresentationGeometry):
            if identity in pending_grants:
                x0, y0, x1, y1 = state.world.bounds
                supports = {p for p in circle_positions(geometry.center, geometry.radius_feet // 5)
                            if x0 <= p[0] <= x1 and y0 <= p[1] <= y1}
                if not supports <= pending_grants[identity]:
                    # This whole-bank billboard has no XYZ permission mask.
                    # It cannot claim partially disclosed formation surfaces.
                    continue
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
        drawn_origin = (origin[0] + translation[0], origin[1] + translation[1])
        anchored = anchors.get(effect.anchor_entity_uuid) if effect.anchor_entity_uuid is not None else None
        if anchored is not None and effect.anchor_position is not None:
            drawn_origin = (origin[0] + anchored.grid[0] - effect.anchor_position[0],
                            origin[1] + anchored.grid[1] - effect.anchor_position[1])
            height = anchored.elevation_steps
        anchor = project_screen(drawn_origin, camera, elevation_steps=height)
        observed = frozenset(effect.positions)
        for layer_index, layer in enumerate(binding.layers):
            if (layer.composition in ("floor", "xy_volume", "clump")
                    or layer.composition == "xyz_volume" and isinstance(geometry, (SpherePresentationGeometry, CylinderPresentationGeometry))):
                continue
            alpha = maintained_media_alpha(binding, layer, presentation_ms, removed)
            if binding.formationFadeMs and start is not None:
                alpha *= max(0., min(1., (presentation_ms - start) / binding.formationFadeMs))
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
                    rotated = rotate_position(drawn_origin, camera.quadrant)
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
