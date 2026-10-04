"""Offline selection over existing storage addresses, without an owner registry."""

import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
from typing import Iterator


def _paths(storage: dict) -> Iterator[str]:
    for phase in storage.get("phases", {}).values():
        packet = phase.get("surfaceFrames")
        if packet is not None:
            if packet.get("pattern") is not None:
                yield packet["pattern"]
            if packet.get("archive") is not None:
                yield packet["archive"]["file"]
            for parts in packet.get("componentsByFacing", {}).values():
                for part in parts:
                    if part.get("pattern") is not None:
                        yield part["pattern"]
                    if part.get("archive") is not None:
                        yield part["archive"]["file"]
        for layer in phase.get("layers", ()):
            if layer.get("pattern") is not None:
                yield layer["pattern"]
            for pages in layer.get("pages", {}).values():
                for page in pages:
                    yield page["file"]
            sequences = layer.get("partsByFacing", {}).values() if "partsByFacing" in layer else (layer.get("parts", ()),)
            for frames in sequences:
                for parts in frames:
                    for part in parts:
                        yield part["file"]
                        if part.get("footpoint") is not None:
                            yield part["footpoint"]["file"]


def owns_selected_media(storage: dict, identity: str, media_root: str) -> bool:
    """A historical converter may refresh its own selected media, not another delivery.

    No selection yet permits initial conversion. Explicitly importing the newer
    delivery owns replacement; rerunning an older bundle preserves that choice.
    The predicate inspects metadata already loaded by the importer, never files.
    """
    selected = storage.get(identity)
    if selected is None:
        return True
    paths = tuple(_paths(selected))
    return bool(paths) and all(PurePosixPath(path).is_relative_to(media_root) for path in paths)


def contained_media_path(root: Path, relative: str) -> Path:
    """Resolve an archive address without admitting traversal or symlink escapes."""
    path = PurePosixPath(relative)
    if path.is_absolute() or ".." in path.parts or "\\" in relative:
        raise ValueError(f"Invalid media address: {relative}")
    resolved = (root / path).resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError(f"Media address leaves its root: {relative}")
    return resolved


def install_verified_payloads(source: Path, payloads: tuple[tuple[str, str, str], ...], *,
                              preserved: Path, production: Path, repo: Path) -> tuple[dict, ...]:
    """Preserve and install selected source/runtime/SHA256 rows, without recipes."""
    admitted = []
    for relative, runtime, digest in payloads:
        origin = contained_media_path(source, relative)
        if not PurePosixPath(runtime).is_relative_to("game/assets"):
            raise ValueError("Media payload leaves its authorized root")
        content = origin.read_bytes()
        if hashlib.sha256(content).hexdigest() != digest:
            raise ValueError(f"Media source checksum mismatch: {relative}")
        destinations = (contained_media_path(preserved, relative),
            contained_media_path(repo / "game/assets", str(PurePosixPath(runtime).relative_to("game/assets"))),
            contained_media_path(production / "game/assets", str(PurePosixPath(runtime).relative_to("game/assets"))))
        for target in destinations:
            if target.exists() and (not target.is_file() or target.read_bytes() != content):
                raise ValueError(f"Refusing to overwrite different media: {target}")
        admitted.append((origin, destinations, {"path": runtime, "bytes": len(content), "sha256": digest}))
    manifest = production / "art-manifest.json"
    previous = manifest.read_bytes()
    data = json.loads(previous)
    installed = {row["path"]: row for row in data["files"]}
    preserved.mkdir(parents=True, exist_ok=True)
    snapshot = preserved / "previous-art-manifest.json"
    if not snapshot.exists():
        snapshot.write_bytes(previous)
    for origin, destinations, row in admitted:
        for target in destinations:
            target.parent.mkdir(parents=True, exist_ok=True)
            if origin != target:
                shutil.copyfile(origin, target)
        installed[row["path"]] = row
    data["files"] = sorted(installed.values(), key=lambda row: row["path"])
    data["total_bytes"] = sum(row["bytes"] for row in data["files"])
    manifest.write_text(json.dumps(data, indent=2) + "\n")
    return tuple(row for _, _, row in admitted)
