"""Shared authored clocks and physical area pixels consume detached game facts."""

from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import pygame
import pytest

from dnd.core.life_types import LifeState
from dnd.types.world import CardinalDirection
from dnd.types.world_placement import WorldObjectPlacement, WorldPlacementKind
from game.animation import (
    ActorContact, CastApplication, CastInput, GroundContact, compile_cast,
    project_projectile, sample_cast,
)
from game.animation_data import load_animation_data
from game.area_media import AreaMedia, mask_ground_area
from game.projection import Camera, TILE_WIDTH, project_world


@pytest.fixture(scope="module")
def data():
    return load_animation_data(rig_files=tuple(sorted(Path("game/data/rigs").glob("*.json"))))


@pytest.fixture(scope="module", autouse=True)
def display():
    with pytest.MonkeyPatch.context() as environment:
        environment.setenv("SDL_VIDEODRIVER", "dummy")
        environment.setenv("SDL_AUDIODRIVER", "dummy")
        pygame.init()
        pygame.display.set_mode((8, 8))
        yield
        pygame.quit()


def caster():
    return ActorContact("caster", (2, 2), "E", 3, hp=30)


def test_area_is_one_ground_delivery_with_or_without_visible_recipients(data):
    actor = caster()
    first = ActorContact("first", (7, 5), "W", 2, hp=20)
    second = ActorContact("second", (8, 5), "W", 3, hp=30)
    ground = GroundContact((7, 5), 1)
    empty = compile_cast(data, "spell.fireball", CastInput("empty", actor, (), ground))
    populated = compile_cast(data, "spell.fireball", CastInput("populated", actor, (
        CastApplication("first-hit", first, True, 8, 12, damage_type="fire"),
        CastApplication("second-hit", second, True, 4, 26, damage_type="fire"),
    ), ground))
    assert empty.ground_delivery is not None and populated.ground_delivery is not None
    arrival = empty.ground_delivery.travel_end_ms
    assert populated.ground_delivery.travel_end_ms == arrival
    for timeline in (empty, populated):
        traveling = sample_cast(timeline, (timeline.release_ms + arrival) / 2)
        travel = [row for row in traveling.projectiles if row.phase == "travel"]
        impact = [row for row in sample_cast(timeline, arrival).projectiles if row.phase == "impact"]
        assert len(travel) == len(impact) == 1
        assert travel[0].application_id is None and impact[0].application_id is None
    before = sample_cast(populated, arrival - .01)
    impact = sample_cast(populated, arrival + .01)
    assert {row.actor_uuid: row.hp for row in before.vitals} == {"first": 20, "second": 30}
    assert {row.clip for row in impact.bodies if row.actor_uuid != actor.actor_uuid} == {data.damage_context.bodyClip}
    # The original recipe commits HP/numbers at its authored reaction frame.
    frame = populated.recipe.damage.floatingNumber.frame
    fps = data.rigs[first.rig_id].clips[data.damage_context.bodyClip].fps * data.damage_context.bodyPlaybackSpeed
    after = sample_cast(populated, arrival + frame * 1000 / fps + .01)
    assert {row.actor_uuid: row.hp for row in after.vitals} == {"first": 12, "second": 26}
    assert {row.application_id for row in after.numbers} == {"first-hit", "second-hit"}


@pytest.mark.parametrize("lethal", (False, True))
def test_self_affected_caster_has_one_body_track_before_during_and_after_hit(data, lethal):
    actor = caster()
    timeline = compile_cast(data, "spell.fireball", CastInput("self-area", actor, (
        CastApplication("self-hit", actor, True, 30 if lethal else 4, 0 if lethal else 26,
                        LifeState.DEAD if lethal else None, "fire"),
    ), GroundContact((3, 2))))
    application, = timeline.applications
    assert application.damage_start_ms is not None
    for time in (0, application.damage_start_ms - .01, application.damage_start_ms,
                 application.damage_end_ms + .01, timeline.complete_ms):
        sample = sample_cast(timeline, time)
        assert [row.actor_uuid for row in sample.bodies] == [actor.actor_uuid]
    assert sample_cast(timeline, 0).bodies[0].clip == timeline.recipe.cast.actionClip
    assert sample_cast(timeline, application.damage_start_ms).bodies[0].clip == (
        data.death_context.bodyClip if lethal else data.damage_context.bodyClip)
    assert sample_cast(timeline, timeline.complete_ms).bodies[0].clip == (
        data.death_context.bodyClip if lethal else "Idle")


def test_eldritch_overlapping_preparation_and_held_release_preserve_individual_hits(data):
    target = ActorContact("target", (7, 2), "W", 3, hp=30)
    timeline = compile_cast(data, "spell.eldritch_blast", CastInput("volley", caster(), (
        CastApplication("hit", target, True, 4, 26, damage_type="force"),
        CastApplication("miss", target, False, None, None),
        CastApplication("critical", target, True, 8, 18, damage_type="force"),
        CastApplication("last", target, True, 3, 15, damage_type="force"),
    )))
    launches = [row.travel_start_ms for row in timeline.applications]
    assert launches == pytest.approx([timeline.release_ms + index * 160 for index in range(4)])
    # Delivered preparation is a complete 72-frame/144-Hz strip, allowed to
    # overlap release rather than getting shortened to the release boundary.
    early = sample_cast(timeline, 333.333333 + .01)
    last_prepare = sample_cast(timeline, 833.333333 - .01)
    assert [(row.phase, row.column) for row in early.projectiles] == [("prepare", 260)]
    assert any(row.phase == "prepare" and row.column == 331 for row in last_prepare.projectiles)
    assert not any(row.phase == "prepare" for row in sample_cast(timeline, 833.333334).projectiles)
    for time in (timeline.release_ms, 800, launches[-1]):
        assert sample_cast(timeline, time).bodies[0].frame == timeline.recipe.cast.releaseFrame
    assert sample_cast(timeline, launches[-1] + 84).bodies[0].frame == timeline.recipe.cast.releaseFrame + 1
    for identity, hp in (("hit", 26), ("critical", 18), ("last", 15)):
        committed = next(anchor.at_ms for anchor in timeline.anchors
                         if anchor.name == "vitals" and anchor.application_id == identity)
        assert sample_cast(timeline, committed + .01).vitals[0].hp == hp
    assert timeline.applications[1].damage_start_ms is None
    miss_time = timeline.applications[1].travel_end_ms
    assert sample_cast(timeline, miss_time - .01).vitals[0].hp == sample_cast(timeline, miss_time + .01).vitals[0].hp
    final_numbers = sample_cast(timeline, timeline.applications[-1].hp_ms + .01).numbers
    assert "miss" not in {number.application_id for number in final_numbers}


@pytest.mark.parametrize("quadrant", range(4))
@pytest.mark.parametrize("horizontal_scale", (1.0, 1.4))
@pytest.mark.parametrize("phase", ("prepare", "travel"))
def test_authored_hand_pixel_is_final_socket_in_each_camera(data, quadrant, horizontal_scale, phase):
    actor = replace(caster(), elevation_steps=2, visual_scale_x=horizontal_scale)
    target = ActorContact("target", (7, 2), "W", 3, hp=30)
    timeline = compile_cast(data, "spell.eldritch_blast", CastInput("sockets", actor, (
        CastApplication("beam", target, False, None, None),
    )))
    time = 500 if phase == "prepare" else timeline.release_ms
    sample = sample_cast(timeline, time)
    original, = (row for row in sample.projectiles if row.phase == phase)
    projected = project_projectile(timeline, original, quadrant)
    asset = data.projectile_assets[projected.asset_id]
    facing = asset.rowOrder[projected.row]
    sockets = timeline.recipe.projectile.sourceSockets
    socket = sockets.preparation[facing][sample.bodies[0].frame] if phase == "prepare" else sockets.release[facing]
    assert socket is not None
    rig = data.rigs[actor.rig_id]
    origin = project_world(actor.grid, elevation_steps=actor.elevation_steps, quadrant=quadrant)
    reference_scale = data.rig.TILE_W / TILE_WIDTH
    expected = (
        origin[0] * reference_scale + (socket.x - rig.cell_width / 2) * actor.visual_scale * horizontal_scale,
        origin[1] * reference_scale + (socket.y - rig.cell_height + rig.origin_y_from_ground) * actor.visual_scale,
    )
    assert projected.point == pytest.approx(expected)


@pytest.mark.parametrize("quadrant", range(4))
@pytest.mark.parametrize("rig_id", ("neuroclient.modular", "smallscale.greywolf", "smallscale.demonbeast02"))
def test_impact_contacts_actual_target_rig_body_pixel(data, quadrant, rig_id):
    target = ActorContact("target", (7, 2), "W", 2.2, hp=30,
                          elevation_steps=2, visual_scale_x=1.4, rig_id=rig_id)
    timeline = compile_cast(data, "spell.guiding_bolt", CastInput("body-contact", caster(), (
        CastApplication("hit", target, False, None, None),
    )))
    arrival = timeline.applications[0].travel_end_ms
    impact, = (row for row in sample_cast(timeline, arrival).projectiles if row.phase == "impact")
    projected = project_projectile(timeline, impact, quadrant)
    rig = data.rigs[rig_id]
    socket = rig.body_anchor
    assert socket is not None and socket.y < rig.cell_height - rig.origin_y_from_ground
    origin = project_world(target.grid, elevation_steps=target.elevation_steps, quadrant=quadrant)
    reference_scale = data.rig.TILE_W / TILE_WIDTH
    expected = (
        origin[0] * reference_scale + (socket.x - rig.cell_width / 2) * target.visual_scale * target.visual_scale_x,
        origin[1] * reference_scale + (socket.y - rig.cell_height + rig.origin_y_from_ground) * target.visual_scale,
    )
    assert projected.point == pytest.approx(expected)


def boundary(direction, *, bottom=0, top=2):
    return WorldObjectPlacement(object_uuid=uuid4(), tile_uuid=uuid4(),
        position=(1, 0) if direction is CardinalDirection.EAST else (0, 1),
        kind=WorldPlacementKind.BOUNDARY, occupies_bands=True, boundary_direction=direction,
        base_height_steps=bottom, top_height_steps=top)


def local_pixel(position, elevation, camera):
    x, y = project_world(position, elevation_steps=elevation, quadrant=camera.quadrant)
    return round(x * camera.zoom + camera.pan[0]), round(y * camera.zoom + camera.pan[1])


@pytest.mark.parametrize("direction", (CardinalDirection.EAST, CardinalDirection.NORTH))
@pytest.mark.parametrize("quadrant", range(4))
def test_closed_wall_or_door_masks_finite_ground_shadow_for_both_blends(direction, quadrant):
    camera = Camera(quadrant=quadrant, zoom=.5, viewport=(512, 512)).with_focus((0, 0))
    wall = boundary(direction)
    media = AreaMedia((wall,))
    points = ((1.25, 0), (1.75, 0), (2, 2)) if direction is CardinalDirection.EAST else (
        (0, 1.25), (0, 1.75), (2, 2))
    before_wall, behind_wall, around_end = [local_pixel(point, 0, camera) for point in points]
    for blend in (0, pygame.BLEND_RGB_ADD):
        original = pygame.Surface((512, 512), pygame.SRCALPHA)
        original.fill((80, 60, 40, 128))
        before = pygame.image.tobytes(original, "RGBA")
        clipped = mask_ground_area(original, (0, 0), (0, 0), 0, camera, media)
        assert tuple(clipped.get_at(behind_wall)) == (0, 0, 0, 0)
        for point in (before_wall, around_end):
            assert clipped.get_at(point) == original.get_at(point)
        composited = pygame.Surface((512, 512))
        composited.fill((11, 17, 23))
        composited.blit(clipped, (0, 0), special_flags=blend)
        assert tuple(composited.get_at(behind_wall))[:3] == (11, 17, 23)
        assert tuple(composited.get_at(before_wall))[:3] != (11, 17, 23)
        assert pygame.image.tobytes(original, "RGBA") == before
        # An open door contributes no propagation boundary to this captured
        # media input; its historical open state leaves both sides untouched.
        opened = mask_ground_area(original, (0, 0), (0, 0), 0, camera, AreaMedia(()))
        assert pygame.image.tobytes(opened, "RGBA") == before


@pytest.mark.parametrize("elevation,blocked", ((0, False), (1, True), (2, True), (3, False)))
@pytest.mark.parametrize("direction", (CardinalDirection.EAST, CardinalDirection.NORTH))
@pytest.mark.parametrize("quadrant", range(4))
def test_ground_shadow_uses_recorded_vertical_extent(elevation, blocked, direction, quadrant):
    camera = Camera(quadrant=quadrant, zoom=.5, viewport=(512, 512)).with_focus((0, 0), elevation_steps=elevation)
    original = pygame.Surface((512, 512), pygame.SRCALPHA)
    original.fill((80, 60, 40, 128))
    clipped = mask_ground_area(original, (0, 0), (0, 0), elevation, camera,
                               AreaMedia((boundary(direction, bottom=1, top=3),)))
    point = local_pixel((2, 0) if direction is CardinalDirection.EAST else (0, 2), elevation, camera)
    assert (tuple(clipped.get_at(point)) == (0, 0, 0, 0)) is blocked


@pytest.mark.parametrize("quadrant", range(4))
def test_l_shaped_walls_stop_both_layers_without_erasing_the_open_side(quadrant):
    camera = Camera(quadrant=quadrant, zoom=.5, viewport=(512, 512)).with_focus((0, 0))
    east = boundary(CardinalDirection.EAST)
    north = boundary(CardinalDirection.NORTH).model_copy(update={"position": (1, 0)})
    media = AreaMedia((east, north))
    source = pygame.Surface((512, 512), pygame.SRCALPHA)
    source.fill((80, 60, 40, 128))
    clipped = mask_ground_area(source, (0, 0), (0, 0), 0, camera, media)
    for blend in (0, pygame.BLEND_RGB_ADD):
        result = pygame.Surface((512, 512))
        result.fill((11, 17, 23))
        result.blit(clipped, (0, 0), special_flags=blend)
        for point in ((2, 0), (1, 1)):
            assert tuple(result.get_at(local_pixel(point, 0, camera)))[:3] == (11, 17, 23)
        assert tuple(result.get_at(local_pixel((-2, 2), 0, camera)))[:3] != (11, 17, 23)
