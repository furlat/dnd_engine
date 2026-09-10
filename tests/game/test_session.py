"""Human choices and native decisions share the existing encounter rules."""

import random

import pytest

from dnd.actions import AttackEvent, MovementEvent
from dnd.core.base_conditions import ConditionRemovalEvent
from dnd.core.events import EventPhase, EventQueue, RoundStartEvent, TurnEndEvent, TurnStartEvent
from dnd.encounter import TurnState
from game.session import (
    Operation, Session, advance_controller, close_session, create_session,
    discover_player_actions, end_player_turn, execute_player_action,
)


@pytest.fixture
def session():
    random_state = random.getstate()
    random.seed(0)
    value = create_session()
    try:
        yield value
    finally:
        close_session(value)
        random.setstate(random_state)


def _advance_to_human(session: Session, operations: list[Operation]) -> None:
    for _ in range(32):
        operation = advance_controller(session)
        operations.append(operation)
        assert operation.boundary is not None
        assert operation.boundary.status != "error"
        if operation.boundary.status == "waiting_for_human":
            return
    pytest.fail("native encounter did not return a human decision boundary")


def test_two_players_move_spend_actions_and_receive_native_enemy_turns(session: Session) -> None:
    # Creation is a usable observation baseline before the first AI decision.
    assert session.encounter.turn_state is TurnState.NOT_STARTED
    assert len(session.births) == 4
    assert {birth.entity_uuid for birth in session.births} == set(session.game.entities)
    fighter, sorcerer = (session.game.entities[identity] for identity in session.player_uuids)
    assert (fighter.get_normal_hp(), sorcerer.get_normal_hp()) == (44, 37)
    assert sorcerer.action_economy.get_normal_spell_slot_capacities() == {1: 4, 2: 3, 3: 2}
    assert (fighter.appearance.visual_scale, sorcerer.appearance.visual_scale_x) == (1, 0.9)
    assert all(actor.creation_committed and actor.is_deployed for actor in session.game.entities.values())
    assert not any(isinstance(event, (TurnStartEvent, AttackEvent, MovementEvent))
                   for _, event in EventQueue.iter_events_since(0))

    start = EventQueue.event_cursor()
    operations: list[Operation] = []
    _advance_to_human(session, operations)
    actor = session.encounter.get_current_entity()
    assert actor is not None
    first_player = actor.uuid
    choices = discover_player_actions(session, first_player)
    assert choices.entity_uuid == first_player
    move = next(row for row in choices.position_actions if row.behavior_id == "action.move")
    destination = min(move.valid_targets, key=lambda target: target.path_cost or 0)
    assert destination.path_cost is not None
    movement_before = actor.action_economy.movement.normalized_score
    actions_before = actor.action_economy.actions.normalized_score
    other_player = next(identity for identity in session.player_uuids if identity != first_player)
    cursor_before_rejection = EventQueue.event_cursor()
    with pytest.raises(ValueError, match="current human turn"):
        execute_player_action(session, other_player, move, destination)
    assert EventQueue.event_cursor() == cursor_before_rejection

    movement = execute_player_action(session, first_player, move, destination)
    operations.append(movement)
    assert actor.position == destination.position
    assert actor.action_economy.movement.normalized_score == movement_before - destination.path_cost
    assert actor.action_economy.actions.normalized_score == actions_before
    assert any(isinstance(root, MovementEvent) and root.source_entity_uuid == first_player for root in movement.roots)

    choices = discover_player_actions(session, first_player)
    dodge = next(row for row in choices.self_actions if row.behavior_id == "action.dodge")
    operations.append(execute_player_action(session, first_player, dodge, dodge.valid_targets[0]))
    assert actor.action_economy.actions.normalized_score == actions_before - 1
    operations.append(end_player_turn(session, first_player))
    assert any(isinstance(root, TurnEndEvent) for root in operations[-1].roots)
    cursor_before_rejection = EventQueue.event_cursor()
    with pytest.raises(ValueError, match="current human turn"):
        execute_player_action(session, first_player, move, destination)
    assert EventQueue.event_cursor() == cursor_before_rejection

    _advance_to_human(session, operations)
    next_player = session.encounter.get_current_entity()
    assert next_player is not None and next_player.uuid == other_player
    assert discover_player_actions(session, other_player).entity_uuid == other_player
    operations.append(end_player_turn(session, other_player))
    _advance_to_human(session, operations)
    returned = session.encounter.get_current_entity()
    assert returned is actor and session.encounter.round_number == 2

    roots = tuple(root for operation in operations for root in operation.roots)
    enemy_uuids = set(session.enemy_controller.controlled_entity_uuids)
    assert {root.source_entity_uuid for root in roots if isinstance(root, AttackEvent)} == enemy_uuids
    assert any(isinstance(root, RoundStartEvent) for root in roots)
    assert any(isinstance(root, ConditionRemovalEvent) for root in roots)
    # The application receives every independently terminal root, including the
    # expiry emitted alongside the next turn. Descendants remain in their own
    # parent's lineage rather than becoming extra root deliveries.
    expected = tuple(event.uuid for _, event in EventQueue.iter_events_since(start)
                     if event.parent_lineage is None and event.phase in (EventPhase.COMPLETION, EventPhase.CANCEL))
    assert tuple(root.uuid for root in roots) == expected
    assert all(operation.start_cursor <= operation.end_cursor for operation in operations)


def test_explicit_arrangement_uses_the_same_public_composition() -> None:
    random_state = random.getstate()
    random.seed(1)
    players, enemies = ((5, 4), (7, 4)), ((5, 8), (7, 8))
    session = create_session(player_positions=players, enemy_positions=enemies)
    try:
        assert tuple(session.game.entities[identity].position for identity in session.player_uuids) == players
        assert tuple(session.game.entities[identity].position
                     for identity in session.enemy_controller.controlled_entity_uuids) == enemies
        assert session.battlefield.definition.battlefield_id == "battlefield.open_floor_bright"
        assert session.encounter.turn_state is TurnState.NOT_STARTED
        for player_uuid in session.player_uuids:
            actor = session.game.entities[player_uuid]
            assert all(actor.senses.entities[enemy_uuid].visual
                       for enemy_uuid in session.enemy_controller.controlled_entity_uuids)
    finally:
        close_session(session)
        random.setstate(random_state)
