"""Durable generation-fenced terminal evidence written by hosted workers.

The spool is deliberately independent of gateway, repository, and ASGI
ownership.  A worker publishes immutable canonical component files first and
an authenticated ready manifest last.  Readers ignore incomplete component
sets until that final manifest exists.
"""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from hashlib import sha256
from pathlib import Path, PurePosixPath
from tempfile import NamedTemporaryFile
from typing import Literal, Self, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from server.canonical_json import canonical_json_bytes
from server.character_settlement import WorkerCharacterHoldingsEvidence
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


WORKER_TERMINAL_SPOOL_SCHEMA_VERSION = 1
WORKER_SUMMARY_EVIDENCE_SCHEMA = "dnd.worker-summary-evidence.v1"
WORKER_HOLDINGS_EVIDENCE_SCHEMA = "dnd.worker-character-holdings-evidence.v1"
OBJECTIVE_REPLAY_SCHEMA = (
    f"dnd.objective-replay.v{OBJECTIVE_REPLAY_CONTRACT_VERSION}."
    f"{OBJECTIVE_REPLAY_CONTRACT_HASH}"
)
SUBJECTIVE_REPLAY_SCHEMA = (
    f"dnd.subjective-player-replay.v{PLAYER_REPLAY_CONTRACT_VERSION}."
    f"{PLAYER_REPLAY_CONTRACT_HASH}"
)

_DIGEST_LENGTH = 64
_LOWERCASE_HEXADECIMAL = frozenset("0123456789abcdef")
_TERMINAL_DIRECTORY_NAME = "terminal"
_COMPONENT_DIRECTORY_NAME = "components"
_READY_MANIFEST_NAME = "ready.json"
_TerminalComponentModelT = TypeVar(
    "_TerminalComponentModelT",
    bound=BaseModel,
)


class WorkerTerminalSpoolError(RuntimeError):
    """Base error for hosted-worker terminal spool operations."""


class WorkerTerminalSpoolNotReady(WorkerTerminalSpoolError):
    """Raised when no final ready manifest has been published."""


class WorkerTerminalSpoolIntegrityError(WorkerTerminalSpoolError):
    """Raised when a manifest or component fails exact integrity checks."""


class WorkerTerminalComponentKind(str, Enum):
    """Closed component identities referenced by one ready manifest."""

    SUMMARY = "summary"
    OBJECTIVE_REPLAY = "objective_replay"
    SUBJECTIVE_REPLAY = "subjective_replay"
    HOLDINGS = "holdings"


class WorkerTerminalComponentDescriptor(BaseModel):
    """Authenticated location and wire identity of one component file."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    component_kind: WorkerTerminalComponentKind
    schema_id: str = Field(min_length=1)
    relative_path: str = Field(min_length=1)
    byte_size: int = Field(ge=1)
    content_digest: str = Field(
        min_length=_DIGEST_LENGTH,
        max_length=_DIGEST_LENGTH,
    )

    @model_validator(mode="after")
    def _validate_descriptor(self) -> Self:
        _validate_digest(self.content_digest, "component content digest")
        expected_path = _component_relative_path(
            self.component_kind,
            self.content_digest,
        )
        if self.relative_path != expected_path:
            raise ValueError(
                "terminal component path does not match its kind and digest",
            )
        if self.schema_id != _COMPONENT_SCHEMAS[self.component_kind]:
            raise ValueError(
                "terminal component schema does not match its kind",
            )
        return self


class WorkerTerminalReadyManifest(BaseModel):
    """Compact terminal boundary published after every component is durable."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = WORKER_TERMINAL_SPOOL_SCHEMA_VERSION
    game_id: UUID
    worker_instance_id: UUID
    worker_generation: int = Field(ge=1)
    ready_at: datetime
    summary: WorkerTerminalComponentDescriptor
    objective_replay: WorkerTerminalComponentDescriptor
    subjective_replay: WorkerTerminalComponentDescriptor
    holdings: WorkerTerminalComponentDescriptor | None = None
    manifest_digest: str = Field(
        min_length=_DIGEST_LENGTH,
        max_length=_DIGEST_LENGTH,
    )

    @classmethod
    def create(
        cls,
        *,
        game_id: UUID,
        worker_instance_id: UUID,
        worker_generation: int,
        summary: WorkerTerminalComponentDescriptor,
        objective_replay: WorkerTerminalComponentDescriptor,
        subjective_replay: WorkerTerminalComponentDescriptor,
        holdings: WorkerTerminalComponentDescriptor | None,
        ready_at: datetime | None = None,
    ) -> Self:
        """Create one ready manifest with its canonical self-authentication."""

        resolved_ready_at = datetime.now(UTC) if ready_at is None else ready_at
        payload = {
            "schema_version": WORKER_TERMINAL_SPOOL_SCHEMA_VERSION,
            "game_id": game_id,
            "worker_instance_id": worker_instance_id,
            "worker_generation": worker_generation,
            "ready_at": resolved_ready_at,
            "summary": summary,
            "objective_replay": objective_replay,
            "subjective_replay": subjective_replay,
            "holdings": holdings,
        }
        return cls(
            **payload,
            manifest_digest=sha256(canonical_json_bytes(payload)).hexdigest(),
        )

    @model_validator(mode="after")
    def _validate_manifest(self) -> Self:
        _validate_digest(self.manifest_digest, "terminal manifest digest")
        if self.ready_at.tzinfo is None or self.ready_at.utcoffset() is None:
            raise ValueError("terminal ready timestamp must be timezone-aware")
        expected_kinds = (
            (self.summary, WorkerTerminalComponentKind.SUMMARY),
            (
                self.objective_replay,
                WorkerTerminalComponentKind.OBJECTIVE_REPLAY,
            ),
            (
                self.subjective_replay,
                WorkerTerminalComponentKind.SUBJECTIVE_REPLAY,
            ),
        )
        if any(
            descriptor.component_kind is not expected
            for descriptor, expected in expected_kinds
        ):
            raise ValueError(
                "terminal manifest component occupies the wrong field",
            )
        if (
            self.holdings is not None
            and self.holdings.component_kind
            is not WorkerTerminalComponentKind.HOLDINGS
        ):
            raise ValueError(
                "terminal holdings descriptor occupies the wrong field",
            )
        payload = {
            "schema_version": self.schema_version,
            "game_id": self.game_id,
            "worker_instance_id": self.worker_instance_id,
            "worker_generation": self.worker_generation,
            "ready_at": self.ready_at,
            "summary": self.summary,
            "objective_replay": self.objective_replay,
            "subjective_replay": self.subjective_replay,
            "holdings": self.holdings,
        }
        expected_digest = sha256(canonical_json_bytes(payload)).hexdigest()
        if expected_digest != self.manifest_digest:
            raise ValueError("terminal ready manifest digest mismatch")
        return self


@dataclass(frozen=True, slots=True)
class WorkerTerminalSpoolBundle:
    """Fully decoded and cross-validated terminal evidence."""

    manifest: WorkerTerminalReadyManifest
    summary: WorkerSummaryEvidence
    objective_replay: ObjectiveReplayBundle
    subjective_replay: SubjectivePlayerReplayArchive
    holdings: WorkerCharacterHoldingsEvidence | None


_COMPONENT_SCHEMAS = {
    WorkerTerminalComponentKind.SUMMARY: WORKER_SUMMARY_EVIDENCE_SCHEMA,
    WorkerTerminalComponentKind.OBJECTIVE_REPLAY: OBJECTIVE_REPLAY_SCHEMA,
    WorkerTerminalComponentKind.SUBJECTIVE_REPLAY: SUBJECTIVE_REPLAY_SCHEMA,
    WorkerTerminalComponentKind.HOLDINGS: WORKER_HOLDINGS_EVIDENCE_SCHEMA,
}


class WorkerTerminalSpool:
    """Own one hosted game's immutable terminal component directory."""

    def __init__(self, game_runtime_directory: str | Path) -> None:
        runtime_directory = Path(game_runtime_directory)
        runtime_directory.mkdir(parents=True, exist_ok=True)
        self._runtime_directory = _require_directory(
            runtime_directory,
            "worker game runtime directory",
        )
        terminal_directory = self._runtime_directory / _TERMINAL_DIRECTORY_NAME
        terminal_directory.mkdir(exist_ok=True)
        self._terminal_directory = _require_directory(
            terminal_directory,
            "worker terminal directory",
        )
        component_directory = (
            self._terminal_directory / _COMPONENT_DIRECTORY_NAME
        )
        component_directory.mkdir(exist_ok=True)
        self._component_directory = _require_directory(
            component_directory,
            "worker terminal component directory",
        )

    @property
    def ready_manifest_path(self) -> Path:
        """Return the fixed manifest path whose existence denotes readiness."""

        return self._terminal_directory / _READY_MANIFEST_NAME

    def publish(
        self,
        *,
        game_id: UUID,
        worker_instance_id: UUID,
        worker_generation: int,
        summary: WorkerSummaryEvidence,
        objective_replay: ObjectiveReplayBundle,
        subjective_replay: SubjectivePlayerReplayArchive,
        holdings: WorkerCharacterHoldingsEvidence | None = None,
    ) -> WorkerTerminalReadyManifest:
        """Durably publish components followed by the generation-fenced manifest."""

        _validate_terminal_components(
            game_id=game_id,
            summary=summary,
            objective_replay=objective_replay,
            subjective_replay=subjective_replay,
            holdings=holdings,
        )
        if self.ready_manifest_path.exists() or self.ready_manifest_path.is_symlink():
            existing = self.read_ready(
                expected_game_id=game_id,
                expected_worker_instance_id=worker_instance_id,
                expected_worker_generation=worker_generation,
            )
            if (
                not _same_canonical_value(existing.summary, summary)
                or not _same_canonical_value(
                    existing.objective_replay,
                    objective_replay,
                )
                or not _same_canonical_value(
                    existing.subjective_replay,
                    subjective_replay,
                )
                or not _same_canonical_value(existing.holdings, holdings)
            ):
                raise WorkerTerminalSpoolIntegrityError(
                    "worker terminal ready manifest already authenticates "
                    "different evidence",
                )
            return existing.manifest
        summary_descriptor = self._publish_component(
            WorkerTerminalComponentKind.SUMMARY,
            summary,
        )
        objective_descriptor = self._publish_component(
            WorkerTerminalComponentKind.OBJECTIVE_REPLAY,
            objective_replay,
        )
        subjective_descriptor = self._publish_component(
            WorkerTerminalComponentKind.SUBJECTIVE_REPLAY,
            subjective_replay,
        )
        holdings_descriptor = (
            None
            if holdings is None
            else self._publish_component(
                WorkerTerminalComponentKind.HOLDINGS,
                holdings,
            )
        )
        manifest = WorkerTerminalReadyManifest.create(
            game_id=game_id,
            worker_instance_id=worker_instance_id,
            worker_generation=worker_generation,
            summary=summary_descriptor,
            objective_replay=objective_descriptor,
            subjective_replay=subjective_descriptor,
            holdings=holdings_descriptor,
        )
        self._publish_ready_manifest(manifest)
        return manifest

    def read_ready(
        self,
        *,
        expected_game_id: UUID,
        expected_worker_instance_id: UUID,
        expected_worker_generation: int,
    ) -> WorkerTerminalSpoolBundle:
        """Read and verify one complete ready manifest plus all components."""

        ready_path = self.ready_manifest_path
        if not ready_path.exists() and not ready_path.is_symlink():
            raise WorkerTerminalSpoolNotReady(
                "worker terminal ready manifest does not exist",
            )
        ready_payload = _read_regular_file(
            ready_path,
            "worker terminal ready manifest",
        )
        try:
            manifest = WorkerTerminalReadyManifest.model_validate_json(
                ready_payload,
            )
        except ValueError as exc:
            raise WorkerTerminalSpoolIntegrityError(
                "worker terminal ready manifest is invalid",
            ) from exc
        if (
            manifest.game_id != expected_game_id
            or manifest.worker_instance_id != expected_worker_instance_id
            or manifest.worker_generation != expected_worker_generation
        ):
            raise WorkerTerminalSpoolIntegrityError(
                "worker terminal ready manifest identity or generation mismatch",
            )

        summary = self._read_component(
            manifest.summary,
            WorkerSummaryEvidence,
        )
        objective_replay = self._read_component(
            manifest.objective_replay,
            ObjectiveReplayBundle,
        )
        subjective_replay = self._read_component(
            manifest.subjective_replay,
            SubjectivePlayerReplayArchive,
        )
        holdings = (
            None
            if manifest.holdings is None
            else self._read_component(
                manifest.holdings,
                WorkerCharacterHoldingsEvidence,
            )
        )
        _validate_terminal_components(
            game_id=expected_game_id,
            summary=summary,
            objective_replay=objective_replay,
            subjective_replay=subjective_replay,
            holdings=holdings,
        )
        return WorkerTerminalSpoolBundle(
            manifest=manifest,
            summary=summary,
            objective_replay=objective_replay,
            subjective_replay=subjective_replay,
            holdings=holdings,
        )

    def _publish_component(
        self,
        component_kind: WorkerTerminalComponentKind,
        value: BaseModel,
    ) -> WorkerTerminalComponentDescriptor:
        payload = canonical_json_bytes(value)
        content_digest = sha256(payload).hexdigest()
        descriptor = WorkerTerminalComponentDescriptor(
            component_kind=component_kind,
            schema_id=_COMPONENT_SCHEMAS[component_kind],
            relative_path=_component_relative_path(
                component_kind,
                content_digest,
            ),
            byte_size=len(payload),
            content_digest=content_digest,
        )
        path = self._path_for_descriptor(descriptor)
        _publish_immutable_file(
            path,
            payload,
            directory=self._component_directory,
            label=f"worker terminal {component_kind.value} component",
        )
        return descriptor

    def _publish_ready_manifest(
        self,
        manifest: WorkerTerminalReadyManifest,
    ) -> None:
        payload = canonical_json_bytes(manifest)
        _publish_immutable_file(
            self.ready_manifest_path,
            payload,
            directory=self._terminal_directory,
            label="worker terminal ready manifest",
        )

    def _read_component(
        self,
        descriptor: WorkerTerminalComponentDescriptor,
        model_type: type[_TerminalComponentModelT],
    ) -> _TerminalComponentModelT:
        path = self._path_for_descriptor(descriptor)
        payload = _read_regular_file(
            path,
            f"worker terminal {descriptor.component_kind.value} component",
        )
        if len(payload) != descriptor.byte_size:
            raise WorkerTerminalSpoolIntegrityError(
                f"worker terminal {descriptor.component_kind.value} size mismatch",
            )
        if sha256(payload).hexdigest() != descriptor.content_digest:
            raise WorkerTerminalSpoolIntegrityError(
                f"worker terminal {descriptor.component_kind.value} digest mismatch",
            )
        try:
            return model_type.model_validate_json(payload)
        except ValueError as exc:
            raise WorkerTerminalSpoolIntegrityError(
                f"worker terminal {descriptor.component_kind.value} schema mismatch",
            ) from exc

    def _path_for_descriptor(
        self,
        descriptor: WorkerTerminalComponentDescriptor,
    ) -> Path:
        relative = PurePosixPath(descriptor.relative_path)
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or relative.parts[:1] != (_COMPONENT_DIRECTORY_NAME,)
        ):
            raise WorkerTerminalSpoolIntegrityError(
                "worker terminal component path escapes its spool",
            )
        path = self._terminal_directory.joinpath(*relative.parts)
        if path.parent.resolve(strict=False) != self._component_directory:
            raise WorkerTerminalSpoolIntegrityError(
                "worker terminal component path escapes its component directory",
            )
        return path


def _validate_terminal_components(
    *,
    game_id: UUID,
    summary: WorkerSummaryEvidence,
    objective_replay: ObjectiveReplayBundle,
    subjective_replay: SubjectivePlayerReplayArchive,
    holdings: WorkerCharacterHoldingsEvidence | None,
) -> None:
    """Require every component to describe one exact terminal boundary."""

    expected_game_id = str(game_id)
    terminal = summary.summary.terminal_cursor
    if (
        summary.summary.game_id != expected_game_id
        or objective_replay.game_id != expected_game_id
        or subjective_replay.game_id != expected_game_id
    ):
        raise WorkerTerminalSpoolIntegrityError(
            "worker terminal components belong to different games",
        )
    encounter_uuid = str(summary.summary.encounter_uuid)
    if (
        objective_replay.encounter_uuid != encounter_uuid
        or subjective_replay.encounter_uuid != encounter_uuid
    ):
        raise WorkerTerminalSpoolIntegrityError(
            "worker terminal components describe different encounters",
        )
    if objective_replay.generation_id != str(summary.generation_id):
        raise WorkerTerminalSpoolIntegrityError(
            "worker terminal objective replay generation mismatch",
        )
    if (
        objective_replay.terminal_event_cursor != terminal.event_cursor
        or objective_replay.terminal_combat_log_cursor
        != terminal.combat_log_cursor
        or subjective_replay.terminal_source_event_cursor
        != terminal.event_cursor
        or subjective_replay.terminal_combat_log_cursor
        != terminal.combat_log_cursor
    ):
        raise WorkerTerminalSpoolIntegrityError(
            "worker terminal component cursor mismatch",
        )
    if holdings is not None and (
        holdings.game_id != game_id
        or holdings.generation_id != summary.generation_id
        or holdings.terminal_event_cursor != terminal.event_cursor
        or holdings.terminal_combat_log_cursor != terminal.combat_log_cursor
    ):
        raise WorkerTerminalSpoolIntegrityError(
            "worker terminal holdings boundary mismatch",
        )


def _component_relative_path(
    component_kind: WorkerTerminalComponentKind,
    content_digest: str,
) -> str:
    _validate_digest(content_digest, "component content digest")
    return (
        f"{_COMPONENT_DIRECTORY_NAME}/"
        f"{component_kind.value}.{content_digest}.json"
    )


def _same_canonical_value(left: object, right: object) -> bool:
    if left is None or right is None:
        return left is right
    return canonical_json_bytes(left) == canonical_json_bytes(right)


def _validate_digest(value: str, label: str) -> None:
    if (
        len(value) != _DIGEST_LENGTH
        or any(character not in _LOWERCASE_HEXADECIMAL for character in value)
    ):
        raise ValueError(
            f"{label} must be exactly 64 lowercase hexadecimal characters",
        )


def _require_directory(path: Path, label: str) -> Path:
    if path.is_symlink():
        raise WorkerTerminalSpoolIntegrityError(
            f"{label} cannot be a symbolic link",
        )
    resolved = path.resolve()
    if not resolved.is_dir():
        raise WorkerTerminalSpoolIntegrityError(
            f"{label} is not a directory",
        )
    return resolved


def _publish_immutable_file(
    path: Path,
    payload: bytes,
    *,
    directory: Path,
    label: str,
) -> None:
    """Publish bytes once by hard link, then fsync the owning directory."""

    if path.exists() or path.is_symlink():
        existing = _read_regular_file(path, label)
        if existing != payload:
            raise WorkerTerminalSpoolIntegrityError(
                f"{label} already contains conflicting bytes",
            )
        return

    temporary_path: Path | None = None
    try:
        with NamedTemporaryFile(
            mode="wb",
            dir=directory,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary.write(payload)
            temporary.flush()
            os.fsync(temporary.fileno())
            temporary_path = Path(temporary.name)
        try:
            os.link(temporary_path, path)
        except FileExistsError:
            existing = _read_regular_file(path, label)
            if existing != payload:
                raise WorkerTerminalSpoolIntegrityError(
                    f"{label} was concurrently published with conflicting bytes",
                )
        _fsync_directory(directory)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def _read_regular_file(path: Path, label: str) -> bytes:
    try:
        file_status = path.lstat()
    except FileNotFoundError as exc:
        raise WorkerTerminalSpoolIntegrityError(
            f"{label} is missing",
        ) from exc
    if not stat.S_ISREG(file_status.st_mode):
        raise WorkerTerminalSpoolIntegrityError(
            f"{label} is not a regular file",
        )
    try:
        return path.read_bytes()
    except OSError as exc:
        raise WorkerTerminalSpoolIntegrityError(
            f"{label} could not be read",
        ) from exc


def _fsync_directory(directory: Path) -> None:
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    descriptor = os.open(directory, flags)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


__all__ = [
    "OBJECTIVE_REPLAY_SCHEMA",
    "SUBJECTIVE_REPLAY_SCHEMA",
    "WORKER_HOLDINGS_EVIDENCE_SCHEMA",
    "WORKER_SUMMARY_EVIDENCE_SCHEMA",
    "WORKER_TERMINAL_SPOOL_SCHEMA_VERSION",
    "WorkerTerminalComponentDescriptor",
    "WorkerTerminalComponentKind",
    "WorkerTerminalReadyManifest",
    "WorkerTerminalSpool",
    "WorkerTerminalSpoolBundle",
    "WorkerTerminalSpoolError",
    "WorkerTerminalSpoolIntegrityError",
    "WorkerTerminalSpoolNotReady",
]
