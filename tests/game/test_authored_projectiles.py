"""Imported sprites use the shared ordered delivery, curve and feedback owners."""

from dataclasses import replace
import json
from math import atan2, cos, pi, sin
from types import MappingProxyType

import pytest

from game.animation import (
    ActorContact, CastApplication, CastInput, CastTimeline, GroundContact, ProjectileSample,
    compile_cast, project_projectile, projectile_contact, sample_cast,
)
from game.animation_data import DATA_ROOT, load_animation_data
from game.animation_types import StudioSpellDraft
from game.device_art import DeviceEmission, device_bank
from game.projection import TILE_WIDTH, project_world


@pytest.fixture(scope="module")
def timeline() -> CastTimeline:
    a = ActorContact("A", (3, -3), "W", 1, hp=80)
    b = ActorContact("B", (3, 0), "W", 1, hp=80)
    return compile_cast(load_animation_data(), "spell.magic_missile", CastInput(
        "volley", ActorContact("caster", (0, 0), "S", 1), (
            CastApplication("A1", a, True, 5, 75, damage_type="Force"),
            CastApplication("B1", b, True, 5, 75, damage_type="Force"),
            CastApplication("A2", a, True, 2, 73, damage_type="Force"),
        ),
    ))


def effect_at(timeline: CastTimeline, index: int, progress: float) -> ProjectileSample:
    application = timeline.applications[index]
    elapsed = application.travel_start_ms + progress * (application.travel_end_ms - application.travel_start_ms)
    effect = next(effect for effect in sample_cast(timeline, elapsed).projectiles
                  if effect.application_id == application.source.application_id)
    assert isinstance(effect, ProjectileSample)
    return effect


def test_default_bundle_replaces_geometry_without_changing_body_delivery_or_vital_clock(timeline: CastTimeline) -> None:
    # Compare media choices with the same authored contacts. The original
    # imported recipe's old canvas/insets no longer describe the selected
    # palm-to-torso trajectory, so its absolute arrivals are not a baseline.
    reference = load_animation_data(authored_bundles=())
    document = reference.drafts["spell.magic_missile"].model_dump(mode="json", exclude_unset=True)
    assert timeline.recipe.projectile is not None
    document["projectile"]["sourceAnchor"] = timeline.recipe.projectile.sourceAnchor.model_dump(mode="json")
    document["projectile"]["targetAnchor"] = timeline.recipe.projectile.targetAnchor.model_dump(mode="json")
    reference = replace(reference, drafts=MappingProxyType({**reference.drafts,
        "spell.magic_missile": StudioSpellDraft.model_validate_json(json.dumps(document))}))
    baseline = compile_cast(reference, "spell.magic_missile", timeline.source)
    assert timeline.recipe.projectile is not None and baseline.recipe.projectile is not None
    assert timeline.recipe.projectile.sprite is not None
    assert baseline.recipe.projectile.sprite is None
    assert timeline.recipe.cast == baseline.recipe.cast
    assert (timeline.release_ms, timeline.body_end_ms, timeline.complete_ms) == (
        baseline.release_ms, baseline.body_end_ms, baseline.complete_ms,
    )
    for actual, original in zip(timeline.applications, baseline.applications, strict=True):
        assert (actual.travel_start_ms, actual.travel_end_ms, actual.hp_ms, actual.curvature) == (
            original.travel_start_ms, original.travel_end_ms, original.hp_ms, original.curvature,
        )
        assert [interval.name for interval in actual.projectile_intervals] == ["travel", "impact"]
        assert [(interval.phase.start, interval.phase.frames, interval.fps) for interval in actual.projectile_intervals] == [
            (16, 10, 24), (26, 18, 24),
        ]
    for at in (0, *(row.travel_end_ms for row in timeline.applications), timeline.complete_ms):
        actual, original = sample_cast(timeline, at), sample_cast(baseline, at)
        assert (actual.bodies, actual.numbers, actual.complete) == (
            original.bodies, original.numbers, original.complete,
        )
        assert [(v.actor_uuid, v.hp, v.life_state) for v in actual.vitals] == [
            (v.actor_uuid, v.hp, v.life_state) for v in original.vitals]
    # The selected media retains delivery/state timing while using the approved
    # Force palette at contact instead of the reference's single-color flash.
    damage = timeline.recipe.damage
    assert damage is not None and damage.hitFlash.palette is not None
    for application in timeline.applications:
        assert application.flash_ms == application.travel_end_ms
        for delta, flashing in ((0, True), (149.9, True), (150, False)):
            sample = sample_cast(timeline, application.travel_end_ms + delta)
            vital = next(v for v in sample.vitals if v.actor_uuid == application.source.target.actor_uuid)
            assert vital.flash == (damage.hitFlash.palette if flashing else None)


@pytest.mark.parametrize("quadrant", range(4))
def test_authored_sprite_spread_and_depth_follow_the_shared_bezier(timeline: CastTimeline, quadrant: int) -> None:
    first = project_projectile(timeline, effect_at(timeline, 0, 0.5), quadrant)
    last = project_projectile(timeline, effect_at(timeline, 2, 0.5), quadrant)
    start = project_projectile(timeline, replace(first, progress=0), quadrant)
    end = project_projectile(timeline, replace(first, progress=1), quadrant)
    assert first.point != last.point
    assert tuple((a + b) / 2 for a, b in zip(first.point, last.point)) == pytest.approx(
        tuple((a + b) / 2 for a, b in zip(start.point, end.point)),
    )
    first_ground, first_height = projectile_contact(timeline, first, quadrant=quadrant)
    last_ground, last_height = projectile_contact(timeline, last, quadrant=quadrant)
    assert first_height == last_height
    projected_first = project_world(first_ground, elevation_steps=first_height, quadrant=quadrant)
    projected_last = project_world(last_ground, elevation_steps=last_height, quadrant=quadrant)
    factor = TILE_WIDTH / timeline.data.rig.TILE_W
    assert tuple(a - b for a, b in zip(projected_first, projected_last)) == pytest.approx(
        tuple((a - b) * factor for a, b in zip(first.point, last.point)),
    )


def test_target_vector_sprite_rotation_retains_the_original_initial_curve_tangent(timeline: CastTimeline) -> None:
    document = timeline.recipe.model_dump(mode="json", exclude_unset=True)
    # This is the retained legacy mode's contract, not the selected spell's mode.
    document["projectile"]["orientation"]["directionSource"] = "target_vector"
    curved_draft = StudioSpellDraft.model_validate_json(json.dumps(document))
    curved_data = replace(timeline.data, drafts={**timeline.data.drafts, "spell.magic_missile": curved_draft})
    timeline = compile_cast(curved_data, "spell.magic_missile", timeline.source)
    document["projectile"]["trajectory"] = {"type": "straight", "sameTargetSpread": True}
    draft = StudioSpellDraft.model_validate_json(json.dumps(document))
    data = replace(timeline.data, drafts=MappingProxyType({**timeline.data.drafts, "spell.magic_missile": draft}))
    straight = compile_cast(data, "spell.magic_missile", timeline.source)
    application = timeline.applications[0]
    first, last = application.from_point, application.to_point
    dx, dy = last[0] - first[0], last[1] - first[1]
    curvature = application.curvature
    expected = atan2(dy + 2 * dx * curvature, dx - 2 * dy * curvature) - atan2(dy, dx)
    curved_effect, straight_effect = effect_at(timeline, 0, 0.5), effect_at(straight, 0, 0.5)
    actual = curved_effect.rotation_radians - straight_effect.rotation_radians
    assert (actual + pi) % (2 * pi) - pi == pytest.approx((expected + pi) % (2 * pi) - pi)


@pytest.mark.parametrize("quadrant", range(4))
@pytest.mark.parametrize("index", range(3), ids=("A-first", "B", "A-second"))
def test_magic_missile_faces_its_curve_without_moving_contacts_or_changing_timing(
    timeline: CastTimeline, quadrant: int, index: int,
) -> None:
    projectile = timeline.recipe.projectile
    assert projectile is not None
    legacy_recipe = timeline.recipe.model_copy(update={"projectile": projectile.model_copy(update={
        "orientation": projectile.orientation.model_copy(update={"directionSource": "target_vector"}),
    })})
    legacy = compile_cast(replace(timeline.data, drafts={**timeline.data.drafts,
        "spell.magic_missile": legacy_recipe}), "spell.magic_missile", timeline.source)
    assert timeline.anchors == legacy.anchors
    assert timeline.applications == legacy.applications
    assert (timeline.release_ms, timeline.body_end_ms, timeline.complete_ms) == (
        legacy.release_ms, legacy.body_end_ms, legacy.complete_ms,
    )
    for progress in (.01, .25, .5, .75, .99):
        effect = effect_at(timeline, index, progress)
        actual = project_projectile(timeline, effect, quadrant)
        travel = replace(effect, phase="travel", progress=progress)
        before = project_projectile(timeline, replace(travel, progress=progress - .0001), quadrant)
        after = project_projectile(timeline, replace(travel, progress=progress + .0001), quadrant)
        direction = atan2(after.point[1] - before.point[1], after.point[0] - before.point[0])
        facing = timeline.data.projectile_assets[actual.asset_id].rowOrder[actual.row]
        row_index = timeline.data.rig.AUTHORED_PROJECTILE_ROW_ORDER.index(facing)
        angle = row_index * pi / 4 - pi / 4
        x, y = cos(angle), sin(angle)
        row_angle = atan2((x + y) * timeline.data.rig.TILE_H, (x - y) * timeline.data.rig.TILE_W)
        error = (row_angle + actual.rotation_radians - direction + pi) % (2 * pi) - pi
        assert abs(error) < 1e-6
        original = project_projectile(legacy, effect_at(legacy, index, progress), quadrant)
        assert actual.point == original.point
    # Its directional body impact continues the arriving dart's orientation.
    impact = effect_at(timeline, index, 1)
    landed = project_projectile(timeline, impact, quadrant)
    arriving = project_projectile(timeline, replace(impact, phase="travel", progress=1), quadrant)
    assert (landed.point, landed.row, landed.rotation_radians) == (
        arriving.point, arriving.row, arriving.rotation_radians,
    )


def test_movement_preserves_source_timing_with_the_selected_local_media() -> None:
    source = json.loads((DATA_ROOT / "source/src/render/data/animation/actionContextPresentation.json").read_text())
    media = json.loads((DATA_ROOT.parent / "movement-media.json").read_text())
    data = load_animation_data()
    expected = {**source["contexts"]["voluntary_movement"],
                "walkMedia": media["walkMedia"], "jumpMedia": media["jumpMedia"]}
    assert data.movement_context.model_dump(mode="json", exclude_unset=True) == expected


@pytest.mark.parametrize("device", (False, True))
@pytest.mark.parametrize("travel_override", (False, True))
def test_directional_travel_and_floor_aligned_impact_have_independent_authored_rotation(
    timeline: CastTimeline, device: bool, travel_override: bool,
) -> None:
    document = timeline.recipe.model_dump(mode="json", exclude_unset=True)
    projectile = document["projectile"]
    projectile["trajectory"] = {"type": "straight", "sameTargetSpread": False}
    projectile["orientation"]["fineRotation"] = "none" if travel_override else "isometricHybrid"
    if travel_override:
        projectile["travel"]["fineRotation"] = "isometricHybrid"
    projectile["impact"]["fineRotation"] = "none"
    draft = StudioSpellDraft.model_validate_json(json.dumps(document))
    data = replace(timeline.data, drafts={**timeline.data.drafts, "spell.magic_missile": draft})
    art = data.devices["environment.fireball_cannon"]
    emitter = DeviceEmission("fixture", (1, 1), 0, "E", art, device_bank(art)) if device else None
    bound = compile_cast(data, "spell.magic_missile", CastInput(
        "ground-shot", ActorContact("caster", (0, 1), "S", 1), (),
        ground_target=GroundContact((7, 3)), emitter=emitter,
    ))
    delivery = bound.ground_delivery
    assert delivery is not None
    travel, = (effect for effect in sample_cast(bound,
        delivery.travel_start_ms + (delivery.travel_end_ms - delivery.travel_start_ms) * .35).projectiles
        if isinstance(effect, ProjectileSample) and effect.phase == "travel")
    impact, = (effect for effect in sample_cast(bound, delivery.travel_end_ms + 1).projectiles
               if isinstance(effect, ProjectileSample) and effect.phase == "impact")
    angles = []
    for quadrant in range(4):
        flying = project_projectile(bound, travel, quadrant)
        landed = project_projectile(bound, impact, quadrant)
        angles.append(flying.rotation_radians)
        assert landed.rotation_radians == 0
        assert projectile_contact(bound, landed, quadrant=quadrant) == ((7, 3), 0)
        # Phase orientation cannot change the recorded arrival or its position.
        arrived = project_projectile(bound, replace(travel, progress=1), quadrant)
        assert arrived.point == pytest.approx(landed.point)
    assert all(abs(angle) > .01 for angle in angles), "Noncanonical travel must retain its authored fine rotation"
