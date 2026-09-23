"""Actual item casts retain their muzzle, spell delivery and seekable body timing."""

from dataclasses import replace
from math import hypot

import pytest

from game.animation import ActorContact, CastApplication, CastInput, ProjectileSample, cast_deliveries, compile_cast, delivery_identity, project_projectile, sample_cast
from game.animation_data import load_animation_data
from game.combat import bind_cast
from game.player_facts import SpellFact
from game.player_projection import project_sequence
from game.player_reduction import decode_player_sequence, encode_player_sequence, reduce_lineage
from game.projection import TILE_WIDTH, project_world
from tests.game.device_scenarios import device_history


@pytest.fixture(scope="module")
def casts():
    captured = device_history(program="mixed-spells")
    data = load_animation_data()
    result = []
    for history in captured.views.values():
        state, lineages = decode_player_sequence(encode_player_sequence(project_sequence(history)))
        for lineage in lineages:
            if (isinstance(lineage.root.fact, SpellFact) and not lineage.root.canceled
                    and lineage.root.fact.cast_origin == "source_item"):
                result.append(bind_cast(state, lineage, data).timeline)
            state = reduce_lineage(state, lineage)
    return result


@pytest.mark.parametrize("quadrant", range(4))
def test_both_spells_launch_from_the_same_measured_device_muzzle(casts, quadrant):
    assert len(casts) == 4  # Two real spells, witnessed by both participants.
    for timeline in casts:
        emitter = timeline.source.emitter
        assert emitter is not None and emitter.grid != timeline.source.caster.grid
        assert emitter.art.identity == "cannon"
        assert timeline.recipe.cast.actionClip == "Attack5"
        assert timeline.release_ms == 250
        row = emitter.art.rows.index(emitter.facing)
        pixel = emitter.bank.muzzle_pixels[quadrant][row][emitter.art.release_frame]
        support = project_world(emitter.grid, elevation_steps=emitter.elevation_steps, quadrant=quadrant)
        expected = tuple(support[i] + (pixel[i] - emitter.art.anchor[i]) * emitter.art.scale for i in range(2))
        for delivery in cast_deliveries(timeline):
            sample = sample_cast(timeline, delivery.travel_start_ms)
            effect = next(effect for effect in sample.projectiles if isinstance(effect, ProjectileSample)
                          and effect.phase == "travel" and effect.application_id == delivery_identity(delivery))
            drawn = project_projectile(timeline, effect, quadrant)
            factor = TILE_WIDTH / timeline.data.rig.TILE_W
            assert tuple(value * factor for value in drawn.point) == pytest.approx(expected)
            next_point = project_projectile(timeline, replace(effect, progress=0.000001), quadrant).point
            delta = next_point[0] - drawn.point[0], next_point[1] - drawn.point[1]
            bore = emitter.bank.forward_screen[quadrant][row]
            cosine = sum(a*b for a, b in zip(delta, bore)) / hypot(*delta) / hypot(*bore)
            assert cosine > .99999


def test_device_recoil_never_moves_a_launched_spell_and_seek_is_repeatable(casts):
    for timeline in casts:
        release = sample_cast(timeline, timeline.release_ms)
        recoil = sample_cast(timeline, timeline.release_ms + 100)
        assert release.device_frame == 3 and recoil.device_frame == 4
        sample_cast(timeline, timeline.complete_ms)
        assert sample_cast(timeline, timeline.release_ms) == release
        assert sample_cast(timeline, timeline.release_ms + 100) == recoil
        assert not release.bodies[0].cast_layers
        assert timeline.ground_delivery is not None
        assert timeline.ground_delivery.target.grid == (10, 5)
        assert len(cast_deliveries(timeline)) == 1
        if timeline.recipe.definitionRef.content_id == "spell.sleep":
            assert not any(row.source.damage_applied for row in timeline.applications)
            assert all(isinstance(effect, ProjectileSample) and effect.asset_id == "sleep.projectile.v1"
                       for effect in release.projectiles)


def test_device_launch_preserves_the_spells_authored_rotation_opt_out(casts):
    for timeline in casts:
        projectile = timeline.recipe.projectile
        assert projectile is not None
        orientation = projectile.orientation.model_copy(update={"fineRotation": "none"})
        recipe = timeline.recipe.model_copy(update={
            "projectile": projectile.model_copy(update={
                "orientation": orientation,
                "travel": projectile.travel.model_copy(update={"fineRotation": "none"}),
            }),
        })
        timeline = replace(timeline, recipe=recipe)
        delivery = cast_deliveries(timeline)[0]
        sample = sample_cast(timeline, (delivery.travel_start_ms + delivery.travel_end_ms) / 2)
        effects = [effect for effect in sample.projectiles
                   if isinstance(effect, ProjectileSample) and effect.phase == "travel"]
        assert effects
        for effect in effects:
            assert [project_projectile(timeline, effect, camera).rotation_radians
                    for camera in range(4)] == [0.0] * 4


@pytest.mark.parametrize("quadrant", range(4))
def test_fire_bolt_uses_actual_muzzle_and_insets_along_the_device_target_chord(casts, quadrant):
    reference = casts[0]
    emitter = reference.source.emitter
    assert emitter is not None
    target = ActorContact("recipient", (9, 6), "N", .8, elevation_steps=1)
    timeline = compile_cast(reference.data, "spell.fire_bolt", CastInput("shot",
        reference.source.caster, (CastApplication("hit", target, False, None, None),), emitter=emitter))
    delivery, = timeline.applications
    effect = next(row for row in sample_cast(timeline, delivery.travel_start_ms).projectiles
        if isinstance(row, ProjectileSample) and row.phase == "travel")
    row = emitter.art.rows.index(emitter.facing)
    pixel = emitter.bank.muzzle_pixels[quadrant][row][emitter.art.release_frame]
    support = project_world(emitter.grid, elevation_steps=emitter.elevation_steps, quadrant=quadrant)
    factor = TILE_WIDTH / timeline.data.rig.TILE_W
    muzzle = tuple((support[i]+(pixel[i]-emitter.art.anchor[i])*emitter.art.scale)/factor for i in range(2))
    assert project_projectile(timeline, replace(effect, progress=0), quadrant).point == pytest.approx(muzzle)
    x, y = project_world(target.grid, elevation_steps=target.elevation_steps, quadrant=quadrant)
    center = (x/factor, y/factor+(41-64)*target.visual_scale)
    dx, dy = center[0]-muzzle[0], center[1]-muzzle[1]
    distance = hypot(dx, dy)
    end = (center[0]-16*target.visual_scale*dx/distance,
           center[1]-16*target.visual_scale*dy/distance)
    assert project_projectile(timeline, replace(effect, progress=1), quadrant).point == pytest.approx(end)
