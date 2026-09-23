"""Damage facts select shared blood styles without changing receiving geometry."""

from dataclasses import replace
from functools import partial

import pygame
import pytest

from dnd.core.creature_types import DamageType
from game.action_media import bind_action_strips, sample_action_strip
from game.animation_data import load_animation_data
from game.animation_draw import action_media_draw_commands
from game.animation_types import ParticleMediaAsset
from game.choreography import bind_choreography
from game.particle_media import sample_particles, sample_vapor
from game.player_projection import project_sequence
from game.player_reduction import decode_player_sequence, encode_player_sequence, reduce_lineage
from game.projection import Camera
from game.residue_media import landing_point, landing_template, particle_schedule, target_cell
from tests.game.spell_handoff_scenarios import spell_handoff_history
from tests.game.cantrip_scenarios import cantrip_history
from tests.game.area_spell_scenarios import area_spell_history


@pytest.fixture(scope="module")
def data():
    pygame.init()
    pygame.display.set_mode((320,240))
    yield load_animation_data()
    pygame.quit()


@pytest.mark.parametrize("history,expected", (
    (partial(spell_handoff_history, program="acid"), DamageType.ACID),
    (partial(spell_handoff_history, program="ray"), DamageType.COLD),
    (partial(spell_handoff_history, program="fireball"), DamageType.FIRE),
    (partial(spell_handoff_history, program="eldritch"), DamageType.FORCE),
    (partial(cantrip_history, program="shocking"), DamageType.LIGHTNING),
    (partial(spell_handoff_history, program="chill"), DamageType.NECROTIC),
    (partial(cantrip_history, program="poison"), DamageType.POISON),
    (partial(cantrip_history, program="sacred"), DamageType.RADIANT),
    (partial(area_spell_history, program="thunderwave"), DamageType.THUNDER),
))
def test_real_spell_replay_retains_particle_destinations_and_finite_material_tail(data, history, expected):
    saved = history()
    state, roots = decode_player_sequence(encode_player_sequence(project_sequence(next(iter(saved.views.values())))))
    checked = 0
    for root in roots:
        group = bind_choreography(state, root, data)
        for cue in group.strips:
            if cue.release is None:
                continue
            release, asset = cue.release, cue.asset
            assert release.primary_damage_type is expected
            assert cue.response == data.blood_responses[expected.value]
            assert cue.response is not None
            assert isinstance(asset, ParticleMediaAsset) and asset.region is not None
            assert release.pattern is not None
            family = asset.region.families[release.pattern]
            for region_index, region in enumerate(release.regions):
                template = landing_template(asset.region, region.ellipse)
                for particle in template.particles:
                    goal = landing_point(region.ellipse, particle.target)
                    if target_cell(goal) not in region.positions:
                        continue
                    identity = region_index*len(template.particles)+particle.id
                    delay, flight, melt = particle_schedule(particle,family,cue.response)
                    landing = cue.start_ms + (delay+flight)*1000*asset.defaultFps/cue.track.fps
                    sample = sample_action_strip(cue, landing-.001)
                    assert sample is not None
                    last = next(p for p in sample_particles(sample,asset) if p.identity == identity)
                    assert last.grid == pytest.approx(goal,abs=.0001)
                    assert last.elevation == pytest.approx(region.elevation_steps,abs=.0001)
                    if melt:
                        sample = sample_action_strip(cue, landing+melt*500)
                        assert sample is not None
                        solid = next(p for p in sample_particles(sample,asset) if p.identity == identity)
                        assert solid.grid == pytest.approx(goal)
                        assert solid.solid == pytest.approx(.5)
                    assert cue.end_ms >= landing+melt*1000
            ending = sample_action_strip(cue,cue.end_ms-.001)
            assert ending is not None
            assert not sample_particles(ending,asset) and not sample_vapor(ending,asset)
            assert sample_action_strip(cue,cue.end_ms) is None
            sample = sample_action_strip(cue,cue.start_ms+120)
            assert sample is not None
            particles = sample_particles(sample,asset)
            for quadrant in range(4):
                assert action_media_draw_commands(sample,{},Camera(quadrant=quadrant))
                assert sample_particles(sample,asset) == particles
            assert sample_action_strip(cue,cue.start_ms+120) == sample
            checked += 1
        state = reduce_lineage(state,root)
    assert checked


def test_cold_vapor_and_other_materials_do_not_invent_blood_responses(data):
    # These are passive presentation values: one retained native release is
    # replayed with each declared causal type, without executing mechanics.
    saved = spell_handoff_history(program="ray")
    state, roots = decode_player_sequence(encode_player_sequence(project_sequence(next(iter(saved.views.values())))))
    original = None
    for root in roots:
        group = bind_choreography(state,root,data)
        original = next((cue for cue in group.strips if cue.release is not None), original)
        state = reduce_lineage(state,root)
    assert original is not None and original.release is not None
    for damage_type in DamageType:
        release = original.release.model_copy(update={"primary_damage_type": damage_type})
        cue, = bind_action_strips(original.event_uuid,original.contact,(original.track,),data,
            start_ms=0, release=release)
        assert cue.response == data.blood_responses[damage_type.value]
        if damage_type in (DamageType.PIERCING,DamageType.SLASHING,DamageType.BLUDGEONING):
            assert cue.response is None
        for material in ("body.bone","body.corrosive_demonic_blood","body.dread_blood"):
            other, = bind_action_strips(original.event_uuid,original.contact,(original.track,),data,
                start_ms=0, release=release.model_copy(update={"release_id":material}))
            assert other.response is None
    fire, = bind_action_strips(original.event_uuid,original.contact,(original.track,),data,
        start_ms=0,release=original.release.model_copy(update={"primary_damage_type":DamageType.FIRE}))
    assert isinstance(fire.asset,ParticleMediaAsset)
    sample = sample_action_strip(fire,500)
    assert sample is not None
    vapor = sample_vapor(sample,fire.asset)
    assert vapor
    moved = replace(sample,cue=replace(fire,contact=replace(fire.contact,grid=(40,40))))
    # Some emissions happen while airborne; their origins use actual past
    # trajectory points, not a current actor-position-following body burst.
    assert any(row.grid != fire.contact.grid for row in vapor)
    assert sample_vapor(sample,fire.asset) == vapor
    assert sample_vapor(moved,fire.asset) != vapor
