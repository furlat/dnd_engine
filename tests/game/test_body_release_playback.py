"""Recorded injuries drive one-shot Studio strips and persistent floor marks."""

from dataclasses import replace
import os
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import pytest

from game.animation_data import load_animation_data
from game.animation_draw import action_media_draw_commands, load_action_strip_media
from game.animation import body_elevation_steps
from game.animation_types import ParticleMediaAsset
from game.particle_media import sample_particles
from game.attack import BoundAttack
from game.assets import SurfaceCache, load_catalog
from game.app import draw_frame
from game.choreography import bind_choreography, sample_choreography
from game.motion import bind_motion, sample_motion
from game.player_facts import AttackFact, DamageFact
from game.player_projection import project_sequence
from game.player_reduction import decode_player_sequence, encode_player_sequence, reduce_lineage
from game.projection import Camera
from tests.game.body_residue_scenarios import body_residue_history, hidden_residue_history
from tests.game.dread_residue_scenarios import dread_residue_history
from tests.game.player_helpers import player_history
from tests.game.scenarios import attack_history


@pytest.fixture(scope="module")
def rendering():
    pygame.init()
    screen = pygame.display.set_mode((800, 600))
    yield screen, load_animation_data(rig_files=tuple(sorted(Path("game/data/rigs").glob("*.json")))), load_catalog()
    pygame.quit()


@pytest.fixture(scope="module", params=("blood", "bone", "corrosive"))
def history(request):
    captured = body_residue_history(profile=request.param)
    return decode_player_sequence(encode_player_sequence(project_sequence(captured.views["walker"])))


def test_each_received_injury_plays_one_strip_at_contact_and_retains_one_stain(history, rendering):
    _, data, _ = rendering
    state, roots = history
    releases = []
    residue_uuid = None
    for root in roots:
        if not isinstance(root.root.fact, AttackFact):
            state = reduce_lineage(state, root)
            continue
        packets = [node for node in root.events if isinstance(node.fact, DamageFact)
                   and node.fact.body_release is not None]
        group = bind_choreography(state, root, data)
        assert not group.gaps
        assert len(packets) == len(group.strips) == 1
        cue, = group.strips
        attack, = group.nodes
        assert isinstance(attack.bound, BoundAttack)
        assert cue.event_uuid == packets[0].uuid
        assert cue.start_ms == attack.start_ms + attack.bound.timeline.contact_ms
        assert not sample_choreography(group, cue.start_ms - 1).strips
        first, = sample_choreography(group, cue.start_ms).strips
        middle, = sample_choreography(group, cue.start_ms + 5.5 * 1000 / cue.track.fps).strips
        assert first.frame == 0 and middle.frame == 5
        assert not sample_choreography(group, cue.end_ms).strips
        assert sample_choreography(group, cue.start_ms).strips == (first,)
        state = reduce_lineage(state, root)
        residue, = state.tiles[(5, 3)].residues
        residue_uuid = residue_uuid or residue.condition_uuid
        assert residue.condition_uuid == residue_uuid
        releases.append(cue.event_uuid)
    assert len(releases) == 2 and releases[0] != releases[1]


def test_body_strips_share_the_historical_body_anchor_in_all_cameras(history, rendering):
    _, data, _ = rendering
    state, roots = history
    root = next(root for root in roots if isinstance(root.root.fact, AttackFact))
    original = bind_choreography(state, root, data)
    cue, = original.strips
    # A movement reaction owns a visual contact between legal cells, possibly
    # lifted above support. This presentation override never changes the input.
    held = replace(cue.contact, grid=(4.4, 3.2), elevation_steps=1, body_lift_px=20)
    group = bind_choreography(state, root, data, contacts={held.actor_uuid: held})
    placed, = group.strips
    assert placed.contact == held
    sample, = sample_choreography(group, placed.start_ms + 100).strips
    pixels = load_action_strip_media(group.strips)
    assert isinstance(placed.asset, ParticleMediaAsset)
    particles = sample_particles(sample, placed.asset)
    assert particles
    # The held source changes the early trajectory, never the native receiving regions.
    assert placed.release == cue.release
    born = sample_choreography(group, placed.start_ms + 20).strips[0]
    early = sample_particles(born, placed.asset)
    assert early and all(abs(p.grid[0] - held.grid[0]) < .1 for p in early)
    assert all(p.elevation > body_elevation_steps(held, data) for p in early)
    for quadrant in range(4):
        camera = Camera(quadrant=quadrant, zoom=1, viewport=(800, 600)).with_focus(held.grid)
        commands = action_media_draw_commands(sample, pixels, camera)
        assert len(commands) == len(particles)
        assert all(row.surface.get_bounding_rect().width > 0 for row in commands)


@pytest.mark.parametrize("first_sight", (False, True))
def test_hidden_or_old_injury_never_replays_a_burst_for_the_witness(first_sight, rendering):
    _, data, _ = rendering
    captured = hidden_residue_history(first_sight=first_sight)
    state, roots = decode_player_sequence(encode_player_sequence(project_sequence(captured.views["witness"])))
    for root in roots:
        assert not bind_choreography(state, root, data).strips
        state = reduce_lineage(state, root)
    assert state.tiles[(5, 3)].residues


@pytest.mark.parametrize("maximum_hp", (80, 4))
def test_real_opportunity_injury_keeps_its_midstep_release_contact(maximum_hp, rendering):
    _, data, _ = rendering
    captured = attack_history("weapon.longsword", 5, opportunity=True, whole_movement=True,
                              maximum_hp=maximum_hp, bloodied=True)
    before, (root,) = player_history(captured, role="hero")
    motion = bind_motion(before, root, data)
    assert motion is not None
    reaction, = motion.reactions
    strip, = reaction.choreography.strips
    assert strip.contact.grid == reaction.contact.grid != motion.actor.grid
    at = reaction.start_ms + strip.start_ms + 100
    frame = sample_motion(motion, data, at)
    assert frame.contact is not None and frame.reaction_sample is not None
    drawn, = frame.reaction_sample.strips
    assert drawn.cue.contact.grid == frame.contact.grid
    injury, = [node.fact for node in root.events if isinstance(node.fact, DamageFact)
               and node.fact.body_release is not None]
    assert injury.body_release is not None
    assert injury.body_release.position != strip.contact.grid


def test_known_bone_and_demonic_floor_memberships_draw_the_delivered_profiles(rendering):
    screen, _, catalog = rendering
    captures = (body_residue_history(mixed=True), body_residue_history(profile="corrosive"),
                dread_residue_history(entry="walk"))
    for captured in captures:
        view = next(iter(captured.views.values()))
        state, roots = decode_player_sequence(encode_player_sequence(project_sequence(view)))
        for root in roots:
            state = reduce_lineage(state, root)
        expected = {r.residue_id for tile in state.tiles.values() for r in tile.residues}
        assert expected
        for quadrant in range(4):
            camera = Camera(quadrant=quadrant, zoom=1, viewport=screen.get_size()).with_focus((6, 3))
            evidence = draw_frame(screen, state, catalog, SurfaceCache(catalog), camera, 0,
                show_grid=False, show_debug=False, mouse_position=None, collect_evidence=True)
            assert evidence is not None and evidence.matches
            drawn = {row[0] for row in evidence.actual_draws if len(row) > 6 and row[6] == "ground_residue"}
            assert drawn == {r.condition_uuid for tile in state.tiles.values() for r in tile.residues}
