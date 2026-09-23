"""Actual projectile drawing lands its registered image point on the same torso."""

from dataclasses import replace
from math import cos, sin

import pygame
import pytest

from game.animation import ActorContact, CastApplication, CastInput, ProjectileSample, compile_cast, project_projectile, sample_cast
from game.animation_data import DATA_ROOT, load_animation_data
from game.animation_draw import load_animation_media, projectile_layer_blits
from game.animation_types import RigLayer
from game.projection import Camera, TILE_WIDTH, project_screen


@pytest.fixture(scope="module")
def data():
    return load_animation_data(rig_files=(DATA_ROOT.parent / "rigs/goblin01.json",))


@pytest.fixture(scope="module", autouse=True)
def display():
    with pytest.MonkeyPatch.context() as environment:
        environment.setenv("SDL_VIDEODRIVER", "dummy")
        environment.setenv("SDL_AUDIODRIVER", "dummy")
        pygame.init()
        pygame.display.set_mode((1, 1))
        yield
        pygame.quit()


@pytest.mark.parametrize("spell", (
    "poison_spray", "ray_of_frost", "ice_knife",
    "acid_splash", "guiding_bolt", "eldritch_blast", "magic_missile",
))
@pytest.mark.parametrize("target_scale,elevation,lift", ((1.0, 0, 0), (.7, 2, 3)))
@pytest.mark.parametrize("target_rig,body_y", (("neuroclient.modular", 60), ("smallscale.goblin01", 72)))
def test_actual_arrival_image_pivot_uses_shared_rig_body_point(data, spell, target_scale, elevation, lift,
                                                           target_rig, body_y):
    source = ActorContact("caster", (3, 3), "SE", 1)
    target = ActorContact("recipient", (5, 4), "NW", target_scale,
                          elevation_steps=elevation, body_lift_px=lift, rig_id=target_rig)
    cast = compile_cast(data, "spell." + spell, CastInput("cast", source,
        (CastApplication("hit", target, False, None, None, hit=True),)))
    application, = cast.applications
    appearance = (RigLayer("body", "NakedBody"), RigLayer("head", "Head10"))
    recipient = appearance if target_rig == "neuroclient.modular" else (RigLayer("body", "Goblin01"),)
    media = load_animation_media(cast, {"caster": appearance, "recipient": recipient})
    # A real final flight sample, including the actual authored frame/rotation.
    effect, = [row for row in sample_cast(cast, application.travel_end_ms - 1e-6).projectiles
               if isinstance(row, ProjectileSample) and row.phase == "travel"]
    projectile = cast.recipe.projectile
    assert projectile is not None and projectile.sprite is not None
    asset = data.projectile_assets[effect.asset_id]
    for quadrant in range(4):
        camera = Camera(quadrant=quadrant, zoom=.5).with_focus(target.grid)
        ground = project_screen(target.grid, camera, elevation_steps=elevation)
        factor = TILE_WIDTH / data.rig.TILE_W * camera.zoom
        # Independent authored source points in each 128px rig cell: modular
        # torso (64,60), packaged goblin (64,72), both with 41px ground padding.
        expected = (ground[0], ground[1] + ((body_y - 128 + 41) * target_scale - lift) * factor)
        projected = project_projectile(cast, effect, quadrant)
        draws = projectile_layer_blits(cast, projected, media, camera)
        assert draws
        facing = asset.rowOrder[projected.row]
        pivot = (asset.anchorsByFacing or {}).get(facing, projectile.sprite.anchor or asset.anchor)
        scale = (projectile.travel.scale if projectile.travel.scale is not None else projectile.scale) * factor
        # Recover the source's registered pixel from the actual rotated draw rect.
        # Checking only projected.point would miss canvas compensation in drawing.
        dx = (pivot.x - .5) * asset.frame.width * scale
        dy = (pivot.y - .5) * asset.frame.height * scale
        rotated = (dx*cos(projected.rotation_radians) - dy*sin(projected.rotation_radians),
                   dx*sin(projected.rotation_radians) + dy*cos(projected.rotation_radians))
        for image, destination, _ in draws:
            drawn_pivot = (destination[0] + image.width/2 + rotated[0],
                           destination[1] + image.height/2 + rotated[1])
            assert drawn_pivot == pytest.approx(expected, abs=1), (spell, quadrant, target_scale)


@pytest.mark.parametrize("spell", ("fire_bolt", "poison_spray", "ray_of_frost", "magic_missile"))
@pytest.mark.parametrize("facing,points", (
    ("S", ((57, 57), (87, 74), (66, 99), (35, 79))),
    ("NE", ((48, 96), (40, 67), (75, 60), (85, 91))),
))
def test_resting_recipient_moves_only_the_authored_target_contact(data, spell, facing, points):
    # Fire Bolt keeps its approved canvas/inset placement. Sleep adds a
    # relative pose displacement; it does not redefine that standing baseline.
    source = ActorContact("caster", (3, 3), "SE", 1)
    standing = ActorContact("recipient", (5, 4), facing, .7, visual_scale_x=.8, elevation_steps=2)
    timelines = [compile_cast(data, "spell." + spell, CastInput("cast", source,
        (CastApplication("hit", target, False, None, None, hit=True),)))
        for target in (standing, replace(standing, rest_pose="Die"))]
    effects = [next(row for row in sample_cast(cast, cast.applications[0].travel_start_ms + .001).projectiles
                    if isinstance(row, ProjectileSample) and row.phase == "travel") for cast in timelines]
    for quadrant, (x, y) in enumerate(points):
        def at(index, progress):
            return project_projectile(timelines[index], replace(effects[index], progress=progress), quadrant).point
        assert at(0, 0) == pytest.approx(at(1, 0)), "Resting target must not move the authored launch"
        first, last = at(0, 1), at(1, 1)
        assert (last[0]-first[0], last[1]-first[1]) == pytest.approx(((x-64)*.7*.8, (y-60)*.7))


@pytest.mark.parametrize("basis,local_y", (("rigRoot", 41), ("body", -27), ("tileCenter", 0)))
def test_explicit_source_and_target_bases_use_the_same_body_geometry(data, basis, local_y):
    recipe = data.drafts["spell.poison_spray"]
    projectile = recipe.projectile
    assert projectile is not None
    source_anchor = projectile.sourceAnchor.model_copy(update={
        "basis": basis, "liftY": 0, "forwardPx": 0, "sidePx": 0, "axisPx": 0})
    target_anchor = projectile.targetAnchor.model_copy(update={
        "basis": basis, "liftY": 0, "forwardPx": 0, "axisPx": 0})
    recipe = recipe.model_copy(update={"projectile": projectile.model_copy(update={
        "sourceAnchor": source_anchor, "targetAnchor": target_anchor,
        "sourceSockets": None, "sourceAnchorsByFacing": None})})
    data = replace(data, drafts={**data.drafts, "spell.poison_spray": recipe})
    source = ActorContact("caster", (1, 2), "S", .4, elevation_steps=1)
    target = ActorContact("recipient", (5, 3), "N", .8, elevation_steps=2)
    timeline = compile_cast(data, "spell.poison_spray", CastInput("shot", source,
        (CastApplication("hit", target, False, None, None),)))
    delivery, = timeline.applications
    effect = next(row for row in sample_cast(timeline, delivery.travel_start_ms).projectiles
                  if isinstance(row, ProjectileSample) and row.phase == "travel")
    for quadrant in range(4):
        camera = Camera(quadrant=quadrant, zoom=.5)
        factor = TILE_WIDTH / data.rig.TILE_W * camera.zoom
        for progress, contact in ((0, source), (1, target)):
            point = project_projectile(timeline, replace(effect, progress=progress), quadrant).point
            ground = project_screen(contact.grid, camera, elevation_steps=contact.elevation_steps)
            assert (point[0]*factor+camera.pan[0], point[1]*factor+camera.pan[1]) == pytest.approx(
                (ground[0], ground[1]+local_y*contact.visual_scale*factor))


def test_scalar_and_directional_pivots_have_identical_registration(data):
    recipe = data.drafts["spell.fire_bolt"]
    projectile = recipe.projectile
    assert projectile is not None and projectile.sprite is not None
    recipe = recipe.model_copy(update={"projectile": projectile.model_copy(update={
        "sprite": projectile.sprite.model_copy(update={"anchor": None})})})
    asset = data.projectile_assets[projectile.sprite.assetId]
    pivot = asset.anchor.model_copy(update={"x": .3, "y": .7})
    asset = asset.model_copy(update={"anchor": pivot, "anchorsByFacing": None})
    source = CastInput("shot", ActorContact("caster", (2, 2), "S", .5),
        (CastApplication("hit", ActorContact("recipient", (6, 3), "N", .8), False, None, None),))
    timelines = [compile_cast(replace(data, drafts={**data.drafts, "spell.fire_bolt": recipe},
        projectile_assets={**data.projectile_assets, asset.assetId: selected}), "spell.fire_bolt", source)
        for selected in (asset, asset.model_copy(update={"anchorsByFacing": {f: pivot for f in asset.rowOrder}}))]
    layers = (RigLayer("body", "NakedBody"),)
    media = load_animation_media(timelines[0], {"caster": layers, "recipient": layers})
    for quadrant in range(4):
        camera = Camera(quadrant=quadrant, zoom=.5)
        actual = []
        for timeline in timelines:
            delivery, = timeline.applications
            effect = next(row for row in sample_cast(timeline,
                delivery.travel_start_ms+.4*(delivery.travel_end_ms-delivery.travel_start_ms)).projectiles
                if isinstance(row, ProjectileSample) and row.phase == "travel")
            drawn = project_projectile(timeline, effect, quadrant)
            actual.append(tuple((position, blend, surface.get_size(), pygame.image.tobytes(surface, "RGBA"))
                for surface, position, blend in projectile_layer_blits(timeline, drawn, media, camera)))
        assert actual[0] == actual[1]
