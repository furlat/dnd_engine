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
from dnd.core.values import Channel, Kind, add_modifier


@pytest.fixture
def actor():
    reset_engine_runtime()
    actor = Entity.create(uuid4(), "Passive observer", config=EntityConfig())
    actor.compose_entity()
    actor.proficiency_bonus.base = 3
    actor.ability_scores.wisdom.ability_score.base = 15
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
    add_modifier(actor.proficiency_bonus, Channel.SELF_STATIC, Kind.VALUE, number(actor, 100, uuid=shared))
    add_modifier(skill.skill_bonus, Channel.SELF_STATIC, Kind.VALUE, number(actor, 5, uuid=shared, score_normalizer=lambda n: n * 2))
    add_modifier(actor.ability_scores.wisdom.modifier_bonus, Channel.SELF_STATIC, Kind.VALUE, number(actor, 2, uuid=shared, score_normalizer=lambda n: n * 3))
    check_passive(actor, 21)


@pytest.mark.parametrize("inactive_factor,expected", [(False, 28), (True, 30)])
def test_passive_factor_presence_keeps_channel_and_aggregate_bounds(actor, inactive_factor, expected):
    ability = actor.ability_scores.wisdom
    ability.ability_score.base = 10
    skill = actor.skill_set.get_skill("perception").skill_bonus
    skill.base = 10
    add_modifier(skill, Channel.SELF_STATIC, Kind.MAX, number(actor, 8, score_normalizer=lambda n: 0))
    value, bound = number(actor, 10), number(actor, 20)
    add_modifier(skill, Channel.SELF_CONTEXTUAL, Kind.VALUE, ContextualNumericalModifier(
        source_entity_uuid=actor.uuid, callable=lambda *_: value))
    add_modifier(skill, Channel.SELF_CONTEXTUAL, Kind.MAX, ContextualNumericalModifier(
        source_entity_uuid=actor.uuid, callable=lambda *_: bound))
    if inactive_factor:
        add_modifier(skill, Channel.SELF_STATIC, Kind.FACTOR, ArithmeticFactor(source_entity_uuid=actor.uuid,
            numerator=2, contribution_owner_uuid=uuid4()))
    check_passive(actor, expected)


def test_passive_fractional_factor_truncates_after_raw_ability_normalization(actor):
    ability = actor.ability_scores.wisdom
    ability.ability_score.base = 20
    add_modifier(ability.ability_score, Channel.SELF_STATIC, Kind.FACTOR, ArithmeticFactor(source_entity_uuid=actor.uuid,
        numerator=1, denominator=2))
    add_modifier(ability.ability_score, Channel.SELF_STATIC, Kind.MAX, number(actor, 9))
    add_modifier(ability.ability_score, Channel.SELF_STATIC, Kind.ADVANTAGE, AdvantageModifier(
        source_entity_uuid=actor.uuid, value=AdvantageStatus.ADVANTAGE))
    skill = actor.skill_set.get_skill("perception").skill_bonus
    skill.base = -4
    add_modifier(skill, Channel.SELF_STATIC, Kind.FACTOR, ArithmeticFactor(source_entity_uuid=actor.uuid,
        numerator=1, denominator=2))
    assert ability.ability_score.score == 9
    assert ability_score_normalizer(9) == -1
    check_passive(actor, 8)


def test_passive_direct_ability_bonus_constraint_clamps_combined_skill(actor):
    ability = actor.ability_scores.wisdom
    ability.ability_score.base = 16
    ability.modifier_bonus.base = 2
    add_modifier(ability.modifier_bonus, Channel.SELF_STATIC, Kind.MAX, number(actor, 4))
    check_passive(actor, 14)


def test_passive_is_a_read_with_no_target_and_no_context(actor):
    skill = actor.skill_set.get_skill("perception").skill_bonus
    calls = []

    def conditional(source, current_target, context):
        calls.append((source, current_target, context))
        return number(actor, 4, use_register=False)

    add_modifier(skill, Channel.SELF_CONTEXTUAL, Kind.VALUE, ContextualNumericalModifier(
        source_entity_uuid=actor.uuid, callable=conditional))
    check_passive(actor, 16)
    assert calls and all(row == (actor.uuid, None, None) for row in calls)


def test_passive_proficiency_callback_contributes_its_own_normalized_value(actor):
    actor.skill_set.get_skill("perception").add_proficiency_source(uuid4(), ProficiencyMode.FULL)

    def conditional(source, target, context):
        return number(actor, 5, use_register=False)

    modifier = ContextualNumericalModifier(source_entity_uuid=actor.uuid, callable=conditional)
    add_modifier(actor.proficiency_bonus, Channel.SELF_CONTEXTUAL, Kind.VALUE, modifier)
    check_passive(actor, 20)


def test_passive_rechecks_contextual_advantage_after_neutral_result(actor):
    answers = iter((AdvantageStatus.NONE, AdvantageStatus.DISADVANTAGE))
    skill = actor.skill_set.get_skill("perception").skill_bonus
    add_modifier(skill, Channel.SELF_CONTEXTUAL, Kind.ADVANTAGE, ContextualAdvantageModifier(
        source_entity_uuid=actor.uuid,
        callable=lambda *_: AdvantageModifier(source_entity_uuid=actor.uuid,
            value=next(answers), use_register=False)))
    assert actor.passive_skill("perception") == 7


def clamped_perception(actor):
    """Owner channels with their own bounds: static 3+2 in [8, 10], contextual 4 in [6, 7]."""
    skill = actor.skill_set.get_skill("perception").skill_bonus
    skill.base = 3
    add_modifier(skill, Channel.SELF_STATIC, Kind.MIN, number(actor, 8))
    add_modifier(skill, Channel.SELF_STATIC, Kind.MAX, number(actor, 10))
    contextual_value, minimum, maximum = number(actor, 4), number(actor, 6), number(actor, 7)
    add_modifier(skill, Channel.SELF_CONTEXTUAL, Kind.VALUE, ContextualNumericalModifier(
        source_entity_uuid=actor.uuid, callable=lambda *_: contextual_value))
    add_modifier(skill, Channel.SELF_CONTEXTUAL, Kind.MIN, ContextualNumericalModifier(
        source_entity_uuid=actor.uuid, callable=lambda *_: minimum))
    add_modifier(skill, Channel.SELF_CONTEXTUAL, Kind.MAX, ContextualNumericalModifier(
        source_entity_uuid=actor.uuid, callable=lambda *_: maximum))
    return skill


@pytest.mark.parametrize("factored", [False, True])
def test_passive_keeps_separate_channel_clamps_inside_owner_global_bounds(actor, factored):
    skill = clamped_perception(actor)
    if factored:
        add_modifier(skill, Channel.SELF_STATIC, Kind.FACTOR, ArithmeticFactor(source_entity_uuid=actor.uuid, numerator=2))
    check_passive(actor, 20)


@pytest.mark.parametrize("factored,expected", [(False, 28), (True, 30)])
def test_opposed_read_keeps_separate_channel_clamps_and_loose_global_bounds(actor, factored, expected):
    """The opponent's outgoing rows clamp in their own channel and widen the global bounds."""
    skill = clamped_perception(actor)
    opponent = Entity.create(uuid4(), "Passive opponent", config=EntityConfig())
    opponent.compose_entity()
    outgoing = opponent.skill_set.get_skill("perception").skill_bonus
    add_modifier(outgoing, Channel.TO_TARGET_STATIC, Kind.VALUE, NumericalModifier(source_entity_uuid=opponent.uuid, value=3))
    add_modifier(outgoing, Channel.TO_TARGET_STATIC, Kind.MIN, NumericalModifier(source_entity_uuid=opponent.uuid, value=4))
    add_modifier(outgoing, Channel.TO_TARGET_STATIC, Kind.MAX, NumericalModifier(source_entity_uuid=opponent.uuid, value=20))
    if factored:
        add_modifier(skill, Channel.SELF_STATIC, Kind.FACTOR, ArithmeticFactor(source_entity_uuid=actor.uuid, numerator=2))
    assert 10 + actor.skill_bonus(opponent.uuid, "perception").normalized_score == expected
    assert actor.passive_skill("perception") == 20


def test_passive_reads_each_contextual_constraint_once_per_read(actor):
    """One read evaluates a contextual bound once; that answer clamps the channel and the aggregate."""
    skill = actor.skill_set.get_skill("perception").skill_bonus
    contextual = number(actor, 20)
    answers = iter((number(actor, 10), None, number(actor, 6)))
    add_modifier(skill, Channel.SELF_CONTEXTUAL, Kind.VALUE, ContextualNumericalModifier(
        source_entity_uuid=actor.uuid, callable=lambda *_: contextual))
    add_modifier(skill, Channel.SELF_CONTEXTUAL, Kind.MAX, ContextualNumericalModifier(
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
    add_modifier(actor.proficiency_bonus, Channel.SELF_CONTEXTUAL, Kind.ADVANTAGE, modifier)
    check_passive(actor, 7)


def test_passive_proficiency_outgoing_callback_does_not_contribute(actor):
    actor.skill_set.get_skill("perception").add_proficiency_source(uuid4(), ProficiencyMode.FULL)

    def outgoing(source, target, context):
        raise AssertionError("Outgoing channels do not contribute to the passive score")

    add_modifier(actor.proficiency_bonus, Channel.TO_TARGET_CONTEXTUAL, Kind.VALUE, ContextualNumericalModifier(
        source_entity_uuid=actor.uuid, callable=outgoing))
    check_passive(actor, 15)


def test_passive_contextual_uuid_winners_and_channel_advantage_cancellation(actor):
    skill = actor.skill_set.get_skill("perception").skill_bonus
    bonus = actor.ability_scores.wisdom.modifier_bonus
    shared_value, shared_advantage = uuid4(), uuid4()
    for value, amount in ((skill, 7), (bonus, 3)):
        payload = number(actor, amount, score_normalizer=lambda n: n * 2)
        add_modifier(value, Channel.SELF_CONTEXTUAL, Kind.VALUE, ContextualNumericalModifier(uuid=shared_value,
            source_entity_uuid=actor.uuid, callable=lambda *_, payload=payload: payload))
    for owner, value in ((actor.proficiency_bonus, AdvantageStatus.ADVANTAGE),
                         (skill, AdvantageStatus.DISADVANTAGE),
                         (bonus, AdvantageStatus.ADVANTAGE)):
        add_modifier(owner, Channel.SELF_STATIC, Kind.ADVANTAGE, AdvantageModifier(uuid=shared_advantage,
            source_entity_uuid=actor.uuid, value=value))
    for owner, value in ((skill, AdvantageStatus.ADVANTAGE),
                         (bonus, AdvantageStatus.DISADVANTAGE)):
        payload = AdvantageModifier(source_entity_uuid=actor.uuid, value=value)
        add_modifier(owner, Channel.SELF_CONTEXTUAL, Kind.ADVANTAGE, ContextualAdvantageModifier(uuid=shared_advantage,
            source_entity_uuid=actor.uuid, callable=lambda *_, payload=payload: payload))
    check_passive(actor, 18)


@pytest.mark.parametrize("ability_bonus", [False, True])
def test_passive_rejects_mismatched_value_sources(actor, ability_bonus):
    value = (actor.ability_scores.wisdom.modifier_bonus if ability_bonus else
             actor.skill_set.get_skill("perception").skill_bonus)
    value.source_entity_uuid = uuid4()
    with pytest.raises(ValueError, match="Source entity UUIDs do not match"):
        actor.skill_bonus(None, "perception")
    with pytest.raises(ValueError, match="Source entity UUIDs do not match"):
        actor.passive_skill("perception")


def test_passive_retains_outgoing_modifier_target_validation(actor):
    skill = actor.skill_set.get_skill("perception").skill_bonus
    add_modifier(skill, Channel.TO_TARGET_STATIC, Kind.VALUE, number(actor, 3, target_entity_uuid=actor.uuid))
    with pytest.raises(ValueError, match="Outgoing modifier target"):
        actor.skill_bonus(None, "perception")
    with pytest.raises(ValueError, match="Outgoing modifier target"):
        actor.passive_skill("perception")
