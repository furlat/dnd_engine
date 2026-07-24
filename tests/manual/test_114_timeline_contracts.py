"""Focused checks for cold live/archive timeline contracts."""

from collections.abc import Callable
from copy import deepcopy
from hashlib import sha256
import json

import pytest
from pydantic import ValidationError

from dnd.core.combat_log import CombatLogEntry, CombatLogEntryType
from server.timeline_contracts import (
    CombatLogFrame,
    CombatLogFramesResponse,
    CombatLogProjection,
    EVENT_CONTRACT_HASH,
    EVENT_CONTRACT_VERSION,
    GameEventFrame,
    GameEventFramesResponse,
    TIMELINE_CONTRACT_HASH,
    TIMELINE_CONTRACT_VERSION,
    TimelineProtocolIdentity,
    WireEvent,
    timeline_contract_summary,
    timeline_wire_schema,
)


def _wire_event_payload(*, event_uuid: str = "event-1") -> dict[str, object]:
    """Return a fully serialized generic event without constructing Event."""
    return {
        "wire_type": "dnd.core.events.Event",
        "canceled": False,
        "canceled_from_phase": None,
        "children_events": [],
        "children_lineages": [],
        "context": {"cold": True},
        "event_type": "trigger_event",
        "is_first": True,
        "is_last": True,
        "lineage_children_events": [],
        "lineage_uuid": "lineage-1",
        "modified": False,
        "name": "Archived trigger",
        "outcome_code": None,
        "outcome_source_entity_uuid": None,
        "parent_event": None,
        "parent_lineage": None,
        "phase": "completion",
        "source_entity_name": "Archivist",
        "source_entity_uuid": "source-1",
        "status_message": None,
        "target_entity_name": None,
        "target_entity_uuid": None,
        "timestamp": "2026-07-22T12:00:00+00:00",
        "use_register": True,
        "uuid": event_uuid,
    }


def _entry(label: str = "acts") -> CombatLogEntry:
    return CombatLogEntry(
        entry_type=CombatLogEntryType.ACTION,
        source_name="Archivist",
        source_uuid="source-1",
        compact=label,
        verbose=label,
        detailed=label,
    )


def _game_frame(
    cursor: int,
    *,
    combat_log_cursor: int = 0,
    source_stream_id: str = "stream-1",
    generation_id: str = "generation-1",
) -> GameEventFrame:
    return GameEventFrame(
        source_stream_id=source_stream_id,
        generation_id=generation_id,
        event_index=cursor - 1,
        event_cursor=cursor,
        combat_log_cursor=combat_log_cursor,
        event=WireEvent.model_validate(_wire_event_payload(event_uuid=f"event-{cursor}")),
    )


def _combat_frame(
    cursor: int,
    *,
    projection: CombatLogProjection = CombatLogProjection.SUBJECTIVE,
    entry: CombatLogEntry | None = None,
    event_cursor: int = 1,
) -> CombatLogFrame:
    return CombatLogFrame(
        source_stream_id="stream-1",
        generation_id="generation-1",
        perspective_epoch_id="objective" if projection is CombatLogProjection.OBJECTIVE else "perspective-1",
        projection=projection,
        combat_log_cursor=cursor,
        event_cursor=event_cursor,
        entry=entry,
    )


def test_wire_event_is_cold_frozen_and_json_round_trippable() -> None:
    """A serialized event round-trips without an engine Event instance."""
    payload = _wire_event_payload()

    event = WireEvent.model_validate(payload)
    encoded = event.model_dump_json()
    decoded = WireEvent.model_validate_json(encoded)

    assert event.model_dump(mode="json") == payload
    assert decoded == event
    assert decoded.model_dump(mode="json")["context"] == {"cold": True}
    with pytest.raises(ValidationError, match="frozen"):
        event.event_type = "movement"


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda payload: payload.update(wire_type="not.registered.Event"), "absent from the generated"),
        (lambda payload: payload.pop("uuid"), "missing=\\['uuid'\\]"),
        (lambda payload: payload.update(undeclared=True), "unexpected=\\['undeclared'\\]"),
        (lambda payload: payload.update(event_type="not_an_event"), "event.event_type"),
        (lambda payload: payload.update(children_events=[1]), "event.children_events\\[0\\]"),
    ],
)
def test_wire_event_rejects_manifest_drift(
    mutate: Callable[[dict[str, object]], object],
    message: str,
) -> None:
    """Discriminators, exact fields, semantic types, and field shapes are checked."""
    payload = _wire_event_payload()
    mutate(payload)

    with pytest.raises(ValidationError, match=message):
        WireEvent.model_validate(payload)


def test_game_event_windows_are_exact_contiguous_and_round_trippable() -> None:
    """Objective event pages preserve every source slot and both cursors."""
    response = GameEventFramesResponse(
        source_stream_id="stream-1",
        generation_id="generation-1",
        retained_from_cursor=0,
        from_cursor=0,
        through_cursor=2,
        frames=(
            _game_frame(1, combat_log_cursor=0),
            _game_frame(2, combat_log_cursor=1),
        ),
        total=2,
    )

    restored = GameEventFramesResponse.model_validate_json(response.model_dump_json())
    assert restored == response
    assert restored.frames[1].event.model_dump(mode="json")["uuid"] == "event-2"

    with pytest.raises(ValidationError, match="contiguous and ordered"):
        GameEventFramesResponse(
            source_stream_id="stream-1",
            generation_id="generation-1",
            retained_from_cursor=0,
            from_cursor=0,
            through_cursor=2,
            frames=(_game_frame(1), _game_frame(3)),
            total=3,
        )
    with pytest.raises(ValidationError, match="nondecreasing"):
        GameEventFramesResponse(
            source_stream_id="stream-1",
            generation_id="generation-1",
            retained_from_cursor=0,
            from_cursor=0,
            through_cursor=2,
            frames=(
                _game_frame(1, combat_log_cursor=2),
                _game_frame(2, combat_log_cursor=1),
            ),
            total=2,
        )


def test_game_event_frame_binds_storage_index_to_cursor() -> None:
    with pytest.raises(ValidationError, match=r"event_index \+ 1"):
        GameEventFrame(
            source_stream_id="stream-1",
            generation_id="generation-1",
            event_index=7,
            event_cursor=1,
            combat_log_cursor=0,
            event=WireEvent.model_validate(_wire_event_payload()),
        )


def test_combat_log_projection_distinguishes_hidden_and_missing_data() -> None:
    """Only subjective projection may represent a retained slot with null content."""
    hidden = _combat_frame(1)
    objective = _combat_frame(
        1,
        projection=CombatLogProjection.OBJECTIVE,
        entry=_entry(),
    )

    assert hidden.entry is None
    assert objective.entry is not None
    with pytest.raises(ValidationError, match="objective combat-log frames must contain"):
        _combat_frame(1, projection=CombatLogProjection.OBJECTIVE)


def test_combat_log_windows_are_exact_and_projection_homogeneous() -> None:
    response = CombatLogFramesResponse(
        source_stream_id="stream-1",
        generation_id="generation-1",
        perspective_epoch_id="perspective-1",
        projection=CombatLogProjection.SUBJECTIVE,
        retained_from_cursor=0,
        from_cursor=0,
        through_cursor=2,
        frames=(
            _combat_frame(1, entry=_entry("visible"), event_cursor=1),
            _combat_frame(2, entry=None, event_cursor=2),
        ),
        total=2,
    )

    restored = CombatLogFramesResponse.model_validate_json(response.model_dump_json())
    assert restored == response
    assert [frame.entry is None for frame in restored.frames] == [False, True]

    wrong_projection = _combat_frame(
        2,
        projection=CombatLogProjection.OBJECTIVE,
        entry=_entry(),
        event_cursor=2,
    )
    with pytest.raises(ValidationError, match="perspective epoch|projection"):
        CombatLogFramesResponse(
            source_stream_id="stream-1",
            generation_id="generation-1",
            perspective_epoch_id="perspective-1",
            projection=CombatLogProjection.SUBJECTIVE,
            retained_from_cursor=0,
            from_cursor=0,
            through_cursor=2,
            frames=(_combat_frame(1), wrong_projection),
            total=2,
        )


def test_combat_log_uuid_sets_have_canonical_json_order() -> None:
    entry = CombatLogEntry(
        entry_type=CombatLogEntryType.ACTION,
        source_name="Archivist",
        source_uuid="source-1",
        compact="acts",
        verbose="acts",
        detailed="acts",
        perceiver_uuids={"observer-z", "observer-a"},
        revealed_entity_uuids={"entity-z", "entity-a"},
        sub_entries=[
            CombatLogEntry(
                entry_type=CombatLogEntryType.ACTION,
                source_name="Witness",
                source_uuid="source-2",
                compact="reacts",
                verbose="reacts",
                detailed="reacts",
                perceiver_uuids={"observer-y", "observer-b"},
            )
        ],
    )

    encoded = json.loads(entry.model_dump_json())
    restored = CombatLogEntry.model_validate_json(entry.model_dump_json())

    assert encoded["perceiver_uuids"] == ["observer-a", "observer-z"]
    assert encoded["revealed_entity_uuids"] == ["entity-a", "entity-z"]
    assert encoded["sub_entries"][0]["perceiver_uuids"] == [
        "observer-b",
        "observer-y",
    ]
    assert restored.model_dump(mode="json") == entry.model_dump(mode="json")


def test_protocol_identity_is_portable_and_fail_closed() -> None:
    identity = TimelineProtocolIdentity()

    assert identity.model_dump(mode="json") == timeline_contract_summary() == {
        "timeline_contract_version": TIMELINE_CONTRACT_VERSION,
        "timeline_contract_hash": TIMELINE_CONTRACT_HASH,
        "event_contract_version": EVENT_CONTRACT_VERSION,
        "event_contract_hash": EVENT_CONTRACT_HASH,
    }
    assert "source_stream_id" not in TimelineProtocolIdentity.model_fields
    assert "generation_id" not in TimelineProtocolIdentity.model_fields

    incompatible = deepcopy(identity.model_dump(mode="json"))
    incompatible["timeline_contract_hash"] = "wrong"
    with pytest.raises(ValidationError, match="timeline contract hash mismatch"):
        TimelineProtocolIdentity.model_validate(incompatible)


def test_timeline_hash_authenticates_transitive_event_and_log_schemas() -> None:
    schema = timeline_wire_schema()
    canonical = json.dumps(schema, sort_keys=True, separators=(",", ":")).encode()

    assert sha256(canonical).hexdigest() == TIMELINE_CONTRACT_HASH
    log_schema = schema["objective_combat_log_window"]
    assert isinstance(log_schema, dict)
    definitions = log_schema["$defs"]
    assert "CombatLogEntry" in definitions
    assert "ObjectiveCombatLogFrame" in definitions
    entry_properties = definitions["CombatLogEntry"]["properties"]
    assert entry_properties["perceiver_uuids"]["uniqueItems"] is True
    assert entry_properties["revealed_entity_uuids"]["uniqueItems"] is True
    assert schema["event_contract_hash"] == EVENT_CONTRACT_HASH
