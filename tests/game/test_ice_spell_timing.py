"""Actual authored deliveries keep contact separate from their visual clocks."""

from dataclasses import replace

import pytest

from game.animation import ActorContact, CastApplication, CastInput, compile_cast, sample_cast, project_projectile, ProjectileSample
from game.animation_data import load_animation_data


@pytest.fixture(scope="module")
def data():
    return load_animation_data()


def cast(data, spell):
    return compile_cast(data, "spell."+spell, CastInput("ice-review",
        ActorContact("caster", (2,2), "E", 1),
        (CastApplication("hit",ActorContact("target", (7,3), "W", 1,hp=30),True,4,26),)))


def test_chill_smoke_does_not_hit_until_the_authored_hand_contacts(data):
    timeline = cast(data,"chill_touch")
    assert timeline.release_ms == pytest.approx(1000*7/12)
    assert timeline.applications[0].damage_start_ms == pytest.approx(625)
    before = sample_cast(timeline, 624)
    contact = sample_cast(timeline, 625)
    assert next(body for body in before.bodies if body.actor_uuid=="target").clip == "Idle"
    assert next(body for body in contact.bodies if body.actor_uuid=="target").clip == "TakeDamage"
    assert before.vitals[0].flash is None
    assert contact.vitals[0].flash is not None
    assert sample_cast(timeline,775).vitals[0].flash is None
    effect, = contact.projectiles
    assert isinstance(effect,ProjectileSample) and effect.column == 236
    early, = sample_cast(timeline,1000*5/12).projectiles
    assert isinstance(early,ProjectileSample) and early.column == 206
    assert not any(effect.phase=="travel" for effect in before.projectiles)
    frames = [sample_cast(timeline,t).projectiles[0].column for t in (0,200,416.67,625,900,1800)]
    assert frames == sorted(set(frames))


def test_ray_fades_at_contact_while_source_animation_keeps_advancing(data):
    timeline = cast(data,"ray_of_frost")
    arrival = timeline.applications[0].travel_end_ms
    contact = sample_cast(timeline,arrival)
    midway = sample_cast(timeline,arrival+80)
    travel = next(effect for effect in contact.projectiles if effect.phase=="travel")
    later = next(effect for effect in midway.projectiles if effect.phase=="travel")
    assert isinstance(travel,ProjectileSample) and isinstance(later,ProjectileSample)
    assert any(effect.phase=="impact" for effect in contact.projectiles)
    assert travel.opacity==1 and later.opacity==pytest.approx(.5)
    assert travel.progress==later.progress==1
    assert later.column!=travel.column
    assert not any(effect.phase=="travel" for effect in sample_cast(timeline,arrival+160).projectiles)
    assert contact.vitals[0].flash is not None
    for quadrant in range(4):
        assert project_projectile(timeline,travel,quadrant).point == project_projectile(timeline,later,quadrant).point
    recipe=timeline.recipe
    assert recipe.projectile is not None
    no_overlap=recipe.model_copy(update={"projectile":recipe.projectile.model_copy(update={
        "travel":recipe.projectile.travel.model_copy(update={"overlapContactMs":0})})})
    previous=cast(replace(data,drafts={**data.drafts,"spell.ray_of_frost":no_overlap}),"ray_of_frost")
    assert previous.applications[0].damage_start_ms==timeline.applications[0].damage_start_ms
