"""Actual spell injuries survive JSON replay as contact-timed material releases."""

from dataclasses import replace
from functools import partial
from pathlib import Path

import pygame
import pytest

from game.action_media import bind_action_strips, sample_action_strip
from game.animation_data import load_animation_data
from game.animation_draw import action_media_draw_commands
from game.animation_types import ParticleMediaAsset
from game.choreography import bind_choreography
from game.combat import BoundCast
from game.player_facts import DamageFact
from game.player_projection import project_sequence
from game.player_reduction import decode_player_sequence, encode_player_sequence, reduce_lineage
from game.projection import Camera
from tests.game.area_spell_scenarios import area_spell_history
from tests.game.body_residue_scenarios import body_residue_history
from tests.game.cantrip_scenarios import cantrip_history
from tests.game.spell_handoff_scenarios import spell_handoff_history


@pytest.fixture(scope="module")
def data():
    return load_animation_data(rig_files=tuple(sorted(Path("game/data/rigs").glob("*.json"))))


@pytest.mark.parametrize("make_history,has_release", (
    (partial(cantrip_history, program="sacred"), True),
    (partial(cantrip_history, program="sacred", outcome="saved"), False),
    (partial(cantrip_history, program="poison"), True),
    (partial(cantrip_history, program="poison", outcome="saved"), False),
    (partial(cantrip_history, program="shocking"), True),
    (partial(cantrip_history, program="shocking", outcome="miss"), False),
    (partial(area_spell_history, program="burning_hands"), True),
    (partial(area_spell_history, program="thunderwave"), True),
    (partial(area_spell_history, program="gust_of_wind"), False),
    (partial(spell_handoff_history, program="eldritch", split=True, miss=True), True),
    (partial(spell_handoff_history, program="acid"), True),
    (partial(spell_handoff_history, program="ray"), True),
    (partial(spell_handoff_history, program="chill"), True),
    (partial(spell_handoff_history, program="ice"), True),
    (partial(spell_handoff_history, program="fireball"), True),
))
def test_saved_spell_damage_releases_at_its_own_contact(data, make_history, has_release):
    captured = make_history()
    for native in captured.views.values():
        state, roots = decode_player_sequence(encode_player_sequence(project_sequence(native)))
        witnessed = 0
        for root in roots:
            group = bind_choreography(state, root, data)
            assert not group.gaps
            packets = {node.uuid: node.fact for node in root.events
                       if isinstance(node.fact, DamageFact) and node.fact.stage == "applied"}
            releases = {cue.event_uuid: cue for cue in group.strips if cue.release is not None}
            assert set(releases) == set(packets)
            for identity, cue in releases.items():
                assert cue.release is not None
                assert cue.release == packets[identity].body_release
                assert cue.release.release_id == "body.blood"
                assert cue.particle_colors is not None
                # Each saved application has its own contact, including multi-hit
                # deliveries and Ice Knife's child area. No root-wide guessed time.
                arrivals = {node.start_ms + application.travel_end_ms
                    for node in group.nodes if isinstance(node.bound, BoundCast)
                    for application in node.bound.timeline.applications
                    if application.source.target.actor_uuid == cue.contact.actor_uuid}
                assert cue.start_ms in arrivals
                assert sample_action_strip(cue, cue.start_ms - .01) is None
                assert sample_action_strip(cue, cue.start_ms) is not None
                witnessed += 1
            state = reduce_lineage(state, root)
        assert bool(witnessed) is has_release
        assert any(residue.residue_id == "residue.blood"
                   for tile in state.tiles.values() for residue in tile.residues) is has_release


@pytest.mark.parametrize("profile", ("blood", "bone", "corrosive", "dread"))
def test_spell_tint_is_a_light_transient_overlay_on_the_existing_material(data, profile):
    captured = body_residue_history(profile=profile, hits=1, crossings=False)
    state, roots = decode_player_sequence(encode_player_sequence(project_sequence(captured.views["walker"])))
    root = next(root for root in roots if any(isinstance(node.fact, DamageFact) for node in root.events))
    group = bind_choreography(state, root, data)
    original, = group.strips
    assert isinstance(original.asset, ParticleMediaAsset)
    assert original.particle_colors is None
    tinted, = bind_action_strips(original.event_uuid, original.contact, (original.track,), data,
        start_ms=original.start_ms, direction=original.direction, release=original.release,
        spell_color=0x88CAFF)
    assert tinted.release == original.release and tinted.asset is original.asset
    assert tinted.particle_colors is not None and tinted.particle_colors != original.asset.colors
    for baseline, changed in zip(original.asset.colors, tinted.particle_colors, strict=True):
        assert all(abs((baseline >> shift & 255) - (changed >> shift & 255)) <= 16
                   for shift in (16, 8, 0))
    # Disabling only this authored overlay restores exact material colors.
    untinted, = bind_action_strips(original.event_uuid, original.contact,
        (original.track.model_copy(update={"spellTintStrength": 0}),), data,
        start_ms=original.start_ms, direction=original.direction, release=original.release,
        spell_color=0x88CAFF)
    assert untinted.particle_colors is None
    sample = sample_action_strip(tinted, tinted.start_ms + 100)
    assert sample is not None
    for quadrant in range(4):
        camera = Camera(quadrant=quadrant, zoom=1).with_focus(tinted.contact.grid)
        commands = action_media_draw_commands(sample, {}, camera)
        original_commands = action_media_draw_commands(replace(sample, cue=original), {}, camera)
        assert commands and len(commands) == len(original_commands)
        assert [(row.key, row.destination) for row in commands] == [
            (row.key, row.destination) for row in original_commands]
        assert any(pygame.image.tobytes(a.surface, "RGBA") != pygame.image.tobytes(b.surface, "RGBA")
                   for a, b in zip(commands, original_commands, strict=True))
    # Landed marks retain the original media/region palette and native substance.
    assert all(row.asset is original.asset for row in group.residue_reveals)
    assert all(residue.residue_id == {"blood": "residue.blood", "bone": "residue.bone_fragments",
        "corrosive": "residue.corrosive_demonic_blood", "dread": "residue.dread_blood"}[profile]
        for row in group.residue_reveals for residue in (row.after,))
