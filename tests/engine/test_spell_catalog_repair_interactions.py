"""Observable ownership, native clocks and factual publication after the catalog repair."""
from uuid import uuid4

import pytest

from dnd.actions import entity_action_economy_cost_evaluator
from dnd.core.base_actions import BaseAction, Cost, TargetType
from dnd.conditions import Charmed, Concentrating
from dnd.core.base_conditions import ConditionApplicationEvent, ConditionStateChangedEvent
from dnd.core.creature_types import DamageType, Size
from dnd.core.dice import fixed_dice_faces
from dnd.core.events import EventHandler, Trigger, Event, EventPhase, EventQueue, EventType
from dnd.spells.abjuration import GreaterRestoration, ProtectionFromEnergy, ShieldOfFaith, Stoneskin
from dnd.player.event_record import encode_event, decode_event
from dnd.spells.evocation import Fireball, TrueStrike
from tests.engine.test_bg3_spell_hit_riders import equip
from dnd.spells.divination import Guidance
from dnd.spells.enchantment import Bane, Bless, CharmPerson, HoldPerson
from dnd.spells.illusion import HypnoticPattern, Blur, GreaterInvisibility, Invisibility
from dnd.entity import Entity
from dnd.spells.necromancy import BestowCurse, ChillTouch, NoHealing
from dnd.spells.transmutation import BonusDash, EnhanceAbility, EnlargeReduce, ExpeditiousRetreat, Haste
from tests.engine.test_bg3_rank_one_two_spells import combatant
from tests.engine.test_spell_catalog_audit_gameplay_regressions import cast
from tests.engine.test_spell_catalog_audit_admission_regressions import recipient_effect_state
from tests.engine.test_spell_reaction_admission_repairs import deny
from tests.engine.test_roster_support_spells import game as game
from tests.manual.spell_regression_support import force_save_result


@pytest.mark.parametrize("before,after", [("enlarge", "enlarge"), ("enlarge", "reduce"), ("reduce", "enlarge"), ("reduce", "reduce")])
def test_size_replacement_and_durable_change_use_current_owners(game, before, after):
    caster = combatant(game)
    target = combatant(game, "Recipient", (3, 2))
    cast(EnlargeReduce, caster, target, enlarge_mode=before)
    cast(EnlargeReduce, caster, target, enlarge_mode=after)
    size = target.size
    assert size is (Size.LARGE if after == "enlarge" else Size.SMALL)
    structural = uuid4()
    target.add_structural_size_source(structural, Size.LARGE)
    size = target.size
    assert size is (Size.HUGE if after == "enlarge" else Size.MEDIUM)
    caster.remove_condition("Concentrating")
    size = target.size
    assert size is Size.LARGE
    target.remove_structural_size_source(structural)
    size = target.size
    assert size is Size.MEDIUM


@pytest.mark.parametrize("base,mode", [(Size.TINY, "reduce"), (Size.GARGANTUAN, "enlarge")])
def test_temporary_size_clamps_to_authored_bounds(game, base, mode):
    caster = combatant(game)
    source = uuid4()
    caster.add_structural_size_source(source, base)
    cast(EnlargeReduce, caster, caster, enlarge_mode=mode)
    size = caster.size
    assert size is base
    caster.remove_condition("Concentrating")
    size = caster.size
    assert size is base


def test_retreat_replaces_only_its_exact_dash_and_pays_bonus_cost(game):
    caster = combatant(game)
    independent = BonusDash(source_entity_uuid=caster.uuid, template=True)
    caster.register_action(independent)
    cast(ExpeditiousRetreat, caster)
    first = next(a.uuid for a in caster.registered_actions if a.contribution_owner_uuid is not None and isinstance(a, BonusDash))
    cast(ExpeditiousRetreat, caster)
    owned = next(a for a in caster.registered_actions if a.contribution_owner_uuid is not None and isinstance(a, BonusDash))
    identities = {a.uuid for a in caster.registered_actions}
    assert first not in identities and independent.uuid in identities
    caster.action_economy.reset_all_costs()
    before = caster.action_economy.movement_remaining()
    result = owned.model_copy(update={"template": False}).apply()
    accepted = result is not None and not result.canceled
    bonus = caster.action_economy.bonus_actions.normalized_score
    movement = caster.action_economy.movement_remaining()
    assert accepted and bonus == 0 and movement > before
    caster.remove_condition("Concentrating")
    identities = {a.uuid for a in caster.registered_actions}
    assert owned.uuid not in identities and independent.uuid in identities


@pytest.mark.parametrize("spell", [Guidance, Haste, Blur, BestowCurse, Invisibility, GreaterInvisibility, EnhanceAbility, EnlargeReduce, ShieldOfFaith, Stoneskin, ProtectionFromEnergy])
def test_refused_replacement_preserves_previous_concentration_and_effects(game, spell):
    caster = combatant(game)
    target = combatant(game, "Recipient", (3, 2))
    force_save_result(target, "wisdom", succeeds=False)
    cast(Bless, caster, target)
    sustain = caster.active_conditions["Concentrating"].uuid
    before = recipient_effect_state(target)
    deny(caster, EventType.CAST_SPELL, EventPhase.EFFECT)
    caster.action_economy.reset_all_costs()
    result = spell(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid, alt_skip_slot=True).apply()
    canceled = result.canceled
    after = recipient_effect_state(target)
    concentration = caster.active_conditions["Concentrating"].uuid
    assert canceled and concentration == sustain and after == before


def test_chill_touch_one_source_can_affect_two_recipients_until_its_turn(game):
    caster = combatant(game)
    targets = [combatant(game, "First", (3, 2), "foes"), combatant(game, "Second", (4, 2), "foes")]
    for target in targets:
        with fixed_dice_faces(20, 20, *([2] * 10)):
            cast(ChillTouch, caster, target)
    blocked = [target.receive_healing(5, target.uuid) for target in targets]
    assert blocked == [0, 0]
    targets[0].add_condition(NoHealing(source_entity_uuid=targets[0].uuid, target_entity_uuid=targets[0].uuid))
    caster.on_turn_start()
    healed = [target.receive_healing(5, target.uuid) for target in targets]
    assert healed == [0, 4]


def test_independent_charmers_keep_their_own_relationship_and_generic_charm(game):
    first = combatant(game)
    second = combatant(game, "Second charmer", (2, 3))
    target = combatant(game, "Recipient", (3, 2), "foes")
    force_save_result(target, "wisdom", succeeds=False)
    cast(CharmPerson, first, target)
    cast(CharmPerson, second, target)
    owners = [c for c in target.active_conditions_by_uuid.values() if c.get_display_name() == "Charm Person"]
    relationships = {c.source_entity_uuid for c in target.active_conditions_by_uuid.values() if c.get_display_name() == "Charmed"}
    assert relationships == {first.uuid, second.uuid}
    target.remove_condition_by_uuid(next(c.uuid for c in owners if c.source_entity_uuid == first.uuid))
    relationships = {c.source_entity_uuid for c in target.active_conditions_by_uuid.values() if c.get_display_name() == "Charmed"}
    assert relationships == {second.uuid}
    generic = Charmed(source_entity_uuid=first.uuid, target_entity_uuid=target.uuid)
    target.add_condition(generic)
    target.receive_damage(1, DamageType.FORCE, second.uuid)
    remaining = {c.uuid for c in target.active_conditions_by_uuid.values()}
    assert generic.uuid in remaining
    charms = [c for c in target.active_conditions_by_uuid.values() if c.get_display_name() == "Charm Person"]
    assert not charms


@pytest.mark.parametrize("rank,rounds,concentrating", [(3, 10, True), (4, 20, True), (5, 50, True), (6, 100, True), (7, 14400, False), (8, 14400, False), (9, None, False)])
def test_curse_uses_explicit_bg3_and_srd_rank_deadlines(game, rank, rounds, concentrating):
    caster = combatant(game)
    target = combatant(game, "Recipient", (3, 2), "foes")
    force_save_result(target, "wisdom", succeeds=False)
    cast(BestowCurse, caster, target, cast_at_level=rank)
    deadline = target.active_conditions["Bestow Curse"].duration.duration
    sustained = "Concentrating" in caster.active_conditions
    assert deadline == rounds and sustained is concentrating


def test_concentration_unchanged_publication_ignores_unrelated_history(game):
    caster = combatant(game)
    cast(Haste, caster)
    condition = caster.active_conditions["Concentrating"]
    assert isinstance(condition, Concentrating)
    for _ in range(1000):
        Event(source_entity_uuid=caster.uuid, target_entity_uuid=caster.uuid, event_type=EventType.BASE_ACTION, phase=EventPhase.COMPLETION)
    cursor = EventQueue.event_cursor()
    condition.publish_owner_state(None)
    published = [event for _, event in EventQueue.iter_events_since(cursor) if isinstance(event, ConditionStateChangedEvent)]
    assert not published


@pytest.mark.parametrize("spell,name", [(HoldPerson,"Hold Person"), (Bless,"Bless"), (Bane,"Bane"), (Haste,"Haste"), (Blur,"Blur"), (BestowCurse,"Bestow Curse")])
def test_finite_spell_expires_through_real_turn_events(game, spell, name):
    caster = combatant(game)
    target = caster if spell is Blur else combatant(game, "Recipient", (3, 2), "foes" if spell in (Bane, HoldPerson, BestowCurse) else "heroes")
    force_save_result(target, "wisdom", succeeds=False)
    force_save_result(target, "charisma", succeeds=False)
    cast(spell, caster, target)
    for number in range(1,10):
        target.on_turn_start(round_number=number)
        target.on_turn_end(round_number=number)
    retained = name in target.active_conditions
    assert retained
    target.on_turn_start(round_number=10)
    expired = name not in target.active_conditions
    assert expired


def test_concentration_publication_survives_passive_observer_error(game):
    caster = combatant(game)
    cast(Haste, caster)
    force_save_result(caster, "constitution", succeeds=True)
    caster.receive_damage(1, DamageType.FORCE, caster.uuid)
    concentration = caster.active_conditions["Concentrating"]
    def failed_observer(event):
        if isinstance(event, ConditionStateChangedEvent):
            raise RuntimeError("Stored observation consumer failed")
    EventQueue.add_on_event_callback(failed_observer)
    try:
        concentration.publish_owner_state(None)
    finally:
        EventQueue.remove_on_event_callback(failed_observer)
    cursor = EventQueue.event_cursor()
    concentration.publish_owner_state(None)
    duplicated = [event for _,event in EventQueue.iter_events_since(cursor) if isinstance(event, ConditionStateChangedEvent)]
    assert not duplicated


@pytest.mark.parametrize("spell_name", ["person", "pattern"])
@pytest.mark.parametrize("veto", [False, True])
def test_restoration_cures_source_specific_charm_owner_and_honors_removal_veto(game, spell_name, veto):
    caster = combatant(game, "Charmer", (5,2))
    target = combatant(game, "Charmed", (10,2), "foes")
    healer = combatant(game, "Healer", (2,2), "foes")
    force_save_result(target, "wisdom", succeeds=False)
    spell = CharmPerson if spell_name == "person" else HypnoticPattern
    cast(spell, caster, target, **({"end_position": target.position} if spell_name == "pattern" else {}))
    if veto:
        target.add_event_handler(EventHandler(name="Preserve charm owner", source_entity_uuid=target.uuid,
            trigger_conditions=[Trigger(event_type=EventType.CONDITION_REMOVAL, event_phase=EventPhase.EFFECT,
                event_target_entity_uuid=target.uuid)],
            event_processor=lambda event, _: event.cancel(status_message="Charm removal refused")))
    Entity.update_entity_position(healer, (9,2))
    cast(GreaterRestoration, healer, target)
    relationships = [c for c in target.active_conditions_by_uuid.values() if c.get_display_name() == "Charmed"]
    sustained = [c for c in target.active_conditions_by_uuid.values() if c.get_display_name() in {"Charm Person","Hypnotic Pattern"}]
    assert bool(relationships) is veto and bool(sustained) is veto


def test_true_strike_effect_refusal_prevents_its_native_weapon_attack(game):
    caster = combatant(game)
    target = combatant(game, "Recipient", (3,2), "foes")
    equip(caster)
    before = target.get_hp()
    deny(caster, EventType.CAST_SPELL, EventPhase.EFFECT)
    with fixed_dice_faces(20, *([2]*20)):
        result = TrueStrike(source_entity_uuid=caster.uuid, target_entity_uuid=target.uuid).apply()
    canceled = result.canceled
    hp = target.get_hp()
    assert canceled and hp == before


def test_refused_multi_recipient_cast_records_no_children_or_replacement(game):
    caster = combatant(game)
    first = combatant(game, "First", (3,2))
    second = combatant(game, "Second", (4,2))
    cast(Bless, caster, first)
    concentration = caster.active_conditions["Concentrating"].uuid
    states = [recipient_effect_state(target) for target in (first, second)]
    deny(caster, EventType.CAST_SPELL, EventPhase.EFFECT)
    caster.action_economy.reset_all_costs()
    cursor = EventQueue.event_cursor()
    result = Bless(source_entity_uuid=caster.uuid, target_entity_uuid=first.uuid,
        extra_target_entity_uuids=[second.uuid], cast_at_level=3, alt_skip_slot=True).apply()
    canceled = result.canceled
    after = [recipient_effect_state(target) for target in (first, second)]
    sustain = caster.active_conditions["Concentrating"].uuid
    decoded = [decode_event(encode_event(event)) for _,event in EventQueue.iter_events_since(cursor)]
    created = [event.condition_state.name for event in decoded
        if isinstance(event, ConditionApplicationEvent) and event.phase is EventPhase.COMPLETION
        and event.condition_state is not None]
    assert canceled and states == after and sustain == concentration
    declared = set(result.declared_target_entity_uuids)
    assert declared == {first.uuid, second.uuid}
    assert not created


@pytest.mark.parametrize("harmful", [False, True])
@pytest.mark.parametrize("secondary_only", [False, True])
def test_charmed_honors_authored_direct_ability_intent_at_admission(game, harmful, secondary_only):
    charmer = combatant(game)
    actor = combatant(game, "Charmed", (3,2), "foes")
    actor.add_condition(Charmed(source_entity_uuid=charmer.uuid, target_entity_uuid=actor.uuid))
    action = BaseAction(name="Authored ability", source_entity_uuid=actor.uuid,
        target_entity_uuid=None if secondary_only else charmer.uuid,
        extra_target_entity_uuids=[charmer.uuid] if secondary_only else [],
        harmful=harmful, target_type=TargetType.MULTI_ENTITY if secondary_only else TargetType.ENTITY,
        costs=[Cost(name="Ability action",cost_type="actions",cost=1,evaluator=entity_action_economy_cost_evaluator)])
    result = action.apply()
    canceled = result.canceled
    remaining = actor.action_economy.actions.normalized_score
    assert canceled is harmful
    if harmful:
        assert remaining == 1


def test_charmed_does_not_make_the_charmer_immune_to_incidental_area_damage(game):
    charmer = combatant(game)
    actor = combatant(game, "Charmed", (6,2), "foes")
    actor.add_condition(Charmed(source_entity_uuid=charmer.uuid, target_entity_uuid=actor.uuid))
    force_save_result(charmer,"dexterity",succeeds=False)
    before = charmer.get_hp()
    with fixed_dice_faces(*([2]*100)):
        result = Fireball(source_entity_uuid=actor.uuid,end_position=charmer.position).apply()
    canceled = result.canceled
    hp = charmer.get_hp()
    assert not canceled and hp < before
