"""Deployment configuration for trusted installed content-pack roots."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONTENT_PACK_ROOT = (REPOSITORY_ROOT / "content_packs").resolve()
CONTENT_PACK_ROOTS_ENV = "DND_CONTENT_PACK_ROOTS"


def configured_content_pack_roots(
    environment: Mapping[str, str] | None = None,
) -> tuple[Path, ...]:
    """Return the repository root plus normalized absolute deployment roots."""
    values = os.environ if environment is None else environment
    configured = values.get(CONTENT_PACK_ROOTS_ENV, "")
    roots: dict[str, Path] = {
        DEFAULT_CONTENT_PACK_ROOT.as_posix(): DEFAULT_CONTENT_PACK_ROOT,
    }
    for raw_path in configured.split(os.pathsep):
        if not raw_path:
            continue
        path = Path(raw_path)
        if not path.is_absolute():
            raise ValueError(
                f"{CONTENT_PACK_ROOTS_ENV} entries must be absolute: "
                f"{raw_path!r}",
            )
        resolved = path.resolve(strict=True)
        if not resolved.is_dir():
            raise ValueError(f"Content pack root is not a directory: {resolved}")
        roots[resolved.as_posix()] = resolved
    additional = tuple(
        roots[key]
        for key in sorted(roots)
        if roots[key] != DEFAULT_CONTENT_PACK_ROOT
    )
    return (DEFAULT_CONTENT_PACK_ROOT, *additional)
