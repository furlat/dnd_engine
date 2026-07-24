"""Focused checks for the generated engine-event wire contract."""

from datetime import datetime
import json
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest

from devtools.generate_event_contract import build_manifest
from dnd.actions import JumpEvent, Move, MovementEvent
from dnd.core.base_conditions import (
    ConditionApplicationEvent,
    OutcomeProtection,
)
from dnd.core.condition_types import (
    ConditionRemovalTrigger,
    ConditionTag,
)
from dnd.core.events import (
    Event,
    EventQueue,
    EventPhase,
    EventType,
    SavingThrowEvent,
    SensesUpdateHint,
    SpatialChangeEvent,
    SpatialChangeType,
    WindExposureEvent,
)
from dnd.entity import Entity
from dnd.spells.abjuration import ShieldBuff
from server.event_contract import (
    EVENT_CONTRACT,
    EventContractError,
    event_contract_summary,
    serialize_event,
)
from server.timeline_contracts import WireEvent
from tests.engine_book.test_chapter_10_core_actions_combat import (
    reset_core_action_state,
    strong_entity,
)


def test_generated_contract_covers_every_semantic_and_concrete_event() -> None:
    """The checked-in manifest equals a fresh scan of the runtime model graph."""
    assert build_manifest() == EVENT_CONTRACT
    assert set(EVENT_CONTRACT["event_types"]) == {
        event_type.value for event_type in EventType
    }
    assert event_contract_summary()["wire_types"] == sorted(EVENT_CONTRACT["event_classes"])


def test_executed_event_lineages_round_trip_typed_values_through_json() -> None:
    """Real movement and save lineages remain valid JSON-backed wire events."""
    reset_core_action_state()
    mover = strong_entity("Wire Mover", (1, 1), "heroes")
    saver = strong_entity("Wire Saver", (5, 5), "heroes")
    caster = strong_entity("Wire Caster", (6, 5), "monsters")
    Entity.update_all_entities_senses(max_distance=30)

    movement = Move(
        source_entity_uuid=mover.uuid,
        end_position=(3, 1),
        template=False,
    ).apply()
    assert isinstance(movement, MovementEvent)
    saving_throw = caster.create_saving_throw_request(
        target_entity_uuid=saver.uuid,
        ability_name="wisdom",
        dc=30,
    )
    with patch("dnd.core.dice.random.randint", return_value=7):
        saver.saving_throw(saving_throw)

    movement_versions = [
        event
        for event in EventQueue.get_events_by_type(EventType.MOVEMENT)
        if event.lineage_uuid == movement.lineage_uuid
    ]
    saving_throw_versions = [
        event
        for event in EventQueue.get_events_by_type(EventType.SAVING_THROW)
        if event.lineage_uuid == saving_throw.lineage_uuid
    ]

    assert movement.phase is EventPhase.COMPLETION
    assert {event.phase for event in movement_versions} == {
        EventPhase.DECLARATION,
        EventPhase.EXECUTION,
        EventPhase.EFFECT,
        EventPhase.COMPLETION,
    }
    assert {event.phase for event in saving_throw_versions} == {
        EventPhase.DECLARATION,
        EventPhase.EXECUTION,
        EventPhase.EFFECT,
        EventPhase.COMPLETION,
    }
    assert len({event.uuid for event in movement_versions}) == len(movement_versions)
    assert len({event.uuid for event in saving_throw_versions}) == len(
        saving_throw_versions
    )

    lineage_versions = [*movement_versions, *saving_throw_versions]
    for event in lineage_versions:
        assert isinstance(event.uuid, UUID)
        assert isinstance(event.lineage_uuid, UUID)
        assert isinstance(event.timestamp, datetime)
        assert isinstance(event.event_type, EventType)
        assert isinstance(event.phase, EventPhase)

        model_payload = json.loads(event.model_dump_json())
        wire_payload = serialize_event(event)
        json_payload = json.loads(json.dumps(wire_payload))
        cold_payload = WireEvent.model_validate(json_payload).model_dump(mode="json")

        assert json_payload == wire_payload
        assert cold_payload == wire_payload
        assert model_payload == {
            key: value for key, value in wire_payload.items() if key != "wire_type"
        }
        assert wire_payload["uuid"] == str(event.uuid)
        assert wire_payload["lineage_uuid"] == str(event.lineage_uuid)
        assert wire_payload["phase"] == event.phase.value
        assert wire_payload["event_type"] == event.event_type.value

    assert movement.path is not None
    assert all(isinstance(position, tuple) for position in movement.path)
    assert serialize_event(movement)["path"] == [[1, 1], [2, 1], [3, 1]]
    saving_completion = next(
        event
        for event in saving_throw_versions
        if event.phase is EventPhase.COMPLETION
    )
    assert isinstance(saving_completion, SavingThrowEvent)
    assert saving_completion.dice_roll is not None
    assert saving_completion.dice_roll.results == [7]
    assert serialize_event(saving_completion)["dice_roll"]["results"] == [7]


def test_concrete_wire_type_distinguishes_move_jump_and_generic_events() -> None:
    """Shared semantic categories never erase concrete payload identity."""
    source_uuid = uuid4()
    movement = MovementEvent(
        source_entity_uuid=source_uuid,
        start_position=(0, 0),
        end_position=(1, 0),
        path=[(0, 0), (1, 0)],
        phase=EventPhase.COMPLETION,
    )
    jump = JumpEvent(
        source_entity_uuid=source_uuid,
        start_position=(0, 0),
        end_position=(2, 1),
        jump_distance=10,
        path=[(0, 0), (1, 0), (2, 1)],
        phase=EventPhase.COMPLETION,
    )
    generic = Event(
        name="Generic movement notification",
        source_entity_uuid=source_uuid,
        event_type=EventType.MOVEMENT,
        phase=EventPhase.COMPLETION,
    )

    movement_payload = serialize_event(movement)
    jump_payload = serialize_event(jump)
    generic_payload = serialize_event(generic)

    assert movement_payload["event_type"] == jump_payload["event_type"] == "movement"
    assert movement_payload["wire_type"] == "dnd.actions.MovementEvent"
    assert jump_payload["wire_type"] == "dnd.actions.JumpEvent"
    assert generic_payload["wire_type"] == "dnd.core.events.Event"
    assert movement_payload["trajectory"] == "path"
    assert jump_payload["trajectory"] == "direct_arc"


def test_cold_timeline_accepts_the_generated_event_serializer() -> None:
    """Objective timelines preserve the generated event object byte-for-byte."""
    event = MovementEvent(
        source_entity_uuid=uuid4(),
        start_position=(2, 7),
        end_position=(3, 7),
        path=[(2, 7), (3, 7)],
        phase=EventPhase.COMPLETION,
    )
    serialized = serialize_event(event)
    cold = WireEvent.model_validate(serialized).model_dump(mode="json")

    assert cold == serialized
    assert cold["path"] == [[2, 7], [3, 7]]


def test_event_serializer_canonicalizes_every_unordered_wire_field() -> None:
    source_uuid = uuid4()
    target_uuid = uuid4()
    condition = ShieldBuff(
        source_entity_uuid=source_uuid,
        target_entity_uuid=target_uuid,
        tags={ConditionTag.POISON, ConditionTag.MAGICAL, ConditionTag.CURSE},
        outcome_protections=(
            OutcomeProtection(
                protection_id="deterministic-protection",
                blocked_effect_ids=frozenset({"effect-z", "effect-a", "effect-m"}),
            ),
        ),
        removal_triggers=frozenset(
            {ConditionRemovalTrigger.POSITIVE_DAMAGE_APPLIED}
        ),
    )
    condition_event = ConditionApplicationEvent(
        source_entity_uuid=source_uuid,
        target_entity_uuid=target_uuid,
        condition=condition,
        phase=EventPhase.COMPLETION,
    )
    spatial_event = SpatialChangeEvent(
        source_entity_uuid=source_uuid,
        event_type=EventType.SPATIAL_TILE_CHANGED,
        change_type=SpatialChangeType.TILE_CHANGED,
        position=(0, 0),
        senses_hint=SensesUpdateHint(
            light_changed_positions={(9, 1), (1, 9), (4, 4)},
            directional_positions={(8, 2), (2, 8), (4, 4)},
            directional_neighbors={(7, 3), (3, 7), (4, 4)},
            directional_channels_changed={"vision", "light", "movement"},
        ),
        phase=EventPhase.COMPLETION,
    )
    wind_event = WindExposureEvent(
        source_entity_uuid=source_uuid,
        positions={(9, 1), (1, 9), (4, 4)},
        phase=EventPhase.COMPLETION,
    )

    condition_payload = serialize_event(condition_event)
    spatial_payload = serialize_event(spatial_event)
    wind_payload = serialize_event(wind_event)

    assert condition_payload["condition"]["tags"] == [
        "curse",
        "magical",
        "poison",
    ]
    assert condition_payload["condition"]["removal_triggers"] == [
        "positive_damage_applied"
    ]
    assert condition_payload["condition"]["outcome_protections"][0][
        "blocked_effect_ids"
    ] == ["effect-a", "effect-m", "effect-z"]
    assert spatial_payload["senses_hint"]["light_changed_positions"] == [
        [1, 9],
        [4, 4],
        [9, 1],
    ]
    assert spatial_payload["senses_hint"]["directional_positions"] == [
        [2, 8],
        [4, 4],
        [8, 2],
    ]
    assert spatial_payload["senses_hint"]["directional_neighbors"] == [
        [3, 7],
        [4, 4],
        [7, 3],
    ]
    assert spatial_payload["senses_hint"]["directional_channels_changed"] == [
        "light",
        "movement",
        "vision",
    ]
    assert wind_payload["positions"] == [[1, 9], [4, 4], [9, 1]]
    assert (
        ShieldBuff.model_json_schema(mode="serialization")["properties"]["tags"][
            "uniqueItems"
        ]
        is True
    )
    assert (
        WireEvent.model_validate(condition_payload).model_dump(mode="json")
        == condition_payload
    )
    assert (
        WireEvent.model_validate(spatial_payload).model_dump(mode="json")
        == spatial_payload
    )
    assert (
        WireEvent.model_validate(wind_payload).model_dump(mode="json")
        == wind_payload
    )


def test_unknown_event_subclass_fails_at_the_transport_boundary() -> None:
    """A new event class cannot silently reach clients before regeneration."""

    class UnregisteredEvent(Event):
        pass

    event = UnregisteredEvent(
        name="Unregistered",
        source_entity_uuid=uuid4(),
        event_type=EventType.TRIGGER_EVENT,
        phase=EventPhase.COMPLETION,
    )

    with pytest.raises(EventContractError, match="absent from the generated wire contract"):
        serialize_event(event)
