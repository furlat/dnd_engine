"""Real summon damage packets retain their public source, not inferred bonuses.

Inputs: native Conjure Elemental bodies, real prerequisite conditions and attacks.
Boundary: admitted Entity.perform actions and detached per-seat PlayerUpdates.
Outputs: exact source damage UUIDs/content, actual gear identity, affinity results,
and Tenacity's condition UUID; unseen sources and ordinary damage stay distinct.
"""

import random

import pytest

from dnd.actions import AttackEvent
from dnd.actions_functional import execute_available_action, get_available_actions
from dnd.conditions import Invisible, Prone
from dnd.core.creature_types import DamageType
from dnd.core.dice import AttackOutcome, fixed_dice_faces
from dnd.core.equipment_types import WeaponSlot, WeaponUsage
from dnd.core.events import DamageRollResultEvent, EventPhase, EventQueue
from dnd.core.modifiers import NumericalModifier
from dnd.core.values import Channel, Kind, add_modifier
from dnd.monsters.spell_summon_actions import (
    Burning, Chilled, ElementalMultiattackBonus, MyrmidonStrikeDice, MyrmidonTenacity, Shocked,
)
from dnd.monsters.traits import SpellDamageResistance
from dnd.player.application import capture_application_operation, initialize_audiences
from dnd.player.audience import PlayerAudience
from dnd.player.content_composition import ui_content_manifest
from dnd.player.facts import AttackFact, DamageResultFact, PlayerUpdate
from dnd.player.session import close_session, create_session
from dnd.spells.summoning import ConjureElemental
from dnd.types.character_progression import CharacterClass
from tests.player.test_emitted_update_replica import operation_since
from tests.progression.prepared_class_support import prepared_build


@pytest.fixture
def contact():
    previous_random = random.getstate()
    random.seed(6)
    session = create_session(player_builds=(prepared_build(CharacterClass.WIZARD, 11),),
        enemy_positions=((14, 10), (14, 12)))
    caster = session.game.entities[session.player_uuids[0]]
    target = next(actor for actor in session.game.entities.values()
        if actor.position == (14, 10) and caster.is_enemy(actor))
    add_modifier(target.health.max_hit_points_bonus, Channel.SELF_STATIC, Kind.VALUE,
        NumericalModifier(name='Survive attributed summon attacks', value=500, source_entity_uuid=target.uuid))
    add_modifier(target.equipment.ac_bonus, Channel.SELF_STATIC, Kind.VALUE,
        NumericalModifier(name='Deterministic noncritical hits', value=-50, source_entity_uuid=target.uuid))
    admitted = target.add_condition(SpellDamageResistance(
        source_entity_uuid=target.uuid, target_entity_uuid=target.uuid))
    assert admitted is not None and not admitted.canceled

    def prepare(form, *, hidden=False, prerequisite=None):
        before = set(session.game.entities)
        rank = 5 if form.endswith('elemental') else 6
        # Native slot-six admission is real. The separately known worker choice
        # omission for Myrmidons is not changed or claimed solved by this test.
        result = ConjureElemental(source_entity_uuid=caster.uuid, form_id=form,
            cast_at_level=rank, end_position=(13, 10)).apply()
        assert result is not None and not result.canceled
        identity, = set(session.game.entities) - before
        actor = session.game.entities[identity]
        if prerequisite is not None:
            admitted = target.add_condition(prerequisite(
                source_entity_uuid=actor.uuid, target_entity_uuid=target.uuid))
            assert admitted is not None and not admitted.canceled
        if hidden:
            # The primitive state also models persistent invisibility; no fake
            # source/action identity or attack-breaking wrapper is introduced.
            admitted = actor.add_condition(Invisible(
                source_entity_uuid=actor.uuid, target_entity_uuid=actor.uuid))
            assert admitted is not None and not admitted.canceled
            assert actor.uuid not in target.senses.entities
        session.seats.clear()
        session.seats.update(owner=PlayerAudience((actor.uuid,), (actor.uuid,)),
            recipient=PlayerAudience((target.uuid,), (target.uuid,)))
        catalog = ui_content_manifest()
        audiences, _ = initialize_audiences(session, catalog)
        return actor, target, audiences, catalog

    try:
        yield session, prepare
    finally:
        close_session(session)
        random.setstate(previous_random)


def publish(session, audiences, catalog, cursor):
    updates = capture_application_operation(audiences, operation_since(session, cursor), catalog)
    return {seat: PlayerUpdate.model_validate_json(update.model_dump_json()) for seat, update in updates.items()}


def facts(update, kind):
    return [node.fact for group in update.lineages for node in group.events if isinstance(node.fact, kind)]


def perform(actor, target, behavior, *, face=2):
    available = get_available_actions(actor)
    row = next(row for row in available.entity_actions if row.behavior_id == behavior
        and any(binding.target_uuid == target.uuid for binding in row.valid_targets))
    binding = next(binding for binding in row.valid_targets if binding.target_uuid == target.uuid)
    cursor = EventQueue.event_cursor()
    with fixed_dice_faces(face, face, *([2] * 200)):
        result = execute_available_action(actor, row, binding)
    assert result is not None and not result.canceled
    return cursor


@pytest.mark.parametrize('form,prerequisite,behavior,condition_kind,semantic', [
    *((form, prerequisite, 'action.monster.multiattack', ElementalMultiattackBonus,
        'condition.summon.elemental_multiattack_bonus') for form, prerequisite in (
            ('air_elemental', Shocked), ('earth_elemental', Prone),
            ('fire_elemental', Burning), ('water_elemental', Chilled))),
    *((form, None, behavior, MyrmidonStrikeDice, 'condition.summon.myrmidon_strike_dice')
      for form, behavior in (('air_myrmidon', 'action.air_myrmidon.electrified_flail'),
          ('fire_myrmidon', 'action.fire_myrmidon.scorching_strike'),
          ('water_myrmidon', 'action.water_myrmidon.hiemal_strike'))),
])
@pytest.mark.parametrize('hidden', [False, True])
def test_summon_bonus_packets_have_exact_public_content_sources(contact, form, prerequisite,
        behavior, condition_kind, semantic, hidden):
    session, prepare = contact
    actor, target, audiences, catalog = prepare(form, hidden=hidden, prerequisite=prerequisite)
    condition, = (condition for condition in actor.active_conditions_by_uuid.values()
        if isinstance(condition, condition_kind))
    assert condition.get_semantic_key() == semantic
    weapon = actor.equipment.get_weapon(WeaponSlot.MELEE_MAIN)
    assert weapon is not None
    assert weapon.usage is (WeaponUsage.BODY if prerequisite is not None else WeaponUsage.HELD)
    cursor = perform(actor, target, behavior)
    updates = publish(session, audiences, catalog, cursor)
    rolls = [event for _, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, DamageRollResultEvent) and event.phase is EventPhase.COMPLETION
        and event.source_entity_uuid == actor.uuid]
    assert len(rolls) == (2 if prerequisite is not None else 1)
    appended = [packet.damage for roll in rolls for packet in (
        roll.damage_packets[condition.packet_count:] if isinstance(condition, ElementalMultiattackBonus)
        else roll.damage_packets[-1:])]
    assert appended
    expected = {damage.uuid for damage in appended}
    for seat, update in updates.items():
        results = facts(update, DamageResultFact)
        assert results and all(fact.target_entity_uuid == target.uuid for fact in results)
        components = [component for fact in results for component in fact.components
            if component.source_damage_uuid in expected]
        assert {component.source_damage_uuid for component in components} == expected
        # Chilled explicitly doubles Cold; Spell Damage Resistance must not
        # halve any of these innate attack packets, including that vulnerability.
        assert all(component.incoming_damage > 0 and component.after_affinity_damage ==
            component.incoming_damage * (2 if form == 'water_elemental'
                and component.damage_type is DamageType.COLD else 1) for component in components)
        if seat == 'recipient' and hidden:
            assert all(component.source_entity_uuid is None and component.source_id is None for component in components)
        else:
            assert all(component.source_entity_uuid == actor.uuid and component.source_id == semantic
                for component in components)
            attacks = facts(update, AttackFact)
            assert attacks and all(attack.source_item_uuid == weapon.uuid for attack in attacks)
    assert all(damage.effect_origin is not None and damage.effect_origin.kind.value == 'action'
        and damage.effect_origin.source_id == semantic for damage in appended)
    assert all(packet.damage.effect_origin.source_position == actor.position
        and packet.damage.effect_origin.source_event_lineage_uuid == str(roll.lineage_uuid)
        for roll in rolls for packet in roll.damage_packets if packet.damage.uuid in expected)
    if isinstance(condition, ElementalMultiattackBonus):
        assert all(extra.attack_magical == original.damage.attack_magical for roll in rolls
            for original, extra in zip(roll.damage_packets[:condition.packet_count],
                (packet.damage for packet in roll.damage_packets[condition.packet_count:]), strict=True))
    else:
        assert all(damage.attack_magical is True for damage in appended)
    cursor = EventQueue.event_cursor()
    # Hiemal Strike applies Chilled after its hit; the ordinary follow-up keeps
    # that native Cold vulnerability but gains no content/condition attribution.
    assert target.receive_damage(5, appended[0].damage_type, actor.uuid) == (
        10 if form == 'water_myrmidon' else 5)
    ordinary = publish(session, audiences, catalog, cursor)
    for update in ordinary.values():
        fact, = facts(update, DamageResultFact)
        assert not fact.components and fact.source_condition_uuid is None


@pytest.mark.parametrize('hidden', [False, True])
def test_tenacity_miss_damage_has_exact_condition_owner(contact, hidden):
    session, prepare = contact
    actor, target, audiences, catalog = prepare('air_myrmidon', hidden=hidden)
    condition, = (condition for condition in actor.active_conditions_by_uuid.values()
        if isinstance(condition, MyrmidonTenacity))
    assert condition.get_semantic_key() == 'condition.summon.tenacity'
    weapon = actor.equipment.get_weapon(WeaponSlot.MELEE_MAIN)
    hp = target.get_normal_hp()
    cursor = perform(actor, target, 'action.attack', face=1)
    assert target.get_normal_hp() == hp - 4
    updates = publish(session, audiences, catalog, cursor)
    for seat, update in updates.items():
        damage, = facts(update, DamageResultFact)
        assert damage.applied_damage == 4 and damage.damage_type is DamageType.BLUDGEONING
        if seat == 'recipient' and hidden:
            assert damage.source_entity_uuid is None and damage.source_condition_uuid is None
        else:
            assert damage.source_entity_uuid == actor.uuid and damage.source_condition_uuid == condition.uuid
            attack, = facts(update, AttackFact)
            assert attack.attack_outcome is AttackOutcome.CRIT_MISS
            assert attack.source_item_uuid == weapon.uuid
            assert attack.attack_source_kind == 'equipped'
    cursor = EventQueue.event_cursor()
    assert target.receive_damage(4, DamageType.BLUDGEONING, actor.uuid) == 4
    ordinary = publish(session, audiences, catalog, cursor)
    for update in ordinary.values():
        fact, = facts(update, DamageResultFact)
        assert fact.source_condition_uuid is None
