"""Transport-neutral validation and publication of terminal game evidence."""

from __future__ import annotations

from uuid import UUID

from server.game_artifact_store import GameArtifactStore
from server.game_directory.contracts import (
    ArtifactCreate,
    ArtifactKind,
    ProducerKind,
)
from server.game_directory.repository import GameDirectoryRepository
from server.game_runtime_identity import ENGINE_VERSION
from server.game_summary_store import WorkerSummaryEvidence
from server.objective_replay import (
    OBJECTIVE_REPLAY_CONTRACT_HASH,
    OBJECTIVE_REPLAY_CONTRACT_VERSION,
    ObjectiveReplayBundle,
)
from server.player_replay import (
    PLAYER_REPLAY_CONTRACT_HASH,
    PLAYER_REPLAY_CONTRACT_VERSION,
    SubjectivePlayerReplayArchive,
)


OBJECTIVE_REPLAY_SCHEMA_VERSION = (
    f"dnd.objective-replay.v{OBJECTIVE_REPLAY_CONTRACT_VERSION}."
    f"{OBJECTIVE_REPLAY_CONTRACT_HASH}"
)
SUBJECTIVE_REPLAY_SCHEMA_VERSION = (
    f"dnd.subjective-player-replay.v{PLAYER_REPLAY_CONTRACT_VERSION}."
    f"{PLAYER_REPLAY_CONTRACT_HASH}"
)


class TerminalEvidenceError(ValueError):
    """Typed mismatch between immutable terminal evidence inputs."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(code, message)
        self.code = code
        self.message = message

    def __str__(self) -> str:
        return self.message


def publish_terminal_evidence(
    *,
    repository: GameDirectoryRepository,
    artifact_store: GameArtifactStore,
    game_id: UUID,
    evidence: WorkerSummaryEvidence,
    objective_replay: ObjectiveReplayBundle,
    subjective_replay: SubjectivePlayerReplayArchive,
    known_membership_ids: frozenset[UUID],
    producer_kind: ProducerKind,
    producer_version: str = ENGINE_VERSION,
) -> None:
    """Validate, store, and atomically publish both replays plus summary."""

    replay_artifact, subjective_replay_artifact = store_terminal_artifacts(
        artifact_store=artifact_store,
        game_id=game_id,
        evidence=evidence,
        objective_replay=objective_replay,
        subjective_replay=subjective_replay,
        known_membership_ids=known_membership_ids,
        producer_kind=producer_kind,
        producer_version=producer_version,
    )
    repository.publish_terminal_evidence(
        replay_artifact,
        evidence.summary,
        additional_artifacts=(subjective_replay_artifact,),
        summary_revision=1,
        source_event_digest=evidence.source_event_digest,
        source_combat_log_digest=evidence.source_combat_log_digest,
    )


def store_terminal_artifacts(
    *,
    artifact_store: GameArtifactStore,
    game_id: UUID,
    evidence: WorkerSummaryEvidence,
    objective_replay: ObjectiveReplayBundle,
    subjective_replay: SubjectivePlayerReplayArchive,
    known_membership_ids: frozenset[UUID],
    producer_kind: ProducerKind,
    producer_version: str = ENGINE_VERSION,
) -> tuple[ArtifactCreate, ArtifactCreate]:
    """Validate terminal coordinates and store both immutable replay bytes."""

    validate_terminal_evidence(
        game_id=game_id,
        evidence=evidence,
        objective_replay=objective_replay,
        subjective_replay=subjective_replay,
        known_membership_ids=known_membership_ids,
    )
    stored_objective = artifact_store.put_json(objective_replay)
    stored_subjective = artifact_store.put_json(subjective_replay)
    return (
        ArtifactCreate(
            game_id=game_id,
            artifact_kind=ArtifactKind.REPLAY_BUNDLE,
            schema_version=OBJECTIVE_REPLAY_SCHEMA_VERSION,
            media_type="application/json",
            uri=stored_objective.uri,
            byte_size=stored_objective.byte_size,
            content_digest=stored_objective.content_digest,
            producer_kind=producer_kind,
            producer_version=producer_version,
        ),
        ArtifactCreate(
            game_id=game_id,
            artifact_kind=ArtifactKind.SUBJECTIVE_REPLAY_BUNDLE,
            schema_version=SUBJECTIVE_REPLAY_SCHEMA_VERSION,
            media_type="application/json",
            uri=stored_subjective.uri,
            byte_size=stored_subjective.byte_size,
            content_digest=stored_subjective.content_digest,
            producer_kind=producer_kind,
            producer_version=producer_version,
        ),
    )


def validate_stored_terminal_artifacts(
    *,
    artifact_store: GameArtifactStore,
    game_id: UUID,
    evidence: WorkerSummaryEvidence,
    objective_artifact: ArtifactCreate,
    subjective_artifact: ArtifactCreate,
    known_membership_ids: frozenset[UUID],
) -> tuple[ObjectiveReplayBundle, SubjectivePlayerReplayArchive]:
    """Integrity-check and decode compactly referenced terminal replay files."""

    _validate_artifact_descriptor(
        objective_artifact,
        game_id=game_id,
        artifact_kind=ArtifactKind.REPLAY_BUNDLE,
        schema_version=OBJECTIVE_REPLAY_SCHEMA_VERSION,
    )
    _validate_artifact_descriptor(
        subjective_artifact,
        game_id=game_id,
        artifact_kind=ArtifactKind.SUBJECTIVE_REPLAY_BUNDLE,
        schema_version=SUBJECTIVE_REPLAY_SCHEMA_VERSION,
    )
    objective_payload = artifact_store.read_bytes(
        objective_artifact.content_digest,
    )
    subjective_payload = artifact_store.read_bytes(
        subjective_artifact.content_digest,
    )
    if len(objective_payload) != objective_artifact.byte_size:
        raise TerminalEvidenceError(
            "objective_replay_size_mismatch",
            "Objective replay byte size does not match its descriptor",
        )
    if len(subjective_payload) != subjective_artifact.byte_size:
        raise TerminalEvidenceError(
            "subjective_replay_size_mismatch",
            "Subjective replay byte size does not match its descriptor",
        )
    try:
        objective_replay = ObjectiveReplayBundle.model_validate_json(
            objective_payload,
        )
        subjective_replay = SubjectivePlayerReplayArchive.model_validate_json(
            subjective_payload,
        )
    except ValueError as exc:
        raise TerminalEvidenceError(
            "terminal_replay_contract_invalid",
            "Stored terminal replay bytes do not match their contracts",
        ) from exc
    validate_terminal_evidence(
        game_id=game_id,
        evidence=evidence,
        objective_replay=objective_replay,
        subjective_replay=subjective_replay,
        known_membership_ids=known_membership_ids,
    )
    return objective_replay, subjective_replay


def _validate_artifact_descriptor(
    artifact: ArtifactCreate,
    *,
    game_id: UUID,
    artifact_kind: ArtifactKind,
    schema_version: str,
) -> None:
    if artifact.game_id != game_id:
        raise TerminalEvidenceError(
            "terminal_artifact_game_mismatch",
            "Terminal replay descriptor belongs to another game",
        )
    if (
        artifact.artifact_kind is not artifact_kind
        or artifact.schema_version != schema_version
        or artifact.media_type != "application/json"
    ):
        raise TerminalEvidenceError(
            "terminal_artifact_descriptor_invalid",
            "Terminal replay descriptor does not match its wire contract",
        )


def validate_terminal_evidence(
    *,
    game_id: UUID,
    evidence: WorkerSummaryEvidence,
    objective_replay: ObjectiveReplayBundle,
    subjective_replay: SubjectivePlayerReplayArchive,
    known_membership_ids: frozenset[UUID],
) -> None:
    expected_game_id = str(game_id)
    if evidence.summary.game_id != expected_game_id:
        raise TerminalEvidenceError(
            "summary_game_mismatch",
            "Terminal summary belongs to another game",
        )
    if objective_replay.game_id != expected_game_id:
        raise TerminalEvidenceError(
            "replay_game_mismatch",
            "Objective replay belongs to another game",
        )
    if subjective_replay.game_id != expected_game_id:
        raise TerminalEvidenceError(
            "subjective_replay_game_mismatch",
            "Player replay belongs to another game",
        )
    encounter_uuid = str(evidence.summary.encounter_uuid)
    if objective_replay.encounter_uuid != encounter_uuid:
        raise TerminalEvidenceError(
            "replay_encounter_mismatch",
            "Objective replay and summary describe different encounters",
        )
    if subjective_replay.encounter_uuid != encounter_uuid:
        raise TerminalEvidenceError(
            "subjective_replay_encounter_mismatch",
            "Player replay and summary describe different encounters",
        )
    if objective_replay.generation_id != str(evidence.generation_id):
        raise TerminalEvidenceError(
            "replay_generation_mismatch",
            "Objective replay and summary use different generations",
        )
    terminal = evidence.summary.terminal_cursor
    if (
        objective_replay.terminal_event_cursor != terminal.event_cursor
        or objective_replay.terminal_combat_log_cursor
        != terminal.combat_log_cursor
    ):
        raise TerminalEvidenceError(
            "replay_cursor_mismatch",
            "Objective replay and summary terminal cursors differ",
        )
    if (
        subjective_replay.terminal_source_event_cursor
        != terminal.event_cursor
        or subjective_replay.terminal_combat_log_cursor
        != terminal.combat_log_cursor
    ):
        raise TerminalEvidenceError(
            "subjective_replay_cursor_mismatch",
            "Player replay and summary terminal cursors differ",
        )
    replay_membership_ids: set[UUID] = set()
    try:
        for bundle in subjective_replay.membership_replays:
            replay_membership_ids.add(UUID(bundle.membership_id))
    except ValueError as exc:
        raise TerminalEvidenceError(
            "subjective_replay_membership_mismatch",
            "Player replay contains a non-directory membership identity",
        ) from exc
    if not replay_membership_ids.issubset(known_membership_ids):
        raise TerminalEvidenceError(
            "subjective_replay_membership_mismatch",
            "Player replay contains an unknown or cross-game membership",
        )


__all__ = [
    "OBJECTIVE_REPLAY_SCHEMA_VERSION",
    "SUBJECTIVE_REPLAY_SCHEMA_VERSION",
    "TerminalEvidenceError",
    "publish_terminal_evidence",
    "store_terminal_artifacts",
    "validate_stored_terminal_artifacts",
    "validate_terminal_evidence",
]
