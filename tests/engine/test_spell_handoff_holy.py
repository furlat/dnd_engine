"""Holy spell commands retain native spatial triggers, exact owners and finite benefits."""
from uuid import uuid4

import pytest

from dnd.actions import SpellEvent
from dnd.conditions import Frightened, Poisoned
from dnd.core.base_conditions import BaseCondition
from dnd.core.condition_types import ConditionTag
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import DamageAppliedEvent, EventPhase, EventQueue, EventType
from dnd.core.gridmap import get_map
from dnd.core.modifiers import AdvantageModifier, AdvantageStatus, ResistanceModifier, ResistanceStatus
from dnd.entity import Entity
from dnd.spells.conjuration import (SpiritGuardians, SpiritGuardiansZone, GuardianOfFaith,
    GuardianOfFaithObject, GuardianOfFaithZone, HeroesFeast, HeroesFeastObject, HeroesFeastSource,
    HeroesFeastLifetime)
from dnd.core.creature_types import DamageType
from tests.engine.support import set_hp
from tests.engine.test_roster_support_spells import game, actor, cast
from tests.manual.spell_regression_support import force_save_result


def zones(kind):
    return [zone for zone in get_map().get_spatial_conditions() if isinstance(zone, kind)]


def feast_for(caster, position=(3, 2)):
    cast(HeroesFeast, caster, end_position=position)
    return next(obj for identity in get_map().get_objects_at(position)
        if isinstance(obj := HeroesFeastObject.get(identity), HeroesFeastObject))


def eat(feast, target, faces=(4, 5)):
    target.action_economy.reset_all_costs()
    action = feast.get_use_actions(target.uuid)[0]
    with fixed_dice_faces(*faces):
        result = action.apply()
    assert result is not None and not result.canceled, result
    return result


@pytest.mark.parametrize('damage_type', [DamageType.RADIANT, DamageType.NECROTIC])
def test_guardians_appearance_slow_is_immediate_but_damage_waits_for_recipient(damage_type, game):
    caster, target = actor(game), actor(game, 'Nearby', (4, 2), 'foes')
    force_save_result(target, 'wisdom', succeeds=False)
    before = target.get_hp()
    result = cast(SpiritGuardians, caster, damage_type=damage_type)
    assert isinstance(result, SpellEvent) and result.damage_types == [damage_type]
    assert target.get_hp() == before
    assert target.action_economy.current_speed() == 15
    assert zones(SpiritGuardiansZone)[0].duration.duration == 100
    with fixed_dice_faces(10, 2, 2, 2):
        target.on_turn_start(round_number=1)
    assert target.get_hp() == before - 6
    dealt = [e for e in EventQueue.get_events_by_type(EventType.DAMAGE_APPLIED)
        if isinstance(e, DamageAppliedEvent) and e.phase is EventPhase.COMPLETION]
    assert dealt[-1].damage_type is damage_type
    assert dealt[-1].source_condition_uuid == zones(SpiritGuardiansZone)[0].uuid


def test_guardians_explicit_exclusion_survives_faction_change(game):
    caster = actor(game)
    excluded = actor(game, 'Excluded', (4, 2), 'foes')
    ally = actor(game, 'Ally', (4, 3), 'heroes')
    cast(SpiritGuardians, caster, excluded_entity_uuids=frozenset({excluded.uuid}))
    assert 'Spirit Guardians Slowed' not in excluded.active_conditions
    assert 'Spirit Guardians Slowed' in ally.active_conditions
    excluded.faction, ally.faction = 'heroes', 'foes'
    excluded.on_turn_start(round_number=1)
    assert 'Spirit Guardians Slowed' not in excluded.active_conditions
    caster.remove_condition('Concentrating')
    assert 'Spirit Guardians Slowed' not in ally.active_conditions


def test_guardians_rejects_unseen_exclusion_before_payment(game):
    caster, target = actor(game), actor(game, 'Hidden', (4, 2), 'foes')
    target.set_invisible(True)
    Entity.update_all_entities_senses()
    result = SpiritGuardians(source_entity_uuid=caster.uuid,
        excluded_entity_uuids=frozenset({target.uuid}), alt_skip_slot=True).apply()
    assert result is not None and result.canceled
    assert caster.action_economy.actions.normalized_score == 1
    assert not zones(SpiritGuardiansZone)


def test_guardians_aura_movement_does_not_deal_entry_damage(game):
    caster, target = actor(game), actor(game, 'Outside', (7, 2), 'foes')
    before = target.get_hp()
    cast(SpiritGuardians, caster)
    Entity.update_entity_position(caster, (4, 2))
    assert target.get_hp() == before
    assert target.action_economy.current_speed() == 15
    game.remove_entity(caster.uuid)
    assert not zones(SpiritGuardiansZone)
    assert target.action_economy.current_speed() == 30


def test_guardians_entry_first_per_turn_and_start_turn_are_independent(game):
    caster, target = actor(game), actor(game, 'Visitor', (7, 2), 'foes')
    force_save_result(target, 'wisdom', succeeds=False)
    cast(SpiritGuardians, caster, cast_at_level=4)
    before = target.get_hp()
    turn = EventQueue.begin_turn_execution()
    try:
        with fixed_dice_faces(*([2]*30)):
            Entity.update_entity_position(target, (5, 2))
            Entity.update_entity_position(target, (4, 2))
            Entity.update_entity_position(target, (7, 2))
            Entity.update_entity_position(target, (5, 2))
        assert target.get_hp() == before - 8
        with fixed_dice_faces(*([2]*10)):
            target.on_turn_start(round_number=1)
        assert target.get_hp() == before - 16
    finally:
        EventQueue.end_turn_execution(turn)


def test_guardian_large_placement_no_creation_attack_and_source_absence(game):
    caster, enemy = actor(game), actor(game, 'Enemy', (8, 2), 'foes')
    force_save_result(enemy, 'dexterity', succeeds=False)
    before = enemy.get_hp()
    cast(GuardianOfFaith, caster, end_position=(5, 2))
    zone = zones(GuardianOfFaithZone)[0]
    placement = get_map().get_object_placement(zone.anchor_uuid)
    assert placement is not None and set(placement.positions) == {(5, 2), (6, 2), (5, 3), (6, 3)}
    assert all(not get_map().is_walkable_for(*cell) for cell in placement.positions)
    assert enemy.get_hp() == before
    game.remove_entity(caster.uuid)
    with fixed_dice_faces(10):
        Entity.update_entity_position(enemy, (8, 3))
    assert enemy.get_hp() == before - 20
    assert zone.damage_dealt == 20
    enemy.on_turn_start(round_number=1)
    assert enemy.get_hp() == before - 20


def test_guardian_rejects_occupied_nonanchor_cell_before_payment(game):
    caster = actor(game)
    actor(game, 'Occupant', (6, 3), 'foes')
    result = GuardianOfFaith(source_entity_uuid=caster.uuid, end_position=(5, 2), alt_skip_slot=True).apply()
    assert result is not None and result.canceled
    assert caster.action_economy.actions.normalized_score == 1
    assert not zones(GuardianOfFaithZone)
    assert not get_map().get_objects_at((5, 2))


@pytest.mark.parametrize('resistance,expected', [(ResistanceStatus.NONE, 20),
    (ResistanceStatus.RESISTANCE, 10), (ResistanceStatus.IMMUNITY, 0)])
def test_guardian_counts_resolved_temp_hp_absorption(game, resistance, expected):
    caster, enemy = actor(game), actor(game, 'Enemy', (8, 2), 'foes')
    force_save_result(enemy, 'dexterity', succeeds=False)
    enemy.health.damage_reduction.self_static.add_resistance_modifier(ResistanceModifier(name='Defense',
        value=resistance, damage_type=DamageType.RADIANT, source_entity_uuid=enemy.uuid, target_entity_uuid=enemy.uuid))
    enemy.health.add_temporary_hit_points(30, source_entity_uuid=enemy.uuid)
    before = enemy.get_normal_hp()
    cast(GuardianOfFaith, caster, end_position=(5, 2))
    zone = zones(GuardianOfFaithZone)[0]
    with fixed_dice_faces(10):
        Entity.update_entity_position(enemy, (8, 3))
    assert enemy.get_normal_hp() == before
    assert zone.damage_dealt == expected


def test_feast_full_benefits_and_exact_tenth_recipient_turn_expiry(game):
    caster = actor(game)
    target = actor(game, 'Guest', (3, 3))
    target.add_condition(Poisoned(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid))
    target.add_condition(Frightened(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid))
    disease = BaseCondition(name='Disease', source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid,
        tags={ConditionTag.DISEASE})
    target.add_condition(disease)
    maximum = target.get_max_hp()
    set_hp(target, maximum - 30)
    feast = feast_for(caster)
    eat(feast, target)
    assert target.get_max_hp() == maximum + 9 and target.get_normal_hp() == maximum - 21
    assert target.health.get_resistance(DamageType.POISON) is ResistanceStatus.IMMUNITY
    assert target.saving_throw_bonus(None, 'wisdom').advantage is AdvantageStatus.ADVANTAGE
    assert all(name not in target.active_conditions for name in ('Poisoned', 'Frightened', 'Disease'))
    assert target.action_economy.actions.normalized_score == 0
    assert feast.charges == 12 and target.uuid in feast.consumed_by
    target.on_turn_start(round_number=1)
    source = next(c for c in target.active_conditions.values() if isinstance(c, HeroesFeastSource))
    assert source.duration.duration == 9
    for turn in range(2, 11):
        target.on_turn_start(round_number=turn)
    assert "Heroes' Feast" not in target.active_conditions
    assert target.get_max_hp() == maximum and target.get_normal_hp() == maximum - 21
    assert target.health.get_resistance(DamageType.POISON) is ResistanceStatus.NONE


def test_feast_overlap_preserves_weaker_source_without_rehealing(game):
    caster, target = actor(game), actor(game, 'Guest', (3, 3))
    maximum = target.get_max_hp()
    set_hp(target, maximum - 30)
    first, second = feast_for(caster), feast_for(caster, (4, 3))
    eat(first, target, (4, 4))
    effect = target.active_conditions["Heroes' Feast"]
    eat(second, target, (6, 6))
    assert target.get_max_hp() == maximum + 12 and target.get_normal_hp() == maximum - 18
    sources = sorted((c for c in target.active_conditions.values() if isinstance(c, HeroesFeastSource)), key=lambda c:c.hp_bonus)
    target.remove_condition_by_uuid(sources[1].uuid)
    assert target.active_conditions["Heroes' Feast"].uuid == effect.uuid
    assert target.get_max_hp() == maximum + 8 and target.get_normal_hp() == maximum - 18
    target.remove_condition_by_uuid(sources[0].uuid)
    assert target.get_max_hp() == maximum and target.get_normal_hp() == maximum - 18


def test_feast_duplicate_and_remote_use_do_not_pay_or_consume(game):
    caster, target = actor(game), actor(game, 'Guest', (3, 3))
    feast = feast_for(caster)
    stale = feast.get_use_actions(target.uuid)[0]
    eat(feast, target)
    target.action_economy.reset_all_costs()
    result = stale.apply()
    assert result is not None and result.canceled
    assert feast.charges == 12 and target.action_economy.actions.normalized_score == 1
    remote = actor(game, 'Remote', (12, 3))
    result = feast.get_use_actions(remote.uuid)[0].apply()
    assert result is not None and result.canceled
    assert feast.charges == 12 and remote.action_economy.actions.normalized_score == 1


def test_feast_prop_expiry_and_caster_removal_leave_recipient_benefits(game):
    caster, target = actor(game), actor(game, 'Guest', (3, 3))
    feast = feast_for(caster)
    eat(feast, target)
    game.remove_entity(caster.uuid)
    lifetime = zones(HeroesFeastLifetime)[0]
    for _ in range(9):
        assert not lifetime.progress_spatial_duration()
    assert get_map().get_object_placement(feast.uuid) is not None
    assert lifetime.progress_spatial_duration()
    assert get_map().get_object_placement(feast.uuid) is None
    assert not zones(HeroesFeastLifetime)
    assert "Heroes' Feast" in target.active_conditions


def test_guardian_first_movement_each_turn_and_threshold_can_exceed_sixty(game):
    caster = actor(game)
    cast(GuardianOfFaith, caster, end_position=(5, 2))
    zone = zones(GuardianOfFaithZone)[0]
    for index, saved in enumerate((True, False, False, False)):
        enemy = actor(game, f'Enemy{index}', (10, index + 1), 'foes')
        force_save_result(enemy, 'dexterity', succeeds=saved)
        turn = EventQueue.begin_turn_execution()
        try:
            with fixed_dice_faces(10):
                Entity.update_entity_position(enemy, (8, 2))
            if index < 3:
                after = enemy.get_hp()
                Entity.update_entity_position(enemy, (7, 3))
                assert enemy.get_hp() == after
        finally:
            EventQueue.end_turn_execution(turn)
        Entity.update_entity_position(enemy, (10, index + 1))
    assert zone.damage_dealt == 70
    assert not zones(GuardianOfFaithZone)
    assert get_map().get_object_placement(zone.anchor_uuid) is None
    assert get_map().is_walkable_for(5, 2)


def test_guardian_keeps_faction_and_expires_without_caster(game):
    caster, ally = actor(game), actor(game, 'Ally', (8, 2), 'heroes')
    cast(GuardianOfFaith, caster, end_position=(5, 2))
    zone = zones(GuardianOfFaithZone)[0]
    before = ally.get_hp()
    game.remove_entity(caster.uuid)
    Entity.update_entity_position(ally, (8, 3))
    assert ally.get_hp() == before and zone.damage_dealt == 0
    for _ in range(4799):
        assert not zone.progress_spatial_duration()
    assert zone.progress_spatial_duration()
    assert get_map().get_object_placement(zone.anchor_uuid) is None


def test_feast_source_cleanup_preserves_other_immunity_and_advantage_owners(game):
    caster, target = actor(game), actor(game, 'Guest', (3, 3))
    other = uuid4()
    target.add_condition_immunity_source('Poisoned', other)
    target.health.damage_reduction.self_static.add_resistance_modifier(ResistanceModifier(
        name='Other poison immunity', source_entity_uuid=target.uuid, target_entity_uuid=target.uuid,
        value=ResistanceStatus.IMMUNITY, damage_type=DamageType.POISON))
    target.saving_throws.get_saving_throw('wisdom').bonus.self_static.add_advantage_modifier(
        AdvantageModifier(name='Other Wisdom advantage', source_entity_uuid=target.uuid,
            target_entity_uuid=target.uuid, value=AdvantageStatus.ADVANTAGE))
    feast = feast_for(caster)
    eat(feast, target)
    target.remove_condition("Heroes' Feast")
    assert not any(isinstance(c, HeroesFeastSource) for c in target.active_conditions.values())
    assert target.health.get_resistance(DamageType.POISON) is ResistanceStatus.IMMUNITY
    assert target.saving_throw_bonus(None, 'wisdom').advantage is AdvantageStatus.ADVANTAGE
    result = target.add_condition(Poisoned(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid))
    assert result is None or result.canceled
    assert 'Poisoned' not in target.active_conditions


def test_feast_reserves_caster_serving_and_retires_at_thirteen(game):
    caster = actor(game)
    feast = feast_for(caster)
    for index in range(12):
        guest = actor(game, f'Guest{index}', (7 + index % 10, 4 + index // 10))
        Entity.update_entity_position(guest, (3, 3))
        eat(feast, guest, (2, 2))
        Entity.update_entity_position(guest, (7 + index % 10, 4 + index // 10))
    thirteenth = actor(game, 'Extra guest', (3, 3))
    assert feast.charges == 1 and not feast.get_use_actions(thirteenth.uuid)
    eat(feast, caster, (2, 2))
    assert feast.charges == 0 and len(feast.consumed_by) == 13
    assert get_map().get_object_placement(feast.uuid) is None
    assert not zones(HeroesFeastLifetime)


def test_feast_destroyed_prop_rejects_stale_use_without_ending_benefits(game):
    caster, target = actor(game), actor(game, 'Guest', (3, 3))
    feast = feast_for(caster)
    stale = feast.get_use_actions(caster.uuid)[0]
    eat(feast, target)
    feast.destroy()
    caster.action_economy.reset_all_costs()
    result = stale.apply()
    assert result is not None and result.canceled
    assert caster.action_economy.actions.normalized_score == 1
    assert "Heroes' Feast" in target.active_conditions
    assert not zones(HeroesFeastLifetime)


def test_feast_equal_and_weaker_contributions_do_not_stack_or_reheal(game):
    caster, target = actor(game), actor(game, 'Guest', (3, 3))
    maximum = target.get_max_hp()
    set_hp(target, maximum - 30)
    for position, faces in (((3, 2), (5, 5)), ((4, 3), (5, 5)), ((3, 4), (2, 2))):
        eat(feast_for(caster, position), target, faces)
    assert target.get_max_hp() == maximum + 10 and target.get_normal_hp() == maximum - 20
    sources = sorted((c for c in target.active_conditions.values() if isinstance(c, HeroesFeastSource)),
        key=lambda c:c.application_order)
    assert target.active_conditions["Heroes' Feast"].winning_source_uuid == sources[1].uuid
    target.remove_condition_by_uuid(sources[2].uuid)
    target.remove_condition_by_uuid(sources[1].uuid)
    assert target.get_max_hp() == maximum + 10 and target.get_normal_hp() == maximum - 20
    assert target.active_conditions["Heroes' Feast"].winning_source_uuid == sources[0].uuid


def test_guardians_overlapping_sources_share_slow_and_cleanup_exactly(game):
    first, second = actor(game), actor(game, 'Second caster', (2, 4))
    target = actor(game, 'Target', (4, 3), 'foes')
    cast(SpiritGuardians, first, excluded_entity_uuids=frozenset({second.uuid}))
    cast(SpiritGuardians, second, excluded_entity_uuids=frozenset({first.uuid}))
    shared = target.active_conditions['Spirit Guardians Slowed'].uuid
    assert target.action_economy.current_speed() == 15
    first.remove_condition('Concentrating')
    assert target.active_conditions['Spirit Guardians Slowed'].uuid == shared
    assert target.action_economy.current_speed() == 15
    second.remove_condition('Concentrating')
    assert target.action_economy.current_speed() == 30


def test_guardians_expire_after_one_hundred_world_rounds(game):
    caster, target = actor(game), actor(game, 'Target', (4, 2), 'foes')
    cast(SpiritGuardians, caster)
    zone = zones(SpiritGuardiansZone)[0]
    for _ in range(99):
        assert not zone.progress_spatial_duration()
    assert target.action_economy.current_speed() == 15
    assert zone.progress_spatial_duration()
    assert target.action_economy.current_speed() == 30
    assert 'Concentrating' not in caster.active_conditions


def test_feast_independent_serving_clocks_reveal_weaker_without_healing(game):
    caster, target = actor(game), actor(game, 'Guest', (3, 3))
    maximum = target.get_max_hp()
    set_hp(target, maximum - 30)
    eat(feast_for(caster), target, (5, 5))
    for tick in range(1, 6):
        target.on_turn_start(round_number=tick)
    eat(feast_for(caster, (4, 3)), target, (2, 2))
    for tick in range(6, 11):
        target.on_turn_start(round_number=tick)
    assert target.get_max_hp() == maximum + 4 and target.get_normal_hp() == maximum - 20
    assert len([c for c in target.active_conditions.values() if isinstance(c, HeroesFeastSource)]) == 1
    for tick in range(11, 16):
        target.on_turn_start(round_number=tick)
    assert target.get_max_hp() == maximum and target.get_normal_hp() == maximum - 20
    assert "Heroes' Feast" not in target.active_conditions


def test_feast_maximum_expiry_clamps_full_hp_without_damage_or_heal_event(game):
    caster = actor(game)
    maximum = caster.get_max_hp()
    eat(feast_for(caster), caster, (5, 5))
    assert caster.get_normal_hp() == maximum + 10
    cursor = EventQueue.event_cursor()
    caster.remove_condition("Heroes' Feast")
    assert caster.get_normal_hp() == caster.get_max_hp() == maximum
    assert not any(e.event_type in (EventType.TAKE_DAMAGE, EventType.DAMAGE_APPLIED, EventType.HEAL)
        for _, e in EventQueue.iter_events_since(cursor))
