"""Offline review envelopes from authored canvases and runtime registration."""

from math import cos, sin

from game.animation import BodySample, CastTimeline, view_facing
from game.cast_media import cast_media_placement
from game.projection import Camera


Bounds = tuple[float, float, float, float]


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
        for track in recipe.media:
            asset = data.projectile_assets[track.assetId]
            pivot = (asset.anchorsByFacing or {}).get(facing, asset.anchor)
            contacts = targets if track.attachment.startswith("target_") else (source.caster,)
            for contact in contacts:
                if track.onMiss == "omit" and any(application.target.actor_uuid == contact.actor_uuid
                        and application.hit is False for application in source.applications):
                    continue
                poses: list[BodySample | None] = [None]
                sockets = recipe.cast.sourceSockets
                if (track.attachment == "source_hand" and track.startOffsetMs < 0
                        and sockets is not None and sockets.preparation is not None):
                    poses.extend(BodySample(contact.actor_uuid, recipe.cast.actionClip, frame, timeline.facing)
                                 for frame in range(len(sockets.preparation[facing])))
                if track.attachment == "target_body" and track.bodyOffsetsByFacing is not None:
                    viewed_body = view_facing(contact.facing, quadrant, data)
                    poses.extend(BodySample(contact.actor_uuid, data.damage_context.bodyClip, frame, contact.facing)
                                 for frame in range(len(track.bodyOffsetsByFacing[viewed_body])))
                for pose in poses:
                    placement = cast_media_placement(timeline, track, contact, camera, pose)
                    for x in (-pivot.x * asset.frame.width, (1 - pivot.x) * asset.frame.width):
                        for y in (-pivot.y * asset.frame.height, (1 - pivot.y) * asset.frame.height):
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
