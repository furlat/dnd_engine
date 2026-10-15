"""Paid support casts through native health, action, reaction and turn boundaries."""

from uuid import uuid4

import pytest

from dnd.actions import Attack
from dnd.conditions import Charmed, Paralyzed, Prone
from dnd.controller import PassController
from dnd.core.creature_types import CreatureType, DamageType
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import Event, EventPhase, EventType
from dnd.core.life_types import LifeState
from dnd.core.modifiers import AdvantageStatus, NumericalModifier
from dnd.encounter import Encounter
from dnd.entity import Entity
from dnd.monsters.traits import LifeDrainReduction
from dnd.reactions import add_stand_when_healed_handler
from dnd.spells.abjuration import (
    AuraOfLife,
    BreakEnchantment,
    DispelEvilAndGood,
    GreaterRestoration,
    HolyAura,
    register_counterspell_reaction,
)
from dnd.spells.divination import Foresight
from dnd.spells.enchantment import CharmMonster, Feeblemind
from dnd.spells.evocation import HealingWord, HealSpell, PowerWordHeal
from dnd.spells.illusion import PhantasmalKiller
from dnd.spells.necromancy import NoHealing
from tests.engine.test_bg3_rank_one_two_spells import combatant
from tests.engine.test_high_level_spell_controls import (
    cast,
    conditions,
    game,
    high_actor,
)
from tests.manual.spell_regression_support import force_save_result


@pytest.mark.parametrize("success", [False, True])
def test_feeblemind_damage_on_both_saves_and_exact_cure(game, success):
    caster = high_actor(game)
    target = high_actor(game, "Victim", (3, 2), "foes")
    target.ability_scores.get_ability(
        "intelligence"
    ).ability_score.self_static.add_min_constraint(
        NumericalModifier(
            name="Native minimum", value=19, source_entity_uuid=target.uuid
        )
    )
    before = target.ability_scores.get_ability("intelligence").ability_score.score
    hp = target.get_hp()
    force_save_result(target, "intelligence", succeeds=success)
    with fixed_dice_faces(*([2] * 10)):
        cast(Feeblemind, caster, target)
    assert target.get_hp() == hp - 8
    if success:
        assert (
            target.ability_scores.get_ability("intelligence").ability_score.score
            == before
        )
        assert "Feeblemind" not in conditions(target)
        return
    assert target.ability_scores.get_ability("intelligence").ability_score.score == 1
    assert target.ability_scores.get_ability("intelligence").modifier == -5
    assert target.ability_scores.get_ability("charisma").modifier == -5
    target.action_economy.reset_all_costs()
    result = HealingWord(
        source_entity_uuid=target.uuid, target_entity_uuid=target.uuid
    ).apply()
    assert result is not None and result.canceled
    assert target.action_economy.bonus_actions.normalized_score == 1
    cast(HealSpell, caster, target)
    assert "Feeblemind" not in conditions(target)
    assert (
        target.ability_scores.get_ability("intelligence").ability_score.score == before
    )


def test_feeblemind_native_elapsed_time_recovery_uses_retained_dc(game):
    caster = high_actor(game)
    target = high_actor(game, "Victim", (3, 2), "foes")
    force_save_result(target, "intelligence", succeeds=False)
    cast(Feeblemind, caster, target)
    effect = conditions(target)["Feeblemind"]
    force_save_result(target, "intelligence", succeeds=True)
    force_save_result(target, "intelligence", succeeds=True)
    adjudication = Event(
        event_type=EventType.BASE_ACTION,
        name="Thirty days elapsed",
        source_entity_uuid=caster.uuid,
        phase=EventPhase.EFFECT,
    )
    assert effect.recover_after_thirty_days(adjudication)
    assert not target.is_spellcasting_blocked()


def test_aura_life_prevents_new_loss_keeps_old_loss_and_resists_necrotic(game):
    caster = high_actor(game)
    ally = high_actor(game, "Ally", (3, 2))
    foe = high_actor(game, "Foe", (4, 3), "foes")
    ally.add_condition(
        LifeDrainReduction(
            source_entity_uuid=foe.uuid, target_entity_uuid=ally.uuid, amount=10
        )
    )
    maximum = ally.get_max_hp()
    cast(AuraOfLife, caster)
    hp = ally.get_hp()
    ally.receive_damage(10, DamageType.NECROTIC, foe.uuid)
    assert ally.get_hp() == hp - 5
    result = ally.add_condition(
        LifeDrainReduction(
            source_entity_uuid=foe.uuid, target_entity_uuid=ally.uuid, amount=20
        )
    )
    assert result is not None and result.canceled
    conditions(ally)["Life Drain"].add_reduction(
        5, Event(event_type=EventType.BASE_ACTION, source_entity_uuid=foe.uuid)
    )
    assert ally.get_max_hp() == maximum
    ally.move((12, 2))
    assert not ally.health.prevents_maximum_reduction()
    assert ally.get_max_hp() == maximum


def test_aura_life_heals_before_death_save_and_respects_no_healing(game):
    caster = high_actor(game)
    ally = high_actor(game, "Ally", (3, 2))
    ally.uses_death_saves = True
    cast(AuraOfLife, caster)
    ally.receive_damage(ally.get_hp(), DamageType.FORCE, caster.uuid)
    ally.death_save_failures = 2
    with fixed_dice_faces(1):
        ally.on_turn_start()
    assert ally.get_hp() == 1 and ally.health.life_state is LifeState.ALIVE
    assert ally.death_save_failures == 0
    ally.receive_damage(1, DamageType.FORCE, caster.uuid)
    ally.add_condition(
        NoHealing(source_entity_uuid=caster.uuid, target_entity_uuid=ally.uuid)
    )
    with fixed_dice_faces(15):
        ally.on_turn_start()
    assert ally.get_hp() == 0


@pytest.mark.parametrize("enabled", [False, True])
def test_power_word_heal_cures_before_optional_native_reaction_stand(game, enabled):
    caster = high_actor(game)
    ally = high_actor(game, "Ally", (3, 2))
    add_stand_when_healed_handler(ally)
    handler = next(
        handler
        for handler in ally.event_handlers.values()
        if handler.semantic_key == "reaction.stand_when_healed"
    )
    handler.enabled = enabled
    ally.add_condition(
        Prone(source_entity_uuid=caster.uuid, target_entity_uuid=ally.uuid)
    )
    ally.add_condition(
        Paralyzed(source_entity_uuid=caster.uuid, target_entity_uuid=ally.uuid)
    )
    ally.receive_damage(20, DamageType.FORCE, caster.uuid)
    move = ally.action_economy.movement_spent()
    cast(PowerWordHeal, caster, ally)
    assert ally.get_hp() == ally.get_max_hp()
    assert "Paralyzed" not in conditions(ally)
    assert ("Prone" not in conditions(ally)) == enabled
    assert ally.action_economy.reactions.normalized_score == (0 if enabled else 1)
    assert ally.action_economy.movement_spent() == move


def test_power_word_heal_no_healing_still_cures_and_offers_stand(game):
    caster = high_actor(game)
    ally = high_actor(game, "Ally", (3, 2))
    add_stand_when_healed_handler(ally)
    ally.add_condition(
        Prone(source_entity_uuid=caster.uuid, target_entity_uuid=ally.uuid)
    )
    ally.add_condition(
        Paralyzed(source_entity_uuid=caster.uuid, target_entity_uuid=ally.uuid)
    )
    ally.add_condition(
        NoHealing(source_entity_uuid=caster.uuid, target_entity_uuid=ally.uuid)
    )
    ally.receive_damage(20, DamageType.FORCE, caster.uuid)
    hp = ally.get_hp()
    cast(PowerWordHeal, caster, ally)
    assert ally.get_hp() == hp
    assert "Prone" not in conditions(ally) and "Paralyzed" not in conditions(ally)


def test_foresight_all_rolls_surprise_and_same_caster_retarget(game):
    caster = high_actor(game)
    ally = high_actor(game, "Ally", (3, 2))
    other = high_actor(game, "Other", (2, 3))
    cast(Foresight, caster, ally)
    assert ally.equipment.attack_bonus.advantage is AdvantageStatus.ADVANTAGE
    assert (
        ally.skill_set.get_skill("stealth").skill_bonus.advantage
        is AdvantageStatus.ADVANTAGE
    )
    assert (
        ally.saving_throws.get_saving_throw("wisdom").bonus.advantage
        is AdvantageStatus.ADVANTAGE
    )
    encounter = Encounter(source_entity_uuid=uuid4())
    encounter.add_combatant(
        ally, PassController(source_entity_uuid=ally.uuid), surprised=True
    )
    encounter.start_encounter()
    assert ally.action_economy.reactions.normalized_score == 1
    encounter.start_turn()
    assert ally.is_my_turn
    encounter.end_encounter()
    cast(Foresight, caster, other)
    assert not ally.prevents_surprise() and other.prevents_surprise()
    assert (
        ally.skill_set.get_skill("stealth").skill_bonus.advantage
        is AdvantageStatus.NONE
    )


def test_holy_aura_fixed_recipients_and_melee_hit_blindness_cleanup(game):
    caster = high_actor(game)
    ally = high_actor(game, "Ally", (3, 2))
    attacker = high_actor(
        game, "Fiend", (4, 2), "foes", creature_type=CreatureType.FIEND
    )
    force_save_result(attacker, "constitution", succeeds=False)
    cast(HolyAura, caster, ally)
    assert (
        ally.saving_throws.get_saving_throw("wisdom").bonus.advantage
        is AdvantageStatus.ADVANTAGE
    )
    with fixed_dice_faces(*([20] * 2 + [2] * 12)):
        result = Attack(
            source_entity_uuid=attacker.uuid,
            target_entity_uuid=ally.uuid,
            weapon_slot=WeaponSlot.MELEE_MAIN,
            costs=[],
        ).apply()
    assert result is not None and not result.canceled
    assert any(
        "Blinded" in condition.immunity_names or condition.name == "Blinded"
        for condition in attacker.active_conditions_by_uuid.values()
    )
    ally.move((15, 2))
    assert (
        ally.saving_throws.get_saving_throw("wisdom").bonus.advantage
        is AdvantageStatus.ADVANTAGE
    )
    caster.remove_condition("Concentrating")
    assert not any(
        "Blinded" in condition.immunity_names
        for condition in attacker.active_conditions_by_uuid.values()
    )


def test_break_enchantment_cures_eligible_source_and_ends_exact_ward(game):
    caster = high_actor(game)
    ally = high_actor(game, "Ally", (3, 2))
    fiend = high_actor(game, "Fiend", (4, 3), "foes", creature_type=CreatureType.FIEND)
    force_save_result(ally, "wisdom", succeeds=False)
    cast(CharmMonster, fiend, ally)
    cast(DispelEvilAndGood, caster)
    ward = conditions(caster)["Dispel Evil and Good"]
    caster.action_economy.reset_all_costs()
    result = BreakEnchantment(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=ally.uuid,
        ward_uuid=ward.uuid,
    ).apply()
    assert result is not None and not result.canceled, (
        result.status_message if result else "No action"
    )
    assert "Charm Monster" not in conditions(ally)
    assert "Dispel Evil and Good" not in conditions(caster)


def test_holy_aura_recipient_turns_do_not_shorten_cast_and_blindness_is_cast_owned(
    game,
):
    caster = high_actor(game)
    ally = high_actor(game, "Ally", (3, 2))
    attacker = high_actor(
        game, "Fiend", (4, 2), "foes", creature_type=CreatureType.FIEND
    )
    force_save_result(attacker, "constitution", succeeds=False)
    cast(HolyAura, caster, ally)
    for _ in range(10):
        ally.on_turn_start()
        ally.on_turn_end()
    assert "Holy Aura" in conditions(ally)
    with fixed_dice_faces(20, 20, *([2] * 50)):
        Attack(
            source_entity_uuid=attacker.uuid,
            target_entity_uuid=ally.uuid,
            weapon_slot=WeaponSlot.MELEE_MAIN,
            costs=[],
        ).apply()
    assert any(
        "Blinded" in effect.immunity_names
        for effect in attacker.active_conditions_by_uuid.values()
    )
    ally.remove_condition_by_uuid(conditions(ally)["Holy Aura"].uuid)
    assert any(
        "Blinded" in effect.immunity_names
        for effect in attacker.active_conditions_by_uuid.values()
    )
    caster.remove_condition("Concentrating")
    assert not any(
        "Blinded" in effect.immunity_names
        for effect in attacker.active_conditions_by_uuid.values()
    )


def test_foresight_advantage_applies_to_actual_lower_slot_counterspell_check(game):
    reactor = combatant(game, "Reactor", (2, 2), "heroes", slots={3: 1, 9: 1})
    hostile = high_actor(game, "Hostile", (4, 2), "foes")
    victim = high_actor(game, "Victim", (5, 2))
    cast(Foresight, reactor, reactor)
    register_counterspell_reaction(reactor)
    force_save_result(victim, "wisdom", succeeds=False)
    Entity.update_all_entities_senses()
    with fixed_dice_faces(5, 15, *([2] * 50)):
        result = PhantasmalKiller(
            source_entity_uuid=hostile.uuid, target_entity_uuid=victim.uuid
        ).apply()
    assert result is not None and result.canceled
    assert "Phantasmal Killer" not in conditions(victim)
    assert reactor.action_economy.reactions.normalized_score == 0
    assert reactor.action_economy.spell_slot_value(3).normalized_score == 0
