"""Offline review envelopes from authored canvases and runtime registration."""

from math import cos, sin

from dnd.core.presentation_geometry import LinePresentationGeometry

from game.animation_types import AnimationData, Facing8
from game.animation import ActorContact, BodySample, CastTimeline, feedback_identity, view_facing
from game.cast_media import cast_media_placement
from game.forced_movement import ForcedMovementCue
from game.projection import Camera, TILE_WIDTH, project_screen


Bounds = tuple[float, float, float, float]


def displacement_media_bounds(cue: ForcedMovementCue) -> tuple[Bounds, ...]:
    """Fit the unchanged registered hand layers across their admitted transfer."""
    if not cue.layers:
        return ()
    data, actor = cue.data, cue.actor
    factor = actor.visual_scale * TILE_WIDTH / data.rig.TILE_W
    lift = cue.flight.clearancePx if cue.flight is not None else 0.
    views = []
    for quadrant in range(4):
        camera = Camera(quadrant=quadrant, zoom=1)
        points = []
        for point in cue.points:
            x, y = project_screen(point.grid, camera, elevation_steps=point.elevation_steps)
            for layer in cue.layers:
                media = data.condition_media[layer.assetId]
                for identity in (media.asset_id, media.application_asset_id, media.removal_asset_id):
                    if identity is None:
                        continue
                    asset = data.projectile_assets[identity]
                    scale = media.scale * factor
                    anchor = x + layer.offsetX * factor * actor.visual_scale_x, y + layer.offsetY * factor
                    points.extend((anchor[0] + dx * scale, anchor[1] + dy * scale - height)
                        for dx in (-asset.anchor.x * asset.frame.width, (1 - asset.anchor.x) * asset.frame.width)
                        for dy in (-asset.anchor.y * asset.frame.height, (1 - asset.anchor.y) * asset.frame.height)
                        for height in (0., lift * TILE_WIDTH / data.rig.TILE_W))
        views.append((min(p[0] for p in points), min(p[1] for p in points),
                      max(p[0] for p in points), max(p[1] for p in points)))
    return tuple(views)


def registered_media_bounds(data: AnimationData, identity: str, phase: str,
                            facing: Facing8) -> Bounds | None:
    """Union the lossless crop addresses; empty storage contributes no extent."""
    asset = data.projectile_assets[identity]
    full = (0.,0.,float(asset.frame.width),float(asset.frame.height))
    storage = data.projectile_storage.get(identity)
    if storage is None or phase not in storage.phases:
        return full
    selected = storage.phases[phase]
    if selected.surfaceFrames is not None:
        return full
    rectangles = []
    for layer in selected.layers:
        frames = layer.partsByFacing[facing] if layer.partsByFacing is not None else layer.parts
        if frames is None:
            return full
        rectangles.extend((part.offset[0],part.offset[1],
            part.offset[0]+part.rect[2],part.offset[1]+part.rect[3])
            for frame in frames for part in frame)
    return (min(row[0] for row in rectangles),min(row[1] for row in rectangles),
        max(row[2] for row in rectangles),max(row[3] for row in rectangles)) if rectangles else None


def cast_media_bounds(timeline: CastTimeline) -> tuple[Bounds, ...]:
    """One full-history envelope per camera, before camera zoom/pan.

    Registration can change with a preparation socket or hit-body offset. Their
    finite authored poses cover that motion without decoding or scanning media.
    """
    data, source, recipe = timeline.data, timeline.source, timeline.recipe
    targets = tuple(dict.fromkeys(application.target for application in source.applications))
    views = []
    for quadrant in range(4):
        camera = Camera(quadrant=quadrant, zoom=1)
        facing = view_facing(timeline.facing, quadrant, data)
        points = []
        if recipe.arcs is not None:
            contacts = (source.caster, *targets)
            positions = [(contact.grid, contact.elevation_steps + 1.5) for contact in contacts]
            geometry = source.area_geometry
            if isinstance(geometry, LinePresentationGeometry):
                dx, dy = geometry.direction
                length = geometry.length_feet / 5 / (dx*dx + dy*dy)**.5
                positions.append(((geometry.origin[0]+dx*length, geometry.origin[1]+dy*length),
                    source.ground_target.elevation_steps + 1.5 if source.ground_target else 1.5))
            for point, height in positions:
                px, py = project_screen(point, camera, elevation_steps=height)
                points.extend(((px-48, py-48), (px+48, py+96)))
        tracks = (*recipe.media, *(recipe.cancellationMedia.media if recipe.cancellationMedia else ()))
        for track in tracks:
            asset_id = track.assetIdsByCamera[quadrant] if track.assetIdsByCamera else track.assetId
            asset = data.projectile_assets[asset_id]
            media_facing = view_facing(track.viewFacing or timeline.facing, quadrant, data)
            pivot = (asset.anchorsByFacing or {}).get(media_facing, asset.anchor)
            bounds = registered_media_bounds(data, asset_id, track.assetPhase, media_facing)
            if bounds is None:
                continue
            contacts = targets if track.attachment.startswith("target_") else (source.caster,)
            for contact in contacts:
                if track.onMiss == "omit" and any(feedback_identity(application.target) == feedback_identity(contact)
                        and application.hit is False for application in source.applications):
                    continue
                poses: list[BodySample | None] = [None]
                sockets = recipe.cast.sourceSockets
                if (isinstance(contact, ActorContact) and track.attachment == "source_hand" and track.startOffsetMs < 0
                        and sockets is not None and sockets.preparation is not None):
                    poses.extend(BodySample(contact.actor_uuid, recipe.cast.actionClip, frame, timeline.facing)
                                 for frame in range(len(sockets.preparation[facing])))
                if isinstance(contact, ActorContact) and track.attachment == "target_body" and track.bodyOffsetsByFacing is not None:
                    viewed_body = view_facing(contact.facing, quadrant, data)
                    poses.extend(BodySample(contact.actor_uuid, data.damage_context.bodyClip, frame, contact.facing)
                                 for frame in range(len(track.bodyOffsetsByFacing[viewed_body])))
                for pose in poses:
                    placement = cast_media_placement(timeline, track, contact, camera, pose)
                    for x in (bounds[0]-pivot.x*asset.frame.width, bounds[2]-pivot.x*asset.frame.width):
                        for y in (bounds[1]-pivot.y*asset.frame.height, bounds[3]-pivot.y*asset.frame.height):
                            dx, dy = x * placement.scale, y * placement.scale
                            points.append((placement.anchor[0] + dx * cos(placement.rotation) - dy * sin(placement.rotation),
                                           placement.anchor[1] + dx * sin(placement.rotation) + dy * cos(placement.rotation)))
        if not points:
            return ()
        views.append((min(point[0] for point in points), min(point[1] for point in points),
                      max(point[0] for point in points), max(point[1] for point in points)))
    return tuple(views)


def projected_bounds(bounds: Bounds, camera: Camera) -> Bounds:
    return (bounds[0] * camera.zoom + camera.pan[0], bounds[1] * camera.zoom + camera.pan[1],
            bounds[2] * camera.zoom + camera.pan[0], bounds[3] * camera.zoom + camera.pan[1])
