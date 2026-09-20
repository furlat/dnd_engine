"""Approved droplet motion stays seekable and shares world painter ordering."""

from dataclasses import replace
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import pytest

from game.action_media import bind_action_strips, sample_action_strip
from game.animation_data import load_animation_data
from game.animation_draw import action_media_draw_commands
from game.animation_types import ParticleMediaAsset
from game.choreography import bind_choreography
from game.particle_media import sample_particles
from game.player_facts import AttackFact
from game.player_projection import project_sequence
from game.player_reduction import decode_player_sequence, encode_player_sequence
from game.projection import Camera, painter_key
from tests.game.body_residue_scenarios import body_residue_history


@pytest.fixture(scope="module")
def injury():
    pygame.init()
    pygame.display.set_mode((800, 600))
    data = load_animation_data()
    state, roots = decode_player_sequence(encode_player_sequence(
        project_sequence(body_residue_history().views["walker"])))
    root = next(root for root in roots if isinstance(root.root.fact, AttackFact))
    existing, = bind_choreography(state, root, data).strips
    track = existing.track.model_copy(update={"assetId": "particles.body.blood", "role": "particles"})
    cue, = bind_action_strips(existing.event_uuid, existing.contact, (track,), data,
                             start_ms=existing.start_ms, direction=existing.direction)
    yield cue
    pygame.quit()


def test_approved_particles_spawn_and_land_once_and_seek_without_simulation(injury):
    asset = injury.asset
    assert isinstance(asset, ParticleMediaAsset)
    for particle in asset.particles:
        born = injury.start_ms + particle.delay * 1000 + .001
        at_birth = sample_action_strip(injury, born)
        assert at_birth is not None
        assert particle.id in {row.identity for row in sample_particles(at_birth, asset)}
        landed = sample_action_strip(injury, injury.start_ms + (particle.delay + particle.life) * 1000 + .001)
        assert landed is not None
        assert particle.id not in {row.identity for row in sample_particles(landed, asset)}
        assert sample_action_strip(injury, born) == at_birth
    assert sample_action_strip(injury, injury.start_ms - 1) is None
    assert sample_action_strip(injury, injury.end_ms) is None


def test_strike_rotation_and_historical_contact_change_world_samples_before_projection(injury):
    asset = injury.asset
    assert isinstance(asset, ParticleMediaAsset)
    assert injury.direction == (1, 0)  # Real attacker (4,3) -> defender (5,3).
    at = injury.start_ms + 250
    initial = sample_action_strip(injury, at)
    assert initial is not None
    original = sample_particles(initial, asset)
    held = replace(injury.contact, grid=(8.4, 2.2), elevation_steps=1, body_lift_px=32)
    rotated = sample_action_strip(replace(injury, contact=held, direction=(0, 1)), at)
    assert rotated is not None
    moved = sample_particles(rotated, asset)
    assert len(original) == len(moved) > 1
    for first, second in zip(original, moved):
        assert first.identity == second.identity
        assert second.grid == pytest.approx((held.grid[0] - (first.grid[1] - injury.contact.grid[1]),
                                              held.grid[1] + (first.grid[0] - injury.contact.grid[0])))
        # Root rig pixels are doubled into the game's 128px-wide tile scale.
        assert second.elevation - first.elevation == pytest.approx(2)


def test_particles_keep_individual_ground_depth_in_all_four_views(injury):
    asset = injury.asset
    assert isinstance(asset, ParticleMediaAsset)
    sample = sample_action_strip(injury, injury.start_ms + 250)
    assert sample is not None
    particles = sample_particles(sample, asset)
    assert len(particles) > 1
    for quadrant in range(4):
        camera = Camera(quadrant=quadrant, zoom=1, viewport=(800, 600)).with_focus(injury.contact.grid)
        commands = action_media_draw_commands(sample, {}, camera)
        assert len(commands) == len(particles)
        for command, particle in zip(commands, particles):
            assert command.key == painter_key(particle.grid, elevation_steps=particle.elevation,
                quadrant=quadrant, role="action_strip", identity=(str(injury.event_uuid), str(particle.identity)))
            assert command.surface.get_bounding_rect().width > 0
        assert len({command.key[1] for command in commands}) > 1
        # Drawing another camera and then returning does not advance the effect.
        repeated = action_media_draw_commands(sample, {}, camera)
        assert [row.destination for row in commands] == [row.destination for row in repeated]
        assert all(pygame.image.tobytes(a.surface, "RGBA") == pygame.image.tobytes(b.surface, "RGBA")
                   for a, b in zip(commands, repeated))
