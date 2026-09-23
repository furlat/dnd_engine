"""Saved support actions own healing contact, condition lifetime and illumination."""

import pytest

from devtools.animation_review.cases import SupportCase, TrueStrikeCase, load_cases
from dnd.core.base_object import PASSIVE_EVENT_REPLAY, BaseObject
from dnd.core.base_block import LightLevel
from dnd.core.events import EventQueue, TakeDamageEvent
from game.animation import sample_cast
from game.animation_data import load_animation_data
from game.choreography import bind_choreography, sample_choreography
from game.combat import BoundCast
from game.condition_animation import resolve_condition_appearance
from game.feedback import choreography_feedback
from game.player_facts import HealFact, MovementFact, SpellFact
from game.player_projection import project_sequence
from game.player_reduction import decode_player_sequence, encode_player_sequence, reduce_lineage
from game.replay import RecordedSequence
from tests.game.support_scenarios import support_history


PROGRAMS = ("cure_wounds", "healing_word", "prayer_of_healing", "guidance", "resistance",
            "shield_of_faith", "light", "thaumaturgy", "stacked")
CONDITIONS = frozenset(f"condition.spell.{name}" for name in ("guidance", "resistance", "shield_of_faith", "light"))


@pytest.fixture(scope="module")
def data():
    return load_animation_data()


@pytest.fixture(scope="module", params=PROGRAMS)
def captured(request):
    return request.param, support_history(program=request.param)


@pytest.mark.parametrize("role", ("caster", "recipient"))
def test_support_replay_preserves_contact_lifetime_and_native_results(captured, data, role):
    program, history = captured
    assert set(history.views) == {"caster", "recipient"}
    recorded = RecordedSequence.model_validate_json(history.views[role].model_dump_json(), context=PASSIVE_EVENT_REPLAY)
    state, roots = decode_player_sequence(encode_player_sequence(project_sequence(recorded)))
    actors = {actor.name: actor.uuid for actor in state.actors.values()}
    recipient, caster = actors["Recipient"], actors["Caster"]
    healing = program in ("cure_wounds", "healing_word", "prayer_of_healing")
    if healing:
        assert not any(isinstance(event, TakeDamageEvent) for root in recorded.lineages for event in root.events)
    initial_hp = {identity: actor.normal_hp for identity, actor in state.actors.items()}
    initial_conditions = state.actors[caster].conditions
    if program == "light":
        assert state.senses is not None
        # The fixture grants darkvision: actual darkness is perceived as dim.
        assert state.senses.effective_light_levels[(4, 6)] is LightLevel.DIM_LIGHT
    maximum_layers = 0
    witnessed_light = moved_light = False
    cast_count = 0
    for root in roots:
        lineages = {event.lineage_uuid for event in root.events}
        assert all(child in lineages for event in root.events for child in event.children_lineages)
        after = reduce_lineage(state, root)
        if isinstance(root.root.fact, SpellFact):
            cast_count += 1
            group = bind_choreography(state, root, data, facings={str(caster): "NW"})
            assert not group.gaps, (program, role, group.gaps)
            if healing:
                node, = group.nodes
                assert isinstance(node.bound, BoundCast)
                timeline = node.bound.timeline
                targets = {application.source.target.actor_uuid for application in timeline.applications}
                expected_targets = {str(recipient)} | ({str(actors["Second"])} if program == "prayer_of_healing" else set())
                assert targets == expected_targets
                assert len(group.healing) == len(expected_targets)
                for cue in group.healing:
                    fact = cue.event.fact
                    assert isinstance(fact, HealFact) and not fact.was_blocked
                    expected = 12 if program == "prayer_of_healing" else 8
                    assert fact.actual_healing == expected and fact.resulting_normal_hp == 40 + expected
                    assert cue.start_ms == pytest.approx(node.start_ms + timeline.release_ms)
                    early = sample_choreography(group, cue.start_ms - .01)
                    assert early.displayed.actors[fact.target_entity_uuid].normal_hp == 40
                    for at in (cue.start_ms, cue.start_ms + 50, group.complete_ms - .01):
                        sample = sample_choreography(group, at)
                        assert sample.displayed.actors[fact.target_entity_uuid].normal_hp == 40 + expected
                        assert all(value.flash is None for value in sample.vitals)
                        assert all(body.clip != data.damage_context.bodyClip
                                   for clip in sample.clips for body in clip.sample.bodies)
                    assert sample_choreography(group, cue.start_ms - .01).displayed == early.displayed
                assert not group.damage
                numbers = [track for track in choreography_feedback(group, data, 0) if track.kind == "number"]
                assert len(numbers) == len(expected_targets) and all(track.value == expected for track in numbers)
                if program == "prayer_of_healing":
                    assert after.actors[actors["Unselected"]].normal_hp == 40
            elif program == "thaumaturgy":
                fact = root.root.fact
                assert fact.target_entity_uuid is None and not fact.declared_target_entity_uuids
                node, = group.nodes
                assert isinstance(node.bound, BoundCast)
                timeline = node.bound.timeline
                assert not timeline.applications and timeline.source.ground_target is None
                assert timeline.facing == "NW"
                assert sample_cast(timeline, timeline.release_ms).bodies[0].facing == "NW"
                assert not group.conditions and not group.healing and not group.damage
            else:
                # Exact condition memberships become visible at the parent's contact.
                for condition in group.conditions:
                    if condition.target_uuid != recipient:
                        continue
                    sample = sample_choreography(group, condition.start_ms)
                    assert {member.condition_uuid for member in sample.displayed.actors[recipient].conditions} == {
                        member.condition_uuid for member in condition.after_membership}
                    if condition.start_ms > 0:
                        early = sample_choreography(group, condition.start_ms - .01)
                        assert {member.condition_uuid for member in early.displayed.actors[recipient].conditions} == {
                            member.condition_uuid for member in condition.before_membership}
                        sample_choreography(group, group.complete_ms)
                        assert sample_choreography(group, condition.start_ms - .01).displayed == early.displayed
                    if program == "light":
                        assert sample.displayed.senses is not None and early.displayed.senses is not None
                        assert early.displayed.senses.effective_light_levels[(4, 6)] is LightLevel.DIM_LIGHT
                        assert sample.displayed.senses.effective_light_levels[(4, 6)] is LightLevel.BRIGHT_LIGHT
        appearance = resolve_condition_appearance(after.actors[recipient].conditions, data.condition_recipes, data.condition_media)
        active = {member.behavior_id for member in after.actors[recipient].conditions
                  if member.behavior_id is not None and member.behavior_id in CONDITIONS}
        expected_layers = {f"support.{identity.removeprefix('condition.spell.')}.{depth}"
                           for identity in active for depth in ("back", "front")}
        assert {resolved.layer.assetId for resolved in appearance.layers} == expected_layers
        maximum_layers = max(maximum_layers, len(appearance.layers))
        if program == "light":
            assert state.senses is not None and after.senses is not None
            position = after.actors[recipient].last_visual_position
            assert position is not None
            if active:
                assert after.senses.effective_light_levels[position] is LightLevel.BRIGHT_LIGHT
                witnessed_light = True
                moved_light |= any(isinstance(event.fact, MovementFact) for event in root.events)
            elif witnessed_light:
                assert after.senses.effective_light_levels[position] is LightLevel.DIM_LIGHT
        state = after
    assert cast_count == (5 if program == "stacked" else 1)
    assert not ({member.behavior_id for member in state.actors[recipient].conditions} & CONDITIONS)
    if not healing:
        assert {identity: actor.normal_hp for identity, actor in state.actors.items()} == initial_hp
    if program == "stacked":
        assert maximum_layers == 8
    elif program in ("guidance", "resistance", "shield_of_faith", "light"):
        assert maximum_layers == 2
    elif program == "thaumaturgy":
        assert state.actors[caster].conditions == initial_conditions
    if program == "light":
        assert witnessed_light and moved_light
    assert not BaseObject._registry and EventQueue.event_cursor() == 0


def test_support_gallery_has_all_thirteen_real_scenarios():
    cases = [case for case in load_cases() if "support-batch" in case.tags]
    assert len(cases) == 13
    assert {case.scenario.program for case in cases if isinstance(case.scenario, SupportCase)} == set(PROGRAMS)
    assert {(case.scenario.ranged, case.scenario.miss) for case in cases if isinstance(case.scenario, TrueStrikeCase)} == {
        (False, False), (False, True), (True, False), (True, True)}
    assert all({"paired-observers", "four-corners"} <= set(case.tags) for case in cases)
