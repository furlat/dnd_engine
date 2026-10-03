"""BG3 Call Lightning through native actions, turn clocks and emitted results."""
import pytest

from dnd.actions import Move, SpellEvent
from dnd.actions_functional import execute_available_action, get_available_actions
from dnd.conditions import Blinded
from dnd.classes.fighter import ActionSurge, ActionSurgeFeature, ExtraAttackFeature
from dnd.core.action_types import HasteActionPolicy
from dnd.core.base_conditions import ConditionApplicationEvent
from dnd.core.creature_types import DamageType
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import Event, EventHandler, EventPhase, EventType, Trigger
from dnd.entity import Entity
from dnd.spells.conjuration import CallLightning
from dnd.spells.transmutation import HasteEffect
from tests.manual.spell_regression_support import create_spell_regression_actor, force_save_result, reset_spell_regression_arena


def arena(*, slot_level=3):
    reset_spell_regression_arena(24, 12)
    caster = create_spell_regression_actor('Storm caster', (2, 5), 'heroes', spell_slots={slot_level: 2})
    targets = [create_spell_regression_actor(name, point, faction) for name, point, faction in (
        ('Center', (7, 5), 'monsters'), ('Neighbor', (8, 5), 'monsters'),
        ('Ally in area', (7, 6), 'heroes'), ('Outside', (10, 5), 'monsters'))]
    for target in targets:
        force_save_result(target, 'dexterity', succeeds=target is targets[1])
    Entity.update_all_entities_senses(max_distance=120)
    return caster, targets


def test_initial_and_repeat_strike_hit_every_area_occupant_once_and_preserve_outsider():
    caster, targets = arena()
    before = [target.get_normal_hp() for target in targets]
    with fixed_dice_faces(*([4] * 100)):
        cast = CallLightning(source_entity_uuid=caster.uuid, end_position=(7, 5), cast_at_level=3).apply()
    assert isinstance(cast, SpellEvent) and not cast.canceled
    after = [target.get_normal_hp() for target in targets]
    losses = [a-b for a,b in zip(before, after)]
    assert losses[0] > 0 and losses[1] == losses[0] // 2 and losses[2] == losses[0]
    assert losses[3] == 0
    assert cast.total_targets == 3
    assert len([action for action in caster.registered_actions if action.name == 'Call Lightning Strike']) == 1
    strike = caster.get_action_template('Call Lightning Strike')
    assert strike is not None
    caster.action_economy.reset_all_costs()
    with fixed_dice_faces(*([4] * 100)):
        repeated = strike.instantiate(end_position=(7, 5)).apply()
    assert repeated is not None and not repeated.canceled
    assert [a-target.get_normal_hp() for a,target in zip(after, targets)] == losses
    assert caster.action_economy.actions.normalized_score == 0
    caster.remove_condition('Concentrating')
    assert caster.get_action_template('Call Lightning Strike') is None
    caster.action_economy.reset_all_costs()
    rejected = strike.instantiate(end_position=(7, 5)).apply()
    assert rejected is not None and rejected.canceled


def test_empty_initial_strike_still_grants_one_repeat_action():
    caster, targets = arena()
    before = [target.get_normal_hp() for target in targets]
    with fixed_dice_faces(*([4] * 100)):
        result = CallLightning(source_entity_uuid=caster.uuid, end_position=(12, 8), cast_at_level=3).apply()
    assert result is not None and not result.canceled
    assert [target.get_normal_hp() for target in targets] == before
    assert caster.get_action_template('Call Lightning Strike') is not None
    assert 'Concentrating' in caster.active_conditions


@pytest.mark.parametrize('slot_level', (3, 5))
def test_bg3_cast_and_activation_share_geometry_spell_results_and_upcast_level(slot_level):
    caster, targets = arena(slot_level=slot_level)
    before = [target.get_normal_hp() for target in targets]
    with fixed_dice_faces(*([4] * 100)):
        initial = CallLightning(source_entity_uuid=caster.uuid, end_position=(7, 5), cast_at_level=slot_level).apply()
    assert isinstance(initial, SpellEvent) and not initial.canceled
    assert initial.range_ft == 60 and initial.aoe_radius_ft == 7
    assert initial.cast_at_level == slot_level
    assert caster.has_spell_slot(slot_level)
    strike = caster.get_action_template('Call Lightning Strike')
    assert strike is not None
    caster.on_turn_start()
    with fixed_dice_faces(*([4] * 100)):
        repeated = strike.instantiate(end_position=(7, 5)).apply()
    assert isinstance(repeated, SpellEvent) and not repeated.canceled
    assert repeated.range_ft == 60 and repeated.aoe_radius_ft == 7
    assert repeated.cast_at_level == slot_level and repeated.area_geometry == initial.area_geometry
    assert [value-target.get_normal_hp() for value, target in zip(before, targets)] == [slot_level*8, slot_level*4, slot_level*8, 0]
    assert caster.has_spell_slot(slot_level)
    assert caster.action_economy.actions.normalized_score == 0


def test_range_follows_caster_after_paid_movement_without_a_persistent_damage_area():
    caster, targets = arena()
    spell = CallLightning(source_entity_uuid=caster.uuid, template=True)
    assert (14, 5) in spell.get_valid_positions()
    assert (15, 5) not in spell.get_valid_positions()
    initial = spell.instantiate(end_position=(14, 5)).apply()
    assert initial is not None and not initial.canceled
    strike = caster.get_action_template('Call Lightning Strike')
    assert strike is not None
    before = [target.get_normal_hp() for target in targets]
    moved = Move(source_entity_uuid=caster.uuid, end_position=(4, 5), path=[(2, 5), (3, 5), (4, 5)]).apply()
    assert moved is not None and not moved.canceled and caster.position == (4, 5)
    assert caster.action_economy.movement_remaining() == 20
    Entity.update_all_entities_senses(max_distance=120)
    assert (16, 5) in strike.get_valid_positions() and (17, 5) not in strike.get_valid_positions()
    caster.on_turn_start()
    repeated = strike.instantiate(end_position=(16, 5)).apply()
    assert isinstance(repeated, SpellEvent) and not repeated.canceled
    assert repeated.source_position == (4, 5) and repeated.aoe_position == (16, 5)
    assert [target.get_normal_hp() for target in targets] == before


def test_ten_caster_turns_expire_activation_even_when_no_more_bolts_are_called():
    caster, _ = arena()
    CallLightning(source_entity_uuid=caster.uuid, end_position=(12, 8)).apply()
    strike = caster.get_action_template('Call Lightning Strike')
    assert strike is not None
    for _ in range(9):
        caster.on_turn_start()
        assert caster.get_action_template('Call Lightning Strike') is not None
    caster.on_turn_start()
    assert caster.get_action_template('Call Lightning Strike') is None
    assert 'Concentrating' not in caster.active_conditions
    rejected = strike.instantiate(end_position=(12, 8)).apply()
    assert rejected is not None and rejected.canceled
    assert caster.action_economy.actions.normalized_score == 1


def test_recasting_replaces_the_grant_and_rejects_the_old_activation():
    caster, _ = arena()
    CallLightning(source_entity_uuid=caster.uuid, end_position=(12, 8)).apply()
    old = caster.get_action_template('Call Lightning Strike')
    assert old is not None
    caster.on_turn_start()
    result = CallLightning(source_entity_uuid=caster.uuid, end_position=(12, 8)).apply()
    assert result is not None and not result.canceled
    current = caster.get_action_template('Call Lightning Strike')
    assert current is not None and current.uuid != old.uuid
    caster.on_turn_start()
    rejected = old.instantiate(end_position=(12, 8)).apply()
    assert rejected is not None and rejected.canceled
    assert caster.action_economy.actions.normalized_score == 1
    result = current.instantiate(end_position=(12, 8)).apply()
    assert result is not None and not result.canceled


@pytest.mark.parametrize('policy, permitted', ((HasteActionPolicy.BG3_HONOUR, True), (HasteActionPolicy.SRD_5_1, False)))
def test_activation_uses_existing_haste_policy_without_an_extra_spell_slot(policy, permitted):
    caster, _ = arena()
    caster.action_economy.haste_action_policy = policy
    caster.add_condition(HasteEffect(source_entity_uuid=caster.uuid, target_entity_uuid=caster.uuid, apply_lethargy=False))
    CallLightning(source_entity_uuid=caster.uuid, end_position=(12, 8)).apply()
    available = get_available_actions(caster)
    choices = [(action, target) for action in available.all_actions
               if action.template_name == 'Call Lightning Strike__grant_haste'
               for target in action.valid_targets if target.position == (12, 8)]
    assert bool(choices) is permitted
    if permitted:
        repeated = execute_available_action(caster, *choices[0])
        assert isinstance(repeated, SpellEvent) and not repeated.canceled
        assert caster.action_economy.resources['haste_action'].current == 0
        assert caster.has_spell_slot(3)


@pytest.mark.parametrize('repeat', (False, True))
@pytest.mark.parametrize('unseen', (False, True), ids=('out-of-range', 'unseen'))
def test_direct_invalid_strike_is_rejected_before_spending_actions_or_slots(repeat, unseen):
    caster, _ = arena()
    if repeat:
        CallLightning(source_entity_uuid=caster.uuid, end_position=(12, 8)).apply()
        caster.on_turn_start()
        template = caster.get_action_template('Call Lightning Strike')
        assert template is not None
    else:
        template = CallLightning(source_entity_uuid=caster.uuid, template=True)
    if unseen:
        caster.add_condition(Blinded(source_entity_uuid=caster.uuid, target_entity_uuid=caster.uuid))
        Entity.update_all_entities_senses(max_distance=120)
    result = template.instantiate(end_position=(12, 8) if unseen else (15, 5)).apply()
    assert result is not None and result.canceled
    assert caster.action_economy.actions.normalized_score == 1
    assert caster.has_spell_slot(3)


@pytest.mark.parametrize('downed', (False, True), ids=('failed-concentration-save', 'downed'))
def test_initial_self_damage_can_end_concentration_without_restoring_the_grant(downed):
    caster, _ = arena()
    force_save_result(caster, 'dexterity', succeeds=False)
    force_save_result(caster, 'constitution', succeeds=False)
    if downed:
        caster.receive_damage(amount=caster.get_normal_hp()-1, damage_type=DamageType.BLUDGEONING,
            source_entity_uuid=caster.uuid)
    with fixed_dice_faces(*([4] * 100)):
        result = CallLightning(source_entity_uuid=caster.uuid, end_position=caster.position).apply()
    assert result is not None and not result.canceled
    assert (caster.get_normal_hp() <= 0) is downed
    assert 'Concentrating' not in caster.active_conditions
    assert caster.get_action_template('Call Lightning Strike') is None


def test_rejected_effect_admission_has_no_bolt_or_leaked_repeat_grant():
    caster, targets = arena()
    before = [target.get_normal_hp() for target in targets]

    def reject_marker(event: Event, _source_uuid):
        if isinstance(event, ConditionApplicationEvent) and event.condition.name == 'Call Lightning':
            return event.cancel('Call Lightning effect rejected')
        return None

    caster.add_event_handler(EventHandler(name='Reject Call Lightning effect', source_entity_uuid=caster.uuid,
        trigger_conditions=[Trigger(event_type=EventType.CONDITION_APPLICATION, event_phase=EventPhase.EFFECT)],
        event_processor=reject_marker))
    result = CallLightning(source_entity_uuid=caster.uuid, end_position=(7, 5)).apply()
    assert result is not None and result.canceled
    assert caster.get_action_template('Call Lightning Strike') is None
    assert 'Concentrating' not in caster.active_conditions
    assert [target.get_normal_hp() for target in targets] == before


def test_extra_attack_does_not_grant_a_bolt_but_action_surge_pays_for_one():
    caster, _ = arena()
    caster.add_condition(ExtraAttackFeature(source_entity_uuid=caster.uuid,
        target_entity_uuid=caster.uuid, extra_attacks=2))
    caster.add_condition(ActionSurgeFeature(source_entity_uuid=caster.uuid, target_entity_uuid=caster.uuid))
    first = CallLightning(source_entity_uuid=caster.uuid, end_position=(12, 8)).apply()
    assert first is not None and not first.canceled
    strike = caster.get_action_template('Call Lightning Strike')
    assert strike is not None
    denied = strike.instantiate(end_position=(12, 8)).apply()
    assert denied is None or denied.canceled
    surge = ActionSurge(source_entity_uuid=caster.uuid).apply()
    assert surge is not None and not surge.canceled
    repeated = strike.instantiate(end_position=(12, 8)).apply()
    assert isinstance(repeated, SpellEvent) and not repeated.canceled
    assert caster.has_spell_slot(3) and caster.action_economy.actions.normalized_score == 0


def test_discovery_and_execution_allow_both_bolts_at_the_casters_feet():
    caster, _ = arena()
    force_save_result(caster, 'constitution', succeeds=True)
    caster.register_action(CallLightning(source_entity_uuid=caster.uuid, template=True))
    for name in ('Call Lightning', 'Call Lightning Strike'):
        available = get_available_actions(caster)
        choices = [(action, target) for action in available.all_actions if action.template_name.split('__', 1)[0] == name
                   for target in action.valid_targets if target.position == caster.position]
        assert choices
        with fixed_dice_faces(*([4] * 100)):
            result = execute_available_action(caster, *choices[0])
        assert isinstance(result, SpellEvent) and not result.canceled
        assert result.aoe_position == caster.position
        caster.on_turn_start()
