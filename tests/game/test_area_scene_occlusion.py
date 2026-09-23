"""An extended area picture must not overwrite a foreground boundary's pixels."""

from dataclasses import replace
from uuid import uuid4

import numpy as np
import pygame
import pytest

from game.animation import GroundContact, compile_cast, sample_cast
from game.animation_data import load_animation_data
from game.animation_draw import animation_draw_commands, load_animation_media
from dnd.types.world import CardinalDirection
from dnd.types.world_placement import WorldObjectPlacement, WorldPlacementKind
from game.area_media import AreaLayer, AreaMedia, BoundarySprite, compose_area, mask_ground_area
from game.draw_commands import DrawCommand
from game.app import draw_frame
from game.assets import SurfaceCache, load_catalog
from game.combat import bind_cast
from game.environment_art import load_environment_art
from game.environment_draw import environment_command
from game.projection import Camera, camera_pose, painter_key, project_screen
from tests.game.player_helpers import player_inputs
from tests.game.spell_handoff_scenarios import spell_handoff_history


@pytest.fixture(scope="module")
def rendering():
    with pytest.MonkeyPatch.context() as environment:
        environment.setenv("SDL_VIDEODRIVER", "dummy")
        environment.setenv("SDL_AUDIODRIVER", "dummy")
        pygame.init()
        screen = pygame.display.set_mode((800, 600))
        data, catalog = load_animation_data(), load_catalog()
        yield screen, data, catalog, SurfaceCache(catalog)
        pygame.quit()


@pytest.fixture(scope="module", params=("wall-east", "wall-north", "closed-door", "open-door"))
def scene(request, rendering):
    _, data, _, _ = rendering
    history = spell_handoff_history(program="fireball", environment=request.param)
    state, lineages = player_inputs(history.initialization, history.lineages)
    cast = bind_cast(state, lineages[0], data)
    return request.param, state, cast


def boundary_silhouette(state, catalog, cache, camera, *, close_doors=False):
    """Registered selected artwork, including the doorway's open/closed hole."""
    silhouette = pygame.Surface(camera.viewport, pygame.SRCALPHA)
    environment = load_environment_art()
    for identity, obj in state.objects.items():
        placement, item = obj.placement, obj.item
        boundary_pose = camera_pose(placement.boundary_direction.value, camera.quadrant)
        contact = project_screen(placement.position, camera,
                                 elevation_steps=placement.base_height_steps)
        if item.boundary_structure.structure.value == "wall":
            bindings = (catalog.bindings["stone_wall_straight"][boundary_pose],)
        else:
            door = environment.doors[item.item_id]
            bank = door.openings[item.door_swing.value]
            pose = ("e", "s", "w", "n")[
                (("e", "s", "w", "n").index(boundary_pose) - door.pose_offset) % 4]
            frame = bank.frame_count - 1 if item.is_open and not close_doors else 0
            command = environment_command(bank, frame, identity=identity,
                position=placement.position, elevation=placement.base_height_steps,
                pose=pose, boundary_pose=boundary_pose, camera=camera, multiplier=(1, 1, 1))
            silhouette.blit(command.surface, command.destination)
            bindings = (door.frame_resource_by_pose[boundary_pose],) if door.frame_resource_by_pose else ()
        for asset in bindings:
            silhouette.blit(cache.scaled(asset, camera.zoom),
                            cache.blit_position(asset, camera.zoom, contact))
    return silhouette


@pytest.mark.parametrize("quadrant", range(4))
@pytest.mark.parametrize("height", (0, 2))
@pytest.mark.parametrize("blend", (0, pygame.BLEND_RGB_ADD))
def test_area_cannot_overwrite_any_part_of_foreground_wall_or_door(rendering, scene, quadrant, height, blend):
    screen, data, catalog, cache = rendering
    environment, state, cast = scene
    north = environment == "wall-north"
    # Both sides of each real boundary, with camera rotation and raised support.
    # These are explicit presentation inputs, not claims of additional native casts.
    positive_camera = quadrant in ((0, 3) if north else (0, 1))
    across = 6 if positive_camera else 9
    center = (6, across) if north else (across, 6)
    state = replace(state, objects={identity: replace(obj, placement=
        obj.placement.model_copy(update={"base_height_steps": height, "top_height_steps": height + 1}))
        for identity, obj in state.objects.items()})
    source = replace(cast.timeline.source, applications=(), ground_target=GroundContact(center, height))
    timeline = compile_cast(data, "spell.fireball", source)
    boundaries = tuple(obj.placement for obj in state.objects.values()
                       if obj.item.is_open is not True)
    media = load_animation_media(timeline, {source.caster.actor_uuid: cast.appearances[source.caster.actor_uuid]},
                                 area_boundaries=boundaries)
    camera = Camera(quadrant=quadrant, zoom=.5, viewport=screen.get_size()).with_focus(center, elevation_steps=height)
    assert timeline.ground_delivery is not None
    sample = sample_cast(timeline, timeline.ground_delivery.travel_end_ms + 200)
    commands = tuple(row for row in animation_draw_commands(timeline, sample, media, camera)
                     if row[4][6] == "projectile" and row[4][8] == "impact" and row[3] == blend)
    assert commands, "Exercise each actual exported impact layer separately"

    silhouette = boundary_silhouette(state, catalog, cache, camera)
    closed_leaf = boundary_silhouette(state, catalog, cache, camera, close_doors=True)
    opaque = pygame.surfarray.array_alpha(silhouette) == 255
    isolated = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
    for command in commands:
        isolated.blit(command[1], command[2], special_flags=command[3])
    effect = np.max(pygame.surfarray.array3d(isolated), axis=2) > 0
    assert np.count_nonzero(effect & opaque) > 0, "The effect must actually overlap the foreground boundary"

    def pixels(extra):
        draw_frame(screen, state, catalog, cache, camera, 0, show_grid=False,
                   show_debug=False, mouse_position=None, extra_commands=extra)
        return pygame.surfarray.array3d(screen)

    bare, composed = pixels(()), pixels(commands)
    changed = np.any(composed != bare, axis=2)
    assert np.count_nonzero(changed & opaque) == 0, "Area fire/smoke painted over solid foreground pixels"
    assert np.count_nonzero(changed & ~opaque) > 0, "Exposed fire must remain visible"
    if environment == "open-door":
        opening = (pygame.surfarray.array_alpha(closed_leaf) == 255) & ~opaque
        assert np.count_nonzero(changed & opening) > 0, "The open doorway must actually admit the effect"


@pytest.mark.parametrize("quadrant", range(4))
@pytest.mark.parametrize("blend", (0, pygame.BLEND_RGB_ADD))
def test_area_reaches_exposed_rear_wall_face_without_reopening_space_beyond_it(rendering, scene, quadrant, blend):
    screen, data, catalog, cache = rendering
    environment, state, cast = scene
    north = environment == "wall-north"
    positive_camera = quadrant in ((0, 3) if north else (0, 1))
    across = 9 if positive_camera else 6
    center = (6, across) if north else (across, 6)
    source = replace(cast.timeline.source, applications=(), ground_target=GroundContact(center, 0))
    timeline = compile_cast(data, "spell.fireball", source)
    appearances = {source.caster.actor_uuid: cast.appearances[source.caster.actor_uuid]}
    boundaries = tuple(obj.placement for obj in state.objects.values() if obj.item.is_open is not True)
    media = load_animation_media(timeline, appearances, area_boundaries=boundaries)
    raw_media = replace(media, area=None)
    camera = Camera(quadrant=quadrant, zoom=.5, viewport=screen.get_size()).with_focus(center)
    assert timeline.ground_delivery is not None
    sample = sample_cast(timeline, timeline.ground_delivery.travel_end_ms + 200)

    def impacts(selected):
        return tuple(row for row in animation_draw_commands(timeline, sample, selected, camera)
                     if row[4][6] == "projectile" and row[4][8] == "impact" and row.blend == blend)

    commands, raw_commands = impacts(media), impacts(raw_media)
    silhouette = boundary_silhouette(state, catalog, cache, camera)
    opaque = pygame.surfarray.array_alpha(silhouette) == 255

    def effect_pixels(rows):
        result = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        for row in rows:
            result.blit(row.surface, row.destination, special_flags=row.blend)
        return np.max(pygame.surfarray.array3d(result), axis=2) > 0

    raw = effect_pixels(raw_commands)
    # Ground shadow is correct for empty space behind the wall, but its pixels
    # cannot stand in for the elevated surface which physically receives fire.
    from_ground = []
    assert media.area is not None
    for row in raw_commands:
        from_ground.append(row._replace(surface=mask_ground_area(row.surface, row.destination,
            center, 0, camera, media.area)))
    blocked = raw & ~effect_pixels(from_ground)
    receiving = blocked & opaque
    if environment != "open-door":
        assert np.count_nonzero(receiving) > 0, "Exercise fire previously clipped off an exposed face"

    def composed(rows):
        draw_frame(screen, state, catalog, cache, camera, 0, show_grid=False,
                   show_debug=False, mouse_position=None, extra_commands=rows)
        return pygame.surfarray.array3d(screen)

    changed = np.any(composed(commands) != composed(()), axis=2)
    if environment != "open-door":
        assert np.count_nonzero(changed & receiving) > 0, "Fire must actually touch the exposed wall face"
    empty = pygame.surfarray.array_alpha(silhouette) == 0
    assert not np.any(changed & blocked & empty), "Receiving wall pixels do not reopen space beyond the wall"


@pytest.mark.parametrize("quadrant", range(4))
@pytest.mark.parametrize("blend", (0, pygame.BLEND_RGB_ADD))
def test_wall_contact_respects_an_intervening_wall_and_foreground_body(rendering, quadrant, blend):
    screen, _, catalog, cache = rendering
    center = (3, 0) if quadrant in (0, 1) else (0, 0)
    far_x = -1 if quadrant in (0, 1) else 3
    camera = Camera(quadrant=quadrant, zoom=.5, viewport=screen.get_size()).with_focus(center)
    pose = camera_pose("east", quadrant)
    asset = catalog.bindings["stone_wall_straight"][pose]
    walls, commands, silhouettes = [], [], []
    partial_edges = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
    for x in (1, far_x):
        silhouette = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        for y in range(-5, 6):
            wall = WorldObjectPlacement(object_uuid=uuid4(), tile_uuid=uuid4(), position=(x, y),
                kind=WorldPlacementKind.BOUNDARY, occupies_bands=True,
                boundary_direction=CardinalDirection.EAST, base_height_steps=0, top_height_steps=2)
            image = cache.scaled(asset, camera.zoom)
            destination = cache.blit_position(asset, camera.zoom, project_screen(wall.position, camera))
            key = painter_key(wall.position, elevation_steps=0, quadrant=quadrant, role="wall",
                              identity=wall.object_uuid, direction=pose, boundary_poses=(pose,))
            walls.append(BoundarySprite((wall,), image, destination, key))
            commands.append(DrawCommand(key, image, destination, 0, ()))
            silhouette.blit(image, destination)
            partial = pygame.Surface(image.get_size(), pygame.SRCALPHA)
            opacity = pygame.surfarray.array_alpha(image)
            pygame.surfarray.pixels_alpha(partial)[:] = np.where((opacity > 0) & (opacity < 255), 255, 0)
            partial_edges.blit(partial, destination)
        silhouettes.append(pygame.surfarray.array_alpha(silhouette) == 255)
    raw = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
    raw.fill((80, 60, 40, 128))
    source_bytes = pygame.image.tobytes(raw, "RGBA")
    layer = AreaLayer(center, 0, AreaMedia(tuple(wall.placements[0] for wall in walls)))
    ground, contacts = compose_area(raw, (0, 0), layer, camera, walls, blend)
    effects = [DrawCommand(painter_key(center, elevation_steps=0, quadrant=quadrant,
                    role="projectile", identity="area"), ground, (0, 0), blend, ())]
    effects.extend(DrawCommand(row.key, row.image, row.destination, blend, ()) for row in contacts)

    def pixels(extra):
        screen.fill((11, 17, 23))
        for row in sorted((*commands, *extra), key=lambda row: row.key):
            screen.blit(row.surface, row.destination, special_flags=row.blend)
        return pygame.surfarray.array3d(screen)

    bare, lit = pixels(()), pixels(effects)
    changed = np.any(lit != bare, axis=2)
    near, far = silhouettes
    assert np.count_nonzero(far & ~near) > 0
    assert not np.any(changed & far & ~near), "An intervening wall blocks the farther wall's exposed top too"
    assert np.any(changed & near), "The first wall receives fire"
    assert pygame.image.tobytes(raw, "RGBA") == source_bytes
    # Adjacent opaque wall sprites overlap; each receives this layer once.
    # The pack has one translucent edge pixel per east sprite; general stacked
    # translucent surfaces are outside this opaque pixel-art composition test.
    expected = pygame.Surface(screen.get_size())
    pygame.surfarray.blit_array(expected, bare)
    expected.blit(raw, (0, 0), special_flags=blend)
    solid = near & (pygame.surfarray.array_alpha(partial_edges) == 0)
    assert np.array_equal(lit[solid], pygame.surfarray.array3d(expected)[solid])
    point = tuple(int(v) for v in np.argwhere(changed & near)[len(np.argwhere(changed & near)) // 2])
    body = pygame.Surface((20, 20))
    body.fill((20, 210, 90))
    actor = DrawCommand(painter_key(center, elevation_steps=0, quadrant=quadrant,
        role="actor", identity="foreground-body"), body, (point[0] - 10, point[1] - 10), 0, ())
    assert tuple(pixels((*effects, actor))[point]) == (20, 210, 90)
