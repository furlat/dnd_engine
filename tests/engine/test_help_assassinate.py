"""Registered attack assistance and Assassin opening attacks at the command boundary.

Input: Help/Attack selections and authoritative encounter turns. Output: the
attack's rolled advantage/critical outcome, condition lifecycle and action cost.
"""

from uuid import uuid4

import pytest

from dnd.actions import Attack, AttackEvent, HelpAttack, Move
from dnd.actions_functional import setup_standard_actions, preview_available_selection
from dnd.blocks.health import HealthConfig
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.conditions import Invisible
from dnd.controller import HumanController
from dnd.core.action_types import ActionSelection
from dnd.core.base_conditions import ConditionApplicationEvent
from dnd.core.dice import AttackOutcome, fixed_dice_faces
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import EventPhase, EventQueue, EventType, EventHandler, Trigger
from dnd.core.modifiers import AdvantageStatus
from dnd.encounter import Encounter
from dnd.entity import Entity, EntityConfig
from dnd.game import Game
from dnd.monsters.traits import register_assassinate, register_sneak_attack
from dnd.runtime_reset import reset_engine_runtime


@pytest.fixture
def game():
    reset_engine_runtime(grid_size=(14, 10))
    result = Game()
    yield result
    result.close()
    reset_engine_runtime(grid_size=(14, 10))


def actor(game, name, position, faction):
    entity = Entity.create(uuid4(), name, config=EntityConfig(faction=faction,
        health=HealthConfig(max_hit_points_bonus=100)))
    entity.compose_entity()
    game.deploy_entity(entity, position)
    weapon = build_authored_item('weapon.shortsword', entity.uuid)
    assert entity.loot_item(weapon) and entity.equip_item(weapon.uuid, WeaponSlot.MELEE_MAIN)
    setup_standard_actions(entity)
    Entity.update_all_entities_senses()
    return entity


def attack(owner, target, *, advantage, face=15, critical=False, miss=False):
    template = next(action for action in owner.registered_actions
        if isinstance(action, Attack) and action.weapon_slot is WeaponSlot.MELEE_MAIN)
    owner.action_economy.reset_all_costs()
    with fixed_dice_faces(*([face] * (2 if advantage else 1)), 2, 2):
        result = owner.perform(template, ActionSelection(template_uuid=template.uuid,
            target_uuids=(target.uuid,)))
    assert isinstance(result, AttackEvent) and not result.canceled
    assert result.dice_roll.advantage_status is (AdvantageStatus.ADVANTAGE if advantage else AdvantageStatus.NONE)
    if face == 1:
        assert result.attack_outcome is AttackOutcome.CRIT_MISS
    elif miss:
        assert result.attack_outcome is AttackOutcome.MISS
    else:
        assert result.attack_outcome is (AttackOutcome.CRIT if critical else AttackOutcome.HIT)
    return result


def help_attack(helper, enemy, ally):
    template = helper.get_action_template('Help Attack')
    assert isinstance(template, HelpAttack)
    result = helper.perform(template, ActionSelection(template_uuid=template.uuid,
        target_uuids=(enemy.uuid, ally.uuid)))
    assert result is not None and not result.canceled
    return result


def battle(actors, *, surprised=()):
    encounter = Encounter(source_entity_uuid=uuid4())
    for entity in actors:
        encounter.add_combatant(entity, HumanController(source_entity_uuid=entity.uuid),
            surprised=entity in surprised)
    encounter.initiative_order = [entity.uuid for entity in actors]
    encounter.start_encounter()
    return encounter


def assistance(target):
    return [condition for condition in target.active_conditions_by_uuid.values()
        if condition.get_display_name() == 'Attack Assistance']


def test_help_discovery_and_only_selected_ally_enemy_first_rolled_attack(game):
    helper = actor(game, 'Helper', (3, 3), 'party')
    ally = actor(game, 'Ally', (4, 4), 'party')
    other = actor(game, 'Other ally', (4, 2), 'party')
    enemy = actor(game, 'Enemy', (4, 3), 'foes')
    other_enemy = actor(game, 'Other enemy', (5, 4), 'foes')
    before = EventQueue.event_cursor()
    row = next(row for row in helper.get_available_actions().entity_actions
        if row.display_name == 'Help Attack')
    assert {target.target_uuid for target in row.valid_targets} == {enemy.uuid}
    primary = row.valid_targets[0]
    prefix = preview_available_selection(helper, row, (primary,))
    assert not prefix.can_confirm
    assert {target.target_uuid for target in prefix.next_targets} == {ally.uuid, other.uuid}
    chosen_ally = next(target for target in prefix.next_targets if target.target_uuid == ally.uuid)
    assert preview_available_selection(helper, row, (primary, chosen_ally)).can_confirm
    assert EventQueue.event_cursor() == before  # Discovery creates no events.
    help_attack(helper, enemy, ally)
    assert helper.action_economy.actions.normalized_score == 0
    assert len(assistance(enemy)) == 1
    attack(other, enemy, advantage=False)
    attack(ally, other_enemy, advantage=False)
    assert len(assistance(enemy)) == 1
    attack(ally, enemy, advantage=True, face=1)  # A miss consumes assistance too.
    assert not assistance(enemy)
    attack(ally, enemy, advantage=False)


def test_help_persists_when_helper_moves_and_expires_at_helper_next_turn(game):
    helper = actor(game, 'Helper', (3, 3), 'party')
    ally = actor(game, 'Ally', (4, 4), 'party')
    enemy = actor(game, 'Enemy', (4, 3), 'foes')
    help_attack(helper, enemy, ally)
    move = next(action for action in helper.registered_actions
        if isinstance(action, Move) and action.name == 'Move')
    result = helper.perform(move, ActionSelection(template_uuid=move.uuid, positions=((2, 3),)))
    assert result is not None and not result.canceled
    assert len(assistance(enemy)) == 1
    helper.on_turn_start()
    assert not assistance(enemy)
    attack(ally, enemy, advantage=False)


@pytest.mark.parametrize('end', ['encounter', 'despawn'])
def test_help_cleanup_has_no_lingering_benefit(game, end):
    helper = actor(game, 'Helper', (3, 3), 'party')
    ally = actor(game, 'Ally', (4, 4), 'party')
    enemy = actor(game, 'Enemy', (4, 3), 'foes')
    encounter = battle((helper, ally, enemy))
    help_attack(helper, enemy, ally)
    if end == 'encounter':
        encounter.end_encounter()
    else:
        game.remove_entity(helper.uuid)
    assert not assistance(enemy)
    attack(ally, enemy, advantage=False)


def test_help_refused_condition_leaves_no_benefit(game):
    helper = actor(game, 'Helper', (3, 3), 'party')
    ally = actor(game, 'Ally', (4, 4), 'party')
    enemy = actor(game, 'Enemy', (4, 3), 'foes')

    def refuse(event, _source):
        if isinstance(event, ConditionApplicationEvent) and event.condition.get_display_name() == 'Attack Assistance':
            return event.cancel(status_message='Refused assistance')
        return None

    enemy.add_event_handler(EventHandler(source_entity_uuid=enemy.uuid,
        trigger_conditions=[Trigger(event_type=EventType.CONDITION_APPLICATION,
            event_phase=EventPhase.DECLARATION, event_target_entity_uuid=enemy.uuid)],
        event_processor=refuse))
    template = helper.get_action_template('Help Attack')
    result = helper.perform(template, ActionSelection(template_uuid=template.uuid,
        target_uuids=(enemy.uuid, ally.uuid)))
    assert result is not None
    assert any(event.canceled for event in EventQueue.get_events_by_type(EventType.CONDITION_APPLICATION)
        if isinstance(event, ConditionApplicationEvent) and event.condition.get_display_name() == "Attack Assistance")
    assert not assistance(enemy)
    attack(ally, enemy, advantage=False)


@pytest.mark.parametrize('targets', [('enemy',), ('enemy', 'helper'), ('ally', 'enemy')])
def test_help_rejects_missing_or_ineligible_pair_before_action_cost(game, targets):
    helper = actor(game, 'Helper', (3, 3), 'party')
    ally = actor(game, 'Ally', (4, 4), 'party')
    enemy = actor(game, 'Enemy', (4, 3), 'foes')
    entities = {'helper': helper, 'ally': ally, 'enemy': enemy}
    template = helper.get_action_template('Help Attack')
    result = helper.perform(template, ActionSelection(template_uuid=template.uuid,
        target_uuids=tuple(entities[name].uuid for name in targets)))
    assert result is not None and result.canceled
    assert helper.action_economy.actions.normalized_score == 1
    assert not assistance(enemy)


def test_assassinate_opening_advantage_stops_at_first_turn_start(game):
    assassin = actor(game, 'Ordinary named attacker', (3, 3), 'party')
    target = actor(game, 'Target', (4, 3), 'foes')
    register_assassinate(assassin)
    encounter = battle((assassin, target))
    encounter.start_turn()
    attack(assassin, target, advantage=True)
    encounter.next_turn()  # Target's turn has started, but has not ended.
    assert encounter.combatants[target.uuid].turn_count == 0
    attack(assassin, target, advantage=False)
    encounter.next_turn()
    attack(assassin, target, advantage=False)


def test_assassinate_surprise_crit_requires_hit_and_ends_after_skipped_turn(game):
    assassin = actor(game, 'Assassin', (3, 3), 'party')
    target = actor(game, 'Surprised', (4, 3), 'foes')
    register_assassinate(assassin)
    encounter = battle((assassin, target), surprised=(target,))
    encounter.start_turn()
    attack(assassin, target, advantage=True, face=1)
    attack(assassin, target, advantage=True, face=2, miss=True)
    attack(assassin, target, advantage=True, critical=True)
    encounter.next_turn()  # The skipped target turn has real start/end hooks.
    assert encounter.combatants[target.uuid].turn_count == 1
    attack(assassin, target, advantage=False)
    encounter.end_encounter()
    attack(assassin, target, advantage=False)
    restarted = battle((assassin, target))
    restarted.start_turn()
    attack(assassin, target, advantage=True)  # New encounter, no stale surprise.


def test_assassinate_late_join_uses_joined_targets_own_first_turn(game):
    assassin = actor(game, 'Assassin', (3, 3), 'party')
    original = actor(game, 'Original target', (4, 3), 'foes')
    register_assassinate(assassin)
    encounter = battle((assassin, original))
    encounter.start_turn()
    encounter.next_turn()
    encounter.next_turn()  # Round two.
    incoming = actor(game, 'Late arrival', (3, 4), 'foes')
    join = encounter.prepare_combatant_join(incoming,
        HumanController(source_entity_uuid=incoming.uuid), after_uuid=assassin.uuid)
    encounter.commit_combatant_join(join)
    attack(assassin, incoming, advantage=True)
    encounter.next_turn()
    attack(assassin, incoming, advantage=False)


def test_assassinate_requires_a_shared_active_encounter(game):
    assassin = actor(game, 'Assassin', (3, 3), 'party')
    target = actor(game, 'Outside target', (4, 3), 'foes')
    register_assassinate(assassin)
    attack(assassin, target, advantage=False)
    battle((assassin,))
    attack(assassin, target, advantage=False)


def test_assassinate_surprise_remains_live_during_its_first_skipped_turn(game):
    assassin = actor(game, 'Assassin', (3, 3), 'party')
    target = actor(game, 'Surprised', (4, 3), 'foes')
    register_assassinate(assassin)
    encounter = battle((assassin, target), surprised=(target,))
    encounter.start_turn()
    observed = []

    def opening_reaction(event, _source):
        observed.append(attack(assassin, target, advantage=False, critical=True).attack_outcome)
        return None

    assassin.add_event_handler(EventHandler(source_entity_uuid=assassin.uuid,
        trigger_conditions=[Trigger(event_type=EventType.TURN_START,
            event_phase=EventPhase.EFFECT, event_source_entity_uuid=target.uuid)],
        event_processor=opening_reaction))
    encounter.next_turn()
    assert observed == [AttackOutcome.CRIT]
    attack(assassin, target, advantage=False)


def test_assassinate_and_unseen_attacker_compose_after_target_first_turn(game):
    assassin = actor(game, 'Assassin', (3, 3), 'party')
    target = actor(game, 'Target', (4, 3), 'foes')
    register_assassinate(assassin)
    encounter = battle((target, assassin))
    encounter.start_turn()
    encounter.next_turn()
    assassin.add_condition(Invisible(source_entity_uuid=assassin.uuid, target_entity_uuid=assassin.uuid))
    attack(assassin, target, advantage=True)
    assassin.remove_condition('Invisible')
    attack(assassin, target, advantage=False)


def test_assassin_four_die_sneak_attack_uses_final_attack_facts(game):
    owner = actor(game, 'Assassin', (3, 3), 'party')
    target = actor(game, 'Target', (4, 3), 'foes')
    register_assassinate(owner)
    register_sneak_attack(owner, dice_numbers=4)
    battle((owner, target))
    template = next(action for action in owner.registered_actions
        if isinstance(action, Attack) and action.weapon_slot is WeaponSlot.MELEE_MAIN)
    hp = target.get_normal_hp()
    with fixed_dice_faces(15, 15, 2, 2, 2, 2, 2):
        result = owner.perform(template, ActionSelection(template_uuid=template.uuid,
            target_uuids=(target.uuid,)))
    assert isinstance(result, AttackEvent) and not result.canceled
    assert target.get_normal_hp() == hp - 10  # Shortsword 1d6 + selected Sneak Attack 4d6.
    finalized = next(event for event in reversed(EventQueue.get_events_by_type(EventType.DAMAGE_ROLL_RESULT))
        if event.phase is EventPhase.COMPLETION and event.source_entity_uuid == owner.uuid)
    assert finalized.attack_advantage is AdvantageStatus.ADVANTAGE
    assert finalized.damage_packets[-1].damage.dice_numbers == 4
