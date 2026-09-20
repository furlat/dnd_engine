"""Real trap history drives bloodied shaft pixels on the shared contact clock."""

from dataclasses import replace
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import numpy as np
import pygame
import pytest

from dnd.core.base_object import PASSIVE_EVENT_REPLAY
from dnd.core.events import EventQueue
from dnd.entity import Entity
from dnd.types.traps import TrapState
from game.animation_data import load_animation_data
from game.app import draw_frame
from game.assets import SurfaceCache, load_catalog
from game.attack import BoundAttack
from game.choreography import bind_choreography, sample_choreography
from game.motion import bind_motion, sample_motion
from game.player_facts import ActionFact, AttackFact, DamageFact, MovementFact
from game.player_projection import project_sequence
from game.player_reduction import decode_player_sequence, encode_player_sequence, reduce_lineage
from game.projection import Camera, camera_pose, project_screen
from game.replay import RecordedSequence
from game.world_animation import sample_world_transitions
from tests.game.body_residue_scenarios import body_residue_history, hidden_residue_history
from tests.game.trap_scenarios import trap_history


@pytest.fixture(scope="module", params=("plain", "poison-damage"))
def history(request):
    return trap_history(payload=request.param, bloodied=True), request.param


@pytest.fixture(scope="module")
def rendering():
    pygame.init()
    screen = pygame.display.set_mode((800, 600))
    catalog = load_catalog()
    clean_catalog = replace(catalog, spatial_residue_overlays={})
    yield screen, catalog, SurfaceCache(catalog), load_animation_data(), clean_catalog, SurfaceCache(clean_catalog)
    pygame.quit()


def public_history(history, role):
    restored = RecordedSequence.model_validate_json(history.views[role].model_dump_json(), context=PASSIVE_EVENT_REPLAY)
    return decode_player_sequence(encode_player_sequence(project_sequence(restored)))


@pytest.mark.parametrize("first_sight", (False, True))
def test_known_blood_ground_renders_without_revealing_donor_or_hidden_spikes(rendering, first_sight):
    history = hidden_residue_history(first_sight=first_sight)
    before, roots = public_history(history, "witness")
    after = before
    for root in roots:
        after = reduce_lineage(after, root)
    donor = history.views["donor"].initialization.observer_uuid
    assert donor not in after.actors
    for quadrant in range(4):
        camera = Camera(quadrant=quadrant, zoom=1, viewport=(800, 600)).with_focus((5, 3))
        initial, _ = draw_world(before, camera, (), rendering)
        rows, _ = draw_world(after, camera, (), rendering)
        assert not any(len(row) > 6 and row[6] == "ground_residue" for row in initial)
        ground, = [row for row in rows if len(row) > 6 and row[6] == "ground_residue"]
        assert ground[1] == (5, 3)
        assert ground[2] == f"residue.blood.{camera_pose('east', quadrant)}"
        assert not any(len(row) > 6 and row[6] in ("spatial_effect", "residue_overlay") for row in rows)


def selected(history, role, kind, occurrence=0):
    state, roots = public_history(history, role)
    for root in roots:
        if isinstance(root.root.fact, kind):
            if occurrence == 0:
                return state, root
            occurrence -= 1
        state = reduce_lineage(state, root)
    raise AssertionError("Expected action is absent from the native narrative")


def draw_world(state, camera, changes, rendering, *, clean=False):
    screen, catalog, cache, _, clean_catalog, clean_cache = rendering
    evidence = draw_frame(screen, state, clean_catalog if clean else catalog,
        clean_cache if clean else cache, camera, 0, show_grid=False, show_debug=False,
        mouse_position=None, collect_evidence=True, world_transitions=changes)
    assert evidence is not None and evidence.matches
    return evidence.actual_draws, pygame.surfarray.array3d(screen)


def assert_shaft_raster(state, camera, changes, rendering, *, frame, coated):
    rows, pixels = draw_world(state, camera, changes, rendering)
    base, = (row for row in rows if len(row) > 6 and row[6] == "spatial_effect")
    pose = camera_pose("east", camera.quadrant)
    assert base[2] == f"spikes.{'coated.' if coated else ''}{pose}.{frame}"
    overlays = [row for row in rows if len(row) > 6 and row[6] == "residue_overlay"]
    _, clean_pixels = draw_world(state, camera, changes, rendering, clean=True)
    if frame == 0:
        assert overlays == []
        assert np.array_equal(pixels, clean_pixels), "Lowered shafts must hide their blood pixels"
        return
    overlay, = overlays
    assert overlay[2] == f"spikes.blood.{pose}.{frame}" and overlay[7] == base[7] == frame
    assert rows.index(base) < rows.index(overlay)
    screen, _, cache, _, _, _ = rendering
    expected = pygame.Surface(screen.get_size()).convert()
    pygame.surfarray.blit_array(expected, clean_pixels)
    contact = project_screen((5, 3), camera, elevation_steps=state.tiles[(5, 3)].elevation_steps)
    assert base[5] == overlay[5] == "light.bright"
    expected.blit(cache.scaled(overlay[2], camera.zoom), cache.blit_position(overlay[2], camera.zoom, contact))
    composed = pygame.surfarray.array3d(expected)
    changed = np.any(pixels != clean_pixels, axis=2)
    assert np.count_nonzero(changed) > 0, "A recorded Bloodied tile must produce actual blood pixels"
    assert np.array_equal(pixels[changed], composed[changed])
    support = np.any(composed != clean_pixels, axis=2)
    assert np.array_equal(pixels[~support], clean_pixels[~support]), "The blood overlay must retain uncovered coating pixels"
    if coated:
        plain = cache.scaled(f"spikes.{pose}.{frame}", camera.zoom)
        coated_surface = cache.scaled(base[2], camera.zoom)
        coating = pygame.surfarray.array3d(coated_surface)
        mask = (np.any(coating != pygame.surfarray.array3d(plain), axis=2)
                & (pygame.surfarray.array_alpha(coated_surface) == 255)
                & (pygame.surfarray.array_alpha(cache.scaled(overlay[2], camera.zoom)) == 0))
        x, y = np.nonzero(mask)
        left, top = cache.blit_position(base[2], camera.zoom, contact)
        assert x.size > 0 and np.any(np.all(pixels[x + left, y + top] == coating[x, y], axis=1)), (
            "The actual bloodied frame must retain visible pixels from the coating palette")


@pytest.mark.parametrize("role", ("walker", "operator"))
def test_full_saved_story_keeps_one_bloodied_tile_through_lowering_and_occupied_raise(history, role):
    captured, payload = history
    before, roots = public_history(captured, role)
    walker = captured.views["walker"].initialization.observer_uuid
    assert before.senses is not None and not before.senses.spatial_effects
    assert before.tiles[(5, 3)].residues == ()
    state = before
    condition_uuid = None
    actions = []
    releases = []
    for root in roots:
        old_hp = state.actors[walker].normal_hp
        state = reduce_lineage(state, root)
        releases.extend(node.fact.body_release for node in root.events
                        if isinstance(node.fact, DamageFact) and node.fact.body_release is not None)
        if not isinstance(root.root.fact, (MovementFact, ActionFact)):
            continue
        residue, = state.tiles[(5, 3)].residues
        assert residue.residue_id == "residue.blood"
        condition_uuid = condition_uuid or residue.condition_uuid
        assert residue.condition_uuid == condition_uuid
        assert state.senses is not None
        trap, = state.senses.spatial_effects.values()
        actions.append((trap.trap_state, old_hp - state.actors[walker].normal_hp))
    hit = 6 if payload == "poison-damage" else 4
    assert actions == [(TrapState.ACTIVATED, hit), (TrapState.ACTIVATED, 0),
        (TrapState.ACTIVATED, hit), (TrapState.ACTIVATED, 0), (TrapState.DEACTIVATED, 0),
        (TrapState.DEACTIVATED, 0), (TrapState.DEACTIVATED, 0), (TrapState.DEACTIVATED, 0),
        (TrapState.ACTIVATED, hit), (TrapState.ACTIVATED, 0)]
    assert len(releases) == 3 and all(row.release_id == "body.blood" for row in releases)
    assert EventQueue.event_cursor() == 0 and not Entity.get_all_entities()


@pytest.mark.parametrize("role", ("walker", "operator"))
def test_bloodied_spike_pixels_follow_contact_and_existing_deployment_frames(history, rendering, role):
    captured, payload = history
    screen, _, _, data, _, _ = rendering
    before, root = selected(captured, role, MovementFact)
    motion = bind_motion(before, root, data)
    assert motion is not None
    reaction, = motion.reactions
    contact_ms = reaction.start_ms + reaction.choreography.damage[0].timing.start_ms
    pending = sample_motion(motion, data, contact_ms - 1)
    impact = sample_motion(motion, data, contact_ms)
    assert pending.displayed is not None and pending.displayed.tiles[(5, 3)].residues == ()
    assert impact.displayed is not None and len(impact.displayed.tiles[(5, 3)].residues) == 1
    for quadrant in range(4):
        camera = Camera(quadrant=quadrant, viewport=screen.get_size()).with_focus((5, 3))
        rows, _ = draw_world(pending.displayed, camera, (), rendering)
        assert not any(len(row) > 6 and row[6] in ("spatial_effect", "residue_overlay") for row in rows)
        for offset, frame in ((0, 0), (125, 3), (300, 6)):
            at = contact_ms + offset
            sampled = sample_motion(motion, data, at)
            assert sampled.displayed is not None
            assert_shaft_raster(sampled.displayed, camera,
                sample_world_transitions(motion.world_transitions, at), rendering,
                frame=frame, coated=payload != "plain")
        assert sample_motion(motion, data, contact_ms - 1).displayed == pending.displayed
    for occurrence in (0, 1):
        before, root = selected(captured, role, ActionFact, occurrence)
        group = bind_choreography(before, root, data)
        cue, = group.body_actions
        residue, = before.tiles[(5, 3)].residues
        # Reactivating occupied spikes causes another real injury. Lowering
        # keeps the amount; raising adds blood without replacing the condition.
        expected = residue.model_copy(update={"amount": residue.amount + occurrence})
        assert sample_choreography(group, cue.effect_ms - 1).displayed.tiles[(5, 3)].residues == (residue,)
        for quadrant in range(4):
            camera = Camera(quadrant=quadrant, viewport=screen.get_size()).with_focus((5, 3))
            for offset, lower_frame in ((0, 6), (125, 3), (300, 0), (125, 3)):
                at = cue.effect_ms + offset
                sampled = sample_choreography(group, at)
                assert sampled.displayed.tiles[(5, 3)].residues == (expected,)
                assert_shaft_raster(sampled.displayed, camera,
                    sample_world_transitions(group.world_transitions, at), rendering,
                    frame=6 - lower_frame if occurrence else lower_frame, coated=payload != "plain")
    assert EventQueue.event_cursor() == 0 and not Entity.get_all_entities()


def test_attack_deposition_uses_recorded_injury_contact(rendering):
    history = body_residue_history()
    before, root = selected(history, "walker", AttackFact)
    data = rendering[3]
    group = bind_choreography(before, root, data)
    action, = group.nodes
    assert isinstance(action.bound, BoundAttack) and action.bound.timeline.damage_timing is not None
    contact_ms = action.start_ms + action.bound.timeline.damage_timing.start_ms
    pending = sample_choreography(group, contact_ms - 1)
    hit = sample_choreography(group, contact_ms)
    assert pending.displayed.tiles[(5, 3)].residues == ()
    residue, = hit.displayed.tiles[(5, 3)].residues
    assert residue.residue_id == "residue.blood"
    assert sample_choreography(group, contact_ms - 1) == pending
    assert EventQueue.event_cursor() == 0 and not Entity.get_all_entities()
