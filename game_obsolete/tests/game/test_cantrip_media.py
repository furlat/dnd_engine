"""Direct/touch media preserve registration, actual outcomes and one contact clock."""

from dataclasses import replace

import pygame
import pytest

from game.animation import (
    ActorContact, CastApplication, CastInput, ProjectileSample, body_elevation_steps, body_rig, compile_cast,
    project_projectile, sample_cast, view_facing,
)
from game.animation_data import load_animation_data
from game.animation_draw import AnimationMedia, projectile_layer_blits
from game.cast_media import cast_media_draw_commands
from game.projection import Camera, TILE_WIDTH, project_screen


@pytest.fixture(scope="module")
def data():
    return load_animation_data()


@pytest.fixture(scope="module", autouse=True)
def display():
    with pytest.MonkeyPatch.context() as environment:
        environment.setenv("SDL_VIDEODRIVER", "dummy")
        environment.setenv("SDL_AUDIODRIVER", "dummy")
        pygame.init()
        pygame.display.set_mode((1, 1))
        yield
        pygame.quit()


def direct_cast(data, spell, *, hit=True):
    source = ActorContact("caster", (3, 3), "SE", 1)
    target = ActorContact("target", (4, 3), "NW", 1, hp=30)
    return compile_cast(data, "spell." + spell, CastInput("cast", source,
        (CastApplication("application", target, hit, 4 if hit else None,
                         26 if hit else None, hit=hit),)))


def test_sacred_column_precedes_release_but_damage_waits_for_contact(data):
    timeline = direct_cast(data, "sacred_flame")
    target_track = timeline.recipe.media[0]
    start = timeline.release_ms + target_track.startOffsetMs
    assert start < timeline.release_ms
    assert sample_cast(timeline, timeline.release_ms-.01).vitals[0].hp == 30
    assert sample_cast(timeline, timeline.release_ms).vitals[0].flash is not None
    hp_ms = timeline.applications[0].hp_ms
    assert hp_ms is not None and sample_cast(timeline, hp_ms).vitals[0].hp == 26
    camera = Camera(zoom=.5).with_focus((4, 3))
    assert not cast_media_draw_commands(timeline, sample_cast(timeline, start-.01), camera, None, {})
    draws = cast_media_draw_commands(timeline, sample_cast(timeline, timeline.release_ms+50), camera, None, {})
    assert len(draws) == 2 and any(command.surface.get_bounding_rect().width for command in draws)
    assert draws[0].key < draws[1].key
    assert not sample_cast(timeline, timeline.release_ms).projectiles


def test_touch_miss_keeps_hand_charge_without_target_arcs_or_damage(data):
    hit, miss = (direct_cast(data, "shocking_grasp", hit=value) for value in (True, False))
    assert hit.release_ms == miss.release_ms
    camera = Camera(zoom=.5).with_focus((3, 3))
    early = cast_media_draw_commands(miss, sample_cast(miss, 300), camera, None, {})
    assert early and all(command.evidence[8] in ("hand-back", "hand-front") for command in early)
    arrived = hit.release_ms + 100
    assert cast_media_draw_commands(hit, sample_cast(hit, arrived), camera, None, {})
    assert not cast_media_draw_commands(miss, sample_cast(miss, arrived), camera, None, {})
    assert sample_cast(miss, arrived).vitals[0].hp == 30
    assert sample_cast(miss, arrived).vitals[0].flash is None
    assert sample_cast(hit, arrived).vitals[0].flash is not None
    hp_ms = hit.applications[0].hp_ms
    assert hp_ms is not None and sample_cast(hit, hp_ms).vitals[0].hp == 26


def test_poison_contact_and_save_feedback_share_the_existing_clock(data):
    for hit in (True, False):
        timeline = direct_cast(data, "poison_spray", hit=hit)
        arrival = timeline.applications[0].travel_end_ms
        assert arrival == pytest.approx(timeline.release_ms + 400)
        assert not sample_cast(timeline, timeline.release_ms - .01).projectiles
        assert sample_cast(timeline, arrival - .01).vitals[0].hp == 30
        assert (sample_cast(timeline, arrival).vitals[0].flash is not None) is hit
        hp_ms = timeline.applications[0].hp_ms
        if hit:
            assert hp_ms is not None and sample_cast(timeline, hp_ms).vitals[0].hp == 26
        else:
            assert sample_cast(timeline, timeline.complete_ms).vitals[0].hp == 30
        camera = Camera(zoom=1).with_focus((3, 3))
        media = AnimationMedia({}, {}, {}, pygame.font.Font(None, 12))
        effect, = sample_cast(timeline, arrival + 100).projectiles
        assert isinstance(effect, ProjectileSample)
        effect = project_projectile(timeline, effect, camera.quadrant)
        first = projectile_layer_blits(timeline, effect, media, camera)
        sample_cast(timeline, timeline.complete_ms)
        repeated, = sample_cast(timeline, arrival + 100).projectiles
        assert isinstance(repeated, ProjectileSample)
        after = projectile_layer_blits(timeline, project_projectile(timeline, repeated, camera.quadrant), media, camera)
        assert [(xy, blend, pygame.image.tobytes(image, "RGBA")) for image, xy, blend in first] == [
            (xy, blend, pygame.image.tobytes(image, "RGBA")) for image, xy, blend in after]
        assert not sample_cast(timeline, timeline.complete_ms).projectiles


@pytest.mark.parametrize("delta", ((1, 0), (1, 1), (2, 0), (2, 2), (2, 1)))
@pytest.mark.parametrize("height", (-1, 0, 1))
@pytest.mark.parametrize("zoom", (.5, 1))
def test_poison_stays_on_the_hand_to_body_journey_and_dissipates_locally(data, delta, height, zoom):
    """All phases, including near-contact overlap, use compact real source pixels."""
    original = direct_cast(data, "poison_spray")
    application, = original.source.applications
    target = replace(application.target, grid=(3+delta[0], 3+delta[1]), elevation_steps=height)
    timeline = compile_cast(data, "spell.poison_spray", replace(original.source,
        applications=(replace(application, target=target),)))
    projectile = timeline.recipe.projectile
    assert projectile is not None and projectile.sourceSockets is not None
    caster, rig = timeline.source.caster, body_rig(data, target)
    assert rig.body_anchor is not None
    media = AnimationMedia({}, {}, {}, pygame.font.Font(None, 12))
    for quadrant in range(4):
        camera = Camera(quadrant=quadrant, zoom=zoom).with_focus((3, 3))
        factor = TILE_WIDTH/data.rig.TILE_W*zoom
        facing = view_facing(timeline.facing, quadrant, data)
        socket = projectile.sourceSockets.release[facing]
        caster_rig = body_rig(data, caster)
        ground = project_screen(caster.grid, camera, elevation_steps=body_elevation_steps(caster, data))
        palm = (ground[0]+(socket.x-caster_rig.cell_width/2)*factor,
                ground[1]+(socket.y-caster_rig.cell_height+caster_rig.origin_y_from_ground)*factor)
        ground = project_screen(target.grid, camera, elevation_steps=body_elevation_steps(target, data))
        body = (ground[0]+(rig.body_anchor.x-rig.cell_width/2)*factor,
                ground[1]+(rig.body_anchor.y-rig.cell_height+rig.origin_y_from_ground)*factor)
        for age in (0, 50, 100, 200, 399.9, 400, 450, 550, 725):
            sample = sample_cast(timeline, timeline.release_ms+age)
            effect, = sample.projectiles
            assert isinstance(effect, ProjectileSample)
            projected = project_projectile(timeline, effect, quadrant)
            point = (projected.point[0]*factor+camera.pan[0], projected.point[1]*factor+camera.pan[1])
            progress = min(age/400, 1)
            assert point == pytest.approx(tuple(a+(b-a)*progress for a,b in zip(palm,body)))
            for image, xy, _ in projectile_layer_blits(timeline, projected, media, camera):
                bounds = image.get_bounding_rect(min_alpha=48).move(xy)
                if bounds.width and bounds.height:
                    # Fixed-size smoke must remain a small puff around its
                    # moving contact, then around the body; no baked long tail.
                    assert max(abs(bounds.left-point[0]), abs(bounds.right-point[0]),
                               abs(bounds.top-point[1]), abs(bounds.bottom-point[1])) <= 45*zoom+1
            if age == 400:
                patch = pygame.Surface((25, 25), pygame.SRCALPHA)
                for image, xy, _ in projectile_layer_blits(timeline, projected, media, camera):
                    patch.blit(image, (round(xy[0]-body[0]+12), round(xy[1]-body[1]+12)))
                assert pygame.mask.from_surface(patch, threshold=48).count() > 0


@pytest.mark.parametrize("spell", ("burning_hands", "thunderwave", "gust_of_wind"))
def test_area_media_cannot_invent_an_unobserved_ground_origin(data, spell):
    source = direct_cast(data, "shocking_grasp").source
    with pytest.raises(ValueError, match="requires its observed ground destination"):
        compile_cast(data, "spell." + spell, source)
