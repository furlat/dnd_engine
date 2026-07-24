"""Focused tests for immutable content-addressed game artifact bytes."""

from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path

import pytest

from server.game_artifact_store import (
    ArtifactIntegrityError,
    ArtifactPathError,
    GameArtifactStore,
)


def test_canonical_json_roundtrip_returns_exact_metadata(tmp_path: Path) -> None:
    """Stored JSON is canonical, addressable, and byte-for-byte readable."""

    store = GameArtifactStore(tmp_path / "artifacts")
    metadata = store.put_json({"z": 7, "alpha": [True, None, "value"]})

    expected = b'{"alpha":[true,null,"value"],"z":7}'
    expected_digest = sha256(expected).hexdigest()
    assert metadata.content_digest == expected_digest
    assert metadata.byte_size == len(expected)
    assert metadata.path == (
        store.root / "sha256" / expected_digest[:2] / f"{expected_digest}.json"
    )
    assert metadata.uri == metadata.path.as_uri()
    assert store.read_bytes(expected_digest) == expected
    assert json.loads(store.read_bytes(expected_digest)) == {
        "alpha": [True, None, "value"],
        "z": 7,
    }


def test_repeated_semantic_write_deduplicates_without_replacing(tmp_path: Path) -> None:
    """Equivalent canonical payloads retain one unchanged filesystem object."""

    store = GameArtifactStore(tmp_path / "artifacts")
    first = store.put_json({"second": 2, "first": 1})
    first_stat = first.path.stat()

    second = store.put_json({"first": 1, "second": 2})
    second_stat = second.path.stat()

    assert second == first
    assert second_stat.st_ino == first_stat.st_ino
    assert second_stat.st_mtime_ns == first_stat.st_mtime_ns
    assert tuple((store.root / "sha256" / first.content_digest[:2]).glob("*.json")) == (
        first.path,
    )


def test_existing_corruption_is_refused_and_never_overwritten(tmp_path: Path) -> None:
    """A damaged digest identity fails reads and idempotent publication."""

    store = GameArtifactStore(tmp_path / "artifacts")
    value = {"game": "finished", "events": [1, 2, 3]}
    metadata = store.put_json(value)
    corrupt_bytes = b'{"corrupted":true}'
    metadata.path.write_bytes(corrupt_bytes)

    with pytest.raises(ArtifactIntegrityError, match="digest mismatch"):
        store.read_bytes(metadata.content_digest)
    with pytest.raises(ArtifactIntegrityError, match="digest mismatch"):
        store.put_json(value)
    assert metadata.path.read_bytes() == corrupt_bytes


@pytest.mark.parametrize(
    "unsafe_digest",
    (
        "../outside",
        "a" * 63,
        "a" * 65,
        "A" * 64,
        "g" * 64,
        "0" * 63 + "/",
    ),
)
def test_digest_path_rejects_noncanonical_or_traversing_input(
    tmp_path: Path,
    unsafe_digest: str,
) -> None:
    """Callers cannot turn a content digest into an arbitrary path."""

    store = GameArtifactStore(tmp_path / "artifacts")
    with pytest.raises(ArtifactPathError, match="64 lowercase hexadecimal"):
        store.path_for_digest(unsafe_digest)


def test_symbolic_link_shard_cannot_redirect_artifacts_outside_root(tmp_path: Path) -> None:
    """A redirected digest shard is rejected before any bytes are written."""

    store = GameArtifactStore(tmp_path / "artifacts")
    outside = tmp_path / "outside"
    outside.mkdir()
    redirected_shard = store.root / "sha256" / "aa"
    try:
        os.symlink(outside, redirected_shard, target_is_directory=True)
    except (NotImplementedError, OSError):
        pytest.skip("Symbolic links are unavailable on this platform")

    with pytest.raises(ArtifactPathError, match="escapes"):
        store.path_for_digest("aa" + "0" * 62)
    assert tuple(outside.iterdir()) == ()
