"""Native hot-side damage replays a finite contact sweep without changing terrain."""

from dataclasses import replace

import pygame
import pytest

from dnd.core.events import EventQueue
from game.animation_data import load_animation_data
from game.choreography import bind_choreography, sample_choreography
from game.player_facts import DamageFact
from game.player_facts import SpellFact
from game.player_projection import project_sequence
from game.player_reduction import decode_player_sequence, encode_player_sequence, reduce_lineage
from game.projection import Camera, project_screen
from game.spatial_contact_media import bind_damage_sweep
from game.stationary_media import stationary_media_draw_commands
from game.wall_media import wall_media_draw_commands
from tests.game.wall_spell_scenarios import wall_spell_history


@pytest.fixture(scope="module")
def heat_data():
    pygame.init()
    pygame.display.set_mode((640, 480))
    yield load_animation_data()
    pygame.quit()


@pytest.mark.parametrize("axis", ("x", "y"))
def test_received_hot_side_damage_plays_native_sweep_in_cold_replay(heat_data, axis):
    recorded = wall_spell_history(axis=axis)
    state, lineages = decode_player_sequence(encode_player_sequence(project_sequence(recorded.views["caster"])))
    assert EventQueue.event_cursor() == 0
    witnessed = 0
    for lineage in lineages:
        group = bind_choreography(state, lineage, heat_data)
        for node in lineage.events:
            fact = node.fact
            if not (isinstance(fact, DamageFact) and fact.stage == "applied"
                    and fact.spatial_source is not None and fact.spatial_source.exposure == "radiated_heat"):
                continue
            source = fact.spatial_source
            cues = tuple(cue for cue in group.contact_media if cue.event_uuid == node.uuid)
            assert len(cues) == 6
            start = min(cue.start_ms for cue in cues)
            assert any(cue.contact.actor_uuid == str(fact.target_entity_uuid)
                       and cue.timing.start_ms == start+900 for cue in group.damage)
            prior = sample_choreography(group, start+899).displayed.actors[fact.target_entity_uuid]
            assert prior.normal_hp == state.actors[fact.target_entity_uuid].normal_hp
            assert {cue.start_ms-start for cue in cues} == {0, 180, 360}
            expected = {tuple(a+(b-a)*fraction for a, b in zip(source.position, source.target_position))
                        for fraction in (0, .5, 1)}
            assert {cue.position for cue in cues} == expected
            assert all(cue.native_pixels and cue.elevation_steps == source.base_height_steps for cue in cues)
            assert not stationary_media_draw_commands(cues, start+1810, Camera())
            for quadrant in range(4):
                camera = Camera(quadrant=quadrant, zoom=1, viewport=(640, 480)).with_focus(source.position)
                draw = stationary_media_draw_commands(cues, start+800, camera)
                assert draw
                for command in draw:
                    asset = heat_data.projectile_assets[command.evidence[2]]
                    layer = heat_data.projectile_storage[asset.assetId].phases["impact"].layers[0]
                    part = layer.partsByFacing[("E", "S", "W", "N")[quadrant]][command.evidence[9]][0]
                    anchor = project_screen(command.evidence[1], camera, elevation_steps=source.base_height_steps)
                    assert command.destination == (round(anchor[0]+part.offset[0]-asset.anchor.x*asset.frame.width),
                                                   round(anchor[1]+part.offset[1]-asset.anchor.y*asset.frame.height))
                    assert command.surface.get_size() == part.rect[2:]
            for changed in (replace(fact, spatial_source=None), replace(fact, applied_damage=0),
                            replace(fact, spatial_source=source.model_copy(update={"exposure": "contact"})),
                            replace(fact, spatial_source=source.model_copy(update={
                                "target_position": (source.position[0]+1, source.position[1]+1)}))):
                assert not bind_damage_sweep(state, replace(node, fact=changed), heat_data, 0)
            assert group.after == reduce_lineage(state, lineage), "Decorative fire does not change saved game state"
            witnessed += 1
        state = reduce_lineage(state, lineage)
    assert witnessed > 0
    assert EventQueue.event_cursor() == 0


def test_multiple_wall_recipients_keep_safe_side_unharmed(heat_data):
    recorded = wall_spell_history(multiple_targets=True)
    state, lineages = decode_player_sequence(encode_player_sequence(project_sequence(recorded.views["safe"])))
    safe = next(actor for actor in state.actors.values() if actor.name == "Safe")
    hp = safe.normal_hp
    for lineage in lineages:
        assert not any(isinstance(node.fact, DamageFact) and node.fact.stage == "applied"
                       and node.fact.target_entity_uuid == safe.uuid for node in lineage.events)
        state = reduce_lineage(state, lineage)
    assert state.actors[safe.uuid].normal_hp == hp


def test_wall_formation_damages_two_victims_at_the_same_presentation_time(heat_data):
    recorded = wall_spell_history(multiple_targets=True, formation_targets=True)
    state, lineages = decode_player_sequence(encode_player_sequence(project_sequence(recorded.views["caster"])))
    victims = {actor.uuid for actor in state.actors.values() if actor.name in ("Hot near", "Hot far")}
    assert len(victims) == 2
    for lineage in lineages:
        if isinstance(lineage.root.fact, SpellFact) and lineage.root.fact.behavior_id == "spell.wall_of_fire":
            bound = bind_choreography(state, lineage, heat_data)
            injuries = [cue for cue in bound.damage if cue.contact.actor_uuid in {str(identity) for identity in victims}]
            assert len(injuries) == 2
            assert len({cue.timing.start_ms for cue in injuries}) == 1
            return
        state = reduce_lineage(state, lineage)
    pytest.fail("Native wall cast was not received")


@pytest.mark.parametrize("axis", ("x", "y"))
def test_safe_base_tint_follows_recorded_side_preserving_alpha_and_old_recordings(heat_data, axis):
    recorded = wall_spell_history(axis=axis)
    state, lineages = decode_player_sequence(encode_player_sequence(project_sequence(recorded.views["caster"])))
    cast = next(lineage for lineage in lineages if isinstance(lineage.root.fact, SpellFact)
                and lineage.root.fact.behavior_id == "spell.wall_of_fire")
    for lineage in lineages:
        state = reduce_lineage(state, lineage)
        if lineage is cast:
            break
    identity, effect = next(iter(state.senses.spatial_effects.items()))
    geometry = effect.area_geometry
    assert geometry.hot_side == "left"
    binding = heat_data.spatial_media[effect.content_ref.content_id]
    uncolored = binding.model_copy(update={"safeSideTint": None})
    opposite = effect.model_copy(update={"area_geometry": geometry.model_copy(update={"hot_side": "right"})})
    legacy = effect.model_copy(update={"area_geometry": geometry.model_copy(update={"hot_side": None})})
    reverse = effect.model_copy(update={"area_geometry": geometry.model_copy(update={"path":
        geometry.path.model_copy(update={"start": geometry.path.end, "end": geometry.path.start})})})
    for quadrant in range(4):
        camera = Camera(quadrant=quadrant, zoom=1, viewport=(640, 480)).with_focus((6, 6))
        def draw(row, recipe=binding):
            return wall_media_draw_commands(row, identity, heat_data, recipe, 2000, camera, 0, None)
        normal, plain, other = draw(effect), draw(effect, uncolored), draw(opposite)
        assert normal and len(normal) == len(plain) == len(other)
        assert any(pygame.image.tobytes(a.surface, "RGB") != pygame.image.tobytes(b.surface, "RGB")
                   for a, b in zip(normal, plain))
        assert any(pygame.image.tobytes(a.surface, "RGB") != pygame.image.tobytes(b.surface, "RGB")
                   for a, b in zip(normal, other))
        assert all(pygame.surfarray.array_alpha(a.surface).tolist() ==
                   pygame.surfarray.array_alpha(b.surface).tolist() for a, b in zip(normal, plain))
        assert [pygame.image.tobytes(row.surface, "RGBA") for row in draw(legacy)] == [
            pygame.image.tobytes(row.surface, "RGBA") for row in plain]
        assert [pygame.image.tobytes(row.surface, "RGBA") for row in draw(reverse)] == [
            pygame.image.tobytes(row.surface, "RGBA") for row in other]


@pytest.mark.parametrize("form", ("straight", "ring"))
def test_formation_contact_flames_precede_injury_for_both_wall_forms(heat_data, form):
    recorded = (wall_spell_history(multiple_targets=True, formation_targets=True) if form == "straight"
                else wall_spell_history(ring_hot_side="inside"))
    view = recorded.views["caster" if form == "straight" else "center"]
    state, lineages = decode_player_sequence(encode_player_sequence(project_sequence(view)))
    for lineage in lineages:
        if isinstance(lineage.root.fact, SpellFact) and lineage.root.fact.behavior_id == "spell.wall_of_fire":
            group = bind_choreography(state, lineage, heat_data)
            release = group.body_actions[0].effect_ms
            packets = [node for node in lineage.events if isinstance(node.fact, DamageFact)
                and node.fact.stage == "applied" and node.fact.spatial_source is not None
                and node.fact.spatial_source.exposure == "contact"]
            assert packets
            for packet in packets:
                victim = packet.fact.target_entity_uuid
                injury = next(cue for cue in group.damage if cue.contact.actor_uuid == str(victim))
                flames = tuple(cue for cue in group.contact_media if cue.event_uuid == packet.uuid)
                assert len(flames) == 2, "Paired native contact flames must envelop the actual victim"
                assert {cue.position for cue in flames} == {packet.fact.spatial_source.target_position}
                assert injury.timing.start_ms == release+900
                assert min(cue.start_ms for cue in flames) == release
                assert sample_choreography(group, release+899).displayed.actors[victim].normal_hp == state.actors[victim].normal_hp
                assert stationary_media_draw_commands(flames, release+800, Camera())
            # Delayed injury must not replay an older perception snapshot over
            # creation's completed shell, or leave a gap before sustained media.
            for age in (800, 1600, 2300):
                displayed = sample_choreography(group, release+age).displayed
                assert displayed.senses is not None
                assert displayed.senses.spatial_effects
                for identity, effect in displayed.senses.spatial_effects.items():
                    binding = heat_data.spatial_media[effect.content_ref.content_id]
                    assert wall_media_draw_commands(effect, identity, heat_data, binding,
                        release+age, Camera(), release, None), (form, age, effect.positions)
            return
        state = reduce_lineage(state, lineage)
    pytest.fail("Native formation cast absent")
