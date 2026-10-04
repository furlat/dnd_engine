"""Packet 3 spell commands retain damage, concentration and exact effect ownership."""

import pytest

from dnd.conditions import Frightened
from dnd.core.creature_types import CreatureType, DamageType
from dnd.core.base_conditions import Duration
from dnd.core.condition_types import DurationType
from dnd.core.gridmap import get_map
from dnd.residues import DREAD_RESIDUE, deposit_residue
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import EventQueue, EventPhase, EventType, SavingThrowEvent, TakeDamageEvent, EventHandler, Trigger
from dnd.core.life_types import LifeState
from dnd.actions import Move, SpellEvent
from dnd.core.modifiers import AdvantageStatus, ResistanceModifier, ResistanceStatus
from dnd.entity import Entity
from dnd.monsters.traits import MagicResistance
from dnd.spells.necromancy import Blight, Eyebite, FingerOfDeath, Harm, HarmSource
from dnd.spells.evocation import CircleOfDeath
from dnd.spells.abjuration import AntimagicField, GreaterRestoration, LesserRestoration, SanctuaryEffect
from dnd.spells.illusion import Silence
from tests.engine.support import set_hp
from tests.manual.spell_regression_support import (
    create_spell_regression_actor, force_save_result, reset_spell_regression_arena,
)


def scene(*, creature_type=CreatureType.HUMANOID):
    reset_spell_regression_arena(26, 8)
    caster = create_spell_regression_actor("Caster", (2, 2), "heroes",
        spell_slots={4: 2, 5: 2, 6: 3, 7: 2, 9: 2})
    target = create_spell_regression_actor("Target", (5, 2), "foes", creature_type=creature_type)
    Entity.update_all_entities_senses(max_distance=140)
    return caster, target


def cast_eyebite(caster, target, choice="sickened"):
    force_save_result(target, "wisdom", succeeds=False)
    with fixed_dice_faces(10):
        event = Eyebite(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid,
            effect_choice=choice).apply()
    assert event is not None and not event.canceled
    return event


@pytest.mark.parametrize("slot", [7, 9])
@pytest.mark.parametrize("saved", [False, True])
def test_finger_death_keeps_seven_dice_and_ordinary_damage(slot, saved):
    caster, target = scene()
    force_save_result(target, "constitution", succeeds=saved)
    before = target.get_normal_hp()
    with fixed_dice_faces(10, *([2] * 9)):
        event = FingerOfDeath(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid,
            cast_at_level=slot).apply()
    assert event is not None and not event.canceled
    assert target.get_normal_hp() == before - (22 if saved else 44)
    requests = [event for event in EventQueue.get_events_by_type(EventType.TAKE_DAMAGE)
        if isinstance(event, TakeDamageEvent) and event.phase is EventPhase.COMPLETION]
    assert len(requests) == 1
    assert requests[0].effect_origin is not None
    assert requests[0].source_entity_uuid == caster.uuid
    assert requests[0].damage_rolls[0].effective_dice_count == 7


@pytest.mark.parametrize("slot,saved,expected", [(4, False, 64), (4, True, 32), (5, False, 72)])
def test_blight_plant_maximum_still_halves_on_a_save(slot, saved, expected):
    caster, target = scene(creature_type=CreatureType.PLANT)
    force_save_result(target, "constitution", succeeds=saved)
    before = target.get_normal_hp()
    with fixed_dice_faces(10, 10):
        event = Blight(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid,
            cast_at_level=slot).apply()
    assert event is not None and not event.canceled
    assert target.get_normal_hp() == before - expected
    assert event.save_roll.advantage_status is AdvantageStatus.DISADVANTAGE
    assert target.saving_throw_bonus(caster.uuid, "constitution").advantage is AdvantageStatus.NONE


@pytest.mark.parametrize("creature_type", [CreatureType.UNDEAD, CreatureType.CONSTRUCT])
def test_blight_immune_creature_never_takes_damage(creature_type):
    caster, target = scene(creature_type=creature_type)
    before = target.get_normal_hp()
    event = Blight(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid).apply()
    assert event is not None and event.canceled
    assert target.get_normal_hp() == before
    assert not EventQueue.get_events_by_type(EventType.TAKE_DAMAGE)


@pytest.mark.parametrize("choice,condition", [("asleep", "Eyebite Asleep"),
    ("panicked", "Eyebite Panicked"), ("sickened", "Sickened")])
def test_eyebite_initial_strike_costs_once_and_expires_all_owned_effects(choice, condition):
    caster, target = scene()
    cast_eyebite(caster, target, choice)
    assert condition in {row.get_display_name() for row in target.active_conditions.values()}
    assert caster.action_economy.actions.normalized_score == 0
    assert caster.action_economy.spell_slot_6.normalized_score == 2
    assert caster.get_action_template("Eyebite Strike") is not None
    for _ in range(10):
        caster.advance_duration("Eyebite Casting")
    assert condition not in {row.get_display_name() for row in target.active_conditions.values()}
    assert caster.get_action_template("Eyebite Strike") is None
    assert "Concentrating" not in caster.active_conditions


@pytest.mark.parametrize("invalid", ["range", "hidden"])
def test_eyebite_initial_target_admission_precedes_payment(invalid):
    caster, target = scene()
    if invalid == "range":
        Entity.update_entity_position(target, (24, 2))
    else:
        target.set_invisible(True)
    Entity.update_all_entities_senses(max_distance=140)
    event = Eyebite(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid).apply()
    assert event is not None and event.canceled
    assert caster.action_economy.actions.normalized_score == 1
    assert caster.action_economy.spell_slot_6.normalized_score == 3
    assert "Concentrating" not in caster.active_conditions


def test_eyebite_retained_old_action_cannot_attach_to_a_new_cast():
    caster, target = scene()
    cast_eyebite(caster, target)
    old = caster.get_action_template("Eyebite Strike")
    assert old is not None
    caster.action_economy.reset_all_costs()
    cast_eyebite(caster, target)
    caster.action_economy.reset_all_costs()
    result = old.instantiate(target_entity_uuid=target.uuid).apply()
    assert result is not None and result.canceled
    assert caster.action_economy.actions.normalized_score == 1
    assert caster.get_action_template("Eyebite Strike") is not None


@pytest.mark.parametrize("repeat", [False, True])
def test_eyebite_respects_sanctuary_before_action_or_slot_payment(repeat):
    caster, target = scene()
    if repeat:
        cast_eyebite(caster, target)
        target.remove_condition("Sickened")
        caster.action_economy.reset_all_costs()
    slots = caster.action_economy.spell_slot_6.normalized_score
    target.add_condition(SanctuaryEffect(source_entity_uuid=target.uuid,
        target_entity_uuid=target.uuid, spell_dc=30))
    force_save_result(caster, "wisdom", succeeds=False)
    force_save_result(target, "wisdom", succeeds=False)
    strike = caster.get_action_template("Eyebite Strike") if repeat else None
    action = (strike.instantiate(target_entity_uuid=target.uuid) if strike is not None
        else Eyebite(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid))
    with fixed_dice_faces(*([2] * 10)):
        event = action.apply()
    assert event is not None and event.canceled
    assert caster.action_economy.actions.normalized_score == 1
    assert caster.action_economy.spell_slot_6.normalized_score == slots
    assert "Sickened" not in target.active_conditions


def test_eyebite_repeat_cannot_apply_its_effect_inside_antimagic():
    caster, target = scene()
    cast_eyebite(caster, target)
    target.remove_condition("Sickened")
    shield = AntimagicField(source_entity_uuid=target.uuid,
        target_entity_uuid=target.uuid, alt_skip_slot=True).apply()
    assert shield is not None and not shield.canceled
    caster.action_economy.reset_all_costs()
    strike = caster.get_action_template("Eyebite Strike")
    assert strike is not None
    with fixed_dice_faces(*([2] * 10)):
        event = strike.instantiate(target_entity_uuid=target.uuid).apply()
    assert event is not None and event.canceled
    assert "Sickened" not in target.active_conditions
    assert caster.get_action_template("Eyebite Strike") is not None


def test_eyebite_repeat_is_nonverbal_noncast_and_retains_its_exact_source():
    caster, target = scene()
    cast_eyebite(caster, target)
    target.remove_condition("Sickened")
    marker = caster.active_conditions["Eyebite Casting"]
    silence = Silence(source_entity_uuid=target.uuid,
        end_position=caster.position, alt_skip_slot=True).apply()
    assert silence is not None and not silence.canceled
    caster.add_condition(SanctuaryEffect(source_entity_uuid=caster.uuid,
        target_entity_uuid=caster.uuid, spell_dc=30))
    caster.action_economy.reset_all_costs()
    slots = caster.action_economy.spell_slot_6.normalized_score
    cursor = EventQueue.event_cursor()
    strike = caster.get_action_template("Eyebite Strike")
    assert strike is not None
    with fixed_dice_faces(2):
        event = strike.instantiate(target_entity_uuid=target.uuid).apply()
    assert isinstance(event, SpellEvent) and not event.canceled
    assert event.event_type is EventType.BASE_ACTION and not event.verbal
    assert event.get_effect_origin() == marker.effect_origin
    assert target.active_conditions["Sickened"].effect_origin == marker.effect_origin
    assert caster.action_economy.actions.normalized_score == 0
    assert caster.action_economy.spell_slot_6.normalized_score == slots
    assert "Sanctuary" not in caster.active_conditions
    assert not any(row.event_type is EventType.CAST_SPELL
        for _, row in EventQueue.iter_events_since(cursor))


def test_eyebite_initial_sanctuary_admission_is_not_repeated_by_its_first_gaze():
    caster, target = scene()
    target.add_condition(SanctuaryEffect(source_entity_uuid=target.uuid,
        target_entity_uuid=target.uuid, spell_dc=15))
    force_save_result(caster, "wisdom", succeeds=True)
    force_save_result(target, "wisdom", succeeds=False)
    with fixed_dice_faces(10, 2):
        event = Eyebite(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid).apply()
    assert event is not None and not event.canceled
    saves = [row for row in EventQueue.get_events_by_type(EventType.SAVING_THROW)
        if isinstance(row, SavingThrowEvent) and row.phase is EventPhase.COMPLETION
        and row.target_entity_uuid == caster.uuid]
    assert len(saves) == 1
    assert "Sickened" in target.active_conditions
    assert caster.action_economy.actions.normalized_score == 0


@pytest.mark.parametrize("repeat", [False, True])
def test_eyebite_retained_saves_preserve_magic_resistance(repeat):
    caster, target = scene()
    cast_eyebite(caster, target)
    target.add_condition(MagicResistance(source_entity_uuid=target.uuid,
        target_entity_uuid=target.uuid))
    caster.action_economy.reset_all_costs()
    cursor = EventQueue.event_cursor()
    with fixed_dice_faces(2, 2):
        if repeat:
            strike = caster.get_action_template("Eyebite Strike")
            assert strike is not None
            strike.instantiate(target_entity_uuid=target.uuid).apply()
        else:
            target.on_turn_end()
    save, = [row for _, row in EventQueue.iter_events_since(cursor)
        if isinstance(row, SavingThrowEvent) and row.phase is EventPhase.COMPLETION]
    assert save.dice_roll is not None
    assert save.dice_roll.advantage_status is AdvantageStatus.ADVANTAGE


def test_eyebite_repeat_success_is_remembered_by_its_cast():
    caster, target = scene()
    cast_eyebite(caster, target)
    force_save_result(target, "wisdom", succeeds=True)
    force_save_result(target, "wisdom", succeeds=True)
    with fixed_dice_faces(10):
        target.on_turn_end()
    assert "Sickened" not in target.active_conditions
    caster.action_economy.reset_all_costs()
    strike = caster.get_action_template("Eyebite Strike")
    assert strike is not None
    result = strike.instantiate(target_entity_uuid=target.uuid).apply()
    assert result is not None and result.canceled
    assert caster.action_economy.actions.normalized_score == 1


def test_eyebite_sickened_disadvantages_attacks_and_checks_without_save_penalty():
    caster, target = scene()
    cast_eyebite(caster, target)
    assert target.attack_bonus().advantage is AdvantageStatus.DISADVANTAGE
    assert target.skill_bonus(None, "athletics").advantage is AdvantageStatus.DISADVANTAGE
    assert target.ability_check_bonus(None, "strength").advantage is AdvantageStatus.DISADVANTAGE
    assert target.saving_throw_bonus(None, "strength").advantage is AdvantageStatus.NONE


def test_eyebite_panicked_cleanup_preserves_independent_frightened():
    caster, target = scene()
    earlier = Frightened(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid)
    target.add_condition(earlier)
    cast_eyebite(caster, target, "panicked")
    caster.remove_condition("Concentrating")
    assert target.active_conditions["Frightened"].uuid == earlier.uuid


def test_eyebite_asleep_wakes_only_from_applied_damage():
    caster, target = scene()
    cast_eyebite(caster, target, "asleep")
    target.receive_damage(0, DamageType.FIRE, caster.uuid)
    assert "Eyebite Asleep" in target.active_conditions
    target.receive_damage(1, DamageType.FIRE, caster.uuid)
    assert "Eyebite Asleep" not in target.active_conditions


def cast_harm(caster, target, *, face=2, saved=False):
    caster.action_economy.reset_all_costs()
    force_save_result(target, "constitution", succeeds=saved)
    with fixed_dice_faces(10, *([face] * 14)):
        event = Harm(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid).apply()
    assert event is not None and not event.canceled
    return event


@pytest.mark.parametrize("saved", [False, True])
def test_harm_preserves_normal_hp_when_maximum_changes_and_on_removal(saved):
    caster, target = scene()
    maximum = target.get_max_hp()
    force_save_result(target, "constitution", succeeds=saved)
    cast_harm(caster, target, saved=saved)
    amount = 14 if saved else 28
    assert target.get_normal_hp() == maximum - amount
    assert target.get_max_hp() == maximum - (0 if saved else amount)
    if not saved:
        target.remove_condition("Harm")
        assert not any(isinstance(condition, HarmSource) for condition in target.active_conditions.values())
        assert target.get_max_hp() == maximum
        assert target.get_normal_hp() == maximum - amount


@pytest.mark.parametrize("affinity,accepted", [(ResistanceStatus.RESISTANCE, 14), (ResistanceStatus.IMMUNITY, 0)])
def test_harm_caps_normal_hp_after_resistance_and_counts_temporary_hp(affinity, accepted):
    caster, target = scene()
    maximum = target.get_max_hp()
    set_hp(target, 5)
    target.health.add_temporary_hit_points(10, target.uuid)
    target.health.damage_reduction.self_static.add_resistance_modifier(ResistanceModifier(
        name="Native affinity", source_entity_uuid=target.uuid, target_entity_uuid=target.uuid,
        damage_type=DamageType.NECROTIC, value=affinity))
    cast_harm(caster, target, face=6)
    assert target.get_normal_hp() == (1 if accepted else 5)
    assert target.health.temporary_hit_points.normalized_score == (0 if accepted else 10)
    assert target.get_max_hp() == maximum - accepted
    assert ("Harm" in target.active_conditions) is bool(accepted)


def test_harm_strongest_source_expiry_reveals_weaker_without_healing():
    caster, target = scene()
    maximum = target.get_max_hp()
    cast_harm(caster, target, face=2)
    public_uuid = target.active_conditions["Harm"].uuid
    first = next(condition for condition in target.active_conditions.values() if isinstance(condition, HarmSource))
    assert first.duration.duration == 600
    cast_harm(caster, target, face=3)
    second = next(condition for condition in target.active_conditions.values()
        if isinstance(condition, HarmSource) and condition.uuid != first.uuid)
    normal = target.get_normal_hp()
    assert target.get_max_hp() == maximum - 42
    for _ in range(600):
        target.advance_duration(second.name)
    assert target.active_conditions["Harm"].uuid == public_uuid
    assert target.get_max_hp() == maximum - 28
    assert target.get_normal_hp() == normal
    for _ in range(600):
        target.advance_duration(first.name)
    assert "Harm" not in target.active_conditions
    assert target.get_max_hp() == maximum
    assert target.get_normal_hp() == normal


def test_harm_weaker_expiry_and_ties_retain_one_effect():
    caster, target = scene()
    maximum = target.get_max_hp()
    cast_harm(caster, target, face=3)
    first = next(condition for condition in target.active_conditions.values() if isinstance(condition, HarmSource))
    cast_harm(caster, target, face=2)
    weak = next(condition for condition in target.active_conditions.values()
        if isinstance(condition, HarmSource) and condition.uuid != first.uuid)
    normal = target.get_normal_hp()
    for _ in range(600):
        target.advance_duration(weak.name)
    assert target.get_max_hp() == maximum - 42
    assert target.get_normal_hp() == normal
    cast_harm(caster, target, face=3)
    latest = max((condition for condition in target.active_conditions.values() if isinstance(condition, HarmSource)),
        key=lambda condition: condition.application_order)
    assert target.active_conditions["Harm"].winning_source_uuid == latest.uuid
    assert target.get_max_hp() == maximum - 42


@pytest.mark.parametrize("restoration", [LesserRestoration, GreaterRestoration])
def test_harm_disease_or_maximum_restoration_retires_all_casts(restoration):
    caster, target = scene()
    maximum = target.get_max_hp()
    cast_harm(caster, target, face=2)
    cast_harm(caster, target, face=3)
    normal = target.get_normal_hp()
    Entity.update_entity_position(caster, (4, 2))
    caster.action_economy.reset_all_costs()
    Entity.update_all_entities_senses(max_distance=140)
    event = restoration(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid, alt_skip_slot=True).apply()
    assert event is not None and not event.canceled
    assert "Harm" not in target.active_conditions
    assert not any(isinstance(condition, HarmSource) for condition in target.active_conditions.values())
    assert target.get_max_hp() == maximum
    assert target.get_normal_hp() == normal


@pytest.mark.parametrize("slot,expected", [(6, 16), (7, 20), (9, 28)])
def test_circle_death_uses_sixty_foot_radius_and_one_owned_damage_per_recipient(slot, expected):
    reset_spell_regression_arena(36, 8)
    caster = create_spell_regression_actor("Caster", (2, 2), "heroes", spell_slots={slot: 1})
    close = create_spell_regression_actor("Close", (18, 3), "foes")
    edge = create_spell_regression_actor("Edge", (30, 2), "foes")
    outside = create_spell_regression_actor("Outside", (31, 2), "foes")
    for target in (close, edge, outside):
        force_save_result(target, "constitution", succeeds=False)
    Entity.update_all_entities_senses(max_distance=180)
    before = {target.uuid: target.get_normal_hp() for target in (caster, close, edge, outside)}
    with fixed_dice_faces(*([2] * 100)):
        event = CircleOfDeath(source_entity_uuid=caster.uuid, end_position=(18, 2), cast_at_level=slot).apply()
    assert event is not None and not event.canceled
    assert close.get_normal_hp() == before[close.uuid] - expected
    assert edge.get_normal_hp() == before[edge.uuid] - expected
    assert outside.get_normal_hp() == before[outside.uuid]
    assert caster.get_normal_hp() == before[caster.uuid]
    requests = [event for event in EventQueue.get_events_by_type(EventType.TAKE_DAMAGE)
        if isinstance(event, TakeDamageEvent) and event.phase is EventPhase.COMPLETION]
    assert len(requests) == 2
    assert all(request.source_entity_uuid == caster.uuid and request.effect_origin is not None for request in requests)


def test_eyebite_panicked_dash_spends_normal_movement():
    caster, target = scene()
    cast_eyebite(caster, target, "panicked")
    before = target.position
    target.on_turn_start(round_number=1, turn_index=0)
    assert target.position != before
    assert target.action_economy.actions.normalized_score == 0
    assert target.action_economy.movement_spent() > 0
    assert EventQueue.get_events_by_type(EventType.STEP_MOVEMENT)
    assert not EventQueue.get_events_by_type(EventType.FORCED_MOVEMENT)


@pytest.mark.parametrize("spell_type,choice", [(Blight, None), (FingerOfDeath, None),
    (Harm, None), (Eyebite, "sickened")])
def test_necromancy_canceled_effect_does_not_commit_damage_or_conditions(spell_type, choice):
    caster, target = scene()
    force_save_result(target, "constitution", succeeds=False)
    force_save_result(target, "wisdom", succeeds=False)
    before = target.get_normal_hp()

    def cancel_effect(event, _source):
        if isinstance(event, SpellEvent):
            return event.cancel(status_message="Spell stopped at effect")
        return event

    EventQueue.add_event_handler(EventHandler(name="Stop the spell", source_entity_uuid=caster.uuid,
        trigger_conditions=[Trigger(event_type=EventType.CAST_SPELL, event_phase=EventPhase.EFFECT)],
        event_processor=cancel_effect))
    kwargs = {"effect_choice": choice} if choice else {}
    with fixed_dice_faces(*([2] * 40)):
        event = spell_type(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid, **kwargs).apply()
    assert event is not None and event.canceled
    assert target.get_normal_hp() == before
    assert not target.active_conditions
    assert "Concentrating" not in caster.active_conditions
    assert not EventQueue.get_events_by_type(EventType.TAKE_DAMAGE)


def test_finger_death_uses_ordinary_death_without_creating_an_actor():
    caster, target = scene()
    set_hp(target, 1)
    force_save_result(target, "constitution", succeeds=False)
    actor_uuids = {actor.uuid for actor in Entity.get_all_entities()}
    with fixed_dice_faces(10, *([2] * 7)):
        event = FingerOfDeath(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid).apply()
    assert event is not None and not event.canceled
    assert target.health.life_state is LifeState.DEAD
    assert {actor.uuid for actor in Entity.get_all_entities()} == actor_uuids


def test_harm_reduction_uses_committed_damage_before_reactive_healing():
    caster, target = scene()
    maximum = target.get_max_hp()

    def heal_after_damage(event, _source):
        target.receive_healing(10, target.uuid, parent_event=event.uuid)
        return event

    EventQueue.add_event_handler(EventHandler(name="Reactive healing", source_entity_uuid=target.uuid,
        trigger_conditions=[Trigger(event_type=EventType.DAMAGE_APPLIED,
            event_phase=EventPhase.EFFECT, event_target_entity_uuid=target.uuid)],
        event_processor=heal_after_damage))
    cast_harm(caster, target, face=2)
    assert target.get_max_hp() == maximum - 28
    assert target.get_normal_hp() <= target.get_max_hp()



def overlapping_panicked():
    first, target = scene()
    second = create_spell_regression_actor("Second Caster", (8, 2), "heroes", spell_slots={6: 2})
    Entity.update_all_entities_senses(max_distance=140)
    cast_eyebite(first, target, "panicked")
    shared_uuid = target.active_conditions["Frightened"].uuid
    cast_eyebite(second, target, "panicked")
    assert target.active_conditions["Frightened"].uuid == shared_uuid
    assert sum(condition.get_display_name() == "Eyebite Panicked"
        for condition in target.active_conditions.values()) == 2
    return first, second, target, shared_uuid


def test_panicked_sources_keep_separate_visibility_and_cleanup():
    first, second, target, shared_uuid = overlapping_panicked()
    first.set_invisible(True)
    Entity.update_all_entities_senses(max_distance=140)
    assert target.action_economy.current_speed() == 30
    assert target.attack_bonus().advantage is AdvantageStatus.DISADVANTAGE
    assert target.skill_bonus(None, "athletics").advantage is AdvantageStatus.DISADVANTAGE
    assert target.ability_check_bonus(None, "strength").advantage is AdvantageStatus.DISADVANTAGE
    assert target.saving_throw_bonus(None, "strength").advantage is AdvantageStatus.NONE
    second.remove_condition("Concentrating")
    assert target.active_conditions["Frightened"].uuid == shared_uuid
    assert sum(condition.get_display_name() == "Eyebite Panicked"
        for condition in target.active_conditions.values()) == 1
    assert target.attack_bonus().advantage is AdvantageStatus.NONE
    assert target.skill_bonus(None, "athletics").advantage is AdvantageStatus.NONE
    assert target.ability_check_bonus(None, "strength").advantage is AdvantageStatus.NONE
    first.set_invisible(False)
    Entity.update_all_entities_senses(max_distance=140)
    assert target.attack_bonus().advantage is AdvantageStatus.DISADVANTAGE
    first.remove_condition("Concentrating")
    assert "Frightened" not in target.active_conditions
    assert target.attack_bonus().advantage is AdvantageStatus.NONE


def test_panicked_sources_constrain_only_their_own_visible_directions():
    first, second, target, _ = overlapping_panicked()
    first.set_invisible(True)
    Entity.update_all_entities_senses(max_distance=140)
    result = Move(source_entity_uuid=target.uuid, end_position=(6, 2)).apply()
    assert result is not None
    assert target.position == (5, 2)
    assert target.action_economy.movement_spent() == 0
    second.remove_condition("Concentrating")
    result = Move(source_entity_uuid=target.uuid, end_position=(6, 2)).apply()
    assert result is not None and not result.canceled
    assert target.position == (6, 2)
    assert target.action_economy.movement_spent() == 5
    first.set_invisible(False)
    Entity.update_all_entities_senses(max_distance=140)
    result = Move(source_entity_uuid=target.uuid, end_position=(5, 2)).apply()
    assert result is not None
    assert target.position == (6, 2)
    assert target.action_economy.movement_spent() == 5


def test_panicked_borrows_ordinary_fear_without_changing_its_movement_lock():
    ordinary_source, target = scene()
    caster = create_spell_regression_actor("Eyebite Caster", (8, 2), "heroes", spell_slots={6: 1})
    Entity.update_all_entities_senses(max_distance=140)
    ordinary = Frightened(source_entity_uuid=ordinary_source.uuid, target_entity_uuid=target.uuid)
    target.add_condition(ordinary)
    assert target.action_economy.current_speed() == 0
    cast_eyebite(caster, target, "panicked")
    assert target.active_conditions["Frightened"].uuid == ordinary.uuid
    assert target.action_economy.current_speed() == 0
    ordinary_source.set_invisible(True)
    Entity.update_all_entities_senses(max_distance=140)
    assert target.action_economy.current_speed() == 30
    assert target.attack_bonus().advantage is AdvantageStatus.DISADVANTAGE
    caster.remove_condition("Concentrating")
    assert target.active_conditions["Frightened"].uuid == ordinary.uuid
    assert target.attack_bonus().advantage is AdvantageStatus.NONE
    assert target.ability_check_bonus(None, "strength").advantage is AdvantageStatus.NONE
    ordinary_source.set_invisible(False)
    Entity.update_all_entities_senses(max_distance=140)
    assert target.action_economy.current_speed() == 0


def test_later_ordinary_fear_keeps_panicked_ownership_until_its_cast_ends():
    caster, target = scene()
    other = create_spell_regression_actor("Ordinary Fear", (8, 2), "heroes")
    cast_eyebite(caster, target, "panicked")
    ordinary = Frightened(source_entity_uuid=other.uuid, target_entity_uuid=target.uuid)
    target.add_condition(ordinary)
    assert any(condition.get_display_name() == "Eyebite Panicked"
        for condition in target.active_conditions.values())
    assert target.active_conditions["Frightened"].uuid == ordinary.uuid
    other.set_invisible(True)
    Entity.update_all_entities_senses(max_distance=140)
    assert target.attack_bonus().advantage is AdvantageStatus.DISADVANTAGE
    caster.remove_condition("Concentrating")
    assert target.active_conditions["Frightened"].uuid == ordinary.uuid
    assert target.attack_bonus().advantage is AdvantageStatus.NONE


def test_removing_shared_frightened_retires_all_panicked_contributions():
    first, second, target, _ = overlapping_panicked()
    target.remove_condition("Frightened")
    assert not any(condition.get_display_name() == "Eyebite Panicked"
        for condition in target.active_conditions.values())
    assert target.attack_bonus().advantage is AdvantageStatus.NONE
    assert target.skill_bonus(None, "athletics").advantage is AdvantageStatus.NONE
    assert target.ability_check_bonus(None, "strength").advantage is AdvantageStatus.NONE
    target.on_turn_start(round_number=1, turn_index=0)
    assert target.action_economy.actions.normalized_score == 1
    assert first.get_action_template("Eyebite Strike") is not None
    assert second.get_action_template("Eyebite Strike") is not None



def test_expired_ordinary_fear_releases_its_rules_but_keeps_live_panicked_membership():
    ordinary_source, target = scene()
    caster = create_spell_regression_actor("Eyebite Caster", (8, 2), "heroes", spell_slots={6: 1})
    Entity.update_all_entities_senses(max_distance=140)
    ordinary = Frightened(source_entity_uuid=ordinary_source.uuid, target_entity_uuid=target.uuid,
        duration=Duration(duration_type=DurationType.ROUNDS, duration=2))
    target.add_condition(ordinary)
    cast_eyebite(caster, target, "panicked")
    target.advance_duration("Frightened")
    assert target.action_economy.current_speed() == 0
    target.advance_duration("Frightened")
    assert target.active_conditions["Frightened"].uuid == ordinary.uuid
    assert target.action_economy.current_speed() == 30
    assert target.attack_bonus().advantage is AdvantageStatus.DISADVANTAGE
    caster.set_invisible(True)
    Entity.update_all_entities_senses(max_distance=140)
    assert target.attack_bonus().advantage is AdvantageStatus.NONE
    caster.remove_condition("Concentrating")
    assert "Frightened" not in target.active_conditions


def test_residue_fear_ending_does_not_remove_a_borrowing_eyebite_cast():
    caster, target = scene()
    tile = get_map().get_tile(6, 2)
    assert tile is not None
    assert deposit_residue(tile, DREAD_RESIDUE) is not None
    force_save_result(target, "wisdom", succeeds=False)
    target.action_economy.consume("movement", 25)
    Entity.update_all_entities_senses(max_distance=140)
    with fixed_dice_faces(10):
        result = Move(source_entity_uuid=target.uuid, end_position=(6, 2), path=[(5, 2), (6, 2)]).apply()
    assert result is not None and not result.canceled
    assert target.position == (6, 2)
    fear_uuid = target.active_conditions["Frightened"].uuid
    cast_eyebite(caster, target, "panicked")
    assert tile.remove_condition(DREAD_RESIDUE.name)
    assert target.active_conditions["Frightened"].uuid == fear_uuid
    assert any(condition.get_display_name() == "Eyebite Panicked" for condition in target.active_conditions.values())
    assert target.attack_bonus().advantage is AdvantageStatus.DISADVANTAGE
    caster.set_invisible(True)
    Entity.update_all_entities_senses(max_distance=140)
    assert target.attack_bonus().advantage is AdvantageStatus.NONE
    caster.remove_condition("Concentrating")
    assert "Frightened" not in target.active_conditions


def test_repeated_panicked_from_the_same_cast_replaces_only_its_own_contribution():
    caster, target = scene()
    cast_eyebite(caster, target, "panicked")
    shared_uuid = target.active_conditions["Frightened"].uuid
    caster.action_economy.reset_all_costs()
    strike = caster.get_action_template("Eyebite Strike")
    assert strike is not None
    with fixed_dice_faces(10):
        result = strike.instantiate(target_entity_uuid=target.uuid).apply()
    assert result is not None and not result.canceled
    assert target.active_conditions["Frightened"].uuid == shared_uuid
    assert sum(condition.get_display_name() == "Eyebite Panicked"
        for condition in target.active_conditions.values()) == 1
    caster.remove_condition("Concentrating")
    assert "Frightened" not in target.active_conditions
    assert target.attack_bonus().advantage is AdvantageStatus.NONE
    assert target.ability_check_bonus(None, "strength").advantage is AdvantageStatus.NONE
