"""Frozen world contacts determine time; camera projection only changes view.

These are the bounded G5 reference-stage contracts. They do not establish
terrain, wall, door or raised-map painter occlusion.
"""

from dataclasses import replace
import json
from math import atan2, cos, sin
from types import MappingProxyType
from typing import Literal

import pytest

from game.animation import (
    ActorContact, CastApplication, CastInput, CastTimeline, ProjectileSample, compile_cast,
    crossed_anchors, project_projectile, projectile_contact, sample_cast, view_facing,
)
from game.animation_data import load_animation_data
from game.animation_types import AnimationData, Facing8, StudioSpellDraft
from game.projection import HEIGHT_STEP_PIXELS, TILE_WIDTH, project_world


@pytest.fixture(scope="module")
def data() -> AnimationData:
    return load_animation_data()


def reference_cast(
    data: AnimationData,
    *,
    caster_grid: tuple[float, float] = (0, 0),
    target_grid: tuple[float, float] = (3, -3),
    caster_height: int = 0,
    target_height: int = 0,
    target_scale: float = 0.5,
) -> CastTimeline:
    source = CastInput(
        root_event_uuid='space-reference',
        caster=ActorContact('caster', caster_grid, 'S', 0.5, elevation_steps=caster_height),
        applications=(
            CastApplication(
                application_id='application-1',
                target=ActorContact('target', target_grid, 'W', target_scale, hp=20, elevation_steps=target_height),
                damage_applied=True,
                damage_total=7,
                resulting_hp=13,
            ),
        ),
    )
    return compile_cast(data, "spell.fire_bolt", source)


def phase_sample(
    timeline: CastTimeline,
    name: Literal["prepare", "travel", "impact"],
    progress: float = 0.0,
) -> ProjectileSample:
    interval = next((phase for phase in timeline.applications[0].projectile_intervals if phase.name == name))
    elapsed = interval.start_ms + (interval.end_ms - interval.start_ms) * progress
    effect = next(effect for effect in sample_cast(timeline, elapsed).projectiles if effect.phase == name)
    assert isinstance(effect, ProjectileSample)
    return effect


@pytest.mark.parametrize("scale", [0.5, 0.82])
@pytest.mark.parametrize("quadrant", range(4))
def test_authored_attachment_follows_actor_scale_without_resizing_the_projectile(
    data: AnimationData, scale: float, quadrant: int,
) -> None:
    """Studio's unit-scale canvas attachment must stay attached to smaller bodies."""
    source = reference_cast(data, caster_height=2, target_height=2).source
    unit = compile_cast(
        data,
        'spell.fire_bolt',
        replace(
            source,
            caster=replace(source.caster, visual_scale=1),
            applications=(replace(source.applications[0], target=replace(source.applications[0].target, visual_scale=1)),),
        ),
    )
    scaled = compile_cast(
        data,
        'spell.fire_bolt',
        replace(
            source,
            caster=replace(source.caster, visual_scale=scale),
            applications=(replace(source.applications[0], target=replace(source.applications[0].target, visual_scale=scale)),),
        ),
    )
    # The original 128px asset is centered in its canvas and bottom-anchored.
    # Its canvas center stays 64px above the draw endpoint at effect scale 1.
    factor = data.rig.TILE_W / TILE_WIDTH
    endpoints: tuple[tuple[Literal["prepare", "impact"], ActorContact], ...] = (
        ("prepare", source.caster), ("impact", source.applications[0].target),
    )
    for phase, contact in endpoints:
        unit_view = project_projectile(unit, phase_sample(unit, phase), quadrant)
        scaled_view = project_projectile(scaled, phase_sample(scaled, phase), quadrant)
        x, y = project_world(contact.grid, elevation_steps=2, quadrant=quadrant)
        ground = x * factor, y * factor
        assert (scaled_view.point[0] - ground[0], scaled_view.point[1] - 64 - ground[1]) == pytest.approx((
            (unit_view.point[0] - ground[0]) * scale,
            (unit_view.point[1] - 64 - ground[1]) * scale,
        ))
    assert scaled.recipe == unit.recipe


@pytest.mark.parametrize("target,caster_height,target_height,duration", [
    pytest.param((3, -3), 0, 0, 844.444444, id="original-flat-reference"),
    pytest.param((3, -3), 0, 1, 862.955015, id="target-five-feet-higher"),
    pytest.param((1, 1), 0, 1, 183.249139, id="support-projection-collapses"),
    pytest.param((3, -3), 1, 0, 862.955015, id="target-five-feet-lower"),
    pytest.param((3, -3), 3, 3, 844.444444, id="equal-raised-supports"),
])
def test_travel_duration_uses_independent_height_not_view_distance(
    data: AnimationData, target: tuple[float, float], caster_height: int,
    target_height: int, duration: float,
) -> None:
    timeline = reference_cast(data, target_grid=target, caster_height=caster_height,
                              target_height=target_height)
    travel = next((phase for phase in timeline.applications[0].projectile_intervals if phase.name == 'travel'))
    # These worked values are reviewed in RECOVERY_PLAN §8.3, independently of
    # the evaluator: source flat metric plus 32 reference pixels per 5ft step.
    assert travel.end_ms - travel.start_ms == pytest.approx(duration, abs=0.000001, rel=0)


@pytest.mark.parametrize("facing,expected", [
    ("E", ("E", "S", "W", "N")),
    ("SE", ("SE", "SW", "NW", "NE")),
    ("S", ("S", "W", "N", "E")),
    ("SW", ("SW", "NW", "NE", "SE")),
    ("W", ("W", "N", "E", "S")),
    ("NW", ("NW", "NE", "SE", "SW")),
    ("N", ("N", "E", "S", "W")),
    ("NE", ("NE", "SE", "SW", "NW")),
])
def test_camera_turns_select_the_corresponding_authored_facing(
    data: AnimationData, facing: Facing8, expected: tuple[Facing8, ...],
) -> None:
    assert tuple(view_facing(facing, quadrant, data) for quadrant in range(4)) == expected


@pytest.mark.parametrize("phase", ["prepare", "travel", "impact"])
def test_four_camera_views_preserve_the_same_authored_clock_sample(
    data: AnimationData, phase: Literal["prepare", "travel", "impact"],
) -> None:
    timeline = reference_cast(data, caster_height=1, target_height=2)
    effect = phase_sample(timeline, phase, 0.375)
    anchors = timeline.anchors
    views = tuple(project_projectile(timeline, effect, quadrant) for quadrant in range(4))
    asset = data.projectile_assets[effect.asset_id]
    assert tuple(asset.rowOrder[view.row] for view in views) == ("E", "S", "W", "N")
    assert len({view.point for view in views}) == 4
    for view in views:
        assert (view.application_id, view.phase, view.asset_id, view.column, view.progress) == (
            effect.application_id, effect.phase, effect.asset_id, effect.column, effect.progress,
        )
    assert timeline.anchors == anchors
    assert phase_sample(timeline, phase, 0.375) == effect
    assert project_projectile(timeline, effect, 0) == views[0]


@pytest.mark.parametrize("phase", ["prepare", "travel", "impact"])
def test_original_studio_unit_scale_camera_zero_sample_remains_unchanged(
    data: AnimationData, phase: Literal["prepare", "travel", "impact"],
) -> None:
    source = reference_cast(data).source
    timeline = compile_cast(
        data,
        'spell.fire_bolt',
        replace(
            source,
            caster=replace(source.caster, visual_scale=1),
            applications=(replace(source.applications[0], target=replace(source.applications[0].target, visual_scale=1)),),
        ),
    )
    effect = phase_sample(timeline, phase, 0.375)
    view = project_projectile(timeline, effect, 0)
    assert view.point == pytest.approx(effect.point)
    assert view.row == effect.row
    assert view.rotation_radians == pytest.approx(effect.rotation_radians)


def test_projected_contact_overlap_does_not_finish_travel_early(data: AnimationData) -> None:
    timeline = reference_cast(data, target_grid=(1, 1), target_height=1)
    source = timeline.source
    assert project_world(source.caster.grid, elevation_steps=0) == project_world(source.applications[0].target.grid, elevation_steps=1)
    travel = next((phase for phase in timeline.applications[0].projectile_intervals if phase.name == 'travel'))
    for progress in (0.0, 0.5, 0.999):
        effect = phase_sample(timeline, "travel", progress)
        view = project_projectile(timeline, effect, 0)
        assert view.progress == pytest.approx(progress)
        assert view.phase == "travel"
        assert timeline.data.projectile_assets[view.asset_id].rowOrder[view.row] == "S"
        expected_ground = project_world(source.caster.grid)
        factor = TILE_WIDTH / data.rig.TILE_W
        assert view.point == pytest.approx((expected_ground[0] / factor,
                                           expected_ground[1] / factor + 52.5))
        elapsed = travel.start_ms + (travel.end_ms - travel.start_ms) * progress
        assert "impact" not in {anchor.name for anchor in crossed_anchors(
            timeline, travel.start_ms, elapsed,
        )}
    impact = phase_sample(timeline, "impact")
    assert impact.phase == "impact"
    assert [anchor.name for anchor in crossed_anchors(
        timeline, travel.start_ms, travel.end_ms,
    )] == ["impact"]


@pytest.mark.parametrize("quadrant", range(4))
def test_support_lift_and_art_padding_stay_vertical_in_every_view(
    data: AnimationData, quadrant: int,
) -> None:
    # Remove authored insets in the actual source-format record so the two
    # endpoints isolate support lift and the scaled canvas attachment.
    document = data.drafts["spell.fire_bolt"].model_dump(mode="json", exclude_unset=True)
    document["projectile"]["sourceAnchor"]["axisPx"] = 0
    document["projectile"]["targetAnchor"]["forwardPx"] = 0
    document["projectile"].pop("sourceAnchorsByFacing", None)
    draft = StudioSpellDraft.model_validate_json(json.dumps(document))
    selected = replace(data, drafts=MappingProxyType({**data.drafts, "spell.fire_bolt": draft}))
    timeline = reference_cast(selected, caster_height=2, target_height=3, target_scale=0.75)
    factor = TILE_WIDTH / data.rig.TILE_W
    endpoints: tuple[tuple[Literal["prepare", "impact"], ActorContact], ...] = (
        ("prepare", timeline.source.caster), ("impact", timeline.source.applications[0].target),
    )
    for phase, contact in endpoints:
        effect = phase_sample(timeline, phase)
        view = project_projectile(timeline, effect, quadrant)
        ground = project_world(contact.grid, elevation_steps=contact.elevation_steps,
                               quadrant=quadrant)
        assert view.point == pytest.approx((
            ground[0] / factor,
            ground[1] / factor + data.rig.RIG_ORIGIN_Y_FROM_GROUND * contact.visual_scale
            + 64 * (1 - contact.visual_scale),
        ))


def test_camera_uses_its_authored_local_anchor_without_retiming(data: AnimationData) -> None:
    document = data.drafts["spell.fire_bolt"].model_dump(mode="json", exclude_unset=True)
    source_anchor = document["projectile"]["sourceAnchor"]
    source_anchor["axisPx"] = 0
    document["projectile"]["targetAnchor"]["forwardPx"] = 0
    document["projectile"]["sourceAnchorsByFacing"] = {
        "S": {**source_anchor, "forwardPx": 10, "sidePx": 4, "liftY": -6},
    }
    draft = StudioSpellDraft.model_validate_json(json.dumps(document))
    selected = replace(data, drafts=MappingProxyType({**data.drafts, "spell.fire_bolt": draft}))
    timeline = reference_cast(selected)
    effect = phase_sample(timeline, "prepare")
    anchors = timeline.anchors
    factor = TILE_WIDTH / data.rig.TILE_W
    for quadrant, offset in ((0, (0, 0)), (1, (-2, 2)), (2, (0, 0)), (3, (0, 0))):
        view = project_projectile(timeline, effect, quadrant)
        ground = project_world(timeline.source.caster.grid, quadrant=quadrant)
        assert view.point == pytest.approx((ground[0] / factor + offset[0],
                                           ground[1] / factor + 52.5 + offset[1]))
    assert timeline.anchors == anchors
    assert phase_sample(timeline, "prepare") == effect


def test_explicit_terrace_arc_clears_full_support_spans_without_retiming(data: AnimationData) -> None:
    straight = reference_cast(data, caster_grid=(16, 25), target_grid=(16, 20),
                              target_height=2, target_scale=0.82)
    arc = compile_cast(data, 'spell.fire_bolt', replace(straight.source, applications=(replace(straight.source.applications[0], travel_apex_steps=1),)))
    assert arc.recipe == straight.recipe
    assert arc.anchors == straight.anchors
    assert arc.applications[0].projectile_intervals == straight.applications[0].projectile_intervals
    assert arc.complete_ms == straight.complete_ms

    # Actual terrace supports from battlefield.visual_vertical_seam. The upper
    # stair starts at t=.5, before its center t=.6. A positive quadratic is
    # concave, so each constant-height cell's minimum is at one of its edges.
    spans = (
        (0, 0.0, 0.1), (0, 0.1, 0.3), (1, 0.3, 0.5),
        (2, 0.5, 0.7), (2, 0.7, 0.9), (2, 0.9, 1.0),
    )
    for support, entry, exit in spans:
        for progress in (entry, (entry + exit) / 2, exit):
            effect = phase_sample(arc, "impact") if progress == 1 else phase_sample(arc, "travel", progress)
            position, height = projectile_contact(arc, effect)
            assert position == pytest.approx((16, 25 - 5 * progress))
            assert height >= support - 1e-9
    assert projectile_contact(straight, phase_sample(straight, "travel", 0.5))[1] == pytest.approx(1)
    assert projectile_contact(arc, phase_sample(arc, "travel", 0.5))[1] == pytest.approx(2)
    assert projectile_contact(arc, phase_sample(arc, "prepare")) == ((16, 25), 0)
    assert projectile_contact(arc, phase_sample(arc, "impact")) == ((16, 20), 2)
    for elapsed in (0, arc.release_ms, arc.applications[0].hp_ms, arc.complete_ms):
        assert elapsed is not None
        original, lifted = sample_cast(straight, elapsed), sample_cast(arc, elapsed)
        assert lifted.bodies == original.bodies
        assert lifted.vitals[0].hp == original.vitals[0].hp
        assert lifted.numbers == original.numbers


@pytest.mark.parametrize("quadrant", range(4))
def test_terrace_arc_projects_world_lift_and_preserves_incoming_impact_tangent(
    data: AnimationData, quadrant: int,
) -> None:
    straight = reference_cast(data, caster_grid=(16, 25), target_grid=(16, 20),
                              target_height=2, target_scale=0.82)
    arc = compile_cast(data, 'spell.fire_bolt', replace(straight.source, applications=(replace(straight.source.applications[0], travel_apex_steps=1),)))
    height_pixels = HEIGHT_STEP_PIXELS * data.rig.TILE_W / TILE_WIDTH
    for progress, lift in ((0.25, 0.75), (0.5, 1), (0.75, 0.75)):
        original = project_projectile(straight, phase_sample(straight, "travel", progress), quadrant)
        lifted = project_projectile(arc, phase_sample(arc, "travel", progress), quadrant)
        assert lifted.point == pytest.approx((original.point[0], original.point[1] - lift * height_pixels))
        assert (lifted.row, lifted.column, lifted.progress, lifted.phase) == (
            original.row, original.column, original.progress, original.phase,
        )
    for phase in ("prepare", "impact"):
        original = project_projectile(straight, phase_sample(straight, phase), quadrant)
        lifted = project_projectile(arc, phase_sample(arc, phase), quadrant)
        assert lifted.point == pytest.approx(original.point)

    original_end = project_projectile(straight, phase_sample(straight, "impact"), quadrant)
    arc_end = project_projectile(arc, phase_sample(arc, "impact"), quadrant)
    original_incoming = project_projectile(straight, phase_sample(straight, "travel", 1 - 1e-6), quadrant)
    arc_incoming = project_projectile(arc, phase_sample(arc, "travel", 1 - 1e-6), quadrant)
    original_bearing = atan2(original_end.point[1] - original_incoming.point[1],
                             original_end.point[0] - original_incoming.point[0])
    arc_bearing = atan2(arc_end.point[1] - arc_incoming.point[1],
                       arc_end.point[0] - arc_incoming.point[0])
    # Compare against the actual projected path, cancelling the shared authored
    # atlas orientation. Impact keeps the incoming tangent without a snap.
    orientation_error = (arc_end.rotation_radians - original_end.rotation_radians
                         - (arc_bearing - original_bearing))
    continuity_error = arc_end.rotation_radians - arc_incoming.rotation_radians
    for error in (orientation_error, continuity_error):
        assert sin(error) == pytest.approx(0, abs=2e-5)
        assert cos(error) == pytest.approx(1, abs=2e-5)
