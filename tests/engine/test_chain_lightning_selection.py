"""One real cast selects each branch from the primary, never a nearest-neighbor chain."""
import pytest

from dnd.actions import SpellEvent
from dnd.ai.contracts.control import DecisionEpochReason
from dnd.ai.contracts.decision import ExecuteIntent
from dnd.ai.runtime.execution import AIDecisionValidationError, ValidatedExecuteDecision, validate_policy_intent
from dnd.ai.runtime.state_projection import SubjectiveAIStateProjector
from dnd.controller import TurnContext
from dnd.actions_functional import execute_available_action, get_available_actions, register_spell
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import EventPhase, EventQueue, TakeDamageEvent
from dnd.entity import Entity
from dnd.runtime_reset import reset_engine_runtime
from dnd.spells.evocation import ChainLightning
from dnd.spells.abjuration import AntimagicField
from tests.manual.spell_regression_support import create_spell_regression_actor, reset_spell_regression_arena, force_save_result


@pytest.fixture
def scene():
    reset_spell_regression_arena(30, 12)
    caster = create_spell_regression_actor('Caster', (2, 5), 'heroes', spell_slots={6: 2, 7: 2, 8: 2, 9: 2})
    recipients = [create_spell_regression_actor(name, pos, 'monsters') for name, pos in
                  [('Primary', (8, 5)), ('Secondary', (14, 5)), ('Invalid chained target', (20, 5)),
                   ('Other secondary', (9, 8))]]
    for recipient in recipients:
        force_save_result(recipient, 'dexterity', succeeds=False)
    Entity.update_all_entities_senses(max_distance=300)
    register_spell(caster, ChainLightning)
    yield caster, recipients
    reset_engine_runtime()


def choice(caster, target, slot=6):
    row = next(row for row in get_available_actions(caster).entity_actions
               if row.behavior_id == 'spell.chain_lightning' and row.cast_at_level == slot)
    option = next(option for option in row.valid_targets if option.target_uuid == target.uuid)
    return row, option


@pytest.mark.parametrize('slot', [6, 7, 8, 9])
def test_upcast_adds_selected_recipients_not_damage_or_extra_casts(scene, slot):
    caster, (primary, secondary, distant, other) = scene
    row, option = choice(caster, primary, slot)
    assert row.num_projectiles == slot - 2 and row.allow_same_target is False
    assert option.secondary_targets is not None
    offered = {target.target_uuid for target in option.secondary_targets}
    assert secondary.uuid in offered and other.uuid in offered and distant.uuid not in offered and primary.uuid not in offered
    hp = {entity.uuid: entity.get_normal_hp() for entity in (primary, secondary, distant, other)}
    cursor = EventQueue.event_cursor()
    with fixed_dice_faces(*([2] * 100)):
        result = execute_available_action(caster, row, option, extra_target_uuids=[str(secondary.uuid), str(other.uuid)])
    assert isinstance(result, SpellEvent) and result.phase is EventPhase.COMPLETION
    assert caster.action_economy.actions.normalized_score == 0
    assert caster.action_economy.spell_slot_value(slot).normalized_score == 1
    for entity in (primary, secondary, other):
        assert hp[entity.uuid] - entity.get_normal_hp() == 20
    assert distant.get_normal_hp() == hp[distant.uuid]
    events = [event for _, event in EventQueue.iter_events_since(cursor) if event.phase is EventPhase.COMPLETION]
    applications = [event for event in events if isinstance(event, SpellEvent) and event.application is not None]
    assert len(applications) == 3
    assert {event.target_entity_uuid for event in applications} == {primary.uuid, secondary.uuid, other.uuid}
    for index, event in enumerate(applications):
        assert event.propagation is not None and event.application is not None
        assert event.propagation.application_id == event.application.application_id
        assert event.propagation.source.uuid == (caster.uuid if index == 0 else primary.uuid)
        assert event.propagation.target.uuid == event.target_entity_uuid
        assert event.damage_rolls[0].effective_dice_count == 10
    assert len([event for event in events if isinstance(event, TakeDamageEvent)]) == 3


@pytest.mark.parametrize('invalid', ['duplicate', 'chained'])
def test_invalid_secondary_does_not_spend_or_select_a_replacement(scene, invalid):
    caster, (primary, _, distant, _) = scene
    target = primary if invalid == 'duplicate' else distant
    row, option = choice(caster, primary)
    with pytest.raises(ValueError):
        execute_available_action(caster, row, option, extra_target_uuids=[str(target.uuid)])
    result = ChainLightning(source_entity_uuid=caster.uuid, target_entity_uuid=primary.uuid,
                            extra_target_entity_uuids=[target.uuid]).apply()
    assert result is not None and result.canceled
    assert caster.action_economy.actions.normalized_score == 1
    assert caster.action_economy.spell_slot_6.normalized_score == 2


def test_object_is_an_explicit_primary_or_secondary_and_save_halves_only_its_recipient(scene):
    caster, (primary, _, _, _) = scene
    secondary = create_spell_regression_actor('Saved recipient', (12, 7), 'monsters')
    item = build_authored_item('environment.furniture.clay_stove', caster.uuid)
    item.place_on_grid((7, 7))
    Entity.update_all_entities_senses(max_distance=300)
    force_save_result(secondary, 'dexterity', succeeds=True)
    row, option = choice(caster, item)
    assert option.target_kind == 'object'
    hp = secondary.get_normal_hp()
    with fixed_dice_faces(*([2] * 100)):
        result = execute_available_action(caster, row, option, extra_target_uuids=[str(secondary.uuid)])
    assert isinstance(result, SpellEvent) and not result.canceled
    assert secondary.get_normal_hp() == hp - 10
    assert primary.get_normal_hp() == 240


def test_secondary_uses_primary_contact_when_caster_diagonal_crosses_antimagic(scene):
    caster, (primary, _, _, _) = scene
    secondary = create_spell_regression_actor('Corner secondary', (8, 11), 'monsters')
    field_owner = create_spell_regression_actor('Field owner', (5, 8), 'monsters', spell_slots={8: 1})
    field = AntimagicField(source_entity_uuid=field_owner.uuid).apply()
    assert field is not None and not field.canceled
    force_save_result(secondary, 'dexterity', succeeds=False)
    Entity.update_all_entities_senses(max_distance=300)
    row, option = choice(caster, primary)
    assert option.secondary_targets is not None
    assert secondary.uuid in {target.target_uuid for target in option.secondary_targets}
    before = primary.get_normal_hp(), secondary.get_normal_hp()
    cursor = EventQueue.event_cursor()
    with fixed_dice_faces(*([2] * 100)):
        result = execute_available_action(caster, row, option,
            extra_target_uuids=[str(secondary.uuid)])
    assert isinstance(result, SpellEvent) and not result.canceled
    assert primary.get_normal_hp() == before[0] - 20
    assert secondary.get_normal_hp() == before[1] - 20
    applications = [event for _, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, SpellEvent) and event.phase is EventPhase.COMPLETION
        and event.application is not None]
    assert len(applications) == 2
    branch, = (event for event in applications if event.target_entity_uuid == secondary.uuid)
    assert branch.propagation is not None
    assert branch.propagation.source.uuid == primary.uuid
    assert branch.propagation.source.position == primary.position
    assert branch.propagation.target.uuid == secondary.uuid


def test_ai_receives_and_validates_the_same_primary_dependent_branches(scene):
    caster, (primary, secondary, distant, _) = scene
    projector = SubjectiveAIStateProjector(assignment_id="chain-selection", controlled_entity_uuids=(caster.uuid,))
    context = TurnContext(source_entity_uuid=caster.uuid, entity_uuid=caster.uuid)
    state = projector.project_decision(caster, context, reason=DecisionEpochReason.SNAPSHOT)
    row = next(row for row in state.epoch_build.epoch.affordances.all_rows
               if row.targets and row.targets[0].target_uuid == str(primary.uuid)
               and row.targets[0].secondary_targets is not None)
    cursor = EventQueue.event_cursor()
    for targets in ((str(distant.uuid),), (str(primary.uuid),), (str(secondary.uuid), str(secondary.uuid))):
        with pytest.raises(AIDecisionValidationError):
            validate_policy_intent(state, ExecuteIntent(row_id=row.row_id, extra_target_uuids=targets))
    valid = validate_policy_intent(state, ExecuteIntent(row_id=row.row_id, extra_target_uuids=(str(secondary.uuid),)))
    assert isinstance(valid, ValidatedExecuteDecision)
    assert valid.extra_target_uuids == (str(secondary.uuid),)
    assert EventQueue.event_cursor() == cursor and caster.action_economy.actions.normalized_score == 1
