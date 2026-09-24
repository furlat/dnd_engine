"""Real discovered support actions remain sufficient for cold public replay."""

import pytest
from dataclasses import replace

from dnd.core.base_object import BaseObject, PASSIVE_EVENT_REPLAY
from dnd.core.events import EventQueue, EventType
from game.animation_data import load_animation_data
from game.animation import sample_cast
from game.cast_media import cast_media_draw_commands
from game.choreography import bind_choreography, bind_motion, sample_choreography
from game.combat import BoundCast
from game.player_facts import ConditionChangeFact, DamageFact, HealFact, MovementFact, SpellFact
from game.condition_animation import resolve_condition_appearance
from game.condition_media_lifetime import register_condition_lifetimes, sample_condition_lifetimes
from game.condition_sampling import sample_condition_media
from game.projection import Camera
from game.player_projection import project_sequence
from game.player_reduction import decode_player_sequence, encode_player_sequence, reduce_lineage
from game.replay import RecordedSequence
from tests.game.healing_batch_scenarios import SPELLS, healing_batch_history
from tests.game.test_projectile_media import display as display


@pytest.fixture(scope="module", params=tuple(SPELLS))
def captured(request):
    return request.param, healing_batch_history(program=request.param)


def public_sequence(recorded):
    retained = RecordedSequence.model_validate_json(recorded.model_dump_json(), context=PASSIVE_EVENT_REPLAY)
    return decode_player_sequence(encode_player_sequence(project_sequence(retained)))


@pytest.mark.parametrize("role", ("caster", "recipient"))
def test_native_outcomes_and_selected_recipients_survive_cold_replay(captured, role):
    program, history = captured
    state, roots = public_sequence(history.views[role])
    initial = {actor.name: actor for actor in state.actors.values()}
    assert not BaseObject._registry and EventQueue.event_cursor() == 0
    observed_aid = False
    for root in roots:
        assert not any(isinstance(node.fact, DamageFact) for node in root.events)
        state = reduce_lineage(state, root)
        actors = {actor.name: actor for actor in state.actors.values()}
        if isinstance(root.root.fact, SpellFact):
            if program == "aid":
                observed_aid = True
                for name in ("Recipient", "Second", "Third"):
                    assert (actors[name].normal_hp, actors[name].maximum_hp) == (initial[name].normal_hp + 5, 125)
                assert actors["Bystander"].conditions == initial["Bystander"].conditions
                assert not any(isinstance(node.fact, HealFact) for node in root.events)
            elif program in ("lesser_restoration", "greater_restoration"):
                assert all(row.name != "Poisoned" for row in actors["Recipient"].conditions)
                assert actors["Recipient"].normal_hp == initial["Recipient"].normal_hp
            elif program in ("heal", "mass_heal"):
                assert actors["Recipient"].normal_hp == 120
                assert all(row.name != "Deafened" for row in actors["Recipient"].conditions)
            else:
                assert actors["Recipient"].normal_hp == 101
            if program.startswith("mass_"):
                assert actors["Second"].normal_hp == 120  # actual capped healing
                assert actors["Bystander"].normal_hp == initial["Bystander"].normal_hp
    if program == "aid":
        assert observed_aid
        for name in ("Recipient", "Second", "Third"):
            assert (actors[name].normal_hp, actors[name].maximum_hp) == (initial[name].normal_hp, 120)
            assert all(row.name != "Aid" for row in actors[name].conditions)


@pytest.fixture(scope="module")
def data():
    return load_animation_data()


@pytest.mark.parametrize("role", ("caster", "recipient"))
def test_shared_cast_contacts_have_real_outcomes_without_damage_reactions(captured, data, role):
    program, history = captured
    state, roots = public_sequence(history.views[role])
    for root in roots:
        group = bind_choreography(state, root, data)
        assert not group.gaps, (program, role, group.gaps)
        assert not group.damage
        if isinstance(root.root.fact, SpellFact):
            if program == "aid":
                body, = group.body_actions
                assert body.recipe_id == "spell.aid" and body.clip == "Special1"
                assert len(group.conditions) == 3 and not group.healing
                for transition in group.conditions:
                    target = transition.target_uuid
                    assert transition.start_ms == body.effect_ms
                    assert sample_choreography(group, transition.start_ms - .01).displayed.actors[target].maximum_hp == 120
                    at = sample_choreography(group, transition.start_ms).displayed.actors[target]
                    assert at.maximum_hp == 125 and at.normal_hp == state.actors[target].normal_hp + 5
                state = reduce_lineage(state, root)
                continue
            cast, = (node for node in group.nodes if isinstance(node.bound, BoundCast))
            assert isinstance(cast.bound, BoundCast)
            timeline = cast.bound.timeline
            assert timeline.recipe.definitionRef.content_id == "spell." + program
            expected = {str(node.fact.target_entity_uuid) for node in root.events
                        if isinstance(node.fact, (HealFact, ConditionChangeFact))}
            recipients = {app.source.target.actor_uuid for app in timeline.applications}
            assert recipients == expected
            for healing in group.healing:
                fact = healing.event.fact
                assert isinstance(fact, HealFact)
                assert fact.resulting_normal_hp is not None
                early = sample_choreography(group, healing.start_ms - .01)
                contact = sample_choreography(group, healing.start_ms)
                assert contact.displayed.actors[fact.target_entity_uuid].normal_hp == fact.resulting_normal_hp
                assert not any(value.flash is not None for value in contact.vitals)
                if fact.actual_healing:
                    assert early.displayed.actors[fact.target_entity_uuid].normal_hp < fact.resulting_normal_hp
            assert all(body.clip != data.damage_context.bodyClip for at in (timeline.release_ms, group.complete_ms / 2)
                       for clip in sample_choreography(group, at).clips for body in clip.sample.bodies)
            if program == "mass_cure_wounds":
                assert timeline.source.ground_target is not None
                # AoE targeting does not turn recipient curtains into a ground
                # propagation volume or stamp their pixels onto nearby walls.
                sample = sample_cast(timeline, timeline.release_ms + 1000)
                for q in range(4):
                    commands = cast_media_draw_commands(timeline, sample, Camera(quadrant=q), None, {})
                    assert commands and all(command.area is None and command.volume is None for command in commands)
        state = reduce_lineage(state, root)


@pytest.mark.parametrize("program", ("lesser_restoration", "greater_restoration", "heal"))
def test_self_target_and_clean_restoration_remain_native_successes(program, data):
    history = healing_batch_history(program=program, self_target=True, clean_target=True)
    state, roots = public_sequence(history.views["caster"])
    root = next(row for row in roots if isinstance(row.root.fact, SpellFact))
    group = bind_choreography(state, root, data)
    assert not group.gaps
    assert not any(isinstance(node.fact, ConditionChangeFact) and node.fact.event_type is EventType.CONDITION_REMOVAL
                   for node in root.events)
    after = reduce_lineage(state, root)
    assert next(actor for actor in after.actors.values() if actor.name == "Caster").normal_hp == (120 if program == "heal" else 85)


def test_aid_membership_loop_survives_movement_and_fades_from_its_current_phase(data):
    history = healing_batch_history(program="aid")
    state, roots = public_sequence(history.views["recipient"])
    records, clock, starts, removals, movement = {}, 0., {}, set(), False
    def appearances(snapshot):
        return {str(actor.uuid): resolve_condition_appearance(actor.conditions, data.condition_recipes,
                                                             data.condition_media) for actor in snapshot.actors.values()}
    for root in roots:
        motion = bind_motion(state, root, data) if isinstance(root.root.fact, MovementFact) else None
        group = bind_choreography(state, root, data) if motion is None else None
        after = reduce_lineage(state, root)
        records = register_condition_lifetimes(records, state, data, absolute_start_ms=clock,
            lineage=root, choreography=group, motion=motion)
        for owner, record in records.items():
            assert record.applied_ms is not None
            starts.setdefault(owner, record.applied_ms)
            assert record.applied_ms == starts[owner]
            if motion is not None:
                movement = True
            if record.removed_ms is not None and owner not in removals:
                removals.add(owner)
                fade = data.condition_media["healing.aid.back"].removal_fade_ms
                at = record.removed_ms + fade / 2
                sampled = sample_condition_lifetimes(appearances(after), records, data, at)
                layers = [layer for layer in sampled[str(record.actor_uuid)].layers if layer.owner_uuid == owner]
                assert len(layers) == 2 and all(layer.alpha == pytest.approx(.5) for layer in layers)
                for layer in layers:
                    expected = sample_condition_media(data, replace(layer, alpha=1))
                    actual = sample_condition_media(data, layer)
                    assert [(part.asset_id, part.frame) for part in actual] == [(part.asset_id, part.frame) for part in expected]
                    assert all(part.alpha == pytest.approx(other.alpha / 2) for part, other in zip(actual, expected))
                gone = sample_condition_lifetimes(appearances(after), records, data, record.removed_ms + fade)
                assert all(layer.owner_uuid != owner for layer in gone[str(record.actor_uuid)].layers)
        assert motion is not None or group is not None
        clock += motion.complete_ms if motion is not None else group.complete_ms if group is not None else 0
        state = after
    assert movement and len(starts) == len(removals) == 3


def test_aid_application_crossfade_has_its_own_hold_origin_and_quiet_reacquisition(data):
    history = healing_batch_history(program="aid")
    state, roots = public_sequence(history.views["caster"])
    applied = reduce_lineage(state, roots[0])
    recipient = next(actor for actor in applied.actors.values() if actor.name == "Recipient")
    appearance = resolve_condition_appearance(recipient.conditions, data.condition_recipes, data.condition_media)
    layer, _ = appearance.layers
    media = layer.media
    start, end = media.application_fade_ms
    at = (start + end) / 2
    samples = sample_condition_media(data, replace(layer, age_ms=at, application=True))
    application, hold = samples
    assert application.asset_id == media.application_asset_id and application.alpha == pytest.approx(.5)
    assert hold.asset_id == media.asset_id and hold.alpha == pytest.approx(.5)
    assert hold.frame == 2  # midpoint of the unchanged 152.78 ms overlap at 32 FPS
    period = 4000  # The authored hold still takes four seconds to wrap.
    first, = sample_condition_media(data, replace(layer, age_ms=end + 1, application=True))
    later, = sample_condition_media(data, replace(layer, age_ms=end + 1 + period, application=True))
    assert first == later
    quiet, = sample_condition_media(data, replace(layer, age_ms=1000, application=False))
    assert quiet.asset_id == media.asset_id and quiet.frame == 32 and quiet.alpha == 1


def test_repeated_aid_uses_completion_stats_after_replacing_old_modifiers():
    history = healing_batch_history(program="aid", repeat_aid=True)
    for recorded in history.views.values():
        state, roots = public_sequence(recorded)
        casts = 0
        for root in roots:
            state = reduce_lineage(state, root)
            if isinstance(root.root.fact, SpellFact):
                casts += 1
                target = next(actor for actor in state.actors.values() if actor.name == "Recipient")
                assert (target.normal_hp, target.maximum_hp) == (90, 125)
                assert sum(member.name == "Aid" for member in target.conditions) == 1
        assert casts == 2
