"""Permitted native HUD/log facts remain detached and replayable at their boundary."""

import random
from dataclasses import replace

import pytest

from dnd.conditions import Poisoned, Invisible
from dnd.entity import Entity
from dnd.subjective_combat_log import project_combat_log
from dnd.core.events import EventQueue
from game.presentation import capture_interval
from game.player_facts import PlayerSequence
from game.player_projection import project_sequence, begin_projection
from game.player_reduction import encode_player_sequence, decode_player_sequence, reduce_initialization
from game.replay import RecordedSequence
from game.session import (advance_controller, close_session, create_session, discover_player_actions,
    end_player_turn, execute_player_action, snapshot_player_hud)


@pytest.fixture
def session():
    state = random.getstate()
    random.seed(0)
    value = create_session()
    try:
        for _ in range(32):
            operation = advance_controller(value)
            if operation.boundary.status == "waiting_for_human":
                break
        yield value
    finally:
        close_session(value)
        random.setstate(state)


def test_dash_and_spend_preserve_evaluated_resource_capacity(session):
    actor = session.encounter.get_current_entity()
    choices = discover_player_actions(session, actor.uuid)
    row = next(row for row in choices.self_actions if row.behavior_id == "action.dash")
    operation = execute_player_action(session, actor.uuid, row, row.valid_targets[0])
    sheet = next(sheet for sheet in operation.hud_snapshot.sheets if sheet.actor_uuid == actor.uuid)
    pools = {resource.key: resource for resource in sheet.resources}
    assert pools["movement"].current == pools["movement"].maximum == 60
    assert pools["actions"].current == 0 and pools["actions"].maximum == 1
    before = operation.hud_snapshot
    choices = discover_player_actions(session, actor.uuid)
    move = next(row for row in choices.position_actions if row.behavior_id == "action.move"
                and row.valid_targets)
    destination = next(target for target in move.valid_targets if target.path_cost)
    after = execute_player_action(session, actor.uuid, move, destination).hud_snapshot
    later = next(sheet for sheet in after.sheets if sheet.actor_uuid == actor.uuid)
    movement = next(pool for pool in later.resources if pool.key == "movement")
    assert movement.maximum == 60 and movement.current < 60
    assert before == operation.hud_snapshot


def test_visible_other_immunity_is_original_projected_append(session):
    actor = session.encounter.get_current_entity()
    other = session.game.entities[session.player_uuids[1]]
    observer = session.game.entities[session.player_uuids[0]]
    assert other.uuid in observer.senses.entities
    other.add_condition_immunity("Poisoned")
    result = other.add_condition(Poisoned(source_entity_uuid=actor.uuid, target_entity_uuid=other.uuid))
    assert result.canceled
    operation = end_player_turn(session, actor.uuid)
    appends=tuple(row for row in operation.combat_log_appends if row.observer_uuid==observer.uuid)
    assert len(appends)==1
    assert {row.observer_uuid for row in operation.combat_log_appends}==set(session.player_uuids)
    append = appends[0]
    assert append.entry.target_uuid == str(other.uuid) and "immune" in append.entry.compact
    assert append.operation_end_cursor == operation.end_cursor
    assert append.entry.compact == session.encounter.combat_log[append.encounter_log_index].compact
    initial = capture_interval(name="append packet", start_cursor=0, end_cursor=operation.end_cursor,
        observer_uuid=session.player_uuids[0], battlefield_id=session.battlefield.definition.battlefield_id)
    packet = project_sequence(RecordedSequence(initialization=initial, lineages=(),
        combat_log_appends=appends))
    restored = PlayerSequence.model_validate_json(encode_player_sequence(packet))
    assert restored.combat_log_appends == appends


def test_hud_and_standalone_append_roundtrip_with_old_packet_defaults(session):
    observer = session.player_uuids[0]
    initial = capture_interval(name="HUD baseline", start_cursor=0, end_cursor=EventQueue.event_cursor(),
        observer_uuid=observer, battlefield_id=session.battlefield.definition.battlefield_id)
    snapshot = snapshot_player_hud(session)
    native = RecordedSequence(initialization=initial, lineages=(), hud_snapshots=(snapshot,))
    projected = project_sequence(RecordedSequence.model_validate_json(native.model_dump_json()))
    assert projected.initialization.hud_snapshot == snapshot
    restored = PlayerSequence.model_validate_json(encode_player_sequence(projected))
    assert restored.initialization.hud_snapshot == snapshot
    state, _ = decode_player_sequence(encode_player_sequence(projected))
    assert state.hud_snapshot == snapshot
    with pytest.raises(ValueError, match="HUD"):
        reduce_initialization(replace(restored.initialization,
            hud_snapshot=replace(snapshot, revision=initial.end_cursor + 1)))
    old = PlayerSequence(initialization=replace(projected.initialization, hud_snapshot=None), lineages=())
    assert PlayerSequence.model_validate_json(encode_player_sequence(old)).hud_snapshots == ()


def test_nonvisual_immunity_uses_original_native_disclosure_policy(session):
    actor = session.encounter.get_current_entity()
    enemy = session.game.entities[session.enemy_controller.controlled_entity_uuids[0]]
    enemy.add_condition(Invisible(source_entity_uuid=enemy.uuid, target_entity_uuid=enemy.uuid))
    Entity.update_all_entities_senses()
    observer = session.game.entities[session.player_uuids[0]]
    assert enemy.uuid not in observer.senses.entities or not observer.senses.entities[enemy.uuid].visual
    enemy.add_condition_immunity("Poisoned")
    result = enemy.add_condition(Poisoned(source_entity_uuid=enemy.uuid, target_entity_uuid=enemy.uuid))
    assert result.canceled
    original = session.encounter.combat_log[-1]
    operation = end_player_turn(session, actor.uuid)
    expected = project_combat_log(original, controlled_entity_uuids=frozenset({str(observer.uuid)}),
                                 observer_entity_uuids=frozenset({str(observer.uuid)}))
    # Native contact can identify an invisible actor through nonvisual senses.
    # The adapter preserves this policy instead of granting visual access or suppressing real logs.
    appends=tuple(row for row in operation.combat_log_appends if row.observer_uuid==observer.uuid)
    if expected is None:
        assert not appends
    else:
        assert len(appends)==1
        assert appends[0].entry.model_dump()==expected.model_dump()


def test_separated_party_keeps_roster_without_sharing_spatial_or_inventory_facts():
    value=create_session(encounter_id='encounter.lantern_crypt')
    try:
        first,second=(value.game.entities[identity] for identity in value.player_uuids)
        Entity.update_entity_position(second,(14,6))
        Entity.update_all_entities_senses()
        enemies=set(value.enemy_controller.controlled_entity_uuids)
        assert not any(contact.visual for identity,contact in first.senses.entities.items() if identity in enemies)
        assert any(contact.visual for identity,contact in second.senses.entities.items() if identity in enemies)
        for observer,other in ((first,second),(second,first)):
            snapshot=snapshot_player_hud(value,observer.uuid)
            assert {sheet.actor_uuid for sheet in snapshot.sheets}==set(value.player_uuids)
            assert all(sheet.name and sheet.portrait_key and sheet.maximum_hp for sheet in snapshot.sheets)
            initial=capture_interval(name='Separated party',start_cursor=0,end_cursor=EventQueue.event_cursor(),
                observer_uuid=observer.uuid,battlefield_id=value.battlefield.definition.battlefield_id)
            _,packet=begin_projection(initial)
            state=reduce_initialization(replace(packet,hud_snapshot=snapshot))
            assert state.actors[observer.uuid].controlled_items is not None
            assert other.uuid not in state.actors or state.actors[other.uuid].controlled_items is None
            assert state.hud_snapshot.observer_uuid==observer.uuid
    finally:
        close_session(value)
