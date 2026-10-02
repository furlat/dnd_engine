"""Native curse choices/outcomes and observable phase/attachment regressions."""

from dataclasses import replace
from uuid import uuid4

import pygame
import pytest

from game.animation import media_target_applies
from game.actor_facts import ConditionFact
from dnd.core.condition_types import ConditionCategory
from game.animation_data import load_animation_data
from game.condition_animation import ConditionAppearance, resolve_condition_appearance
from game.condition_draw import compose_condition_layers
from game.condition_media_lifetime import ConditionMediaLifetime, sample_condition_lifetimes
from game.condition_sampling import sample_condition_media, _loop_samples
from game.choreography_draw import load_choreography_media
from game.playback_frame import sample_playback_frame
from game.scene import load_scene_media, scene_actors
from game.projection import Camera
from game.choreography import bind_choreography
from game.combat import BoundCast
from game.player_projection import project_sequence
from game.player_reduction import decode_player_sequence, encode_player_sequence, reduce_lineage
from game.replay import RecordedSequence, PASSIVE_EVENT_REPLAY
from tests.game.curse_scenarios import curse_history


@pytest.fixture(scope="module")
def data():
    pygame.init()
    pygame.display.set_mode((1, 1))
    yield load_animation_data()
    pygame.quit()


def cue(data, option):
    key = ("ability", "attack", "inaction", "damage")[option - 1]
    identity = f"condition.spell.bestow_curse.{key}"
    actor, owner = uuid4(), uuid4()
    member = ConditionFact(uuid4(), owner, identity, ConditionCategory.STATUS, identity, None, None)
    appearance = resolve_condition_appearance((member,), data.condition_recipes, data.condition_media)
    return str(actor), appearance, ConditionMediaLifetime(actor, owner, identity, applied_ms=1000)


@pytest.mark.parametrize("option", range(1, 5))
def test_warmup_quiet_reacquisition_and_source_release(data, option):
    actor, appearance, lifetime = cue(data, option)

    def samples(time, visible=appearance, record=lifetime):
        resolved = sample_condition_lifetimes({actor: visible}, {record.owner_uuid: record}, data, time)[actor]
        return tuple(item for layer in resolved.layers for item in sample_condition_media(data, layer))

    assert len(samples(1000)) == 4 and all(".apply." in r.asset_id for r in samples(1000))
    assert len(samples(2000)) == 4 and all(".hold." in r.asset_id and r.frame == 0 for r in samples(2000))
    overlap = samples(3875)
    assert len(overlap) == 8
    assert all(r.frame in (60, 4) and r.alpha == pytest.approx(.5) for r in overlap)
    unknown = replace(lifetime, applied_ms=None)
    assert all(".hold." in r.asset_id for r in samples(8875, record=unknown))
    removed = replace(lifetime, removed_ms=3900,
        removed_layers=tuple(row.layer.assetId for row in appearance.layers))
    release = samples(4150, ConditionAppearance(), removed)
    assert len(release) == 4 and all("release" in r.asset_id and r.frame == 8 for r in release)
    assert not samples(5650, ConditionAppearance(), removed)
    assert samples(3875) == overlap


@pytest.mark.parametrize("quadrant", range(4))
def test_mark_stays_above_actual_actor_envelope_during_movement(data, quadrant):
    actor, appearance, lifetime = cue(data, 1)
    resolved = sample_condition_lifetimes({actor: appearance}, {lifetime.owner_uuid: lifetime}, data, 2500)[actor]
    layers = tuple(r for r in resolved.layers if r.layer.attachment == "head")
    for position, top in (((180, 170), 9), ((240, 215), 2), ((300, 180), 20)):
        body = pygame.Surface((40, 80), pygame.SRCALPHA)
        body.fill((33, 55, 77, 255), (10, top, 20, 80 - top))
        output, origin = compose_condition_layers(body, position,
            (position[0] + 20., position[1] + 80.), "E", 1., 1., layers, {}, data=data,
            quadrant=quadrant, attachment_anchors={"head": (position[0] + 20., position[1] + 30.)})
        alpha = pygame.surfarray.array_alpha(output)
        # No cue pixel may invade the clearance band directly above the head.
        y0 = position[1] + top - 9 - origin[1]
        y1 = position[1] + top - origin[1]
        assert not alpha[:, max(0, y0):max(0, y1)].any()


@pytest.fixture(scope="module", params=[(option, saved) for option in range(1, 5) for saved in (False, True)])
def captured(request):
    option, saved = request.param
    return option, saved, curse_history(option=option, saved=saved)


@pytest.mark.parametrize("role", ("caster", "recipient"))
def test_actual_cast_replay_keeps_choice_save_and_cleanup(captured, data, role):
    option, saved, history = captured
    recorded = RecordedSequence.model_validate_json(history.views[role].model_dump_json(), context=PASSIVE_EVENT_REPLAY)
    state, roots = decode_player_sequence(encode_player_sequence(project_sequence(recorded)))
    saves = []
    acquired = set()
    for root in roots:
        group = bind_choreography(state, root, data)
        for clip in group.nodes:
            if isinstance(clip.bound, BoundCast) and clip.bound.timeline.recipe.definitionRef.content_id == "spell.bestow_curse":
                timeline = clip.bound.timeline
                marks = [track for track in timeline.recipe.media if track.requiredSaveSuccess is True]
                expected_mark = ('ability_burden', 'bent_strike', 'action_denial', 'necrotic_wound')[option - 1]
                assert len(marks) == 2
                assert all(expected_mark in track.assetId and track.actorTopClearancePx == 10 for track in marks)
                for application in timeline.source.applications:
                    for mark in marks:
                        assert media_target_applies(mark, application) is saved
                        assert not media_target_applies(mark, replace(application, save_succeeded=None))
                        assert media_target_applies(mark, replace(application, hit=False)) is saved
                saves.extend(a.save_succeeded for a in timeline.source.applications)
        state = reduce_lineage(state, root)
        acquired.update(c.behavior_id for actor in state.actors.values() for c in actor.conditions
            if c.behavior_id is not None and c.behavior_id.startswith("condition.spell.bestow_curse."))
    assert saves and all(s is saved for s in saves)
    expected = f"condition.spell.bestow_curse.{('ability','attack','inaction','damage')[option - 1]}"
    assert acquired == (set() if saved else {expected})
    assert not any(c.behavior_id == expected for actor in state.actors.values() for c in actor.conditions)


@pytest.mark.parametrize("boundary", (2000., 3750., 5500., 9000.))
def test_overlap_clock_continues_incoming_frames_at_every_seam(boundary):
    before = _loop_samples("test", boundary - .001, 32, 64, 1., 250., None)
    after = _loop_samples("test", boundary, 32, 64, 1., 250., None)
    assert before[-1].frame == 7 and before[-1].alpha > .999
    assert len(after) == 1 and after[0].frame == 8 and after[0].alpha == 1.


@pytest.mark.parametrize("saved", (False, True))
def test_main_playback_draws_resisted_mark_only_after_disclosed_success(data, saved):
    history = curse_history(option=1, saved=saved)
    state, roots = decode_player_sequence(encode_player_sequence(project_sequence(history.views["caster"])))
    font = pygame.font.Font(None, 14)
    for root in roots:
        group = bind_choreography(state, root, data)
        casts = [node for node in group.nodes if isinstance(node.bound, BoundCast)
            and node.bound.timeline.recipe.definitionRef.content_id == "spell.bestow_curse"]
        if casts:
            node = casts[0]
            timeline = node.bound.timeline
            time = node.start_ms + timeline.release_ms + 656.25 + 300
            rows = {}
            bodies = load_scene_media(scene_actors(state, data, {}), data, body_rows=rows)
            media = load_choreography_media(group, body_rows=rows)
            for quadrant in range(4):
                frame = sample_playback_frame(group.before, group.after, data, time, time,
                    Camera(quadrant=quadrant), {}, bodies, font, font,
                    choreography=group, choreography_media=media)
                marks = [command for command in frame.commands if any(
                    isinstance(value, str) and value.startswith("resisted.") for value in command.evidence)]
                assert bool(marks) is saved
                if saved:
                    target = timeline.source.applications[0].target
                    body_bounds = [command.surface.get_bounding_rect().move(command.destination)
                        for command in frame.commands if command.role == "actor" and command.owner == target.actor_uuid]
                    assert body_bounds
                    top = min(rect.top for rect in body_bounds)
                    assert all(command.surface.get_bounding_rect().move(command.destination).bottom <= top - 5
                        for command in marks)
            return
        state = reduce_lineage(state, root)
    pytest.fail("No disclosed curse cast")
