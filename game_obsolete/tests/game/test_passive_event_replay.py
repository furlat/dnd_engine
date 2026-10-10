"""Retained event JSON validates without joining the running rules session."""

import json
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from dnd.core.base_actions import ActionEvent
from dnd.core.base_object import BaseObject, PASSIVE_EVENT_REPLAY
from dnd.core.content.runtime import BehaviorBinding, runtime_behavior_provider
from dnd.core.dice import DiceRoll
from dnd.core.events import DamageRollResultEvent, EventQueue
from dnd.runtime_reset import reset_engine_runtime


@pytest.fixture(autouse=True)
def isolated_native_runtime():
    reset_engine_runtime()
    yield
    reset_engine_runtime()


def test_replay_preserves_absent_turn_and_behavior_without_registering() -> None:
    actor = uuid4()
    event_id, lineage_id = uuid4(), uuid4()
    payload = json.dumps({
        "uuid": str(event_id), "lineage_uuid": str(lineage_id),
        "source_entity_uuid": str(actor), "turn_execution_id": None,
        "behavior_id": None, "provided_by_id": None, "origin_root_id": None,
        "use_register": True,
    })
    binding = BehaviorBinding(
        behavior_id="action.attack", provided_by_id="feature.extra_attack",
        runtime_owner_uuid=actor,
    )
    active_turn = EventQueue.begin_turn_execution()
    try:
        with runtime_behavior_provider(binding):
            decoded = ActionEvent.model_validate_json(payload, context=PASSIVE_EVENT_REPLAY)
            assert decoded.uuid == event_id and decoded.lineage_uuid == lineage_id
            assert decoded.turn_execution_id is None
            assert (decoded.behavior_id, decoded.provided_by_id, decoded.origin_root_id) == (None, None, None)
            assert EventQueue.event_cursor() == 0
            assert EventQueue.get_event_by_uuid(event_id) is None

            # Ordinary construction still belongs to the live ambient action/turn.
            live = ActionEvent.model_validate_json(payload)
            assert live.turn_execution_id == active_turn
            assert (live.behavior_id, live.provided_by_id) == (binding.behavior_id, binding.provided_by_id)
            assert EventQueue.get_event_by_uuid(event_id) is not None
            assert EventQueue.event_cursor() == 1
    finally:
        EventQueue.end_turn_execution(active_turn)


def damage_result_json(*, roll_type: str = "Damage") -> tuple[str, UUID, UUID, UUID]:
    actor, target, event_id, damage_id, roll_id = (uuid4() for _ in range(5))
    roll = {
        "roll_uuid": str(roll_id), "dice_uuid": str(uuid4()),
        "roll_type": roll_type, "results": [3], "total": 5, "bonus": 2,
        "advantage_status": "None", "critical_status": "None",
        "auto_hit_status": "None", "source_entity_uuid": str(actor),
        "target_entity_uuid": str(target), "attack_outcome": "Hit",
        "die_size": 6, "effective_dice_count": 1, "random_faces_rolled": 1,
    }
    payload = {
        "uuid": str(event_id), "source_entity_uuid": str(actor),
        "target_entity_uuid": str(target), "use_register": True,
        "context": {}, "weapon_slot": "MELEE_MAIN", "attack_outcome": "Hit",
        "damage_packets": [{
            "damage": {
                "uuid": str(damage_id), "source_entity_uuid": str(actor),
                "damage_dice": 6, "dice_numbers": 1, "damage_type": "Fire",
                "damage_bonus": None, "use_register": True,
            },
            "original_roll": roll, "final_roll": roll,
        }],
    }
    return json.dumps(payload), event_id, damage_id, roll_id


def test_replay_context_reaches_nested_damage_and_concrete_roll_values() -> None:
    payload, event_id, damage_id, roll_id = damage_result_json()
    decoded = DamageRollResultEvent.model_validate_json(payload, context=PASSIVE_EVENT_REPLAY)
    packet = decoded.damage_packets[0]
    assert packet.damage.uuid == damage_id
    assert packet.original_roll.roll_uuid == packet.final_roll.roll_uuid == roll_id
    assert packet.original_roll.results == [3] and packet.final_roll.total == 5
    assert packet.final_roll.bonus == 2
    assert BaseObject.get(damage_id) is None
    assert DiceRoll.get(roll_id) is None
    assert EventQueue.get_event_by_uuid(event_id) is None
    assert EventQueue.event_cursor() == 0

    live = DamageRollResultEvent.model_validate_json(payload)
    assert BaseObject.get(damage_id) is live.damage_packets[0].damage
    assert DiceRoll.get(roll_id) is live.damage_packets[0].final_roll
    assert EventQueue.get_event_by_uuid(event_id) is not None


def test_passive_replay_still_rejects_inconsistent_action_identity() -> None:
    payload = json.dumps({"source_entity_uuid": str(uuid4()), "behavior_id": "action.attack"})
    with pytest.raises(ValidationError, match="behavior_id and provided_by_id must be present together"):
        ActionEvent.model_validate_json(payload, context=PASSIVE_EVENT_REPLAY)
    assert EventQueue.event_cursor() == 0


def test_invalid_nested_roll_is_rejected_without_partial_registry_writes() -> None:
    payload, event_id, damage_id, roll_id = damage_result_json(roll_type="Heal")
    with pytest.raises(ValidationError, match="original_roll must be a damage roll"):
        DamageRollResultEvent.model_validate_json(payload, context=PASSIVE_EVENT_REPLAY)
    assert BaseObject.get(damage_id) is None
    assert DiceRoll.get(roll_id) is None
    assert EventQueue.get_event_by_uuid(event_id) is None
    assert EventQueue.event_cursor() == 0
