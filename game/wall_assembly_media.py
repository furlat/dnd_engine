"""Registered single-layer wall modules over received native construction paths."""

from math import ceil, hypot, isclose
from uuid import UUID

from game.volume_media import ExcludedSphere, SurfaceVolume

from dnd.core.presentation_geometry import WallAssemblyPresentationGeometry, WallPolyline, WallRing, WallSegment
from dnd.core.wall_geometry import wall_shell_cells
from dnd.types.senses import PerceivedSpatialEffect
from game.animation import view_facing
from game.animation_types import AnimationData, AssemblyModuleMedia, SpatialMediaBinding, WallAssemblyMedia
from game.area_media import AreaLayer, AreaMedia
from game.draw_commands import DrawCommand
from game.maintained_media import maintained_media_alpha, maintained_media_frame
from game.projection import Camera, painter_key, project_screen
from game.registered_media import registered_media_samples


def assembly_segments(geometry: WallAssemblyPresentationGeometry) -> tuple[WallSegment, ...]:
    path = geometry.path
    if isinstance(path, WallSegment):
        return (path,)
    if isinstance(path, WallPolyline):
        return tuple(WallSegment(start=a, end=b) for a, b in zip(path.points, path.points[1:]))
    return ()


def assembly_bank(path: WallSegment, registration: WallAssemblyMedia) -> AssemblyModuleMedia | None:
    """Select native geometry; unsupported angles never screen-rotate a wall."""
    dx, dy = path.end[0]-path.start[0], path.end[1]-path.start[1]
    length = hypot(dx, dy)
    for bank in registration.modules:
        tx, ty = bank.tangent
        if dx*tx+dy*ty > 0 and abs(dx*ty-dy*tx) <= 1e-8*length*hypot(tx, ty):
            return bank
    return None


def assembly_centers(path: WallSegment, length_cells: float) -> tuple[tuple[float, float], ...]:
    """Canonical arclength slots precede disclosure filtering and camera choice."""
    dx, dy = path.end[0]-path.start[0], path.end[1]-path.start[1]
    count = max(1, ceil(hypot(dx, dy)/length_cells))
    return tuple((path.start[0]+dx*(i+.5)/count, path.start[1]+dy*(i+.5)/count) for i in range(count))


def module_is_received(point: tuple[float, float], bank: AssemblyModuleMedia,
                       registration: WallAssemblyMedia, geometry: WallAssemblyPresentationGeometry,
                       admitted: frozenset[tuple[int, int]]) -> bool:
    """Opaque faces can be received at the shell's edge while its center is hidden."""
    tx, ty = bank.tangent
    factor = registration.moduleLengthCells / (2*hypot(tx, ty))
    section = geometry.model_copy(update={"path": WallSegment(
        start=(point[0]-tx*factor, point[1]-ty*factor),
        end=(point[0]+tx*factor, point[1]+ty*factor))})
    return bool(wall_shell_cells(section).intersection(admitted))


def assembly_media_limitation(effect: PerceivedSpatialEffect, binding: SpatialMediaBinding) -> str | None:
    geometry = effect.area_geometry
    if not isinstance(geometry, WallAssemblyPresentationGeometry):
        return 'Assembly media requires retained native construction geometry'
    for layer in binding.layers:
        registration = layer.wallAssembly
        if registration is None:
            continue
        if not isclose(registration.widthFeet, geometry.width_feet):
            return 'Native wall width has no matched module registration'
        if isinstance(geometry.path, WallRing):
            ring = registration.ring
            if ring is None or not isclose(ring.radiusFeet, geometry.path.radius_feet) or not isclose(ring.widthFeet, geometry.width_feet):
                return 'Native ring has no matched source bank'
            if not isclose(ring.heightFeet, geometry.height_feet):
                return 'Native ring height has no matched source bank'
            if effect.suppressions or not wall_shell_cells(geometry) <= set(effect.positions):
                return 'Whole-ring media requires complete received shell coverage'
        elif not isclose(registration.heightFeet, geometry.height_feet):
            return 'Native wall height has no matched module registration'
        elif not assembly_segments(geometry):
            return 'Native shape has no delivered assembly profile'
        elif any(assembly_bank(segment, registration) is None for segment in assembly_segments(geometry)):
            return 'Native path angle has no matched module bank'
    return None


def assembly_media_draw_commands(effect: PerceivedSpatialEffect, identity: UUID,
        data: AnimationData, binding: SpatialMediaBinding, now_ms: float, camera: Camera,
        applied_ms: float | None, removed_ms: float | None, area: AreaMedia | None = None,
        exclusions: tuple[ExcludedSphere, ...] = (), suppressed_positions: tuple[tuple[int,int], ...] = ()) -> tuple[DrawCommand, ...]:
    """Existence and visibility come from received state; clocks add no mechanics."""
    if assembly_media_limitation(effect, binding) is not None:
        return ()
    geometry = effect.area_geometry
    assert isinstance(geometry, WallAssemblyPresentationGeometry)
    admitted = frozenset((*effect.positions,*suppressed_positions))
    commands = []
    for layer_index, layer in enumerate(binding.layers):
        registration = layer.wallAssembly
        if registration is None:
            continue
        if isinstance(geometry.path, WallRing):
            ring = registration.ring
            assert ring is not None
            candidates = ((geometry.path.center, ring, ring.pixelScale),)
        else:
            candidates = tuple((point, bank, registration.pixelScale)
                for segment in assembly_segments(geometry)
                if (bank := assembly_bank(segment, registration)) is not None
                for point in assembly_centers(segment, registration.moduleLengthCells)
                if module_is_received(point, bank, registration, geometry, admitted))
        for point, bank, pixel_scale in candidates:
            selected_layer = layer.model_copy(update={'assetId': bank.assetId,
                'applicationAssetId': bank.applicationAssetId, 'removalAssetId': bank.removalAssetId})
            selected = maintained_media_frame(data, binding, selected_layer, now_ms, applied_ms, removed_ms)
            alpha = maintained_media_alpha(binding, selected_layer, now_ms, removed_ms)
            if selected is None or alpha <= 0:
                continue
            asset_id, frame = selected
            for part_index, part in enumerate(registered_media_samples(data, asset_id, binding.assetPhase,
                    frame, view_facing('E', camera.quadrant, data), scale=binding.scale*pixel_scale*camera.zoom,
                    anchor=project_screen(point, camera, elevation_steps=geometry.base_height_steps), rows={},
                    alpha=alpha, zoom=camera.zoom)):
                volume = None
                if part.positions is not None and part.ownership is not None:
                    volume = SurfaceVolume(point, geometry.base_height_steps, 0,
                        part.positions, part.ownership, part.vertical_scale,
                        area.boundaries if area is not None else (), exclusions,
                        area.solids if area is not None else (), area.supports if area is not None else (),
                        admitted=tuple(sorted(admitted)), resolved_occupancy=True)
                commands.append(DrawCommand(painter_key(point, elevation_steps=geometry.base_height_steps,
                    quadrant=camera.quadrant, role='actor', identity=(str(identity), str(point), str(layer_index), str(part_index))),
                    part.image, part.destination, part.blend,
                    (str(identity), point, asset_id, 'current', None, 'authored', 'wall_assembly', geometry.base_height_steps,
                     binding.assetPhase, frame), area=AreaLayer(point, geometry.base_height_steps, area) if volume is None else None,
                    volume=volume, world_depth_group=(str(identity),str(point)) if volume is not None else None,
                    owner=str(identity), support_height_steps=geometry.base_height_steps))
    return tuple(commands)
