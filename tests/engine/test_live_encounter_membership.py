"""Live initiative changes preserve the acting creature and its turn budget."""

from uuid import uuid4

import pytest

from dnd.ai.runtime.assignment_lifecycle import AIDecisionBudget, assignment_turn_key
from dnd.actions import Move
from dnd.actions_functional import setup_standard_actions
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.core.equipment_types import WeaponSlot
from dnd.controller import HumanController
from dnd.core.events import EventPhase, EventQueue, EventType
from dnd.encounter import Encounter, EncounterState, TurnState
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.runtime_reset import reset_engine_runtime
from dnd.reactions import add_opportunity_attack_handler


@pytest.fixture(autouse=True)
def reset():
    reset_engine_runtime(grid_size=(12, 12))
    yield
    reset_engine_runtime(grid_size=(12, 12))


def battle():
    game = Game()
    actors = []
    encounter = Encounter(source_entity_uuid=uuid4(), name="Living membership")
    for i, faction in enumerate(("party", "party", "enemy", "enemy")):
        actor = Entity.create(source_entity_uuid=uuid4(), name=f"Actor {i}",
                              config=EntityConfig(position=(i + 1, 2), faction=faction))
        actor.compose_entity()
        game.deploy_entity(actor, actor.position)
        encounter.add_combatant(actor, HumanController(source_entity_uuid=actor.uuid))
        actors.append(actor)
    encounter.initiative_order = [actor.uuid for actor in actors]
    encounter.start_encounter()
    encounter.start_turn()
    return game, encounter, actors


def test_live_join_before_current_keeps_turn_and_ai_budget():
    game, encounter, (anchor, acting, *_) = battle()
    encounter.next_turn()
    original = encounter.build_current_turn_context()
    budget = AIDecisionBudget(10, 3)
    budget.reset_for_turn(assignment_turn_key(acting, original))
    budget.begin_decision()
    acting.action_economy.consume("actions", 1, "Already acted")
    joins = []
    for offset in (0, 1):
        incoming = Entity.create(source_entity_uuid=uuid4(), name="New ally",
            config=EntityConfig(position=(6 + offset, 2), faction="party"))
        controller = HumanController(source_entity_uuid=incoming.uuid)
        join = encounter.prepare_combatant_join(incoming, controller, after_uuid=anchor.uuid)
        assert incoming.uuid not in encounter.combatants
        incoming.compose_entity()
        game.deploy_entity(incoming, incoming.position)
        encounter.commit_combatant_join(join)
        encounter.commit_combatant_join(join)
        joins.append(incoming)
    current = encounter.build_current_turn_context()
    assert encounter.get_current_entity() is acting
    assert current.turn_index == original.turn_index + 2
    assert current.turn_execution_id == original.turn_execution_id
    assert not budget.reset_for_turn(assignment_turn_key(acting, current))
    assert budget.turn_decisions == 1
    assert acting.action_economy.actions.normalized_score == 0
    assert encounter.initiative_order[:4] == [anchor.uuid, *(a.uuid for a in joins), acting.uuid]


def test_departure_before_current_does_not_change_turn_identity():
    _, encounter, (before, acting, *_) = battle()
    encounter.next_turn()
    turn = encounter.current_turn_execution_id
    with encounter.membership_execution():
        encounter.request_combatant_leave(before.uuid)
        assert before.uuid in encounter.initiative_order
        assert not before.can_take_actions()
    assert encounter.get_current_entity() is acting
    assert encounter.current_turn_index == 0 and encounter.current_turn_execution_id == turn
    assert encounter.turn_state is TurnState.IN_PROGRESS


def test_current_departure_ends_once_and_does_not_skip_successor():
    _, encounter, (first, successor, *_) = battle()
    with encounter.membership_execution():
        encounter.request_combatant_leave(first.uuid)
        encounter.request_combatant_leave(first.uuid)
        assert encounter.get_current_entity() is first
        assert not first.can_take_actions()
    ends = [event for event in EventQueue.get_events_by_type(EventType.TURN_END)
            if event.phase is EventPhase.COMPLETION and event.entity_uuid == first.uuid]
    assert len(ends) == 1
    assert encounter.current_turn_execution_id is None
    encounter.next_turn()
    assert encounter.get_current_entity() is successor
    assert encounter.turn_state is TurnState.IN_PROGRESS


def test_future_departure_preserves_immediate_successor():
    _, encounter, (first, successor, later, _) = battle()
    encounter.request_combatant_leave(later.uuid)
    encounter.finish_combatant_leaves()
    assert encounter.get_current_entity() is first
    encounter.next_turn()
    assert encounter.get_current_entity() is successor
    assert encounter.state is EncounterState.ACTIVE


@pytest.mark.parametrize("advance", ("next_turn", "advance_one_controller_action_boundary"))
def test_last_current_departure_wraps_once_to_next_round(advance):
    _, encounter, actors = battle()
    for _ in range(3):
        encounter.next_turn()
    assert encounter.get_current_entity() is actors[-1]
    round_before = encounter.round_number
    encounter.request_combatant_leave(actors[-1].uuid)
    encounter.finish_combatant_leaves()
    if advance == "next_turn":
        encounter.next_turn()
    else:
        result = encounter.advance_one_controller_action_boundary()
        assert result.status == "waiting_for_human"
    assert encounter.get_current_entity() is actors[0]
    assert encounter.round_number == round_before + 1


def test_pending_departure_cannot_react_before_membership_unwinds():
    _, encounter, (departing, _, mover, _) = battle()
    Entity.update_entity_position(mover, (1, 3))
    setup_standard_actions(departing)
    setup_standard_actions(mover)
    weapon = build_authored_item("weapon.longsword", departing.uuid)
    assert departing.loot_item(weapon)
    assert departing.equip_item(weapon.uuid, WeaponSlot.MELEE_MAIN)
    add_opportunity_attack_handler(departing)
    Entity.update_all_entities_senses()
    assert mover.position in departing.senses.get_threathened_positions()
    hp = mover.get_hp()
    with encounter.membership_execution():
        encounter.request_combatant_leave(departing.uuid)
        assert departing.uuid in encounter.combatants
        event = Move(source_entity_uuid=mover.uuid, end_position=(1, 4)).apply()
        assert event is not None and not event.canceled
        assert mover.position == (1, 4)
        assert mover.get_hp() == hp
        assert departing.action_economy.reactions.normalized_score == 1
    assert not any(event.phase is EventPhase.COMPLETION and event.source_entity_uuid == departing.uuid
                   for event in EventQueue.get_events_by_type(EventType.ATTACK))
