"""Permitted native HUD/log facts remain detached and replayable at their boundary."""

import random
from dataclasses import replace

import pytest

from dnd.conditions import Poisoned, Invisible
from dnd.entity import Entity
from dnd.subjective_combat_log import project_combat_log
from dnd.core.events import EventQueue
from dnd.player.capture import capture_interval, capture_lineage
from dnd.player.facts import PlayerSequence
from dnd.player.recorded import project_sequence
from dnd.player.projection import begin_projection, project_after_values
from dnd.player.reduction import encode_player_sequence, decode_player_sequence, reduce_initialization
from dnd.player.recorded import RecordedSequence
from dnd.player.session import (advance_controller, close_session, create_session, discover_player_actions,
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


def test_visible_other_immunity_keeps_its_original_canceled_event(session):
    actor = session.encounter.get_current_entity()
    other = session.game.entities[session.player_uuids[1]]
    observer = session.game.entities[session.player_uuids[0]]
    assert other.uuid in observer.senses.entities
    other.add_condition_immunity("Poisoned")
    initial = capture_interval(name="immunity baseline", start_cursor=0,
        end_cursor=EventQueue.event_cursor(), observer_uuid=observer.uuid,
        battlefield_id=session.battlefield.definition.battlefield_id)
    result = other.add_condition(Poisoned(source_entity_uuid=actor.uuid, target_entity_uuid=other.uuid))
    assert result.canceled and result.combat_log is not None
    lineage = capture_lineage(result, observer_uuid=observer.uuid)
    operation = end_player_turn(session, actor.uuid)
    assert not operation.combat_log_appends
    packet = project_sequence(RecordedSequence(initialization=initial, lineages=(lineage,)))
    restored = PlayerSequence.model_validate_json(encode_player_sequence(packet))
    node = next(node for group in restored.lineages for node in group.events if node.uuid == result.uuid)
    assert node.canceled and node.combat_log is not None
    assert node.combat_log.target_uuid == str(other.uuid)
    assert node.combat_log.compact == result.combat_log.compact
    assert restored.combat_log_appends == ()


def test_hud_and_standalone_append_roundtrip_with_old_packet_defaults(session):
    observer = session.player_uuids[0]
    initial = capture_interval(name="HUD baseline", start_cursor=0, end_cursor=EventQueue.event_cursor(),
        observer_uuid=observer, battlefield_id=session.battlefield.definition.battlefield_id)
    snapshot = snapshot_player_hud(session)
    native = RecordedSequence(initialization=initial, lineages=(), hud_snapshots=(snapshot,))
    projected = project_sequence(RecordedSequence.model_validate_json(native.model_dump_json()))
    public_snapshot = replace(snapshot, revision=projected.initialization.end_cursor)
    assert projected.initialization.hud_snapshot == public_snapshot
    restored = PlayerSequence.model_validate_json(encode_player_sequence(projected))
    assert restored.initialization.hud_snapshot == public_snapshot
    state, _ = decode_player_sequence(encode_player_sequence(projected))
    assert state.hud_snapshot == public_snapshot
    with pytest.raises(ValueError, match="HUD"):
        reduce_initialization(replace(restored.initialization,
            hud_snapshot=replace(snapshot, revision=initial.end_cursor + 1)))
    old = PlayerSequence(initialization=replace(projected.initialization, hud_snapshot=None), lineages=())
    assert PlayerSequence.model_validate_json(encode_player_sequence(old)).hud_snapshots == ()


def test_nonvisual_immunity_uses_original_native_disclosure_policy(session):
    actor = session.encounter.get_current_entity()
    enemy = session.game.entities[session.ai_controllers[0].controlled_entity_uuids[0]]
    enemy.add_condition(Invisible(source_entity_uuid=enemy.uuid, target_entity_uuid=enemy.uuid))
    Entity.update_all_entities_senses()
    observer = session.game.entities[session.player_uuids[0]]
    assert enemy.uuid not in observer.senses.entities or not observer.senses.entities[enemy.uuid].visual
    enemy.add_condition_immunity("Poisoned")
    initial = capture_interval(name="nonvisual immunity baseline", start_cursor=0,
        end_cursor=EventQueue.event_cursor(), observer_uuid=observer.uuid,
        battlefield_id=session.battlefield.definition.battlefield_id)
    result = enemy.add_condition(Poisoned(source_entity_uuid=enemy.uuid, target_entity_uuid=enemy.uuid))
    assert result.canceled and result.combat_log is not None
    original = session.encounter.combat_log[-1]
    packet = project_sequence(RecordedSequence(initialization=initial,
        lineages=(capture_lineage(result, observer_uuid=observer.uuid),)))
    operation = end_player_turn(session, actor.uuid)
    expected = project_combat_log(original, controlled_entity_uuids=frozenset({str(observer.uuid)}),
                                 observer_entity_uuids=frozenset({str(observer.uuid)}))
    # Native contact can identify an invisible actor through nonvisual senses.
    # The adapter preserves this policy instead of granting visual access or suppressing real logs.
    assert not operation.combat_log_appends
    logs = tuple(node.combat_log for group in packet.lineages for node in group.events
        if node.uuid == result.uuid and node.combat_log is not None)
    if expected is None:
        assert not logs
    else:
        assert len(logs)==1
        assert logs[0].model_dump()==expected.model_dump()


def test_single_actor_audiences_keep_only_owned_sheets_and_subjective_facts():
    value=create_session(encounter_id='encounter.lantern_crypt')
    try:
        first,second=(value.game.entities[identity] for identity in value.player_uuids)
        Entity.update_entity_position(second,(14,6))
        Entity.update_all_entities_senses()
        enemies={identity for controller in value.ai_controllers
                 for identity in controller.controlled_entity_uuids}
        assert not any(contact.visual for identity,contact in first.senses.entities.items() if identity in enemies)
        assert any(contact.visual for identity,contact in second.senses.entities.items() if identity in enemies)
        for observer,other in ((first,second),(second,first)):
            snapshot=snapshot_player_hud(value,observer.uuid)
            assert {sheet.actor_uuid for sheet in snapshot.sheets}=={observer.uuid}
            assert all(sheet.name and sheet.portrait_key and sheet.maximum_hp for sheet in snapshot.sheets)
            initial=capture_interval(name='Separated party',start_cursor=0,end_cursor=EventQueue.event_cursor(),
                observer_uuid=observer.uuid,battlefield_id=value.battlefield.definition.battlefield_id)
            projection,packet=begin_projection(initial)
            public_snapshot,_=project_after_values(projection,snapshot,())
            state=reduce_initialization(replace(packet,hud_snapshot=public_snapshot))
            assert state.actors[observer.uuid].controlled_items is not None
            assert other.uuid not in state.actors or state.actors[other.uuid].controlled_items is None
            assert state.hud_snapshot.observer_uuid==observer.uuid
    finally:
        close_session(value)
