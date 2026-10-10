"""Recorded creature presence owns finite reveal/retirement, never game state."""

import numpy as np
import pygame
import pytest

from game.animation_data import DATA_ROOT, load_animation_data
from game.animation_draw import actor_draw_commands
from game.body_effects import reveal_body
from game.body_presentation import sample_body_presentation
from game.choreography import bind_choreography
from game.choreography_draw import load_choreography_media
from game.condition_animation import condition_body_pose
from game.motion_media import choreography_motion_media
from dnd.player.recorded import project_sequence
from dnd.player.reduction import reduce_initialization, reduce_lineage
from game.scene_actors import scene_actors
from game.projection import Camera
from tests.game.test_summoning_presentation import summon_history


@pytest.fixture(scope="module")
def data():
    return load_animation_data(rig_files=tuple(DATA_ROOT.parent / "rigs" / name
        for name in ("greywolf.json", "demonbeast01.json")))


@pytest.mark.parametrize("family", ("animals", "fey", "fiend"))
@pytest.mark.parametrize("ending", ("dismiss", "defeat"))
def test_birth_and_terminal_body_follow_received_native_clocks(data, family, ending):
    history, identity, _ = summon_history(ending, family=family)
    for view in ("caster", "witness"):
        sequence = project_sequence(history.views[view])
        state = reduce_initialization(sequence.initialization)
        phases = []
        for root in sequence.lineages:
            contacts = {actor.contact.actor_uuid: actor.contact for actor in scene_actors(state, data, {})}
            group = bind_choreography(state, root, data, contacts=contacts)
            for cue in group.entity_lifecycle:
                phases.append(cue.phase)
                assert cue.actor.contact.actor_uuid == str(identity)
                def pose_at(age):
                    frame = sample_body_presentation(state, group.after, data, age, age, {}, choreography=group)
                    poses = [pose for pose in frame.poses if pose.body.actor_uuid == str(identity)]
                    assert len(poses) <= 1
                    return poses[0] if poses else None
                beginning = pose_at(cue.start_ms)
                assert beginning is not None
                assert beginning.coverage == (0 if cue.phase == "arrival" else 1)
                mid = pose_at(cue.start_ms + (562.5 if cue.phase == "arrival" else 437.5))
                assert mid is not None and mid.coverage == pytest.approx(.5)
                settled = pose_at(cue.body_end_ms)
                if cue.phase == "arrival":
                    assert settled is not None and settled.coverage == 1
                    assert group.after.actors[identity].present
                else:
                    assert settled is None and not group.after.actors[identity].present
                    if ending == "defeat":
                        assert beginning.body.clip == ("Death" if family == "fiend" else "Die")
                        assert all(cue.start_ms >= damage.timing.end_ms for damage in group.damage
                                   if damage.contact.actor_uuid == str(identity))
                assert pose_at(cue.start_ms) == beginning  # Backward seek never restarts a native action.
                media = [row.media for row in choreography_motion_media(group, data, 9000)
                         if row.media.event_uuid == cue.event_uuid]
                assert len(media) == 3
                assert all(row.position == cue.actor.contact.grid for row in media)
                assert all(row.end_ms > 9000 + cue.body_end_ms for row in media)
                assert all(row.native_pixels for row in media)
            state = reduce_lineage(state, root)
        assert phases == ["arrival", "departure"]


def test_fey_control_break_keeps_same_body_and_only_adds_finite_media(data):
    history, identity, _ = summon_history("control_loss")
    sequence = project_sequence(history.views["caster"])
    state = reduce_initialization(sequence.initialization)
    found = False
    for root in sequence.lineages:
        group = bind_choreography(state, root, data)
        for cue in group.entity_lifecycle:
            if cue.phase != "bond":
                continue
            found = True
            assert group.after.actors[identity].present
            assert group.after.actors[identity].normal_hp == state.actors[identity].normal_hp
            assert group.after.actors[identity].manifestation == state.actors[identity].manifestation
            assert group.after.actors[identity].faction != state.actors[identity].faction
            for age in (0, 187.5, 750):
                frame = sample_body_presentation(state, group.after, data, age, age, {}, choreography=group)
                pose, = (pose for pose in frame.poses if pose.body.actor_uuid == str(identity))
                assert pose.coverage == 1
        state = reduce_lineage(state, root)
    assert found


@pytest.mark.parametrize("ending", ("defeat", "instant_death"))
@pytest.mark.parametrize("prone", (False, True))
def test_fiend_terminal_explosion_finishes_before_dissolve(data, ending, prone):
    history, identity, _ = summon_history(ending, family="fiend", prone_before_departure=prone)
    sequence = project_sequence(history.views["caster"])
    state = reduce_initialization(sequence.initialization)
    seen = False
    for root in sequence.lineages:
        group = bind_choreography(state, root, data)
        assert not group.gaps
        for cue in group.entity_lifecycle:
            if cue.phase != "departure":
                continue
            seen = True
            def body_at(age):
                frame = sample_body_presentation(state, group.after, data, age, age, {}, choreography=group)
                pose, = (pose for pose in frame.poses if pose.body.actor_uuid == str(identity))
                return pose.body
            # Upright deaths play the fifteen original frames at 12 fps. A
            # creature already lying down never restarts the standing wind-up.
            start = min([row.timing.start_ms for row in group.damage
                         if row.contact.actor_uuid == str(identity)] +
                        [row.start_ms for row in group.lifecycle
                         if row.contact.actor_uuid == str(identity) and row.death_end_ms is not None])
            assert cue.start_ms - start == pytest.approx(0 if prone else 14 * 1000 / 12)
            first = body_at(start)
            middle = body_at((start + cue.start_ms) / 2)
            last = body_at(cue.start_ms)
            assert (first.clip, first.frame) == ("Death", 14 if prone else 0)
            assert middle.clip == "Death"
            assert middle.frame == 14 if prone else 0 < middle.frame < 14
            assert (last.clip, last.frame) == ("Death", 14)
            assert body_at(start) == first
        state = reduce_lineage(state, root)
    assert seen


def test_reveal_preserves_original_rgb_shadow_alpha_and_endpoints():
    image = pygame.Surface((11, 15), pygame.SRCALPHA)
    image.fill((81, 117, 153, 128), (2, 2, 7, 11))
    source = pygame.surfarray.array_alpha(image)
    assert not np.any(pygame.surfarray.array_alpha(reveal_body(image, 0)))
    assert reveal_body(image, 1) is image
    previous = np.zeros_like(source)
    for progress in (.2, .5, .8):
        result = reveal_body(image, progress)
        alpha = pygame.surfarray.array_alpha(result)
        assert np.all(alpha >= previous) and np.all(alpha <= source)
        assert np.array_equal(pygame.surfarray.array3d(result), pygame.surfarray.array3d(image))
        previous = alpha
    assert np.array_equal(pygame.surfarray.array_alpha(image), source)


@pytest.mark.parametrize("family", ("animals", "fiend"))
def test_terminal_cleanup_preserves_prone_body_until_it_has_dissolved(data, family):
    pygame.init()
    pygame.display.set_mode((1, 1))
    history, identity, _ = summon_history("dismiss", family=family, prone_before_departure=True)
    sequence = project_sequence(history.views["caster"])
    state = reduce_initialization(sequence.initialization)
    found = False
    for root in sequence.lineages:
        group = bind_choreography(state, root, data)
        for cue in group.entity_lifecycle:
            if cue.phase != "departure":
                continue
            found = True
            assert cue.actor.condition.body_pose is not None
            # A fresh playback head must load the intact resting body itself.
            rows = {}
            load_choreography_media(group, body_rows=rows)
            for elapsed in (cue.start_ms, cue.body_end_ms-1):
                frame = sample_body_presentation(state, group.after, data, elapsed, elapsed, {}, choreography=group)
                pose, = (pose for pose in frame.poses if pose.body.actor_uuid == str(identity))
                assert pose.appearance_override == cue.actor.condition
                assert pose.body.clip != "Idle"
                assert condition_body_pose(data, pose.body, pose.actor.contact,
                                           pose.appearance_override) == pose.body
                assert actor_draw_commands(data, pose.body, pose.actor.contact, pose.actor.layers,
                                           rows, Camera(), condition=pose.appearance_override)
            assert not group.after.actors[identity].present
        state = reduce_lineage(state, root)
    assert found
