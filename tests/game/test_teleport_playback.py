"""Real teleports replay from paired player bytes at the authored release."""

from uuid import UUID

import pygame
import pytest

from game.animation_data import load_animation_data
from game.choreography import bind_choreography, sample_choreography
from game.choreography_draw import load_choreography_media
from game.combat import actor_contact, actor_is_visible
from game.playback_frame import sample_playback_frame
from game.player_facts import SpatialFact, SpellFact
from game.player_reduction import reduce_lineage, stage_lineage
from game.projection import Camera
from game.scene import load_scene_media, scene_actors
from tests.game.player_helpers import player_history
from tests.game.teleport_scenarios import teleport_history


@pytest.fixture(scope="module")
def data():
    return load_animation_data()


@pytest.fixture(scope="module")
def graphics():
    pygame.init()
    pygame.display.set_mode((640, 480))
    yield pygame.font.Font(None, 24)
    pygame.quit()


def selected(history, role):
    before, roots = player_history(history, role=role)
    for root in roots:
        if isinstance(root.root.fact, SpellFact) and root.root.fact.behavior_id == "spell.misty_step":
            return before, root
        before = reduce_lineage(before, root)
    raise AssertionError(f"No disclosed Misty Step for {role}")


@pytest.mark.parametrize("battlefield,origin,destination,witness", (
    ("battlefield.open_floor_bright", (3, 3), (7, 3), (4, 3)),
    ("battlefield.open_floor_bright", (7, 3), (3, 3), (6, 3)),
    ("battlefield.visual_vertical_seam", (33, 28), (35, 26), (32, 28)),
    ("battlefield.visual_vertical_seam", (13, 20), (14, 20), (12, 20)),
    ("battlefield.visual_vertical_seam", (14, 20), (13, 20), (15, 20)),
))
def test_cast_relocates_once_at_release_with_received_destination_height(data, battlefield, origin, destination, witness):
    history = teleport_history(battlefield_id=battlefield, caster_position=origin,
        destination=destination, witness_position=witness)
    for role in ("caster", "witness"):
        before, root = selected(history, role)
        group = bind_choreography(before, root, data)
        cue, = group.body_actions
        assert not group.gaps
        actor_id = UUID(cue.contact.actor_uuid)
        latest = reduce_lineage(before, root)
        pending = sample_choreography(group, cue.effect_ms - 1)
        reached = sample_choreography(group, cue.effect_ms)
        assert pending.contacts[0].grid == origin
        assert reached.contacts[0].grid == destination
        expected = actor_contact(latest, latest.actors[actor_id], data)
        assert reached.contacts[0].elevation_steps == expected.elevation_steps
        assert reached.bodies[0].frame == 8, "relocation must continue the same cast, not restart it"
        assert not reached.complete
        assert actor_contact(pending.displayed, pending.displayed.actors[actor_id], data).grid == origin
        assert actor_contact(reached.displayed, reached.displayed.actors[actor_id], data).grid == destination
        assert sample_choreography(group, cue.effect_ms - 1) == pending
        assert sample_choreography(group, cue.effect_ms) == reached
        for elapsed in (0, 200, cue.effect_ms - 1, cue.effect_ms, 900, group.complete_ms - 1):
            sample = sample_choreography(group, elapsed)
            assert sample.contacts[0].grid == (origin if elapsed < cue.effect_ms else destination)


@pytest.mark.parametrize("origin,destination,sees_before,sees_after", (
    ((8, 7), (8, 10), True, False),
    ((8, 10), (8, 7), False, True),
))
def test_doorway_witness_sees_only_authorized_endpoint_at_release(data, origin, destination, sees_before, sees_after):
    history = teleport_history(battlefield_id="battlefield.visibility_doorway_open",
        caster_position=origin, destination=destination, witness_position=(5, 7))
    before, root = selected(history, "witness")
    group = bind_choreography(before, root, data)
    cue, = group.body_actions
    assert not group.gaps
    identity = UUID(cue.contact.actor_uuid)
    for elapsed, visible in ((cue.effect_ms - 1, sees_before), (cue.effect_ms, sees_after)):
        sample = sample_choreography(group, elapsed)
        actor = sample.displayed.actors.get(identity)
        assert (actor is not None and actor_is_visible(sample.displayed, actor)) == visible
        if visible:
            assert actor is not None
            expected = origin if elapsed < cue.effect_ms else destination
            assert actor_contact(sample.displayed, actor, data).grid == expected
            assert sample.contacts[0].grid == expected
    if not sees_after:
        assert not sample_choreography(group, cue.effect_ms).contacts
    fact = root.root.fact
    assert isinstance(fact, SpellFact)
    if not sees_before:
        assert fact.source_position is None, "arrival does not disclose the hidden departure coordinate"
    endpoint = origin if sees_before else destination
    assert all(node.fact.position == endpoint for node in root.events
               if isinstance(node.fact, SpatialFact) and node.fact.entity_uuid == identity)


@pytest.mark.parametrize("origin,destination,role", (
    ((8, 7), (8, 10), "caster"),
    ((8, 7), (8, 10), "witness"),
    ((8, 10), (8, 7), "witness"),
))
def test_four_cameras_show_release_and_settle_without_an_old_position(data, graphics, origin, destination, role):
    history = teleport_history(battlefield_id="battlefield.visibility_doorway_open",
        caster_position=origin, destination=destination, witness_position=(5, 7))
    before, root = selected(history, role)
    group = bind_choreography(before, root, data)
    cue, = group.body_actions
    identity = UUID(cue.contact.actor_uuid)
    rows = {}
    media = load_scene_media(scene_actors(stage_lineage(before, root), data, {}), data, body_rows=rows)
    choreography_media = load_choreography_media(group, body_rows=rows)
    for quadrant in range(4):
        camera = Camera(quadrant=quadrant, viewport=(640, 480)).with_focus((7, 8))
        positions = {}
        for elapsed in (cue.effect_ms - 1, cue.effect_ms, group.complete_ms):
            frame = sample_playback_frame(before, group.after, data, elapsed, elapsed, camera, {}, media,
                graphics, graphics, choreography=group, choreography_media=choreography_media, positions=positions)
            expected = origin if elapsed < cue.effect_ms else destination
            visible = role == "caster" or expected == (8, 7)
            assert any(command[4][6] == "actor" and str(command[4][0]) == str(identity)
                       for command in frame.commands) == visible
            actor = next((actor for actor in frame.actors if actor.contact.actor_uuid == str(identity)), None)
            assert (actor is not None) == visible
            if actor is not None:
                assert actor.contact.grid == expected
            positions = frame.positions
        idle = sample_playback_frame(group.after, None, data, 0, 1500, camera, {}, media,
            graphics, graphics, positions=positions)
        actor = next((actor for actor in idle.actors if actor.contact.actor_uuid == str(identity)), None)
        if actor is not None:
            assert actor.contact.grid == destination
