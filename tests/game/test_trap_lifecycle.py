"""The review videos and acceptance tests share the user's exact action narrative."""

from typing import Literal

import pytest

from dnd.core.base_object import PASSIVE_EVENT_REPLAY
from dnd.core.events import EventQueue, EventType
from dnd.entity import Entity
from dnd.types.traps import TrapState
from game.player_facts import ActionFact, ConditionChangeFact, DamageFact, MovementFact, SpatialEffectStateFact
from game.player_projection import project_sequence
from game.player_reduction import decode_player_sequence, encode_player_sequence, reduce_lineage
from game.replay import RecordedSequence
from tests.game.trap_scenarios import TRAP_CONTENT, trap_history


@pytest.mark.parametrize("detected,payload,save_face", [
    (False, "plain", 1), (True, "plain", 1),
    (False, "poison-damage", 1), (True, "poison-damage", 1),
    (False, "poisoned", 1), (True, "poisoned", 1), (True, "poisoned", 20),
])
def test_full_trap_narrative_from_both_players_saved_events(
    detected: bool, payload: Literal["plain", "poison-damage", "poisoned"], save_face: Literal[1, 20],
) -> None:
    history = trap_history(detected=detected, payload=payload, save_face=save_face)
    walker = history.views["walker"].initialization.observer_uuid
    operator = history.views["operator"].initialization.observer_uuid
    hit = 6 if payload == "poison-damage" else 4
    # (real action, walker position, damage in this action, resulting trap state)
    expected = [
        ("move", (5, 3), hit, TrapState.ACTIVATED),  # First entry, raises exactly once.
        ("move", (6, 3), 0, TrapState.ACTIVATED),
        ("move", (5, 3), hit, TrapState.ACTIVATED),  # Back into already-up spikes.
        ("move", (4, 3), 0, TrapState.ACTIVATED),
        ("lever", (4, 3), 0, TrapState.DEACTIVATED),
        ("move", (5, 3), 0, TrapState.DEACTIVATED),
        ("move", (6, 3), 0, TrapState.DEACTIVATED),
        ("move", (5, 3), 0, TrapState.DEACTIVATED),  # Stay inside while disabled.
        ("lever", (5, 3), hit, TrapState.ACTIVATED),  # Other actor raises beneath walker.
        ("move", (6, 3), 0, TrapState.ACTIVATED),
    ]
    for role, native in history.views.items():
        restored = RecordedSequence.model_validate_json(native.model_dump_json(), context=PASSIVE_EVENT_REPLAY)
        state, roots = decode_player_sequence(encode_player_sequence(project_sequence(restored)))
        assert state.senses is not None
        assert bool(state.senses.spatial_effects) is (detected and role == "walker")
        original_hp = state.actors[walker].normal_hp
        observed = []
        transitions = []
        applied_poison = False
        for root in roots:
            previous_hp = state.actors[walker].normal_hp
            state = reduce_lineage(state, root)
            for node in root.events:
                if isinstance(node.fact, SpatialEffectStateFact):
                    transitions.append((node.fact.previous_state, node.fact.state))
                    assert node.fact.positions == ((5, 3),)
                if isinstance(node.fact, ConditionChangeFact) and node.fact.condition.name == "Poisoned":
                    applied_poison |= node.fact.event_type is EventType.CONDITION_APPLICATION
            fact = root.root.fact
            action = "move" if isinstance(fact, MovementFact) else (
                "lever" if isinstance(fact, ActionFact) and fact.behavior_id == "action.environment.trap_lever.pull" else None)
            if action is None:
                continue
            assert not root.root.canceled
            if action == "lever":
                assert isinstance(fact, ActionFact) and fact.source_entity_uuid == operator
            assert state.senses is not None
            effect, = state.senses.spatial_effects.values()
            assert effect.content_ref == TRAP_CONTENT[payload]
            damage = previous_hp - state.actors[walker].normal_hp
            packets = [node.fact for node in root.events
                if isinstance(node.fact, DamageFact) and node.fact.stage == "applied"]
            assert sum(packet.applied_damage or 0 for packet in packets) == damage
            observed.append((action, state.actors[walker].last_visual_position, damage, effect.trap_state))
        assert observed == expected, role
        assert state.actors[walker].normal_hp == original_hp - 3 * hit
        assert transitions == [(TrapState.READY, TrapState.ACTIVATED),
            (TrapState.ACTIVATED, TrapState.DEACTIVATED), (TrapState.DEACTIVATED, TrapState.ACTIVATED)]
        assert applied_poison is (payload == "poisoned" and save_face == 1)
    assert EventQueue.event_cursor() == 0 and not Entity.get_all_entities()
