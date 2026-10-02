"""Original wall-section pixels attached to received physical object geometry."""

from dataclasses import dataclass
from math import floor, hypot, isclose
from typing import Mapping
from uuid import UUID

from dnd.core.presentation_geometry import WallAssemblyPresentationGeometry, WallSegment
from game.animation import view_facing
from game.animation_types import AnimationData, ConstructionMediaBinding
from game.draw_commands import DrawCommand
from game.player_facts import PlayerObject, PlayerState
from game.projection import Camera, painter_key, project_screen
from game.registered_media import registered_media_samples


@dataclass(frozen=True, slots=True)
class ConstructionMediaLifetime:
    object: PlayerObject
    applied_ms: float | None = None
    destroyed_ms: float | None = None
    removed_ms: float | None = None


def construction_duration(data: AnimationData, binding: ConstructionMediaBinding, phase: str) -> float:
    banks = (v.application if phase == 'application' else v.destruction
        for direction in binding.directions for v in direction.variants)
    durations = []
    for pair in banks:
        for identity in pair:
            asset = data.projectile_assets[identity]
            selected = asset.phases.impact
            assert selected is not None
            durations.append(selected.frames*1000/(selected.fps or asset.fps))
    return max(durations)


def construction_media_limitation(obj: PlayerObject, binding: ConstructionMediaBinding) -> str | None:
    geometry = obj.item.construction_geometry
    if not isinstance(geometry, WallAssemblyPresentationGeometry) or not isinstance(geometry.path, WallSegment):
        return 'Construction geometry has no delivered section profile'
    if not isclose(geometry.height_feet, binding.heightFeet):
        return 'Construction height has no matched source bank'
    path = geometry.path
    dx, dy = path.end[0]-path.start[0], path.end[1]-path.start[1]
    length = hypot(dx, dy)*5
    if not isclose(length/binding.lengthFeet, round(length/binding.lengthFeet)):
        return 'Construction length is not an exact source-module multiple'
    if not any(dx*x+dy*y > 0 and abs(dx*y-dy*x) < 1e-8 for x, y in (d.tangent for d in binding.directions)):
        return 'Construction heading has no native source bank'
    return None


def construction_media_draw_commands(state: PlayerState, data: AnimationData, now_ms: float,
        camera: Camera, lifetimes: Mapping[UUID, ConstructionMediaLifetime]) -> tuple[DrawCommand, ...]:
    senses = state.senses
    if senses is None:
        return ()
    result = []
    objects = {identity: obj for identity, obj in state.objects.items() if identity in senses.objects}
    for identity, record in lifetimes.items():
        if (record.destroyed_ms is not None and record.destroyed_ms <= now_ms
                and any(position in senses.visible for position in record.object.placement.positions)):
            objects[identity] = record.object
    for identity, obj in objects.items():
        binding = data.construction_media.get(obj.item.item_id)
        if binding is None or construction_media_limitation(obj, binding) is not None:
            continue
        geometry = obj.item.construction_geometry
        assert isinstance(geometry, WallAssemblyPresentationGeometry) and isinstance(geometry.path, WallSegment)
        record = lifetimes.get(identity)
        if record is not None and record.removed_ms is not None and now_ms >= record.removed_ms:
            continue  # No intact-retirement donor: actual removal never selects a fracture.
        dx, dy = geometry.path.end[0]-geometry.path.start[0], geometry.path.end[1]-geometry.path.start[1]
        direction = next(d for d in binding.directions if dx*d.tangent[0]+dy*d.tangent[1] > 0
            and abs(dx*d.tangent[1]-dy*d.tangent[0]) < 1e-8)
        count = round(hypot(dx, dy)*5/binding.lengthFeet)
        for index in range(count):
            variant = direction.variants[(identity.int+index) % len(direction.variants)]
            if record is not None and record.destroyed_ms is not None and now_ms >= record.destroyed_ms:
                identities = variant.destruction
                age = now_ms-record.destroyed_ms
            elif record is not None and record.applied_ms is not None and now_ms >= record.applied_ms:
                age = now_ms-record.applied_ms
                identities = variant.application if age < construction_duration(data, binding, 'application') else variant.intact
            else:
                identities, age = variant.intact, 0.
            point = (geometry.path.start[0]+dx*(index+.5)/count,
                     geometry.path.start[1]+dy*(index+.5)/count)
            origin = (point[0]-direction.centerlineOffsetCells[0], point[1]-direction.centerlineOffsetCells[1])
            for side, asset_id in enumerate(identities):
                asset = data.projectile_assets[asset_id]
                phase = asset.phases.impact
                assert phase is not None
                frame = 0 if identities == variant.intact else floor(age*(phase.fps or asset.fps)/1000)
                if frame >= phase.frames:
                    continue
                for part_index, part in enumerate(registered_media_samples(data, asset_id, 'impact', frame,
                        view_facing('E', camera.quadrant, data), scale=binding.pixelScale*camera.zoom,
                        anchor=project_screen(origin, camera, elevation_steps=geometry.base_height_steps), rows={} )):
                    result.append(DrawCommand(painter_key(point, elevation_steps=geometry.base_height_steps,
                        quadrant=camera.quadrant, role='actor', identity=(str(identity), str(index), str(side), str(part_index))),
                        part.image, part.destination, part.blend,
                        (str(identity), point, asset_id, 'current', None, 'authored', 'construction_media',
                         geometry.base_height_steps, 'impact', frame), owner=str(identity),
                        support_height_steps=geometry.base_height_steps))
    return tuple(result)
