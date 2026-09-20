"""Native concealment roots cross player bytes and reuse authored actor tracks."""

from dataclasses import replace
import json
from types import MappingProxyType
from uuid import UUID

import pygame
import pytest

from game.animation_draw import LoadedBodyRows
from game.animation_data import load_animation_data
from game.choreography import bind_choreography, sample_choreography
from game.choreography_draw import load_choreography_media
from game.condition_types import ConditionRecipe
from game.feedback import choreography_feedback, sample_feedback
from game.playback_frame import sample_playback_frame
from game.player_facts import ActionFact, AttackFact, SpellFact
from game.player_reduction import reduce_lineage, stage_lineage
from game.projection import Camera
from game.scene import load_scene_media, scene_actors
from tests.game.concealment_scenarios import concealment_history
from tests.game.environment_scenarios import environment_history
from tests.game.player_helpers import player_history


@pytest.fixture(scope="module")
def data():
    return load_animation_data()


@pytest.fixture(scope="module")
def graphics():
    pygame.init()
    pygame.display.set_mode((640, 480))
    yield pygame.font.Font(None, 24)
    pygame.quit()


@pytest.fixture(scope="module")
def histories():
    return {
        "invisibility": concealment_history(reveal="attack"),
        "potion": concealment_history(sight_grant="potion", reveal="none"),
        "hide": concealment_history(program="hide-dim", reveal="none"),
    }


@pytest.fixture(scope="module")
def light_history():
    return environment_history()


def selected(history, role, behavior):
    before, roots = player_history(history, role=role)
    for root in roots:
        fact = root.root.fact
        if isinstance(fact, (SpellFact, ActionFact, AttackFact)) and fact.behavior_id == behavior:
            return before, root
        before = reduce_lineage(before, root)
    raise AssertionError(f"No disclosed {behavior} for {role}")


def frame(before, root, data, elapsed, quadrant, font):
    group = bind_choreography(before, root, data)
    actors = scene_actors(stage_lineage(before, root), data, {})
    body_rows: LoadedBodyRows = {}
    media = load_scene_media(actors, data, body_rows=body_rows)
    camera = Camera(quadrant=quadrant, viewport=(640, 480)).with_focus((7, 3))
    return sample_playback_frame(before, group.after, data, elapsed, elapsed, camera, {},
        media, font, font, choreography=group, choreography_media=load_choreography_media(group, body_rows=body_rows),
        feedback=choreography_feedback(group, data, 0))


def test_original_four_utility_drafts_have_body_and_effect_without_projectile(data):
    for identity in ("spell.invisibility", "spell.greater_invisibility", "spell.see_invisibility", "spell.true_seeing"):
        draft = data.drafts[identity]
        assert draft.projectile is None and draft.area is None
        assert (draft.cast.actionClip, draft.cast.bodyPlaybackSpeed, draft.cast.releaseFrame) == ("Special1", 1, 8)
        assert draft.cast.effects == () and not draft.cast.recovery.enabled


def test_actual_self_cast_releases_condition_at_frame_eight_in_all_views(histories, data, graphics):
    before, root = selected(histories["invisibility"], "subject", "spell.invisibility")
    group = bind_choreography(before, root, data)
    assert len(group.body_actions) == 1 and not group.nodes and not group.gaps
    cue = group.body_actions[0]
    assert cue.effect_ms == pytest.approx(8 / 12 * 1000)
    assert group.complete_ms == pytest.approx(14 / 12 * 1000)
    actor_id = UUID(cue.contact.actor_uuid)
    prior = sample_choreography(group, cue.effect_ms - 1)
    assert not any(member.behavior_id == "condition.spell.invisibility" for member in prior.displayed.actors[actor_id].conditions)
    midway = cue.effect_ms + 120
    for quadrant in range(4):
        result = frame(before, root, data, midway, quadrant, graphics)
        assert any(member.behavior_id == "condition.spell.invisibility" for member in result.displayed.actors[actor_id].conditions)
        body = next(command for command in result.commands
                    if str(command[4][0]) == cue.contact.actor_uuid and command[4][6] == "actor")
        assert body[1].get_alpha() == 191
        assert body[1].get_bounding_rect().width > 0
    frozen = sample_choreography(group, midway)
    latest = reduce_lineage(before, root)
    assert sample_choreography(group, midway) == frozen
    assert latest.actors[actor_id].conditions != before.actors[actor_id].conditions


def test_drink_uses_same_body_join_and_original_slot_scope(histories, data, graphics):
    before, root = selected(histories["potion"], "perceiver", "action.item.potion_true_seeing.drink")
    group = bind_choreography(before, root, data)
    cue, = group.body_actions
    assert cue.recipe_id == "action.item.potion_greater_invisibility.drink"
    assert cue.clip == "Taunt" and cue.effect_ms == pytest.approx(8 / 12 * 1000)
    assert cue.feedback is not None and cue.feedback.text == "True Seeing Potion"
    sample = sample_choreography(group, cue.effect_ms)
    body = next(body for body in sample.bodies if body.actor_uuid == cue.contact.actor_uuid)
    assert body.hidden_slots == ("weapon", "weaponGlow", "offhand")
    actor = sample.displayed.actors[UUID(body.actor_uuid)]
    assert any(member.behavior_id == "condition.spell.true_seeing" for member in actor.conditions)
    assert len(group.gaps) == 1 and "strip media" in group.gaps[0][1]
    # The missing original strip does not substitute another effect or suppress
    # the actor's real Taunt and causally anchored condition transition.
    result = frame(before, root, data, cue.effect_ms, 0, graphics)
    assert any(command[4][6] == "actor" and str(command[4][0]) == body.actor_uuid for command in result.commands)


def test_body_finished_does_not_restore_drink_slots_before_child_join(histories, data):
    before, root = selected(histories["potion"], "perceiver", "action.item.potion_true_seeing.drink")
    recipe = data.condition_recipes["condition.spell.true_seeing"].model_dump(mode="json")
    recipe["persistent"]["alphaMultiplier"] = .5
    recipe["application"]["durationMs"] = 2000
    prolonged = ConditionRecipe.model_validate_json(json.dumps(recipe))
    selected_data = replace(data, condition_recipes=MappingProxyType({**data.condition_recipes,
        "condition.spell.true_seeing": prolonged}))
    group = bind_choreography(before, root, selected_data)
    cue, = group.body_actions
    assert group.complete_ms == pytest.approx(cue.effect_ms + 2000)
    held = sample_choreography(group, cue.body_end_ms + 100)
    body = next(body for body in held.bodies if body.actor_uuid == cue.contact.actor_uuid)
    assert body.clip == "Idle" and body.hidden_slots == ("weapon", "weaponGlow", "offhand")
    assert sample_choreography(group, group.complete_ms).bodies == ()


def test_hide_preserves_source_disabled_actor_track(histories, data):
    before, root = selected(histories["hide"], "subject", "action.hide")
    group = bind_choreography(before, root, data)
    cue, = group.body_actions
    assert not cue.enabled and group.complete_ms == 0
    sample = sample_choreography(group, 0)
    assert not sample.bodies
    assert any(member.behavior_id == "condition.hidden" for actor in sample.displayed.actors.values() for member in actor.conditions)


@pytest.mark.parametrize("role", ("operator", "witness"))
def test_object_interaction_reaches_with_empty_hands_then_restores_gear(light_history, role, data, graphics):
    before, root = selected(light_history, role, "action.environment.wall_torch.extinguish")
    group = bind_choreography(before, root, data)
    cue, = group.body_actions
    assert not group.gaps
    assert cue.enabled and cue.clip == "Attack5"
    assert cue.effect_ms == pytest.approx(250)
    assert cue.complete_ms == pytest.approx(14 / 12 * 1000)
    assert cue.interaction_object_uuid is not None
    fixture = before.objects[cue.interaction_object_uuid]
    assert fixture.placement.position == (6, 5) and cue.contact.grid == (5, 5)
    assert cue.contact.facing == "SE", "the operator reaches toward the fixture, not its SELF mechanics target"
    at_contact = sample_choreography(group, cue.effect_ms)
    body, = at_contact.bodies
    assert body.frame == 3 and body.hidden_slots == ("weapon", "weaponGlow", "offhand")
    for quadrant in range(4):
        reaching = frame(before, root, data, cue.effect_ms - 1, quadrant, graphics)
        assert any(command[4][6] == "actor" and str(command[4][0]) == body.actor_uuid
                   for command in reaching.commands)
        contact_frame = frame(before, root, data, cue.effect_ms, quadrant, graphics)
        sees_operator = any(command[4][6] == "actor" and str(command[4][0]) == body.actor_uuid
                            for command in contact_frame.commands)
        assert sees_operator == (role == "operator"), "the ordinary witness loses the operator when the light goes off"
    assert sample_choreography(group, group.complete_ms).bodies == ()
    assert group.before.actors[UUID(body.actor_uuid)].visual_loadout == group.after.actors[UUID(body.actor_uuid)].visual_loadout


def test_reveal_feedback_uses_actual_reacquisition_contact(histories, data, graphics):
    before, root = selected(histories["invisibility"], "perceiver", "action.attack")
    group = bind_choreography(before, root, data)
    assert len(group.nodes) == 1
    source_id = root.root.fact.source_entity_uuid if isinstance(root.root.fact, AttackFact) else None
    assert source_id is not None
    staged = sample_choreography(group, 0).displayed
    assert staged.senses is not None and staged.senses.entities[source_id].position == (9, 3)
    assert before.actors[source_id].last_visual_position == (7, 3)
    assert not staged.actors[source_id].conditions
    removal = next(condition for condition in group.conditions if condition.feedback_text == "−Invisible")
    assert not sample_choreography(group, removal.start_ms).displayed.actors[source_id].conditions
    visible = frame(before, root, data, 0, 0, graphics)
    body = next(command for command in visible.commands
                if command[4][6] == "actor" and str(command[4][0]) == str(source_id))
    assert body[1].get_alpha() in (None, 255)
    assert before.senses is not None and removal.target_uuid not in before.senses.entities
    tracks = choreography_feedback(group, data, 0)
    feedback = next(track for track in tracks if track.label == "−Invisible")
    assert feedback.contact.grid == (9, 3)
    frozen = sample_feedback(feedback, removal.start_ms + 30)
    reduce_lineage(before, root)
    assert sample_feedback(feedback, removal.start_ms + 30) == frozen


def test_witnessed_invisibility_keeps_cast_and_fade_before_contact_loss(histories, data, graphics):
    before, root = selected(histories["invisibility"], "perceiver", "spell.invisibility")
    group = bind_choreography(before, root, data)
    cue, = group.body_actions
    assert cue.contact.grid == (7, 3)
    for quadrant in range(4):
        during = frame(before, root, data, cue.effect_ms + 120, quadrant, graphics)
        actor = next(command for command in during.commands
                     if command[4][6] == "actor" and str(command[4][0]) == cue.contact.actor_uuid)
        assert actor[1].get_alpha() == 191
        complete = frame(before, root, data, group.complete_ms, quadrant, graphics)
        assert all(view.contact.actor_uuid != cue.contact.actor_uuid for view in complete.actors)
