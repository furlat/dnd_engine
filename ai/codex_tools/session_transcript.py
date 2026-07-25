"""Append-only subjective evidence for one hot Codex session."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import json
import os
from pathlib import Path
from threading import Lock
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, JsonValue, TypeAdapter

from ai.codex_tools.representation.models import ResolvedRepresentationManifest
from dnd.ai.contracts.observation import ObservationFrame, ObservationSnapshot
from dnd.ai.contracts.control import CommandResult
from server.agent_protocol.telemetry import AgentEvent


_JSON_VALUE_ADAPTER = TypeAdapter(JsonValue)


class TranscriptRecordType(str, Enum):
    """Stable categories stored in a hot-session transcript."""

    SESSION_STARTED = "session_started"
    SUBJECTIVE_SNAPSHOT = "subjective_snapshot"
    SUBJECTIVE_FRAME = "subjective_frame"
    AGENT_EVENT = "agent_event"
    OPERATOR_INTERACTION = "operator_interaction"
    COMMAND_INTENT = "command_intent"
    COMMAND_ACKNOWLEDGEMENT = "command_acknowledgement"
    COMMAND_TRANSPORT_FAILURE = "command_transport_failure"
    COMMAND = "command"
    TERMINAL_SUMMARY = "terminal_summary"
    SESSION_RELEASED = "session_released"


class TranscriptRecord(BaseModel):
    """One digest-linked JSON record in source order."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = Field(default=1, description="Record schema version.")
    sequence: int = Field(ge=0, description="Monotonic record sequence within the runtime.")
    recorded_at: str = Field(description="UTC timestamp at which the local runtime retained the record.")
    record_type: TranscriptRecordType = Field(description="Typed lifecycle or evidence category.")
    payload_type: str = Field(description="Versioned schema identity of the JSON payload.")
    runtime_id: str = Field(description="Hot runtime that owns this transcript.")
    session_id: str = Field(description="Subjective controller session represented by this record.")
    encounter_uuid: Optional[str] = Field(default=None, description="Subjectively known encounter UUID.")
    observation_cursor: Optional[int] = Field(
        default=None,
        ge=0,
        description="Subjective cursor associated with this evidence, when available.",
    )
    epoch_id: Optional[str] = Field(default=None, description="Decision epoch associated with this evidence.")
    actor_uuid: Optional[str] = Field(default=None, description="Actor associated with this evidence.")
    command_id: Optional[str] = Field(default=None, description="Controller command correlation identifier.")
    payload: JsonValue = Field(description="Validated JSON-native typed payload.")
    previous_record_digest: Optional[str] = Field(
        default=None,
        description="Digest of the preceding record, or None for the first record.",
    )
    record_digest: str = Field(description="SHA-256 digest of this record and its predecessor link.")


class SessionTranscriptStatus(BaseModel):
    """Compact durable-state descriptor for one transcript."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    runtime_id: str = Field(description="Hot runtime that owns the transcript.")
    session_id: str = Field(description="Subjective session represented by the transcript.")
    jsonl_path: str = Field(description="Append-only JSON Lines evidence path.")
    final_json_path: str = Field(description="Final immutable-style JSON export path.")
    record_count: int = Field(ge=0, description="Records durably appended so far.")
    last_record_digest: Optional[str] = Field(default=None, description="Digest chain head.")
    finalized: bool = Field(description="Whether a complete JSON export has been written.")
    terminal: bool = Field(description="Whether terminal subjective evidence has been recorded.")


class SessionTranscript(BaseModel):
    """Complete typed export reconstructed from append-only records."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = Field(default=1, description="Transcript export schema version.")
    runtime_id: str = Field(description="Hot runtime that owns the transcript.")
    session_id: str = Field(description="Subjective session represented by the transcript.")
    generated_at: str = Field(description="UTC timestamp when this export was generated.")
    subjectivity_scope: Literal["session_subjective"] = Field(
        default="session_subjective",
        description="Absolute information boundary of every retained record.",
    )
    record_count: int = Field(ge=0, description="Number of retained records.")
    final_record_digest: Optional[str] = Field(default=None, description="Digest chain head for verification.")
    records: tuple[TranscriptRecord, ...] = Field(description="Complete ordered transcript records.")


class SessionReleasePayload(BaseModel):
    """Typed local and upstream teardown result retained in the transcript."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: str = Field(description="Local runtime release status.")
    claim_id: str = Field(description="Takeover claim associated with the runtime.")
    upstream_status: Optional[str] = Field(
        default=None,
        description="Remote release result or unavailable when the server was already gone.",
    )
    shutdown_failures: tuple[str, ...] = Field(
        default_factory=tuple,
        description="Sanitized teardown failures that did not prevent local evidence sealing.",
    )


class CodexSessionTranscript:
    """Thread-safe append-only recorder owned by one hot runtime."""

    def __init__(
        self,
        *,
        runtime_id: str,
        session_id: str,
        claim_id: str,
        faction: str,
        controlled_entity_uuids: tuple[str, ...],
        representation_manifest: ResolvedRepresentationManifest,
        directory: Path,
    ) -> None:
        """Create the durable transcript and append its non-secret identity record."""
        self.runtime_id = runtime_id
        self.session_id = session_id
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        stem = f"{timestamp}-{runtime_id}"
        self.jsonl_path = self.directory / f"{stem}.jsonl"
        self.final_json_path = self.directory / f"{stem}.json"
        self._records: list[TranscriptRecord] = []
        self._lock = Lock()
        self._finalized = False
        self._terminal = False
        self.append(
            TranscriptRecordType.SESSION_STARTED,
            payload_type="codex.session_started@v1",
            payload={
                "claim_id": claim_id,
                "faction": faction,
                "controlled_entity_uuids": list(controlled_entity_uuids),
                "representation_profile_id": representation_manifest.profile_id,
                "representation_manifest_digest": representation_manifest.manifest_digest,
                "representation_manifest": representation_manifest.model_dump(mode="json"),
                "subjectivity_scope": "session_subjective",
            },
            durable=True,
        )

    def record_snapshot(self, snapshot: ObservationSnapshot, *, reason: str) -> None:
        """Append one complete typed subjective snapshot."""
        self.append(
            TranscriptRecordType.SUBJECTIVE_SNAPSHOT,
            payload_type="ai.observation.ObservationSnapshot@v1",
            payload={"reason": reason, "snapshot": snapshot.model_dump(mode="json")},
            encounter_uuid=snapshot.encounter.uuid if snapshot.encounter is not None else None,
            observation_cursor=snapshot.observation_cursor,
            epoch_id=snapshot.current_epoch.epoch_id if snapshot.current_epoch is not None else None,
            actor_uuid=snapshot.current_epoch.actor_uuid if snapshot.current_epoch is not None else None,
        )

    def record_frame(self, frame: ObservationFrame) -> None:
        """Append one applied session-subjective event envelope."""
        command_id = frame.source_command_id
        if command_id is None and frame.command_result is not None:
            command_id = frame.command_result.command_id
        self.append(
            TranscriptRecordType.SUBJECTIVE_FRAME,
            payload_type="ai.observation.ObservationFrame@v1",
            payload=frame.model_dump(mode="json"),
            observation_cursor=frame.observation_cursor,
            epoch_id=frame.decision_epoch.epoch_id if frame.decision_epoch is not None else None,
            actor_uuid=frame.decision_epoch.actor_uuid if frame.decision_epoch is not None else None,
            command_id=command_id,
        )

    def record_agent_event(self, event: AgentEvent) -> None:
        """Append one typed agent telemetry event without changing gameplay truth."""
        self.append(
            TranscriptRecordType.AGENT_EVENT,
            payload_type="ai.subjective.AgentEvent@v1",
            payload=event.model_dump(mode="json"),
            observation_cursor=event.observation_cursor,
            epoch_id=event.epoch_id,
            actor_uuid=event.actor_uuid,
            command_id=_optional_text(event.payload.get("command_id")),
        )

    def record_command_intent(self, payload: dict[str, Any]) -> None:
        """Persist sanitized command intent before its HTTP submission."""
        self.append(
            TranscriptRecordType.COMMAND_INTENT,
            payload_type="ai.protocol.command_intent@v1",
            payload=payload,
            epoch_id=_optional_text(payload.get("basis_epoch_id")),
            actor_uuid=_optional_text(payload.get("actor_uuid")),
            command_id=_optional_text(payload.get("command_id")),
            durable=True,
        )

    def record_command_acknowledgement(self, result: CommandResult) -> None:
        """Persist one validated HTTP acknowledgement without treating it as game truth."""
        self.append(
            TranscriptRecordType.COMMAND_ACKNOWLEDGEMENT,
            payload_type="ai.protocol.CommandResult@v1",
            payload=result.model_dump(mode="json"),
            observation_cursor=result.accepted_at_observation_cursor,
            epoch_id=result.current_epoch_id or result.requested_epoch_id,
            actor_uuid=result.actor_uuid,
            command_id=result.command_id,
        )

    def record_command_transport_failure(
        self,
        command_id: str,
        error: BaseException,
    ) -> None:
        """Persist an ambiguous transport failure without inferring an engine result."""
        self.append(
            TranscriptRecordType.COMMAND_TRANSPORT_FAILURE,
            payload_type="codex.command_transport_failure@v1",
            payload={
                "error_type": type(error).__name__,
                "message": str(error),
            },
            command_id=command_id,
        )

    def record_operator_interaction(
        self,
        operation: str,
        payload: JsonValue,
        *,
        encounter_uuid: Optional[str] = None,
        observation_cursor: Optional[int] = None,
        epoch_id: Optional[str] = None,
        actor_uuid: Optional[str] = None,
    ) -> None:
        """Append an explicit local query or representation interaction."""
        self.append(
            TranscriptRecordType.OPERATOR_INTERACTION,
            payload_type="codex.operator_interaction@v1",
            payload={"operation": operation, "data": payload},
            encounter_uuid=encounter_uuid,
            observation_cursor=observation_cursor,
            epoch_id=epoch_id,
            actor_uuid=actor_uuid,
        )
        if self.status().terminal:
            self.finalize()

    def record_command(
        self,
        payload: JsonValue,
        *,
        encounter_uuid: Optional[str],
        observation_cursor: int,
        epoch_id: Optional[str],
        actor_uuid: Optional[str],
        command_id: Optional[str],
    ) -> None:
        """Append one complete command request/result/timing lifecycle."""
        self.append(
            TranscriptRecordType.COMMAND,
            payload_type="codex.command_lifecycle@v1",
            payload=payload,
            encounter_uuid=encounter_uuid,
            observation_cursor=observation_cursor,
            epoch_id=epoch_id,
            actor_uuid=actor_uuid,
            command_id=command_id,
        )

    def record_terminal(self, payload: JsonValue, *, encounter_uuid: Optional[str], cursor: int) -> None:
        """Append terminal subjective evidence exactly once and finalize the JSON export."""
        with self._lock:
            if self._terminal:
                return
            self._terminal = True
        self.append(
            TranscriptRecordType.TERMINAL_SUMMARY,
            payload_type="codex.terminal_summary@v1",
            payload=payload,
            encounter_uuid=encounter_uuid,
            observation_cursor=cursor,
            durable=True,
        )
        self.finalize()

    def record_release(self, payload: SessionReleasePayload) -> None:
        """Append release lifecycle evidence and refresh the complete JSON export."""
        self.append(
            TranscriptRecordType.SESSION_RELEASED,
            payload_type="codex.session_released@v1",
            payload=payload.model_dump(mode="json"),
            durable=True,
        )
        self.finalize()

    def append(
        self,
        record_type: TranscriptRecordType,
        *,
        payload_type: str,
        payload: Any,
        encounter_uuid: Optional[str] = None,
        observation_cursor: Optional[int] = None,
        epoch_id: Optional[str] = None,
        actor_uuid: Optional[str] = None,
        command_id: Optional[str] = None,
        durable: bool = False,
    ) -> TranscriptRecord:
        """Validate, digest, and durably append one JSON-native record."""
        json_payload = _JSON_VALUE_ADAPTER.validate_python(payload)
        with self._lock:
            sequence = len(self._records)
            previous_digest = self._records[-1].record_digest if self._records else None
            recorded_at = datetime.now(timezone.utc).isoformat()
            digest_payload = {
                "schema_version": 1,
                "sequence": sequence,
                "recorded_at": recorded_at,
                "record_type": record_type.value,
                "payload_type": payload_type,
                "runtime_id": self.runtime_id,
                "session_id": self.session_id,
                "encounter_uuid": encounter_uuid,
                "observation_cursor": observation_cursor,
                "epoch_id": epoch_id,
                "actor_uuid": actor_uuid,
                "command_id": command_id,
                "payload": json_payload,
                "previous_record_digest": previous_digest,
            }
            digest = sha256(
                json.dumps(digest_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest()
            record = TranscriptRecord(**digest_payload, record_digest=digest)
            with self.jsonl_path.open("a", encoding="utf-8") as handle:
                handle.write(record.model_dump_json())
                handle.write("\n")
                handle.flush()
                if durable:
                    os.fsync(handle.fileno())
            self._records.append(record)
            self._finalized = False
            return record

    def status(self) -> SessionTranscriptStatus:
        """Return compact durable transcript state."""
        with self._lock:
            return SessionTranscriptStatus(
                runtime_id=self.runtime_id,
                session_id=self.session_id,
                jsonl_path=str(self.jsonl_path),
                final_json_path=str(self.final_json_path),
                record_count=len(self._records),
                last_record_digest=self._records[-1].record_digest if self._records else None,
                finalized=self._finalized,
                terminal=self._terminal,
            )

    def export(self) -> SessionTranscript:
        """Build a complete validated transcript from retained records."""
        with self._lock:
            return SessionTranscript(
                runtime_id=self.runtime_id,
                session_id=self.session_id,
                generated_at=datetime.now(timezone.utc).isoformat(),
                record_count=len(self._records),
                final_record_digest=self._records[-1].record_digest if self._records else None,
                records=tuple(self._records),
            )

    def finalize(self) -> SessionTranscriptStatus:
        """Atomically write the complete JSON transcript beside its append log."""
        exported = self.export()
        temporary_path = self.final_json_path.with_suffix(".json.tmp")
        temporary_path.write_text(exported.model_dump_json(indent=2) + "\n", encoding="utf-8")
        temporary_path.replace(self.final_json_path)
        with self._lock:
            self._finalized = True
        return self.status()


def _optional_text(value: Any) -> Optional[str]:
    """Return a JSON scalar as text only when it already is a string."""
    return value if isinstance(value, str) else None
