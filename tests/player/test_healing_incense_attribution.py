"""Turn-start heals identify the real equipped item's observed aura.

Two prepared clerics earn and activate their own maces through discovered
actions. Detached updates must distinguish both healing owners, redact unseen
zones, and leave an ordinary same-holder heal unattributed.
"""

from dataclasses import replace
import random

import pytest

from dnd.actions_functional import execute_available_action, get_available_actions
from dnd.conditions import Blinded
from dnd.core.creature_types import DamageType
from dnd.core.dice import fixed_dice_faces
from dnd.core.equipment_types import WeaponSlot
from dnd.core.events import EventPhase, EventQueue, HealEvent
from dnd.core.gridmap import get_map
from dnd.items.divine_rewards import HealingIncenseZone
from dnd.player.application import capture_application_operation, initialize_audiences
from dnd.player.audience import PlayerAudience
from dnd.player.content_composition import ui_content_manifest
from dnd.player.facts import HealFact, PlayerUpdate
from dnd.player.reduction import reduce_initialization, reduce_operation
from dnd.player.session import close_session, create_session
from dnd.types.character_progression import CharacterClass
from tests.player.test_emitted_update_replica import operation_since
from tests.progression.prepared_class_support import prepared_build


@pytest.fixture
def incense_arena():
    previous_random = random.getstate()
    random.seed(6)
    build = prepared_build(CharacterClass.CLERIC, 10)
    session = create_session(player_builds=tuple(replace(build, name=name)
        for name in ('First holder', 'Second holder', 'Recipient')),
        player_positions=((12, 10), (13, 10), (14, 10)),
        enemy_positions=((14, 12), (14, 13)))
    try:
        first, second, recipient = (session.game.entities[identity]
            for identity in session.player_uuids)
        recipient.receive_damage(20, DamageType.FORCE, first.uuid)
        session.seats['recipient'] = PlayerAudience((recipient.uuid,), (recipient.uuid,))
        yield session, (first, second), recipient
    finally:
        close_session(session)
        random.setstate(previous_random)


def use(actor, behavior_id):
    action, = (row for row in get_available_actions(actor).self_actions
        if row.behavior_id == behavior_id)
    result = execute_available_action(actor, action, action.valid_targets[0])
    assert result is not None and not result.canceled


def heals(update, recipient):
    return [node.fact for group in update.lineages for node in group.events
        if isinstance(node.fact, HealFact) and node.fact.target_entity_uuid == recipient.uuid]


@pytest.mark.parametrize('hide_zones', [False, True])
def test_incense_turn_heals_join_exact_observed_owners(incense_arena, hide_zones):
    session, holders, recipient = incense_arena
    catalog = ui_content_manifest()
    audiences, initializations = initialize_audiences(session, catalog)
    clients = {seat: reduce_initialization(initial) for seat, initial in initializations.items()}

    def capture(cursor):
        updates = capture_application_operation(audiences, operation_since(session, cursor), catalog)
        detached = {seat: PlayerUpdate.model_validate_json(update.model_dump_json())
            for seat, update in updates.items()}
        for seat, update in detached.items():
            clients[seat] = reduce_operation(clients[seat], update)
        return detached

    zones = {}
    for holder in holders:
        cursor = EventQueue.event_cursor()
        use(holder, 'action.class.cleric.divine_intervention.arm_thy_servant')
        mace = holder.equipment.weapon_melee_main
        assert mace is not None and mace.item_id == 'weapon.devotees_mace'
        use(holder, 'action.item.devotees_mace.healing_incense')
        zone, = (zone for zone in get_map().get_spatial_conditions()
            if isinstance(zone, HealingIncenseZone) and zone.source_item_uuid == mace.uuid)
        zones[holder.uuid] = zone.uuid
        capture(cursor)
        for seat, client in clients.items():
            assert zone.uuid in client.senses.spatial_effects, (seat,
                zone.contributions_active(), zone.uuid in holder.senses.spatial_effects,
                zone.uuid in recipient.senses.spatial_effects)
            observed = client.senses.spatial_effects[zone.uuid]
            assert observed.content_ref.content_id == 'spatial_effect.item.devotees_mace.healing_incense'
            assert observed.anchor_entity_uuid == holder.uuid
    assert len(set(zones.values())) == 2

    if hide_zones:
        cursor = EventQueue.event_cursor()
        condition = recipient.add_condition(Blinded(
            source_entity_uuid=recipient.uuid, target_entity_uuid=recipient.uuid))
        assert condition is not None and not condition.canceled
        capture(cursor)
        assert not (set(zones.values()) & clients['recipient'].senses.spatial_effects.keys())

    hp = recipient.get_normal_hp()
    cursor = EventQueue.event_cursor()
    with fixed_dice_faces(2, 2):
        turn = recipient.on_turn_start()
    assert not turn.canceled and recipient.get_normal_hp() == hp + 4
    updates = capture(cursor)
    native = [event for _, event in EventQueue.iter_events_since(cursor)
        if isinstance(event, HealEvent) and event.phase is EventPhase.COMPLETION
        and event.target_entity_uuid == recipient.uuid]
    assert len(native) == 2 and all(event.parent_lineage == turn.lineage_uuid for event in native)
    for seat, update in updates.items():
        facts = heals(update, recipient)
        assert len(facts) == 2
        assert all(fact.actual_healing == 2 and not fact.was_blocked for fact in facts)
        if seat == 'recipient' and hide_zones:
            assert all(fact.source_condition_uuid is None for fact in facts)
        else:
            assert {fact.source_entity_uuid: fact.source_condition_uuid for fact in facts} == zones
    assert {event.source_entity_uuid: event.source_condition_uuid for event in native} == zones

    cursor = EventQueue.event_cursor()
    assert recipient.receive_healing(2, holders[1].uuid) == 2
    for update in capture(cursor).values():
        fact, = heals(update, recipient)
        assert fact.source_condition_uuid is None

    # Unequipping one actual sustaining mace stops that owner's contributions.
    cursor = EventQueue.event_cursor()
    assert holders[0].unequip_item(WeaponSlot.MELEE_MAIN) is not None
    capture(cursor)
    hp = recipient.get_normal_hp()
    cursor = EventQueue.event_cursor()
    with fixed_dice_faces(2):
        assert not recipient.on_turn_start().canceled
    assert recipient.get_normal_hp() == hp + 2
    for seat, update in capture(cursor).items():
        fact, = heals(update, recipient)
        assert fact.source_condition_uuid == (None if seat == 'recipient' and hide_zones
            else zones[holders[1].uuid])
