"""Registered finite media on the shared cast clock; no spell identities or rules."""

from math import atan2, floor
from typing import Literal, Mapping, NamedTuple

import pygame

from game.animation import (
    ActorContact, ObjectContact, feedback_identity, BodySample, CastSample, CastTimeline, actor_point_offset, body_elevation_steps, body_rig,
    facing_vector, media_track_duration, media_track_frame, media_track_opacity, media_target_applies, view_facing, rest_pose_offset,
)
from game.animation_types import AnimationData, BodyMaterialSample, StudioMediaTrack
from game.finite_material import sample_material_track
from game.area_media import AreaLayer, AreaMedia
from game.draw_commands import DrawCommand
from game.media_blend import SCREEN_BLEND
from game.projectile_media import projectile_frame_layers
from game.registered_media import registered_material, registered_media_samples, RegisteredMediaSample
from game.volume_media import ExcludedSphere, SurfaceVolume
from dnd.core.presentation_geometry import ConePresentationGeometry, LinePresentationGeometry, SpherePresentationGeometry
from game.projection import Camera, TILE_WIDTH, HEIGHT_STEP_PIXELS, painter_key, project_screen, project_world


def sample_cast_body_materials(timeline: CastTimeline, elapsed_ms: float) -> tuple[tuple[str, BodyMaterialSample], ...]:
    """Sample authored envelopes for disclosed recipients with admitted outcomes."""
    samples = []
    for track in timeline.recipe.bodyMaterials:
        recipients = {}
        for application in timeline.applications:
            target = application.source.target
            if not isinstance(target, ActorContact) or not media_target_applies(track, application.source):
                continue
            start = application.travel_end_ms if track.clock == "contact" else timeline.release_ms
            sample = sample_material_track(track, elapsed_ms-start)
            if sample is not None:
                recipients[target.actor_uuid] = sample
        samples.extend(recipients.items())
    return tuple(samples)


def preload_cast_media(timeline: CastTimeline) -> None:
    """Warm selected first pages only; the existing bounded cache owns decoding."""
    tracks = (*timeline.recipe.media, *(timeline.recipe.cancellationMedia.media
        if timeline.recipe.cancellationMedia is not None else ()))
    for track in tracks:
        if track.attachment.startswith("target_") and not any(
                media_target_applies(track, application) for application in timeline.source.applications):
            continue
        for quadrant in range(4):
            asset_id = track.assetIdsByCamera[quadrant] if track.assetIdsByCamera else track.assetId
            asset = timeline.data.projectile_assets[asset_id]
            facing = view_facing(track.viewFacing or timeline.facing, quadrant, timeline.data)
            storage = timeline.data.projectile_storage.get(asset_id)
            first = 0
            if storage is not None:
                first = min((index for layer in storage.phases[track.assetPhase].layers
                    for frames in (layer.partsByFacing[facing] if layer.partsByFacing is not None else layer.parts,)
                    if frames is not None
                    for index, parts in enumerate(frames) if parts), default=0)
            projectile_frame_layers(timeline.data, asset, track.assetPhase, first, facing,
                                    registered_material(asset_id, track.alpha), {})


def _socket(data: AnimationData, contact: ActorContact, camera: Camera,
            *, point: tuple[float, float]) -> tuple[float, float]:
    dx, dy = actor_point_offset(data, contact, point)
    factor = TILE_WIDTH / data.rig.TILE_W * camera.zoom
    return dx * factor, dy * factor


def _world_offset(point: tuple[float, float], quadrant: int) -> tuple[float, float]:
    x, y = point
    return ((x, y), (y, -x), (-x, -y), (-y, x))[quadrant]


class CastMediaPlacement(NamedTuple):
    grid: tuple[float, float]
    height: float
    anchor: tuple[float, float]
    scale: float
    rotation: float


def cast_media_placement(timeline: CastTimeline, track: StudioMediaTrack,
                         contact: ActorContact | ObjectContact, camera: Camera,
                         body: BodySample | None = None) -> CastMediaPlacement:
    """Resolve one authored registration; shared by drawing and review framing."""
    data, source, recipe = timeline.data, timeline.source, timeline.recipe
    viewed = view_facing(track.viewFacing or timeline.facing, camera.quadrant, data)
    targets = tuple(dict.fromkeys(application.target for application in source.applications))
    grid = contact.grid
    height = (body_elevation_steps(contact, data) if isinstance(contact, ActorContact) and track.attachment in ("source_hand", "target_body")
              else contact.elevation_steps)
    if track.attachment == "area_ground":
        assert source.ground_target is not None
        grid, height = source.ground_target.grid, source.ground_target.elevation_steps
    if track.worldOffsetsByFacing is not None:
        offset = track.worldOffsetsByFacing[viewed]
        dx, dy = _world_offset((offset.x, offset.y), camera.quadrant)
        grid = grid[0] + dx, grid[1] + dy
    anchor = project_screen(grid, camera, elevation_steps=height)
    if track.attachment == "source_hand" and isinstance(contact, ActorContact):
        sockets = recipe.cast.sourceSockets
        if sockets is None:
            raise ValueError("source-hand media requires authored cast sockets")
        # A world-oriented effect bank and the caster's viewed hand are separate
        # registrations. Orbit media can stay on E while the body faces elsewhere.
        hand_facing = view_facing(body.facing if body is not None else timeline.facing,
                                  camera.quadrant, data)
        socket = sockets.release[hand_facing]
        if (track.startOffsetMs < 0 and sockets.preparation is not None
                and body is not None and body.clip == recipe.cast.actionClip):
            socket = sockets.preparation[hand_facing][body.frame] or socket
        dx, dy = _socket(data, contact, camera, point=(socket.x, socket.y))
        anchor = anchor[0] + dx, anchor[1] + dy
    elif track.attachment == "target_body" and isinstance(contact, ActorContact):
        socket = body_rig(data, contact).body_anchor
        if socket is not None:
            dx, dy = _socket(data, contact, camera, point=(socket.x, socket.y))
            anchor = anchor[0] + dx, anchor[1] + dy
        dx, dy = rest_pose_offset(data, contact, camera.quadrant)
        factor = TILE_WIDTH / data.rig.TILE_W * camera.zoom
        anchor = anchor[0] + dx * factor, anchor[1] + dy * factor
    if (track.bodyOffsetsByFacing is not None and body is not None and isinstance(contact, ActorContact)
            and body.clip == (track.bodyOffsetsClip or data.damage_context.bodyClip)):
        facing = view_facing(body.facing, camera.quadrant, data)
        offset = track.bodyOffsetsByFacing[facing][body.frame]
        factor = contact.visual_scale * TILE_WIDTH / data.rig.TILE_W * camera.zoom
        anchor = anchor[0] + offset.x * factor * contact.visual_scale_x, anchor[1] + offset.y * factor
    rotation = 0.0
    factor = track.scale * TILE_WIDTH / data.rig.TILE_W * camera.zoom
    if track.scaleWithActor and isinstance(contact, ActorContact):
        factor *= contact.visual_scale
    if track.emissionPointByFacing is not None:
        point = track.emissionPointByFacing[viewed]
        anchor = anchor[0] - point.x * factor, anchor[1] - point.y * factor
    if track.orientation == "target_vector" and isinstance(source.area_geometry, (ConePresentationGeometry, LinePresentationGeometry)):
        end_x, end_y = project_world(source.area_geometry.direction, quadrant=camera.quadrant)
        origin_x, origin_y = project_world((0, 0), quadrant=camera.quadrant)
        dx, dy = end_x-origin_x, end_y-origin_y
        vx,vy = facing_vector(viewed,data)
        rotation = atan2(dy,dx)-atan2(vy,vx)
    elif track.orientation == "target_vector" and targets:
        target = targets[0]
        endpoint = project_screen(target.grid, camera, elevation_steps=(body_elevation_steps(target, data)
            if isinstance(target, ActorContact) else target.elevation_steps))
        socket = body_rig(data, target).body_anchor if isinstance(target, ActorContact) else None
        if socket is not None and isinstance(target, ActorContact):
            dx, dy = _socket(data, target, camera, point=(socket.x, socket.y))
            endpoint = endpoint[0] + dx, endpoint[1] + dy
        dx, dy = rest_pose_offset(data, target, camera.quadrant) if isinstance(target, ActorContact) else (0, 0)
        body_factor = TILE_WIDTH / data.rig.TILE_W * camera.zoom
        endpoint = endpoint[0] + dx * body_factor, endpoint[1] + dy * body_factor
        vx, vy = facing_vector(viewed, data)
        rotation = atan2(endpoint[1]-anchor[1], endpoint[0]-anchor[0]) - atan2(vy, vx)
    return CastMediaPlacement(grid, height, anchor, factor, rotation)


def cast_surface_volume(timeline: CastTimeline, sample: RegisteredMediaSample, area: AreaMedia | None,
                        center: tuple[float, float], height: float, *,
                        translation: tuple[float, float, float] = (0, 0, 0),
                        support_clipping: Literal["physical", "raised"] = "physical") -> SurfaceVolume:
    source, data = timeline.source, timeline.data
    assert sample.positions is not None and sample.ownership is not None
    exclusions = tuple(ExcludedSphere(str(identity), protection.area_geometry.center,
        protection.anchor_elevation_steps or 0, protection.area_geometry.radius_feet / 5,
        data.spatial_media[protection.content_ref.content_id].surfaceHeightScale)
        for identity, protection in source.protections
        if isinstance(protection.area_geometry, SpherePresentationGeometry)
        and protection.content_ref.content_id in data.spatial_media)
    return SurfaceVolume(center, height, source.area_radius_feet / 5,
        sample.positions, sample.ownership, sample.vertical_scale,
        area.boundaries if area is not None else (), exclusions,
        area.solids if area is not None else (), area.supports if area is not None else (),
        # A witnessed burst is one continuous volume. Received affected cells
        # describe outcomes, not a stencil for its artwork. Actual barriers,
        # raised supports and exclusions still clip the physical volume.
        source.area_propagation,
        translation=translation,
        line_geometry=source.area_geometry if isinstance(source.area_geometry, LinePresentationGeometry) else None,
        support_clipping=support_clipping)


def cast_media_draw_commands(timeline: CastTimeline, sample: CastSample, camera: Camera,
                             area: AreaMedia | None,
                             rows: Mapping[tuple[str, int], pygame.Surface],
                             *, actor_bounds: Mapping[str, pygame.Rect] | None = None,
                             body_samples: Mapping[str, BodySample] | None = None,
                             actor_contacts: Mapping[str, ActorContact] | None = None,
                             ) -> tuple[DrawCommand, ...]:
    data, source, recipe = timeline.data, timeline.source, timeline.recipe
    bodies = {body.actor_uuid: body for body in sample.bodies}
    if body_samples is not None:
        bodies.update(body_samples)
    targets = tuple(dict.fromkeys(application.target for application in source.applications))
    commands = []
    for track in recipe.media:
        viewed = view_facing(track.viewFacing or timeline.facing, camera.quadrant, data)
        duration = media_track_duration(data, track)
        asset_id = track.assetIdsByCamera[camera.quadrant] if track.assetIdsByCamera else track.assetId
        asset = data.projectile_assets[asset_id]
        contacts = targets if track.attachment.startswith("target_") else (source.caster,)
        timed = (tuple((row.source.target,row.travel_end_ms) for row in timeline.applications
            if media_target_applies(track,row.source)) if track.clock == "contact" else
            tuple((contact,timeline.release_ms) for contact in contacts))
        for contact, landmark in timed:
            start = landmark + track.startOffsetMs
            if not start <= sample.media_elapsed_ms < start + duration:
                continue
            age = sample.media_elapsed_ms - start
            opacity = media_track_opacity(data, track, age)
            if isinstance(contact, ActorContact) and actor_contacts is not None:
                contact = actor_contacts.get(contact.actor_uuid, contact)
            if track.attachment.startswith("target_") and not any(
                    feedback_identity(application.target) == feedback_identity(contact) and media_target_applies(track, application)
                    for application in source.applications):
                continue
            if track.onMiss == "omit" and any(feedback_identity(application.target) == feedback_identity(contact)
                    and application.hit is False for application in source.applications):
                continue
            grid, height, anchor, factor, rotation = cast_media_placement(
                timeline, track, contact, camera, bodies.get(feedback_identity(contact)))
            if track.composition == "clump" and (area is None or area.admitted is None
                    or (floor(grid[0] + .5), floor(grid[1] + .5)) not in area.admitted):
                continue
            if track.actorTopClearancePx is not None:
                bounds = None if actor_bounds is None else actor_bounds.get(feedback_identity(contact))
                if bounds is None:
                    continue
                anchor = (anchor[0], bounds.top - track.actorTopClearancePx * camera.zoom)
            origin = project_screen(grid, camera, elevation_steps=height)
            dx, dy = (anchor[0]-origin[0])/camera.zoom, (anchor[1]-origin[1])/camera.zoom
            translation = dx/TILE_WIDTH, -dy/HEIGHT_STEP_PIXELS, -dx/TILE_WIDTH
            frame = media_track_frame(data, track, age, viewed)
            key = painter_key(grid, elevation_steps=height, quadrant=camera.quadrant,
                role="ground_effect" if track.depth == "ground" else "actor" if track.depth in ("behind_body", "front_body") else "projectile",
                identity=(source.root_event_uuid, track.id, feedback_identity(contact)))
            if track.depth in ("behind_body", "front_body"):
                key = (*key[:3], key[3] + (-1 if track.depth == "behind_body" else 1), key[4])
            if track.sortDepthByFacing is not None:
                key = (key[0], key[1] + track.sortDepthByFacing[viewed] * 32, *key[2:])
            for layer in registered_media_samples(data, asset_id,
                    track.assetPhase, frame, viewed, scale=factor, anchor=anchor, rows=rows,
                    alpha=opacity, rotation=rotation, zoom=camera.zoom):
                if track.composition == "xyz_volume":
                    commands.append(DrawCommand(key, layer.image, layer.destination, SCREEN_BLEND if track.blendMode == "screen" else layer.blend,
                        (source.root_event_uuid, grid, asset.assetId, "current", None, "authored",
                         "cast_media", height, track.id, frame),
                        volume=cast_surface_volume(timeline, layer, area, grid, height, translation=translation,
                                                  support_clipping=track.supportClipping),
                        world_depth_group=(source.root_event_uuid, "cast-media")))
                    continue
                commands.append(DrawCommand(key, layer.image, layer.destination, SCREEN_BLEND if track.blendMode == "screen" else layer.blend,
                    (source.root_event_uuid, grid, asset.assetId, "current", None, "authored",
                     "cast_media", height, track.id, frame),
                    AreaLayer(source.ground_target.grid, source.ground_target.elevation_steps, area)
                    if source.ground_target is not None and not track.attachment.startswith("target_")
                    and track.composition != "clump" else None))
    return tuple(commands)
