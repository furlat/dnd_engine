"""Saved paired views preserve actual light and linked-trap consequences."""

from typing import Literal

import pytest

from dnd.core.base_object import PASSIVE_EVENT_REPLAY
from dnd.core.events import EventQueue
from dnd.entity import Entity
from game.player_facts import MovementFact, StepFact
from game.player_projection import project_sequence
from game.player_reduction import decode_player_sequence, encode_player_sequence, reduce_lineage
from game.replay import RecordedSequence
from tests.game.environment_scenarios import environment_history


def saved_player_view(native: RecordedSequence):
    restored = RecordedSequence.model_validate_json(
        native.model_dump_json(), context=PASSIVE_EVENT_REPLAY,
    )
    return decode_player_sequence(encode_player_sequence(project_sequence(restored)))


@pytest.mark.parametrize("fixture_kind, darkvision, second_light", [
    ("standing", False, False), ("wall", False, False),
    ("standing", True, False), ("standing", False, True),
])
def test_fixed_lights_replay_real_state_and_observer_specific_visibility(
    fixture_kind: Literal["standing", "wall"], darkvision: bool, second_light: bool,
) -> None:
    history = environment_history(fixture_kind=fixture_kind,
        observer_darkvision=darkvision, second_light=second_light)
    operator_uuid = history.views["operator"].initialization.observer_uuid
    assert EventQueue.event_cursor() == 0 and not Entity.get_all_entities()
    for role, native in history.views.items():
        state, roots = saved_player_view(native)
        position = (6, 5) if fixture_kind == "standing" else (6, 8)
        fixture_uuid = next(identity for identity, obj in state.objects.items()
                            if obj.placement.position == position)
        assert state.objects[fixture_uuid].item.is_lit is True
        assert state.senses is not None
        lit = [True]
        visible = [operator_uuid in state.senses.entities]
        owned_steps_while_unlit = 0
        for root in roots:
            state = reduce_lineage(state, root)
            assert state.senses is not None
            is_lit = state.objects[fixture_uuid].item.is_lit
            assert is_lit is not None
            if is_lit != lit[-1]:
                lit.append(is_lit)
            sees_operator = operator_uuid in state.senses.entities
            if sees_operator != visible[-1]:
                visible.append(sees_operator)
            if not is_lit:
                owned_steps_while_unlit += sum(
                    isinstance(node.fact, StepFact)
                    and node.fact.source_entity_uuid == state.observer_uuid
                    for node in root.events
                )
        assert lit == [True, False, True], role
        assert owned_steps_while_unlit == 2, role
        if role == "witness":
            assert visible == ([True] if darkvision or second_light else [True, False, True])
    assert EventQueue.event_cursor() == 0 and not Entity.get_all_entities()


def test_lever_replay_shows_damage_before_pull_safe_recross_and_unrelated_live_trap() -> None:
    history = environment_history(program="lever")
    witness_uuid = history.views["witness"].initialization.observer_uuid
    assert [row.root.uuid for row in history.views["operator"].lineages] == [
        row.root.uuid for row in history.views["witness"].lineages
    ]
    for role, native in history.views.items():
        state, roots = saved_player_view(native)
        assert state.senses is not None
        assert state.senses.hazardous_cells[(5, 1)]
        assert state.senses.hazardous_cells[(7, 1)]
        moves = []
        for root in roots:
            previous_hp = state.actors[witness_uuid].normal_hp
            state = reduce_lineage(state, root)
            if isinstance(root.root.fact, MovementFact) and root.root.fact.source_entity_uuid == witness_uuid:
                assert state.senses is not None
                position = (state.senses.position if role == "witness"
                            else state.senses.entities[witness_uuid].position)
                moves.append((position, state.actors[witness_uuid].normal_hp - previous_hp))
        assert moves == [((5, 1), -4), ((4, 1), 0), ((5, 1), 0), ((7, 1), -4)], role
        assert state.senses is not None
        assert not state.senses.hazardous_cells[(5, 1)]
        assert state.senses.hazardous_cells[(7, 1)]
    assert EventQueue.event_cursor() == 0 and not Entity.get_all_entities()
