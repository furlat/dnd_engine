"""Shared map painter for public playback and explicit rendering diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence, cast
from uuid import UUID

import pygame

from dnd.core.events import WorldObjectState, WorldTileState
from dnd.core.world_edges import ElevationSurfaceKind, SlopeAxis
from dnd.types.materials import Material
from dnd.types.world import CardinalDirection, LightLevel
from dnd.types.world_placement import BoundaryStructureKind

from game.assets import AssetCatalog, SurfaceCache, flame_frame_index
from game.actor_facts import PresentationTarget
from game.player_facts import PlayerObject, PlayerState
from game.projection import (
    Camera,
    TILE_HEIGHT,
    TILE_WIDTH,
    camera_axis_vectors,
    camera_pose,
    inverse_plane,
    painter_key,
    pick_support,
    project_screen,
)
from game.water import WaterSupportInput, render_water_batch, water_source_origin


WINDOW_SIZE = (1280, 720)
BACKGROUND = (10, 12, 18)
CAMERA_LABELS = (
    ("NE", "SW"),
    ("SE", "NW"),
    ("SW", "NE"),
    ("NW", "SE"),
)

DrawCommand = tuple[
    tuple[int, float, float, int, tuple[str, ...]],
    pygame.Surface, tuple[int, int], int, tuple[object, ...],
]


@dataclass(frozen=True, slots=True)
class FrameEvidence:
    """Primitive calculation/draw evidence and bounded work counters."""

    expected_calculations: frozenset[tuple[object, ...]]
    actual_calculations: frozenset[tuple[object, ...]]
    expected_draws: tuple[tuple[object, ...], ...]
    actual_draws: tuple[tuple[object, ...], ...]
    candidate_coordinates: int
    static_draws: int
    water_chunks: int
    water_pixels: int
    grid_candidates: int
    grid_draws: int
    animated_fixtures: int
    flame_frame: int | None

    @property
    def matches(self) -> bool:
        return (
            self.expected_calculations == self.actual_calculations
            and self.expected_draws == self.actual_draws
        )



def _incident_positions(
    position: tuple[int, int],
    direction: CardinalDirection,
) -> tuple[tuple[int, int], tuple[int, int]]:
    offsets = {
        CardinalDirection.NORTH: (0, 1),
        CardinalDirection.EAST: (1, 0),
        CardinalDirection.SOUTH: (0, -1),
        CardinalDirection.WEST: (-1, 0),
    }
    dx, dy = offsets[direction]
    return position, (position[0] + dx, position[1] + dy)


def _treatment(
    catalog: AssetCatalog,
    level: LightLevel | None,
) -> tuple[str, tuple[float, float, float]]:
    treatments = cast(Mapping[str, Mapping[str, object]], catalog.bindings["treatments"])
    key = "memory" if level is None else str(level.value)
    row = treatments[key]
    rgb = cast(list[float], row["rgb"])
    return cast(str, row["id"]), (float(rgb[0]), float(rgb[1]), float(rgb[2]))


def _authored_treatment(
    catalog: AssetCatalog,
) -> tuple[str, tuple[float, float, float]]:
    """Return the neutral treatment for objective structural geometry."""
    treatments = cast(Mapping[str, Mapping[str, object]], catalog.bindings["treatments"])
    row = treatments["authored"]
    rgb = cast(list[float], row["rgb"])
    return cast(str, row["id"]), (float(rgb[0]), float(rgb[1]), float(rgb[2]))


def _disclosure(
    target: PresentationTarget | PlayerState,
    positions: tuple[tuple[int, int], ...],
) -> tuple[str, LightLevel | None] | None:
    senses = target.senses
    if senses is None:
        return None
    current = [position for position in positions if position in senses.visible]
    if current:
        levels: list[LightLevel] = []
        for position in current:
            level = senses.effective_light_levels.get(position)
            if level is None:
                raise RuntimeError(f"visible support {position} lacks effective light")
            levels.append(level)
        return "current", max(levels, key=lambda value: value.value)
    if any(position in senses.seen for position in positions):
        return "memory", None
    return None


def _boundary_disclosure(
    target: PresentationTarget | PlayerState,
    position: tuple[int, int],
    direction: CardinalDirection,
) -> str | None:
    """Classify composite boundary geometry from its incident supports."""
    senses = target.senses
    if senses is None:
        return None
    incident = _incident_positions(position, direction)
    if any(support in senses.visible for support in incident):
        return "current"
    if any(support in senses.seen for support in incident):
        return "memory"
    return None


def _stair_runs(
    target: PresentationTarget | PlayerState,
    profile: Mapping[str, object],
) -> tuple[tuple[WorldTileState, WorldTileState, WorldTileState, CardinalDirection], ...]:
    """Match only the supported whole-flight shape in detached support facts."""
    stairs = {p: t for p, t in target.tiles.items() if t.surface_kind is ElevationSurfaceKind.STAIRS}
    covered: set[tuple[int, int]] = set()
    runs = []
    offsets = cast(list[list[int]], profile["support_offsets"])
    for position, lower in sorted(stairs.items(), key=lambda row: (row[1].elevation_steps, row[0])):
        if position in covered:
            continue
        if lower.slope_axis not in (SlopeAxis.EAST_WEST, SlopeAxis.NORTH_SOUTH):
            raise RuntimeError(f"unsupported stair axis at {position}")
        directions = (
            ((1, 0, CardinalDirection.WEST), (-1, 0, CardinalDirection.EAST))
            if lower.slope_axis is SlopeAxis.EAST_WEST
            else ((0, 1, CardinalDirection.SOUTH), (0, -1, CardinalDirection.NORTH))
        )
        matches = []
        for dx, dy, downhill in directions:
            supports = tuple(stairs.get((position[0] - offset[0] * dx,
                                         position[1] - offset[0] * dy)) for offset in offsets)
            if all(t is not None and t.slope_axis is lower.slope_axis
                   and t.elevation_steps == lower.elevation_steps + offset[2]
                   and t.surface.base_material is Material.EARTH
                   for t, offset in zip(supports, offsets, strict=True)):
                matches.append((*supports, downhill))
        if len(matches) != 1:
            raise RuntimeError(f"unsupported or ambiguous three-support stair run at {position}")
        lower, middle, upper, downhill = matches[0]
        positions = {lower.position, middle.position, upper.position}
        if covered & positions:
            raise RuntimeError(f"overlapping stair run at {position}")
        covered.update(positions)
        runs.append((lower, middle, upper, downhill))
    return tuple(runs)


def _support_evidence(target: PresentationTarget | PlayerState, tile: WorldTileState) -> tuple[object, ...]:
    """Keep a composite sprite's individual support knowledge unmerged."""
    state, level = _disclosure(target, (tile.position,)) or ("authored", None)
    return tile.tile_uuid, tile.position, tile.elevation_steps, state, level.value if level is not None else None


def _corner_representative(
    directions: frozenset[CardinalDirection],
) -> CardinalDirection | None:
    """Return the one q0 representative for a perpendicular wall pair."""
    return {
        frozenset((CardinalDirection.NORTH, CardinalDirection.EAST)):
            CardinalDirection.EAST,
        frozenset((CardinalDirection.EAST, CardinalDirection.SOUTH)):
            CardinalDirection.SOUTH,
        frozenset((CardinalDirection.SOUTH, CardinalDirection.WEST)):
            CardinalDirection.WEST,
        frozenset((CardinalDirection.WEST, CardinalDirection.NORTH)):
            CardinalDirection.NORTH,
    }.get(directions)


def _visible_rect(surface: pygame.Surface, destination: tuple[int, int], screen: pygame.Surface) -> bool:
    return surface.get_rect(topleft=destination).colliderect(screen.get_rect())


def _static_blit(
    cache: SurfaceCache,
    asset_id: str,
    camera: Camera,
    contact: tuple[float, float],
    multiplier: tuple[float, float, float],
    screen: pygame.Surface,
) -> tuple[pygame.Surface, tuple[int, int]] | None:
    """Cull by the old full raster, then omit only transparent submitted pixels."""
    full_destination = cache.blit_position(asset_id, camera.zoom, contact)
    if not _visible_rect(
        cache.scaled(asset_id, camera.zoom),
        full_destination,
        screen,
    ):
        return None
    offset_x, offset_y, _, _ = cache.alpha_bounds(asset_id, camera.zoom)
    return (
        cache.cropped_treated(asset_id, camera.zoom, multiplier),
        (full_destination[0] + offset_x, full_destination[1] + offset_y),
    )


def draw_frame(
    screen: pygame.Surface,
    target: PresentationTarget | PlayerState,
    catalog: AssetCatalog,
    cache: SurfaceCache,
    camera: Camera,
    presentation_time: float,
    *,
    show_grid: bool,
    mouse_position: tuple[int, int] | None,
    objective_lines: Sequence[str] = (),
    subjective_lines: Sequence[str] = (),
    revisions: tuple[int, int, int] = (0, 0, 0),
    extra_commands: Sequence[DrawCommand] = (),
    show_debug: bool = True,
    collect_evidence: bool = False,
) -> FrameEvidence | None:
    """Draw disclosed state; duplicate calculation/draw evidence is opt-in."""
    screen.fill(BACKGROUND)
    senses = target.senses
    if target.world is None or senses is None:
        return (FrameEvidence(frozenset(), frozenset(), (), (), 0, 0, 0, 0, 0, 0, 0, None)
                if collect_evidence else None)
    screen_rect = screen.get_rect()
    authored_treatment_id, authored_multiplier = _authored_treatment(catalog)

    commands: list[DrawCommand] = list(extra_commands)
    expected_calculations: set[tuple[object, ...]] | None = set() if collect_evidence else None
    actual_calculations: set[tuple[object, ...]] | None = set() if collect_evidence else None
    water_rows: dict[
        tuple[tuple[int, int], str],
        list[
            tuple[
                tuple[int, int],
                object,
                str,
                LightLevel | None,
                str,
                tuple[float, float, float],
                tuple[int, float, float, int, tuple[str, ...]],
            ]
        ],
    ] = {}
    candidate_count = 0
    static_draws = 0

    terrain_bindings = cast(Mapping[str, object], catalog.bindings["terrain"])
    cliff_profile = cast(Mapping[str, object], catalog.bindings["terrain_cliff"])
    stair_profile = cast(Mapping[str, object], catalog.bindings["terrain_stairs"])
    cliff_rise = cast(int, cliff_profile["rise_steps"])
    flights = _stair_runs(target, stair_profile)
    lower_by_middle = {middle.position: lower for lower, middle, _, _ in flights}
    flight_exits = {(upper.position, middle.position) for _, middle, upper, _ in flights}
    terrain_pose = camera_pose("east", camera.quadrant)
    raster_terrain: dict[
        Material,
        tuple[str, tuple[int, int], tuple[int, int, int, int]],
    ] = {}
    for material in (Material.EARTH, Material.WOOD, Material.STONE):
        material_bindings = cast(Mapping[str, str], terrain_bindings[material.value])
        material_asset_id = material_bindings[terrain_pose]
        raster_terrain[material] = (
            material_asset_id,
            cache.scaled(material_asset_id, camera.zoom).get_size(),
            cache.alpha_bounds(material_asset_id, camera.zoom),
        )
    for position, tile in target.tiles.items():
        candidate_count += 1
        contact = project_screen(
            position,
            camera,
            elevation_steps=tile.elevation_steps,
        )
        lower_datum = lower_by_middle.get(position)
        if tile.elevation_steps >= cliff_rise or lower_datum is not None:
            # The lower raster closes the solid terrain body. It is not a
            # second support or a disclosure claim at this XY/height.
            bed_height = (lower_datum.elevation_steps if lower_datum is not None
                          else tile.elevation_steps - cliff_rise)
            bed_id = raster_terrain[Material(cliff_profile["bed_material"])][0]
            bed_contact = project_screen(position, camera, elevation_steps=bed_height)
            prepared = _static_blit(cache, bed_id, camera, bed_contact, authored_multiplier, screen)
            if prepared is not None:
                bed, destination = prepared
                commands.append((
                    painter_key(position, elevation_steps=bed_height, quadrant=camera.quadrant,
                                role="terrain_bed", identity=tile.tile_uuid),
                    bed, destination, 0,
                    (tile.tile_uuid, position, bed_id, "structural", None, authored_treatment_id,
                     "terrain_bed", bed_height, tile.elevation_steps),
                ))
        if tile.elevation_steps >= cliff_rise:
            faces = []
            lower_supports = []
            for direction in CardinalDirection:
                _, neighbor_position = _incident_positions(position, direction)
                neighbor = target.tiles.get(neighbor_position)
                if neighbor is None or neighbor.elevation_steps >= tile.elevation_steps:
                    continue
                if (position, neighbor_position) in flight_exits:
                    continue
                if tile.elevation_steps - neighbor.elevation_steps != cliff_rise:
                    # A bank beside the middle tread meets the same full
                    # cliff face, partly covered by the accepted flight.
                    flight_lower = lower_by_middle.get(neighbor_position)
                    if (flight_lower is None
                            or tile.elevation_steps - flight_lower.elevation_steps != cliff_rise):
                        raise RuntimeError(f"unsupported cliff rise at {position}/{direction.value}")
                    lower_supports.append(flight_lower)
                faces.append(direction)
                lower_supports.append(neighbor)
            if faces:
                if len(faces) == 1:
                    pose = camera_pose(faces[0].value, camera.quadrant)
                    table = cast(Mapping[str, str], cliff_profile["straight"])
                else:
                    corner_faces = cast(Mapping[str, list[str]], cliff_profile["corner_faces"])
                    base_pose = next((p for p, normals in corner_faces.items()
                                      if set(normals) == {face.value for face in faces}), None)
                    if base_pose is None:
                        raise RuntimeError(f"unsupported cliff corner at {position}")
                    poses = ("e", "s", "w", "n")
                    pose = poses[(poses.index(base_pose) + camera.quadrant) % 4]
                    table = cast(Mapping[str, str], cliff_profile["corner"])
                asset_id = table[pose]
                base_height = tile.elevation_steps - cliff_rise
                cliff_contact = project_screen(position, camera, elevation_steps=base_height)
                prepared = _static_blit(cache, asset_id, camera, cliff_contact, authored_multiplier, screen)
                if prepared is not None:
                    surface, destination = prepared
                    commands.append((
                        painter_key(position, elevation_steps=base_height, quadrant=camera.quadrant,
                                    role=cast(str, cliff_profile["role"]), identity=tile.tile_uuid, direction=pose),
                        surface, destination, 0,
                        (tile.tile_uuid, (position, tuple(face.value for face in faces)), asset_id,
                         "structural", None, authored_treatment_id, "cliff", base_height,
                         tile.elevation_steps, tuple(_support_evidence(target, support)
                                                    for support in (tile, *lower_supports))),
                    ))
        if lower_datum is not None:
            continue  # The complete flight, not a floating flat floor, shows this support.
        if tile.surface.base_material is Material.WATER:
            current = position in senses.visible
            remembered = position in senses.seen
            level = senses.effective_light_levels.get(position) if current else None
            if current:
                if level is None:
                    raise RuntimeError(
                        f"visible support {position} lacks effective light"
                    )
                state = "current"
                treatment_id, multiplier = _treatment(catalog, level)
            elif remembered:
                state = "memory"
                treatment_id, multiplier = _treatment(catalog, None)
            else:
                state = "authored"
                treatment_id, multiplier = (
                    authored_treatment_id,
                    authored_multiplier,
                )
            identity = tile.tile_uuid
            owner_chunk = (position[0] // 16, position[1] // 16)
            water_rows.setdefault((owner_chunk, state), []).append((
                position,
                identity,
                state,
                level,
                treatment_id,
                multiplier,
                painter_key(
                    position,
                    elevation_steps=tile.elevation_steps,
                    quadrant=camera.quadrant,
                    role="water",
                    identity=identity,
                ),
            ))
            continue
        material_row = raster_terrain.get(tile.surface.base_material)
        if material_row is None:
            raise RuntimeError(
                "unsupported raster terrain material: "
                f"{tile.surface.base_material.value}"
            )
        asset_id, full_size, alpha_bounds = material_row
        full_destination = cache.blit_position(asset_id, camera.zoom, contact)
        if (
            full_destination[0] >= screen_rect.right
            or full_destination[1] >= screen_rect.bottom
            or full_destination[0] + full_size[0] <= screen_rect.left
            or full_destination[1] + full_size[1] <= screen_rect.top
        ):
            continue
        current = position in senses.visible
        remembered = position in senses.seen
        level = senses.effective_light_levels.get(position) if current else None
        if current:
            if level is None:
                raise RuntimeError(f"visible support {position} lacks effective light")
            state = "current"
            treatment_id, multiplier = _treatment(catalog, level)
        elif remembered:
            state = "memory"
            treatment_id, multiplier = _treatment(catalog, None)
        else:
            state = "authored"
            treatment_id, multiplier = authored_treatment_id, authored_multiplier
        offset_x, offset_y, _, _ = alpha_bounds
        surface = cache.cropped_treated(asset_id, camera.zoom, multiplier)
        destination = (
            full_destination[0] + offset_x,
            full_destination[1] + offset_y,
        )
        evidence = (
            tile.tile_uuid,
            position,
            asset_id,
            state,
            level.value if level is not None else None,
            treatment_id,
        )
        commands.append((
            painter_key(
                position,
                elevation_steps=tile.elevation_steps,
                quadrant=camera.quadrant,
                role="terrain",
                identity=tile.tile_uuid,
            ),
            surface,
            destination,
            0,
            evidence,
        ))

    stair_assets = cast(Mapping[str, str], stair_profile["poses"])
    for lower, middle, upper, downhill in flights:
        pose = camera_pose(downhill.value, camera.quadrant)
        asset_id = stair_assets[pose]
        contacts = tuple(project_screen(t.position, camera, elevation_steps=t.elevation_steps)
                         for t in (lower, middle, upper))
        prepared = _static_blit(cache, asset_id, camera, contacts[0], authored_multiplier, screen)
        if prepared is not None:
            surface, destination = prepared
            identities = tuple(str(t.tile_uuid) for t in (lower, middle, upper))
            commands.append((
                painter_key(middle.position, elevation_steps=middle.elevation_steps,
                            quadrant=camera.quadrant, role=cast(str, stair_profile["role"]),
                            identity=identities, direction=pose),
                surface, destination, 0,
                (identities, tuple(t.position for t in (lower, middle, upper)), asset_id,
                 "structural", None, authored_treatment_id, "stairs",
                 tuple(_support_evidence(target, t) for t in (lower, middle, upper)), contacts),
            ))

    water_pixel_count = 0
    water_chunk_count = 0
    for (owner_chunk, water_state), rows in sorted(water_rows.items()):
        water_mask = cache.scaled(cast(str, catalog.water["mask"]), camera.zoom)
        ripple = cache.rgb(cast(str, catalog.water["ripple"]))
        normal = cache.rgb(cast(str, catalog.water["normal"]))
        water_asset = cast(str, terrain_bindings[Material.WATER.value])
        water_spec = catalog.resources[cast(str, catalog.water["mask"])]
        water_mask_pixels = cache.qualified_alpha_pixels(
            cast(str, catalog.water["mask"]),
            camera.zoom,
            float(cast(float, catalog.water["alphaCutoff"])),
        ) if collect_evidence else 0
        packed: list[WaterSupportInput] = []
        retained_rows: list[tuple[
            tuple[int, int], object, str, LightLevel | None, str,
            tuple[int, float, float, int, tuple[str, ...]],
        ]] = []
        for position, identity, state, level, treatment_id, multiplier, key in rows:
            tile = target.tiles[position]
            source_origin = water_source_origin(
                position,
                pivot=water_spec.pivot,
                asset_scale=water_spec.scale,
            )
            contact = project_screen(
                position,
                camera,
                elevation_steps=tile.elevation_steps,
            )
            destination = cache.blit_position(
                cast(str, catalog.water["mask"]),
                camera.zoom,
                contact,
            )
            if not _visible_rect(water_mask, destination, screen):
                continue
            packed.append(WaterSupportInput(
                source_origin_px=source_origin,
                destination_px=destination,
                multiplier=multiplier,
            ))
            retained_rows.append((position, identity, state, level, treatment_id, key))
        if not packed:
            continue
        batch_time = (
            presentation_time
            if water_state in {"current", "authored"}
            else 0.0
        )
        if expected_calculations is not None:
            expected_raw = (
                owner_chunk,
                (
                    min(row.destination_px[0] for row in packed),
                    min(row.destination_px[1] for row in packed),
                    max(row.destination_px[0] + water_mask.get_width() for row in packed),
                    max(row.destination_px[1] + water_mask.get_height() for row in packed),
                ),
                water_mask_pixels * len(packed),
                batch_time,
                "water.unity-material",
            )
            expected_calculations.add(expected_raw)
        batch = render_water_batch(
            mask_surface=water_mask,
            ripple_texture=ripple,
            normal_texture=normal,
            supports=packed,
            framebuffer_size=screen.get_size(),
            tile_width_px=TILE_WIDTH,
            render_scale=camera.zoom,
            time_seconds=batch_time,
            material=catalog.water,
        )
        if actual_calculations is not None:
            actual_calculations.add((
                owner_chunk,
                batch.destination_bounds,
                batch.evaluated_pixels,
                batch_time,
                "water.unity-material",
            ))
        water_chunk_count += 1
        water_pixel_count += batch.evaluated_pixels
        for surface, destination, row in zip(
            batch.surfaces,
            batch.destinations,
            retained_rows,
            strict=True,
        ):
            position, identity, state, level, treatment_id, key = row
            evidence = (
                identity,
                position,
                water_asset,
                state,
                level.value if level is not None else None,
                treatment_id,
            )
            commands.append((
                key,
                surface,
                destination,
                pygame.BLEND_PREMULTIPLIED,
                evidence,
            ))

    stone_straight_bindings = cast(
        Mapping[str, str], catalog.bindings["stone_wall_straight"]
    )
    stone_corner_bindings = cast(
        Mapping[str, str], catalog.bindings["stone_wall_corner"]
    )
    wood_straight_bindings = cast(
        Mapping[str, str], catalog.bindings["wood_wall_straight"]
    )
    wood_corner_bindings = cast(
        Mapping[str, str], catalog.bindings["wood_wall_corner"]
    )
    frame_bindings = cast(Mapping[str, str], catalog.bindings["stone_door_frame"])
    closed_bindings = cast(Mapping[str, str], catalog.bindings["wood_door_closed"])
    open_bindings = cast(Mapping[str, str], catalog.bindings["wood_door_open"])
    wall_rows: dict[
        tuple[tuple[int, int], Material],
        list[
            tuple[
                UUID,
                WorldObjectState | PlayerObject,
                CardinalDirection,
                str,
                LightLevel | None,
                str,
                tuple[float, float, float],
            ]
        ],
    ] = {}
    for object_uuid, world_object in sorted(target.objects.items(), key=lambda row: str(row[0])):
        structure = world_object.item.boundary_structure
        direction = world_object.placement.boundary_direction
        if structure is None or direction is None:
            continue
        disclosure = _boundary_disclosure(
            target,
            world_object.placement.position,
            direction,
        )
        if disclosure is None:
            state, level = "authored", None
            treatment_id, multiplier = authored_treatment_id, authored_multiplier
        else:
            state, level = disclosure, None
            if state == "memory":
                treatment_id, multiplier = _treatment(catalog, None)
            else:
                treatment_id, multiplier = authored_treatment_id, authored_multiplier
        pose = camera_pose(direction.value, camera.quadrant)
        position = world_object.placement.position
        base_height = world_object.placement.base_height_steps
        contact = project_screen(position, camera, elevation_steps=base_height)
        if structure.structure is BoundaryStructureKind.DOOR:
            if structure.material is not Material.WOOD:
                raise RuntimeError(
                    f"unsupported boundary material: {structure.material.value}"
                )
            frame_id = frame_bindings[pose]
            prepared_frame = _static_blit(
                cache, frame_id, camera, contact, multiplier, screen
            )
            if prepared_frame is not None:
                frame, frame_destination = prepared_frame
                commands.append((
                    painter_key(
                        position,
                        elevation_steps=base_height,
                        quadrant=camera.quadrant,
                        role="frame",
                        identity=object_uuid,
                        direction=pose,
                        boundary_poses=(pose,),
                    ),
                    frame,
                    frame_destination,
                    0,
                    (
                        object_uuid,
                        (position, direction.value),
                        frame_id,
                        state,
                        level.value if level is not None else None,
                        treatment_id,
                        "door_frame",
                        base_height,
                    ),
                ))
            if object_uuid not in senses.objects:
                continue
            is_open = world_object.item.is_open
            if is_open is None:
                raise RuntimeError("disclosed DirectionalDoor has no state")
            leaf_id = (open_bindings if is_open else closed_bindings)[pose]
            prepared_leaf = _static_blit(
                cache, leaf_id, camera, contact, multiplier, screen
            )
            if prepared_leaf is not None:
                leaf, leaf_destination = prepared_leaf
                commands.append((
                    painter_key(
                        position,
                        elevation_steps=base_height,
                        quadrant=camera.quadrant,
                        role="leaf",
                        identity=object_uuid,
                        direction=pose,
                        boundary_poses=(pose,),
                    ),
                    leaf,
                    leaf_destination,
                    0,
                    (
                        object_uuid,
                        (position, direction.value),
                        leaf_id,
                        state,
                        level.value if level is not None else None,
                        treatment_id,
                        "door_leaf",
                        base_height,
                        is_open,
                    ),
                ))
        elif structure.structure is BoundaryStructureKind.WALL:
            if structure.material not in {Material.STONE, Material.WOOD}:
                raise RuntimeError(
                    f"unsupported boundary material: {structure.material.value}"
                )
            wall_rows.setdefault((position, structure.material), []).append((
                object_uuid,
                world_object,
                direction,
                state,
                level,
                treatment_id,
                multiplier,
            ))
        else:
            raise RuntimeError(
                "unsupported boundary structure: "
                f"{structure.structure.value}"
            )

    for (position, material), rows in sorted(
        wall_rows.items(),
        key=lambda item: (item[0][0], item[0][1].value),
    ):
        if material is Material.STONE:
            straight_bindings = stone_straight_bindings
            corner_bindings = stone_corner_bindings
        elif material is Material.WOOD:
            straight_bindings = wood_straight_bindings
            corner_bindings = wood_corner_bindings
        else:
            raise RuntimeError(f"unsupported wall material: {material.value}")
        representative = (
            _corner_representative(frozenset(row[2] for row in rows))
            if len(rows) == 2
            else None
        )
        same_treatment_and_height = (
            len(rows) == 2
            and (rows[0][5], rows[0][6])
            == (rows[1][5], rows[1][6])
            and rows[0][1].placement.base_height_steps
            == rows[1][1].placement.base_height_steps
        )
        if representative is not None and same_treatment_and_height:
            source_ids = tuple(sorted(str(row[0]) for row in rows))
            directions = tuple(sorted(row[2].value for row in rows))
            state = "current" if any(row[3] == "current" for row in rows) else rows[0][3]
            pose = camera_pose(representative.value, camera.quadrant)
            asset_id = corner_bindings[pose]
            base_height = rows[0][1].placement.base_height_steps
            contact = project_screen(position, camera, elevation_steps=base_height)
            prepared = _static_blit(
                cache, asset_id, camera, contact, rows[0][6], screen
            )
            if prepared is not None:
                surface, destination = prepared
                commands.append((
                    painter_key(
                        position,
                        elevation_steps=base_height,
                        quadrant=camera.quadrant,
                        role="wall",
                        identity=source_ids,
                        direction=pose,
                        boundary_poses=tuple(camera_pose(row[2].value, camera.quadrant) for row in rows),
                    ),
                    surface,
                    destination,
                    0,
                    (
                        source_ids,
                        (position, directions),
                        asset_id,
                        state,
                        None,
                        rows[0][5],
                        "wall_corner",
                        base_height,
                    ),
                ))
            continue

        for object_uuid, world_object, direction, state, level, treatment_id, multiplier in rows:
            pose = camera_pose(direction.value, camera.quadrant)
            asset_id = straight_bindings[pose]
            base_height = world_object.placement.base_height_steps
            contact = project_screen(position, camera, elevation_steps=base_height)
            prepared = _static_blit(
                cache, asset_id, camera, contact, multiplier, screen
            )
            if prepared is None:
                continue
            surface, destination = prepared
            commands.append((
                painter_key(
                    position,
                    elevation_steps=base_height,
                    quadrant=camera.quadrant,
                    role="wall",
                    identity=object_uuid,
                    direction=pose,
                    boundary_poses=(pose,),
                ),
                surface,
                destination,
                0,
                (
                    object_uuid,
                    (position, direction.value),
                    asset_id,
                    state,
                    level.value if level is not None else None,
                    treatment_id,
                    "wall",
                    base_height,
                ),
            ))
    animated_fixtures = 0
    flame_index: int | None = None
    for fixture_uuid, fixture in target.objects.items():
        binding = catalog.props.get(fixture.item.item_id)
        if binding is None or fixture_uuid not in senses.objects:
            continue
        fixture_state = fixture.item
        position = fixture.placement.position
        disclosure = _disclosure(target, (position,))
        if disclosure is not None:
            state, level = disclosure
            treatment_id, multiplier = _treatment(catalog, level)
            pose = camera_pose((fixture.placement.orientation or CardinalDirection.EAST).value, camera.quadrant)
            body_id = binding.body_by_pose[pose]
            base_height = fixture.placement.base_height_steps
            contact = project_screen(position, camera, elevation_steps=base_height)
            prepared_body = _static_blit(
                cache, body_id, camera, contact, multiplier, screen
            )
            body_evidence = (
                fixture_uuid,
                fixture_state.is_lit,
                body_id,
                state,
                level.value if level is not None else None,
                treatment_id,
                None,
                None,
                base_height,
            )
            if prepared_body is not None:
                body, destination = prepared_body
                commands.append((
                    painter_key(
                        position,
                        elevation_steps=base_height,
                        quadrant=camera.quadrant,
                        role="object",
                        identity=fixture_uuid,
                    ),
                    body,
                    destination,
                    0,
                    body_evidence,
                ))
            loop = binding.lit_animation
            if fixture_state.is_lit and loop is not None:
                flame_index = flame_frame_index(
                    presentation_time,
                    frame_count=len(loop.frames),
                    fps=loop.fps,
                )
                flame_id = loop.frames[flame_index]
                flame = cache.scaled(flame_id, camera.zoom)
                flame_destination = cache.blit_position(flame_id, camera.zoom, contact)
                flame_evidence = body_evidence[:-3] + (
                    flame_id,
                    flame_index,
                    base_height,
                )
                if _visible_rect(flame, flame_destination, screen):
                    commands.append((
                        painter_key(
                            position,
                            elevation_steps=base_height,
                            quadrant=camera.quadrant,
                            role="torch_flame",
                            identity=fixture_uuid,
                        ),
                        flame,
                        flame_destination,
                        0,
                        flame_evidence,
                    ))
                    animated_fixtures += 1

    commands.sort(key=lambda row: row[0])
    expected_draws = tuple(command[4] for command in commands) if collect_evidence else ()
    actual_draws: list[tuple[object, ...]] | None = [] if collect_evidence else None
    for _, surface, destination, special_flags, evidence in commands:
        screen.blit(surface, destination, special_flags=special_flags)
        if actual_draws is not None:
            actual_draws.append(evidence)
        static_draws += 1

    grid_tiles = tuple(target.tiles.values()) if show_grid else ()
    grid_candidates = len(grid_tiles)
    grid_draws = 0
    if show_grid:
        for tile in grid_tiles:
            contact = project_screen(
                tile.position,
                camera,
                elevation_steps=tile.elevation_steps,
            )
            half_w = TILE_WIDTH * camera.zoom / 2
            half_h = TILE_HEIGHT * camera.zoom / 2
            bounds = pygame.Rect(
                round(contact[0] - half_w),
                round(contact[1] - half_h),
                max(1, round(half_w * 2)),
                max(1, round(half_h * 2)),
            )
            if not bounds.colliderect(screen_rect):
                continue
            pygame.draw.polygon(
                screen,
                (105, 120, 150),
                (
                    (contact[0] - half_w, contact[1]),
                    (contact[0], contact[1] - half_h),
                    (contact[0] + half_w, contact[1]),
                    (contact[0], contact[1] + half_h),
                ),
                width=1,
            )
            grid_draws += 1

    frame_evidence = None
    if expected_calculations is not None and actual_calculations is not None and actual_draws is not None:
        frame_evidence = FrameEvidence(
            expected_calculations=frozenset(expected_calculations),
            actual_calculations=frozenset(actual_calculations),
            expected_draws=expected_draws,
            actual_draws=tuple(actual_draws),
            candidate_coordinates=candidate_count,
            static_draws=static_draws,
            water_chunks=water_chunk_count,
            water_pixels=water_pixel_count,
            grid_candidates=grid_candidates,
            grid_draws=grid_draws,
            animated_fixtures=animated_fixtures,
            flame_frame=flame_index,
        )
    if not show_debug:
        return frame_evidence

    hover_text = "hover: outside world"
    boundary_text = "boundaries=none"
    if mouse_position is not None:
        chosen, tested = pick_support(
            mouse_position,
            camera,
            target.tiles.values(),
        )
        if chosen is not None:
            tile = target.tiles[chosen.position]
            presentation_state = (
                "current"
                if chosen.position in senses.visible
                else "memory"
                if chosen.position in senses.seen
                else "authored"
            )
            contact = project_screen(
                chosen.position,
                camera,
                elevation_steps=chosen.elevation_steps,
            )
            hover_text = (
                f"hover={chosen.position} z={chosen.elevation_steps} ({chosen.elevation_steps * 5}ft) "
                f"material={tile.surface.base_material.value} "
                f"surface={tile.surface_kind.value} axis={tile.slope_axis.value if tile.slope_axis else '-'} "
                f"zpx={-chosen.elevation_steps * 64} contact={tuple(round(v, 1) for v in contact)} "
                f"state={presentation_state} tested={tested} tile={chosen.tile_uuid}"
            )
            boundary_rows = []
            for object_uuid, world_object in sorted(
                target.objects.items(), key=lambda row: str(row[0])
            ):
                structure = world_object.item.boundary_structure
                direction = world_object.placement.boundary_direction
                if (
                    world_object.placement.position != chosen.position
                    or structure is None
                    or direction is None
                ):
                    continue
                boundary_rows.append(
                    f"{object_uuid}/{structure.structure.value}/"
                    f"{structure.material.value}/{direction.value}/"
                    f"z{world_object.placement.base_height_steps}"
                )
            if boundary_rows:
                boundary_text = "boundaries=" + "; ".join(boundary_rows)
        else:
            hover_text = f"hover: outside world tested_z={tested}"

    center = camera.viewport[0] / 2, camera.viewport[1] / 2
    center_anchor = inverse_plane(center, camera)
    center_pixel = round(center[0]), round(center[1])
    pygame.draw.line(
        screen,
        (255, 245, 125),
        (center_pixel[0] - 6, center_pixel[1]),
        (center_pixel[0] + 6, center_pixel[1]),
        width=1,
    )
    pygame.draw.line(
        screen,
        (255, 245, 125),
        (center_pixel[0], center_pixel[1] - 6),
        (center_pixel[0], center_pixel[1] + 6),
        width=1,
    )

    font = cache.debug_font
    viewpoint, looking = CAMERA_LABELS[camera.quadrant]
    diagnostic = [
        f"E/R/D={revisions[0]}/{revisions[1]}/{revisions[2]} T={presentation_time:.2f}",
        f"camera=q{camera.quadrant} viewpoint={viewpoint} looking={looking} "
        f"zoom={camera.zoom:.2f} pan=({camera.pan[0]:.0f},{camera.pan[1]:.0f})",
        f"extent=full-structural center_world=({center_anchor[0]:.3f},{center_anchor[1]:.3f})",
        f"world={len(target.tiles)} visible={len(senses.visible)} seen={len(senses.seen)} candidates={candidate_count}",
        f"draws={static_draws} grid={grid_draws}/{grid_candidates} "
        f"water_chunks={water_chunk_count} water_px={water_pixel_count} flame={flame_index}",
        f"cache hit/rebuild={cache.cache_hits}/{cache.cache_rebuilds}",
        hover_text,
        boundary_text,
    ]
    y = 6
    for text in diagnostic:
        screen.blit(font.render(text, True, (235, 235, 240)), (8, y))
        y += 18
    compass_origin = (92, y + 30)
    north_axis, east_axis = camera_axis_vectors(camera.quadrant)
    for label, axis, color in (
        ("N", north_axis, (100, 190, 255)),
        ("E", east_axis, (255, 185, 95)),
    ):
        endpoint = (
            round(compass_origin[0] + axis[0] * 0.55),
            round(compass_origin[1] + axis[1] * 0.55),
        )
        pygame.draw.line(screen, color, compass_origin, endpoint, width=2)
        screen.blit(font.render(label, True, color), (endpoint[0] - 4, endpoint[1] - 8))
    rail_x = max(8, screen.get_width() - 430)
    y = 6
    for text in (*objective_lines[-18:], *subjective_lines[-8:]):
        screen.blit(font.render(text[:72], True, (210, 215, 225)), (rail_x, y))
        y += 17

    return frame_evidence
