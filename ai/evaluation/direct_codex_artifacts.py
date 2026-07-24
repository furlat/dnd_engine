"""Durable raw evidence for runs controlled directly by Codex."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Literal, Optional, Sequence
from uuid import uuid4

import httpx
from pydantic import BaseModel, ConfigDict, Field, model_validator

from ai.validation_harness import (
    ValidationHarnessClient,
    ValidationMode,
    ValidationScheduleEntry,
    ValidationStartResult,
)
from server.agent_protocol.observation import (
    ObservationFramesResponse,
    ObservationSnapshot,
)
from server.agent_protocol.observation_legacy import (
    migrate_legacy_frame_semantics as _migrate_legacy_frame_semantics,
    migrate_legacy_snapshot_semantics as _migrate_legacy_snapshot_semantics,
)
from server.agent_protocol.telemetry import AgentEventHistoryResponse


class DirectCodexFrictionCategory(str, Enum):
    """Evidence categories for friction observed during direct Codex play."""

    SUBJECTIVE_INFORMATION_ABSENT = "subjective_information_absent"
    PRESENT_NOT_PROCESSED = "present_not_processed"
    PROCESSED_OMITTED_FROM_BRIEF = "processed_omitted_from_brief"
    AWKWARD_LOCAL_QUERY = "awkward_local_query"
    AGENT_IGNORED_OR_MISINTERPRETED = "agent_ignored_or_misinterpreted"
    POLICY_RECOMMENDATION_BIAS = "policy_recommendation_bias"
    SUBJECTIVE_IDENTITY_DISCONTINUITY = "subjective_identity_discontinuity"
    RUNTIME_HANDOFF_FAILURE = "runtime_handoff_failure"
    LATENCY_REGRESSION = "latency_regression"
    ENGINE_RULE_DEFECT = "engine_rule_defect"
    ENEMY_POLICY_WEAKNESS = "enemy_policy_weakness"


class DirectCodexRotationSlot(BaseModel):
    """Validation-rotation identity assigned to one direct Codex run."""

    model_config = ConfigDict(extra="forbid")

    sequence: int = Field(ge=0, description="Rotation sequence number assigned to the run.")
    focus: str = Field(min_length=1, description="Character or controller focus for this rotation slot.")
    mode: str = Field(min_length=1, description="Controller composition requested for the slot.")
    arena_id: str = Field(min_length=1, description="Arena identifier used by the run.")


class DirectCodexPerspective(BaseModel):
    """Subjective session and takeover identity recorded by the artifact."""

    model_config = ConfigDict(extra="forbid")

    controller_mode: Literal["direct_codex"] = Field(
        default="direct_codex",
        description="Controller mode represented by this evidence schema.",
    )
    session_id: str = Field(min_length=1, description="Subjective session observed by Codex.")
    takeover_claim_id: Optional[str] = Field(
        default=None,
        description="Runtime takeover claim associated with the session, when used.",
    )
    faction: Optional[str] = Field(default=None, description="Faction claimed by Codex when known.")
    controlled_entity_uuids: list[str] = Field(
        default_factory=list,
        description="Entity UUIDs controlled by the direct Codex session at bootstrap.",
    )


class DirectCodexFrictionAnnotation(BaseModel):
    """Human-authored friction note anchored to retained subjective evidence."""

    model_config = ConfigDict(extra="forbid")

    category: DirectCodexFrictionCategory = Field(description="Stage at which useful information or guidance failed.")
    note: str = Field(min_length=1, description="Concrete observation recorded during the run.")
    observation_cursor: Optional[int] = Field(
        default=None,
        ge=0,
        description="Relevant subjective observation cursor, when known.",
    )
    epoch_id: Optional[str] = Field(default=None, description="Relevant decision epoch identifier, when known.")
    command_id: Optional[str] = Field(default=None, description="Relevant controller command identifier, when known.")
    surface: Optional[str] = Field(
        default=None,
        description="Agent interface, query, or brief surface where the friction appeared.",
    )


class DirectCodexRunArtifact(BaseModel):
    """Immutable raw subjective evidence for one direct Codex-controlled run.

    This contract intentionally contains no inferred winner, latency summary,
    subjectivity verdict, or zero-valued proxy metrics. Consumers may derive
    claims only when the retained source responses actually support them.
    """

    model_config = ConfigDict(extra="forbid")

    artifact_type: Literal["direct_codex_run"] = Field(
        default="direct_codex_run",
        description="Stable discriminator separating direct runs from self-play artifacts.",
    )
    schema_version: Literal[1] = Field(default=1, description="Direct Codex artifact schema version.")
    run_id: str = Field(min_length=1, description="Stable unique run identifier and artifact filename stem.")
    captured_at: str = Field(description="UTC timestamp when final retained evidence was collected.")
    source_revision: Optional[str] = Field(
        default=None,
        description="Source revision or working-tree identity when known.",
    )
    rotation: DirectCodexRotationSlot = Field(description="Validation rotation slot represented by this run.")
    perspective: DirectCodexPerspective = Field(description="Session-subjective controller perspective.")
    initial_subjective_snapshot: ObservationSnapshot = Field(
        description="Typed subjective bootstrap snapshot captured before direct play.",
    )
    observation_frames_response: ObservationFramesResponse = Field(
        description="Complete unpaginated subjective frame response after the bootstrap cursor.",
    )
    agent_events_response: AgentEventHistoryResponse = Field(
        description="Complete retained agent telemetry response, including eviction state.",
    )
    manual_friction: list[DirectCodexFrictionAnnotation] = Field(
        default_factory=list,
        description="Evidence-anchored qualitative friction observations without fabricated scores.",
    )

    @model_validator(mode="before")
    @classmethod
    def migrate_pre_location_semantics(cls, value: Any) -> Any:
        """Read immutable evidence emitted before world-effect locations were typed."""
        if not isinstance(value, dict):
            return value
        migrated = value
        snapshot = value.get("initial_subjective_snapshot")
        migrated_snapshot = _migrate_legacy_snapshot_semantics(snapshot)
        if migrated_snapshot is not snapshot:
            migrated = {
                **migrated,
                "initial_subjective_snapshot": migrated_snapshot,
            }

        frames_response = value.get("observation_frames_response")
        if not isinstance(frames_response, dict):
            return migrated
        frames = frames_response.get("frames")
        if not isinstance(frames, list):
            return migrated
        migrated_frames = [
            _migrate_legacy_frame_semantics(frame)
            for frame in frames
        ]
        if all(
            migrated_frame is frame
            for migrated_frame, frame in zip(migrated_frames, frames)
        ):
            return migrated
        return {
            **migrated,
            "observation_frames_response": {
                **frames_response,
                "frames": migrated_frames,
            },
        }

    @model_validator(mode="after")
    def validate_retained_evidence(self) -> "DirectCodexRunArtifact":
        """Validate that retained streams belong to one coherent perspective."""
        session_id = self.perspective.session_id
        snapshot_session = self.initial_subjective_snapshot.session
        if snapshot_session.session_id != session_id:
            raise ValueError("initial snapshot session does not match artifact perspective")
        if set(self.perspective.controlled_entity_uuids) != set(snapshot_session.controlled_entity_uuids):
            raise ValueError("perspective entities do not match bootstrap session ownership")

        frames = self.observation_frames_response.frames
        if self.observation_frames_response.count != len(frames):
            raise ValueError("observation frame count does not match retained rows")
        cursors = [frame.observation_cursor for frame in frames]
        if cursors != sorted(cursors) or len(cursors) != len(set(cursors)):
            raise ValueError("observation frame cursors must be unique and ordered")
        if cursors and cursors[0] <= self.initial_subjective_snapshot.observation_cursor:
            raise ValueError("observation frames must follow the bootstrap snapshot cursor")
        expected_observation_cursor = cursors[-1] if cursors else self.initial_subjective_snapshot.observation_cursor
        if self.observation_frames_response.next_observation_cursor != expected_observation_cursor:
            raise ValueError("next observation cursor does not match retained frame history")
        for frame in frames:
            if frame.command_result is not None and frame.command_result.session_id != session_id:
                raise ValueError("command result session does not match artifact perspective")

        events = self.agent_events_response.events
        if self.agent_events_response.count != len(events):
            raise ValueError("agent event count does not match retained rows")
        agent_cursors = [event.agent_cursor for event in events]
        if agent_cursors != sorted(agent_cursors) or len(agent_cursors) != len(set(agent_cursors)):
            raise ValueError("agent event cursors must be unique and ordered")
        for event in events:
            if event.event.session_id != session_id:
                raise ValueError("agent event session does not match artifact perspective")
        return self


class DirectCodexStartedRun(BaseModel):
    """Direct Codex run context captured before the first command.

    The context keeps the startup response for provenance, but its artifact
    evidence remains the session-subjective snapshot and later subjective
    frame/event histories.
    """

    model_config = ConfigDict(extra="forbid")

    start_result: ValidationStartResult = Field(description="Validation arena startup response.")
    rotation: DirectCodexRotationSlot = Field(description="Rotation slot represented by the direct run.")
    perspective: DirectCodexPerspective = Field(description="Direct Codex session perspective.")
    initial_snapshot: ObservationSnapshot = Field(description="Pre-command subjective bootstrap snapshot.")

    def collect(
        self,
        collector: "DirectCodexArtifactCollector",
        *,
        manual_friction: Sequence[DirectCodexFrictionAnnotation] = (),
        run_id: Optional[str] = None,
        source_revision: Optional[str] = None,
    ) -> DirectCodexRunArtifact:
        """Finalize this started run from later subjective evidence.

        Args:
            collector: Subjective evidence collector for the same server.
            manual_friction: Qualitative notes anchored to retained evidence.
            run_id: Optional caller-supplied immutable run identifier.
            source_revision: Revision or working-tree identity when known.

        Returns:
            Validated direct Codex run artifact.
        """
        return collector.collect(
            initial_snapshot=self.initial_snapshot,
            rotation=self.rotation,
            perspective=self.perspective,
            manual_friction=manual_friction,
            run_id=run_id,
            source_revision=source_revision,
        )


class DirectCodexArtifactCollector:
    """Collect a direct Codex run through subjective evidence endpoints only."""

    def __init__(
        self,
        base_url: str,
        *,
        client: Optional[httpx.Client] = None,
        timeout: float = 10.0,
    ) -> None:
        """Create a collector bound to one game server.

        Args:
            base_url: Base URL of the running D&D engine server.
            client: Optional caller-owned HTTP client, primarily for reuse or tests.
            timeout: Request timeout used by an internally owned client.
        """
        self.base_url = base_url.rstrip("/")
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=timeout)

    def close(self) -> None:
        """Close the HTTP client when it was created by this collector."""
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "DirectCodexArtifactCollector":
        """Return this collector as a context-managed resource."""
        return self

    def __exit__(self, *_args: object) -> None:
        """Release an internally owned HTTP client."""
        self.close()

    def capture_initial_snapshot(self, session_id: str) -> ObservationSnapshot:
        """Capture the subjective bootstrap state before direct Codex play.

        Args:
            session_id: Session whose subjective perspective must be retained.

        Returns:
            Validated initial subjective snapshot.
        """
        payload = self._get_json(
            f"/ai/sessions/{session_id}/observation/snapshot",
        )
        snapshot = ObservationSnapshot.model_validate(payload)
        if snapshot.session.session_id != session_id:
            raise ValueError("snapshot endpoint returned a different session")
        return snapshot

    def collect(
        self,
        *,
        initial_snapshot: ObservationSnapshot,
        rotation: DirectCodexRotationSlot,
        perspective: DirectCodexPerspective,
        manual_friction: Sequence[DirectCodexFrictionAnnotation] = (),
        run_id: Optional[str] = None,
        source_revision: Optional[str] = None,
    ) -> DirectCodexRunArtifact:
        """Finalize one run from raw subjective frames and agent telemetry.

        The initial snapshot must have been captured before gameplay. This call
        requests every later observation frame and every retained agent event
        without consulting objective state, visibility, logs, or action routes.

        Args:
            initial_snapshot: Pre-play subjective bootstrap snapshot.
            rotation: Validation rotation identity for the run.
            perspective: Direct Codex session and takeover identity.
            manual_friction: Qualitative notes anchored to retained evidence.
            run_id: Optional caller-supplied immutable run identifier.
            source_revision: Revision or working-tree identity when known.

        Returns:
            Validated direct Codex run artifact ready for exclusive storage.
        """
        session_id = perspective.session_id
        frames_payload = self._get_json(
            f"/ai/sessions/{session_id}/observation/frames",
            params={"since": initial_snapshot.observation_cursor, "limit": 0},
        )
        agent_events_payload = self._get_json(
            f"/ai/sessions/{session_id}/agent-events",
            params={"since": 0, "limit": 0},
        )
        frames = ObservationFramesResponse.model_validate(frames_payload)
        agent_events = AgentEventHistoryResponse.model_validate(agent_events_payload)
        captured_at = datetime.now(timezone.utc).isoformat()
        return DirectCodexRunArtifact(
            run_id=run_id or _new_direct_run_id(rotation.arena_id, captured_at),
            captured_at=captured_at,
            source_revision=source_revision,
            rotation=rotation,
            perspective=perspective,
            initial_subjective_snapshot=initial_snapshot,
            observation_frames_response=frames,
            agent_events_response=agent_events,
            manual_friction=list(manual_friction),
        )

    def _get_json(
        self,
        path: str,
        *,
        params: Optional[dict[str, int]] = None,
    ) -> object:
        """GET one allowlisted evidence route and return its JSON payload."""
        response = self._client.get(f"{self.base_url}{path}", params=params)
        response.raise_for_status()
        return response.json()


def start_direct_codex_validation_run(
    base_url: str,
    *,
    arena_id: str,
    sequence: int,
    focus: str,
    mode: ValidationMode = "codex_monsters",
    faction: Optional[str] = "monsters",
    client: Optional[httpx.Client] = None,
) -> DirectCodexStartedRun:
    """Start a direct Codex validation arena and capture evidence immediately.

    This helper closes the gap where a run could begin before the immutable
    direct-artifact bootstrap snapshot was captured. It performs startup, then
    immediately reads the Codex session's subjective snapshot before returning
    control to the operator.

    Args:
        base_url: Running D&D engine server URL.
        arena_id: Validation arena id.
        sequence: Rotation sequence number assigned by the iteration loop.
        focus: Rotation focus label.
        mode: Validation startup mode. Must return a Codex session.
        faction: Faction claimed by Codex for perspective metadata.
        client: Optional HTTPX client for tests or caller-managed pooling.

    Returns:
        Direct run context containing startup metadata and pre-command snapshot.

    Raises:
        ValueError: If the arena is unknown or startup does not create a Codex
            session.
    """
    with ValidationHarnessClient(base_url, client=client) as harness:
        arenas = {arena.arena_id: arena for arena in harness.list_arenas()}
        arena = arenas.get(arena_id)
        if arena is None:
            raise ValueError(f"Unknown validation arena: {arena_id}")
        entry = ValidationScheduleEntry(
            sequence=sequence,
            focus=focus,
            mode=mode,
            arena_id=arena.arena_id,
            arena_title=arena.title,
            hero_role=arena.hero_role,
            tags=list(arena.tags),
            rationale=f"direct Codex validation through {arena.title}",
        )
        start_result = harness.start_entry(entry)

    session_id = start_result.codex_session_id
    if session_id is None:
        raise ValueError(f"Validation mode {mode!r} did not create a Codex session")

    collector = DirectCodexArtifactCollector(base_url, client=client)
    try:
        initial_snapshot = collector.capture_initial_snapshot(session_id)
    finally:
        collector.close()

    perspective = DirectCodexPerspective(
        session_id=session_id,
        takeover_claim_id=start_result.takeover_claim_id,
        faction=faction,
        controlled_entity_uuids=list(initial_snapshot.session.controlled_entity_uuids),
    )
    return DirectCodexStartedRun(
        start_result=start_result,
        rotation=DirectCodexRotationSlot(
            sequence=sequence,
            focus=focus,
            mode=mode,
            arena_id=arena_id,
        ),
        perspective=perspective,
        initial_snapshot=initial_snapshot,
    )


def write_direct_codex_run_artifact(
    artifact: DirectCodexRunArtifact,
    output_directory: Path | str,
) -> Path:
    """Persist one direct Codex artifact without overwriting evidence.

    Args:
        artifact: Validated direct Codex evidence to persist.
        output_directory: Directory that owns direct-run JSON files.

    Returns:
        Path of the newly created artifact.

    Raises:
        FileExistsError: If the run id already has a persisted artifact.
    """
    directory = Path(output_directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{artifact.run_id}.json"
    with path.open("x", encoding="utf-8") as handle:
        handle.write(artifact.model_dump_json(indent=2))
        handle.write("\n")
    return path


def _new_direct_run_id(arena_id: str, captured_at: str) -> str:
    """Build a readable unique identifier safe for a JSON filename."""
    timestamp = captured_at.replace("-", "").replace(":", "").replace("+", "_").replace(".", "_")
    safe_arena = "".join(
        character if character.isalnum() or character in {"-", "_"} else "-"
        for character in arena_id
    )
    return f"{timestamp}-{safe_arena}-direct-codex-{uuid4().hex[:8]}"
