"""Enclosing art keeps actors behind its near hardware, independently of UUID order."""

from dataclasses import replace
from uuid import UUID

import numpy as np
import pygame
import pytest

from game.animation import BodySample
from game.animation_data import load_animation_data, resolve_player_layers
from game.animation_draw import actor_draw_commands, load_actor_media
from game.animation_types import PropDepth
from game.app import draw_frame
from game.assets import SurfaceCache, load_catalog, prop_animation_frame
from game.combat import actor_contact
from game.draw_commands import DrawCommand
from game.fixture_depth import FixtureDepthSample, split_actor_fixtures
from game.player_projection import project_sequence
from game.player_reduction import decode_player_sequence, encode_player_sequence, reduce_lineage
from game.projection import Camera, camera_axis_vectors, camera_pose, project_screen
from game.world_animation import WorldTransition, WorldTransitionSample
from tests.game.mechanism_scenarios import mechanism_history


@pytest.fixture(scope="module")
def display():
    pygame.init()
    screen = pygame.display.set_mode((600, 450))
    yield screen
    pygame.quit()


@pytest.fixture(scope="module", params=("blade", "crusher"))
def scene(display, request):
    history = mechanism_history(program=request.param)
    state, roots = decode_player_sequence(encode_player_sequence(project_sequence(history.views["traveler"])))
    for root in roots:
        state = reduce_lineage(state, root)
        actor = next(row for row in state.actors.values() if row.name == "Traveler")
        if actor.normal_hp < 80:
            break
    assert actor.normal_hp < 80
    data, catalog = load_animation_data(), load_catalog()
    contact = actor_contact(state, actor, data)
    layers = resolve_player_layers(data, actor, rig_id=contact.rig_id)
    media = load_actor_media(data, ((contact, layers, ("TakeDamage",)),), all_facings=True)
    assert state.senses is not None
    identity, = [key for key, effect in state.senses.spatial_effects.items()
                 if effect.content_ref.content_id.endswith("swinging_blade" if request.param == "blade" else "crusher")]
    return state, data, catalog, SurfaceCache(catalog), contact, layers, media, identity


def render(display, scene, camera, contact, *, identity=None, height=0, frame=5, body=True):
    state, data, catalog, cache, _, layers, media, original = scene
    new = original if identity is None else identity
    state = replace(state, tiles={key: tile.model_copy(update={"elevation_steps": height}) for key, tile in state.tiles.items()},
        senses=replace(state.senses, spatial_effects={new if key == original else key: effect
                      for key, effect in state.senses.spatial_effects.items()}))
    commands = actor_draw_commands(data, BodySample(contact.actor_uuid, "TakeDamage", 2, contact.facing),
        contact, layers, media, camera) if body else ()
    transition = WorldTransitionSample(WorldTransition(new, "activation", None, None, 0),
                                        frame * 1000 / 12 + .01)
    draw_frame(display, state, catalog, cache, camera, 0, show_grid=False, show_debug=False,
               mouse_position=None, extra_commands=commands, world_transitions=(transition,))
    return pygame.surfarray.array3d(display), commands, transition


@pytest.mark.parametrize("quadrant", range(4))
@pytest.mark.parametrize("frame", (0, 5, 11))
def test_real_hurt_body_and_arch_ignore_identity_order(display, scene, quadrant, frame):
    contact = scene[4]
    camera = Camera(quadrant=quadrant, zoom=.75, viewport=display.get_size()).with_focus(contact.grid)
    first, _, _ = render(display, scene, camera, contact, identity=UUID(int=0), frame=frame)
    last, _, _ = render(display, scene, camera, contact, identity=UUID(int=(1 << 128) - 1), frame=frame)
    np.testing.assert_array_equal(first, last)
    if frame == 5:
        render(display, scene, camera, contact, identity=UUID(int=0), frame=11)
        sought, _, _ = render(display, scene, camera, contact, identity=UUID(int=0), frame=5)
        np.testing.assert_array_equal(sought, first)


@pytest.mark.parametrize("quadrant", range(4))
@pytest.mark.parametrize("height", (0, 2))
def test_actual_hardware_hides_hurt_body_only_on_its_far_side(display, scene, quadrant, height):
    state, _, catalog, cache, contact, _, _, identity = scene
    origin = contact.grid
    camera = Camera(quadrant=quadrant, zoom=1, viewport=display.get_size()).with_focus(origin, elevation_steps=height)
    north, east = camera_axis_vectors(quadrant)
    toward = (np.sign(east[1]), np.sign(north[1]))
    effect = state.senses.spatial_effects[identity]
    animation = catalog.spatial_effects[effect.content_ref.content_id]
    pose = camera_pose("east", quadrant)
    for offset in (-.8, 0, .8):
        current = replace(contact, grid=tuple(origin[i] + offset * toward[i] for i in range(2)), elevation_steps=height)
        bare, _, transition = render(display, scene, camera, current, height=height, body=False)
        actual, commands, _ = render(display, scene, camera, current, height=height)
        actor = next(command for command in commands if command.evidence[6] == "actor")
        body_mask = pygame.Surface(display.get_size(), pygame.SRCALPHA)
        body_mask.blit(actor.surface, actor.destination)
        asset_id, _ = prop_animation_frame(animation, pose, effect.trap_state.value, transition)
        fixture_mask = pygame.Surface(display.get_size(), pygame.SRCALPHA)
        fixture_mask.blit(cache.scaled(asset_id, camera.zoom), cache.blit_position(asset_id, camera.zoom,
            project_screen(origin, camera, elevation_steps=height)))
        overlap = (pygame.surfarray.array_alpha(body_mask) > 250) & (pygame.surfarray.array_alpha(fixture_mask) > 250)
        assert np.any(overlap), (quadrant, offset)
        visible = np.any(actual != bare, axis=2) & overlap
        if offset < 0:
            assert not np.any(visible), "The whole fixture is physically nearer."
        elif offset > 0:
            assert np.all(visible[overlap]), "The actor is physically in front of the whole fixture."
        else:
            assert np.any(visible) and np.any(overlap & ~visible), "The center body belongs between the two supports."


@pytest.mark.parametrize("fixture_alpha", (128, 255))
@pytest.mark.parametrize("fixture_identity", ("a", "z"))
@pytest.mark.parametrize("peer_role", ("actor", "wall"))
def test_registered_depth_preserves_partial_alpha_and_leaves_vfx_intact(display, tmp_path, fixture_alpha, fixture_identity, peer_role):
    depth = pygame.Surface((2, 1), pygame.SRCALPHA)
    for x, value in enumerate((-.5, .5)):
        encoded = round((value + 1) / 2 * 65534) + 1
        depth.set_at((x, 0), (encoded % 256, encoded // 256, 0, 255))
    path = tmp_path / "depth.png"
    pygame.image.save(depth, path)
    fixture = pygame.Surface((2, 1), pygame.SRCALPHA)
    fixture.set_at((0, 0), (210, 20, 20, fixture_alpha))
    fixture.set_at((1, 0), (20, 210, 20, fixture_alpha))
    actor = pygame.Surface((2, 1), pygame.SRCALPHA)
    actor.fill((20, 20, 210, 128))
    smoke = pygame.Surface((2, 1), pygame.SRCALPHA)
    smoke.fill((230, 230, 230, 32))
    key = lambda identity, y=0: (100, y, 0., 504, (identity,))
    commands = [DrawCommand(key(fixture_identity), fixture, (0, 0), 0, (0, 0, 0, 0, 0, 0, "spatial_effect")),
        DrawCommand(key("m"), actor, (0, 0), 0, (0, 0, 0, 0, 0, 0, peer_role)),
        DrawCommand(key("smoke", 2), smoke, (0, 0), 0, (0, 0, 0, 0, 0, 0, "projectile"))]
    registration = PropDepth("depth", (2, 1), {"e": 0}, (-1, 1), {"e": 1})
    parts = split_actor_fixtures(commands, [FixtureDepthSample(0, path, registration, "e", 0, (2, 1), (0, 0, 2, 1), 1)])
    actual = pygame.Surface((2, 1))
    actual.fill((30, 30, 30))
    for command in sorted(parts, key=lambda row: row.key):
        actual.blit(command.surface, command.destination)
    expected = pygame.Surface((2, 1))
    expected.fill((30, 30, 30))
    expected.blit(fixture, (0, 0), (0, 0, 1, 1))
    expected.blit(actor, (0, 0))
    expected.blit(fixture, (1, 0), (1, 0, 1, 1))
    expected.blit(smoke, (0, 0))
    np.testing.assert_array_equal(pygame.surfarray.array3d(actual), pygame.surfarray.array3d(expected))
    assert commands[1] in parts and commands[2] in parts
    assert actor.get_at((0, 0)).a == 128 and fixture.get_at((0, 0)).a == fixture_alpha
