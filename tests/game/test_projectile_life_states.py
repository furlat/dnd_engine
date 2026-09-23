"""Real projectile outcomes retain HP/life and use shared authored downed poses."""

from dataclasses import replace
import json

import pygame
import pytest

from dnd.core.life_types import LifeState
from devtools.animation_review.trace import group_trace
from game.animation import (ActorContact, CastApplication, CastInput, body_clip, compile_cast,
                            sample_cast, sample_idle_body)
from game.animation_data import load_animation_data
from game.choreography import bind_choreography, sample_choreography
from game.choreography_draw import load_choreography_media
from game.combat import BoundCast
from game.damage import bind_damage, sample_damage
from game.playback_frame import sample_playback_frame
from game.player_facts import DamageFact, LifeFact
from game.player_reduction import lineage_branch
from game.projection import Camera
from game.scene import load_scene_media, scene_actors
from tests.game.player_helpers import player_history
from tests.game.projectile_life_scenarios import projectile_life_history


@pytest.fixture(scope="module")
def data():
    return load_animation_data()




@pytest.mark.parametrize("role", ("caster", "recipient"))
@pytest.mark.parametrize("initial", (LifeState.ALIVE, LifeState.DYING, LifeState.STABLE))
def test_native_projectile_downing_and_downed_death_play_without_a_gap(data, role, initial):
    before, (lineage,) = player_history(projectile_life_history(initial), role=role)
    identity = next(actor.uuid for actor in before.actors.values() if actor.name == "Death-save recipient")
    hp = 0
    life = LifeState.DYING if initial is LifeState.ALIVE else LifeState.DEAD
    group = bind_choreography(before, lineage, data)
    assert group.gaps == ()
    assert json.loads(json.dumps(group_trace(group)))["root_uuid"] == str(group.root_uuid)
    if role == "recipient" and initial is not LifeState.ALIVE:
        # A downed observer has no sight of the caster; only its own injury is retained.
        assert not group.nodes and len(group.damage) == 1
        cue = group.damage[0]
        assert cue.resulting_hp == hp and cue.resulting_life_state is life
        assert sample_choreography(group, cue.timing.hp_ms).bodies[0].frame == 14
        assert group.after.actors[identity].normal_hp == hp
        return
    assert len(group.nodes) == 1
    assert group.after.actors[identity].life_state is life
    assert group.after.actors[identity].normal_hp == hp == 0
    assert life is (LifeState.DYING if initial is LifeState.ALIVE else LifeState.DEAD)
    bound = group.nodes[0].bound
    assert isinstance(bound, BoundCast)
    timeline = bound.timeline
    application, = timeline.applications
    assert application.source.resulting_hp == hp and application.source.resulting_life_state is life
    transitions = {event.uuid for event in lineage.events if isinstance(event.fact, LifeFact)}
    assert group.nodes[0].bound.owned_life_events == transitions
    at = application.hp_ms
    assert at is not None
    early = sample_choreography(group, at - .001)
    assert early.displayed.actors[identity].life_state is initial
    assert early.displayed.actors[identity].normal_hp == before.actors[identity].normal_hp
    samples = [sample_choreography(group, time) for time in (at, at + 100, group.complete_ms)]
    frames = [next(body.frame for body in sample.clips[0].sample.bodies if body.actor_uuid == str(identity))
              for sample in samples]
    assert frames[-1] == 14
    if initial is LifeState.ALIVE:
        assert 0 == frames[0] < frames[1] < frames[-1]
    else:
        assert frames == [14, 14, 14]
    for sample in samples:
        assert (sample.displayed.actors[identity].normal_hp, sample.displayed.actors[identity].life_state) == (hp, life)
        assert not sample.bodies  # The damaging application owns this body once.
    assert sample_choreography(group, at - .001) == early


def test_downed_entry_keeps_authored_damage_delay_and_hp_frame(data):
    before, (lineage,) = player_history(projectile_life_history())
    identity = next(actor.uuid for actor in before.actors.values() if actor.name == "Death-save recipient")
    draft = data.drafts["spell.fire_bolt"]
    damage = draft.damage.model_copy(update={"impactDelayMs": 125.,
        "floatingNumber": draft.damage.floatingNumber.model_copy(update={"frame": 3}),
        "hitFlash": draft.damage.hitFlash.model_copy(update={"frame": 1})})
    authored = replace(data, drafts={**data.drafts, "spell.fire_bolt": draft.model_copy(update={"damage": damage})})
    group = bind_choreography(before, lineage, authored)
    assert group.gaps == ()
    bound = group.nodes[0].bound
    assert isinstance(bound, BoundCast)
    timeline = bound.timeline
    application, = timeline.applications
    interval = 1000 / (body_clip(authored, application.source.target, authored.damage_context.bodyClip).fps
                       * authored.damage_context.bodyPlaybackSpeed)
    assert application.damage_start_ms == application.travel_end_ms + 125
    assert application.hp_ms == pytest.approx(application.damage_start_ms + 3 * interval)
    assert application.hp_ms is not None
    before_hp = sample_choreography(group, application.hp_ms - .001)
    after_hp = sample_choreography(group, application.hp_ms)
    assert before_hp.displayed.actors[identity].normal_hp == 4
    assert before_hp.displayed.actors[identity].life_state is LifeState.ALIVE
    assert after_hp.displayed.actors[identity].normal_hp == 0
    assert after_hp.displayed.actors[identity].life_state is LifeState.DYING
    assert next(body for body in before_hp.clips[0].sample.bodies if body.actor_uuid == str(identity)).clip == "TakeDamage"
    assert next(body for body in after_hp.clips[0].sample.bodies if body.actor_uuid == str(identity)).frame == 0


def test_native_stable_hit_owns_both_life_transitions_as_standalone_damage(data):
    before, (lineage,) = player_history(projectile_life_history(LifeState.STABLE))
    taken, = (node for node in lineage.events if isinstance(node.fact, DamageFact) and node.fact.stage == "taken")
    branch = lineage_branch(lineage, taken)
    cue = bind_damage(before, branch, data, start_ms=250)
    assert cue is not None
    changes = [(node.uuid, node.fact) for node in branch.events if isinstance(node.fact, LifeFact)]
    assert [fact.new_state for _, fact in changes] == [LifeState.DYING, LifeState.DEAD]
    assert cue.owned_life_events == frozenset(identity for identity, _ in changes)
    assert cue.resulting_hp == 0 and cue.resulting_life_state is LifeState.DEAD
    sample = sample_damage(cue, cue.timing.hp_ms)
    assert sample.body is not None and sample.body.frame == 14


def test_native_repeated_projectile_replays_downing_then_death_without_refall(data):
    before, (lineage,) = player_history(projectile_life_history(repeated=True))
    group = bind_choreography(before, lineage, data)
    assert group.gaps == () and len(group.nodes) == 1
    bound = group.nodes[0].bound
    assert isinstance(bound, BoundCast)
    timeline = bound.timeline
    first, second, third = timeline.applications
    assert first.source.resulting_life_state is LifeState.DYING
    assert second.source.resulting_life_state is LifeState.DEAD
    assert first.source.resulting_hp == second.source.resulting_hp == 0
    assert first.life_body is not None and second.life_body is third.life_body is None
    assert first.hp_ms is not None and second.hp_ms is not None
    for time in (first.hp_ms, second.hp_ms, first.hp_ms + 240, timeline.complete_ms):
        sample = sample_cast(timeline, time)
        body = next(body for body in sample.bodies if body.actor_uuid == first.source.target.actor_uuid)
        assert body.clip == "Die"
        assert body.frame == min(first.life_body.frames - 1, int((time - first.hp_ms) * first.life_body.fps / 1000))
    assert bound.owned_life_events == frozenset(node.uuid for node in lineage.events if isinstance(node.fact, LifeFact))


def test_native_downed_hit_without_a_life_transition_keeps_the_rest_pose(data):
    before, (lineage,) = player_history(projectile_life_history(LifeState.DYING, maximum_hp=20))
    assert not any(isinstance(node.fact, LifeFact) for node in lineage.events)
    group = bind_choreography(before, lineage, data)
    assert group.gaps == ()
    bound = group.nodes[0].bound
    assert isinstance(bound, BoundCast)
    application, = bound.timeline.applications
    assert application.source.resulting_hp == 0 and application.life_body is None
    assert application.hp_ms is not None
    for time in (application.hp_ms, bound.timeline.complete_ms):
        sample = sample_cast(bound.timeline, time)
        assert sample.vitals[0].hp == 0 and sample.vitals[0].life_state is LifeState.DYING
        body = next(body for body in sample.bodies if body.actor_uuid == application.source.target.actor_uuid)
        assert body.clip == "Die" and body.frame == 14


def test_repeated_delivery_crossing_dying_then_dead_continues_one_fall(data):
    recipient = ActorContact("recipient", (4, 0), "W", 1, hp=4)
    timeline = compile_cast(data, "spell.magic_missile", CastInput("volley",
        ActorContact("caster", (0, 0), "S", 1), (
            CastApplication("first", recipient, True, 5, 0, LifeState.DYING, "Force"),
            CastApplication("second", recipient, True, 5, 0, LifeState.DEAD, "Force"),
        )))
    first, second = timeline.applications
    assert first.life_body is not None and second.life_body is None
    assert first.hp_ms is not None and second.hp_ms is not None
    assert first.hp_ms < second.hp_ms
    frames = []
    for at, life in ((first.hp_ms, LifeState.DYING), (second.hp_ms, LifeState.DEAD),
                     (timeline.complete_ms, LifeState.DEAD)):
        sample = sample_cast(timeline, at)
        body = next(body for body in sample.bodies if body.actor_uuid == "recipient")
        assert body.clip == "Die"
        frames.append(body.frame)
        assert sample.vitals[0].hp == 0 and sample.vitals[0].life_state is life
    assert 0 == frames[0] <= frames[1] < frames[2] == 14
    midway = sample_cast(timeline, first.hp_ms + 250)
    assert next(body.frame for body in midway.bodies if body.actor_uuid == "recipient") == int(250 * first.life_body.fps / 1000)
    assert sample_idle_body(data, replace(recipient, life_state=LifeState.DYING), 0).frame == 14


def test_native_downing_renders_one_body_and_settles_in_all_cameras(data):
    before, (lineage,) = player_history(projectile_life_history())
    identity = next(actor.uuid for actor in before.actors.values() if actor.name == "Death-save recipient")
    group = bind_choreography(before, lineage, data)
    pygame.init()
    pygame.display.set_mode((640, 480))
    try:
        rows = {}
        media = load_scene_media((*scene_actors(before, data, {}), *scene_actors(group.after, data, {})),
                                 data, body_rows=rows)
        group_media = load_choreography_media(group, body_rows=rows)
        number, badge = (pygame.font.SysFont(style.fontFamily, round(style.fontSizePx))
                         for style in (data.number_style, data.badge_style))
        for quadrant in range(4):
            camera = Camera(quadrant=quadrant, viewport=(640, 480)).with_focus((4, 3))
            active = sample_playback_frame(before, group.after, data, group.complete_ms, 5000,
                camera, {}, media, number, badge, choreography=group, choreography_media=group_media)
            settled = sample_playback_frame(group.after, None, data, 0, 5000, camera, {}, media, number, badge)
            actual, = (command for command in active.commands if command.evidence[0] == str(identity)
                       and command.evidence[6] == "actor")
            idle, = (command for command in settled.commands if command.evidence[0] == str(identity)
                     and command.evidence[6] == "actor")
            assert actual.evidence[8:10] == idle.evidence[8:10] == ("Die", 14)
            assert actual.destination == idle.destination
            assert pygame.image.tobytes(actual.surface, "RGBA") == pygame.image.tobytes(idle.surface, "RGBA")
    finally:
        pygame.quit()
