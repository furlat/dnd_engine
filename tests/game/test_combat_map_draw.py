"""Real map pixels compose retained casts with cliffs and boundary walls."""

from dataclasses import dataclass, replace
from typing import Iterator, Mapping, cast

import numpy as np
import pygame
import pytest

from dnd.types.world import CardinalDirection
from game.animation import CastSample, CastTimeline, compile_cast, sample_cast
from game.animation_data import load_animation_data
from game.animation_draw import AnimationMedia, animation_draw_commands, load_animation_media
from game.app import draw_frame
from game.assets import AssetCatalog, SurfaceCache, load_catalog
from game.combat import BoundCast, bind_cast
from game.combat_demo import iter_combat_demo
from game.presentation import CompletedLineage, PresentationTarget
from game.projection import Camera, camera_pose, project_screen


@dataclass
class MapScene:
    screen: pygame.Surface
    catalog: AssetCatalog
    cache: SurfaceCache
    target: PresentationTarget
    cast: BoundCast
    media: AnimationMedia


@pytest.fixture(scope="module")
def scene() -> Iterator[MapScene]:
    with pytest.MonkeyPatch.context() as environment:
        environment.setenv("SDL_VIDEODRIVER", "dummy")
        environment.setenv("SDL_AUDIODRIVER", "dummy")
        pygame.init()
        screen = pygame.display.set_mode((1000, 800))
        scenario = iter_combat_demo(caster_position=(16, 24))
        target, lineage = next(scenario), next(scenario)
        assert isinstance(target, PresentationTarget)
        assert isinstance(lineage, CompletedLineage)
        # This fixture also protects the original point-dart depth regression.
        # The playable game selects the authored sprite bundle separately.
        cast = bind_cast(target, lineage, load_animation_data(authored_bundles=()))
        catalog = load_catalog()
        media = load_animation_media(cast.timeline, cast.appearances)
        try:
            yield MapScene(screen, catalog, SurfaceCache(catalog), target, cast, media)
        finally:
            scenario.close()
            pygame.quit()


def frame_pixels(scene: MapScene, target: PresentationTarget, camera: Camera,
                 timeline: CastTimeline, sample: CastSample | None) -> np.ndarray:
    evidence = draw_frame(
        scene.screen, target, scene.catalog, scene.cache, camera, 1.0,
        show_grid=False, mouse_position=None,
        extra_commands=animation_draw_commands(timeline, sample, scene.media, camera) if sample is not None else (),
    )
    assert evidence.actual_draws == evidence.expected_draws
    return pygame.surfarray.array3d(scene.screen)


def caster_mask(scene: MapScene, timeline: CastTimeline, sample: CastSample,
                camera: Camera) -> np.ndarray:
    command = next(
        row for row in animation_draw_commands(timeline, sample, scene.media, camera)
        if row[4][0] == timeline.source.caster.actor_uuid and row[4][6] == "actor"
    )
    layer = pygame.Surface(scene.screen.get_size(), pygame.SRCALPHA)
    layer.blit(command[1], command[2])
    return pygame.surfarray.array_alpha(layer) >= 250


@pytest.mark.parametrize("quadrant", [0, 3])
def test_real_lower_caster_is_partly_occluded_by_the_terrace_cliff(
    scene: MapScene, quadrant: int,
) -> None:
    timeline = scene.cast.timeline
    assert timeline.source.caster.elevation_steps == 0
    assert timeline.source.applications[0].target.elevation_steps == 2
    camera = Camera(quadrant=quadrant, zoom=1, viewport=scene.screen.get_size()).with_focus(
        (16, 22), elevation_steps=1,
    )
    sample = sample_cast(timeline, 1000)
    assert sample.projectiles[0].phase == "travel"
    bare_map = frame_pixels(scene, scene.target, camera, timeline, None)
    with_cast = frame_pixels(scene, scene.target, camera, timeline, sample)
    body = caster_mask(scene, timeline, sample, camera)
    changed = np.any(with_cast != bare_map, axis=2)
    # Drawing every actor over the map loses the hidden pixels; drawing actors
    # behind the entire terrain loses the visible pixels. Both must coexist.
    assert np.count_nonzero(body & changed) > 0
    assert np.count_nonzero(body & ~changed) > 0


@pytest.mark.parametrize("quadrant", range(4))
def test_height_arc_keeps_the_bolt_visible_above_the_upper_stair(
    scene: MapScene, quadrant: int,
) -> None:
    # Exercise the map drawing boundary at the integrated scene's stair-mouth
    # contact, with its explicit height arc and the same imported sprite data.
    original = scene.cast.timeline
    source = replace(original.source,
                     caster=replace(original.source.caster, grid=(16, 25)),
                     applications=(replace(original.source.applications[0], travel_apex_steps=1),))
    timeline = compile_cast(original.data, "spell.fire_bolt", source)
    travel = next(phase for phase in timeline.applications[0].projectile_intervals if phase.name == "travel")
    sample = sample_cast(timeline, travel.start_ms + .6 * (travel.end_ms - travel.start_ms))
    camera = Camera(quadrant=quadrant, zoom=1, viewport=scene.screen.get_size()).with_focus(
        (16, 22.5), elevation_steps=1,
    )
    bare_map = frame_pixels(scene, scene.target, camera, timeline, None)
    with_cast = frame_pixels(scene, scene.target, camera, timeline, sample)
    effect = next(row for row in animation_draw_commands(timeline, sample, scene.media, camera)
                  if row[4][6] == "projectile")
    isolated = pygame.Surface(scene.screen.get_size())
    isolated.fill((0, 0, 0))
    isolated.blit(effect[1], effect[2], special_flags=effect[3])
    core = np.max(pygame.surfarray.array3d(isolated), axis=2) >= 160
    assert np.count_nonzero(core) > 0
    # The former straight path buried the effect in the upper stair. Require
    # its bright core to remain substantially visible through real map sorting.
    changed = np.any(with_cast != bare_map, axis=2)
    assert np.count_nonzero(core & changed) > np.count_nonzero(core) / 2


def test_point_dart_remains_visible_above_the_target_floor(scene: MapScene) -> None:
    source = replace(scene.cast.timeline.source,
                     caster=replace(scene.cast.timeline.source.caster, grid=(16, 25)),
                     applications=(replace(scene.cast.timeline.source.applications[0], travel_apex_steps=1),))
    timeline = compile_cast(scene.cast.timeline.data, "spell.magic_missile", source)
    media = load_animation_media(timeline, scene.cast.appearances)
    sample = sample_cast(timeline, timeline.applications[0].travel_end_ms - 0.25)
    camera = Camera(quadrant=0, zoom=1, viewport=scene.screen.get_size()).with_focus(
        (16, 22.5), elevation_steps=1,
    )
    effects = tuple(command for command in animation_draw_commands(timeline, sample, media, camera)
                    if command[4][6] == "projectile")
    assert len(effects) == 1
    bare = frame_pixels(scene, scene.target, camera, timeline, None)
    # Isolate the actual approaching head from actor overlap: its own floor
    # must not erase a point which is above that floor at the target attachment.
    draw_frame(scene.screen, scene.target, scene.catalog, scene.cache, camera, 1,
               show_grid=False, mouse_position=None, extra_commands=effects)
    composed = pygame.surfarray.array3d(scene.screen)
    isolated = pygame.Surface(scene.screen.get_size())
    isolated.fill((0, 0, 0))
    isolated.blit(effects[0][1], effects[0][2], special_flags=effects[0][3])
    head = np.max(pygame.surfarray.array3d(isolated), axis=2) >= 160
    assert np.count_nonzero(head) > 0
    visible = head & np.any(composed != bare, axis=2)
    assert np.count_nonzero(visible) > np.count_nonzero(head) / 2


@pytest.mark.parametrize("quadrant, wall_is_in_front", [(0, True), (2, False)])
@pytest.mark.parametrize("directions, binding", [
    ((CardinalDirection.EAST,), "stone_wall_straight"),
    ((CardinalDirection.NORTH, CardinalDirection.EAST), "stone_wall_corner"),
])
def test_same_cell_wall_face_occludes_according_to_camera_side(
    scene: MapScene, quadrant: int, wall_is_in_front: bool,
    directions: tuple[CardinalDirection, ...], binding: str,
) -> None:
    # The lodge's northeast corner supplies two actual retained boundary rows.
    # Compare a single face and the authored composite of both faces.
    walls = tuple(
        obj for obj in scene.target.objects.values()
        if obj.item.boundary_structure is not None
        and obj.item.boundary_structure.structure.value == "wall"
        and obj.placement.position == (31, 37)
        and obj.placement.boundary_direction in directions
    )
    assert len(walls) == len(directions)
    wall = walls[0]
    position = wall.placement.position
    height = wall.placement.base_height_steps
    target = replace(scene.target, objects={row.item.item_uuid: row for row in walls})
    camera = Camera(quadrant=quadrant, zoom=1, viewport=scene.screen.get_size()).with_focus(
        position, elevation_steps=height,
    )
    # This drawing-boundary case supplies a contact at an existing wall cell;
    # it does not claim the engine cast through that wall. Keep the real rig,
    # authored recipe, and direction so the same preloaded media is used.
    original = scene.cast.timeline
    source = replace(
        original.source,
        caster=replace(original.source.caster, grid=position, elevation_steps=height),
        applications=(replace(original.source.applications[0], target=replace(
            original.source.applications[0].target, grid=(position[0], position[1] - 4), elevation_steps=height,
        )),),
    )
    timeline = compile_cast(original.data, "spell.fire_bolt", source)
    sample = sample_cast(timeline, 0)
    bare_wall = frame_pixels(scene, target, camera, timeline, None)
    with_actor = frame_pixels(scene, target, camera, timeline, sample)
    poses = cast(Mapping[str, str], scene.catalog.bindings[binding])
    asset_id = poses[camera_pose("east", quadrant)]
    wall_pixels = pygame.Surface(scene.screen.get_size(), pygame.SRCALPHA)
    wall_pixels.blit(
        scene.cache.scaled(asset_id, camera.zoom),
        scene.cache.blit_position(asset_id, camera.zoom,
                                  project_screen(position, camera, elevation_steps=height)),
    )
    overlap = caster_mask(scene, timeline, sample, camera) & (
        pygame.surfarray.array_alpha(wall_pixels) == 255
    )
    assert np.count_nonzero(overlap) > 0
    changed = np.any(with_actor != bare_wall, axis=2)
    if wall_is_in_front:
        assert np.count_nonzero(overlap & changed) == 0
    else:
        assert np.count_nonzero(overlap & changed) > 0
