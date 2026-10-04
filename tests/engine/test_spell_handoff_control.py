"""Control spell admission, hit-point gates and independently owned conditions."""

from uuid import uuid4

import pytest

from dnd.conditions import Paralyzed, Stunned
from dnd.core.creature_types import CreatureType
from dnd.core.dice import fixed_dice_faces
from dnd.core.life_types import LifeState
from dnd.entity import Entity
from dnd.spells.enchantment import HoldMonster, PowerWordKill, PowerWordStun, PowerWordStunEffect
from tests.engine.support import set_hp
from tests.manual.spell_regression_support import (
    create_spell_regression_actor, force_save_result, reset_spell_regression_arena,
)


def scene():
    reset_spell_regression_arena(25, 12)
    caster = create_spell_regression_actor("Caster", (2, 2), "heroes", spell_slots={5: 2, 6: 2, 8: 2, 9: 2})
    target = create_spell_regression_actor("Target", (5, 2), "monsters")
    Entity.update_all_entities_senses(max_distance=130)
    return caster, target


@pytest.mark.parametrize("spell_type,threshold,effect", [
    (PowerWordKill, 100, "Dead"), (PowerWordStun, 150, "Stunned"),
])
def test_power_words_ignore_temporary_hp_in_threshold(spell_type, threshold, effect):
    caster, target = scene()
    set_hp(target, threshold)
    target.health.add_temporary_hit_points(50, target.uuid)
    result = spell_type(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid).apply()
    assert result is not None and not result.canceled
    if effect == "Dead":
        assert target.health.life_state is LifeState.DEAD
    else:
        assert effect in target.active_conditions


@pytest.mark.parametrize("spell_type,child_type,parent", [
    (HoldMonster, Paralyzed, "Hold Monster"), (PowerWordStun, Stunned, "Power Word Stun"),
])
def test_control_cleanup_preserves_an_earlier_independent_condition(spell_type, child_type, parent):
    caster, target = scene()
    set_hp(target, 100)
    force_save_result(target, "wisdom", succeeds=False)
    original = child_type(source_entity_uuid=target.uuid, target_entity_uuid=target.uuid)
    target.add_condition(original)
    with fixed_dice_faces(10):
        result = spell_type(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid).apply()
    assert result is not None and not result.canceled
    target.remove_condition(parent)
    assert target.active_conditions[original.name].uuid == original.uuid


@pytest.mark.parametrize("invalid", ["undead", "range", "spacing"])
def test_hold_monster_rejects_invalid_second_target_before_spending(invalid):
    caster, target = scene()
    position = (24, 2) if invalid == "range" else (14, 2) if invalid == "spacing" else (6, 2)
    second = create_spell_regression_actor("Second", position, "monsters",
        creature_type=CreatureType.UNDEAD if invalid == "undead" else CreatureType.HUMANOID)
    Entity.update_all_entities_senses(max_distance=130)
    before = caster.action_economy.actions.normalized_score
    result = HoldMonster(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid,
        extra_target_entity_uuids=[second.uuid], cast_at_level=6).apply()
    assert result is not None and result.canceled
    assert caster.action_economy.actions.normalized_score == before
    assert "Hold Monster" not in target.active_conditions
    assert "Hold Monster" not in second.active_conditions


def test_hold_monster_expires_after_one_minute():
    caster, target = scene()
    force_save_result(target, "wisdom", succeeds=False)
    with fixed_dice_faces(10):
        HoldMonster(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid).apply()
    assert target.active_conditions["Hold Monster"].duration.duration == 10
    for _ in range(10):
        target.advance_duration("Hold Monster")
    assert "Paralyzed" not in target.active_conditions


def test_word_stun_uses_recorded_dc_after_source_disappears():
    _, target = scene()
    former_caster = uuid4()
    target.add_condition(PowerWordStunEffect(source_entity_uuid=former_caster,
        caster_uuid=former_caster, target_entity_uuid=target.uuid, spell_dc=100))
    with fixed_dice_faces(10):
        target.on_turn_end()
    assert "Stunned" in target.active_conditions
    force_save_result(target, "constitution", succeeds=True)
    with fixed_dice_faces(10):
        target.on_turn_end()
    assert "Stunned" not in target.active_conditions


@pytest.mark.parametrize("spell_type,condition,parent", [
    (PowerWordStun, "Stunned", "Power Word Stun"), (HoldMonster, "Paralyzed", "Hold Monster"),
])
def test_control_immunity_does_not_leave_a_false_parent_or_repeat_save(spell_type, condition, parent):
    caster, target = scene()
    set_hp(target, 100)
    target.add_condition_immunity(condition, immunity_name="Creature immunity")
    force_save_result(target, "wisdom", succeeds=False)
    with fixed_dice_faces(1):
        result = spell_type(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid).apply()
    assert result is not None
    assert condition not in target.active_conditions
    assert parent not in target.active_conditions
    assert caster.action_economy.actions.normalized_score == 0
