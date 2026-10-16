"""Native target/condition admission, exact sustain ownership and paid siblings.

These desired-behavior cases fail against the task-start spell implementations.
The caster, targets, registered repeat actions and all vetoes are real engine
objects. Snapshots and witnesses are bounded native state/facts, not mocks.
"""

import random

import pytest

from dnd.conditions import Blinded, Deafened
from dnd.core.creature_types import DamageType
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import EventHandler, EventPhase, EventType, Trigger
from dnd.core.gridmap import get_map
from dnd.core.modifiers import NumericalModifier
from dnd.spells.abjuration import Aid, BeaconOfHope
from dnd.spells.conjuration import AcidSplash, CallLightning
from dnd.spells.enchantment import Bane, Bless, HoldMonster, HoldPerson, Sleep
from dnd.spells.evocation import (
    BurningHands,
    ConeOfCold,
    DivineWord,
    FlameStrike,
    GustOfWind,
    LightningBolt,
    MagicMissile,
    MassCureWounds,
    MassHeal,
    MassHealingWord,
    PrayerOfHealing,
    PrismaticSpray,
    Shatter,
    Sunbeam,
    Thunderwave,
)
from dnd.spells.illusion import ColorSpray, Fear, HypnoticPattern
from dnd.spells.necromancy import BlindnessDeafness
from dnd.spells.transmutation import (
    CreateOrDestroyWater,
    EnhanceAbility,
    Haste,
    RainWetEffect,
    Slow,
)
from tests.engine.test_high_level_spell_controls import high_actor
from tests.engine.test_roster_support_spells import game as game  # noqa: PLC0414 - pytest fixture export
from tests.manual.spell_regression_support import force_save_result

TARGET_SPELLS = (
    AcidSplash, Aid, Bane, BeaconOfHope, BlindnessDeafness, Bless, BurningHands,
    CallLightning, ColorSpray, ConeOfCold, DivineWord, Fear, FlameStrike,
    GustOfWind, HoldMonster, HypnoticPattern, LightningBolt, MagicMissile,
    MassCureWounds, MassHeal, MassHealingWord, PrayerOfHealing, PrismaticSpray,
    Shatter, Sleep, Slow, Thunderwave,
)
HEALING_SPELLS = (MassCureWounds, MassHeal, MassHealingWord, PrayerOfHealing)
FRIENDLY_SPELLS = (Aid, BeaconOfHope, Bless, *HEALING_SPELLS)
SUSTAINED_CONDITIONS = (Bane, BeaconOfHope, Bless, Fear, HoldMonster, HoldPerson, HypnoticPattern, Slow)


def state(actor):
    return {
        "hp": actor.get_hp(), "maximum_hp": actor.get_max_hp(),
        "temporary_hp": actor.health.temporary_hit_points.normalized_score,
        "life": actor.health.life_state.value, "position": actor.position,
        "conditions": frozenset(actor.active_conditions),
    }


def listen(actor, kinds, processor, *, target_uuid=None):
    handler = EventHandler(
        source_entity_uuid=actor.uuid,
        trigger_conditions=[Trigger(
            event_type=kind, event_phase=EventPhase.EFFECT,
            **({"event_target_entity_uuid": target_uuid} if target_uuid is not None else
               {"event_source_entity_uuid": actor.uuid}),
        ) for kind in kinds],
        event_processor=processor,
    )
    actor.add_event_handler(handler)
    return handler


def cast(spell):
    previous_random = random.getstate()
    try:
        random.seed(1)
        with fixed_dice_faces(*([4] * 200)):
            result = spell.apply()
    finally:
        random.setstate(previous_random)
    assert result is not None
    return result


def prepare_targets(game, spell_type):
    caster = high_actor(game)
    faction = "heroes" if spell_type in FRIENDLY_SPELLS else "foes"
    first = high_actor(game, "First", (3, 2), faction)
    second = high_actor(game, "Second", (4, 3) if spell_type is GustOfWind else (4, 2), faction)
    for recipient in (first, second):
        if spell_type in HEALING_SPELLS:
            recipient.receive_damage(40, DamageType.FORCE, caster.uuid)
        if spell_type in (Sleep, ColorSpray, DivineWord):
            recipient.receive_damage(recipient.get_hp() - 5, DamageType.FORCE, caster.uuid)
        for ability in ("wisdom", "constitution", "dexterity", "charisma", "strength"):
            force_save_result(recipient, ability, succeeds=False)
    return caster, first, second


@pytest.mark.parametrize("spell_type", TARGET_SPELLS, ids=lambda kind: kind.__name__)
@pytest.mark.parametrize("mode", ["admitted", "root_refused", "all_children_refused", "first_recipient_refused"])
def test_refused_target_has_no_effect_and_admitted_siblings_continue(game, spell_type, mode):
    caster, first, second = prepare_targets(game, spell_type)
    before = state(first), state(second)
    refused, committed = set(), []

    def refuse(event, _):
        reject = (
            mode == "root_refused" and event.application is None
            or mode == "all_children_refused" and event.application is not None
            or mode == "first_recipient_refused" and event.application is not None
            and event.target_entity_uuid == first.uuid
        )
        if reject:
            refused.add(event.lineage_uuid)
            return event.cancel(status_message="Target admission repair regression")
        return event

    def record_commit(event, _):
        committed.append(event.target_entity_uuid)

    listen(caster, (EventType.CAST_SPELL,), refuse)
    listen(caster, (EventType.ACTION_APPLICATION_COMMITTED,), record_commit)
    result = cast(spell_type(
        source_entity_uuid=caster.uuid, target_entity_uuid=first.uuid,
        extra_target_entity_uuids=[second.uuid], end_position=first.position,
        **({"cast_at_level": {BlindnessDeafness: 3, HoldMonster: 6}[spell_type]}
           if spell_type in (BlindnessDeafness, HoldMonster) else {}),
    ))
    after = state(first), state(second)
    assert bool(refused) is (mode != "admitted")
    if mode == "root_refused":
        canceled = result.canceled
        assert canceled
    if mode in ("root_refused", "all_children_refused", "first_recipient_refused"):
        assert after[0] == before[0]
        assert first.uuid not in committed
    else:
        assert after[0] != before[0]
        assert first.uuid in committed
    if mode in ("root_refused", "all_children_refused"):
        assert after[1] == before[1]
        assert second.uuid not in committed
    else:
        assert after[1] != before[1]
        assert second.uuid in committed


@pytest.mark.parametrize("spell_type", SUSTAINED_CONDITIONS, ids=lambda kind: kind.__name__)
@pytest.mark.parametrize("boundary", ["target_effect", "target_condition", "concentration"])
def test_refused_sustain_preserves_previous_exact_concentration(game, spell_type, boundary):
    caster = high_actor(game)
    target = high_actor(game, "Only recipient", (3, 2),
                        "heroes" if spell_type in FRIENDLY_SPELLS else "foes")
    for ability in ("wisdom", "charisma"):
        force_save_result(target, ability, succeeds=False)
    initial = cast(Haste(source_entity_uuid=caster.uuid, target_entity_uuid=caster.uuid))
    initial_canceled = initial.canceled
    assert not initial_canceled
    old_concentration = caster.active_conditions["Concentrating"].uuid
    old_haste = caster.active_conditions["Haste"].uuid
    caster.action_economy.reset_all_costs()
    before = state(target)
    refused = []

    def refuse(event, _):
        if boundary == "target_effect":
            selected = event.target_entity_uuid == target.uuid and (
                spell_type is HoldPerson or event.application is not None
            )
        else:
            selected = event.target_entity_uuid == (caster.uuid if boundary == "concentration" else target.uuid)
            if boundary == "concentration":
                selected = selected and event.condition.name == "Concentrating"
        if selected:
            refused.append(event.lineage_uuid)
            return event.cancel(status_message="Keep previous exact sustain")
        return event

    listen(caster, (EventType.CAST_SPELL,) if boundary == "target_effect" else
           (EventType.CONDITION_APPLICATION,), refuse)
    cast(spell_type(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid, end_position=target.position))
    actual = (caster.active_conditions.get("Concentrating"), caster.active_conditions.get("Haste"))
    retained = tuple(condition.uuid if condition is not None else None for condition in actual)
    after = state(target)
    assert len(refused) > 0
    assert retained == (old_concentration, old_haste)
    assert after == before


@pytest.mark.parametrize("spell_type", [Bane, HoldMonster, HoldPerson], ids=lambda kind: kind.__name__)
def test_admitted_all_saved_cast_keeps_its_existing_concentration_replacement_policy(game, spell_type):
    caster = high_actor(game)
    target = high_actor(game, "Successful saver", (3, 2), "foes")
    cast(Haste(source_entity_uuid=caster.uuid, target_entity_uuid=caster.uuid))
    caster.action_economy.reset_all_costs()
    force_save_result(target, "wisdom" if spell_type is not Bane else "charisma", succeeds=True)
    before = state(target)
    result = cast(spell_type(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid))
    canceled = result.canceled
    haste_retained = "Haste" in caster.active_conditions
    assert not canceled
    assert not haste_retained
    after = state(target)
    assert after == before


def test_magic_missile_refused_middle_dart_keeps_ordinals_siblings_and_one_paid_cast(game):
    caster = high_actor(game)
    target = high_actor(game, "Dart recipient", (3, 2), "foes")
    hp_before = target.get_hp()
    slots_before = caster.action_economy.spell_slot_value(1).normalized_score
    seen, committed = [], []

    def veto_middle(event, _):
        if event.application is None:
            return event
        seen.append(event.application.index)
        if event.application.index == 1:
            return event.cancel(status_message="Only middle dart is refused")
        return event

    def record_commit(event, _):
        committed.append(event.target_entity_uuid)

    listen(caster, (EventType.CAST_SPELL,), veto_middle)
    listen(caster, (EventType.ACTION_APPLICATION_COMMITTED,), record_commit)
    result = cast(MagicMissile(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid))
    actual = {
        "damage": hp_before - target.get_hp(), "reported_damage": result.total_damage,
        "slots": caster.action_economy.spell_slot_value(1).normalized_score,
        "actions": caster.action_economy.actions.normalized_score,
        "ordinals": seen, "commits": len(committed),
    }
    assert actual == {"damage": 10, "reported_damage": 10, "slots": slots_before - 1,
                      "actions": 0, "ordinals": [0, 1, 2], "commits": 2}


@pytest.mark.parametrize("boundary", ["admitted", "target_condition", "concentration"])
def test_enhance_ability_grants_temp_hp_only_after_both_admissions(game, boundary):
    caster = high_actor(game)
    target = high_actor(game, "Recipient", (3, 2))
    cast(Haste(source_entity_uuid=caster.uuid, target_entity_uuid=caster.uuid))
    old_concentration = caster.active_conditions["Concentrating"].uuid
    caster.action_economy.reset_all_costs()
    target.health.add_temporary_hit_points(3, target.uuid)
    old_grant = target.health.temporary_hit_points_grant
    before = state(target)
    refused = []

    def refuse(event, _):
        selected = (
            boundary == "target_condition" and event.target_entity_uuid == target.uuid
            or boundary == "concentration" and event.target_entity_uuid == caster.uuid
            and event.condition.name == "Concentrating"
        )
        if selected:
            refused.append(event.lineage_uuid)
            return event.cancel(status_message="Reject Enhance Ability admission")
        return event

    listen(caster, (EventType.CONDITION_APPLICATION,), refuse)
    result = cast(EnhanceAbility(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid,
                                 enhance_ability_type="constitution"))
    after = state(target)
    canceled = result.canceled
    assert bool(refused) is (boundary != "admitted")
    assert canceled is (boundary != "admitted")
    if boundary == "admitted":
        assert after["temporary_hp"] == 8
    else:
        grant = target.health.temporary_hit_points_grant
        concentration_uuid = caster.active_conditions["Concentrating"].uuid
        assert after == before
        assert grant == old_grant
        assert concentration_uuid == old_concentration


@pytest.mark.parametrize("refused", [False, True])
def test_hold_person_honors_its_single_target_effect_boundary(game, refused):
    caster, target, _ = prepare_targets(game, HoldPerson)
    before = state(target)
    witnesses = []

    def veto(event, _):
        if refused:
            witnesses.append(event.lineage_uuid)
            return event.cancel(status_message="Refuse Hold Person")
        return event

    listen(caster, (EventType.CAST_SPELL,), veto)
    result = cast(HoldPerson(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid))
    canceled = result.canceled
    after = state(target)
    assert canceled is refused
    assert bool(witnesses) is refused
    assert (after == before) is refused


@pytest.mark.parametrize("refused", [False, True])
def test_rain_recipient_refusal_preserves_independent_admitted_water_surface(game, refused):
    caster = high_actor(game)
    target = high_actor(game, "Rain recipient", (3, 2))
    witnesses = []

    def veto(event, _):
        if refused and event.application is not None and event.target_entity_uuid == target.uuid:
            witnesses.append(event.lineage_uuid)
            return event.cancel(status_message="Refuse direct rain lease")
        return event

    listen(caster, (EventType.CAST_SPELL,), veto)
    result = cast(CreateOrDestroyWater(source_entity_uuid=caster.uuid,
        target_entity_uuid=target.uuid, end_position=target.position))
    canceled = result.canceled
    rain = any(isinstance(condition, RainWetEffect) for condition in target.active_conditions_by_uuid.values())
    water = any(zone.name == "Wet Surface" for zone in get_map().get_spatial_conditions())
    assert not canceled
    assert bool(witnesses) is refused
    assert rain is (not refused)
    assert water


@pytest.mark.parametrize("spell_type,repeat_name", [(CallLightning, "Call Lightning Strike"), (Sunbeam, "Sunbeam Strike")])
@pytest.mark.parametrize("refused", [False, True])
def test_real_retained_repeat_action_honors_each_target_admission(game, spell_type, repeat_name, refused):
    caster = high_actor(game)
    target = high_actor(game, "Recipient", (6, 2), "foes")
    for ability in ("dexterity", "constitution"):
        force_save_result(target, ability, succeeds=False)
    initial = cast(spell_type(source_entity_uuid=caster.uuid, end_position=target.position))
    canceled = initial.canceled
    assert not canceled
    template = caster.get_action_template(repeat_name)
    assert template is not None
    caster.action_economy.reset_all_costs()
    before = state(target)
    witnesses = []

    def veto(event, _):
        if refused and event.application is not None and event.target_entity_uuid == target.uuid:
            witnesses.append(event.lineage_uuid)
            return event.cancel(status_message="Refuse retained activation recipient")
        return event

    listen(caster, (EventType.CAST_SPELL, EventType.BASE_ACTION), veto)
    cast(template.instantiate(end_position=target.position))
    after = state(target)
    grant_retained = caster.get_action_template(repeat_name) is not None
    assert bool(witnesses) is refused
    assert (after == before) is refused
    assert grant_retained


@pytest.mark.parametrize("boundary", ["target_effect", "healing_effect"])
def test_mass_heal_refused_recipient_does_not_spend_later_recipients_pool(game, boundary):
    caster, first, second = prepare_targets(game, MassHeal)
    for target in (first, second):
        target.health.max_hit_points_bonus.self_static.add_value_modifier(
            NumericalModifier(source_entity_uuid=target.uuid, value=1000)
        )
        target.receive_damage(860, DamageType.FORCE, caster.uuid)
    before = first.get_hp(), second.get_hp()
    first.add_condition(Blinded(source_entity_uuid=first.uuid, target_entity_uuid=first.uuid))
    first.add_condition(Deafened(source_entity_uuid=first.uuid, target_entity_uuid=first.uuid))
    witnesses = []

    def veto(event, _):
        if boundary == "target_effect" and event.application is None:
            return event
        if event.target_entity_uuid == first.uuid:
            witnesses.append(event.lineage_uuid)
            return event.cancel(status_message="Preserve remaining healing pool")
        return event

    listen(caster, (EventType.CAST_SPELL,) if boundary == "target_effect" else (EventType.HEAL,), veto)
    action = MassHeal(source_entity_uuid=caster.uuid, target_entity_uuid=first.uuid,
                      extra_target_entity_uuids=[second.uuid])
    cast(action)
    hp_after = first.get_hp(), second.get_hp()
    pool_after = action.healing_pool_remaining
    assert len(witnesses) > 0
    assert hp_after == (before[0], before[1] + 700)
    assert pool_after == 0
    if boundary == "target_effect":
        retained = frozenset(first.active_conditions)
        assert {"Blinded", "Deafened"} <= retained
    else:
        retained = frozenset(first.active_conditions)
        assert not {"Blinded", "Deafened"} & retained


@pytest.mark.parametrize("boundary", ["admitted", "condition_effect", "previous_removal"])
def test_divine_word_lethal_effect_requires_condition_commit(game, boundary):
    caster = high_actor(game)
    target = high_actor(game, "Divine Word recipient", (3, 2), "foes")
    target.receive_damage(target.get_hp() - 45, DamageType.FORCE, caster.uuid)
    old_word = None
    if boundary == "previous_removal":
        initial = cast(DivineWord(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid))
        initial_canceled = initial.canceled
        assert not initial_canceled
        old_word = target.active_conditions["Divine Word"].uuid
        caster.action_economy.reset_all_costs()
    target.receive_damage(target.get_hp() - 10, DamageType.FORCE, caster.uuid)
    before = state(target)
    witnesses = []

    def veto(event, _):
        if boundary == "condition_effect" or event.condition.uuid == old_word:
            witnesses.append(event.lineage_uuid)
            return event.cancel(status_message="Reject lethal condition commitment")
        return event

    if boundary != "admitted":
        listen(caster, (EventType.CONDITION_APPLICATION,) if boundary == "condition_effect" else
               (EventType.CONDITION_REMOVAL,), veto, target_uuid=target.uuid)
    cast(DivineWord(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid))
    after = state(target)
    assert bool(witnesses) is (boundary != "admitted")
    if boundary == "admitted":
        assert after["life"] == "dead"
    else:
        assert after == before
        if boundary == "previous_removal":
            retained_uuid = target.active_conditions["Divine Word"].uuid
            assert retained_uuid == old_word
