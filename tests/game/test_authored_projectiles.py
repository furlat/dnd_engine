"""Imported sprites use the shared ordered delivery, curve and feedback owners."""

from dataclasses import replace
import json
from math import atan2, pi
from types import MappingProxyType

import pytest

from game.animation import (
    ActorContact, CastApplication, CastInput, CastTimeline, ProjectileSample,
    compile_cast, project_projectile, projectile_contact, sample_cast,
)
from game.animation_data import DATA_ROOT, load_animation_data
from game.animation_types import StudioSpellDraft
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
    baseline = compile_cast(load_animation_data(authored_bundles=()), "spell.magic_missile", timeline.source)
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
        assert (actual.bodies, actual.vitals, actual.numbers, actual.complete) == (
            original.bodies, original.vitals, original.numbers, original.complete,
        )


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


def test_movement_context_preserves_original_source_data() -> None:
    source = json.loads((DATA_ROOT / "source/src/render/data/animation/actionContextPresentation.json").read_text())
    data = load_animation_data()
    assert data.movement_context.model_dump(mode="json") == source["contexts"]["voluntary_movement"]
