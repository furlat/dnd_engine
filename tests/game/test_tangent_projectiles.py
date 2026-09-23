"""Directional art follows actual travel without moving its semantic contact."""

from dataclasses import replace
import json
from math import atan2, cos, hypot, pi, sin
from pathlib import Path
from typing import Literal

import pygame
import numpy as np
import pytest

from game.animation import (
    ActorContact, CastApplication, CastInput, CastTimeline, GroundContact, ProjectileSample,
    compile_cast, project_projectile, sample_cast,
)
from game.animation_data import load_animation_data
from game.animation_draw import load_animation_media, projectile_layer_blits
from game.animation_types import AnimationData, AuthoredProjectileAsset, RigLayer, StudioSpellDraft
from game.device_art import DeviceEmission, device_bank, device_muzzle_offset
from game.projection import Camera, TILE_WIDTH, project_world


@pytest.fixture(scope="module")
def data() -> AnimationData:
    return load_animation_data(authored_bundles=())


def cast(data: AnimationData, path: Literal["device", "straight", "vertical", "bezier"], *,
         direction: str = "tangent", rotation: str = "isometricHybrid") -> CastTimeline:
    document = data.drafts["spell.fire_bolt"].model_dump(mode="json", exclude_unset=True)
    projectile = document["projectile"]
    projectile["orientation"]["directionSource"] = direction
    projectile["orientation"]["fineRotation"] = rotation
    projectile["trajectory"] = ({"type": "bezier", "curvature": .65, "sameTargetSpread": False}
                                if path == "bezier" else {"type": "straight", "sameTargetSpread": False})
    projectile["impact"]["fineRotation"] = "none"
    draft = StudioSpellDraft.model_validate_json(json.dumps(document))
    data = replace(data, drafts={**data.drafts, "spell.fire_bolt": draft})
    art = data.devices["environment.fireball_cannon"]
    emitter = DeviceEmission("fixture", (1, 1), 1, "E", art, device_bank(art)) if path == "device" else None
    caster = ActorContact("caster", (0, 1), "S", .7, elevation_steps=1)
    source = (CastInput("shot", caster, (), GroundContact((7, 3)), emitter) if path != "vertical" else
              CastInput("shot", caster, (CastApplication("hit", ActorContact("target", (7, 3), "W", .7),
                        False, None, None, travel_apex_steps=5),)))
    return compile_cast(data, "spell.fire_bolt", source)


def travel(timeline: CastTimeline, progress: float) -> ProjectileSample:
    delivery = timeline.ground_delivery or timeline.applications[0]
    # Select a real authored travel phase, then seek its retained progress.
    at = delivery.travel_start_ms + .5 * (delivery.travel_end_ms - delivery.travel_start_ms)
    effect, = (effect for effect in sample_cast(timeline, at).projectiles
               if isinstance(effect, ProjectileSample) and effect.phase == "travel")
    return replace(effect, progress=progress)


def angular_error(first: float, second: float) -> float:
    return abs((first - second + pi) % (2 * pi) - pi)


def row_angle(timeline: CastTimeline, effect: ProjectileSample) -> float:
    asset = timeline.data.projectile_assets[effect.asset_id]
    index = timeline.data.rig.AUTHORED_PROJECTILE_ROW_ORDER.index(asset.rowOrder[effect.row])
    angle = index * pi / 4 - pi / 4
    x, y = cos(angle), sin(angle)
    return atan2((x + y) * timeline.data.rig.TILE_H, (x - y) * timeline.data.rig.TILE_W)


@pytest.fixture(scope="module")
def fireball_data() -> AnimationData:
    return load_animation_data()


@pytest.mark.parametrize("device", (False, True), ids=("mage", "cannon"))
@pytest.mark.parametrize("quadrant", range(4))
def test_authored_fireball_faces_its_flight_without_turning_the_ground_explosion(
    fireball_data: AnimationData, device: bool, quadrant: int,
) -> None:
    data = fireball_data
    art = data.devices["environment.fireball_cannon"]
    emitter = DeviceEmission("cannon", (1, 1), 0, "E", art, device_bank(art)) if device else None
    source = CastInput("fireball", ActorContact("caster", (0, 1), "S", .7), (),
                       ground_target=GroundContact((7, 3)), emitter=emitter)
    timeline = compile_cast(data, "spell.fireball", source)
    projectile = timeline.recipe.projectile
    assert projectile is not None
    # Compare the shipped art with rotation disabled: only orientation may change.
    recipe = timeline.recipe.model_copy(update={"projectile": projectile.model_copy(update={
        "travel": projectile.travel.model_copy(update={"fineRotation": "none"}),
    })})
    unrotated = compile_cast(replace(data, drafts={**data.drafts, "spell.fireball": recipe}),
                             "spell.fireball", source)
    assert timeline.anchors == unrotated.anchors and timeline.complete_ms == unrotated.complete_ms
    for progress in (.01, .25, .5, .75, .99):
        effect = travel(timeline, progress)
        actual = project_projectile(timeline, effect, quadrant)
        before = project_projectile(timeline, replace(effect, progress=progress - .0001), quadrant)
        after = project_projectile(timeline, replace(effect, progress=progress + .0001), quadrant)
        direction = atan2(after.point[1] - before.point[1], after.point[0] - before.point[0])
        assert angular_error(row_angle(timeline, actual) + actual.rotation_radians, direction) < 1e-6
        original = project_projectile(unrotated, effect, quadrant)
        assert actual.point == original.point and actual.row == original.row
    delivery = timeline.ground_delivery
    assert delivery is not None
    impact, = (effect for effect in sample_cast(timeline, delivery.travel_end_ms + 1).projectiles
               if isinstance(effect, ProjectileSample) and effect.phase == "impact")
    assert project_projectile(timeline, impact, quadrant) == project_projectile(unrotated, impact, quadrant)
    assert project_projectile(timeline, impact, quadrant).rotation_radians == 0


@pytest.mark.parametrize("path", ("device", "vertical", "bezier"))
@pytest.mark.parametrize("quadrant", range(4))
def test_directional_rows_and_residual_rotation_follow_actual_curve(
    data: AnimationData, path: Literal["device", "vertical", "bezier"], quadrant: int,
) -> None:
    timeline = cast(data, path)
    rows = set()
    for progress in (.001, .1, .35, .65, .9, .999):
        effect = travel(timeline, progress)
        actual = project_projectile(timeline, effect, quadrant)
        before = project_projectile(timeline, replace(effect, progress=progress - .0001), quadrant)
        after = project_projectile(timeline, replace(effect, progress=progress + .0001), quadrant)
        angle = atan2(after.point[1] - before.point[1], after.point[0] - before.point[0])
        direction = timeline.data.projectile_assets[actual.asset_id].rowOrder[actual.row]
        row_index = timeline.data.rig.AUTHORED_PROJECTILE_ROW_ORDER.index(direction)
        assert angular_error(row_index * pi / 4, angle) <= pi / 8 + 1e-6
        assert angular_error(row_angle(timeline, actual) + actual.rotation_radians, angle) < 1e-6
        rows.add(actual.row)
    assert len(rows) > 1, "The curve must exercise row changes, including its descending part"


@pytest.mark.parametrize("quadrant", range(4))
def test_mage_stays_straight_and_orientation_does_not_change_contacts_or_clock(data: AnimationData, quadrant: int) -> None:
    tangent, original = cast(data, "straight"), cast(data, "straight", direction="target_vector")
    assert tangent.anchors == original.anchors
    first = project_projectile(tangent, travel(tangent, 0), quadrant)
    last = project_projectile(tangent, travel(tangent, 1), quadrant)
    for progress in (.1, .5, .9):
        effect = project_projectile(tangent, travel(tangent, progress), quadrant)
        retained = project_projectile(original, travel(original, progress), quadrant)
        assert effect.point == pytest.approx(retained.point)
        assert effect.point == pytest.approx(tuple(a + (b - a) * progress for a, b in zip(first.point, last.point)))
        assert effect.row == first.row and effect.rotation_radians == pytest.approx(first.rotation_radians)


@pytest.mark.parametrize("quadrant", range(4))
def test_none_disables_extra_rotation_but_keeps_tangent_rows_and_arrival_direction(data: AnimationData, quadrant: int) -> None:
    rotated, unrotated = cast(data, "device"), cast(data, "device", rotation="none")
    for progress in (0, .2, .8, 1):
        actual = project_projectile(unrotated, travel(unrotated, progress), quadrant)
        reference = project_projectile(rotated, travel(rotated, progress), quadrant)
        assert actual.row == reference.row and actual.point == reference.point
        assert actual.rotation_radians == 0
    arrival = project_projectile(rotated, travel(rotated, 1), quadrant)
    delivery = rotated.ground_delivery
    assert delivery is not None
    impact, = (effect for effect in sample_cast(rotated, delivery.travel_end_ms + 1).projectiles
               if isinstance(effect, ProjectileSample) and effect.phase == "impact")
    impact = project_projectile(rotated, impact, quadrant)
    assert impact.row == arrival.row and impact.point == arrival.point
    assert impact.rotation_radians == 0, "The authored impact override remains independent of travel"


@pytest.mark.parametrize("destination", ((3, 2), (14, 8)))
def test_single_source_sequence_fits_each_flight_without_changing_arrival(
    data: AnimationData, destination: tuple[int, int],
) -> None:
    baseline = cast(data, "straight")
    assert baseline.recipe.projectile is not None and baseline.recipe.projectile.sprite is not None
    original = data.projectile_assets[baseline.recipe.projectile.sprite.assetId]
    assert original.phases.travel is not None
    phase = original.phases.travel.model_copy(update={"frames": 144, "loop": False})
    asset = original.model_copy(update={
        "phases": original.phases.model_copy(update={"travel": phase}),
        "frame": original.frame.model_copy(update={"cols": max(original.frame.cols, phase.start + phase.frames)}),
    })
    data = replace(baseline.data, projectile_assets={**data.projectile_assets, asset.assetId: asset})
    source = replace(baseline.source, ground_target=GroundContact(destination))
    before = compile_cast(data, "spell.fire_bolt", source)
    document = baseline.recipe.model_dump(mode="json", exclude_unset=True)
    document["projectile"]["travel"]["fitDuration"] = True
    recipe = StudioSpellDraft.model_validate_json(json.dumps(document))
    data = replace(data, drafts={**data.drafts, "spell.fire_bolt": recipe})
    fitted = compile_cast(data, "spell.fire_bolt", source)
    assert before.anchors == fitted.anchors and before.complete_ms == fitted.complete_ms
    delivery = fitted.ground_delivery
    assert delivery is not None and before.ground_delivery is not None
    assert [(p.start_ms, p.end_ms) for p in delivery.projectile_intervals] == [
        (p.start_ms, p.end_ms) for p in before.ground_delivery.projectile_intervals]
    for progress, frame in ((0, 0), (.5, 72), (1 - 1e-8, 143)):
        elapsed = delivery.travel_start_ms + progress * (delivery.travel_end_ms - delivery.travel_start_ms)
        effect, = (effect for effect in sample_cast(fitted, elapsed).projectiles
                   if isinstance(effect, ProjectileSample) and effect.phase == "travel")
        assert effect.column == phase.start + frame
        retained, = (effect for effect in sample_cast(before, elapsed).projectiles
                     if isinstance(effect, ProjectileSample) and effect.phase == "travel")
        assert effect.point == retained.point and effect.progress == retained.progress


@pytest.mark.parametrize("measured", (False, True))
def test_legacy_and_measured_media_keep_the_contact_through_row_changes(
    data: AnimationData, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, measured: bool,
) -> None:
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    pygame.init()
    pygame.display.set_mode((8, 8))
    try:
        timeline = cast(data, "device")
        document = timeline.recipe.model_dump(mode="json", exclude_unset=True)
        projectile = document["projectile"]
        projectile["scale"] = 1
        projectile["sprite"].update(blendMode="normal", offsetX=0, offsetY=0)
        projectile["prepare"]["enabled"] = False
        document["cast"].update(weaponGlow=None, aura=None, effects=[], slash=None)
        recipe = StudioSpellDraft.model_validate_json(json.dumps(document))
        assert recipe.projectile is not None and recipe.projectile.sprite is not None
        original = timeline.data.projectile_assets[recipe.projectile.sprite.assetId]
        art = original.model_dump(mode="json")
        art["frame"] = {"width": 32, "height": 32, "cols": 1, "rows": 8}
        art["phases"] = {"travel": {"start": 0, "frames": 1, "fps": 24, "loop": True},
                         "impact": {"start": 0, "frames": 1, "fps": 24, "loop": False}}
        art["anchor"] = {"x": .5, "y": .5}
        art["anchorsByFacing"] = ({facing: {"x": (6 + i * 2) / 32, "y": (22 - i) / 32}
                                   for i, facing in enumerate(original.rowOrder)} if measured else None)
        asset = AuthoredProjectileAsset.model_validate_json(json.dumps(art))
        sheet = pygame.Surface((32, 32 * 8), pygame.SRCALPHA)
        for row, facing in enumerate(asset.rowOrder):
            anchor = asset.anchorsByFacing[facing] if asset.anchorsByFacing is not None else asset.anchor
            pygame.draw.circle(sheet, "white", (round(anchor.x * 32), row * 32 + round(anchor.y * 32)), 2)
        path = tmp_path / "directional-contact.png"
        pygame.image.save(sheet, path)
        data = replace(timeline.data,
                       drafts={**timeline.data.drafts, "spell.fire_bolt": recipe},
                       projectile_assets={**timeline.data.projectile_assets, asset.assetId: asset},
                       resources={**timeline.data.resources, asset.sheet: path})
        timeline = compile_cast(data, "spell.fire_bolt", timeline.source)
        media = load_animation_media(timeline, {"caster": (RigLayer("body", "NakedBody"),)})
        emitter = timeline.source.emitter
        assert emitter is not None
        for quadrant in range(4):
            camera = Camera(quadrant=quadrant, zoom=data.rig.TILE_W / TILE_WIDTH)
            start = project_projectile(timeline, travel(timeline, 0), quadrant)
            support = project_world(emitter.grid, elevation_steps=emitter.elevation_steps, quadrant=quadrant)
            muzzle = device_muzzle_offset(emitter, quadrant)
            assert start.point == pytest.approx(tuple((a + b) * data.rig.TILE_W / TILE_WIDTH
                                                      for a, b in zip(support, muzzle)))
            end = project_projectile(timeline, travel(timeline, 1), quadrant)
            assert end.point == pytest.approx(tuple(value * data.rig.TILE_W / TILE_WIDTH
                for value in project_world((7, 3), quadrant=quadrant)))
            for progress in (0, .1, .35, .65, .9, 1):
                effect = project_projectile(timeline, travel(timeline, progress), quadrant)
                layer, = projectile_layer_blits(timeline, effect, media, camera)
                image, destination, _ = layer
                center = tuple(float(axis.mean()) for axis in np.nonzero(pygame.surfarray.array_alpha(image)))
                contact = tuple(a + b for a, b in zip(destination, center))
                assert hypot(contact[0] - effect.point[0], contact[1] - effect.point[1]) < 2, (quadrant, progress)
    finally:
        pygame.quit()
