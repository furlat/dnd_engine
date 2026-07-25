"""Durable hot-Codex session transcript contracts."""

from __future__ import annotations

from hashlib import sha256
import json

from ai.codex_tools.session_transcript import (
    CodexSessionTranscript,
    SessionReleasePayload,
    SessionTranscript,
    TranscriptRecord,
    TranscriptRecordType,
)
from ai.codex_tools.representation.profiles import (
    BALANCED_V2_PROFILE_ID,
    build_builtin_representation_registry,
)
from dnd.ai.contracts.observation import (
    ObservationFrame,
    ObservationFrameType,
    ObservationSessionState,
    ObservationSnapshot,
    ObservationSourceKind,
)
from dnd.ai.contracts.control import CommandResult, CommandResultStatus
from server.agent_protocol.telemetry import AgentEvent


def test_transcript_retains_complete_subjective_lifecycle_with_digest_chain(tmp_path) -> None:
    """Snapshots, frames, commands, telemetry, terminal state, and release survive as JSON."""
    transcript = CodexSessionTranscript(
        runtime_id="runtime-1",
        session_id="session-1",
        claim_id="claim-1",
        faction="monsters",
        controlled_entity_uuids=("skeleton-1",),
        representation_manifest=build_builtin_representation_registry().resolve_profile(
            BALANCED_V2_PROFILE_ID
        ),
        directory=tmp_path,
    )
    snapshot = ObservationSnapshot(
        observation_cursor=4,
        source_event_cursor=9,
        source_combat_log_cursor=2,
        session=ObservationSessionState(
            session_id="session-1",
            player_type="codex",
            name="Codex",
            connection_status="connected",
            controlled_entity_uuids=["skeleton-1"],
            active_entity_uuid="skeleton-1",
            active_entity_name="Skeleton",
            is_my_turn=True,
        ),
    )
    frame = ObservationFrame(
        observation_cursor=5,
        frame_type=ObservationFrameType.EVENT,
        source_kind=ObservationSourceKind.ENGINE_EVENT,
        event_type="movement",
        event_uuid="event-1",
    )
    event = AgentEvent(
        session_id="session-1",
        actor_uuid="skeleton-1",
        observation_cursor=5,
        event_type="runtime.test",
        source="test",
        summary="Retained test telemetry.",
    )
    intent = {
        "command_id": "command-1",
        "actor_uuid": "skeleton-1",
        "basis_epoch_id": "epoch-1",
        "row_id": "entity|Attack|uuid=hero",
        "include_diagnostics": False,
    }
    acknowledgement = CommandResult(
        status=CommandResultStatus.ACCEPTED,
        command_id="command-1",
        session_id="session-1",
        actor_uuid="skeleton-1",
        requested_epoch_id="epoch-1",
        row_id="entity|Attack|uuid=hero",
        message="Command accepted.",
        accepted_at_observation_cursor=6,
    )

    transcript.record_snapshot(snapshot, reason="bootstrap")
    transcript.record_frame(frame)
    transcript.record_agent_event(event)
    transcript.record_command_intent(intent)
    transcript.record_command_acknowledgement(acknowledgement)
    transcript.record_command(
        {"operation": "execute", "result": acknowledgement.model_dump(mode="json")},
        encounter_uuid="encounter-1",
        observation_cursor=6,
        epoch_id="epoch-1",
        actor_uuid="skeleton-1",
        command_id="command-1",
    )
    transcript.record_terminal(
        {"winner": "monsters", "subjectivity_complete": False},
        encounter_uuid="encounter-1",
        cursor=8,
    )
    transcript.record_release(SessionReleasePayload(
        status="released",
        claim_id="claim-1",
    ))

    jsonl_records = [
        TranscriptRecord.model_validate_json(line)
        for line in transcript.jsonl_path.read_text(encoding="utf-8").splitlines()
    ]
    exported = SessionTranscript.model_validate_json(
        transcript.final_json_path.read_text(encoding="utf-8")
    )

    assert [record.sequence for record in jsonl_records] == list(range(len(jsonl_records)))
    assert exported.records == tuple(jsonl_records)
    assert exported.record_count == len(jsonl_records)
    assert exported.subjectivity_scope == "session_subjective"
    started_payload = jsonl_records[0].payload
    assert isinstance(started_payload, dict)
    manifest_payload = started_payload["representation_manifest"]
    assert isinstance(manifest_payload, dict)
    assert manifest_payload["profile_id"] == BALANCED_V2_PROFILE_ID
    assert started_payload["representation_manifest_digest"] == manifest_payload["manifest_digest"]
    assert jsonl_records[-1].record_type is TranscriptRecordType.SESSION_RELEASED
    assert transcript.status().finalized is True
    assert transcript.status().terminal is True
    assert "secret" not in transcript.jsonl_path.read_text(encoding="utf-8").lower()
    _verify_digest_chain(jsonl_records)


def test_transport_failure_is_evidence_not_a_fabricated_game_result(tmp_path) -> None:
    """An ambiguous HTTP failure is retained without manufacturing an observation frame."""
    transcript = CodexSessionTranscript(
        runtime_id="runtime-2",
        session_id="session-2",
        claim_id="claim-2",
        faction="monsters",
        controlled_entity_uuids=(),
        representation_manifest=build_builtin_representation_registry().resolve_profile(
            BALANCED_V2_PROFILE_ID
        ),
        directory=tmp_path,
    )

    transcript.record_command_transport_failure("command-2", TimeoutError("timed out"))

    records = transcript.export().records
    assert records[-1].record_type is TranscriptRecordType.COMMAND_TRANSPORT_FAILURE
    assert records[-1].command_id == "command-2"
    assert records[-1].payload == {"error_type": "TimeoutError", "message": "timed out"}
    assert all(record.record_type is not TranscriptRecordType.SUBJECTIVE_FRAME for record in records)


def _verify_digest_chain(records: list[TranscriptRecord]) -> None:
    """Recompute every record digest from its canonical predecessor-linked payload."""
    previous = None
    for record in records:
        payload = record.model_dump(mode="json", exclude={"record_digest"})
        assert payload["previous_record_digest"] == previous
        digest = sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        assert record.record_digest == digest
        previous = digest
