"""Cantrip review inputs preserve real outcomes in both serialized player views."""

import pytest

from dnd.actions import SpellEvent
from dnd.core.base_object import PASSIVE_EVENT_REPLAY, BaseObject
from dnd.core.dice import AttackOutcome
from dnd.core.events import EventQueue, SavingThrowEvent, TakeDamageEvent
from dnd.entity import Entity
from game.player_facts import SpellFact
from game.player_projection import project_sequence
from game.player_reduction import decode_player_sequence, encode_player_sequence, reduce_lineage
from game.replay import RecordedSequence
from tests.game.cantrip_scenarios import cantrip_history


@pytest.mark.parametrize("program,outcome,layout", (
    ("sacred", "hit", "adjacent-axis"), ("sacred", "saved", "adjacent-diagonal"),
    ("sacred", "saved", "range-axis"), ("sacred", "hit", "range-diagonal"),
    ("poison", "hit", "adjacent-axis"), ("poison", "saved", "adjacent-diagonal"),
    ("poison", "saved", "range-axis"), ("poison", "hit", "range-diagonal"),
    ("shocking", "hit", "adjacent-axis"), ("shocking", "miss", "adjacent-diagonal"),
))
def test_real_cantrip_encounters_replay_damage_saves_and_touch_status(program, outcome, layout) -> None:
    captured = cantrip_history(program=program, outcome=outcome, layout=layout)
    assert set(captured.views) == {"caster", "perceiver"}
    native, = [root for root in captured.lineages if isinstance(root.root, SpellEvent)]
    spell = native.root
    assert isinstance(spell, SpellEvent)
    assert spell.behavior_id == {"sacred": "spell.sacred_flame", "shocking": "spell.shocking_grasp",
                                 "poison": "spell.poison_spray"}[program]
    assert spell.source_position is not None and spell.target_entity_uuid is not None
    damage = [event for event in native.events if isinstance(event, TakeDamageEvent)]
    assert len(damage) == int(outcome == "hit")
    assert all(event.target_entity_uuid == spell.target_entity_uuid for event in damage)
    if program == "shocking":
        assert spell.attack_outcome is (AttackOutcome.HIT if outcome == "hit" else AttackOutcome.CRIT_MISS)
    else:
        save, = [event for event in native.events if isinstance(event, SavingThrowEvent)]
        assert save.result is (outcome == "saved") and save.dice_roll is not None
        assert spell.save_success is (outcome == "saved")
    assert not BaseObject._registry and not Entity.get_all_entities() and EventQueue.event_cursor() == 0

    for role, original in captured.views.items():
        restored = RecordedSequence.model_validate_json(original.model_dump_json(), context=PASSIVE_EVENT_REPLAY)
        payload = encode_player_sequence(project_sequence(restored))
        state, roots = decode_player_sequence(payload)
        initial = state.actors[spell.target_entity_uuid]
        assert initial.normal_hp == 60 and not initial.conditions
        observed = []
        for root in roots:
            state = reduce_lineage(state, root)
            if isinstance(root.root.fact, SpellFact):
                observed.append(root.root.fact)
        fact, = observed
        assert fact.behavior_id == spell.behavior_id and fact.source_entity_uuid == spell.source_entity_uuid
        assert fact.target_entity_uuid == spell.target_entity_uuid
        assert fact.attack_outcome is spell.attack_outcome
        target = state.actors[spell.target_entity_uuid]
        assert target.normal_hp == initial.normal_hp - (4 if outcome == "hit" else 0), role
        assert any(condition.name == "No Reactions" for condition in target.conditions) is (
            program == "shocking" and outcome == "hit")
        assert "objective_rows" not in payload.decode() and "identified_entity_observer_uuids" not in payload.decode()
    assert not BaseObject._registry and not Entity.get_all_entities() and EventQueue.event_cursor() == 0
