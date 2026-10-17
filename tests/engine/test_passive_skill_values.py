"""Passive skills retain the public composed skill math without temporary graphs."""
from uuid import uuid4

import pytest

from dnd.blocks.abilities import ability_score_normalizer
from dnd.core.modifiers import (
    AdvantageModifier, AdvantageStatus, ArithmeticFactor,
    ContextualAdvantageModifier, ContextualNumericalModifier, NumericalModifier,
)
from dnd.core.proficiency_types import ProficiencyMode
from dnd.entity import Entity, EntityConfig
from dnd.runtime_reset import reset_engine_runtime


@pytest.fixture
def actor():
    reset_engine_runtime()
    actor = Entity.create(uuid4(), "Passive observer", config=EntityConfig())
    actor.compose_entity()
    actor.proficiency_bonus.get_base_modifier().value = 3
    actor.ability_scores.wisdom.ability_score.get_base_modifier().value = 15
    yield actor
    reset_engine_runtime()


def number(actor, value, **kwargs):
    return NumericalModifier(source_entity_uuid=actor.uuid, value=value, **kwargs)


def check_passive(actor, expected):
    public_bonus = actor.skill_bonus(None, "perception")
    adjustment = 5 if public_bonus.advantage is AdvantageStatus.ADVANTAGE else (
        -5 if public_bonus.advantage is AdvantageStatus.DISADVANTAGE else 0)
    assert 10 + public_bonus.normalized_score + adjustment == expected
    assert actor.passive_skill("perception") == expected


@pytest.mark.parametrize("skill_modes,ability_modes,expected", [
    ((), (), 12),
    ((ProficiencyMode.FULL,), (), 15),
    ((ProficiencyMode.HALF_ROUND_DOWN,), (), 13),
    ((ProficiencyMode.HALF_ROUND_UP,), (), 14),
    ((ProficiencyMode.EXPERTISE,), (), 12),
    ((ProficiencyMode.FULL, ProficiencyMode.EXPERTISE), (), 18),
    ((ProficiencyMode.HALF_ROUND_UP,), (ProficiencyMode.FULL,), 15),
])
def test_passive_skill_uses_strongest_owned_proficiency(actor, skill_modes, ability_modes, expected):
    skill = actor.skill_set.get_skill("perception")
    for mode in skill_modes:
        skill.add_proficiency_source(uuid4(), mode)
    for mode in ability_modes:
        actor.ability_scores.wisdom.add_check_proficiency_source(uuid4(), mode)
    check_passive(actor, expected)


def test_passive_skill_keeps_last_uuid_winner_normalizer(actor):
    skill = actor.skill_set.get_skill("perception")
    skill.add_proficiency_source(uuid4(), ProficiencyMode.FULL)
    shared = uuid4()
    actor.proficiency_bonus.self_static.add_value_modifier(number(actor, 100, uuid=shared))
    skill.skill_bonus.self_static.add_value_modifier(number(actor, 5, uuid=shared, score_normalizer=lambda n: n * 2))
    actor.ability_scores.wisdom.modifier_bonus.self_static.add_value_modifier(
        number(actor, 2, uuid=shared, score_normalizer=lambda n: n * 3))
    check_passive(actor, 21)


@pytest.mark.parametrize("inactive_factor,expected", [(False, 28), (True, 30)])
def test_passive_factor_presence_keeps_channel_and_aggregate_bounds(actor, inactive_factor, expected):
    ability = actor.ability_scores.wisdom
    ability.ability_score.get_base_modifier().value = 10
    skill = actor.skill_set.get_skill("perception").skill_bonus
    skill.get_base_modifier().value = 10
    skill.self_static.add_max_constraint(number(actor, 8, score_normalizer=lambda n: 0))
    value, bound = number(actor, 10), number(actor, 20)
    skill.self_contextual.add_value_modifier(ContextualNumericalModifier(
        source_entity_uuid=actor.uuid, callable=lambda *_: value))
    skill.self_contextual.add_max_constraint(ContextualNumericalModifier(
        source_entity_uuid=actor.uuid, callable=lambda *_: bound))
    if inactive_factor:
        skill.self_static.add_factor(ArithmeticFactor(source_entity_uuid=actor.uuid,
            numerator=2, contribution_owner_uuid=uuid4()))
    check_passive(actor, expected)


def test_passive_fractional_factor_truncates_after_raw_ability_normalization(actor):
    ability = actor.ability_scores.wisdom
    ability.ability_score.get_base_modifier().value = 20
    ability.ability_score.self_static.add_factor(ArithmeticFactor(source_entity_uuid=actor.uuid,
        numerator=1, denominator=2))
    ability.ability_score.self_static.add_max_constraint(number(actor, 9))
    ability.ability_score.self_static.add_advantage_modifier(AdvantageModifier(
        source_entity_uuid=actor.uuid, value=AdvantageStatus.ADVANTAGE))
    skill = actor.skill_set.get_skill("perception").skill_bonus
    skill.get_base_modifier().value = -4
    skill.self_static.add_factor(ArithmeticFactor(source_entity_uuid=actor.uuid,
        numerator=1, denominator=2))
    assert ability.ability_score.score == 9
    assert ability_score_normalizer(9) == -1
    check_passive(actor, 8)


def test_passive_direct_ability_bonus_constraint_clamps_combined_skill(actor):
    ability = actor.ability_scores.wisdom
    ability.ability_score.get_base_modifier().value = 16
    ability.modifier_bonus.get_base_modifier().value = 2
    ability.modifier_bonus.self_static.add_max_constraint(number(actor, 4))
    check_passive(actor, 14)


def test_passive_is_a_read_with_no_target_and_no_context(actor):
    skill = actor.skill_set.get_skill("perception").skill_bonus
    calls = []

    def conditional(source, current_target, context):
        calls.append((source, current_target, context))
        return number(actor, 4, use_register=False)

    skill.self_contextual.add_value_modifier(ContextualNumericalModifier(
        source_entity_uuid=actor.uuid, callable=conditional))
    check_passive(actor, 16)
    assert calls and all(row == (actor.uuid, None, None) for row in calls)


def test_passive_proficiency_callback_contributes_its_own_normalized_value(actor):
    actor.skill_set.get_skill("perception").add_proficiency_source(uuid4(), ProficiencyMode.FULL)

    def conditional(source, target, context):
        return number(actor, 5, use_register=False)

    modifier = ContextualNumericalModifier(source_entity_uuid=actor.uuid, callable=conditional)
    actor.proficiency_bonus.self_contextual.add_value_modifier(modifier)
    check_passive(actor, 20)


def test_passive_rechecks_contextual_advantage_after_neutral_result(actor):
    answers = iter((AdvantageStatus.NONE, AdvantageStatus.DISADVANTAGE))
    skill = actor.skill_set.get_skill("perception").skill_bonus
    skill.self_contextual.add_advantage_modifier(ContextualAdvantageModifier(
        source_entity_uuid=actor.uuid,
        callable=lambda *_: AdvantageModifier(source_entity_uuid=actor.uuid,
            value=next(answers), use_register=False)))
    assert actor.passive_skill("perception") == 7


def clamped_perception(actor):
    """Owner channels with their own bounds: static 3+2 in [8, 10], contextual 4 in [6, 7]."""
    skill = actor.skill_set.get_skill("perception").skill_bonus
    skill.get_base_modifier().value = 3
    skill.self_static.add_min_constraint(number(actor, 8))
    skill.self_static.add_max_constraint(number(actor, 10))
    contextual_value, minimum, maximum = number(actor, 4), number(actor, 6), number(actor, 7)
    skill.self_contextual.add_value_modifier(ContextualNumericalModifier(
        source_entity_uuid=actor.uuid, callable=lambda *_: contextual_value))
    skill.self_contextual.add_min_constraint(ContextualNumericalModifier(
        source_entity_uuid=actor.uuid, callable=lambda *_: minimum))
    skill.self_contextual.add_max_constraint(ContextualNumericalModifier(
        source_entity_uuid=actor.uuid, callable=lambda *_: maximum))
    return skill


@pytest.mark.parametrize("factored", [False, True])
def test_passive_keeps_separate_channel_clamps_inside_owner_global_bounds(actor, factored):
    skill = clamped_perception(actor)
    if factored:
        skill.self_static.add_factor(ArithmeticFactor(source_entity_uuid=actor.uuid, numerator=2))
    check_passive(actor, 20)


@pytest.mark.parametrize("factored,expected", [(False, 28), (True, 30)])
def test_opposed_read_keeps_separate_channel_clamps_and_loose_global_bounds(actor, factored, expected):
    """The opponent's outgoing rows clamp in their own channel and widen the global bounds."""
    skill = clamped_perception(actor)
    opponent = Entity.create(uuid4(), "Passive opponent", config=EntityConfig())
    opponent.compose_entity()
    outgoing = opponent.skill_set.get_skill("perception").skill_bonus.to_target_static
    outgoing.add_value_modifier(NumericalModifier(source_entity_uuid=opponent.uuid, value=3))
    outgoing.add_min_constraint(NumericalModifier(source_entity_uuid=opponent.uuid, value=4))
    outgoing.add_max_constraint(NumericalModifier(source_entity_uuid=opponent.uuid, value=20))
    if factored:
        skill.self_static.add_factor(ArithmeticFactor(source_entity_uuid=actor.uuid, numerator=2))
    assert 10 + actor.skill_bonus(opponent.uuid, "perception").normalized_score == expected
    assert actor.passive_skill("perception") == 20


def test_passive_reads_each_contextual_constraint_once_per_read(actor):
    """One read evaluates a contextual bound once; that answer clamps the channel and the aggregate."""
    skill = actor.skill_set.get_skill("perception").skill_bonus
    contextual = number(actor, 20)
    answers = iter((number(actor, 10), None, number(actor, 6)))
    skill.self_contextual.add_value_modifier(ContextualNumericalModifier(
        source_entity_uuid=actor.uuid, callable=lambda *_: contextual))
    skill.self_contextual.add_max_constraint(ContextualNumericalModifier(
        source_entity_uuid=actor.uuid, callable=lambda *_: next(answers)))
    assert 10 + actor.skill_bonus(None, "perception").normalized_score == 20
    assert next(answers) is None
    answers = iter((number(actor, 10), None, number(actor, 6)))
    assert actor.passive_skill("perception") == 20
    assert next(answers) is None


def test_passive_proficiency_contextual_advantage_applies(actor):
    modifier = ContextualAdvantageModifier(source_entity_uuid=actor.uuid,
        callable=lambda *_: AdvantageModifier(source_entity_uuid=actor.uuid,
            value=AdvantageStatus.DISADVANTAGE, use_register=False))
    actor.proficiency_bonus.self_contextual.add_advantage_modifier(modifier)
    check_passive(actor, 7)


def test_passive_proficiency_outgoing_callback_does_not_contribute(actor):
    actor.skill_set.get_skill("perception").add_proficiency_source(uuid4(), ProficiencyMode.FULL)

    def outgoing(source, target, context):
        raise AssertionError("Outgoing channels do not contribute to the passive score")

    actor.proficiency_bonus.to_target_contextual.add_value_modifier(ContextualNumericalModifier(
        source_entity_uuid=actor.uuid, callable=outgoing))
    check_passive(actor, 15)


def test_passive_contextual_uuid_winners_and_channel_advantage_cancellation(actor):
    skill = actor.skill_set.get_skill("perception").skill_bonus
    bonus = actor.ability_scores.wisdom.modifier_bonus
    shared_value, shared_advantage = uuid4(), uuid4()
    for channel, amount in ((skill.self_contextual, 7), (bonus.self_contextual, 3)):
        payload = number(actor, amount, score_normalizer=lambda n: n * 2)
        channel.add_value_modifier(ContextualNumericalModifier(uuid=shared_value,
            source_entity_uuid=actor.uuid, callable=lambda *_, payload=payload: payload))
    for channel, value in ((actor.proficiency_bonus.self_static, AdvantageStatus.ADVANTAGE),
                           (skill.self_static, AdvantageStatus.DISADVANTAGE),
                           (bonus.self_static, AdvantageStatus.ADVANTAGE)):
        channel.add_advantage_modifier(AdvantageModifier(uuid=shared_advantage,
            source_entity_uuid=actor.uuid, value=value))
    for channel, value in ((skill.self_contextual, AdvantageStatus.ADVANTAGE),
                           (bonus.self_contextual, AdvantageStatus.DISADVANTAGE)):
        payload = AdvantageModifier(source_entity_uuid=actor.uuid, value=value)
        channel.add_advantage_modifier(ContextualAdvantageModifier(uuid=shared_advantage,
            source_entity_uuid=actor.uuid, callable=lambda *_, payload=payload: payload))
    check_passive(actor, 18)


@pytest.mark.parametrize("ability_bonus", [False, True])
def test_passive_rejects_mismatched_value_sources(actor, ability_bonus):
    value = (actor.ability_scores.wisdom.modifier_bonus if ability_bonus else
             actor.skill_set.get_skill("perception").skill_bonus)
    value.set_source_entity(uuid4())
    with pytest.raises(ValueError, match="Source entity UUIDs do not match"):
        actor.skill_bonus(None, "perception")
    with pytest.raises(ValueError, match="Source entity UUIDs do not match"):
        actor.passive_skill("perception")


def test_passive_retains_outgoing_modifier_target_validation(actor):
    skill = actor.skill_set.get_skill("perception").skill_bonus
    skill.to_target_static.add_value_modifier(number(actor, 3, target_entity_uuid=actor.uuid))
    with pytest.raises(ValueError, match="Outgoing modifier target"):
        actor.skill_bonus(None, "perception")
    with pytest.raises(ValueError, match="Outgoing modifier target"):
        actor.passive_skill("perception")
