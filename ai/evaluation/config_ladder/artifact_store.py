"""Durable, hash-addressed storage primitives for isolated match workers."""

from __future__ import annotations

import errno
import fcntl
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
from types import TracebackType
from typing import Any, TypeVar
from uuid import uuid4

from pydantic import BaseModel, TypeAdapter

from ai.evaluation.config_ladder.worker_contracts import ArtifactDescriptor


_ModelT = TypeVar("_ModelT", bound=BaseModel)
_JSON_VALUE_ADAPTER = TypeAdapter(Any)
_SAFE_COMPONENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_COPY_CHUNK_BYTES = 1024 * 1024


class ImmutableArtifactError(RuntimeError):
    """Raised when an immutable path already contains different bytes."""


class ArtifactValidationError(RuntimeError):
    """Raised when persisted evidence does not match its integrity metadata."""


class ExperimentLockUnavailable(RuntimeError):
    """Raised when another coordinator already owns an experiment lock."""


def _json_value(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    return _JSON_VALUE_ADAPTER.dump_python(value, mode="json")


def canonical_json_bytes(value: Any, *, trailing_newline: bool = False) -> bytes:
    """Serialize a JSON-compatible value with one stable byte representation."""
    encoded = json.dumps(
        _json_value(value),
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return encoded + (b"\n" if trailing_newline else b"")


def sha256_bytes(payload: bytes) -> str:
    """Return the lowercase SHA-256 digest of exact bytes."""
    return hashlib.sha256(payload).hexdigest()


def sha256_json(value: Any) -> str:
    """Hash the canonical JSON representation of a value."""
    return sha256_bytes(canonical_json_bytes(value))


def reproducible_result_hash(payload: dict[str, Any]) -> str:
    """Reproduce a semantic match hash or a generic task payload hash.

    Real-match evidence carries a normalized projection whose own hash excludes
    the hash field. Infrastructure probes have no semantic projection and keep
    using the complete payload.
    """
    normalized = payload.get("normalized_result")
    if isinstance(normalized, dict) and isinstance(normalized.get("semantic_hash"), str):
        semantic_payload = {
            key: value
            for key, value in normalized.items()
            if key != "semantic_hash"
        }
        return sha256_json(semantic_payload)
    return sha256_json(payload)


def sha256_file(path: Path) -> str:
    """Hash a file without loading it into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(_COPY_CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _temporary_path(destination: Path) -> Path:
    return destination.with_name(f".{destination.name}.{os.getpid()}.{uuid4().hex}.tmp")


def atomic_write_bytes(path: Path, payload: bytes, *, immutable: bool = True) -> str:
    """Publish bytes atomically, refusing conflicting immutable rewrites."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload_hash = sha256_bytes(payload)

    if path.exists():
        existing_hash = sha256_file(path)
        if existing_hash == payload_hash:
            return payload_hash
        if immutable:
            raise ImmutableArtifactError(f"Immutable path has different content: {path}")

    temporary = _temporary_path(path)
    try:
        with temporary.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())

        if immutable:
            try:
                os.link(temporary, path)
            except FileExistsError:
                existing_hash = sha256_file(path)
                if existing_hash != payload_hash:
                    raise ImmutableArtifactError(f"Immutable path has different content: {path}")
            finally:
                temporary.unlink(missing_ok=True)
        else:
            os.replace(temporary, path)
        _fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)
    return payload_hash


def atomic_write_json(path: Path, value: Any, *, immutable: bool = True) -> str:
    """Publish canonical JSON with a trailing newline."""
    return atomic_write_bytes(
        Path(path),
        canonical_json_bytes(value, trailing_newline=True),
        immutable=immutable,
    )


def read_json_model(path: Path, model_type: type[_ModelT]) -> _ModelT:
    """Read and strictly validate one persisted protocol model."""
    return model_type.model_validate_json(Path(path).read_bytes())


def deterministic_gzip(payload: bytes, *, compresslevel: int = 6) -> bytes:
    """Compress bytes reproducibly by removing filename and timestamp metadata."""
    output = io.BytesIO()
    with gzip.GzipFile(
        filename="",
        mode="wb",
        compresslevel=compresslevel,
        fileobj=output,
        mtime=0,
    ) as stream:
        stream.write(payload)
    return output.getvalue()


def write_gzip_json(path: Path, value: Any) -> ArtifactDescriptor:
    """Write one immutable canonical JSON artifact using deterministic gzip."""
    path = Path(path)
    payload = canonical_json_bytes(value)
    compressed = deterministic_gzip(payload)
    compressed_hash = atomic_write_bytes(path, compressed, immutable=True)
    return ArtifactDescriptor(
        file_name=path.name,
        sha256=compressed_hash,
        size_bytes=len(compressed),
        payload_sha256=sha256_bytes(payload),
        payload_size_bytes=len(payload),
    )


def read_gzip_json(
    path: Path,
    *,
    expected: ArtifactDescriptor | None = None,
    max_payload_bytes: int = 512 * 1024 * 1024,
) -> tuple[Any, ArtifactDescriptor]:
    """Read, bound, and authenticate a deterministic gzip JSON artifact."""
    path = Path(path)
    compressed = path.read_bytes()
    if expected is not None:
        if path.name != expected.file_name:
            raise ArtifactValidationError(
                f"Artifact filename mismatch: {path.name!r} != {expected.file_name!r}"
            )
        if len(compressed) != expected.size_bytes:
            raise ArtifactValidationError("Compressed artifact size mismatch.")
        if sha256_bytes(compressed) != expected.sha256:
            raise ArtifactValidationError("Compressed artifact hash mismatch.")

    try:
        with gzip.GzipFile(fileobj=io.BytesIO(compressed), mode="rb") as stream:
            payload = stream.read(max_payload_bytes + 1)
    except (EOFError, OSError) as exc:
        raise ArtifactValidationError("Artifact is not a valid gzip stream.") from exc
    if len(payload) > max_payload_bytes:
        raise ArtifactValidationError(
            f"Artifact expands beyond the {max_payload_bytes}-byte safety limit."
        )

    descriptor = ArtifactDescriptor(
        file_name=path.name,
        sha256=sha256_bytes(compressed),
        size_bytes=len(compressed),
        payload_sha256=sha256_bytes(payload),
        payload_size_bytes=len(payload),
    )
    if expected is not None and descriptor != expected:
        raise ArtifactValidationError("Artifact payload integrity metadata mismatch.")
    try:
        value = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ArtifactValidationError("Artifact payload is not valid UTF-8 JSON.") from exc
    return value, descriptor


def promote_file_atomic(
    source: Path,
    destination: Path,
    *,
    expected_sha256: str | None = None,
) -> str:
    """Copy a private spool file into an immutable canonical path."""
    source = Path(source)
    destination = Path(destination)
    source_hash = sha256_file(source)
    if expected_sha256 is not None and source_hash != expected_sha256:
        raise ArtifactValidationError(f"Source hash mismatch while promoting {source}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        destination_hash = sha256_file(destination)
        if destination_hash != source_hash:
            raise ImmutableArtifactError(
                f"Canonical path has different content: {destination}"
            )
        return destination_hash

    temporary = _temporary_path(destination)
    try:
        with source.open("rb") as input_stream, temporary.open("xb") as output_stream:
            shutil.copyfileobj(input_stream, output_stream, length=_COPY_CHUNK_BYTES)
            output_stream.flush()
            os.fsync(output_stream.fileno())
        if sha256_file(temporary) != source_hash:
            raise ArtifactValidationError(f"Copied bytes changed while promoting {source}")
        try:
            os.link(temporary, destination)
        except FileExistsError:
            if sha256_file(destination) != source_hash:
                raise ImmutableArtifactError(
                    f"Canonical path has different content: {destination}"
                )
        finally:
            temporary.unlink(missing_ok=True)
        _fsync_directory(destination.parent)
    finally:
        temporary.unlink(missing_ok=True)
    return source_hash


def safe_path_component(value: str) -> str:
    """Validate an identity before using it as one filesystem component."""
    if value in {".", ".."} or _SAFE_COMPONENT.fullmatch(value) is None:
        raise ValueError(f"Unsafe path component: {value!r}")
    return value


class ExperimentLock:
    """Non-blocking process lock held for one coordinator's full lifetime."""

    def __init__(self, path: Path, *, metadata: dict[str, Any] | None = None) -> None:
        self.path = Path(path)
        self.metadata = dict(metadata or {})
        self._stream: io.TextIOWrapper | None = None

    def acquire(self) -> ExperimentLock:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        stream = self.path.open("a+", encoding="utf-8")
        try:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            stream.close()
            if exc.errno in {errno.EACCES, errno.EAGAIN}:
                raise ExperimentLockUnavailable(
                    f"Another coordinator owns {self.path}"
                ) from exc
            raise

        lock_value = {"pid": os.getpid(), **self.metadata}
        stream.seek(0)
        stream.truncate()
        stream.write(canonical_json_bytes(lock_value, trailing_newline=True).decode("ascii"))
        stream.flush()
        os.fsync(stream.fileno())
        self._stream = stream
        return self

    def release(self) -> None:
        if self._stream is None:
            return
        try:
            fcntl.flock(self._stream.fileno(), fcntl.LOCK_UN)
        finally:
            self._stream.close()
            self._stream = None

    def __enter__(self) -> ExperimentLock:
        return self.acquire()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.release()
