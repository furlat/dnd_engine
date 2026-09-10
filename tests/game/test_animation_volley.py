"""One authored body with distinct A/B/A effects remains seekable in every view."""

from dataclasses import replace
import json
from math import hypot
from types import MappingProxyType

import pytest

from game.animation import (
    ActorContact, CastApplication, CastInput, CastTimeline, GeometryProjectileSample,
    compile_cast, project_geometry_projectile, projectile_contact, sample_cast,
    view_facing,
)
from game.animation_data import load_animation_data
from game.animation_types import StudioSpellDraft
from game.projection import HEIGHT_STEP_PIXELS, TILE_WIDTH, project_world


@pytest.fixture(scope="module")
def timeline() -> CastTimeline:
    data = load_animation_data(authored_bundles=())
    a = ActorContact("A", (3, -3), "W", 1, hp=80)
    b = ActorContact("B", (3, 0), "W", 1, hp=80)
    return compile_cast(data, "spell.magic_missile", CastInput(
        "volley", ActorContact("caster", (0, 0), "S", 1), (
            CastApplication("A1", a, True, 5, 75, damage_type="Force"),
            CastApplication("B1", b, True, 5, 75, damage_type="Force"),
            CastApplication("A2", a, True, 2, 73, damage_type="Force"),
        ),
    ))


def test_repeated_recipient_reenters_one_body_and_keeps_both_numbers(timeline: CastTimeline) -> None:
    first, middle, last = timeline.applications
    before = sample_cast(timeline, last.travel_end_ms - 0.001)
    arrival = sample_cast(timeline, last.travel_end_ms)
    assert [(body.actor_uuid, body.clip) for body in arrival.bodies] == [
        ("caster", "Special1"), ("A", "TakeDamage"), ("B", "TakeDamage"),
    ]
    assert before.bodies[1].frame > 0 and arrival.bodies[1].frame == 0
    assert arrival.bodies[2].frame == before.bodies[2].frame
    assert [(value.actor_uuid, value.hp) for value in arrival.vitals] == [("A", 73), ("B", 75)]
    assert [(number.application_id, number.actor_uuid, number.value, number.label) for number in arrival.numbers] == [
        ("A1", "A", 5, "Force"), ("B1", "B", 5, "Force"), ("A2", "A", 2, "Force"),
    ]
    assert arrival.numbers[0].progress > arrival.numbers[1].progress > arrival.numbers[2].progress
    assert timeline.recipe.damage is None
    assert first.hp_ms == first.travel_end_ms and middle.hp_ms == middle.travel_end_ms
    assert first.damage_end_ms is not None
    assert sample_cast(timeline, first.damage_end_ms).bodies[1].clip == "TakeDamage"
    final = sample_cast(timeline, timeline.complete_ms)
    assert final.complete and final.projectiles == ()
    assert [body.clip for body in final.bodies] == ["Idle", "Idle", "Idle"]
    assert sample_cast(timeline, last.travel_end_ms) == arrival


def _effect(timeline: CastTimeline, index: int, progress: float) -> GeometryProjectileSample:
    application = timeline.applications[index]
    elapsed = application.travel_start_ms + progress * (application.travel_end_ms - application.travel_start_ms)
    effect = next(effect for effect in sample_cast(timeline, elapsed).projectiles
                  if effect.application_id == application.source.application_id)
    assert isinstance(effect, GeometryProjectileSample)
    return effect


@pytest.mark.parametrize("quadrant", range(4))
def test_same_recipient_darts_spread_to_opposite_sides_in_each_view(
    timeline: CastTimeline, quadrant: int,
) -> None:
    first = project_geometry_projectile(timeline, _effect(timeline, 0, 0.5), quadrant)
    last = project_geometry_projectile(timeline, _effect(timeline, 2, 0.5), quadrant)
    start = project_geometry_projectile(timeline, replace(first, progress=0), quadrant)
    end = project_geometry_projectile(timeline, replace(first, progress=1), quadrant)
    assert first.point != last.point
    assert tuple((a + b) / 2 for a, b in zip(first.point, last.point)) == pytest.approx(
        tuple((a + b) / 2 for a, b in zip(start.point, end.point)),
    )
    factor = timeline.data.rig.TILE_W / TILE_WIDTH
    for effect in (first, last):
        contact, height = projectile_contact(timeline, effect, quadrant=quadrant)
        assert project_world(contact, elevation_steps=height, quadrant=quadrant) == pytest.approx(
            tuple(value / factor for value in effect.point),
        )


@pytest.mark.parametrize("quadrant", range(4))
def test_explicit_height_lift_keeps_geometry_clock_and_curved_ground_depth(
    timeline: CastTimeline, quadrant: int,
) -> None:
    raised = compile_cast(timeline.data, "spell.magic_missile", replace(
        timeline.source,
        applications=tuple(replace(application, travel_apex_steps=1) for application in timeline.source.applications),
    ))
    assert raised.anchors == timeline.anchors and raised.complete_ms == timeline.complete_ms
    reference = project_geometry_projectile(timeline, _effect(timeline, 0, 0.5), quadrant)
    lifted = project_geometry_projectile(raised, _effect(raised, 0, 0.5), quadrant)
    factor = timeline.data.rig.TILE_W / TILE_WIDTH
    assert lifted.point == pytest.approx((reference.point[0], reference.point[1] - HEIGHT_STEP_PIXELS * factor))
    ground, height = projectile_contact(timeline, reference, quadrant=quadrant)
    raised_ground, raised_height = projectile_contact(raised, lifted, quadrant=quadrant)
    assert raised_ground == pytest.approx(ground)
    assert raised_height == height + 1


def test_dart_trail_uses_reference_frame_cadence_and_seeks_without_history(timeline: CastTimeline) -> None:
    effect = _effect(timeline, 0, 0.75)  # 150 ms = nine reference display frames.
    assert len(effect.trail) == timeline.data.dart_style.trailPointLimit == 8
    assert effect.trail[-1] == effect.point
    early = _effect(timeline, 0, 1 / 6)  # Its second reference frame is the oldest surviving point.
    assert effect.trail[0] == pytest.approx(early.point)
    sample_cast(timeline, timeline.complete_ms + 10000)
    assert _effect(timeline, 0, 0.75) == effect


@pytest.mark.parametrize("quadrant", range(4))
@pytest.mark.parametrize("heights,scales", [((0, 2), (0.5, 0.82)), ((2, 2), (1.0, 1.0))])
def test_geometry_endpoints_use_authored_tile_centers_above_each_support(
    timeline: CastTimeline, quadrant: int, heights: tuple[int, int], scales: tuple[float, float],
) -> None:
    source = timeline.source
    caster = replace(source.caster, elevation_steps=heights[0], visual_scale=scales[0])
    # Keep endpoint insets separated in every view; the existing near-target
    # tests already cover source inset compression.
    target = replace(source.applications[0].target, grid=(6, -6),
                     elevation_steps=heights[1], visual_scale=scales[1])
    selected = compile_cast(timeline.data, "spell.magic_missile", replace(
        source, caster=caster, applications=(replace(source.applications[0], target=target),),
    ))
    projectile = selected.recipe.projectile
    assert projectile is not None
    assert projectile.sourceAnchor.basis == projectile.targetAnchor.basis == "tileCenter"
    factor = selected.data.rig.TILE_W / TILE_WIDTH
    first = project_world(caster.grid, elevation_steps=heights[0], quadrant=quadrant)
    last = project_world(target.grid, elevation_steps=heights[1], quadrant=quadrant)
    # The original point recipe lifts 16px above ground, with 16px axis insets.
    # Sprite-root padding does not belong to either geometry endpoint.
    first = first[0] * factor, first[1] * factor - 16 * scales[0]
    last = last[0] * factor, last[1] * factor - 16 * scales[1]
    dx, dy = last[0] - first[0], last[1] - first[1]
    distance = hypot(dx, dy)
    expected = (
        (first[0] + dx / distance * 16 * scales[0], first[1] + dy / distance * 16 * scales[0]),
        (last[0] - dx / distance * 16 * scales[1], last[1] - dy / distance * 16 * scales[1]),
    )
    effect = _effect(selected, 0, 0.5)
    for progress, point in zip((0.0, 1.0), expected):
        assert project_geometry_projectile(selected, replace(effect, progress=progress), quadrant).point == pytest.approx(point)


@pytest.mark.parametrize("quadrant", range(4))
def test_vertical_authored_attachment_changes_height_without_moving_ground_depth(
    timeline: CastTimeline, quadrant: int,
) -> None:
    source = replace(timeline.source, caster=replace(timeline.source.caster, visual_scale=0.5), applications=(
        replace(timeline.source.applications[0],
                target=replace(timeline.source.applications[0].target, visual_scale=0.82, elevation_steps=2)),
    ))
    original = compile_cast(timeline.data, "spell.magic_missile", source)
    recipe = original.recipe.model_dump(mode="json", exclude_unset=True)
    projectile = recipe["projectile"]
    facing = view_facing(original.applications[0].facing, quadrant, original.data)
    # Raise both attachment points by 32 reference pixels despite different
    # actor scales. The source value is deliberately a per-facing override.
    projectile["sourceAnchorsByFacing"] = {facing: {
        **projectile["sourceAnchor"], "liftY": projectile["sourceAnchor"]["liftY"] - 32 / source.caster.visual_scale,
    }}
    projectile["targetAnchor"]["liftY"] -= 32 / source.applications[0].target.visual_scale
    draft = StudioSpellDraft.model_validate_json(json.dumps(recipe))
    data = replace(original.data, drafts=MappingProxyType({**original.data.drafts, "spell.magic_missile": draft}))
    raised = compile_cast(data, "spell.magic_missile", source)
    reference = project_geometry_projectile(original, _effect(original, 0, 0.375), quadrant)
    lifted = project_geometry_projectile(raised, _effect(raised, 0, 0.375), quadrant)
    assert lifted.point == pytest.approx((reference.point[0], reference.point[1] - 32))
    ground, height = projectile_contact(original, reference, quadrant=quadrant)
    raised_ground, raised_height = projectile_contact(raised, lifted, quadrant=quadrant)
    assert raised_ground == pytest.approx(ground)
    factor = original.data.rig.TILE_W / TILE_WIDTH
    assert raised_height == pytest.approx(height + 32 / (HEIGHT_STEP_PIXELS * factor))
    assert project_world(raised_ground, elevation_steps=raised_height, quadrant=quadrant) == pytest.approx(
        tuple(value / factor for value in lifted.point),
    )
