"""Discovered creature-plus-landing choices reach the ordinary native command."""
import pytest

from dnd.actions_functional import execute_available_action, get_available_actions, get_extra_position_options, register_spell
from dnd.core.events import EventQueue
from dnd.ai.contracts.control import DecisionEpochReason
from dnd.ai.contracts.decision import ExecuteIntent
from dnd.ai.runtime.execution import AIDecisionValidationError, ValidatedExecuteDecision, validate_policy_intent
from dnd.ai.runtime.state_projection import SubjectiveAIStateProjector
from dnd.controller import TurnContext
from dnd.spells.transmutation import Telekinesis
from tests.engine.test_telekinesis_landing import scene as scene


def choice(caster, target, behavior):
    choices = get_available_actions(caster)
    row = next(row for row in choices.entity_actions if row.behavior_id == behavior)
    recipient = next(option for option in row.valid_targets if option.target_uuid == target.uuid)
    return choices, row, recipient


def test_discovered_initial_and_repeat_require_and_pay_for_one_selected_landing(scene):
    caster, target = scene
    target.faction = caster.faction
    register_spell(caster, Telekinesis)
    for behavior, destination in (("spell.telekinesis", (7, 2)), ("action.spell.telekinesis.move", (8, 2))):
        caster.action_economy.reset_all_costs()
        _, row, recipient = choice(caster, target, behavior)
        assert row.position_selection is not None and row.position_selection.kind == "entity_destination"
        cursor = EventQueue.event_cursor()
        options = get_extra_position_options(caster, row, recipient)
        assert destination in options and (20, 2) not in options and caster.position not in options
        assert EventQueue.event_cursor() == cursor
        with pytest.raises(ValueError, match="destination"):
            execute_available_action(caster, row, recipient)
        assert caster.action_economy.actions.normalized_score == 1
        result = execute_available_action(caster, row, recipient, extra_target_positions=[destination])
        assert result is not None and not result.canceled
        assert target.position == destination
        assert caster.action_economy.actions.normalized_score == 0
        assert caster.action_economy.spell_slot_5.normalized_score == 1


def test_discovered_destination_revalidates_after_target_moves(scene):
    caster, target = scene
    target.faction = caster.faction
    register_spell(caster, Telekinesis)
    _, row, recipient = choice(caster, target, "spell.telekinesis")
    destination = (4, 3)
    assert destination in get_extra_position_options(caster, row, recipient)
    target.move((12, 2))
    result = execute_available_action(caster, row, recipient, extra_target_positions=[destination])
    assert result is not None and result.canceled
    assert target.position == (12, 2)
    assert caster.action_economy.actions.normalized_score == 1
    assert caster.action_economy.spell_slot_5.normalized_score == 2


def test_typed_ai_destination_intent_uses_same_native_options(scene):
    caster, target = scene
    target.faction = caster.faction
    register_spell(caster, Telekinesis)
    projector = SubjectiveAIStateProjector(assignment_id="landing-test", controlled_entity_uuids=(caster.uuid,))
    context = TurnContext(source_entity_uuid=caster.uuid, entity_uuid=caster.uuid)
    state = projector.project_decision(caster, context, reason=DecisionEpochReason.SNAPSHOT)
    row = next(row for row in state.epoch_build.epoch.affordances.all_rows
        if row.position_selection is not None and row.position_selection.kind == "entity_destination"
        and row.targets[0].target_uuid == str(target.uuid))
    cursor = EventQueue.event_cursor()
    for points in ((), ((7, 2), (8, 2)), ((20, 2),)):
        with pytest.raises(AIDecisionValidationError):
            validate_policy_intent(state, ExecuteIntent(row_id=row.row_id, extra_target_positions=points))
    valid = validate_policy_intent(state, ExecuteIntent(row_id=row.row_id, extra_target_positions=((7, 2),)))
    assert isinstance(valid, ValidatedExecuteDecision)
    assert valid.extra_target_positions == ((7, 2),)
    assert EventQueue.event_cursor() == cursor and caster.action_economy.actions.normalized_score == 1
