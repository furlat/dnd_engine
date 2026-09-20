"""Real saved injuries become fixed receiving geometry and seekable floor growth."""

from dataclasses import replace
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import pytest

from dnd.core.events import EventQueue
from game.action_media import sample_action_strip
from game.animation import body_elevation_steps
from game.animation_data import load_animation_data
from game.animation_types import ParticleMediaAsset
from game.choreography import bind_choreography
from game.particle_media import sample_particles
from game.player_facts import AttackFact
from game.player_projection import project_sequence
from game.player_reduction import decode_player_sequence, encode_player_sequence, reduce_lineage
from game.projection import Camera
from game.residue_media import landing_point, landing_template, sample_residue_reveals, target_cell
from game.surface_residue import ResidueSurfaceCache, geometric_residue_image
from tests.game.body_residue_scenarios import body_residue_history


@pytest.fixture(scope="module")
def data():
    pygame.init()
    pygame.display.set_mode((800, 600))
    yield load_animation_data()
    pygame.quit()


def bound_hits(data, **options):
    history = body_residue_history(**options)
    state, roots = decode_player_sequence(encode_player_sequence(project_sequence(history.views["walker"])))
    groups = []
    for root in roots:
        if isinstance(root.root.fact, AttackFact):
            groups.append(bind_choreography(state, root, data))
        state = reduce_lineage(state, root)
    return groups


def floor_image(group, elapsed, camera, cache):
    cue, = group.strips
    assert isinstance(cue.asset, ParticleMediaAsset)
    assert cue.release is not None
    position = cue.release.position
    residue, = group.after.tiles[position].residues
    return geometric_residue_image(cache, cue.asset, position, residue, camera, (1, 1, 1),
                                   sample_residue_reveals(group.residue_reveals, elapsed))


@pytest.mark.parametrize("weapon", ("weapon.dagger", "weapon.longsword", "weapon.mace"))
def test_air_keeps_historical_source_but_finishes_at_recorded_receiving_regions(data, weapon):
    group, = bound_hits(data, weapon=weapon, hits=1)
    cue, = group.strips
    asset, release = cue.asset, cue.release
    assert isinstance(asset, ParticleMediaAsset) and asset.region is not None
    assert release is not None and release.pattern is not None and release.regions
    family = asset.region.families[release.pattern]
    held = replace(cue, contact=replace(cue.contact, grid=(4.4, 3.2), body_lift_px=20))
    for r_index, region in enumerate(release.regions):
        template = landing_template(asset.region, region.ellipse)
        for particle in template.particles:
            goal = landing_point(region.ellipse, particle.target)
            identity = r_index * len(template.particles) + particle.id
            born = sample_action_strip(held, held.start_ms + particle.delay * family.delayScale * 1000 + .001)
            assert born is not None
            samples = {p.identity: p for p in sample_particles(born, asset)}
            if target_cell(goal) not in region.positions:
                assert identity not in samples
                continue
            assert samples[identity].grid == pytest.approx(held.contact.grid, abs=.0001)
            assert samples[identity].elevation == pytest.approx(body_elevation_steps(held.contact, data) + asset.region.sourceHeight, abs=.0001)
            landing = held.start_ms + (particle.delay * family.delayScale + particle.duration * family.durationScale) * 1000
            ending = sample_action_strip(held, landing - .001)
            assert ending is not None
            last = next(p for p in sample_particles(ending, asset) if p.identity == identity)
            assert last.grid == pytest.approx(goal, abs=.0001)
            assert last.elevation == pytest.approx(region.elevation_steps, abs=.0001)
    assert EventQueue.event_cursor() == 0


def test_seven_real_injuries_grow_then_freeze_floor_and_do_not_rebuild_idle_frames(data):
    groups = bound_hits(data, hits=7)
    camera = Camera(quadrant=0, zoom=1, viewport=(800, 600))
    cache = ResidueSurfaceCache()
    final_pixels = []
    for index, group in enumerate(groups):
        cue, = group.strips
        start = floor_image(group, cue.start_ms, camera, cache)
        final = floor_image(group, group.complete_ms, camera, cache)
        pixels = pygame.image.tobytes(final, "RGBA")
        if index == 0:
            assert not pygame.surfarray.array_alpha(start).any()
        else:
            assert pygame.image.tobytes(start, "RGBA") == final_pixels[-1]
        if index < 5:
            assert group.residue_reveals
            assert pixels != pygame.image.tobytes(start, "RGBA")
        else:
            assert not group.residue_reveals
        final_pixels.append(pixels)
        # Seeking backward leaves the same footprint; idle reads reuse the surface.
        assert pygame.image.tobytes(floor_image(group, cue.start_ms, camera, cache), "RGBA") == pygame.image.tobytes(start, "RGBA")
        builds = cache.rebuilds
        assert floor_image(group, group.complete_ms, camera, cache) is final
        assert cache.rebuilds == builds
    assert final_pixels[4] == final_pixels[5] == final_pixels[6]


@pytest.mark.parametrize("weapon", ("weapon.dagger", "weapon.longsword"))
def test_blood_spray_leaves_visible_neighboring_marks_and_accumulates(data, weapon):
    groups = bound_hits(data, weapon=weapon, hits=5, crossings=False)
    camera = Camera(quadrant=0, zoom=1, viewport=(800, 600))
    cache = ResidueSurfaceCache()
    coverage = []
    for group in (groups[0], groups[-1]):
        cue, = group.strips
        assert isinstance(cue.asset, ParticleMediaAsset) and cue.release is not None
        visible = {}
        for cell in {cell for region in cue.release.regions for cell in region.positions}:
            residue, = group.after.tiles[cell].residues
            surface = geometric_residue_image(cache, cue.asset, cell, residue, camera, (1, 1, 1))
            visible[cell] = int((pygame.surfarray.array_alpha(surface) > 0).sum())
        # Substantial marks beyond the victim, not just barely visible edge pixels.
        neighbors = {cell for cell, pixels in visible.items() if cell != cue.release.position and pixels >= 32}
        assert len(neighbors) >= 2, visible
        coverage.append(sum(visible.values()))
    assert coverage[1] > coverage[0] * 1.5
    assert EventQueue.event_cursor() == 0


def test_floor_appears_at_particle_arrival_and_critical_leaves_identical_geometry(data):
    ordinary, = bound_hits(data, hits=1)
    critical, = bound_hits(data, hits=1, critical=True)
    for group in (ordinary, critical):
        cue, = group.strips
        assert isinstance(cue.asset, ParticleMediaAsset) and cue.asset.region is not None
        assert cue.release is not None and cue.release.pattern is not None
        family = cue.asset.region.families[cue.release.pattern]
        first = min(p.delay * family.delayScale + p.duration * family.durationScale
                    for region in cue.release.regions for p in landing_template(cue.asset.region, region.ellipse).particles)
        for quadrant in range(4):
            camera = Camera(quadrant=quadrant, zoom=1, viewport=(800, 600))
            cache = ResidueSurfaceCache()
            before = floor_image(group, cue.start_ms + first * 1000 - .1, camera, cache)
            assert not pygame.surfarray.array_alpha(before).any()
            settled = floor_image(group, group.complete_ms, camera, cache)
            assert pygame.surfarray.array_alpha(settled).any()
            reference = floor_image(ordinary, ordinary.complete_ms, camera, cache)
            assert pygame.image.tobytes(settled, "RGBA") == pygame.image.tobytes(reference, "RGBA")
    regular_cue, = ordinary.strips
    critical_cue, = critical.strips
    normal = sample_action_strip(regular_cue, regular_cue.start_ms + 200)
    fuller = sample_action_strip(critical_cue, critical_cue.start_ms + 200)
    assert normal is not None and fuller is not None
    assert isinstance(regular_cue.asset, ParticleMediaAsset) and isinstance(critical_cue.asset, ParticleMediaAsset)
    assert len(sample_particles(fuller, critical_cue.asset)) == 2 * len(sample_particles(normal, regular_cue.asset))
