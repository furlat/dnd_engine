"""Paid high-level casts: observable control, recovery, cures and damage timing."""

from uuid import uuid4

import pytest

from dnd.core.creature_types import CreatureType, DamageType
from dnd.core.dice import fixed_dice_faces
from dnd.core.modifiers import AdvantageStatus
from dnd.entity import Entity
from dnd.spells.abjuration import GreaterRestoration
from dnd.spells.enchantment import (
    CalmEmotions,
    CharmMonster,
    Heroism,
    IrresistibleDance,
)
from dnd.spells.evocation import HealingWord, VitriolicSphere
from dnd.spells.illusion import PhantasmalKiller, Weird
from dnd.spells.transmutation import FleshToStone, Haste
from tests.engine.test_bg3_rank_one_two_spells import combatant, game
from tests.manual.spell_regression_support import force_save_result


def high_actor(game, name="Caster", position=(2, 2), faction="heroes", **kwargs):
    return combatant(
        game,
        name,
        position,
        faction,
        slots={1: 4, 2: 4, 3: 4, 4: 4, 5: 4, 6: 4, 7: 4, 8: 4, 9: 4},
        **kwargs,
    )


def conditions(actor):
    return {
        effect.get_display_name(): effect
        for effect in actor.active_conditions_by_uuid.values()
    }


def cast(spell, caster, target=None, **kwargs):
    caster.action_economy.reset_all_costs()
    Entity.update_all_entities_senses()
    result = spell(
        source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid if target else None,
        **kwargs,
    ).apply()
    assert result is not None and not result.canceled, (
        result.status_message if result else "No result"
    )
    assert caster.action_economy.actions.normalized_score == 0
    return result


@pytest.mark.parametrize(
    "creature_type", [CreatureType.BEAST, CreatureType.DRAGON, CreatureType.UNDEAD]
)
def test_charm_monster_general_creatures_and_source_damage_break(game, creature_type):
    caster = high_actor(game)
    victim = high_actor(game, "Victim", (4, 2), "foes", creature_type=creature_type)
    outsider = high_actor(game, "Outsider", (5, 3), "others")
    force_save_result(victim, "wisdom", succeeds=False)
    cast(CharmMonster, caster, victim)
    assert "Charm Monster" in conditions(victim)
    assert "Concentrating" not in caster.active_conditions
    assert conditions(victim)["Charm Monster"].duration.duration == 600
    victim.receive_damage(1, DamageType.FORCE, outsider.uuid)
    assert "Charm Monster" in conditions(victim)
    victim.receive_damage(1, DamageType.FORCE, caster.uuid)
    assert "Charm Monster" not in conditions(victim)


def test_charm_monster_upcast_independent_recipients_and_calm_cure(game):
    caster = high_actor(game)
    left = high_actor(game, "Left", (4, 2), "foes")
    right = high_actor(game, "Right", (3, 3), "foes")
    force_save_result(left, "wisdom", succeeds=False)
    force_save_result(right, "wisdom", succeeds=True)
    cast(
        CharmMonster,
        caster,
        left,
        cast_at_level=5,
        extra_target_entity_uuids=[right.uuid],
    )
    assert "Charm Monster" in conditions(left) and "Charm Monster" not in conditions(
        right
    )
    caster.action_economy.reset_all_costs()
    cast(CalmEmotions, caster, end_position=left.position)
    assert "Charm Monster" not in conditions(left)
    caster.remove_condition("Concentrating")
    assert "Charm Monster" not in conditions(left)


@pytest.mark.parametrize(
    "spell,ability", [(PhantasmalKiller, "wisdom"), (Weird, "wisdom")]
)
def test_fear_repeat_save_precedes_damage_and_heroism_clears(game, spell, ability):
    caster = high_actor(game)
    victim = high_actor(game, "Victim", (10, 2), "foes")
    force_save_result(victim, ability, succeeds=False)
    if spell is Weird:
        cast(spell, caster, end_position=victim.position)
    else:
        cast(spell, caster, victim)
    hp = victim.get_hp()
    with fixed_dice_faces(*([2] * 20)):
        victim.on_turn_end()
    assert victim.get_hp() == hp - 8
    force_save_result(victim, ability, succeeds=True)
    force_save_result(victim, ability, succeeds=True)
    with fixed_dice_faces(*([2] * 20)):
        victim.on_turn_end()
    assert victim.get_hp() == hp - 8
    assert ("Weird" if spell is Weird else "Phantasmal Killer") not in conditions(
        victim
    )


def test_killer_immunity_upcast_and_concentration_cleanup(game):
    caster = high_actor(game)
    victim = high_actor(game, "Victim", (4, 2), "foes")
    force_save_result(victim, "wisdom", succeeds=False)
    cast(PhantasmalKiller, caster, victim, cast_at_level=5)
    assert victim.action_economy.current_speed() == 0
    hp = victim.get_hp()
    with fixed_dice_faces(*([3] * 20)):
        victim.on_turn_end()
    assert victim.get_hp() == hp - 15
    caster.remove_condition("Concentrating")
    assert victim.action_economy.current_speed() == 30
    victim.add_condition_immunity_source("Frightened", uuid4())
    caster.action_economy.reset_all_costs()
    result = PhantasmalKiller(
        source_entity_uuid=caster.uuid, target_entity_uuid=victim.uuid
    ).apply()
    assert result is not None and result.canceled
    assert "Phantasmal Killer" not in conditions(victim)


def test_dance_has_no_initial_save_preserves_bonus_reaction_and_no_autofail(game):
    caster = high_actor(game)
    victim = high_actor(game, "Victim", (4, 2), "foes")
    force_save_result(victim, "wisdom", succeeds=True)
    cast(IrresistibleDance, caster, victim)
    assert "Irresistible Dance" in conditions(victim)
    assert victim.can_take_actions()
    assert (
        Haste(source_entity_uuid=victim.uuid, target_entity_uuid=victim.uuid).apply()
        is None
    )
    assert (
        HealingWord(
            source_entity_uuid=victim.uuid, target_entity_uuid=victim.uuid
        ).apply()
        is not None
    )
    assert victim.action_economy.current_speed() == 0
    assert victim.action_economy.bonus_actions.normalized_score == 0
    assert victim.action_economy.reactions.normalized_score == 1
    assert (
        victim.saving_throws.get_saving_throw("dexterity").bonus.advantage
        == AdvantageStatus.DISADVANTAGE
    )
    victim.on_turn_end()
    assert "Irresistible Dance" not in conditions(victim)
    assert victim.can_take_actions()


def test_flesh_four_failures_persist_after_concentration_and_restoration_cures(game):
    caster = high_actor(game)
    victim = high_actor(game, "Victim", (3, 2), "foes")
    force_save_result(victim, "constitution", succeeds=False)
    cast(FleshToStone, caster, victim)
    for _ in range(2):
        victim.on_turn_end()
        assert "Flesh to Stone Petrified" not in conditions(victim)
    victim.on_turn_end()
    assert "Flesh to Stone Petrified" in conditions(victim)
    assert "Flesh to Stone" not in conditions(victim)
    caster.remove_condition("Concentrating")
    assert "Flesh to Stone Petrified" in conditions(victim)
    hp = victim.get_hp()
    victim.receive_damage(10, DamageType.POISON, caster.uuid)
    assert victim.get_hp() == hp
    cast(GreaterRestoration, caster, victim)
    assert "Flesh to Stone Petrified" not in conditions(victim)


@pytest.mark.parametrize("saved,later", [(False, 10), (True, 0)])
def test_vitriolic_upcast_initial_only_and_failed_save_delayed_packet(
    game, saved, later
):
    caster = high_actor(game)
    victim = high_actor(game, "Victim", (10, 2), "foes")
    force_save_result(victim, "dexterity", succeeds=saved)
    hp = victim.get_hp()
    with fixed_dice_faces(*([2] * 20)):
        cast(VitriolicSphere, caster, end_position=victim.position, cast_at_level=5)
    assert victim.get_hp() == hp - 24 if not saved else victim.get_hp() == hp - 12
    hp = victim.get_hp()
    with fixed_dice_faces(*([2] * 20)):
        victim.on_turn_end()
    assert victim.get_hp() == hp - later
    hp = victim.get_hp()
    with fixed_dice_faces(*([2] * 20)):
        victim.on_turn_end()
    assert victim.get_hp() == hp


@pytest.mark.parametrize("spell", [PhantasmalKiller, Weird])
def test_overlapping_fear_only_one_tick_on_older_stronger_expiry(game, spell):
    first = high_actor(game, "First", (2, 2))
    second = high_actor(game, "Second", (2, 3), intelligence=14)
    victim = high_actor(game, "Victim", (10, 2), "foes")
    force_save_result(victim, "wisdom", succeeds=False)
    kwargs = (
        {"end_position": victim.position}
        if spell is Weird
        else {"target": victim, "cast_at_level": 5}
    )
    cast(spell, first, **kwargs)
    with fixed_dice_faces(*([2] * 200)):
        for _ in range(9):
            victim.on_turn_end()
    cast(
        spell,
        second,
        **({"end_position": victim.position} if spell is Weird else {"target": victim}),
    )
    hp = victim.get_hp()
    with fixed_dice_faces(*([2] * 200)):
        victim.on_turn_end()
    assert victim.get_hp() == hp - (8 if spell is Weird else 10)
    remaining = [
        condition
        for condition in victim.active_conditions_by_uuid.values()
        if condition.get_display_name() == spell.model_fields["name"].default
    ]
    assert len(remaining) == 1
    hp = victim.get_hp()
    with fixed_dice_faces(*([2] * 200)):
        victim.on_turn_end()
    assert victim.get_hp() == hp - 8


@pytest.mark.parametrize("spell", [Weird, VitriolicSphere])
def test_position_root_rejects_unseen_placement_before_cost(game, spell):
    caster = high_actor(game)
    slots = caster.action_economy.spell_slot_value(
        spell.model_fields["spell_level"].default
    ).normalized_score
    result = spell(source_entity_uuid=caster.uuid, end_position=(17, 7)).apply()
    assert result is not None and result.canceled
    assert caster.action_economy.actions.normalized_score == 1
    assert (
        caster.action_economy.spell_slot_value(
            spell.model_fields["spell_level"].default
        ).normalized_score
        == slots
    )
