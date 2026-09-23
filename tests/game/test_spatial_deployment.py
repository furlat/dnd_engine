"""A witnessed field creation owns one finite ground sequence, then its last frame."""

from dataclasses import replace
from pathlib import Path

import numpy as np
import pygame
import pytest

from dnd.core.events import EventQueue
from dnd.types.spatial_effects import SpatialEffectChangeOperation
from game.animation import CastSample
from game.animation_data import load_animation_data
from game.app import draw_frame
from game.assets import AssetSpec, SurfaceCache, load_catalog
from game.choreography import bind_choreography, sample_choreography
from game.combat import BoundCast
from game.draw_commands import DrawCommand
from game.player_facts import SpatialEffectStateFact, SpellFact
from game.player_projection import project_sequence
from game.player_reduction import decode_player_sequence, encode_player_sequence, reduce_lineage
from game.projection import Camera, TILE_HEIGHT, TILE_WIDTH, painter_key, project_screen
from game.world_animation import prop_animation, sample_world_transitions, world_transition_end
from tests.game.web_scenarios import web_history


@pytest.fixture(scope="module")
def captures():
    return {delivery: web_history(delivery=delivery) for delivery in ("mage", "cannon")}


@pytest.fixture(scope="module")
def data():
    return load_animation_data()


@pytest.mark.parametrize("delivery", ("mage", "cannon"))
@pytest.mark.parametrize("role", ("caster", "target"))
def test_saved_creation_starts_at_contact_and_does_not_replay_older_fields(captures, data, delivery, role):
    state, roots = decode_player_sequence(encode_player_sequence(project_sequence(captures[delivery].views[role])))
    cast_count = 0
    for root in roots:
        if isinstance(root.root.fact, SpellFact) and root.root.fact.behavior_id == "spell.web":
            group = bind_choreography(state, root, data)
            assert not group.gaps
            created, = (event.fact for event in root.events if isinstance(event.fact, SpatialEffectStateFact)
                        and event.fact.operation is SpatialEffectChangeOperation.CREATED)
            change, = (change for change in group.world_transitions if change.field == "creation")
            assert change.identity == created.spatial_effect_uuid
            assert state.senses is not None and change.identity not in state.senses.spatial_effects
            node, = (node for node in group.nodes if isinstance(node.bound, BoundCast))
            assert isinstance(node.bound, BoundCast) and node.bound.timeline.ground_delivery is not None
            assert change.start_ms == node.start_ms + node.bound.timeline.ground_delivery.travel_end_ms
            before = sample_choreography(group, change.start_ms - .001).displayed
            contact = sample_choreography(group, change.start_ms).displayed
            assert before.senses is not None and contact.senses is not None
            assert len(before.senses.spatial_effects) == cast_count
            assert len(contact.senses.spatial_effects) == cast_count + 1
            assert all(identity != change.identity for identity in before.senses.spatial_effects)
            assert any(condition.behavior_id == "condition.restrained"
                       for actor in contact.actors.values() for condition in actor.conditions)
            finished = world_transition_end(change, contact, data.world_animations)
            assert group.complete_ms >= finished > change.start_ms
            for elapsed in (change.start_ms + 1, finished, change.start_ms - .001, change.start_ms + 1):
                sample = sample_choreography(group, elapsed)
                assert not any(effect.phase == "impact" for clip in sample.clips
                    if isinstance(clip.sample, CastSample) for effect in clip.sample.projectiles)
            assert sample_choreography(group, change.start_ms + 1).displayed == contact
            cast_count += 1
        state = reduce_lineage(state, root)
    assert cast_count == (2 if delivery == "cannon" else 1)
    assert EventQueue.event_cursor() == 0


@pytest.mark.parametrize("quadrant", range(4))
def test_deployment_and_resting_field_share_clipped_ground_pixels_and_fractional_origin(
    captures, data, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, quadrant: int,
):
    state, roots = decode_player_sequence(encode_player_sequence(project_sequence(captures["mage"].views["caster"])))
    root = next(root for root in roots if isinstance(root.root.fact, SpellFact))
    catalog = load_catalog()
    width, height = round(TILE_WIDTH * 4), round(TILE_HEIGHT * 4)
    frames = tuple(f"test.field.{index}" for index in range(3))
    binding = prop_animation({"frames_by_pose": {pose: frames for pose in ("e", "n", "w", "s")},
        "fps": 10, "state_frames": {}, "default_frame": 2, "creation_start_frame": 0,
        "placement": "area", "origin_offset": [-.5, -.5]})
    data = replace(data, world_animations={**data.world_animations, "spatial_effect.spell.web": binding})
    group = bind_choreography(state, root, data)
    change, = (change for change in group.world_transitions if change.field == "creation")
    state = sample_choreography(group, change.start_ms).displayed
    assert state.senses is not None
    effect = state.senses.spatial_effects[change.identity]
    # A partial subjective footprint on two supports exercises the ordinary
    # renderer boundary; unreceived cells must not gain deployment pixels.
    positions = tuple(position for position in effect.positions if position[0] < 9)
    effect = effect.model_copy(update={"positions": positions})
    state = replace(state, senses=replace(state.senses, spatial_effects={change.identity: effect}),
        tiles={position: tile.model_copy(update={"elevation_steps": 1 if position[1] < 5 else 0})
               for position, tile in state.tiles.items()})
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    pygame.init()
    try:
        screen = pygame.display.set_mode((800, 600))
        resources = dict(catalog.resources)
        for index, identity in enumerate(frames):
            image = pygame.Surface((width, height), pygame.SRCALPHA)
            image.fill((50 + index * 70, 150, 200 - index * 60, 120))
            pygame.draw.line(image, (30, 250, 40, 160), (width // 2, 0), (width // 2, height), 4)
            path = tmp_path / f"field-{index}.png"
            pygame.image.save(image, path)
            resources[identity] = AssetSpec(identity, path, (width, height), (width / 2, height / 2), 1)
        catalog = replace(catalog, resources=resources, spatial_effects={"spatial_effect.spell.web": binding})
        cache = SurfaceCache(catalog)
        camera = Camera(quadrant=quadrant, viewport=screen.get_size()).with_focus((8.5, 4.5))
        actor_position = positions[len(positions) // 2]
        actor_height = state.tiles[actor_position].elevation_steps
        actor_point = tuple(round(value) for value in project_screen(actor_position, camera, elevation_steps=actor_height))
        body = pygame.Surface((20, 20))
        body.fill((250, 20, 90))
        actor = DrawCommand(painter_key(actor_position, elevation_steps=actor_height, quadrant=quadrant,
            role="actor", identity="test-body"), body, (actor_point[0] - 10, actor_point[1] - 10), 0,
            ("test-body", actor_position, "test.body", "current", None, "authored", "actor"))

        def render(snapshot, elapsed, *, active=True):
            transitions = sample_world_transitions((change,), elapsed) if active else ()
            evidence = draw_frame(screen, snapshot, catalog, cache, camera, 0,
                show_grid=False, show_debug=False, mouse_position=None, collect_evidence=True,
                world_transitions=transitions, extra_commands=(actor,))
            assert evidence is not None and evidence.matches
            rows = tuple(row for row in evidence.actual_draws if len(row) > 6 and row[6] == "spatial_effect")
            return rows, pygame.surfarray.array3d(screen)

        assert state.senses is not None
        absent = replace(state, senses=replace(state.senses, spatial_effects={}))
        _, bare = render(absent, change.start_ms)
        allowed = pygame.Surface(screen.get_size())
        for position in positions:
            x, y = project_screen(position, camera, elevation_steps=state.tiles[position].elevation_steps)
            pygame.draw.polygon(allowed, "white", ((x, y - TILE_HEIGHT / 2), (x + TILE_WIDTH / 2, y),
                                                   (x, y + TILE_HEIGHT / 2), (x - TILE_WIDTH / 2, y)))
        permitted = pygame.surfarray.array3d(allowed)[:, :, 0] != 0
        saved = {}
        for delta, frame in ((0, 0), (100, 1), (200, 2), (100, 1)):
            rows, pixels = render(state, change.start_ms + delta)
            assert {row[1] for row in rows} == set(positions)
            assert len(rows) == len(positions), "Each cell has exactly one ground pass"
            assert all(row[7] == frame for row in rows)
            assert {(row[1], row[8]) for row in rows} == {(position, state.tiles[position].elevation_steps)
                                                         for position in positions}
            assert np.any(pixels != bare)
            assert not np.any(np.any(pixels != bare, axis=2) & ~permitted), "No pixels outside observed supports"
            assert tuple(pixels[actor_point]) == (250, 20, 90), "Ground deployment stays below actors"
            if frame in saved:
                assert np.array_equal(saved[frame], pixels), "Backward seek restores identical pixels"
            saved[frame] = pixels
        rows, resting = render(state, change.start_ms + 200, active=False)
        assert all(row[7] == 2 for row in rows)
        assert np.array_equal(saved[2], resting), "The final deployment frame is the resting field"
        # Acquisition without a witnessed native creation is already settled.
        _, acquired = render(state, 0, active=False)
        assert np.array_equal(resting, acquired)
        catalog = replace(catalog, spatial_effects={"spatial_effect.spell.web": replace(binding, origin_offset=(0, 0))})
        cache = SurfaceCache(catalog)
        _, without_offset = render(state, 0, active=False)
        assert not np.array_equal(resting, without_offset), "The authored fractional origin controls picture registration"
    finally:
        pygame.quit()
