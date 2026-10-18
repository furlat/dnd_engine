"""Shared roster traits through deployed native actors and their real actions.

Inputs are ordinary equipped attacks, Leadership, conditions, turns and rests.
Outputs are attack outcomes, damage packets, reaction costs and effective rolls.
"""

from uuid import uuid4

import pytest

from dnd.actions import Attack, AttackEvent
from dnd.actions_functional import execute_by_index, register_spell
from dnd.conditions import Blinded, Deafened, Incapacitated
from dnd.classes.fighter import FightingStyleProtection
from dnd.content.items.authored_item_builders import build_authored_item
from dnd.content_system.creature_materialization import materialize_creature
from dnd.core.base_actions import BaseAction
from dnd.core.content.materialization import CreatureDeploymentRole, CreaturePossessionMode
from dnd.core.creature_types import DamageType
from dnd.core.dice import AttackOutcome, RollType, fixed_dice_faces
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import D20RollResultEvent, EventHandler, EventPhase, EventQueue, EventType, Trigger
from dnd.core.values import ModifiableValue, ValueRead, parts, read_value
from dnd.entity import Entity
from dnd.game import Game
from dnd.monsters.srd_roster import SRD_CREATURE_RECIPES_BY_ID
from dnd.monsters.traits import DivineEminenceActive, register_leadership
from dnd.runtime_reset import reset_engine_runtime
from dnd.spells.transmutation import Shillelagh
from dnd.spells.illusion import Silence
from tests.engine.support import admitted_in_discovery, force_attack_hit


@pytest.fixture
def game():
    reset_engine_runtime(grid_size=(20, 12))
    result = Game()
    yield result
    result.close()
    reset_engine_runtime(grid_size=(20, 12))


def actor(game, creature_id, position, faction="allies"):
    creature = materialize_creature(
        SRD_CREATURE_RECIPES_BY_ID[creature_id],
        runtime_entity_uuid=uuid4(),
        display_name=creature_id,
        position=position,
        faction=faction,
        deployment_role=CreatureDeploymentRole(role_id="tests.roster_mechanics"),
        possession_mode=CreaturePossessionMode.INCLUDE_DEFAULT_POSSESSIONS,
    )
    creature.compose_entity()
    game.deploy_entity(creature, position)
    return creature


def strike(source, target, *, face=10, slot=WeaponSlot.MELEE_MAIN):
    Entity.update_all_entities_senses(max_distance=100)
    action = next(
        row for row in source.registered_actions
        if isinstance(row, Attack) and row.weapon_slot == slot
    )
    action = action.instantiate(target_entity_uuid=target.uuid)
    with fixed_dice_faces(face, *([2] * 20)):
        result = source.perform(action, action.current_selection())
    assert isinstance(result, AttackEvent)
    assert not result.canceled, result.status_message
    return result


def equip(source, item_id):
    item = build_authored_item(item_id, source.uuid)
    assert source.loot_item(item)
    assert source.equip_item(item.uuid, WeaponSlot.MELEE_MAIN)


@pytest.mark.parametrize("item_id,expected_die", [
    ("weapon.maul", 6), ("weapon.greatsword", 6), ("weapon.longsword", 8),
])
def test_brute_adds_one_actual_weapon_die(game, item_id, expected_die):
    brute = actor(game, "bugbear", (2, 2))
    target = actor(game, "veteran", (3, 2), "enemies")
    equip(brute, item_id)

    event = strike(brute, target, face=19)

    assert event.damages is not None
    assert [(row.dice_numbers, row.damage_dice) for row in event.damages] == [
        (2 if expected_die == 6 else 1, expected_die), (1, expected_die),
    ]


def test_brute_follows_weapon_replacement_and_independent_critical_damage(game):
    brute = actor(game, "bugbear", (2, 2))
    target = actor(game, "veteran", (3, 2), "enemies")
    equip(brute, "weapon.maul")
    assert [row.damage_dice for row in strike(brute, target, face=19).damages] == [6, 6]
    brute.on_turn_start()
    equip(brute, "weapon.longsword")
    brute.add_condition(DivineEminenceActive(source_entity_uuid=brute.uuid, target_entity_uuid=brute.uuid))

    event = strike(brute, target, face=20)

    assert [(row.dice_numbers, row.damage_dice, row.damage_type) for row in event.damages] == [
        (1, 8, DamageType.SLASHING), (1, 8, DamageType.SLASHING), (3, 6, DamageType.RADIANT),
    ]
    assert [roll.effective_dice_count for roll in event.damage_rolls] == [2, 2, 6]


def test_brute_uses_the_actual_shillelagh_weapon_die(game):
    brute = actor(game, "bugbear", (2, 2))
    target = actor(game, "veteran", (3, 2), "enemies")
    equip(brute, "weapon.quarterstaff")
    register_spell(brute, Shillelagh)
    available = brute.get_available_actions(include_aoe_preview=False)
    row = next(row for row in available.self_actions if row.template_name.startswith("Shillelagh"))
    result = execute_by_index(brute, row.template_name, 0, available=available)
    assert result is not None and not result.canceled

    event = strike(brute, target, face=19)

    assert [(row.dice_numbers, row.damage_dice) for row in event.damages] == [(1, 8), (1, 8)]


def test_brute_does_not_add_a_weapon_die_to_an_unarmed_attack(game):
    brute = actor(game, "bugbear", (2, 2))
    target = actor(game, "veteran", (3, 2), "enemies")
    assert brute.unequip_item(WeaponSlot.MELEE_MAIN)

    event = strike(brute, target, face=19)

    assert len(event.damages) == 1


def test_parry_ignores_an_attack_that_already_misses(game):
    defender = actor(game, "knight", (2, 2))
    attacker = actor(game, "veteran", (3, 2), "enemies")

    event = strike(attacker, defender, face=2)

    assert event.attack_outcome == AttackOutcome.MISS
    assert defender.action_economy.reactions.normalized_score == 1


def test_parry_turns_one_eligible_hit_into_a_miss(game):
    defender = actor(game, "knight", (2, 2))
    attacker = actor(game, "veteran", (3, 2), "enemies")
    hp = defender.get_normal_hp()

    first = strike(attacker, defender, face=13)

    assert first.attack_outcome is AttackOutcome.MISS
    assert first.ac is not None and first.ac.normalized_score == 20
    assert defender.get_normal_hp() == hp
    assert defender.action_economy.reactions.normalized_score == 0

    attacker.on_turn_start()
    second = strike(attacker, defender, face=13)

    assert second.attack_outcome is AttackOutcome.HIT
    assert defender.get_normal_hp() < hp


def test_parry_and_protection_share_the_same_reaction(game):
    defender = actor(game, "knight", (2, 2))
    ally = actor(game, "veteran", (3, 2))
    attacker = actor(game, "veteran", (3, 3), "enemies")
    equip(defender, "weapon.longsword")
    shield = build_authored_item("shield.shield", defender.uuid)
    assert defender.loot_item(shield)
    assert defender.equip_item(shield.uuid, WeaponSlot.MELEE_OFF)
    defender.add_condition(FightingStyleProtection(source_entity_uuid=defender.uuid, target_entity_uuid=defender.uuid))

    strike(attacker, ally, face=13)
    assert defender.action_economy.reactions.normalized_score == 0
    attacker.on_turn_start()
    event = strike(attacker, defender, face=15)

    assert event.attack_outcome is AttackOutcome.HIT
    assert not any(row.name == "Parry" for row in event.ac.breakdown)


@pytest.mark.parametrize("reason", [
    "unarmed", "shield_only", "ranged_stance", "blinded", "spent_reaction",
    "critical", "unpreventable", "automatic_hit", "ranged_attack",
])
def test_parry_never_spends_a_reaction_on_ineligible_attacks(game, reason):
    defender = actor(game, "knight", (2, 2))
    attacker = actor(game, "veteran", (3, 2), "enemies")
    face, slot, expected_reactions = 13, WeaponSlot.MELEE_MAIN, 1
    if reason in {"unarmed", "shield_only"}:
        assert defender.unequip_item(WeaponSlot.MELEE_MAIN)
        if reason == "shield_only":
            shield = build_authored_item("shield.shield", defender.uuid)
            assert defender.loot_item(shield)
            assert defender.equip_item(shield.uuid, WeaponSlot.MELEE_OFF)
    elif reason == "ranged_stance":
        defender.equipment.activate_weapon_slot(WeaponSlot.RANGED_MAIN)
    elif reason == "blinded":
        defender.add_condition(Blinded(source_entity_uuid=attacker.uuid, target_entity_uuid=defender.uuid))
    elif reason == "spent_reaction":
        defender.action_economy.consume("reactions", 1)
        expected_reactions = 0
    elif reason == "critical":
        face = 20
    elif reason == "unpreventable":
        face = 19
    elif reason == "automatic_hit":
        force_attack_hit(attacker)
        face = 2
    elif reason == "ranged_attack":
        slot = WeaponSlot.RANGED_MAIN

    event = strike(attacker, defender, face=face, slot=slot)

    assert defender.action_economy.reactions.normalized_score == expected_reactions
    assert event.ac is not None
    assert not any(row.name == "Parry" for row in event.ac.breakdown)
    if reason == "critical":
        assert event.attack_outcome is AttackOutcome.CRIT
    if reason == "automatic_hit":
        assert event.attack_outcome is AttackOutcome.HIT


def use_leadership(leader):
    action = leader.get_action_template("Leadership")
    assert isinstance(action, BaseAction)
    result = leader.perform(action, action.current_selection())
    assert result is not None and not result.canceled
    return result


def grant_common(creature):
    creature.creature_proficiencies.add_language_source(creature.uuid, "language.common")


def support_roll(creature, roll_type=RollType.ATTACK):
    bonus = ModifiableValue(source_entity_uuid=creature.uuid, base=0, use_register=False)
    with fixed_dice_faces(10, 2, 2):
        result = creature.roll_d20(read_value(parts(bonus), ValueRead(creature.uuid)), roll_type)
    event_type = (EventType.ATTACK_D20_ROLL_RESULT if roll_type == RollType.ATTACK
                  else EventType.SAVE_D20_ROLL_RESULT)
    event = next(row for row in reversed(EventQueue.get_events_by_type(event_type))
                 if row.phase is EventPhase.COMPLETION)
    assert isinstance(event, D20RollResultEvent)
    return result, event


def test_leadership_does_not_stack_and_recharges_on_short_rest(game):
    first = actor(game, "knight", (2, 2))
    second = actor(game, "knight", (2, 4))
    ally = actor(game, "veteran", (3, 3))
    for creature in (first, second, ally):
        grant_common(creature)
    use_leadership(first)
    use_leadership(second)

    roll, event = support_roll(ally)
    assert roll.total == 12
    assert len([row for row in event.roll_modifications if row.handler_name == "Leadership"]) == 1

    first.on_short_rest()
    first.on_turn_start()
    use_leadership(first)


def test_leadership_resource_is_released_with_its_action_source(game):
    leader = actor(game, "knight", (2, 2))
    action = leader.get_action_template("Leadership")
    assert action is not None

    assert leader.unregister_action_by_uuid(action.uuid)

    assert not leader.action_economy.has_resource("leadership")
    register_leadership(leader)
    replacement = leader.get_action_template("Leadership")
    assert replacement is not None and replacement.uuid != action.uuid
    assert leader.action_economy.get_resource_current("leadership") == 1
    assert leader.unregister_action_by_uuid(replacement.uuid)
    assert not leader.action_economy.has_resource("leadership")


def test_leadership_refused_effect_does_not_inspire_allies(game):
    leader = actor(game, "knight", (2, 2))
    ally = actor(game, "veteran", (3, 2))
    grant_common(ally)
    leader.add_event_handler(EventHandler(
        name="Refuse Leadership",
        source_entity_uuid=leader.uuid,
        trigger_conditions=[Trigger(event_type=EventType.BASE_ACTION,
            event_phase=EventPhase.EFFECT, event_source_entity_uuid=leader.uuid)],
        event_processor=lambda event, _: event.cancel(status_message="Leadership refused"),
    ))
    action = leader.get_action_template("Leadership")
    assert action is not None

    result = leader.perform(action, action.current_selection())

    assert result is not None and result.canceled
    assert support_roll(ally)[0].total == 10


@pytest.mark.parametrize("roll_type", [RollType.ATTACK, RollType.SAVE])
@pytest.mark.parametrize("reason", ["eligible", "out_of_range", "no_shared_language", "deafened", "leader_deafened", "leader_incapacitated", "leader_is_roller", "enemy"])
def test_leadership_uses_local_range_language_hearing_and_agency_facts(game, roll_type, reason):
    leader = actor(game, "knight", (2, 2))
    ally = actor(game, "veteran", (10, 2) if reason == "out_of_range" else (3, 2),
                "enemies" if reason == "enemy" else "allies")
    if reason != "no_shared_language":
        grant_common(ally)
    use_leadership(leader)
    if reason == "deafened":
        ally.add_condition(Deafened(source_entity_uuid=leader.uuid, target_entity_uuid=ally.uuid))
    if reason == "leader_deafened":
        leader.add_condition(Deafened(source_entity_uuid=ally.uuid, target_entity_uuid=leader.uuid))
    if reason == "leader_incapacitated":
        leader.add_condition(Incapacitated(source_entity_uuid=ally.uuid, target_entity_uuid=leader.uuid))

    roll, event = support_roll(leader if reason == "leader_is_roller" else ally, roll_type)

    eligible = reason in {"eligible", "leader_deafened"}
    assert roll.total == (12 if eligible else 10)
    assert len(event.roll_modifications) == (1 if eligible else 0)


def test_leadership_cannot_be_heard_from_a_leader_inside_silence(game):
    leader = actor(game, "knight", (5, 5))
    ally = actor(game, "veteran", (11, 5))
    caster = actor(game, "cult_fanatic", (5, 10))
    grant_common(ally)
    use_leadership(leader)
    register_spell(caster, Silence)
    Entity.update_all_entities_senses(max_distance=100)
    spell = caster.get_action_template("Silence")
    assert spell is not None
    spell = spell.instantiate(end_position=leader.position)
    result = caster.perform(spell, spell.current_selection())
    assert result is not None and not result.canceled, result
    assert "Deafened" in leader.active_conditions
    assert "Deafened" not in ally.active_conditions

    assert support_roll(ally)[0].total == 10


@pytest.mark.parametrize("rest", ["short", "long"])
def test_leadership_lasts_ten_turns_and_recovers_on_either_rest(game, rest):
    leader = actor(game, "knight", (2, 2))
    ally = actor(game, "veteran", (3, 2))
    grant_common(ally)
    Entity.update_all_entities_senses(max_distance=100)
    action = leader.get_action_template("Leadership")
    assert action is not None and admitted_in_discovery(action)
    use_leadership(leader)
    assert not admitted_in_discovery(action)
    assert leader.action_economy.actions.normalized_score == 0
    for _ in range(9):
        leader.on_turn_start()
    assert support_roll(ally)[0].total == 12
    leader.on_turn_start()
    assert support_roll(ally)[0].total == 10
    if rest == "short":
        leader.on_short_rest()
    else:
        assert leader.on_long_rest()
    assert admitted_in_discovery(action)
    use_leadership(leader)
