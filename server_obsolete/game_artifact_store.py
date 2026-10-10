"""Immutable content-addressed storage for canonical JSON artifact bytes.

The store owns bytes only.  Replay schemas, game-directory records, and route
authorization remain outside this module so the same storage primitive can
retain any typed JSON evidence without depending on its DTO.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import os
from pathlib import Path
import stat
from tempfile import NamedTemporaryFile
from typing import Any

from server.canonical_json import canonical_json_bytes


_SHA256_HEXDIGEST_LENGTH = 64
_LOWERCASE_HEXADECIMAL = frozenset("0123456789abcdef")


class ArtifactStoreError(RuntimeError):
    """Base error raised by the immutable artifact byte store."""


class ArtifactIntegrityError(ArtifactStoreError):
    """Stored bytes do not match their immutable content identity."""


class ArtifactNotFoundError(ArtifactStoreError):
    """No artifact bytes exist for the requested content digest."""


class ArtifactPathError(ArtifactStoreError, ValueError):
    """An artifact path or digest would escape the store namespace."""


@dataclass(frozen=True, slots=True)
class JsonArtifactMetadata:
    """Location and exact content identity of one stored JSON artifact."""

    uri: str
    path: Path
    byte_size: int
    content_digest: str


class GameArtifactStore:
    """Store canonical JSON bytes under immutable SHA-256 identities.

    Objects use the layout ``<root>/sha256/<prefix>/<digest>.json``.  A
    temporary file is fully flushed before an atomic hard-link publishes the
    final name, so readers never observe a partially written artifact and an
    existing identity is never overwritten.
    """

    def __init__(self, root: str | Path) -> None:
        configured_root = Path(root)
        configured_root.mkdir(parents=True, exist_ok=True)
        if not configured_root.is_dir():
            raise ArtifactPathError(f"Artifact root is not a directory: {configured_root}")

        self._root = configured_root.resolve()
        object_root = self._root / "sha256"
        object_root.mkdir(exist_ok=True)
        if object_root.is_symlink() or object_root.resolve() != object_root:
            raise ArtifactPathError("Artifact object namespace cannot be a symbolic link")
        self._object_root = object_root

    @property
    def root(self) -> Path:
        """Absolute configured artifact-store root."""

        return self._root

    def put_json(self, value: Any) -> JsonArtifactMetadata:
        """Canonically encode and immutably retain one JSON-compatible value.

        Repeating the same write is an idempotent lookup.  If bytes already
        occupying the derived digest path differ from the canonical payload,
        the store raises rather than replacing or accepting corrupted data.
        """

        payload = canonical_json_bytes(value)
        content_digest = sha256(payload).hexdigest()
        target = self.path_for_digest(content_digest)
        self._ensure_shard_directory(target.parent)

        if target.exists() or target.is_symlink():
            self._verify_existing(target, content_digest, expected=payload)
            return self._metadata(target, payload, content_digest)

        temporary_path: Path | None = None
        try:
            with NamedTemporaryFile(
                mode="wb",
                dir=target.parent,
                prefix=f".{content_digest}.",
                suffix=".tmp",
                delete=False,
            ) as temporary:
                temporary.write(payload)
                temporary.flush()
                os.fsync(temporary.fileno())
                temporary_path = Path(temporary.name)

            try:
                os.link(temporary_path, target)
                _fsync_directory(target.parent)
            except FileExistsError:
                self._verify_existing(target, content_digest, expected=payload)
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

        self._verify_existing(target, content_digest, expected=payload)
        return self._metadata(target, payload, content_digest)

    def read_bytes(self, content_digest: str) -> bytes:
        """Read and integrity-check exact canonical bytes by SHA-256 digest."""

        target = self.path_for_digest(content_digest)
        return self._read_verified(target, content_digest)

    def path_for_digest(self, content_digest: str) -> Path:
        """Return the safe object path for one lowercase SHA-256 digest."""

        self._validate_digest(content_digest)
        target = (
            self._object_root
            / content_digest[:2]
            / f"{content_digest}.json"
        )
        resolved_parent = target.parent.resolve(strict=False)
        if not resolved_parent.is_relative_to(self._object_root):
            raise ArtifactPathError("Artifact path escapes the configured store root")
        if target.is_symlink():
            raise ArtifactPathError("Artifact object path cannot be a symbolic link")
        return target

    def _ensure_shard_directory(self, shard: Path) -> None:
        """Create one digest shard while refusing redirected directories."""

        shard.mkdir(exist_ok=True)
        if shard.is_symlink() or shard.resolve() != shard:
            raise ArtifactPathError("Artifact digest shard cannot be a symbolic link")
        if not shard.is_dir():
            raise ArtifactPathError(f"Artifact digest shard is not a directory: {shard}")

    def _read_verified(self, target: Path, content_digest: str) -> bytes:
        """Read a regular object and verify its name-to-bytes commitment."""

        try:
            file_status = target.lstat()
        except FileNotFoundError as exc:
            raise ArtifactNotFoundError(
                f"Artifact bytes not found for digest {content_digest}"
            ) from exc
        if not stat.S_ISREG(file_status.st_mode):
            raise ArtifactIntegrityError(
                f"Artifact path is not a regular file for digest {content_digest}"
            )

        payload = target.read_bytes()
        actual_digest = sha256(payload).hexdigest()
        if actual_digest != content_digest:
            raise ArtifactIntegrityError(
                "Stored artifact digest mismatch: "
                f"expected {content_digest}, found {actual_digest}"
            )
        return payload

    def _verify_existing(
        self,
        target: Path,
        content_digest: str,
        *,
        expected: bytes,
    ) -> None:
        """Require an occupied content identity to contain the exact bytes."""

        existing = self._read_verified(target, content_digest)
        if existing != expected:
            raise ArtifactIntegrityError(
                f"Artifact identity {content_digest} contains conflicting bytes"
            )

    @staticmethod
    def _metadata(
        path: Path,
        payload: bytes,
        content_digest: str,
    ) -> JsonArtifactMetadata:
        """Build immutable metadata for verified stored bytes."""

        return JsonArtifactMetadata(
            uri=path.as_uri(),
            path=path,
            byte_size=len(payload),
            content_digest=content_digest,
        )

    @staticmethod
    def _validate_digest(content_digest: str) -> None:
        """Reject non-canonical digests before constructing any filesystem path."""

        if (
            len(content_digest) != _SHA256_HEXDIGEST_LENGTH
            or any(character not in _LOWERCASE_HEXADECIMAL for character in content_digest)
        ):
            raise ArtifactPathError(
                "Artifact digest must be exactly 64 lowercase hexadecimal characters"
            )


def _fsync_directory(directory: Path) -> None:
    """Durably publish one newly linked immutable artifact name."""

    descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
