"""Sanctuary's real ward ownership survives public serialization and playback."""

import pytest

from dnd.core.events import EventType
from game.animation_data import load_animation_data
from game.choreography import bind_choreography, bind_motion
from game.condition_animation import resolve_condition_appearance
from game.condition_media_lifetime import register_condition_lifetimes, sample_condition_lifetimes
from game.condition_sampling import sample_condition_media
from game.player_facts import ConditionChangeFact, DamageFact, SavingThrowFact, SpellFact, TurnFact
from game.player_reduction import reduce_lineage
from tests.game.persistent_spell_scenarios import persistent_spell_history
from tests.game.player_helpers import player_history


@pytest.fixture(scope="module", params=("hostile-break", "expiry", "maintained"))
def history(request):
    return request.param, persistent_spell_history(program="sanctuary",
        ward_expiry=request.param == "expiry", ward_retained=request.param == "maintained")


@pytest.mark.parametrize("role", ("caster", "target"))
def test_saved_ward_blocks_failed_save_keeps_successful_injury_and_removes_causally(history, role):
    ending, captured = history
    state, heads = player_history(captured, role=role)
    warded = next(actor.uuid for actor in state.actors.values() if actor.name == "Caster")
    owner = None
    saves, removals, starts = [], [], 0
    moved = False
    for head in heads:
        after = reduce_lineage(state, head)
        changes = [node.fact for node in head.events if isinstance(node.fact, ConditionChangeFact)
                   and node.fact.condition.behavior_id == "condition.spell.sanctuary"]
        for change in changes:
            if change.event_type is EventType.CONDITION_APPLICATION:
                assert owner is None
                owner = change.condition.condition_uuid
            if change.event_type is EventType.CONDITION_REMOVAL:
                assert change.condition.condition_uuid == owner
                removals.append(head)
        members = [condition for condition in after.actors[warded].conditions
                   if condition.behavior_id == "condition.spell.sanctuary"]
        if members:
            assert len(members) == 1 and members[0].condition_uuid == owner
            moved |= after.actors[warded].last_visual_position == (3, 7)
            assert not any(condition.behavior_id == "condition.concentrating"
                           for condition in after.actors[warded].conditions)
        for node in head.events:
            fact = node.fact
            if owner is not None and isinstance(fact, TurnFact) and fact.entity_uuid == warded:
                starts += fact.event_type is EventType.TURN_START
            if isinstance(fact, SavingThrowFact) and fact.ability_name == "wisdom":
                saves.append(fact.succeeded)
                injuries = [child.fact for child in head.events if isinstance(child.fact, DamageFact)
                            and child.fact.stage == "applied"]
                assert members, "Neither save outcome removes the ward"
                if fact.succeeded:
                    assert not head.root.canceled and len(injuries) == 1
                    assert injuries[0].applied_damage == 6
                    assert injuries[0].body_release is not None
                    assert injuries[0].body_release.release_id == "body.blood"
                    assert after.actors[warded].normal_hp == state.actors[warded].normal_hp - 6
                else:
                    assert head.root.canceled and not injuries
                    assert after.actors[warded].normal_hp == state.actors[warded].normal_hp
        state = after
    assert saves == [False, True] and moved
    retained = ending == "maintained"
    assert len(removals) == (0 if retained else 1)
    assert any(condition.behavior_id == "condition.spell.sanctuary"
               for condition in state.actors[warded].conditions) is retained
    if ending == "expiry":
        assert starts == 10
    elif not retained:
        assert isinstance(removals[0].root.fact, SpellFact)
        assert removals[0].root.fact.behavior_id == "spell.fire_bolt"
    assert any(residue.residue_id == "residue.blood" for tile in state.tiles.values() for residue in tile.residues)


def test_saved_sanctuary_uses_shared_apply_hold_and_real_removal_media(history):
    ending, captured = history
    data = load_animation_data()
    state, heads = player_history(captured, role="caster")
    warded = next(actor.uuid for actor in state.actors.values() if actor.name == "Caster")
    records, clock = {}, 0.
    held_samples = 0
    for head in heads:
        after = reduce_lineage(state, head)
        motion = bind_motion(state, head, data)
        group = None if motion else bind_choreography(state, head, data)
        assert motion is not None or group is not None
        if group is not None:
            assert not group.gaps
            if head.root.canceled:
                assert not group.damage and not group.body_actions
                assert group.nodes and group.nodes[0].interrupted
                assert group.complete_ms > 0
                assert head.root.cancellation is not None
                assert not head.root.cancellation.action_economy_spent
        records = register_condition_lifetimes(records, state, data, absolute_start_ms=clock,
            lineage=head, choreography=group, motion=motion)
        appearances = {str(actor.uuid): resolve_condition_appearance(actor.conditions,
            data.condition_recipes, data.condition_media) for actor in after.actors.values()}
        if any(member.behavior_id == "condition.spell.sanctuary" for member in after.actors[warded].conditions):
            owner, = [record for record in records.values() if record.actor_uuid == warded]
            assert owner.applied_ms is not None and owner.removed_ms is None
            # The ward must keep drawing beyond the old preview's compulsory fade.
            for age in (8000., 60000.):
                sampled = sample_condition_lifetimes(appearances, records, data, owner.applied_ms + age)
                layers = sampled[str(warded)].layers
                assert len(layers) == 2
                assert {layer.layer.drawOrder for layer in layers} == {"behind_body", "in_front_of_body"}
                for layer in layers:
                    media, = sample_condition_media(data, layer)
                    assert media.asset_id.endswith(".hold") and media.alpha > 0
            held_samples += 1
        duration = motion.complete_ms if motion is not None else group.complete_ms if group is not None else 0
        clock += duration + 25
        state = after
    assert held_samples > 0 and records
    retained = ending == "maintained"
    assert all((record.removed_ms is None) is retained for record in records.values())
    later = sample_condition_lifetimes(appearances, records, data, clock + 60000)
    assert bool(later[str(warded)].layers) is retained
