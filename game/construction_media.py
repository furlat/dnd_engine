"""Original wall-section pixels attached to received physical object geometry."""

from dataclasses import dataclass, replace
from math import floor, hypot, isclose
from typing import Mapping
from uuid import UUID

import numpy as np
import pygame

from dnd.core.effect_types import ObjectSectionVolume

from dnd.core.presentation_geometry import WallAssemblyPresentationGeometry, WallSegment, WallDome, SpherePresentationGeometry
from game.animation import view_facing
from game.animation_types import AnimationData, ConstructionMediaBinding
from game.draw_commands import DrawCommand
from game.body_effects import silhouette_dust
from game.construction_surface import construction_surface_commands
from game.player_facts import PlayerObject, PlayerState
from game.projection import Camera, painter_key, project_screen, inverse_rotate_position
from game.registered_media import RegisteredMediaSample, registered_media_samples
from game.world_animation import WorldTransitionSample, ObjectDustContact
from game.volume_media import ExcludedSphere, SurfaceVolume


@dataclass(frozen=True, slots=True)
class ConstructionMediaLifetime:
    object: PlayerObject
    applied_ms: float | None = None
    destroyed_ms: float | None = None
    removed_ms: float | None = None
    collapse_contacts: tuple[tuple[float,float,float], ...] = ()
    membrane_impulses: tuple[tuple[float, tuple[float,float,float]], ...] = ()


def construction_duration(data: AnimationData, binding: ConstructionMediaBinding, phase: str) -> float:
    source_duration = ({'application': binding.surface.applicationMs, 'destruction': binding.surface.destructionMs,
        'removal': binding.surface.removalMs}[phase] if binding.surface is not None else 0.)
    if phase == 'removal':
        return max(binding.removalDurationMs or 0., source_duration)
    banks = (v.application if phase == 'application' else v.destruction
        for direction in binding.directions for v in direction.variants)
    durations = []
    for pair in banks:
        for identity in pair:
            asset = data.projectile_assets[identity]
            selected = asset.phases.impact
            assert selected is not None
            durations.append(selected.frames*1000/(selected.fps or asset.fps))
    return max((*durations, source_duration))


def construction_media_limitation(obj: PlayerObject, binding: ConstructionMediaBinding) -> str | None:
    geometry = obj.item.construction_geometry
    if binding.surface is not None and isinstance(geometry, WallAssemblyPresentationGeometry):
        if isinstance(geometry.path, WallDome):
            return None if geometry.path.radius_feet in (5, 10) else 'Construction radius has no original operator'
        if not binding.surface.domeOnly and isinstance(geometry.path, WallSegment):
            return None
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
        camera: Camera, lifetimes: Mapping[UUID, ConstructionMediaLifetime],
        transitions: tuple[WorldTransitionSample, ...] = ()) -> tuple[DrawCommand, ...]:
    senses = state.senses
    if senses is None:
        return ()
    result = []
    objects = {identity: obj for identity, obj in state.objects.items() if identity in senses.objects}
    for identity, record in lifetimes.items():
        if ((record.destroyed_ms is not None and record.destroyed_ms <= now_ms
                or record.removed_ms is not None and record.removed_ms <= now_ms)
                and any(position in senses.visible for position in record.object.placement.positions)):
            objects[identity] = record.object
    entries: list[tuple[UUID,PlayerObject,ObjectDustContact | None,float]] = [
        (identity,obj,None,0.) for identity,obj in objects.items()]
    dust_recipe = data.death_context.silhouetteDust
    entries.extend((sample.transition.identity,sample.transition.object_dust.object,
        sample.transition.object_dust,sample.elapsed_ms) for sample in transitions
        if dust_recipe is not None and sample.transition.object_dust is not None
        and sample.transition.duration_ms is not None
        and 0 <= sample.elapsed_ms < sample.transition.duration_ms
        and any(cell in senses.visible for cell in sample.transition.object_dust.object.placement.positions))
    consumed: set[UUID] = set()
    for identity, obj, dust, dust_age in entries:
        if identity in consumed:
            continue
        binding = data.construction_media.get(obj.item.item_id)
        if binding is None or construction_media_limitation(obj, binding) is not None:
            continue
        geometry = obj.item.construction_geometry
        assert isinstance(geometry, WallAssemblyPresentationGeometry)
        record = lifetimes.get(identity) if dust is None else None
        exclusions = tuple(ExcludedSphere(str(row.provider_uuid), row.area_geometry.center,
            row.anchor_elevation_steps, row.area_geometry.radius_feet/5,
            data.spatial_media[row.provider_content_ref.content_id].surfaceHeightScale)
            for row in obj.item.construction_suppressions
            if row.antimagic and isinstance(row.area_geometry, SpherePresentationGeometry)
            and row.anchor_elevation_steps is not None and row.provider_content_ref is not None
            and row.provider_content_ref.content_id in data.spatial_media)
        if binding.surface is not None and (not binding.surface.domeOnly or isinstance(geometry.path, WallDome)):
            if binding.surface.material == 'force_membrane' and isinstance(geometry.path, WallSegment) and dust is None:
                path = geometry.path
                remaining = [(other_id, other) for other_id, other, other_dust, _ in entries
                    if other_id != identity and other_id not in consumed and other_dust is None
                    and other.item.construction_owner_uuid == obj.item.construction_owner_uuid
                    and other.item.item_id == obj.item.item_id]
                while remaining:
                    joined = False
                    for other_id, other in tuple(remaining):
                        candidate = other.item.construction_geometry
                        if not isinstance(candidate, WallAssemblyPresentationGeometry) or not isinstance(candidate.path, WallSegment):
                            continue
                        if candidate.base_height_steps != geometry.base_height_steps or candidate.height_feet != geometry.height_feet:
                            continue
                        a, b = np.subtract(path.end, path.start), np.subtract(candidate.path.end, candidate.path.start)
                        if abs(a[0]*b[1]-a[1]*b[0]) > 1e-8 or float(a@b) <= 0:
                            continue
                        if np.allclose(path.end, candidate.path.start, atol=1e-8):
                            path = WallSegment(start=path.start, end=candidate.path.end)
                        elif np.allclose(candidate.path.end, path.start, atol=1e-8):
                            path = WallSegment(start=candidate.path.start, end=path.end)
                        else:
                            continue
                        consumed.add(other_id); remaining.remove((other_id,other)); joined = True
                    if not joined:
                        break
                geometry = geometry.model_copy(update={'path': path})
            commands = construction_surface_commands(geometry, binding.surface, data, now_ms, camera, str(identity),
                record.applied_ms if record else None, record.removed_ms if record else None,
                record.destroyed_ms if record else None,
                collapse_contact=record.collapse_contacts[camera.quadrant] if record and record.collapse_contacts else None,
                impulses=record.membrane_impulses if record else ())
            if dust is not None:
                assert dust_recipe is not None
                for command in commands:
                    image, offset = silhouette_dust(command.surface, dust_recipe, dust_age, dust.seed)
                    result.append(command._replace(surface=image,
                        destination=(command.destination[0]+offset[0], command.destination[1]+offset[1]),
                        volume=None, world_depth_group=None))
            else:
                result.extend(command._replace(volume=replace(command.volume, exclusions=exclusions))
                    if exclusions and command.volume is not None else command for command in commands)
            continue
        assert isinstance(geometry.path, WallSegment)
        if (record is not None and record.removed_ms is not None
                and now_ms >= record.removed_ms + construction_duration(data, binding, 'removal')):
            continue
        dx, dy = geometry.path.end[0]-geometry.path.start[0], geometry.path.end[1]-geometry.path.start[1]
        direction = next(d for d in binding.directions if dx*d.tangent[0]+dy*d.tangent[1] > 0
            and abs(dx*d.tangent[1]-dy*d.tangent[0]) < 1e-8)
        count = round(hypot(dx, dy)*5/binding.lengthFeet)
        for index in range(count):
            variant = direction.variants[(identity.int+index) % len(direction.variants)]
            if record is not None and record.removed_ms is not None and now_ms >= record.removed_ms:
                if variant.removal is None:
                    continue
                identities, age = variant.removal, now_ms-record.removed_ms
            elif record is not None and record.destroyed_ms is not None and now_ms >= record.destroyed_ms:
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
                        anchor=project_screen(origin, camera, elevation_steps=geometry.base_height_steps),
                        rows={}, zoom=camera.zoom)):
                    image, destination = part.image, part.destination
                    if geometry.removed_sections:
                        image = image.copy()
                        kept = _section_mask(part,origin,geometry.base_height_steps,geometry.removed_sections,camera)
                        opacity = pygame.surfarray.pixels_alpha(image);opacity[:] *= kept;del opacity
                    if dust is not None:
                        assert dust_recipe is not None
                        image = image.copy()
                        if dust.affected_volume is not None:
                            affected = ~_section_mask(part,origin,geometry.base_height_steps,(dust.affected_volume,),camera)
                            assert part.ownership is not None
                            affected &= part.ownership != 0
                            opacity = pygame.surfarray.pixels_alpha(image);opacity[:] *= affected;del opacity
                        image, offset = silhouette_dust(image,dust_recipe,dust_age,dust.seed)
                        destination = destination[0]+offset[0],destination[1]+offset[1]
                    volume = None
                    if exclusions and dust is None:
                        if part.positions is None or part.ownership is None:
                            raise ValueError('Suppressed construction requires genuine source coordinates')
                        volume = SurfaceVolume(origin, geometry.base_height_steps, 0, part.positions,
                            part.ownership, part.vertical_scale, exclusions=exclusions, resolved_occupancy=True)
                    result.append(DrawCommand(painter_key(point, elevation_steps=geometry.base_height_steps,
                        quadrant=camera.quadrant, role='actor', identity=(str(identity), str(index), str(side), str(part_index))),
                        image, destination, part.blend,
                        (str(identity), point, asset_id, 'current', None, 'authored', 'construction_media',
                         geometry.base_height_steps, 'impact', frame), owner=str(identity), volume=volume,
                        support_height_steps=geometry.base_height_steps))
    return tuple(result)


def _section_mask(part: RegisteredMediaSample, origin: tuple[float,float], base_height: int,
                  volumes: tuple[ObjectSectionVolume,...], camera: Camera) -> np.ndarray:
    """Keep only genuine source surfaces outside native removed ten-foot cubes."""
    positions = part.material_positions if part.material_positions is not None else part.positions
    if positions is None or part.ownership is None:
        raise ValueError('A partially cut construction needs its matched source coordinates')
    zero = inverse_rotate_position((0.,0.),camera.quadrant)
    axis_x = np.subtract(inverse_rotate_position((1.,0.),camera.quadrant),zero)
    axis_z = np.subtract(inverse_rotate_position((0.,1.),camera.quadrant),zero)
    ground = positions[:,:,0,None]*axis_x+positions[:,:,2,None]*axis_z+np.asarray(origin)
    height = positions[:,:,1]+base_height
    kept = part.ownership != 0
    for volume in volumes:
        x,z=volume.minimum_position
        kept &= ~((ground[:,:,0]>x-.5)&(ground[:,:,0]<x+1.5)
            &(ground[:,:,1]>z-.5)&(ground[:,:,1]<z+1.5)
            &(height>=volume.base_height_steps)&(height<volume.base_height_steps+2))
    return kept
