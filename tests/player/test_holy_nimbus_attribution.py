"""Real Nimbus contact keeps its exact public owner, without proximity inference.

Input: two prepared level-20 Paladins activate their discovered Nimbus actions.
Boundary: Entity.perform, actual enemy turn start, two independent capture streams.
Output: native and serialized damage identify the emitting condition only when
its owner is identified; ordinary radiant damage never borrows that identity.
"""

from dataclasses import replace
import random

import pytest

from dnd.actions_functional import execute_available_action, get_available_actions
from dnd.classes.paladin import HolyNimbusEffect
from dnd.conditions import Invisible
from dnd.core.creature_types import DamageType
from dnd.core.events import DamageAppliedEvent, EventPhase, EventQueue, TakeDamageEvent
from dnd.core.modifiers import NumericalModifier
from dnd.core.values import Channel, Kind, add_modifier
from dnd.player.application import capture_application_operation, initialize_audiences
from dnd.player.audience import PlayerAudience
from dnd.player.content_composition import ui_content_manifest
from dnd.player.facts import ActorChangeFact, DamageResultFact, PlayerUpdate
from dnd.player.session import close_session, create_session
from dnd.types.actor_facts import ConditionRow
from dnd.types.character_progression import CharacterClass
from tests.player.test_emitted_update_replica import operation_since
from tests.progression.prepared_class_support import prepared_build


@pytest.fixture
def nimbus_arena():
    previous_random = random.getstate()
    random.seed(6)
    build = prepared_build(CharacterClass.PALADIN, 20)
    session = create_session(player_builds=(replace(build, name='First Paladin'),
        replace(build, name='Second Paladin')), player_positions=((12, 10), (13, 10)),
        enemy_positions=((14, 10), (14, 12)))
    try:
        owners = tuple(session.game.entities[identity] for identity in session.player_uuids)
        enemy = next(actor for actor in session.game.entities.values()
            if owners[0].is_enemy(actor) and actor.position == (14, 10))
        add_modifier(enemy.health.max_hit_points_bonus, Channel.SELF_STATIC, Kind.VALUE,
            NumericalModifier(name='Survive distinct Nimbus contacts', value=100,
                source_entity_uuid=enemy.uuid))
        session.seats['recipient'] = PlayerAudience((enemy.uuid,), (enemy.uuid,))
        yield session, owners, enemy
    finally:
        close_session(session)
        random.setstate(previous_random)


def capture(session, audiences, catalog, cursor):
    updates = capture_application_operation(audiences, operation_since(session, cursor), catalog)
    return {seat: PlayerUpdate.model_validate_json(update.model_dump_json())
        for seat, update in updates.items()}


def damage_facts(update, target_uuid):
    return [node.fact for group in update.lineages for node in group.events
        if isinstance(node.fact, DamageResultFact) and node.fact.target_entity_uuid == target_uuid]


@pytest.mark.parametrize('hide_first_owner', [False, True])
def test_nimbus_turn_contact_preserves_exact_owner_and_disclosure(nimbus_arena, hide_first_owner):
    session, owners, enemy = nimbus_arena
    if hide_first_owner:
        admitted = owners[0].add_condition(Invisible(
            source_entity_uuid=owners[0].uuid, target_entity_uuid=owners[0].uuid))
        assert admitted is not None and not admitted.canceled
        assert owners[0].uuid not in enemy.senses.entities
    else:
        assert owners[0].uuid in enemy.senses.entities
    assert owners[1].uuid in enemy.senses.entities
    catalog = ui_content_manifest()
    audiences, _ = initialize_audiences(session, catalog)
    conditions = {}
    for owner in owners:
        cursor = EventQueue.event_cursor()
        action, = (row for row in get_available_actions(owner).self_actions
            if row.behavior_id == 'action.class.paladin.holy_nimbus')
        result = execute_available_action(owner, action, action.valid_targets[0])
        assert result is not None and not result.canceled
        condition, = (condition for condition in owner.active_conditions_by_uuid.values()
            if isinstance(condition, HolyNimbusEffect))
        assert condition.effect_origin is not None
        assert condition.effect_origin.source_id == 'class_feature.paladin.holy_nimbus'
        conditions[owner.uuid] = condition.uuid
        activation = capture(session, audiences, catalog, cursor)
        for seat, update in activation.items():
            memberships = [row.member for group in update.lineages for node in group.events
                if isinstance(node.fact, ActorChangeFact) for actor in node.fact.actors
                if actor.actor_uuid == owner.uuid for row in actor.rows
                if isinstance(row, ConditionRow) and row.member is not None]
            public_owner = any(member.condition_uuid == condition.uuid for member in memberships)
            assert public_owner is not (seat == 'recipient' and hide_first_owner and owner is owners[0])
    assert len(set(conditions.values())) == 2
    assert all(conditions[owner.uuid] in owner.active_conditions_by_uuid for owner in owners)
    if hide_first_owner:
        assert owners[0].uuid not in enemy.senses.entities

    hp = enemy.get_normal_hp()
    cursor = EventQueue.event_cursor()
    turn = enemy.on_turn_start()
    assert not turn.canceled and enemy.get_normal_hp() == hp - 20
    updates = capture(session, audiences, catalog, cursor)
    native = [event for _, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, DamageAppliedEvent) and event.phase is EventPhase.COMPLETION
        and event.target_entity_uuid == enemy.uuid]
    assert len(native) == 2
    requests = [event for _, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, TakeDamageEvent) and event.phase is EventPhase.COMPLETION
        and event.target_entity_uuid == enemy.uuid]
    assert len(requests) == 2 and all(event.effect_origin is not None
        and event.effect_origin.source_id == 'class_feature.paladin.holy_nimbus' for event in requests)
    assert all(event.parent_lineage == turn.lineage_uuid for event in requests)
    assert {event.parent_lineage for event in native} == {event.lineage_uuid for event in requests}
    assert set(updates) == {'party', 'recipient'}
    for seat, update in updates.items():
        facts = damage_facts(update, enemy.uuid)
        assert len(facts) == 2
        assert all(fact.damage_type is DamageType.RADIANT and fact.applied_damage == 10 for fact in facts)
        if seat == 'recipient' and hide_first_owner:
            assert {(fact.source_entity_uuid, fact.source_condition_uuid) for fact in facts} == {
                (None, None), (owners[1].uuid, conditions[owners[1].uuid])}
        else:
            assert {fact.source_entity_uuid: fact.source_condition_uuid for fact in facts} == conditions
    assert {event.source_entity_uuid: event.source_condition_uuid for event in native} == conditions

    # Same visible actor, same damage type, both nearby owners still active:
    # an ordinary radiant result has no condition cause to disclose.
    cursor = EventQueue.event_cursor()
    assert enemy.receive_damage(10, DamageType.RADIANT, owners[1].uuid) == 10
    ordinary = capture(session, audiences, catalog, cursor)
    for update in ordinary.values():
        fact, = damage_facts(update, enemy.uuid)
        assert fact.source_entity_uuid == owners[1].uuid
        assert fact.source_condition_uuid is None

    cursor = EventQueue.event_cursor()
    assert owners[0].remove_condition_by_uuid(conditions[owners[0].uuid])
    capture(session, audiences, catalog, cursor)
    hp = enemy.get_normal_hp()
    cursor = EventQueue.event_cursor()
    assert not enemy.on_turn_start().canceled
    assert enemy.get_normal_hp() == hp - 10
    remaining = capture(session, audiences, catalog, cursor)
    for update in remaining.values():
        fact, = damage_facts(update, enemy.uuid)
        assert fact.source_entity_uuid == owners[1].uuid
        assert fact.source_condition_uuid == conditions[owners[1].uuid]
