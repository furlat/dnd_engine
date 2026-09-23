"""Native Sleep/wake facts select held rig poses and authored sleep media."""

from dataclasses import replace
from uuid import UUID

import pygame
import pytest

from dnd.core.life_types import LifeState
from game.animation import BodySample, body_clip
from game.animation_data import load_animation_data
from game.animation_draw import actor_draw_commands, load_actor_media
from game.choreography import bind_choreography
from game.condition_media_lifetime import register_condition_lifetimes
from game.choreography_draw import load_choreography_media
from game.playback_frame import sample_playback_frame
from game.player_facts import SpellFact
from game.player_reduction import reduce_lineage
from game.projection import Camera
from game.scene import load_scene_media, scene_actors
from tests.game.device_scenarios import device_history
from tests.game.player_helpers import player_history


@pytest.fixture(scope="module")
def rendering():
    pygame.init()
    pygame.display.set_mode((640, 480))
    data = load_animation_data()
    fonts = tuple(pygame.font.SysFont(style.fontFamily, round(style.fontSizePx))
                  for style in (data.number_style, data.badge_style))
    yield data, fonts
    pygame.quit()


def actor_command(frame, identity: UUID):
    command, = (row for row in frame.commands if row.evidence[0] == str(identity)
                and row.evidence[6] == "actor")
    return command


def sleeping_labels(frame) -> set[str]:
    return {str(row.evidence[0]) for row in frame.commands
            if row.evidence[6] == "floating_number" and row.evidence[2] == "Zzz"}


def has_condition_pixels(frame, identity: UUID, data, media, camera) -> bool:
    actor = next(row for row in frame.actors if row.contact.actor_uuid == str(identity))
    actual = actor_command(frame, identity)
    bare, = (row for row in actor_draw_commands(data,
        BodySample(str(identity), actual.evidence[8], actual.evidence[9], actor.contact.facing),
        actor.contact, actor.layers, media, camera) if row.evidence[6] == "actor")
    return (actual.destination != bare.destination
            or pygame.image.tobytes(actual.surface, "RGBA") != pygame.image.tobytes(bare.surface, "RGBA"))


@pytest.mark.parametrize("program", ("normal-sleep", "sleep-area"))
def test_native_sleep_and_damage_wake_render_different_from_a_corpse(rendering, program) -> None:
    data, (number_font, badge_font) = rendering
    before, lineages = player_history(device_history(program=program))
    states = []
    for lineage in lineages:
        states.append((before, lineage))
        before = reduce_lineage(before, lineage)
    asleep, wake = next((state, lineage) for state, lineage in states
        if isinstance(lineage.root.fact, SpellFact) and lineage.root.fact.behavior_id == "spell.fire_bolt")
    awake = reduce_lineage(asleep, wake)
    target = wake.root.fact.target_entity_uuid
    assert target is not None
    sleepers = {actor.uuid for actor in asleep.actors.values()
                if any(condition.behavior_id == "condition.spell.sleep" for condition in actor.conditions)}
    assert len(sleepers) == 2 and target in sleepers
    assert all(asleep.actors[identity].life_state is LifeState.ALIVE for identity in sleepers)
    rows = {}
    media = load_scene_media((*scene_actors(asleep, data, {}), *scene_actors(awake, data, {})),
                             data, body_rows=rows)
    group = bind_choreography(asleep, wake, data)
    group_media = load_choreography_media(group, body_rows=rows)
    removal, = (condition for condition in group.conditions if condition.target_uuid == target
                and any(member.behavior_id == "condition.spell.sleep" for member in condition.before_membership)
                and not any(member.behavior_id == "condition.spell.sleep" for member in condition.after_membership))
    records = register_condition_lifetimes({}, asleep, data, absolute_start_ms=4000,
        lineage=wake, choreography=group)
    assert removal.start_ms > 0
    delivery = group.nodes[0].bound.timeline.applications[0]
    assert delivery.damage_start_ms is not None
    for quadrant in range(4):
        camera = Camera(quadrant=quadrant, viewport=(640, 480)).with_focus((8, 5))

        def frame(state, after=None, time=0, *, active=False):
            return sample_playback_frame(state, after, data, time, 4000 + time, camera, {}, media,
                number_font, badge_font, choreography=group if active else None,
                choreography_media=group_media if active else None, condition_lifetimes=records)

        idle = frame(asleep)
        assert not sleeping_labels(idle)
        assert all(has_condition_pixels(idle, identity, data, media, camera) for identity in sleepers)
        for actor in idle.actors:
            identity = UUID(actor.contact.actor_uuid)
            if identity not in sleepers:
                continue
            expected_frame = body_clip(data, actor.contact, "Die").frames - 1
            actual = actor_command(idle, identity)
            assert actual.evidence[8:10] == ("Die", expected_frame)
        before_contact = frame(asleep, awake, delivery.damage_start_ms - .001, active=True)
        at_contact = frame(asleep, awake, removal.start_ms, active=True)
        assert actor_command(before_contact, target).evidence[8] == "Die"
        assert not sleeping_labels(before_contact)
        # Contact hits the resting pose; actual condition removal starts rising.
        before_wake = frame(asleep, awake, removal.start_ms - .001, active=True)
        assert not sleeping_labels(before_wake) and not sleeping_labels(at_contact)
        assert actor_command(before_wake, target).evidence[8:10] == ("Die", 14)
        assert actor_command(at_contact, target).evidence[8:10] == ("Die", 14)
        rising = frame(asleep, awake, (removal.start_ms + removal.complete_ms) / 2, active=True)
        assert actor_command(rising, target).evidence[8:10] == ("Die", 7)
        assert rising.displayed.actors[target].normal_hp == awake.actors[target].normal_hp
        after_rise = frame(asleep, awake, removal.complete_ms + .001, active=True)
        assert actor_command(after_rise, target).evidence[8] == "Idle"
        final = frame(asleep, awake, group.complete_ms, active=True)
        assert actor_command(final, target).evidence[8] == "Idle"
        assert not sleeping_labels(final)
        assert not has_condition_pixels(final, target, data, media, camera)
        assert all(has_condition_pixels(final, identity, data, media, camera) for identity in sleepers - {target})
        assert final.displayed.actors[target].life_state is LifeState.ALIVE
        # Seeking backwards restores the resting pose and authored indicator from history.
        rewound = frame(asleep, awake, delivery.damage_start_ms - .001, active=True)
        assert all(has_condition_pixels(rewound, identity, data, media, camera) for identity in sleepers)


def test_sleep_pose_never_replaces_an_active_body_clip_or_marks_a_dead_actor(rendering) -> None:
    data, (number_font, badge_font) = rendering
    before, lineages = player_history(device_history(program="normal-sleep"))
    for lineage in lineages:
        before = reduce_lineage(before, lineage)
        if isinstance(lineage.root.fact, SpellFact) and lineage.root.fact.behavior_id == "spell.sleep":
            break
    actor = next(row for row in scene_actors(before, data, {}) if row.condition.body_pose)
    rows = {}
    media = load_scene_media((actor,), data, body_rows=rows)
    load_actor_media(data, ((actor.contact, actor.layers, ("TakeDamage", "Attack1")),),
                     body_rows=rows, all_facings=True)
    for clip in ("Attack1", "Die"):
        commands = actor_draw_commands(data, BodySample(actor.contact.actor_uuid, clip, 1, "S"),
            actor.contact, actor.layers, media, Camera(), condition=actor.condition)
        assert next(row for row in commands if row.evidence[6] == "actor").evidence[8:10] == (clip, 1)
    identity = UUID(actor.contact.actor_uuid)
    dead_actor = replace(before.actors[identity], life_state=LifeState.DEAD)
    dead = replace(before, actors={**before.actors, identity: dead_actor})
    load_scene_media(scene_actors(dead, data, {}), data, body_rows=rows)
    frame = sample_playback_frame(dead, None, data, 0, 4000, Camera(), {}, media, number_font, badge_font)
    assert actor_command(frame, identity).evidence[8] == data.death_context.bodyClip
    assert not sleeping_labels(frame)
    assert not has_condition_pixels(frame, identity, data, media, Camera())


def test_native_sleep_plays_one_fall_before_holding_the_rest_pose(rendering) -> None:
    data, (number_font, badge_font) = rendering
    before, lineages = player_history(device_history(program="normal-sleep"))
    for lineage in lineages:
        if isinstance(lineage.root.fact, SpellFact) and lineage.root.fact.behavior_id == "spell.sleep":
            break
        before = reduce_lineage(before, lineage)
    group = bind_choreography(before, lineage, data)
    rows = {}
    media = load_scene_media((*scene_actors(before, data, {}), *scene_actors(group.after, data, {})),
                             data, body_rows=rows)
    group_media = load_choreography_media(group, body_rows=rows)
    falls = [cue for cue in group.conditions if cue.body is not None]
    assert len(falls) == 2
    for quadrant in range(4):
        camera = Camera(quadrant=quadrant, viewport=(640, 480)).with_focus((8, 5))
        for cue in falls:
            frames = []
            for fraction in (0, .5, 1):
                at = cue.start_ms + fraction * (cue.complete_ms - cue.start_ms)
                frame = sample_playback_frame(before, group.after, data, at, at, camera, {}, media,
                    number_font, badge_font, choreography=group, choreography_media=group_media)
                command = actor_command(frame, cue.target_uuid)
                assert command.evidence[8] == "Die"
                frames.append(command.evidence[9])
            assert frames == [0, 7, 14]
            assert group.complete_ms >= cue.complete_ms


def test_native_lethal_hit_on_a_sleeper_never_stands_or_restarts_falling(rendering) -> None:
    data, (number_font, badge_font) = rendering
    before, lineages = player_history(device_history(program="normal-sleep", wake_damage=10))
    for lineage in lineages:
        if isinstance(lineage.root.fact, SpellFact) and lineage.root.fact.behavior_id == "spell.fire_bolt":
            break
        before = reduce_lineage(before, lineage)
    group = bind_choreography(before, lineage, data)
    target = lineage.root.fact.target_entity_uuid
    assert group.after.actors[target].life_state is LifeState.DEAD
    rows = {}
    media = load_scene_media((*scene_actors(before, data, {}), *scene_actors(group.after, data, {})),
                             data, body_rows=rows)
    group_media = load_choreography_media(group, body_rows=rows)
    hit = group.nodes[0].bound.timeline.applications[0].damage_start_ms
    for quadrant in range(4):
        camera = Camera(quadrant=quadrant, viewport=(640, 480)).with_focus((8, 5))
        for at in (hit - .001, hit, hit + 100, hit + 500, group.complete_ms):
            frame = sample_playback_frame(before, group.after, data, at, at, camera, {}, media,
                number_font, badge_font, choreography=group, choreography_media=group_media)
            assert actor_command(frame, target).evidence[8:10] == ("Die", 14)
            if at >= hit:
                assert frame.displayed.actors[target].life_state is LifeState.DEAD
